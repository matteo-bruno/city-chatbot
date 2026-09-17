"""Population-weighted statistics used by both the prep script and the store.

Every headline number in the paper is weighted by the population living in a
cell, not by the number of cells: a city is "15-minute" for its residents, not
for its geometry. Keeping these in one place means the live queries and the
precomputed profile cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Sequence


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float | None:
    """Population-weighted mean, falling back to the plain mean if nobody lives there."""
    total_w = 0.0
    acc = 0.0
    for v, w in zip(values, weights):
        if v is None:
            continue
        if w > 0:
            acc += v * w
            total_w += w
    if total_w > 0:
        return acc / total_w
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def weighted_quantile(values: Sequence[float], weights: Sequence[float], q: float) -> float | None:
    """Lower-weighted quantile (q in [0, 1]) of values, weighted by weights."""
    pairs = sorted(
        ((v, w) for v, w in zip(values, weights) if v is not None and w > 0),
        key=lambda p: p[0],
    )
    if not pairs:
        clean = sorted(v for v in values if v is not None)
        if not clean:
            return None
        idx = min(len(clean) - 1, max(0, int(round(q * (len(clean) - 1)))))
        return clean[idx]
    total = sum(w for _, w in pairs)
    target = q * total
    cum = 0.0
    for v, w in pairs:
        cum += w
        if cum >= target:
            return v
    return pairs[-1][0]


def weighted_share_below(
    values: Sequence[float], weights: Sequence[float], threshold: float
) -> float | None:
    """Percentage of the weight whose value is <= threshold.

    With `values` = proximity times and `weights` = population this is F_t from
    the paper (F15 for the 15-minute threshold), expressed in percent.
    """
    total = 0.0
    below = 0.0
    for v, w in zip(values, weights):
        if v is None or w <= 0:
            continue
        total += w
        if v <= threshold:
            below += w
    if total <= 0:
        return None
    return 100.0 * below / total


def weighted_gini(values: Sequence[float], weights: Sequence[float]) -> float | None:
    """Gini index of `values` across the population given by `weights`.

    Discrete form of equation (5) in Bruno et al. (2024): every resident of a
    cell is assigned that cell's proximity time, the residents are sorted by
    it, and the Lorenz curve is integrated. Identical to the per-person formula
    up to a 1/N_pop term that is negligible at city scale.
    """
    pairs = sorted(
        ((v, w) for v, w in zip(values, weights) if v is not None and w > 0),
        key=lambda p: p[0],
    )
    if len(pairs) < 2:
        return None
    total_w = sum(w for _, w in pairs)
    total_vw = sum(v * w for v, w in pairs)
    if total_w <= 0 or total_vw <= 0:
        return None
    cum = 0.0
    acc = 0.0
    for v, w in pairs:
        prev = cum
        cum += v * w
        acc += w * (prev + cum)
    return 1.0 - acc / (total_w * total_vw)
