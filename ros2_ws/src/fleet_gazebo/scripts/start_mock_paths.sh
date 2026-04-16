#!/bin/bash
# Start Mock Path Publisher for Multi-Robot Testing
# Usage: bash start_mock_paths.sh robot_a robot_b robot_c

set -e

source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=0

ROBOT_IDS="${@:-robot_a robot_b robot_c}"

echo "Starting mock path publisher for: $ROBOT_IDS"

python3 /tmp/mock_path_publisher_all.py $ROBOT_IDS