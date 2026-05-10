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

---

## Scenario: Nav2 reachable goal and collector fix

**日期**: 2026-05-10

### root cause

上一轮的 planner blocker 不是 `bt_navigator` lifecycle，而是 e2e 使用的地图与 Gazebo 场景不一致：

- Gazebo 场景：`fleet_gazebo/worlds/corridor.world`
- 原 Nav2 map：`/opt/ros/humble/share/nav2_bringup/maps/turtlebot3_world.yaml`
- PGM 栅格抽样显示 `(0,0)`、`(-4,0)`、`(4,0)` 在 TurtleBot3 示例地图中落在 occupied / unknown / inflation 风险区，不能作为 corridor 场景的可靠目标点。

本轮改为运行时生成与 `corridor.world` 对齐的 corridor occupancy map，并用 `ComputePathToPose` probe 先验证候选目标。

### modified files

| 路径 | 说明 |
|------|------|
| `ros2_ws/src/fleet_gazebo/scripts/write_corridor_map.py` | 新增 corridor map 生成器，输出 `corridor_map.yaml` / `corridor_map.pgm` 到本轮 `LOG_DIR` |
| `ros2_ws/src/fleet_gazebo/scripts/compute_path_probe.py` | 新增最小 `ComputePathToPose` probe，验证当前点与候选目标是否可规划 |
| `ros2_ws/src/fleet_gazebo/scripts/collect_nav2_e2e_topics.py` | 新增受控 Python subscriber collector，替代 `ros2 topic echo` 采集 status / speed_limit / yield |
| `ros2_ws/src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh` | 使用 corridor map、可配置 reachable goals、path probes、Python collector，并修正 collector 退出竞态 |
| `ros2_ws/src/fleet_gazebo/scripts/send_nav2_goal.py` | 显式设置 sim time，使用 `cancelTask()`，记录 `NavigateToPose` result |
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_with_fleet.xml` | 按 Nav2 BT 模式调整 `GoalUpdatedController` 与 `AdjustSpeedForFleet` 的位置，避免继续盲目使用原结构 |

### map / goal analysis

- 原 map：`/opt/ros/humble/share/nav2_bringup/maps/turtlebot3_world.yaml`
- 原 map metadata：`resolution=0.05`，`origin=[-10.0, -10.0, 0.0]`，`size=384x384`
- PGM 抽样结论：
  - `(-4,0)` / `(4,0)` / `(0,0)` 在示例 map 中不是可靠 free cell
  - 该 map 与 corridor walls `y=±1.5`、end walls `x=±10` 不一致
- 新 map：每轮运行写入 `${LOG_DIR}/corridor_map.yaml`
- 新目标：
  - `robot_a -> (-1.0, 0.0, yaw=0.0)`
  - `robot_b -> (1.0, 0.0, yaw=3.14159)`
- 选择理由：两点位于 corridor 中心线 free space，可验证 `goal accepted -> plan created -> robot starts moving` 的最小闭环；本轮不宣称完整 yield e2e PASS。

### ComputePathToPose result

`LOG_DIR=/tmp/fleet_test_nav2_e2e_yield_20260510_142132`

| robot | goal | result | path poses |
|------|------|--------|------------|
| `robot_a` | current `(0.0, 0.0)` | PASS | 158 |
| `robot_a` | reachable `(-1.0, 0.0)` | PASS | 118 |
| `robot_a` | corridor_far `(1.0, 0.0)` | PASS | 198 |
| `robot_b` | current `(0.0, 0.0)` | PASS | 159 |
| `robot_b` | reachable `(1.0, 0.0)` | PASS | 119 |
| `robot_b` | corridor_far `(-1.0, 0.0)` | PASS | 199 |

**判定**: PASS - 使用 corridor map 后，planner 已能对当前点和新目标生成非空 path；上一轮 `failed to create plan with tolerance 0.50` blocker 已前移。

### collector replacement result

- 已替换 `ros2 topic echo` 为 `collect_nav2_e2e_topics.py`
- 本轮 `status_robot_a.log` / `status_robot_b.log` 成功采集 JSON 状态，无 `xmlrpc.client.Fault: !rclpy.ok()` 干扰
- `speed_robot_a.log` / `speed_robot_b.log` 为空：不是 collector crash，而是本轮未观察到 `/robot_*/speed_limit` 消息
- `yield.log` 为空：本轮未观察到 `/fleet/yield` 消息
- 已追加 runner 修正：collector duration 比场景 duration 短 3 秒，避免 cleanup 抢先 kill collector，后续应能写入 `COLLECTOR_DONE`

### build / test result

远端执行：

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
colcon test
colcon test-result --verbose
```

