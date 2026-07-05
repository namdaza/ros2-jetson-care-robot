#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import json
import numpy as np
import traceback
import cv2
import os
import time
from ultralytics import YOLO

# --- TUYỆT CHIÊU MONKEY PATCHING (ÉP NHÂN HỆ THỐNG NHẬN KPT_SHAPE) ---
from ultralytics.nn.autobackend import AutoBackend
AutoBackend.kpt_shape = [17, 3]

class YoloDetectionNode(Node):
    def __init__(self):
        super().__init__('yolo_detection_node')
        self.declare_parameter('model_path', '/home/jetson/mopero/ros2_ws/src/yolov8n-pose.engine')
        model_path = self.get_parameter('model_path').value
        
        self.bridge = CvBridge()
        self.get_logger().info(f"🧠 Loading YOLO Engine: {model_path}")
        self.model = YOLO(model_path, task='pose')
        
        self.meta_yaml = '/tmp/pose_meta.yaml'
        with open(self.meta_yaml, 'w') as f:
            f.write("names:\n  0: person\nnc: 1\nkpt_shape: [17, 3]\n")
        
        self.frame_count = 0
        self.next_track_id = 1
        self.tracks = {}
        self.max_track_age = 1.5
        self.detections_file = '/tmp/yolo_detections.json'
        self.target_file = '/tmp/human_follow_target.json'
        
        self.get_logger().info("🔥 Đang mồi GPU TensorRT ...")
        try:
            dummy_img = np.zeros((320, 320, 3), dtype=np.uint8)
            self.model.predict(dummy_img, data=self.meta_yaml, device=0, verbose=False)
            self.get_logger().info("✅ Warmup xong! Bộ nhớ đã ổn định!")
        except Exception as e:
            self.get_logger().error(f"❌ Lỗi Warmup: {traceback.format_exc()}")
        
        self.det_pub = self.create_publisher(String, '/yolo/detections', 10)
        self.debug_pub = self.create_publisher(Image, '/yolo/debug_image', 1)
        self.image_sub = self.create_subscription(Image, '/image_raw', self.image_cb, 1)

    def read_target_id(self):
        try:
            with open(self.target_file, 'r', encoding='utf-8') as f:
                target = json.load(f).get('target_id')
        except (OSError, json.JSONDecodeError):
            return None
        return int(target) if target is not None else None

    def write_detections_file(self, payload):
        tmp_path = f'{self.detections_file}.tmp'
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f)
            os.replace(tmp_path, self.detections_file)
        except OSError as exc:
            self.get_logger().warn(f'Cannot write detections file: {exc}')

    def bbox_iou(self, a, b):
        ax1, ay1, ax2, ay2 = a['x1'], a['y1'], a['x2'], a['y2']
        bx1, by1, bx2, by2 = b['x1'], b['y1'], b['x2'], b['y2']
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def match_track(self, det, used_track_ids):
        bbox = det['bbox']
        best_id = None
        best_score = 0.0
        for track_id, track in self.tracks.items():
            if track_id in used_track_ids:
                continue

            tb = track['bbox']
            iou = self.bbox_iou(bbox, tb)
            dx = bbox['center_x'] - tb['center_x']
            dy = bbox['center_y'] - tb['center_y']
            distance = (dx * dx + dy * dy) ** 0.5
            max_dim = max(det['image_width'], det['image_height'], 1)
            distance_score = max(0.0, 1.0 - distance / (max_dim * 0.35))
            score = iou * 0.7 + distance_score * 0.3

            if score > best_score:
                best_score = score
                best_id = track_id

        return best_id if best_score >= 0.25 else None

    def assign_track_ids(self, detections):
        now = time.time()
        used_track_ids = set()
        tracked = []

        for det in detections:
            track_id = self.match_track(det, used_track_ids)
            if track_id is None:
                track_id = self.next_track_id
                self.next_track_id += 1

            used_track_ids.add(track_id)
            self.tracks[track_id] = {
                'bbox': det['bbox'],
                'last_seen': now,
            }
            det['track_id'] = track_id
            tracked.append(det)

        self.tracks = {
            track_id: track
            for track_id, track in self.tracks.items()
            if now - track['last_seen'] <= self.max_track_age
        }
        return tracked

    def draw_detections(self, frame, detections, target_id):
        annotated = frame.copy()
        for det in detections:
            bbox = det['bbox']
            track_id = det['track_id']
            locked = target_id == track_id
            color = (40, 220, 40) if locked else (255, 180, 40)
            label = f'ID {track_id}' + (' LOCKED' if locked else '')
            x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            y_text = max(0, y1 - th - 8)
            cv2.rectangle(annotated, (x1, y_text), (x1 + tw + 8, y_text + th + 8), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1 + 4, y_text + th + 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )
        return annotated

    def image_cb(self, msg):
        self.frame_count += 1
        if self.frame_count % 4 != 0:
            return
            
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            cv_img = cv2.resize(cv_img, (0, 0), fx=0.5, fy=0.5)

            results = self.model.predict(cv_img, data=self.meta_yaml, conf=0.5, classes=[0], device=0, verbose=False)

            detections = []
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                confidence = float(box.conf[0].cpu().numpy()) if box.conf is not None else 0.0
                detections.append({
                    'bbox': {
                        'x1': x1,
                        'y1': y1,
                        'x2': x2,
                        'y2': y2,
                        'center_x': int((x1 + x2) / 2),
                        'center_y': int((y1 + y2) / 2),
                        'width': int(x2 - x1),
                        'height': int(y2 - y1),
                    },
                    'confidence': confidence,
                    'image_width': cv_img.shape[1],
                    'image_height': cv_img.shape[0],
                })

            detections = self.assign_track_ids(detections)
            target_id = self.read_target_id()
            payload = {
                'detections': detections,
                'target_id': target_id,
                'stamp': time.time(),
            }
            self.write_detections_file(payload)
            self.det_pub.publish(String(data=json.dumps(payload)))

            annotated = self.draw_detections(cv_img, detections, target_id)
            self.debug_pub.publish(self.bridge.cv2_to_imgmsg(annotated, "bgr8"))
        except Exception as e:
            self.get_logger().error(f"[Loop Error]:\n{traceback.format_exc()}")

def main():
    rclpy.init()
    rclpy.spin(YoloDetectionNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
