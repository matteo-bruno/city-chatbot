#!/usr/bin/env python3
"""Download Milan's official neighbourhood boundaries (NIL) for the gazetteer.

    python scripts/fetch_milan_nil.py

The 88 *Nuclei di Identita Locale* are Milan's official neighbourhood units,
published as open data by the Comune di Milano. With this file in place the
chatbot selects cells by point-in-polygon inside the real boundary instead of
a circle around an approximate centre, and `place.precision` becomes
"official boundary".

Needs outbound internet access. Equivalent manual route: download the GeoJSON
from https://dati.comune.milano.it (search "NIL") and save it as
data/places/milan.boundaries.geojson
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Portale open data del Comune di Milano - "NIL (Nuclei di Identita Locale)".
# Resource URLs on the portal do change; --url lets you point at a fresh one.
DEFAULT_URL = (
    "https://dati.comune.milano.it/dataset/e8e765fc-d882-40b8-95d8-16ff3d39eb7c/"
    "resource/9c4e0776-56fc-4f3b-8da6-ba1dbd403d0a/download/ds964_nil_wm.geojson"
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--out", type=Path, default=Path("data/places/milan.boundaries.geojson"))
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    from citychat.http import httpx

    print(f"downloading {args.url}")
    try:
        response = httpx.get(args.url, timeout=args.timeout, follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"error: download failed ({exc})", file=sys.stderr)
        print(
            "If the resource moved, find the current NIL GeoJSON on "
            "https://dati.comune.milano.it and pass it with --url, or save it "
            f"manually to {args.out}",
            file=sys.stderr,
        )
        return 1

    features = payload.get("features") or []
    if not features:
        print("error: no features in the downloaded file", file=sys.stderr)
        return 1

    props = features[0].get("properties") or {}
    name_field = next((f for f in ("NIL", "nil", "name", "nome") if f in props), None)
    if not name_field:
        print(f"warning: no obvious name field; properties are {sorted(props)}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {args.out} - {len(features)} boundaries, name field {name_field!r}")
    print("Restart the chatbot; boundaries are preferred over the seed points automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
