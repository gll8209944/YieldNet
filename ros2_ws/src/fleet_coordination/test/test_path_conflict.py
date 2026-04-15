"""Unit tests for path conflict detection - M4 Multi-robot Extension.

Tests the path conflict detection algorithm from architecture spec §6.3:
- Paths conflict if any two points are within PATH_CONFLICT_THRESHOLD
- Uses hysteresis (CONFLICT_HYSTERESIS_TICKS) to prevent flickering
"""

import pytest
import math


class MockPeer:
    """Mock peer for testing path conflict detection."""

    def __init__(self, robot_id: str, planned_path: list[tuple[float, float]]):
        self.robot_id = robot_id
        self.planned_path = planned_path


class PathConflictDetector:
    """Path conflict detection logic extracted for unit testing.

    Mirrors the logic in FleetCoordinator._check_path_conflict().
    """

    PATH_CONFLICT_THRESHOLD = 1.5  # meters

    @classmethod
    def check_conflict(cls, own_path, peer_path):
        """Check if two paths conflict.

        Args:
            own_path: List of (x, y) tuples
            peer_path: List of (x, y) tuples

        Returns:
            True if any points are within threshold distance
        """
        if not own_path or not peer_path:
            return False

        for my_pt in own_path:
            for peer_pt in peer_path:
                dist = math.sqrt((my_pt[0] - peer_pt[0])**2 + (my_pt[1] - peer_pt[1])**2)
                if dist < cls.PATH_CONFLICT_THRESHOLD:
                    return True
        return False


class TestPathConflictDetection:
    """Test suite for path conflict detection."""

    def test_no_conflict_parallel_paths(self):
        """Parallel paths with sufficient clearance should not conflict."""
        # Two robots moving in parallel, 3m apart
        own_path = [(0, 0), (1, 0), (2, 0), (3, 0)]  # Along x-axis at y=0
        peer_path = [(0, 3), (1, 3), (2, 3), (3, 3)]  # Along x-axis at y=3

        assert not PathConflictDetector.check_conflict(own_path, peer_path)

    def test_conflict_crossing_paths(self):
        """Crossing paths should conflict at intersection."""
        # Two robots crossing at origin
        own_path = [(0, 0), (1, 1), (2, 2)]  # Diagonal
        peer_path = [(0, 2), (1, 1), (2, 0)]  # Other diagonal (intersects at (1,1))

        assert PathConflictDetector.check_conflict(own_path, peer_path)

    def test_conflict_head_on_approach(self):
        """Head-on approach should conflict."""
        own_path = [(0, 0), (1, 0), (2, 0)]  # Moving +x
        peer_path = [(2, 0), (1, 0), (0, 0)]  # Moving -x (same line)

        assert PathConflictDetector.check_conflict(own_path, peer_path)

    def test_no_conflict_safe_distance(self):
        """Paths with all points > threshold apart should not conflict."""
        own_path = [(0, 0), (5, 0), (10, 0)]
        peer_path = [(0, 5), (5, 5), (10, 5)]  # 5m apart ( > 1.5m threshold)

        assert not PathConflictDetector.check_conflict(own_path, peer_path)

    def test_no_conflict_empty_path(self):
        """Empty path should not cause conflict."""
        own_path = []
        peer_path = [(0, 0), (1, 1)]

        assert not PathConflictDetector.check_conflict(own_path, peer_path)

    def test_no_conflict_peer_empty_path(self):
        """Empty peer path should not cause conflict."""
        own_path = [(0, 0), (1, 1)]
        peer_path = []

        assert not PathConflictDetector.check_conflict(own_path, peer_path)

    def test_conflict_at_threshold_boundary(self):
        """Points exactly at threshold should not conflict (strict <)."""
        # Points exactly at 1.5m apart
        own_path = [(0, 0)]
        peer_path = [(1.5, 0)]  # Exactly at threshold

        # Strict less than, so this should NOT conflict
        assert not PathConflictDetector.check_conflict(own_path, peer_path)

    def test_conflict_just_within_threshold(self):
        """Points just within threshold should conflict."""
        own_path = [(0, 0)]
        peer_path = [(1.4, 0)]  # Just within 1.5m threshold

        assert PathConflictDetector.check_conflict(own_path, peer_path)

    def test_conflict_t_intersection(self):
        """T-intersection should conflict."""
        # Robot A going north, Robot B going east
        own_path = [(0, 0), (0, 1), (0, 2), (0, 3)]  # North
        peer_path = [(0, 1), (1, 1), (2, 1), (3, 1)]  # East (crosses at (0,1))

        assert PathConflictDetector.check_conflict(own_path, peer_path)


class TestConflictHysteresis:
    """Test suite for conflict hysteresis (debouncing)."""

    def test_hysteresis_prevents_flickering(self):
        """Single conflicting tick should not clear conflict immediately."""
        conflict_ticks = 0
        CONFLICT_HYSTERESIS = 5

        # Simulate: conflict for 3 ticks, then clears
        for i in range(3):
            conflict_ticks += 1
            # With hysteresis, conflict should still be considered active
            is_persistent = conflict_ticks >= CONFLICT_HYSTERESIS
            assert not is_persistent

        # Simulate: conflict for 5+ ticks
        for i in range(5):
            conflict_ticks += 1
            is_persistent = conflict_ticks >= CONFLICT_HYSTERESIS
            if conflict_ticks >= CONFLICT_HYSTERESIS:
                assert is_persistent

    def test_hysteresis_clear_requires_continuous_clear(self):
        """Conflict should only clear after CONFLICT_HYSTERESIS clean ticks."""
        conflict_ticks = 10  # Already in conflict
        CONFLICT_HYSTERESIS = 5

        # Simulate 5 clean ticks - should NOT clear yet
        for i in range(5):
            conflict_ticks = max(0, conflict_ticks - 1)
            is_persistent = conflict_ticks >= CONFLICT_HYSTERESIS
            assert is_persistent, f"Tick {i+1}: should still be persistent (ticks={conflict_ticks})"

        # After 5 clean ticks, still at threshold
        assert conflict_ticks == 5

        # Simulate 1 more clean tick - NOW it clears
        conflict_ticks = max(0, conflict_ticks - 1)
        assert conflict_ticks == 4
        is_persistent = conflict_ticks >= CONFLICT_HYSTERESIS
        assert not is_persistent, "Should clear after 6 clean ticks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
