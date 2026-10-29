"""Six-cube TCP policy. Initial inventory and one pre-first-pick recovery only."""
import copy
import time
import numpy as np
from primitives import MotionPrimitives, RehearsalConfig, ReviewRequired, square_delta

COLOURS=['yellow','yellow','blue','blue','red','red']
STACK_XY=np.array([.28,.10])


def validate_stack(plan):
    if plan.get('source')!='Cosmos3-Nano' or plan.get('task')!='cube_stack' or plan.get('stack_ready') is not True:
        raise ReviewRequired('Need an accepted Cosmos-assisted six-cube stack plan')
    picks=plan.get('picks',[])
    if len(picks)!=6 or [p.get('colour') for p in picks]!=COLOURS:
        raise ReviewRequired('Require six cubes in yellow-yellow-blue-blue-red-red order')
    if len({p['detection_id'] for p in picks})!=6 or not np.isclose(plan.get('open_gap_m',0),.012):
        raise ReviewRequired('Repeated detection or incompatible gripper opening')
    for level,p in enumerate(picks):
        xy=np.asarray(p.get('xy'),float)
        values=[p.get(k,float('nan')) for k in ('yaw_deg','pose_confidence','pose_silhouette_iou','pick_z','place_z')]
        if (xy.shape!=(2,) or not np.isfinite(xy).all() or not np.isfinite(values).all() or
                p.get('category')!='cube' or p.get('eligible') is not True or p.get('stack_level')!=level or
                not .8<=p['pose_confidence']<=1 or not .85<=p['pose_silhouette_iou']<=1):
            raise ReviewRequired('Invalid cube pose, confidence, image fit or stack level')
        if not (.18<=xy[0]<=.48 and -.25<=xy[1]<=.25) or np.linalg.norm(xy)>.50:
            raise ReviewRequired('Cube outside conservative prototype work area')
        if (not np.allclose(p.get('place_xy'),STACK_XY,atol=1e-9) or
                not np.isclose(p['pick_z'],-.0026,atol=1e-9) or
                not np.isclose(p['place_z'],-.0026+level*.010,atol=1e-9)):
            raise ReviewRequired('Stack destination or fingertip height differs from reviewed task')
        theta=np.deg2rad(p['yaw_deg'])
        if (not np.allclose(p.get('spread_dir'),[-np.sin(theta),np.cos(theta),0.]) or
                not np.allclose(p.get('place_spread_dir'),[0.,1.,0.])):
            raise ReviewRequired('Cube grasp or stack wrist alignment is inconsistent')
        # These estimates share image geometry; agreement is not independent accuracy.
        measurement=p.get('image_pose_measurement',{})
        measured=np.asarray(measurement.get('position_world_m'),float)
        yaw=float(measurement.get('yaw_deg',float('nan')))
        if (measured.shape!=(3,) or not np.isfinite(measured).all() or not np.isfinite(yaw) or
                measurement.get('source')!='calibrated_image_silhouette_fit' or
                np.linalg.norm(measured[:2]-xy)>.002 or abs(square_delta(yaw,p['yaw_deg']))>3):
            raise ReviewRequired('Image-derived measurement and planned grasp disagree (>2 mm or >3 deg)')
        for earlier in picks[:level]:
            if np.linalg.norm(xy-np.asarray(earlier['xy']))<.04:
                raise ReviewRequired('Initial cube inventory overlaps or repeats a location')
    return copy.deepcopy(plan)


