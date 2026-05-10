#!/usr/bin/env python3
"""Send one NavigateToPose goal using nav2_simple_commander (blocking).

Usage:
  python3 send_nav2_goal.py <namespace_no_slash> <x> <y> [yaw_rad]
"""

import argparse
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator
from rclpy.node import Node


class AmclPoseWaiter(Node):
    def __init__(self, namespace: str, topic: str):
        super().__init__(f'amcl_pose_waiter_{namespace}')
        self.received = False
        self.topic = topic
        self.create_subscription(
            PoseWithCovarianceStamped,
            topic,
            self._callback,
            10,
        )

    def _callback(self, _msg: PoseWithCovarianceStamped) -> None:
        self.received = True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('namespace', help='e.g. robot_a')
    ap.add_argument('x', type=float)
    ap.add_argument('y', type=float)
    ap.add_argument('yaw', type=float, nargs='?', default=0.0)
    ap.add_argument('--amcl-timeout', type=float, default=20.0)
    args = ap.parse_args()

    rclpy.init()
    nav = BasicNavigator(namespace=args.namespace)
    amcl_topic = f'/{args.namespace}/amcl_pose'
    waiter = AmclPoseWaiter(args.namespace, amcl_topic)

    nav.get_logger().info(
        f'Waiting up to {args.amcl_timeout:.1f}s for AMCL pose on {amcl_topic}')
    wait_deadline = time.time() + args.amcl_timeout
    while rclpy.ok() and time.time() < wait_deadline and not waiter.received:
        rclpy.spin_once(waiter, timeout_sec=0.2)
    if not waiter.received:
        print(
            f'Timeout waiting for {amcl_topic}; check AMCL namespace and odom TF',
            file=sys.stderr,
        )
        waiter.destroy_node()
        nav.destroy_node()
        rclpy.shutdown()
        sys.exit(2)
    waiter.destroy_node()

    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = nav.get_clock().now().to_msg()
    pose.pose.position.x = args.x
    pose.pose.position.y = args.y
    pose.pose.position.z = 0.0
    cy = math.cos(args.yaw * 0.5)
    sy = math.sin(args.yaw * 0.5)
    pose.pose.orientation.z = sy
    pose.pose.orientation.w = cy

    nav.get_logger().info(
        f'Received AMCL pose on {amcl_topic}; sending NavigateToPose goal directly')
    nav.goToPose(pose)
    start = time.time()
    while not nav.isTaskComplete():
        feedback = nav.getFeedback()
        if feedback:
            nav.get_logger().debug(str(feedback))
        time.sleep(0.05)
        if time.time() - start > 120.0:
            print('Timeout waiting for navigation', file=sys.stderr)
            nav.cancelNav()
            sys.exit(3)

    rclpy.shutdown()


if __name__ == '__main__':
    main()
