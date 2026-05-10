#!/bin/bash
# S3-M3: corridor-2robot + optional dual Nav2 (SLAM) + fleet coordinators + motion harness.
#
# Usage:
#   bash run_m3_nav2_e2e_yield.sh [duration_sec]
#
# Env:
#   WITH_NAV2  - 1: launch dual nav2 bringup + fleet BT YAML merge (default 1)
#   WITH_GOALS - 1: send NavigateToPose goals (default 1). Recommended when WITH_NAV2=1 so cmd_vel stays with Nav2.
#   BT_XML_MODE - fleet | default | goal_updated | conflict | speed (default: fleet)
#   NAV2_BT_XML - absolute BT XML override, takes precedence over BT_XML_MODE.
#   PATH_PROBE_TIMEOUT - per-robot ComputePathToPose probe timeout in seconds (default 45)
#   SAFETY_JUDGE - 1: run offline collision/deadlock/emergency judge at end (default 1)
#   SEND_GOAL_AMCL_TIMEOUT - AMCL pose wait for goal sender in seconds (default 45)
#
# Fleet-only motion (no Nav2):
#   WITH_NAV2=0 bash run_m3_nav2_e2e_yield.sh
# Logs: /tmp/fleet_test_nav2_e2e_yield_<timestamp>/
#
# Notes:
# - WITH_NAV2=1 does NOT publish test cmd_vel via move_robots_corridor_two.py (would fight Nav2). Use WITH_GOALS=1.
# - WITH_NAV2=0 starts the corridor_two mover harness (same class of test stimulus as legacy scripts).

# Do not use `set -u` before sourcing /opt/ros/humble/setup.bash: Bash 5.1+ treats
# unset vars as errors even inside `[ -n "$AMENT_TRACE_SETUP_FILES" ]`, which breaks
# the stock ament prefix setup.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Workspace root = .../ros2_ws (contains install/, src/). From this file: scripts -> fleet_gazebo -> src -> ws.
ROS2_WS="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DURATION=${1:-90}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR=/tmp/fleet_test_nav2_e2e_yield_${TIMESTAMP}
WITH_NAV2=${WITH_NAV2:-1}
WITH_GOALS=${WITH_GOALS:-1}
WITH_PATH_PROBES=${WITH_PATH_PROBES:-1}
SAFETY_JUDGE=${SAFETY_JUDGE:-1}
BT_XML_MODE=${BT_XML_MODE:-fleet}
PATH_PROBE_TIMEOUT=${PATH_PROBE_TIMEOUT:-45}
SEND_GOAL_AMCL_TIMEOUT=${SEND_GOAL_AMCL_TIMEOUT:-45}
ROBOT_A_GOAL_X=${ROBOT_A_GOAL_X:--1.0}
ROBOT_A_GOAL_Y=${ROBOT_A_GOAL_Y:-0.0}
ROBOT_A_GOAL_YAW=${ROBOT_A_GOAL_YAW:-0.0}
ROBOT_B_GOAL_X=${ROBOT_B_GOAL_X:-1.0}
ROBOT_B_GOAL_Y=${ROBOT_B_GOAL_Y:-0.0}
ROBOT_B_GOAL_YAW=${ROBOT_B_GOAL_YAW:-3.14159}

mkdir -p "$LOG_DIR"

source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger
# Resolve TurtleBot paths while only Humble is sourced (robust vs. thin workspace overlays).
TB3GZ_PREFIX=""
TB3GZ_PREFIX=$(ros2 pkg prefix turtlebot3_gazebo 2>/dev/null) || true
if [ -z "$TB3GZ_PREFIX" ] || [ ! -d "${TB3GZ_PREFIX}/share/turtlebot3_gazebo/models" ]; then
  TB3GZ_PREFIX="/opt/ros/humble"
fi
export GAZEBO_MODEL_PATH="${TB3GZ_PREFIX}/share/turtlebot3_gazebo/models"

TB3_PREFIX=""
TB3_PREFIX=$(ros2 pkg prefix turtlebot3_description 2>/dev/null) || true
if [ -z "$TB3_PREFIX" ] || [ ! -f "${TB3_PREFIX}/share/turtlebot3_description/urdf/turtlebot3_burger.urdf.xacro" ]; then
  TB3_PREFIX="/opt/ros/humble"
