#!/usr/bin/env python3
"""
=============================================================================
ROS 2 SERIAL BRIDGE NODE - Kết nối Jetson Nano (ROS 2) ↔ Arduino Uno
=============================================================================
Node này:
  1. Subscribe /cmd_vel (geometry_msgs/Twist)
     → Tính vận tốc bánh trái/phải theo kinematics vi sai
     → Gửi lệnh "CMD,<left_rpm>,<right_rpm>" xuống Arduino qua USB Serial

  2. Đọc dữ liệu "ENC,<lt>,<rt>,<l_rpm>,<r_rpm>" từ Arduino
     → Tính toán Odometry (vị trí x, y, góc theta của robot)
     → Publish lên:
         - /odom          (nav_msgs/Odometry)
         - /tf            (transform odom → base_footprint)

Thông số robot (lấy từ URDF):
  - Bán kính bánh:   0.085 m
  - Khoảng cách 2 bánh: 0.3846 m
=============================================================================
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
import tf2_ros
import serial
import math
import threading
import time
from rclpy.clock import Clock


class SerialBridgeNode(Node):

    def __init__(self):
        super().__init__('serial_bridge_node')

        # ── Tham số có thể cấu hình qua ROS params ──────────────────────────
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate',   115200)
        self.declare_parameter('wheel_radius',    0.085)   # m
        self.declare_parameter('wheel_base',      0.3846)  # m  (khoảng cách 2 tâm bánh)
        self.declare_parameter('max_rpm',         23.0)

        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate   = self.get_parameter('baud_rate').value
        self.R           = self.get_parameter('wheel_radius').value
        self.L           = self.get_parameter('wheel_base').value
        self.max_rpm     = self.get_parameter('max_rpm').value

        # ── Kết nối Serial ────────────────────────────────────────────────────
        self.ser = None
        self.serial_lock = threading.Lock()
        self.last_reconnect_attempt = 0.0
        self.last_serial_warn = 0.0
        if not self._connect_serial(initial=True):
            raise SystemExit(1)

        # ── Trạng thái Odometry ───────────────────────────────────────────────
        self.x     = 0.0
        self.y     = 0.0
        self.theta = 0.0
        self.last_odom_time = self.get_clock().now()

        # ── ROS Publishers & Subscribers ─────────────────────────────────────
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)

        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)

        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # ── Timer 10Hz: publish odom TF liên tục kể cả khi không có encoder data ──
        self.odom_timer = self.create_timer(0.1, self._publish_odom_tf)

        # ── Thread đọc Serial liên tục ────────────────────────────────────────
        self.serial_thread = threading.Thread(
            target=self._serial_reader_thread, daemon=True)
        self.serial_thread.start()

        self.get_logger().info('🤖 Serial Bridge Node đang chạy. Subscribe: /cmd_vel')

    # =========================================================================
    # CALLBACK: Nhận /cmd_vel → tính RPM → gửi Serial xuống Arduino
    # =========================================================================
    def cmd_vel_callback(self, msg: Twist):
        linear_x  = msg.linear.x   # m/s
        angular_z = msg.angular.z  # rad/s

        # Kinematics vi sai:
        # v_left  = linear_x - angular_z * L/2
        # v_right = linear_x + angular_z * L/2
        v_left  = linear_x - angular_z * (self.L / 2.0)
        v_right = linear_x + angular_z * (self.L / 2.0)

        # Chuyển m/s → RPM:  rpm = (v / (2*pi*R)) * 60
        # Ghi chú: Đã thêm dấu trừ (-) để đảo ngược chiều quay thực tế của cả 2 bánh (fix lỗi i lùi, , tiến)
        rpm_left  = -(v_left  / (2.0 * math.pi * self.R)) * 60.0
        rpm_right = -(v_right / (2.0 * math.pi * self.R)) * 60.0

        # Clamp về giới hạn max
        rpm_left  = max(-self.max_rpm, min(self.max_rpm, rpm_left))
        rpm_right = max(-self.max_rpm, min(self.max_rpm, rpm_right))

        cmd = f'CMD,{rpm_left:.2f},{rpm_right:.2f}\n'
        if not self._ensure_serial_connected():
            self._warn_serial_throttled('Serial motor chưa kết nối, bỏ qua /cmd_vel')
            return

        try:
            with self.serial_lock:
                self.ser.write(cmd.encode())
        except serial.SerialException as e:
            self.get_logger().warn(f'Lỗi ghi Serial: {e}')
            self._mark_serial_disconnected()

    # =========================================================================
    # THREAD: Đọc dữ liệu từ Arduino liên tục
    # =========================================================================
    def _serial_reader_thread(self):
        while rclpy.ok():
            if not self._ensure_serial_connected():
                time.sleep(0.2)
                continue

            try:
                with self.serial_lock:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('ENC,'):
                    self._parse_encoder(line)
                elif line:
                    self.get_logger().debug(f'[Arduino] {line}')
            except serial.SerialException as e:
                self.get_logger().error(f'Lỗi đọc Serial: {e}')
                self._mark_serial_disconnected()

    def _connect_serial(self, initial=False):
        try:
            with self.serial_lock:
                self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1.0)
            self.get_logger().info(f'✅ Đã kết nối Serial: {self.serial_port} @ {self.baud_rate}')
            return True
        except serial.SerialException as e:
            level = self.get_logger().error if initial else self.get_logger().warn
            level(f'❌ Không mở được cổng Serial: {e}')
            if initial:
                self.get_logger().error('   Kiểm tra: ls /dev/ttyUSB* hoặc ls /dev/ttyACM*')
            return False

    def _ensure_serial_connected(self):
        if self.ser is not None and self.ser.is_open:
            return True

        now = time.monotonic()
        if now - self.last_reconnect_attempt < 1.5:
            return False

        self.last_reconnect_attempt = now
        return self._connect_serial(initial=False)

    def _mark_serial_disconnected(self):
        with self.serial_lock:
            try:
                if self.ser is not None:
                    self.ser.close()
            except serial.SerialException:
                pass
            self.ser = None

    def _warn_serial_throttled(self, message):
        now = time.monotonic()
        if now - self.last_serial_warn >= 2.0:
            self.get_logger().warn(message)
            self.last_serial_warn = now

    # =========================================================================
    # Publish TF + Odom (gọi bởởi timer 10Hz và parse_encoder)
    # =========================================================================
    def _publish_odom_tf(self):
        """Publish odom → base_footprint TF và /odom dựa trên trạng thái hiện tại."""
        now = self.get_clock().now()

        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)

        # ── TF: odom → base_footprint ────────────────────────────────────
        t = TransformStamped()
        t.header.stamp    = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id  = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(t)

        # ── /odom message ───────────────────────────────────────────────
        odom = Odometry()
        odom.header.stamp    = now.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id  = 'base_footprint'
        odom.pose.pose.position.x    = self.x
        odom.pose.pose.position.y    = self.y
        odom.pose.pose.position.z    = 0.0
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x    = getattr(self, '_last_v',     0.0)
        odom.twist.twist.angular.z   = getattr(self, '_last_omega', 0.0)
        self.odom_pub.publish(odom)

    # =========================================================================
    # PARSE encoder line → Cập nhật vị trí x, y, theta
    # =========================================================================
    def _parse_encoder(self, line: str):
        # Format: "ENC,<left_ticks>,<right_ticks>,<left_rpm>,<right_rpm>"
        # Đảo dấu lại khi đọc từ Arduino để vẽ Odom lên RViz2 không bị ngược hướng
        try:
            parts = line.split(',')
            if len(parts) != 5:
                return
            left_rpm  = -float(parts[3])
            right_rpm = -float(parts[4])
        except (ValueError, IndexError):
            return

        now = self.get_clock().now()
        dt  = (now - self.last_odom_time).nanoseconds / 1e9
        self.last_odom_time = now

        if dt <= 0 or dt > 1.0:
            return

        # Tính vận tốc tuyến tính và góc của robot từ RPM
        v_left  = (left_rpm  / 60.0) * (2.0 * math.pi * self.R)
        v_right = (right_rpm / 60.0) * (2.0 * math.pi * self.R)

        v     = (v_left + v_right) / 2.0
        omega = (v_right - v_left) / self.L

        # Cập nhật tư thế robot (Dead reckoning)
        self.theta += omega * dt
        self.x     += v * math.cos(self.theta) * dt
        self.y     += v * math.sin(self.theta) * dt
        self.theta  = math.atan2(math.sin(self.theta), math.cos(self.theta))

        # Lưu vận tốc hiện tại để timer publish odom đọc
        self._last_v     = v
        self._last_omega = omega
        # (Timer 10Hz sẽ tự publish TF + /odom dựa trên x, y, theta mới nhất)

    # =========================================================================
    def destroy_node(self):
        """Gửi STOP khi node tắt để đảm bảo robot dừng lại."""
        if hasattr(self, 'ser') and self.ser is not None and self.ser.is_open:
            with self.serial_lock:
                self.ser.write(b'STOP\n')
                self.ser.close()
                self.get_logger().info('🛑 Đã gửi STOP và đóng cổng Serial.')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
