"""Project-owned parameter construction over the pinned Surge Python API."""
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
LOCK=json.loads((HERE/'lock.json').read_text())
PATCHES=json.loads((HERE/'patches.json').read_text())
PATCH_SHA=hashlib.sha256((HERE/'patches.json').read_bytes()).hexdigest()

def load_surge(module_dir):
    sys.path.insert(0,str(Path(module_dir).resolve()))
    import surgepy
    if getattr(surgepy,'lodBuildRevision',None)!=LOCK['bindingRevision']:
        raise RuntimeError('Surge binding revision does not match lock.json; run surge/prepare.py')
    if LOCK['commit'][:7] not in surgepy.getVersion():raise RuntimeError('Unexpected Surge build version')
    return surgepy

def resolve(patch,path):
    node=patch
    for key in path.split('.'):node=node[int(key) if key.isdigit() else key]
    return node

def construct(surge,name,seed,role='T2',receipt=None):
    spec=next(v for v in PATCHES['voices'] if v['name']==name)
    synth=surge.createLoDSurge(LOCK['sampleRate'],seed,130)
    patch=synth.getPatch();parameters={**PATCHES['commonParameters'],**spec['parameters']}
    if role in ('T0','INTERLUDE'):parameters.update(spec.get('calmParameters',{}))
    # Change oscillator/filter/effect types before touching type-dependent p[].
    # Resolve through the API's hierarchy, never synth-side numerical offsets.
    types=[k for k in parameters if k.endswith('.type')]
    def set_value(path,value):
        param=resolve(patch,path)
        if isinstance(value,str):value=getattr(surge.constants,value)
        if not synth.getParamMin(param)<=value<=synth.getParamMax(param):
            raise ValueError(f'{name}: {path}={value} outside {synth.getParamInfo(param)}')
        synth.setParamVal(param,value)
    for path in types:set_value(path,parameters[path])
    synth.process();synth.process();patch=synth.getPatch()
    for path,value in parameters.items():
        if path not in types:set_value(path,value)
    for route in spec['modulations']:
        target=resolve(patch,route['target']);source=synth.getModSource(getattr(surge.constants,route['source']))
        if not synth.isValidModulation(target,source):raise ValueError('Unsupported route: '+str(route))
        synth.setModDepth01(target,source,route['depth01'])
    for path in PATCHES['activeParameters']:synth.setLoDParameterActive(resolve(patch,path),True)
    synth.finalizeLoDPatch();synth.process();synth.process()
    if receipt is not None:
        receipt[name]={path:{'name':resolve(patch,path).getName(),'value':synth.getParamVal(resolve(patch,path)),
                            'display':synth.getParamDisplay(resolve(patch,path)),
                            'active':synth.getLoDParameterActive(resolve(patch,path))} for path in parameters}
    return synth,spec['gain']

def render_voice(surge,name,events,duration,seed,role='T2',receipt=None):
    synth,gain=construct(surge,name,seed,role,receipt);block=synth.getBlockSize();rate=LOCK['sampleRate']
    count=math.ceil(duration*rate);blocks=math.ceil(count/block);output=synth.createMultiBlock(blocks)
    schedule=[]
    for onset,gate,pitch,velocity in events:
        # One native block is 0.726 ms. Nearest-block events preserve the source
        # grid to that bounded precision; no onset/gate/pitch/velocity mutation.
        on=round(onset*rate/block);off=max(on+1,round((onset+gate)*rate/block))
        schedule.extend([(on,1,pitch,velocity),(min(blocks,off),0,pitch,0)])
    schedule.sort(key=lambda e:(e[0],e[1],e[2]))
    at=0
    for index,kind,pitch,velocity in schedule:
        index=min(index,blocks)
        if index>at:synth.processMultiBlock(output,at,index-at);at=index
        if kind:synth.playNote(0,pitch,velocity)
        else:synth.releaseNote(0,pitch,0)
    if at<blocks:synth.processMultiBlock(output,at,blocks-at)
    # Copy before the synth is destroyed; contiguous stereo float32 (frames,2).
    return np.ascontiguousarray(output[:,:count].T)*gain
