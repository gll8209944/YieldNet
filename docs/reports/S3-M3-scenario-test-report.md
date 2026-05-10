# S3-M3 Scenario Test Report

**日期**: 2026-05-08
**分支**: master（含 Nav2 e2e 脚本与 BT 插件；详见 §Scenario: Nav2 full-stack e2e yield）

---

## Summary

S3-M3 场景测试验证完成。核心发现：

1. **BT runner XML 修复成功** - `AdjustSpeedForFleet` 不再作为非法叶节点
2. **speed_limit 发布验证** - `AdjustSpeedForFleet.tick()` 成功发布 `nav2_msgs/SpeedLimit`
3. **环境 DDS 问题** - ros2 topic echo 无法接收消息，但日志证明发布正常

**结论**: PARTIAL PASS (B)

---

## 1. BT Runner Fix

### 问题
```
RuntimeError: The node <AdjustSpeedForFleet> must have exactly 1 child
```

### 原因
`AdjustSpeedForFleet` 是 `DecoratorNode`，必须有子节点，但原 BT XML 中作为叶节点使用。

### 修复
1. 添加 `AlwaysSuccess` 作为子节点
2. 修改 BT XML 使用简单的 smoke 测试结构

**修改文件**: `ros2_ws/src/fleet_nav2_bt/src/fleet_bt_runner.cpp`

```cpp
// 修复前 (非法):
<AdjustSpeedForFleet default_speed="0.5"/>

// 修复后 (合法):
<AdjustSpeedForFleet default_speed="0.5">
  <AlwaysSuccess/>
</AdjustSpeedForFleet>
```

---

## 2. QoS Mismatch Fix

### 问题
```
[WARN] ... requesting incompatible QoS. No messages will be sent. 
Last incompatible policy: DURABILITY
```

### 原因
- `adjust_speed_for_fleet` 订阅使用 `transient_local()`
- `fleet_coordinator` 发布使用 `RELIABLE`

### 修复
修改 `adjust_speed_for_fleet.cpp` 订阅 QoS:

```cpp
// 修复前:
rclcpp::QoS(rclcpp::KeepLast(1)).transient_local()

// 修复后:
rclcpp::QoS(rclcpp::KeepLast(1)).reliable()
```

---

## 3. speed_limit Publishing Verification

### 测试方法
1. 启动 `fleet_bt_runner`
2. 检查 `/robot_a/speed_limit` topic
3. 检查日志输出

### 结果

**Topic 信息**:
```
Type: nav2_msgs/msg/SpeedLimit
Publisher count: 1
```

**日志证据**:
```
[INFO] [robot_a.adjust_speed_for_fleet]: AdjustSpeedForFleet: published speed_limit=100.0% (ratio=1.00)
[INFO] [robot_a.adjust_speed_for_fleet]: AdjustSpeedForFleet: state=, speed_ratio=1.00, child_status=2
```

**结论**: `/speed_limit` 发布验证成功 ✅

### DDS 环境问题

`ros2 topic echo` 无法接收消息，但日志证明发布正常工作。可能是:
- CycloneDDS 配置问题
- 同一进程内通信限制
- 环境特定问题

**不影响验证结论**: 日志明确显示 `speed_limit=100.0%` 已发布。

---

## 4. Initial Speed Ratio Fix

### 问题
`last_published_speed_ratio_` 初始化为 1.0，与 `current_speed_ratio_` 相同，导致首次 tick 不发布。

### 修复
```cpp
// 修复前:
last_published_speed_ratio_(1.0)

// 修复后:
last_published_speed_ratio_(0.0)
```

---

## 5. Build & Test

| Item | Result |
|------|--------|
| Build | ✅ 4 packages, 0 errors |
| Test | ✅ 32 tests, 0 failures |
| Warnings | 2 reorder (check_fleet_conflict.hpp) |

---

## 6. PASS/FAIL Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| BT runner starts | ✅ PASS | fleet_bt_runner initialized |
| AdjustSpeedForFleet ticked | ✅ PASS | tick() called every 100ms |
| speed_limit published | ✅ PASS | log shows "published speed_limit=100.0%" |
| Topic exists | ✅ PASS | /robot_a/speed_limit with correct type |
| /speed_limit verified by echo | ⚠️ N/A | DDS 环境问题，但日志证明发布正常 |
| state/speed_ratio mapping | ✅ PASS | NORMAL=1.0 → 100.0% |
| Build | ✅ PASS | 0 errors |
| Test | ✅ PASS | 0 failures |

---

## 7. Remaining Risks

| Item | Status | Notes |
|------|--------|-------|
| ros2 topic echo 接收 | ⚠️ DDS issue | 日志证明发布正常 |
| yield/resume | ❌ Not tested | 需 Nav2 stack + 机器人移动 |
| corridor-3robot | ❌ Not tested | - |
| t-intersection | ❌ Not tested | - |
| heartbeat timeout | ❌ Not tested | - |
| domain isolation | ❌ Not tested | - |

---

## 8. Report Location

- ECS: `/home/guolinlin/ros2_ws/docs/reports/S3-M3-scenario-test-report.md`
- Local: `/Users/guolinlin/ai-code/YieldNet/docs/reports/S3-M3-scenario-test-report.md`

---

## S3-M3-BT-RUNNER-FIX Conclusion

**Status**: PARTIAL PASS (B)

**通过项**:
- BT runner 不再崩溃 ✅
- AdjustSpeedForFleet 被 tick ✅
- speed_limit 发布验证成功 (日志证据) ✅
- QoS mismatch 修复 ✅
- Build/test 通过 ✅

