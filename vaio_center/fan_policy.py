"""Fan mode policy: what the EC should be told for a mode and a CPU temperature.

Pure logic without I/O; the daemon calls target() every tick and only sends changes.
"""
MODES = ("quiet", "normal", "aggressive", "manual", "max")
AUTO = "auto"
LIMIT_C = 90           # manual/max hand control back to the EC at this CPU temperature
MIN_PCT = 30           # manual slider floor
QUIET_PCT = 25         # quiet duty: the helper's minimum (64/255)
QUIET_HANDOFF_C = 60   # quiet: the EC takes over at or above this
QUIET_RESUME_C = 55    # quiet: back to QUIET_PCT at or below this
AGGR_MIN_PCT = 40
AGGR_LOW_C = 45
AGGR_HIGH_C = 68
MAX_MISSES = 2         # consecutive unreadable temperatures before failing closed


def aggressive_pct(temp):
    if temp <= AGGR_LOW_C:
        return AGGR_MIN_PCT
    if temp >= AGGR_HIGH_C:
        return 100
    raw = AGGR_MIN_PCT + (100 - AGGR_MIN_PCT) * (temp - AGGR_LOW_C) / (AGGR_HIGH_C - AGGR_LOW_C)
    return min(100, 5 * round(raw / 5))


class FanPolicy:
    def __init__(self, mode="normal", duty_pct=50):
        self._last = AUTO
        self.set_mode(mode, duty_pct)

    def set_mode(self, mode, duty_pct=50):
        if mode not in MODES:
            raise ValueError(f"unknown fan mode {mode!r}")
        self.mode = mode
        self.duty_pct = max(MIN_PCT, min(100, int(duty_pct)))
        self.forced = False
        self.misses = 0
        self._quiet_handoff = False

    def target(self, temp):
        """AUTO, or the duty percent the fans should run at."""
        if temp is None:
            self.misses += 1
            if self.misses >= MAX_MISSES:
                self._last = AUTO
            return self._last
        self.misses = 0
        self._last = self._decide(temp)
        return self._last

    def _decide(self, temp):
        if self.forced or self.mode == "normal":
            return AUTO
        if self.mode in ("manual", "max"):
            if temp >= LIMIT_C:
                self.forced = True
                return AUTO
            return 100 if self.mode == "max" else self.duty_pct
        if self.mode == "aggressive":
            return aggressive_pct(temp)
        if temp >= QUIET_HANDOFF_C:
            self._quiet_handoff = True
        elif temp <= QUIET_RESUME_C:
            self._quiet_handoff = False
        return AUTO if self._quiet_handoff else QUIET_PCT
