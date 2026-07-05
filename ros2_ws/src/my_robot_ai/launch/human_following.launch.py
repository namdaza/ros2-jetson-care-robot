from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():

    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyUSB0',
        description='Cổng USB kết nối với Arduino (/dev/ttyUSB0 hoặc /dev/ttyACM0)'
    )

    sonar_port_arg = DeclareLaunchArgument(
        'sonar_port',
        default_value='/dev/ttyUSB1',
        description='Cổng USB kết nối với Arduino Nano siêu âm'
    )

    video_device_arg = DeclareLaunchArgument(
        'video_device',
        default_value='/dev/camera_human',
        description='Camera device dùng cho human following'
    )

    model_path_arg = DeclareLaunchArgument(
        'model_path',
        default_value='/home/jetson/mopero/ros2_ws/src/yolov8n-pose.engine',
        description='Đường dẫn TensorRT YOLO pose engine'
    )

    center_stop_distance_arg = DeclareLaunchArgument(
        'center_stop_distance',
        default_value='0.65',
        description='Khoảng cách dừng khi vật cản ở trước mặt, mét'
    )

    side_stop_distance_arg = DeclareLaunchArgument(
        'side_stop_distance',
        default_value='0.45',
        description='Khoảng cách dừng khi vật cản ở hai bên, mét'
    )

    web_stream_port_arg = DeclareLaunchArgument(
        'web_stream_port',
        default_value='5002',
        description='HTTP port để xem YOLO debug stream trên browser'
    )

    web_stream_fps_arg = DeclareLaunchArgument(
        'web_stream_fps',
        default_value='5.0',
        description='FPS tối đa cho web stream'
    )

    web_stream_quality_arg = DeclareLaunchArgument(
        'web_stream_quality',
        default_value='70',
        description='JPEG quality cho web stream'
    )

    # ── 1. Camera (v4l2) ─────────────────────────────────────────────────────
    camera_node = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='camera_node',
        output='screen',
        parameters=[{
            'video_device': LaunchConfiguration('video_device'),
            'image_size': [320, 240],
            'pixel_format': 'YUYV',
            'camera_frame_id': 'camera_link_optical',
        }]
    )

    # ── 2. YOLO Detection ─────────────────────────────────────────────────────
    yolo_node = Node(
        package='my_robot_ai',
        executable='yolo_detection',
        name='yolo_detection_node',
        output='screen',
        parameters=[{
            'model_path': LaunchConfiguration('model_path'),
        }]
    )

    # ── 3. Human Follower (tính toán cmd_vel) ─────────────────────────────────
    follower_node = Node(
        package='my_robot_ai',
        executable='human_follower',
        name='human_follower_node',
        output='screen',
        parameters=[{
            'center_stop_distance': ParameterValue(LaunchConfiguration('center_stop_distance'), value_type=float),
            'side_stop_distance': ParameterValue(LaunchConfiguration('side_stop_distance'), value_type=float),
        }]
    )

    # ── 4. Serial Bridge (gửi cmd_vel xuống Arduino) ──────────────────────────
    serial_bridge_node = Node(
        package='my_robot_driver',
        executable='serial_bridge',
        name='serial_bridge_node',
        output='screen',
        parameters=[{
            'serial_port':  LaunchConfiguration('serial_port'),  # ← nhận từ argument
            'baud_rate':    115200,
            'wheel_radius': 0.085,    # ← khớp với serial_bridge_node.py
            'wheel_base':   0.3846,   # ← khớp với serial_bridge_node.py
            'max_rpm':      23.0,
        }]
    )

    # ── 5. Sonar Bridge (publish /sonar_left, /sonar_center, /sonar_right) ──────
    sonar_node = Node(
        package='my_robot_driver',
        executable='sonar',
        name='sonar_node',
        output='screen',
        parameters=[{
            'serial_port': LaunchConfiguration('sonar_port'),
            'baud_rate': 115200,
        }]
    )

    # ── 6. Web Stream (serve /yolo/debug_image as MJPEG for laptop browser) ──────
    yolo_web_stream_node = Node(
        package='my_robot_ai',
        executable='yolo_web_stream',
        name='yolo_web_stream_node',
        output='screen',
        parameters=[{
            'image_topic': '/yolo/debug_image',
            'host': '0.0.0.0',
            'port': ParameterValue(LaunchConfiguration('web_stream_port'), value_type=int),
            'max_fps': ParameterValue(LaunchConfiguration('web_stream_fps'), value_type=float),
            'jpeg_quality': ParameterValue(LaunchConfiguration('web_stream_quality'), value_type=int),
        }]
    )

    return LaunchDescription([
        serial_port_arg,
        sonar_port_arg,
        video_device_arg,
        model_path_arg,
        center_stop_distance_arg,
        side_stop_distance_arg,
        web_stream_port_arg,
        web_stream_fps_arg,
        web_stream_quality_arg,
        camera_node,
        yolo_node,
        follower_node,
        serial_bridge_node,
        sonar_node,
        yolo_web_stream_node,
    ])
