#!/usr/bin/env python3
"""Merge stock nav2_params.yaml with FleetGuard BT plugins + per-robot Nav2 namespacing.

Usage:
  fleet_merge_nav2_fleet_params /path/to/out.yaml [robot_namespace] [/path/to/nav2_params.yaml]
"""
import sys
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory

FLEET_BT_PLUGINS = [
    'fleet_check_fleet_conflict_bt_node',
    'fleet_wait_for_yield_clear_bt_node',
    'fleet_adjust_speed_for_fleet_bt_node',
]


def _rewrite_nav2_namespace(value, key: str, namespace: str):
    """Rewrite frame/topic values so namespaced Gazebo TF matches Nav2 expectations."""
    ns = namespace.strip('/')
    if not ns or not isinstance(value, str):
        return value

    if key == 'base_frame_id':
        return f'{ns}/base_footprint'
    if key == 'robot_base_frame':
        return f'{ns}/base_link'
    if key == 'odom_frame_id':
        return f'{ns}/odom'
    if key == 'global_frame' and value == 'odom':
        return f'{ns}/odom'
    if key == 'odom_topic':
        # Keep this relative so namespace:=robot_a resolves to /robot_a/odom.
        return 'odom'
    if key == 'scan_topic':
        return 'scan'
    if key == 'topic' and value in ('/scan', '/odom'):
        return value.lstrip('/')
    return value


def _walk_and_rewrite(node, namespace: str):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, (dict, list)):
                _walk_and_rewrite(value, namespace)
            else:
                node[key] = _rewrite_nav2_namespace(value, key, namespace)
    elif isinstance(node, list):
        for item in node:
            _walk_and_rewrite(item, namespace)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dest = Path(sys.argv[1])
    namespace = ''
    if len(sys.argv) >= 3:
        maybe_arg = sys.argv[2]
        if maybe_arg.endswith('.yaml'):
            base_yaml = Path(maybe_arg)
        else:
            namespace = maybe_arg
            if len(sys.argv) >= 4:
                base_yaml = Path(sys.argv[3])
            else:
                base_yaml = Path(get_package_share_directory('nav2_bringup')) / 'params' / 'nav2_params.yaml'
    else:
        base_yaml = Path(get_package_share_directory('nav2_bringup')) / 'params' / 'nav2_params.yaml'

    with open(base_yaml, 'r', encoding='utf-8') as fh:
        data = yaml.safe_load(fh)

    fleet_share = get_package_share_directory('fleet_nav2_bt')
    bt_xml = str(Path(fleet_share) / 'behavior_trees' / 'navigate_with_fleet.xml')

    nav_bt = data['bt_navigator']['ros__parameters']
    libs = list(nav_bt['plugin_lib_names'])
    for p in FLEET_BT_PLUGINS:
        if p not in libs:
            libs.append(p)
    nav_bt['plugin_lib_names'] = libs
    nav_bt['default_nav_to_pose_bt_xml'] = bt_xml

    if namespace:
        _walk_and_rewrite(data, namespace)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as fh:
        yaml.dump(data, fh, sort_keys=False, default_flow_style=False)

    print(f'Wrote {dest}')
    print(f'default_nav_to_pose_bt_xml={bt_xml}')
    if namespace:
        print(f'nav2_namespace={namespace}')


if __name__ == '__main__':
    main()
