#!/usr/bin/env python3
"""Verify the configured provider, model and key against the live API.

    python scripts/check_provider.py                 one real round trip
    python scripts/check_provider.py --list-models   what this key can use
    python scripts/check_provider.py --probe         bisect a failing request
    python scripts/check_provider.py --debug         log the raw HTTP exchange
    python scripts/check_provider.py --dry-run       no API call at all

Use this first after setting a key or changing CITYCHAT_MODEL. It reports the
resolved provider and model, lists the tools as the provider declares them,
and then asks one question that forces a tool call, so a wrong model name, a
rejected schema or a missing key surfaces here rather than mid-conversation.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from citychat.agent import CityAgent  # noqa: E402
from citychat.config import Settings  # noqa: E402
from citychat.context import CityContext  # noqa: E402
from citychat.providers.base import ProviderError  # noqa: E402

PROBE = "In one sentence: what is the average walking proximity time of this city?"


def run_probe(agent) -> int:
    """Add one piece of the payload at a time and report where it breaks.

    Gemini answers some malformed requests with 500 INTERNAL, which is
    indistinguishable from a transient fault. Splitting the payload tells them
    apart: if the bare request succeeds and adding the function declarations
    fails, the tool schemas are the problem, not the network.
    """
    probe = getattr(agent.provider, "probe", None)
    if probe is None:
        print(f"--probe is not implemented for the {agent.provider_name} provider", file=sys.stderr)
        return 1

    steps = [
        ("models list", None),
        ("bare request (no system prompt, no tools)", {"system": False, "tools": False}),
        ("with the system prompt", {"system": True, "tools": False}),
        ("with the tool declarations", {"system": True, "tools": True}),
    ]
    first_failure: str | None = None
    for label, kwargs in steps:
        try:
            if kwargs is None:
                count = len(agent.provider.list_models())
                ok, note = True, f"{count} models visible"
            else:
                result = probe(**kwargs)
                ok = result["ok"]
                note = f"{result['status']} {result['detail']}".strip()
        except Exception as exc:
            ok, note = False, f"{type(exc).__name__}: {exc}"
        print(f"  [{'ok  ' if ok else 'FAIL'}] {label}: {note}")
        if not ok and first_failure is None:
            first_failure = label

    print()
    if first_failure is None:
        print(
            "Everything the probe sends is accepted, so the earlier failure was most likely\n"
            "transient. Re-run `python scripts/check_provider.py`."
        )
        return 0

    advice = {
        "models list": (
            "The key or the endpoint is the problem, not the payload. Check GEMINI_API_KEY and\n"
            "that the Generative Language API is enabled for the project behind it."
        ),
        "bare request (no system prompt, no tools)": (
            f"Even a minimal request fails, so the model name is the likely cause. Run\n"
            f"`--list-models` and set CITYCHAT_MODEL to one of the listed ids (currently\n"
            f"{agent.provider.model!r})."
        ),
        "with the system prompt": (
            "The model rejects a system instruction. Some older models do not support one.\n"
            "Pick a current model, or report this and I will move the prompt into the first turn."
        ),
        "with the tool declarations": (
            "The model rejects the function declarations. Run again with --debug to see the\n"
            "body, and send me the output: the schema subset this model accepts differs from\n"
            "what citychat/providers/gemini.py currently emits."
        ),
    }
    print(advice[first_failure])
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--list-models", action="store_true", help="list the models this key can use")
    ap.add_argument(
        "--probe",
        action="store_true",
        help="send progressively larger requests to find which part the API rejects",
    )
    ap.add_argument("--debug", action="store_true", help="log the raw HTTP status and body")
    ap.add_argument("--dry-run", action="store_true", help="report configuration, call nothing")
    ap.add_argument("--question", default=PROBE, help="question to send instead of the default")
    args = ap.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s %(message)s")

    settings = Settings.from_env()
    try:
        agent = CityAgent(CityContext(settings))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(agent.describe(), indent=2, default=str))
    if not settings.api_key_for_provider:
        key_var = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(
            settings.provider, "the provider's API key"
        )
        print(f"\nwarning: {key_var} is not set in the environment", file=sys.stderr)

    if args.list_models:
        lister = getattr(agent.provider, "list_models", None)
        if lister is None:
            print(
                f"\n{agent.provider_name} exposes no model listing here; see the provider's docs.",
                file=sys.stderr,
            )
            return 1
        try:
            models = lister()
        except Exception as exc:
            print(f"\nerror: could not list models ({exc})", file=sys.stderr)
            return 1
        print(f"\n{len(models)} model(s) available to this key:")
        for entry in models:
            name = str(entry.get("name", "")).removeprefix("models/")
            methods = entry.get("supportedGenerationMethods") or []
            usable = "generateContent" in methods
            print(f"  {'*' if usable else ' '} {name}")
        print("\n  * = usable as CITYCHAT_MODEL")
        return 0

    if args.dry_run:
        print("\ndry run: no API call made")
        return 0

    if args.probe:
        return run_probe(agent)

    print(f"\nasking: {args.question}\n")
    tools_used: list[str] = []
    try:
        for event in agent.run(agent.prepare_messages([], args.question)):
            if event["type"] == "text":
                sys.stdout.write(event["text"])
                sys.stdout.flush()
            elif event["type"] == "tool_call":
                tools_used.append(event["name"])
            elif event["type"] == "error":
                print(f"\n\nerror: {event['message']}", file=sys.stderr)
            elif event["type"] == "done":
                print("\n")
                if event.get("error"):
                    return 1
                print(f"tools called: {', '.join(tools_used) or 'none'}")
                print(f"usage: {json.dumps(event['usage'], default=str)}")
                if not tools_used:
                    print(
                        "\nwarning: the model answered without calling a tool. Check that the "
                        "function declarations were accepted by this model.",
                        file=sys.stderr,
                    )
    except ProviderError as exc:
        print(f"\nerror: {exc.message}", file=sys.stderr)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
