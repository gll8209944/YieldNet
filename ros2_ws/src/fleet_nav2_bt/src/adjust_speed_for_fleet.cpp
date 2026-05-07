#include "fleet_nav2_bt/adjust_speed_for_fleet.hpp"

#include <string>
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

AdjustSpeedForFleet::AdjustSpeedForFleet(
  const std::string & name,
  const BT::NodeConfiguration & conf)
: BT::DecoratorNode(name, conf),
  node_(rclcpp::Node::make_shared("adjust_speed_for_fleet")),
  default_speed_(0.5)
{
  // Subscription for fleet state
  state_sub_ = node_->create_subscription<std_msgs::msg::String>(
    "fleet/coordinator_status",
    rclcpp::QoS(rclcpp::KeepLast(1)).transient_local(),
    [this](const std_msgs::msg::String::SharedPtr msg) {
      current_fleet_state_ = msg->data;
    });

  getInput<double>("default_speed", default_speed_);

  RCLCPP_INFO(node_->get_logger(), "AdjustSpeedForFleet constructed: default=%.2f",
    default_speed_);
}

AdjustSpeedForFleet::~AdjustSpeedForFleet()
{
  RCLCPP_INFO(node_->get_logger(), "Destructing AdjustSpeedForFleet");
}

double AdjustSpeedForFleet::getSpeedScaling(const std::string & state)
{
  // Map fleet state to speed scaling factor
  // Based on SAD §5.1 State definitions
  if (state == "NORMAL") {
    return 1.0;
  } else if (state == "AWARENESS") {
    return 1.0;
  } else if (state == "CAUTION") {
    return 0.5;
  } else if (state == "YIELDING") {
    return 0.0;  // Stop for yielding
  } else if (state == "PASSING") {
    return 0.3;  // Slow down for passing
  } else if (state == "EMERGENCY") {
    return 0.0;  // Emergency stop
  }
  return default_speed_;  // Default if unknown state
}

BT::NodeStatus AdjustSpeedForFleet::tick()
{
  // Get speed scaling from fleet state
  double speed_ratio = getSpeedScaling(current_fleet_state_);

  // Tick the child node
  BT::NodeStatus child_status = child_node_->executeTick();

  // Apply speed scaling - only affect if we need to stop
  if (speed_ratio < 0.01 && child_status == BT::NodeStatus::RUNNING) {
    // Stop the robot
    geometry_msgs::msg::Twist cmd;
    cmd.linear.x = 0.0;
    cmd.angular.z = 0.0;
    // Note: In a real implementation, we'd intercept the child's cmd_vel output
    // For now, we just return the child's status
  }

  RCLCPP_INFO(node_->get_logger(), "AdjustSpeedForFleet: state=%s, speed_ratio=%.2f",
    current_fleet_state_.c_str(), speed_ratio);

  return child_status;
}

}  // namespace fleet_nav2_bt