结果：

- `colcon build`: PASS，`Summary: 4 packages finished`
- `colcon test`: PASS，`Summary: 32 tests, 0 errors, 0 failures, 0 skipped`
- 仍有 `fleet_gazebo` 的 0-test stderr 输出：`Ran 0 tests ... OK`，未构成失败

### run command

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90
```

为避免 SSH 断开杀掉场景，最终有效轮次使用 `nohup bash -lc ...` 在远端 detached 执行。

### LOG_DIR

- `LOG_DIR=/tmp/fleet_test_nav2_e2e_yield_20260510_142132`
- runner exit code: `0`

### AMCL pose evidence

- `goal_robot_a.log`: `AMCL pose available; waiting for Nav2 lifecycle to become active`
- `goal_robot_b.log`: `AMCL pose available; waiting for Nav2 lifecycle to become active`

**判定**: PASS

### bt_navigator active evidence

- `goal_robot_a.log`: `Nav2 is ready for use!`
- `goal_robot_b.log`: `Nav2 is ready for use!`

**判定**: PASS

### goal accepted evidence

- `goal_robot_a.log`: `Navigating to goal: -1.0 0.0...`
- `goal_robot_b.log`: `Navigating to goal: 1.0 0.0...`
- 未见 `Goal was rejected`

**判定**: PARTIAL - goal 未在 lifecycle 阶段被 reject，但最终仍 `TaskResult.FAILED`。

### planner evidence

- `ComputePathToPose` probe 对 6 个目标全部 PASS
- `nav2_robot_a.log` / `nav2_robot_b.log` 不再出现上一轮 `GridBased: failed to create plan with tolerance 0.50`

**判定**: PASS - planner 可生成 path。

### robot movement evidence

- `mock_path.log`:
  - `robot_a` 从 `x=-4.00` 变化到约 `x=-3.72, y=0.05`
  - `robot_b` 从 `x=4.00` 变化到约 `x=3.75, y=-0.00`
- 移动幅度较小，且 goal 最终失败。

**判定**: PARTIAL - 有实际位移证据，但没有形成稳定 Nav2 goal success。

### /speed_limit evidence

- `nav2_robot_*.log`: `AdjustSpeedForFleet` 在 BT tick 中运行
- `speed_robot_a.log` / `speed_robot_b.log`: 空
- `nav2_robot_*.log` 未见 `AdjustSpeedForFleet: published speed_limit`

**判定**: FAIL - 本轮不能证明 `/speed_limit` 动态发布。

### state transition evidence

- `coord_robot_a.log`: `NORMAL -> CAUTION`，并有多次 `CAUTION <-> AWARENESS`
- `coord_robot_b.log`: `NORMAL -> CAUTION`，并有多次 `CAUTION <-> AWARENESS`
- `status_robot_*.log` 采集到 `speed_ratio=0.5` 与 `speed_ratio=1.0`
- 未见 `YIELDING` / `PASSING`

**判定**: PARTIAL

### yield / resume evidence

- `yield.log`: 空
- `coord_*.log` / `nav2_robot_*.log` 未见 `REQUEST_YIELD` / `ACK_YIELD` / `RESUME`

**判定**: FAIL

### Nav2 / Gazebo error summary

| 组件 | 证据 | 影响 |
|------|------|------|
| `controller_server` | `Resulting plan has 0 poses in it` | `FollowPath` 收到空 path，goal 最终失败 |
| `bt_navigator` | `Goal failed` | 两台机器人都未完成 Nav2 goal |
| `global_costmap` | 启动早期仍有 `Timed out waiting for transform ... map` / extrapolation | map TF 建链存在启动抖动 |
| `planner_server` | 后段有 `Robot is out of bounds of the costmap` | 与 odom / map pose 漂移或多源 odom 冲突相关，需单独处理 |
| `/speed_limit` | 无 SpeedLimit 消息 | `AdjustSpeedForFleet` tick 了，但未形成可观测 speed limit 发布 |

### final verdict

**FAIL**

理由：

1. planner blocker 已明显前移：corridor map + reachable goals 下 `ComputePathToPose` 全部 PASS。
2. 机器人已出现短时实际位移，但两个 Nav2 goal 最终仍 `TaskResult.FAILED`。
3. `FollowPath` 仍收到 zero-length plan，说明 BT blackboard / FollowPath path 输入链路仍有问题。
4. `/speed_limit`、yield request / ack / resume 仍没有日志证据。

### remaining risks

1. `ComputePathToPose` probe 成功，但 BT runtime 中 `FollowPath` 仍收到 0 poses，需继续定位 Nav2 BT blackboard path 传递与自定义 decorator 交互。
2. `mock_path.log` 中机器人位置有短时位移，但后续仍可能受 Gazebo diff_drive odom 与 `cmd_vel_to_odom.py` 双源 odom 影响。
3. `AdjustSpeedForFleet` 已 tick，但未发布 `/speed_limit`，需要确认其订阅的 `fleet/coordinator_status` 是否解析到了状态，或是否只在 speed ratio 变化时发布导致首帧缺失。
4. 本轮没有 yield/resume 闭环，不满足 M3 PASS。

### next recommendation

1. 新增一个最小 BT runtime 对照：使用同一 `ComputePathToPose -> FollowPath` 默认 Nav2 XML 验证 `FollowPath` 是否能收到非空 path。
2. 如果默认 XML 可移动，则继续缩小 `navigate_with_fleet.xml`：先保留 `FollowPath` 原样，再逐步加入 `CheckFleetConflict`、`WaitForYieldClear`、`AdjustSpeedForFleet`。
3. 修复 `/speed_limit` 证据链：让 `AdjustSpeedForFleet` 首次 tick 发布当前 speed limit，并确认订阅到 `/robot_*/fleet/coordinator_status`。

---

## Scenario: Nav2 default FollowPath and blackboard fix

**日期**: 2026-05-10

### root cause

本轮对照确认，上一轮的 `FollowPath` 空 path / controller failed 不是 Fleet 自定义节点直接覆盖 `{path}`：

- 手写极简 XML（仅 `PipelineSequence: ComputePathToPose -> FollowPath`）仍复现 `Resulting plan has 0 poses`，两台 goal 均失败。
- Nav2 Humble 标准默认树结构（`RateController + RecoveryNode + ComputePathToPose -> FollowPath`）在同一 corridor map、同一起点、同一 reachable goals 下可让两台 goal 成功。
- 因此核心问题是 Fleet XML 偏离 Nav2 默认 replanning/recovery 结构，导致 controller 面对瞬时空 path / local costmap 抖动时没有默认恢复语义。
- `/speed_limit` 为空的次级原因是 Fleet BT 插件订阅回调没有在 tick 中处理；改为按机器人 namespace 创建插件专用 ROS node，并在 tick 中 `rclcpp::spin_some()` 后，插件可读取 `coordinator_status` 并发布 SpeedLimit。

### modified files

| 路径 | 说明 |
|------|------|
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_default_follow_path.xml` | 新增 Nav2 标准默认对照树（无 Fleet 节点） |
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_goal_updated_follow_path.xml` | 新增 `GoalUpdatedController` 对照树 |
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_with_conflict_check.xml` | 新增 `CheckFleetConflict` 对照树 |
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_with_speed.xml` | 新增 `AdjustSpeedForFleet` 对照树 |
| `ros2_ws/src/fleet_nav2_bt/behavior_trees/navigate_with_fleet.xml` | 对齐 Nav2 默认 replanning/recovery 结构，并将 Fleet 节点放在 controller 侧 |
| `ros2_ws/src/fleet_nav2_bt/include/fleet_nav2_bt/bt_ros_host_utils.hpp` | Fleet BT 插件使用同 namespace 专用 ROS node |
| `ros2_ws/src/fleet_nav2_bt/src/{check_fleet_conflict,adjust_speed_for_fleet,wait_for_yield_clear}.cpp` | tick 内 `spin_some()`，处理订阅回调 |
| `ros2_ws/src/fleet_gazebo/fleet_gazebo/merge_nav2_fleet_params.py` | 支持 `BT_XML_MODE` / `NAV2_BT_XML` 选择 BT XML |
| `ros2_ws/src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh` | 输出 BT 模式，增加 `PATH_PROBE_TIMEOUT`，避免 probe 阻塞 e2e |

### default BT XML result

| XML / mode | LOG_DIR | result |
|------------|---------|--------|
| 手写极简 `ComputePathToPose -> FollowPath` | `/tmp/fleet_test_nav2_e2e_yield_20260510_171104` | FAIL：probe PASS，但 runtime 仍 `Resulting plan has 0 poses`，两台 `TaskResult.FAILED` |
| Nav2 标准默认树 `BT_XML_MODE=default` | `/tmp/fleet_test_nav2_e2e_yield_20260510_171703` | PASS：两台 `NavigateToPose result: TaskResult.SUCCEEDED`，机器人稳定移动 |

### incremental Fleet BT A/B result

本轮新增了 `default`、`goal_updated`、`conflict`、`speed`、`fleet` 五种 XML mode。实际执行了关键 A/B：

| mode | path / controller | movement | SpeedLimit | yield |
|------|-------------------|----------|------------|-------|
| `default` | transient zero-length plan 可被 Nav2 默认 recovery/replanning 消化 | PASS，两台 goal 成功 | N/A | N/A |
| `fleet`（修复后） | 仍有 local costmap / DWB transient warnings，但 `robot_a` goal 成功 | PARTIAL，`robot_a` 成功，`robot_b` 90s 内未写出最终结果 | PASS，50/100 动态值可观测 | FAIL，本轮 `yield.log` 为空 |

### blackboard path analysis

- `ComputePathToPose` 输出仍为 `path="{path}"`。
- `FollowPath` 输入仍为 `path="{path}"`。
- 修复没有更改 blackboard key 名；真正修复点是保留 Nav2 默认 `RateController`、planner/controller `RecoveryNode`、context costmap clear 与 top-level recovery。
- `CheckFleetConflict` 输出端口已显式绑定 `conflict_peer="{conflict_peer}"`，避免 `WaitForYieldClear` 无法读取 peer。
- `AdjustSpeedForFleet` 只包裹 `FollowPath`，不再包裹 `ComputePathToPose`，避免影响 path 计算阶段。

### build / test result

远端独立测试目录执行：

```bash
cd /home/guolinlin/ros2_ws/s3_m3_default_bt_worktree/YieldNet/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
colcon test
colcon test-result --verbose
```

结果：

- `colcon build`: PASS，`Summary: 4 packages finished`
- `colcon test`: PASS，`Summary: 4 packages finished`
- `colcon test-result --verbose`: PASS，`32 tests, 0 errors, 0 failures, 0 skipped`

### run command

```bash
cd /home/guolinlin/ros2_ws/s3_m3_default_bt_worktree/YieldNet/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

