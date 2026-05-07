"""Launch file for fleet coordination node.

Usage:
    ros2 launch fleet_coordination fleet_bringup.launch.py \
        robot_id:=robot_a \
        peer_ips:="[192.168.50.102, 192.168.50.103]"

"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for fleet coordination."""

    # Declare launch arguments
    robot_id_arg = DeclareLaunchArgument(
        'robot_id',
        description='Robot ID (e.g., robot_a, robot_b, robot_c)',
        default_value='robot_a'
    )

    peer_ips_arg = DeclareLaunchArgument(
        'peer_ips',
        description='List of peer robot IPs for DDS discovery',
        default_value='[192.168.50.102, 192.168.50.103]'
    )

    # Get configurations
    robot_id = LaunchConfiguration('robot_id')
    peer_ips = LaunchConfiguration('peer_ips')

    # Fleet coordinator node
    fleet_coordinator_node = Node(
        package='fleet_coordination',
        executable='fleet_coordinator',
        name='fleet_coordinator',
        output='screen',
        parameters=[{
            'robot_id': robot_id,
            # Distance thresholds (meters)
            'emergency_range': 0.8,
            'yield_range': 2.5,
            'caution_range': 4.0,
            'awareness_range': 8.0,
            # Path conflict detection
            'path_conflict_dist': 1.5,
            'path_lookahead': 5.0,
            # Timeouts
            'yield_timeout': 15.0,
            'heartbeat_timeout': 6.0,
            # Hysteresis for path conflict
            'conflict_hysteresis_ticks': 5,
        }],
        remappings=[
            # Local odometry
            ('/odom', f'/{robot_id}/odom'),
        ],
        namespace=robot_id,
    )

    # Environment variables for DDS
    env_vars = [
        SetEnvironmentVariable('ROS_DOMAIN_ID', '0'),
        SetEnvironmentVariable(
            'CYCLONEDDS_URI',
            'file:///etc/cyclonedds/internal.xml'
        ),
    ]

    return LaunchDescription([
        # Environment
        *env_vars,

        # Arguments
        robot_id_arg,
        peer_ips_arg,

        # Nodes
        fleet_coordinator_node,
    ])
