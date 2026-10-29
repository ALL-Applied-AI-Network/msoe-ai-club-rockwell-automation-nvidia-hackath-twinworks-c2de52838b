"""Organizer policy entry point; default is observe-and-plan, motion disabled."""
from datetime import datetime,timezone
import json,sys,uuid
from pathlib import Path
from evidence import dump,sha
from primitives import RehearsalConfig
from stack_policy import StackPolicy

CHECKS=['coordinate_frame_checked','image_localization_checked','hook_contact_height_checked',
        'orientation_mapping_checked','path_clearance_checked','start_pose_checked']


def load_settings(path):
    config=json.loads(Path(path).read_text())
    mode=config.get('mode')
    if mode not in ('mock','observe_and_plan','execute_stack'):raise ValueError('Unsupported policy mode')
    if config.get('recovery') not in ('enabled','disabled'):raise ValueError('Set recovery enabled or disabled')
    if mode=='mock' and '--mock' not in sys.argv:
        raise ValueError('Mock fixture policy is permitted only with organizer run.py --mock')
    if mode=='execute_stack':
        checks=config.get('operator_checks',{})
        if any(checks.get(name) is not True for name in CHECKS) or not str(checks.get('operator','')).strip():
            raise ValueError('Physical execution blocked: documented operator commissioning checks are incomplete')
        if config.get('tcp_r_for_zero_yaw_deg') is None:
            raise ValueError('Physical finger orientation mapping is not specified')
    return config


class Policy(StackPolicy):
    def __init__(self,checkpoint=None):
        package=Path(__file__).resolve().parent
        self.settings=load_settings(checkpoint or package.parent/'session_config.json')
        self.output=Path(self.settings['output_root'])
        if not self.output.is_absolute():raise ValueError('Capture output root must be absolute')
        self.session=self.output/('session_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8])
        self.session.mkdir(exist_ok=False,parents=True)
        self.trial_number=0;self.trial_output=None
        self.constructing=True
        mode=self.settings['mode']
        r=0. if mode=='mock' or self.settings.get('tcp_r_for_zero_yaw_deg') is None else float(self.settings['tcp_r_for_zero_yaw_deg'])
        super().__init__(None,motion_enabled=mode in ('mock','execute_stack'),
            recovery_enabled=self.settings['recovery']=='enabled',operator_release_required=mode=='execute_stack',
            config=RehearsalConfig(r_zero_deg=r))
        self.constructing=False
        dump(self.session/'settings.json',self.settings)
        print('TwinWorks six-cube policy:',mode,'— session:',self.session,flush=True)

    def reset(self):
        super().reset()
        if not hasattr(self,'session') or getattr(self,'constructing',False):return
        self.trial_number+=1
        self.trial_output=self.session/f'rollout_{self.trial_number:03d}';self.trial_output.mkdir()
        self.release_nonce=uuid.uuid4().hex
        modes=self.settings.get('recovery_by_rollout',[])
        if modes:
            if self.trial_number>len(modes) or modes[self.trial_number-1] not in ('enabled','disabled'):
                raise ValueError('No documented recovery mode for this rollout; inspect operator plan')
            self.recovery_enabled=modes[self.trial_number-1]=='enabled'
        print('Rollout',self.trial_number,'recovery:', 'enabled' if self.recovery_enabled else 'disabled',flush=True)
        dump(self.trial_output/'trial_settings.json',dict(recovery_enabled=self.recovery_enabled,
            policy_mode=self.settings['mode'],sequence_number=self.trial_number))
        if self.settings['mode']=='mock':
            from replay import ScriptedBackend
            self.backend=ScriptedBackend(self.settings.get('mock_case','unchanged'))
        else:
            from vision_backend import VisionBackend
            s=self.settings
            self.backend=VisionBackend(s['client'],s['project'],s['cosmos'],s['host'],s['model'],self.trial_output)

    def act(self,obs):
        if self.settings['mode']=='mock' and obs.get('tcp_pose') is None:
            obs=dict(obs,tcp_pose=[300.,0.,-180.,-180.,0.,0.])
        try:
            if self.state=='await_operator_release':
                release=self.trial_output/'operator_release.json'
                if release.exists():
                    record=json.loads(release.read_text())
                    if (record.get('nonce')!=self.release_nonce or record.get('workspace_clear') is not True
                            or not str(record.get('operator','')).strip()):
                        raise ValueError('Invalid operator start record; remain stopped')
                    self.state='above_source'
                    self.log('operator_start_record_received',operator=record['operator'])
            result=super().act(obs)
        except Exception as error:
            self.state='human_review_required';self.review_reason=str(error)
            dump(self.trial_output/'policy_report.json',self.report())
            dump(self.trial_output/'human_review_request.json',dict(reason=str(error),
                automatically_sent=False,grasp_attempted=self.grasp_commanded))
            raise
        report=self.report()
        report['input_kind']='mock_fixture' if self.settings['mode']=='mock' else 'real_observations'
        dump(self.trial_output/'policy_report.json',report)
        if self.state=='await_operator_release':
            dump(self.trial_output/'awaiting_operator_release.json',dict(nonce=self.release_nonce,
                instruction='CSI operator: confirm calibration/start pose, supervised disturbance if approved, then workspace clear before release.',
                mode='pre-first-pick commissioning checkpoint',not_a_safety_interlock=True))
        if self.state=='human_review_required':
            dump(self.trial_output/'human_review_request.json',dict(reason=self.review_reason,
                automatically_sent=False,grasp_attempted=self.grasp_commanded))
        return result
