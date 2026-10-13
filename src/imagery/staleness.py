"""SafeRoute AI — Road Imagery Staleness & Timeliness Evaluator.

Phase ID: PHASE_14
Follows TRD §10.1, ARCHITECTURE §8, master_rules.md Rule 9.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple


class StalenessEvaluator:
    """Evaluates the timeliness and staleness of road imagery against policy thresholds."""

    def __init__(self, max_age_days: int = 180, flag_as_limitation: bool = True):
        self.max_age_days = max_age_days
        self.flag_as_limitation = flag_as_limitation

    def evaluate(
        self,
        captured_at: Optional[str],
        reference_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """Evaluate if an image capture timestamp is considered stale.
        
        Returns:
            (is_stale: bool, age_days: Optional[int], limitation_note: Optional[str])
        """
        if not captured_at:
            # Capture date unknown: flag as potential staleness limitation
            return True, None, "Imagery capture timestamp is unrecorded; freshness cannot be verified."

        ref = reference_time or datetime.now(timezone.utc)
        try:
            # Handle ISO formats
            clean_ts = captured_at.replace("Z", "+00:00")
            if "T" in clean_ts:
                cap_dt = datetime.fromisoformat(clean_ts)
            else:
                cap_dt = datetime.strptime(clean_ts[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)

            if cap_dt.tzinfo is None:
                cap_dt = cap_dt.replace(tzinfo=timezone.utc)

            delta = ref - cap_dt
            age_days = max(0, delta.days)

            if age_days > self.max_age_days:
                return (
                    True,
                    age_days,
                    f"Imagery is stale ({age_days} days old > {self.max_age_days} days policy threshold); condition may not reflect current road state.",
                )
            return False, age_days, None

        except Exception as e:
            return True, None, f"Failed to parse capture timestamp '{captured_at}': {str(e)}"
