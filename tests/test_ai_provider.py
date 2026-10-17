import asyncio

import pytest

from utils import ai_provider


class TestProviderSelection:
    def test_default_provider_is_ollama(self, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        assert ai_provider.get_provider() == "ollama"

    def test_provider_is_lowercased_and_stripped(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "  OpenAI ")
        assert ai_provider.get_provider() == "openai"

    def test_active_model_ollama(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "ollama")
        monkeypatch.setenv("ollama_model", "mistral")
        assert ai_provider.get_active_model() == "mistral"

    def test_active_model_openai(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("openai_model", "meta-llama/llama-3.1-8b-instruct")
        assert ai_provider.get_active_model() == "meta-llama/llama-3.1-8b-instruct"


class TestResponseParsing:
    def test_parse_ollama_ok(self):
        data = {"message": {"role": "assistant", "content": "bonjour"}}
        assert ai_provider._parse_ollama_response(data) == "bonjour"

    def test_parse_ollama_missing_message(self):
        assert ai_provider._parse_ollama_response({}) is None
        assert ai_provider._parse_ollama_response({"message": {}}) is None

    def test_parse_ollama_blank_content(self):
        assert (
            ai_provider._parse_ollama_response({"message": {"content": "   "}}) is None
        )

    def test_parse_openai_ok(self):
        data = {"choices": [{"message": {"content": "hello"}}]}
        assert ai_provider._parse_openai_response(data) == "hello"

    def test_parse_openai_empty_choices(self):
        assert ai_provider._parse_openai_response({"choices": []}) is None
        assert ai_provider._parse_openai_response({}) is None

    def test_parse_openai_blank_content(self):
        data = {"choices": [{"message": {"content": ""}}]}
        assert ai_provider._parse_openai_response(data) is None


class TestChatRouting:
    def test_unknown_provider_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "wat")
        with pytest.raises(ai_provider.AIProviderConfigError):
            asyncio.run(ai_provider.chat([{"role": "user", "content": "hi"}]))

    def test_openai_without_key_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.delenv("openai_api_key", raising=False)
        with pytest.raises(ai_provider.AIProviderConfigError):
            asyncio.run(ai_provider.chat([{"role": "user", "content": "hi"}]))

    def test_chat_openai_builds_request(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("openai_api_key", "test-key")
        monkeypatch.setenv("openai_base_url", "https://example.test/api/v1/")
        monkeypatch.setenv("openai_model", "my-model")

        captured = {}

        async def fake_request(url, *, headers, body, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return {"choices": [{"message": {"content": "salut"}}]}

        monkeypatch.setattr(ai_provider, "_request_json", fake_request)

        result = asyncio.run(
            ai_provider.chat([{"role": "user", "content": "hi"}], temperature=0.5)
        )

        assert result == "salut"
        assert captured["url"] == "https://example.test/api/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["body"]["model"] == "my-model"
        assert captured["body"]["temperature"] == 0.5

    def test_chat_ollama_builds_request(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "ollama")
        monkeypatch.setenv("ollama_host", "http://ollama.test:11434")
        monkeypatch.setenv("ollama_model", "llama3")

        captured = {}

        async def fake_request(url, *, headers, body, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return {"message": {"content": "coucou"}}

        monkeypatch.setattr(ai_provider, "_request_json", fake_request)

        result = asyncio.run(
            ai_provider.chat([{"role": "user", "content": "hi"}], temperature=0.3)
        )

        assert result == "coucou"
        assert captured["url"] == "http://ollama.test:11434/api/chat"
        assert captured["body"]["model"] == "llama3"
        assert captured["body"]["stream"] is False
        assert captured["body"]["options"]["temperature"] == 0.3

    def test_chat_ollama_host_and_model_override(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "ollama")
        monkeypatch.setenv("ollama_host", "http://default:11434")
        monkeypatch.setenv("ollama_model", "default-model")

        captured = {}

        async def fake_request(url, *, headers, body, timeout):
            captured["url"] = url
            captured["body"] = body
            return {"message": {"content": "ok"}}

        monkeypatch.setattr(ai_provider, "_request_json", fake_request)

        asyncio.run(
            ai_provider.chat(
                [{"role": "user", "content": "hi"}],
                model="override-model",
                host="http://override:11434",
            )
        )

        assert captured["url"] == "http://override:11434/api/chat"
        assert captured["body"]["model"] == "override-model"
