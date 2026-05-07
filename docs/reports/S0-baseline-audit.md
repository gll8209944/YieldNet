# S0-baseline-audit

**日期**: 2026-05-07
**阶段**: S0 基线冻结与仓库体检
**审计人**: Claude Code
**分支**: master
**Commit**: 0fe87fd

---

## Summary

本报告记录 YieldNet/FleetGuard 仓库在 `v0.3.0-m3-baseline` 打标签前的基线状态确认结果。

**结论**: 当前代码库结构完整、核心逻辑对齐架构，但存在 **5 个已识别的技术债风险项**，其中 **2 个阻塞性问题**必须在打基线标签前或后明确处理策略。

- `fleet_nav2_bt` BT 节点使用 `std_msgs/String` 而非 `fleet_msgs/msg/YieldCommand`，违反 CLAUDE.md §3.3 消息协议要求
- `CheckFleetConflict` 将 JSON 字符串直接与枚举名比较，存在健壮性风险
- `WaitForYieldClear` 发布 `fleet/yield_command` (String) 而非 `fleet/yield` (YieldCommand)
- `fleet/coordinator_status` 被多个 BT 节点订阅作为生产控制契约，违反 CLAUDE.md §3.2 "仅用于本机诊断" 的定位
- `AdjustSpeedForFleet` 尚未真实影响 Nav2 FollowPath 速度限制

**build 和 test 无法验证**（ROS 2 环境未安装在当前审查环境），需要用户在有 ROS 2 的环境中执行验证。

---

## CLAUDE.md Compliance

| 约束项 | 状态 | 说明 |
|--------|------|------|
| DDS 双 Domain 隔离 | ✅ | Topic 白名单正确（`/fleet/*`） |
| Nav2 BT 原生集成路线 | ⚠️ | BT 节点存在但使用 String 协议 |
| fleet_speed_controller 定位 | ✅ | 注释明确为仿真/过渡/兜底 |
| cmd_vel_to_odom 定位 | ✅ | 注释明确为 Gazebo workaround |
| 不自动 push/tag | ✅ | 已遵守 |
| 非平凡修改后 build+test | ⚠️ | 环境缺失，未执行 |

---

## Git Status

| 项目 | 值 |
|------|-----|
| 当前分支 | master |
| 当前 commit | 0fe87fd |
| upstream 状态 | 与 origin/master 一致 |
| 未提交文件 | `.DS_Store`, `CLAUDE.md`, `ros2_ws/.DS_Store` |
| 未 push commit | 无 |
| remote | https://github.com/gll8209944/YieldNet.git |

**备注**: `CLAUDE.md` 已创建但未提交（新文件）。

---

## Repository Structure

```
YieldNet/
├── ros2_ws/src/
│   ├── fleet_coordination/          # 核心协调逻辑 (Python)
│   │   ├── fleet_coordination/
│   │   │   ├── fleet_coordinator.py  # 主协调节点 (~700行)
│   │   │   ├── peer_state.py         # 状态数据结构
│   │   │   ├── cmd_vel_to_odom.py    # Gazebo workaround
│   │   │   └── fleet_speed_controller.py  # 速度调制 (过渡)
│   │   ├── launch/
│   │   │   └── fleet_bringup.launch.py
│   │   └── test/
│   │       ├── test_state_machine.py
│   │       ├── test_priority.py
│   │       └── test_path_conflict.py
│   ├── fleet_msgs/                   # 消息定义
│   │   └── msg/
│   │       ├── RobotHeartbeat.msg
│   │       ├── RobotPose.msg
│   │       ├── PlannedPath.msg
│   │       └── YieldCommand.msg
│   ├── fleet_gazebo/                 # Gazebo 仿真
│   │   ├── worlds/
│   │   │   ├── corridor.world        # 走廊世界
│   │   │   └── t_intersection.world # T字路口世界
│   │   └── scripts/
│   │       ├── mock_path_publisher_all.py
│   │       ├── move_robots_to_center.py
│   │       ├── nav_test_3robots.py
│   │       ├── test_multi_robot.sh
│   │       └── test_multi_robot_with_nav.sh
│   └── fleet_nav2_bt/               # Nav2 BT 集成 (C++)
│       ├── src/
│       │   ├── check_fleet_conflict.cpp
│       │   ├── wait_for_yield_clear.cpp
│       │   ├── adjust_speed_for_fleet.cpp
│       │   └── fleet_bt_runner.cpp
│       ├── behavior_trees/
│       │   └── navigate_with_fleet.xml
│       └── plugin_descriptions.xml
├── deploy/                          # 部署配置
│   └── etc/
│       ├── cyclonedds/
│       ├── fleet/
│       └── systemd/
├── docs/
│   ├── execution-plans/
│   │   └── Task-Board.md
│   └── notion-sync/
└── CLAUDE.md                        # 约束文件 (未提交)
```

---

## ROS2 Packages

