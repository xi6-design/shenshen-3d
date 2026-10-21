"""Build the 3D model of the DSH desktop pet 'shenshen' (blue-haired maid whale girl).

Proportions follow the sprite sheet: chibi, head+hair is roughly half the height,
long wavy blue hair, white lace headdress, navy maid dress with a white apron.
Run:  python build.py   -> writes shenshen.{obj,mtl,stl,glb}
"""
from __future__ import annotations

import math
import os

import numpy as np

import mesh
from mesh import Model, catmull_rom, cylinder, ellipsoid, shell_patch, sphere, torus, tube

C = {
    "hair": (0.245, 0.375, 0.615),
    "hair_light": (0.450, 0.635, 0.825),
    "hair_dark": (0.165, 0.255, 0.440),
    "skin": (0.990, 0.878, 0.822),
    "skin_shade": (0.940, 0.795, 0.745),
    "lace": (0.945, 0.960, 0.985),
    "lace_shade": (0.835, 0.875, 0.935),
    "dress": (0.105, 0.150, 0.265),
    "dress_light": (0.165, 0.225, 0.375),
    "ink": (0.050, 0.060, 0.100),
    "eye_white": (0.975, 0.985, 1.000),
    "iris": (0.330, 0.565, 0.805),
    "iris_deep": (0.135, 0.275, 0.495),
    "teal": (0.275, 0.605, 0.715),
    "teal_dark": (0.170, 0.415, 0.530),
    "blush": (0.960, 0.715, 0.715),
}

HEAD_C = np.array([0.0, 1.630, 0.0])
HEAD_R = np.array([0.492, 0.512, 0.466])


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------ head

def add_head(model):
    v, f = ellipsoid(HEAD_R, 26, 36)
    model.add(mesh.translate(v, HEAD_C), f, "skin", C["skin"], flip_center=tuple(HEAD_C))


def add_hair_cap(model):
    """Hair shell with a soft face dish, so the head shows through the opening."""
    verts, faces = sphere(1.0, 44, 60)
    d = verts.copy()
    front = d[:, 2]
    ex = d[:, 0] / 0.556
    ey = (d[:, 1] + 0.030) / 0.640
    radial = np.sqrt(ex * ex + ey * ey)
    gate = smoothstep(0.02, 0.50, front) * (1.0 - smoothstep(0.52, 0.98, radial))
    radius = 0.615 * (1.0 - 0.47 * gate)
    v = d * radius[:, None]
    v = v * np.array([1.020, 1.005, 1.010])
    v = v + HEAD_C
    model.add(v, faces, "hair", C["hair"], flip_center=tuple(HEAD_C))


def add_hair_volume(model):
    v, f = ellipsoid((0.560, 0.585, 0.520), 26, 36)
    model.add(mesh.translate(v, (0.0, 1.640, -0.075)), f, "hair", C["hair"], flip_center=(0.0, 1.640, -0.075))
    v, f = ellipsoid((0.520, 0.470, 0.440), 26, 36)
    model.add(mesh.translate(v, (0.0, 1.220, -0.115)), f, "hair", C["hair"], flip_center=(0.0, 1.220, -0.115))
    v, f = ellipsoid((0.430, 0.265, 0.335), 24, 34)
    model.add(mesh.translate(v, (0.0, 0.950, -0.150)), f, "hair", C["hair"], flip_center=(0.0, 0.950, -0.150))


def add_sidelocks(model):
    left = [(0.470, 1.860, 0.060), (0.560, 1.560, 0.070), (0.530, 1.230, 0.040),
            (0.555, 0.930, 0.010), (0.500, 0.780, -0.020), (0.430, 0.650, -0.060)]
    for sign in (1, -1):
        pts = [(sign * x, y, z) for (x, y, z) in left]
        path = catmull_rom(pts, 8)
        radii = np.linspace(0.138, 0.062, len(path))
        v, f = tube(path, radii, 14)
        model.add(v, f, "hair", C["hair"], flip_center=(sign * 0.5, 1.2, 0.0))
        tip = path[-16:]
        v, f = tube(tip, np.linspace(0.080, 0.040, len(tip)), 12)
        model.add(v, f, "hair_light", C["hair_light"], flip_center=(sign * 0.45, 0.65, 0.0))


def add_fringe(model):
    # fringe over the forehead, hanging from the hairline into the face opening
    specs = [
        ([-0.34, 1.94, 0.42], [-0.36, 1.80, 0.50], [-0.30, 1.66, 0.47], 0.062),
        ([-0.17, 1.99, 0.40], [-0.19, 1.84, 0.52], [-0.15, 1.70, 0.49], 0.064),
        ([0.00, 2.02, 0.38], [0.02, 1.86, 0.54], [0.00, 1.72, 0.50], 0.066),
        ([0.16, 1.99, 0.40], [0.18, 1.84, 0.52], [0.15, 1.70, 0.49], 0.064),
        ([0.32, 1.94, 0.42], [0.34, 1.80, 0.50], [0.29, 1.66, 0.47], 0.060),
    ]
    for a, b, c, r in specs:
        path = catmull_rom([a, b, c], 8)
        radii = np.linspace(r, r * 0.34, len(path))
        v, f = tube(path, radii, 16)
        model.add(v, f, "hair", C["hair"], flip_center=(0.0, 1.85, 0.25))


