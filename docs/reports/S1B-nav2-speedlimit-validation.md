# S1B-nav2-speedlimit-validation

**日期**: 2026-05-07
**阶段**: S1-B Nav2 SpeedLimit 集成验证
**分支**: s1b-nav2-speedlimit-validation
**基于 commit**: 6c7793d (S1-A)

---

## Summary

本报告记录 S1-B 阶段的验证和实现工作：Nav2 SpeedLimit 能力审计和集成实现。

**结论**: Nav2 Humble 支持 `nav2_msgs/msg/SpeedLimit` 话题，`controller_server` 订阅该话题并调用 `setSpeedLimit()`。已实现 AdjustSpeedForFleet 使用 Nav2 SpeedLimit 替代 cmd_vel 拦截。

**修复内容**:
1. 添加 nav2_msgs 依赖到 adjust_speed_for_fleet
2. 实现 Nav2 SpeedLimit topic 发布（生产路径）
3. 移除 cmd_vel 拦截（安全兜底已不再需要）

---

## Nav2 SpeedLimit 能力审计

### ECS Nav2 Humble 环境确认

```bash
# Nav2 包列表
nav2_amcl, nav2_behaviors, nav2_behavior_tree, nav2_bringup,
nav2_bt_navigator, nav2_collision_monitor, nav2_common,
nav2_constrained_smoother, nav2_controller, nav2_core,
nav2_costmap_2d, nav2_dwb_controller, nav2_lifecycle_manager,
nav2_map_server, nav2_mppi_controller, nav2_msgs,
nav2_navfn_planner, nav2_planner, nav2_regulated_pure_pursuit_controller,
nav2_rotation_shim_controller
```

### SpeedLimit 消息结构

```rosidl
# /opt/ros/humble/share/nav2_msgs/msg/SpeedLimit.msg
std_msgs/Header header
bool percentage        # true=百分比, false=绝对值 m/s
float64 speed_limit    # 0.0 = 无限制
```

### Nav2 Controller 支持确认

```cpp
// nav2_controller/controller_server.hpp
rclcpp::Subscription<nav2_msgs::msg::SpeedLimit>::SharedPtr speed_limit_sub_;
void speedLimitCallback(const nav2_msgs::msg::SpeedLimit::SharedPtr msg);

// nav2_core/controller.hpp (抽象接口)
virtual void setSpeedLimit(const double & speed_limit, const bool & percentage) = 0;

// nav2_regulated_pure_pursuit_controller/regulated_pure_pursuit_controller.hpp
void setSpeedLimit(const double & speed_limit, const bool & percentage) override;
```

**结论**: Nav2 controller_server 订阅 `speed_limit` 话题，调用 active controller 的 `setSpeedLimit()` 方法。

---

## 实现变更

### Topic Contract

| Topic | Type | Direction | Status |
|-------|------|-----------|--------|
| `/speed_limit` | nav2_msgs/SpeedLimit | pub | ✅ 新增生产路径 |
| `/fleet/coordinator_status` | std_msgs/String (JSON) | sub (diagnostic) | ✅ 不变 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `adjust_speed_for_fleet.hpp` | +nav2_msgs include, +speed_limit_pub_, +last_published_speed_ratio_ |
| `adjust_speed_for_fleet.cpp` | +nav2_msgs include, 创建 speed_limit publisher, 替换 cmd_vel 拦截为 SpeedLimit 发布 |
| `CMakeLists.txt` | +nav2_msgs 依赖 |

### 关键代码变更

**之前 (cmd_vel 拦截 - 非生产路径)**:
```cpp
if (speed_ratio < 0.01 && child_status == BT::NodeStatus::RUNNING) {
  geometry_msgs::msg::Twist cmd;
  cmd.linear.x = 0.0;
  cmd.angular.z = 0.0;
  // 直接发布 cmd_vel - 非生产路径！
}
```

**之后 (Nav2 SpeedLimit - 生产路径)**:
```cpp
if (std::abs(speed_ratio - last_published_speed_ratio_) > 0.01) {
  nav2_msgs::msg::SpeedLimit msg;
  msg.percentage = true;  // 使用百分比 (0-100)
  msg.speed_limit = speed_ratio * 100.0;  // 比例转百分比
  speed_limit_pub_->publish(msg);
  last_published_speed_ratio_ = speed_ratio;
}
```

---

## 速度映射 (不变)

| Fleet State | Speed Ratio | SpeedLimit (%) |
|-------------|-------------|----------------|
| NORMAL | 1.0 | 100% |
| AWARENESS | 1.0 | 100% |
| CAUTION | 0.5 | 50% |
| YIELDING | 0.0 | 0% |
| PASSING | 0.3 | 30% |
| EMERGENCY | 0.0 | 0% |

---

## ECS Build 结果

| 项目 | 值 |
|------|-----|
| Build | ✅ 4 packages, 1min 47s |
| Warnings | ⚠️ 2 reorder warnings (check_fleet_conflict.hpp 初始化顺序) |
| Errors | ✅ 0 errors |

**Reorder warnings 说明**: `check_fleet_conflict.hpp` 中成员初始化顺序与构造函数初始化列表顺序不一致。不影响功能，建议后续修复。

## ECS Test 结果

| 项目 | 值 |
|------|-----|
| Tests | ✅ 32 tests |
| Errors | ✅ 0 |
| Failures | ✅ 0 |
| Skipped | ✅ 0 |

## Git Push 结果

✅ **Push 成功**: `origin/s1b-nav2-speedlimit-validation`

- Branch URL: https://github.com/gll8209944/YieldNet/tree/s1b-nav2-speedlimit-validation
- Commit URL: https://github.com/gll8209944/YieldNet/commit/a7e5cc8

---

## S1-B Completed

- [x] Nav2 SpeedLimit 能力审计 (ECS 确认)
- [x] 添加 nav2_msgs 依赖
- [x] 实现 SpeedLimit topic 发布
- [x] 移除 cmd_vel 拦截
- [x] Build 验证 (4 packages, 0 errors)
- [x] Test 验证 (32 tests, 0 failures)

---

## S1-B Remaining

- [x] Build 验证 ✅
- [x] Test 验证 ✅
- [ ] Gazebo / BT runtime 验证 (S3 场景测试)
- [ ] fleet_msgs 中添加 command 常量定义 (统一常量)

---

## Appendix: PR 创建

PR 创建链接:
https://github.com/gll8209944/YieldNet/pull/new/s1b-nav2-speedlimit-validation

base: `s1-bt-protocol-alignment`
head: `s1b-nav2-speedlimit-validation`
