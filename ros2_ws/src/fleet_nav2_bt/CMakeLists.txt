cmake_minimum_required(VERSION 3.8)
project(fleet_nav2_bt)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(behaviortree_cpp_v3 REQUIRED)
find_package(nav2_msgs REQUIRED)

# Include directories
include_directories(
  include
)

# Build shared libraries
add_library(check_fleet_conflict SHARED
  src/check_fleet_conflict.cpp
)
ament_target_dependencies(check_fleet_conflict
    rclcpp
  geometry_msgs
  std_msgs
  behaviortree_cpp_v3
)

add_library(wait_for_yield_clear SHARED
  src/wait_for_yield_clear.cpp
)
ament_target_dependencies(wait_for_yield_clear
    rclcpp
  rclcpp_action
  geometry_msgs
  std_msgs
  behaviortree_cpp_v3
)

add_library(adjust_speed_for_fleet SHARED
  src/adjust_speed_for_fleet.cpp
)
ament_target_dependencies(adjust_speed_for_fleet
    rclcpp
  geometry_msgs
  std_msgs
  behaviortree_cpp_v3
)

# Build standalone BT runner executable
add_executable(fleet_bt_runner
  src/fleet_bt_runner.cpp
)
ament_target_dependencies(fleet_bt_runner
    rclcpp
  rclcpp_action
  geometry_msgs
  std_msgs
  behaviortree_cpp_v3
)
target_link_libraries(fleet_bt_runner
  check_fleet_conflict
  wait_for_yield_clear
  adjust_speed_for_fleet
)


# Install libraries
install(TARGETS
  check_fleet_conflict
  wait_for_yield_clear
  adjust_speed_for_fleet
  fleet_bt_runner
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

# Install headers
install(DIRECTORY include/
  DESTINATION include
)

# Install behavior trees
install(DIRECTORY behavior_trees/
  DESTINATION share/${PROJECT_NAME}/behavior_trees
)

# Install plugin descriptors for manual registration
install(FILES plugin_descriptions.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_export_include_directories(include)
ament_export_libraries(
  check_fleet_conflict
  wait_for_yield_clear
  adjust_speed_for_fleet
)
ament_export_dependencies(
    rclcpp
  rclcpp_action
  geometry_msgs
  std_msgs
  behaviortree_cpp_v3
)
ament_package()