fi
TB3_XACRO_URDF="${TB3_PREFIX}/share/turtlebot3_description/urdf/turtlebot3_burger.urdf.xacro"
TB3_STATIC_URDF="${TB3GZ_PREFIX}/share/turtlebot3_gazebo/urdf/turtlebot3_burger.urdf"

echo "[0] Build check: source workspace"
if [ -f "${ROS2_WS}/install/setup.bash" ]; then
  # shellcheck source=/dev/null
  source "${ROS2_WS}/install/setup.bash"
else
  echo "ERROR: ${ROS2_WS}/install/setup.bash missing — run colcon build first"
  exit 1
fi

# Isolated/partial overlays may not chain every package prefix; use install tree directly.
PKG_SHARE="${ROS2_WS}/install/fleet_gazebo/share/fleet_gazebo"
if [ ! -d "${PKG_SHARE}/scripts" ]; then
  _fg_prefix=""
  _fg_prefix=$(ros2 pkg prefix fleet_gazebo 2>/dev/null) || true
  if [ -n "$_fg_prefix" ]; then
    PKG_SHARE="${_fg_prefix}/share/fleet_gazebo"
  fi
fi
if [ ! -f "${PKG_SHARE}/scripts/move_robots_corridor_two.py" ]; then
  echo "ERROR: fleet_gazebo scripts not found under ${PKG_SHARE}"
  exit 1
fi
MOVE_PY="${PKG_SHARE}/scripts/move_robots_corridor_two.py"
SEND_GOAL_PY="${PKG_SHARE}/scripts/send_nav2_goal.py"
COLLECTOR_PY="${PKG_SHARE}/scripts/collect_nav2_e2e_topics.py"
COMPUTE_PATH_PROBE_PY="${PKG_SHARE}/scripts/compute_path_probe.py"
SAFETY_JUDGE_PY="${PKG_SHARE}/scripts/judge_nav2_e2e_safety.py"
WRITE_CORRIDOR_MAP_PY="${PKG_SHARE}/scripts/write_corridor_map.py"
C2O_PY="${ROS2_WS}/src/fleet_coordination/fleet_coordination/cmd_vel_to_odom.py"
for helper in COLLECTOR_PY COMPUTE_PATH_PROBE_PY SAFETY_JUDGE_PY WRITE_CORRIDOR_MAP_PY; do
  helper_path="${!helper}"
  if [ ! -f "$helper_path" ]; then
    helper_name="$(basename "$helper_path")"
    helper_src="${SCRIPT_DIR}/${helper_name}"
    if [ -f "$helper_src" ]; then
      printf -v "$helper" '%s' "$helper_src"
    fi
  fi
done

cleanup_screens() {
  screen -ls 2>/dev/null | awk '
    match($1, /\.(gaz|mover|mock_path|nav2_ra|nav2_rb|goal_a|goal_b|rsp_robot_a|rsp_robot_b|coord_robot_a|coord_robot_b|c2o_robot_a|c2o_robot_b|e2e_collector|eco_yield|eco_status_robot_a|eco_status_robot_b|eco_sl_robot_a|eco_sl_robot_b)$/) {
      print $1
    }' | while read -r session; do
      [ -n "$session" ] || continue
      screen -S "$session" -X quit 2>/dev/null || true
    done
}

cleanup() {
  echo "[CLEANUP] Stopping scenario processes..."
  cleanup_screens
  pkill -f "gzserver" 2>/dev/null || true
  pkill -f "fleet_coordinator" 2>/dev/null || true
  pkill -f "robot_state_publisher" 2>/dev/null || true
  pkill -f "mock_path_publisher" 2>/dev/null || true
  pkill -f "robot_mover_corridor_two" 2>/dev/null || true
  pkill -f "nav2_container" 2>/dev/null || true
  pkill -f "cmd_vel_to_odom" 2>/dev/null || true
  pkill -f "send_nav2_goal.py" 2>/dev/null || true
  cleanup_screens
  screen -wipe 2>/dev/null || true
}

trap cleanup EXIT

echo "[PRE-CLEANUP] Removing stale scenario processes before start"
cleanup
sleep 2

