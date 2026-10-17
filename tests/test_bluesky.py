"""
Tests for the Bluesky integration helpers.

Covers the pure (network-free) functions used by commands/bluesky.py:
identifier normalization/validation, post URL building and post parsing.
"""

import asyncio

import discord
from discord import app_commands

from commands.bluesky import (
    extract_post_created_at,
    extract_post_image,
    extract_post_text,
    is_valid_bluesky_did,
    is_valid_bluesky_handle,
    normalize_bluesky_identifier,
    post_web_url,
    select_new_posts,
    validate_bluesky_identifier,
)
from utils.i18n import JsonTranslator, base_locale


class TestNormalizeIdentifier:
    def test_strips_whitespace_and_at(self):
        assert normalize_bluesky_identifier("  @Jay.bsky.social ") == "Jay.bsky.social"

    def test_keeps_plain_handle(self):
        assert normalize_bluesky_identifier("jay.bsky.social") == "jay.bsky.social"

    def test_empty(self):
        assert normalize_bluesky_identifier("   ") == ""


class TestHandleValidation:
    def test_valid_handles(self):
        assert is_valid_bluesky_handle("jay.bsky.social")
        assert is_valid_bluesky_handle("a-b.c-d.com")
        assert is_valid_bluesky_handle("user123.custom-domain.org")

    def test_invalid_handles(self):
        assert not is_valid_bluesky_handle("no-dot")
        assert not is_valid_bluesky_handle("")
        assert not is_valid_bluesky_handle("bad..domain")
        assert not is_valid_bluesky_handle("-leading.com")

    def test_valid_dids(self):
        assert is_valid_bluesky_did("did:plc:abc123xyz")
        assert is_valid_bluesky_did("did:web:example.com")

    def test_invalid_dids(self):
        assert not is_valid_bluesky_did("did:key:abc")
        assert not is_valid_bluesky_did("plc:abc")


class TestValidateIdentifier:
    def test_valid_handle_accepted(self):
        ok, msg = validate_bluesky_identifier("jay.bsky.social", "en-US")
        assert ok is True
        assert msg == ""

    def test_valid_did_accepted(self):
        ok, _ = validate_bluesky_identifier("did:plc:abc123", "en-US")
        assert ok is True

    def test_at_prefix_accepted(self):
        ok, _ = validate_bluesky_identifier("@jay.bsky.social", "fr")
        assert ok is True

    def test_empty_rejected(self):
        ok, msg = validate_bluesky_identifier("", "fr")
        assert ok is False
        assert msg  # message localisé

    def test_malformed_rejected(self):
        ok, msg = validate_bluesky_identifier("not a handle", "en-US")
        assert ok is False
        assert msg


class TestPostWebUrl:
    def test_extracts_rkey(self):
        uri = "at://did:plc:abc123/app.bsky.feed.post/3k2abcdef"
        assert (
            post_web_url("jay.bsky.social", uri)
            == "https://bsky.app/profile/jay.bsky.social/post/3k2abcdef"
        )

    def test_handles_missing_uri(self):
        assert post_web_url("jay.bsky.social", "") == (
            "https://bsky.app/profile/jay.bsky.social/post/"
        )


class TestPostParsing:
    def test_extract_text(self):
        post = {"record": {"text": "  Hello 🦋  "}}
        assert extract_post_text(post) == "Hello 🦋"

    def test_extract_text_missing(self):
        assert extract_post_text({}) == ""
        assert extract_post_text({"record": {}}) == ""

    def test_extract_image_from_images(self):
        post = {
            "embed": {
                "$type": "app.bsky.embed.images#view",
                "images": [{"thumb": "thumb.jpg", "fullsize": "full.jpg"}],
            }
        }
        assert extract_post_image(post) == "full.jpg"

    def test_extract_image_from_external(self):
        post = {
            "embed": {
                "$type": "app.bsky.embed.external#view",
                "external": {"uri": "https://x.com", "thumb": "card.jpg"},
            }
        }
        assert extract_post_image(post) == "card.jpg"

    def test_extract_image_none(self):
        assert extract_post_image({}) is None

    def test_extract_created_at(self):
        post = {"record": {"createdAt": "2026-01-01T00:00:00.000Z"}}
        assert extract_post_created_at(post) == "2026-01-01T00:00:00.000Z"

    def test_extract_created_at_fallback_indexed(self):
        post = {"indexedAt": "2026-02-02T00:00:00.000Z"}
        assert extract_post_created_at(post) == "2026-02-02T00:00:00.000Z"

    def test_extract_created_at_missing(self):
        assert extract_post_created_at({}) is None


