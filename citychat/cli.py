"""Terminal chat, for trying the assistant without a browser.

python -m citychat.cli                      interactive
python -m citychat.cli "Is Rogoredo a 15-minute neighbourhood?"   one-shot
python -m citychat.cli --check              load data, print no-API-needed diagnostics
"""

from __future__ import annotations

import argparse
import json
import sys

from .agent import CityAgent
from .config import Settings
from .context import CityContext

BANNER = """
{city} accessibility assistant - {provider} / {model}
Ask about proximity times, neighbourhoods, or the 15-minute-city methodology.
Commands: /reset  /city  /places [query]  /quit
""".strip()


def _run_turn(agent: CityAgent, history: list[dict], message: str, show_tools: bool) -> list[dict]:
    updated = history
    for event in agent.run(agent.prepare_messages(history, message)):
        if event["type"] == "text":
            sys.stdout.write(event["text"])
            sys.stdout.flush()
        elif event["type"] == "tool_call" and show_tools:
            args = json.dumps(event["input"], ensure_ascii=False)
            print(f"\n  [{event['name']} {args}]", flush=True)
        elif event["type"] == "error":
            print(f"\n! {event['message']}", file=sys.stderr)
        elif event["type"] == "done":
            updated = event["messages"]
            print()
            if show_tools and event["usage"]:
                usage = event["usage"]
                print(
                    f"  [in {usage.get('input_tokens', 0)} "
                    f"cache_read {usage.get('cache_read_input_tokens', 0)} "
                    f"cache_write {usage.get('cache_creation_input_tokens', 0)} "
                    f"out {usage.get('output_tokens', 0)}]",
                    file=sys.stderr,
                )
    return updated


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("question", nargs="*", help="ask one question and exit")
    ap.add_argument(
        "--check", action="store_true", help="print diagnostics without calling the API"
    )
    ap.add_argument("--verbose", "-v", action="store_true", help="show tool calls and token usage")
    args = ap.parse_args(argv)

    settings = Settings.from_env()
    try:
        context = CityContext(settings)
        agent = CityAgent(context)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        print(json.dumps(context.data_summary(), indent=2, default=str))
        print(json.dumps({"assistant": agent.describe()}, indent=2, default=str))
        print(f"system prompt: {len(agent.system_prompt)} chars")
        print(f"max_tokens: {settings.max_tokens}, tool rounds: {settings.max_tool_rounds}")
        if not settings.api_key_for_provider:
            print(
                f"warning: no API key found for provider {settings.provider!r}",
                file=sys.stderr,
            )
        return 0

    if args.question:
        _run_turn(agent, [], " ".join(args.question), args.verbose)
        return 0

    print(
        BANNER.format(
            city=context.store.name,
            provider=agent.provider_name,
            model=agent.provider.model,
        )
    )
    history: list[dict] = []
    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("/quit", "/exit"):
            return 0
        if line == "/reset":
            history = []
            print("history cleared")
            continue
        if line == "/city":
            print(json.dumps(context.store.overview(), indent=2, default=str))
            continue
        if line.startswith("/places"):
            query = line[len("/places") :].strip().lower()
            names = [
                p.name for p in context.gazetteer.places if not query or query in p.name.lower()
            ]
            print(f"{len(names)} place(s): {', '.join(sorted(names))}")
            continue
        print()
        history = _run_turn(agent, history, line, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
