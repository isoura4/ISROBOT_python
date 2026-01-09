# ISROBOT - Discord Bot

A feature-rich Discord bot built with Python and discord.py, offering various interactive commands, mini-games, Twitch stream notifications, and AI integration.

## Features

### 🤖 AI Integration
- **AI Chat**: Ask questions to an AI assistant powered by Ollama
- **Configurable Models**: Support for different AI models through Ollama
- **Smart Responses**: AI responses formatted in beautiful Discord embeds

### 🎮 Mini-Games
- **Counter Game**: A collaborative counting game where users must count sequentially without the same user counting twice in a row
- **Coin Flip**: Simple coin flip command for random decisions

### 📊 XP System
- **Level System**: Users gain XP for sending messages and level up automatically
- **Leaderboard**: View server rankings based on levels and XP
- **Profile Command**: Check your or another user's level, XP, and message count

### 🎥 Twitch Integration
- **Stream Notifications**: Automatically announce when configured streamers go live
- **Stream Management**: Add streamers to watch list with custom notification channels
- **Rich Embeds**: Beautiful stream announcements with thumbnails and stream details

### 📺 YouTube Integration
- **Video Notifications**: Automatically announce when a channel uploads a new video
- **Short Notifications**: Notify when a channel posts a new YouTube Short
- **Flexible Configuration**: Choose which types of content to monitor (videos, shorts)
- **Handle Support**: Add channels using either their channel ID or @handle (e.g., @el-dorado-community)
- **Rich Embeds**: Beautiful announcements with thumbnails and video details

### 🔧 Administrative Tools
- **Reload Command**: Hot-reload bot extensions without restarting
- **Configuration Commands**: Set up mini-games and stream notifications
- **Permissions**: Admin-only commands for server management

### 🛡️ Moderation System 
- **Smart Warning System**: Issue warnings with automatic escalation
  - Intelligent warning decay based on warn count
  - Automatic muting at 2 and 3 warnings
  - Manual moderator intervention at 4+ warnings
- **Mute Management**: Temporary mutes with automatic expiration
- **User Appeals**: Allow users to appeal warnings with review system
- **AI-Assisted Moderation**: Ollama-powered message flagging
  - Automatic detection of toxicity, spam, NSFW, harassment
  - Moderators make all final decisions
  - Conservative threshold to avoid false positives
- **Comprehensive Audit Trail**: Immutable logging of all actions
- **Context Menu Integration**: Right-click messages to warn users
- **Flexible Configuration**: Per-guild customization of all settings

### 🏓 Utility Commands
- **Ping**: Simple response command
- **Bot Ping**: Check bot latency and connection status

## Installation

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Twitch API credentials (for stream features)
- YouTube Data API v3 key (for YouTube features)
- Ollama server (for AI features)

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
   youtube_api_key=YOUR_YOUTUBE_API_KEY
   ollama_host=http://localhost:11434
   ollama_model=llama2
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
├── commands/               # Bot command modules
│   ├── ai.py               # AI chat integration with Ollama
│   ├── coinflip.py         # Coin flip command
│   ├── count.py            # Counter game setup
│   ├── moderation.py       # Moderation commands (warn, mute, etc.)
│   ├── moderation_config.py # Moderation configuration commands
│   ├── moderation_context.py # Context menu for warnings
│   ├── user_moderation.py  # User appeal commands
│   ├── ping.py             # Basic ping command
│   ├── ping_bot.py         # Bot latency command
│   ├── reload.py           # Hot-reload extensions
│   ├── stream.py           # Twitch stream integration
│   ├── xp_system.py        # XP and leveling system
│   ├── xp_voice.py         # Voice XP tracking
│   └── youtube.py          # YouTube channel integration
└── utils/                  # Utility modules
    ├── ai_moderation.py    # AI message analysis with Ollama
    └── moderation_utils.py # Moderation helper functions
