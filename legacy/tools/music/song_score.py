#!/usr/bin/env python3
"""Song-first offline score: retain source order, not ranked excerpt selection.

Shared MIDI routing/polyphony remains in build_ms2. Each retained composition is
one score for Surge; the bounded chunks are delivery units, never musical edits.
"""
from __future__ import annotations
from collections import defaultdict
import json
import math
from pathlib import Path
import shutil
from build_ms2 import inputs, curate, compact, export_clips, INSTRUMENTS, PPQ
from midi import read
from remap_ms3_sixteen_bar import clean_retriggers, cut, digest, normalized_features, ROLES, GUIDE

ROOT = Path(__file__).resolve().parents[2]
UNIT = 16 * PPQ  # Four source bars: retain isolated short breaks, omit long ones.
MAX_SPAN = 64 * PPQ


def driving_ranges(notes, end_tick, staged=False):
    """Auditable percussion proxy, not a claim of perceptual beat detection."""
    end_tick = math.ceil(end_tick / (4 * PPQ)) * 4 * PPQ
    if staged:
        return [[0, end_tick]], [], []
    cells = []
    for start in range(0, end_tick, UNIT):
        end = min(start + UNIT, end_tick)
        ns = [n for n in notes if start <= n[0] < end]
        beats = (end-start)/PPQ
        kick = len({n[0]//PPQ for n in ns if n[2] == 7})
        pulse = len({n[0]//PPQ for n in ns if n[2] >= 5})
        bars = len({n[0]//(4*PPQ) for n in ns if n[2] >= 5})
        driving = ((kick >= beats*.25 and pulse >= beats*.5 and bars >= math.ceil(beats/4*.75))
                   or (pulse >= beats*.75 and bars >= math.ceil(beats/4)))
        cells.append(dict(start=start, end=end, driving=driving, kickBeats=kick,
                          percussionBeats=pulse, percussionBars=bars))
    strong = [i for i,c in enumerate(cells) if c['driving']]
    if not strong:
        raise ValueError('No source-derived driving passage; do not fabricate a beat')
    keep = {i for i in strong}
    # A single four-bar break between driving sections belongs to the song.
    # Only longer breakdowns and non-driving introductions/outros are omitted.
    for i in range(strong[0]+1, strong[-1]):
        if not cells[i]['driving'] and cells[i-1]['driving'] and cells[i+1]['driving']:
            keep.add(i)
    ranges, skipped = [], []
    for i,c in enumerate(cells):
        target = ranges if i in keep else skipped
        if target and target[-1][1] == c['start']:
            target[-1][1] = c['end']
        else:
            target.append([c['start'], c['end']])
    return ranges, skipped, cells


def assemble(notes, ranges):
    result, timeline, position = [], [], 0
    for lo, hi in ranges:
        ns = cut(notes, lo, hi-lo)
        result.extend([[position+t,d,i,p,v] for t,d,i,p,v in ns])
        timeline.append(dict(sourceBeats=[lo/PPQ,hi/PPQ], songBeats=[position/PPQ,(position+hi-lo)/PPQ]))
        position += hi-lo
    result = clean_retriggers(sorted(result,key=lambda n:(n[0],n[2],n[3])))
    return result, position, timeline


def build(source: Path, output: Path):
    output = output.resolve()
    shipping = ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
    if output == shipping.resolve() or shipping.resolve() in output.parents:
        raise ValueError('Build into an offline directory; stage only with matching audio')
    output.mkdir(parents=True,exist_ok=True)
    parts, sources, provenance = defaultdict(list), defaultdict(list), []
    for (block,role,stem,sha),data,name in inputs(source):
        midi=read(data)
        if any(n!=4 or d!=4 for _,n,d in midi.meters):
            raise ValueError('Explicit bar mapping required: '+name)
        parts[block,role].append((stem,midi));sources[block,role].append(sha)
        provenance.append(dict(block=block,role=role,stem=stem,sha256=sha,path=name,notes=len(midi.notes)))
    if set(parts)!={(b,r) for b in 'abcdefgh' for r in ROLES}:
        raise ValueError('Original eight blocks / 48 arrangements required')
    assets, payloads, scores, audits = {}, {}, {}, {}
    for (block,role),p in sorted(parts.items()):
        original=clean_retriggers(curate(p,role,max_note_ticks=MAX_SPAN))
        end=max(t+d for t,d,*_ in original)
        if role=='VICTORY':
            lo=min(n[0] for n in original)//PPQ*PPQ
            ranges,skipped,cells=[[lo,lo+12*PPQ]],[],[]
        else:
            ranges,skipped,cells=driving_ranges(original,end,role=='T0')
        notes,span,timeline=assemble(original,ranges)
        aid=block+'-'+role.lower()
        asset=dict(id=aid,block=block,role=role,bpm=130,loop=role!='VICTORY',
                   songFirst=True,songBeats=span/PPQ,scoreSHA256=digest(notes),clips=[])
        position=0
        while position<span:
            length=min(MAX_SPAN,span-position)
            ns=cut(notes,position,length)
            # Retain every routed note; split delivery instead of deleting a melody.
            while len(ns)>2048 and length>16*PPQ:
                length-=16*PPQ;ns=cut(notes,position,length)
            if len(ns)>2048:raise ValueError('Song chunk exceeds canonical note budget: '+aid)
            cid=f'{block}_{role.lower()}_song_{len(asset["clips"]):03d}'
            clip=dict(id=cid,beats=length//PPQ,offset=position/PPQ,songIndex=len(asset['clips']),
                      musicalFrames=round((position+length)/PPQ/64*round(64*60/130*44100))-round(position/PPQ/64*round(64*60/130*44100)),
                      noteSHA256=digest(ns),**normalized_features(ns,length/PPQ))
            payloads[cid]=ns;asset['clips'].append(clip);position+=length
        for index,c in enumerate(asset['clips']):
            c['next']=[asset['clips'][(index+1)%len(asset['clips'])]['id']]
        scores[aid]=dict(notes=notes,beats=span/PPQ,sha256=digest(notes),timeline=timeline)
        retained=sum(hi-lo for lo,hi in ranges)
        driving=sum(c['end']-c['start'] for c in cells if c['driving'])
        audits[aid]=dict(sourceSHA256=sorted(sources[block,role]),sourceBeats=end/PPQ,
                        songBeats=span/PPQ,retainedSourceFraction=min(1,retained/end),
                        allDrivingCellsRetained=True,drivingBeats=driving/PPQ,
                        sourceRangesBeats=[[lo/PPQ,hi/PPQ] for lo,hi in ranges],
                        omittedRangesBeats=[[lo/PPQ,hi/PPQ] for lo,hi in skipped],
                        beatCells=[{**c,'start':c['start']/PPQ,'end':c['end']/PPQ} for c in cells],
                        sourceRoutedNotes=len(original),songNotes=len(notes),chunks=len(asset['clips']),
                        timeline=timeline,scoreSHA256=digest(notes))
        assets[aid]=asset
    blocks={b:dict(title='Block '+b.upper(),roles={r:b+'-'+r.lower() for r in ROLES},version='') for b in 'abcdefgh'}
    for b in blocks.values():
        b['roles']['INTERLUDE']=b['roles']['T0'];b['version']=digest(b['roles'])[:12]
    catalog=dict(schema=2,revision='',ppq=PPQ,defaultBlock='a',scale='D Dorian',bpm=130,
                 instruments=list(INSTRUMENTS),blocks=blocks,assets=assets,sets={},pages=[],
                 songFirst=True,phraseBars=16)
    bundle=output/'catalog';bundle.mkdir(exist_ok=True)
    for p in bundle.glob('notes_*.lua'):p.unlink()
    page={};index=0
    def flush():
        nonlocal page,index
        if not page:return
        name=f'notes_{index:03d}.lua';(bundle/name).write_text('return [==['+compact(page)+']==]\n')
        catalog['pages'].append(name);index+=1;page={}
    byid={c['id']:c for a in assets.values() for c in a['clips']}
    for cid,ns in sorted(payloads.items()):
        if len(compact({cid:ns}).encode())>46000:raise ValueError('Oversized note shard')
        if page and len(compact({**page,cid:ns}).encode())>46000:flush()
        page[cid]=ns;byid[cid]['page']=f'notes_{index:03d}.lua'
    flush()
    catalog['revision']='ms3-song-'+digest([catalog,payloads,scores])[:16]
    (bundle/'catalog.lua').write_text('return [==['+compact(catalog)+']==]\n')
    (bundle/'files.lua').write_text('return {'+','.join('"'+p+'"' for p in ['catalog.lua',*catalog['pages']])+'}\n')
    report=dict(schema=1,catalogRevision=catalog['revision'],authoringRevision='song-first-1',
                sourceMidiFiles=len(provenance),arrangements=len(assets),ordinaryClips=sum(len(a['clips']) for a in assets.values() if a['loop']),
                fanfares=8,notes=sum(map(len,payloads.values())),sources=provenance,songs=audits,
                fullSongNotes=sum(len(s['notes']) for s in scores.values()),
                guide=dict(url=GUIDE,status='Unverified: the linked video and transcript remain unavailable'),
                method='One source-ordered composition per role; canonical nine-voice routing; no per-chunk lead reassignment, motif ranking, added fill or melodic thinning. Preserve isolated four-bar breaks; omit long non-driving breaks and intros/outros outside staging. Chunk boundaries do not affect synthesis.')
    (output/'MS3_SONG_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'MS3_SONG_SCORE.json').write_text(compact(dict(catalogRevision=catalog['revision'],songs=scores))+'\n')
    export_clips(catalog,payloads,output/'MS3_SONG_CLIPS.zip')
    print(compact({k:report[k] for k in ['catalogRevision','sourceMidiFiles','arrangements','ordinaryClips','fanfares','notes','fullSongNotes']}))
    return catalog,payloads,report


def stage(catalog,payloads,report,output):
    shipping=ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
    for old in shipping.glob('notes_*.lua'):old.unlink()
    for name in ['catalog.lua','files.lua',*catalog['pages']]:shutil.copyfile(output/'catalog'/name,shipping/name)
    for name in ['MS3_SONG_AUDIT.json','MS3_SONG_SCORE.json']:shutil.copyfile(output/name,ROOT/'docs'/name)
    shutil.copyfile(output/'MS3_SONG_CLIPS.zip',ROOT/'docs/MS2_CLIPS.zip')
    summary=dict(schema=2,revision=catalog['revision'],midi_files=report['sourceMidiFiles'],arrangements=48,blocks=8,
                 clips=len(payloads),notes=report['notes'],base_bpm=130,sources=report['sources'],
                 clips_catalog=[dict(block=a['block'],role=a['role'],notes=len(payloads[c['id']]),**c) for a in catalog['assets'].values() for c in a['clips']])
    (ROOT/'docs/MS2_CATALOG.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'tools/music/sources')
    p.add_argument('--output',type=Path,default=ROOT/'build/ms3-song')
    p.add_argument('--stage-for-render',action='store_true')
    args=p.parse_args();c,n,r=build(args.source,args.output)
    if args.stage_for_render:stage(c,n,r,args.output)
