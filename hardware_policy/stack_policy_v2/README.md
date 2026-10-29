# TwinWorks six-cube hardware policy v2 and commissioning request

Main task: stack six 10 mm cubes, bottom-to-top **yellow, yellow, blue, blue,
red, red**, at robot-base XY (0.28,0.10) m. Existing simulation, source code,
selected successful runs and earlier prototype packages remain unchanged.

## Readiness — do not confuse the checks

This package contains a six-cube TCP controller, camera/Cosmos/planner bridge,
the original pre-first-pick recovery gate, a disagreement diagnostic, scripted
tests, and an honest commissioning submission. It defaults to observe-and-plan:
the real client holds position after producing an initial image-derived plan.
Physical motion remains disabled until on-site commissioning settings are
documented. No physical grasp, placement or real-camera accuracy has been
validated by the package's host/mock checks. Operator scoring is required;
local reports never infer physical success from commanded TCP arrival.

The requested session is Friday **October 30, 2026, 12:00–12:30 Central**.
No slot availability, organizer approval or booking is assumed. The request
asks for supervised commissioning, then normal and matched disturbed trials
if ready and time permits. Three rollouts are requested, not ten: cold model
inference and physical commissioning may consume much of a half-hour slot.
Ask CSI about extra time. An approval request is not a hardware-success claim.

## 1. Install and test on Spark

Upload this ZIP into `/home/yt-twinworksb921/workspace/fanuc_hardware_client/`.
In Spark SSH:

```bash
cd /workspace/fanuc_hardware_client
python3 -m zipfile -e twinworks_stack_policy_v2_source.zip .
.venv/bin/python -m unittest discover -s twinworks_stack_policy_v2 -p test_policy.py
```

The tested suite has 27 tests. Run a full scripted six-cube replay:

```bash
.venv/bin/python twinworks_stack_policy_v2/replay.py \
  --out /workspace/fanuc_hardware_client/runs/stack_policy_v2_replay_001
```

Unchanged and 10 mm shifted cases finish six placement COMMAND sequences.
Injected disagreement and uncertainty stop before grasping. Scripted positions
are mock fixtures, not AI estimates or measured physical outcomes. Do not
replay exported mock targets on the physical robot. Complete command-sequence
rehearsal does not test dynamics, collisions, slips or tower stability.

## 2. Demonstrate the EXISTING disagreement guard

```bash
/workspace/fanuc_er4ia_sim/.venv/bin/python \
  /workspace/fanuc_hardware_client/twinworks_stack_policy_v2/disagreement_check.py \
  --project /workspace/fanuc_er4ia_sim \
  --source runs/baseline_03_promptfix \
  --out runs/stack_disagreement_check_01
```

This imports the reviewed stacking recovery validator and original
`sort_scene.validate_plan`. It uses copies of the baseline VISION plan and
explicitly injected candidate/evidence values. Matching moved-target estimates
are accepted; an injected 8 mm disagreement is rejected with a local
human_review_request.json. No original file, threshold, simulator or model is
changed or launched. The 8 mm mismatch is NOT an observed Cosmos failure and
must not be presented as real-image or physical validation.

The existing update validator stops at position disagreement >2 mm or square
yaw disagreement >3 degrees, and permits only a 5–25 mm first-target update.
This hardware controller also compares the initial planner pose with its
same-image measured pose (2 mm / 3 degrees). Both estimates share calibrated
image geometry: this is a consistency guard, NOT two independent sensors or
proof of true position accuracy. Same-image/common-calibration errors can pass.

## 3. Prepare a separate submission folder

```bash
cd /workspace/fanuc_hardware_client
.venv/bin/python twinworks_stack_policy_v2/prepare_submission.py \
  --client /workspace/fanuc_hardware_client \
  --project /workspace/fanuc_er4ia_sim \
  --out /workspace/twinworks_stack_submission_01 --check
```

If compatible, repeat without `--check`. The output must be new. Copies only
reviewed SDK sources/calibration; no credentials or environments. Original
policy.py is preserved as a backup in the new folder. The new policy shim
imports this six-cube version. Source hashes catch unreviewed file changes;
inspect a mismatch rather than bypassing it.

The actual organizer entry point can then be tested safely:

```bash
cd /workspace/twinworks_stack_submission_01
/workspace/fanuc_hardware_client/.venv/bin/python run.py \
  --mock --trials 3 --trial-s 4 --checkpoint mock_config.json
```

Mock mode is refused without the `--mock` command-line flag, preventing
accidental use of scripted positions in a real client run. The mock has no
kinematics and initially returns TCP null; a synthetic starting TCP is injected
ONLY in this mock mode. Real mode refuses missing measured TCP. Short SDK mock
trials check only the motion prefix, while replay checks the entire sequence.

## 4. Review the approval request, then submit

```bash
/workspace/fanuc_hardware_client/.venv/bin/python \
  /workspace/twinworks_stack_submission_01/stack_policy_v2/preview_submission.py \
  --session /workspace/twinworks_stack_submission_01
```

Prepared details:

- Team: TwinWorks (UWM/MSOE-Team-49).
- Contact: Shubhangi Salunkhe <salunkh3@uwm.edu>.
- Policy: TwinWorks-SixCube-Recovery-v2-Commissioning; model type Hybrid.
- Task ID: stack-six-Team-49, using the provided full team identifier rather
  than inventing a one-letter assignment. CSI can request a different ID.
