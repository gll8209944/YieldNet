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
from rclpy.parameter import Parameter
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TransformStamped
import tf2_ros
import math


def _quaternion_from_yaw(yaw: float):
    """Compute quaternion (x,y,z,w) from yaw angle. Pure math, no tf_transformations."""
    sy = math.sin(yaw * 0.5)
    cy = math.cos(yaw * 0.5)
    return (0.0, 0.0, sy, cy)  # (qx, qy, qz, qw)


class CmdVelToOdom(Node):
    def __init__(self, robot_id: str):
        super().__init__(f'cmd_vel_to_odom_{robot_id}')
        # This Gazebo smoke workaround must follow simulation time so TF/odom
        # timestamps line up with Nav2, AMCL and LaserScan messages.
        self.set_parameters([Parameter('use_sim_time', value=True)])
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

        # Publish tf robot_id/odom -> robot_id/base_footprint to /tf using tf2_ros
        # TransformBroadcaster. This must match the namespaced frame IDs from
        # robot_state_publisher (URDF chain: robot_a/odom -> robot_a/base_footprint
        # -> robot_a/base_link). Without matching namespaced frame IDs, tf2 cannot
        # find the transform chain and local_costmap reports "frame odom does not exist".
        self._tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # Publish TF at 10Hz so Nav2 can find odom frame before any goal is accepted.
        self._tf_timer = self.create_timer(0.1, self._publish_tf)
        self._tf_count = 0

        self.get_logger().info(f'CmdVelToOdom started for {robot_id}')

    def _publish_tf(self):
        """Publish robot_id/odom->robot_id/base_footprint TF to /tf at 10Hz."""
        current_time = self.get_clock().now()
        qx, qy, qz, qw = _quaternion_from_yaw(self.theta)

        # Use namespaced frame IDs to match robot_state_publisher URDF chain.
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

        self._tf_broadcaster.sendTransform(tf)

        self._tf_count += 1
        if self._tf_count % 50 == 0:
            self.get_logger().info(f'TF {self.robot_id}/odom->base_footprint count={self._tf_count}')

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


def main():
    import sys
    from rclpy.executors import SingleThreadedExecutor

    if len(sys.argv) < 2:
        print("Usage: cmd_vel_to_odom.py <robot_id>")
        sys.exit(1)

    robot_id = sys.argv[1]
    rclpy.init()
    node = CmdVelToOdom(robot_id)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
