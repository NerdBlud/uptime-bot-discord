import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from discord import app_commands
from pymongo import MongoClient
from bson.objectid import ObjectId
import asyncio
import re
import json
import datetime
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import aiohttp

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BOT_TOKEN = os.getenv("BOT_TOKEN")

try:
    with open("config.json") as f:
        config = json.load(f)
    required_keys = ["prefix", "bot_name", "owner_id", "blacklist_role_id", "whitelist_role_id", "vip_role_id"]
    for key in required_keys:
        if key not in config:
            raise KeyError(f"Missing {key} in config.json")
    BOT_NAME = config["bot_name"]
    OWNER_ID = int(config["owner_id"])
    BLACKLIST_ROLE_ID = int(config["blacklist_role_id"])
    WHITELIST_ROLE_ID = int(config["whitelist_role_id"])
    VIP_ROLE_ID = int(config["vip_role_id"])
except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
    print(f"Config error: {e}")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config["prefix"], intents=intents, case_insensitive=True)
        self.tree = app_commands.CommandTree(self)

bot = MyBot()

try:
    mongo = MongoClient(MONGO_URI)
    db = mongo["discord_bot"]
    links_col = db["links"]
    users_col = db["users"]
    settings_col = db["settings"]
except Exception as e:
    print(f"MongoDB connection error: {e}")
    exit(1)

url_pattern = re.compile(r'^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([\/\w .-]*)*\/?$')

def validate_url(url):
    return re.match(url_pattern, url) is not None

def make_embed(title, description, color=discord.Color.blurple()):
    embed = discord.Embed(title=f"{BOT_NAME} | {title}", description=description, color=color)
    embed.set_footer(text=BOT_NAME)
    embed.timestamp = datetime.datetime.utcnow()
    return embed

async def send_log(action, user, link_id=None, link_url=None):
    log_channel_id = settings_col.find_one({}).get("log_channel_id") if settings_col.find_one({}) else None
    if not log_channel_id:
        return
    channel = bot.get_channel(int(log_channel_id))
    if not channel:
        return
    embed = make_embed(
        "Link Action",
        f"**Action**: {action}\n**User**: {user.mention} (ID: {user.id})\n**Link ID**: {link_id or 'N/A'}\n**URL**: {link_url or 'N/A'}"
    )
    await channel.send(embed=embed)

@tasks.loop(hours=24)
async def delete_old_links():
    threshold = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    result = links_col.delete_many({"added_at": {"$lt": threshold}})
    print(f"[CLEANUP] Deleted {result.deleted_count} expired links.")

@tasks.loop(minutes=2.5)
async def keep_glitch_links_alive():
    try:
        async with aiohttp.ClientSession() as session:
            links = links_col.find({})
            for link in links:
                url = link["link"]
                if "glitch.me" in urlparse(url).netloc:
                    try:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                print(f"[PING] Successfully pinged {url}")
                            else:
                                print(f"[PING] Failed to ping {url} - Status: {response.status}")
                    except Exception as e:
                        print(f"[PING] Error pinging {url}: {e}")
    except Exception as e:
        print(f"[PING] Error in keep_glitch_links_alive task: {e}")

@bot.event
async def on_ready():
    if not delete_old_links.is_running():
        delete_old_links.start()
    if not keep_glitch_links_alive.is_running():
        keep_glitch_links_alive.start()
    await bot.tree.sync()
    print(f"{bot.user} has connected to Discord!")

def is_owner():
    def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

def get_user_status(user_id):
    user = users_col.find_one({"user_id": str(user_id)})
    return user["status"] if user else "none"

def set_user_status(user_id, status):
    users_col.update_one(
        {"user_id": str(user_id)},
        {"$set": {"status": status, "updated_at": datetime.datetime.utcnow()}},
        upsert=True
    )

async def apply_roles(member, status):
    roles_to_remove = [BLACKLIST_ROLE_ID, WHITELIST_ROLE_ID, VIP_ROLE_ID]
    for role_id in roles_to_remove:
        role = member.guild.get_role(role_id)
        if role and role in member.roles:
            await member.remove_roles(role)
    role_id = {
        "blacklist": BLACKLIST_ROLE_ID,
        "whitelist": WHITELIST_ROLE_ID,
        "vip": VIP_ROLE_ID
    }.get(status)
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role)
        else:
            print(f"Role ID {role_id} not found in guild")

