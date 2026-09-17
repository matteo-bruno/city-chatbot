"""The terminal entry point.

Thin, but worth covering: it is the first thing anyone runs, and it is the one
surface with no framework to catch a stale attribute reference.
"""

from __future__ import annotations

import json

import pytest

from citychat import cli


@pytest.fixture
def cli_env(monkeypatch, settings):
    """Point the CLI's own Settings.from_env() at this repo's data."""
    monkeypatch.setenv("CITYCHAT_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("CITYCHAT_KNOWLEDGE_DIR", str(settings.knowledge_dir))
    monkeypatch.setenv("CITYCHAT_CITY", "milan")
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_check_reports_the_dataset_and_the_provider(cli_env, capsys):
    cli_env.setenv("CITYCHAT_PROVIDER", "gemini")
    assert cli.main(["--check"]) == 0

    out, err = capsys.readouterr()
    # Two JSON documents: the dataset summary, then the assistant description.
    dataset, assistant = _json_documents(out)
    assert dataset["city"] == "Milan"
    assert assistant["assistant"]["provider"] == "gemini"
    assert assistant["assistant"]["model"] == "gemini-3.8-flash"
    assert "area_accessibility" in assistant["assistant"]["tools"]
    assert "system prompt:" in out
    # No key set, so it must say so rather than fail later on a live call.
    assert "no API key found" in err


def test_check_follows_the_provider_setting(cli_env, capsys):
    cli_env.setenv("CITYCHAT_PROVIDER", "anthropic")
    assert cli.main(["--check"]) == 0
    _, assistant = _json_documents(capsys.readouterr().out)
    assert assistant["assistant"]["provider"] == "anthropic"
    assert assistant["assistant"]["model"] == "claude-opus-5"


def test_check_honours_an_explicit_model(cli_env, capsys):
    cli_env.setenv("CITYCHAT_PROVIDER", "anthropic")
    cli_env.setenv("CITYCHAT_MODEL", "claude-sonnet-5")
    assert cli.main(["--check"]) == 0
    _, assistant = _json_documents(capsys.readouterr().out)
    assert assistant["assistant"]["model"] == "claude-sonnet-5"


def test_an_unknown_provider_exits_with_a_message(cli_env, capsys):
    cli_env.setenv("CITYCHAT_PROVIDER", "nope")
    assert cli.main(["--check"]) == 1
    assert "unknown CITYCHAT_PROVIDER" in capsys.readouterr().err


def test_a_missing_city_exits_with_a_message(cli_env, capsys, tmp_path):
    cli_env.setenv("CITYCHAT_DATA_DIR", str(tmp_path))
    assert cli.main(["--check"]) == 1
    assert "no prepared city" in capsys.readouterr().err


def test_a_one_shot_question_streams_an_answer(cli_env, capsys, monkeypatch):
    """Drives the real loop, with the provider swapped for a scripted stub."""
    from gemini_stub import GeminiStub, text_chunk

    from citychat.providers.gemini import GeminiProvider

    cli_env.setenv("CITYCHAT_PROVIDER", "gemini")
    cli_env.setenv("GEMINI_API_KEY", "test-key")

    real_init = GeminiProvider.__init__

    def stubbed_init(self, *args, **kwargs):
        kwargs["transport"] = GeminiStub([[text_chunk("9.8 minutes on foot.", finish="STOP")]])
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(GeminiProvider, "__init__", stubbed_init)
    assert cli.main(["What is the proximity time?"]) == 0
    assert "9.8 minutes on foot." in capsys.readouterr().out


def _json_documents(text: str) -> list[dict]:
    """Pull the pretty-printed JSON documents out of mixed CLI output."""
    decoder = json.JSONDecoder()
    documents: list[dict] = []
    index = 0
    while True:
        start = text.find("{", index)
        if start == -1:
            return documents
        try:
            value, end = decoder.raw_decode(text[start:])
        except ValueError:
            index = start + 1
            continue
        documents.append(value)
        index = start + end