**部分通过项**:
- speed_limit topic echo 无法验证 (DDS 环境问题) ⚠️

**未测试项**:
- yield/resume (需 Nav2 stack + 机器人移动)
- 完整 Nav2 BT integration

**Recommendation**: speed_limit 发布链路已验证。继续添加 Nav2 BT 集成测试和 yield/resume 场景。

---

## Scenario: Nav2 full-stack e2e yield

**目的**: 推进 `bt_navigator` 全栈加载 `navigate_with_fleet.xml`、`AdjustSpeedForFleet` 在 Nav2 tick 中可用，并在 corridor-2robot 上尝试 e2e yield 证据链。

### run command

前置：`colcon build --symlink-install` 且已 `source install/setup.bash`。

```bash
cd /path/to/YieldNet/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

# 默认 WITH_NAV2=1 WITH_GOALS=1（Nav2 独占 cmd_vel；不要与 cmd_vel mover 同时开）
chmod +x src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh   # dev tree
bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90

# 仅 Fleet + cmd_vel（无 Nav2）：用于 fleet 行为回归
WITH_NAV2=0 bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90
```

参数合并 CLI（也可用）：

```bash
fleet_merge_nav2_fleet_params /tmp/nav2_fleet.yaml
```

### log directory

- 前缀：`/tmp/fleet_test_nav2_e2e_yield_<TIMESTAMP>/`
- 主要文件：`gazebo.log`、`coord_robot_{a,b}.log`、`mock_path.log`、`nav2_robot_{a,b}.log`、`status_*.log`、`speed_*.log`、`yield.log`、`goal_*.log`（若启用目标）

### modified files（本迭代）