def add_ahoge(model):
    pts = [(0.00, 2.08, -0.03), (0.07, 2.22, 0.02), (0.15, 2.26, 0.12), (0.12, 2.18, 0.20)]
    path = catmull_rom(pts, 9)
    v, f = tube(path, np.linspace(0.026, 0.008, len(path)), 10)
    model.add(v, f, "hair", C["hair_dark"], flip_center=(0.08, 2.2, 0.08))


def add_headdress(model):
    """White lace bonnet edge: an arc over the crown, tilted back, with scalloped lace."""
    cy, cz = HEAD_C[1], HEAD_C[2]
    R = 0.545
    tilt = mesh.rot_x(math.radians(-42))
    origin = np.array([0.0, cy + 0.045, cz + 0.030])

    def arc_points(radius, span_deg, count):
        pts = []
        for k in range(count):
            a = math.radians(-span_deg / 2 + span_deg * k / (count - 1))
            pts.append((radius * math.sin(a), radius * math.cos(a), 0.0))
        return np.array(pts) @ tilt.T + origin

    # band
    path = arc_points(R, 158, 44)
    v, f = tube(path, 0.052, 12)
    model.add(v, f, "lace", C["lace"], flip_center=tuple(origin))
    # scalloped lace along the band
    for k in range(1, 16):
        a = math.radians(-74 + 148 * k / 16.0)
        p = (np.array([R * 1.03 * math.sin(a), R * 1.03 * math.cos(a), 0.0]) @ tilt.T) + origin
        v, f = ellipsoid((0.060, 0.060, 0.058), 12, 16)
        v = v @ tilt.T
        model.add(mesh.translate(v, p), f, "lace", C["lace"], flip_center=tuple(p))
    # frilled veil hanging down the back of the head (world space, behind the crown)
    for k in range(-3, 4):
        p = (0.105 * k, cy - 0.075 - 0.012 * abs(k), cz - 0.345)
        v, f = ellipsoid((0.090, 0.100, 0.058), 12, 16)
        model.add(mesh.translate(v, p), f, "lace", C["lace_shade"], flip_center=p)


def add_face(model):
    for s in (-1, 1):
        ex = 0.172 * s
        # sclera
        v, f = ellipsoid((0.122, 0.150, 0.050), 20, 26)
        model.add(mesh.translate(v, (ex, 1.588, 0.398)), f, "eye_white", C["eye_white"], flip_center=(ex, 1.588, 0.398))
        # iris
        v, f = ellipsoid((0.099, 0.124, 0.046), 20, 26)
        model.add(mesh.translate(v, (ex, 1.575, 0.437)), f, "iris", C["iris"], flip_center=(ex, 1.575, 0.437))
        # deep pupil band
        v, f = ellipsoid((0.060, 0.074, 0.040), 16, 20)
        model.add(mesh.translate(v, (ex, 1.556, 0.462)), f, "iris_deep", C["iris_deep"], flip_center=(ex, 1.556, 0.462))
        # highlights
        v, f = sphere(0.042, 12, 16)
        model.add(mesh.translate(v, (ex - 0.032 * s, 1.622, 0.470)), f, "eye_white", C["eye_white"], flip_center=(ex, 1.62, 0.47))
        v, f = sphere(0.020, 10, 12)
        model.add(mesh.translate(v, (ex + 0.040 * s, 1.540, 0.474)), f, "eye_white", C["eye_white"], flip_center=(ex, 1.54, 0.47))
        # upper lash
        v, f = ellipsoid((0.128, 0.030, 0.044), 16, 22)
        model.add(mesh.translate(v, (ex, 1.706, 0.404)), f, "ink", C["ink"], flip_center=(ex, 1.706, 0.404))
        # brow
        v, f = ellipsoid((0.090, 0.017, 0.024), 12, 16)
        model.add(mesh.translate(v, (ex, 1.790, 0.386)), f, "hair_dark", C["hair_dark"], flip_center=(ex, 1.79, 0.386))

    v, f = ellipsoid((0.038, 0.015, 0.012), 12, 16)
    model.add(mesh.translate(v, (0.0, 1.398, 0.444)), f, "ink", C["ink"], flip_center=(0.0, 1.398, 0.444))


def add_bow(model):
    base = np.array([-0.455, 1.845, 0.255])
    for s in (-1, 1):
        v, f = ellipsoid((0.100, 0.068, 0.042), 12, 16)
        v = v @ mesh.rot_z(math.radians(26 * s)).T
        model.add(mesh.translate(v, base + np.array([0.082 * s, 0.0, 0.012])), f, "teal", C["teal"], flip_center=tuple(base))
    v, f = sphere(0.040, 12, 16)
    model.add(mesh.translate(v, base), f, "teal_dark", C["teal_dark"], flip_center=tuple(base))


# ------------------------------------------------------------------ body

