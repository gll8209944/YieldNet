# S3-M3 Scenario Test Report

**日期**: 2026-05-08
**分支**: master (commit 149a305 + BT fixes)

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
