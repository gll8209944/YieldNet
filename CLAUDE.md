# YieldNet / FleetGuard 执行约束

本文件定义 Claude Code / CC CLI 在 YieldNet / FleetGuard 仓库中的长期执行约束。

所有代码修改、测试、文档和部署工作都必须遵守本文件。

## 1. 项目身份

YieldNet / FleetGuard 是一个 ROS 2 多机器人协调避撞系统，用于同楼层多台讲解机器人在走廊、T 字路口等狭窄区域中实现安全、确定、可审计的协同通行。

本项目目标不是临时仿真 demo，而是可验收、可部署、可观测、可降级、可回滚的生产系统。

主要技术栈：

- ROS 2
- CycloneDDS
- domain_bridge
- Nav2
- BehaviorTree.CPP
- Gazebo 11
- Python 3
- C++

## 2. 事实来源

进行架构级修改前，必须先阅读并对齐以下文档：

- `docs/notion-sync/多机避撞协同系统 · PRD.md`
- `docs/notion-sync/多机避撞协同系统 · 系统架构设计.md`
- `docs/execution-plans/Task-Board.md`
- `docs/reports/` 下已有阶段报告

如果代码实现与 PRD / SAD 冲突，不要静默选择更容易的实现。必须先报告冲突、影响范围和最小安全修复方案。

## 3. 不可违背的架构原则

### 3.1 DDS 双 Domain 隔离

系统使用双 DDS Domain 架构：

- Domain 0：机器人内部通信，走有线 `eth0`
- Domain 42 / 43 / ...：同楼层机器人协同通信，走无线 `wlan0`

只有 `/fleet/*` Topic 可以进入无线 Fleet Domain。

禁止将以下内部 Topic 暴露到无线侧：

- `/tf`
- `/cmd_vel`
- `/scan`
- `/camera/*`
- `/odom`
- Nav2 内部 Topic
- SLAM / 感知 / 控制内部 Topic

### 3.2 Fleet Topic 白名单

标准 Fleet Topic 为：

- `/fleet/heartbeat`
- `/fleet/pose`
- `/fleet/planned_path`
- `/fleet/yield`

诊断 Topic：

- `/fleet/coordinator_status`

`/fleet/coordinator_status` 仅用于本机诊断、日志采集和可观测性，不应作为唯一生产控制契约。

### 3.3 消息协议

最终生产让行协议必须收敛到：

- Topic：`/fleet/yield`
- 类型：`fleet_msgs/msg/YieldCommand`

不要长期引入 `std_msgs/String` 命令协议。

如果当前代码中存在 String 兼容路径，只能作为过渡方案，必须在报告中记录为技术债，并给出收敛计划。

### 3.4 Nav2 原生集成

最终生产集成路线必须是 Nav2 Behavior Tree 原生集成。

标准 BT 节点：

- `CheckFleetConflict`
- `WaitForYieldClear`
- `AdjustSpeedForFleet`

不要用外部 `cmd_vel` 拦截替代最终生产架构。

`fleet_speed_controller` 可以作为：

- 仿真支持
- 过渡路径
- 安全兜底

但不能替代最终 Nav2 BT 原生集成，除非 PRD / SAD 被明确更新。

### 3.5 去中心化 per-peer 决策

系统必须保持去中心化：

- 不引入中心调度器
- 每台机器人独立评估所有 peer
- 每个 peer 独立决策
- 最终速度取所有 peer 中最保守结果
- 动态优先级防止饿死

未经明确要求，不要引入中央协调节点。

## 4. 标准状态机

标准状态：

1. `NORMAL`
2. `AWARENESS`
3. `CAUTION`
4. `YIELDING`
5. `PASSING`
6. `EMERGENCY`

标准速度缩放：

- `NORMAL`: 1.0
- `AWARENESS`: 1.0
- `CAUTION`: 0.5
- `YIELDING`: 0.0
- `PASSING`: 0.3
- `EMERGENCY`: 0.0

默认阈值：