class StackPolicy(MotionPrimitives):
    CAMERAS=['table','side','wrist']
    IMAGE_SIZE=(1920,1080)
    IMAGE_FORMAT='png'
    ACTION='tcp'
    PREFETCH=False
    DEPTH=[]
    DT=.1

    def __init__(self,backend,*,motion_enabled=False,recovery_enabled=True,operator_release_required=False,config=None,clock=time.monotonic):
        self.backend=backend;self.motion_enabled=motion_enabled;self.recovery_enabled=recovery_enabled
        self.c=config or RehearsalConfig();self.clock=clock
        self.operator_release_required=operator_release_required
        if self.c.dt_s!=.1 or self.c.max_rows not in range(1,101):raise ValueError('Invalid chunk timing')
        self.reset()

    def reset(self):
        self.state='initial_observation';self.events=[];self.plan=None;self.initial=None
        self.pending=[];self.target=None;self.phase=None;self.after_arrival=None
        self.wait_started=None;self.stable_polls=0;self.level=0
        self.recovery_applied=False;self.grasp_commanded=False;self.review_reason=None
        self.commanded_placements=0

    def _advance(self,current):
        p=self.plan['picks'][self.level]
        xy=np.array(p['xy']);site=np.array(p['place_xy'])
        if self.state=='above_source':
            after='fresh_pregrasp' if self.level==0 else 'descend_source'
            self._move(current,self._row(xy,self.c.travel_base_z_m,self._r(p['yaw_deg']),0),'approach_source',after)
        elif self.state=='descend_source':
            self._move(current,self._row(xy,p['pick_z'],self._r(p['yaw_deg']),0),'descend','close')
        elif self.state=='close':
            target=current.copy();target[6]=1;self.grasp_commanded=True
            self._move(current,target,'close_stationary','lift')
        elif self.state=='lift':
            self._move(current,self._row(xy,self.c.travel_base_z_m,self._r(p['yaw_deg']),1),'lift','carry')
        elif self.state=='carry':
            self._move(current,self._row(site,self.c.travel_base_z_m,self._r(0),1),'carry','lower')
        elif self.state=='lower':
            self._move(current,self._row(site,p['place_z'],self._r(0),1),'lower','release')
        elif self.state=='release':
            target=current.copy();target[6]=0
            self._move(current,target,'release_stationary','retreat')
        elif self.state=='retreat':
            self._move(current,self._row(site,self.c.travel_base_z_m,self._r(0),0),'retreat','placement_command_complete')

    def act(self,obs):
        try:current=self._pose(obs)
        except ReviewRequired as error:
            self.state='human_review_required';self.review_reason=str(error);raise
        try:
            if self.state in ('human_review_required','complete_unverified','observe_and_plan','await_operator_release'):
                return current.tolist()
            if self.state=='initial_observation':
                self.plan=validate_stack(self.backend.initial(obs))
                self.initial=copy.deepcopy(self.plan)
                self.log('six_cube_plan_created',colour_order=COLOURS)
                if not self.motion_enabled:
                    self.state='observe_and_plan';return current.tolist()
                if current[6]!=0:raise ReviewRequired('Start with gripper open; do not release unknown held object')
                if current[2]+330<self.c.travel_base_z_m*1000-1:
                    raise ReviewRequired('Start must be at or above the operator-reviewed travel plane')
                if abs(abs(current[3])-180)>1 or abs(current[4])>1:
                    raise ReviewRequired('Start must already point fingers downward')
                if self.operator_release_required:
                    self.state='await_operator_release'
                    self.log('awaiting_operator_release_before_motion')
                    return current.tolist()
                self.state='above_source'
            if self.state=='fresh_pregrasp':
                # Backend uses current pixels, not requested disturbance or truth.
                result=self.backend.pregrasp(obs,self.initial,self.recovery_enabled)
                if result['decision']=='review':raise ReviewRequired(result['reason'])
                updated=validate_stack(result['plan'])
                self.plan=updated
                self.recovery_applied=bool(result.get('recovery_applied',False))
                self.log('pre_first_pick_check',decision=result['decision'],recovery_applied=self.recovery_applied)
                if self.recovery_applied:
                    self._move(current,self._row(self.plan['picks'][0]['xy'],self.c.travel_base_z_m,
                        self._r(self.plan['picks'][0]['yaw_deg']),0),'recovery_reapproach','descend_source')
                else:self.state='descend_source'
            if self.state=='waiting':
                distance=np.linalg.norm(current[:3]-self.target[:3])
                angle=np.max(np.abs((current[3:6]-self.target[3:6]+180)%360-180))
                arrived=distance<=self.c.endpoint_tolerance_mm and angle<=self.c.orientation_tolerance_deg and current[6]==self.target[6]
                self.stable_polls=self.stable_polls+1 if arrived else 0
                if self.clock()-self.wait_started>self.c.arrival_timeout_s:
                    raise ReviewRequired('Timed out waiting for measured TCP/gripper arrival')
                if self.stable_polls>=2:
                    self.log('command_arrival_observed',phase=self.phase,stack_level=self.level)
                    self.state=self.after_arrival;self.target=None
                    return current.tolist()
                return self.target.tolist()
            if self.state=='placement_command_complete':
                self.commanded_placements+=1;self.level+=1
                self.log('placement_command_sequence_finished',stack_level=self.level-1,physical_success_verified=False)
                if self.level==6:
                    self.state='complete_unverified';return current.tolist()
                self.state='above_source'
            if self.state!='sending':self._advance(current)
            if self.state=='sending':
                chunk=self.pending[:self.c.max_rows];self.pending=self.pending[len(chunk):]
                if not self.pending:
                    self.state='waiting';self.wait_started=self.clock();self.stable_polls=0
                return chunk
            return current.tolist()
        except Exception as error:
            self.review_reason=str(error);self.state='human_review_required';self.pending=[];self.target=None
            self.log('human_review_required',reason=str(error),grasp_commanded=self.grasp_commanded)
            return current.tolist()

    def report(self):
        return dict(state=self.state,task_complete=None,verified_pickups=None,verified_placements=None,
            commanded_placement_sequences=self.commanded_placements,colour_order=COLOURS,
            recovery_applied=self.recovery_applied,recovery_enabled=self.recovery_enabled,
            recovery_scope='one pre-first-pick update only; not general failure recovery',
            physical_execution_evaluated=False,grasp_commanded=self.grasp_commanded,
            human_review_required=self.state=='human_review_required',reason=self.review_reason,events=self.events)