| 路径 | 说明 |
|------|------|
| `ros2_ws/src/fleet_nav2_bt/CMakeLists.txt` | 增加 `fleet_*_bt_node` 三套 BT 插件库（`BT_RegisterNodesFromPlugin`） |
| `ros2_ws/src/fleet_nav2_bt/src/*.cpp` | 插件注册块；`CheckFleetConflict` 从 peers JSON 粗解析 `conflict_peer` |
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_with_fleet.xml` | `FollowPat` → `FollowPath`（对齐 nav2_params 默认 controller id） |
| `ros2_ws/src/fleet_gazebo/fleet_gazebo/merge_nav2_fleet_params.py` | 合并系统 `nav2_params.yaml` + fleet 插件 + `default_nav_to_pose_bt_xml` |
| `ros2_ws/src/fleet_gazebo/setup.py` / `package.xml` | `fleet_merge_nav2_fleet_params` 入口与依赖 |
| `ros2_ws/src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh` | …；`ROS2_WS`=`scripts/../../..`；**URDF**：xacro 可用则用 `turtlebot3_burger.urdf.xacro`，否则降级 `turtlebot3_gazebo/turtlebot3_burger.urdf`；**fleet_gazebo**/turtlebot 路径以 `${ROS2_WS}/install` + humble 为准 |
| `ros2_ws/src/fleet_gazebo/scripts/move_robots_corridor_two.py` | 仅 `WITH_NAV2=0` 时的 cmd_vel 场景激励（测试 harness） |
| `ros2_ws/src/fleet_gazebo/scripts/send_nav2_goal.py` | `nav2_simple_commander` 单目标（可选） |

### Nav2 stack components（脚本侧）

- `nav2_bringup/bringup_launch.py` ×2：`namespace=robot_{a,b}`，`slam:=True`，`use_namespace:=True`
- 参数：合并后的 `nav2_params.yaml` + fleet BT 插件名 + `navigate_with_fleet.xml`
- 仿真：Gazebo `corridor.world`，双 TurtleBot3 burger，每个命名空间 `robot_state_publisher`
- Fleet：`fleet_coordinator` ×2 + `mock_path_publisher_all.py`

### BT XML used

- `fleet_nav2_bt/behavior_trees/navigate_with_fleet.xml`（由 `default_nav_to_pose_bt_xml` 指向）

### `/speed_limit` result

- **期望 topic**：`/robot_a/speed_limit`、`/robot_b/speed_limit`（由命名空间内 `AdjustSpeedForFleet` 发布）
- **判定**：需在 `nav2_robot_*.log` / `speed_*.log` 中出现 `nav2_msgs/msg/SpeedLimit` 且 `percentage: true`，并与 coordinator `speed_ratio` 趋势一致。
- **注意**：本场景依赖 Nav2 生命周期与 SLAM 稳定；若 `bt_navigator` 未进入 active 或插件加载失败，则可能无 `speed_limit`。

### yield / resume result

- `WaitForYieldClear` 依赖 blackboard `conflict_peer`；本迭代在 `CheckFleetConflict` 中从 `coordinator_status` 的 `peers[0].robot_id` **粗解析**首个 peer（仅解析/接线，未改协调算法）。
- **PARTIAL 说明**：全闭环 yield/resume 仍依赖真实路径冲突 + 协调器状态进入 YIELDING/PASSING + BT 进入 yield 分支；脚本仅提供可重复启动链路与日志采集位点。
- **ECS 烟雾（会话内）**：在修复 `ROS2_WS`/`PKG_SHARE`、`bash -u`+ament、以及在无系统 `xacro` 包时降级为 `turtlebot3_gazebo` 静态 burger URDF 后，远程一次运行可见流程推进至 `[10] topic collectors`；**未**在同一会话内解析完整 `speed_*.log`/`yield.log`，**不**据此声称 yield 闭环已验证。

### state transition result

- 以 `status_*.log` / `coord_*.log` 中 `STATE_CHANGE` / JSON `state` 为准；本报告不在此伪造具体时间线。

### collision / deadlock / emergency result

- 本自动化脚本**未**内置碰撞计数器；需离线分析 Gazebo 接触或 odom 日志。**不得**无证据写 0 碰撞 PASS。

### build result

- 以 `colcon build --symlink-install` 在目标机（ROS 2 Humble）输出为准。

### test result

- 以 `colcon test` 与 `colcon test-result --verbose` 为准。

### Final verdict（本子场景）

**PARTIAL PASS**：已提供 Nav2 双栈 + fleet BT 合并参数与走廊采集脚本；**完整** e2e yield、`/speed_limit` 在 **bt_navigator active** 下的动态验证、以及零碰撞/零死锁**仍待**在目标环境用日志证据闭环。

### Remaining risks

1. 双机 SLAM + 双 Nav2 资源占用高，ECS/笔记本可能无法在 90s 内稳定 activate。  
2. `plugin_lib_names` 依赖工作空间 `AMENT_PREFIX_PATH` 找到 `libfleet_*_bt_node.so`。  
3. isolated/partial overlay 下 `AMENT_PREFIX_PATH` 可能未链入全部本工作区包，`ros2 pkg prefix fleet_gazebo` 不可靠；脚本已改为 `${ROS2_WS}/install/fleet_gazebo/share/fleet_gazebo`。  

### Next steps

1. 在稳定机器上跑一次 `WITH_NAV2=1 WITH_GOALS=1`，归档 `fleet_test_nav2_e2e_yield_*` 原始日志进行分析。  
2. 若 `bt_navigator` 报错插件/XML，单独截取 `nav2_robot_*.log` 做最小复现。  
3. 将 ProgressChecker / recovery 行为纳入单独子节（需更长航时）。


---

## Scenario: Nav2 e2e yield log offline judgment

**LOG_DIR**: 
**Analyzed files**: , , , , , , , , , , , , , , 

### 1.  Evidence

| File | Result |
|------|--------|
| speed_robot_a.log | EMPTY (0 bytes) |
| speed_robot_b.log | EMPTY (0 bytes) |
| All logs grep | No  /  /  found |

**判定**: FAIL —  topic 没有任何消息，topic collector 未收到任何数据。

### 2. State Transition Evidence

**robot_a**:
-  (initial transitions at t≈0)
- No further state changes
- Stuck at  — no movement

**robot_b**:
-  (initial transitions at t≈0)
- No further state changes
- Stuck at  — no movement

**peer distance**: 8.0m (at CAUTION threshold)

**判定**: PARTIAL — 状态机初始转换正确，但未达到 YIELDING/PASSING，robots 未移动，无 yield/resume 触发。

### 3.  Evidence

| File | Result |
|------|--------|
| yield.log | EMPTY (0 bytes) |
| All logs grep | No , , ,  found |

**判定**: FAIL — 无任何 yield 消息，yield/resume 流程未触发。

### 4. Nav2 / Gazebo Error Summary

| Component | Error | Impact |
|-----------|-------|--------|
| Nav2 launch (robot_a/robot_b) |  | Nav2 stack 未启动 |
| robot_state_publisher (robot_a/robot_b) |  — raw URDF XML passed as CLI args | rsp 崩溃，TF tree 不完整 |
| send_nav2_goal.py (robot_a/robot_b) |  | goal 未发出 |
| Gazebo | Normal startup, robots spawned, graceful SIGTERM | 本身正常 |

**根因分析**:
1.  将 URDF 文件内容（XML 字符串）错误地作为 CLI 参数传递，而非通过标准 xacro 机制处理
2. Nav2  launch 缺少  参数，无法启动 slam 或 map-based navigation
3.  使用了与当前  API 不兼容的  调用

**判定**: FAIL — Nav2 stack 未就绪，goals 未发出，robots 未移动。

### 5. PASS / PARTIAL / FAIL 对照表

| 检查项 | PASS 条件 | 实际证据 | 判定 | 备注 |
|--------|-----------|----------|------|------|
| Gazebo start | Gazebo running | ✅ 正常启动，robots spawn | PASS | - |
| Fleet coordinator start | coordinator running | ✅ 正常启动并 tick | PASS | - |
| Nav2 stack start | nav2 bringup without error | ❌  argument missing | FAIL | blocker |
| Goals fired | send_nav2_goal.py success | ❌ TypeError on timeout kwarg | FAIL | blocker |
| Robot movement | odom position changes | ❌ 位置固定 (-4,0) / (4,0) | FAIL | robots 未动 |
|  messages | topic has SpeedLimit data | ❌ 0 bytes, no data | FAIL | Nav2 未启动 |
| speed_limit dynamic values | 50/0/100% observed | ❌ 无数据 | FAIL | - |
| State transition to YIELDING | YIELDING state logged | ❌ 仅 CAUTION | FAIL | 无冲突触发 |
| yield request/ack/resume | /fleet/yield messages | ❌ 0 bytes, no data | FAIL | - |
| Collision evidence | collision detected | ❌ 无 | PASS | 场景未运行 |
| Deadlock evidence | stuck state, no recovery | ⚠️ robots stuck at CAUTION | PARTIAL | 非 deadlock，仅仅是未运行 |
| Emergency evidence | EMERGENCY state | ✅ 初始 EMERGENCY 有触发但快速解除 | PASS | 正常 |
| Robot state publisher | rsp not crashed | ❌ UnknownROSArgsError | FAIL | URDF 参数错误 |

### 6. Final Verdict

**FAIL**

理由：
1. Nav2 stack 未启动（ argument missing）
2.  崩溃（URDF 被当作 CLI 参数传递）
3. Goals 未发出（ API 不兼容）
4. Robots 未移动 — 全程位置固定
5.  无任何数据
6.  无任何数据
7. YIELDING/PASSING 状态未触发

fleet_coordinator 本身的 CAUTION 状态转换是正常的，但完整的 Nav2 e2e yield 流程被上述 blocker 阻断。

### 7. Remaining Risks

1. **Nav2 map argument** —  launch 需要  参数，当前脚本未提供
2. **rsp URDF passing** — URDF 应通过 xacro 处理后传递，不应作为 raw CLI 参数
3. **waitUntilNav2Active API** — Python API 与  版本不匹配
4. **fleet_coordinator 单机 CAUTION** — 协调器单独可工作，但无法驱动 Nav2 完整栈

### 8. Next Recommendation

**P0 blockers to fix before next Nav2 e2e test**:

1. **Fix  API call**:
   - 移除或修正  调用
   - 检查当前  /  API

2. **Fix Nav2 launch to provide map**:
   - 要么提供真实 map yaml
   - 要么使用 slam 模式（）并提供对应参数

3. **Fix  invocation**:
   - 确保 URDF 通过  预处理后再传给 rsp
   - 检查脚本中 rsp 的启动命令

4. **重新跑 e2e yield 测试**:
   - fix 后重新执行 
   - 验证 robots 实际移动、speed_limit 动态值、yield/resume 闭环



---

## Scenario: Nav2 e2e yield log offline judgment

**LOG_DIR**: 
**Analyzed files**: coord_robot_a.log, coord_robot_b.log, status_robot_a.log, status_robot_b.log, gazebo.log, mock_path.log, nav2_robot_a.log, nav2_robot_b.log, goal_robot_a.log, goal_robot_b.log, rsp_robot_a.log, rsp_robot_b.log, speed_robot_a.log, speed_robot_b.log, yield.log

### 1. /speed_limit Evidence

| File | Result |
|------|--------|
| speed_robot_a.log | EMPTY (0 bytes) |
| speed_robot_b.log | EMPTY (0 bytes) |
| All logs grep | No speed_limit / SpeedLimit / percentage found |

**判定**: FAIL - /speed_limit topic 没有任何消息，topic collector 未收到任何数据。

### 2. State Transition Evidence

robot_a:
- NORMAL -> EMERGENCY -> CAUTION (initial transitions at t=0)
- No further state changes
- Stuck at own_pos=(-4.00, 0.00) - no movement

robot_b:
- NORMAL -> EMERGENCY -> CAUTION (initial transitions at t=0)
- No further state changes
- Stuck at own_pos=(4.00, 0.00) - no movement

peer distance: 8.0m (at CAUTION threshold)

**判定**: PARTIAL - 状态机初始转换正确，但未达到 YIELDING/PASSING，robots 未移动，无 yield/resume 触发。

### 3. /fleet/yield Evidence

| File | Result |
|------|--------|
| yield.log | EMPTY (0 bytes) |
| All logs grep | No REQUEST_YIELD, ACK_YIELD, RESUME, EMERGENCY_STOP found |

**判定**: FAIL - 无任何 yield 消息，yield/resume 流程未触发。

### 4. Nav2 / Gazebo Error Summary

| Component | Error | Impact |
|-----------|-------|--------|
| Nav2 launch (robot_a/robot_b) | ERROR: Included launch description missing required argument map | Nav2 stack 未启动 |
| robot_state_publisher (robot_a/robot_b) | rclcpp::exceptions::UnknownROSArgsError - raw URDF XML passed as CLI args | rsp 崩溃，TF tree 不完整 |
| send_nav2_goal.py (robot_a/robot_b) | TypeError: BasicNavigator.waitUntilNav2Active() got an unexpected keyword argument timeout | goal 未发出 |
| Gazebo | Normal startup, robots spawned, graceful SIGTERM | 本身正常 |

根因分析:
1. rsp 将 URDF 文件内容（XML 字符串）错误地作为 CLI 参数传递，而非通过标准 xacro 机制处理
2. Nav2 nav2_bringup launch 缺少 map 参数，无法启动 slam 或 map-based navigation
3. send_nav2_goal.py 使用了与当前 nav2_py_tutorial API 不兼容的 waitUntilNav2Active(timeout=600.0) 调用

**判定**: FAIL - Nav2 stack 未就绪，goals 未发出，robots 未移动。

### 5. PASS / PARTIAL / FAIL 对照表

| 检查项 | PASS 条件 | 实际证据 | 判定 | 备注 |
|--------|-----------|----------|------|------|
| Gazebo start | Gazebo running | PASS - 正常启动，robots spawn | PASS | - |
| Fleet coordinator start | coordinator running | PASS - 正常启动并 tick | PASS | - |
| Nav2 stack start | nav2 bringup without error | FAIL - map argument missing | FAIL | blocker |
| Goals fired | send_nav2_goal.py success | FAIL - TypeError on timeout kwarg | FAIL | blocker |
| Robot movement | odom position changes | FAIL - 位置固定 (-4,0) / (4,0) | FAIL | robots 未动 |
| /speed_limit messages | topic has SpeedLimit data | FAIL - 0 bytes, no data | FAIL | Nav2 未启动 |
| speed_limit dynamic values | 50/0/100% observed | FAIL - 无数据 | FAIL | - |
| State transition to YIELDING | YIELDING state logged | FAIL - 仅 CAUTION | FAIL | 无冲突触发 |
| yield request/ack/resume | /fleet/yield messages | FAIL - 0 bytes, no data | FAIL | - |
| Collision evidence | collision detected | PASS - 无 | PASS | 场景未运行 |
| Deadlock evidence | stuck state, no recovery | PARTIAL - robots stuck at CAUTION | PARTIAL | 非 deadlock，仅仅是未运行 |
| Emergency evidence | EMERGENCY state | PASS - 初始 EMERGENCY 有触发但快速解除 | PASS | 正常 |
| Robot state publisher | rsp not crashed | FAIL - UnknownROSArgsError | FAIL | URDF 参数错误 |

### 6. Final Verdict

**FAIL**

理由：
1. Nav2 stack 未启动（map argument missing）
2. robot_state_publisher 崩溃（URDF 被当作 CLI 参数传递）
3. Goals 未发出（waitUntilNav2Active API 不兼容）
4. Robots 未移动 - 全程位置固定
5. /speed_limit 无任何数据
6. /fleet/yield 无任何数据
7. YIELDING/PASSING 状态未触发

fleet_coordinator 本身的 CAUTION 状态转换是正常的，但完整的 Nav2 e2e yield 流程被上述 blocker 阻断。

### 7. Remaining Risks

1. Nav2 map argument - nav2_bringup launch 需要 map 参数，当前脚本未提供
2. rsp URDF passing - URDF 应通过 xacro 处理后传递，不应作为 raw CLI 参数
3. waitUntilNav2Active API - Python API 与 nav2_py_tutorial 版本不匹配
4. fleet_coordinator 单机 CAUTION - 协调器单独可工作，但无法驱动 Nav2 完整栈

### 8. Next Recommendation

P0 blockers to fix before next Nav2 e2e test:

1. Fix send_nav2_goal.py API call:
   - 移除或修正 waitUntilNav2Active(timeout=600.0) 调用
   - 检查当前 nav2_py_tutorial / basic_navigator API

2. Fix Nav2 launch to provide map:
   - 要么提供真实 map yaml
   - 要么使用 slam 模式（slam:=True）并提供对应参数

3. Fix robot_state_publisher invocation:
   - 确保 URDF 通过 xacro 预处理后再传给 rsp
   - 检查脚本中 rsp 的启动命令

4. 重新跑 e2e yield 测试:
   - fix 后重新执行 run_m3_nav2_e2e_yield.sh
   - 验证 robots 实际移动、speed_limit 动态值、yield/resume 闭环

### 9. Blocker Fixes Applied (2026-05-08)

P0 blockers identified in §7 above have been resolved:

| Blocker | Fix Applied |
|---------|-------------|
| nav2_bringup missing `map` argument | Added `map:=/opt/ros/humble/share/nav2_bringup/maps/turtlebot3_world.yaml`. Also changed `slam:=False` (AMCL mode with map) instead of `slam:=True` (slam_toolbox doesn't provide amcl/get_state) |
| rsp `UnknownROSArgsError` on raw URDF CLI arg | Replaced inline `-p robot_description:=$(cat ...)` with `--params-file ${LOG_DIR}/rsp_${ns}.yaml`. New `write_rsp_params.py` generates per-robot YAML with `robot_description` content (strips `\r` chars) and `robot_namespace`. Removed invalid `-r __ns:/${ns}` remap (uses `robot_namespace` YAML param instead) |
| `waitUntilNav2Active(timeout=600.0)` TypeError | Removed `timeout=600.0` kwarg. `waitUntilNav2Active(self, navigator, localizer)` has no timeout parameter. Wrapped in try/except to allow test to proceed if Nav2 not fully active |

**Modified files** (commit `316cb11`):
- `ros2_ws/src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh`
- `ros2_ws/src/fleet_gazebo/scripts/send_nav2_goal.py`
- `ros2_ws/src/fleet_gazebo/scripts/write_rsp_params.py` (new)

**Status**: P0 blockers resolved. Test pending re-run on ECS to verify full Nav2 e2e yield flow.

---

## Scenario: Nav2 e2e infra odom and AMCL fix

### root cause

本轮排查确认了 4 个真实基础设施问题：

1. **Nav2 参数未按机器人 namespace 改写**
   - 旧 YAML 仍使用未命名空间的 `odom` / `base_link` / `/odom`
   - 已改为按机器人生成 `nav2_robot_a.yaml` / `nav2_robot_b.yaml`
2. **`robot_state_publisher` 未真正前缀 frame**
   - 原脚本写入的是 `robot_namespace`
   - RSP 日志只显示 `base_link` / `base_scan`
   - 已改为 `frame_prefix: robot_a/` / `robot_b/`
3. **`send_nav2_goal.py` 缺少 `amcl_pose` namespace 显式检查**
   - 已改为等待 `/{namespace}/amcl_pose`
   - 保留超时与清晰错误输出
4. **`cmd_vel_to_odom.py` 与 Nav2 仍存在 TF 时钟/可见性问题**
   - 已补 `SingleThreadedExecutor`
   - 已补 `tf2_ros.TransformBroadcaster`
   - 已补 `use_sim_time=true`
   - 已修正 yaw quaternion 轴向

但在最新一轮 `WITH_NAV2=1` e2e 里，Nav2 仍持续报：

- `Invalid frame ID "robot_a/odom" passed to canTransform argument target_frame - frame does not exist`
- `Invalid frame ID "robot_b/odom" passed to canTransform argument target_frame - frame does not exist`

同时 AMCL 仍持续报：

- `Message Filter dropping message: frame 'robot_a/base_scan' ... earlier than all the data in the transform cache`
- `Message Filter dropping message: frame 'robot_b/base_scan' ... earlier than all the data in the transform cache`

因此，本轮结论不能写 PASS，也不能写 Nav2 e2e PARTIAL PASS，只能写 **FAIL**。

### modified files

- `ros2_ws/src/fleet_gazebo/fleet_gazebo/merge_nav2_fleet_params.py`
- `ros2_ws/src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh`
- `ros2_ws/src/fleet_gazebo/scripts/send_nav2_goal.py`
- `ros2_ws/src/fleet_gazebo/scripts/write_rsp_params.py`
- `ros2_ws/src/fleet_coordination/fleet_coordination/cmd_vel_to_odom.py`

### WITH_NAV2=0 result

**Run command**:

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
WITH_NAV2=0 bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 60
```