echo "LOG_DIR=$LOG_DIR"
echo "WITH_NAV2=$WITH_NAV2 WITH_GOALS=$WITH_GOALS WITH_PATH_PROBES=$WITH_PATH_PROBES DURATION=$DURATION"
echo "SAFETY_JUDGE=$SAFETY_JUDGE"
echo "BT_XML_MODE=$BT_XML_MODE NAV2_BT_XML=${NAV2_BT_XML:-}"
echo "PATH_PROBE_TIMEOUT=${PATH_PROBE_TIMEOUT}s"
echo "SEND_GOAL_AMCL_TIMEOUT=${SEND_GOAL_AMCL_TIMEOUT}s"
echo "GOALS robot_a=(${ROBOT_A_GOAL_X}, ${ROBOT_A_GOAL_Y}, ${ROBOT_A_GOAL_YAW}) robot_b=(${ROBOT_B_GOAL_X}, ${ROBOT_B_GOAL_Y}, ${ROBOT_B_GOAL_YAW})"

echo "[1] Merge Nav2 params with fleet BT plugins"
fleet_merge_nav2_fleet_params "${LOG_DIR}/nav2_robot_a.yaml" robot_a
fleet_merge_nav2_fleet_params "${LOG_DIR}/nav2_robot_b.yaml" robot_b

echo "[1b] Generate corridor occupancy map aligned with corridor.world"
python3 "${WRITE_CORRIDOR_MAP_PY}" "${LOG_DIR}"
MAP_YAML="${LOG_DIR}/corridor_map.yaml"

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
PYEOF
}

mkdir -p /tmp/robot_sdf
for r in robot_a robot_b; do prepare_robot_sdf "$r"; done

WORLD="${ROS2_WS}/install/fleet_gazebo/share/fleet_gazebo/worlds/corridor.world"
if [ ! -f "$WORLD" ]; then
  echo "WARN: corridor world missing at $WORLD — falling back to empty world"
  WORLD=/opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world
fi

echo "[2] Start Gazebo"
screen -dmS gaz bash -c "gzserver --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so $WORLD 2>&1 | tee $LOG_DIR/gazebo.log; exec bash"
sleep 8

echo "[3] Spawn robots"
ros2 run gazebo_ros spawn_entity.py -entity robot_a -file /tmp/robot_sdf/robot_a.sdf \
  -x -4.0 -y 0.0 -z 0.01 -Y 0.0 -robot_namespace robot_a
sleep 1
ros2 run gazebo_ros spawn_entity.py -entity robot_b -file /tmp/robot_sdf/robot_b.sdf \
  -x 4.0 -y 0.0 -z 0.01 -Y 3.14159 -robot_namespace robot_b
sleep 2

echo "[4] robot_state_publisher (burger URDF)"
if [ -f "$TB3_XACRO_URDF" ] && command -v xacro >/dev/null 2>&1 && xacro "$TB3_XACRO_URDF" > "$LOG_DIR/burger.urdf"; then
  true
elif [ -f "$TB3_XACRO_URDF" ] && ros2 run xacro xacro "$TB3_XACRO_URDF" > "$LOG_DIR/burger.urdf" 2>/dev/null; then
  true
elif [ -f "$TB3_STATIC_URDF" ]; then
  echo "[4] WARN: xacro not available; using turtlebot3_gazebo static turtlebot3_burger.urdf (install ros-humble-xacro for xacro path)"
  cp -f "$TB3_STATIC_URDF" "$LOG_DIR/burger.urdf"
else
  echo "ERROR: need turtlebot3 burger URDF (xacro: ${TB3_XACRO_URDF} or static: ${TB3_STATIC_URDF})"
  exit 1
fi
WRITE_RSP_PY="${PKG_SHARE}/scripts/write_rsp_params.py"
for ns in robot_a robot_b; do
  python3 ${WRITE_RSP_PY} ${LOG_DIR} ${ns}
  screen -dmS rsp_${ns} bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    ros2 run robot_state_publisher robot_state_publisher --ros-args \
      -r /tf:=/${ns}/tf \
      -r /tf_static:=/${ns}/tf_static \
      --params-file ${LOG_DIR}/rsp_${ns}.yaml \
      2>&1 | tee $LOG_DIR/rsp_${ns}.log
    exec bash"
  sleep 0.5
done

COORDINATOR_BIN="${ROS2_WS}/install/fleet_coordination/lib/fleet_coordination/fleet_coordinator"
if [ ! -x "$COORDINATOR_BIN" ]; then
  COORDINATOR_BIN="${ROS2_WS}/install/fleet_coordination/bin/fleet_coordinator"
