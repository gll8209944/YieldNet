#!/usr/bin/env python3
"""Navigation Test Script for 3-Robot Fleet Coordination.

This script sends navigation goals to make 3 robots move toward the center
to test the yield/passing negotiation.

Scenario: Triple-Meet
- robot_a: from (-4, 0) toward (0, 0)
- robot_b: from (4, 0) toward (0, 0)
- robot_c: from (0, 4) toward (0, 0)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math

from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry


class NavTestNode(Node):
    """Sends navigation goals to make robots move toward center."""

    def __init__(self):
        super().__init__('nav_test_3robots')
        self.declare_parameter('target_x', 0.0)
        self.declare_parameter('target_y', 0.0)

        self.target_x = self.get_parameter('target_x').value
        self.target_y = self.get_parameter('target_y').value

        # Subscribe to odometry to track robot positions
        qos_odom = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.robots = {}
        for robot_id in ['robot_a', 'robot_b', 'robot_c']:
            self.create_subscription(
                Odometry,
                f'/{robot_id}/odom',
                lambda msg, rid=robot_id: self._odom_callback(msg, rid),
                qos_odom
            )
            # Publisher for NavigateToPose goal
            self.create_publisher(
                PoseStamped,
                f'/{robot_id}/goal_pose',
                QoSProfile(depth=1)
            )

        # Timer to check and send goals
        self.goal_sent = {rid: False for rid in ['robot_a', 'robot_b', 'robot_c']}
        self.create_timer(1.0, self._check_and_send_goals)

        self.get_logger().info('NavTestNode started - will send goals to move robots to center (0,0)')

    def _odom_callback(self, msg: Odometry, robot_id: str):
        """Store odometry data for robot."""
        self.robots[robot_id] = {
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y
        }

    def _create_pose(self, x: float, y: float) -> PoseStamped:
        """Create a PoseStamped message for navigation goal."""
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0

        # Face toward the target direction based on quadrant
        # For simplicity, face toward center (0, 0)
        if x > 0:
            # Coming from right, face left
            pose.pose.orientation.z = -0.707
            pose.pose.orientation.w = 0.707
        else:
            # Coming from left, face right
            pose.pose.orientation.z = 0.707
            pose.pose.orientation.w = 0.707
        return pose

    def _check_and_send_goals(self):
        """Check positions and send goals if robots haven't moved."""
        if not self.robots:
            return

        # Goals for each robot to move toward center
        goals = {
            'robot_a': (-2.5, 0.0),   # Move right toward center
            'robot_b': (2.5, 0.0),    # Move left toward center
            'robot_c': (0.0, 2.5),    # Move down toward center
        }

        for robot_id, (goal_x, goal_y) in goals.items():
            if robot_id not in self.robots:
                continue

            pos = self.robots[robot_id]

            # Check if robot has reached goal (within 0.5m)
            dist_to_goal = math.sqrt((pos['x'] - goal_x)**2 + (pos['y'] - goal_y)**2)

            if dist_to_goal > 0.5 and not self.goal_sent[robot_id]:
                pose = self._create_pose(goal_x, goal_y)
                pose.header.stamp = self.get_clock().now().to_msg()

                self.get_logger().info(
                    f'Sending goal to {robot_id}: ({goal_x:.2f}, {goal_y:.2f}) '
                    f'(current: {pos["x"]:.2f}, {pos["y"]:.2f}, dist: {dist_to_goal:.2f})'
                )

                # Publish to goal_pose topic (Nav2 standard topic)
                # Note: Some Nav2 configurations use /goal_pose, others use /navigate_to_pose
                goal_pub = self.create_publisher(
                    PoseStamped,
                    f'/{robot_id}/goal_pose',
                    QoSProfile(depth=1)
                )
                goal_pub.publish(pose)
                self.goal_sent[robot_id] = True
            elif dist_to_goal <= 0.5:
                if self.goal_sent.get(robot_id, False):
                    self.get_logger().info(f'{robot_id} reached goal!')


def main():
    rclpy.init(args=None)
    node = NavTestNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
