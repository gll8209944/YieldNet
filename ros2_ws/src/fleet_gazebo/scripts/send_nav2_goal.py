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
from nav2_simple_commander.robot_navigator import BasicNavigator


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('namespace', help='e.g. robot_a')
    ap.add_argument('x', type=float)
    ap.add_argument('y', type=float)
    ap.add_argument('yaw', type=float, nargs='?', default=0.0)
    args = ap.parse_args()

    rclpy.init()
    nav = BasicNavigator(namespace=args.namespace)

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

    # NOTE: waitUntilNav2Active() can block indefinitely when Nav2 is running but
    # BT navigator state is not "active" (e.g. no initial pose, no odom TF).
    # For smoke tests we skip it and send the goal directly - failures are
    # expected and logged.
    nav.get_logger().info('Sending NavigateToPose goal directly (skipping waitUntilNav2Active)')
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
