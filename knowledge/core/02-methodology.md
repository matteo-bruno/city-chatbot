# Methodology: how proximity time is measured

Source of the method: Bruno, M., Melo, H. P. M., Campanelli, B. & Loreto, V.
**A universal framework for inclusive 15-minute cities**, *Nature Cities* 1,
633-641 (2024), https://doi.org/10.1038/s44284-024-00119-4. The companion
platform covers roughly 10,000 cities worldwide:
https://whatif.sonycsl.it/15mincity/

## Input data

| Ingredient | Source |
|---|---|
| City boundary | OECD functional-urban-area shapefiles, core city; GHS Urban Centre Database where OECD data is missing |
| Points of interest | OpenStreetMap, filtered to POIs that are services for people (trees, buildings and similar are discarded) |
| Population | WorldPop 100 m gridded population, rescaled to match UN-corrected municipal estimates |
| Travel times | Open Source Routing Machine (OSRM) over the OpenStreetMap network, walking and cycling profiles |

Analysis was done in Python with GeoPandas and the OSRM API.

## Spatial unit

The city is covered by a regular hexagonal grid (about 200 m side length, so
roughly 0.10 km2 per cell). Cells with no POI anywhere near them are dropped
from the analysis, which is why a prepared city can have cells that carry a
population but no accessibility score.

## The nine service categories

Every retained POI is classified into exactly one of nine categories:

1. outdoor activities
2. learning (education)
3. supplies
4. eating (restaurants)
5. moving (public transport)
6. cultural activities
7. physical exercise
8. services
9. health care

This lets accessibility be reported overall and per category.

## Proximity time, step by step

1. **Category time for one cell.** For a cell `k` and a category `c`, find the
   **20 nearest POIs** of that category by routed travel time, and average
   those 20 times:

   `<t>(c,k) = (1/20) * sum over i of t(i, c, k)`

   Twenty rather than one, deliberately: access to a single option is not
   meaningful choice, and the paper shows the results are robust to that
   number. Conceptually this is the "dual access" measure of Cui & Levinson.

2. **Proximity time of a cell.** Average the nine category times:

   `PT(k) = (1/9) * sum over c of <t>(c,k)`

   This is the value stored per cell, separately for walking and for cycling.

3. **Proximity time of a city (or of any area).** Average the cell values,
   **weighted by the population of each cell**:

   `PT_city = sum(PT(k) * pop(k)) / sum(pop(k))`

   Population weighting is what makes the score about residents rather than
   about geometry. An unweighted average over cells is a different, usually
   much worse-looking number, because empty peripheral cells count as much as
   dense central ones.

4. **F15, the 15-minute population share.**

   `F15 = 100 * sum of pop(k) where PT(k) <= 15 / sum of pop(k)`

   The same formula at other thresholds gives F10, F20, F30.

5. **Inequality of access.** The Gini index is computed over proximity times
   across residents (each resident carries their cell's PT, residents sorted
   by PT, Lorenz curve integrated). 0 means everyone has identical access;
   higher means more unequal. Note that a city can have a good average PT and
   still a substantial Gini, because times fluctuate.

## The redistribution results

Two simulations in the paper go beyond measurement:

- **Relocating existing POIs.** A heuristic algorithm redistributes the POIs a
  city already has so that each POI serves roughly the same number of people.
  Capacity is `CAP(c) = N_pop / N(c)`. The city starts empty; each iteration
  places a POI at the highest-demand cell (randomising among its neighbours to
  avoid always picking the local peak) and deducts `CAP(c)` from the unserved
  population within 15 minutes, in proportion to each cell's demand. Result:
  peripheries improve substantially while the centre is not stripped of
  services. Car-centric North American cities would need to relocate over 70%
  of their POIs; Milan, Copenhagen, Lisbon and Paris need very little, their
  distribution being already close to homogeneous.
- **Optimal number of POIs.** Starting from an empty city, POIs are added
  optimally until F15 reaches 90%. The count needed, per 1,000 residents, is
  the paper's measure of how hard 15-minuteness is for that city. Examples:
  Mumbai 0.45, Bogota 0.56, Turin 0.73, Milan 0.82, Copenhagen 0.94,
  Barcelona 0.97, Paris 1.39, Rome 2.45, Greater Melbourne 2.80,
  Amsterdam 5.36, Dallas 7.30, Detroit 11.65, Boston 15.03, Atlanta 15.46
  (about one POI per 64 residents, i.e. not sustainable).

## Known limitations of the data

State these when they are relevant to the question, rather than every time.

- OpenStreetMap POI coverage is uneven; it is thinner in parts of the Global
  South, which biases current-accessibility estimates downwards there.
- All POI categories are weighted equally, and all POIs within a category are
  treated as interchangeable. Quality, size, price and opening hours are not
  modelled.
- Routing uses the street network; dedicated sidewalk networks and local
  walkability (crossings, slope, safety, shade) are not modelled.
- Climate and cultural differences in what counts as an essential service are
  not modelled.
- Population is a gridded estimate, not a census count, for any given cell.
- The measure is a snapshot for its data vintage, not a live figure.
