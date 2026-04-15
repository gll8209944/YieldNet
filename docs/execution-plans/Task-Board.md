# Task Board - YieldNet 多机避撞协同系统

> Last Updated: 2026-04-15

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
| T3-02a | 🔄 | - | Spawn 2 robots in corridor |
| T3-02b | ⏳ | - | Verify: opposing robots → one yields, one passes |
| T3-02c | ⏳ | - | Verify: T-intersection → correct priority ordering |
| T3-02d | ⏳ | - | Record behavior logs |

### T3-03: 三机测试

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T3-03a | ⏳ | - | Spawn 3 robots |
| T3-03b | ⏳ | - | Verify: A→B→C priority order maintained |
| T3-03c | ⏳ | - | Verify: queuing without deadlock/starvation |

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
| T4-02b | ⏳ | - | Bandwidth ≤ 10 KB/s sustained |

---

## Sprint 5: S5-M2* 双机验证 (Optional)

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| T5-01 | ⏳ | - | Run 2-robot Gazebo scenario |
| T5-02 | ⏳ | - | Verify M4 works for N=2 |

---

## Next Action

**Next**: Start S3-M3 Gazebo 环境准备 (T3-01)

1. T3-01a: Install Gazebo 11.10.2
2. T3-01b: Create corridor world
3. T3-01c: Create T-intersection world
4. T3-01d: Create 3-robot spawn config