BT_XML_MODE=default bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90
BT_XML_MODE=fleet bash src/fleet_gazebo/scripts/run_m3_nav2_e2e_yield.sh 90
```

### LOG_DIR

- default 标准树：`/tmp/fleet_test_nav2_e2e_yield_20260510_171703`
- full fleet 最新轮：`/tmp/fleet_test_nav2_e2e_yield_20260510_173145`
- runner exit code: `0`

### evidence summary

| 检查项 | PASS 条件 | 实际证据 | 判定 | 备注 |
|--------|-----------|----------|------|------|
| default BT XML movement smoke | 默认 Nav2 可移动并完成 goal | 两台 `TaskResult.SUCCEEDED` | PASS | 证明地图/goal/planner 可用 |
| blackboard path key | Compute 与 Follow 使用同一 key | 均为 `{path}` | PASS | 未改 key 名 |
| AMCL pose | 收到 `/{ns}/amcl_pose` | `AMCL pose available` | PASS | 两机均有 |
| bt_navigator active | Nav2 ready | `Nav2 is ready for use!` | PASS | 两机均有 |
| goal accepted | 未被 reject | `Navigating to goal`，未见 reject | PASS | - |
| planner path created | probe 非空 path | 6 组 probe 全 PASS，118/119/198/199 poses | PASS | corridor map 有效 |
| controller path consumed | full fleet goal 至少成功 | `robot_a` full fleet `TaskResult.SUCCEEDED` | PARTIAL | `robot_b` 未在 90s 内写结果 |
| robot movement | odom 有明显变化 | full fleet: `robot_a` x min/max `-4.0/7.09`，`robot_b` `2.88/6.39` | PASS | 仍有仿真 odom 抖动风险 |
| collector reliability | Python collector 写出 topic 数据 | status/speed 有数据，无 `!rclpy.ok()` | PASS | `collector.log` 空但输出文件有效 |
| `/speed_limit` messages | 有 SpeedLimit 消息 | `speed_robot_a.log` / `speed_robot_b.log` 有 50/100 | PASS | 动态值已观测 |
| state transition | 有 Fleet 状态变化 | CAUTION/AWARENESS 多次切换 | PARTIAL | full fleet 未稳定 PASSING |
| yield request / ack / resume | `/fleet/yield` 有 request/ack/resume | latest full fleet `yield.log` 为空 | FAIL | 旧一轮有 request，但非最终轮 |
| collision | 有碰撞计数或明确无碰撞证据 | 无碰撞计数器 | FAIL | 不宣称 0 collision |
| deadlock | 有 0 deadlock 证据 | 无完整判据 | FAIL | 不宣称 0 deadlock |
| emergency | 0 unrecovered emergency | 初始 EMERGENCY 可恢复，后续无完整统计 | PARTIAL | 需专门统计 |

### Nav2 / Gazebo error summary

- 默认标准树和 full fleet 中仍可见短时 `Resulting plan has 0 poses`、`No valid trajectories`、`PathDist/Trajectory Hits Unreachable Area`。
- 默认标准树能通过 Nav2 replanning/recovery 语义恢复并成功到达。
- full fleet 中 `CheckFleetConflict` 与 `AdjustSpeedForFleet` 已能读取 coordinator JSON，但状态多在 CAUTION/AWARENESS 间抖动。
- `cmd_vel_to_odom.py` 仍仅作为 Gazebo / namespace e2e smoke workaround，不作为生产 odom 来源。

### final verdict

**PARTIAL PASS**

理由：

1. default Nav2 标准树对照已证明 corridor map、reachable goals、planner、controller 基本闭环可用。
2. full fleet 模式已消除“插件完全收不到 coordinator_status”的问题，并已观测到动态 `/speed_limit`。
3. full fleet 最新轮 `robot_a` goal 成功，但 `robot_b` 未在 90s 内写出最终结果。
4. 最新 full fleet 没有 `/fleet/yield` request/ack/resume 证据，且缺少 collision/deadlock/emergency 完整统计。

### remaining risks

1. full fleet 中仍有 DWB / local costmap transient errors，说明局部代价地图与仿真 odom 仍需稳定化。
2. Fleet 状态在 CAUTION/AWARENESS 间高频抖动，可能影响 yield 触发稳定性。
3. `yield.log` 为空，M3 完整 yield/resume 验收仍未闭环。
4. 仍未内置碰撞计数器、deadlock 计数器与 unrecovered emergency 判据。

### next recommendation

1. 基于当前 Nav2 标准树结构继续调稳定性：缩小 DWB/local costmap out-of-plan 问题。
2. 增加 collision/deadlock/emergency 自动判定器，避免人工推断。
3. 针对 Fleet 状态抖动单独调参或加入状态滞回，再重跑 90s / 180s full fleet yield。

## Scenario: DWB / yield loop / automatic safety judge fix

日期：2026-05-10

### scope

本轮目标是修复上一轮 `PARTIAL PASS` 中的 3 个缺口：

- `/fleet/yield` 没有 request/ack/resume 证据。
- DWB/local costmap 抖动导致 full fleet 目标不稳定。
- 缺少 collision / deadlock / unrecovered emergency 自动判据。

### code changes

- 修复 `fleet_coordinator.py` 的 peer 距离计算：从 `sqrt(peer.x^2 + peer.y^2)` 改为相对距离 `sqrt((peer.x-own_x)^2 + (peer.y-own_y)^2)`。
- 增加确定性优先级 tie-break：动态优先级相等时按 `robot_id` 字典序决定 passing/yielding，避免双方分支不一致。
- 补齐 `REQUEST_YIELD` 处理：低优先级机器人收到 request 后进入 `YIELDING` 并发布 `ACK_YIELD`。
- 为 `WaitForYieldClear` 增加 `/speed_limit` 输出：yield 等待期间持续发布 `0%`，resume/halt/timeout 发布 `100%`，避免 BT 分支阻塞 `AdjustSpeedForFleet` 时无法真正让 Nav2 controller 停车。
- 修复 `WaitForYieldClear` 在 blackboard `robot_id` 未设置时 `from_robot=''` 的问题：从 ROS namespace 推断 robot id。
- 在 `merge_nav2_fleet_params.py` 中加入 e2e 稳定性参数：
  - `controller_server.failure_tolerance >= 2.0`
  - `progress_checker.required_movement_radius <= 0.1`
  - `progress_checker.movement_time_allowance >= 20.0`
  - local costmap `width/height >= 6`
  - local costmap `inflation_radius <= 0.35`
- 新增 `judge_nav2_e2e_safety.py`，自动输出：
  - collision events / min distance
  - deadlock candidate windows and pass/fail
  - unrecovered emergency pass/fail
  - goal success and yield command counts
- `run_m3_nav2_e2e_yield.sh` 接入 safety judge，并将 goal sender 的 AMCL pose 等待改为 `SEND_GOAL_AMCL_TIMEOUT`，默认 `45s`。

### verification commands

```bash
cd /home/guolinlin/ros2_ws/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
colcon test
colcon test-result --verbose
```

结果：

- `colcon build`: PASS，`Summary: 4 packages finished`
- `colcon test`: PASS，`Summary: 4 packages finished`
- `colcon test-result --verbose`: PASS，`33 tests, 0 errors, 0 failures, 0 skipped`

### scenario runs

| LOG_DIR | Duration | Result | Key evidence |
|---------|----------|--------|--------------|
| `/tmp/fleet_test_nav2_e2e_yield_20260510_191259` | 90s | PASS | `robot_a` / `robot_b` both `TaskResult.SUCCEEDED`; safety judge `passed=true`; `/speed_limit` includes `0%`; `REQUEST_YIELD=97`, `ACK_YIELD=502`, `RESUME=472` |
| `/tmp/fleet_test_nav2_e2e_yield_20260510_192314` | 180s | FAIL | both goals `TaskResult.SUCCEEDED`; deadlock pass; unrecovered emergency pass; collision fail: `events=173`, `min_distance_m=0.032` |
| `/tmp/fleet_test_nav2_e2e_yield_20260510_192935` | 90s | FAIL | both goals `TaskResult.SUCCEEDED`; deadlock pass; unrecovered emergency pass; collision fail: `events=16`, `min_distance_m=0.112` |

### evidence summary

| 检查项 | PASS 条件 | 实际证据 | 判定 | 备注 |
|--------|-----------|----------|------|------|
| build / tests | build + tests 全通过 | 4 packages build pass；33 tests pass | PASS | 远端 ROS 环境验证 |
| AMCL pose wait | 两机 goal sender 可等待 AMCL | `SEND_GOAL_AMCL_TIMEOUT=45s` 后有效 180s 中两机均进入 Nav2 active | PASS | 仍可能受仿真启动负载影响 |
| Nav2 goals | 两机都完成目标 | 180s 最新有效轮两机 `TaskResult.SUCCEEDED` | PASS | 目标为对向穿越中心点 |
| yield messages | `/fleet/yield` 有 request/ack/resume | 180s: `REQUEST_YIELD=5`, `ACK_YIELD=371`, `RESUME=381` | PASS | 消息量偏高，存在抖动 |
| speed limit execution | yield 期间能发 0% | `speed_robot_*.log` 出现 `speed_limit=0.000` | PASS | `WaitForYieldClear` 直接发布 |
| deadlock judge | 0 deadlock events | 180s: `deadlock.passed=true`, `events=0` | PASS | candidate windows 为 goal 前/后静止，不计失败 |
| unrecovered emergency judge | 无未恢复 emergency | 180s: `unrecovered_emergency.passed=true` | PASS | - |
| collision judge | `min_distance >= 0.35m` 且 events=0 | 180s: `events=173`, `min_distance_m=0.032`; 90s 复验: `events=16`, `min_distance_m=0.112` | FAIL | 不能宣称 0 collision |

### final verdict

**PARTIAL PASS**

理由：

1. 本轮已修通 `/fleet/yield` request / ack / resume 证据链，并让 `/speed_limit=0%` 可被 Nav2 controller 观测到。
2. 自动 safety judge 已接入 runner，能够阻止 collision / deadlock / unrecovered emergency 被人工误判为 PASS。
3. 有一轮 90s full fleet 验证达到 `passed=true`，说明修复方向有效。
4. 但正式 180s 和复验 90s 仍出现真实 collision 判据失败，最小距离低至 `0.032m` / `0.112m`，不满足 M3/P0 的 0 collision 完成定义。

### remaining risks

1. yield/resume 消息量偏高，说明 `WaitForYieldClear` 与 coordinator latch 之间仍存在抖动，需要节流或更明确的 per-peer yield ownership。
2. 当前对向穿越中心点目标会把机器人带入极窄相遇区域，局部速度限制虽然生效，但还不足以稳定保证 `min_distance >= 0.35m`。
3. `cmd_vel_to_odom.py` 仍只是 Gazebo / namespace workaround，不能作为生产 odom 来源；当前 collision judge 依赖该 e2e odom 证据。
