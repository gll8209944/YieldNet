#!/usr/bin/env python3
"""
Fleet Nav2 BT Launch

Launches the fleet coordination behavior tree nodes and registers them with Nav2.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Get package paths
    pkg_dir = get_package_share_directory('fleet_nav2_bt')

    # Behavior tree configuration
    bt_xml_path = os.path.join(pkg_dir, 'behavior_trees', 'navigate_with_fleet.xml')

    # Nodes to register BT plugins
    check_fleet_conflict_node = Node(
        package='fleet_nav2_bt',
        executable='check_fleet_conflict_node',
        name='check_fleet_conflict_node',
        output='screen',
        parameters=[{
            'bt_xml_filename': bt_xml_path
        }]
    )

    wait_for_yield_clear_node = Node(
        package='fleet_nav2_bt',
        executable='wait_for_yield_clear_node',
        name='wait_for_yield_clear_node',
        output='screen',
        parameters=[{
            'bt_xml_filename': bt_xml_path
        }]
    )

    adjust_speed_for_fleet_node = Node(
        package='fleet_nav2_bt',
        executable='adjust_speed_for_fleet_node',
        name='adjust_speed_for_fleet_node',
        output='screen',
        parameters=[{
            'bt_xml_filename': bt_xml_path
        }]
    )

    return LaunchDescription([
        # BT Plugin Nodes
        check_fleet_conflict_node,
        wait_for_yield_clear_node,
        adjust_speed_for_fleet_node,
    ])
