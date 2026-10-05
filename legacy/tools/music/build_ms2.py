#!/usr/bin/env python3
"""Compile the author's nested MIDI ZIP or extracted MIDI folder into MS2.

Reproducible offline curation: paired stems, D-Dorian pitch cleanup, 1/48-beat
timing, bounded orchestrated notes, two-bar phrases, source lineage and a
cadence/energy/pulse transition graph. No recordings ship with the catalog.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics
import struct
import zipfile

from midi import read, write_clip

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'gamemodes/legend_of_deborah/gamemode/lod/ms2'
PPQ, BEATS, TICKS = 48, 8, 384
ROLES = {'chill':'T0', 't2':'T1', 't3':'T2', 't4':'T3', 'boss':'BOSS', 'fanfare':'VICTORY'}
SCALE = (0, 2, 3, 5, 7, 9, 10)  # D Dorian: D E F G A B C.
INSTRUMENTS = ('acid','industrial','strings','brass','bass','tom','snare','kick','hat')
LIMITS = {0:1, 1:3, 2:3, 3:2, 4:1, 5:2, 6:1, 7:1, 8:1}


def compact(obj):
    return json.dumps(obj, separators=(',',':'), ensure_ascii=True, sort_keys=True)


def inputs(path):
    """Walk nested zips in memory; reject bombs, absolute/traversal filenames."""
    budget, seen, result = [0, 0], set(), []
    def visit(name, data, depth=0):
        budget[0] += len(data)
        budget[1] += 1
        if budget[0] > 256_000_000 or budget[1] > 4096 or depth > 3:
            raise ValueError('MIDI archive work/expanded-byte limit exceeded')
        name = name.replace('\\', '/')
        if name.startswith('/') or '..' in name.split('/'):
            raise ValueError('unsafe archive path')
        if name.lower().endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for item in sorted(z.infolist(), key=lambda i:i.filename):
                    if item.is_dir(): continue
                    # MP3/WAV stems are intentionally never read or shipped.
                    if not item.filename.lower().endswith(('.zip','.mid','.midi')): continue
                    if item.file_size > 64_000_000 or budget[0]+item.file_size > 256_000_000:
                        raise ValueError('oversized archive member')
                    visit(name+'/'+item.filename, z.read(item), depth+1)
        elif name.lower().endswith(('.mid','.midi')):
            digest = hashlib.sha256(data).hexdigest()
            match = re.search(r'Block ([A-H]) (Chill|T2|T3|T4|Boss|Fanfare) \(([^)]+)\)', name, re.I)
            if not match: raise ValueError('unrecognized MIDI stem name: '+name)
            block, role, stem = match.groups()
            identity = (block.lower(), ROLES[role.lower()], stem.lower(), digest)
            if identity in seen: return
            seen.add(identity)
            result.append((identity, data, name))
    if path.is_dir():
        for f in sorted(path.rglob('*')):
            if f.is_file() and f.suffix.lower() in ('.mid','.midi','.zip'):
                visit(f.relative_to(path).as_posix(), f.read_bytes())
    else: visit(path.name, path.read_bytes())
    return result


def snap(pitch):
    # Preserve pitch class where it is in the declared mode; repair conversion
    # semitone artifacts conservatively, preferring the lower neighbor on ties.
    return min((p for p in range(pitch-2,pitch+3) if (p-2)%12 in SCALE), key=lambda p:(abs(p-pitch),p))


def route(stem, note):
    start, duration, pitch, velocity, channel, _ = note
    if channel == 9 or stem in ('drums','percussion'):
        if pitch in (35,36): return 7,36
        if pitch in (37,38,39,40,54,60,61,62): return 6,38
        if pitch in (41,43,45,47,48,50,64,65,66): return 5, {41:41,43:43,45:45,47:47,48:48,50:50}.get(pitch,45)
        return 8,46 if pitch in (46,49,51,52,53,55,57,59) else 42
    if stem == 'bass': inst, lo, hi = 4,28,52
    elif stem in ('strings','vocals','backing vocals'): inst, lo, hi = 2,48,84
    elif stem in ('brass','woodwinds'): inst, lo, hi = 3,48,79
    elif stem == 'guitar': inst, lo, hi = 1,43,76
    elif stem == 'fx': inst, lo, hi = 1,48,72
    elif stem == 'keyboard':
        inst, lo, hi = (1,43,76) if duration >= .75 else (0,48,79)
    else: inst, lo, hi = 0,48,79
    pitch = snap(pitch)
    while pitch < lo: pitch += 12
    while pitch > hi: pitch -= 12
    return inst, pitch


def curate(stems, role, max_note_ticks=TICKS):
    events = {}
    for stem, midi in stems:
        for note in midi.notes:
            start, duration, _, velocity, _, _ = note
            percussion = note[4] == 9 or stem in ('drums','percussion')
            if (duration < .035 and not percussion) or velocity < 25: continue
            inst, pitch = route(stem,note)
            # Melodic timing retains 1/48 beat; hits are snapped to sixteenths.
            grid = 12 if inst >= 5 else 3
            tick = int(round(start*PPQ/grid))*grid
            length = max(3,min(max_note_ticks,int(round(duration*PPQ/3))*3))
            if inst >= 5: length = 6 if inst != 8 or pitch == 42 else 18
            velocity = min(112, max(32, velocity))
            key = tick,inst,pitch
            previous = events.get(key)
            if previous is None or velocity > previous[4]:
                events[key] = [tick,length,inst,pitch,velocity]
    ordered = sorted(events.values(),key=lambda n:(n[0], n[2],-n[4], n[3]))
    selected, sounding, recent = [], defaultdict(list), {}
    for n in ordered:
        t,d,inst,p,v = n
        # Acoustic transcriptions often repeat one held note hundreds of times.
        if t-recent.get((inst,p),-1000) < (6 if inst < 5 else 12): continue
        live = [x for x in sounding[inst] if x[0]+x[1] > t]
        if len(live) >= LIMITS[inst]:
            # Mono voices use last-note priority. Chords retain strong voices.
            if LIMITS[inst] == 1:
                if any(old[0] == t for old in live): continue
                for old in live: old[1] = max(1,t-old[0])
            elif live and min(x[4] for x in live) < v:
                old = min(live,key=lambda x:x[4]);old[1] = max(1,t-old[0])
            else: continue
        sounding[inst] = [x for x in live if x[0]+x[1] > t]
        sounding[inst].append(n);selected.append(n);recent[inst,p] = t
    return selected


def features(notes, beats=BEATS):
    profile = [0]*12
    for t,d,i,p,v in notes:
        if i < 5: profile[p%12] += min(d,PPQ*2)*v
    total = sum(profile) or 1
    pc = [round(n/total,4) for n in profile]
    beginning = [n for n in notes if n[0]<PPQ]
    ending = [n for n in notes if n[0]+n[1]>beats*PPQ-PPQ]
    def root(ns):
        bass = [n for n in ns if n[2]==4]
        melody = [n for n in ns if n[2]<5]
        return min(bass,key=lambda n:n[3])[3]%12 if bass else (Counter(n[3]%12 for n in melody).most_common(1) or [(2,0)])[0][0]
    drums = [n for n in notes if n[2]>=5]
    pulse = len({n[0]//48 for n in drums})/beats
    energy = min(1,.55*len(notes)/180+.25*len(drums)/48+.2*sum(n[4] for n in notes)/(max(1,len(notes))*127))
    return dict(energy=round(energy,3),pulse=round(pulse,3),entry=root(beginning),exit=root(ending),pc=pc)


def write_direction(catalog, payloads, report, path):
    """Readable musical direction alongside the complete per-clip JSON catalog."""
    labels={'T0':'Chill / Tension 1','T1':'Tension 2','T2':'Tension 3','T3':'Tension 4','BOSS':'Boss','VICTORY':'Fanfare'}
    rows=[
        '# Music System 2 — core clip catalog and direction', '',
        f"Revision `{catalog['revision']}`. {report['midi_files']} original MIDI stems → "
        f"{report['blocks']} blocks / {report['arrangements']} arrangements → {report['clips']:,} curated phrases / {report['notes']:,} notes.", '',
        'All melodic material uses D Dorian (D E F G A B C), on one shared '
        f"{catalog['bpm']} BPM grid. Repeated phrases receive new performance variation. "
        'The author’s recognizable families and ostinati remain the selection unit.', '',
        '| Role | Use | Direction |',
        '| --- | --- | --- |',
        '| Chill / Tension 1 (T0) | Staging, relaxed exploration, post-fanfare | Quieter half of the authored Chill passages; retain harmony/melody with sparse, soft percussion. |',
        '| Tension 2 (T1) | Alertness / first pressure step | Enter a pulsed interior phrase. Favor cadence-compatible neighbors and keep the motif legible. |',
        '| Tension 3 (T2) | Sustained danger | Keep rhythmic pulse as pressure eases within combat; change density through authored material and gentle performance variation. |',
        '| Tension 4 (T3) | Desperation | Stronger pulsed orchestration; only confirmed critical combat permits the small pitch/dynamics lift. |',
        '| Boss | Existing active boss authority | Dedicated arena arrangement, on the same clock/mode; avoid shrill brass and retain bass/kick headroom. |',
        '| Fanfare | Accepted rescue / cash receipt | Coherent twelve-beat authored beginning, once, then the next floor’s Chill. |', '',
        '## Arrangement inventory', '',
        'Energy is a structural density/velocity score from 0–1, not measured loudness. '
        'Pulse is the fraction of beats containing percussion. Primary colors rank '
        'melodic instruments by held-note duration × velocity. These are curation '
        'heuristics; the native listening gate remains the authority for the final mix.', '',
        '| Arrangement | Phrases | Median energy | Median pulse | Primary colors |',
        '| --- | ---: | ---: | ---: | --- |',
    ]
    role_order=('T0','T1','T2','T3','BOSS','VICTORY')
    examples=[]
    for block in sorted(catalog['blocks']):
        for role in role_order:
            asset=catalog['assets'][catalog['blocks'][block]['roles'][role]]
            clips=asset['clips']; energy=statistics.median(c['energy'] for c in clips)
            pulse=statistics.median(c['pulse'] for c in clips);colors=Counter()
            for clip in clips:
                for _,duration,inst,_,velocity in payloads[clip['id']]:
                    if inst<5: colors[INSTRUMENTS[inst]]+=duration*velocity
            rows.append(f"| Block {block.upper()} · {labels[role]} | {len(clips)} | {energy:.3f} | {pulse:.3f} | {', '.join(i for i,_ in colors.most_common(3))} |")
            clip=min(clips,key=lambda c:(abs(c['energy']-energy),c['id']))
            examples.append((asset,clip))
    rows.extend(['', '## Compatible phrase examples', '',
                 'The runtime ranks up to six successors for every phrase. Ranking rewards '
                 'overlapping pitch-class profiles, nearby exit/entry roots, small energy '
                 'moves and compatible source adjacency. The composer excludes the three '
                 'most recent phrases when enough alternatives exist, then varies its '
                 'choice. The full graph, source offsets, pitch-class profiles and SHA-256 '
                 'lineage are in [MS2_CATALOG.json](MS2_CATALOG.json).', '',
                 '| Representative phrase | Source start (beats) | Preferred next phrase | Circumstance |',
                 '| --- | ---: | --- | --- |'])
    for asset,clip in examples:
        next_id=clip['next'][0] if asset['loop'] else 'next floor’s Chill'
        circumstance='continue this pressure class' if asset['role'] not in ('T0','VICTORY') else 'remain calm' if asset['role']=='T0' else 'accepted victory receipt, then AUTO'
        rows.append(f"| `{clip['id']}` | {clip['offset']:g} | {next_id} | {circumstance} |")
    rows.extend(['', '## Between arrangements', '',
                 '| Change | Musical handoff |', '| --- | --- |',
                 '| Pressure rises / falls | Existing server hysteresis chooses the role; change phrase at the next shared bar, retaining queued lead-in and short release tails. Tension decreases within combat keep a pulse. |',
                 '| Staging → portal | Keep the first floor’s block and its musical position where the role remains Chill; enter combat material on the grid when pressure calls for it. |',
                 '| Stairs / reversal | The two frozen floor blocks share the same beat clock and D-Dorian mode; square-root gain weights blend them. Reversing a crossing reuses the live lanes. |',
                 '| Boss begins / ends | Select the existing universal or assigned boss arrangement on the shared bar. Boss defeat alone cannot invent victory. |',
                 '| Rescue / cash → fanfare → Chill | Admit the fanfare once for the server’s accepted receipt; its twelve beats lead into the upcoming first floor’s calm arrangement. |',
                 '| Timer expires soon | Slew tempo toward a ceiling of +6%; deadline extensions also feed this target. Keep pitch normal unless recent critical combat authorizes expression. |',
                 '| Scheduler stalls | Retain the quiet D bridge, discard missed attacks and resume at a future beat; do not burst old notes. |', '',
                 '## Instrument assignment', '',
                 '| Source stem | MS2 voice |', '| --- | --- |',
                 '| Synth and short keyboard notes | Monophonic resonant acid; occasional bar-start register inversion. |',
                 '| Guitar, FX and long keyboard notes | Gritty industrial pad / rhythm guitar; bounded chords and softened high frequencies. |',
                 '| Strings, vocals and backing vocals | Synth strings; relaxed attack in calm/staging and punchier attack in combat. |',
                 '| Brass and woodwinds | Warm heroic brass; low-pass filtering controls harshness. |',
                 '| Bass | Monophonic gritty bass with a sub oscillator; last-note priority. |',
                 '| Drum / percussion stem or MIDI drum channel | Kick, snare, two-voice tom and choking closed/open hats according to the transcribed GM pitch. |', '',
                 'Melodic semitone transcription artifacts are conservatively snapped to '
                 'D Dorian and instrument range. Dense duplicate/retrigger artifacts are '
                 'merged, weak candidates are removed, and polyphony is bounded. Very '
                 'short percussion detections are retained. Fills replace their occupied '
                 'last-beat snare/tom/hat slots instead of stacking a second kit.', '',
                 'Rebuild and operating instructions: [MUSIC_SYSTEM.md](MUSIC_SYSTEM.md).', ''])
    path.write_text('\n'.join(rows))


def export_clips(catalog, payloads, destination):
    """Deterministic portable MIDI clip bank; never loaded by the game client."""
    entries={};index=[]
    for asset in catalog['assets'].values():
        for clip in asset['clips']:
            name=f"Block-{asset['block'].upper()}/{asset['role']}/{clip['id']}.mid"
            entries[name]=write_clip(payloads[clip['id']],catalog['bpm'],clip['beats'])
            index.append(dict(block=asset['block'],role=asset['role'],file=name,**clip))
    entries['index.json']=compact(dict(schema=2,revision=catalog['revision'],ppq=48,bpm=catalog['bpm'],scale='D Dorian',clips=index)).encode()
    entries['README.txt']=('MS2 core MIDI phrases, exported from the curated event catalog.\n'
                          'Nine named instrument tracks plus a tempo/meter conductor.\n'
                          'GM programs are DAW audition hints; LoD uses its own instruments.\n'
                          'Original source lineage and direction: docs/MS2_CATALOG.json / .md.\n'
                          'Rebuild the game bank from tools/music/sources; these exports are portable editing/audition copies.\n').encode()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)


def compile_library(source, destination=DATA, sources_dir=None, report_path=None):
    stems, provenance, grouped = inputs(source), [], defaultdict(list)
    for (block,role,stem,digest), data, name in stems:
        midi = read(data)
        grouped[block,role].append((stem,midi))
        provenance.append(dict(block=block,role=role,stem=stem,sha256=digest,notes=len(midi.notes),source=name))
        if sources_dir:
            sources_dir.mkdir(parents=True,exist_ok=True)
            source_role={'T0':'Chill','T1':'T2','T2':'T3','T3':'T4','BOSS':'Boss','VICTORY':'Fanfare'}[role]
            (sources_dir/f'Block {block.upper()} {source_role} ({stem})-{digest[:12]}.mid').write_bytes(data)
    if not grouped: raise ValueError('no MIDI arrangements')
    catalog = dict(schema=2,revision='',ppq=PPQ,defaultBlock='a',scale='D Dorian',bpm=128,
                   instruments=list(INSTRUMENTS),blocks={},assets={},sets={})
    payloads, clip_rows, source_tempos = {}, [], []
    for (block,role), parts in sorted(grouped.items()):
        notes = curate(parts,role)
        source_tempos.extend(t[1] for _,m in parts for t in m.tempos if 60<=t[1]<=200)
        max_tick = max((n[0]+n[1] for n in notes),default=0)
        clips = []
        for offset in range(0,max_tick,TICKS):
            phrase = []
            for t,d,i,p,v in notes:
                if t>=offset+TICKS: break
                if t+d>offset:
                    start=max(t,offset);finish=min(t+d,offset+TICKS)
                    phrase.append([start-offset,finish-start,i,p,v])
            if len(phrase)<4 or not any(n[2]<5 for n in phrase): continue
            feat = features(phrase)
            # Combat roles need actual musical pulse. Calm retains the quietest
            # authored passages with fewer drums; energy is secondary to pulse.
            if role not in ('T0','VICTORY') and feat['pulse']<.5: continue
            cid=f'{block}_{role.lower()}_{offset//TICKS:03d}'
            clip=dict(id=cid,beats=BEATS,offset=round(offset/PPQ,3),**feat)
            phrase.sort(key=lambda n:(n[0],n[2],n[3]))
            payloads[cid]=phrase
            clips.append(clip)
        if role=='T0' and clips:
            # Use the quieter half of this actual arrangement, retaining its
            # thematic variety, rather than mislabeling the loudest breakdown.
            threshold=statistics.median(c['energy'] for c in clips)
            clips=[c for c in clips if c['energy']<=threshold]
        if role=='VICTORY' and clips:
            # A coherent contiguous 12-beat fanfare, from the authored beginning.
            offset=min((n[0] for n in notes),default=0)
            offset=(offset//PPQ)*PPQ
            phrase=[[t-offset,min(d,12*PPQ-(t-offset)),i,p,v] for t,d,i,p,v in notes if offset<=t<offset+12*PPQ]
            cid=f'{block}_victory_000';payloads[cid]=phrase
            clips=[dict(id=cid,beats=12,offset=offset/PPQ,**features(phrase,12))]
        if not clips: raise ValueError(f'no usable {block}/{role} phrases; curate source first')
        aid=f'{block}-{role.lower()}'
        catalog['assets'][aid]=dict(id=aid,block=block,role=role,loop=role!='VICTORY',bpm=128,clips=clips)
        b=catalog['blocks'].setdefault(block,dict(title=f'Block {block.upper()}',version='',roles={}))
        b['roles'][role]=aid
    for block,b in catalog['blocks'].items():
        b['roles']['INTERLUDE']=b['roles'].get('T0')
        for role in ('T0','T1','T2','T3','BOSS','VICTORY'):
            if role not in b['roles'] and block=='a': raise ValueError('Block A must contain all six default roles')
        b['version']=hashlib.sha256(compact(b['roles']).encode()).hexdigest()[:12]
    # Pairwise graph limited to this role; adjacency is preferred when compatible,
    # with cadence/pitch-class overlap and small energy moves ranking alternatives.
    for a in catalog['assets'].values():
        clips=a['clips']
        for idx,c in enumerate(clips):
            ranked=[]
            for j,d in enumerate(clips):
                if d['id']==c['id'] and len(clips)>1: continue
                circular=min((d['entry']-c['exit'])%12,(c['exit']-d['entry'])%12)
                harmonic=sum(min(x,y) for x,y in zip(c['pc'],d['pc']))
                adjacency=.18 if j==(idx+1)%len(clips) else 0
                score=harmonic-.045*circular-.25*abs(c['energy']-d['energy'])+adjacency
                ranked.append((score,d['id']))
            c['next']=[cid for _,cid in sorted(ranked,key=lambda v:(-v[0],v[1]))[:6]] or [c['id']]
            clip_rows.append(dict(block=a['block'],role=a['role'],**c,notes=len(payloads[c['id']])))
    used={c['id'] for a in catalog['assets'].values() for c in a['clips']}
    payloads={k:v for k,v in payloads.items() if k in used}
    catalog['bpm']=round(statistics.median(source_tempos)) if source_tempos else 128
    catalog['bpm']=max(116,min(140,catalog['bpm']))
    for asset in catalog['assets'].values(): asset['bpm']=catalog['bpm']
    # Files are small Lua-returned JSON shards, so native AddCSLuaFile/Workshop
    # distribution works without resource.AddFile or an external music origin.
    destination.mkdir(parents=True,exist_ok=True)
    for p in destination.glob('notes_*.lua'): p.unlink()
    page,content,pages=0,{},[]
    def flush():
        nonlocal page,content
        if not content: return
        name=f'notes_{page:03d}.lua'
        (destination/name).write_text('return [==['+compact(content)+']==]\n')
        pages.append(name);page+=1;content={}
    for cid,notes in sorted(payloads.items()):
        if len(compact({**content,cid:notes}))>46000: flush()
        content[cid]=notes
        for a in catalog['assets'].values():
            for c in a['clips']:
                if c['id']==cid: c['page']=f'notes_{page:03d}.lua'
    flush()
    catalog['pages']=pages
    catalog['revision']='ms2-'+hashlib.sha256(compact([catalog,payloads]).encode()).hexdigest()[:16]
    (destination/'catalog.lua').write_text('return [==['+compact(catalog)+']==]\n')
    (destination/'files.lua').write_text('return '+ '{'+','.join('"'+n+'"' for n in ['catalog.lua',*pages])+'}\n')
    report=dict(schema=2,revision=catalog['revision'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None,
                midi_files=len(stems),arrangements=len(catalog['assets']),blocks=len(catalog['blocks']),clips=len(payloads),
                notes=sum(len(v) for v in payloads.values()),catalog_bytes=sum((destination/name).stat().st_size for name in
                    ['catalog.lua','files.lua',*pages]+(['engine.lua'] if (destination/'engine.lua').exists() else [])),
                base_bpm=catalog['bpm'],sources=provenance,clips_catalog=clip_rows)
    if report_path:
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,indent=2)+'\n')
        write_direction(catalog,payloads,report,report_path.with_suffix('.md'))
    print(compact({k:v for k,v in report.items() if k not in ('sources','clips_catalog')}))
    return catalog,payloads,report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=DATA)
    parser.add_argument('--sources',type=Path)
    parser.add_argument('--report',type=Path,default=ROOT/'docs/MS2_CATALOG.json')
    parser.add_argument('--export-midi',type=Path,help='Optional portable ZIP of every curated MIDI phrase')
    a=parser.parse_args()
    catalog,payloads,_=compile_library(a.source,a.output,a.sources,a.report)
    if a.export_midi: export_clips(catalog,payloads,a.export_midi)
