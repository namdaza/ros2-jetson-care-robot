<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:22314E,100:76B900&height=220&section=header&text=Mopero&fontColor=ffffff&fontSize=58&desc=ROS%202%20Jetson%20Care%20Robot&descSize=18&descAlignY=64" alt="Mopero banner" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/ROS%202-Foxy-22314E?style=for-the-badge&logo=ros&logoColor=white" alt="ROS 2 Foxy" />
  <img src="https://img.shields.io/badge/Ubuntu-20.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white" alt="Ubuntu 20.04" />
  <img src="https://img.shields.io/badge/Python-3.8-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8" />
  <img src="https://img.shields.io/badge/NVIDIA-Jetson-76B900?style=for-the-badge&logo=nvidia&logoColor=white" alt="NVIDIA Jetson" />
  <img src="https://img.shields.io/badge/Status-Prototype-yellow?style=for-the-badge" alt="Prototype status" />
</p>

<p align="center">
  <img src="https://skillicons.dev/icons?i=python,flask,opencv,arduino,linux,bash,git" alt="Technology icons" />
</p>

## Overview

**Mopero** is a prototype care-assistant robot built around **NVIDIA Jetson + ROS 2 Foxy**. It combines motor control, lidar navigation, sonar safety sensing, camera perception, human-following behavior, and a Flask kiosk interface with a Vietnamese AI voice assistant.

> This project is designed for real-robot experimentation. Hardware ports, model paths, map files, and startup scripts may need to be adjusted for your own Jetson setup.

## Highlights

| Module | What it does |
| --- | --- |
| ![ROS](https://img.shields.io/badge/ROS%202-22314E?logo=ros&logoColor=white) | Coordinates robot drivers, navigation, perception, and transforms |
| ![Arduino](https://img.shields.io/badge/Arduino-00979D?logo=arduino&logoColor=white) | Receives velocity commands and controls the differential-drive motors |
| ![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?logo=opencv&logoColor=white) | Handles camera-based perception and visual processing |
| ![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white) | Provides the kiosk UI and AI assistant endpoints |
| ![NVIDIA](https://img.shields.io/badge/Jetson-76B900?logo=nvidia&logoColor=white) | Runs ROS 2, AI workloads, and the local user interface |

Core capabilities:

- Differential-drive control through `/cmd_vel`.
- ROS 2 serial bridge for Arduino motor control.
- Encoder odometry publishing on `/odom`.
- RPLIDAR scan publishing and filtering.
- Sonar range publishing for left, center, and right sensors.
- SLAM and Nav2 launch files for mapping and navigation.
- USB camera publishing through `v4l2_camera`.
- YOLO-based person detection and human-following behavior.
- Flask UI on port `5000`.
- Browser map UI for robot pose, initial pose, and navigation goals.
- `rosbridge_server` WebSocket integration on port `9090`.
- AI server on port `5001` with chat, STT, and TTS endpoints.

## System Architecture

```mermaid
flowchart LR
    user["User / Caregiver"] --> ui["Flask Kiosk UI<br/>robot_ui/run_app.py"]
    ui --> map_ui["Robot Map Page<br/>/map"]
    ui <--> ai_server["AI Server<br/>robot_ui/server.py"]
    ai_server <--> gemini["Gemini API<br/>Chat + STT"]
    ai_server --> tts["gTTS<br/>Vietnamese TTS"]
    map_ui <--> rosbridge["rosbridge_server<br/>ws://host:9090"]

    subgraph jetson["NVIDIA Jetson / Ubuntu 20.04"]
        ros["ROS 2 Foxy"]
        driver["my_robot_driver<br/>serial, sonar, scan filter"]
        nav["my_robot_nav<br/>SLAM + Nav2"]
        goal_bridge["ui_goal_bridge.py<br/>browser goals to Nav2"]
        perception["my_robot_ai<br/>YOLO + human follower"]
        description["my_robot_description<br/>URDF + robot frames"]
    end

    subgraph hardware["Robot Hardware"]
        arduino_motor["Arduino Motor Controller"]
        motors["DC Motors + Encoders"]
        lidar["RPLIDAR"]
        sonar["Sonar Sensors"]
        camera["USB Camera / Microphone"]
    end

    rosbridge --> ros
    rosbridge --> goal_bridge
    ros --> driver
    ros --> nav
    goal_bridge --> nav
    ros --> perception
    ros --> description

    driver <--> arduino_motor
    arduino_motor <--> motors
    lidar --> driver
    sonar --> driver
    camera --> perception

    perception -->|/cmd_vel| driver
    nav -->|/cmd_vel| driver
    driver -->|/odom, /scan, /sonar_*| ros
```

## Hardware Setup

| Component | Role |
| --- | --- |
| NVIDIA Jetson | Main compute unit for ROS 2, UI, and AI workloads |
| Arduino motor controller | Receives serial commands and controls the motors |
| DC motors + encoders | Differential-drive movement and odometry feedback |
| RPLIDAR | Laser scan input for mapping and navigation |
| Sonar sensors | Short-range safety sensing |
| USB camera + microphone | Vision input and voice interaction |
| Battery and regulators | Power distribution for robot electronics |

Important robot parameters:

| Parameter | Value |
| --- | --- |
| Wheel radius | `0.085 m` |
| Wheel base | `0.3846 m` |
| Max motor speed | `23 RPM` |
| Base frame | `base_footprint` |
| Odom frame | `odom` |
| Map frame | `map` |

---

## Instructions

### 1. Prerequisites
- **OS**: Ubuntu 20.04
- **ROS 2**: Foxy
- **Python**: 3.8
- **Hardware**: NVIDIA Jetson

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/namdaza/mopero.git
cd mopero

# Build the ROS 2 workspace
source /opt/ros/foxy/setup.bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash

# Configure USB device names
sudo ./install_udev_rules.sh
sudo udevadm control --reload-rules && sudo udevadm trigger

# Configure the UI and AI server
cd ~/mopero/robot_ui
cp .env.example .env
nano .env # Add your Gemini API key and admin passwords here
```

### 3. Usage
You can start the entire robot stack (ROS navigation, rosbridge, AI server, and browser UI) using the provided launcher:

```bash
cd ~/mopero/robot_ui/robot_launcher
bash ./start_robot_stack.sh
```

**Accessing the Interfaces:**
- **Main UI:** `http://localhost:5000/`
- **Robot Map:** `http://localhost:5000/map`
- **AI Camera (Human Following):** `http://localhost:5000/human-following`
- **Debug Stream:** `http://localhost:5002/`

**To stop the stack:**
```bash
cd ~/mopero/ros2_ws
bash ./stop_robot_stack.sh
```

### 4. Development Notes
- The admin map page is accessed via the **Trang Quản Lý** button.
- Make sure to use udev symlinks (e.g. `/dev/arduino_motor`, `/dev/lidar`, `/dev/arduino_sonar`) instead of raw `ttyUSB*` ports.
- The YOLO node uses `LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1` to avoid memory allocation errors on the Jetson Nano. This is handled automatically by the web UI launcher.
