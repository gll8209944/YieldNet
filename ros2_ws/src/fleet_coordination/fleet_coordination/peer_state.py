"""Peer state management for fleet coordination - M4 Multi-robot Extension."""
from dataclasses import dataclass, field
from enum import IntEnum
import time


class CoordinationState(IntEnum):
    """Per-peer coordination states ordered by urgency (higher = more conservative).

    State ordering: NORMAL < AWARENESS < CAUTION < YIELDING < PASSING < EMERGENCY
    Used with max() to find worst-case across all peers.
    """
    NORMAL = 0
    AWARENESS = 1
    CAUTION = 2
    YIELDING = 3
    PASSING = 4
    EMERGENCY = 5


@dataclass
class PeerState:
    """Dynamic peer state for N-robot per-peer scalability.

    Each robot maintains a Dict[str, PeerState] for all known peers.
    Decisions are made per-peer, then the most conservative result is used.
    """
    robot_id: str
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    linear_vel: float = 0.0
    angular_vel: float = 0.0
    last_seen: float = field(default_factory=time.time)
    planned_path: list = field(default_factory=list)  # List of (x, y) tuples
    coordination_state: CoordinationState = CoordinationState.NORMAL
    yield_start_time: float = 0.0
    yield_count: int = 0  # Cumulative yield events (for dynamic priority)
    dist_to_goal: float = float("inf")  # Distance to goal (for dynamic priority)
    battery_pct: float = 100.0  # Battery percentage (for dynamic priority)

    def calculate_priority_score(self) -> float:
        """Dynamic priority scoring to prevent starvation.

        Formula:
            priority_score = yield_count × 10.0
                          + (1.0 / dist_to_goal) × 5.0
                          + (100 - battery_pct) × 0.1

        Higher score = higher priority to pass.
        All robots compute this independently and get the same result.
        """
        score = self.yield_count * 10.0
        if self.dist_to_goal > 0:
            score += (1.0 / self.dist_to_goal) * 5.0
        score += (100 - self.battery_pct) * 0.1
        return score

    def update_last_seen(self):
        """Update last seen timestamp to current time."""
        self.last_seen = time.time()
