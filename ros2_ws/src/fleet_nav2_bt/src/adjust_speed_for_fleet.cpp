#include "fleet_nav2_bt/adjust_speed_for_fleet.hpp"
#include "fleet_nav2_bt/bt_ros_host_utils.hpp"

#include <string>
#include <memory>
#include <algorithm>
#include <cstdlib>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
#include "nav2_msgs/msg/speed_limit.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

// Helper function to extract a string value from JSON-like string
// Same as in check_fleet_conflict.cpp - shared utility
static bool extractJsonStringField(const std::string& json_str,
                                   const std::string& field_name,
                                   std::string& out_value)
{
  std::string colon_space = "\":\"";
  std::string colon_quote = "\": \"";

  size_t field_pos = json_str.find("\"" + field_name + "\"");
  if (field_pos == std::string::npos) {
    return false;
  }

  size_t colon_pos = json_str.find(':', field_pos);
  if (colon_pos == std::string::npos) {
    return false;
  }

  size_t value_start = colon_pos + 1;
  while (value_start < json_str.size() &&
         (json_str[value_start] == ' ' || json_str[value_start] == '"')) {
    value_start++;
  }

  size_t value_end = value_start;
  bool is_quoted = (json_str[value_start - 1] == '"');

  if (is_quoted) {
    value_end = json_str.find('"', value_start);
    if (value_end == std::string::npos) {
      return false;
    }
  } else {
    while (value_end < json_str.size() &&
           json_str[value_end] != ',' &&
           json_str[value_end] != '}' &&
           json_str[value_end] != ' ' &&
           json_str[value_end] != '\n' &&
           json_str[value_end] != '\r') {
      value_end++;
    }
  }

  out_value = json_str.substr(value_start, value_end - value_start);
  return true;
}

// Extract speed_ratio as double
static bool extractSpeedRatioDouble(const std::string& json_str, double& out_value)
{
  size_t field_pos = json_str.find("\"speed_ratio\"");
  if (field_pos == std::string::npos) {
    return false;
  }

  size_t colon_pos = json_str.find(':', field_pos);
  if (colon_pos == std::string::npos) {
    return false;
  }

  size_t value_start = colon_pos + 1;
  while (value_start < json_str.size() &&
         (json_str[value_start] == ' ' || json_str[value_start] == '\n' || json_str[value_start] == '\r' || json_str[value_start] == '\t')) {
    value_start++;
  }

  size_t value_end = value_start;
  while (value_end < json_str.size() &&
         (std::isdigit(json_str[value_end]) ||
          json_str[value_end] == '.' ||
          json_str[value_end] == '-' ||
          json_str[value_end] == '+' ||
          json_str[value_end] == 'e' ||
          json_str[value_end] == 'E')) {
    value_end++;
  }

  if (value_end == value_start) {
    return false;
  }

  std::string num_str = json_str.substr(value_start, value_end - value_start);
  try {
    out_value = std::stod(num_str);
    return true;
  } catch (...) {
    return false;
  }
}

AdjustSpeedForFleet::AdjustSpeedForFleet(
  const std::string & name,
  const BT::NodeConfiguration & conf)
: BT::DecoratorNode(name, conf),
  node_(host_node_from_tree_config(conf, "adjust_speed_for_fleet")),
  default_speed_(0.5),
  current_speed_ratio_(1.0),
  last_published_speed_ratio_(1.0)
{
  // Publisher for Nav2 SpeedLimit topic
  // This is the production path for fleet speed control per S1-B
  speed_limit_pub_ = node_->create_publisher<nav2_msgs::msg::SpeedLimit>(
    "speed_limit",
    rclcpp::QoS(rclcpp::KeepLast(1)).reliable());

  // Subscription for fleet state
  // Note: /fleet/coordinator_status is diagnostic-only per SAD §13.2
  // This node uses it for BT state awareness only
  state_sub_ = node_->create_subscription<std_msgs::msg::String>(
    "fleet/coordinator_status",
    rclcpp::QoS(rclcpp::KeepLast(1)).transient_local(),
    [this](const std_msgs::msg::String::SharedPtr msg) {
      current_fleet_state_ = msg->data;

      // Try to extract speed_ratio directly from JSON
      double speed_ratio = 1.0;
      if (extractSpeedRatioDouble(msg->data, speed_ratio)) {
        current_speed_ratio_ = speed_ratio;
      } else {
        // Fallback to parsing state name
        std::string state_str;
        if (extractJsonStringField(msg->data, "state", state_str)) {
          current_speed_ratio_ = getSpeedScaling(state_str);
        }
      }
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
  // Get speed scaling from fleet state (already computed in subscription callback)
  double speed_ratio = current_speed_ratio_;

  // Publish speed limit to Nav2 controller
  // Only publish when speed_ratio changes to reduce traffic
  if (std::abs(speed_ratio - last_published_speed_ratio_) > 0.01) {
    nav2_msgs::msg::SpeedLimit msg;
    msg.percentage = true;  // Use percentage (0-100)
    msg.speed_limit = speed_ratio * 100.0;  // Convert ratio to percentage
    speed_limit_pub_->publish(msg);
    last_published_speed_ratio_ = speed_ratio;
    RCLCPP_INFO(node_->get_logger(), "AdjustSpeedForFleet: published speed_limit=%.1f%% (ratio=%.2f)",
      msg.speed_limit, speed_ratio);
  }

  // Tick the child node
  BT::NodeStatus child_status = child_node_->executeTick();

  RCLCPP_INFO(node_->get_logger(), "AdjustSpeedForFleet: state=%s, speed_ratio=%.2f, child_status=%d",
    current_fleet_state_.c_str(), speed_ratio, static_cast<int>(child_status));

  return child_status;
}

}  // namespace fleet_nav2_bt
