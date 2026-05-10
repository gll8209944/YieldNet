#!/usr/bin/env python3
"""Merge stock nav2_params.yaml with FleetGuard BT plugins + per-robot Nav2 namespacing.

Usage:
  fleet_merge_nav2_fleet_params /path/to/out.yaml [robot_namespace] [/path/to/nav2_params.yaml]

Env:
  BT_XML_MODE  - fleet | default | goal_updated | conflict | speed (default: fleet)
  NAV2_BT_XML  - absolute BT XML path override
"""
import os
import sys
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory

FLEET_BT_PLUGINS = [
    'fleet_check_fleet_conflict_bt_node',
    'fleet_wait_for_yield_clear_bt_node',
    'fleet_adjust_speed_for_fleet_bt_node',
]

BT_XML_BY_MODE = {
    'fleet': 'navigate_with_fleet.xml',
    'default': 'navigate_default_follow_path.xml',
    'goal_updated': 'navigate_goal_updated_follow_path.xml',
    'conflict': 'navigate_with_conflict_check.xml',
    'speed': 'navigate_with_speed.xml',
}


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


def _apply_e2e_nav2_stability_overrides(data):
    """Apply narrow Nav2 overrides for the corridor e2e yield scenario."""
    controller_params = data.get('controller_server', {}).get('ros__parameters', {})
    controller_params['failure_tolerance'] = max(
        float(controller_params.get('failure_tolerance', 0.0) or 0.0),
        2.0,
    )

    progress_checker = controller_params.get('progress_checker', {})
    if isinstance(progress_checker, dict):
        progress_checker['required_movement_radius'] = min(
            float(progress_checker.get('required_movement_radius', 0.5) or 0.5),
            0.1,
        )
        progress_checker['movement_time_allowance'] = max(
            float(progress_checker.get('movement_time_allowance', 10.0) or 10.0),
            20.0,
        )

    for costmap_name in ('local_costmap',):
        costmap = data.get(costmap_name, {}).get(f'{costmap_name}', {}).get('ros__parameters', {})
        costmap['width'] = max(int(costmap.get('width', 3) or 3), 6)
        costmap['height'] = max(int(costmap.get('height', 3) or 3), 6)
        inflation = costmap.get('inflation_layer', {})
        if isinstance(inflation, dict):
            inflation['inflation_radius'] = min(
                float(inflation.get('inflation_radius', 0.55) or 0.55),
                0.35,
            )


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
    bt_xml_override = os.environ.get('NAV2_BT_XML', '').strip()
    bt_xml_mode = os.environ.get('BT_XML_MODE', 'fleet').strip() or 'fleet'
    if bt_xml_override:
        bt_xml = bt_xml_override
    else:
        try:
            bt_xml_name = BT_XML_BY_MODE[bt_xml_mode]
        except KeyError:
            valid_modes = ', '.join(sorted(BT_XML_BY_MODE))
            raise SystemExit(f'Unknown BT_XML_MODE={bt_xml_mode!r}; valid modes: {valid_modes}')
        bt_xml = str(Path(fleet_share) / 'behavior_trees' / bt_xml_name)

    nav_bt = data['bt_navigator']['ros__parameters']
    libs = list(nav_bt['plugin_lib_names'])
    for p in FLEET_BT_PLUGINS:
        if p not in libs:
            libs.append(p)
    nav_bt['plugin_lib_names'] = libs
    nav_bt['default_nav_to_pose_bt_xml'] = bt_xml

    if namespace:
        _walk_and_rewrite(data, namespace)

    _apply_e2e_nav2_stability_overrides(data)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as fh:
        yaml.dump(data, fh, sort_keys=False, default_flow_style=False)

    print(f'Wrote {dest}')
    print(f'bt_xml_mode={bt_xml_mode}')
    print(f'default_nav_to_pose_bt_xml={bt_xml}')
    if namespace:
        print(f'nav2_namespace={namespace}')


if __name__ == '__main__':
    main()
