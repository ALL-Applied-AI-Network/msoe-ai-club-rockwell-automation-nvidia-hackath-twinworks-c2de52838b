"""Six-cube perception/geometry worker. No simulator, network or motion commands."""
import argparse,json,runpy,subprocess,sys
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=Path);ap.add_argument('--run',required=True,type=Path)
    ap.add_argument('--host',required=True);ap.add_argument('--operation',choices=['initial','pregrasp'],required=True)
    ap.add_argument('--recovery',choices=['enabled','disabled'],default='enabled')
    a=ap.parse_args();project=a.project.resolve();folder=a.run.resolve()
    sys.path.append(str(project))
    import cv2
    from stack_policy import validate_stack
    from stack_recovery_guard import validate_update,validate_explanation
    camera=json.loads((folder/'camera.json').read_text())
    result=dict(decision='retain',recovery_applied=False)
    observation=None;old=None
    if a.operation=='pregrasp':
        from check_pick_position import check_target
        old=json.loads((folder/'initial_sort_plan.json').read_text())
        observation=check_target(cv2.imread(str(folder/'world_camera.png')),camera,old['picks'][0],{})
        (folder/'position_check.json').write_text(json.dumps(observation,indent=2)+'\n')
        if a.recovery=='disabled' or observation['status']=='position_consistent':
            result['plan']=old
            (folder/'worker_result.json').write_text(json.dumps(result,indent=2)+'\n');return
        if observation['status']!='target_moved':
            raise ValueError('Current target image is uncertain; review before grasp')
    # Model sees only the current corrected image and calibration. No truth/state.
    sys.argv=[str(project/'perceive.py'),'--run',str(folder),'--stack-cubes']
    values=runpy.run_path(str(project/'perceive.py'),run_name='__main__')
    with (folder/'planning.log').open('x') as log:
        subprocess.run([a.host,'-u',str(Path(__file__).with_name('stack_planner.py')),
            '--project',str(project),'--run',str(folder)],cwd=project,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    plan=json.loads((folder/'sort_plan.json').read_text())
    validate_stack(plan)
    if old is not None:
        result['update']=validate_update(old,plan,observation)
        # Whole current table image: explanations cannot assert an unobserved cause.
        prompt=('Explain the pre-grasp problem supported by this current image and measurements. '
            'Return JSON with observed_change=target_position_changed, cause=unknown, grasp_attempted=false, '
            'recommended_action=replan or request_human, and explanation (one short evidence-based sentence). '
            'Use request_human if ambiguous; do not invent a cause. Measurements: '+json.dumps(observation))
        (folder/'explanation_prompt.txt').write_text(prompt)
        raw=values['ask'](values['model'],values['processor'],folder/'world_camera.png',prompt,500)
        (folder/'ai_explanation_raw.txt').write_text(raw)
        explanation=values['parse_json'](raw)
        if not isinstance(explanation,dict):raise ValueError('AI explanation is not JSON')
        validate_explanation(explanation)
        (folder/'ai_explanation.json').write_text(json.dumps(explanation,indent=2)+'\n')
        result.update(decision='replan',recovery_applied=True)
    result['plan']=plan
    (folder/'worker_result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