fi

echo "[5] Fleet coordinators"
for robot in robot_a robot_b; do
  peers=$([ "$robot" = robot_a ] && echo robot_b || echo robot_a)
  screen -dmS coord_${robot} bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    ${COORDINATOR_BIN} --ros-args -p robot_id:=${robot} -p peer_ids:=[${peers}] -r __ns:=/${robot} \
      2>&1 | tee $LOG_DIR/coord_${robot}.log
    exec bash"
done
sleep 3

echo "[6] mock_path_publisher"
screen -dmS mock_path bash -c "
  source /opt/ros/humble/setup.bash
  source ${ROS2_WS}/install/setup.bash
  export ROS_DOMAIN_ID=0
  export PYTHONPATH=${ROS2_WS}/install/fleet_msgs/local/lib/python3.10/dist-packages:${ROS2_WS}/install/fleet_msgs/lib/python3.10/site-packages:${ROS2_WS}/install/fleet_coordination/lib/python3.10/site-packages:\$PYTHONPATH
  python3 ${SCRIPT_DIR}/mock_path_publisher_all.py robot_a robot_b 2>&1 | tee $LOG_DIR/mock_path.log
  exec bash"
sleep 2

if [ "$WITH_NAV2" = "1" ]; then
  # Start cmd_vel_to_odom BEFORE Nav2 so odom->base_footprint TF is available
  # when Nav2 controller_server starts. This is a Gazebo/namespace workaround.
  echo "[6b] cmd_vel_to_odom (odom TF workaround for Gazebo)"
  CMD_VEL_TO_ODOM="${ROS2_WS}/install/fleet_coordination/lib/fleet_coordination/cmd_vel_to_odom"
  for robot in robot_a robot_b; do
    screen -dmS c2o_${robot} bash -c "
      source /opt/ros/humble/setup.bash
      source ${ROS2_WS}/install/setup.bash
      export ROS_DOMAIN_ID=0
      python3 ${C2O_PY} ${robot} --ros-args \
        -r /tf:=/${robot}/tf \
        -r /tf_static:=/${robot}/tf_static \
        2>&1 | tee $LOG_DIR/cmd_vel_to_odom_${robot}.log
      exec bash"
    sleep 0.5
  done
  sleep 1

  echo "[7] Nav2 bringup (AMCL) x2 — params ${LOG_DIR}/nav2_robot_{a,b}.yaml"
  screen -dmS nav2_ra bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    ros2 launch nav2_bringup bringup_launch.py \
      slam:=False use_sim_time:=True \
      map:=${MAP_YAML} \
      namespace:=robot_a use_namespace:=True \
      params_file:=${LOG_DIR}/nav2_robot_a.yaml \
      autostart:=true use_composition:=False \
      2>&1 | tee $LOG_DIR/nav2_robot_a.log
    exec bash"
  sleep 2
  screen -dmS nav2_rb bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    ros2 launch nav2_bringup bringup_launch.py \
      slam:=False use_sim_time:=True \
      map:=${MAP_YAML} \
      namespace:=robot_b use_namespace:=True \
      params_file:=${LOG_DIR}/nav2_robot_b.yaml \
      autostart:=true use_composition:=False \
      2>&1 | tee $LOG_DIR/nav2_robot_b.log
    exec bash"
  sleep 6
else
  echo "[7] Skipping Nav2 (WITH_NAV2=0)"
fi

if [ "$WITH_NAV2" = "1" ] && [ "$WITH_PATH_PROBES" = "1" ]; then
  echo "[7b] ComputePathToPose probes"
  timeout "${PATH_PROBE_TIMEOUT}s" python3 "${COMPUTE_PATH_PROBE_PY}" robot_a \
    --start-x -4.0 --start-y 0.0 --start-yaw 0.0 \
    --goal current:0.0:0.0:0.0 \
    --goal reachable:${ROBOT_A_GOAL_X}:${ROBOT_A_GOAL_Y}:${ROBOT_A_GOAL_YAW} \
    --goal corridor_far:1.0:0.0:0.0 \
    > "${LOG_DIR}/compute_path_robot_a.log" 2>&1 || true
  timeout "${PATH_PROBE_TIMEOUT}s" python3 "${COMPUTE_PATH_PROBE_PY}" robot_b \
    --start-x 4.0 --start-y 0.0 --start-yaw 3.14159 \
    --goal current:0.0:0.0:3.14159 \
    --goal reachable:${ROBOT_B_GOAL_X}:${ROBOT_B_GOAL_Y}:${ROBOT_B_GOAL_YAW} \
    --goal corridor_far:-1.0:0.0:3.14159 \
    > "${LOG_DIR}/compute_path_robot_b.log" 2>&1 || true
