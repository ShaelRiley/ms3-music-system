#!/usr/bin/env python3
"""Render the compiled MS2 phrase bank with pinned external Surge XT.

Full authoring gate. Normal CI validates the committed bank without Surge.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import struct
import subprocess
import sys
import wave
import numpy as np
from scipy.signal import butter,sosfilt,stft
import scipy
from surge.bank import LOCK,PATCHES,PATCH_SHA,load_surge,render_voice,construct
ROOT=Path(__file__).resolve().parents[2]
BUNDLE=ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
DEST=ROOT/'gamemodes/legend_of_deborah/content/sound/lod/ms2_surge'
MANIFEST=ROOT/'docs/MS2_SURGE_BANK.json'
RATE=LOCK['sampleRate']
NAMES=['acid','industrial','strings','brass','bass','tom','snare','kick']

def sha(data):return hashlib.sha256(data).hexdigest()
def lua_json(path):return json.loads(path.read_text().split('[==[',1)[1].rsplit(']==]',1)[0])
def clips():
    catalog=lua_json(BUNDLE/'catalog.lua');pages={};out=[]
    for aid,a in sorted(catalog['assets'].items()):
        for c in a['clips']:
            if c['page'] not in pages:pages[c['page']]=lua_json(BUNDLE/c['page'])
            notes=pages[c['page']][c['id']]
            out.append({**c,'block':a['block'],'role':a['role'],'asset':aid,'notes':notes})
    audit=json.loads((ROOT/('docs/MS3_SONG_AUDIT.json' if catalog.get('songFirst') else 'docs/MS3_16_BAR_AUDIT.json')).read_text())
    if (catalog.get('phraseBars')!=16 or audit['catalogRevision']!=catalog['revision']
            or len(out)!=audit['ordinaryClips']+audit['fanfares'] or len({c['id'] for c in out})!=len(out)
            or sum(len(c['notes']) for c in out)!=audit['notes']
            or any((c['beats']!=(12 if c['role']=='VICTORY' else 64)) if not catalog.get('songFirst') else (c['beats']<4 or c['beats']>64 or c['beats']%4) for c in out)):
        raise RuntimeError('Long-form score/audit mismatch; regenerate from source first')
    for c in out:
        if sha(json.dumps(c['notes'],separators=(',',':')).encode())!=c['noteSHA256']:
            raise RuntimeError('Changed arranged notes: '+c['id'])
    return catalog,out

def condition(pcm,tail_fade=True):
    if not np.isfinite(pcm).all():raise ValueError('Non-finite Surge PCM')
    hp=butter(2,PATCHES['highPassHz'],btype='highpass',fs=RATE,output='sos')
    lp=butter(2,PATCHES['lowPassHz'],btype='lowpass',fs=RATE,output='sos')
    pcm=sosfilt(lp,sosfilt(hp,pcm,axis=0),axis=0)*PATCHES['masterGain']
    fade=round(PATCHES['tailFadeSeconds']*RATE)
    if tail_fade:pcm[-fade:]*=np.linspace(1,0,fade)[:,None]
    peak=float(abs(pcm).max());rms=float(np.sqrt((pcm*pcm).mean()));dc=float(abs(pcm.mean(axis=0)).max())
    if not .00002<rms or peak>.82 or dc>.005:raise ValueError(f'Invalid PCM peak={peak:.5f} rms={rms:.6f} dc={dc:.6f}')
    return pcm,{'peak':peak,'rms':rms,'dc':dc}

def wav_write(path,pcm):
    raw=np.asarray(np.rint(pcm*32767),dtype='<i2').tobytes()
    with wave.open(str(path),'wb') as f:f.setparams((2,2,RATE,0,'NONE','not compressed'));f.writeframes(raw)

def wav_read(path):
    with wave.open(str(path)) as f:
        assert(f.getnchannels(),f.getsampwidth(),f.getframerate())==(2,2,RATE)
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).astype(np.float64)/32768

# Canonical Ogg stream IDs and page checksums remove muxer-generated entropy.
CRC_TABLE=[]
for i in range(256):
    r=i<<24
    for _ in range(8):r=((r<<1)^0x04c11db7 if r&0x80000000 else r<<1)&0xffffffff
    CRC_TABLE.append(r)
def canonical_ogg(path,clip):
    data=bytearray(path.read_bytes());at=0;serial=int(sha(clip.encode())[:8],16)
    while at<len(data):
        if data[at:at+4]!=b'OggS':raise ValueError('Invalid Ogg container')
        segments=data[at+26];size=27+segments+sum(data[at+27:at+27+segments])
        struct.pack_into('<I',data,at+14,serial);data[at+22:at+26]=b'\0'*4
        crc=0
        for x in data[at:at+size]:crc=((crc<<8)&0xffffffff)^CRC_TABLE[((crc>>24)^x)&255]
        struct.pack_into('<I',data,at+22,crc);at+=size
    if at!=len(data):raise ValueError('Truncated Ogg page')
    path.write_bytes(data)

def tail_peak(pcm,musical):
    # Cover the last 150 ms of musical time too, conservatively allowing the
    # native frame/fast-seek window at a natural overlapping release.
    return float(abs(pcm[max(0,math.floor((musical-.15)*RATE)):]).max())

def encode(path,dest,clip,musical=None):
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(path),'-map_metadata','-1','-fflags','+bitexact',
                    '-flags:a','+bitexact','-c:a','libvorbis','-q:a',str(LOCK['vorbisQuality']),str(dest)],check=True)
    canonical_ogg(dest,clip)
    # Real decoding checks encoder overshoot/silence and reports exact granules.
    result=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(dest),'-f','f32le','-acodec','pcm_f32le','-'],capture_output=True,check=True)
    decoded=np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2)
    if not np.isfinite(decoded).all() or abs(decoded).max()>.9 or np.sqrt((decoded*decoded).mean())<.00002:raise ValueError('Invalid encoded audio: '+clip)
    frames=round(float(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=duration','-of','csv=p=0',str(dest)],text=True))*RATE)
    return {**({'decodedTailPeak':tail_peak(decoded,musical)} if musical is not None else {}),
            'duration':frames/RATE,'decodedFrames':len(decoded),'decodedPeak':float(abs(decoded).max()),
            'decodedRMS':float(np.sqrt((decoded*decoded).mean())),'decodedDC':float(abs(decoded.mean(axis=0)).max()),
            'sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size}

def render_clip(task):
    c,bpm,module,work,render_fingerprint=task
    work=Path(work);cid=c['id'];duration=c['beats']*60/bpm+LOCK['releaseSeconds'];wave_path=work/(cid+'.wav');cache=work/(cid+'.json')
    note_hash=sha(json.dumps(c['notes'],separators=(',',':')).encode())
    key=sha((render_fingerprint+note_hash+c['role']+str(c['beats'])).encode())
    known=json.loads(cache.read_text()) if cache.exists() else {}
    if known.get('key')==key and wave_path.exists() and known.get('pcmSHA256')==sha(wave_path.read_bytes()):metrics=known['metrics']
    else:
        surge=load_surge(module);pcm=np.zeros((math.ceil(duration*RATE),2),dtype=np.float64)
        parts={name:[] for name in [*NAMES,'closed','open']}
        hat_closed=[]
        for t,d,inst,pitch,velocity in c['notes']:
            name=NAMES[inst] if inst<8 else ('open' if pitch==46 else 'closed')
            onset=t/48*60/bpm;gate=d/48*60/bpm
            parts[name].append((onset,gate,pitch,velocity))
            if name=='closed':hat_closed.append(onset)
        for name,events in parts.items():
            if not events:continue
            if name=='open':events=[(on,min(gate,min((x-on for x in hat_closed if x>on),default=gate)),p,v) for on,gate,p,v in events]
            seed=int(sha((cid+':'+name).encode())[:8],16)
            pcm+=render_voice(surge,name,events,duration,seed,c['role'])
        pcm,metrics=condition(pcm);wav_write(wave_path,pcm)
        cache.write_text(json.dumps({'key':key,'metrics':metrics,'pcmSHA256':sha(wave_path.read_bytes())}))
    target=DEST/(cid+'.ogg');encoded=encode(wave_path,target,cid,c['beats']*60/bpm)
    if encoded['bytes']>1024*1024:raise ValueError('Phrase exceeds bounded local-file admission: '+cid)
    if abs(encoded['duration']-duration)>2/RATE:raise ValueError('Wrong duration: '+cid)
    return {'id':cid,'block':c['block'],'role':c['role'],'asset':c['asset'],'beats':c['beats'],'bpm':bpm,
            'musicalDuration':c['beats']*60/bpm,'path':str(target.relative_to(ROOT)),'noteSHA256':note_hash,
            'rendererRevision':LOCK['rendererVersion'],'patchRevision':PATCHES['revision']+'-'+PATCH_SHA[:12],
            'pcmSHA256':sha(wave_path.read_bytes()),**metrics,**encoded}


def render_song(task):
    """One uninterrupted Surge performance; split PCM, never restart voices.

    Internal chunks carry zero release padding. A prepared adjacent chunk starts
    with the actual continuation waveform, so overlap-add cannot double it. Only
    the song's last chunk has the real terminal release. The resident loop is a
    bounded emergency fallback, not the normal song traversal.
    """
    asset,score,bank,module,work,fingerprint=task
    work=Path(work);aid=asset['id'];beat_seconds=round(64*60/130*RATE)/(64*RATE)
    total_frames=sum(c['musicalFrames'] for c in bank)
    release=round(LOCK['releaseSeconds']*RATE)
    duration=(total_frames+release)/RATE
    if sha(json.dumps(score['notes'],separators=(',',':')).encode())!=asset['scoreSHA256']:
        raise ValueError('Whole-song score hash mismatch: '+aid)
    surge=load_surge(module);pcm=np.zeros((total_frames+release,2),dtype=np.float64)
    parts={name:[] for name in [*NAMES,'closed','open']};hat_closed=[]
    for t,d,inst,pitch,velocity in score['notes']:
        name=NAMES[inst] if inst<8 else ('open' if pitch==46 else 'closed')
        onset=t/48*beat_seconds;gate=d/48*beat_seconds
        parts[name].append((onset,gate,pitch,velocity))
        if name=='closed':hat_closed.append(onset)
    for name,events in parts.items():
        if not events:continue
        if name=='open':events=[(on,min(gate,min((x-on for x in hat_closed if x>on),default=gate)),p,v) for on,gate,p,v in events]
        seed=int(sha((aid+':whole-song:'+name).encode())[:8],16)
        voice=render_voice(surge,name,events,duration,seed,asset['role'])
        pcm+=voice[:len(pcm)];del voice
    pcm,_=condition(pcm)
    # Quantize once for a reproducible dry-body reconstruction proof.
    pcm=np.asarray(np.rint(pcm*32767),dtype='<i2').astype(np.float64)/32767
    full_hash=sha(np.asarray(np.rint(pcm[:total_frames]*32767),dtype='<i2').tobytes())
    body_hash=hashlib.sha256();results=[];offset=0
    for index,c in enumerate(bank):
        frames=c['musicalFrames'];last=index==len(bank)-1
        part=np.zeros((frames+release,2),dtype=np.float64)
        part[:frames]=pcm[offset:offset+frames]
        if last:part[frames:]=pcm[total_frames:total_frames+release]
        body_hash.update(np.asarray(np.rint(part[:frames]*32767),dtype='<i2').tobytes())
        path=work/(c['id']+'.wav');wav_write(path,part)
        target=DEST/(c['id']+'.ogg');encoded=encode(path,target,c['id'],frames/RATE)
        if abs(encoded['duration']-(frames+release)/RATE)>2/RATE:raise ValueError('Song chunk duration mismatch')
        results.append({'id':c['id'],'block':c['block'],'role':c['role'],'asset':aid,
            'beats':c['beats'],'bpm':130,'musicalFrames':frames,'musicalDuration':frames/RATE,
            'songIndex':index,'songPCM_SHA256':full_hash,'continuousPerformance':True,
            'sourceFrameRange':[offset,offset+frames],'internalZeroTail':not last,
            'path':str(target.relative_to(ROOT)),'noteSHA256':c['noteSHA256'],
            'rendererRevision':LOCK['rendererVersion'],'patchRevision':PATCHES['revision']+'-'+PATCH_SHA[:12],
            'pcmSHA256':sha(path.read_bytes()),'peak':float(abs(part).max()),
            'rms':float(np.sqrt((part*part).mean())),'dc':float(abs(part.mean(axis=0)).max()),**encoded})
        offset+=frames
    if body_hash.hexdigest()!=full_hash or offset!=total_frames:
        raise ValueError('Chunk bodies do not reconstruct the continuous song PCM: '+aid)
    return results

def voice_gate(surge,work):
    receipt={};measures=[];sections=[];pitches=[62,62,69,64,38,45,38,36,46]
    for i,v in enumerate(PATCHES['voices']):
        pitch=pitches[v['logicalInstrument']];duration=3.6 if v['name']=='acid' else 1.6;gate=3 if v['name']=='acid' else 1
        pcm=render_voice(surge,v['name'],[(0,gate,pitch,110)],duration,42,receipt=receipt)
        repeated=render_voice(surge,v['name'],[(0,gate,pitch,110)],duration,42)
        if not np.array_equal(pcm,repeated):raise ValueError('Nonreproducible voice: '+v['name'])
        peak=float(abs(pcm).max());rms=float(np.sqrt((pcm*pcm).mean()))
        if not np.isfinite(pcm).all() or peak>.82 or rms<.0002:raise ValueError('Silent/invalid voice: '+v['name'])
        metric={'name':v['name'],'logicalInstrument':v['logicalInstrument'],'peak':peak,'rms':rms,'deterministic':True}
        if v['name']=='acid':
            f,t,z=stft(pcm.mean(axis=1),RATE,nperseg=2048,noverlap=1024);power=abs(z)**2
            cent=(f[:,None]*power).sum(axis=0)/(power.sum(axis=0)+1e-20)
            low,high=np.percentile(cent[(t>.45)&(t<2.9)],[10,90]);ratio=float(high/max(1,low))
            metric['heldSpectralCentroid10Hz']=float(low);metric['heldSpectralCentroid90Hz']=float(high);metric['movementRatio']=ratio
            if ratio<1.3:raise ValueError('Acid cutoff does not materially move over held notes')
        measures.append(metric);sections.append(pcm)
    # Exercise a different heap/render order after spectral analysis too.
    for i in reversed(range(len(PATCHES['voices']))):
        v=PATCHES['voices'][i];duration=3.6 if v['name']=='acid' else 1.6;gate=3 if v['name']=='acid' else 1
        if not np.array_equal(sections[i],render_voice(surge,v['name'],[(0,gate,pitches[v['logicalInstrument']],110)],duration,42)):
            raise ValueError('Render-order dependent voice: '+v['name'])
    (work/'patch-parameters.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return measures,sections

def write_runtime(manifest):
    runtime={'schema':1,'revision':manifest['revision'],'catalogRevision':manifest['catalogRevision'],'patchRevision':manifest['patchRevision'],
             'bpm':manifest['bpm'],'bridge':{'duration':manifest['bridge']['duration'],'peak':manifest['bridge']['decodedPeak']},
             'clips':{r['id']:{'beats':r['beats'],'duration':r['duration'],'peak':r['decodedPeak'],'tailPeak':r['decodedTailPeak'],**({'musicalFrames':r['musicalFrames']} if 'musicalFrames' in r else {})} for r in manifest['clips']}}
    (BUNDLE/'render.lua').write_text('return [==['+json.dumps(runtime,separators=(',',':'))+']==]\n')

def refresh_join_metadata():
    manifest=json.loads(MANIFEST.read_text())
    def measure(c):
        path=ROOT/c['path']
        if sha(path.read_bytes())!=c['sha256']:raise ValueError('Changed bank: '+c['id'])
        raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(path),'-f','f32le','-acodec','pcm_f32le','-'])
        pcm=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
        if abs(float(abs(pcm).max())-c['decodedPeak'])>1e-7:raise ValueError('Changed decode: '+c['id'])
        c['decodedTailPeak']=tail_peak(pcm,c['musicalDuration'])
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(measure,manifest['clips']))
    manifest['rendererSHA256']=sha(Path(__file__).read_bytes()+(ROOT/'tools/music/surge/bank.py').read_bytes())
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n');write_runtime(manifest)
    print(json.dumps({'metadataOnly':True,'clips':len(manifest['clips']),'unchangedAudioBytes':manifest['totalBytes']}))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--surge-module',type=Path)
    parser.add_argument('--refresh-join-metadata',action='store_true',help='Decode committed audio to refresh conservative tail peaks; do not render or encode')
    parser.add_argument('--work',type=Path,default=ROOT/'build/ms2-surge');parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--limit',type=int,help='Smoke render only; does not publish a manifest or runtime bank')
    args=parser.parse_args()
    if args.refresh_join_metadata:refresh_join_metadata();return
    if not args.surge_module:parser.error('--surge-module is required for rendering')
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=True);DEST.mkdir(parents=True,exist_ok=True)
    surge=load_surge(args.surge_module);catalog,bank=clips();voices,isolated=voice_gate(surge,work)
    renderer_hash=sha(Path(__file__).read_bytes()+(ROOT/'tools/music/surge/bank.py').read_bytes())
    render_fingerprint=sha((PATCH_SHA+LOCK['bindingPatchSHA256']+renderer_hash).encode())
    selected=bank[:args.limit] if args.limit else bank
    results=[]
    if catalog.get('songFirst'):
        score=json.loads((ROOT/'docs/MS3_SONG_SCORE.json').read_text())
        if score['catalogRevision']!=catalog['revision']:raise ValueError('Song score/catalog mismatch')
        tasks=[(a,score['songs'][aid],[c for c in bank if c['asset']==aid],str(args.surge_module.resolve()),str(work),render_fingerprint)
               for aid,a in sorted(catalog['assets'].items())]
        if args.limit:tasks=tasks[:args.limit]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for i,rows in enumerate(pool.map(render_song,tasks),1):
                results.extend(rows)
                print(f'Rendered complete song {i}/{len(tasks)}; {sum(r["bytes"] for r in results):,} bytes',flush=True)
    else:
        tasks=[(c,catalog['bpm'],str(args.surge_module.resolve()),str(work),render_fingerprint) for c in selected]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for i,result in enumerate(pool.map(render_clip,tasks,chunksize=4),1):
                results.append(result)
                if i%50==0 or i==len(tasks):print(f'Rendered {i}/{len(tasks)}; {sum(r["bytes"] for r in results):,} bytes',flush=True)
    if args.limit:
        print('Smoke mean bytes:',sum(r['bytes'] for r in results)//len(results),'estimated bank bytes:',sum(r['bytes'] for r in results)//len(results)*len(bank));return
    # Bounded quiet D/A ambient bed drawn from the same synthetic string patch.
    drone=render_voice(surge,'strings',[(0,8,50,60),(0,8,57,45)],8.6,7919,'T0')[RATE:RATE*5]
    drone,_=condition(drone,tail_fade=False)
    width=round(.08*RATE);fade=np.linspace(0,1,width)[:,None]
    loop=drone[width:].copy();loop[-width:]=drone[-width:]*(1-fade)+drone[:width]*fade
    wav_write(work/'bridge.wav',loop)
    bridge=encode(work/'bridge.wav',DEST/'bridge.ogg','bridge');bridge['path']=str((DEST/'bridge.ogg').relative_to(ROOT))
    total=sum(r['bytes'] for r in results)+bridge['bytes']
    if total>LOCK['packageBudgetBytes']:raise ValueError(f'Encoded bank {total:,} exceeds selected {LOCK["packageBudgetBytes"]:,}-byte budget')
    revision='ms2-surge-'+sha(json.dumps([(r['id'],r['sha256']) for r in results]+[('bridge',bridge['sha256'])]).encode())[:16]
    manifest={'schema':1,'revision':revision,'catalogRevision':catalog['revision'],'rendererRevision':LOCK['rendererVersion'],
              'rendererSHA256':renderer_hash,'patchRevision':PATCHES['revision']+'-'+PATCH_SHA[:12],'patchSHA256':PATCH_SHA,
              'surge':{**LOCK,'reportedBuildVersion':surge.getVersion()},'encoder':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],
              'toolchain':{'python':platform.python_version(),'system':platform.system(),'architecture':platform.machine(),
                           'numpy':np.__version__,'scipy':scipy.__version__},
              'sampleRate':RATE,'channels':2,'bpm':catalog['bpm'],'clipCount':len(results),'fileCount':len(results)+1,
              'totalBytes':total,'largestBytes':max(r['bytes'] for r in results),'averagePhraseBytes':sum(r['bytes'] for r in results)/len(results),
              'voices':voices,'bridge':bridge,'clips':results}
    # The complete new bank passed before retiring old short recordings.
    keep={r['id']+'.ogg' for r in results}|{'bridge.ogg'}
    for old in DEST.glob('*.ogg'):
        if old.name not in keep:old.unlink()
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    write_runtime(manifest)
    # Representative ordered listening evidence: Chill, isolated voices, roles.
    audition=[];cues=[];offset=0
    def append(label,pcm):
        nonlocal offset
        cues.append({'label':label,'seconds':offset});audition.append(pcm);audition.append(np.zeros((round(.15*RATE),2)));offset+=(len(pcm)/RATE+.15)
    for role in ['T0']:
        r=next(r for r in results if r['block']=='a' and r['role']==role);append('Block A '+role,wav_read(work/(r['id']+'.wav')))
    for v,pcm in zip(PATCHES['voices'],isolated):append(v['name'],pcm*PATCHES['masterGain'])
    for role in ['T1','T2','T3','BOSS','VICTORY']:
        r=next(r for r in results if r['block']=='a' and r['role']==role);append('Block A '+role,wav_read(work/(r['id']+'.wav')))
    wav_write(work/'audition.wav',np.concatenate(audition));encode(work/'audition.wav',ROOT/'docs/validation/MS2_SURGE_AUDITION.ogg','audition')
    (ROOT/'docs/validation/MS2_SURGE_AUDITION.json').write_text(json.dumps({'cues':cues,'duration':offset,'bankRevision':revision},indent=2)+'\n')
    print(json.dumps({'revision':revision,'files':len(results)+1,'bytes':total,'voices':voices}),flush=True)

if __name__=='__main__':main()
