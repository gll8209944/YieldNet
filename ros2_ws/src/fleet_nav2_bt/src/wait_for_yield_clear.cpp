#include "fleet_nav2_bt/wait_for_yield_clear.hpp"

#include <string>
#include <memory>
#include <chrono>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"

namespace fleet_nav2_bt
{

WaitForYieldClear::WaitForYieldClear(
  const std::string & action_name,
  const BT::NodeConfiguration & conf)
: BT::ActionNodeBase(action_name, conf),
  node_(rclcpp::Node::make_shared("wait_for_yield_clear")),
  resume_received_(false),
  timeout_(15.0),
  first_tick_(true)
{
  // Publisher for cmd_vel to stop the robot
  cmd_vel_pub_ = node_->create_publisher<geometry_msgs::msg::Twist>(
    "cmd_vel",
    rclcpp::QoS(rclcpp::KeepLast(1)).reliable());

  // Publisher for yield commands
  yield_pub_ = node_->create_publisher<std_msgs::msg::String>(
    "fleet/yield_command",
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable());

  // Subscription for RESUME command
  resume_sub_ = node_->create_subscription<std_msgs::msg::String>(
    "fleet/yield_command",
    rclcpp::QoS(rclcpp::KeepLast(10)).reliable(),
    [this](const std_msgs::msg::String::SharedPtr msg) {
      if (msg->data.find("RESUME") != std::string::npos) {
        resume_received_ = true;
        RCLCPP_INFO(node_->get_logger(), "RESUME received, stopping yield wait");
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
  if (first_tick_) {
    first_tick_ = false;

    // Get parameters from ports
    getInput<std::string>("robot_id", robot_id_);
    getInput<std::string>("peer_id", peer_id_);
    getInput<double>("timeout", timeout_);

    // Reset state
    resume_received_ = false;
    yield_start_time_ = node_->now();

    // Send ACK_YIELD command
    sendYieldCommand("ACK_YIELD");

    // Publish zero velocity to stop robot
    geometry_msgs::msg::Twist cmd;
    cmd.linear.x = 0.0;
    cmd.angular.z = 0.0;
    cmd_vel_pub_->publish(cmd);

    RCLCPP_INFO(node_->get_logger(), "Yield started: %s yielding to %s, timeout=%.1fs",
      robot_id_.c_str(), peer_id_.c_str(), timeout_);

    return BT::NodeStatus::RUNNING;
  }

  // Check for RESUME
  if (resume_received_) {
    first_tick_ = true;
    sendYieldCommand("RESUME");
    RCLCPP_INFO(node_->get_logger(), "Yield cleared, resuming");
    return BT::NodeStatus::SUCCESS;
  }

  // Check timeout
  auto elapsed = (node_->now() - yield_start_time_).seconds();
  if (elapsed >= timeout_) {
    first_tick_ = true;
    RCLCPP_WARN(node_->get_logger(), "Yield timeout after %.1fs", elapsed);
    return BT::NodeStatus::FAILURE;
  }

  // Keep publishing zero velocity
  geometry_msgs::msg::Twist cmd;
  cmd.linear.x = 0.0;
  cmd.angular.z = 0.0;
  cmd_vel_pub_->publish(cmd);

  return BT::NodeStatus::RUNNING;
}

void WaitForYieldClear::halt()
{
  first_tick_ = true;
  sendYieldCommand("RESUME");
  RCLCPP_INFO(node_->get_logger(), "Yield halted");
}

void WaitForYieldClear::sendYieldCommand(const std::string & command)
{
  std_msgs::msg::String msg;
  msg.data = command + ":" + robot_id_ + ":" + peer_id_;
  yield_pub_->publish(msg);
  RCLCPP_INFO(node_->get_logger(), "Sending yield command: %s from %s to %s",
    command.c_str(), robot_id_.c_str(), peer_id_.c_str());
}

}  // namespace fleet_nav2_bt
