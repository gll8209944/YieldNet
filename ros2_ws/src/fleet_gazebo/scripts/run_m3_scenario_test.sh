#!/bin/bash
# S3-M3 Scenario Test Runner for YieldNet Fleet Coordination
#
# Usage: bash run_m3_scenario_test.sh <scenario> [duration]
#
# Scenarios:
#   corridor-2robot     - Two robots meeting in corridor
#   corridor-3robot    - Three robots in corridor (triple meet)
#   t-intersection     - Two robots at T-intersection
#   t-intersection-3   - Three robots at T-intersection
#
# This script requires:
# - ROS 2 Humble
# - Gazebo 11
# - turtlebot3_gazebo
# - fleet_coordination package built
# - fleet_gazebo package built

set -e

# Get script directory regardless of symlinks
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS2_WS="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

SCENARIO=${1:-corridor-2robot}
DURATION=${2:-60}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR=/tmp/fleet_test_${SCENARIO}_${TIMESTAMP}
REPORT_DIR="${ROS2_WS}/docs/reports"

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger
GAZEBO_MODEL_PATH=$(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models

mkdir -p "$LOG_DIR"

echo "=========================================="
echo "  S3-M3 Scenario Test Runner"
echo "=========================================="
echo "Scenario: $SCENARIO"
echo "Duration: ${DURATION}s"
echo "Log dir: $LOG_DIR"
echo "ROS2_ws: $ROS2_WS"
echo ""

# Cleanup function
cleanup() {
    echo "[CLEANUP] Stopping processes..."
    killall -9 gzserver 2>/dev/null || true
    killall -9 python3 2>/dev/null || true
    screen -wipe 2>/dev/null || true
}

trap cleanup EXIT

# Cleanup old processes
echo "[1] Cleaning up old processes..."
screen -wipe 2>/dev/null || true
killall -9 gzserver 2>/dev/null || true
killall -9 gzclient 2>/dev/null || true
killall -9 python3 2>/dev/null || true
sleep 2

# Prepare robot SDFs
echo "[2] Preparing robot SDFs..."
mkdir -p /tmp/robot_sdf

prepare_robot_sdf() {
    local robot=$1
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

tree.write(f'/tmp/robot_sdf/{namespace}.sdf', xml_declaration=False)
print(f"Created {namespace}.sdf")
PYEOF
}

# Start Gazebo with appropriate world
echo "[3] Starting Gazebo..."
case $SCENARIO in
    corridor-2robot|corridor-3robot)
        WORLD="${ROS2_WS}/install/fleet_gazebo/share/fleet_gazebo/worlds/corridor.world"
        ;;
    t-intersection|t-intersection-3)
        WORLD="${ROS2_WS}/install/fleet_gazebo/share/fleet_gazebo/worlds/t_intersection.world"
        ;;
    *)
        WORLD=/opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world
        ;;
esac

# Fallback to empty world if custom world doesn't exist
if [ ! -f "$WORLD" ]; then
    echo "   World file not found: $WORLD, using empty_world"
    WORLD=/opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world
fi

screen -dmS gaz bash -c "gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so $WORLD 2>&1 | tee $LOG_DIR/gazebo.log; exec bash"
sleep 8

# Check Gazebo
if ! ps aux | grep -v grep | grep gzserver > /dev/null; then
    echo "ERROR: Gazebo failed to start"
    cat $LOG_DIR/gazebo.log | tail -20
    exit 1
fi
echo "   Gazebo running"

# Determine robots based on scenario
case $SCENARIO in
    corridor-2robot|t-intersection)
        ROBOTS=(robot_a robot_b)
        ;;
    corridor-3robot|t-intersection-3)
        ROBOTS=(robot_a robot_b robot_c)
        ;;
    *)
        ROBOTS=(robot_a robot_b)
        ;;
esac

for robot in "${ROBOTS[@]}"; do
    prepare_robot_sdf $robot
done

# Spawn robots based on scenario
echo "[4] Spawning robots..."
case $SCENARIO in
    corridor-2robot)
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_a \
            -file /tmp/robot_sdf/robot_a.sdf \
            -x -4.0 -y 0.0 -z 0.01 \
            -robot_namespace robot_a
        sleep 1
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_b \
            -file /tmp/robot_sdf/robot_b.sdf \
            -x 4.0 -y 0.0 -z 0.01 \
            -robot_namespace robot_b
        ;;
    corridor-3robot|t-intersection-3)
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_a \
            -file /tmp/robot_sdf/robot_a.sdf \
            -x -4.0 -y 0.0 -z 0.01 \
            -robot_namespace robot_a
        sleep 1
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_b \
            -file /tmp/robot_sdf/robot_b.sdf \
            -x 4.0 -y 0.0 -z 0.01 \
            -robot_namespace robot_b
        sleep 1
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_c \
            -file /tmp/robot_sdf/robot_c.sdf \
            -x 0.0 -y 4.0 -z 0.01 \
            -robot_namespace robot_c
        ;;
    t-intersection)
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_a \
            -file /tmp/robot_sdf/robot_a.sdf \
            -x -2.0 -y 0.0 -z 0.01 \
            -robot_namespace robot_a
        sleep 1
        ros2 run gazebo_ros spawn_entity.py \
            -entity robot_b \
            -file /tmp/robot_sdf/robot_b.sdf \
            -x 0.0 -y 3.0 -z 0.01 \
            -robot_namespace robot_b
        ;;
