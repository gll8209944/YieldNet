#ifndef CHECK_FLEET_CONFLICT_HPP_
#define CHECK_FLEET_CONFLICT_HPP_

#include <string>
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "behaviortree_cpp_v3/condition_node.h"

namespace fleet_nav2_bt
{

/**
 * @brief CheckFleetConflict BT Condition Node
 *
 * Checks if the robot has a fleet coordination conflict with any peer.
 * Reads the current robot state from /fleet/coordinator_status topic.
 *
 * Returns SUCCESS if conflict detected (YIELDING, PASSING, or EMERGENCY state),
 * FAILURE otherwise.
 */
class CheckFleetConflict : public BT::ConditionNode
{
public:
  /**
   * @brief Constructor
   * @param condition_name Name of the condition node
   * @param conf BT node configuration
   */
  CheckFleetConflict(
    const std::string & condition_name,
    const BT::NodeConfiguration & conf);

  /**
   * @brief Destructor
   */
  ~CheckFleetConflict();

  /**
   * @brief Define ports for the condition node
   */
  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("robot_id", "Robot ID"),
      BT::OutputPort<std::string>("conflict_peer", "Peer robot ID causing conflict, or 'unknown'")
    };
  }

  /**
   * @brief Tick callback - performs conflict check
   * @return BT::NodeStatus SUCCESS if conflict detected, FAILURE otherwise
   */
  BT::NodeStatus tick() override;

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr state_sub_;
  std::string current_fleet_state_;
  std::string current_speed_ratio_;
  std::string conflict_peer_;
  bool state_received_;
};

}  // namespace fleet_nav2_bt

#endif  // CHECK_FLEET_CONFLICT_HPP_
