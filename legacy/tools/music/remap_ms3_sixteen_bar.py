#!/usr/bin/env python3
"""Author genuine 16-bar MS3 candidates from the original MIDI stems.

This is an OFFLINE candidate builder, not a runtime switch. It reuses the
canonical MIDI reader, instrument router/curator and portable MIDI writer.
No old short-clip bank or rendered recording is an input. All ordinary clips
are contiguous 64-beat source windows. Victory remains a 12-beat one-shot.

Default outputs are isolated authoring files. --stage-for-render explicitly stages
the score; regenerate the matching Surge bank and pass integration gates before
publishing. Native listening acceptance remains a separate release gate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import zipfile
import shutil

from build_ms2 import INSTRUMENTS, LIMITS, PPQ, compact, curate, features, inputs, export_clips
from midi import read, write_clip

ROOT = Path(__file__).resolve().parents[2]
BAR = 4 * PPQ
BEATS = 64
SPAN = BEATS * PPQ
ROLES = ('T0', 'T1', 'T2', 'T3', 'BOSS', 'VICTORY')
REVISION = 'ms3-source-16-v1'
GUIDE = 'https://www.youtube.com/watch?v=8yu502IyV0o'
# Arranger choices, not quotations or claims about the unavailable video.
DIRECTION = {
    'acid': 'Primary moving motif when present; no simultaneous competing lead.',
    'industrial': 'Rhythmic/harmonic support; reduce attacks under the foreground.',
    'strings': 'Held harmonic support, or foreground for a string-led source motif.',
    'brass': 'Answers in foreground rests; avoid continuous lead doubling.',
    'bass': 'Preserve the authored monophonic foundation and contour.',
    'tom': 'Source-derived punctuation and optional neutral transition fill.',
    'snare': 'Preserve the groove; fill replaces occupied slots, never another kit.',
    'kick': 'Preserve the authored pulse; no synthetic blanket four-on-the-floor.',
    'hat': 'Timekeeping with reduced calm density and bounded transition activity.',
}


def digest(value):
    return hashlib.sha256(compact(value).encode()).hexdigest()


def cut(notes, offset, length):
    """Contiguous extraction; clip ties at edges, never tile or time-stretch."""
    return [[max(t, offset)-offset, min(t+d, offset+length)-max(t, offset), i, p, v]
            for t, d, i, p, v in notes if t < offset+length and t+d > offset]


def clean_retriggers(notes):
    """Trim same-voice/same-pitch overlaps before a retrigger.

MIDI note-off has no per-note identity. Keeping an earlier same-pitch gate
across a new onset makes both export/readback and a synth's release ambiguous.
Only note-offs are shortened; no onset, pitch or velocity is changed.
"""
    result = [n[:] for n in notes]
    previous = {}
    for n in result:
        key = (n[2],n[3])
        old = previous.get(key)
        if old is not None and old[0]+old[1]>n[0]:
            old[1] = n[0]-old[0]
        previous[key] = n
    return [n for n in result if n[1]>0]


def grams(notes):
    """Five-onset interval/rhythm fingerprints; not semantic motif recognition.

