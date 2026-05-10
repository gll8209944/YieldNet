#ifndef FLEET_NAV2_BT_BT_ROS_HOST_UTILS_HPP_
#define FLEET_NAV2_BT_BT_ROS_HOST_UTILS_HPP_

#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

/**
 * Build a lightweight ROS node in the same namespace as Nav2's BT node.
 *
 * Nav2's blackboard node is not a reliable place for custom BT subscriptions in
 * this package: subscription callbacks can remain unprocessed while BT ticks are
 * executing. A per-plugin node lets the plugin call rclcpp::spin_some() in tick()
 * without interfering with Nav2's lifecycle executor.
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
      return rclcpp::Node::make_shared(fallback_name, n->get_namespace());
    }
  } catch (const std::exception &) {
  }
  return rclcpp::Node::make_shared(fallback_name);
}

}  // namespace fleet_nav2_bt

#endif  // FLEET_NAV2_BT_BT_ROS_HOST_UTILS_HPP_
