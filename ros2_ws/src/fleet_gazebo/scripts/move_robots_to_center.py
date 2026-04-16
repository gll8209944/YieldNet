#!/usr/bin/env python3
"""Simple Robot Mover - Moves robots toward center using cmd_vel.

This script directly publishes cmd_vel commands to move robots toward the center
to test the fleet coordination system. It simulates what Nav2 would do but
without requiring SLAM/map server.

Usage:
    python3 move_robots_to_center.py

Robot positions and targets:
- robot_a: from (-4, 0) toward center (0, 0)  - move right (+x)
- robot_b: from (4, 0) toward center (0, 0)   - move left (-x)
- robot_c: from (0, 4) toward center (0, 0)   - move down (-y)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from fleet_msgs.msg import RobotPose


class RobotMover(Node):
    """Moves robots toward center by publishing cmd_vel, respecting fleet coordinator speed."""

    def __init__(self):
        super().__init__('robot_mover')

        # Robot targets (where they should go)
        self.targets = {
            'robot_a': (0.0, 0.0),   # Center
            'robot_b': (0.0, 0.0),   # Center
            'robot_c': (0.0, 0.0),   # Center
        }

        # Movement parameters
        self.linear_speed = 0.2  # m/s
        self.angular_speed = 0.5  # rad/s
        self.arrival_threshold = 0.3  # m

        # Track robot positions
        self.positions = {}
        self.cmd_vel_publishers = {}

        # Track fleet coordinator speed scaling (per robot)
        # CoordinationState: NORMAL=0, AWARENESS=1, CAUTION=2, YIELDING=3, PASSING=4, EMERGENCY=5
        self.speed_scaling = {
            'robot_a': 1.0,
            'robot_b': 1.0,
            'robot_c': 1.0,
        }

        qos_odom = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        qos_cmd = QoSProfile(depth=10)

        # Use RELIABLE QoS to match fleet coordinator publisher
        qos_speed = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        for robot_id in ['robot_a', 'robot_b', 'robot_c']:
            # Subscribe to odometry
            self.create_subscription(
                Odometry,
                f'/{robot_id}/odom',
                lambda msg, rid=robot_id: self._odom_callback(msg, rid),
                qos_odom
            )
            # Subscribe to fleet coordinator speed
            # Topic is /robot_a/fleet/coordinator_speed (coordinator runs in /robot_a namespace)
            self.create_subscription(
                RobotPose,
                f'/{robot_id}/fleet/coordinator_speed',
                lambda msg, rid=robot_id: self._speed_callback(msg, rid),
                qos_speed
            )
            # Publisher for cmd_vel
            self.cmd_vel_publishers[robot_id] = self.create_publisher(
                Twist,
                f'/{robot_id}/cmd_vel',
                qos_cmd
            )
            self.get_logger().info(f'Subscribed to /{robot_id}/fleet/coordinator_speed')

        # Movement state
        self.arrived = {rid: False for rid in ['robot_a', 'robot_b', 'robot_c']}

        # Timer for control loop (10 Hz)
        self.create_timer(0.1, self._control_loop)

        self.get_logger().info(
            'RobotMover started - moving robots toward center\n'
            '  robot_a: (-4, 0) -> (0, 0)\n'
            '  robot_b: ( 4, 0) -> (0, 0)\n'
            '  robot_c: ( 0, 4) -> (0, 0)\n'
            'Will respect fleet coordinator speed scaling!'
        )

    def _speed_callback(self, msg, robot_id: str):
        """Receive fleet coordinator speed scaling for this robot."""
        # msg.x contains the speed_ratio (0.0 to 1.0)
        # msg.y contains the CoordinationState enum value
        old_ratio = self.speed_scaling.get(robot_id, 1.0)
        self.speed_scaling[robot_id] = msg.x
        state_name = ['NORMAL', 'AWARENESS', 'CAUTION', 'YIELDING', 'PASSING', 'EMERGENCY'][int(msg.y)]
        if old_ratio != msg.x or msg.x < 1.0:
            self.get_logger().info(f'{robot_id} speed: {old_ratio:.2f} -> {msg.x:.2f} (state={state_name})')

    def _odom_callback(self, msg: Odometry, robot_id: str):
        """Store odometry data."""
        self.positions[robot_id] = {
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y,
            'theta': self._quat_to_yaw(msg.pose.pose.orientation)
        }

    def _quat_to_yaw(self, quat) -> float:
        """Convert quaternion to yaw angle."""
        return math.atan2(
            2.0 * (quat.w * quat.z + quat.x * quat.y),
            1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z)
        )

    def _control_loop(self):
        """Control loop to move robots toward targets, respecting fleet coordinator speed."""
        for robot_id, target in self.targets.items():
            if robot_id not in self.positions:
                continue

            # Get speed scaling from fleet coordinator
            speed_ratio = self.speed_scaling[robot_id]

            # If speed ratio is 0 (EMERGENCY, YIELDING, etc.), stop
            if speed_ratio < 0.01:
                cmd = Twist()
                self.cmd_vel_publishers[robot_id].publish(cmd)
                if not hasattr(self, '_last_stop_log') or self._last_stop_log.get(robot_id, 0) != speed_ratio:
                    self.get_logger().info(f'{robot_id} STOPPED by fleet coordinator (speed_ratio={speed_ratio:.2f})')
                    self._last_stop_log = getattr(self, '_last_stop_log', {})
                    self._last_stop_log[robot_id] = speed_ratio
                continue

            if self.arrived[robot_id]:
                # Already arrived, send zero velocity
                cmd = Twist()
                self.cmd_vel_publishers[robot_id].publish(cmd)
                continue

            pos = self.positions[robot_id]
            dx = target[0] - pos['x']
            dy = target[1] - pos['y']
            dist = math.sqrt(dx*dx + dy*dy)

            # Check if arrived
            if dist < self.arrival_threshold:
                self.get_logger().info(f'{robot_id} ARRIVED at center!')
                self.arrived[robot_id] = True
                cmd = Twist()
                self.cmd_vel_publishers[robot_id].publish(cmd)
                continue

            # Calculate desired heading
            desired_theta = math.atan2(dy, dx)

            # Calculate angle error
            angle_error = desired_theta - pos['theta']

            # Normalize angle error to [-pi, pi]
            while angle_error > math.pi:
                angle_error -= 2 * math.pi
            while angle_error < -math.pi:
                angle_error += 2 * math.pi

            cmd = Twist()

            # Apply fleet coordinator speed scaling
            effective_linear = self.linear_speed * speed_ratio
            effective_angular = self.angular_speed * min(speed_ratio, 1.0)

            # If angle error is large, turn in place
            if abs(angle_error) > 0.1:
                cmd.angular.z = effective_angular if angle_error > 0 else -effective_angular
                cmd.linear.x = 0.0
            else:
                # Move forward with speed scaling
                cmd.linear.x = effective_linear
                cmd.angular.z = 0.0

            self.cmd_vel_publishers[robot_id].publish(cmd)

            # Log every 5 seconds
            if not hasattr(self, '_last_log_time'):
                self._last_log_time = {}
            last_time = self._last_log_time.get(robot_id, 0)
            current_time = self.get_clock().now().nanoseconds / 1e9
            if current_time - last_time > 5.0:
                self._last_log_time[robot_id] = current_time
                self.get_logger().info(
                    f'{robot_id}: pos=({pos["x"]:.2f}, {pos["y"]:.2f}), '
                    f'dist={dist:.2f}, speed_ratio={speed_ratio:.2f}'
                )

        # Log arrival status
        arrived_count = sum(1 for a in self.arrived.values() if a)
        if arrived_count > 0 and arrived_count < 3:
            self.get_logger().info(
                f'Arrival status: robot_a={"✓" if self.arrived["robot_a"] else "✗"}, '
                f'robot_b={"✓" if self.arrived["robot_b"] else "✗"}, '
                f'robot_c={"✓" if self.arrived["robot_c"] else "✗"}'
            )


def main():
    rclpy.init(args=None)
    node = RobotMover()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Stop all robots before shutdown
        for robot_id in ['robot_a', 'robot_b', 'robot_c']:
            cmd = Twist()
            node.cmd_vel_publishers[robot_id].publish(cmd)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