def add_body(model):
    v, f = cylinder(0.090, 0.085, 1.100, 1.210, 18)
    model.add(v, f, "skin", C["skin_shade"], flip_center=(0.0, 1.15, 0.0))

    # dress body (cone) + rounded bottom so the hem reads as a bell, not a hoop
    v, f = cylinder(0.400, 0.205, 0.385, 1.120, 40)
    model.add(v, f, "dress", C["dress"], flip_center=(0.0, 0.78, 0.0))
    v, f = ellipsoid((0.398, 0.086, 0.398), 26, 36)
    model.add(mesh.translate(v, (0.0, 0.386, 0.0)), f, "dress", C["dress"], flip_center=(0.0, 0.386, 0.0))
    # hem frill
    v, f = torus(0.398, 0.038, 46, 12)
    model.add(mesh.translate(v, (0.0, 0.380, 0.0)), f, "lace", C["lace"], flip_center=(0.0, 0.380, 0.0))
    # collar
    v, f = torus(0.145, 0.028, 30, 10)
    model.add(mesh.translate(v, (0.0, 1.128, 0.0)), f, "lace", C["lace"], flip_center=(0.0, 1.128, 0.0))
    # apron panel
    v, f = shell_patch((0.399, 0.258), (0.417, 0.276), 0.400, 0.930, math.radians(68), math.radians(112), 20, 10)
    model.add(v, f, "lace", C["lace"], flip_center=(0.0, 0.75, 0.0))
    # waist band
    v, f = torus(0.262, 0.024, 34, 10)
    model.add(mesh.translate(v, (0.0, 0.930, 0.0)), f, "lace", C["lace"], flip_center=(0.0, 0.930, 0.0))
    # whale emblem
    v, f = ellipsoid((0.072, 0.046, 0.016), 16, 20)
    model.add(mesh.translate(v, (0.0, 0.620, 0.352)), f, "teal", C["teal"], flip_center=(0.0, 0.62, 0.352))
    v, f = ellipsoid((0.032, 0.021, 0.012), 10, 14)
    model.add(mesh.translate(v, (0.0, 0.560, 0.360)), f, "teal_dark", C["teal_dark"], flip_center=(0.0, 0.560, 0.360))

    for s in (-1, 1):
        # puffed sleeve
        v, f = ellipsoid((0.140, 0.145, 0.140), 16, 22)
        model.add(mesh.translate(v, (0.268 * s, 1.030, 0.010)), f, "dress", C["dress"], flip_center=(0.268 * s, 1.03, 0.01))
        # arm
        pts = [(0.282 * s, 1.010, 0.020), (0.322 * s, 0.840, 0.055), (0.336 * s, 0.700, 0.085)]
        path = catmull_rom(pts, 7)
        v, f = tube(path, np.linspace(0.080, 0.060, len(path)), 12)
        model.add(v, f, "dress", C["dress_light"], flip_center=(0.31 * s, 0.85, 0.04))
        v, f = sphere(0.070, 14, 18)
        model.add(mesh.translate(v, (0.340 * s, 0.680, 0.090)), f, "skin", C["skin"], flip_center=(0.34 * s, 0.65, 0.09))
        # leg
        v, f = cylinder(0.056, 0.050, 0.055, 0.315, 14)
        model.add(mesh.translate(v, (0.106 * s, 0.0, 0.020)), f, "skin", C["skin_shade"], flip_center=(0.115 * s, 0.3, 0.02))
        # shoe
        v, f = ellipsoid((0.078, 0.054, 0.112), 14, 18)
        model.add(mesh.translate(v, (0.106 * s, 0.052, 0.045)), f, "ink", C["ink"], flip_center=(0.115 * s, 0.10, 0.05))

    # whale tail peeking from behind the skirt
    pts = [(0.0, 0.60, -0.30), (0.0, 0.46, -0.46), (0.0, 0.42, -0.56)]
    path = catmull_rom(pts, 7)
    v, f = tube(path, np.linspace(0.042, 0.026, len(path)), 10)
    model.add(v, f, "hair", C["hair"], flip_center=(0.0, 0.5, -0.45))


def build() -> Model:
    m = Model()
    add_head(m)
    add_hair_cap(m)
    add_hair_volume(m)
    add_sidelocks(m)
    add_fringe(m)
    add_ahoge(m)
    add_headdress(m)
    add_face(m)
    add_bow(m)
    add_body(m)
    return m


def main(out_dir: str):
    model = build()
    v, f = model.arrays()
    print(f"verts={len(v)} faces={len(f)} materials={len(model.materials)}")
    print("bbox min", np.round(v.min(axis=0), 3), "max", np.round(v.max(axis=0), 3))
    os.makedirs(out_dir, exist_ok=True)
    obj = os.path.join(out_dir, "shenshen.obj")
    model.export_obj(obj)
    model.export_stl(os.path.join(out_dir, "shenshen.stl"))
    model.export_glb(os.path.join(out_dir, "shenshen.glb"))
    print("wrote", obj)


if __name__ == "__main__":
    main(os.path.dirname(os.path.abspath(__file__)))
