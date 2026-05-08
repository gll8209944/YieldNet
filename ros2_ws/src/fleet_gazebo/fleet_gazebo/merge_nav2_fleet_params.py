#!/usr/bin/env python3
"""Merge stock nav2_params.yaml with FleetGuard BT plugins + navigate_with_fleet.xml.

Usage:
  fleet_merge_nav2_fleet_params /path/to/out.yaml [/path/to/nav2_params.yaml]
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


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dest = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        base_yaml = Path(sys.argv[2])
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

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as fh:
        yaml.dump(data, fh, sort_keys=False, default_flow_style=False)

    print(f'Wrote {dest}')
    print(f'default_nav_to_pose_bt_xml={bt_xml}')


if __name__ == '__main__':
    main()
