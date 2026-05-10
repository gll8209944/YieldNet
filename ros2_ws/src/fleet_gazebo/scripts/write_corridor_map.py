#!/usr/bin/env python3
"""Generate a simple occupancy map aligned with fleet_gazebo/worlds/corridor.world."""

from pathlib import Path
import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('output_dir')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    resolution = 0.05
    origin_x = -10.5
    origin_y = -2.0
    width = 420
    height = 80
    image_path = output_dir / 'corridor_map.pgm'
    yaml_path = output_dir / 'corridor_map.yaml'

    pixels = bytearray()
    for row in range(height):
        # PGM rows are top-to-bottom; convert to world y at cell center.
        y = origin_y + (height - 1 - row + 0.5) * resolution
        for col in range(width):
            x = origin_x + (col + 0.5) * resolution
            wall = abs(y) >= 1.40 or x <= -10.0 or x >= 10.0
            pixels.append(0 if wall else 254)

    with image_path.open('wb') as fh:
        fh.write(f'P5\n{width} {height}\n255\n'.encode('ascii'))
        fh.write(pixels)

    yaml_path.write_text(
        '\n'.join(
            [
                'image: corridor_map.pgm',
                f'resolution: {resolution:.6f}',
                f'origin: [{origin_x:.6f}, {origin_y:.6f}, 0.000000]',
                'negate: 0',
                'occupied_thresh: 0.65',
                'free_thresh: 0.196',
                '',
            ]
        ),
        encoding='utf-8',
    )
    print(f'Wrote {yaml_path}')


if __name__ == '__main__':
    main()