class LinkPaginationView(View):
    def __init__(self, links, user):
        super().__init__(timeout=60)
        self.links = links
        self.user = user
        self.page = 0
        self.per_page = 5

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    def get_page_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_links = self.links[start:end]
        embed = make_embed("Your Links", "")
        for link in page_links:
            embed.add_field(name=str(link["_id"]), value=link["link"], inline=False)
        embed.set_footer(text=f"Page {self.page + 1}/{max(1, (len(self.links) + self.per_page - 1) // self.per_page)}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.grey, disabled=True)
    async def previous(self, interaction: discord.Interaction, button: Button):
        self.page -= 1
        self.children[0].disabled = self.page == 0
        self.children[1].disabled = self.page >= (len(self.links) - 1) // self.per_page
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.grey)
    async def next(self, interaction: discord.Interaction, button: Button):
        self.page += 1
        self.children[0].disabled = self.page == 0
        self.children[1].disabled = self.page >= (len(self.links) - 1) // self.per_page
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

class AdminRemoveView(View):
    def __init__(self, links, user):
        super().__init__(timeout=60)
        self.user = user
        for idx, link in enumerate(links):
            self.add_item(Button(
                label=f"Remove Link {idx + 1}",
                style=discord.ButtonStyle.danger,
                custom_id=str(link["_id"])
            ))

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Remove Link 1", style=discord.ButtonStyle.danger, custom_id="dummy")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        link_id = interaction.data["custom_id"]
        links_col.delete_one({"_id": ObjectId(link_id)})
        await send_log("Link Removed", interaction.user, link_id, None)
        await interaction.response.send_message(embed=make_embed("Link Removed", f"Link `{link_id}` has been removed."), ephemeral=True)

class UndoView(View):
    def __init__(self, link_data, user):
        super().__init__(timeout=60)
        self.link_data = link_data
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Undo", style=discord.ButtonStyle.green)
    async def undo(self, interaction: discord.Interaction, button: Button):
        links_col.insert_one(self.link_data)
        await send_log("Link Restored", interaction.user, str(self.link_data["_id"]), self.link_data["link"])
        await interaction.response.edit_message(embed=make_embed("Link Restored", f"Link `{self.link_data['_id']}` has been restored."), view=None)

@bot.command(name="blacklist")
@is_owner()
async def blacklist(ctx, member: discord.Member):
    set_user_status(member.id, "blacklist")
    await apply_roles(member, "blacklist")
    await ctx.send(embed=make_embed("User Blacklisted", f"{member.mention} has been blacklisted."))

@bot.command(name="whitelist")
@is_owner()
async def whitelist(ctx, member: discord.Member):
    set_user_status(member.id, "whitelist")
    await apply_roles(member, "whitelist")
    await ctx.send(embed=make_embed("User Whitelisted", f"{member.mention} has been whitelisted."))

@bot.command(name="vip")
@is_owner()
async def vip(ctx, member: discord.Member):
    set_user_status(member.id, "vip")
    await apply_roles(member, "vip")
    await ctx.send(embed=make_embed("VIP Granted", f"{member.mention} has been granted VIP access."))

@bot.command(name="log")
@is_owner()
async def log(ctx, action: str, channel: discord.TextChannel = None):
    if action.lower() == "set" and channel:
        settings_col.update_one({}, {"$set": {"log_channel_id": channel.id}}, upsert=True)
        await ctx.send(embed=make_embed("Logging Enabled", f"Logs will now be sent to {channel.mention}"))
    elif action.lower() == "remove":
        settings_col.update_one({}, {"$unset": {"log_channel_id": ""}})
        await ctx.send(embed=make_embed("Logging Disabled", "Logging channel has been removed."))
    else:
        await ctx.send(embed=make_embed("Invalid Usage", "Use `!log set #channel` or `!log remove`", color=discord.Color.red()))

@bot.command(name="admin-links")
@is_owner()
async def admin_links(ctx):
    total = links_col.count_documents({})
    await ctx.send(embed=make_embed("Total Links", f"There are currently **{total}** links in the database."))

@bot.command(name="admin-remove")
@is_owner()
async def admin_remove(ctx, member: discord.Member):
    user_links = list(links_col.find({"user_id": str(member.id)}).limit(3))
    if not user_links:
        await ctx.send(embed=make_embed("No Links Found", f"{member.mention} has no links to remove."))
        return
    view = AdminRemoveView(user_links, ctx.author)
    embed = make_embed("Remove Links", f"Choose which link(s) to remove for {member.mention}")
    for idx, link in enumerate(user_links):
        embed.add_field(name=f"Link {idx + 1}", value=f"ID: {link['_id']}\nURL: {link['link']}", inline=False)
    view.message = await ctx.send(embed=embed, view=view)

