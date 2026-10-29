"""Save current observations and invoke isolated model and planner workers."""
import json,os,shutil,subprocess,time
from pathlib import Path
import cv2,numpy as np
from geometry_adapter import prepare_bgr
from evidence import dump,sha


class VisionBackend:
    def __init__(self,client,project,cosmos,host,model,output):
        self.client=Path(client).resolve();self.project=Path(project).resolve()
        self.cosmos=str(Path(cosmos).absolute());self.host=str(Path(host).absolute())
        self.model=str(Path(model).resolve());self.output=Path(output);self.counter=0
        hashes=json.loads(Path(__file__).with_name('stacking_revision.json').read_text())
        for name,digest in hashes.items():
            if sha(self.project/name)!=digest:raise ValueError('Reviewed stacking source changed: '+name)
        revision=self.output/'source_revision';revision.mkdir(exist_ok=False)
        for name in hashes:
            target=revision/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(self.project/name,target)
        dump(self.output/'stacking_source.json',hashes)

    def initial(self,obs):return self._call(obs,'initial')['plan']

    def pregrasp(self,obs,plan,enabled):return self._call(obs,'pregrasp',plan,enabled)

    def _call(self,obs,operation,plan=None,enabled=True):
        self.counter+=1;folder=self.output/f'observation_{self.counter:03d}';folder.mkdir()
        rgb=np.asarray(obs['images']['table'])
        if rgb.shape!=(1080,1920,3) or rgb.dtype!=np.uint8:raise ValueError('Require native 1920x1080 table RGB')
        raw=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
        image,camera=prepare_bgr(raw,self.client/'calibration/cameras.json')
        for name,data in [('raw_table.png',raw),('world_camera.png',image)]:
            if not cv2.imwrite(str(folder/name),data):raise OSError('Cannot save camera evidence')
        dump(folder/'camera.json',camera)
        dump(folder/'observation.json',dict(operation=operation,t=obs.get('t'),
            joints=np.asarray(obs['joints']).tolist(),tcp_pose=np.asarray(obs['tcp_pose']).tolist(),
            image_sha256=sha(folder/'world_camera.png'),calibration_sha256=sha(self.client/'calibration/cameras.json')))
        if plan is not None:dump(folder/'initial_sort_plan.json',plan)
        environment=os.environ.copy()
        for name in ('TWINWORKS_TASK','TWINWORKS_SCENARIO','COSMOS3_ROOT','PYTHONHOME','PYTHONPATH'):
            environment.pop(name,None)
        environment.update(COSMOS3_NANO_PATH=self.model,PYTHONUNBUFFERED='1',
            OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        command=[self.cosmos,'-u',str(Path(__file__).with_name('vision_worker.py')),
            '--project',str(self.project),'--host',self.host,'--run',str(folder),
            '--operation',operation,'--recovery','enabled' if enabled else 'disabled']
        start=time.monotonic()
        try:
            with (folder/'vision.log').open('x') as log:
                subprocess.run(command,cwd=self.project,env=environment,stdout=log,
                    stderr=subprocess.STDOUT,check=True,timeout=1200)
            result=json.loads((folder/'worker_result.json').read_text())
            dump(folder/'timing.json',dict(vision_wall_seconds=time.monotonic()-start))
            return result
        except Exception as error:
            dump(folder/'worker_failure.json',dict(reason=str(error),elapsed_seconds=time.monotonic()-start))
            raise
