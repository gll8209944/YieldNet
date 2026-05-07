/**
 * @file fleet_bt_runner.cpp
 * @brief Standalone Fleet Coordination BT Runner
 *
 * This node executes the fleet coordination behavior tree standalone,
 * without requiring Nav2's bt_navigator.
 *
 * It provides the BT nodes as ROS 2 components and executes the tree.
 */

#include <memory>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "behaviortree_cpp_v3/behavior_tree.h"
#include "behaviortree_cpp_v3/bt_factory.h"
#include "behaviortree_cpp_v3/loggers/bt_cout_logger.h"
#include "behaviortree_cpp_v3/loggers/bt_file_logger.h"

#include "fleet_nav2_bt/check_fleet_conflict.hpp"
#include "fleet_nav2_bt/wait_for_yield_clear.hpp"
#include "fleet_nav2_bt/adjust_speed_for_fleet.hpp"

using namespace std::chrono_literals;

// Behavior Tree XML
const std::string FLEET_BT_XML = R"(
<root main_tree_to_execute="FleetCoordination">
  <BehaviorTree ID="FleetCoordination">
    <Sequence name="FleetCoordinationSequence">
      <!-- Check for fleet conflict -->
      <CheckFleetConflict robot_id="{robot_id}"/>

      <!-- If conflict, wait for clear -->
      <WaitForYieldClear robot_id="{robot_id}" peer_id="{peer_id}" timeout="15.0"/>

      <!-- Adjust speed based on fleet state -->
      <AdjustSpeedForFleet default_speed="0.5"/>
    </Sequence>
  </BehaviorTree>
</root>
)";

class FleetBTRunner : public rclcpp::Node
{
public:
  FleetBTRunner()
  : Node("fleet_bt_runner")
  {
    this->declare_parameter("robot_id", "robot_a");
    this->declare_parameter("bt_xml", FLEET_BT_XML);

    robot_id_ = this->get_parameter("robot_id").as_string();

    RCLCPP_INFO(this->get_logger(), "FleetBTRunner starting for %s", robot_id_.c_str());

    // Create BT factory and register nodes
    factory_ = std::make_unique<BT::BehaviorTreeFactory>();

    // Register fleet BT nodes
    factory_->registerNodeType<fleet_nav2_bt::CheckFleetConflict>("CheckFleetConflict");
    factory_->registerNodeType<fleet_nav2_bt::WaitForYieldClear>("WaitForYieldClear");
    factory_->registerNodeType<fleet_nav2_bt::AdjustSpeedForFleet>("AdjustSpeedForFleet");

    // Create tree
    tree_ = factory_->createTreeFromText(FLEET_BT_XML);

    // Create logger
    logger_ = std::make_unique<BT::StdCoutLogger>(tree_);

    // Create timer for tree tick
    timer_ = this->create_wall_timer(
      100ms,
      [this]() { this->tickTree(); }
    );

    RCLCPP_INFO(this->get_logger(), "FleetBTRunner initialized");
  }

  ~FleetBTRunner()
  {
    RCLCPP_INFO(this->get_logger(), "FleetBTRunner destroyed");
  }

private:
  void tickTree()
  {
    // Tick the tree - this will execute all nodes
    tree_.rootNode()->executeTick();
  }

  std::string robot_id_;
  std::unique_ptr<BT::BehaviorTreeFactory> factory_;
  BT::Tree tree_;
  std::unique_ptr<BT::StdCoutLogger> logger_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<FleetBTRunner>();

  RCLCPP_INFO(node->get_logger(), "Spinning fleet_bt_runner...");
  rclcpp::spin(node);

  rclcpp::shutdown();
  return 0;
}
