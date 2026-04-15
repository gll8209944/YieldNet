#!/bin/bash
# Fleet Gazebo Test Script - Run on Cloud Server
# Usage: bash test_fleet.sh

set -e

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger

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

echo "[4] Spawning robot_a at (-2.0, 0.5)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_a \
    -file $(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
    -x -2.0 -y 0.5 -z 0.01

sleep 1

echo "[5] Spawning robot_b at (2.0, -0.5)..."
ros2 run gazebo_ros spawn_entity.py \
    -entity robot_b \
    -file $(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
    -x 2.0 -y -0.5 -z 0.01

sleep 2

echo "[6] Listing spawned models..."
gz model list

echo ""
echo "=== Test Complete ==="
echo "To view Gazebo GUI, run: gzclient"
echo "To stop, run: killall gzserver"
