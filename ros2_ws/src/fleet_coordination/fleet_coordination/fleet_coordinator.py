#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math
import time
from fleet_msgs.msg import RobotHeartbeat, RobotPose, PlannedPath, YieldCommand
from fleet_coordination.peer_state import PeerState, CoordinationState

CMD_REQUEST_YIELD = 0
CMD_ACK_YIELD = 1
CMD_RESUME = 2
CMD_EMERGENCY_STOP = 3

class FleetCoordinator(Node):
    def __init__(self):
        super().__init__("fleet_coordinator")
        self.declare_parameter("robot_id", "robot_a")
        self.declare_parameter("peer_ids", ["robot_b", "robot_c"])
        self.declare_parameter("emergency_range", 0.8)
        self.declare_parameter("yield_range", 2.5)
        self.declare_parameter("caution_range", 4.0)
        self.declare_parameter("awareness_range", 8.0)
        self.declare_parameter("yield_timeout", 15.0)
        self.declare_parameter("heartbeat_timeout", 6.0)

        self.robot_id = self.get_parameter("robot_id").value
        self.emergency_range = self.get_parameter("emergency_range").value
        self.yield_range = self.get_parameter("yield_range").value
        self.caution_range = self.get_parameter("caution_range").value
        self.awareness_range = self.get_parameter("awareness_range").value
        self.yield_timeout = self.get_parameter("yield_timeout").value
        self.heartbeat_timeout = self.get_parameter("heartbeat_timeout").value

        self.peers = {}
        self.current_state = CoordinationState.NORMAL
        self.own_yield_start_time = 0.0

        qos = QoSProfile(depth=10)
        self.heartbeat_pub = self.create_publisher(RobotHeartbeat, "/fleet/heartbeat", qos)
        self.pose_pub = self.create_publisher(RobotPose, "/fleet/pose", qos)
        self.path_pub = self.create_publisher(PlannedPath, "/fleet/planned_path", qos)
        self.yield_pub = self.create_publisher(YieldCommand, "/fleet/yield", qos)

        qos_sub = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=1)
        self.create_subscription(RobotHeartbeat, "/fleet/heartbeat", self.heartbeat_callback, qos_sub)
        self.create_subscription(RobotPose, "/fleet/pose", self.pose_callback, qos_sub)
        self.create_subscription(PlannedPath, "/fleet/planned_path", self.path_callback, qos_sub)
        self.create_subscription(YieldCommand, "/fleet/yield", self.yield_callback, qos_sub)

        self.timer = self.create_timer(0.1, self.coordination_tick)
        self.get_logger().info(f"Fleet Coordinator started: {self.robot_id}")

    def heartbeat_callback(self, msg):
        if msg.robot_id == self.robot_id:
            return
        if msg.robot_id not in self.peers:
            self.peers[msg.robot_id] = PeerState(msg.robot_id)
        peer = self.peers[msg.robot_id]
        peer.battery_pct = msg.battery_pct
        peer.yield_count = msg.yield_count
        peer.dist_to_goal = msg.dist_to_goal
        peer.last_seen = time.time()

    def pose_callback(self, msg):
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
        peer.last_seen = time.time()

    def path_callback(self, msg):
        if msg.robot_id == self.robot_id:
            return
        if msg.robot_id not in self.peers:
            self.peers[msg.robot_id] = PeerState(msg.robot_id)
        peer = self.peers[msg.robot_id]
        peer.planned_path = [(p.x, p.y) for p in msg.waypoints[:10]]

    def yield_callback(self, msg):
        if msg.to_robot != self.robot_id:
            return
        if msg.command == CMD_ACK_YIELD:
            self.get_logger().info(f"ACK_YIELD from {msg.from_robot}")
            self.current_state = CoordinationState.PASSING
        elif msg.command == CMD_RESUME:
            self.get_logger().info(f"RESUME from {msg.from_robot}")
            self.current_state = CoordinationState.NORMAL

    def coordination_tick(self):
        current_time = time.time()
        timed_out = [pid for pid, p in self.peers.items() if current_time - p.last_seen > self.heartbeat_timeout]
        for pid in timed_out:
            del self.peers[pid]
            self.get_logger().warn(f"Peer {pid} timed out")

        worst_state = CoordinationState.NORMAL
        for pid, peer in self.peers.items():
            dist = math.sqrt(peer.x**2 + peer.y**2)
            if dist < self.emergency_range:
                peer.coordination_state = CoordinationState.EMERGENCY
            elif dist < self.yield_range:
                peer.coordination_state = CoordinationState.YIELDING
            elif dist < self.caution_range:
                peer.coordination_state = CoordinationState.CAUTION
            elif dist < self.awareness_range:
                peer.coordination_state = CoordinationState.AWARENESS
            else:
                peer.coordination_state = CoordinationState.NORMAL
            worst_state = max(worst_state, peer.coordination_state)

        self.current_state = worst_state

        if self.current_state == CoordinationState.YIELDING:
            if self.own_yield_start_time == 0:
                self.own_yield_start_time = current_time
            elif current_time - self.own_yield_start_time > self.yield_timeout:
                self._publish_resume()
                self.current_state = CoordinationState.NORMAL
                self.own_yield_start_time = 0
        else:
            self.own_yield_start_time = 0

    def _publish_resume(self):
        msg = YieldCommand()
        msg.from_robot = self.robot_id
        msg.command = CMD_RESUME
        self.yield_pub.publish(msg)
        self.get_logger().warn("Yield timeout, forcing RESUME")

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