| Package | 类型 | 职责 | 状态 |
|---------|------|------|------|
| fleet_coordination | Python | 核心协调逻辑、6状态机、per-peer决策 | ✅ |
| fleet_msgs | msg | 消息类型定义 | ✅ |
| fleet_gazebo | Python | Gazebo仿真、测试脚本 | ✅ |
| fleet_nav2_bt | C++ | Nav2 BT插件 | ⚠️ 见风险项 |

---

## Build Result

**状态**: 无法验证（ROS 2 环境未安装）

```
colcon: command not found
/opt/ros/: No such file or directory
```

需要在有 ROS 2 的环境中执行:
```bash
cd ros2_ws
source /opt/ros/$ROS_DISTRO/setup.bash
colcon build --symlink-install
```

---

## Test Result

**状态**: 无法验证（依赖 build 成功）

预期测试（根据 Task-Board.md）:
- `test_state_machine.py` - 状态机测试
- `test_priority.py` - 优先级计算测试
- `test_path_conflict.py` - 路径冲突检测测试

根据历史 commit `ac32f25 fix(test_path_conflict): correct hysteresis test logic`，测试逻辑曾被修正，暗示存在 32 个测试的说法需要验证。

---

## Implemented Capabilities

### 6 状态机 ✅

| 状态 | 值 | 速度缩放 | 实现 |
|------|-----|---------|------|
| NORMAL | 0 | 1.0 | ✅ |
| AWARENESS | 1 | 1.0 | ✅ |
| CAUTION | 2 | 0.5 | ✅ |
| YIELDING | 3 | 0.0 | ✅ |
| PASSING | 4 | 0.3 | ✅ |
| EMERGENCY | 5 | 0.0 | ✅ |

### 阈值 ✅

| 参数 | 默认值 | 状态 |
|------|--------|------|
| AWARENESS_RANGE | 8.0m | ✅ |
| CAUTION_RANGE | 4.0m | ✅ |
| YIELD_RANGE | 2.5m | ✅ |
| EMERGENCY_RANGE | 0.8m | ✅ |
| PATH_CONFLICT_DIST | 1.5m | ✅ |
| PATH_LOOKAHEAD | 5.0m | ✅ |
| HEARTBEAT_TIMEOUT | 6.0s | ✅ |
| YIELD_TIMEOUT | 15.0s | ✅ |

### Topic 白名单 ✅

- `/fleet/heartbeat` ✅
- `/fleet/pose` ✅
- `/fleet/planned_path` ✅
- `/fleet/yield` ✅
- `/fleet/coordinator_status` ✅ (但被误用，见风险项)

### 核心功能 ✅

- per-peer 状态管理 ✅
- 动态优先级计算 ✅
- 路径冲突检测（带迟滞）✅
- heartbeat timeout ✅
- yield timeout ✅

### 仿真环境 ✅

- corridor.world ✅
- t_intersection.world ✅
- 三机测试脚本 ✅

### fleet_nav2_bt ⚠️

- `CheckFleetConflict` ✅ (plugin 注册)
- `WaitForYieldClear` ✅ (plugin 注册)
- `AdjustSpeedForFleet` ✅ (plugin 注册)
- `navigate_with_fleet.xml` ✅

---

## Known Risks

### 1. [中] BT 节点使用 std_msgs/String 而非 fleet_msgs/msg/YieldCommand

**位置**: `wait_for_yield_clear.cpp:30-31`

```cpp
yield_pub_ = node_->create_publisher<std_msgs::msg::String>(
    "fleet/yield_command", ...);
```

**影响**: 违反 CLAUDE.md §3.3 消息协议要求。`fleet_coordinator.py` 使用 `fleet_msgs/msg/YieldCommand`，而 BT 节点使用 `std_msgs/String`，协议不一致。

**现状**: `fleet/yield_command` 是 String 协议，与 `/fleet/yield` (YieldCommand) 是两个不同 topic。

**建议**: 这是过渡方案，需要记录为技术债，给出向 `fleet_msgs/msg/YieldCommand` 收敛的计划。

---

### 2. [中] CheckFleetConflict 将 JSON 字符串直接与枚举名比较

**位置**: `check_fleet_conflict.cpp:44-50`

```cpp
std::string fleet_state = current_fleet_state_;  // JSON string
bool has_conflict = (fleet_state == "YIELDING" ||
                     fleet_state == "PASSING" ||
                     fleet_state == "EMERGENCY");
```

**影响**: `_publish_diagnostic()` 发布的是 JSON 字符串:
```json
{"robot_id": "robot_a", "state": "NORMAL", "speed_ratio": 1.0, "peers": [...]}
```

当 `fleet_state == "YIELDING"` 时，比较应该是正确的。但如果 JSON 解析有问题或字段名变更，会导致静默失败。

**建议**: 在 `_publish_diagnostic()` 中直接发布 `state` 字段值（而非完整 JSON），或让 BT 节点解析 JSON。

---

### 3. [中] fleet/coordinator_status 被误用为生产控制契约

**位置**: 多个 BT 节点订阅此 topic

