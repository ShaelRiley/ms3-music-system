#!/usr/bin/env python3
"""Finite committed-bank gate; no Surge, numpy, DAW or network required.

--decode additionally runs every file through ffmpeg (numpy needed for metrics).
Full regeneration belongs to tools/music/build_ms2_surge.py, outside normal CI.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
DEST=ROOT/'gamemodes/legend_of_deborah/content/sound/lod/ms2_surge'

def sha(data):return hashlib.sha256(data).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)
def lua_json(path):return json.loads(path.read_text().split('[==[',1)[1].rsplit(']==]',1)[0])

def ogg_info(data,cid):
    """Parse real Vorbis identification and final granule, not file extensions."""
    at=0;sequence=0;first=bytearray();identified=False;granule=0;ended=False
    serial=int(sha(cid.encode())[:8],16)
    while at<len(data):
        need(len(data)-at>=27 and data[at:at+5]==b'OggS\0','bad Ogg page: '+cid)
        flags=data[at+5];n=data[at+26];table=data[at+27:at+27+n];size=27+n+sum(table)
        need(len(table)==n and at+size<=len(data),'truncated Ogg: '+cid)
        need(struct.unpack_from('<II',data,at+14)==(serial,sequence),'Ogg stream/sequence mismatch: '+cid)
        g=struct.unpack_from('<Q',data,at+6)[0]
        if g!=0xffffffffffffffff:granule=g
        if sequence==0:need(flags&2,'missing stream start: '+cid)
        if not identified:
            body=at+27+n
            for length in table:
                first.extend(data[body:body+length]);body+=length
                if length<255:
                    need(first[:7]==b'\x01vorbis' and len(first)==30,'not Vorbis: '+cid)
                    need(struct.unpack_from('<I',first,7)[0]==0,'Vorbis version: '+cid)
                    channels=first[11];rate=struct.unpack_from('<I',first,12)[0];identified=True;break
        ended=bool(flags&4);at+=size;sequence+=1
        need(not ended or at==len(data),'trailing/concatenated audio: '+cid)
    need(identified and ended and granule>0,'incomplete/silent-length Ogg: '+cid)
    return channels,rate,granule

def validate(decode=False):
    manifest=json.loads((ROOT/'docs/MS2_SURGE_BANK.json').read_text())
    lock=json.loads((ROOT/'tools/music/surge/lock.json').read_text())
    patches=json.loads((ROOT/'tools/music/surge/patches.json').read_text())
    catalog=lua_json(BUNDLE/'catalog.lua');runtime=lua_json(BUNDLE/'render.lua')
    need(manifest['schema']==runtime['schema']==1,'schema')
    need(manifest['catalogRevision']==runtime['catalogRevision']==catalog['revision'],'catalog revision')
    need(manifest['revision']==runtime['revision'],'runtime bank revision')
    need(manifest['patchRevision']==runtime['patchRevision'],'runtime patch revision')
    patch_hash=sha((ROOT/'tools/music/surge/patches.json').read_bytes())
    need(manifest['patchSHA256']==patch_hash and manifest['patchRevision']==patches['revision']+'-'+patch_hash[:12],'patch provenance')
    renderer_hash=sha((ROOT/'tools/music/build_ms2_surge.py').read_bytes()+(ROOT/'tools/music/surge/bank.py').read_bytes())
    need(manifest['rendererSHA256']==renderer_hash,'stale renderer provenance')
    need(manifest['surge']=={**lock,'reportedBuildVersion':manifest['surge']['reportedBuildVersion']},'Surge lock differs')
    need(lock['bindingPatchSHA256']==sha((ROOT/'tools/music/surge/surgepy_lod.patch').read_bytes()),'binding patch provenance')
    for number,line in enumerate((ROOT/'tools/music/surge/surgepy_lod.patch').read_text().splitlines(),1):
        need(line==' ' or not line.endswith((' ','\t')),'trailing whitespace in patch code: '+str(number))
    need(lock['commit'][:7] in manifest['surge']['reportedBuildVersion'],'build source revision')
    need(manifest['channels']==2 and manifest['sampleRate']==lock['sampleRate']==44100,'audio format')
    need(manifest['bpm']==runtime['bpm']==catalog['bpm']==130,'canonical fixed tempo')
    need(len(catalog['blocks'])==8 and len(catalog['assets'])==48,'composition authority')
    audit=json.loads((ROOT/'docs/MS3_SONG_AUDIT.json').read_text())
    need(audit['catalogRevision']==catalog['revision'] and catalog['phraseBars']==16 and catalog['songFirst'],'source arrangement revision')
    need(audit['sourceMidiFiles']==465 and audit['ordinaryClips']==216 and audit['fanfares']==8,'authored long-form coverage')
    expected_count=audit['ordinaryClips']+audit['fanfares']
    pages={};compiled={};notes=0
    for aid,asset in catalog['assets'].items():
        for clip in asset['clips']:
            need(clip['id'] not in compiled,'duplicate catalog ID')
            if clip['page'] not in pages:pages[clip['page']]=lua_json(BUNDLE/clip['page'])
            source=pages[clip['page']][clip['id']];notes+=len(source)
            compiled[clip['id']]={**clip,'block':asset['block'],'role':asset['role'],'asset':aid,
                                 'noteSHA256':sha(json.dumps(source,separators=(',',':')).encode())}
    bank={c['id']:c for c in manifest['clips']}
    need(len(bank)==len(manifest['clips'])==len(compiled)==manifest['clipCount']==expected_count and notes==audit['notes'],'complete curated score')
    need(set(bank)==set(compiled)==set(runtime['clips']),'missing/orphan phrase')
    need({p.name for p in DEST.iterdir()}=={cid+'.ogg' for cid in bank}|{'bridge.ogg'},'missing/orphan runtime audio')
    need({v['name'] for v in patches['voices']}=={'acid','industrial','strings','brass','bass','tom','snare','kick','closed','open'},'physical patches')
    need({v['logicalInstrument'] for v in manifest['voices']}==set(range(9)),'logical voices')
    for v in manifest['voices']:
        need(v['deterministic'] and math.isfinite(v['rms']) and v['rms']>=.0002 and v['peak']<=.82,'inaudible/invalid voice: '+v['name'])
        if v['name']=='acid':
            need(v['movementRatio']>=1.3 and v['heldSpectralCentroid90Hz']/v['heldSpectralCentroid10Hz']>=1.3,'static Acid')
    all_files=[];total=0
    for cid,c in bank.items():
        source=compiled[cid]
        for key in ('block','role','asset','beats','noteSHA256'):need(c[key]==source[key],cid+' source '+key)
        need(c['bpm']==130 and c['rendererRevision']==manifest['rendererRevision'] and c['patchRevision']==manifest['patchRevision'],'phrase provenance: '+cid)
        need((c['beats']==12 if c['role']=='VICTORY' else c['beats'] in range(4,65,4)) and c['musicalDuration']==c['musicalFrames']/44100,'song chunk duration: '+cid)
        need(c['musicalFrames']==source['musicalFrames'] and c['continuousPerformance'] and c['songIndex']==source['songIndex'],'continuous performance provenance: '+cid)
        songrows=[r for r in manifest['clips'] if r['asset']==c['asset']]
        prior=sum(r['musicalFrames'] for r in songrows if r['songIndex']<c['songIndex'])
        need(c['sourceFrameRange']==[prior,prior+c['musicalFrames']],'source performance frame range: '+cid)
        need(len({r['songPCM_SHA256'] for r in songrows})==1,'chunks share one full performance: '+cid)
        need(c['internalZeroTail']==(c['songIndex']<len(songrows)-1),'only terminal song chunk has a release: '+cid)
        need(runtime['clips'][cid]=={'beats':c['beats'],'duration':c['duration'],'peak':c['decodedPeak'],'tailPeak':c['decodedTailPeak'],'musicalFrames':c['musicalFrames']},'runtime duration/peak: '+cid)
        need(math.isfinite(c['decodedTailPeak']) and 0<=c['decodedTailPeak']<=c['decodedPeak'],'tail peak: '+cid)
        need(abs(c['duration']-c['musicalDuration']-lock['releaseSeconds'])<=2/44100,'release tail: '+cid)
        all_files.append((cid,c))
    all_files.append(('bridge',manifest['bridge']))
    need(runtime['bridge']=={'duration':manifest['bridge']['duration'],'peak':manifest['bridge']['decodedPeak']}
         and 1<manifest['bridge']['duration']<8,'bridge contract')
    for cid,c in all_files:
        path=DEST/(cid+'.ogg');need(c['path']==str(path.relative_to(ROOT)),'untrusted path: '+cid)
        data=path.read_bytes();need(1000<len(data)==c['bytes']<=1024*1024 and sha(data)==c['sha256'],'audio integrity: '+cid)
        channels,rate,frames=ogg_info(data,cid)
        need((channels,rate)==(2,44100) and frames/44100==c['duration'],'encoded duration/format: '+cid)
        need(abs(frames-c['decodedFrames'])<=256,'decoded frame count: '+cid)
        need(math.isfinite(c['decodedPeak']) and 0<c['decodedPeak']<=.9,'decoded peak: '+cid)
        need(math.isfinite(c['decodedRMS']) and c['decodedRMS']>.00002,'decoded silence: '+cid)
        need(math.isfinite(c['decodedDC']) and c['decodedDC']<.005,'decoded DC: '+cid)
        if cid!='bridge':
            need(0<c['peak']<=.82 and c['rms']>.00002 and c['dc']<.005,'PCM level: '+cid)
            need(len(c['pcmSHA256'])==64,'PCM provenance: '+cid)
        total+=len(data)
    need(total==manifest['totalBytes']<=lock['packageBudgetBytes']==60000000,'package budget')
    need(lock['designReviewBytes']==100000000 and manifest['fileCount']==len(all_files)==expected_count+1,'file count/design review')
    need(manifest['largestBytes']==max(c['bytes'] for c in bank.values()),'largest file')
    need(manifest['averagePhraseBytes']==sum(c['bytes'] for c in bank.values())/expected_count,'average phrase')
    revision='ms2-surge-'+sha(json.dumps([(c['id'],c['sha256']) for c in manifest['clips']]+[('bridge',manifest['bridge']['sha256'])]).encode())[:16]
    need(revision==manifest['revision'],'content revision')
    if decode:
        import numpy as np
        def check_file(item):
            cid,c=item
            raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(DEST/(cid+'.ogg')),'-f','f32le','-acodec','pcm_f32le','-'])
            pcm=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
            need(len(pcm)==c['decodedFrames'] and np.isfinite(pcm).all(),'actual decode: '+cid)
            need(abs(pcm).max()<=.9 and np.sqrt((pcm*pcm).mean())>.00002 and abs(pcm.mean(axis=0)).max()<.005,'actual decoded level: '+cid)
            need(abs(float(abs(pcm).max())-c['decodedPeak'])<1e-7,'decoded peak metadata: '+cid)
            if cid!='bridge':need(abs(float(abs(pcm[math.floor((c['musicalDuration']-.15)*44100):]).max())-c['decodedTailPeak'])<1e-7,'decoded tail peak metadata: '+cid)
            need(abs(float(np.sqrt((pcm*pcm).mean()))-c['decodedRMS'])<1e-8,'decoded RMS metadata: '+cid)
            need(abs(float(abs(pcm.mean(axis=0)).max())-c['decodedDC'])<1e-8,'decoded DC metadata: '+cid)
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check_file,all_files))
    return {'suite':'MS2_SURGE_BANK','revision':manifest['revision'],'clips':expected_count,'notes':notes,'files':len(all_files),'bytes':total,
            'acidMovementRatio':manifest['voices'][0]['movementRatio'],'actualDecodes':len(all_files) if decode else 0}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--decode',action='store_true');args=parser.parse_args()
    try:print(json.dumps(validate(args.decode)));return 0
    except (ValueError,KeyError,OSError) as err:print('MS2_SURGE_BANK FAIL:',err,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
