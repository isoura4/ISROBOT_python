# ISROBOT - Discord Bot

A feature-rich Discord bot built with Python and discord.py, offering various interactive commands, mini-games and Twitch stream notifications.

## Features

### 🎮 Mini-Games
- **Counter Game**: A collaborative counting game where users must count sequentially without the same user counting twice in a row
- **Coin Flip**: Simple coin flip command for random decisions

### 📊 XP System
- **Level System**: Users gain XP for sending messages and level up automatically
- **Leaderboard**: View server rankings based on levels and XP
- **Profile Command**: Check your or another user's level, XP, and message count

### �🎥 Twitch Integration
- **Stream Notifications**: Automatically announce when configured streamers go live
- **Stream Management**: Add streamers to watch list with custom notification channels
- **Rich Embeds**: Beautiful stream announcements with thumbnails and stream details

### 🔧 Administrative Tools
- **Reload Command**: Hot-reload bot extensions without restarting
- **Configuration Commands**: Set up mini-games and stream notifications
- **Permissions**: Admin-only commands for server management

### 🏓 Utility Commands
- **Ping**: Simple response command
- **Bot Ping**: Check bot latency and connection status

## Installation

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Twitch API credentials (for stream features)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ISROBOT_python
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg** (required for music functionality)
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Windows**: Download from [FFmpeg official site](https://ffmpeg.org/download.html)

4. **Create environment file**
   Create a `.env` file in the root directory with the following variables:
   ```env
   app_id=YOUR_BOT_APPLICATION_ID
   secret_key=YOUR_BOT_TOKEN
   server_id=YOUR_DISCORD_SERVER_ID
   db_path=database.sqlite3
   twitch_client_id=YOUR_TWITCH_CLIENT_ID
   twitch_client_secret=YOUR_TWITCH_CLIENT_SECRET
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

## Project Structure

```
ISROBOT_python/
├── main.py                 # Main bot file and event handlers
├── database.py             # Database setup and connection utilities
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
├── database.sqlite3        # SQLite database (auto-created)
├── discord.log             # Bot logs (auto-created)
└── commands/               # Bot command modules
    ├── coinflip.py         # Coin flip command
    ├── count.py            # Counter game setup
    ├── music.py            # Music playback functionality
    ├── ping.py             # Basic ping command
    ├── ping_bot.py         # Bot latency command
    ├── reload.py           # Hot-reload extensions
    ├── stream.py           # Twitch stream integration
    └── xp_system.py        # XP and leveling system
```

## Commands

### General Commands
- `/ping` - Responds with "Pong!"
- `/ping_bot` - Shows bot latency in milliseconds
- `/coinflip` - Flips a coin and shows the result


### XP System Commands
- `/level [user]` - Display level information for yourself or another user
- `/leaderboard` - Show the server's XP leaderboard

### Administrative Commands (Admin Only)
- `/count <channel>` - Set up the counter mini-game in a specific channel
- `/stream_add <streamer_name> <channel>` - Add a streamer to the notification list
- `/reload` - Reload all bot extensions

## Database Schema

The bot uses SQLite with the following tables:

### Users Table
- Stores user XP, levels, message counts, and economy data
- Primary key: (guildId, userId)

### Streamers Table
- Manages Twitch streamers for notifications
- Tracks announcement status and stream details

### Counter Game Table
- Stores counter game configuration per server
- Tracks current count and last user

## Configuration

### Bot Permissions Required
- Send Messages
- Use Slash Commands
- Embed Links
- Add Reactions
- Read Message History
- Connect (for voice channels)
- Speak (for voice channels)

### Twitch API Setup
1. Create an application at [Twitch Developers](https://dev.twitch.tv/)
2. Get your Client ID and Client Secret
3. Add them to your `.env` file

## Features in Detail

### Counter Game
Users must count sequentially starting from 1. Rules:
- Each number must be exactly one more than the previous
- The same user cannot count twice in a row
- Breaking rules resets the counter to 0

### XP System
- Users gain 15-25 XP per message (with 1-minute cooldown)
- Level calculation: `floor(sqrt(xp / 125)) + 1`
- Automatic level-up notifications

### Stream Notifications
- Checks every 5 minutes for live streams
- Prevents duplicate notifications
- Rich embeds with stream thumbnails and details

## Dependencies

The bot requires the following Python packages:
- `discord.py>=2.3.0` - Discord API wrapper
- `python-dotenv>=1.0.0` - Environment variable management
- `aiohttp>=3.8.0` - HTTP client for API requests
- `PyNaCl>=1.5.0` - Voice functionality support

## Logging

The bot logs important events to `discord.log` including:
- Command executions
- Error messages
- Extension loading/reloading
- Database operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues, questions, or feature requests, please create an issue in the repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details.