fi

if [ "$WITH_NAV2" = "0" ]; then
  echo "[8] Motion harness — cmd_vel (fleet-only)"
  screen -dmS mover bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    export PYTHONPATH=${ROS2_WS}/install/fleet_msgs/local/lib/python3.10/dist-packages:${ROS2_WS}/install/fleet_msgs/lib/python3.10/site-packages:${ROS2_WS}/install/fleet_coordination/lib/python3.10/site-packages:\$PYTHONPATH
    python3 ${MOVE_PY} 2>&1 | tee $LOG_DIR/mover.log
    exec bash"
  sleep 2
else
  echo "[8] Skipping cmd_vel mover (Nav2 mode). Set WITH_NAV2=0 for fleet-only harness."
fi

if [ "$WITH_NAV2" = "1" ] && [ "$WITH_GOALS" = "1" ]; then
  echo "[9] Firing Nav2 goals (simple commander) after warmup"
  screen -dmS goal_a bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    sleep 5
    python3 ${SEND_GOAL_PY} robot_a ${ROBOT_A_GOAL_X} ${ROBOT_A_GOAL_Y} ${ROBOT_A_GOAL_YAW} \
      --amcl-timeout ${SEND_GOAL_AMCL_TIMEOUT} \
      --initial-x -4.0 --initial-y 0.0 --initial-yaw 0.0 \
      2>&1 | tee $LOG_DIR/goal_robot_a.log || true
    exec bash"
  screen -dmS goal_b bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export ROS_DOMAIN_ID=0
    sleep 7
    python3 ${SEND_GOAL_PY} robot_b ${ROBOT_B_GOAL_X} ${ROBOT_B_GOAL_Y} ${ROBOT_B_GOAL_YAW} \
      --amcl-timeout ${SEND_GOAL_AMCL_TIMEOUT} \
      --initial-x 4.0 --initial-y 0.0 --initial-yaw 3.14159 \
      2>&1 | tee $LOG_DIR/goal_robot_b.log || true
    exec bash"
fi

echo "[10] Topic collectors (${DURATION}s)"
COLLECTOR_DURATION=$DURATION
if [ "$DURATION" -gt 5 ]; then
  COLLECTOR_DURATION=$((DURATION - 3))
fi
screen -dmS e2e_collector bash -c "
    source /opt/ros/humble/setup.bash
    source ${ROS2_WS}/install/setup.bash
    export PYTHONPATH=${ROS2_WS}/install/fleet_msgs/local/lib/python3.10/dist-packages:${ROS2_WS}/install/fleet_msgs/lib/python3.10/site-packages:\$PYTHONPATH
    python3 ${COLLECTOR_PY} --duration ${COLLECTOR_DURATION} --output-dir $LOG_DIR 2>&1 | tee $LOG_DIR/collector.log || true
    exec bash" &

sleep "$DURATION"
if [ "$SAFETY_JUDGE" = "1" ]; then
  echo "[10b] Offline safety judge"
  set +e
  python3 "${SAFETY_JUDGE_PY}" \
    --log-dir "${LOG_DIR}" \
    --json-out "${LOG_DIR}/safety_judge.json" \
    > "${LOG_DIR}/safety_judge.log" 2>&1
  judge_rc=$?
  set -e
  cat "${LOG_DIR}/safety_judge.log"
  echo "$judge_rc" > "${LOG_DIR}/safety_judge.exit_code"
  if [ "$judge_rc" -ne 0 ]; then
    echo "ERROR: safety judge failed with exit code ${judge_rc}"
    exit "$judge_rc"
  fi
fi
echo "[11] Done. Logs under $LOG_DIR"
echo "Review: grep -E 'published speed_limit|YIELDING|Yield|fleet_state' $LOG_DIR/*.log"
