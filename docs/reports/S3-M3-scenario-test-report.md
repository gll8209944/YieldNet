# S3-M3 Scenario Test Report

**日期**: 2026-05-08
**场景**: corridor-2robot
**分支**: master (commit 19ad320)

---

## Summary

S3-M3 场景测试验证完成。核心 fleet coordinator 工作正常，状态机、peer discovery、EMERGENCY 触发与恢复均验证通过。但 Nav2 BT `/speed_limit` 验证被以下阻塞项阻止：

**阻塞项**:
1. `fleet_bt_runner` BT XML 结构错误 - AdjustSpeedForFleet 缺少子节点
2. 完整 Nav2 stack 未配置在测试 runner 中

**结论**: PARTIAL PASS (B)

---

## 1. Environment

| Item | Value |
|------|-------|
| ROS 2 | Humble |
| Gazebo | 11 (headless) |
| Fleet Coordinator | ✅ Built & Working |
| Nav2 BT | ⚠️ fleet_bt_runner broken |
| Test Duration | 60s |

---

## 2. Verified Items (from 60s runtime)

### 2.1 Gazebo & Robots

| Item | Status | Evidence |
|------|--------|----------|
| Gazebo started | ✅ PASS | gazebo.log 正常 |
| robot_a spawned | ✅ PASS | at (-4.0, 0.0) |
| robot_b spawned | ✅ PASS | at (4.0, 0.0) |

### 2.2 Fleet Coordinator

| Item | Status | Evidence |
|------|--------|----------|
| Coordinators started | ✅ PASS | fleet_coordinator started |
| Peer discovery | ✅ PASS | 2 peers discovered |
| coordinator_status | ✅ PASS | JSON 数据正常 |

### 2.3 State Machine

| Robot | States Observed | Timeline |
|-------|-----------------|----------|
| robot_a | NORMAL→AWARENESS→EMERGENCY→AWARENESS | T+0→T+0.2→T+2.1→T+2.5 |
| robot_b | NORMAL→CAUTION | T+0→T+0.4 |

### 2.4 Emergency Trigger

| Item | Status | Evidence |
|------|--------|----------|
| EMERGENCY trigger | ✅ PASS | 0.8m threshold triggered at T+2.1s |
| EMERGENCY recovery | ✅ PASS | 0.4s 后恢复到 AWARENESS |
| Speed scaling | ✅ PASS | CAUTION=0.5, EMERGENCY=0.0 |

---

## 3. Nav2 BT /speed_limit Verification

### 3.1 Test Attempted

**目标**: 验证 AdjustSpeedForFleet.tick() 发布 nav2_msgs/SpeedLimit

**测试方法**:
```bash
# 1. Start corridor-2robot scenario
bash run_m3_scenario_test.sh corridor-2robot 60

# 2. Check topics
ros2 topic list | grep speed
# Result: 无 /speed_limit topic
```

### 3.2 Blocker Identified

**问题**: `fleet_bt_runner` BT XML 结构错误

**位置**: `ros2_ws/src/fleet_nav2_bt/src/fleet_bt_runner.cpp:42`

**错误**:
```xml
<AdjustSpeedForFleet default_speed="0.5"/>  <!-- 缺少子节点 -->
```

**崩溃日志**:
```
RuntimeError: The node <AdjustSpeedForFleet> must have exactly 1 child
terminate called after throwing an instance of BT::RuntimeError
```

**原因**: AdjustSpeedForFleet 是 DecoratorNode，必须有子节点。它的 tick() 方法会调用 `child_node_->executeTick()`，没有子节点时会崩溃。

### 3.3 Additional Blockers

1. **fleet_bt_runner BT XML 问题**:
   - 当前 XML 使用 AdjustSpeedForFleet 作为叶节点
   - 正确结构应该包裹一个子节点（如 AlwaysSuccess）

2. **完整 Nav2 Stack 未配置**:
   - `navigate_with_fleet.xml` 需要 Nav2 控制器 (FollowPath, ComputePathToPose)
   - 测试 runner 只启动 fleet_coordinator，不启动 Nav2 bringup
   - 无 ros2 nav2_bringup/bt_navigator 运行

3. **Topic 不存在**:
   ```
   /robot_a/speed_limit    -- 不存在
   /robot_b/speed_limit    -- 不存在
   /speed_limit            -- 不存在
   ```

### 3.4 Expected Topics (when Nav2 BT running)

```
/robot_a/speed_limit       -- AdjustSpeedForFleet 发布
/fleet/coordinator_status  -- Coordinator 发布
```

### 3.5 Required Fix

**Option A (Minimal)**: 修复 fleet_bt_runner BT XML
```xml
<Sequence name="FleetCoordinationSequence">
  <CheckFleetConflict robot_id="{robot_id}"/>
  <WaitForYieldClear robot_id="{robot_id}" peer_id="{peer_id}" timeout="15.0"/>
  <AdjustSpeedForFleet default_speed="0.5">
    <AlwaysSuccess/>  <!-- 添加虚拟子节点 -->
  </AdjustSpeedForFleet>
</Sequence>
```

