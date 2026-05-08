#ifndef ADJUST_SPEED_FOR_FLEET_HPP_
#define ADJUST_SPEED_FOR_FLEET_HPP_

#include <string>
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
#include "nav2_msgs/msg/speed_limit.hpp"
#include "behaviortree_cpp_v3/decorator_node.h"

namespace fleet_nav2_bt
{

/**
 * @brief AdjustSpeedForFleet BT Decorator Node
 *
 * Decorator that modulates the speed of its child node based on
 * fleet coordination state.
 *
 * Reads fleet state from /fleet/coordinator_status and applies speed scaling:
 * - NORMAL: 100% speed
 * - AWARENESS: 100% speed
 * - CAUTION: 50% speed
 * - YIELDING: 0% speed
 * - PASSING: 30% speed
 * - EMERGENCY: 0% speed
 *
 * This replaces cmd_vel interception with native BT speed control.
 */
class AdjustSpeedForFleet : public BT::DecoratorNode
{
public:
  /**
   * @brief Constructor
   * @param name Name of the decorator node
   * @param conf BT node configuration
   */
  AdjustSpeedForFleet(
    const std::string & name,
    const BT::NodeConfiguration & conf);

  /**
   * @brief Destructor
   */
  ~AdjustSpeedForFleet();

  /**
   * @brief Define ports for the decorator node
   */
  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("speed_topic", "/cmd_vel", "Topic to publish speed commands"),
      BT::InputPort<double>("default_speed", 0.5, "Default speed if no fleet state")
    };
  }

  /**
   * @brief Tick callback - applies speed scaling to child
   * @return BT::NodeStatus Result of child tick
   */
  BT::NodeStatus tick() override;

private:
  /**
   * @brief Get speed scaling factor from fleet state
   * @param state Fleet coordination state string
   * @return Speed scaling factor (0.0 to 1.0)
   */
  double getSpeedScaling(const std::string & state);

  rclcpp::Node::SharedPtr node_;
  rclcpp::Publisher<nav2_msgs::msg::SpeedLimit>::SharedPtr speed_limit_pub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr state_sub_;
  std::string current_fleet_state_;
  double default_speed_;
  double current_speed_ratio_;
  double last_published_speed_ratio_;
};

}  // namespace fleet_nav2_bt

#endif  // ADJUST_SPEED_FOR_FLEET_HPP_
