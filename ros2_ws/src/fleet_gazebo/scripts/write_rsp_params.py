#!/usr/bin/env python3
"""Write robot_state_publisher params YAML with robot_description and robot_namespace.

This avoids the inline -p robot_description:=$(cat ...) approach which causes
UnknownROSArgsError due to \\r characters in the URDF corrupting rcl argument parsing.

Usage:
    python3 write_rsp_params.py <log_dir> <robot_namespace>
"""
import os
import sys


def main() -> None:
    log_dir = sys.argv[1] if len(sys.argv) > 1 else '/tmp'
    robot = sys.argv[2] if len(sys.argv) > 2 else 'robot_a'
    urdf_path = os.path.join(log_dir, 'burger.urdf')
    yaml_path = os.path.join(log_dir, f'rsp_{robot}.yaml')

    with open(urdf_path, 'r', encoding='utf-8') as f:
        urdf = f.read()

    # Strip carriage returns that corrupt rcl argument parsing
    urdf = urdf.replace('\r', '')

    # Build YAML with proper newlines and robot_namespace
    yaml_lines = []
    yaml_lines.append('robot_state_publisher:\n')
    yaml_lines.append('  ros__parameters:\n')
    yaml_lines.append(f'    robot_namespace: {robot}\n')
    yaml_lines.append('    use_sim_time: true\n')
    yaml_lines.append('    robot_description: |\n')
    for line in urdf.split('\n'):
        yaml_lines.append(f'      {line}\n')

    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(''.join(yaml_lines))

    print(f'Wrote {yaml_path}')


if __name__ == '__main__':
    main()
