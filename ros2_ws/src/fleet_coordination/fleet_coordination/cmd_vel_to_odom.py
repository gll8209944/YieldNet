#!/usr/bin/env python3
"""
CmdVelToOdom - Converts cmd_vel commands to odometry

This node subscribes to cmd_vel and publishes odometry messages.
It simulates the turtlebot3's native odometry based on wheel commands.

This is a workaround for when Gazebo's diff_drive plugin doesn't properly
publish odometry with namespaced robot models.
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, TransformStamped
import math


def _quaternion_from_yaw(yaw: float):
    """Compute quaternion (x,y,z,w) from yaw angle. Pure math, no tf_transformations."""
    sy = math.sin(yaw * 0.5)
    cy = math.cos(yaw * 0.5)
    return (sy, 0.0, 0.0, cy)  # (qx, qy, qz, qw)


class CmdVelToOdom(Node):
    def __init__(self, robot_id: str):
        super().__init__(f'cmd_vel_to_odom_{robot_id}')
        self.robot_id = robot_id
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_time = self.get_clock().now()

        # Get namespace
        ns = f'/{robot_id}'

        # Subscribe to cmd_vel
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            f'{ns}/cmd_vel',
            self.cmd_vel_callback,
            10
        )

        # Publish odometry
        self.odom_pub = self.create_publisher(Odometry, f'{ns}/odom', 10)

        # Publish tf odom -> base_footprint
        self.tf_broadcaster = self.create_publisher(TransformStamped, f'{ns}/tf_footprint', 10)

        self.get_logger().info(f'CmdVelToOdom started for {robot_id}')

    def cmd_vel_callback(self, msg: Twist):
        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        self.last_time = current_time

        # Avoid division by zero
        if dt < 0.001:
            dt = 0.1

        # Update pose based on velocity
        vx = msg.linear.x
        vy = msg.linear.y
        omega = msg.angular.z

        # Update position
        self.x += vx * dt * math.cos(self.theta) - vy * dt * math.sin(self.theta)
        self.y += vx * dt * math.sin(self.theta) + vy * dt * math.cos(self.theta)
        self.theta += omega * dt

        # Normalize theta to [-pi, pi]
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))

        # Publish odometry message
        odom = Odometry()
        odom.header.stamp = current_time.to_msg()
        odom.header.frame_id = f'{self.robot_id}/odom'
        odom.child_frame_id = f'{self.robot_id}/base_footprint'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0

        qx, qy, qz, qw = _quaternion_from_yaw(self.theta)
        odom.pose.pose.orientation.x = qx
        odom.pose.pose.orientation.y = qy
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw

        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = vy
        odom.twist.twist.angular.z = omega

        self.odom_pub.publish(odom)

        # Publish tf
        tf = TransformStamped()
        tf.header.stamp = current_time.to_msg()
        tf.header.frame_id = f'{self.robot_id}/odom'
        tf.child_frame_id = f'{self.robot_id}/base_footprint'
        tf.transform.translation.x = self.x
        tf.transform.translation.y = self.y
        tf.transform.translation.z = 0.0
        tf.transform.rotation.x = qx
        tf.transform.rotation.y = qy
        tf.transform.rotation.z = qz
        tf.transform.rotation.w = qw

        self.tf_broadcaster.publish(tf)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: cmd_vel_to_odom.py <robot_id>")
        sys.exit(1)

    robot_id = sys.argv[1]
    rclpy.init()
    node = CmdVelToOdom(robot_id)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