```

## Commands

### General Commands
- `/ping` - Responds with "Pong!"
- `/ping_bot` - Shows bot latency in milliseconds
- `/coinflip` - Flips a coin and shows the result
- `/ai <question>` - Ask a question to the AI assistant


### XP System Commands
- `/level [user]` - Display level information for yourself or another user
- `/leaderboard` - Show the server's XP leaderboard

### Minigame Commands
All minigame commands must be run in the designated minigame channel (set by an admin).

> **Note:** The minigame system can be enabled/disabled per-server with `/minigame enable` and `/minigame disable`, or globally via the `.env` file by setting `minigame_enabled=false`.

#### Economy & Wallet
- `/wallet` - View your coins, XP, and level
- `/history [type]` - View recent transactions (filter by type: all, quests, shop, trades, captures, duels)
- `/inventory` - View items in your inventory

#### Daily Quests
- `/daily claim` - Claim your daily quests (assigns new quests if none exist)
- `/daily status` - View progress on your current daily quests

#### Quest Management
- `/quest list` - List all your active quests and their progress
- `/quest claim [quest_id]` - Claim rewards for completed quests

#### Shop System
- `/shop list` - View available shop items
- `/shop buy <item_id> [quantity]` - Purchase an item from the shop

#### Trading System
- `/trade offer @user --coins X --xp Y` - Send a trade offer to another player
- `/trade accept <trade_id>` - Accept a pending trade offer
- `/trade cancel <trade_id>` - Cancel a pending or escrowed trade
- `/trade pending` - View your pending trades (sent and received)

#### Minigames
- `/capture <stake>` - Stake coins for a chance to win more (10-1000 coins)
- `/duel @opponent <bet>` - Challenge another player to a duel (10-500 coins each)
- `/stats` - View your capture and duel statistics

### Administrative Commands (Admin Only)
- `/count <channel>` - Set up the counter mini-game in a specific channel
- `/minigame enable` - Enable the minigame system for this server
- `/minigame disable` - Disable the minigame system for this server
- `/minigame set-channel <channel>` - Set the minigame channel for this server
- `/minigame clear-channel` - Remove the minigame channel restriction
- `/minigame allow-channel <channel>` - Add a quest exception channel
- `/minigame remove-channel <channel>` - Remove a quest exception channel
- `/minigame stats` - View minigame configuration and statistics
- `/stream_add <streamer_name> <channel>` - Add a streamer to the notification list
- `/stream_remove <streamer_name>` - Remove a streamer from the notification list
- `/youtube_add <channel_id_or_handle> <channel> [notify_videos] [notify_shorts] [ping_role]` - Add a YouTube channel to monitor (accepts channel ID or @handle)
- `/youtube_remove <channel_name>` - Remove a YouTube channel from monitoring
- `/reload` - Reload all bot extensions

### Moderation Commands (Moderator+)
- `/warn <user> <reason>` - Issue a warning to a user
- `/warns <user>` - View warning history for a user
- `/unwarn <user> [reason]` - Remove a warning from a user
- `/mute <user> <duration> <reason>` - Temporarily mute a user (e.g., 1h, 30m, 1d)
- `/unmute <user>` - Remove an active mute
- `/modlog [user]` - View moderation logs (server-wide or for specific user)
- **Context Menu**: Right-click message → Apps → "Warn User"

### Moderation Configuration (Administrator Only)
- `/modconfig view` - Display current moderation configuration
- `/modconfig set <parameter> <value>` - Configure moderation settings
  - **Channels**: `log_channel`, `appeal_channel`, `ai_flag_channel`
  - **AI Settings**: `ai_enabled`, `ai_confidence_threshold`, `ai_model`, `ollama_host`
  - **Warning Decay**: `warn_1_decay_days`, `warn_2_decay_days`, `warn_3_decay_days`
  - **Mute Durations**: `mute_duration_2`, `mute_duration_3`
  - **Rules**: `rules_message_id`

### User Commands
- `/appeal <reason>` - Submit an appeal against your warnings (48h cooldown)

## Database Schema

The bot uses SQLite with the following tables:

### Users Table
- Stores user XP, levels, message counts, and economy data
- Primary key: (guildId, userId)

### Streamers Table
- Manages Twitch streamers for notifications
- Tracks announcement status and stream details

### YouTube Channels Table
- Manages YouTube channels for notifications
- Tracks last video/short IDs to prevent duplicates
- Configurable notification types (videos, shorts)

### Counter Game Table
- Stores counter game configuration per server
- Tracks current count and last user

### Minigame Tables
- **guild_settings** - Per-guild configuration (minigame channel, taxes, limits)
- **quest_exception_channels** - Channels where quest actions are allowed
- **quests** - Quest templates (daily, random, event types)
- **user_quests** - User's assigned quests and progress
- **user_daily_tracking** - Daily streaks and XP transfer limits
- **shop_items** - Available shop items with prices and effects
- **user_inventory** - User's owned consumable items
- **user_active_effects** - Currently active item effects
- **trades** - P2P trade records with escrow status
- **transactions** - Complete transaction ledger for auditing
- **user_cooldowns** - Action cooldowns (capture, duel)

### Moderation Tables
- **Warnings**: Current warning count per user per guild
- **Warning History**: Immutable audit trail of all moderation actions
- **Moderation Appeals**: User appeal submissions and moderator decisions
- **Moderation Config**: Per-guild configuration for moderation system
- **AI Flags**: Messages flagged by AI for moderator review
- **Active Mutes**: Current mutes with expiration timestamps

## Configuration

### Bot Permissions Required
- Send Messages
- Use Slash Commands
- Embed Links
- Add Reactions
- Read Message History
- Manage Messages (for context menu message deletion)
- Moderate Members (for timeout/mute feature)
- Connect (for voice channels)
- Speak (for voice channels)

### Twitch API Setup
1. Create an application at [Twitch Developers](https://dev.twitch.tv/)
2. Get your Client ID and Client Secret
3. Add them to your `.env` file

### YouTube API Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3
4. Create credentials (API Key)
5. Add the API key to your `.env` file as `youtube_api_key`
6. Note: YouTube API has quota limits (10,000 units/day by default)

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

### YouTube Notifications
- Checks every 5 minutes for new content
- Monitors videos, shorts, and live streams independently
- Flexible configuration to choose which content types to monitor
- Supports both channel IDs and handles (e.g., @channel-name) for easy channel identification
- Distinguishes between regular videos (>60 seconds) and shorts (≤60 seconds)
- Rich embeds with video thumbnails and direct links
- Role mentions for notifications (optional)
- Prevents duplicate notifications for the same content

### AI Assistant
- Powered by Ollama for local AI inference
- Configurable AI models (default: llama2)
- Question length limit (500 characters) to prevent abuse
- Response length limit (1024 characters) for Discord compatibility
- Asynchronous processing to prevent bot blocking
- Rich embed formatting for AI responses
- **Content Moderation**: Automatic filtering of inappropriate, NSFW, and illegal content
  - Input validation to reject inappropriate questions
  - System prompts to guide AI behavior
  - Output filtering to block inappropriate responses
  - Compliance with server rules and community guidelines

### Minigame System

The minigame system provides a comprehensive economy with quests, trading, and gambling features.

#### Channel Restriction
- All minigame commands require a designated minigame channel
- Admins set the channel with `/minigame set-channel #channel`
- Exception channels can be added for quest tracking in other channels

