#!/bin/bash
# Full Fleet Test Script - Run on Cloud Server Manually
# This script starts Gazebo, spawns 2 robots, and runs fleet coordination

set -e

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=42

echo "=== Fleet Full Test ==="

# Step 1: Clean up
echo "[1] Cleaning up..."
screen -wipe 2>/dev/null || true
killall -9 gzserver 2>/dev/null || true
sleep 2

# Step 2: Start Gazebo
echo "[2] Starting Gazebo..."
screen -dmS gaz bash -c "gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so /opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world 2>&1 | tee /tmp/gazebo.log; exec bash"
sleep 8

# Step 3: Prepare robot SDFs
echo "[3] Preparing robot SDFs..."
mkdir -p /tmp/robot_sdf

python3 << 'PYEOF'
import xml.etree.ElementTree as ET
for ns, x, y in [("robot_a", -2.0, 0.5), ("robot_b", 2.0, -0.5)]:
    tree = ET.parse("/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf")
    root = tree.getroot()
    for tag in root.iter("odometry_frame"):
        tag.text = f"{ns}/odom"
    for tag in root.iter("robot_base_frame"):
        tag.text = f"{ns}/base_footprint"
    for tag in root.iter("frame_name"):
        tag.text = f"{ns}/base_scan"
    tree.write(f"/tmp/robot_sdf/{ns}.sdf", xml_declaration=False)
    print(f"Created {ns}.sdf")
PYEOF

# Step 4: Spawn robots
echo "[4] Spawning robot_a..."
ros2 run gazebo_ros spawn_entity.py -entity robot_a -file /tmp/robot_sdf/robot_a.sdf -x -2.0 -y 0.5 -z 0.01 -robot_namespace robot_a
sleep 1

echo "[5] Spawning robot_b..."
ros2 run gazebo_ros spawn_entity.py -entity robot_b -file /tmp/robot_sdf/robot_b.sdf -x 2.0 -y -0.5 -z 0.01 -robot_namespace robot_b
sleep 2

# Step 5: Start fleet coordinators
echo "[6] Starting fleet coordinators..."
screen -dmS coord_a bash -c "source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash && ros2 run fleet_coordination fleet_coordinator --ros-args -p robot_id:=robot_a -p peer_ids:=[robot_b] -r __ns:=/robot_a 2>&1 | tee /tmp/coord_a.log; exec bash"

screen -dmS coord_b bash -c "source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash && ros2 run fleet_coordination fleet_coordinator --ros-args -p robot_id:=robot_b -p peer_ids:=[robot_a] -r __ns:=/robot_b 2>&1 | tee /tmp/coord_b.log; exec bash"

sleep 3

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To view coordinator logs:"
echo "  screen -r coord_a  (Ctrl+A D to detach)"
echo "  screen -r coord_b  (Ctrl+A D to detach)"
echo ""
echo "To list topics: ros2 topic list"
echo "To check nodes: ros2 node list"
echo ""
echo "To stop: killall -9 gzserver && screen -wipe"
