# ISROBOT Moderation System - Complete Guide

This document provides comprehensive documentation for the ISROBOT moderation system, including setup, usage, and best practices.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [Configuration](#configuration)
5. [Moderator Guide](#moderator-guide)
6. [User Guide](#user-guide)
7. [AI Moderation](#ai-moderation)
8. [Advanced Topics](#advanced-topics)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The ISROBOT moderation system is a comprehensive solution for Discord server moderation that combines:

- **Intelligent Warning System**: Progressive escalation with automatic decay
- **Temporary Muting**: Automatic muting at warning thresholds
- **User Appeals**: Allow users to contest warnings
- **AI Assistance**: Ollama-powered message flagging (optional)
- **Complete Audit Trail**: Immutable logging of all actions
- **User-Friendly**: Context menus and slash commands

### Core Principles

✅ **Human Control**: AI assists but never makes final decisions  
✅ **Transparency**: Users notified of all actions, can appeal  
✅ **Progressive**: Gradual escalation with second chances  
✅ **Customizable**: Per-guild configuration for all settings  
✅ **Privacy-First**: All data stored locally, no external APIs  

---

## Quick Start

### 1. Initial Setup

Set up your moderation channels:

```
/modconfig set log_channel #mod-log
/modconfig set appeal_channel #appeals
```

### 2. Issue First Warning

Warn a user using slash command:

```
/warn @user Spam in general chat
```

Or right-click a message → Apps → "Warn User"

### 3. View Warning History

Check a user's warnings:

```
/warns @user
```

### 4. Enable AI Moderation (Optional)

```
/modconfig set ai_enabled true
/modconfig set ai_flag_channel #ai-flags
/modconfig set ai_confidence_threshold 60
```

---

## Core Concepts

### Warning Escalation

| Warn Count | Automatic Action | User Impact |
|-----------|-----------------|-------------|
| 1 | DM notification | Warning issued |
| 2 | 1-hour mute + DM | Cannot send messages for 1 hour |
| 3 | 24-hour mute + DM | Cannot send messages for 24 hours |
| 4+ | None | Moderator must decide action |

### Warning Decay

Warnings automatically expire based on warn count:

| Current Warns | Decay Period | Rationale |
|--------------|-------------|-----------|
| 1 | 7 days | Quick redemption for first-time issues |
| 2 | 14 days | More time needed after second offense |
| 3 | 21 days | Significant time to demonstrate improvement |
| 4+ | 28 days | Extended period for repeated violations |

**Important Notes:**
- Only the oldest warning decays per cycle
- When warn count reaches 0, active mute is removed
- Users receive DM notification when warnings decay
- All decay events logged in moderation log

### Mute System

**Automatic Mutes:**
- Triggered at 2 and 3 warnings
- Duration configurable per server
- Uses Discord's native timeout feature
- Automatically removed when expired

**Manual Mutes:**
- Issue with `/mute` command
- Specify custom duration (e.g., `1h`, `30m`, `1d`)
- Independent of warning system
- Tracked with expiration

---

## Configuration

### View Current Configuration

```
/modconfig view
```

### Set Configuration Parameters

```
/modconfig set <parameter> <value>
```

### Available Parameters

#### Channels

| Parameter | Description | Example |
|-----------|-------------|---------|
| `log_channel` | Where moderation actions are logged | `/modconfig set log_channel #mod-log` |
| `appeal_channel` | Where user appeals appear | `/modconfig set appeal_channel #appeals` |
| `ai_flag_channel` | Where AI flags messages | `/modconfig set ai_flag_channel #ai-flags` |

#### AI Settings

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `ai_enabled` | Enable/disable AI flagging | `/modconfig set ai_enabled true` | true |
| `ai_confidence_threshold` | Minimum score to flag (0-100) | `/modconfig set ai_confidence_threshold 65` | 60 |
| `ai_model` | Ollama model name | `/modconfig set ai_model llama2` | llama2 |
| `ollama_host` | Ollama server URL | `/modconfig set ollama_host http://localhost:11434` | http://localhost:11434 |

#### Warning Decay

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `warn_1_decay_days` | Days for 1 warning to decay | `/modconfig set warn_1_decay_days 7` | 7 |
| `warn_2_decay_days` | Days for 2 warnings to decay | `/modconfig set warn_2_decay_days 14` | 14 |
| `warn_3_decay_days` | Days for 3 warnings to decay | `/modconfig set warn_3_decay_days 21` | 21 |

#### Mute Durations

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `mute_duration_2` | Auto-mute duration at 2 warns (seconds) | `/modconfig set mute_duration_2 3600` | 3600 (1 hour) |
| `mute_duration_3` | Auto-mute duration at 3 warns (seconds) | `/modconfig set mute_duration_3 86400` | 86400 (24 hours) |

#### Rules

| Parameter | Description | Example |
|-----------|-------------|---------|
| `rules_message_id` | Message ID containing server rules (for AI context) | `/modconfig set rules_message_id 123456789` |

---

## Moderator Guide

### Issuing Warnings

**Method 1: Slash Command**

```
/warn @user <reason>
```

Example:
```
/warn @JohnDoe Spam in #general
```

**Method 2: Context Menu**

1. Right-click on the offending message
2. Click "Apps" → "Warn User"
3. Enter additional notes (optional)
4. Confirm

**What Happens:**
- Warning count incremented
- User receives DM notification
- Action logged in mod-log
- Automatic mute applied if at 2 or 3 warnings
- Message can be deleted (context menu only)

### Viewing Warning History

```
/warns @user
```

Shows:
- Current warning count
- Full moderation history
- Time until next decay
- All previous actions

### Removing Warnings

```
/unwarn @user [reason]
```

Example:
```
/unwarn @JohnDoe Appeal approved - mistake
```

**What Happens:**
- Warning count decremented
- If count reaches 0, active mute removed
- Action logged in mod-log
- User not notified (intentional - moderator discretion)

### Manual Muting

```
/mute @user <duration> <reason>
```

Examples:
```
/mute @JohnDoe 1h Spamming voice channels
/mute @JohnDoe 30m Disrupting discussion
/mute @JohnDoe 2d Repeated violations
```

**Duration Format:**
- `1h` = 1 hour
- `30m` = 30 minutes
- `1d` = 1 day
- `2h30m` = 2 hours 30 minutes

### Unmuting

```
/unmute @user
```

Removes active mute immediately.

### Viewing Moderation Logs

**Server-wide logs (recent 20 actions):**
```
/modlog
```

**User-specific logs:**
```
/modlog @user
```

### Reviewing Appeals

Appeals appear in the configured appeal channel with:
- User information
- Current warning count
- Appeal reason
- Recent moderation history

**Actions:**
1. Click **✅ Approve** to accept appeal (removes 1 warning)
2. Click **❌ Deny** to reject appeal (opens modal for reason)

**What Happens on Approval:**
- 1 warning removed
- If count reaches 0, mute removed
- User receives DM with decision
- Action logged

**What Happens on Denial:**
- User receives DM with decision and reason
- No changes to warning count
- Action logged

---

## User Guide

### Understanding Warnings

When you receive a warning:
1. You'll receive a DM explaining the reason
2. The message shows your current warning count
3. You can read server rules (if configured)
4. You can appeal if you believe it's unjustified

### Warning Consequences

- **1 warning**: Just a notification
- **2 warnings**: Automatically muted for 1 hour
- **3 warnings**: Automatically muted for 24 hours
- **4+ warnings**: Moderators will decide next steps

### Automatic Mutes

- Applied automatically at 2 and 3 warnings
- You'll receive a DM explaining:
  - Why you were muted
  - How long the mute lasts
  - When it expires
- Cannot be manually removed (must wait for expiration)

### Warning Expiration

Good news! Warnings expire over time:
- If you have 1 warning: Expires in 7 days
- If you have 2 warnings: Expires in 14 days
- If you have 3 warnings: Expires in 21 days
- If you have 4+ warnings: Expires in 28 days

When a warning expires:
- You'll receive a DM notification
- Your warning count decreases by 1
- If you reach 0 warnings, any active mute is removed

### Submitting an Appeal

If you believe a warning was unjustified:

```
/appeal <your reason>
```

Example:
```
/appeal I was banned for spam but I was sharing a relevant resource for the discussion topic. I didn't intend to spam and won't repeat this if it's against the rules.
```

**Requirements:**
- Maximum 1000 characters
- Can only appeal if you have active warnings
- Can only have 1 pending appeal at a time
- Must wait 48 hours between appeals

**What Happens:**
1. Your appeal is sent to moderators
2. You receive confirmation DM
3. Moderators review with your full history
4. You receive DM with their decision

**If Approved:**
- 1 warning removed
- If count reaches 0, mute removed
- Moderator explains decision

**If Denied:**
- Warning count unchanged
- Moderator explains reason
- Can contact administrator for escalation

---

## AI Moderation

### How It Works

1. **Message Analysis**: Every message analyzed by Ollama AI
2. **Scoring**: AI scores 0-100 based on server rules and content
3. **Flagging**: Messages above threshold flagged for review
4. **Moderator Review**: Human moderator reviews and decides action

### Risk Levels

The AI assigns risk levels based on score:

| Score | Risk Level | Meaning |
|-------|-----------|---------|
| 0-39 | 🟢 Info | Generally acceptable, may be worth noting |
| 40-59 | 🟡 Low | Borderline content, context needed |
| 60-79 | 🟠 Medium | Likely violation, should review |
| 80-100 | 🔴 High | Clear violation, immediate attention |

### Violation Categories

- **Toxicity**: Insults, aggression, negativity
- **Spam**: Repetitive, promotional, low-value
- **NSFW**: Adult content, inappropriate material
- **Harassment**: Targeted attacks, bullying
- **Misinformation**: False or misleading information
- **None**: No violation detected

### Moderator Actions on Flags

When reviewing an AI flag:

1. **⚠️ WARN**: Opens warn modal, issues warning immediately
2. **🔍 REVIEW**: Mark as reviewing, shows conversation context
3. **✅ IGNORE**: Mark as false positive, removes from queue

### Configuring AI

**Enable AI:**
```
/modconfig set ai_enabled true
```

**Set Threshold:**
```
/modconfig set ai_confidence_threshold <0-100>
```

- **Higher threshold** (70-80): Fewer flags, catches only obvious violations
- **Medium threshold** (60-70): Balanced approach (recommended)
- **Lower threshold** (40-60): More flags, catches borderline content

**Set AI Flag Channel:**
```
/modconfig set ai_flag_channel #ai-flags
```

**Configure Server Rules:**
```
/modconfig set rules_message_id <message_id>
```

To get message ID:
1. Enable Developer Mode in Discord settings
2. Right-click the rules message
3. Click "Copy Message ID"
4. Use in command above

### AI Safety Features

✅ **AI Never:**
- Auto-deletes messages
- Auto-mutes users
- Auto-kicks or bans
- Takes any action without moderator approval

✅ **AI Always:**
- Requires human review
- Provides reasoning for flags
- Uses conservative thresholds
- Continues bot operation if unavailable

### Best Practices

1. **Start Conservative**: Begin with threshold 70-75, lower if needed
2. **Monitor Regularly**: Check AI flags daily
3. **Provide Feedback**: Mark false positives as "ignore"
4. **Context Matters**: AI doesn't understand context perfectly
5. **Trust but Verify**: Review AI reasoning before taking action

### Common False Positives

- **Technical/Code Content**: May flag code snippets
- **Sarcasm/Jokes**: May miss humor context
- **Non-English**: May struggle with other languages
- **Quoted Content**: May flag quotes of violations

**Solution**: Click "Ignore" and the flag is logged as false positive.

---

## Advanced Topics

### Database Schema

The moderation system uses 6 tables:

1. **warnings**: Current warning count per user/guild
2. **warning_history**: Immutable audit trail
3. **moderation_appeals**: Appeal submissions and decisions
4. **moderation_config**: Per-guild configuration
5. **ai_flags**: AI-flagged messages for review
6. **active_mutes**: Current mutes with expiration

### Background Tasks

**Warning Decay Task** (runs every 6 hours):
- Checks all users with warnings
- Calculates decay deadlines
- Decrements warnings if deadline passed
- Removes mutes if count reaches 0
- Sends DM notifications
- Logs all actions

**Mute Expiration Task** (runs every minute):
- Checks for expired mutes
- Removes Discord timeouts
- Cleans up database
- Sends DM notifications
- Logs all actions

### Customizing Decay Rates

You can adjust how quickly warnings decay:

```
/modconfig set warn_1_decay_days 5    # Faster redemption
/modconfig set warn_2_decay_days 10   # Proportional increase
/modconfig set warn_3_decay_days 20   # Longer for repeat offenses
```

### Customizing Auto-Mute Durations

Adjust automatic mute durations (in seconds):

```
/modconfig set mute_duration_2 7200    # 2 hours for 2 warnings
/modconfig set mute_duration_3 172800  # 48 hours for 3 warnings
```

Common durations:
- 1 hour = 3600
- 2 hours = 7200
- 12 hours = 43200
- 24 hours = 86400
- 48 hours = 172800
- 7 days = 604800

### Multi-Server Setup

Each guild has independent configuration:
- Configure each server separately
- No cross-server data sharing
- Different AI thresholds per server
- Different decay rates per server

### Ollama Models

You can use different AI models:

```
/modconfig set ai_model llama3.1
/modconfig set ai_model mistral
/modconfig set ai_model codellama
```

**Recommended Models:**
- `llama2`: Good balance, default choice
- `llama3.1`: More accurate, requires more resources
- `mistral`: Faster, good for high-traffic servers
- `orca-mini`: Lightweight, good for low-resource servers

### Remote Ollama

If running Ollama on another machine:

```
/modconfig set ollama_host http://192.168.1.100:11434
```

---

## Troubleshooting

### AI Not Flagging Messages

**Symptoms**: AI enabled but no messages being flagged

**Solutions:**
1. Check Ollama is running: `curl http://localhost:11434`
2. Verify threshold not too high: `/modconfig view`
3. Check AI flag channel configured: `/modconfig view`
4. Check bot logs for Ollama errors
5. Test with obviously problematic message

### Warnings Not Decaying

**Symptoms**: Warnings not expiring after configured time

**Solutions:**
1. Check warning decay task is running (check bot logs)
2. Verify decay days configured: `/modconfig view`
3. Check warning update timestamp: `/warns @user`
4. Restart bot to restart background tasks

### Mutes Not Expiring

**Symptoms**: Mute not removed after duration

**Solutions:**
1. Check mute expiration task is running
2. Verify bot has "Moderate Members" permission
3. Check active_mutes table has correct expiration
4. Restart bot to restart background tasks

### Appeals Not Appearing

**Symptoms**: User submits appeal but moderators don't see it

**Solutions:**
1. Check appeal channel configured: `/modconfig view`
2. Verify bot has permission to send in appeal channel
3. Check bot has "Embed Links" permission
4. User may have pending appeal already

### DMs Not Sending

**Symptoms**: Users not receiving DM notifications

**Solutions:**
1. User may have DMs disabled
2. User may have blocked the bot
3. Check bot has "Send Messages" permission for DMs
4. This is expected behavior - bot handles gracefully

### Context Menu Not Showing

**Symptoms**: "Warn User" not in Apps menu

**Solutions:**
1. Ensure bot commands are synced
2. Check you have "Moderate Members" permission
3. Try restarting Discord client
4. Commands may take up to 1 hour to sync globally

### AI Timeout Errors

**Symptoms**: Errors in logs about AI analysis timeout

**Solutions:**
1. Check Ollama server performance
2. Increase timeout in code if needed
3. Use lighter AI model
4. Disable AI if server overloaded

---

## Support & Contributing

### Getting Help

1. Check this documentation
2. Review bot logs in `discord.log`
3. Check database with SQLite browser
4. Create issue on GitHub with:
   - Bot version
   - Error messages
   - Steps to reproduce

### Contributing

Contributions welcome! Areas for improvement:
- Additional AI models support
- More detailed analytics
- Export/import configurations
- Multi-language support
- Advanced reporting

---

## License

This moderation system is part of ISROBOT and uses the same license as the main project.

## Credits

- Discord.py for Discord API
- Ollama for local AI inference
- SQLite for database
- The ISROBOT community

---

*Last Updated: November 2025*
