"""The provider smoke-test script's bisecting probe.

This is the tool for diagnosing a failing live request, so its reporting has
to be right: every step label must have advice attached, or the script that is
meant to explain a failure raises one of its own.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script():
    spec = importlib.util.spec_from_file_location(
        "check_provider", ROOT / "scripts" / "check_provider.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_provider"] = module
    spec.loader.exec_module(module)
    return module


class FakeProvider:
    """Fails from a chosen step onwards, as a real rejection would."""

    def __init__(self, fail_from: int = 99, models: int = 3) -> None:
        self.fail_from = fail_from
        self.models = models
        self.model = "gemini-3.8-flash"
        self.calls: list[dict] = []

    def list_models(self):
        if self.fail_from <= 0:
            raise RuntimeError("403 Forbidden")
        return [{"name": f"models/m{i}"} for i in range(self.models)]

    def probe(self, *, system: bool, tools: bool, text: str = ""):
        step = 1 + int(system) + int(tools)
        self.calls.append({"system": system, "tools": tools})
        if step >= self.fail_from:
            return {"status": 500, "ok": False, "detail": "Internal error", "body_bytes": 0}
        return {"status": 200, "ok": True, "detail": "", "body_bytes": 10}


class FakeAgent:
    def __init__(self, provider) -> None:
        self.provider = provider
        self.provider_name = "gemini"


@pytest.fixture(scope="module")
def script():
    return load_script()


def test_a_healthy_provider_probes_clean(script, capsys):
    agent = FakeAgent(FakeProvider())
    assert script.run_probe(agent) == 0
    out = capsys.readouterr().out
    assert out.count("[ok  ]") == 4
    assert "most likely" in out and "transient" in out


def test_a_tools_only_failure_blames_the_schemas(script, capsys):
    agent = FakeAgent(FakeProvider(fail_from=3))
    assert script.run_probe(agent) == 1
    out = capsys.readouterr().out
    assert "[FAIL] with the tool declarations" in out
    assert "rejects the function declarations" in out
    assert "--debug" in out


def test_a_system_prompt_failure_is_identified(script, capsys):
    agent = FakeAgent(FakeProvider(fail_from=2))
    assert script.run_probe(agent) == 1
    out = capsys.readouterr().out
    assert "[FAIL] with the system prompt" in out
    assert "system instruction" in out


def test_a_bare_request_failure_blames_the_model_name(script, capsys):
    agent = FakeAgent(FakeProvider(fail_from=1))
    assert script.run_probe(agent) == 1
    out = capsys.readouterr().out
    assert "--list-models" in out
    assert "gemini-3.8-flash" in out


def test_a_models_list_failure_blames_the_key(script, capsys):
    agent = FakeAgent(FakeProvider(fail_from=0))
    assert script.run_probe(agent) == 1
    out = capsys.readouterr().out
    assert "[FAIL] models list" in out
    assert "GEMINI_API_KEY" in out


def test_every_step_label_has_advice(script, capsys):
    """Guards the advice lookup against a label drifting out of sync."""
    for fail_from in range(0, 4):
        agent = FakeAgent(FakeProvider(fail_from=fail_from))
        assert script.run_probe(agent) == 1  # would KeyError on a missing label
    capsys.readouterr()


def test_a_provider_without_a_probe_says_so(script, capsys):
    class Bare:
        model = "x"

    assert script.run_probe(FakeAgent(Bare())) == 1
    assert "not implemented" in capsys.readouterr().err
