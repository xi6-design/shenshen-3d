"""Software rasterizer for the pet model (numpy only) + PNG writer."""
from __future__ import annotations

import math
import struct
import zlib

import numpy as np

BACKGROUND_TOP = np.array([0.93, 0.95, 0.98])
BACKGROUND_BOTTOM = np.array([0.80, 0.84, 0.92])
KEY_DIR = np.array([-0.35, 0.75, 0.55])
FILL_DIR = np.array([0.65, 0.15, 0.45])
RIM_DIR = np.array([0.0, 0.1, -1.0])


def _norm(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


def write_png(path: str, rgb: np.ndarray):
    rgb = np.clip(rgb, 0.0, 1.0)
    data = (rgb * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = data.shape
    raw = b"".join(b"\x00" + data[y].tobytes() for y in range(h))
    comp = zlib.compress(raw, 6)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        fh.write(chunk(b"IDAT", comp))
        fh.write(chunk(b"IEND", b""))
    return path


def camera_basis(az_deg: float, el_deg: float, target: np.ndarray):
    az, el = math.radians(az_deg), math.radians(el_deg)
    direction = np.array([math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el)])
    eye = target + direction * 1.0
    forward = _norm(target - eye)
    right = _norm(np.cross(forward, np.array([0.0, 1.0, 0.0])))
    up = np.cross(right, forward)
    return eye, right, up, forward


def render(model, az=0.0, el=8.0, dist=6.2, size=(900, 1200), ss=2, fov=26.0):
    verts, faces = model.arrays()
    if len(faces) == 0:
        raise RuntimeError("empty model")

    target = np.array([0.0, 1.15, 0.0])
    _, right, up, forward = camera_basis(az, el, target)
    eye = target - forward * dist

    rel = verts - eye
    xc = rel @ right
    yc = rel @ up
    zc = rel @ forward

    W, H = size[0] * ss, size[1] * ss
    fscale = (H * 0.5) / math.tan(math.radians(fov) * 0.5)
    with np.errstate(divide="ignore", invalid="ignore"):
        sx = W * 0.5 + fscale * xc / zc
        sy = H * 0.5 - fscale * yc / zc

    tri_v = np.stack([verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]], axis=1)
    normals = np.cross(tri_v[:, 1] - tri_v[:, 0], tri_v[:, 2] - tri_v[:, 0])
    nlen = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(nlen, 1e-12)

    view_dir = None
    center = tri_v.mean(axis=1)
    to_eye = eye - center
    to_eye = to_eye / np.maximum(np.linalg.norm(to_eye, axis=1, keepdims=True), 1e-12)
    faces_toward = np.einsum("ij,ij->i", normals, to_eye) >= 0.0
    normals = np.where(faces_toward[:, None], normals, -normals)

    key = np.clip(normals @ _norm(KEY_DIR), 0.0, 1.0)
    fill = np.clip(normals @ _norm(FILL_DIR), 0.0, 1.0)
    rim = np.clip(1.0 - np.abs(np.einsum("ij,ij->i", normals, to_eye)), 0.0, 1.0) ** 2

    shade = 0.40 + 0.68 * key + 0.20 * fill + 0.14 * rim
    shade = np.clip(shade, 0.0, 1.25)

    colors = np.array([model.materials[m] for m in model.mats], dtype=np.float64)
    tri_rgb = np.clip(colors * shade[:, None], 0.0, 1.0)

    ys, xs = np.mgrid[0:H, 0:W]
    t = ys / max(H - 1, 1)
    img = BACKGROUND_TOP[None, None, :] * (1 - t[..., None]) + BACKGROUND_BOTTOM[None, None, :] * t[..., None]
    img = np.repeat(img, 1, axis=0)

    zbuf = np.full((H, W), np.inf)

    s0, s1, s2 = sx[faces[:, 0]], sx[faces[:, 1]], sx[faces[:, 2]]
    y0, y1, y2 = sy[faces[:, 0]], sy[faces[:, 1]], sy[faces[:, 2]]
    z0, z1, z2 = zc[faces[:, 0]], zc[faces[:, 1]], zc[faces[:, 2]]

    order = np.argsort(-(z0 + z1 + z2))
    for i in order:
        if z0[i] <= 0.05 or z1[i] <= 0.05 or z2[i] <= 0.05:
            continue
        minx = int(max(0, math.floor(min(s0[i], s1[i], s2[i]))))
        maxx = int(min(W, math.ceil(max(s0[i], s1[i], s2[i])) + 1))
        miny = int(max(0, math.floor(min(y0[i], y1[i], y2[i]))))
        maxy = int(min(H, math.ceil(max(y0[i], y1[i], y2[i])) + 1))
        if maxx <= minx or maxy <= miny:
            continue
        px = np.arange(minx, maxx, dtype=np.float64) + 0.5
        py = np.arange(miny, maxy, dtype=np.float64) + 0.5
        gx, gy = np.meshgrid(px, py)
        d = (y1[i] - y2[i]) * (s0[i] - s2[i]) + (s2[i] - s1[i]) * (y0[i] - y2[i])
        if abs(d) < 1e-9:
            continue
        w0 = ((y1[i] - y2[i]) * (gx - s2[i]) + (s2[i] - s1[i]) * (gy - y2[i])) / d
        w1 = ((y2[i] - y0[i]) * (gx - s2[i]) + (s0[i] - s2[i]) * (gy - y2[i])) / d
        w2 = 1.0 - w0 - w1
        mask = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not mask.any():
            continue
        z = w0 * z0[i] + w1 * z1[i] + w2 * z2[i]
        sub_z = zbuf[miny:maxy, minx:maxx]
        keep = mask & (z < sub_z)
        if not keep.any():
            continue
        sub_z[keep] = z[keep]
        sub = img[miny:maxy, minx:maxx]
        sub[keep] = tri_rgb[i]

    if ss > 1:
        img = img.reshape(size[1], ss, size[0], ss, 3).mean(axis=(1, 3))
    return img


def contact_sheet(images, path):
    h, w, _ = images[0].shape
    cols = 2
    rows = (len(images) + cols - 1) // cols
    sheet = np.ones((rows * h, cols * w, 3))
    for k, im in enumerate(images):
        r, c = divmod(k, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = im
    return write_png(path, sheet)