class TestSelectNewPosts:
    @staticmethod
    def _item(uri, reason=None):
        return {"post": {"uri": uri}, "reason": reason}

    def test_returns_chronological_order(self):
        feed = [self._item("u3"), self._item("u2"), self._item("u1")]
        posts = select_new_posts(feed, last_post_uri=None)
        assert [p["uri"] for p in posts] == ["u1", "u2", "u3"]

    def test_stops_at_last_known_post(self):
        feed = [self._item("u4"), self._item("u3"), self._item("u2"), self._item("u1")]
        posts = select_new_posts(feed, last_post_uri="u2")
        assert [p["uri"] for p in posts] == ["u3", "u4"]

    def test_skips_reposts(self):
        feed = [self._item("u3"), self._item("u2", reason="repost"), self._item("u1")]
        posts = select_new_posts(feed, last_post_uri="u1")
        assert [p["uri"] for p in posts] == ["u3"]

    def test_no_new_posts(self):
        feed = [self._item("u2"), self._item("u1")]
        assert select_new_posts(feed, last_post_uri="u2") == []

    def test_empty_feed(self):
        assert select_new_posts([], last_post_uri="u1") == []


class TestBlueskyTranslator:
    def test_command_description_translated(self):
        translator = JsonTranslator()
        desc = app_commands.locale_str("x", key="cmd.bluesky_add.desc")
        en = asyncio.run(
            translator.translate(desc, discord.Locale.american_english, object())
        )
        fr = asyncio.run(translator.translate(desc, discord.Locale.french, object()))
        assert en and "Bluesky" in en
        assert fr is None  # locale de base

    def test_feature_label_key_present(self):
        from utils.feature_toggles import feature_label

        assert feature_label("bluesky", "en-US") == "Bluesky"

    def test_base_locale(self):
        assert base_locale("en-US") == "en"
        assert base_locale("fr") == "fr"


class _FakeResponse:
    status = 403
    reason = "Forbidden"


class _FakeAnnouncer:
    """Annonceur factice qui peut échouer sur un post donné."""

    def __init__(self, fail_on: int = None):
        self.sent = []
        self.fail_on = fail_on

    async def announce_post(
        self,
        account_id,
        handle,
        display_name,
        discord_channel,
        post_text,
        post_url,
        thumbnail_url=None,
        created_at=None,
        discord_role=None,
    ):
        if self.fail_on is not None and len(self.sent) == self.fail_on:
            raise discord.Forbidden(_FakeResponse(), "missing permissions")
        self.sent.append(post_url)


class TestAnnounceWithCheckpoint:
    def test_updates_marker_after_each_successful_send(self, monkeypatch):
        import commands.bluesky as bluesky

        updates = []
        monkeypatch.setattr(
            bluesky,
            "_db_update_last_post",
            lambda account_id, uri, cid: updates.append(uri),
        )

        posts = [
            {"uri": "u1", "cid": "c1"},
            {"uri": "u2", "cid": "c2"},
            {"uri": "u3", "cid": "c3"},
        ]
        announcer = _FakeAnnouncer()

        count = asyncio.run(
            bluesky.announce_posts_with_checkpoint(
                announcer, 1, "handle.test", "Name", None, posts
            )
        )

        assert count == 3
        assert updates == ["u1", "u2", "u3"]
        assert len(announcer.sent) == 3

    def test_stops_on_failure_and_keeps_marker(self, monkeypatch):
        import commands.bluesky as bluesky

        updates = []
        monkeypatch.setattr(
            bluesky,
            "_db_update_last_post",
            lambda account_id, uri, cid: updates.append(uri),
        )

        posts = [{"uri": "u1"}, {"uri": "u2"}, {"uri": "u3"}]
        announcer = _FakeAnnouncer(fail_on=1)

        count = asyncio.run(
            bluesky.announce_posts_with_checkpoint(
                announcer, 1, "handle.test", "Name", None, posts
            )
        )

        assert count == 1
        assert updates == ["u1"]  # u2 (échec) et u3 ne sont pas marqués
        assert len(announcer.sent) == 1

    def test_empty_posts_does_nothing(self, monkeypatch):
        import commands.bluesky as bluesky

        updates = []
        monkeypatch.setattr(
            bluesky,
            "_db_update_last_post",
            lambda account_id, uri, cid: updates.append(uri),
        )

        count = asyncio.run(
            bluesky.announce_posts_with_checkpoint(
                _FakeAnnouncer(), 1, "handle.test", "Name", None, []
            )
        )

        assert count == 0
        assert updates == []