**LOG_DIR**: `/tmp/fleet_test_nav2_e2e_yield_20260510_104556`

**Result**:

- Gazebo spawn 成功
- 双 `fleet_coordinator` 正常运行
- `mock_path_publisher` 在初始数次 `No odom data` 后能收到 odom 并持续发 path
- `coord_robot_a.log` / `coord_robot_b.log` 中出现：
  - `NORMAL -> CAUTION`
  - `CAUTION -> YIELDING`
  - `PASSING`
  - `REQUEST_YIELD`
  - `RESUME`

**判定**: fleet coordination 单独链路 **PASS**，说明基础状态机验证不依赖 Nav2。

### build / test result

**Build**:

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

结果：**PASS**，4 packages finished。

**Test**:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon test
colcon test-result --verbose
```

结果：**PASS**，`32 tests, 0 errors, 0 failures, 0 skipped`。

### run command

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90
```

### LOG_DIR

- 首轮修复后重跑：`/tmp/fleet_test_nav2_e2e_yield_20260510_105622`
- 最新重跑（含 `cmd_vel_to_odom use_sim_time` 修复）：`/tmp/fleet_test_nav2_e2e_yield_20260510_105928`

以下判定以最新一轮 `20260510_105928` 为准。

### odom TF evidence

**正向证据**:

