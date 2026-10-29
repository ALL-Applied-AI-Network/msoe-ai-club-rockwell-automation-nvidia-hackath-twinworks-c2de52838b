"""Save one observation per rollout and return only the observed joints."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


class ObservationPolicy:
    CAMERAS = ["table", "side", "wrist"]
    IMAGE_SIZE = (1920, 1080)
    IMAGE_FORMAT = "png"
    ACTION = "joints"
    PREFETCH = False
    DEPTH = []

    def __init__(self, output, calibration, *, input_kind):
        if input_kind not in ("mock", "real"):
            raise ValueError("Input provenance must be explicit")
        self.output, self.calibration = Path(output), Path(calibration)
        self.input_kind = input_kind
        self.output.mkdir(exist_ok=False, parents=True)
        self.rollout = 0
        self.saved = False

    def reset(self):
        self.rollout += 1
        self.saved = False

    def act(self, obs):
        joints = np.asarray(obs["joints"], float)
        if joints.shape != (7,) or not np.isfinite(joints).all():
            raise ValueError("Cannot hold without valid observed joints and gripper")
        if not self.saved:
            folder = self.output / f"observation_{self.rollout:03d}"
            folder.mkdir(exist_ok=False)
            images = {}
            for camera in self.CAMERAS:
                rgb = np.asarray(obs["images"][camera])
                if rgb.shape != (1080, 1920, 3) or rgb.dtype != np.uint8:
                    raise ValueError(f"Unexpected {camera} image shape or type")
                path = folder / f"raw_{camera}.png"
                if not cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)):
                    raise OSError(f"Could not save {camera}")
                images[camera] = dict(file=path.name, sha256=sha(path), resolution=[1920, 1080])
            calibration_copy = folder / "cameras.json"
            calibration_copy.write_bytes(self.calibration.read_bytes())
            trial = obs.get("trial") or {}
            dump(folder / "observation.json", dict(
                input_kind=self.input_kind, physical_execution_evaluated=False,
                policy_behavior="return observed joints; no grasp targets", images=images,
                calibration_sha256=sha(calibration_copy),
                trial={k: trial[k] for k in ("trial_id", "index", "instruction") if k in trial},
                t=obs.get("t"), joints=joints.tolist(),
                tcp_pose=None if obs.get("tcp_pose") is None else np.asarray(obs["tcp_pose"]).tolist()))
            self.saved = True
            print(f"Saved {self.input_kind} observation: {folder}", flush=True)
        return joints.copy()
