#!/usr/bin/env python3
"""Fleet Coordinator - M4 Multi-robot Extension with per-peer architecture.

This module implements the multi-robot collision avoidance coordination logic
as specified in the system architecture design §6 and §8.

Key features:
- Per-peer state management (Dict[str, PeerState]) for N-robot scalability
- Dynamic priority scoring to prevent starvation
- Path conflict detection with hysteresis
- 6-state coordination state machine
- Decentralized decision making (no central coordinator needed)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math
import time
from nav_msgs.msg import Odometry
from fleet_msgs.msg import RobotHeartbeat, RobotPose, PlannedPath, YieldCommand
from fleet_coordination.peer_state import PeerState, CoordinationState

# YieldCommand command types
CMD_REQUEST_YIELD = 0
CMD_ACK_YIELD = 1
CMD_RESUME = 2
CMD_EMERGENCY_STOP = 3

# Speed scaling factors per state
SPEED_SCALING = {
    CoordinationState.NORMAL: 1.0,
    CoordinationState.AWARENESS: 1.0,
    CoordinationState.CAUTION: 0.5,
    CoordinationState.YIELDING: 0.0,
    CoordinationState.PASSING: 0.3,
    CoordinationState.EMERGENCY: 0.0,
}

# Path conflict detection parameters
PATH_CONFLICT_THRESHOLD = 1.5  # meters
PATH_LOOKAHEAD = 5.0  # meters
CONFLICT_HYSTERESIS_TICKS = 5  # must be clear for 5 ticks to clear conflict


class FleetCoordinator(Node):
    """Multi-robot fleet coordination node with per-peer architecture.

    This node runs on each robot and communicates with peers via DDS.
    It subscribes to local Nav2 topics and fleet topics, makes independent
    decisions based on the coordination state machine, and outputs speed
    scaling factors to the chassis.

    Per-peer architecture: Each robot maintains a Dict[str, PeerState] and
    evaluates each peer independently, then takes the most conservative result.
    """

    def __init__(self):
        super().__init__("fleet_coordinator")
        self._declare_parameters()
        self._init_state()
        self._init_publishers()
        self._init_subscriptions()
        self._init_local_subscriptions()
        self._init_timers()

        self.get_logger().info(
            f"Fleet Coordinator started: {self.robot_id} "
            f"(emergency={self.emergency_range}m, yield={self.yield_range}m, "
            f"caution={self.caution_range}m, awareness={self.awareness_range}m)"
        )

    def _declare_parameters(self):
        """Declare all ROS 2 parameters with defaults from architecture spec."""
        self.declare_parameter("robot_id", "robot_a")
        self.declare_parameter("peer_ids", ["robot_b", "robot_c"])

        # Distance thresholds (from architecture spec §5.3)
        self.declare_parameter("emergency_range", 0.8)
        self.declare_parameter("yield_range", 2.5)
        self.declare_parameter("caution_range", 4.0)
        self.declare_parameter("awareness_range", 8.0)
        self.declare_parameter("path_conflict_dist", 1.5)
        self.declare_parameter("path_lookahead", 5.0)

        # Timeouts (from architecture spec §5.3)
        self.declare_parameter("yield_timeout", 15.0)
        self.declare_parameter("heartbeat_timeout", 6.0)

        # Own robot state
        self.declare_parameter("own_x", 0.0)
        self.declare_parameter("own_y", 0.0)
        self.declare_parameter("own_theta", 0.0)
        self.declare_parameter("own_linear_vel", 0.0)
        self.declare_parameter("own_dist_to_goal", float("inf"))
        self.declare_parameter("own_battery_pct", 100.0)

        # Read parameters
        self.robot_id = self.get_parameter("robot_id").value
        self.emergency_range = self.get_parameter("emergency_range").value
        self.yield_range = self.get_parameter("yield_range").value
        self.caution_range = self.get_parameter("caution_range").value
        self.awareness_range = self.get_parameter("awareness_range").value
        self.path_conflict_dist = self.get_parameter("path_conflict_dist").value
        self.path_lookahead = self.get_parameter("path_lookahead").value
        self.yield_timeout = self.get_parameter("yield_timeout").value
        self.heartbeat_timeout = self.get_parameter("heartbeat_timeout").value

    def _init_state(self):
        """Initialize node state."""
        # Per-peer state dictionary - key is robot_id, value is PeerState
        self.peers: dict[str, PeerState] = {}

        # Own robot state
        self.own_x = self.get_parameter("own_x").value
        self.own_y = self.get_parameter("own_y").value
        self.own_theta = self.get_parameter("own_theta").value
        self.own_linear_vel = self.get_parameter("own_linear_vel").value
        self.own_dist_to_goal = self.get_parameter("own_dist_to_goal").value
        self.own_battery_pct = self.get_parameter("own_battery_pct").value
        self.own_yield_count = 0

        # Own planned path for conflict detection
        self.own_planned_path: list[tuple[float, float]] = []

        # Coordination state
        self.current_state = CoordinationState.NORMAL
        self.own_yield_start_time = 0.0

        # Conflict tracking with hysteresis
        self._conflict_ticks: dict[str, int] = {}  # peer_id -> consecutive conflict ticks

        # Pending yield acknowledgments
        self._pending_ack_from: set[str] = set()

    def _init_publishers(self):
        """Initialize fleet topic publishers."""
        # BestEffort for frequent data (pose, heartbeat, path)
        qos_be = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.heartbeat_pub = self.create_publisher(RobotHeartbeat, "/fleet/heartbeat", qos_be)
        self.pose_pub = self.create_publisher(RobotPose, "/fleet/pose", qos_be)
        self.path_pub = self.create_publisher(PlannedPath, "/fleet/planned_path", qos_be)

        # Reliable for yield commands (important for coordination)
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
        self.yield_pub = self.create_publisher(YieldCommand, "/fleet/yield", qos_reliable)

        # Cmd_vel output (speed scaling factor)
        # Note: In full integration, this would interface with Nav2 or chassis
        # Use RELIABLE QoS to ensure speed commands are received
        # Use relative path so namespace is applied
        qos_speed = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.cmd_vel_pub = self.create_publisher(
            RobotPose, "fleet/coordinator_speed", qos_speed
        )

        # Diagnostic topic for local monitoring at 1Hz
        # Per SAD §13.2: This does NOT go through domain_bridge
        from std_msgs.msg import String
        qos_diag = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        self.diagnostic_pub = self.create_publisher(
            String, "fleet/coordinator_status", qos_diag
        )

    def _init_subscriptions(self):
        """Initialize fleet topic subscriptions."""
        # Fleet topics from other robots - use BEST_EFFORT to match publishers
        qos_sub = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.create_subscription(RobotHeartbeat, "/fleet/heartbeat", self._heartbeat_callback, qos_sub)
        self.create_subscription(RobotPose, "/fleet/pose", self._pose_callback, qos_sub)
        self.create_subscription(PlannedPath, "/fleet/planned_path", self._path_callback, qos_sub)
        self.create_subscription(YieldCommand, "/fleet/yield", self._yield_callback, qos_sub)

    def _init_local_subscriptions(self):
        """Initialize subscriptions to local robot sensors via robot namespace."""
        # Subscribe to local odometry to get actual position
        # This is used instead of static own_x/own_y parameters
        from nav_msgs.msg import Odometry
        qos_odom = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(
            Odometry,
            f"/{self.robot_id}/odom",
            self._odom_callback,
            qos_odom
        )

    def _odom_callback(self, msg):
        """Handle incoming odometry data to update own position."""
        self.own_x = msg.pose.pose.position.x
        self.own_y = msg.pose.pose.position.y
        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        self.own_theta = math.atan2(2.0*(q.w*q.z + q.x*q.y), 1.0 - 2.0*(q.y*q.y + q.z*q.z))
        self.own_linear_vel = msg.twist.twist.linear.x

    def _init_timers(self):
        """Initialize timers for coordination loop and publishing.

        Per spec §2.3:
        - heartbeat: 0.5 Hz (every 2s)
        - pose: 10 Hz (every 0.1s)
        - planned_path: 2 Hz (every 0.5s)
        """
        # Main coordination tick at 10 Hz (100ms)
        self.coordination_timer = self.create_timer(0.1, self._coordination_tick)

        # Heartbeat at 0.5 Hz (every 2 seconds)
        self.heartbeat_timer = self.create_timer(2.0, self._publish_heartbeat)

        # Pose at 10 Hz (every 0.1 seconds)
        self.pose_timer = self.create_timer(0.1, self._publish_pose)

        # Planned path at 2 Hz (every 0.5 seconds)
        self.path_timer = self.create_timer(0.5, self._publish_planned_path)

        # Diagnostic status at 1Hz
        self.diagnostic_timer = self.create_timer(1.0, self._publish_diagnostic)

    def _heartbeat_callback(self, msg: RobotHeartbeat):
        """Handle incoming heartbeat from peer.

        Extracts priority-related data for dynamic scoring.
        """
        if msg.robot_id == self.robot_id:
            return

        if msg.robot_id not in self.peers:
            self.get_logger().info(f"Discovered new peer: {msg.robot_id}")
            self.peers[msg.robot_id] = PeerState(msg.robot_id)

        peer = self.peers[msg.robot_id]
        peer.battery_pct = msg.battery_pct
        peer.yield_count = msg.yield_count
        peer.dist_to_goal = msg.dist_to_goal
        peer.update_last_seen()

    def _pose_callback(self, msg: RobotPose):
        """Handle incoming pose from peer.

        Updates peer's position for distance calculation.
        """
        if msg.robot_id == self.robot_id:
            return

        if msg.robot_id not in self.peers:
            self.peers[msg.robot_id] = PeerState(msg.robot_id)

        peer = self.peers[msg.robot_id]
        peer.x = msg.x
        peer.y = msg.y
        peer.theta = msg.theta
        peer.linear_vel = msg.linear_vel
        peer.angular_vel = msg.angular_vel
        peer.update_last_seen()

    def _path_callback(self, msg: PlannedPath):
        """Handle incoming planned path from peer.

        Updates peer's path for conflict detection.
        """
        if msg.robot_id == self.robot_id:
            # Store own path for conflict detection
            self.own_planned_path = [(p.x, p.y) for p in msg.waypoints[:10]]
            return

        if msg.robot_id not in self.peers:
            self.peers[msg.robot_id] = PeerState(msg.robot_id)

        peer = self.peers[msg.robot_id]
        peer.planned_path = [(p.x, p.y) for p in msg.waypoints[:10]]
        peer.update_last_seen()

    def _yield_callback(self, msg: YieldCommand):
        """Handle incoming yield command from peer.

        Processes ACK_YIELD and RESUME commands.
        """
        if msg.to_robot != self.robot_id:
            return

        peer_id = msg.from_robot

        if msg.command == CMD_ACK_YIELD:
            self.get_logger().info(f"ACK_YIELD received from {peer_id}")
            self._pending_ack_from.discard(peer_id)
            # Remote peer has yielded to us - we can PASSING
            if peer_id in self.peers:
                self.peers[peer_id].coordination_state = CoordinationState.PASSING

        elif msg.command == CMD_RESUME:
            self.get_logger().info(f"RESUME received from {peer_id}")
            self._pending_ack_from.discard(peer_id)
            # Remote peer has resumed - clear our yielding state if we were waiting
            if self.current_state == CoordinationState.YIELDING:
                self.current_state = CoordinationState.NORMAL
                self.own_yield_start_time = 0.0

        elif msg.command == CMD_EMERGENCY_STOP:
            self.get_logger().warn(f"EMERGENCY_STOP from {peer_id}")
            self.current_state = CoordinationState.EMERGENCY

    def _publish_heartbeat(self):
        """Publish heartbeat at 0.5 Hz (every 2 seconds).

        Per spec §4.1 FR-001: heartbeat contains robot_id, status, battery_pct, yield_count, dist_to_goal.
        """
        current_time = self.get_clock().now().to_msg()

        heartbeat = RobotHeartbeat()
        heartbeat.robot_id = self.robot_id
        heartbeat.status = 1  # moving
        heartbeat.battery_pct = self.own_battery_pct
        heartbeat.yield_count = self.own_yield_count
        heartbeat.dist_to_goal = self.own_dist_to_goal
        heartbeat.stamp = current_time
        self.heartbeat_pub.publish(heartbeat)

    def _publish_pose(self):
        """Publish pose at 10 Hz (every 0.1 seconds).

        Per spec §4.1 FR-002: pose contains x, y, theta, linear_vel, angular_vel.
        """
        current_time = self.get_clock().now().to_msg()

        pose = RobotPose()
        pose.robot_id = self.robot_id
        pose.x = self.own_x
        pose.y = self.own_y
        pose.theta = self.own_theta
        pose.linear_vel = self.own_linear_vel
        pose.angular_vel = 0.0
        pose.stamp = current_time
        self.pose_pub.publish(pose)

    def _publish_planned_path(self):
        """Publish planned path at 2 Hz (every 0.5 seconds).

        Per spec §4.1 FR-003: path contains waypoints ahead 5m.
        """
        if not self.own_planned_path:
            return

        current_time = self.get_clock().now().to_msg()
        path_msg = PlannedPath()
        path_msg.robot_id = self.robot_id
        from geometry_msgs.msg import Point
        for x, y in self.own_planned_path:
            p = Point()
            p.x = x
            p.y = y
            p.z = 0.0
            path_msg.waypoints.append(p)
        path_msg.estimated_speed = self.own_linear_vel
        path_msg.stamp = current_time
        self.path_pub.publish(path_msg)

    def _publish_diagnostic(self):
        """Publish diagnostic status to /fleet/coordinator_status.

        Per SAD §13.2: Diagnostic topic at 1Hz containing:
        - robot_id
        - current state
        - speed_ratio
        - peer list with distances and states
        """
        import json
        from std_msgs.msg import String

        diag = {
            'robot_id': self.robot_id,
            'state': self.current_state.name,
            'speed_ratio': self.get_speed_scaling(),
            'peers': []
        }

        for peer_id, peer in self.peers.items():
            dist = math.sqrt((peer.x - self.own_x)**2 + (peer.y - self.own_y)**2)
            diag['peers'].append({
                'robot_id': peer_id,
                'distance': round(dist, 2),
                'state': peer.coordination_state.name if hasattr(peer.coordination_state, 'name') else str(peer.coordination_state),
                'priority_score': peer.calculate_priority_score()
            })

        msg = String()
        msg.data = json.dumps(diag)
        self.diagnostic_pub.publish(msg)

    def get_speed_scaling(self) -> float:
        """Get current speed scaling factor based on coordination state."""
        return SPEED_SCALING.get(self.current_state, 1.0)

    def _coordination_tick(self):
        """Main coordination decision loop at 10 Hz.

        Per architecture spec §6.2:
        1. Remove timed-out peers
        2. Evaluate each peer independently
        3. Take the most conservative result
        4. Handle yield timeouts
        """
        current_time = time.time()

        # Debug: log own position every 5 seconds
        if not hasattr(self, '_last_debug_time') or (current_time - self._last_debug_time) > 5.0:
            self._last_debug_time = current_time
            self.get_logger().info(f"TICK: own_pos=({self.own_x:.2f}, {self.own_y:.2f}), peers={len(self.peers)}")

        # Step 1: Remove timed-out peers
        self._remove_timed_out_peers(current_time)

        # Step 2: Evaluate each peer independently
        worst_state = CoordinationState.NORMAL
        worst_speed_ratio = 1.0

        for peer_id, peer in self.peers.items():
            peer_state, speed_ratio = self._evaluate_single_peer(peer, current_time)
            peer.coordination_state = peer_state

            # Take the most conservative (slowest) result
            if speed_ratio < worst_speed_ratio:
                worst_speed_ratio = speed_ratio
            if peer_state > worst_state:
                worst_state = peer_state

        # Step 3: Update overall state
        previous_state = self.current_state
        self.current_state = worst_state

        # State change logging
        if previous_state != self.current_state:
            self.get_logger().info(
                f"STATE_CHANGE: {self.robot_id} {previous_state.name} -> {self.current_state.name} "
                f"(speed_ratio={worst_speed_ratio:.2f})"
            )

        # Step 4: Handle yield timeout
        self._handle_yield_timeout(current_time)

        # Step 5: Publish speed scaling
        self._publish_speed_scaling(worst_speed_ratio)

    def _remove_timed_out_peers(self, current_time: float):
        """Remove peers that haven't been seen recently."""
        timed_out_ids = [
            pid for pid, peer in self.peers.items()
            if current_time - peer.last_seen > self.heartbeat_timeout
        ]
        for pid in timed_out_ids:
            del self.peers[pid]
            self._conflict_ticks.pop(pid, None)
            self._pending_ack_from.discard(pid)
            self.get_logger().warn(f"Peer {pid} timed out after {self.heartbeat_timeout}s")

    def _evaluate_single_peer(self, peer: PeerState, current_time: float) -> tuple[CoordinationState, float]:
        """Evaluate coordination state for a single peer.

        Per architecture spec §6.2, this implements the per-peer decision logic:
        1. Calculate distance to peer
        2. Check for path conflicts
        3. Determine state based on distance and conflict
        4. Apply priority rules for YIELDING vs PASSING

        Args:
            peer: The peer state to evaluate
            current_time: Current timestamp for timeout checks

        Returns:
            Tuple of (coordination_state, speed_ratio)
        """
        # Calculate Euclidean distance to peer
        dist = math.sqrt(peer.x**2 + peer.y**2)

        # Emergency check - always triggered regardless of priority
        if dist < self.emergency_range:
            return CoordinationState.EMERGENCY, 0.0

        # Check for path conflict
        has_conflict = self._check_path_conflict(peer)

        # Update conflict hysteresis
        if has_conflict:
            self._conflict_ticks[peer.robot_id] = self._conflict_ticks.get(peer.robot_id, 0) + 1
        else:
            self._conflict_ticks[peer.robot_id] = 0

        # Apply hysteresis: only consider conflict if persistent for N ticks
        persistent_conflict = self._conflict_ticks.get(peer.robot_id, 0) >= CONFLICT_HYSTERESIS_TICKS

        # State determination based on distance thresholds
        if dist < self.yield_range and persistent_conflict:
            # Within yield range AND path conflict - need to negotiate
            my_priority = self._calculate_own_priority()
            peer_priority = peer.calculate_priority_score()

            if my_priority > peer_priority:
                # I have higher priority - I can pass
                return CoordinationState.PASSING, SPEED_SCALING[CoordinationState.PASSING]
            else:
                # Peer has higher priority - I must yield
                if peer.coordination_state != CoordinationState.YIELDING:
                    # Peer not yet yielding - send request
                    self._send_yield_request(peer.robot_id)
                return CoordinationState.YIELDING, SPEED_SCALING[CoordinationState.YIELDING]

        elif dist < self.caution_range:
            # Within caution range
            return CoordinationState.CAUTION, SPEED_SCALING[CoordinationState.CAUTION]

        elif dist < self.awareness_range:
            # Within awareness range
            return CoordinationState.AWARENESS, SPEED_SCALING[CoordinationState.AWARENESS]

        else:
            # Outside awareness range - normal operation
            return CoordinationState.NORMAL, SPEED_SCALING[CoordinationState.NORMAL]

    def _check_path_conflict(self, peer: PeerState) -> bool:
        """Check if paths intersect with peer.

        Per architecture spec §6.3:
        - Look ahead PATH_LOOKAHEAD meters
        - Paths conflict if any two points are within PATH_CONFLICT_THRESHOLD
        - Uses hysteresis to prevent flickering

        Args:
            peer: Peer to check path against

        Returns:
            True if paths conflict, False otherwise
        """
        if not self.own_planned_path or not peer.planned_path:
            return False

        for my_pt in self.own_planned_path:
            for peer_pt in peer.planned_path:
                dist = math.sqrt((my_pt[0] - peer_pt[0])**2 + (my_pt[1] - peer_pt[1])**2)
                if dist < self.path_conflict_dist:
                    return True

        return False

    def _find_conflict_point(self, peer: PeerState) -> tuple[float, float] | None:
        """Find the conflict point between own and peer paths.

        Returns the midpoint of the closest pair of conflicting points.

        Args:
            peer: Peer to find conflict with

        Returns:
            (x, y) tuple of conflict point, or None if no conflict
        """
        if not self.own_planned_path or not peer.planned_path:
            return None

        min_dist = float("inf")
        conflict_point = None

        for my_pt in self.own_planned_path:
            for peer_pt in peer.planned_path:
                dist = math.sqrt((my_pt[0] - peer_pt[0])**2 + (my_pt[1] - peer_pt[1])**2)
                if dist < self.path_conflict_dist and dist < min_dist:
                    min_dist = dist
                    conflict_point = ((my_pt[0] + peer_pt[0]) / 2.0, (my_pt[1] + peer_pt[1]) / 2.0)

        return conflict_point

    def _calculate_own_priority(self) -> float:
        """Calculate own priority score for comparison with peer.

        Uses same formula as peers but with own state.
        """
        score = self.own_yield_count * 10.0
        if self.own_dist_to_goal > 0:
            score += (1.0 / self.own_dist_to_goal) * 5.0
        score += (100 - self.own_battery_pct) * 0.1
        return score

    def _send_yield_request(self, peer_id: str):
        """Send yield request to peer with lower priority.

        Args:
            peer_id: Robot ID of peer to request yield from
        """
        if peer_id in self._pending_ack_from:
            return  # Already sent, waiting for ACK

        conflict_point = self._find_conflict_point(self.peers[peer_id])

        msg = YieldCommand()
        msg.from_robot = self.robot_id
        msg.to_robot = peer_id
        msg.command = CMD_REQUEST_YIELD
        if conflict_point:
            msg.conflict_x = conflict_point[0]
            msg.conflict_y = conflict_point[1]

        self.yield_pub.publish(msg)
        self._pending_ack_from.add(peer_id)
        self.get_logger().info(f"REQUEST_YIELD sent to {peer_id}")

    def _handle_yield_timeout(self, current_time: float):
        """Handle yield timeout - force resume after YIELD_TIMEOUT seconds.

        Per architecture spec §6.7:
        - If yielding for more than YIELD_TIMEOUT, force resume
        - Send RESUME to peers we requested yield from
        """
        if self.current_state != CoordinationState.YIELDING:
            self.own_yield_start_time = 0.0
            return

        if self.own_yield_start_time == 0:
            self.own_yield_start_time = current_time
            return

        if current_time - self.own_yield_start_time > self.yield_timeout:
            self.get_logger().warn(f"Yield timeout ({self.yield_timeout}s), forcing resume")
            self._publish_resume()
            self.current_state = CoordinationState.NORMAL
            self.own_yield_start_time = 0.0
            self.own_yield_count += 1  # Increment yield count for priority

    def _publish_resume(self):
        """Send RESUME command to all peers."""
        msg = YieldCommand()
        msg.from_robot = self.robot_id
        msg.command = CMD_RESUME

        # Send to all known peers
        for peer_id in list(self.peers.keys()):
            msg.to_robot = peer_id
            self.yield_pub.publish(msg)

        self._pending_ack_from.clear()
        self.get_logger().warn("RESUME sent to all peers")

    def _publish_speed_scaling(self, speed_ratio: float):
        """Publish speed scaling factor to chassis.

        In full integration, this interfaces with Nav2 or chassis controller.
        For now, publishes to /fleet/coordinator_speed for monitoring.

        Args:
            speed_ratio: Speed scaling factor (0.0 to 1.0)
        """
        msg = RobotPose()
        msg.robot_id = self.robot_id
        msg.x = speed_ratio  # Reuse x field for speed ratio
        msg.y = float(self.current_state)  # Reuse y for state
        msg.linear_vel = self.own_linear_vel * speed_ratio
        self.cmd_vel_pub.publish(msg)

    # -------------------------------------------------------------------------
    # Public API for Nav2 integration
    # -------------------------------------------------------------------------

    def get_current_state(self) -> CoordinationState:
        """Get current coordination state.

        Returns:
            Current CoordinationState enum value
        """
        return self.current_state

    def get_speed_scaling(self) -> float:
        """Get current speed scaling factor.

        Returns:
            Speed scaling factor (0.0 to 1.0)
        """
        return SPEED_SCALING.get(self.current_state, 1.0)

    def update_own_state(self, x: float, y: float, theta: float,
                         linear_vel: float, dist_to_goal: float,
                         battery_pct: float, planned_path: list[tuple[float, float]]):
        """Update own robot state from Nav2/SLAM.

        Call this from Nav2 integration to update local state.

        Args:
            x, y, theta: Pose in map frame
            linear_vel: Current linear velocity (m/s)
            dist_to_goal: Distance to current goal (m)
            battery_pct: Battery percentage (0-100)
            planned_path: List of (x, y) tuples representing planned path
        """
        self.own_x = x
        self.own_y = y
        self.own_theta = theta
        self.own_linear_vel = linear_vel
        self.own_dist_to_goal = dist_to_goal
        self.own_battery_pct = battery_pct
        self.own_planned_path = planned_path[:10]  # Limit to 10 points


def main(args=None):
    rclpy.init(args=args)
    node = FleetCoordinator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
