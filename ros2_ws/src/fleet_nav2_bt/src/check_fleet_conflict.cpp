#include "fleet_nav2_bt/check_fleet_conflict.hpp"

#include <string>
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

CheckFleetConflict::CheckFleetConflict(
  const std::string & condition_name,
  const BT::NodeConfiguration & conf)
: BT::ConditionNode(condition_name, conf),
  node_(rclcpp::Node::make_shared("check_fleet_conflict")),
  state_received_(false)
{
  // Subscribe to fleet coordinator status
  state_sub_ = node_->create_subscription<std_msgs::msg::String>(
    "fleet/coordinator_status",
    rclcpp::QoS(rclcpp::KeepLast(1)).transient_local(),
    [this](const std_msgs::msg::String::SharedPtr msg) {
      current_fleet_state_ = msg->data;
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
    return BT::NodeStatus::FAILURE;
  }

  // Get current fleet state
  std::string fleet_state = current_fleet_state_;

  // Determine if there's a conflict
  // States that indicate conflict: YIELDING, PASSING, EMERGENCY
  bool has_conflict = (fleet_state == "YIELDING" ||
                       fleet_state == "PASSING" ||
                       fleet_state == "EMERGENCY");

  // Write fleet state to blackboard for other nodes
  setOutput<std::string>("fleet_state", fleet_state);

  RCLCPP_INFO(node_->get_logger(), "CheckFleetConflict: fleet_state=%s, has_conflict=%d",
    fleet_state.c_str(), has_conflict);

  return has_conflict ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
}

}  // namespace fleet_nav2_bt
