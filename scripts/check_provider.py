#!/usr/bin/env python3
"""Verify the configured provider, model and key against the live API.

    python scripts/check_provider.py                 one real round trip
    python scripts/check_provider.py --list-models   what this key can use
    python scripts/check_provider.py --dry-run       no API call at all

Use this first after setting a key or changing CITYCHAT_MODEL. It reports the
resolved provider and model, lists the tools as the provider declares them,
and then asks one question that forces a tool call, so a wrong model name, a
rejected schema or a missing key surfaces here rather than mid-conversation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from citychat.agent import CityAgent  # noqa: E402
from citychat.config import Settings  # noqa: E402
from citychat.context import CityContext  # noqa: E402
from citychat.providers.base import ProviderError  # noqa: E402

PROBE = "In one sentence: what is the average walking proximity time of this city?"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--list-models", action="store_true", help="list the models this key can use")
    ap.add_argument("--dry-run", action="store_true", help="report configuration, call nothing")
    ap.add_argument("--question", default=PROBE, help="question to send instead of the default")
    args = ap.parse_args()

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
