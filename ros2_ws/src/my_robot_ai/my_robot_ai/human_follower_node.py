#!/usr/bin/env python3
import json
import math
import os
import time
from collections import deque

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import LaserScan, Range
from std_msgs.msg import String


class HumanFollowerNode(Node):
    def __init__(self):
        super().__init__('human_follower_node')

        self.declare_parameter('target_distance', 1.5)
        self.declare_parameter('max_linear_speed', 0.08)
        self.declare_parameter('max_angular_speed', 0.35)
        self.declare_parameter('center_stop_distance', 0.65)
        self.declare_parameter('side_stop_distance', 0.45)
        self.declare_parameter('lost_timeout', 2.0)
        self.declare_parameter('person_real_height', 1.70)
        self.declare_parameter('camera_vertical_fov', 1.047)

        self.target_dist = self.get_parameter('target_distance').value
        self.max_lin = self.get_parameter('max_linear_speed').value
        self.max_ang = self.get_parameter('max_angular_speed').value
        self.center_stop_dist = self.get_parameter('center_stop_distance').value
        self.side_stop_dist = self.get_parameter('side_stop_distance').value
        self.lost_timeout = self.get_parameter('lost_timeout').value
        self.person_height = self.get_parameter('person_real_height').value
        self.vfov = self.get_parameter('camera_vertical_fov').value

        self.sonar_ranges = {'left': 2.0, 'center': 2.0, 'right': 2.0}
        self.lidar_ranges = {'left': 2.5, 'center': 2.5, 'right': 2.5}
        self.distance_history = deque(maxlen=5)
        self.last_person_time = 0.0
        self.last_person_bbox = None
        self.last_detections = []
        self.last_detections_time = 0.0
        self.last_log_time = 0.0
        self.smooth_error_x = 0.0
        self.prev_angular = 0.0
        self.target_file = '/tmp/human_follow_target.json'
        self.target_file_mtime = None
        self.target_id = None

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(String, '/yolo/detections', self.det_cb, 10)
        self.create_subscription(LaserScan, '/scan', self.scan_cb, 10)
        self.create_subscription(Range, '/sonar_left', self.sonar_l_cb, 10)
        self.create_subscription(Range, '/sonar_center', self.sonar_c_cb, 10)
        self.create_subscription(Range, '/sonar_right', self.sonar_r_cb, 10)

        self.timer = self.create_timer(0.1, self.control_loop)
        self.get_logger().info('Human follower started: TARGET_LOCK + OBSTACLE_STOP only')

    def read_target_id(self):
        try:
            mtime = os.path.getmtime(self.target_file)
        except OSError:
            mtime = None

        if mtime == self.target_file_mtime:
            return self.target_id

        self.target_file_mtime = mtime
        previous_target_id = self.target_id

        if mtime is None:
            self.target_id = None
        else:
            try:
                with open(self.target_file, 'r', encoding='utf-8') as f:
                    target = json.load(f).get('target_id')
                self.target_id = int(target) if target is not None else None
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                self.target_id = None

        if previous_target_id != self.target_id:
            self.distance_history.clear()
            self.smooth_error_x = 0.0
            self.publish_stop()
            self.get_logger().info(f'target_id changed: {previous_target_id} -> {self.target_id}')

        return self.target_id

    def sonar_l_cb(self, msg):
        self.sonar_ranges['left'] = msg.range

    def sonar_c_cb(self, msg):
        self.sonar_ranges['center'] = msg.range

    def sonar_r_cb(self, msg):
        self.sonar_ranges['right'] = msg.range

    def scan_cb(self, msg):
        sectors = {'left': [], 'center': [], 'right': []}
        for index, distance in enumerate(msg.ranges):
            if not math.isfinite(distance):
                continue
            if distance < msg.range_min or distance > msg.range_max:
                continue

            angle = msg.angle_min + index * msg.angle_increment
            if -0.35 <= angle <= 0.35:
                sectors['center'].append(distance)
            elif 0.35 < angle <= 1.20:
                sectors['left'].append(distance)
            elif -1.20 <= angle < -0.35:
                sectors['right'].append(distance)

        for sector, values in sectors.items():
            if values:
                self.lidar_ranges[sector] = min(values)

    def det_cb(self, msg):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        detections = data.get('detections', [])
        self.last_detections = detections
        self.last_detections_time = time.time()

        target_id = self.read_target_id()
        if target_id is None:
            self.last_person_bbox = None
            return

        target = next((d for d in detections if d.get('track_id') == target_id), None)
        if target is None:
            return

        self.last_person_bbox = target
        self.last_person_time = time.time()

    def nearest_obstacles(self):
        return {
            key: min(self.sonar_ranges[key], self.lidar_ranges[key])
            for key in ('left', 'center', 'right')
        }

    def has_stop_obstacle(self, obstacles):
        return (
            obstacles['center'] < self.center_stop_dist or
            obstacles['left'] < self.side_stop_dist or
            obstacles['right'] < self.side_stop_dist
        )

    def clamp_cmd(self, linear, angular):
        cmd = Twist()
        cmd.linear.x = max(0.0, min(self.max_lin, linear))
        cmd.angular.z = max(-self.max_ang, min(self.max_ang, angular))
        return cmd

    def publish_stop(self):
        cmd = Twist()
        self.cmd_pub.publish(cmd)
        self.prev_angular = 0.0
        return cmd

    def log_state(self, state, cmd, obstacles, est_distance=None, error_x=None):
        now = time.time()
        if now - self.last_log_time < 0.5:
            return
        self.last_log_time = now

        dist_text = '--' if est_distance is None else f'{est_distance:.2f}'
        err_text = '--' if error_x is None else f'{error_x:.2f}'
        self.get_logger().info(
            f'state={state} | dist={dist_text}m | err_x={err_text} | '
            f'obs L/C/R={obstacles["left"]:.2f}/{obstacles["center"]:.2f}/{obstacles["right"]:.2f} | '
            f'lin={cmd.linear.x:.3f} ang={cmd.angular.z:.3f}'
        )

    def control_loop(self):
        obstacles = self.nearest_obstacles()
        target_id = self.read_target_id()

        if self.has_stop_obstacle(obstacles):
            cmd = self.publish_stop()
            self.distance_history.clear()
            self.log_state('STOP_OBSTACLE', cmd, obstacles)
            return

        if target_id is None:
            cmd = self.publish_stop()
            self.distance_history.clear()
            self.log_state('WAIT_TARGET', cmd, obstacles)
            return

        if self.last_person_bbox is None or time.time() - self.last_person_time > self.lost_timeout:
            cmd = self.publish_stop()
            self.distance_history.clear()
            self.log_state(f'LOST_TARGET_ID_{target_id}', cmd, obstacles)
            return

        if self.last_person_bbox.get('track_id') != target_id:
            cmd = self.publish_stop()
            self.distance_history.clear()
            self.log_state(f'WAIT_TARGET_ID_{target_id}', cmd, obstacles)
            return

        bbox = self.last_person_bbox['bbox']
        img_w = self.last_person_bbox['image_width']
        img_h = self.last_person_bbox['image_height']
        bbox_height = bbox['height']
        error_x = (bbox['center_x'] - img_w / 2.0) / img_w

        if bbox_height <= 0:
            cmd = self.publish_stop()
            self.log_state('LOST_PERSON', cmd, obstacles)
            return

        focal_length = img_h / (2.0 * math.tan(self.vfov / 2.0))
        raw_dist = (self.person_height * focal_length) / bbox_height
        self.distance_history.append(raw_dist)
        est_distance = sum(self.distance_history) / len(self.distance_history)

        alpha = 0.12
        self.smooth_error_x = alpha * error_x + (1.0 - alpha) * self.smooth_error_x
        if abs(self.smooth_error_x) < 0.16:
            angular = 0.0
        else:
            angular = -1.2 * self.smooth_error_x
            angular = max(-self.max_ang, min(self.max_ang, angular))
            if abs(angular) < 0.15:
                angular = math.copysign(0.15, angular)

        max_delta = 0.05
        delta = angular - self.prev_angular
        if abs(delta) > max_delta:
            angular = self.prev_angular + math.copysign(max_delta, delta)
        self.prev_angular = angular

        distance_error = est_distance - self.target_dist
        if abs(distance_error) < 0.15:
            linear = 0.0
        else:
            linear = 0.4 * distance_error
            linear = max(0.0, min(self.max_lin, linear))
            if 0 < linear < 0.05:
                linear = 0.05

        if abs(angular) > self.max_ang * 0.7:
            linear *= 0.5

        cmd = self.clamp_cmd(linear, angular)
        self.cmd_pub.publish(cmd)
        self.log_state('FOLLOW', cmd, obstacles, est_distance, error_x)


def main(args=None):
    rclpy.init(args=args)
    node = HumanFollowerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
