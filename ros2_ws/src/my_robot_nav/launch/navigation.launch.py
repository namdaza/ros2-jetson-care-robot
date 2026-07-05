import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():

    lidar_port_arg = DeclareLaunchArgument(
        'lidar_port', default_value='/dev/lidar',
        description='USB port of RPLidar'
    )
    arduino_port_arg = DeclareLaunchArgument(
        'serial_port', default_value='/dev/arduino_motor',
        description='USB port of Arduino'
    )
    sonar_port_arg = DeclareLaunchArgument(
        'sonar_port', default_value='/dev/arduino_sonar',
        description='USB port of Arduino Nano for Sonar'
    )
    map_yaml_arg = DeclareLaunchArgument(
        'map', default_value=os.path.join(
            get_package_share_directory('my_robot_nav'), 'maps', 'my_room_map.yaml'),
        description='Full path to map yaml file to load'
    )
    waypoints_file_arg = DeclareLaunchArgument(
        'waypoints_file', default_value=os.path.join(
            get_package_share_directory('my_robot_nav'), 'maps', 'my_room_map_waypoints.yaml'),
        description='Full path to waypoint yaml file for the active map'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file', default_value=os.path.join(
            get_package_share_directory('my_robot_nav'), 'config', 'nav2_params.yaml'),
        description='Full path to the ROS2 parameters file to use for all launched nodes'
    )
    enable_web_ui_arg = DeclareLaunchArgument(
        'enable_web_ui', default_value='true',
        description='Start rosbridge and waypoint manager for the browser UI'
    )
    enable_ai_agent_arg = DeclareLaunchArgument(
        'enable_ai_agent', default_value='false',
        description='Start YOLO detection and human follower AI nodes'
    )
    nav2_delay_arg = DeclareLaunchArgument(
        'nav2_delay', default_value='8.0',
        description='Seconds to wait before starting Nav2, so odom TF is available'
    )

    # --- Driver Arduino ---
    driver_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('my_robot_driver'), 'launch', 'robot_driver.launch.py')
        ]),
        launch_arguments={'serial_port': LaunchConfiguration('serial_port')}.items()
    )

    # --- Camera Driver ---
    camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('my_robot_driver'), 'launch', 'camera.launch.py')
        ])
    )

    # --- Sonar Driver ---
    sonar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('my_robot_driver'), 'launch', 'sonar.launch.py')
        ]),
        launch_arguments={'sonar_port': LaunchConfiguration('sonar_port')}.items()
    )

    # --- URDF → Robot State Publisher ---
    urdf_file = os.path.join(get_package_share_directory('my_robot_description'), 'urdf', 'robot.urdf')
    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_desc, 'use_sim_time': False}]
    )

    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
    )

    # --- Lidar A1: xuất ra /scan_raw → qua bộ lọc Python ---
    sllidar_node = Node(
        package='sllidar_ros2',
        executable='sllidar_node',
        name='sllidar_node',
        output='screen',
        parameters=[{
            'serial_port': LaunchConfiguration('lidar_port'),
            'serial_baudrate': 115200,
            'frame_id': 'lidar_link',
            'inverted': False,
            'angle_compensate': True,
        }],
        remappings=[('/scan', '/scan_raw')]
    )

    scan_filter_node = Node(
        package='my_robot_driver',
        executable='scan_filter',
        name='scan_angle_filter',
        output='screen',
        parameters=[{
            'angle_offset': 3.14159,
            'lower_angle': -1.2217,
            'upper_angle':  1.2217,
        }]
    )

    # --- Navigation 2 Bringup (thay thế SLAM) ---
    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'bringup_launch.py')
        ]),
        launch_arguments={
            'use_sim_time': 'False',
            'map': LaunchConfiguration('map'),
            'params_file': LaunchConfiguration('params_file')
        }.items()
    )
    delayed_nav2_bringup = TimerAction(
        period=LaunchConfiguration('nav2_delay'),
        actions=[nav2_bringup]
    )

    rosbridge_launch = IncludeLaunchDescription(
        AnyLaunchDescriptionSource([
            os.path.join(get_package_share_directory('rosbridge_server'), 'launch', 'rosbridge_websocket_launch.xml')
        ]),
        condition=IfCondition(LaunchConfiguration('enable_web_ui'))
    )

    waypoint_manager = Node(
        package='my_robot_nav',
        executable='waypoint_manager.py',
        name='waypoint_manager',
        output='screen',
        parameters=[{
            'waypoints_file': LaunchConfiguration('waypoints_file'),
        }],
        condition=IfCondition(LaunchConfiguration('enable_web_ui'))
    )

    yolo_detection_node = Node(
        package='my_robot_ai',
        executable='yolo_detection',
        name='yolo_detection_node',
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_ai_agent'))
    )

    human_follower_node = Node(
        package='my_robot_ai',
        executable='human_follower',
        name='human_follower_node',
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_ai_agent'))
    )

    return LaunchDescription([
        lidar_port_arg,
        arduino_port_arg,
        sonar_port_arg,
        map_yaml_arg,
        waypoints_file_arg,
        params_file_arg,
        enable_web_ui_arg,
        enable_ai_agent_arg,
        nav2_delay_arg,
        driver_launch,
        camera_launch,
        sonar_launch,
        robot_state_publisher,
        joint_state_publisher,
        sllidar_node,
        scan_filter_node,
        delayed_nav2_bringup,
        rosbridge_launch,
        waypoint_manager,
        yolo_detection_node,
        human_follower_node,
    ])
