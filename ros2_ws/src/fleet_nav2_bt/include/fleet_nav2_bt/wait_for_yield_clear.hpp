#ifndef WAIT_FOR_YIELD_CLEAR_HPP_
#define WAIT_FOR_YIELD_CLEAR_HPP_

#include <string>
#include <memory>
#include <chrono>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
#include "fleet_msgs/msg/yield_command.hpp"
#include "behaviortree_cpp_v3/action_node.h"

namespace fleet_nav2_bt
{

/**
 * @brief WaitForYieldClear BT Action Node
 *
 * Action node that manages yield waiting during fleet coordination.
 * Publishes zero velocity and waits for RESUME command until timeout.
 *
 * This prevents Nav2 ProgressChecker timeout during yield wait.
 */
class WaitForYieldClear : public BT::ActionNodeBase
{
public:
  /**
   * @brief Constructor
   * @param action_name Name of the action node
   * @param conf BT node configuration
   */
  WaitForYieldClear(
    const std::string & action_name,
    const BT::NodeConfiguration & conf);

  /**
   * @brief Destructor
   */
  ~WaitForYieldClear();

  /**
   * @brief Define ports for the action node
   */
  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("robot_id", "Robot ID for yield command"),
      BT::InputPort<std::string>("peer_id", "Peer robot ID to yield to"),
      BT::InputPort<double>("timeout", 15.0, "Yield timeout in seconds")
    };
  }

  /**
   * @brief Tick callback
   */
  BT::NodeStatus tick() override;

  /**
   * @brief Halt callback
   */
  void halt() override;

private:
  /**
   * @brief Send yield command to fleet coordinator
   * @param command Command type (CMD_REQUEST_YIELD, CMD_ACK_YIELD, CMD_RESUME, CMD_EMERGENCY_STOP)
   */
  void sendYieldCommand(uint8_t command);

  rclcpp::Node::SharedPtr node_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_pub_;
  rclcpp::Publisher<fleet_msgs::msg::YieldCommand>::SharedPtr yield_pub_;
  rclcpp::Subscription<fleet_msgs::msg::YieldCommand>::SharedPtr yield_sub_;

  std::string robot_id_;
  std::string peer_id_;
  bool resume_received_;
  bool yield_ack_received_;
  rclcpp::Time yield_start_time_;
  double timeout_;
  bool first_tick_;
};

}  // namespace fleet_nav2_bt

#endif  // WAIT_FOR_YIELD_CLEAR_HPP_
