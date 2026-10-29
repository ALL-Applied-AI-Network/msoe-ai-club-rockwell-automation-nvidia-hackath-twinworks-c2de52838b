"""Scripted complete six-cube rehearsal; not AI or physics evaluation."""
import argparse,copy,json
from pathlib import Path
import numpy as np
from stack_policy import StackPolicy
from evidence import dump


def fixture():return json.loads(Path(__file__).with_name('mock_fixture_plan.json').read_text())


class ScriptedBackend:
    def __init__(self,case='unchanged'):self.case=case
    def initial(self,obs):return fixture()
    def pregrasp(self,obs,plan,enabled):
        if self.case=='disagree':return dict(decision='review',reason='Injected 8 mm position-estimate disagreement')
        if self.case=='uncertain':return dict(decision='review',reason='Injected uncertain target image')
        candidate=copy.deepcopy(plan)
        if enabled and self.case=='shift10':
            p=candidate['picks'][0];p['xy'][0]+=.010
            p['image_pose_measurement']['position_world_m'][0]+=.010
            return dict(decision='replan',plan=candidate,recovery_applied=True)
        return dict(decision='retain',plan=candidate,recovery_applied=False)


def run_replay(policy,limit=10000):
    obs=dict(tcp_pose=[300.,0.,-180.,-180.,0.,0.],joints=[0.,3.,-12.,0.,-75.,0.,0.])
    rows=[]
    for _ in range(limit):
        chunk=np.asarray(policy.act(obs),float).reshape(-1,7)
        rows.extend(chunk.tolist());obs['tcp_pose']=chunk[-1,:6].tolist();obs['joints'][6]=float(chunk[-1,6])
        if policy.state in ('complete_unverified','human_review_required','observe_and_plan'):return rows
    raise RuntimeError('Rehearsal did not terminate')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();a.out.mkdir(exist_ok=False,parents=True)
    for case in ('unchanged','shift10','disagree','uncertain'):
        policy=StackPolicy(ScriptedBackend(case),motion_enabled=True)
        rows=run_replay(policy)
        dump(a.out/f'{case}_report.json',policy.report())
        dump(a.out/f'{case}_mock_targets.json',dict(data_kind='scripted_mock_only',targets=rows))
        if policy.state=='human_review_required':
            dump(a.out/f'{case}_human_review_request.json',dict(reason=policy.review_reason,
                automatically_sent=False,grasp_attempted=policy.grasp_commanded,synthetic_test=True))
        print(case,policy.state,'placement command sequences:',policy.commanded_placements,
              'recovery:',policy.recovery_applied)
    print('Scripted logic only. No model, simulator, physical robot or task-success measurement.')


if __name__=='__main__':main()
