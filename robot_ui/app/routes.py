from pathlib import Path
from flask import Blueprint, render_template, request, jsonify
import json
import subprocess
import re
import os
import socket
import time
from .admin import check_password

main = Blueprint("main", __name__)

BASE_DIR = Path(os.environ.get("MOPERO_BASE_DIR", Path(__file__).resolve().parents[2]))
ROS_WS_DIR = BASE_DIR / "ros2_ws"
MAP_DIR = ROS_WS_DIR / "src" / "my_robot_nav" / "maps"
RVIZ_MAPPING_CONFIG = ROS_WS_DIR / "src" / "my_robot_nav" / "rviz" / "mapping.rviz"
ACTIVE_MAP_FILE = MAP_DIR / ".active_map"
ROS_LOG = Path("/tmp/robot_ros_stack.log")
MODE_STATE_FILE = Path("/tmp/robot_ui_active_mode")
HUMAN_TARGET_FILE = Path("/tmp/human_follow_target.json")
HUMAN_DETECTIONS_FILE = Path("/tmp/yolo_detections.json")
MAP_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
VALID_MODES = {"tele", "slam", "nav2", "human"}

@main.route("/")
def index():
    admin_pw = os.getenv("ADMIN_PASSWORD_FRONTEND", "1234")
    return render_template("index.html", admin_password=admin_pw)

@main.route("/map")
def robot_map():
    return render_template("map.html")


@main.route("/admin")
def admin_page():
    return render_template("admin.html")


@main.route("/human-following")
@main.route("/management-camera")
def management_camera():
    host = request.host.split(":", 1)[0]
    return_url = request.args.get("return") or "/"
    if not return_url.startswith("/") or return_url.startswith("//"):
        return_url = "/"
    stream_base_url = f"{request.scheme}://{host}:5002"
    return render_template(
        "human_following.html",
        stream_url=f"{stream_base_url}/stream.mjpg",
        return_url=return_url,
    )


@main.route("/api/human-following/status", methods=["GET"])
def human_following_status():
    payload = read_json_file(HUMAN_DETECTIONS_FILE, {})
    detections = payload.get("detections", [])
    stamp = float(payload.get("stamp") or 0.0)
    if time.time() - stamp > 2.0:
        detections = []

    target_payload = read_json_file(HUMAN_TARGET_FILE, {"target_id": None})
    return jsonify({
        "ok": True,
        "active": current_mode(),
        "target_id": target_payload.get("target_id"),
        "detections": detections,
        "stamp": stamp,
    })


@main.route("/api/human-following/target", methods=["POST"])
def human_following_target():
    data = request.get_json() or {}
    target_id = data.get("target_id")

    if target_id is None:
        set_human_target(None)
        return jsonify({"ok": True, "target_id": None})

    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "ID không hợp lệ"}), 400

    if target_id < 1:
        return jsonify({"ok": False, "error": "ID không hợp lệ"}), 400

    detections_payload = read_json_file(HUMAN_DETECTIONS_FILE, {})
    detections = detections_payload.get("detections", [])
    stamp = float(detections_payload.get("stamp") or 0.0)
    if time.time() - stamp > 2.0:
        detections = []

    if not any(det.get("track_id") == target_id for det in detections):
        return jsonify({"ok": False, "error": "Không thấy ID này trong khung hình"}), 404

    set_human_target(target_id)
    return jsonify({"ok": True, "target_id": target_id})


@main.route("/api/human-following/stop", methods=["POST"])
def human_following_stop():
    set_human_target(None)
    return jsonify({"ok": True, "target_id": None})


