# TwinWorks stacking and recovery on Brev

## Included code

- fanuc_er4ia_sim: six-cube stacking, assets and scenarios.
- fanuc_er4ia_sim/stack_recovery_v1: recovery before the first pickup.
- hardware_policy/stack_policy_v2: hardware policy and human-review logic.

Stack order: yellow, yellow, blue, blue, red, red.
The cubes are 10 mm.

## What has been tested

The copied code passed 33 stacking tests, 34 recovery tests and
27 hardware-policy tests on DGX Spark.

DGX simulation demonstrated a successful 10 mm shifted recovery trial
and a failed matched recovery-disabled trial. This is one comparison,
not a reliability estimate.

Brev execution has not yet been validated.

## Prepare Brev

Read fanuc_er4ia_sim/SETUP.md and docs/MODEL_NOTES.md first.

Prepare separate Python environments for host planning/tests,
Isaac Sim, and Cosmos inference. Obtain Cosmos3-Nano weights separately.

Use an Isaac Sim build appropriate for the Brev machine architecture.
The tested DGX installation reported Isaac Sim 6.0.1 on ARM.
Do not copy DGX virtual environments or ARM library paths to Brev.

From fanuc_er4ia_sim, create the host environment:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

Configure actual installation paths:

    read -r -p "Isaac directory containing python.sh: " ISAAC
    read -r -p "Cosmos environment Python executable: " COSMOS
    read -r -p "Cosmos3-Nano model directory: " COSMOS3_NANO_PATH
    export ISAAC COSMOS COSMOS3_NANO_PATH
    unset TWINWORKS_TASK TWINWORKS_SCENARIO

Complete the dependency checks in SETUP.md before launching.
Do not change source hashes or acceptance thresholds to bypass errors.

## Host tests

From fanuc_er4ia_sim:

    .venv/bin/python -m unittest test_sort_planning test_cube_perception test_cube_pose test_runtime_config
    .venv/bin/python stack_recovery_v1/run_stack_pilot.py --project "$PWD" --self-test

## Simulation reproduction

Use runs/baseline_03_promptfix as the source.
First run a zero-shift control, then matched 10 mm world-X trials
with recovery enabled and disabled.

The exact runner options and video commands are documented in:
fanuc_er4ia_sim/stack_recovery_v1/README.md

Replace its DGX installation paths with your actual Brev paths.
Always launch the runner using HOST Python, not Isaac Python.
Use a new output directory for every attempt.
Coordinate GPU usage before starting Isaac.

## Human review and limitations

Uncertain observations or rejected updates create a local
human_review_request.json and stop before grasping.

This does not send a notification or provide an automatic resume UI.
Inspect the saved evidence rather than weakening the checks.

Recovery allows one bounded update before the first pickup.
It does not implement fallen-stack recovery, later slip recovery
or general collision avoidance.

Ground truth is for simulation setup and evaluation, not grasp correction.
Keep startup failures separate from task failures.
Keep every attempt, including unsuccessful and review-stop outcomes.

## Hardware boundary

The hardware policy requires the reviewed organizer client and
CSI-supervised commissioning. Private credentials are not included.
See hardware_policy/stack_policy_v2/README.md.

Mock/replay completion is not proof of physical grasp success.
Do not connect to physical equipment without CSI approval.