Instrument identity is retained to avoid mistaking bass/guitar doubling for a
cross-role theme. Velocity, absolute octave and gate lengths are ignored only
for matching; all those source values remain in the actual music.
"""
    output = []
    for inst in range(5):
        strongest = {}
        for n in notes:
            if n[2] != inst:
                continue
            if n[0] not in strongest or (n[4], n[3]) > (strongest[n[0]][4], strongest[n[0]][3]):
                strongest[n[0]] = n
        line = [strongest[t] for t in sorted(strongest)]
        for k in range(len(line)-4):
            group = line[k:k+5]
            if len({n[3] % 12 for n in group}) < 3:
                continue
            if group[-1][0]-group[0][0] > BAR*4:
                continue
            intervals = tuple(group[j+1][3]-group[j][3] for j in range(4))
            rhythm = tuple(round((group[j+1][0]-group[j][0])/6) for j in range(4))
            if 0 in rhythm or any(abs(x)>19 for x in intervals):
                continue
            key = (inst, intervals, rhythm)
            output.append((key, group))
    return output


def discover(arrangements):
    """Rank block-specific recurring cells; preserve provenance and uncertainty."""
    occurrences = defaultdict(list)
    for (block, role), data in sorted(arrangements.items()):
        if role == 'VICTORY':
            continue
        data['grams'] = grams(data['notes'])
        for key, ns in data['grams']:
            occurrences[key].append((block, role, ns))
    signatures = {}
    for block in sorted({k[0] for k in arrangements}):
        ranked = []
        for key, rows in occurrences.items():
            own = [r for r in rows if r[0] == block]
            if len(own) < 2:
                continue
            roles = len({r[1] for r in own})
            other_blocks = len({r[0] for r in rows if r[0] != block})
            # Specificity matters: don't label a ubiquitous scale run a signature.
            score = (min(len(own), 24) + 8*roles)/(1+other_blocks*3)
            ranked.append((score, key, own, other_blocks))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        selected = []
        used_shapes = set()
        for score, key, rows, other_blocks in ranked:
            shape = key[1:]
            if shape in used_shapes:
                continue
            used_shapes.add(shape)
            _, role, ns = rows[0]
            selected.append(dict(id=block+'-motif-'+str(len(selected)+1),
                                 instrument=INSTRUMENTS[key[0]], intervals=list(key[1]),
                                 rhythmEighthBeatUnits=list(key[2]), score=round(score, 3),
                                 occurrences=len(rows), roles=sorted({r[1] for r in rows}),
                                 otherBlocks=other_blocks, sourceRole=role,
                                 sourceBeat=ns[0][0]/PPQ,
                                 exampleNotes=[n[:] for n in ns],
                                 _key=key))
            if len(selected) == 3:
                break
        signatures[block] = selected
    return signatures


def source_coverage(notes, offset, length):
    # A declared MIDI end alone cannot certify that a window contains music.
    ns = cut(notes, offset, length)
    active = {min(15, t//BAR) for t, d, i, p, v in ns}
    melodic_quarters = {t//(BAR*4) for t,d,i,p,v in ns if i<5}
    return len(active), len(melodic_quarters)


def motif_hits(data, offset, length, signatures):
    wanted = {m['_key']: m['id'] for m in signatures}
    result = []
    for key, group in data.get('grams', []):
        if group[0][0] >= offset and group[-1][0] < offset+length and key in wanted:
            result.append((wanted[key], group))
    return result


def cap_polyphony(notes):
    """No extra voices are created by rearrangement or a fill replacement."""
    result, live = [], defaultdict(list)
    for n in sorted(notes, key=lambda x: (x[0],x[2],-x[4],x[3])):
        t,d,i,p,v = n
        active = [old for old in live[i] if old[0]+old[1] > t]
        if len(active) >= LIMITS[i]:
            # Arrangement only subtracts; don't steal a protected melodic onset.
            continue
        result.append(n)
        live[i] = active+[n]
    return sorted(result, key=lambda x:(x[0],x[2],x[3]))


def orchestrate(raw, offset, hits, role, anchor=None):
    """Foreground plus support, in four source-contiguous four-bar sections.

