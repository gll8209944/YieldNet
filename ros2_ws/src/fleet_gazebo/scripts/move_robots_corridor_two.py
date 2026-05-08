#!/usr/bin/env python3
"""Move robot_a / robot_b toward corridor center — test harness only (NOT production control).

Fleet coordinator publishes coordinator_speed scale; movement uses /cmd_vel directly for
scenario mobility when Nav2 is not driving the robots.
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from fleet_msgs.msg import RobotPose


class RobotMoverTwo(Node):

    def __init__(self) -> None:
        super().__init__('robot_mover_corridor_two')
        robots = ('robot_a', 'robot_b')
        self.targets = {rid: (0.0, 0.0) for rid in robots}

        self.linear_speed = 0.2
        self.angular_speed = 0.5
        self.arrival_threshold = 0.3

        self.positions = {}
        self.speed_scaling = {rid: 1.0 for rid in robots}
        self.cmd_vel_publishers = {}
        self.arrived = {rid: False for rid in robots}

        qos_odom = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        qos_speed = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        qos_cmd = QoSProfile(depth=10)

        for robot_id in robots:
            self.create_subscription(
                Odometry,
                f'/{robot_id}/odom',
                lambda msg, rid=robot_id: self._odom_callback(msg, rid),
                qos_odom,
            )
            self.create_subscription(
                RobotPose,
                f'/{robot_id}/fleet/coordinator_speed',
                lambda msg, rid=robot_id: self._speed_callback(msg, rid),
                qos_speed,
            )
            self.cmd_vel_publishers[robot_id] = self.create_publisher(
                Twist, f'/{robot_id}/cmd_vel', qos_cmd
            )

        self.create_timer(0.1, self._control_loop)
        self.get_logger().info(
            'Corridor mover (2 robots): drive toward origin; respecting coordinator_speed.'
        )

    def _speed_callback(self, msg: RobotPose, robot_id: str) -> None:
        self.speed_scaling[robot_id] = msg.x

    def _odom_callback(self, msg: Odometry, robot_id: str) -> None:
        self.positions[robot_id] = {
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y,
            'theta': self._quat_to_yaw(msg.pose.pose.orientation),
        }

    def _quat_to_yaw(self, quat) -> float:
        return math.atan2(
            2.0 * (quat.w * quat.z + quat.x * quat.y),
            1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z),
        )

    def _control_loop(self) -> None:
        for robot_id, target in self.targets.items():
            if robot_id not in self.positions:
                continue
            speed_ratio = self.speed_scaling.get(robot_id, 1.0)
            if speed_ratio < 0.01:
                self.cmd_vel_publishers[robot_id].publish(Twist())
                continue
            if self.arrived.get(robot_id):
                self.cmd_vel_publishers[robot_id].publish(Twist())
                continue

            pos = self.positions[robot_id]
            dx = target[0] - pos['x']
            dy = target[1] - pos['y']
            dist = math.hypot(dx, dy)

            if dist < self.arrival_threshold:
                self.get_logger().info(f'{robot_id} arrived near center.')
                self.arrived[robot_id] = True
                self.cmd_vel_publishers[robot_id].publish(Twist())
                continue

            desired_theta = math.atan2(dy, dx)
            angle_err = desired_theta - pos['theta']
            while angle_err > math.pi:
                angle_err -= 2 * math.pi
            while angle_err < -math.pi:
                angle_err += 2 * math.pi

            eff_lin = self.linear_speed * speed_ratio
            eff_ang = self.angular_speed * min(speed_ratio, 1.0)
            cmd = Twist()
            if abs(angle_err) > 0.1:
                cmd.angular.z = eff_ang if angle_err > 0 else -eff_ang
            else:
                cmd.linear.x = eff_lin

            self.cmd_vel_publishers[robot_id].publish(cmd)


def main() -> None:
    rclpy.init()
    node = RobotMoverTwo()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        for pub in node.cmd_vel_publishers.values():
            pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