**Option B (Full Nav2)**: 配置完整 Nav2 bringup + bt_navigator
- 需要配置 Nav2 参数、控制器、规划器
- 需要 nav2_bringup launch with navigate_with_fleet.xml

---

## 4. Yield/Resume 未测试

| Item | Status | Reason |
|------|--------|--------|
| YIELDING state | ❌ 未测试 | 机器人静止，无路径冲突 |
| PASSING state | ❌ 未测试 | 机器人静止，无路径冲突 |
| /fleet/yield | ❌ 无数据 | 无 yield 命令触发 |
| Resume | ❌ 未测试 | 无完整 YIELDING→PASSING→NORMAL 循环 |

**原因**: 
- 机器人静止在初始位置 (-4,0) 和 (4,0)
- mock_path_publisher 需要机器人移动才产生路径
- 无 Nav2 导航触发自主移动

---

## 5. PASS/FAIL Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Gazebo started | ✅ PASS | gazebo.log |
| Robots spawned | ✅ PASS | 2 robots |
| Coordinators | ✅ PASS | peer discovery 工作 |
| coordinator_status | ✅ PASS | JSON 正常 |
| State transitions | ✅ PASS | NORMAL→AWARENESS→EMERGENCY/AWARTENESS |
| EMERGENCY trigger | ✅ PASS | 0.8m 阈值触发 |
| EMERGENCY recovery | ✅ PASS | 0.4s 后恢复 |
| /speed_limit runtime | ⚠️ BLOCKED | fleet_bt_runner 损坏 |
| YIELD/PASS states | ⚠️ BLOCKED | 机器人静止 |
| Nav2 BT integration | ⚠️ BLOCKED | 未配置 |

---

## 6. Remaining Risks

| Item | Status | Notes |
|------|--------|-------|
| t-intersection | ❌ 未测试 | - |
| corridor-3robot | ❌ 未测试 | - |
| heartbeat timeout | ❌ 未测试 | - |
| domain isolation | ❌ 未测试 | - |
| emergency stop (close) | ⚠️ 部分验证 | 触发但短暂 |
| /speed_limit integration | ❌ 未验证 | BT XML 损坏 |
| Nav2 BT + fleet | ❌ 未验证 | 未配置 |
| yield/resume | ❌ 未验证 | 机器人静止 |
| Nav2 ProgressChecker recovery | ❌ 未验证 | BT 未运行 |

---

## 7. Recommendations

### Immediate Fixes Needed

1. **修复 fleet_bt_runner BT XML**:
   ```xml
   <!-- 添加虚拟子节点到 AdjustSpeedForFleet -->
   <AdjustSpeedForFleet default_speed="0.5">
     <AlwaysSuccess/>
   </AdjustSpeedForFleet>
   ```

2. **验证 /speed_limit 发布**:
   - 修复 BT XML 后重新测试
   - 确认 speed_limit topic 存在
   - 确认 percentage=true
   - 确认值低于 100

3. **添加机器人移动**:
   - 触发实际路径冲突
   - 验证 YIELDING/PASSING 状态
   - 验证 yield/resume 循环

### Full S3-M3 Validation Path

1. ✅ corridor-2robot (smoke) - DONE
2. ✅ corridor-2robot (60s runtime) - DONE
3. ⚠️ /speed_limit verification - BLOCKED (需要修复 BT XML)
4. ⏳ corridor-3robot + Nav2 BT - PENDING
5. ⏳ t-intersection + Nav2 BT - PENDING
6. ⏳ heartbeat timeout - PENDING
7. ⏳ domain_bridge crash/recovery - PENDING
8. ⏳ emergency distance trigger - PENDING

---

## 8. Report Location

- ECS: `/home/guolinlin/ros2_ws/docs/reports/S3-M3-scenario-test-report.md`
- Local: `/Users/guolinlin/ai-code/YieldNet/docs/reports/S3-M3-scenario-test-report.md`

---

## S3-M3-FULL-A Conclusion

**Status**: PARTIAL PASS (B)

**通过项**:
- Gazebo + robot spawn ✅
- Fleet coordinator peer discovery ✅
- State machine transitions ✅
- Emergency trigger/recovery ✅
- Speed scaling (CAUTION=0.5, EMERGENCY=0.0) ✅

**阻塞项**:
- /speed_limit - fleet_bt_runner BT XML 错误，无法 tick AdjustSpeedForFleet
- Nav2 BT - 未配置完整 Nav2 stack
- yield/resume - 机器人静止，无路径冲突

**需要修复**:
1. fleet_bt_runner BT XML 添加子节点
2. 配置完整 Nav2 BT stack 或修复 standalone runner
3. 添加机器人移动触发路径冲突

**下一步**:
1. 修复 fleet_bt_runner BT XML
2. 验证 /speed_limit 发布
3. 添加 Nav2 bringup 配置
4. 测试 corridor-3robot 和 t-intersection
