"""
Tests for AI moderation prompt building and context length limits.
"""

from utils.ai_moderation import (
    MAX_MESSAGE_LENGTH,
    MAX_PROMPT_LENGTH,
    MAX_RULES_LENGTH,
    _build_analysis_prompt,
    _parse_ai_response,
)


class TestBuildAnalysisPrompt:
    """Tests for the _build_analysis_prompt function."""

    def test_short_message_no_rules(self):
        """Short message without rules should produce a concise prompt."""
        prompt = _build_analysis_prompt("hello world", None)
        assert 'Message: "hello world"' in prompt
        assert "SCORE:" in prompt
        assert "CATEGORY:" in prompt
        assert "REASON:" in prompt
        assert len(prompt) <= MAX_PROMPT_LENGTH

    def test_short_message_with_short_rules(self):
        """Short message with short rules included in prompt."""
        rules = "Rule 1: Be nice\nRule 2: No spam"
        prompt = _build_analysis_prompt("hello world", rules)
        assert "Server Rules:" in prompt
        assert rules in prompt
        assert len(prompt) <= MAX_PROMPT_LENGTH

    def test_long_message_truncated(self):
        """Messages longer than MAX_MESSAGE_LENGTH are truncated."""
        long_msg = "a" * (MAX_MESSAGE_LENGTH + 500)
        prompt = _build_analysis_prompt(long_msg, None)
        assert "a" * MAX_MESSAGE_LENGTH in prompt
        assert "..." in prompt
        assert len(prompt) <= MAX_PROMPT_LENGTH

    def test_long_rules_truncated(self):
        """Server rules longer than MAX_RULES_LENGTH are truncated."""
        long_rules = "r" * (MAX_RULES_LENGTH + 500)
        prompt = _build_analysis_prompt("test", long_rules)
        assert "Server Rules:" in prompt
        assert "r" * MAX_RULES_LENGTH in prompt
        # Rules should be truncated with "..."
        assert "r" * (MAX_RULES_LENGTH + 1) not in prompt

    def test_total_prompt_capped(self):
        """Total prompt is capped at MAX_PROMPT_LENGTH."""
        # Use max-length rules and max-length message to push over
        long_rules = "r" * MAX_RULES_LENGTH
        long_msg = "m" * MAX_MESSAGE_LENGTH
        prompt = _build_analysis_prompt(long_msg, long_rules)
        assert len(prompt) <= MAX_PROMPT_LENGTH

    def test_empty_rules_not_included(self):
        """Empty string rules should not add a rules section."""
        prompt = _build_analysis_prompt("hello", "")
        assert "Server Rules:" not in prompt

    def test_none_rules_not_included(self):
        """None rules should not add a rules section."""
        prompt = _build_analysis_prompt("hello", None)
        assert "Server Rules:" not in prompt

    def test_prompt_contains_format_instructions(self):
        """Prompt always contains the expected format instructions."""
        prompt = _build_analysis_prompt("test message", None)
        assert "SCORE:" in prompt
        assert "CATEGORY:" in prompt
        assert "REASON:" in prompt


class TestParseAiResponse:
    """Tests for the _parse_ai_response function."""

    def test_valid_response(self):
        """Valid AI response is parsed correctly."""
        response = "SCORE: 75\nCATEGORY: Toxicity\nREASON: Contains insults"
        result = _parse_ai_response(response)
        assert result is not None
        assert result["score"] == 75
        assert result["category"] == "Toxicity"
        assert result["reason"] == "Contains insults"

    def test_score_clamped_to_100(self):
        """Score above 100 is clamped to 100."""
        response = "SCORE: 150\nCATEGORY: Spam\nREASON: Test"
        result = _parse_ai_response(response)
        assert result["score"] == 100

    def test_score_clamped_to_0(self):
        """Score of 0 is handled correctly."""
        response = "SCORE: 0\nCATEGORY: None\nREASON: Normal message"
        result = _parse_ai_response(response)
        assert result["score"] == 0

    def test_incomplete_response_returns_none(self):
        """Incomplete response returns None."""
        result = _parse_ai_response("SCORE: 50\nCATEGORY: Spam")
        assert result is None

    def test_invalid_category_defaults_to_none(self):
        """Invalid category defaults to 'None'."""
        response = "SCORE: 30\nCATEGORY: InvalidCat\nREASON: Test"
        result = _parse_ai_response(response)
        assert result["category"] == "None"
