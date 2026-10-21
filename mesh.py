"""Minimal mesh toolkit: primitives, transforms, merge, and OBJ/MTL/STL/GLB export.

Pure numpy; no third-party 3D libraries (Blender/trimesh are not installed here).
Conventions: right-handed, +Y up, +Z toward the viewer (character faces +Z).
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------- primitives

def _lat_lon_grid(lat: int, lon: int):
    """Unit sphere parameterisation, poles included (degenerate rows removed)."""
    verts = []
    for i in range(lat + 1):
        theta = math.pi * i / lat
        y = math.cos(theta)
        s = math.sin(theta)
        for j in range(lon):
            phi = 2.0 * math.pi * j / lon
            verts.append((s * math.cos(phi), y, s * math.sin(phi)))
    faces = []
    for i in range(lat):
        for j in range(lon):
            a = i * lon + j
            b = i * lon + (j + 1) % lon
            c = (i + 1) * lon + j
            d = (i + 1) * lon + (j + 1) % lon
            if i != 0:
                faces.append((a, c, b))
            if i != lat - 1:
                faces.append((b, c, d))
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


def sphere(radius: float = 1.0, lat: int = 20, lon: int = 28) -> tuple[np.ndarray, np.ndarray]:
    v, f = _lat_lon_grid(lat, lon)
    return v * radius, f


def ellipsoid(radii, lat: int = 20, lon: int = 28):
    v, f = _lat_lon_grid(lat, lon)
    return v * np.asarray(radii, dtype=np.float64), f


def cylinder(r0: float, r1: float, y0: float, y1: float, lon: int = 28, caps: bool = True):
    """Vertical frustum along +Y."""
    verts = []
    for j in range(lon):
        phi = 2.0 * math.pi * j / lon
        verts.append((r0 * math.cos(phi), y0, r0 * math.sin(phi)))
    for j in range(lon):
        phi = 2.0 * math.pi * j / lon
        verts.append((r1 * math.cos(phi), y1, r1 * math.sin(phi)))
    faces = []
    for j in range(lon):
        a = j
        b = (j + 1) % lon
        c = lon + j
        d = lon + (j + 1) % lon
        faces.append((a, c, b))
        faces.append((b, c, d))
    if caps:
        c0 = len(verts)
        verts.append((0.0, y0, 0.0))
        c1 = len(verts)
        verts.append((0.0, y1, 0.0))
        for j in range(lon):
            b = (j + 1) % lon
            faces.append((c0, b, j))
            faces.append((c1, lon + j, lon + b))
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


def torus(R: float, r: float, nu: int = 40, nv: int = 14, arc: float = 2.0 * math.pi):
    verts = []
    closed = abs(arc - 2.0 * math.pi) < 1e-9
    steps = nu if closed else nu + 1
    for i in range(steps):
        u = arc * i / nu
        cu, su = math.cos(u), math.sin(u)
        for j in range(nv):
            v = 2.0 * math.pi * j / nv
            cv, sv = math.cos(v), math.sin(v)
            verts.append(((R + r * cv) * cu, r * sv, (R + r * cv) * su))
    faces = []
    for i in range(nu):
        i2 = (i + 1) % steps if closed else i + 1
        for j in range(nv):
            j2 = (j + 1) % nv
            a = i * nv + j
            b = i * nv + j2
            c = i2 * nv + j
            d = i2 * nv + j2
            faces.append((a, c, b))
            faces.append((b, c, d))
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


def catmull_rom(points, samples_per_seg: int = 8):
    p = np.asarray(points, dtype=np.float64)
    if len(p) < 3:
        return p
    ext = np.vstack([p[0] + (p[0] - p[1]), p, p[-1] + (p[-1] - p[-2])])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(samples_per_seg):
            t = s / samples_per_seg
            t2, t3 = t * t, t * t * t
            out.append(
                0.5
                * (
                    (2 * p1)
                    + (-p0 + p2) * t
                    + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t3
                )
            )
    out.append(p[-1])
    return np.array(out)


def tube(path, radii, nu: int = 12, cap_start: bool = True, cap_end: bool = True):
    """Round tube swept along a polyline (parallel-transport frames)."""
    pts = np.asarray(path, dtype=np.float64)
    n = len(pts)
    radii = np.broadcast_to(np.asarray(radii, dtype=np.float64), (n,))
    tangents = np.zeros_like(pts)
    tangents[1:-1] = pts[2:] - pts[:-2]
    tangents[0] = pts[1] - pts[0]
    tangents[-1] = pts[-1] - pts[-2]
    norms = np.linalg.norm(tangents, axis=1, keepdims=True)
    tangents = tangents / np.maximum(norms, 1e-9)

    ref = np.array([0.0, 1.0, 0.0])
    if abs(tangents[0] @ ref) > 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    normal = ref - tangents[0] * (ref @ tangents[0])
    normal /= max(np.linalg.norm(normal), 1e-9)

    rings = []
    for i in range(n):
        if i > 0:
            normal = normal - tangents[i] * (normal @ tangents[i])
            ln = np.linalg.norm(normal)
            if ln < 1e-6:
                alt = np.array([1.0, 0.0, 0.0]) if abs(tangents[i][1]) > 0.9 else np.array([0.0, 1.0, 0.0])
                normal = alt - tangents[i] * (alt @ tangents[i])
                ln = np.linalg.norm(normal)
            normal /= max(ln, 1e-9)
        binormal = np.cross(tangents[i], normal)
        ring = []
        for j in range(nu):
            a = 2.0 * math.pi * j / nu
            ring.append(pts[i] + (normal * math.cos(a) + binormal * math.sin(a)) * radii[i])
        rings.append(ring)

    verts = [v for ring in rings for v in ring]
    faces = []
    for i in range(n - 1):
        for j in range(nu):
            j2 = (j + 1) % nu
            a = i * nu + j
            b = i * nu + j2
            c = (i + 1) * nu + j
            d = (i + 1) * nu + j2
            faces.append((a, c, b))
            faces.append((b, c, d))
    if cap_start:
        c0 = len(verts)
        verts.append(pts[0])
        for j in range(nu):
            faces.append((c0, (j + 1) % nu, j))
    if cap_end:
        c1 = len(verts)
        verts.append(pts[-1])
        base = (n - 1) * nu
        for j in range(nu):
            faces.append((c1, base + j, base + (j + 1) % nu))
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


def shell_patch(r_in: float, r_out: float, y0: float, y1: float, a0: float, a1: float,
                nu: int = 24, nv: int = 8):
    """Thick curved plate: a slice of an annulus revolved around +Y."""
    r_in = (r_in, r_in) if np.isscalar(r_in) else tuple(r_in)
    r_out = (r_out, r_out) if np.isscalar(r_out) else tuple(r_out)
    verts, faces = [], []
    layers = [(r_in, 0), (r_out, 1)]
    ring_index = {}
    for radii, tag in layers:
        for iy in range(nv + 1):
            t = iy / nv
            y = y0 + (y1 - y0) * t
            r = radii[0] + (radii[1] - radii[0]) * t
            for ia in range(nu + 1):
                a = a0 + (a1 - a0) * ia / nu
                ring_index[(tag, iy, ia)] = len(verts)
                verts.append((r * math.cos(a), y, r * math.sin(a)))
    for iy in range(nv):
        for ia in range(nu):
            for tag in (0, 1):
                a = ring_index[(tag, iy, ia)]
                b = ring_index[(tag, iy, ia + 1)]
                c = ring_index[(tag, iy + 1, ia)]
                d = ring_index[(tag, iy + 1, ia + 1)]
                faces.append((a, c, b))
                faces.append((b, c, d))
    for ia in range(nu):
        for (iy, sgn) in ((0, -1), (nv, 1)):
            a = ring_index[(0, iy, ia)]
            b = ring_index[(1, iy, ia)]
            c = ring_index[(0, iy, ia + 1)]
            d = ring_index[(1, iy, ia + 1)]
            faces.append((a, b, c))
            faces.append((c, b, d))
    for iy in range(nv):
        for (ia, sgn) in ((0, -1), (nu, 1)):
            a = ring_index[(0, iy, ia)]
            b = ring_index[(1, iy, ia)]
            c = ring_index[(0, iy + 1, ia)]
            d = ring_index[(1, iy + 1, ia)]
            faces.append((a, c, b))
            faces.append((b, c, d))
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


# ---------------------------------------------------------------- transforms

def translate(v, t):
    return v + np.asarray(t, dtype=np.float64)


def scale(v, s):
    return v * np.asarray(s, dtype=np.float64)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def orient(v, f, center=(0.0, 0.0, 0.0)):
    """Flip faces so normals point away from `center` (fixes winding)."""
    c = np.asarray(center, dtype=np.float64)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    d = (tri.mean(axis=1) - c)
    if float(np.sum(np.einsum("ij,ij->i", n, d))) < 0:
        f = f[:, ::-1].copy()
    return v, f


# ---------------------------------------------------------------- assembly

@dataclass
class Part:
    verts: np.ndarray
    faces: np.ndarray
    material: str


class Model:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []           # per-face material name
        self.materials = {}      # name -> (r, g, b)

    def add(self, verts, faces, material, color, transform=None, flip_center=None):
        v = np.asarray(verts, dtype=np.float64)
        f = np.asarray(faces, dtype=np.int64)
        if transform is not None:
            v = v @ np.asarray(transform).T
        if flip_center is not None:
            v, f = orient(v, f, flip_center)
        base = sum(len(x) for x in self.verts)
        self.verts.append(v)
        self.faces.append(f + base)
        self.mats.extend([material] * len(f))
        self.materials[material] = tuple(float(x) for x in color)
        return self

    def arrays(self):
        v = np.concatenate(self.verts) if self.verts else np.zeros((0, 3))
        f = np.concatenate(self.faces) if self.faces else np.zeros((0, 3), dtype=np.int64)
        return v, f

    # ------------------------------------------------------------ export

    def export_obj(self, path: str):
        v, f = self.arrays()
        base = path.rsplit(".", 1)[0]
        mtl = base + ".mtl"
        with open(mtl, "w", encoding="utf-8") as fh:
            fh.write("# shenshen pet model\n")
            for name, (r, g, b) in self.materials.items():
                fh.write(f"newmtl {name}\nKa 0 0 0\nKd {r:.4f} {g:.4f} {b:.4f}\nKs 0.05 0.05 0.05\nNs 20\nd 1\nillum 2\n\n")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"mtllib {mtl.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}\n")
            fh.write("o shenshen\n")
            for x, y, z in v:
                fh.write(f"v {x:.5f} {y:.5f} {z:.5f}\n")
            current = None
            for tri, mat in zip(f, self.mats):
                if mat != current:
                    fh.write(f"usemtl {mat}\n")
                    current = mat
                fh.write(f"f {tri[0] + 1} {tri[1] + 1} {tri[2] + 1}\n")
        return path

    def export_stl(self, path: str):
        v, f = self.arrays()
        tri = v[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.maximum(ln, 1e-12)
        with open(path, "wb") as fh:
            fh.write(b"shenshen 3d pet (binary stl)".ljust(80, b" "))
            fh.write(struct.pack("<I", len(f)))
            for i in range(len(f)):
                fh.write(struct.pack("<3f", *n[i]))
                fh.write(struct.pack("<9f", *tri[i].reshape(-1)))
                fh.write(struct.pack("<H", 0))
        return path

    def export_glb(self, path: str):
        v, f = self.arrays()
        # smooth-ish vertex normals per material island is overkill: use area-weighted
        tri = v[f]
        fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        vn = np.zeros_like(v)
        for k in range(3):
            np.add.at(vn, f[:, k], fn)
        ln = np.linalg.norm(vn, axis=1, keepdims=True)
        vn = vn / np.maximum(ln, 1e-12)

        names = list(self.materials.keys())
        by_mat = [[] for _ in names]
        index_of = {n: i for i, n in enumerate(names)}
        for tri_i, mat in enumerate(self.mats):
            by_mat[index_of[mat]].append(tri_i)

        mat_index = {n: i for i, n in enumerate(names)}
        primitives = []
        for name, tris in zip(names, by_mat):
            if not tris:
                continue
            tris = np.array(tris, dtype=np.int64)
            sub = f[tris]                     # (m,3) vertex ids
            uniq, remap = np.unique(sub.reshape(-1), return_inverse=True)
            primitives.append({
                "material": mat_index[name],
                "mode": 4,
                "indices": remap.astype(np.uint32).tobytes(),
                "count": int(sub.size),
                "verts": uniq.astype(np.uint32).tobytes(),
            })

        blob = bytearray()
        buffer_views = []
        accessors = []

        def push(data: bytes, target: int):
            while len(blob) % 4:
                blob.append(0)
            off = len(blob)
            blob.extend(data)
            buffer_views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
            return len(buffer_views) - 1

        pos_view = push(v.astype(np.float32).tobytes(), 34962)
        nrm_view = push(vn.astype(np.float32).tobytes(), 34962)
        accessors.append({"bufferView": pos_view, "componentType": 5126, "count": len(v), "type": "VEC3",
                          "min": [float(x) for x in v.min(axis=0)], "max": [float(x) for x in v.max(axis=0)]})
        accessors.append({"bufferView": nrm_view, "componentType": 5126, "count": len(vn), "type": "VEC3"})

        gl_prims = []
        for p in primitives:
            idx_view = push(p["indices"], 34963)
            accessors.append({"bufferView": idx_view, "componentType": 5125, "count": p["count"], "type": "SCALAR"})
            gl_prims.append({"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": len(accessors) - 1,
                             "material": p["material"], "mode": 4})

        glb = {
            "asset": {"version": "2.0", "generator": "dsh-shenshen-pet3d"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": "shenshen"}],
            "meshes": [{"name": "shenshen", "primitives": gl_prims}],
            "materials": [
                {"name": n, "pbrMetallicRoughness": {
                    "baseColorFactor": [*self.materials[n], 1.0],
                    "metallicFactor": 0.0, "roughnessFactor": 0.85}}
                for n in names
            ],
            "buffers": [{"byteLength": len(blob)}],
            "bufferViews": buffer_views,
            "accessors": accessors,
        }
        json_bytes = json.dumps(glb, separators=(",", ":")).encode("utf-8")
        while len(json_bytes) % 4:
            json_bytes += b" "
        while len(blob) % 4:
            blob.append(0)
        total = 12 + 8 + len(json_bytes) + 8 + len(blob)
        with open(path, "wb") as fh:
            fh.write(struct.pack("<III", 0x46546C67, 2, total))
            fh.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
            fh.write(json_bytes)
            fh.write(struct.pack("<II", len(blob), 0x004E4942))
            fh.write(bytes(blob))
        return path