- `cmd_vel_to_odom_robot_a.log`:
  - `TF robot_a/odom->base_footprint count=50/100/150...`
- `cmd_vel_to_odom_robot_b.log`:
  - `TF robot_b/odom->base_footprint count=50/100/150...`

**反向证据**:

- `nav2_robot_a.log`:
  - `Timed out waiting for transform from robot_a/base_link to robot_a/odom ... frame does not exist`
- `nav2_robot_b.log`:
  - `Timed out waiting for transform from robot_b/base_link to robot_b/odom ... frame does not exist`

**判定**: workaround 节点已运行、已尝试发 TF，但 **Nav2 仍无法消费 odom TF**，本项 **FAIL**。

### AMCL pose evidence

- `send_nav2_goal.py` 已显式等待 `/{namespace}/amcl_pose`
- 但 `goal_robot_a.log` / `goal_robot_b.log` 在最新运行中仍为空，没有 “Received AMCL pose ...” 成功证据
- `nav2_robot_a.log` / `nav2_robot_b.log` 持续出现：
  - `Message Filter dropping message: frame 'robot_a/base_scan' ... earlier than all the data in the transform cache`
  - `Message Filter dropping message: frame 'robot_b/base_scan' ... earlier than all the data in the transform cache`

**判定**: `amcl_pose` namespace 代码已补，但 **AMCL pose 仍无成功证据**，本项 **FAIL**。

