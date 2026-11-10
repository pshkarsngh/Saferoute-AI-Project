"""SafeRoute AI — Phase 42 uncertainty reporting.

A point estimate without a sample count can overstate detector reliability. This
module supplies two explicit interval methods:

* Wilson score interval for a binomial proportion (precision/recall).
* Cluster bootstrap that resamples **collection sessions**, not frames, so
  adjacent video frames are not treated as independent observations.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_MIN_SAMPLES = 30
Z_95 = 1.959963984540054


def insufficient_sample(
    sample_size: int,
    minimum: int = DEFAULT_MIN_SAMPLES,
) -> bool:
    """Return True when a metric must be labelled ``insufficient_sample``."""
    return int(sample_size) < int(minimum)


def wilson_interval(
    successes: int,
    total: int,
    z: float = Z_95,
) -> Optional[Tuple[float, float]]:
    """Wilson score interval for a proportion. ``None`` when total is zero."""
    if total <= 0:
        return None
    successes = max(0, min(int(successes), int(total)))
    n = float(total)
    p = successes / n
    denominator = 1.0 + (z * z) / n
    centre = (p + (z * z) / (2.0 * n)) / denominator
    margin = (
        z
        * math.sqrt(max(0.0, (p * (1.0 - p) / n) + (z * z) / (4.0 * n * n)))
        / denominator
    )
    low = max(0.0, centre - margin)
    high = min(1.0, centre + margin)
    return (float(low), float(high))


@dataclass(frozen=True)
class BootstrapCI:
    estimate: Optional[float]
    low: Optional[float]
    high: Optional[float]
    n_clusters: int
    n_observations: int
    n_resamples: int
    method: str = "session_clustered_bootstrap"
    status: str = "ok"

    def to_dict(self) -> Dict[str, object]:
        return {
            "estimate": self.estimate,
            "low": self.low,
            "high": self.high,
            "n_clusters": self.n_clusters,
            "n_observations": self.n_observations,
            "n_resamples": self.n_resamples,
            "method": self.method,
            "status": self.status,
        }


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    if fraction <= 0:
        return float(sorted_values[0])
    if fraction >= 1:
        return float(sorted_values[-1])
    position = (len(sorted_values) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def clustered_bootstrap_ci(
    observations: Sequence[Any],
    statistic: Callable[[Sequence[Any]], Optional[float]],
    cluster_getter: Callable[[Any], Optional[str]] = lambda item: getattr(
        item, "cluster_id", None
    ),
    n_resamples: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
    min_clusters: int = 2,
    method: str = "session_clustered_bootstrap",
) -> BootstrapCI:
    """Percentile bootstrap CI resampling whole clusters with replacement.

    ``observations`` are the unit records (predictions for precision, annotated
    boxes for recall). ``statistic`` receives a resampled list and returns the
    metric or ``None``. Clusters are collection sessions/routes -- never
    individual frames.
    """
    if not observations:
        return BootstrapCI(
            estimate=None,
            low=None,
            high=None,
            n_clusters=0,
            n_observations=0,
            n_resamples=0,
            method=method,
            status="insufficient_sample",
        )

    buckets: Dict[str, List[Any]] = {}
    for index, observation in enumerate(observations):
        cluster = cluster_getter(observation)
        key = str(cluster) if cluster not in (None, "") else f"__frame__{index}"
        buckets.setdefault(key, []).append(observation)

    estimate = statistic(list(observations))
    if len(buckets) < min_clusters:
        return BootstrapCI(
            estimate=estimate,
            low=None,
            high=None,
            n_clusters=len(buckets),
            n_observations=len(observations),
            n_resamples=0,
            method=method,
            status="insufficient_sample",
        )

    keys = sorted(buckets)
    rng = random.Random(seed)
    estimates: List[float] = []
    for _ in range(max(1, int(n_resamples))):
        sampled_keys = [keys[rng.randrange(len(keys))] for _ in keys]
        sample: List[Any] = []
        for key in sampled_keys:
            sample.extend(buckets[key])
        value = statistic(sample)
        if value is not None and math.isfinite(float(value)):
            estimates.append(float(value))

    if not estimates:
        return BootstrapCI(
            estimate=estimate,
            low=None,
            high=None,
            n_clusters=len(buckets),
            n_observations=len(observations),
            n_resamples=n_resamples,
            method=method,
            status="undefined",
        )

    estimates.sort()
    return BootstrapCI(
        estimate=estimate,
        low=_percentile(estimates, alpha / 2.0),
        high=_percentile(estimates, 1.0 - alpha / 2.0),
        n_clusters=len(buckets),
        n_observations=len(observations),
        n_resamples=n_resamples,
        method=method,
        status="ok",
    )


__all__ = [
    "BootstrapCI",
    "DEFAULT_MIN_SAMPLES",
    "Z_95",
    "clustered_bootstrap_ci",
    "insufficient_sample",
    "wilson_interval",
]
