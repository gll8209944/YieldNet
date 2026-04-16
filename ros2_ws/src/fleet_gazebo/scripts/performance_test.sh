#!/bin/bash
# Performance Test Script for Fleet Coordination
# Tests: latency ≤ 50ms (P95), bandwidth ≤ 10 KB/s

set -e

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger

TURTLEBOT3_MODEL=burger
GAZEBO_MODEL_PATH=$(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models

echo "=========================================="
echo "  Performance Test - Latency & Bandwidth"
echo "=========================================="
echo ""

echo "[1] Cleaning up old processes..."
screen -wipe 2>/dev/null || true
killall -9 gzserver 2>/dev/null || true
killall -9 python3 2>/dev/null || true
sleep 2

echo "[2] Starting Gazebo server (headless)..."
screen -dmS gaz bash -c "gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world 2>&1 | tee /tmp/gazebo.log; exec bash"
sleep 8

echo "[3] Preparing robot SDFs..."
mkdir -p /tmp/robot_sdf

# Create robot SDFs with namespaces
for robot in robot_a robot_b robot_c; do
    python3 << PYEOF
import xml.etree.ElementTree as ET

tree = ET.parse('/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf')
root = tree.getroot()

namespace = '$robot'
for tag in root.iter('odometry_frame'):
    tag.text = f'{namespace}/odom'
for tag in root.iter('robot_base_frame'):
    tag.text = f'{namespace}/base_footprint'
for tag in root.iter('frame_name'):
    tag.text = f'{namespace}/base_scan'

tree.write('/tmp/robot_sdf/${robot}.sdf', xml_declaration=False)
print("Created ${robot}.sdf")
PYEOF
done

echo "[4] Spawning 3 robots..."
# Robot A at (-4, 0)
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_a \
    -file /tmp/robot_sdf/robot_a.sdf \
    -x -4.0 -y 0.0 -z 0.01 \
    -robot_namespace robot_a
sleep 1

# Robot B at (4, 0)
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_b \
    -file /tmp/robot_sdf/robot_b.sdf \
    -x 4.0 -y 0.0 -z 0.01 \
    -robot_namespace robot_b
sleep 1

# Robot C at (0, 4)
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_c \
    -file /tmp/robot_sdf/robot_c.sdf \
    -x 0.0 -y 4.0 -z 0.01 \
    -robot_namespace robot_c
sleep 2

echo "[5] Starting fleet coordinators..."
COORDINATOR_BIN=/home/guolinlin/ros2_ws/install/fleet_coordination/bin/fleet_coordinator

for robot in robot_a robot_b robot_c; do
    peers=$(echo robot_a robot_b robot_c | sed "s/$robot //")
    screen -dmS coord_${robot} bash -c "
        source /opt/ros/humble/setup.bash
        source ~/ros2_ws/install/setup.bash
        export ROS_DOMAIN_ID=0
        $COORDINATOR_BIN \
            --ros-args \
            -p robot_id:=$robot \
            -p peer_ids:=[$peers] \
            -r __ns:=/$robot \
            2>&1 | tee /tmp/coord_${robot}.log
        exec bash
    "
done

sleep 3

echo "[6] Starting mock path publishers..."
screen -dmS mock_path bash -c "
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export ROS_DOMAIN_ID=0
    export PYTHONPATH=/home/guolinlin/ros2_ws/install/fleet_msgs/local/lib/python3.10/dist-packages:/home/guolinlin/ros2_ws/install/fleet_msgs/lib/python3.10/site-packages:/home/guolinlin/ros2_ws/install/fleet_coordination/lib/python3.10/site-packages:\$PYTHONPATH
    python3 /tmp/mock_path_publisher_all.py robot_a robot_b robot_c \
        2>&1 | tee /tmp/mock_path.log
    exec bash
"
sleep 3

echo ""
echo "=========================================="
echo "  Setup Complete - Running Performance Tests"
echo "=========================================="
echo ""
echo "Waiting for system to stabilize (10s)..."
sleep 10

echo ""
echo "[TEST 1] Measuring topic latency (pose)..."
echo "--- /robot_a/fleet/pose latency ---"
timeout 15 ros2 topic delay /robot_a/fleet/pose 2>&1 || echo "Timeout or error"

echo ""
echo "[TEST 2] Measuring topic latency (heartbeat)..."
echo "--- /robot_a/fleet/heartbeat latency ---"
timeout 15 ros2 topic delay /robot_a/fleet/heartbeat 2>&1 || echo "Timeout or error"

echo ""
echo "[TEST 3] Measuring topic bandwidth..."
echo "--- /robot_a/fleet/pose bandwidth ---"
timeout 10 ros2 topic bw /robot_a/fleet/pose 2>&1 || echo "Timeout or error"

echo ""
echo "--- /robot_a/fleet/heartbeat bandwidth ---"
timeout 10 ros2 topic bw /robot_a/fleet/heartbeat 2>&1 || echo "Timeout or error"

echo ""
echo "--- /robot_a/fleet/planned_path bandwidth ---"
timeout 10 ros2 topic bw /robot_a/fleet/planned_path 2>&1 || echo "Timeout or error"

echo ""
echo "--- /robot_a/fleet/yield bandwidth ---"
timeout 10 ros2 topic bw /robot_a/fleet/yield 2>&1 || echo "Timeout or error"

echo ""
echo "=========================================="
echo "  All 3 Topics Bandwidth (Combined) ---"
echo "=========================================="
timeout 10 bash -c '
    (ros2 topic bw /robot_a/fleet/pose &
     ros2 topic bw /robot_b/fleet/pose &
     ros2 topic bw /robot_c/fleet/pose &
     wait) 2>&1 | grep -E "Average|Bandwidth"
'

echo ""
echo "[TEST 4] Checking coordinator status..."
for robot in robot_a robot_b robot_c; do
    echo "--- $robot coordinator_speed topic info ---"
    ros2 topic info /${robot}/fleet/coordinator_speed 2>&1 | head -5
done

echo ""
echo "=========================================="
echo "  Performance Test Complete"
echo "=========================================="
echo ""
echo "Results interpretation:"
echo "  - Latency: Lower is better. Target: ≤50ms (P95)"
echo "  - Bandwidth: Lower is better. Target: ≤10 KB/s total for 3 robots"
echo ""
echo "To stop: killall -9 gzserver && screen -wipe"
