# GameVox Migration Guide

This document explains how to run the ISROBOT Discord bot on the GameVox platform.

## Overview

GameVox is a modern voice, video, and text chat platform for gamers. This bot is now compatible with both Discord and GameVox without any code changes - you only need to configure two environment variables!

## Prerequisites

1. **Create a GameVox Application**
   - Go to [https://developers.gamevox.com](https://developers.gamevox.com)
   - Sign in with your GameVox account
   - Click "New application"
   - Copy the bot token from the creation modal (this is shown only once, so save it securely)
   - Note your application ID

2. **Invite Bot to Your GameVox Server**
   - In the developer portal, go to your application's OAuth2 tab
   - Build an install URL with the permissions you need
   - Standard URL format: `https://gamevox.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot+applications.commands&permissions=8`
   - Share the URL with your GameVox server owner
   - They click the link, select a GameVox server they own, and confirm

## Configuration

### Step 1: Update `.env` File

Add or modify these environment variables in your `.env` file:

```env
# Set platform to gamevox
PLATFORM=gamevox

# Your GameVox bot token (from the developer portal)
GAMEVOX_BOT_TOKEN=your_gamevox_token_here

# Keep your Discord configuration for backwards compatibility
app_id=123456789012345678
secret_key=your_discord_token_here
server_id=123456789012345678
```

### Step 2: Start the Bot

Run the bot normally:

```bash
python main.py
```

The bot will automatically detect the `PLATFORM=gamevox` setting and configure itself to connect to GameVox instead of Discord.

## Switching Between Discord and GameVox

To switch platforms, simply change the `PLATFORM` environment variable:

- **For Discord (default):**
  ```env
  PLATFORM=discord
  ```

- **For GameVox:**
  ```env
  PLATFORM=gamevox
  ```

The bot will automatically configure the appropriate API endpoints and use the correct token.

## What's Different?

The compatibility surface aims for 100% - your bot's logic doesn't need to know it's not Discord. However, be aware of a few things:

- **Snowflake epoch**: Identical to Discord's (1420070400000, 2015-01-01 UTC). Parsers written for Discord work on GameVox IDs unchanged.
- **Threads / Forum posts**: Not yet supported on GameVox.
- **Voice**: Works with Lavalink. No special config required - `VOICE_SERVER_UPDATE` points to compatible GameVox voice gateway and Lavalink handles the rest.
- **Custom emojis**: Limited in v1 - Unicode emojis fully work, custom guild emojis have limitations.
- **Latency**: Bots hosted outside us-east will see ~80–150ms added latency on writes due to Aurora write forwarding. Host in us-east for best performance.

## Testing

To verify your bot is running correctly on GameVox:

1. Start the bot with `PLATFORM=gamevox`
2. Watch for log messages like:
   ```
   🎮 Configuring bot for GameVox platform
   ✅ GameVox bot token configured
   ```
3. Check that the bot connects without errors
4. Test a simple command (e.g., `!ping`) to verify functionality

If the bot successfully connects and responds to commands, your migration is complete!

## Troubleshooting

### Bot won't connect

- **Check GAMEVOX_BOT_TOKEN**: Ensure it's correct and properly set in `.env`
- **Check PLATFORM setting**: Verify `PLATFORM=gamevox` is set
- **Check logs**: Look for error messages about token validation or API connectivity

### Commands not responding

- **Check bot permissions**: Ensure the bot has appropriate permissions on the GameVox server
- **Check channel access**: Verify the bot can read and write messages in the relevant channels

### API errors

- **Verify bot token**: GameVox tokens are different from Discord tokens - ensure you're using the correct one
- **Check network**: Ensure your bot can reach `https://bot-api.gamevox.com` and `wss://gateway.gamevox.com`

## References

- [GameVox Developer Portal](https://developers.gamevox.com)
- [GameVox Migration Docs](https://developers.gamevox.com/docs/migrating)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)

## Support

For issues or questions about GameVox compatibility, please:
1. Check the [GameVox Developer Documentation](https://developers.gamevox.com/docs)
2. Review the error logs for specific error messages
3. Open an issue on the repository with details about your configuration and the error