esac
sleep 2

echo "[5] Starting fleet coordinators..."
COORDINATOR_BIN="${ROS2_WS}/install/fleet_coordination/bin/fleet_coordinator"

# Fallback if bin doesn't exist
if [ ! -f "$COORDINATOR_BIN" ]; then
    COORDINATOR_BIN=$(ros2 pkg prefix fleet_coordination)/lib/fleet_coordination/fleet_coordinator
fi

for robot in "${ROBOTS[@]}"; do
    peers=""
    for other in "${ROBOTS[@]}"; do
        if [ "$other" != "$robot" ]; then
            if [ -z "$peers" ]; then
                peers="$other"
            else
                peers="$peers,$other"
            fi
        fi
    done

    screen -dmS coord_${robot} bash -c "
        source /opt/ros/humble/setup.bash
        source ${ROS2_WS}/install/setup.bash
        export ROS_DOMAIN_ID=0
        ${COORDINATOR_BIN} \
            --ros-args \
            -p robot_id:=$robot \
            -p peer_ids:=[$peers] \
            -r __ns:=/$robot \
            2>&1 | tee $LOG_DIR/coord_${robot}.log
        exec bash
    "
done
sleep 3

# Start mock path publisher
echo "[6] Starting mock path publisher..."
MOCK_PATH_PY="${ROS2_WS}/src/fleet_gazebo/scripts/mock_path_publisher_all.py"

# Fallback if script doesn't exist at expected path
if [ ! -f "$MOCK_PATH_PY" ]; then
    MOCK_PATH_PY="${SCRIPT_DIR}/mock_path_publisher_all.py"
fi

screen -dmS mock_path bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    export PYTHONPATH=${ROS2_WS}/install/fleet_msgs/local/lib/python3.10/dist-packages:${ROS2_WS}/install/fleet_msgs/lib/python3.10/site-packages:${ROS2_WS}/install/fleet_coordination/lib/python3.10/site-packages:\$PYTHONPATH
    python3 ${MOCK_PATH_PY} ${ROBOTS[@]} \
        2>&1 | tee $LOG_DIR/mock_path.log
    exec bash
"
sleep 2

# Start data collection
echo "[7] Starting data collection..."
for robot in "${ROBOTS[@]}"; do
    screen -dmS topic_${robot} bash -c "
        source /opt/ros/humble/setup.bash
        source ${ROS2_WS}/install/setup.bash
        export ROS_DOMAIN_ID=0
        timeout ${DURATION}s ros2 topic echo /$robot/fleet/coordinator_status 2>&1 | tee $LOG_DIR/status_${robot}.log || true
        exec bash
    " &

    # Collect speed_limit if available (requires Nav2 BT running)
    screen -dmS speed_${robot} bash -c "
        source /opt/ros/humble/setup.bash
        source ${ROS2_WS}/install/setup.bash
        export ROS_DOMAIN_ID=0
        timeout ${DURATION}s ros2 topic echo /${robot}/speed_limit 2>&1 | tee $LOG_DIR/speed_${robot}.log || true
        exec bash
    " &
done

# Collect /fleet/yield if available
screen -dmS yield_fleet bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    timeout ${DURATION}s ros2 topic echo /fleet/yield 2>&1 | tee $LOG_DIR/yield.log || true
    exec bash
" &

echo ""
echo "=========================================="
echo "  Running Scenario: $SCENARIO"
echo "  Duration: ${DURATION}s"
echo "=========================================="
echo ""

# Wait for test duration
echo "[8] Running test for ${DURATION}s..."
sleep $DURATION

# Stop collectors
echo "[9] Stopping data collectors..."
killall -9 timeout 2>/dev/null || true
sleep 1

echo ""
echo "=========================================="
echo "  Test Complete - Generating Report"
echo "=========================================="

# Generate report
REPORT_FILE="$REPORT_DIR/S3-M3-scenario-test-report.md"

cat > "$REPORT_FILE" << RPTEOF
# S3-M3 Scenario Test Report

**Date**: $(date +%Y-%m-%d)
**Scenario**: $SCENARIO
**Duration**: ${DURATION}s
**Timestamp**: $TIMESTAMP

---

## Test Summary

