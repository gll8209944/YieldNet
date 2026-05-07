#!/usr/bin/env python3
"""
FleetSpeedController - Standalone node that modulates cmd_vel based on fleet coordination state

This node subscribes to:
- /{robot_id}/cmd_vel (original velocity commands)
- /{robot_id}/fleet/coordinator_status (fleet coordination state)

And publishes:
- /{robot_id}/cmd_vel (modified velocity commands)

Speed modulation based on coordination state:
- NORMAL: 100%
- AWARENESS: 100%
- CAUTION: 50%
- YIELDING: 0%
- PASSING: 30%
- EMERGENCY: 0%
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import json


class FleetSpeedController(Node):
    """Modulates robot speed based on fleet coordination state."""

    def __init__(self, robot_id: str):
        super().__init__(f'fleet_speed_controller_{robot_id}')
        self.robot_id = robot_id
        self.current_speed_ratio = 1.0
        self.current_state = "NORMAL"

        ns = f'/{robot_id}'

        # Original cmd_vel subscriber
        self.cmd_vel_orig_sub = self.create_subscription(
            Twist,
            f'{ns}/cmd_vel_orig',
            self.cmd_vel_callback,
            10
        )

        # Fleet status subscriber
        self.fleet_status_sub = self.create_subscription(
            String,
            f'{ns}/fleet/coordinator_status',
            self.fleet_status_callback,
            10
        )

        # Modified cmd_vel publisher
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            f'{ns}/cmd_vel',
            10
        )

        # Speed mapping based on coordination state
        self.speed_mapping = {
            "NORMAL": 1.0,
            "AWARENESS": 1.0,
            "CAUTION": 0.5,
            "YIELDING": 0.0,
            "PASSING": 0.3,
            "EMERGENCY": 0.0,
        }

        self.get_logger().info(f'FleetSpeedController started for {robot_id}')

    def cmd_vel_callback(self, msg: Twist):
        """Modify cmd_vel based on fleet state."""
        modified = Twist()
        modified.linear.x = msg.linear.x * self.current_speed_ratio
        modified.linear.y = msg.linear.y * self.current_speed_ratio
        modified.linear.z = msg.linear.z * self.current_speed_ratio
        modified.angular.x = msg.angular.x * self.current_speed_ratio
        modified.angular.y = msg.angular.y * self.current_speed_ratio
        modified.angular.z = msg.angular.z * self.current_speed_ratio

        self.cmd_vel_pub.publish(modified)

        # Log state changes
        if self.current_speed_ratio < 1.0:
            self.get_logger().info(
                f'Speed modified: state={self.current_state}, '
                f'ratio={self.current_speed_ratio:.2f}, '
                f'input={msg.linear.x:.2f}, output={modified.linear.x:.2f}'
            )

    def fleet_status_callback(self, msg: String):
        """Update speed ratio based on fleet coordination state."""
        try:
            data = json.loads(msg.data)
            state = data.get('state', 'NORMAL')
            speed_ratio = data.get('speed_ratio', 1.0)

            if state != self.current_state:
                self.get_logger().info(f'State change: {self.current_state} -> {state}')
                self.current_state = state

            self.current_speed_ratio = speed_ratio

        except json.JSONDecodeError:
            self.get_logger().warn(f'Failed to parse fleet status: {msg.data}')


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: fleet_speed_controller.py <robot_id>")
        sys.exit(1)

    robot_id = sys.argv[1]
    rclpy.init()
    node = FleetSpeedController(robot_id)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