#### Daily Quests
- Users receive 1 guaranteed + up to 2 random quests daily
- Streak bonuses: 7 days = 1.5x, 14 days = 2.0x, 30 days = 2.5x rewards
- Quest types: messages_sent, counting_participation, coinflip_used, capture_attempt, etc.

#### Shop System
- Items can cost coins, XP, or both
- Consumable items are stored in user inventory
- Effects: XP boosts, capture luck, quest rerolls, trade fee waivers

#### Trading System
- P2P trades for coins and XP
- Escrow period (5 minutes) before completion
- Tax on trades (default 10%)
- Daily XP transfer limits (10% of user XP or 500, whichever is lower)
- Confirmation required for trades that would cause level loss

#### Capture Game
- Stake 10-1000 coins per attempt
- Success odds based on XP level and stake amount (30-65%)
- Winners get 2x stake + bonus, losers get consolation XP
- 60-second cooldown between attempts

#### Arena Duels
- Both players bet equal amounts (10-500 coins each)
- Winner takes pot minus tax (default 10%)
- Odds based on level difference (up to ±20% advantage)
- 5-minute cooldown for challenger

#### Configuration Defaults
- Trade tax: 10%
- Duel tax: 10%
- Daily XP transfer cap: 10% of user XP or 500 max
- Capture cooldown: 60 seconds
- Duel cooldown: 300 seconds

#### Running Migrations
To set up the minigame tables, run:
```bash
python db_migrations.py
```

This will:
1. Create a backup of the database
2. Remove the legacy 'corners' column from users table
3. Create all minigame tables
4. Seed default quests and shop items
## Moderation System

The comprehensive moderation system provides advanced tools for server management with AI assistance.

### Warning System

**Escalation Levels:**
1. **First Warning**: User receives DM notification
2. **Second Warning**: Automatic 1-hour mute + DM notification
3. **Third Warning**: Automatic 24-hour mute + DM notification
4. **Fourth+ Warning**: No automatic action - moderator must decide manually

