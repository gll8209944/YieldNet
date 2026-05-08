# S3-M3 Scenario Test Report

**日期**: 2026-05-08  
**场景**: corridor-2robot + BT runner `/speed_limit` smoke  
**分支**: master  

---

## Summary

S3-M3 场景测试中，corridor-2robot 与 fleet coordinator 行为已验证；Nav2 全栈与 yield/resume 仍缺。`fleet_bt_runner` 已修复：`AdjustSpeedForFleet` 符合 Decorator 结构，且通过 blackboard `node` 挂到被 `spin` 的 `fleet_bt_runner`，使 `/fleet/coordinator_status` 订阅与 `speed_limit` 发布在 standalone 下可工作。已在隔离 `ROS_DOMAIN_ID` 下完成 `/speed_limit` smoke（见下文专节）。

**阻塞项（相对完整 M3）**:
1. 完整 Nav2 stack（`nav2_bringup` / `bt_navigator`）仍未纳入本报告测试流程  
2. 机器人静止 / 无规划路径，yield / resume 与 YIELDING→PASSING 全循环仍缺  

**结论**: **PARTIAL PASS (B)** — corridor 与 BT runner `/speed_limit` smoke 可走通；整机 M3 与 Nav2 一体化未 PASS。

---

## 1. Environment

| Item | Value |
|------|-------|
| ROS 2 | Humble |
| Gazebo | 11 (headless) |
| Fleet Coordinator | ✅ Built & Working |
| Nav2 BT standalone runner | ✅ `fleet_bt_runner` 可加载并 tick `AdjustSpeedForFleet` |
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

## Scenario: BT runner SpeedLimit smoke

### Run command（ECS，`ROS_DOMAIN_ID` 隔离示例）

为避免与现场其他 DDS 参与者混叠，单机 smoke 建议使用独立 domain（示例 `99`）：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=99
cd /home/guolinlin/ros2_ws/ros2_ws   # 依部署调整
source install/setup.bash

ros2 run fleet_nav2_bt fleet_bt_runner
```

另一终端注入与订阅者 QoS 对齐的 transient_local + reliable 诊断消息，并观测限速：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=99
cd /home/guolinlin/ros2_ws/ros2_ws && source install/setup.bash

ros2 topic pub --once /fleet/coordinator_status std_msgs/msg/String \
  'data: '\''{"robot_id":"robot_a","state":"CAUTION","speed_ratio":0.5,"peers":[]}'\''' \
  --qos-history keep_last --qos-depth 1 --qos-reliability reliable --qos-durability transient_local

ros2 topic type /speed_limit
ros2 topic echo /speed_limit nav2_msgs/msg/SpeedLimit
```

### Modified files

| Path | Change |
|------|--------|
| `ros2_ws/src/fleet_nav2_bt/src/fleet_bt_runner.cpp` | `AdjustSpeedForFleet` 内嵌 `AlwaysSuccess`；将该装饰器前置到 `Sequence` 首部；blackboard：`robot_id`、`peer_id`、`node`；可选参数 `peer_id`、`bt_xml` |
| `ros2_ws/src/fleet_nav2_bt/include/fleet_nav2_bt/bt_ros_host_utils.hpp` | 读取 blackboard **`node`**（Nav2 惯例），缺失时退回匿名 `rclcpp::Node` |
| `ros2_ws/src/fleet_nav2_bt/src/adjust_speed_for_fleet.cpp` | 使用共享 host `node` |
| `ros2_ws/src/fleet_nav2_bt/src/check_fleet_conflict.cpp` | 同上 |
| `ros2_ws/src/fleet_nav2_bt/src/wait_for_yield_clear.cpp` | 同上 |

`behavior_trees/navigate_with_fleet.xml` 已为 `AdjustSpeedForFleet` 提供 `FollowPath` 子节点，**无需为 Nav2 BT 改名修改**。

### BT XML fix summary

- 叶子写法 `<AdjustSpeedForFleet …/>` → 包裹 **单子节点**：`<AlwaysSuccess/>`（smoke）。
- **`Sequence` 顺序**：在无冲突、`CheckFleetConflict` 返回 FAILURE 时，`Sequence` 会在同一 tick 内提前结束；将 `AdjustSpeedForFleet` 置于序列 **首位**，保证每次 tick 仍可执行限速装饰器并发 `speed_limit`（standalone 冒烟专用顺序；正式 Nav2 树仍以 `navigate_with_fleet.xml` 为准）。

### Node type finding

| 节点 | BehaviorTree.CPP 基类 |
|------|----------------------|
| `AdjustSpeedForFleet` | `BT::DecoratorNode`（`adjust_speed_for_fleet.hpp`） |
| 子节点约束 | Decorator **必须恰好 1 个子**；先前崩溃信息：`must have exactly 1 child` |
| `AlwaysSuccess` | Factory 内置注册，XML 直接使用 |

### Spin / executor 说明（standalone 根因）

仅 `rclcpp::spin(fleet_bt_runner)` 时，插件内 **`Node::make_shared` 孤立节点** 的订阅不在执行器内，**收不到** `/fleet/coordinator_status`。通过 blackboard **`node`** 指向被 spin 的 `fleet_bt_runner`，与 Nav2 `bt_navigator` 向 BT 黑板注入 ROS 节点的模式一致。

### Build / test（ECS，`/home/guolinlin/ros2_ws/ros2_ws`）

