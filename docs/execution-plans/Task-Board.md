# Task Board - YieldNet 多机避撞协同系统

> Last Updated: 2026-04-16

## Sprint 1: S1-M1 通信基础 ✅ COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| T1-01: Define fleet_msgs | ✅ Done | RobotHeartbeat, RobotPose, PlannedPath, YieldCommand |
| T1-02: Implement publishers/subscriptions | ✅ Done | heartbeat/pose/path at correct frequencies |
| T1-03: Configure DDS Domain 42 | ✅ Done | fleet topics on Domain 42 |
| T1-04: Basic peer state tracking | ✅ Done | PeerState with last_seen |

---

## Sprint 2: S2-M4 多机扩展 ✅ CODE COMPLETE

| Task | Status | Notes |
|------|--------|-------|
| T2-01: Per-peer state management | ✅ Done | Dict[str, PeerState] |
| T2-02: 6-state machine | ✅ Done | NORMAL→AWARENESS→CAUTION→YIELDING/PASSING→EMERGENCY |
| T2-03: Distance thresholds | ✅ Done | 0.8/2.5/4.0/8.0m |
| T2-04: Path conflict detection | ✅ Done | 5-tick hysteresis |
| T2-05: Dynamic priority scoring | ✅ Done | yield_count, dist_to_goal, battery |
| T2-06: Yield negotiation | ✅ Done | REQUEST_YIELD/ACK_YIELD/RESUME |
| T2-07: Yield timeout | ✅ Done | 15s auto RESUME |
| T2-08: Heartbeat timeout | ✅ Done | 6s peer removal |
| T2-09: Unit tests | ✅ Done | 32 tests passing |

### S2-M4 验收标准 ⏳ 待验证

| Acceptance Criteria | Status | Verification Method |
|---------------------|--------|---------------------|
| AC1: State transitions at distance thresholds | ⏳ | Mock test or integration test |
| AC2: Path conflict detection (crossing/parallel/T) | ⏳ | Unit tests (need re-verify) |
| AC3: Priority - lexicographic tiebreaker | ⏳ | Unit tests (need re-verify) |
| AC4: Priority - dynamic scoring | ⏳ | Unit tests (need re-verify) |
| AC5: Yield negotiation flow | ⏳ | Integration test |
| AC6: Yield timeout 15s | ⏳ | Mock test |
| AC7: 3-robot queuing | ⏳ | Integration test |

---

## Sprint 3: S3-M3 场景测试 (Gazebo) ⏳ NEXT

### T3-01: 环境准备

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T3-01a | ✅ | - | Install Gazebo 11.10.2 on cloud |
| T3-01b | ✅ | - | Create corridor world (20m × 3m) |
| T3-01c | ✅ | - | Create T-intersection world |
| T3-01d | ✅ | - | Create 3-robot spawn config |

### T3-02: 双机测试

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T3-02a | ✅ | - | **RESOLVED**: Pre-modify SDF to add robot namespace before spawn. robot_a and robot_b both spawn successfully with proper ROS topic isolation |
| T3-02b | ✅ | - | **VERIFIED**: Both robots correctly transitioned through coordination states (NORMAL->CAUTION->EMERGENCY->CAUTION->AWARENESS) when approaching each other. Coordinators use local odom to track positions and detect peers via /fleet/pose. **Key fix**: Added odom callback to get real position instead of default (0,0) |
| T3-02c | ⏳ | - | Verify: T-intersection → correct priority ordering |
| T3-02d | ⏳ | - | Record behavior logs |

**Solution Applied**: Modified SDF files with unique namespaces (robot_a/robot_b) before spawning. Each robot gets isolated topics: `/robot_a/scan`, `/robot_a/imu`, `/robot_b/scan`, `/robot_b/imu`, etc.

**Current Status**:
- Gazebo: Running with robot_a and robot_b spawned
- Fleet Coordinators: Both running with correct parameters (robot_a and robot_b)
- **Next step needed**: Spawn robot_c, start coordinator, verify 3-robot queuing

### T3-03: 三机测试 (跳过M2，直接N机)

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T3-03a | ✅ | - | **DONE**: All 3 robots spawned, all 3 coordinators running, mutual discovery confirmed |
| T3-03b | ✅ | - | **DONE**: mock_path_publisher_all.py 已创建于 `ros2_ws/src/fleet_gazebo/scripts/` |
| T3-03c | ✅ | - | **DONE**: test_multi_robot.sh 已创建，支持3机器人同时启动 |

