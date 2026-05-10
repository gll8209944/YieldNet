#!/usr/bin/env python3
"""Controlled topic collector for the Nav2 e2e scenario."""

from pathlib import Path
import argparse
import time

import rclpy
from rclpy.node import Node
from nav2_msgs.msg import SpeedLimit
from std_msgs.msg import String
from fleet_msgs.msg import YieldCommand


class E2ETopicCollector(Node):
    def __init__(self, output_dir: Path):
        super().__init__('fleet_nav2_e2e_topic_collector')
        self.output_dir = output_dir
        self.files = {
            'speed_robot_a': (output_dir / 'speed_robot_a.log').open('w', encoding='utf-8', buffering=1),
            'speed_robot_b': (output_dir / 'speed_robot_b.log').open('w', encoding='utf-8', buffering=1),
            'status_robot_a': (output_dir / 'status_robot_a.log').open('w', encoding='utf-8', buffering=1),
            'status_robot_b': (output_dir / 'status_robot_b.log').open('w', encoding='utf-8', buffering=1),
            'yield': (output_dir / 'yield.log').open('w', encoding='utf-8', buffering=1),
        }

        self.create_subscription(SpeedLimit, '/robot_a/speed_limit', self._speed_cb('speed_robot_a'), 10)
        self.create_subscription(SpeedLimit, '/robot_b/speed_limit', self._speed_cb('speed_robot_b'), 10)
        self.create_subscription(String, '/robot_a/fleet/coordinator_status', self._string_cb('status_robot_a'), 10)
        self.create_subscription(String, '/robot_b/fleet/coordinator_status', self._string_cb('status_robot_b'), 10)
        self.create_subscription(YieldCommand, '/fleet/yield', self._yield_cb, 10)

    def _stamp(self) -> str:
        return f'{time.time():.3f}'

    def _write(self, key: str, text: str) -> None:
        self.files[key].write(f'{self._stamp()} {text}\n')
        self.files[key].flush()

    def _speed_cb(self, key: str):
        def callback(msg: SpeedLimit) -> None:
            self._write(
                key,
                f'SpeedLimit percentage={msg.percentage} speed_limit={msg.speed_limit:.3f}',
            )

        return callback

    def _string_cb(self, key: str):
        def callback(msg: String) -> None:
            self._write(key, msg.data)

        return callback

    def _yield_cb(self, msg: YieldCommand) -> None:
        self._write('yield', str(msg).replace('\n', ' | '))

    def close(self) -> None:
        for key, fh in self.files.items():
            fh.write(f'{self._stamp()} COLLECTOR_DONE key={key}\n')
            fh.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--duration', type=float, required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    collector = E2ETopicCollector(output_dir)
    deadline = time.time() + args.duration
    try:
        while rclpy.ok() and time.time() < deadline:
            rclpy.spin_once(collector, timeout_sec=0.2)
    finally:
        collector.close()
        collector.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
