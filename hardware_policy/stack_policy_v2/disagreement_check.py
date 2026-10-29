"""Exercise the existing stacking guard with explicit synthetic fault injection."""
import argparse,copy,hashlib,json,os
from pathlib import Path
import sys


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=Path)
    ap.add_argument('--source',default='runs/baseline_03_promptfix',type=Path)
    ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();project=a.project.resolve();source=(project/a.source).resolve();out=(project/a.out).resolve()
    if out.exists() or out.is_relative_to(source):raise ValueError('Use a new separate output folder')
    expected=json.loads(Path(__file__).with_name('stacking_revision.json').read_text())
    for name,digest in expected.items():
        if hashlib.sha256((project/name).read_bytes()).hexdigest()!=digest:raise ValueError('Stacking source changed: '+name)
    for key in ('TWINWORKS_TASK','TWINWORKS_SCENARIO'):os.environ.pop(key,None)
    sys.path.append(str(project))
    from stack_recovery_guard import validate_update,request_human,HumanReviewRequired
    original=json.loads((source/'sort_plan.json').read_text())
    candidate=copy.deepcopy(original)
    p=candidate['picks'][0];old=original['picks'][0]
    p['xy']=[old['xy'][0]+.010,old['xy'][1]]
    evidence=dict(status='target_moved',candidate_count=1,measured_xy_m=list(p['xy']),image_fit_yaw_deg=p['yaw_deg'])
    out.mkdir(parents=True,exist_ok=False)
    cases=[]
    for name,offset in [('estimates_agree',0.),('estimates_disagree_8mm',.008)]:
        folder=out/name;folder.mkdir()
        proposed=copy.deepcopy(candidate);proposed['picks'][0]['xy'][0]+=offset
        for filename,data in [('original_sort_plan.json',original),('candidate_sort_plan.json',proposed),('position_check.json',evidence)]:
            (folder/filename).write_text(json.dumps(data,indent=2)+'\n')
        result=dict(case=name,test_kind='offline_synthetic_fault_injection',
            injected_position_disagreement_mm=offset*1000,model_run=False,simulator_run=False,
            robot_commands_sent=False,grasp_attempted=False,existing_thresholds_changed=False)
        try:
            result['update']=validate_update(original,proposed,evidence)
            result['outcome']='candidate_accepted'
        except ValueError as error:
            try:request_human(folder,error)
            except HumanReviewRequired:pass
            result.update(outcome='human_review_requested',reason=str(error))
        (folder/'diagnostic_report.json').write_text(json.dumps(result,indent=2)+'\n')
        cases.append(result)
        print(name+': '+result['outcome'])
    assert cases[0]['outcome']=='candidate_accepted'
    assert cases[1]['outcome']=='human_review_requested'
    assert 'position evidence' in cases[1]['reason']
    (out/'summary.json').write_text(json.dumps(dict(cases=cases,
        statement='Guard logic test only; injected disagreement is not an observed Cosmos error.'),indent=2)+'\n')
    print('PASS existing disagreement guard; no Isaac, AI inference or robot movement. Results:',out)


if __name__=='__main__':main()