| Item | Value |
|------|-------|
| Scenario | $SCENARIO |
| Duration | ${DURATION}s |
| Robots | ${#ROBOTS[@]} |
| Log Dir | $LOG_DIR |

---

## Scenario Configuration

- SCENARIO=$SCENARIO
- DURATION=$DURATION
- ROBOTS=${ROBOTS[@]}

---

## Coordinator Logs

### robot_a (last 30 lines)
\`\`\`
$(tail -30 $LOG_DIR/coord_robot_a.log 2>/dev/null || echo "No log")
\`\`\`

### robot_b (last 30 lines)
\`\`\`
$(tail -30 $LOG_DIR/coord_robot_b.log 2>/dev/null || echo "No log")
\`\`\`
RPTEOF

if [ ${#ROBOTS[@]} -gt 2 ]; then
cat >> "$REPORT_FILE" << RPTEOF

### robot_c (last 30 lines)
\`\`\`
$(tail -30 $LOG_DIR/coord_robot_c.log 2>/dev/null || echo "No log")
\`\`\`
RPTEOF
fi

cat >> "$REPORT_FILE" << RPTEOF

---

## Coordinator Status Logs

### robot_a (last 20 lines)
\`\`\`
$(tail -20 $LOG_DIR/status_robot_a.log 2>/dev/null || echo "No data")
\`\`\`

### robot_b (last 20 lines)
\`\`\`
$(tail -20 $LOG_DIR/status_robot_b.log 2>/dev/null || echo "No data")
\`\`\`
RPTEOF

if [ ${#ROBOTS[@]} -gt 2 ]; then
cat >> "$REPORT_FILE" << RPTEOF

### robot_c (last 20 lines)
\`\`\`
$(tail -20 $LOG_DIR/status_robot_c.log 2>/dev/null || echo "No data")
\`\`\`
RPTEOF
fi

cat >> "$REPORT_FILE" << RPTEOF

---

## Speed Limit Logs (last 20 lines)
\`\`\`
$(tail -20 $LOG_DIR/speed_robot_a.log 2>/dev/null || echo "No speed_limit data (Nav2 BT may not be running)")
\`\`\`

---

## Fleet Yield Log (last 20 lines)
\`\`\`
$(tail -20 $LOG_DIR/yield.log 2>/dev/null || echo "No yield data")
\`\`\`

---

## Mock Path Log (last 20 lines)
\`\`\`
$(tail -20 $LOG_DIR/mock_path.log 2>/dev/null || echo "No log")
\`\`\`

---

## Gazebo Log (last 30 lines)
\`\`\`
$(tail -30 $LOG_DIR/gazebo.log 2>/dev/null || echo "No log")
\`\`\`

---

## PASS/FAIL Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Gazebo started | $([ -f "$LOG_DIR/gazebo.log" ] && echo "PASS" || echo "FAIL") | $LOG_DIR/gazebo.log |
| Coordinators started | $(grep -q "fleet_coordinator\|Starting\|Initialized" $LOG_DIR/coord_robot_a.log 2>/dev/null && echo "PASS" || echo "FAIL") | coord_*.log |
| coordinator_status received | $(grep -q "NORMAL\|YIELDING\|CAUTION\|PASSING\|state" $LOG_DIR/status_robot_a.log 2>/dev/null && echo "PASS" || echo "FAIL") | status_*.log |
| No crashes | $(grep -q "Segmentation fault\|Aborted\|core dumped" $LOG_DIR/*.log 2>/dev/null && echo "FAIL" || echo "PASS") | *.log |

---

## State Transition Analysis

### robot_a observed states
\`\`\`
$(grep -oE "STATE_CHANGE:[^ ]+ [A-Z]+" $LOG_DIR/coord_robot_a.log 2>/dev/null | sort -u || echo "No STATE_CHANGE found")
\`\`\`

### robot_b observed states
\`\`\`
$(grep -oE "STATE_CHANGE:[^ ]+ [A-Z]+" $LOG_DIR/coord_robot_b.log 2>/dev/null | sort -u || echo "No STATE_CHANGE found")
\`\`\`

---

## Log Files Location

All logs saved to: $LOG_DIR/

- \`gazebo.log\` - Gazebo server output
- \`coord_*.log\` - Fleet coordinator logs
- \`status_*.log\` - coordinator_status topic echo
- \`speed_*.log\` - speed_limit topic echo (if Nav2 BT running)
- \`yield.log\` - /fleet/yield topic echo
- \`mock_path.log\` - Mock path publisher output

---

## Re-run Command

\`\`\`bash
bash ${ROS2_WS}/src/fleet_gazebo/scripts/run_m3_scenario_test.sh $SCENARIO $DURATION
\`\`\`

---

## Notes

- Report generated at: $(date)
- Test duration: ${DURATION}s
- Review coordinator logs for state transitions
RPTEOF

echo "Report saved to: $REPORT_FILE"

echo ""
echo "=========================================="
echo "  S3-M3 Test Complete"
echo "=========================================="
echo "Log directory: $LOG_DIR"
echo "Report: $REPORT_FILE"
echo ""
echo "To view logs:"
echo "  ls $LOG_DIR/"
echo "  tail -f $LOG_DIR/coord_robot_a.log"
echo ""