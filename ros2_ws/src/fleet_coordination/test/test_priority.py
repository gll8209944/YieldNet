"""Unit tests for priority calculation - M4 Dynamic Priority Scoring.

Tests the dynamic priority scoring formula from architecture spec §6.4:
    priority_score = yield_count × 10.0
                   + (1.0 / dist_to_goal) × 5.0
                   + (100 - battery_pct) × 0.1

And lexicographic tie-breaking by robot_id.
"""

import pytest
from fleet_coordination.peer_state import PeerState


class TestPriorityCalculation:
    """Test suite for dynamic priority scoring."""

    def test_higher_yield_count_higher_priority(self):
        """More yield events = higher priority (starvation prevention)."""
        peer_low = PeerState("robot_a")
        peer_low.yield_count = 0
        peer_low.dist_to_goal = 10.0
        peer_low.battery_pct = 100.0

        peer_high = PeerState("robot_b")
        peer_high.yield_count = 5
        peer_high.dist_to_goal = 10.0
        peer_high.battery_pct = 100.0

        assert peer_high.calculate_priority_score() > peer_low.calculate_priority_score()

    def test_closer_to_goal_higher_priority(self):
        """Closer to goal = higher priority."""
        peer_far = PeerState("robot_a")
        peer_far.yield_count = 0
        peer_far.dist_to_goal = 100.0
        peer_far.battery_pct = 100.0

        peer_close = PeerState("robot_b")
        peer_close.yield_count = 0
        peer_close.dist_to_goal = 5.0
        peer_close.battery_pct = 100.0

        assert peer_close.calculate_priority_score() > peer_far.calculate_priority_score()

    def test_lower_battery_higher_priority(self):
        """Lower battery = higher priority (urgency)."""
        peer_full = PeerState("robot_a")
        peer_full.yield_count = 0
        peer_full.dist_to_goal = 10.0
        peer_full.battery_pct = 100.0

        peer_low = PeerState("robot_b")
        peer_low.yield_count = 0
        peer_low.dist_to_goal = 10.0
        peer_low.battery_pct = 20.0

        assert peer_low.calculate_priority_score() > peer_full.calculate_priority_score()

    def test_priority_score_formula_components(self):
        """Verify formula components are weighted correctly."""
        peer = PeerState("robot_a")
        peer.yield_count = 3
        peer.dist_to_goal = 10.0
        peer.battery_pct = 50.0

        expected = 3 * 10.0 + (1.0 / 10.0) * 5.0 + (100 - 50.0) * 0.1
        expected = 30.0 + 0.5 + 5.0 = 35.5

        assert abs(peer.calculate_priority_score() - expected) < 0.01

    def test_zero_dist_to_goal_handled(self):
        """Zero distance to goal should be handled gracefully."""
        peer = PeerState("robot_a")
        peer.yield_count = 0
        peer.dist_to_goal = 0.0  # At goal
        peer.battery_pct = 100.0

        # Should not divide by zero, should use large value instead
        score = peer.calculate_priority_score()
        assert score == 0.0  # yield_count * 10 only

    def test_lexicographic_tiebreaker(self):
        """Equal scores should be broken by robot_id lexicographic order.

        Note: This is handled by comparison logic outside PeerState.
        PeerState only computes the numeric score.
        """
        peer_a = PeerState("robot_a")
        peer_a.yield_count = 1
        peer_a.dist_to_goal = 10.0
        peer_a.battery_pct = 100.0

        peer_b = PeerState("robot_b")
        peer_b.yield_count = 1
        peer_b.dist_to_goal = 10.0
        peer_b.battery_pct = 100.0

        # Same numeric score
        assert peer_a.calculate_priority_score() == peer_b.calculate_priority_score()

        # But robot_id differs - "robot_a" < "robot_b" lexicographically
        assert peer_a.robot_id < peer_b.robot_id


class TestPriorityComparison:
    """Test suite for priority comparison between robots."""

    def test_two_robot_static_priority(self):
        """Two robots with equal dynamic scores: lexicographic wins."""
        # robot_a < robot_b lexicographically
        # So robot_a has priority when scores are equal
        score_a = PeerState("robot_a").calculate_priority_score()
        score_b = PeerState("robot_b").calculate_priority_score()

        assert score_a == score_b  # Same score

        # But robot_id comparison gives robot_a higher "effective" priority
        robot_ids_equal_score = ["robot_a", "robot_b"]
        robot_ids_equal_score.sort()
        assert robot_ids_equal_score[0] == "robot_a"  # robot_a wins tie

    def test_three_robot_dynamic_priority_order(self):
        """Three robots with different yield counts should be ordered correctly."""
        peer_c = PeerState("robot_c")
        peer_c.yield_count = 0

        peer_b = PeerState("robot_b")
        peer_b.yield_count = 3

        peer_a = PeerState("robot_a")
        peer_a.yield_count = 5

        # Sort by (priority_score, robot_id) - higher score first, then lexicographic
        peers = [peer_a, peer_b, peer_c]
        peers.sort(key=lambda p: (-p.calculate_priority_score(), p.robot_id))

        assert peers[0].robot_id == "robot_a"  # Highest yield_count
        assert peers[1].robot_id == "robot_b"
        assert peers[2].robot_id == "robot_c"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
