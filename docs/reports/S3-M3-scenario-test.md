# S3-M3 Scenario Test Report

**日期**: 2026-05-08
**阶段**: S3-M3 场景测试验证
**分支**: s1-bt-protocol-alignment
**基于 commit**: 353ad1c (S1-A + S1-B merged)

---

## Summary

本报告记录 S3-M3 场景测试验证结果，验证 S1-A + S1-B 在场景层面闭环可用性。

**结论**: PARTIAL PASS (B) - 核心协议正确，单元测试通过，但完整场景 runtime 验证需要 Gazebo 仿真环境。

---

## Commit 信息

| 阶段 | Commit | 说明 |
|------|--------|------|
| S0 baseline | d2d63eb | v0.3.0-m3-baseline |
| S1-A | 6c7793d | BT yield protocol alignment |
| S1-B | 3eadf47 | Nav2 SpeedLimit integration |
| Merge | 353ad1c | PR #1 merged |

---

## Build 结果

| 项目 | 值 |
|------|-----|
| 状态 | ✅ PASS |
| Packages | 4 |
| Duration | 1min 49s |
| Warnings | 2 reorder warnings (check_fleet_conflict.hpp) |
| Errors | 0 |

---

## Test 结果

| 项目 | 值 |
|------|-----|
| 状态 | ✅ PASS |
| Tests | 32 |
| Errors | 0 |
| Failures | 0 |
| Skipped | 0 |

---

## 静态协议检查

### A. BT Yield Protocol (S1-A)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| CheckFleetConflict JSON 解析 | ✅ | 不再直接比较 JSON 字符串与 "YIELDING" |
| CheckFleetConflict state 提取 | ✅ | 从 coordinator_status JSON 提取 state 字段 |
| CheckFleetConflict conflict_peer | ✅ | 提供 OutputPort 并正确 setOutput |
| WaitForYieldClear /fleet/yield | ✅ | 使用 /fleet/yield topic |
| WaitForYieldClear YieldCommand | ✅ | 使用 fleet_msgs::msg::YieldCommand |
| WaitForYieldClear robot_id 过滤 | ✅ | 只处理 to_robot == robot_id_ 的消息 |
| WaitForYieldClear std_msgs/String 移除 | ✅ | 不再使用 fleet/yield_command |

### B. Nav2 SpeedLimit (S1-B)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| AdjustSpeedForFleet SpeedLimit 发布 | ✅ | 发布 nav2_msgs::msg::SpeedLimit |
| AdjustSpeedForFleet topic | ✅ | 发布到 speed_limit 话题 |
| AdjustSpeedForFleet percentage 模式 | ✅ | percentage=true, 0-100% |
| SpeedScaling state 映射 | ✅ | YIELDING=0, CAUTION=0.5, NORMAL=1.0 |
| SpeedScaling 回退机制 | ✅ | 解析失败回退 default_speed |
| 新 topic 范围 | ✅ | 仅 speed_limit，无大范围变更 |

### C. BT XML 结构

| 检查项 | 状态 | 说明 |
|--------|------|------|
| navigate_with_fleet.xml 存在 | ✅ | 存在于 fleet_nav2_bt/behavior_trees/ |
| CheckFleetConflict 端口 | ✅ | robot_id 输入, conflict_peer 输出 |
| WaitForYieldClear 端口 | ✅ | robot_id, peer_id, timeout |
| AdjustSpeedForFleet 端口 | ✅ | default_speed 输入 |
| conflict_peer 连接 | ✅ | 从 CheckFleetConflict 传给 WaitForYieldClear |

---

## 场景测试

### 场景 1: 无冲突基线

| 项目 | 值 |
|------|-----|
| 测试类型 | 单元测试 (test_path_conflict.py) |
| 覆盖测试 | test_no_conflict_parallel_paths, test_no_conflict_safe_distance, test_no_conflict_empty_path |
| 结果 | ✅ PASS |

**验证点**:
- 无冲突时 CheckFleetConflict 返回 FAILURE
- 不应发布错误的 YieldCommand
- coordinator_status state 应为 NORMAL

### 场景 2: 冲突 / Yield 触发

| 项目 | 值 |
|------|-----|
| 测试类型 | 单元测试 (test_path_conflict.py, test_state_machine.py) |
| 覆盖测试 | test_conflict_crossing_paths, test_yielding_when_low_priority_in_conflict, test_conflict_head_on_approach |
| 结果 | ✅ PASS |

**验证点**:
- CheckFleetConflict 识别冲突并返回 SUCCESS
- conflict_peer 有值
- WaitForYieldClear 监听 /fleet/yield
- YieldCommand 使用 fleet_msgs::msg::YieldCommand

### 场景 3: 恢复 / Resume

| 项目 | 值 |
|------|-----|
| 测试类型 | 单元测试 (test_state_machine.py) |
| 覆盖测试 | test_priority_changes_during_yield |
| 结果 | ✅ PASS |

**验证点**:
- 状态机支持 yield → resume 转换
- WaitForYieldClear 处理 CMD_RESUME 消息
- speed scaling 恢复

---

## 运行时 Topic 观测

| Topic | Type | Pub | Sub | Status |
|-------|------|-----|-----|--------|
| /fleet/yield | fleet_msgs/YieldCommand | 3 | 3 | ✅ |
| /fleet/heartbeat | - | - | - | ✅ |
| /fleet/planned_path | - | - | - | ✅ |
| /fleet/pose | - | - | - | ✅ |
| /robot_a/fleet/coordinator_status | std_msgs/String | 1 | 1 | ✅ |
| /speed_limit | nav2_msgs/SpeedLimit | - | - | ⚠️ Nav2 controller 未运行 |

**说明**: /speed_limit 话题在 Nav2 controller 运行时才会创建，AdjustSpeedForFleet 发布到该话题供 Nav2 controller 消费。

---

## S3-M3 结论

### 结论: PARTIAL PASS (B)

**通过项**:
- Build: 4 packages, 0 errors ✅
- Test: 32 tests, 0 failures ✅
- S1-A protocol: 所有检查通过 ✅
- S1-B SpeedLimit: 所有检查通过 ✅

**部分通过项**:
- 场景 1/2/3: 单元测试覆盖核心逻辑 ✅
- BT XML 结构正确 ✅
- 完整 runtime 验证需要 Gazebo 仿真 ⚠️

**未完整验证项**:
- 完整 BT runtime 在 Gazebo 中运行
- speed_limit 端到端验证 (需要 Nav2 controller)
- 多机器人实际让行流程

---

## 是否建议进入 S1-CLOSE

**建议**: ✅ 进入 S1-CLOSE

**条件**:
1. S3-M3 核心协议和单元测试全部通过
2. PARTIAL PASS 原因仅为缺少 Gazebo 仿真环境
3. 下一步可通过 S3-M3-full 或人工验收补充场景测试

**Merge master 前需确认**:
- 人工审查 BT XML 和协议实现
- 可选择补充 Gazebo 场景测试

---

## 剩余风险

1. **Reorder warnings**: check_fleet_conflict.hpp 初始化顺序不一致 (非阻塞)
2. **Runtime 验证**: 完整 BT runtime + Gazebo 场景未跑通 (需要仿真环境)
3. **speed_limit 端到端**: Nav2 controller 集成需要完整 Nav2 stack

---

## Appendix: 验证命令

```bash
# Build
cd /home/guolinlin/ros2_ws
source /opt/ros/humble/setup.bash
colcon build

# Test
source install/setup.bash
colcon test
colcon test-result --verbose

# 运行时观测
ros2 topic list | grep fleet
ros2 topic info /fleet/yield
ros2 node list
```
