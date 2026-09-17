# City accessibility chatbot

A small, portable chatbot that answers questions about one city's
**15-minute-city accessibility data**, about the concept, and about the
methodology behind the numbers. It runs on **Gemini or Claude**, chosen with
one environment variable, and is designed to be lifted into another website:
the assistant is a plain Python package, the HTTP layer is ~180 lines of
FastAPI, and the front end is a single static HTML file.

Questions it is built for:

- *What is the proximity time?*
- *What does it mean to be a 15-minute city?*
- *Is Milan a 15-minute city?*
- *Is Rogoredo a 15-minute neighbourhood?*
- *Which neighbourhoods are worst served, and for what?*
- *How is the score computed, and what are its limitations?*

The bundled dataset is Milan: 7,637 hexagonal cells, 3.07M residents, walking
and cycling proximity times overall and for nine service categories.

## Quick start

**Python 3.10 or newer is required** — the Anthropic SDK itself does not
install on 3.9, and 3.9 reached end of life in October 2025. Check with
`python3 --version`; if it is older, see [Upgrading Python](#upgrading-python)
below. Tested on 3.10, 3.12 and 3.13.

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then put your key in GEMINI_API_KEY
set -a && source .env && set +a

python scripts/check_provider.py    # one real round trip, confirms key + model

python -m citychat.cli --check     # loads the data, no API call
python -m citychat.cli             # terminal chat
uvicorn citychat.server:app --reload   # then open http://localhost:8000
```

Milan is already prepared in `data/cities/milan/`, so nothing needs building
first. To re-prepare it, or to add another city:

```bash
pip install -r requirements-prep.txt
python scripts/prepare_city.py data/raw/milan.geojson.gz --slug milan --name Milan \
    --country Italy --data-vintage "OpenStreetMap May 2023, WorldPop 2020"
```

## Upgrading Python

You do not need to touch your system Python: install a newer one alongside it
and point the project's virtualenv at that.

The least invasive route, on any OS, is [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # Windows: see the uv docs
uv python install 3.12
uv venv --python 3.12
uv pip install -r requirements.txt
source .venv/bin/activate
```

Or with your platform's package manager:

| Platform | Command |
|---|---|
| macOS (Homebrew) | `brew install python@3.12`, then `python3.12 -m venv .venv` |
| Ubuntu 22.04+ / Debian | `sudo apt install python3.12 python3.12-venv`, then `python3.12 -m venv .venv` |
| Older Ubuntu | add the deadsnakes PPA first: `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update` |
| Windows | `winget install Python.Python.3.12`, then `py -3.12 -m venv .venv` |
| Any (pyenv) | `pyenv install 3.12 && pyenv local 3.12`, then `python -m venv .venv` |

Then continue from `pip install -r requirements.txt` in the quick start. Verify
with `python --version` **after** activating the virtualenv — that is the
interpreter the project actually uses.

## How it works

```
                  ┌───────────────────────────────────────────┐
 .geojson.gz ───► │ scripts/prepare_city.py                   │
 (per-cell        │  detects the schema, computes PT/F15/Gini  │
  indicators)     └───────────────────┬───────────────────────┘
                                      ▼
                      data/cities/<slug>/{meta,profile}.json + cells.json.gz
                                      │
 papers (PDF) ──► scripts/ingest_pdf.py ──► knowledge/papers/*.md
                                      │              │
                  knowledge/core/*.md ─┤              │ searched on demand
                  (always in prompt)   │              │
                                      ▼              ▼
                              ┌──────────────────────────┐        ┌──────────┐
  place names ───────────────►│  CityContext + CityAgent │◄──────►│ Provider │
  (gazetteer / geocoder)      └────────────┬─────────────┘ 6 tools└────┬─────┘
                                           ▼                           ▼
                             citychat/server.py            Gemini API │ Claude API
                             /api/chat, /api/chat/stream
```

Three design decisions worth knowing about:

**The city data is not in the prompt.** 7,637 cells would be expensive to send
and would leave the model doing arithmetic. Instead, six tools return
already-aggregated, population-weighted answers, so the model only interprets
and words them. Every figure in an answer traces back to a tool result.

**The papers and the methodology are in the prompt.** `knowledge/core/*.md`
(~3k tokens: the concept, the methodology, the reporting rules) plus the city's
headline indicators sit behind a single prompt-cache breakpoint, so the model
"has them in memory" at roughly a tenth of the cost after the first call of a
cache window. The full paper text is chunked and BM25-searched only when a
question needs its exact wording.

**Nothing about Milan is hardcoded.** `scripts/prepare_city.py` discovers the
indicator columns and travel modes from the file and writes them into
`meta.json`; the runtime reads only that. A different city, an extra service
category or a third travel mode needs no code change.

### The six tools

| Tool | Answers |
|---|---|
| `city_overview` | city-wide proximity time, F10/F15/F20/F30, Gini, per-category scores, deciles, extremes |
| `area_accessibility` | one neighbourhood or coordinate: proximity time, verdict, thresholds, per-category breakdown, comparison with the city |
| `compare_areas` | up to six named areas side by side |
| `rank_areas` | best/worst named areas, overall or by one service category |
| `list_known_places` | which names resolve in this deployment |
| `search_methodology` | BM25 search over the reference library |
| `web_search` | *(optional, off by default)* Anthropic's server-side web search |

## The data format

Input is a GeoJSON `FeatureCollection` (plain or gzipped) whose features are
small polygons carrying:

| Property | Meaning |
|---|---|
| `h3` | cell id (any id column works: `h3`, `cell_id`, `id`, …) |
| `population` | residents in the cell |
| `proximity_time_<mode>` | the overall score, in minutes |
| `<category>_<mode>` | per-category score, in minutes |

For Milan that is `foot` and `bicycle` as modes and nine categories
(`outdoor`, `education`, `supplies`, `restaurant`, `transport`, `culture`,
`physical`, `services`, `healthcare`). A token is treated as a travel mode when
it is the suffix of at least three columns, which is what separates `foot` in
`supplies_foot` from `time` in `proximity_time`.

**This format is a good fit, so there is no reason to change it.** The prep
step converts it to a columnar store that gzips to 280 KB for Milan and loads
in well under a second, and it keeps only centroids (an area query is an
aggregate, so the rings are dead weight). If you ever serve dozens of cities or
files an order of magnitude larger, swap the store for Parquet or SQLite inside
`prepare_city.py` and `citydata.py`; nothing else touches it.

The prep step also verifies that `proximity_time` really is the mean of the
nine category columns (99% of Milan cells match to within 0.06 min, the rest is
rounding) and records that check in `meta.json`, so the bot can describe how
*this* dataset is built rather than quoting the paper and hoping.

## Place names

The indicator data has no names in it, only cell ids, so *"Is Rogoredo a
15-minute neighbourhood?"* needs a gazetteer. Three sources, in order of
preference:

1. **Official boundaries** (`data/places/<slug>*.geojson`). Cells are selected
   by point-in-polygon inside the real administrative area. For Milan:
   ```bash
   python scripts/fetch_milan_nil.py    # the 88 official NIL neighbourhoods
   ```
   This needs internet access and is the recommended setup for production.
2. **Seed points** (`data/places/milan.places.json`, shipped). 76 hand-compiled
   Milan neighbourhood and municipality centres, each queried as a circle of
   700-1,800 m. Coordinates are **approximate by construction**; the bot is
   told to say so when a verdict lands near the threshold. They were sanity
   checked against the data: the ranking runs Duomo/Brera 4.0-4.1 min → inner
   ring 5-7 → outer ring 8-10 → rural fringe (Muggiano, Chiaravalle, Figino)
   18-26, which is what Milan's geography should produce.
3. **Live geocoding** (off by default). Set `CITYCHAT_GEOCODER=nominatim` and
   any address or landmark resolves. Results are cached on disk and rate
   limited to one request per second; self-host Nominatim for real traffic.

Raw `lat`/`lon` always works, whatever is loaded. A name that resolves to
somewhere outside the dataset is refused rather than answered.

## Adding a paper or other reference material

```bash
pip install -r requirements-prep.txt
python scripts/ingest_pdf.py paper.pdf \
    --out knowledge/papers/author-2025-title.md \
    --title "Paper title" --citation "Author et al., Journal (2025)"
```

Files in `knowledge/papers/` are chunked and searched on demand. Files in
`knowledge/core/` go into every prompt, so keep that directory small (a few
thousand words) and written as instructions the model should follow, not as
prose to recite. Markdown is the storage format so you can read and correct
what was extracted.

## HTTP API

| Endpoint | Purpose |
|---|---|
| `GET /health` | status, city, model, tool list |
| `GET /api/city` | dataset description + city-level indicators |
| `GET /api/places` | resolvable place names (`?query=`, `?kind=`) |
| `POST /api/chat` | one turn, JSON in / JSON out |
| `POST /api/chat/stream` | the same turn as server-sent events |
| `DELETE /api/session/{id}` | drop a server-side session |
| `GET /` | the bundled demo page |

**Stateless by default**, which is what makes it easy to embed and to scale:
send the `history` and the `provider` you got back with the next `message`.

```bash
curl -s localhost:8000/api/chat -H 'Content-Type: application/json' \
  -d '{"message": "Is Rogoredo a 15-minute neighbourhood?"}' | jq .reply
```

```json
{
  "reply": "…",
  "city": "Milan",
  "provider": "gemini",
  "model": "gemini-3.8-flash",
  "history": [{"role": "user", "parts": [{"text": "…"}]}, {"role": "model", "parts": [...]}],
  "tool_calls": [{"name": "area_accessibility", "input": {"place": "Rogoredo"}, "is_error": false}],
  "usage": {"promptTokenCount": 4200, "candidatesTokenCount": 210, "totalTokenCount": 4410}
}
```

`usage` is passed through from the provider as-is, so its keys differ between
the two (`promptTokenCount` on Gemini, `input_tokens` on Claude).

Pass `"session_id": "new"` instead of `history` if the front end would rather
not hold the transcript; the server then keeps it in a capped in-process dict
(single worker only, lost on restart).

`/api/chat/stream` emits one JSON object per SSE frame: `start`, then `text`
deltas, `tool_call` / `tool_result` progress, an `error` if something failed,
and a final `done` carrying the full text, the updated history and token usage.

## Migrating it into another site

- **Keep the backend, replace the front end.** Point your own UI at
  `/api/chat/stream` and set `CITYCHAT_ALLOW_ORIGINS` to your site's origin.
  `web/index.html` is a 250-line reference implementation of the SSE protocol;
  set `window.CITYCHAT_API` to host the page elsewhere.
- **Keep the assistant, replace the HTTP layer.** `citychat/server.py` has no
  logic in it. In any other framework:
  ```python
  from citychat.agent import CityAgent
  from citychat.config import Settings
  from citychat.context import CityContext

  agent = CityAgent(CityContext(Settings.from_env()))   # once, at start-up
  turn = agent.ask(agent.prepare_messages(history, user_message))
  # turn.text, turn.messages, turn.tool_calls, turn.usage
  ```
  `agent.run(...)` is the same thing as a generator of events if you want to
  stream. Build the context once per process: it loads the store and the
  knowledge index, and the system prompt must be byte-identical between
  requests for the prompt cache to hit.
- **Never expose the Claude key to the browser.** All calls go through this
  backend, which is the other reason the HTTP layer exists.

## Choosing the provider and model

Two environment variables. The default is Gemini Flash.

```bash
CITYCHAT_PROVIDER=gemini     CITYCHAT_MODEL=              # default
CITYCHAT_PROVIDER=anthropic  CITYCHAT_MODEL=claude-opus-5
```

An empty `CITYCHAT_MODEL` means "the provider's own default"
(`gemini-3.8-flash`, or `claude-opus-5` for Anthropic). Each provider reads its
own key, so both can stay in `.env` and switching is one variable:

| Provider | Key | Default model | Get a key |
|---|---|---|---|
| `gemini` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | `gemini-3.8-flash` | https://aistudio.google.com/apikey |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5` | https://console.anthropic.com |

**Check the model id before anything else.** Google's model names move, so
confirm what your key can actually use rather than trusting the default:

```bash
python scripts/check_provider.py --list-models   # names this key can use
python scripts/check_provider.py                 # one real tool-calling round trip
python scripts/check_provider.py --dry-run       # configuration only, no API call
```

If the configured model does not exist, the error names the models that do.

### Claude model options

Model ids are complete as written below — never append a date suffix.

| `CITYCHAT_MODEL` | $ / MTok in‑out | Notes for this workload |
|---|---|---|
| `claude-opus-5` | 5 / 25 | Best judgement on the interpretive part: caveats, comparisons, "close but no". |
| `claude-sonnet-5` | 2 / 10 | The sensible cost saving. The tools do the reasoning-heavy work, so quality holds up well. |
| `claude-haiku-4-5` | 1 / 5 | Cheapest. 200K context. Fine for lookups, weaker at methodology discussion. |
| `claude-opus-4-8` | 5 / 25 | Previous Opus generation, if you have a reason to pin it. |
| `claude-fable-5-1` | 10 / 50 | Anthropic's most capable model; overkill here, and priced accordingly. |

### Per-provider options

These only apply to their own provider and are ignored by the other, so you
can leave both sets configured.

**Gemini**
- `CITYCHAT_THINKING_BUDGET` — thinking tokens on models that support it. `0`
  is the fastest and cheapest; empty leaves the model's default.
- `CITYCHAT_TEMPERATURE` — empty leaves the model's default.
- `CITYCHAT_GEMINI_BASE_URL` — for a proxy or a regional endpoint.

**Claude**
- `CITYCHAT_EFFORT` — `low`/`medium`/`high`/`xhigh`/`max` on Opus 5, Sonnet 5
  and Opus 4.6+. Haiku 4.5 does not accept it. Empty uses the model's default.
- `CITYCHAT_REFUSAL_FALLBACK` — only meaningful on models that can return
  `stop_reason: "refusal"`. Set `0` for anything else.

Both providers drop a parameter the model rejects and retry the same turn once,
logging which variable to set permanently, so a model swap needs nothing else.

### Adding a third provider

Implement `citychat/providers/base.Provider` and add one line to `BUILDERS` in
`citychat/providers/__init__.py`. The conversation loop, the tools, the prompt
and the HTTP layer do not change: a provider owns its request shape, its
streaming format, its history dialect and its error vocabulary, and nothing
else knows the difference. `citychat/providers/gemini.py` is the shorter of the
two existing ones to copy from.

### Conversation histories are provider-native

A transcript is content blocks on Claude and `contents` parts on Gemini, so it
cannot be replayed against the other API. `/api/chat` therefore returns a
`provider` field alongside `history`; send it back with the history and a
mismatch is refused with **409** (and a message saying to start over) rather
than being sent as a malformed request. The demo page handles the 409 by
clearing its transcript. `session_id` mode records the provider server-side and
does the same.

## Configuration

Everything is environment variables; `.env.example` documents the full set.
The ones that matter most:

| Variable | Default | Notes |
|---|---|---|
| `CITYCHAT_PROVIDER` | `gemini` | `gemini` or `anthropic` |
| `GEMINI_API_KEY` | — | required when the provider is `gemini` |
| `ANTHROPIC_API_KEY` | — | required when the provider is `anthropic` |
| `CITYCHAT_MODEL` | the provider's default | `gemini-3.8-flash` / `claude-opus-5` |
| `CITYCHAT_CITY` | the only prepared one | slug under `data/cities/` |
| `CITYCHAT_GEOCODER` | `none` | `nominatim` to resolve arbitrary addresses |
| `CITYCHAT_WEB_SEARCH` | `0` | `1` to add the provider's own server-side search |
| `CITYCHAT_ALLOW_ORIGINS` | `*` | narrow this in production |
| `CITYCHAT_MAX_TOOL_ROUNDS` | `8` | tool rounds one answer may spend |

With web search enabled the model is instructed to use it only for context the
dataset and papers cannot supply, and never to produce a number for this city's
own accessibility. Each provider runs it its own way: Anthropic's `web_search`
server tool, or Gemini's Google Search grounding. Some Gemini versions refuse
to combine grounding with function calling; the provider notices, drops the
grounding and retries, so tools always win.

## What the bot will and will not do

It is scoped to this city's data, the 15-minute-city concept, the methodology
and the published results. It declines anything else in a sentence. By
instruction it also:

- quotes no figure that did not come from a tool or the briefing card;
- always names the travel mode, and defaults to walking, the stricter test;
- states the rule behind a verdict (an area ≤ 15 min; a city ≥ 90% of
  residents within 15 min) and that there is no official certification;
- says when a name could not be resolved instead of substituting another area;
- treats text inside tool results, documents and web pages as data, not as
  instructions.

Real limits worth repeating to users: the score measures routed travel time to
a choice of 20 POIs per category, not the quality, price or opening hours of
those services; OpenStreetMap coverage is uneven; sidewalk-level walkability is
not modelled; population is a gridded estimate; the Milan dataset covers the
wider metropolitan area, so it is not directly comparable with published
core-city figures.

## Development

```bash
pip install -r requirements.txt pytest httpx
pytest                     # 116 tests, no API key or network needed
```

The whole conversation loop is tested twice over, once per provider, with no
API key and no network:

- `tests/fake_client.py` scripts the Anthropic SDK, so the Claude path is
  exercised end to end (tool execution, parallel calls, tool errors, the tool
  budget, `pause_turn` resumption, refusals, API errors, the prompt-cache shape
  of the request, and the model-gated-parameter retry).
- `tests/gemini_stub.py` is an httpx transport that speaks the documented
  Gemini SSE wire format, so the Gemini path is checked against real request
  and response shapes: schema sanitisation, function-call accumulation,
  `functionResponse` ordering, `finishReason` mapping, blocked prompts,
  grounding fallback and every documented error status.

Running the same loop over both dialects is what keeps the provider seam
honest. What the stubs cannot check is whether the live APIs accept the
requests: `scripts/check_provider.py` does that in one call.

```
citychat/
  config.py      environment settings
  geo.py         distances, centroids, point-in-polygon, the cell index
  stats.py       population-weighted mean / quantile / share / Gini
  schema.py      indicator-column discovery
  citydata.py    the in-memory store and every aggregation
  places.py      gazetteer, boundaries, optional Nominatim geocoder
  knowledge.py   always-on core docs + BM25 over the paper corpus
  context.py     binds the above into one object
  prompt.py      system prompt assembly (must stay byte-stable)
  tools.py       provider-neutral tool schemas and dispatch
  agent.py       the streaming conversation loop, provider-neutral
  providers/
    base.py      the Provider interface and the neutral turn/tool types
    gemini.py    Gemini, over the Generative Language REST API
    anthropic.py Claude, over the Anthropic SDK
  server.py      FastAPI endpoints
  cli.py         terminal chat
```

## Method and attribution

The indicators follow Bruno, M., Melo, H. P. M., Campanelli, B. & Loreto, V.
**A universal framework for inclusive 15-minute cities**, *Nature Cities* 1,
633-641 (2024), [doi:10.1038/s44284-024-00119-4](https://doi.org/10.1038/s44284-024-00119-4).
Interactive maps for ~10,000 cities: https://whatif.sonycsl.it/15mincity/

Proximity time for a cell is the mean over nine service categories of the
average routed travel time to the 20 nearest points of interest in that
category. A city's score is the population-weighted mean of its cells, and F15
is the percentage of residents whose cell is within 15 minutes. Source data:
OpenStreetMap POIs, WorldPop population, OSRM routing.