Never transpose the selected motif, move its onsets, paste it across roles or
invent a melody. Subordinate-note removal is explicit in the edit audit.
"""
    protected = set()
    for _, ns in hits:
        protected.update((n[0]-offset,n[2],n[3]) for n in ns)
    # Keep a single foreground identity over the full passage. Four-bar labels
    # describe source development, not an arbitrary instrument swap every four bars.
    anchor_inst = anchor[1][0][2] if anchor else None
    motion = Counter(n[2] for n in raw if n[2] in (0,2,3))
    if anchor_inst is not None and anchor_inst < 4:
        leader = anchor_inst
    elif motion:
        leader = max(motion, key=lambda i:(motion[i], i==0, -i))
    else:
        leader = 1 if any(n[2]==1 for n in raw) else 4
    # Protect the whole source phrase in that voice, not just its five-note label.
    protected.update((n[0],n[2],n[3]) for n in raw if n[2] == leader)
    sections, selected = [], []
    for section in range(4):
        start, end = section*BAR*4, (section+1)*BAR*4
        ns = [n[:] for n in raw if start <= n[0] < end]
        lead = [n for n in ns if n[2] == leader]
        occupied = {tick//12 for t,d,i,p,v in lead for tick in range(t, min(t+d, end),12)}
        before = len(ns)
        removed, softened = Counter(), Counter()
        for n in ns:
            t,d,i,p,v = n
            identity = (t,i,p)
            is_protected = identity in protected
            busy = t//12 in occupied
            if i < 4 and i != leader and not is_protected:
                if i == 3 and busy:
                    removed['brass_under_foreground'] += 1
                    continue
                if i == 0 and busy:
                    removed['acid_competing_lead'] += 1
                    continue
                if i == 1 and busy and (t % PPQ) != 0:
                    removed['industrial_offbeat_collision'] += 1
                    continue
                # Strings are allowed to sustain beneath the foreground.
                scale = .62 if busy else .82
                n[4] = max(32, round(v*scale))
                softened[INSTRUMENTS[i]] += 1
            if role == 'T0' and i >= 5 and not is_protected:
                if i == 8 and t % 24 != 0:
                    removed['calm_hat_density'] += 1
                    continue
                n[4] = max(32, round(v*.72))
            selected.append(n)
        sections.append(dict(bars=[section*4+1,section*4+4], foreground=INSTRUMENTS[leader],
                             sourceNotes=before, removed=dict(removed), softened=dict(softened)))
    selected = cap_polyphony(selected)
    kept = {(n[0],n[2],n[3]) for n in selected}
    if not protected.issubset(kept):
        raise ValueError('Protected motif onset lost during orchestration')
    return selected, dict(sections=sections, protectedOnsets=len(protected),
                         removedNotes=len(raw)-len(selected), insertedMelodicNotes=0, foreground=INSTRUMENTS[leader],
                         anchor=None if anchor is None else dict(id=anchor[0],sourceNotes=anchor[1]))


def normalized_features(notes, beats):
    value = features(notes, beats)
    drums = [n for n in notes if n[2] >= 5]
    factor = beats/8
    value['energy'] = round(min(1, .55*len(notes)/(180*factor)+.25*len(drums)/(48*factor)
                               +.2*sum(n[4] for n in notes)/(max(1,len(notes))*127)),3)
    return value


def similarity(a, b):
    shared = len(set(a['motifs']) & set(b['motifs']))
    root_distance = min((a['exit']-b['entry'])%12,(b['entry']-a['exit'])%12)
    harmonic = sum(min(x,y) for x,y in zip(a['pc'],b['pc']))
    adjacent = a['offset']+BEATS == b['offset']
    score = harmonic + .28*min(shared,2) + .3*adjacent - .06*root_distance - .4*abs(a['energy']-b['energy'])
    return dict(score=round(score,4), sharedMotifs=shared, rootDistance=root_distance,
                sourceAdjacent=adjacent, fillSuggested=bool(not shared and root_distance>2))


def fill_cells(data):
    """Find one-bar percussion cells in this arrangement, not a generic fill."""
    result = []
    notes = data['notes']
    for offset in range(0, max(n[0]+n[1] for n in notes)-BAR+1, BAR):
        ns = [n for n in cut(notes, offset, BAR) if n[2] in (5,6,8)]
        # Require actual tom/snare activity and changing subdivisions.
        if 3 <= len(ns) <= 12 and sum(n[2] in (5,6) for n in ns) >= 2 and len({n[0] for n in ns}) >= 3:
            result.append((offset, ns))
    return result


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name,(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info,data)


def build(source: Path, output: Path, maximum: int = 4, mapped_exits: bool = False):
    if not 1 <= maximum <= 8:
        raise ValueError('maximum clips per arrangement must be in 1..8')
    # Refuse an accidental mutation of the currently working shipping catalog.
    shipping = ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
    resolved = output.resolve()
    if resolved == shipping.resolve() or shipping.resolve() in resolved.parents:
        raise ValueError('Candidate output must not overwrite the shipping MS3 catalog')
    output.mkdir(parents=True,exist_ok=True)
    arrangements = {}
    provenance = []
    for (block,role,stem,sha), data, name in inputs(source):
        midi = read(data)
        if midi.meters and any(numerator != 4 or denominator != 4 for _,numerator,denominator in midi.meters):
            raise ValueError('Non-4/4 source requires explicit bar mapping: '+name)
        a = arrangements.setdefault((block,role),dict(parts=[],source=[],end=0))
        a['parts'].append((stem,midi))
        a['end'] = max(a['end'],midi.end)
        a['source'].append(sha)
        provenance.append(dict(block=block,role=role,stem=stem,sha256=sha,path=name,notes=len(midi.notes)))
    for key, a in arrangements.items():
        a['notes'] = clean_retriggers(curate(a['parts'], key[1], max_note_ticks=SPAN))
        if not a['notes']:
            raise ValueError('Empty curated source: '+str(key))
    expected = {(b,r) for b in 'abcdefgh' for r in ROLES}
    if set(arrangements) != expected:
        raise ValueError('Expected original eight blocks and all six arrangements')
    signatures = discover(arrangements)
    assets, payloads, audit, entries = {}, {}, {}, {}
    for (block,role), data in sorted(arrangements.items()):
        aid = block+'-'+role.lower()
        asset = dict(id=aid,block=block,role=role,bpm=130,loop=role!='VICTORY',clips=[])
        if role == 'VICTORY':
            offset = (min(n[0] for n in data['notes'])//PPQ)*PPQ
            candidates = [(offset, cut(data['notes'],offset,12*PPQ),[], None)]
        else:
            ranked = []
            # Complete non-overlapping, downbeat-aligned source passages only.
            end_tick = min(round(data['end']*PPQ), max(n[0]+n[1] for n in data['notes']))
            for offset in range(0,end_tick-SPAN+1,SPAN):
                active, quarters = source_coverage(data['notes'],offset,SPAN)
                if active<12 or quarters != 4:
                    continue
                raw = cut(data['notes'],offset,SPAN)
                hits = motif_hits(data,offset,SPAN,signatures[block])
                local = [(key,ns) for key,ns in data['grams']
                         if offset <= ns[0][0] and ns[-1][0] < offset+SPAN]
                counts = Counter(key for key,_ in data['grams'])
                melodic_hits = [hit for hit in hits if hit[1][0][2] < 4]
                if melodic_hits:
                    anchor = melodic_hits[0]
                elif local:
                    key,group = max(local,key=lambda row:(row[0][0] < 4,
                        counts[row[0]], row[0][0]==0, -row[1][0][0]))
                    anchor = (block+'-cell-'+digest(key)[:12],group)
                else:
                    raise ValueError('No melodic source anchor: '+aid)
                if anchor not in hits: hits = hits+[anchor]
                ns, edits = orchestrate(raw,offset,hits,role,anchor)
                if len(ns)>2048:
                    raise ValueError(f'Candidate exceeds canonical 2048-note bound: {aid}@{offset/PPQ}')
                f = normalized_features(ns,BEATS)
                if role!='T0' and f['pulse']<.5:
                    continue
                motif_ids = sorted({m for m,_ in hits})
                # Prefer signatures and complete structure, without choosing only
                # the densest passages or the same repeated two-bar ostinato.
                bars = [digest(cut(ns,i*BAR,BAR)) for i in range(16)]
                quality = len(motif_ids)*2 + len(set(bars))/16 + active/16
                if role=='T0': quality -= f['energy']
                ranked.append((quality,offset,ns,motif_ids,edits))
            ranked.sort(key=lambda c:(-c[0],c[1]))
            candidates = [(o,ns,ids,edits) for _,o,ns,ids,edits in ranked[:maximum]]
            candidates.sort(key=lambda c:c[0])
        if not candidates:
            raise ValueError('No honest full-length source passage: '+aid)
        for offset,ns,motifs,edits in candidates:
            beats = 12 if role=='VICTORY' else BEATS
            cid = f'{block}_{role.lower()}_s16_{offset//BAR:03d}'
            file_name = f"Block-{block.upper()}/{role}/{cid}.mid"
            clip = dict(id=cid,beats=beats,offset=offset/PPQ,motifs=motifs,
                        sourceRangeBeats=[offset/PPQ,offset/PPQ+beats],
                        noteSHA256=digest(ns), **normalized_features(ns,beats))
            asset['clips'].append(clip)
            payloads[cid]=ns
            audit[cid]=dict(block=block,role=role,notes=len(ns),sourceSHA256=sorted(data['source']),
                            sourceRangeBeats=clip['sourceRangeBeats'],edits=edits,
                            contiguousSource=True,tiledShortPhrase=False,timeStretch=False,
                            quarterNoteCounts=[sum(j*BAR*4<=n[0]<(j+1)*BAR*4 for n in ns) for j in range(4)] if beats==BEATS else [])
            entries[file_name]=write_clip(ns,130,beats)
        assets[aid]=asset
    transitions, fill_audit = {}, {}
    for aid,asset in assets.items():
        for c in asset['clips']:
            ranked = [(similarity(c,d),d) for d in asset['clips'] if d['id']!=c['id']]
            ranked.sort(key=lambda item:(-item[0]['score'],item[1]['id']))
            c['next']=[d['id'] for _,d in ranked] or [c['id']]
            c['handoffs']={}
            if not asset['loop']:
                continue
            for role in ROLES[:-1]:
                dest = assets[asset['block']+'-'+role.lower()]
                pairs=[(similarity(c,d),d) for d in dest['clips'] if d['id']!=c['id']]
                pairs.sort(key=lambda item:(-item[0]['score'],item[1]['id']))
                if pairs:
                    score,d=pairs[0]
                    c['handoffs'][role]=dict(to=d['id'],**score)
            transitions[c['id']]=c['handoffs']
        # One source-derived neutral one-bar bridge per looping arrangement.
        # It is exported separately, not silently inserted on every transition.
        if asset['loop']:
            cells=fill_cells(arrangements[asset['block'],asset['role']])
            if cells:
                offset,ns=max(cells,key=lambda x:(sum(n[2]==5 for n in x[1]),-abs(len(x[1])-6),-x[0]))
                fid=aid+'-bridge'
                fill_audit[fid]=dict(block=asset['block'],role=asset['role'],sourceRangeBeats=[offset/PPQ,offset/PPQ+4],
                                     sourceSHA256=sorted(arrangements[asset['block'],asset['role']]['source']),
                                     notes=ns, replacementVoices=['tom','snare','hat'],preserveKickAndBass=True,
                                     rule='Replace matching kit slots in the final bar; never stack, extend the clock, or force an unready successor.')
                entries[f"Bridges/Block-{asset['block'].upper()}/{fid}.mid"]=write_clip(ns,130,4)
    # An authored exit fill belongs inside the rendered arrangement, not a
    # second runtime drum kit. Only weaker non-adjacent mapped exits qualify;
    # never decorate an already-contiguous phrase or every sixteen-bar edge.
    applied_fills = {}
    if mapped_exits:
        for aid, asset in assets.items():
            if not asset['loop'] or asset['role']=='T0':
                continue
            fill=fill_audit.get(aid+'-bridge')
            if not fill:
                continue
            for c in asset['clips']:
                handoff=c['handoffs'].get(asset['role'])
                if not handoff or not handoff['fillSuggested'] or handoff['sourceAdjacent']:
                    continue
                cid=c['id'];last=SPAN-BAR
                kept=[]
                for t,d,i,p,v in payloads[cid]:
                    if i in (5,6,8):
                        if t>=last:continue
                        d=min(d,last-t)
                    kept.append([t,d,i,p,v])
                # Preserve bass, kick and ALL melodic parts. The exact source
                # cell replaces only tom/snare/hat in the final bar.
                added=[[last+t,d,i,p,v] for t,d,i,p,v in fill['notes']]
                ns=clean_retriggers(cap_polyphony(kept+added))
                if len(ns)>2048:raise ValueError('Filled phrase exceeds note budget: '+cid)
                payloads[cid]=ns
                c.update(normalized_features(ns,BEATS));c['noteSHA256']=digest(ns)
                c['exitFill']=dict(source=aid+'-bridge',target=handoff['to'])
                audit[cid]['notes']=len(ns)
                audit[cid]['percussionExitReplacement']=dict(source=aid+'-bridge',atBeat=60)
                applied_fills[cid]=dict(source=aid+'-bridge',target=handoff['to'],atBeat=60,
                                       sourceRangeBeats=fill['sourceRangeBeats'],notes=added)
                entries[f"Block-{asset['block'].upper()}/{asset['role']}/{cid}.mid"]=write_clip(ns,130,64)
        # Retain source/motif-led targets, refresh their measured feature scores.
        by_id={c['id']:c for a in assets.values() for c in a['clips']}
        for a in assets.values():
            for c in a['clips']:
                for role,choice in c['handoffs'].items():
                    choice.update(similarity(c,by_id[choice['to']]))
    blocks={b:dict(title='Block '+b.upper(),roles={r:b+'-'+r.lower() for r in ROLES},version='') for b in 'abcdefgh'}
    for b in blocks.values():
        b['roles']['INTERLUDE']=b['roles']['T0']
        b['version']=digest(b['roles'])[:12]
    public_signatures={b:[{k:v for k,v in m.items() if k!='_key'} for m in ms] for b,ms in signatures.items()}
    report=dict(schema=1,authoringRevision=REVISION,bpm=130,meter=[4,4],
                meterEvidence='Source MIDIs have no meter events; retain the existing score\'s explicit 4/4 grid, not inferred MIDI metadata.',
                guide=dict(url=GUIDE,status='UNVERIFIED: full video/transcript unavailable; do not claim guide-specific implementation'),
                sourceMidiFiles=len(provenance),sourcesWithMeter=sum(bool(m.meters) for a in arrangements.values() for _,m in a['parts']),sourceNotes=sum(r['notes'] for r in provenance),
                arrangements=len(assets),ordinaryClips=sum(len(a['clips']) for a in assets.values() if a['loop']),
                fanfares=sum(len(a['clips']) for a in assets.values() if not a['loop']),
                notes=sum(len(v) for v in payloads.values()),instruments=DIRECTION,
                motifMethod='Ranked recurring five-onset interval/rhythm cells with block specificity; heuristic, not human listening acceptance.',
                blockMotifs=public_signatures,sources=provenance,clips=audit,bridges=fill_audit,arrangedExitFills=applied_fills,
                runtimeStatus='Offline arranged score; publish only with matching rendered bank and passing integration gates.')
    catalog=dict(schema=2,revision='',ppq=PPQ,defaultBlock='a',scale='D Dorian',bpm=130,
                 instruments=list(INSTRUMENTS),blocks=blocks,assets=assets,sets={},pages=[],phraseBars=16,mappedExits=mapped_exits)
    # Authoring shards retain the existing byte bound. Shipping is explicit and
    # requires a matching rendered bank; never install an isolated catalog.
    bundle=output/'catalog';bundle.mkdir(exist_ok=True)
    for p in bundle.glob('notes_*.lua'):p.unlink()
    page={};index=0
    for cid,ns in sorted(payloads.items()):
        if len(compact({cid:ns}).encode())>46000:
            raise ValueError('Single phrase exceeds bounded Lua shard: '+cid)
        if page and len(compact({**page,cid:ns}).encode())>46000:
            name=f'notes_{index:03d}.lua';(bundle/name).write_text('return [==['+compact(page)+']==]\n')
            catalog['pages'].append(name);index+=1;page={}
        page[cid]=ns
        for a in assets.values():
            for c in a['clips']:
                if c['id']==cid:c['page']=f'notes_{index:03d}.lua'
    if page:
        name=f'notes_{index:03d}.lua';(bundle/name).write_text('return [==['+compact(page)+']==]\n');catalog['pages'].append(name)
    catalog['revision']='ms3-s16-'+digest([catalog,payloads,public_signatures])[:16]
    report['catalogRevision']=catalog['revision']
    (bundle/'catalog.lua').write_text('return [==['+compact(catalog)+']==]\n')
    (bundle/'files.lua').write_text('return {'+','.join('"'+p+'"' for p in ['catalog.lua',*catalog['pages']])+'}\n')
    (output/'MS3_16_BAR_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'MS3_16_BAR_TRANSITIONS.json').write_text(json.dumps(transitions,indent=2)+'\n')
    entries['index.json']=compact(catalog).encode()
    entries['motifs.json']=compact(public_signatures).encode()
    entries['source-audit.json']=compact(report).encode()
    entries['README.txt']=(
        'MS3 source-derived 16-bar authoring candidates.\n'
        'Ordinary clips: 64 beats / 16 bars in 4/4 at 130 BPM, each a contiguous original source range.\n'
        'Victory: eight separate 12-beat one-shots, not padded into 16 bars.\n'
        'Nine named instrument parts plus conductor. MIDI GM programs are audition hints, not the Surge sound.\n'
        'Bridges/: source-derived one-bar percussion replacement candidates; never a second stacked kit.\n'
        'index.json: candidate graph and role handoffs; motifs.json and source-audit.json: provenance/edit decisions.\n'
        'This ZIP alone does not install game audio. Stage, render and validate a matching bank; native listening remains separate.\n'
        'The linked arrangement video was not accessible in full; guide-specific compliance is not claimed.\n'
    ).encode()
    write_zip(output/'MS3_16_BAR_MIDI_CANDIDATES.zip',entries)
    rows=['# MS3 — genuine 16-bar source arrangement candidates','',
          f"Revision `{catalog['revision']}`. {report['sourceMidiFiles']} original MIDIs → {report['ordinaryClips']} sixteen-bar passages + {report['fanfares']} short fanfares; {report['notes']:,} arranged notes.",'',
          '**Source arrangement report; MIDI exports alone are not an audio installation.** The linked guide could not be reviewed in full. Motif recognition below is an auditable heuristic; perceptual identity and balance require listening.','',
          '## Arrangement principles','',
          'Keep the complete 64-beat source timeline. Choose a foreground from a block motif or recurring source cell and preserve its entire voice part across the full passage. The four four-bar groups retain source development, not arbitrary lead swaps. Protect every selected motif onset, subordinate competing Acid/Brass attacks, soften harmonic support, preserve bass/kick, and reduce calm hat density. Same-pitch overlapping gates are shortened at their next source retrigger so MIDI note-offs are unambiguous. No new melodic notes or repeated two-bar tiles are manufactured. Fills are separately exported source-derived replacement candidates, not automatically played at every seam.','',
          '## Block motifs','', '| Block | Voice | Source role / beat | Intervals (semitones) | Roles with exact fingerprint |','| --- | --- | --- | --- | --- |']
    for b,ms in public_signatures.items():
        for m in ms:rows.append(f"| {b.upper()} | {m['instrument']} | {m['sourceRole']} / {m['sourceBeat']:g} | {', '.join(map(str,m['intervals']))} | {', '.join(m['roles'])} |")
    rows+=['','## Source windows','', '| Arrangement | Source starts (beats) | Length |','| --- | --- | --- |']
    for aid,a in assets.items():rows.append(f"| {aid} | {', '.join(str(c['offset']) for c in a['clips'])} | {64 if a['loop'] else 12} beats |")
    rows+=['','## Publication and listening gates','',
           'Stage the catalog only as part of the offline Surge build, with matching note/audio hashes, byte-bounded compact-tail transport, complete music/integration regressions and real sixteen-bar browser joins. The source-derived mapped exits replace percussion rather than stacking a kit. Native GMod/Steam Deck listening remains the perceptual acceptance gate; no automated result substitutes for it. The reference video has not been verified.','']
    (output/'MS3_16_BAR_DIRECTION.md').write_text('\n'.join(rows))
    print(compact({k:report[k] for k in ('catalogRevision','sourceMidiFiles','arrangements','ordinaryClips','fanfares','notes')}))
    return catalog,payloads,report


def stage_for_render(catalog, payloads, report, output):
    """Offline staging only: render and validate before committing the bank."""
    shipping=ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
    for old in shipping.glob('notes_*.lua'):old.unlink()
    for name in ['catalog.lua','files.lua',*catalog['pages']]:
        shutil.copyfile(output/'catalog'/name,shipping/name)
    (ROOT/'docs/MS3_16_BAR_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    export_clips(catalog,payloads,ROOT/'docs/MS2_CLIPS.zip')
    summary=dict(schema=2,revision=catalog['revision'],midi_files=report['sourceMidiFiles'],
                 arrangements=report['arrangements'],blocks=8,clips=len(payloads),notes=report['notes'],
                 base_bpm=catalog['bpm'],sources=report['sources'],
                 clips_catalog=[dict(block=a['block'],role=a['role'],notes=len(payloads[c['id']]),**c)
                                for a in catalog['assets'].values() for c in a['clips']])
    (ROOT/'docs/MS2_CATALOG.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'tools/music/sources')
    parser.add_argument('--output',type=Path,default=ROOT/'build/ms3-sixteen-bar')
    parser.add_argument('--maximum',type=int,default=4)
    parser.add_argument('--mapped-exits',action='store_true',help='Arrange sparse source-derived fills at weak non-adjacent exits')
    parser.add_argument('--stage-for-render',action='store_true',help='Stage offline score; matching Surge rendering and gates are mandatory before publication')
    args=parser.parse_args()
    catalog,payloads,report=build(args.source,args.output,args.maximum,args.mapped_exits)
    if args.stage_for_render:stage_for_render(catalog,payloads,report,args.output)