@bot.command(name="link")
@commands.cooldown(1, 5, commands.BucketType.user)
async def link_command(ctx, action: str, *args):
    user_id = str(ctx.author.id)
    status = get_user_status(user_id)
    if status == "blacklist":
        await ctx.send(embed=make_embed("Access Denied", "You are blacklisted from using link commands.", color=discord.Color.red()))
        return
    if action.lower() == "add":
        if len(args) != 1:
            await ctx.send(embed=make_embed("Usage Error", "Usage: !link add <url>", color=discord.Color.red()))
            return
        url = args[0]
        if not validate_url(url):
            await ctx.send(embed=make_embed("Invalid URL", "Please enter a valid URL.", color=discord.Color.red()))
            return
        user_links = list(links_col.find({"user_id": user_id}))
        max_links = 5 if status == "vip" else 2
        if len(user_links) >= max_links:
            await ctx.send(embed=make_embed("Limit Reached", f"You can only add up to {max_links} links."))
            return
        link_data = {
            "user_id": user_id,
            "link": url,
            "added_at": datetime.datetime.utcnow()
        }
        result = links_col.insert_one(link_data)
        await send_log("Link Added", ctx.author, str(result.inserted_id), url)
        view = View(timeout=60)
        view.add_item(Button(label="View Link", url=url, style=discord.ButtonStyle.link))
        await ctx.send(embed=make_embed("Link Added", f"URL added with ID `{result.inserted_id}`"), view=view)
    elif action.lower() == "remove":
        if len(args) != 1:
            await ctx.send(embed=make_embed("Usage Error", "Usage: !link remove <link_id>", color=discord.Color.red()))
            return
        link_id = args[0]
        try:
            link = links_col.find_one({"_id": ObjectId(link_id)})
        except:
            await ctx.send(embed=make_embed("Invalid ID", "Invalid link ID format.", color=discord.Color.red()))
            return
        if not link:
            await ctx.send(embed=make_embed("Not Found", "Link not found."))
            return
        if link["user_id"] != user_id and ctx.author.id != OWNER_ID:
            await ctx.send(embed=make_embed("Permission Denied", "You do not have permission to delete this link."))
            return
        links_col.delete_one({"_id": ObjectId(link_id)})
        await send_log("Link Removed", ctx.author, link_id, link["link"])
        view = UndoView(link, ctx.author)
        view.message = await ctx.send(embed=make_embed("Link Removed", f"Link `{link_id}` removed. Click below to undo."), view=view)
    elif action.lower() == "edit":
        if len(args) != 2:
            await ctx.send(embed=make_embed("Usage Error", "Usage: !link edit <link_id> <new_url>", color=discord.Color.red()))
            return
        link_id, new_url = args
        try:
            link = links_col.find_one({"_id": ObjectId(link_id)})
        except:
            await ctx.send(embed=make_embed("Invalid ID", "Invalid link ID format.", color=discord.Color.red()))
            return
        if not link:
            await ctx.send(embed=make_embed("Not Found", "Link not found."))
            return
        if link["user_id"] != user_id and ctx.author.id != OWNER_ID:
            await ctx.send(embed=make_embed("Permission Denied", "You do not have permission to edit this link."))
            return
        if not validate_url(new_url):
            await ctx.send(embed=make_embed("Invalid URL", "New URL is not valid.", color=discord.Color.red()))
            return
        links_col.update_one({"_id": ObjectId(link_id)}, {"$set": {"link": new_url}})
        await send_log("Link Edited", ctx.author, link_id, new_url)
        view = View(timeout=60)
        view.add_item(Button(label="View Updated Link", url=new_url, style=discord.ButtonStyle.link))
        await ctx.send(embed=make_embed("Link Updated", f"Link `{link_id}` updated."), view=view)
    elif action.lower() == "show":
        user_links = list(links_col.find({"user_id": user_id}))
        if not user_links:
            await ctx.send(embed=make_embed("No Links", "You have not added any links yet."), ephemeral=True)
            return
        view = LinkPaginationView(user_links, ctx.author)
        view.message = await ctx.send(embed=view.get_page_embed(), view=view, ephemeral=True)
    else:
        await ctx.send(embed=make_embed("Unknown Action", "Available actions: add, remove, edit, show", color=discord.Color.red()))

bot.run(BOT_TOKEN)