- Exactly six 10 mm cubes, no new gripper/bins; original six-cube colour order.
- One fixed layout, with generic cube-coordinate entries. The operator prompt
  identifies entries 1–2 yellow, 3–4 blue, 5–6 red. Approximate positions/yaws
  come from the successful baseline vision plan and are SETUP instructions,
  not coordinates supplied to the runtime perception backend.
- Prompt explicitly discloses observe-and-plan default and required physical
  commissioning. Physical disturbance is conditional on operator approval.

After reviewing the prepared files, submit using the organizer's client:

```bash
cd /workspace/twinworks_stack_submission_01
/workspace/fanuc_hardware_client/.venv/bin/python run.py --submit
```

This sends task/setup metadata plus the action/camera interface, NOT model
weights or our code. The actual policy stays on Spark. The server may reject
metadata or ask for setup changes: preserve its response and correct the
documented request; do not claim approval from local validation.

The command prints a request ID. Enter that ID in the website Calendar and
request Friday October 30, 12:00–12:30 Central if available. Wait for organizer
approval. Keep .request.json private: it holds the request secret. Do not upload
it here or to GitHub. Status command: the same interpreter and `run.py --status`.
Submitting/booking does not itself start robot motion. This packet does not
perform either network action automatically.

## Friday commissioning and physical execution

Do not change existing plant controls or cameras. Ask CSI whether additional
time is available: three full cold-inference six-cube trials may not fit after
commissioning. Record latency and every attempt; do not promise 3 successes.

1. Obtain actual calibrated native table images; confirm calibration is current.
   Phone photos, CAD textures, resized mock images are not calibration evidence.
2. In observe-and-plan mode, run the approved client with CSI supervision and
   inspect saved camera/pose overlays and model evidence. Hardware execution
   settings are still disabled. Initial six-cube inventory must be accepted.
3. With the operator, validate frames, fingertip hook height, yaw-to-FANUC R
   mapping, open/close timing, the high-plane start and all approach paths.
   R=0 in mock is an assumption, not a calibration result.
4. Only after those real checks, document the operator checks and actual
   `tcp_r_for_zero_yaw_deg` in session_config.json and select execute_stack.
   These booleans are records, NOT safety certification or safety interlocks.
   Missing fields prevent motion mode. No real execution command is provided
   until the operator approves the setup and procedure.
5. Each rollout first perceives all six cubes, then HOLDS at a local operator
   checkpoint. An approved controlled shift, if any, occurs only using CSI's
   approved stop/access procedure. The policy does not move the physical cube.
   Clear personnel/objects and use `confirm_start.py --help` for the explicit
   local start record after operator clearance. This is not a safety interlock.
6. Intended modes: rollout 1 recovery-enabled with no disturbance; rollout 2
   approved +10 mm first-target world-X shift with recovery disabled; rollout 3
   the same shift with recovery enabled. Modes are recorded/printed. Extra
   rollouts are refused unless the documented mode list is extended. A voided
   rollout may require adjusting the plan with the operator, not silently
   assuming trial numbering matches. No intervention is hidden.

The policy interpolates TCP targets, closes/opens only while stationary, and
waits for observed endpoint arrival, not merely an empty SDK queue. Default
targets use 20 mm/s and 15 deg/s increments. The cell may enforce additional
limits or spread targets across rows. The site's October 28 guidance says
z below -333 mm is raised to -333 mm; the reviewed grasp target is -332.6 mm,
but numerical compliance is NOT physical contact validation.

Source and wrist yaw must be aligned; placement aligns the cube to world yaw
zero at the common stack site. No simulator +0.9 m world offset enters hardware
commands. UF0 conversion is base metres ×1000 with z minus330 mm. The simulated
2.5 mm fingertip clearance and binary physical gripper still require verification.

## Scope and evidence limits

- Recovery matches the existing experiment: ONE bounded update before the
  FIRST pickup. It does not recover later slips, failed grasps, fallen towers,
  moving supporting cubes or obstructions. No general collision avoidance.
- The original Cosmos and geometry front end plus guarded planner are reused.
  This is hybrid perception, not independent VLM 6D pose estimation. Real
  camera/model inference has NOT been run locally while preparing this packet.
- Model process per image is simple but slow; actual SDK permits the arm to
  hold during inference. Timing must include inference, not just video length.
- Position-consistent -> retain plan; uncertain -> hold/review; moved -> fresh
  six-cube perception plus original validator and explanation. Disabled mode
  intentionally retains the original plan for the approved comparison.
- Real pickup/placement visual verification is NOT implemented. TCP arrival
  and gripper state do not prove a cube is held. Operator must monitor and stop
  the physical trial on failed pickup, unsafe contact or unstable stack. Local
  reports have null verified counts/task_complete, never invented successes.
- Human-review records are local and not automatically sent. A review stop has
  no automatic resume; the operator/client must end it and inspect evidence.
- Keep simulation results, synthetic fault injection, scripted mock checks and
  eventual real robot results as distinct evidence categories. Do not present
  injected 8 mm mismatch as natural AI failure or scripted completion as 6/6
  physical placements. Videos and official operator scoring establish the
  physical outcomes for the final submission.