**Note**: M2双机验证跳过 - M4 per-peer架构天然支持N机，无需单独双机测试

**3机验证证据** (2026-04-16):
- robot_a: 发现 robot_b + robot_c → CAUTION ✓ (peer距离~5.66m)
- robot_b: 发现 robot_a + robot_c → CAUTION ✓ (peer距离~5.66m)
- robot_c: 发现 robot_b + robot_a ✓
- mock_path_publisher 正常发布PlannedPath ✓

**已修复**: coordinator_speed消息类型不匹配问题 - robot_mover使用PoseStamped订阅，但fleet_coordinator发布RobotPose类型。已更新move_robots_to_center.py使用RobotPose类型订阅。

**已验证** (2026-04-16):
1. ✓ NORMAL → AWARENESS → CAUTION → EMERGENCY 状态转移正确
2. ✓ EMERGENCY在距离<0.8m时正确触发
3. ✓ Speed ratio正确计算 (EMERGENCY=0.0, CAUTION=0.5)
4. ✓ robot_mover正确接收coordinator_speed并控制机器人速度
5. ✓ 3机器人互相发现并进行协调

**解决方案**: 创建了模拟路径发布器和多机测试脚本
- `scripts/mock_path_publisher_all.py` - 同时为3个机器人发布模拟PlannedPath
- `scripts/test_multi_robot.sh` - 完整3机器人测试启动脚本
- 基于机器人当前odometry位置和朝向，生成前方5米的路径点
- QoS使用BEST_EFFORT，与协调器订阅匹配

**部署步骤**:
1. 复制 `mock_path_publisher_all.py` 到云服务器 `/tmp/`
2. 复制 `test_multi_robot.sh` 到云服务器 `/tmp/`
3. 执行 `bash /tmp/test_multi_robot.sh`
4. 观察协调器日志中的状态转移

### T3-04: 异常测试

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T3-04a | ⏳ | - | WiFi disconnect 6s → robots resume independent |
| T3-04b | ⏳ | - | Measure wireless bandwidth (≤10 KB/s target) |

---

## Sprint 4: S4-M5 稳定性验证

### T4-01: 长期运行测试

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T4-01a | ⏳ | - | 7-day × 8h continuous run |
| T4-01b | ⏳ | - | Random scenario generator |
| T4-01c | ⏳ | - | Zero collision target |

### T4-02: 性能验证

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T4-02a | ⏳ | - | Average yield delay ≤ 15s |
| T4-02b | ✅ Done | - | **VERIFIED**: 3-robot bandwidth = ~2.87 KB/s (well under 10 KB/s target). Details: pose ~191 B/s, heartbeat ~123 B/s, planned_path ~2.63 KB/s |

---

## Sprint 5: S5-M2* 双机验证 (Optional)

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T5-01 | ⏳ | - | Run 2-robot Gazebo scenario |
| T5-02 | ⏳ | - | Verify M4 works for N=2 |

---

## Next Action

**已完成**:
- ✅ T3-03 多机测试环境搭建完成
- ✅ mock_path_publisher_all.py 创建并验证
- ✅ test_multi_robot.sh 创建并验证
- ✅ 3机互相发现验证通过
- ✅ 移动导航集成测试完成
- ✅ EMERGENCY状态在距离<0.8m时正确触发
- ✅ **已修复**: robot_mover现在正确接收coordinator_speed并控制机器人速度
- ✅ **性能验证通过**: 3机总带宽 ~2.87 KB/s (目标≤10 KB/s) ✓

**已验证的协调逻辑** (2026-04-16):
- 状态机: NORMAL→AWARENESS→CAUTION→EMERGENCY ✓
- EMERGENCY触发: 距离<0.8m时所有机器人立即停车 ✓
- Speed ratio: EMERGENCY时正确输出0.0, CAUTION时输出0.5 ✓
- robot_mover订阅coordinator_speed: RobotPose类型匹配 ✓
- 机器人实际按协调器速度控制移动 ✓

**测试命令** (在云服务器上):
```bash
# 查看协调器状态
tail -f /tmp/coord_a.log

# 查看路径发布
tail -f /tmp/mock_path.log

# 查看机器人移动
tail -f /tmp/robot_mover.log
```
