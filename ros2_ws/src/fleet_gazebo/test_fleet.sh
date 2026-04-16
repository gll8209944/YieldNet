#!/bin/bash
# Fleet Gazebo Test Script - Run on Cloud Server
# Usage: bash test_fleet.sh

set -e

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger

TURTLEBOT3_MODEL=burger
GAZEBO_MODEL_PATH=$(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models

echo "=== Fleet Gazebo Test ==="
echo ""

echo "[1] Cleaning up old processes..."
screen -wipe 2>/dev/null || true
killall -9 gzserver 2>/dev/null || true
killall -9 gzclient 2>/dev/null || true
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

# Create modified SDF files for each robot to avoid namespace conflicts
echo "[4] Preparing robot SDFs with unique namespaces..."

mkdir -p /tmp/robot_sdf

# Robot A
python3 << 'PYEOF'
import xml.etree.ElementTree as ET

tree = ET.parse('/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf')
root = tree.getroot()

namespace = 'robot_a'
for odom_frame_tag in root.iter('odometry_frame'):
    odom_frame_tag.text = f'{namespace}/odom'
for base_frame_tag in root.iter('robot_base_frame'):
    base_frame_tag.text = f'{namespace}/base_footprint'
for scan_frame_tag in root.iter('frame_name'):
    scan_frame_tag.text = f'{namespace}/base_scan'

tree.write('/tmp/robot_sdf/robot_a.sdf', xml_declaration=False)
print("Created robot_a.sdf")
PYEOF

# Robot B
python3 << 'PYEOF'
import xml.etree.ElementTree as ET

tree = ET.parse('/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf')
root = tree.getroot()

namespace = 'robot_b'
for odom_frame_tag in root.iter('odometry_frame'):
    odom_frame_tag.text = f'{namespace}/odom'
for base_frame_tag in root.iter('robot_base_frame'):
    base_frame_tag.text = f'{namespace}/base_footprint'
for scan_frame_tag in root.iter('frame_name'):
    scan_frame_tag.text = f'{namespace}/base_scan'

tree.write('/tmp/robot_sdf/robot_b.sdf', xml_declaration=False)
print("Created robot_b.sdf")
PYEOF

echo "[5] Spawning robot_a at (-2.0, 0.5)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_a \
    -file /tmp/robot_sdf/robot_a.sdf \
    -x -2.0 -y 0.5 -z 0.01 \
    -robot_namespace robot_a

sleep 1

echo "[6] Spawning robot_b at (2.0, -0.5)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_b \
    -file /tmp/robot_sdf/robot_b.sdf \
    -x 2.0 -y -0.5 -z 0.01 \
    -robot_namespace robot_b

sleep 2

echo "[7] Listing spawned models..."
gz model list

echo ""
echo "=== Test Complete ==="
echo "To view Gazebo GUI, run: gzclient"
echo "To stop, run: killall gzserver"
