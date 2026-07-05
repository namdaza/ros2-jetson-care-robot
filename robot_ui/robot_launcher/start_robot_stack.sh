#!/bin/bash

set -euo pipefail

exec > >(tee -a /tmp/mopero_start_robot_stack.log) 2>&1
echo
echo "========== $(date '+%F %T') start_robot_stack =========="

BASE_DIR="/home/jetson/mopero"
ROBOT_UI_DIR="${BASE_DIR}/robot_ui"
ROS_WS_DIR="${BASE_DIR}/ros2_ws"

echo "[launcher] Khoi dong robot stack + UI"
cd "${ROBOT_UI_DIR}"

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/jetson/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"

echo "[launcher] Doi desktop san sang"
for _ in $(seq 1 30); do
    if [ -S /tmp/.X11-unix/X0 ]; then
        break
    fi
    sleep 1
done

set +u
source /opt/ros/foxy/setup.bash
if [ -f "${ROS_WS_DIR}/install/setup.bash" ]; then
    source "${ROS_WS_DIR}/install/setup.bash"
fi
set -u

echo "[launcher] Don tien trinh cu"
pkill -f "ros2 launch my_robot_nav navigation.launch.py" 2>/dev/null || true
pkill -f "ros2 launch my_robot_nav mapping.launch.py" 2>/dev/null || true
pkill -f "ros2 launch my_robot_nav slam_only.launch.py" 2>/dev/null || true
pkill -f "ros2 launch my_robot_nav teleop.launch.py" 2>/dev/null || true
pkill -f "ros2 launch my_robot_ai human_following.launch.py" 2>/dev/null || true
pkill -f "ros2 launch my_robot_driver robot_driver.launch.py" 2>/dev/null || true
pkill -f "ros2 launch my_robot_driver sonar.launch.py" 2>/dev/null || true
pkill -f "ros2 launch rosbridge_server rosbridge_websocket_launch.xml" 2>/dev/null || true
pkill -f "rosbridge_websocket" 2>/dev/null || true
pkill -f "rosapi_node" 2>/dev/null || true
pkill -f "ui_goal_bridge.py" 2>/dev/null || true
pkill -f "waypoint_manager.py" 2>/dev/null || true
pkill -f "waypoint_manager" 2>/dev/null || true
pkill -f "component_container" 2>/dev/null || true
pkill -f "nav2_" 2>/dev/null || true
pkill -f "sllidar_node" 2>/dev/null || true
pkill -f "scan_filter" 2>/dev/null || true
pkill -f "scan_angle_filter" 2>/dev/null || true
pkill -f "robot_state_publisher" 2>/dev/null || true
pkill -f "joint_state_publisher" 2>/dev/null || true
pkill -f "slam_toolbox" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "amcl" 2>/dev/null || true
pkill -f "controller_server" 2>/dev/null || true
pkill -f "planner_server" 2>/dev/null || true
pkill -f "bt_navigator" 2>/dev/null || true
pkill -f "recoveries_server" 2>/dev/null || true
pkill -f "behavior_server" 2>/dev/null || true
pkill -f "waypoint_follower" 2>/dev/null || true
pkill -f "map_server" 2>/dev/null || true
pkill -f "smoother_server" 2>/dev/null || true
pkill -f "velocity_smoother" 2>/dev/null || true
pkill -f "lifecycle_manager" 2>/dev/null || true
pkill -f "local_costmap" 2>/dev/null || true
pkill -f "global_costmap" 2>/dev/null || true
pkill -f "serial_bridge" 2>/dev/null || true
pkill -f "sonar_node" 2>/dev/null || true
pkill -f "v4l2_camera_node" 2>/dev/null || true
pkill -f "yolo_detection_node" 2>/dev/null || true
pkill -f "human_follower_node" 2>/dev/null || true
pkill -f "yolo_web_stream_node" 2>/dev/null || true
pkill -f "python3 /home/jetson/mopero/robot_ui/server.py" 2>/dev/null || true
pkill -f "python3 /home/jetson/mopero/robot_ui/run_app.py" 2>/dev/null || true
pkill -f "firefox.*http://localhost:5000" 2>/dev/null || true
pkill -f "chromium.*http://localhost:5000" 2>/dev/null || true
pkill -f "google-chrome.*http://localhost:5000" 2>/dev/null || true
rm -f /tmp/robot_ui_active_mode
: > /tmp/robot_ros_stack.log
echo "[launcher] Robot mode idle. Use Trang Quan Ly switches to start Tele, SLAM, Nav2, or Human Following."

echo "[launcher] Khoi dong AI server"
AI_PORT="${AI_PORT:-5001}" /usr/bin/python3 "${ROBOT_UI_DIR}/server.py" > /tmp/robot_ai_server.log 2>&1 &
AI_PID=$!
echo "[launcher] AI server pid=${AI_PID}, log=/tmp/robot_ai_server.log"

bash "${ROBOT_UI_DIR}/start_ui.sh"