- `AWARENESS_RANGE`: 8.0 m
- `CAUTION_RANGE`: 4.0 m
- `YIELD_RANGE`: 2.5 m
- `EMERGENCY_RANGE`: 0.8 m
- `PATH_CONFLICT_DIST`: 1.5 m
- `PATH_LOOKAHEAD`: 5.0 m
- `HEARTBEAT_TIMEOUT`: 6.0 s
- `YIELD_TIMEOUT`: 15.0 s

不要无理由修改默认值。修改时必须说明原因，并补充或更新测试。

## 5. 必测 P0 场景

M3 / P0 验收必须覆盖：

- 双机走廊对向会车
- 同向追赶
- 双机 T 字路口
- 三机 T 字路口 / 排队
- peer heartbeat timeout
- WiFi / Domain 42 中断与恢复
- emergency 距离触发
- 通信隔离：无线侧仅 `/fleet/*`
- 楼层隔离：Domain 42 / 43 互不可见
- domain_bridge 崩溃后 systemd 自动恢复

## 6. 测试规则

非平凡修改前后，必须在 `ros2_ws` 下运行：

- `colcon build --symlink-install`
- `colcon test`
- `colcon test-result --verbose`

不要破坏已有测试。

修改协调逻辑时，必须运行或补充：

- 状态机测试
- 优先级计算测试
- 路径冲突检测测试
- heartbeat timeout 测试
- yield timeout 测试
- 多 peer 最保守合并测试
- 消息协议兼容测试

修改 BT 集成时，必须验证：

- `fleet_nav2_bt` package 可构建
- plugin 注册可用
- behavior tree XML 可加载
- `WaitForYieldClear` 在等待让行期间返回 `RUNNING`
- 合法让行等待不会触发 Nav2 ProgressChecker recovery
- `AdjustSpeedForFleet` 能真实影响 Nav2 controller 速度限制

## 7. 安全规则

安全优先于代码美观。

禁止做出以下修改：

- 移除 emergency stop
- 增加碰撞风险但不补测试
- 忽略 heartbeat timeout
- 隐藏通信失败
- 扩大无线 Topic 暴露面
- 将仿真 odom workaround 作为生产 odom 来源

`cmd_vel_to_odom.py` 仅是 Gazebo / namespace workaround，不能进入生产 odom 链路。

## 8. 变更管理规则

每个任务必须遵循：

1. 先审计当前代码
2. 总结发现
3. 提出最小修改计划
4. 小步修改
5. 运行相关 build / test
6. 报告修改文件、修改原因、验证命令、验证结果和剩余风险

禁止无目的大规模重构。

不要自动 push。

不要自动 tag。

不要擅自删除文件。

## 9. 文档规则

阶段报告放在：

- `docs/reports/`

建议报告包括：

- `S0-baseline-audit.md`
- `S1-integration-contract.md`
- `S2-config-externalization.md`
- `S3-M3-scenario-test-report.md`
- `S4-acceptance-metrics.md`
- `S5-ci-cd.md`
- `S6-M5-stability-report.md`

部署文档放在：

- `docs/deployment/`

关键架构变更必须更新相关文档。

## 10. 完成定义

一个修改只有在以下条件满足后才算完成：

- build 通过
- 相关测试通过
- 必要报告已更新
- PRD / SAD 对齐未被破坏
- 剩余风险已记录

生产就绪要求：

- 必测场景 0 碰撞
- 0 死锁
- 0 不可恢复 emergency
- 平均让行延迟 ≤ 15s
- 3 机无线带宽 ≤ 10 KB/s
- 位姿延迟 P95 ≤ 50ms
- emergency stop 响应 ≤ 200ms
- yield command 送达率 ≥ 99.9%
- wireless non-fleet traffic count = 0
- 7 天 × 8h 稳定性验证通过

## 11. 不确定时的处理方式

如果不确定某个修改是否违反架构：

1. 停止修改
2. 阅读 PRD / SAD
3. 总结不确定点
4. 给出可选方案
5. 等待确认后再实现
