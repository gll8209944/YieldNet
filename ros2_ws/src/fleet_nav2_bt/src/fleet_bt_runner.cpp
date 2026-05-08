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

// Behavior Tree XML — AdjustSpeedForFleet is a BT::DecoratorNode and requires exactly one child.
// Place it before CheckFleetConflict so standalone ticks still publish /speed_limit when the
// condition returns FAILURE (no conflict); BehaviorTree.CPP builtins such as AlwaysSuccess are
// registered by BehaviorTreeFactory by default.
const std::string FLEET_BT_XML = R"(
<root main_tree_to_execute="FleetCoordination">
  <BehaviorTree ID="FleetCoordination">
    <Sequence name="FleetCoordinationSequence">
      <AdjustSpeedForFleet default_speed="0.5">
        <AlwaysSuccess/>
      </AdjustSpeedForFleet>
      <!-- Check for fleet conflict -->
      <CheckFleetConflict robot_id="{robot_id}"/>
      <!-- If conflict, wait for clear -->
      <WaitForYieldClear robot_id="{robot_id}" peer_id="{peer_id}" timeout="15.0"/>
    </Sequence>
  </BehaviorTree>
</root>
)";

class FleetBTRunner : public rclcpp::Node, public std::enable_shared_from_this<FleetBTRunner>
{
public:
  FleetBTRunner()
  : Node("fleet_bt_runner")
  {
    this->declare_parameter("robot_id", "robot_a");
    this->declare_parameter("peer_id", "robot_b");
    this->declare_parameter("bt_xml", FLEET_BT_XML);

    robot_id_ = this->get_parameter("robot_id").as_string();
    peer_id_ = this->get_parameter("peer_id").as_string();
    bt_xml_ = this->get_parameter("bt_xml").as_string();
    if (bt_xml_.empty()) {
      bt_xml_ = FLEET_BT_XML;
    }

    RCLCPP_INFO(
      this->get_logger(), "FleetBTRunner starting for %s (peer_id=%s)", robot_id_.c_str(),
      peer_id_.c_str());

    // Create BT factory and register nodes
    factory_ = std::make_unique<BT::BehaviorTreeFactory>();

    // Register fleet BT nodes
    factory_->registerNodeType<fleet_nav2_bt::CheckFleetConflict>("CheckFleetConflict");
    factory_->registerNodeType<fleet_nav2_bt::WaitForYieldClear>("WaitForYieldClear");
    factory_->registerNodeType<fleet_nav2_bt::AdjustSpeedForFleet>("AdjustSpeedForFleet");
  }

  /** Call immediately after std::make_shared<FleetBTRunner>() so blackboard can use shared_from_this(). */
  void finish_construction()
  {
    BT::Blackboard::Ptr blackboard = BT::Blackboard::create();
    blackboard->set("robot_id", robot_id_);
    blackboard->set("peer_id", peer_id_);
    blackboard->set<rclcpp::Node::SharedPtr>("node", shared_from_this());

    tree_ = factory_->createTreeFromText(bt_xml_, blackboard);

    logger_ = std::make_unique<BT::StdCoutLogger>(tree_);

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
  std::string peer_id_;
  std::string bt_xml_;
  std::unique_ptr<BT::BehaviorTreeFactory> factory_;
  BT::Tree tree_;
  std::unique_ptr<BT::StdCoutLogger> logger_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<FleetBTRunner>();
  node->finish_construction();

  RCLCPP_INFO(node->get_logger(), "Spinning fleet_bt_runner...");
  rclcpp::spin(node);

  rclcpp::shutdown();
  return 0;
}
