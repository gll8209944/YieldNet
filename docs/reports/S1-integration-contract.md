# S1-integration-contract

**日期**: 2026-05-07
**阶段**: S1 BT 协议对齐与 JSON 解析修复
**分支**: s1-bt-protocol-alignment
**基于 commit**: d2d63eb (v0.3.0-m3-baseline)

---

## Summary

本报告记录 S1-A 阶段的修复工作：BT 协议对齐与 JSON 解析问题修复。

**结论**: BT 节点协议问题已修复，`fleet_msgs/YieldCommand` 已作为生产路径，`coordinator_status` 已明确为诊断路径。

**修复内容**:
1. CheckFleetConflict: 修复 JSON 状态解析 bug
2. AdjustSpeedForFleet: 修复 JSON 状态解析 bug
3. WaitForYieldClear: 切换到 `/fleet/yield` + `fleet_msgs/YieldCommand`
4. 添加 conflict_peer OutputPort
5. 添加 fleet_msgs 依赖

---

## Baseline

| 项目 | 值 |
|------|-----|
| 分支 | s1-bt-protocol-alignment |
| 基于 commit | d2d63eb |
| Tag | v0.3.0-m3-baseline |
| Build | ✅ 4 packages, 2min 2s |
| Test | ✅ 32 tests, 0 failures |

---

## Python Coordinator Contract

### Topic Contract

| Topic | Type | Direction | Status |
|-------|------|-----------|--------|
| `/fleet/heartbeat` | RobotHeartbeat | pub/sub | ✅ 正确 |
| `/fleet/pose` | RobotPose | pub/sub | ✅ 正确 |
| `/fleet/planned_path` | PlannedPath | pub/sub | ✅ 正确 |
| `/fleet/yield` | YieldCommand | pub/sub | ✅ 正确 |
| `fleet/coordinator_status` | std_msgs/String (JSON) | pub (diagnostic only) | ⚠️ 诊断用 |
| `fleet/coordinator_speed` | RobotPose | pub (internal) | ⚠️ 内部用 |

### Command Types

```python
CMD_REQUEST_YIELD = 0
CMD_ACK_YIELD = 1
CMD_RESUME = 2
CMD_EMERGENCY_STOP = 3
```

### coordinator_status JSON Format

```json
{
  "robot_id": "robot_a",
  "state": "NORMAL",
  "speed_ratio": 1.0,
  "peers": [
    {
      "robot_id": "robot_b",
      "distance": 5.2,
      "state": "NORMAL",
      "priority_score": 12.5
    }
  ]
}
```

**重要**: `/fleet/coordinator_status` 是诊断路径，**不是生产控制契约**。生产控制契约使用 `/fleet/yield` + `fleet_msgs/YieldCommand`。

---

## BT Contract Before

| 节点 | 问题 |
|------|------|
| CheckFleetConflict | Bug: 直接比较 JSON 字符串与 "YIELDING" |
| AdjustSpeedForFleet | Bug: 同上，永远 fallback 到 default_speed |
| WaitForYieldClear | 使用 std_msgs/String + `fleet/yield_command` |

---

## BT Contract After

### Topic Contract

| Topic | Type | Direction | Status |
|-------|------|-----------|--------|
| `/fleet/coordinator_status` | std_msgs/String (JSON) | sub (diagnostic) | ✅ 诊断用 |
| `/fleet/yield` | YieldCommand | pub/sub | ✅ 生产路径 |

### CheckFleetConflict

- 订阅 `/fleet/coordinator_status` (诊断)
- 解析 JSON 中的 `state` 字段
- 返回 SUCCESS if `state` in {YIELDING, PASSING, EMERGENCY}
- 输出 `fleet_state` 和 `conflict_peer` 到 blackboard
- conflict_peer 暂时输出 "unknown"（精确提取是 S1-B 任务）

### AdjustSpeedForFleet

- 订阅 `/fleet/coordinator_status` (诊断)
- 解析 JSON 中的 `speed_ratio` 或 `state`
- 优先使用 `speed_ratio`，否则根据 `state` fallback
- 速度映射:
  - NORMAL: 1.0
  - AWARENESS: 1.0
  - CAUTION: 0.5
  - YIELDING: 0.0
  - PASSING: 0.3
  - EMERGENCY: 0.0
- **注意**: 当前实现仍使用 cmd_vel 拦截作为安全兜底。真实 Nav2 SpeedLimit 集成是 S1-B 任务。