def run_stack_command(command: str):
    log = open(ROS_LOG, "a", encoding="utf-8")
    return subprocess.Popen(
        ["/bin/bash", "-lc", command],
        cwd=str(BASE_DIR),
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def run_shell_command(command: str, timeout: float = 10.0):
    with open(ROS_LOG, "a", encoding="utf-8") as log:
        return subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=str(BASE_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )


def tcp_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_tcp_port(host: str, port: int, timeout_seconds: float = 10.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if tcp_port_open(host, port):
            return True
        time.sleep(0.25)
    return False


def wait_for_tcp_port_closed(host: str, port: int, timeout_seconds: float = 6.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not tcp_port_open(host, port):
            return True
        time.sleep(0.25)
    return False


def current_mode():
    if MODE_STATE_FILE.exists():
        mode = MODE_STATE_FILE.read_text(encoding="utf-8").strip()
        if mode == "manual":
            return "tele"
        if mode in VALID_MODES:
            return mode
    return "idle"


def set_current_mode(mode: str):
    if mode == "idle":
        MODE_STATE_FILE.unlink(missing_ok=True)
    elif mode in VALID_MODES:
        MODE_STATE_FILE.write_text(mode, encoding="utf-8")


def write_json_atomic(path: Path, payload: dict):
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json_dumps(payload), encoding="utf-8")
    tmp_path.replace(path)


def json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def read_json_file(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def set_human_target(target_id):
    write_json_atomic(HUMAN_TARGET_FILE, {
        "target_id": target_id,
        "updated_at": time.time(),
    })


def stop_robot_modes_command():
    patterns = [
        "ros2 launch my_robot_nav navigation.launch.py",
        "ros2 launch my_robot_nav mapping.launch.py",
        "ros2 launch my_robot_nav slam_only.launch.py",
        "ros2 launch my_robot_ai human_following.launch.py",
        "ros2 launch my_robot_nav teleop.launch.py",
        "ros2 launch my_robot_driver robot_driver.launch.py",
        "ros2 launch my_robot_driver sonar.launch.py",
        "ros2 launch rosbridge_server rosbridge_websocket_launch.xml",
        "rosbridge_websocket",
        "rosapi_node",
        "ui_goal_bridge.py",
        "waypoint_manager.py",
        "waypoint_manager",
        "component_container",
        "nav2_",
        "rviz2",
        "sllidar_node",
        "scan_filter",
        "scan_angle_filter",
        "robot_state_publisher",
        "joint_state_publisher",
        "slam_toolbox",
        "async_slam_toolbox_node",
        "amcl",
        "controller_server",
        "planner_server",
        "bt_navigator",
        "recoveries_server",
        "behavior_server",
        "waypoint_follower",
        "map_server",
        "planner_server",
        "smoother_server",
        "velocity_smoother",
        "lifecycle_manager",
        "local_costmap",
        "global_costmap",
        "serial_bridge",
        "sonar_node",
        "v4l2_camera_node",
        "yolo_detection_node",
        "human_follower_node",
        "yolo_web_stream_node",
    ]
    quoted_patterns = " ".join(f"'{pattern}'" for pattern in patterns)
    return (
        "echo '--- stopping robot modes ---'; "
        f"for pattern in {quoted_patterns}; do "
        "for pid in $(pgrep -f \"$pattern\" 2>/dev/null || true); do "
        "echo \"TERM $pid $pattern\"; "
        "[ \"$pid\" != \"$$\" ] && kill -TERM \"$pid\" 2>/dev/null || true; "
        "done; "
        "done; "
        "sleep 2; "
        f"for pattern in {quoted_patterns}; do "
        "for pid in $(pgrep -f \"$pattern\" 2>/dev/null || true); do "
        "echo \"KILL $pid $pattern\"; "
        "[ \"$pid\" != \"$$\" ] && kill -KILL \"$pid\" 2>/dev/null || true; "
        "done; "
        "done; "
        "sleep 1"
    )


def stop_robot_modes():
    try:
        run_shell_command(stop_robot_modes_command(), timeout=12.0)
    except subprocess.TimeoutExpired:
        pass
    wait_for_tcp_port_closed("127.0.0.1", 9090)


def ros_env_command():
    return (
        "export DISPLAY=${DISPLAY:-:0}; "
        "export XAUTHORITY=${XAUTHORITY:-/home/jetson/.Xauthority}; "
        "export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/1000}; "
        "source /opt/ros/foxy/setup.bash; "
        f"source {ROS_WS_DIR}/install/setup.bash; "
        f"cd {ROS_WS_DIR}; "
    )


def selected_map_name():
    if ACTIVE_MAP_FILE.exists():
        name = ACTIVE_MAP_FILE.read_text(encoding="utf-8").strip()
        if is_valid_nav_map_name(name) and (MAP_DIR / f"{name}.yaml").exists():
            return name
        if name.endswith("_waypoints"):
            base_name = name[:-10]
            if is_valid_nav_map_name(base_name) and (MAP_DIR / f"{base_name}.yaml").exists():
                ACTIVE_MAP_FILE.write_text(base_name, encoding="utf-8")
                return base_name
    if (MAP_DIR / "my_room_map.yaml").exists():
        return "my_room_map"
    maps = sorted(path for path in MAP_DIR.glob("*.yaml") if is_valid_nav_map_name(path.stem))
    return maps[0].stem if maps else None


def map_yaml_path(name: str) -> Path:
    return MAP_DIR / f"{name}.yaml"


def waypoint_yaml_path(name: str) -> Path:
    return MAP_DIR / f"{name}_waypoints.yaml"


def is_valid_map_name(name: str) -> bool:
    return bool(MAP_NAME_RE.fullmatch(name or ""))


def is_valid_nav_map_name(name: str) -> bool:
    return is_valid_map_name(name) and not (name or "").endswith("_waypoints")


def human_camera_device() -> str:
    for device in ("/dev/camera_human", "/dev/video1", "/dev/video0"):
        if Path(device).exists():
            return device
    return "/dev/video0"


@main.route("/api/modes/status", methods=["GET"])
def mode_status():
    return jsonify({
        "ok": True,
        "active": current_mode(),
        "active_map": selected_map_name(),
    })


@main.route("/api/modes/stop", methods=["POST"])
def stop_modes():
    stop_robot_modes()
    set_current_mode("idle")
    set_human_target(None)
    return jsonify({"ok": True, "active": "idle"})


@main.route("/api/modes/start", methods=["POST"])
def start_mode():
    data = request.get_json() or {}
    mode = data.get("mode", "")
    if mode not in VALID_MODES:
        return jsonify({"ok": False, "error": "Mode không hợp lệ"}), 400

    active = current_mode()
    if active != "idle" and active != mode:
        return jsonify({
            "ok": False,
            "error": "Tắt tính năng hiện tại trước khi bật tính năng khác",
            "active": active,
        }), 409

    stop_robot_modes()

    if mode == "tele":
        command = (
            ros_env_command()
            + "echo '--- starting mode: tele ---'; "
            + "ros2 launch my_robot_nav teleop.launch.py "
            "serial_port:=/dev/arduino_motor "
            "rosbridge_port:=9090 "
            "rosbridge_address:=0.0.0.0"
        )
    elif mode == "slam":
        command = (
            ros_env_command()
            + "echo '--- starting mode: slam ---'; "
            + "ros2 launch my_robot_nav slam_only.launch.py "
            "lidar_port:=/dev/lidar "
            "serial_port:=/dev/arduino_motor"
        )
    elif mode == "nav2":
        name = data.get("map") or selected_map_name()
        if not is_valid_nav_map_name(name) or not map_yaml_path(name).exists():
            return jsonify({"ok": False, "error": "Map không hợp lệ"}), 400
        ACTIVE_MAP_FILE.write_text(name, encoding="utf-8")
        command = (
            ros_env_command()
            + "echo '--- starting mode: nav2 ---'; "
            + "ros2 launch my_robot_nav navigation.launch.py "
            "enable_web_ui:=true "
            f"map:={map_yaml_path(name)} "
            f"waypoints_file:={waypoint_yaml_path(name)} "
            "lidar_port:=/dev/lidar "
            "serial_port:=/dev/arduino_motor "
            "sonar_port:=/dev/arduino_sonar"
        )
    else:
        camera_device = human_camera_device()
        set_human_target(None)
        command = (
            ros_env_command()
            + f"echo '--- starting mode: human camera={camera_device} ---'; "
            + "export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1${LD_PRELOAD:+:$LD_PRELOAD}; "
            + "ros2 launch my_robot_ai human_following.launch.py "
            "serial_port:=/dev/arduino_motor "
            "sonar_port:=/dev/arduino_sonar "
            f"video_device:={camera_device} "
            "web_stream_fps:=2.0 "
            "web_stream_quality:=60"
        )

    run_stack_command(command)
    if mode == "tele" and not wait_for_tcp_port("127.0.0.1", 9090):
        set_current_mode("idle")
        return jsonify({
            "ok": False,
            "error": "Tele Only đã gọi launch nhưng rosbridge chưa mở port 9090. Xem /tmp/robot_ros_stack.log",
        }), 503

    set_current_mode(mode)
    return jsonify({"ok": True, "active": mode})


@main.route("/api/maps", methods=["GET"])
def list_maps():
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    active = selected_map_name()
    maps = []
    for yaml_path in sorted(MAP_DIR.glob("*.yaml")):
        if not is_valid_nav_map_name(yaml_path.stem):
            continue
        maps.append({
            "name": yaml_path.stem,
            "yaml": yaml_path.name,
            "active": yaml_path.stem == active,
            "mtime": int(yaml_path.stat().st_mtime),
        })
    return jsonify({"ok": True, "active": active, "maps": maps})


@main.route("/api/maps/select", methods=["POST"])
def select_map():
    data = request.get_json() or {}
    name = data.get("name", "")
    if not is_valid_nav_map_name(name):
        return jsonify({"ok": False, "error": "Tên map không hợp lệ"}), 400
    if not map_yaml_path(name).exists():
        return jsonify({"ok": False, "error": "Map không tồn tại"}), 404
    ACTIVE_MAP_FILE.write_text(name, encoding="utf-8")
    return jsonify({"ok": True, "active": name})


@main.route("/api/maps/save", methods=["POST"])
def save_map():
    data = request.get_json() or {}
    name = data.get("name", "")
    if not is_valid_map_name(name):
        return jsonify({"ok": False, "error": "Tên map chỉ dùng chữ, số, _ hoặc -"}), 400

    MAP_DIR.mkdir(parents=True, exist_ok=True)
    output_prefix = MAP_DIR / name
    command = (
        "set -e; "
        "source /opt/ros/foxy/setup.bash; "
        f"source {ROS_WS_DIR}/install/setup.bash; "
        f"ros2 run nav2_map_server map_saver_cli -f {output_prefix} "
        "--ros-args "
        "-p save_map_timeout:=20.0 "
        "-p map_subscribe_transient_local:=false "
        "-p free_thresh_default:=0.25 "
        "-p occupied_thresh_default:=0.65"
    )
    try:
        result = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=str(ROS_WS_DIR),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Lưu map quá thời gian"}), 504

    if result.returncode != 0:
        return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500

    ACTIVE_MAP_FILE.write_text(name, encoding="utf-8")
    return jsonify({"ok": True, "active": name})


@main.route("/api/robot/start-mapping", methods=["POST"])
def start_mapping():
    command = (
        stop_robot_modes_command() + "; "
        "export DISPLAY=${DISPLAY:-:0}; "
        "export XAUTHORITY=${XAUTHORITY:-/home/jetson/.Xauthority}; "
        "export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/1000}; "
        "source /opt/ros/foxy/setup.bash; "
        f"source {ROS_WS_DIR}/install/setup.bash; "
        f"cd {ROS_WS_DIR}; "
        "ros2 launch my_robot_nav mapping.launch.py & "
        "MAPPING_PID=$!; "
        "sleep 8; "
        f"rviz2 -d {RVIZ_MAPPING_CONFIG} >/tmp/robot_rviz2.log 2>&1 & "
        "wait ${MAPPING_PID}"
    )
    run_stack_command(command)
    return jsonify({"ok": True, "mode": "mapping", "rviz": True})


@main.route("/api/robot/start-navigation", methods=["POST"])
def start_navigation():
    data = request.get_json() or {}
    name = data.get("name") or selected_map_name()
    if not is_valid_nav_map_name(name) or not map_yaml_path(name).exists():
        return jsonify({"ok": False, "error": "Map không hợp lệ"}), 400
    ACTIVE_MAP_FILE.write_text(name, encoding="utf-8")

    command = (
        stop_robot_modes_command() + "; "
        "source /opt/ros/foxy/setup.bash; "
        f"source {ROS_WS_DIR}/install/setup.bash; "
        f"cd {ROS_WS_DIR}; "
        f"ros2 launch my_robot_nav navigation.launch.py "
        f"enable_web_ui:=true "
        f"map:={map_yaml_path(name)} "
        f"waypoints_file:={waypoint_yaml_path(name)} "
        f"lidar_port:=/dev/lidar "
        f"serial_port:=/dev/arduino_motor "
        f"sonar_port:=/dev/arduino_sonar"
    )
    run_stack_command(command)
    return jsonify({"ok": True, "mode": "navigation", "active": name})

@main.route("/exit", methods=["POST"])
def exit_kiosk():
    data = request.get_json()
    pw = data.get("password", "")

    if check_password(pw):
        try:
            subprocess.run(["pkill", "firefox"])
            return jsonify ({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    return jsonify({"ok": False, "message": "sai mau khau!"})
