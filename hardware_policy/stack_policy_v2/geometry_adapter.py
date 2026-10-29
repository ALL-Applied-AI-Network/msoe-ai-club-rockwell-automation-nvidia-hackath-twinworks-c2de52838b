"""Convert the supplied fixed-table calibration to an undistorted planner view."""
import json
from pathlib import Path
import cv2
import numpy as np


def table_calibration(path):
    raw = json.loads(Path(path).read_text())["table"]
    w, h = raw["size"]
    t = np.asarray(raw["T_base_cam"], dtype=float)
    if (w, h) != (1920, 1080) or t.shape != (4, 4) or not np.isfinite(t).all():
        raise ValueError("Expected reviewed native 1920x1080 table calibration")
    if not np.allclose(t[:3, :3].T @ t[:3, :3], np.eye(3), atol=1e-6):
        raise ValueError("Invalid camera rotation")
    f = float(raw["fx"])
    k = float(raw["k1"])
    if not np.isfinite([f, k]).all() or f <= 0:
        raise ValueError("Invalid focal length or distortion")
    intrinsics = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]], float)
    distortion = np.array([k, 0, 0, 0, 0], float)
    # CameraModel uses row-vector USD (+x right, +y up, -z forward).
    # The supplied transform uses OpenCV (+x right, +y down, +z forward).
    usd = np.eye(4)
    usd[:3, :3] = np.diag([1., -1., -1.]) @ t[:3, :3].T
    usd[3, :3] = t[:3, 3]
    camera = dict(camera="table", resolution=[w, h], focal_length_mm=1.,
                  horizontal_aperture_mm=w / f, vertical_aperture_mm=h / f,
                  camera_to_world=usd.tolist(), table_top_z=-0.0051,
                  robot_base_xy=[0., 0.], coordinates="robot_base_metres",
                  image_processing="undistorted using supplied table k1; same intrinsic matrix")
    return intrinsics, distortion, camera


def prepare_bgr(image, calibration):
    intrinsics, distortion, camera = table_calibration(calibration)
    if image is None or image.dtype != np.uint8 or image.shape != (1080, 1920, 3):
        raise ValueError("Require native 1920x1080 uint8 colour image; do not upscale")
    return cv2.undistort(image, intrinsics, distortion, None, intrinsics), camera


def base_to_uf0(xyz):
    xyz = np.asarray(xyz, float)
    if xyz.shape != (3,) or not np.isfinite(xyz).all():
        raise ValueError("Expected finite XYZ in base metres")
    return (xyz * 1000 + [0., 0., -330.]).tolist()
