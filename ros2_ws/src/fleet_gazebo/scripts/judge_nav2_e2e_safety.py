#!/usr/bin/env python3
"""Offline safety judge for the Nav2 fleet e2e scenario logs."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Iterable


ODOM_RE = re.compile(
    r"\[(?P<t>\d+(?:\.\d+)?)\].*Odom received for (?P<robot>robot_[a-z]): "
    r"x=(?P<x>-?\d+(?:\.\d+)?), y=(?P<y>-?\d+(?:\.\d+)?)"
)


def _goal_succeeded(log_dir: Path, robot: str) -> bool:
    path = log_dir / f"goal_{robot}.log"
    if not path.exists():
        return False
    text = path.read_text(errors="replace")
    return "TaskResult.SUCCEEDED" in text or "Goal succeeded" in text


def _parse_odom(log_dir: Path) -> dict[str, list[tuple[float, float, float]]]:
    samples: dict[str, list[tuple[float, float, float]]] = {"robot_a": [], "robot_b": []}
    path = log_dir / "mock_path.log"
    if not path.exists():
        return samples

    for line in path.read_text(errors="replace").splitlines():
        match = ODOM_RE.search(line)
        if not match:
            continue
        robot = match.group("robot")
        if robot in samples:
            samples[robot].append(
                (
                    float(match.group("t")),
                    float(match.group("x")),
                    float(match.group("y")),
                )
            )
    return samples


def _iter_pair_distances(
    samples: dict[str, list[tuple[float, float, float]]],
    max_skew_sec: float,
) -> Iterable[tuple[float, float]]:
    last: dict[str, tuple[float, float, float] | None] = {"robot_a": None, "robot_b": None}
    events: list[tuple[float, str, float, float]] = []
    for robot, rows in samples.items():
        events.extend((t, robot, x, y) for t, x, y in rows)
    events.sort()

    for t, robot, x, y in events:
        last[robot] = (t, x, y)
        a = last["robot_a"]
        b = last["robot_b"]
        if a is None or b is None:
            continue
        if abs(a[0] - b[0]) > max_skew_sec:
            continue
        dist = math.hypot(a[1] - b[1], a[2] - b[2])
        yield max(a[0], b[0]), dist


def _count_collision_events(distances: list[tuple[float, float]], threshold: float) -> int:
    events = 0
    in_event = False
    for _, dist in distances:
        if dist < threshold and not in_event:
            events += 1
            in_event = True
        elif dist >= threshold:
            in_event = False
    return events


def _deadlock_windows(
    samples: dict[str, list[tuple[float, float, float]]],
    window_sec: float,
    min_displacement: float,
) -> list[dict[str, float]]:
    rows_a = samples.get("robot_a", [])
    rows_b = samples.get("robot_b", [])
    if len(rows_a) < 2 or len(rows_b) < 2:
        return []

    start = max(rows_a[0][0], rows_b[0][0])
    end = min(rows_a[-1][0], rows_b[-1][0])
    windows: list[dict[str, float]] = []
    cursor = start
    while cursor + window_sec <= end:
        window_end = cursor + window_sec
        moves = {}
        for robot, rows in samples.items():
            in_window = [(t, x, y) for t, x, y in rows if cursor <= t <= window_end]
            if len(in_window) < 2:
                moves[robot] = float("inf")
                continue
            _, x0, y0 = in_window[0]
            _, x1, y1 = in_window[-1]
            moves[robot] = math.hypot(x1 - x0, y1 - y0)
        if moves["robot_a"] < min_displacement and moves["robot_b"] < min_displacement:
            windows.append(
                {
                    "start": round(cursor, 3),
                    "end": round(window_end, 3),
                    "robot_a_displacement": round(moves["robot_a"], 3),
                    "robot_b_displacement": round(moves["robot_b"], 3),
                }
            )
        cursor += max(1.0, window_sec / 4.0)
    return windows


def _status_states(log_dir: Path) -> dict[str, list[tuple[float, str]]]:
    states: dict[str, list[tuple[float, str]]] = {"robot_a": [], "robot_b": []}
    for robot in states:
        path = log_dir / f"status_{robot}.log"
        if not path.exists():
            continue
        for line in path.read_text(errors="replace").splitlines():
            try:
                stamp_text, payload = line.split(" ", 1)
                data = json.loads(payload)
            except Exception:
                continue
            state = data.get("state")
            if isinstance(state, str):
                states[robot].append((float(stamp_text), state))
    return states


def _unrecovered_emergency(states: dict[str, list[tuple[float, str]]]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for robot, rows in states.items():
        emergency_seen = any(state == "EMERGENCY" for _, state in rows)
        result[robot] = bool(emergency_seen and rows and rows[-1][1] == "EMERGENCY")
    return result


def _yield_counts(log_dir: Path) -> dict[str, int]:
    path = log_dir / "yield.log"
    counts = {"REQUEST_YIELD": 0, "ACK_YIELD": 0, "RESUME": 0, "EMERGENCY_STOP": 0}
    if not path.exists():
        return counts
    command_names = {
        "command=0": "REQUEST_YIELD",
        "command: 0": "REQUEST_YIELD",
        "command=1": "ACK_YIELD",
        "command: 1": "ACK_YIELD",
        "command=2": "RESUME",
        "command: 2": "RESUME",
        "command=3": "EMERGENCY_STOP",
        "command: 3": "EMERGENCY_STOP",
    }
    for line in path.read_text(errors="replace").splitlines():
        for needle, name in command_names.items():
            if needle in line:
                counts[name] += 1
                break
    return counts


def judge(log_dir: Path, args: argparse.Namespace) -> dict:
    samples = _parse_odom(log_dir)
    distances = list(_iter_pair_distances(samples, args.max_skew_sec))
    min_distance = min((dist for _, dist in distances), default=None)
    collisions = _count_collision_events(distances, args.collision_distance)
    deadlocks = _deadlock_windows(samples, args.deadlock_window_sec, args.deadlock_min_displacement)
    states = _status_states(log_dir)
    emergencies = _unrecovered_emergency(states)
    goals = {
        "robot_a": _goal_succeeded(log_dir, "robot_a"),
        "robot_b": _goal_succeeded(log_dir, "robot_b"),
    }
    yield_counts = _yield_counts(log_dir)

    deadlock_fail = bool(deadlocks) and not all(goals.values())
    unrecovered_emergency_fail = any(emergencies.values())
    passed = collisions == 0 and not deadlock_fail and not unrecovered_emergency_fail

    return {
        "passed": passed,
        "thresholds": {
            "collision_distance_m": args.collision_distance,
            "deadlock_window_sec": args.deadlock_window_sec,
            "deadlock_min_displacement_m": args.deadlock_min_displacement,
            "max_pair_sample_skew_sec": args.max_skew_sec,
        },
        "collision": {
            "passed": collisions == 0,
            "events": collisions,
            "min_distance_m": round(min_distance, 3) if min_distance is not None else None,
            "paired_samples": len(distances),
        },
        "deadlock": {
            "passed": not deadlock_fail,
            "events": len(deadlocks) if deadlock_fail else 0,
            "candidate_windows": deadlocks[:20],
        },
        "unrecovered_emergency": {
            "passed": not unrecovered_emergency_fail,
            "by_robot": emergencies,
        },
        "goals": goals,
        "yield_commands": yield_counts,
        "state_samples": {robot: len(rows) for robot, rows in states.items()},
        "odom_samples": {robot: len(rows) for robot, rows in samples.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", required=True, type=Path)
    parser.add_argument("--collision-distance", type=float, default=0.35)
    parser.add_argument("--deadlock-window-sec", type=float, default=20.0)
    parser.add_argument("--deadlock-min-displacement", type=float, default=0.10)
    parser.add_argument("--max-skew-sec", type=float, default=0.5)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = judge(args.log_dir, args)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