**Intelligent Warning Decay:**
- Warnings automatically expire based on warn count
- Higher warn counts = longer decay periods
- **1 warning**: Expires after 7 days
- **2 warnings**: Expires after 14 days
- **3 warnings**: Expires after 21 days
- **4+ warnings**: Expires after 28 days
- When warn count reaches 0, active mute is automatically removed
- All decay events are logged and users receive DM notifications

### Mute System

**Features:**
- Uses Discord's native timeout feature
- Automatic expiration tracking
- Manual mute/unmute commands
- Automatic removal when warnings reach 0
- DM notifications for mute applied/expired

**Duration Format:**
- Examples: `1h` (1 hour), `30m` (30 minutes), `1d` (1 day), `2h30m` (2 hours 30 minutes)

### Appeal System

**User Perspective:**
- Users can appeal warnings using `/appeal <reason>`
- 48-hour cooldown between appeals
- Maximum 1000 characters for appeal reason
- Appeal status notifications via DM
- Cannot view own warning count (prevents gaming the system)

**Moderator Perspective:**
- Appeals posted to configured appeal channel
- View user's warning history with appeal
- Approve or deny with custom decision message
- Approved appeals automatically remove 1 warning
- All decisions logged and DMed to user

### AI-Assisted Moderation

**How It Works:**
1. Every message is analyzed by Ollama (if AI enabled)
2. AI scores message 0-100 based on server rules
3. Messages scoring above threshold are flagged
4. Flags appear in moderation log with:
   - AI confidence score and risk level
   - Violation category (Toxicity, Spam, NSFW, Harassment, Misinformation)
   - AI reasoning
   - Link to message and context
5. Moderators review and take action (warn, review, or ignore)

**Safety Guardrails:**
- ✅ AI never auto-deletes messages
- ✅ AI never auto-mutes or bans users
- ✅ Moderators must click button to take action
- ✅ Conservative threshold to minimize false positives
- ✅ System continues normally if Ollama unavailable
- ✅ Temperature set to 0.3 for consistent decisions

**Risk Levels:**
- 🟢 **Info** (0-39): May be worth reviewing
- 🟡 **Low** (40-59): Borderline content
- 🟠 **Medium** (60-79): Should be reviewed
- 🔴 **High** (80-100): Immediate attention needed

### Configuration

**Initial Setup:**
1. Configure moderation log channel:
   ```
   /modconfig set log_channel #mod-log
   ```

2. Configure appeal channel:
   ```
   /modconfig set appeal_channel #appeals
   ```

3. Enable AI moderation:
   ```
   /modconfig set ai_enabled true
   /modconfig set ai_flag_channel #ai-flags
   /modconfig set ai_confidence_threshold 60
   ```

4. (Optional) Set rules message for AI context:
   ```
   /modconfig set rules_message_id 123456789012345678
   ```

**Customization:**
- Adjust warning decay times per warn level
- Customize automatic mute durations
- Set AI confidence threshold (0-100)
- Choose AI model and Ollama host
- Configure all channels independently

### Moderation Log

All moderation actions are logged in the configured log channel with rich embeds:
- ⚠️ Warnings issued
- ✅ Warnings removed/expired
- 🔇 Mutes applied
- 🔊 Mutes removed/expired
- 📝 Appeals created
- ⚖️ Appeals reviewed

### Best Practices

1. **Start Conservative**: Begin with higher AI threshold (70+) and lower it as needed
2. **Review Regularly**: Check AI flags daily to provide feedback
3. **Document Rules**: Set up clear server rules for AI context
4. **Train Moderators**: Ensure team understands the appeal process
5. **Monitor Logs**: Review moderation log channel regularly
6. **Adjust Settings**: Fine-tune decay times and thresholds based on your community

### Privacy & Data

- All data stored locally in SQLite database
- No external APIs except Ollama (runs locally)
- User messages analyzed only if AI enabled
- Complete audit trail for transparency
- Appeals and warnings are permanent record

## Dependencies

The bot requires the following Python packages:
- `discord.py>=2.3.0` - Discord API wrapper
- `python-dotenv>=1.0.0` - Environment variable management
- `aiohttp>=3.8.0` - HTTP client for API requests
- `PyNaCl>=1.5.0` - Voice functionality support
- `ollama>=0.5.0` - Ollama AI integration

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
