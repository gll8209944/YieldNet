#!/usr/bin/env python3
"""Probe Nav2 ComputePathToPose for one robot namespace and multiple goals."""

import argparse
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator
from rclpy.node import Node
from rclpy.parameter import Parameter


def pose_stamped(node: Node, x: float, y: float, yaw: float) -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = node.get_clock().now().to_msg()
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.position.z = 0.0
    pose.pose.orientation.z = math.sin(yaw * 0.5)
    pose.pose.orientation.w = math.cos(yaw * 0.5)
    return pose


class AmclWaiter(Node):
    def __init__(self, namespace: str):
        super().__init__(f'compute_path_amcl_waiter_{namespace}')
        self.set_parameters([Parameter('use_sim_time', value=True)])
        self.received = False
        self.initial_pose_topic = f'/{namespace}/initialpose'
        self.create_subscription(
            PoseWithCovarianceStamped,
            f'/{namespace}/amcl_pose',
            self._callback,
            10,
        )
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped,
            self.initial_pose_topic,
            10,
        )

    def _callback(self, _msg: PoseWithCovarianceStamped) -> None:
        self.received = True

    def publish_initial_pose(self, x: float, y: float, yaw: float) -> None:
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw * 0.5)
        msg.pose.pose.orientation.w = math.cos(yaw * 0.5)
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.0685
        self.initial_pose_pub.publish(msg)


def parse_goal(value: str):
    parts = value.split(':')
    if len(parts) != 4:
        raise argparse.ArgumentTypeError('goal must be label:x:y:yaw')
    label, x, y, yaw = parts
    return label, float(x), float(y), float(yaw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('namespace')
    parser.add_argument('--start-x', type=float, required=True)
    parser.add_argument('--start-y', type=float, required=True)
    parser.add_argument('--start-yaw', type=float, default=0.0)
    parser.add_argument('--goal', action='append', type=parse_goal, required=True)
    parser.add_argument('--amcl-timeout', type=float, default=30.0)
    args = parser.parse_args()

    rclpy.init()
    nav = BasicNavigator(namespace=args.namespace)
    nav.set_parameters([Parameter('use_sim_time', value=True)])
    waiter = AmclWaiter(args.namespace)

    print(f'PROBE namespace={args.namespace} waiting_for_amcl timeout={args.amcl_timeout:.1f}', flush=True)
    deadline = time.time() + args.amcl_timeout
    next_initial = 0.0
    while rclpy.ok() and time.time() < deadline and not waiter.received:
        if time.time() >= next_initial:
            waiter.publish_initial_pose(args.start_x, args.start_y, args.start_yaw)
            print(
                f'PROBE namespace={args.namespace} initialpose '
                f'x={args.start_x:.2f} y={args.start_y:.2f} yaw={args.start_yaw:.2f}',
                flush=True,
            )
            next_initial = time.time() + 1.0
        rclpy.spin_once(waiter, timeout_sec=0.2)

    if not waiter.received:
        print(f'PROBE namespace={args.namespace} RESULT amcl_timeout', flush=True)
        waiter.destroy_node()
        nav.destroy_node()
        rclpy.shutdown()
        sys.exit(2)

    waiter.destroy_node()
    print(f'PROBE namespace={args.namespace} amcl_pose_received', flush=True)
    nav.waitUntilNav2Active(localizer='amcl')
    print(f'PROBE namespace={args.namespace} nav2_active', flush=True)

    start = pose_stamped(nav, args.start_x, args.start_y, args.start_yaw)
    failures = 0
    for label, x, y, yaw in args.goal:
        goal = pose_stamped(nav, x, y, yaw)
        try:
            path = nav.getPath(start, goal, planner_id='GridBased', use_start=True)
            count = len(path.poses) if path is not None else 0
            verdict = 'PASS' if count > 0 else 'FAIL'
            if count == 0:
                failures += 1
            print(
                f'PROBE namespace={args.namespace} goal={label} '
                f'start=({args.start_x:.2f},{args.start_y:.2f}) '
                f'end=({x:.2f},{y:.2f}) result={verdict} poses={count}',
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            failures += 1
            print(
                f'PROBE namespace={args.namespace} goal={label} '
                f'end=({x:.2f},{y:.2f}) result=EXCEPTION error={exc}',
                flush=True,
            )

    nav.destroy_node()
    rclpy.shutdown()
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
