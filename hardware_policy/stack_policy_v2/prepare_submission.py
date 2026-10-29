"""Create a separate six-cube commissioning submission folder. No network calls."""
import argparse,hashlib,json,shutil
from pathlib import Path
import yaml
from evidence import dump

HERE=Path(__file__).resolve().parent
CLIENT_FILES=['README.md','run.py','cell_client.py','mock_cell.py','pyproject.toml','uv.lock',
    'calibration/__init__.py','calibration/cameras.json','calibration/geometry.py','calibration/FRAMES.md',
    'submission/table_plan.png']


def prepare(client,project,output,check=False):
    client,project,output=Path(client).resolve(),Path(project).resolve(),Path(output).resolve()
    if output.exists() or output.is_relative_to(client) or output.is_relative_to(project):
        raise ValueError('Use a NEW separate sibling submission folder')
    expected=json.loads((HERE/'client_revision.json').read_text())
    for name,digest in expected.items():
        if hashlib.sha256((client/name).read_bytes()).hexdigest()!=digest:raise ValueError('Reviewed client changed: '+name)
    stack=json.loads((HERE/'stacking_revision.json').read_text())
    for name,digest in stack.items():
        if hashlib.sha256((project/name).read_bytes()).hexdigest()!=digest:raise ValueError('Reviewed stacking source changed: '+name)
    if check:
        print('Six-cube submission preparation compatible. No files changed or request sent.');return
    output.mkdir(parents=True,exist_ok=False)
    for name in CLIENT_FILES:
        target=output/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(client/name,target)
    shutil.copy2(client/'policy.py',output/'original_policy.py.backup')
    package=output/'stack_policy_v2';package.mkdir()
    for source in HERE.iterdir():
        if source.is_file():shutil.copy2(source,package/source.name)
    (output/'policy.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parent/"stack_policy_v2"))\nfrom hardware_policy import Policy\n')
    initial=json.loads((HERE/'mock_fixture_plan.json').read_text())
    positions=[[round(p['xy'][0]*1000,1),round(p['xy'][1]*1000,1),round(p['yaw_deg'],1)] for p in initial['picks']]
    task='Stack six 10 mm cubes yellow-yellow-blue-blue-red-red at base XY (280,100) mm; supervised commissioning and bounded pre-first-pick recovery.'
    submission=dict(team='TwinWorks (UWM/MSOE-Team-49)',
        contact='Shubhangi Salunkhe <salunkh3@uwm.edu>',policy='TwinWorks-SixCube-Recovery-v2-Commissioning',
        model_type='Hybrid',task_id='stack-six-Team-49',task=task,objects='same',layout='same',
        rollouts=3,custom_hardware='none')
    prompt=('Setup cube entries 1-2 yellow, 3-4 blue, 5-6 red, all 10 mm and loose on table. '
        'Stack bottom-to-top yellow, yellow, blue, blue, red, red at (280,100) mm. '
        'Commissioning first: current policy defaults to observe-and-plan with motion disabled. '
        'Operator must validate calibration, hooked-tip heights, orientation and path before motion. '
        'If approved: rollout 1 normal, rollout 2 +10 mm world-X first target shift with recovery disabled, '
        'rollout 3 same shift with recovery enabled. Move any cube only at the operator-controlled checkpoint, '
        'using CSI-approved stopping/access procedures. No automatic physical disturbance. '
        'An uncertain image or >2 mm position-estimate disagreement requests review; no automatic review-resume.')
    placement=dict(rollouts=[dict(objects={'cube':positions},prompt=prompt)])
    for name,value in [('submission.yaml',submission),('placement.yaml',placement)]:
        (output/'submission'/name).write_text(yaml.safe_dump(value,sort_keys=False))
    settings=dict(mode='observe_and_plan',recovery='enabled',recovery_by_rollout=['enabled','disabled','enabled'],
        client=str(client),project=str(project),cosmos='/workspace/cosmos-venv/bin/python',
        host=str(project/'.venv/bin/python'),model='/workspace/models/Cosmos3-Nano',
        output_root=str(output/'captures'),tcp_r_for_zero_yaw_deg=None,
        operator_checks={k:False for k in ['coordinate_frame_checked','image_localization_checked',
            'hook_contact_height_checked','orientation_mapping_checked','path_clearance_checked','start_pose_checked']})
    settings['operator_checks']['operator']=''
    dump(output/'session_config.json',settings)
    mock=dict(settings,mode='mock',mock_case='unchanged');dump(output/'mock_config.json',mock)
    dump(output/'preparation_record.json',dict(client_source_sha256=expected,stacking_source_sha256=stack,
        source_files_copied=CLIENT_FILES,credentials_copied=False,submission_sent=False,
        requested_slot='2026-10-30 12:00-12:30 America/Chicago',availability_confirmed=False,
        hardware_motion_enabled=False))
    print('Prepared:',output)
    print('Six-cube task, observe-and-plan default, no request sent or physical movement enabled.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('client','project','out'):ap.add_argument('--'+name,required=True,type=Path)
    ap.add_argument('--check',action='store_true');a=ap.parse_args()
    prepare(a.client,a.project,a.out,a.check)


if __name__=='__main__':main()