| Step | Result |
|------|--------|
| `colcon build --symlink-install` | ✅ 通过；`fleet_nav2_bt` 仍有 `CheckFleetConflict` 成员 **[-Wreorder]**（既有） |
| `colcon test` | ✅ `32 tests, 0 failures` |

### Topics observed（`ROS_DOMAIN_ID=99`）

| Topic | Type |
|-------|------|
| `/speed_limit` | `nav2_msgs/msg/SpeedLimit` |
| `/fleet/coordinator_status` | smoke：`std_msgs/msg/String`（JSON，与 coordinator 诊断格式对齐） |

### `/speed_limit` observation

- **类型**：`nav2_msgs/msg/SpeedLimit`
- **`percentage`**：`true`（实现于 `adjust_speed_for_fleet.cpp`）
- **映射**：`speed_ratio 0.5 → speed_limit 50.0`；`0.0 → 0.0`；恢复 `1.0 → 100.0`（以 `fleet_bt_runner` 日志中 `published speed_limit=…` 为证）
- **去重**：`|Δ ratio| > 0.01` 才再次发布，避免刷消息

### State / speed_ratio relation

订阅 JSON **优先**解析数值字段 `speed_ratio`；否则读 `state` 字符串并按 SAD 状态表映射（如 CAUTION→0.5，YIELDING→0.0）。

### Limitations

- 验证范围：**standalone** `fleet_bt_runner`，**未**包含 `bt_navigator`、真实 `FollowPath`、ProgressChecker、全机 yield/resume 闭环。
- M3 corridor 场景中 **yield / resume、碰撞率、死锁、emergency** 仍以 §2 / §4 既有记录为准；本子场景不扩展为全量 M3 PASS。

### Final verdict（本子场景）

**PARTIAL PASS**：BT 可加载、`AdjustSpeedForFleet` 被 tick、`/speed_limit` 可按预期发布且比率映射正确；**非**完整 Nav2+M3 PASS。

### Remaining risks / next steps

1. `navigate_with_fleet.xml` + `nav2_bringup` / `bt_navigator` 端到端复验 `speed_limit` 对控制器生效。  
2. 机器人移动 + 路径冲突，补 YIELDING/PASSING 与 `/fleet/yield`。  
3. 评估是否将 `CheckFleetConflict` 构造成员顺序 **[-Wreorder]** 清零（无关功能，降噪）。

---


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
| /speed_limit runtime | ✅ **smoke** PASS | standalone `fleet_bt_runner` + 隔离 `ROS_DOMAIN_ID`；日志 `published speed_limit=50/0/100`；`ros2 topic type` 为 `nav2_msgs/msg/SpeedLimit` |
| YIELD/PASS states | ⚠️ BLOCKED | 机器人静止 |
| Nav2 BT integration | ⚠️ PARTIAL | standalone 已验证；**未**接入 `bt_navigator` 全栈 |

---

## 6. Remaining Risks

| Item | Status | Notes |
|------|--------|-------|
| t-intersection | ❌ 未测试 | - |
| corridor-3robot | ❌ 未测试 | - |
| heartbeat timeout | ❌ 未测试 | - |
| domain isolation | ❌ 未测试 | - |
| emergency stop (close) | ⚠️ 部分验证 | 触发但短暂 |
| /speed_limit integration | ⚠️ **standalone** smoke 通过；全 Nav2 未验 | 本子场景 §「BT runner SpeedLimit smoke」|
| Nav2 BT + fleet | ❌ 未验证 | 未配置 |
| yield/resume | ❌ 未验证 | 机器人静止 |
| Nav2 ProgressChecker recovery | ❌ 未验证 | BT 未运行 |

---

## 7. Recommendations

### Immediate Fixes Needed

1. **fleet_bt_runner**：XML 子节点、`Sequence` 顺序与 blackboard `node` — **已完成**，见 «Scenario: BT runner SpeedLimit smoke»
2. **/speed_limit**：standalone 冒烟 **已完成**；**待** Nav2 `bt_navigator` 全链路  
3. **添加机器人移动**:
   - 触发实际路径冲突
   - 验证 YIELDING/PASSING 状态
   - 验证 yield/resume 循环

### Full S3-M3 Validation Path

1. ✅ corridor-2robot (smoke) - DONE
2. ✅ corridor-2robot (60s runtime) - DONE
3. ⚠️ /speed_limit **全 Nav2 控制器链** verification — standalone 已通过，**bt_navigator** 仍未接
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
- Standalone **`fleet_bt_runner`**：`AdjustSpeedForFleet` 合法子节点、blackboard **`node`** 注入、`/speed_limit` smoke 与 `speed_ratio→百分比` 映射 ✅（见 «Scenario: BT runner SpeedLimit smoke»）

**阻塞项（完整 M3 / 全 Nav2）**:
- **`bt_navigator` + navigate_with_fleet**：控制器链路 `/speed_limit` 仍未端到端验证
- yield/resume 全闭环：机器人静止，路径冲突缺失

**需要跟进**:
1. Nav2 bringup + BT XML 全栈复验限速对跟踪器生效
2. 移动 / 导航触发 yield、 collision / deadlock 统计

**下一步**:
1. 接入 `nav2_bringup` / `bt_navigator`，复验 `/speed_limit`
2. corridor-3robot、t-intersection 等 Task-Board 条目
