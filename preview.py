"""Render preview views of the pet model."""
from __future__ import annotations

import os
import sys
import time

import numpy as np

import build
import render

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    t0 = time.time()
    model = build.build()
    v, f = model.arrays()
    print(f"verts={len(v)} faces={len(f)} materials={len(model.materials)} build={time.time() - t0:.2f}s")
    print("bbox", np.round(v.min(axis=0), 3), np.round(v.max(axis=0), 3))

    views = [(0, 6), (34, 6), (90, 6), (180, 6)]
    imgs = []
    for az, el in views:
        t = time.time()
        img = render.render(model, az=az, el=el, dist=6.3, size=(640, 860), ss=2)
        print(f"view az={az} {time.time() - t:.2f}s")
        imgs.append(img)
    out = os.path.join(HERE, "preview.png")
    render.contact_sheet(imgs, out)
    print("wrote", out)


if __name__ == "__main__":
    main()
