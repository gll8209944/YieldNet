#!/bin/bash
# Multi-Robot Fleet Test Script with Navigation - 3 Robots (N-Machine Mode)
# Usage: bash test_multi_robot_with_nav.sh
#
# This script tests the multi-robot coordination with 3 robots:
# - robot_a at (-4, 0) facing east (+x)
# - robot_b at (4, 0) facing west (-x)
# - robot_c at (0, 4) facing south (-y)
#
# All robots will move toward center (0, 0) to trigger yield/passing negotiation.

set -e

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger

TURTLEBOT3_MODEL=burger
GAZEBO_MODEL_PATH=$(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models

echo "=========================================="
echo "  Multi-Robot Fleet Coordination Test (3)"
echo "         With Navigation Enabled"
echo "=========================================="
echo ""
echo "Scenario: 三方交汇 (Triple-Meet) - All robots move to center"
echo "  robot_a: (-4, 0) → (0, 0) - move right"
echo "  robot_b: ( 4, 0) → (0, 0) - move left"
echo "  robot_c: ( 0, 4) → (0, 0) - move down"
echo ""

echo "[1] Cleaning up old processes..."
screen -wipe 2>/dev/null || true
killall -9 gzserver 2>/dev/null || true
killall -9 gzclient 2>/dev/null || true
killall -9 python3 2>/dev/null || true
sleep 2

echo "[2] Starting Gazebo server (headless)..."
screen -dmS gaz bash -c "gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world 2>&1 | tee /tmp/gazebo.log; exec bash"
sleep 8

echo "[3] Checking Gazebo is running..."
if ps aux | grep -v grep | grep gzserver > /dev/null; then
    echo "   ✓ Gazebo is running"
else
    echo "   ✗ Gazebo failed to start"
    cat /tmp/gazebo.log | tail -20
    exit 1
fi

# Create modified SDF files for each robot with unique namespaces
echo "[4] Preparing robot SDFs with unique namespaces..."

mkdir -p /tmp/robot_sdf

# Robot A
python3 << 'PYEOF'
import xml.etree.ElementTree as ET

tree = ET.parse('/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf')
root = tree.getroot()

namespace = 'robot_a'
for tag in root.iter('odometry_frame'):
    tag.text = f'{namespace}/odom'
for tag in root.iter('robot_base_frame'):
    tag.text = f'{namespace}/base_footprint'
for tag in root.iter('frame_name'):
    tag.text = f'{namespace}/base_scan'

tree.write('/tmp/robot_sdf/robot_a.sdf', xml_declaration=False)
print("Created robot_a.sdf")
PYEOF

# Robot B
python3 << 'PYEOF'
import xml.etree.ElementTree as ET

tree = ET.parse('/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf')
root = tree.getroot()

namespace = 'robot_b'
for tag in root.iter('odometry_frame'):
    tag.text = f'{namespace}/odom'
for tag in root.iter('robot_base_frame'):
    tag.text = f'{namespace}/base_footprint'
for tag in root.iter('frame_name'):
    tag.text = f'{namespace}/base_scan'

tree.write('/tmp/robot_sdf/robot_b.sdf', xml_declaration=False)
print("Created robot_b.sdf")
PYEOF

# Robot C
python3 << 'PYEOF'
import xml.etree.ElementTree as ET

tree = ET.parse('/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf')
root = tree.getroot()

namespace = 'robot_c'
for tag in root.iter('odometry_frame'):
    tag.text = f'{namespace}/odom'
for tag in root.iter('robot_base_frame'):
    tag.text = f'{namespace}/base_footprint'
for tag in root.iter('frame_name'):
    tag.text = f'{namespace}/base_scan'

tree.write('/tmp/robot_sdf/robot_c.sdf', xml_declaration=False)
print("Created robot_c.sdf")
PYEOF

echo "[5] Spawning 3 robots..."
echo "   Spawning robot_a at (-4, 0)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_a \
    -file /tmp/robot_sdf/robot_a.sdf \
    -x -4.0 -y 0.0 -z 0.01 \
    -robot_namespace robot_a
sleep 1

echo "   Spawning robot_b at (4, 0)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_b \
    -file /tmp/robot_sdf/robot_b.sdf \
    -x 4.0 -y 0.0 -z 0.01 \
    -robot_namespace robot_b
sleep 1

echo "   Spawning robot_c at (0, 4)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_c \
    -file /tmp/robot_sdf/robot_c.sdf \
    -x 0.0 -y 4.0 -z 0.01 \
    -robot_namespace robot_c
sleep 2

echo "[6] Listing spawned models..."
gz model list

echo ""
echo "[7] Starting fleet coordinators for all 3 robots..."
echo ""

COORDINATOR_BIN=/home/guolinlin/ros2_ws/install/fleet_coordination/bin/fleet_coordinator

# Start fleet coordinator for robot_a
screen -dmS coord_a bash -c "
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=0
    $COORDINATOR_BIN \
        --ros-args \
        -p robot_id:=robot_a \
        -p peer_ids:=[robot_b,robot_c] \
        -r __ns:=/robot_a \
        2>&1 | tee /tmp/coord_a.log
    exec bash
"

# Start fleet coordinator for robot_b
screen -dmS coord_b bash -c "
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=0
    $COORDINATOR_BIN \
        --ros-args \
        -p robot_id:=robot_b \
        -p peer_ids:=[robot_a,robot_c] \
        -r __ns:=/robot_b \
        2>&1 | tee /tmp/coord_b.log
    exec bash
"

# Start fleet coordinator for robot_c
screen -dmS coord_c bash -c "
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=0
    $COORDINATOR_BIN \
        --ros-args \
        -p robot_id:=robot_c \
        -p peer_ids:=[robot_a,robot_b] \
        -r __ns:=/robot_c \
        2>&1 | tee /tmp/coord_c.log
    exec bash
"

sleep 3

echo "[8] Starting mock path publisher for all 3 robots..."
screen -dmS mock_path bash -c "
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=0
    export PYTHONPATH=/home/guolinlin/ros2_ws/install/fleet_msgs/local/lib/python3.10/dist-packages:/home/guolinlin/ros2_ws/install/fleet_msgs/lib/python3.10/site-packages:/home/guolinlin/ros2_ws/install/fleet_coordination/lib/python3.10/site-packages:\$PYTHONPATH
    python3 /tmp/mock_path_publisher_all.py robot_a robot_b robot_c \
        2>&1 | tee /tmp/mock_path.log
    exec bash
"

sleep 5

echo "[9] Waiting for coordinators to initialize..."
sleep 3

echo "[10] Starting robot mover to move robots toward center..."
screen -dmS robot_mover bash -c "
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=0
    export PYTHONPATH=/home/guolinlin/ros2_ws/install/fleet_msgs/local/lib/python3.10/dist-packages:/home/guolinlin/ros2_ws/install/fleet_msgs/lib/python3.10/site-packages:/home/guolinlin/ros2_ws/install/fleet_coordination/lib/python3.10/site-packages:\$PYTHONPATH
    python3 /tmp/move_robots_to_center.py \
        2>&1 | tee /tmp/robot_mover.log
    exec bash
"

sleep 2

echo ""
echo "=========================================="
echo "  Setup Complete - All Systems Running"
echo "=========================================="
echo ""
echo "Expected behavior:"
echo "  1. All 3 robots discover each other → AWARENESS"
echo "  2. Robots approach center, distance < 4m → CAUTION"
echo "  3. Robots get close, path conflict detected:"
echo "     - robot_a (highest priority) → PASSING (30%)"
echo "     - robot_b, robot_c (lower priority) → YIELDING (0%)"
echo "  4. After robot_a passes → RESUME → robot_b starts passing"
echo ""
echo "To view logs:"
echo "  screen -r coord_a  (robot_a coordinator)"
echo "  screen -r coord_b  (robot_b coordinator)"
echo "  screen -r coord_c  (robot_c coordinator)"
echo "  screen -r mock_path  (path publisher)"
echo "  screen -r robot_mover  (robot mover)"
echo ""
echo "Quick status check:"
echo "  tail -f /tmp/coord_a.log"
echo "  tail -f /tmp/robot_mover.log"
echo ""
echo "To stop: killall -9 gzserver && screen -wipe"
echo ""