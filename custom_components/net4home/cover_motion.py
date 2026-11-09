"""Travel state and position for net4home covers.

Commands use D0_SET with 3 = up, 1 = down, 0 = stop. The actor answers a
status request with its own position in percent, 100 up and 0 down, or
0xFF while it does not know it (no run time, or no full run since power-up).
Home Assistant uses the same scale: 100 fully open, 0 fully closed.
"""

from __future__ import annotations

from dataclasses import dataclass

MOTION_STOP = 0
MOTION_DOWN = 1
MOTION_UP = 3

POSITION_UNKNOWN = 0xFF


def cover_position_from_status(status: int) -> int | None:
    """Position in percent from the actor status byte, None if unknown."""
    if 0 <= status <= 100:
        return status
    return None


@dataclass
class CoverTravel:
    """Position estimate from the configured run time of the channel.

    An unknown position only becomes known after a run of at least the
    full run time, because the cover then sits at an end stop.
    """

    position: int | None = None
    closed: bool | None = None
    motion: int = MOTION_STOP
    started_at: float | None = None

    def position_at(self, now: float, run_time: float | None) -> int | None:
        if self.motion == MOTION_STOP or self.started_at is None or not run_time:
            return self.position
        elapsed = max(0.0, now - self.started_at)
        if self.position is None:
            if elapsed < run_time:
                return None
            return 100 if self.motion == MOTION_UP else 0
        delta = elapsed * 100.0 / run_time
        moved = self.position + delta if self.motion == MOTION_UP else self.position - delta
        return int(round(min(100.0, max(0.0, moved))))

    def start(self, motion: int, now: float, run_time: float | None) -> bool:
        """Begin a run. Returns False if the cover already runs that way."""
        if motion == MOTION_STOP:
            self.stop(now, run_time)
            return True
        if motion == self.motion:
            return False
        if self.motion != MOTION_STOP:
            self.stop(now, run_time)
        if not run_time:
            self.closed = motion == MOTION_DOWN
            return True
        self.motion = motion
        self.started_at = now
        return True

    def stop(self, now: float, run_time: float | None) -> None:
        if self.motion == MOTION_STOP:
            return
        motion = self.motion
        self.position = self.position_at(now, run_time)
        self.motion = MOTION_STOP
        self.started_at = None
        if self.position is not None:
            self.closed = self.position == 0
        elif motion == MOTION_UP:
            self.closed = False

    def report(self, position: int | None, now: float) -> bool:
        """Apply a position reported by the actor. True if this ends a run."""
        if position is None:
            if self.motion == MOTION_STOP:
                self.position = None
                self.closed = None
            return False
        if self.motion != MOTION_STOP:
            end = 100 if self.motion == MOTION_UP else 0
            self.position = position
            if position != end:
                self.started_at = now
                return False
            self.motion = MOTION_STOP
            self.started_at = None
            self.closed = position == 0
            return True
        self.position = position
        self.closed = position == 0
        return False

    def is_closed(self) -> bool | None:
        if self.motion == MOTION_UP:
            return False
        if self.position is not None and self.motion == MOTION_STOP:
            return self.position == 0
        return self.closed

    def seconds_to(self, target: int, run_time: float) -> float:
        """Run time needed from the current, known position to target."""
        assert self.position is not None
        return abs(target - self.position) * run_time / 100.0
