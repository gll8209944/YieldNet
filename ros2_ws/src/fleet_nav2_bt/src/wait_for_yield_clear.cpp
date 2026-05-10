#include "fleet_nav2_bt/wait_for_yield_clear.hpp"
#include "fleet_nav2_bt/bt_ros_host_utils.hpp"

#include <string>
#include <memory>
#include <chrono>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "fleet_msgs/msg/yield_command.hpp"
#include "behaviortree_cpp_v3/action_node.h"

namespace fleet_nav2_bt
{

// YieldCommand command types (must match fleet_coordinator.py)
const uint8_t CMD_REQUEST_YIELD = 0;
const uint8_t CMD_ACK_YIELD = 1;
const uint8_t CMD_RESUME = 2;
const uint8_t CMD_EMERGENCY_STOP = 3;

WaitForYieldClear::WaitForYieldClear(
  const std::string & action_name,
  const BT::NodeConfiguration & conf)
: BT::ActionNodeBase(action_name, conf),
  node_(host_node_from_tree_config(conf, "wait_for_yield_clear")),
  resume_received_(false),
  yield_ack_received_(false),
  timeout_(15.0),
  first_tick_(true)
{
  // Publisher for cmd_vel to stop the robot
  // Note: This is a safety fallback. Production path should use Nav2 controller.
  cmd_vel_pub_ = node_->create_publisher<geometry_msgs::msg::Twist>(
    "cmd_vel",
    rclcpp::QoS(rclcpp::KeepLast(1)).reliable());

  // Publisher for yield commands using fleet_msgs/YieldCommand
  // Topic: /fleet/yield (correct production path per SAD §4)
  yield_pub_ = node_->create_publisher<fleet_msgs::msg::YieldCommand>(
    "/fleet/yield",
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable());

  // Subscription for yield commands - listen to /fleet/yield
  // This allows receiving RESUME and ACK_YIELD from peers
  yield_sub_ = node_->create_subscription<fleet_msgs::msg::YieldCommand>(
    "/fleet/yield",
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable(),
    [this](const fleet_msgs::msg::YieldCommand::SharedPtr msg) {
      // Only process if this command is for this robot
      if (msg->to_robot != robot_id_) {
        return;
      }

      // Check for RESUME or ACK_YIELD
      if (msg->command == CMD_RESUME || msg->command == CMD_ACK_YIELD) {
        resume_received_ = true;
        RCLCPP_INFO(node_->get_logger(), "RESUME/ACK_YIELD received from %s, clearing yield wait",
          msg->from_robot.c_str());
      }
    });

  RCLCPP_INFO(node_->get_logger(), "WaitForYieldClear constructed");
}

WaitForYieldClear::~WaitForYieldClear()
{
  RCLCPP_INFO(node_->get_logger(), "Destructing WaitForYieldClear");
}

BT::NodeStatus WaitForYieldClear::tick()
{
  rclcpp::spin_some(node_);

  if (first_tick_) {
    first_tick_ = false;

    // Get parameters from ports
    getInput<std::string>("robot_id", robot_id_);
    getInput<std::string>("peer_id", peer_id_);
    getInput<double>("timeout", timeout_);

    // Reset state
    resume_received_ = false;
    yield_ack_received_ = false;
    yield_start_time_ = node_->now();

    // Send ACK_YIELD command to notify peer we're yielding
    sendYieldCommand(CMD_ACK_YIELD);

    // Publish zero velocity to stop robot
    geometry_msgs::msg::Twist cmd;
    cmd.linear.x = 0.0;
    cmd.angular.z = 0.0;
    cmd_vel_pub_->publish(cmd);

    RCLCPP_INFO(node_->get_logger(), "Yield started: %s yielding to %s, timeout=%.1fs",
      robot_id_.c_str(), peer_id_.c_str(), timeout_);

    return BT::NodeStatus::RUNNING;
  }

  // Check for RESUME (from peer who we yielded to)
  if (resume_received_) {
    first_tick_ = true;
    sendYieldCommand(CMD_RESUME);
    RCLCPP_INFO(node_->get_logger(), "Yield cleared, resuming");
    return BT::NodeStatus::SUCCESS;
  }

  // Check timeout
  auto elapsed = (node_->now() - yield_start_time_).seconds();
  if (elapsed >= timeout_) {
    first_tick_ = true;
    RCLCPP_WARN(node_->get_logger(), "Yield timeout after %.1fs", elapsed);
    // Force resume
    sendYieldCommand(CMD_RESUME);
    return BT::NodeStatus::FAILURE;
  }

  // Keep publishing zero velocity as safety fallback
  geometry_msgs::msg::Twist cmd;
  cmd.linear.x = 0.0;
  cmd.angular.z = 0.0;
  cmd_vel_pub_->publish(cmd);

  return BT::NodeStatus::RUNNING;
}

void WaitForYieldClear::halt()
{
  first_tick_ = true;
  // Send RESUME when halted
  sendYieldCommand(CMD_RESUME);
  RCLCPP_INFO(node_->get_logger(), "Yield halted, sent RESUME");
}

void WaitForYieldClear::sendYieldCommand(uint8_t command)
{
  fleet_msgs::msg::YieldCommand msg;
  msg.from_robot = robot_id_;
  msg.to_robot = peer_id_;
  msg.command = command;
  // Note: conflict_x/y and stamp are optional for ACK_YIELD/RESUME

  yield_pub_->publish(msg);
  RCLCPP_INFO(node_->get_logger(), "Sending yield command: cmd=%d from=%s to=%s",
    command, robot_id_.c_str(), peer_id_.c_str());
}

}  // namespace fleet_nav2_bt

#ifdef FLEET_NAV2_BT_PLUGIN
#include "behaviortree_cpp_v3/bt_factory.h"

BT_REGISTER_NODES(factory)
{
  factory.registerNodeType<fleet_nav2_bt::WaitForYieldClear>("WaitForYieldClear");
}
#endif

