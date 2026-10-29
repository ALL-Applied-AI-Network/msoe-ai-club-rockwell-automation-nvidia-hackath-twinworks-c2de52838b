"""Write a local start record ONLY after on-site operator clearance. Not a safety interlock."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from evidence import dump


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rollout',required=True,type=Path);ap.add_argument('--operator',required=True)
    ap.add_argument('--workspace-clear',action='store_true')
    a=ap.parse_args()
    status=json.loads((a.rollout/'policy_report.json').read_text())
    if status['state']!='await_operator_release':raise ValueError('Not waiting for initial operator start; cannot resume a review stop')
    if not a.workspace_clear or not a.operator.strip():raise ValueError('Operator and workspace-clear confirmation required')
    request=json.loads((a.rollout/'awaiting_operator_release.json').read_text())
    path=a.rollout/'operator_release.json'
    if path.exists():raise FileExistsError('Start record already exists')
    dump(path,dict(nonce=request['nonce'],operator=a.operator,workspace_clear=True,
        time=datetime.now(timezone.utc).isoformat()))
    print('Operator start record written. The running client may now send motion targets; this is not a safety interlock.')


if __name__=='__main__':main()
