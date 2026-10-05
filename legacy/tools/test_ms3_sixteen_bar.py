#!/usr/bin/env python3
"""Source-grounded finite authoring tests; no synth/network/game dependency."""
from collections import defaultdict
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/music'))
import remap_ms3_sixteen_bar as remap
from build_ms2 import curate, inputs, LIMITS
from midi import read

class SixteenBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.out=Path(cls.tmp.name)/'candidate'
        with contextlib.redirect_stdout(io.StringIO()):
            cls.catalog,cls.payloads,cls.audit=remap.build(ROOT/'tools/music/sources',cls.out)
        parts=defaultdict(list)
        cls.raw_midi={}
        for (b,r,s,sha),data,name in inputs(ROOT/'tools/music/sources'):
            midi=read(data);parts[b,r].append((s,midi));cls.raw_midi[sha]=data
        cls.source={k:remap.clean_retriggers(curate(v,k[1],max_note_ticks=remap.SPAN)) for k,v in parts.items()}
        cls.parts=parts
        cls.clips={c['id']:(a,c) for a in cls.catalog['assets'].values() for c in a['clips']}

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_all_original_arrangements_are_used(self):
        self.assertEqual(len(self.raw_midi),465)
        self.assertEqual(len(self.catalog['assets']),48)
        self.assertEqual(len(self.catalog['blocks']),8)
        self.assertEqual(self.audit['ordinaryClips'],157)
        self.assertEqual(self.audit['fanfares'],8)
        self.assertEqual(self.audit['notes'],sum(map(len,self.payloads.values())))
        self.assertTrue(all(1<=len(a['clips'])<=4 for a in self.catalog['assets'].values()))

    def test_real_contiguous_source_not_short_clip_tiling(self):
        for cid,(a,c) in self.clips.items():
            with self.subTest(clip=cid):
                ns=self.payloads[cid];offset=round(c['offset']*48)
                raw=remap.cut(self.source[a['block'],a['role']],offset,c['beats']*48)
                allowed={(t,d,i,p):v for t,d,i,p,v in raw}
                self.assertTrue(all((t,d,i,p) in allowed and v<=allowed[t,d,i,p] for t,d,i,p,v in ns))
                self.assertEqual(c['sourceRangeBeats'],[c['offset'],c['offset']+c['beats']])
                if a['loop']:
                    self.assertEqual(c['beats'],64)
                    self.assertEqual(offset%remap.SPAN,0)
                    self.assertEqual({n[0]//(16*48) for n in ns if n[2]<5},{0,1,2,3})
                    eight_beat_cells=[remap.cut(ns,j*384,384) for j in range(8)]
                    self.assertGreater(len({remap.digest(x) for x in eight_beat_cells}),1)
                else:self.assertEqual(c['beats'],12)

    def test_all_midi_roundtrips_have_nine_parts_and_exact_duration(self):
        with zipfile.ZipFile(self.out/'MS3_16_BAR_MIDI_CANDIDATES.zip') as z:
            count=0
            for name in z.namelist():
                if not name.endswith('.mid') or name.startswith('Bridges/'):continue
                cid=Path(name).stem;a,c=self.clips[cid];midi=read(z.read(name))
                self.assertEqual(midi.end,c['beats'],cid)
                self.assertEqual(midi.names[1:],list(remap.INSTRUMENTS),cid)
                notes=sorted([round(t*48),round(d*48),track-1,p,v] for t,d,p,v,ch,track in midi.notes)
                self.assertEqual(notes,sorted(self.payloads[cid]),cid)
                count+=1
            self.assertEqual(count,len(self.clips))

    def test_protected_anchor_and_foreground_are_unchanged(self):
        for cid,(a,c) in self.clips.items():
            if not a['loop']:continue
            ns=self.payloads[cid];edits=self.audit['clips'][cid]['edits']
            anchor=edits['anchor'];offset=round(c['offset']*48)
            self.assertIsNotNone(anchor,cid)
            self.assertIn(anchor['id'],c['motifs'])
            identities={(n[0],n[2],n[3]) for n in ns}
            for n in anchor['sourceNotes']:self.assertIn((n[0]-offset,n[2],n[3]),identities,cid)
            leader=remap.INSTRUMENTS.index(edits['foreground'])
            raw=remap.cut(self.source[a['block'],a['role']],offset,remap.SPAN)
            self.assertEqual(sorted(n for n in ns if n[2]==leader),sorted(n for n in raw if n[2]==leader),cid)
            self.assertEqual(edits['insertedMelodicNotes'],0)

    def test_bass_and_kick_keep_authored_foundation(self):
        for cid,(a,c) in self.clips.items():
            raw=remap.cut(self.source[a['block'],a['role']],round(c['offset']*48),c['beats']*48)
            # Calm orchestration attenuates percussion, but does not drop/move kick.
            for inst in (4,7):
                self.assertEqual([n[:4] for n in self.payloads[cid] if n[2]==inst],
                                 [n[:4] for n in raw if n[2]==inst],cid)

    def test_polyphony_note_and_shard_limits(self):
        for cid,(a,c) in self.clips.items():
            ns=self.payloads[cid]
            self.assertLessEqual(len(ns),2048,cid)
            active=defaultdict(list)
            for t,d,i,p,v in ns:
                self.assertTrue(0<=t<t+d<=c['beats']*48,cid)
                self.assertTrue(0<=i<9 and 0<=p<128 and 32<=v<=112,cid)
                active[i]=[end for end in active[i] if end>t]+[t+d]
                self.assertLessEqual(len(active[i]),LIMITS[i],cid)
        for name in self.catalog['pages']:self.assertLessEqual((self.out/'catalog'/name).stat().st_size,46020)

    def test_source_derived_bridges_are_separate_and_bounded(self):
        self.assertEqual(len(self.audit['bridges']),39)
        for fid,b in self.audit['bridges'].items():
            ns=b['notes'];start=round(b['sourceRangeBeats'][0]*48)
            raw=remap.cut(self.source[b['block'],b['role']],start,192)
            self.assertEqual(ns,[n for n in raw if n[2] in (5,6,8)])
            self.assertTrue(3<=len(ns)<=12)
            self.assertTrue(b['preserveKickAndBass'])
            self.assertTrue(all(0<=n[0]<n[0]+n[1]<=192 for n in ns))
        with zipfile.ZipFile(self.out/'MS3_16_BAR_MIDI_CANDIDATES.zip') as z:
            fills=[n for n in z.namelist() if n.startswith('Bridges/')]
            self.assertEqual(len(fills),39)
            for name in fills:self.assertEqual(read(z.read(name)).end,4)

    def test_transition_references_and_motif_evidence(self):
        for cid,(a,c) in self.clips.items():
            self.assertTrue(all(d in self.clips for d in c['next']))
            self.assertTrue(all(self.clips[d][0]['id']==a['id'] for d in c['next']))
            if a['loop']:
                self.assertTrue(c['motifs'])
                for role,choice in c['handoffs'].items():
                    target,clip=self.clips[choice['to']]
                    self.assertEqual(target['block'],a['block'])
                    self.assertEqual(target['role'],role)
                    self.assertEqual(choice['sharedMotifs'],len(set(c['motifs'])&set(clip['motifs'])))
        for block,motifs in self.audit['blockMotifs'].items():
            self.assertEqual(len(motifs),3)
            for m in motifs:
                self.assertGreaterEqual(m['occurrences'],2)
                raw=self.source[block,m['sourceRole']]
                self.assertTrue(all(n in raw for n in m['exampleNotes']))

    def test_source_hashes_and_provenance(self):
        for row in self.audit['sources']:
            self.assertEqual(hashlib.sha256(self.raw_midi[row['sha256']]).hexdigest(),row['sha256'])
        for cid,ns in self.payloads.items():self.assertEqual(remap.digest(ns),self.clips[cid][1]['noteSHA256'])
        self.assertEqual(self.audit['sourcesWithMeter'],0)
        self.assertIn('UNVERIFIED',self.audit['guide']['status'])

    def test_output_is_byte_deterministic(self):
        second=Path(self.tmp.name)/'again'
        with contextlib.redirect_stdout(io.StringIO()):remap.build(ROOT/'tools/music/sources',second)
        for p in self.out.rglob('*'):
            if p.is_file():self.assertEqual(p.read_bytes(),(second/p.relative_to(self.out)).read_bytes(),str(p))

    def test_mapped_exit_fills_replace_only_their_source_derived_drum_slots(self):
        with contextlib.redirect_stdout(io.StringIO()):
            catalog,payloads,audit=remap.build(ROOT/'tools/music/sources',Path(self.tmp.name)/'mapped',mapped_exits=True)
        self.assertEqual(len(audit['arrangedExitFills']),7)
        self.assertEqual(audit['notes'],121557)
        self.assertTrue(catalog['mappedExits'])
        for cid,notes in payloads.items():
            old=self.payloads[cid]
            self.assertEqual([n for n in notes if n[2] not in (5,6,8)],
                             [n for n in old if n[2] not in (5,6,8)],cid)
            if cid not in audit['arrangedExitFills']:
                self.assertEqual(notes,old,cid)
                continue
            fill=audit['arrangedExitFills'][cid]
            asset,clip=self.clips[cid]
            self.assertNotIn(asset['role'],('T0','VICTORY'))
            bridge=self.audit['bridges'][fill['source']]
            self.assertEqual(bridge['block'],asset['block'])
            self.assertEqual(bridge['role'],asset['role'])
            self.assertEqual([n for n in notes if n[2] in (5,6,8) and n[0]>=2880],
                             [[t+2880,d,i,p,v] for t,d,i,p,v in bridge['notes']],cid)
            handoff=clip['handoffs'][asset['role']]
            self.assertTrue(handoff['fillSuggested'])
            self.assertFalse(handoff['sourceAdjacent'])
            self.assertEqual(fill['target'],handoff['to'])

    def test_no_shipping_catalog_mutation(self):
        with self.assertRaisesRegex(ValueError,'shipping'):
            remap.build(ROOT/'tools/music/sources',ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2')
        with self.assertRaises(ValueError):remap.build(ROOT/'tools/music/sources',self.out,maximum=0)

    def test_ambiguous_same_pitch_retrigger_is_repaired(self):
        self.assertEqual(remap.clean_retriggers([[0,96,2,62,90],[48,24,2,62,80]]),
                         [[0,48,2,62,90],[48,24,2,62,80]])

    def test_legacy_curator_default_and_long_tie_handling(self):
        self.assertEqual(curate(self.parts['a','T0'],'T0'),curate(self.parts['a','T0'],'T0',max_note_ticks=384))
        # Long source sustains must survive past the retired two-bar boundary.
        long_notes=[n for ns in self.source.values() for n in ns if n[1]>384]
        self.assertGreater(len(long_notes),0)
        self.assertEqual(remap.cut([[100,600,2,62,80]],384,192),[[0,192,2,62,80]])

if __name__=='__main__':unittest.main(verbosity=2)
