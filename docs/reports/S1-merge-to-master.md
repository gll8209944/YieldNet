# S1 Merge to Master

**日期**: 2026-05-08
**source 分支**: s1-bt-protocol-alignment
**target 分支**: master
**source commit**: 37c33d8
**merge commit**: 7ab3065

---

## Summary

S1 契约对齐成果已合并到 master。包含 S1-A (BT yield protocol) 和 S1-B (Nav2 SpeedLimit)。

---

## S1-A: BT Yield Protocol Alignment

**Commit**: 6c7793d

**修复内容**:
1. CheckFleetConflict: 修复 JSON 状态解析 bug
2. AdjustSpeedForFleet: 修复 JSON 状态解析 bug
3. WaitForYieldClear: 切换到 /fleet/yield + fleet_msgs/YieldCommand
4. 添加 conflict_peer OutputPort
5. 添加 fleet_msgs 依赖

**Topic Contract**:
- `/fleet/yield`: fleet_msgs/YieldCommand (生产路径) ✅
- `fleet/coordinator_status`: std_msgs/String (诊断路径) ✅

---

## S1-B: Nav2 SpeedLimit Integration

**Commit**: 3eadf47

**修复内容**:
1. 添加 nav2_msgs 依赖到 adjust_speed_for_fleet
2. 实现 Nav2 SpeedLimit topic 发布 (生产路径)
3. 移除 cmd_vel 拦截 (安全兜底已不再需要)

**Topic Contract**:
- `/speed_limit`: nav2_msgs/SpeedLimit (Nav2 原生) ✅

---

## S3-M3 Smoke Test

**Commit**: 37c33d8

**结论**: PARTIAL PASS (B)

| 项目 | 值 |
|------|-----|
| Build | ✅ 4 packages, 0 errors |
| Test | ✅ 32 tests, 0 failures |
| 静态协议检查 | ✅ S1-A + S1-B 全部通过 |
| 场景测试 | ✅ 单元测试覆盖核心逻辑 |

---

## Build Result (Master)

| 项目 | 值 |
|------|-----|
| Status | ✅ PASS |
| Packages | 4 |
| Duration | 1min 43s |
| Warnings | 2 reorder warnings (check_fleet_conflict.hpp) |
| Errors | 0 |

---

## Test Result (Master)

| 项目 | 值 |
|------|-----|
| Status | ✅ PASS |
| Tests | 32 |
| Errors | 0 |
| Failures | 0 |
| Skipped | 0 |

---

## Remaining Risks

1. **Reorder warnings**: check_fleet_conflict.hpp 初始化顺序不一致 (非阻塞)
2. **S3-M3 full runtime**: 完整 BT runtime + Gazebo 仿真未执行
3. **speed_limit runtime**: Nav2 controller 集成需场景观测
4. **JSON 解析鲁棒性**: 简单字符串查找，非完整 JSON 解析器
5. **S2-S8 尚未完成**

---

## No Tag Created

本次 merge 不创建 tag。等待用户确认后决定是否创建 v0.4.0 或类似 tag。

---

## Next Recommended Phase

由用户选择:
- A. 进入 S2: 配置外置化与安全默认值
- B. 进入 S3-M3-full: 完整 Gazebo runtime 场景验证
- C. 先清理 reorder warnings / ECS 工作区历史标记

---

## Merge History

| Date | Commit | Description |
|------|--------|-------------|
| 2026-05-07 | d2d63eb | S0 baseline (v0.3.0-m3-baseline) |
| 2026-05-07 | 6c7793d | S1-A: BT yield protocol alignment |
| 2026-05-07 | 3eadf47 | S1-B: Nav2 SpeedLimit integration |
| 2026-05-08 | 353ad1c | Merge PR #1 (S1-B) |
| 2026-05-08 | 37c33d8 | S3-M3 scenario test report |
| 2026-05-08 | 7ab3065 | Merge S1 into master |
