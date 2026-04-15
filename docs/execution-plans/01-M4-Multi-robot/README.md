# Execution Plan: M4 Multi-robot Extension First

> **Revised Strategy**: Per-peer architecture naturally handles N robots.
> Skip M2 (dual-robot) and implement M4 (multi-robot) first.
> M2 becomes a validation scenario for M4.

## Rationale

The original plan sequenced: M1 → M2 → M3 → M4 → M5

The new plan sequences: M1 → **M4** → M3 → M5

**Why M4 before M2?**
- Per-peer architecture (§8 of SAD) is designed for N-robot scalability
- M2 dual-robot is simply M4 with 1 peer - no additional logic needed
- Implementing M4 first avoids rework: M2 would require refactoring to M4
- M4's state machine, priority calculation, and path conflict detection are the core

## Revised Sprint Sequence

| Sprint | Milestone | Description | Key Deliverables |
|--------|-----------|-------------|------------------|
| S1 | M1 | Communication Foundation | fleet_msgs, heartbeat/pose/path subscriptions |
| **S2** | **M4** | **Multi-robot Extension** | per-peer state, 6-state machine, dynamic priority, path conflict, yield negotiation |
| S3 | M3 | Scene Testing | Gazebo simulation, 2-robot and 3-robot scenarios |
| S4 | M5 | Stability Verification | 7-day stress test, bandwidth validation |
| S5 | M2* | Dual-robot Validation | M4 naturally handles 2 robots - M2 is subset |

*M2 is not a separate sprint - it's a validation that M4 works for N=2*

## Sprint Details

### S1: M1 - Communication Foundation
**Duration**: 2 days
**Goal**: Establish ROS 2 fleet communication infrastructure

**Tasks**:
- [x] Define fleet_msgs (RobotHeartbeat, RobotPose, PlannedPath, YieldCommand)
- [x] Implement heartbeat/pose/path publishers and subscriptions
- [x] Configure DDS Domain 42 for fleet topics
- [x] Basic peer state tracking

**Acceptance Criteria**:
- [ ] `rostopic list` shows `/fleet/heartbeat`, `/fleet/pose`, `/fleet/planned_path`, `/fleet/yield`
- [ ] Two robots can exchange heartbeat at 0.5 Hz
- [ ] Pose updates at 10 Hz, path updates at 2 Hz

---

### S2: M4 - Multi-robot Extension (PER-PEER ARCHITECTURE)
**Duration**: 5 days
**Goal**: Implement full per-peer coordination with dynamic priority

**Tasks**:
- [x] Per-peer state management (Dict[str, PeerState])
- [x] 6-state coordination state machine
  - [x] NORMAL → AWARENESS → CAUTION → YIELDING/PASSING → EMERGENCY
  - [x] Distance thresholds: 0.8m, 2.5m, 4.0m, 8.0m
- [x] Path conflict detection with hysteresis (5-tick debounce)
- [x] Dynamic priority scoring:
  - [x] yield_count × 10.0
  - [x] (1/dist_to_goal) × 5.0
  - [x] (100 - battery_pct) × 0.1
- [x] Yield negotiation (REQUEST_YIELD/ACK_YIELD/RESUME)
- [x] Yield timeout protection (15s)
- [x] Heartbeat timeout handling (6s → peer removal)
- [x] Most-conservative-wins logic across all peers
- [x] Unit tests (32 tests passing)

**Acceptance Criteria**:
- [ ] State transitions correctly trigger at distance thresholds
- [ ] Path conflict detection works for crossing/parallel/T-intersection
- [ ] Priority comparison correctly handles:
  - [ ] Lexicographic tiebreaker (robot_id)
  - [ ] Dynamic scoring (yield_count, dist_to_goal, battery)
- [ ] Yield negotiation: REQUEST → ACK → RESUME flow
- [ ] Timeout: YIELDING > 15s → auto RESUME
- [ ] 3-robot scenario: highest priority passes, others queue

---

### S3: M3 - Scene Testing (Gazebo)
**Duration**: 3 days
**Goal**: Validate in simulation

**Tasks**:
- [ ] Set up Gazebo world with corridor/T-intersection
- [ ] Spawn 2 robots, verify collision avoidance
- [ ] Spawn 3 robots, verify multi-robot queuing
- [ ] Test WiFi disconnect → recovery behavior
- [ ] Measure wireless bandwidth (target ≤ 10 KB/s)

**Acceptance Criteria**:
- [ ] Opposing robots in corridor: one yields, one passes
- [ ] T-intersection: correct priority ordering
- [ ] 3-robot: A→B→C priority order maintained
- [ ] WiFi disconnect 6s: robots resume independent operation

---

### S4: M5 - Stability Verification
**Duration**: 7 days
**Goal**: Long-running validation

**Tasks**:
- [ ] 7-day × 8h continuous run
- [ ] Random scenario generator (opposing, T-intersection, 3-way)
- [ ] Bandwidth monitoring
- [ ] Log analysis for anomalies

**Acceptance Criteria**:
- [ ] Zero collisions during 56 total hours
- [ ] Average yield delay ≤ 15s
- [ ] Wireless bandwidth ≤ 10 KB/s sustained

---

### S5: M2* - Dual-robot Validation (Optional)
**Duration**: 1 day
**Goal**: Confirm M4 works for N=2

**Note**: M2 is NOT a separate implementation - M4's per-peer architecture
automatically handles N=2. This sprint is only for validation testing
if needed.

**Tasks**:
- [ ] Run 2-robot Gazebo scenario
- [ ] Verify dual-robot collision avoidance works

---

## Dependency Graph

```
M1 (Communication)
    ↓
M4 (Multi-robot Core) ← PRIMARY FOCUS
    ↓
M3 (Gazebo Testing)
    ↓
M5 (Stability)
    ↓
M2* (Validation - optional)
```

## Key Files

| File | Purpose |
|------|---------|
| `fleet_coordination/fleet_coordinator.py` | Main coordination node (~500 lines) |
| `fleet_coordination/peer_state.py` | PeerState dataclass + CoordinationState enum |
| `test/test_*.py` | 32 unit tests (all passing) |

## Status

| Sprint | Status |
|--------|--------|
| S1: M1 | ✅ Complete |
| S2: M4 | ✅ Code Complete, Tests Pass |
| S3: M3 | ⏳ Pending |
| S4: M5 | ⏳ Pending |
| S5: M2* | ⏳ Optional |
