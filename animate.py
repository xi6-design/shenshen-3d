"""Render a turntable frame sequence + a hero still of the pet model."""
from __future__ import annotations

import os
import time

import build
import render

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")


def main():
    model = build.build()
    os.makedirs(FRAMES, exist_ok=True)
    n = 24
    t0 = time.time()
    for i in range(n):
        img = render.render(model, az=360.0 * i / n, el=6.0, dist=6.3, size=(400, 540), ss=2)
        render.write_png(os.path.join(FRAMES, f"f_{i:03d}.png"), img)
        print(f"frame {i + 1}/{n} {time.time() - t0:.1f}s", flush=True)
    hero = render.render(model, az=18.0, el=5.0, dist=6.2, size=(760, 1040), ss=2)
    render.write_png(os.path.join(HERE, "hero.png"), hero)
    print("done", time.time() - t0)


if __name__ == "__main__":
    main()