### WaitForYieldClear

- 订阅 `/fleet/yield` (YieldCommand)
- 发布 `/fleet/yield` (YieldCommand)
- 使用 CMD_ACK_YIELD, CMD_RESUME 作为命令类型
- 等待 RESUME 或 ACK_YIELD 后返回 SUCCESS
- 超时返回 FAILURE
- **已移除** `fleet/yield_command` (String) 路径

---

## Modified Files

| 文件 | 修改内容 |
|------|---------|
| `package.xml` | 添加 fleet_msgs 依赖 |
| `CMakeLists.txt` | 添加 fleet_msgs 依赖 |
| `check_fleet_conflict.hpp` | 添加 conflict_peer OutputPort |
| `check_fleet_conflict.cpp` | 修复 JSON 解析 |
| `wait_for_yield_clear.hpp` | 改为使用 YieldCommand 类型 |
| `wait_for_yield_clear.cpp` | 切换到 /fleet/yield + YieldCommand |
| `adjust_speed_for_fleet.hpp` | 添加 current_speed_ratio_ 成员 |
| `adjust_speed_for_fleet.cpp` | 修复 JSON 解析 |

---

## Test Results

| 项目 | 值 |
|------|-----|
| Build | ✅ 4 packages, 2min 2s |
| Test | ✅ 32 tests, 0 errors, 0 failures, 0 skipped |

---

## S1-A Completed

- [x] CheckFleetConflict JSON 解析修复
- [x] AdjustSpeedForFleet JSON 解析修复
- [x] WaitForYieldClear 切换到 /fleet/yield + YieldCommand
- [x] 添加 conflict_peer OutputPort
- [x] 添加 fleet_msgs 依赖
- [x] Build 通过
- [x] Test 通过
- [x] 文档更新

---

## S1-B Remaining

- [ ] Nav2 SpeedLimit / controller 真实限速验证
  - 当前 AdjustSpeedForFleet 使用 cmd_vel 拦截作为安全兜底
  - 需要验证 Nav2 控制器是否支持 SpeedLimit Topic
- [ ] conflict_peer 更精确提取
  - 当前输出 "unknown"
  - 需要从 peers 数组中解析冲突 peer
- [ ] Gazebo / BT runtime 验证
  - 需要在仿真环境中验证完整的让行流程
- [ ] fleet_msgs 中添加 command 常量定义
  - 当前 C++ 和 Python 各定义一套常量
  - 应统一到 fleet_msgs 包中

---

## Known Risks

1. **JSON 解析鲁棒性**: 当前使用简单的字符串查找，不是完整 JSON 解析器。对于格式变化的 JSON 可能会失败。短期内可接受，S2 可考虑引入 jsoncpp。
2. **command 常量分散**: CMD_* 常量在 Python coordinator 和 C++ BT 节点中各定义一份，应统一到 fleet_msgs。
3. **cmd_vel 拦截**: AdjustSpeedForFleet 仍发布 cmd_vel 作为安全兜底，不是最终 Nav2 原生集成。

---

## Recommendation

### 是否建议进入 S1-B / S3？

**是** - S1-A 已完成基本修复，可以进入 S1-B 或 S3-M3 场景测试。

### 下一步建议

1. **S1-B**: 完成 Nav2 SpeedLimit 集成验证
2. **S3-M3**: 执行完整场景测试
3. **技术债清理**: 统一 command 常量到 fleet_msgs

---

## Appendix: Build/Test Commands

```bash
# Build
cd /home/guolinlin/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install

# Test
source install/setup.bash
colcon test
colcon test-result --verbose
```

---

## Appendix: Modified File Diff Summary

```
package.xml: +fleet_msgs dependency
CMakeLists.txt: +fleet_msgs dependency
check_fleet_conflict.hpp: +OutputPort conflict_peer, +current_speed_ratio_
check_fleet_conflict.cpp: +JSON field extractor, parse state from JSON
wait_for_yield_clear.hpp: +fleet_msgs/YieldCommand, +yield_sub_, -resume_sub_
wait_for_yield_clear.cpp: use /fleet/yield + YieldCommand, CMD_* constants
adjust_speed_for_fleet.hpp: +current_speed_ratio_ member
adjust_speed_for_fleet.cpp: +JSON speed_ratio extractor, getSpeedScaling fix
```
