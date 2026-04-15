"""Peer state management for fleet coordination."""
from dataclasses import dataclass, field
from enum import IntEnum
import time


class CoordinationState(IntEnum):
    NORMAL = 0
    AWARENESS = 1
    CAUTION = 2
    YIELDING = 3
    PASSING = 4
    EMERGENCY = 5


@dataclass
class PeerState:
    robot_id: str
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    linear_vel: float = 0.0
    angular_vel: float = 0.0
    last_seen: float = field(default_factory=time.time)
    planned_path: list = field(default_factory=list)
    coordination_state: CoordinationState = CoordinationState.NORMAL
    yield_start_time: float = 0.0
    yield_count: int = 0
    dist_to_goal: float = float("inf")
    battery_pct: float = 100.0

    def calculate_priority(self) -> float:
        score = self.yield_count * 10.0
        if self.dist_to_goal > 0:
            score += (1.0 / self.dist_to_goal) * 5.0
        score += (100 - self.battery_pct) * 0.1
        return score