根据 CLAUDE.md §3.2:
> `/fleet/coordinator_status` 仅用于本机诊断、日志采集和可观测性，不应作为唯一生产控制契约。

但实际上:
- `CheckFleetConflict` 订阅 `fleet/coordinator_status` 做冲突判断
- `AdjustSpeedForFleet` 订阅 `fleet/coordinator_status` 做速度限制
- `FleetSpeedController` 订阅 `fleet/coordinator_status` 做速度调制

**影响**: 如果此 topic 因网络问题丢失，所有节点会错误地认为无冲突。

**建议**: 这是一个架构问题。需要明确：生产控制契约应该是什么？是否应该有独立的控制 topic？

---

### 4. [中] AdjustSpeedForFleet 尚未真实影响 Nav2 速度限制

**位置**: `adjust_speed_for_fleet.cpp:71-75`

```cpp
if (speed_ratio < 0.01 && child_status == BT::NodeStatus::RUNNING) {
    geometry_msgs::msg::Twist cmd;
    cmd.linear.x = 0.0;
    cmd.angular.z = 0.0;
    // Note: In a real implementation, we'd intercept the child's cmd_vel output
    // For now, we just return the child's status
}
```

**影响**: 注释明确说"For now, we just return the child's status"，速度限制尚未真实集成到 Nav2 controller。

**建议**: 这是已知的过渡实现，需要在 Nav2 原生集成路线中完成。

---

### 5. [低] cmd_vel_to_odom.py 存在被误用为生产 odom 的风险

**位置**: `cmd_vel_to_odom.py`

**现状**: 文件注释明确说明是 "Gazebo / namespace workaround"，但代码中存在被用于生产 odom 的可能性（如果有人不读注释）。

**建议**: 当前 CLAUDE.md §7 已明确禁止，风险可控。

---

## Blocking Issues

### 1. [阻塞] fleet_nav2_bt 协议不一致

**问题**: BT 节点使用 `std_msgs/String` 和 `fleet/yield_command`，而 `fleet_coordinator.py` 使用 `fleet_msgs/msg/YieldCommand` 和 `/fleet/yield`。

**影响**: 当前实现无法与 fleet_coordinator 正确通信。

**处理策略**（二选一）:

**策略 A（推荐）**: 将 BT 节点改为使用 `fleet_msgs/msg/YieldCommand`
- 修改 `wait_for_yield_clear.cpp` 使用 `YieldCommand` 类型发布到 `/fleet/yield`
- 修改 `check_fleet_conflict.cpp` 解析 JSON 或订阅独立的状态 topic

**策略 B**: 保持现状，作为已记录的技术债
- 在 `docs/reports/S0-baseline-audit.md` 中记录为技术债
- 在 PRD/SAD 中更新过渡方案说明
- 给出向最终方案收敛的时间表

---

### 2. [阻塞] build 和 test 未验证

**问题**: 当前审查环境无 ROS 2，无法执行 `colcon build --symlink-install` 和 `colcon test`。

**影响**: 无法确认代码在 ROS 2 环境下可构建和测试通过。

**处理**: 用户在有 ROS 2 的环境中执行验证命令。

---

## Recommendation

### 当前 baseline 是否可用？

**是，但有限制**。核心协调逻辑（`fleet_coordinator.py`、`peer_state.py`）实现完整且对齐架构，但 fleet_nav2_bt 存在协议不一致问题需要处理。

### 是否建议打 tag？

**建议打 tag，但需要先处理阻塞问题 1（协议不一致）**。

如果选择策略 B（记录为技术债），可以打 tag，但需要在 Tag 说明中明确标注 "fleet_nav2_bt 使用过渡协议"。

### Recommended tag

```
v0.3.0-m3-baseline
```

**Tag message 建议**:
```
v0.3.0-m3-baseline

M3 场景测试阶段基线。
核心协调逻辑完成，状态机、per-peer 架构、路径冲突检测已实现。
fleet_nav2_bt 存在，使用 std_msgs/String 过渡协议。
技术债: BT 节点需收敛到 fleet_msgs/msg/YieldCommand。
```

### 下一步建议

1. **立即**: 在有 ROS 2 的环境中执行 build 和 test 验证
2. **S1 前**: 明确 fleet_nav2_bt 协议处理策略（策略 A 或 B）
3. **S1**: 如果选择策略 A，实施协议收敛
4. **S1**: 验证 `/fleet/coordinator_status` 是否应该作为生产控制契约
5. **S3-M3**: 执行完整 P0 场景测试

---

## Appendix: Verification Commands

```bash
# 1. Build
cd ros2_ws
source /opt/ros/$ROS_DISTRO/setup.bash
colcon build --symlink-install

# 2. Test
source install/setup.bash
colcon test
colcon test-result --verbose

# 3. 查看测试
ls ros2_ws/src/fleet_coordination/test/

# 4. 查看 package 结构
find ros2_ws/src -name "package.xml" -exec echo {} \;
```
