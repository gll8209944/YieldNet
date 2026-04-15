import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # Robot configurations
    # Format: [x, y, theta, robot_id]
    robot_a_config = ['-8.0', '0.0', '0.0', 'robot_a']
    robot_b_config = ['8.0', '0.0', '3.14159', 'robot_b']  # Opposite direction
    robot_c_config = ['0.0', '-8.0', '1.5707', 'robot_c']  # Perpendicular

    # Get package paths
    pkg_share = get_package_share_directory('fleet_gazebo')

    # Turtlebot3 model path
    turtlebot3_model = os.path.join(
        get_package_share_directory('turtlebot3_gazebo'),
        'models/turtlebot3_burger/model.sdf'
    )

    nodes = []

    # Spawn robot_a
    nodes.append(
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-entity', 'robot_a',
                '-file', turtlebot3_model,
                '-x', robot_a_config[0],
                '-y', robot_a_config[1],
                '-z', '0.0',
                '-Y', robot_a_config[2],
            ],
            output='screen',
        )
    )

    # Spawn robot_b
    nodes.append(
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-entity', 'robot_b',
                '-file', turtlebot3_model,
                '-x', robot_b_config[0],
                '-y', robot_b_config[1],
                '-z', '0.0',
                '-Y', robot_b_config[2],
            ],
            output='screen',
        )
    )

    return LaunchDescription(nodes)