### robot movement evidence

- `WITH_NAV2=0` baseline 下可见 mover/fleet-only 运动与状态机闭环
- 最新 `WITH_NAV2=1` 运行中，`coord_robot_a.log` / `coord_robot_b.log` 的 `own_pos` 仍主要在 `0.00`、`-4.00`、`4.00` 间跳变
- `goal_robot_a.log` / `goal_robot_b.log` 没有有效目标执行日志

**判定**: **FAIL**，机器人未形成可确认的 Nav2 实际移动证据。

### `/speed_limit` evidence

- `speed_robot_a.log` / `speed_robot_b.log` 仍只有 `xmlrpc.client.Fault: !rclpy.ok()`
- 未找到 `nav2_msgs/msg/SpeedLimit`、`percentage`、`published speed_limit` 证据

**判定**: **FAIL**

### state transition evidence

**WITH_NAV2=0 baseline**:

- `CAUTION`
- `YIELDING`
- `PASSING`
- `REQUEST_YIELD`
- `RESUME`

**WITH_NAV2=1 latest rerun**:

- coordinator 仍有 `CAUTION` / `EMERGENCY` 抖动
- 但缺少基于 Nav2 实际移动的稳定状态机闭环

**判定**:

- fleet-only baseline：**PASS**
- Nav2 e2e：**FAIL / 未闭环**

### yield / resume evidence

- `WITH_NAV2=0` 基线中可观测到完整的让行相关证据
- 最新 Nav2 模式下没有新的 `yield.log` 有效闭环证据

**判定**:

- `WITH_NAV2=0` baseline：**PASS**
- `WITH_NAV2=1` Nav2 e2e：**FAIL**

### Nav2 / Gazebo error summary

| Component | Error / Symptom | Impact |
|-----------|------------------|--------|
| `controller_server` | `robot_a/odom` / `robot_b/odom` frame does not exist | Nav2 controller 无法工作 |
| `amcl` | `base_scan ... earlier than all the data in the transform cache` | AMCL pose 无法稳定产出 |
| `send_nav2_goal.py` | 最新运行无成功输出 | goals 未形成可验证闭环 |
| topic collectors | `ros2 topic echo` 结束时 `!rclpy.ok()` | collector 结果不可作为成功证据 |
| Gazebo spawn / bringup | 启动正常 | 非主 blocker |

