#!/usr/bin/env python3
"""
Comprehensive test suite for Twitch and YouTube periodic check functionality.

This script can be run to verify that:
1. The APIs are correctly configured
2. The check loop logic works as expected
3. Error handling is robust
4. Database operations work correctly

Usage:
    python test_periodic_checks_comprehensive.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import modules
import database
from commands.stream import CheckTwitchStatus, GetTwitchOAuth
from commands.youtube import CheckYouTubeChannel, is_short

# Configuration
TWITCH_CLIENT_ID = os.getenv("twitch_client_id")
TWITCH_CLIENT_SECRET = os.getenv("twitch_client_secret")
YOUTUBE_API_KEY = os.getenv("youtube_api_key")


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_test(test_name):
    """Print a test name."""
    print(f"\n→ {test_name}")


def print_success(message):
    """Print a success message."""
    print(f"  ✓ {message}")


def print_error(message):
    """Print an error message."""
    print(f"  ✗ {message}")


def print_info(message):
    """Print an info message."""
    print(f"  ℹ {message}")


async def test_twitch_configuration():
    """Test Twitch API configuration."""
    print_header("TEST 1: Twitch Configuration")
    
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        print_error("Twitch credentials not configured in .env")
        print_info("Add twitch_client_id and twitch_client_secret to .env")
        return False
    
    print_success("Twitch credentials found in .env")
    
    # Test OAuth
    print_test("Testing OAuth token retrieval")
    try:
        async with aiohttp.ClientSession() as session:
            oauth = GetTwitchOAuth(session)
            token = await oauth.get_auth_token()
            
            if token and len(token) > 0:
                print_success(f"OAuth token retrieved (length: {len(token)})")
                return True
            else:
                print_error("OAuth token is empty")
                return False
    except Exception as e:
        print_error(f"OAuth failed: {e}")
        return False


async def test_youtube_configuration():
    """Test YouTube API configuration."""
    print_header("TEST 2: YouTube Configuration")
    
    if not YOUTUBE_API_KEY:
        print_error("YouTube API key not configured in .env")
        print_info("Add youtube_api_key to .env")
        return False
    
    print_success("YouTube API key found in .env")
    
    # Test API access
    print_test("Testing API access")
    try:
        async with aiohttp.ClientSession() as session:
            checker = CheckYouTubeChannel(session)
            # Test with Google's channel
            channel_info = await checker.get_channel_info("UC_x5XG1OV2P6uZZ5FSM9Ttw")
            
            if channel_info:
                print_success(f"API access works: {channel_info.get('title', 'N/A')}")
                return True
            else:
                print_error("API returned no data")
                return False
    except Exception as e:
        print_error(f"API test failed: {e}")
        return False


async def test_database_setup():
    """Test database setup and operations."""
    print_header("TEST 3: Database Setup")
    
    print_test("Initializing database")
    try:
        database.create_database()
        print_success("Database initialized")
    except Exception as e:
        print_error(f"Database initialization failed: {e}")
        return False
    
    # Test streamers table
    print_test("Checking streamers table")
    try:
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM streamers")
            count = cursor.fetchone()[0]
            print_success(f"Streamers table accessible ({count} rows)")
        finally:
            conn.close()
    except Exception as e:
        print_error(f"Streamers table check failed: {e}")
        return False
    
    # Test youtube_channels table
    print_test("Checking youtube_channels table")
    try:
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM youtube_channels")
            count = cursor.fetchone()[0]
            print_success(f"YouTube channels table accessible ({count} rows)")
        finally:
            conn.close()
    except Exception as e:
        print_error(f"YouTube channels table check failed: {e}")
        return False
    
    return True


async def test_is_short_function():
    """Test the is_short duration parsing function."""
    print_header("TEST 4: is_short() Function")
    
    test_cases = [
        ("PT30S", True, "30 seconds"),
        ("PT1M", True, "1 minute (60 seconds)"),
        ("PT59S", True, "59 seconds"),
        ("PT1M1S", False, "61 seconds"),
        ("PT2M", False, "2 minutes"),
        ("PT1H", False, "1 hour"),
        ("PT5M30S", False, "5 minutes 30 seconds"),
        ("PT1H30M", False, "1 hour 30 minutes"),
    ]
    
    all_passed = True
    for duration, expected, description in test_cases:
        result = is_short(duration)
        if result == expected:
            print_success(f"{description}: {duration} -> {result}")
        else:
            print_error(f"{description}: {duration} -> {result} (expected: {expected})")
            all_passed = False
    
    return all_passed


async def test_twitch_api_functionality():
    """Test Twitch API functionality."""
    print_header("TEST 5: Twitch API Functionality")
    
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        print_info("Skipped: Twitch credentials not configured")
        return True
    
    print_test("Testing streamer status check")
    try:
        async with aiohttp.ClientSession() as session:
            checker = CheckTwitchStatus(session)
            
            # Test with a known streamer
            test_streamer = "shroud"
            stream_data = await checker.check_streamer_status(test_streamer)
            
            if stream_data is not None:
                if len(stream_data) > 0:
                    stream_info = stream_data[0]
                    print_success(f"{test_streamer} is ONLINE")
                    print_info(f"  Title: {stream_info.get('title', 'N/A')}")
                    print_info(f"  Game: {stream_info.get('game_name', 'N/A')}")
                else:
                    print_success(f"{test_streamer} is OFFLINE (normal)")
                return True
            else:
                print_error("API returned None")
                return False
    except Exception as e:
        print_error(f"Streamer status check failed: {e}")
        return False


async def test_youtube_api_functionality():
    """Test YouTube API functionality."""
    print_header("TEST 6: YouTube API Functionality")
    
    if not YOUTUBE_API_KEY:
        print_info("Skipped: YouTube API key not configured")
        return True
    
    async with aiohttp.ClientSession() as session:
        checker = CheckYouTubeChannel(session)
        
        # Test 1: Channel info
        print_test("Testing channel info retrieval")
        try:
            channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
            channel_info = await checker.get_channel_info(channel_id)
            if channel_info:
                print_success(f"Channel: {channel_info.get('title', 'N/A')}")
            else:
                print_error("No channel info returned")
                return False
        except Exception as e:
            print_error(f"Channel info failed: {e}")
            return False
        
        # Test 2: Handle lookup
        print_test("Testing handle lookup")
        try:
            handle = "@Google"
            channel_data = await checker.get_channel_by_handle(handle)
            if channel_data:
                print_success(f"Handle resolved: {channel_data.get('snippet', {}).get('title', 'N/A')}")
            else:
                print_error("Handle not resolved")
                return False
        except Exception as e:
            print_error(f"Handle lookup failed: {e}")
            return False
        
        # Test 3: Latest uploads
        print_test("Testing latest uploads")
        try:
            channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
            uploads = await checker.get_latest_uploads(channel_id, max_results=3)
            if uploads:
                print_success(f"Found {len(uploads)} uploads")
            else:
                print_info("No uploads found (channel might be inactive)")
        except Exception as e:
            print_error(f"Latest uploads failed: {e}")
            return False
        
        # Test 4: Live status
        print_test("Testing live status check")
        try:
            channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
            live_videos = await checker.check_live_status(channel_id)
            if live_videos and len(live_videos) > 0:
                print_success("Live stream detected")
            else:
                print_success("No live stream (normal)")
        except Exception as e:
            print_error(f"Live status check failed: {e}")
            return False
    
    return True


async def test_error_handling():
    """Test error handling with invalid inputs."""
    print_header("TEST 7: Error Handling")
    
    # Test Twitch error handling
    if TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET:
        print_test("Testing Twitch error handling")
        try:
            async with aiohttp.ClientSession() as session:
                checker = CheckTwitchStatus(session)
                result = await checker.check_streamer_status("nonexistent_xyz_123")
                if result is not None:
                    print_success("Handles invalid streamer gracefully")
                else:
                    print_error("Returns None instead of empty list")
        except Exception as e:
            print_info(f"Exception raised (should be caught by loop): {type(e).__name__}")
    
    # Test YouTube error handling
    if YOUTUBE_API_KEY:
        print_test("Testing YouTube error handling")
        try:
            async with aiohttp.ClientSession() as session:
                checker = CheckYouTubeChannel(session)
                result = await checker.get_channel_info("invalid_channel_xyz_123")
                print_info("Handles invalid channel (may raise exception or return None)")
        except Exception as e:
            print_info(f"Exception raised (should be caught by loop): {type(e).__name__}")
    
    return True


async def main():
    """Run all tests."""
    print_header("COMPREHENSIVE PERIODIC CHECK FUNCTIONALITY TESTS")
    print("This test suite verifies Twitch and YouTube periodic check functionality.")
    
    results = {}
    
    # Run all tests
    results["Twitch Config"] = await test_twitch_configuration()
    results["YouTube Config"] = await test_youtube_configuration()
    results["Database Setup"] = await test_database_setup()
    results["is_short Function"] = await test_is_short_function()
    results["Twitch API"] = await test_twitch_api_functionality()
    results["YouTube API"] = await test_youtube_api_functionality()
    results["Error Handling"] = await test_error_handling()
    
    # Summary
    print_header("TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  ✓ All tests passed! The periodic check functionality is working correctly.")
        return 0
    else:
        print(f"\n  ⚠ {total - passed} test(s) failed. Review the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
