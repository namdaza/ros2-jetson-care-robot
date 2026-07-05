#!/usr/bin/env bash
set -e

pkill -f "ros2 launch my_robot_nav navigation.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch my_robot_nav mapping.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch my_robot_nav slam_only.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch my_robot_nav teleop.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch my_robot_ai human_following.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch my_robot_driver robot_driver.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch my_robot_driver sonar.launch.py" >/dev/null 2>&1 || true
pkill -f "ros2 launch rosbridge_server rosbridge_websocket_launch.xml" >/dev/null 2>&1 || true
pkill -f "rosbridge_websocket" >/dev/null 2>&1 || true
pkill -f "rosapi_node" >/dev/null 2>&1 || true
pkill -f "ui_goal_bridge.py" >/dev/null 2>&1 || true
pkill -f "waypoint_manager.py" >/dev/null 2>&1 || true
pkill -f "waypoint_manager" >/dev/null 2>&1 || true
pkill -f "component_container" >/dev/null 2>&1 || true
pkill -f "nav2_" >/dev/null 2>&1 || true
pkill -f "python3 -m http.server 8000" >/dev/null 2>&1 || true
pkill -f "sllidar_node" >/dev/null 2>&1 || true
pkill -f "scan_filter" >/dev/null 2>&1 || true
pkill -f "scan_angle_filter" >/dev/null 2>&1 || true
pkill -f "robot_state_publisher" >/dev/null 2>&1 || true
pkill -f "joint_state_publisher" >/dev/null 2>&1 || true
pkill -f "slam_toolbox" >/dev/null 2>&1 || true
pkill -f "async_slam_toolbox_node" >/dev/null 2>&1 || true
pkill -f "serial_bridge" >/dev/null 2>&1 || true
pkill -f "sonar_node" >/dev/null 2>&1 || true
pkill -f "v4l2_camera_node" >/dev/null 2>&1 || true
pkill -f "yolo_detection_node" >/dev/null 2>&1 || true
pkill -f "human_follower_node" >/dev/null 2>&1 || true
pkill -f "yolo_web_stream_node" >/dev/null 2>&1 || true
pkill -f "amcl" >/dev/null 2>&1 || true
pkill -f "controller_server" >/dev/null 2>&1 || true
pkill -f "planner_server" >/dev/null 2>&1 || true
pkill -f "bt_navigator" >/dev/null 2>&1 || true
pkill -f "recoveries_server" >/dev/null 2>&1 || true
pkill -f "behavior_server" >/dev/null 2>&1 || true
pkill -f "waypoint_follower" >/dev/null 2>&1 || true
pkill -f "map_server" >/dev/null 2>&1 || true
pkill -f "smoother_server" >/dev/null 2>&1 || true
pkill -f "velocity_smoother" >/dev/null 2>&1 || true
pkill -f "lifecycle_manager" >/dev/null 2>&1 || true
pkill -f "local_costmap" >/dev/null 2>&1 || true
pkill -f "global_costmap" >/dev/null 2>&1 || true
pkill -f "rviz2" >/dev/null 2>&1 || true
pkill -f "python3 /home/jetson/mopero/robot_ui/server.py" >/dev/null 2>&1 || true
pkill -f "python3 /home/jetson/mopero/robot_ui/run_app.py" >/dev/null 2>&1 || true
pkill -f "run_app.py" >/dev/null 2>&1 || true
pkill -f "robot_ui/server.py" >/dev/null 2>&1 || true
pkill -f "firefox.*http://localhost:5000" >/dev/null 2>&1 || true
pkill -f "chromium.*http://localhost:5000" >/dev/null 2>&1 || true
pkill -f "google-chrome.*http://localhost:5000" >/dev/null 2>&1 || true
rm -f /tmp/robot_ui_active_mode

echo "Stopped old robot stack processes."