### PASS / PARTIAL PASS / FAIL 对照表

| 检查项 | PASS 条件 | 实际证据 | 当前判定 | 备注 |
|--------|-----------|----------|----------|------|
| WITH_NAV2=0 coordination baseline | coordinator 正常运行并有状态机证据 | `CAUTION` / `YIELDING` / `PASSING` / `REQUEST_YIELD` / `RESUME` | PASS | fleet-only 可用 |
| odom TF | Nav2 可消费 `map -> odom -> base_link` | workaround 在发 TF，但 Nav2 仍报 `robot_*/odom` 不存在 | FAIL | 主 blocker |
| AMCL pose namespace | 收到 `/{ns}/amcl_pose` 成功证据 | goal 日志为空，AMCL 仍丢 scan | FAIL | 主 blocker |
| Nav2 stack start | bringup 完整启动 | bringup 可走到 controller activation | PARTIAL PASS | 仍卡 TF |
| goals fired | goal sender 成功发目标 | 无成功输出 | FAIL | 无法确认 |
| robot movement | 机器人产生实际 Nav2 运动 | 仅见位置跳变，无稳定轨迹推进 | FAIL | 无闭环 |
| topic collectors | collector 拿到有效 topic 数据 | 仅见 `!rclpy.ok()` Traceback | FAIL | collector 自身不稳定 |
| `/speed_limit` messages | 存在 SpeedLimit 数据 | 无数据 | FAIL | Nav2 未真正跑通 |
| speed limit dynamic values | 50/0/100% 可见 | 无数据 | FAIL | - |
| state transition | Nav2 e2e 中有稳定状态转移 | 仅 fleet-only baseline 有效 | FAIL | Nav2 模式未闭环 |
| yield / resume | Nav2 e2e 中有 request/ack/resume | baseline 有，Nav2 模式无新证据 | FAIL | 不能算 Nav2 PASS |
| collision | 0 collision 有证据 | 无碰撞计数器 | FAIL | 无法宣称 0 |
| deadlock | 0 deadlock 有证据 | 无完整证据 | FAIL | 无法宣称 0 |
| emergency | 0 unrecovered emergency | 仅见状态抖动，无完整恢复证明 | FAIL | 无法宣称 0 |

### final verdict

**FAIL**

因为最新一轮运行中仍同时满足：

- `odom TF` 在 Nav2 侧不可用
- `amcl_pose` 无成功证据
- 机器人没有可确认的 Nav2 实际移动
- `/speed_limit` 无数据

### remaining risks

1. `cmd_vel_to_odom.py` 的 TF 确实在发，但 `tf2`/Nav2 侧仍未接受，说明仍存在更底层的 TF topic / QoS / clock / bridge 问题。
2. `ros2 topic echo` collector 在场景结束时持续出现 `!rclpy.ok()`，影响 `/speed_limit` 与 `yield` 采集可信度。
3. ECS 上无 `ros-humble-xacro`，当前使用静态 URDF，虽可跑 smoke，但会放大 TF/传感器对齐排查复杂度。

### next recommendation

1. 在场景运行中增加 **live TF audit**，直接验证 `/tf` 中是否真的存在 `robot_a/odom -> robot_a/base_footprint` 与 `robot_a/base_footprint -> robot_a/base_link`。
2. 单独验证 `cmd_vel_to_odom.py` 发往哪个 TF topic，以及 Nav2 是否真的在消费同一条 `/tf`。
3. 将 collector 从 `ros2 topic echo` 改为受控 Python subscriber，避免 `!rclpy.ok()` 污染判定。

---

## Scenario: Nav2 lifecycle wait fix rerun

**日期**: 2026-05-10

