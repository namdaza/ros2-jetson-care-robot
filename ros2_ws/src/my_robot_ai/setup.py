from setuptools import setup
import os                                 # <-- THÊM VÀO DÒNG NÀY
from glob import glob                     # <-- THÊM VÀO DÒNG NÀY

package_name = 'my_robot_ai'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # THÊM VÀO DÒNG DƯỚI ĐÂY ĐỂ ĐỌC ĐƯỢC FILE LAUNCH:
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jetson',
    maintainer_email='jetson@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'yolo_detection = my_robot_ai.yolo_detection_node:main',
            'human_follower = my_robot_ai.human_follower_node:main',
            'yolo_web_stream = my_robot_ai.yolo_web_stream_node:main',
        ],
    },
)
