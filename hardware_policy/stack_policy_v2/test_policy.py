import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from primitives import ReviewRequired,validate_tcp
from stack_policy import StackPolicy,validate_stack,COLOURS
from replay import ScriptedBackend,fixture,run_replay
from hardware_policy import load_settings,CHECKS


class StackTests(unittest.TestCase):
    def test_six_cube_sequence_finishes_without_success_claim(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True);run_replay(p)
        self.assertEqual(p.state,'complete_unverified');self.assertEqual(p.commanded_placements,6)
        self.assertIsNone(p.report()['task_complete']);self.assertIsNone(p.report()['verified_pickups'])

    def test_order_matches_project(self):
        self.assertEqual([p['colour'] for p in fixture()['picks']],COLOURS)

    def test_placement_heights(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True);run_replay(p)
        heights=[e['target'][2] for e in p.events if e.get('phase')=='lower' and e['event']=='primitive_planned']
        self.assertTrue(np.allclose(heights,[-332.6,-322.6,-312.6,-302.6,-292.6,-282.6]))

    def test_pre_first_pick_recovery_only(self):
        p=StackPolicy(ScriptedBackend('shift10'),motion_enabled=True);run_replay(p)
        self.assertEqual(p.state,'complete_unverified');self.assertTrue(p.recovery_applied)
        self.assertEqual(len([e for e in p.events if e['event']=='pre_first_pick_check']),1)

    def test_disagreement_stops_before_grasp(self):
        p=StackPolicy(ScriptedBackend('disagree'),motion_enabled=True);run_replay(p)
        self.assertEqual(p.state,'human_review_required');self.assertFalse(p.grasp_commanded)

    def test_uncertainty_stops(self):
        p=StackPolicy(ScriptedBackend('uncertain'),motion_enabled=True);run_replay(p)
        self.assertFalse(p.grasp_commanded);self.assertEqual(p.commanded_placements,0)

    def test_actual_initial_position_disagreement_rejected(self):
        plan=fixture();plan['picks'][0]['xy'][0]+=.008
        with self.assertRaisesRegex(ReviewRequired,'disagree'):validate_stack(plan)

    def test_yaw_disagreement_rejected(self):
        plan=fixture();plan['picks'][0]['image_pose_measurement']['yaw_deg']+=5
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_missing_inventory_rejected(self):
        plan=fixture();plan['picks'].pop()
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_wrong_colour_order_rejected(self):
        plan=fixture();plan['picks'][0]['colour']='red'
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_duplicate_detection_rejected(self):
        plan=fixture();plan['picks'][1]['detection_id']=plan['picks'][0]['detection_id']
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_bad_place_site_rejected(self):
        plan=fixture();plan['picks'][0]['place_xy']=[.4,.2]
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_bad_height_rejected(self):
        plan=fixture();plan['picks'][0]['place_z']+=.01
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_low_confidence_and_fit_rejected(self):
        for key,val in [('pose_confidence',.79),('pose_silhouette_iou',.84)]:
            plan=fixture();plan['picks'][0][key]=val
            with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_nan_rejected(self):
        plan=fixture();plan['picks'][0]['xy'][0]=float('nan')
        with self.assertRaises(ReviewRequired):validate_stack(plan)

    def test_proposal_mode_holds(self):
        p=StackPolicy(ScriptedBackend());run_replay(p)
        self.assertEqual(p.state,'observe_and_plan');self.assertFalse(p.grasp_commanded)

    def test_mock_disabled_recovery_does_not_update(self):
        p=StackPolicy(ScriptedBackend('shift10'),motion_enabled=True,recovery_enabled=False);run_replay(p)
        self.assertFalse(p.recovery_applied)

    def test_all_generated_targets_within_limits(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True)
        for row in run_replay(p):validate_tcp(row)

    def test_step_speed_and_stationary_gripper(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True);rows=np.asarray(run_replay(p))
        self.assertLessEqual(np.linalg.norm(np.diff(rows[:,:3],axis=0),axis=1).max(),2.00001)
        for a,b in zip(rows,rows[1:]):
            if a[6]!=b[6]:self.assertTrue(np.allclose(a[:6],b[:6]))

    def test_reset_clears_trial(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True);run_replay(p);p.reset()
        self.assertEqual(p.level,0);self.assertFalse(p.grasp_commanded);self.assertEqual(p.events,[])

    def test_error_stops_without_opening_held_gripper(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True)
        obs=dict(tcp_pose=[300,0,-180,-180,0,0],joints=[0,0,0,0,0,0,1])
        out=p.act(obs);self.assertEqual(out[-1],1);self.assertEqual(p.state,'human_review_required')

    def test_model_failure_becomes_review(self):
        class Broken:
            def initial(self,obs):raise TimeoutError('model timeout')
        p=StackPolicy(Broken(),motion_enabled=True);run_replay(p)
        self.assertEqual(p.review_reason,'model timeout');self.assertFalse(p.grasp_commanded)

    def test_commissioning_checkpoint_holds_before_motion(self):
        p=StackPolicy(ScriptedBackend(),motion_enabled=True,operator_release_required=True)
        obs=dict(tcp_pose=[300,0,-180,-180,0,0],joints=[0,0,0,0,0,0,0])
        for _ in range(3):
            out=p.act(obs);self.assertTrue(np.array_equal(out[:6],obs['tcp_pose']))
        self.assertEqual(p.state,'await_operator_release');self.assertFalse(p.grasp_commanded)


class ConfigurationTests(unittest.TestCase):
    def settings(self,data):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        path=Path(self.tmp.name)/'config.json';path.write_text(json.dumps(data));return path

    def test_mock_cannot_be_used_in_physical_client_mode(self):
        path=self.settings(dict(mode='mock',recovery='enabled'))
        with patch.object(sys,'argv',['run.py']):
            with self.assertRaises(ValueError):load_settings(path)

    def test_mock_permitted_only_with_mock_argument(self):
        path=self.settings(dict(mode='mock',recovery='enabled'))
        with patch.object(sys,'argv',['run.py','--mock']):self.assertEqual(load_settings(path)['mode'],'mock')

    def test_execute_blocked_without_operator_checks(self):
        path=self.settings(dict(mode='execute_stack',recovery='enabled'))
        with self.assertRaises(ValueError):load_settings(path)

    def test_mapping_required_after_checks(self):
        checks={name:True for name in CHECKS};checks['operator']='test operator'
        path=self.settings(dict(mode='execute_stack',recovery='enabled',operator_checks=checks))
        with self.assertRaises(ValueError):load_settings(path)


if __name__=='__main__':unittest.main(verbosity=2)
