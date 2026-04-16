#!/usr/bin/env python3
"""Mock Path Publisher for Multi-Robot Fleet Testing.

Publishes simulated PlannedPath messages for all robots based on their
current odometry position and heading. This allows testing path conflict
detection without requiring a full Nav2 path planner.

Usage:
    python3 mock_path_publisher_all.py robot_a robot_b robot_c

Each robot's path is published on its own namespace topic.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math
import time

from nav_msgs.msg import Odometry
from fleet_msgs.msg import PlannedPath
from geometry_msgs.msg import Point


class MockPathPublisher(Node):
    """Publishes simulated planned paths for multiple robots."""

    def __init__(self, robot_ids: list[str]):
        super().__init__('mock_path_publisher')
        self.robot_ids = robot_ids
        self.path_length = 5.0  # meters
        self.path_point_spacing = 0.5  # meters between points
        self.num_points = int(self.path_length / self.path_point_spacing)

        # Store latest odometry for each robot
        self.odom_data: dict[str, dict] = {}

        # Store path publishers for each robot
        self.path_pubs: dict[str, any] = {}

        # QoS for path publishing - BEST_EFFORT to match fleet coordinator
        qos_be = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribe to odometry for each robot
        for robot_id in robot_ids:
            self.create_subscription(
                Odometry,
                f'/{robot_id}/odom',
                lambda msg, rid=robot_id: self._odom_callback(msg, rid),
                qos_be
            )

            # Publisher for this robot's path - publish to shared fleet topic
            # All robots publish to the same /fleet/planned_path topic
            self.path_pubs[robot_id] = self.create_publisher(
                PlannedPath,
                '/fleet/planned_path',
                qos_be
            )

        # Timer to publish paths at 2 Hz (as per PRD FR-003)
        self.publish_timer = self.create_timer(0.5, self._publish_paths)

        self.get_logger().info(f'MockPathPublisher started for: {robot_ids}')

    def _odom_callback(self, msg: Odometry, robot_id: str):
        """Store latest odometry data for robot."""
        self.odom_data[robot_id] = {
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y,
            'theta': self._quat_to_yaw(msg.pose.pose.orientation),
            'vel': msg.twist.twist.linear.x
        }
        self.get_logger().info(f'Odom received for {robot_id}: x={msg.pose.pose.position.x:.2f}, y={msg.pose.pose.position.y:.2f}')

    def _quat_to_yaw(self, quat) -> float:
        """Convert quaternion to yaw angle."""
        return math.atan2(
            2.0 * (quat.w * quat.z + quat.x * quat.y),
            1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z)
        )

    def _generate_path_points(self, x: float, y: float, theta: float) -> list[tuple[float, float]]:
        """Generate path points in front of the robot based on heading.

        Args:
            x, y: Current position
            theta: Current heading (radians)

        Returns:
            List of (x, y) tuples representing path points
        """
        points = []
        for i in range(1, self.num_points + 1):
            dist = i * self.path_point_spacing
            px = x + dist * math.cos(theta)
            py = y + dist * math.sin(theta)
            points.append((px, py))
        return points

    def _publish_paths(self):
        """Publish simulated paths for all robots at 2 Hz."""
        current_time = self.get_clock().now().to_msg()

        for robot_id in self.robot_ids:
            if robot_id not in self.odom_data:
                self.get_logger().warn(f'No odom data for {robot_id}, skipping path publish')
                continue

            odom = self.odom_data[robot_id]

            # Generate path points based on current heading
            path_points = self._generate_path_points(
                odom['x'], odom['y'], odom['theta']
            )

            # Create and publish path message
            path_msg = PlannedPath()
            path_msg.robot_id = robot_id
            path_msg.estimated_speed = odom['vel']
            path_msg.stamp = current_time

            for px, py in path_points:
                point = Point()
                point.x = px
                point.y = py
                point.z = 0.0
                path_msg.waypoints.append(point)

            # Publish to the robot's namespaced fleet topic
            self.path_pubs[robot_id].publish(path_msg)
            self.get_logger().info(
                f'Publishing path for {robot_id}: '
                f'origin=({odom["x"]:.2f}, {odom["y"]:.2f}), '
                f'heading={odom["theta"]:.2f}, points={len(path_points)}')


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: mock_path_publisher_all.py robot_a [robot_b] [robot_c] ...")
        sys.exit(1)

    robot_ids = sys.argv[1:]

    rclpy.init(args=None)
    node = MockPathPublisher(robot_ids)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()