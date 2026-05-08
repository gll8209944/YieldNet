#include "fleet_nav2_bt/check_fleet_conflict.hpp"
#include "fleet_nav2_bt/bt_ros_host_utils.hpp"

#include <string>
#include <memory>
#include <algorithm>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

// Helper function to extract a string value from JSON-like string
// This is a minimal parser that handles the specific format from coordinator_status
// Format: {"robot_id": "robot_a", "state": "YIELDING", "speed_ratio": 0.0, "peers": [...]}
// Note: This is NOT a full JSON parser, just a simple field extractor for known patterns
static bool extractJsonStringField(const std::string& json_str,
                                   const std::string& field_name,
                                   std::string& out_value)
{
  // Build search patterns for both quoted and unquoted value styles
  std::string colon_space = "\":\"";
  std::string colon_quote = "\": \"";

  // Find the field name position
  size_t field_pos = json_str.find("\"" + field_name + "\"");
  if (field_pos == std::string::npos) {
    return false;
  }

  // Find the colon after the field name
  size_t colon_pos = json_str.find(':', field_pos);
  if (colon_pos == std::string::npos) {
    return false;
  }

  // Skip whitespace and quotes
  size_t value_start = colon_pos + 1;
  while (value_start < json_str.size() &&
         (json_str[value_start] == ' ' || json_str[value_start] == '"')) {
    value_start++;
  }

  // Find the closing quote (if quoted string)
  size_t value_end = value_start;
  bool is_quoted = (json_str[value_start - 1] == '"');

  if (is_quoted) {
    value_end = json_str.find('"', value_start);
    if (value_end == std::string::npos) {
      return false;
    }
  } else {
    // Unquoted value (number, boolean, etc.)
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

// Extract speed_ratio as a string (for passing to getSpeedScaling)
static bool extractSpeedRatio(const std::string& json_str, std::string& out_value)
{
  // Look for "speed_ratio": or "speed_ratio":
  size_t field_pos = json_str.find("\"speed_ratio\"");
  if (field_pos == std::string::npos) {
    return false;
  }

  size_t colon_pos = json_str.find(':', field_pos);
  if (colon_pos == std::string::npos) {
    return false;
  }

  // Skip whitespace
  size_t value_start = colon_pos + 1;
  while (value_start < json_str.size() &&
         (json_str[value_start] == ' ' || json_str[value_start] == '\n' || json_str[value_start] == '\r' || json_str[value_start] == '\t')) {
    value_start++;
  }

  // Find end of number
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

  out_value = json_str.substr(value_start, value_end - value_start);
  return true;
}

CheckFleetConflict::CheckFleetConflict(
  const std::string & condition_name,
  const BT::NodeConfiguration & conf)
: BT::ConditionNode(condition_name, conf),
  node_(host_node_from_tree_config(conf, "check_fleet_conflict")),
  state_received_(false),
  conflict_peer_("unknown")
{
  // Subscribe to fleet coordinator status
  // Note: /fleet/coordinator_status is diagnostic-only per SAD §13.2
  // This node uses it for BT state awareness only, not as production control contract
  state_sub_ = node_->create_subscription<std_msgs::msg::String>(
    "fleet/coordinator_status",
    rclcpp::QoS(rclcpp::KeepLast(1)).transient_local(),
    [this](const std_msgs::msg::String::SharedPtr msg) {
      current_fleet_state_ = msg->data;
      // Also extract speed_ratio for use in tick
      extractSpeedRatio(msg->data, current_speed_ratio_);
      state_received_ = true;
    });
}

CheckFleetConflict::~CheckFleetConflict()
{
  RCLCPP_INFO(node_->get_logger(), "Destructing CheckFleetConflict");
}

BT::NodeStatus CheckFleetConflict::tick()
{
  // Check if fleet state has been received
  if (!state_received_) {
    // No fleet state yet - return failure (no conflict)
    RCLCPP_INFO(node_->get_logger(), "CheckFleetConflict: no state received, returning FAILURE");
    return BT::NodeStatus::FAILURE;
  }

  // Extract state from JSON
  std::string fleet_state;
  if (!extractJsonStringField(current_fleet_state_, "state", fleet_state)) {
    RCLCPP_WARN(node_->get_logger(), "CheckFleetConflict: failed to parse state from JSON, returning FAILURE");
    return BT::NodeStatus::FAILURE;
  }

  // Determine if there's a conflict based on parsed state
  // States that indicate conflict: YIELDING, PASSING, EMERGENCY
  bool has_conflict = (fleet_state == "YIELDING" ||
                       fleet_state == "PASSING" ||
                       fleet_state == "EMERGENCY");

  // Write fleet state and conflict_peer to blackboard for other nodes
  setOutput<std::string>("fleet_state", fleet_state);
  setOutput<std::string>("conflict_peer", conflict_peer_);

  RCLCPP_INFO(node_->get_logger(), "CheckFleetConflict: fleet_state=%s, has_conflict=%d, conflict_peer=%s",
    fleet_state.c_str(), has_conflict, conflict_peer_.c_str());

  return has_conflict ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
}

}  // namespace fleet_nav2_bt
