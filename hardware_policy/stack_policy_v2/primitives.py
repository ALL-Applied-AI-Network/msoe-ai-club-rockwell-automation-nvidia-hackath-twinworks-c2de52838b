"""Shared rehearsal TCP primitives; calibration defaults are not hardware approval."""

from dataclasses import dataclass
import math,time
import numpy as np

class ReviewRequired(ValueError):
    pass

def square_delta(a, b):
    return (float(a) - float(b) + 45.) % 90. - 45.

@dataclass(frozen=True)
class RehearsalConfig:
    # A missing/guessed mapping must never silently become hardware calibration.
    r_zero_deg: float = 0.  # ASSUMED for mock/replay only
    surface_base_m: float = -.0051
    tip_clearance_m: float = .0025
    cube_edge_m: float = .010
    travel_base_z_m: float = .150
    speed_mm_s: float = 20.
    angular_speed_deg_s: float = 15.
    dt_s: float = .1
    max_rows: int = 20
    endpoint_tolerance_mm: float = .8
    orientation_tolerance_deg: float = 1.
    arrival_timeout_s: float = 90.

def validate_tcp(row):
    row = np.asarray(row, float)
    if row.shape != (7,) or not np.isfinite(row).all():
        raise ReviewRequired("Invalid finite TCP target")
    lo = np.array([150., -450., -334.])
    hi = np.array([650., 450., 300.])
    if np.any(row[:3] < lo) or np.any(row[:3] > hi):
        raise ReviewRequired("TCP outside reviewed client bounding box")
    if np.linalg.norm(row[:2]) > 500 or np.max(np.abs(row[3:6])) > 360 or row[6] not in (0, 1):
        raise ReviewRequired("TCP outside conservative rehearsal limits")
    return row

class MotionPrimitives:
    def log(self, event, **data):
            self.events.append(dict(event=event, **data))

    def _pose(self, obs):
            pose = np.asarray(obs.get("tcp_pose"), float)
            joints = np.asarray(obs.get("joints"), float)
            if pose.shape != (6,) or joints.shape != (7,) or not np.isfinite(pose).all() or not np.isfinite(joints).all():
                raise ReviewRequired("Need measured TCP and joints; do not invent a starting pose")
            return validate_tcp(np.r_[pose, float(joints[6] >= .5)])

    def _row(self, xy, z_base, r, grip):
            return validate_tcp([xy[0]*1000, xy[1]*1000, z_base*1000-330, -180, 0, r, grip])

    def _r(self, yaw):
            # This zero-angle relationship is a rehearsal assumption until reviewed.
            return float((self.c.r_zero_deg + yaw + 180) % 360 - 180)

    def _move(self, current, target, phase, after):
            current, target = validate_tcp(current), validate_tcp(target)
            # Binary gripper changes are separate stationary primitives.
            if current[6] != target[6] and not np.allclose(current[:6], target[:6], atol=1e-9):
                raise ReviewRequired("Do not change gripper during a moving primitive")
            distance = np.linalg.norm(target[:3]-current[:3])
            angles = (target[3:6]-current[3:6]+180)%360-180
            duration = max(distance/self.c.speed_mm_s,
                           np.max(np.abs(angles))/self.c.angular_speed_deg_s, .2)
            n = max(2, math.ceil(duration/self.c.dt_s))
            self.pending = []
            for i in range(1, n+1):
                t = i/n
                row = np.r_[current[:3]+t*(target[:3]-current[:3]),
                            current[3:6]+t*angles, target[6]]
                self.pending.append(validate_tcp(row).tolist())
            self.target = np.asarray(self.pending[-1])
            self.after_arrival, self.phase = after, phase
            self.state = "sending"
            self.log("primitive_planned", phase=phase, rows=n, target=self.target.tolist())
