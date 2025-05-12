# Discord Uptime Bot 🚀

A Discord bot built with Python and `discord.py` to uptime Discord bots! (Glitch hosted), user permissions (blacklist, whitelist, VIP), and roles. The bot uses MongoDB to store links and user data, with automatic link deletion after 30 days. It features interactive UI components (buttons, pagination) and logging for link actions.

## Features ✨
- **Link Management**: Users can add, remove, edit, and view links with commands like `!link add <url>`.
- **Permission System**: Owner can blacklist, whitelist, or grant VIP status to users, with corresponding roles.
- **MongoDB Integration**: Stores links and user statuses, with automatic cleanup of links older than 30 days.
- **Logging**: Logs link actions (add/remove/edit) to a designated channel.
- **Interactive UI**: Uses buttons for link removal, undo functionality, and paginated link display.
- **Rate Limiting**: Prevents command abuse with cooldowns.
- **Ephemeral Messages**: Private link display for user privacy.

## Requirements 📋
- Python 3.8 or higher
- A Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications)
- A MongoDB database (e.g., MongoDB Atlas)
- Discord server with roles for blacklist, whitelist, and VIP

## Installation 🛠️

1. **Clone or Download the Project**
   - Download the project files or clone the repository.

2. **Set Up a Virtual Environment** (Recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

## Install Dependencies

```bash
    pip install -r requirements.txt
```

## Configure the Bot ⚙️

    Replace your_discord_user_id with your Discord user ID.
    Replace blacklist_role_id, whitelist_role_id, and vip_role_id with the respective role IDs from your Discord server. Enable Developer Mode in Discord to copy IDs.
    Replace MONGO_URI with your MongoDB connection string (e.g., from MongoDB Atlas).
    Replace BOT_TOKEN with your Discord bot token from the Discord Developer Portal.

## Set Up Discord Bot 🔧

    Create a bot in the Discord Developer Portal.
    Enable the following bot permissions: Manage Roles, Send Messages, Embed Links, Read Message History.
    Invite the bot to your server using the OAuth2 URL generator with the bot and applications.commands scopes.

## Run the Bot ▶️


```bash
python bot.py
```

# Usage 📚

    User Commands (Prefix: !, configurable in config.json)
        !link add <url>: Add a new link (max 2 links, 5 for VIP).
        !link remove <link_id>: Remove a link with an undo option (60-second timeout).
        !link edit <link_id> <new_url>: Edit an existing link.
        !link show: View your links in a paginated, ephemeral embed.
    Owner Commands
        !blacklist @user: Blacklist a user and assign the blacklist role.
        !whitelist @user: Whitelist a user and assign the whitelist role.
        !vip @user: Grant VIP status and assign the VIP role.
        !log set #channel: Set a channel for logging link actions.
        !log remove: Remove the logging channel.
        !admin-links: Show the total number of links in the database.
        !admin-remove @user: Display up to 3 of a user's links with buttons to remove them.

# Notes 📝

    Blacklisted users cannot use link commands.
    Links are automatically deleted after 30 days.
    All commands use embeds with the bot's name (configurable in config.json).
    The bot requires proper permissions to manage roles and send messages.

# Project Structure 📁

```text
discord-bot/
├── bot.py           # Main bot script
├── config.json      # Configuration file (prefix, bot name, IDs)
├── .env            # Environment variables (MongoDB URI, bot token)
├── requirements.txt # Python dependencies
├── README.md       # This file
```
# Troubleshooting ⚠️

    Bot Not Responding: Check the bot token, server permissions, and ensure the bot is invited with the correct scopes.
    MongoDB Errors: Verify the MONGO_URI and ensure the database is accessible.
    Role Issues: Ensure the role IDs in config.json exist in the server and the bot has permission to manage roles.
    Dependency Issues: Update pip (pip install --upgrade pip) and reinstall dependencies.

# License 📜

This project is licensed under the MIT License. Feel free to modify and distribute as needed.

# Contact 📬

For issues or questions, contact the project maintainer or open an issue on the repository (if applicable).