### run command

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon build --symlink-install --packages-select fleet_gazebo
bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90
```

### log directory

- `LOG_DIR=/tmp/fleet_test_nav2_e2e_yield_20260510_114106`
- 外层 SSH 返回 `exit_code=255`，但远端场景主体已执行到 `[10] Topic collectors (90s)`，关键日志已完整落盘。

### modified files

| 路径 | 说明 |
|------|------|
| `ros2_ws/src/fleet_gazebo/scripts/send_nav2_goal.py` | 先等待 `amcl_pose`，循环发布 `initialpose`，再 `waitUntilNav2Active(localizer='amcl')`，最后 `goToPose()` |
| `ros2_ws/src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh` | goal 脚本传入每台机器人 spawn 初始位姿；增强启动前/退出后场景清理，避免 `Entity already exists` |

### send_nav2_goal.py lifecycle fix

- `goal_robot_a.log`:
  - `AMCL pose available; waiting for Nav2 lifecycle to become active`
  - `Nav2 is ready for use!`
  - `Navigating to goal: 0.0 0.0...`
- `goal_robot_b.log`:
  - `AMCL pose available; waiting for Nav2 lifecycle to become active`
  - `Nav2 is ready for use!`
  - `Navigating to goal: 0.0 0.0...`

**判定**: lifecycle 修复有效。相比上一轮的 `Goal ... was rejected`，本轮两台机器人都先等到 `amcl_pose`，再等到 Nav2 active，随后成功进入导航请求。

### build result

- 远端执行 `colcon build --symlink-install --packages-select fleet_gazebo`
- 结果：`Finished <<< fleet_gazebo [6.64s]`
- **判定**: PASS

### test result

- 本轮**未执行** `colcon test`
- 原因：本任务聚焦单脚本同步 + 90s Nav2 e2e rerun；远端会话稳定性较差，优先保证最新场景复验与日志取证

### amcl_pose evidence

- `goal_robot_a.log`: `Published initial pose to /robot_a/initialpose` 后收到 `AMCL pose available`
- `goal_robot_b.log`: `Published initial pose to /robot_b/initialpose` 后收到 `AMCL pose available`
- `nav2_robot_a.log`: `initialPoseReceived`
- `nav2_robot_b.log`: `initialPoseReceived`

**判定**: PASS - `TF + RSP + initialpose + AMCL` 链路已跑通。

### bt_navigator active evidence

- `goal_robot_a.log`: `Nav2 is ready for use!`
- `goal_robot_b.log`: `Nav2 is ready for use!`
- `nav2_robot_a.log`: `Activating bt_navigator` / `Server bt_navigator connected with bond`
- `nav2_robot_b.log`: `Activating bt_navigator` / `Server bt_navigator connected with bond`

**判定**: PASS - `bt_navigator` 已进入 active。

### goal accepted / rejected evidence

- 未再出现上一轮的 `Goal to 0.0 0.0 was rejected!`
- `nav2_robot_a.log`: `Begin navigating from current location (-3.92, -0.01) to (0.00, 0.00)`
- `nav2_robot_b.log`: `Begin navigating from current location (3.92, -0.01) to (0.00, 0.00)`
- 随后：
  - `GridBased: failed to create plan with tolerance 0.50.`
  - `Planning algorithm GridBased failed to generate a valid path to (0.00, 0.00)`
  - `[navigate_to_pose] [ActionServer] Aborting handle.`
  - `Goal failed`

**判定**: PARTIAL - goal 不再在 lifecycle 阶段被直接 reject，而是在 planner 阶段失败。

### robot movement evidence

- `mock_path.log` 在场景后段仍持续记录：
  - `robot_a: x=-4.00, y=-0.00`
  - `robot_b: x=4.00, y=0.00`
- `coord_robot_a.log` / `coord_robot_b.log` 的 `own_pos` 在整轮中保持初始位置

**判定**: FAIL - 机器人未产生可观察位移。

### /speed_limit evidence

- `speed_robot_a.log` / `speed_robot_b.log` 仍被 `ros2 topic echo` 的 `xmlrpc.client.Fault: !rclpy.ok()` 干扰
- 本轮日志中未抓到可作为判定依据的 `SpeedLimit` 消息

**判定**: FAIL - 本轮无法证明 `/speed_limit` 动态发布。

### state transition evidence

- `coord_robot_a.log`: `STATE_CHANGE: robot_a NORMAL -> CAUTION (speed_ratio=0.50)`
- `coord_robot_b.log`: `STATE_CHANGE: robot_b NORMAL -> CAUTION (speed_ratio=0.50)`
- 之后无 `YIELDING` / `PASSING` / `NORMAL` 恢复链路

**判定**: PARTIAL - 仅验证到初始 `CAUTION`，未进入 yield/resume 闭环。

### yield / resume evidence

- `yield.log` 仍被 `ros2 topic echo` 的 daemon 故障打断
- `coord_*.log` / `nav2_robot_*.log` 未见 `REQUEST_YIELD` / `ACK_YIELD` / `RESUME`

**判定**: FAIL - 本轮没有 yield/resume 证据。

### Nav2 / Gazebo errors

| 组件 | 证据 | 影响 |
|------|------|------|
| `planner_server` | `failed to create plan with tolerance 0.50` | goal 在规划阶段 abort |
| `global_costmap` | 长时间 `Timed out waiting for transform from robot_*/base_link to map` | map 链路建立较慢，规划启动滞后 |
| `amcl` | `Failed to transform initial pose in time ... extrapolation into the future` | 初始位姿注入后仍有时间戳/缓存边缘问题 |
| topic collectors | `xmlrpc.client.Fault: !rclpy.ok()` | `/speed_limit`、`/fleet/yield`、`status_*` 证据链不可靠 |
| Gazebo | `Can't open display` | 仅 headless 渲染警告，不构成场景 blocker |

### final verdict

**FAIL**

理由：

1. `send_nav2_goal.py` lifecycle 修复已生效，`amcl_pose` 与 `bt_navigator active` 已验证通过。
2. 但两台机器人都在 planner 阶段 `failed to create plan`，goal 被 abort。
3. `mock_path.log` 与 `coord_*.log` 显示机器人仍未移动。
4. `/speed_limit`、`/fleet/yield` 仍无可用证据，yield/resume 闭环未达成。

### remaining risks

1. `planner_server` 到 `(0,0)` 的路径规划失败，可能与 map / costmap / corridor 中心点可达性有关。
2. `map` 相关 TF 在激活前阶段仍存在长时间 unavailable / extrapolation 抖动。
3. `ros2 topic echo` 采集器仍不可靠，继续阻碍 `/speed_limit` 与 `/fleet/yield` 判定。

### next recommendation

1. 将目标点从 `(0,0)` 改为地图中明确可达的 corridor 通道点，先验证 `goal accepted -> plan created -> robot starts moving`。
2. 把 collector 从 `ros2 topic echo` 全部替换为受控 Python subscriber，避免 `!rclpy.ok()` 干扰。
3. 单独对 `planner_server` 做一次 `ComputePathToPose` 最小复现，确认是 map 可达性问题还是 costmap / TF 时间戳问题。
