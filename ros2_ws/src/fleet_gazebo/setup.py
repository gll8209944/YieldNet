from setuptools import setup
import os
from glob import glob

package_name = 'fleet_gazebo'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'scripts'), glob('scripts/*.py')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    entry_points={
        'console_scripts': [
            'fleet_merge_nav2_fleet_params = fleet_gazebo.merge_nav2_fleet_params:main',
        ],
    },
    zip_safe=True,
    maintainer='guolinlin',
    maintainer_email='guolinlin@hotmail.com',
    description='Fleet Collision Avoidance Gazebo Simulation',
    license='Apache-2.0',
)
