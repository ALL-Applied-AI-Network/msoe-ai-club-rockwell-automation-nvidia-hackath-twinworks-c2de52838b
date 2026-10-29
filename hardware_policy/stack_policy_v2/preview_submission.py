"""Show SDK-equivalent submission payload offline. Does not submit or reserve a slot."""
import argparse,json
from pathlib import Path
import yaml


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--session',required=True,type=Path)
    a=ap.parse_args();root=a.session.resolve()
    sub=yaml.safe_load((root/'submission/submission.yaml').read_text())
    place=yaml.safe_load((root/'submission/placement.yaml').read_text())
    assert sub['team']=='TwinWorks (UWM/MSOE-Team-49)' and sub['rollouts']==3
    assert sub['model_type']=='Hybrid' and sub['layout']=='same'
    assert len(place['rollouts'])==1 and len(place['rollouts'][0]['objects']['cube'])==6
    if sub.get('custom_hardware')=='none':sub['custom_hardware']=None
    sub.update(action='tcp',cameras=['table','side','wrist'],depth=[],placement=place)
    print(json.dumps(sub,indent=2))
    print('OFFLINE PREVIEW ONLY. Real policy and weights stay on Spark; no request ID has been created.')


if __name__=='__main__':main()
