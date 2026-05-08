#ifndef FLEET_NAV2_BT_BT_ROS_HOST_UTILS_HPP_
#define FLEET_NAV2_BT_BT_ROS_HOST_UTILS_HPP_

#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

/**
 * Prefer the Nav2 / BT blackboard "node" (the node that is spun by the executor).
 * Standalone fleet_bt_runner sets this so subscriptions and timers are processed by spin().
 */
inline rclcpp::Node::SharedPtr host_node_from_tree_config(
  const BT::NodeConfiguration & conf,
  const char * fallback_name)
{
  if (!conf.blackboard) {
    return rclcpp::Node::make_shared(fallback_name);
  }
  try {
    auto n = conf.blackboard->template get<rclcpp::Node::SharedPtr>("node");
    if (n) {
      return n;
    }
  } catch (const std::exception &) {
  }
  return rclcpp::Node::make_shared(fallback_name);
}

}  // namespace fleet_nav2_bt

#endif  // FLEET_NAV2_BT_BT_ROS_HOST_UTILS_HPP_
