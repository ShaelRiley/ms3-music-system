#!/usr/bin/env python3
"""Source-order and continuity contracts for the song-first score."""
from collections import defaultdict
import contextlib,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/music'))
import song_score as song
from build_ms2 import inputs,curate,LIMITS
from remap_ms3_sixteen_bar import clean_retriggers,cut,digest
from midi import read

class SongScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.out=Path(cls.tmp.name)/'songs'
        with contextlib.redirect_stdout(io.StringIO()):cls.catalog,cls.payloads,cls.audit=song.build(ROOT/'tools/music/sources',cls.out)
        cls.scores=json.loads((cls.out/'MS3_SONG_SCORE.json').read_text())['songs']
        parts=defaultdict(list)
        for (b,r,s,h),raw,n in inputs(ROOT/'tools/music/sources'):parts[b,r].append((s,read(raw)))
        cls.original={b+'-'+r.lower():clean_retriggers(curate(p,r,max_note_ticks=song.MAX_SPAN)) for (b,r),p in parts.items()}
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_complete_original_library(self):
        self.assertEqual(self.audit['sourceMidiFiles'],465);self.assertEqual(len(self.catalog['assets']),48)
        self.assertEqual(self.audit['ordinaryClips'],216);self.assertEqual(self.audit['fanfares'],8)
    def test_every_driving_cell_is_retained(self):
        for aid,a in self.audit['songs'].items():
            for cell in a['beatCells']:
                if cell['driving']:self.assertTrue(any(lo<=cell['start'] and hi>=cell['end'] for lo,hi in a['sourceRangesBeats']),aid)
    def test_staging_retains_entire_routed_composition(self):
        for aid,score in self.scores.items():
            if aid.endswith('-t0'):
                self.assertEqual(sorted(score['notes']),sorted(self.original[aid]));self.assertEqual(self.audit['songs'][aid]['omittedRangesBeats'],[])
    def test_all_selected_notes_preserve_source_order_pitch_velocity(self):
        for aid,score in self.scores.items():
            ranges=[[round(lo*48),round(hi*48)] for lo,hi in self.audit['songs'][aid]['sourceRangesBeats']]
            expected,span,timeline=song.assemble(self.original[aid],ranges)
            self.assertEqual(score['notes'],expected,aid);self.assertEqual(span/48,score['beats']);self.assertEqual(score['timeline'],timeline)
            self.assertEqual(digest(expected),self.catalog['assets'][aid]['scoreSHA256'])
    def test_chunk_order_is_exhaustive_not_random(self):
        for aid,a in self.catalog['assets'].items():
            at=0;frames=0
            for index,c in enumerate(a['clips']):
                self.assertEqual(c['songIndex'],index);self.assertEqual(c['offset'],at)
                self.assertEqual(c['next'],[a['clips'][(index+1)%len(a['clips'])]['id']])
                self.assertEqual(self.payloads[c['id']],cut(self.scores[aid]['notes'],at*48,c['beats']*48))
                self.assertEqual(digest(self.payloads[c['id']]),c['noteSHA256']);at+=c['beats'];frames+=c['musicalFrames']
            self.assertEqual(at,a['songBeats']);self.assertEqual(frames,round(at/64*round(64*60/130*44100)))
    def test_full_song_ties_exist_across_transport_boundaries(self):
        crossing=0
        for aid,a in self.catalog['assets'].items():
            for c in a['clips'][1:]:
                boundary=c['offset']*48
                crossing+=sum(t<boundary<t+d for t,d,*_ in self.scores[aid]['notes'])
        self.assertGreater(crossing,100) # These gates must render once, not retrigger per chunk.
    def test_bounded_chunks_polyphony_and_shards(self):
        for aid,score in self.scores.items():
            active=defaultdict(list)
            for n in score['notes']:
                t,d,i,p,v=n;active[i]=[x for x in active[i] if x>t];active[i].append(t+d)
                self.assertLessEqual(len(active[i]),LIMITS[i],(aid,n))
        for ns in self.payloads.values():self.assertLessEqual(len(ns),2048)
        for name in self.catalog['pages']:self.assertLessEqual((self.out/'catalog'/name).stat().st_size,46020)
    def test_midi_roundtrip(self):
        byid={c['id']:c for a in self.catalog['assets'].values() for c in a['clips']}
        with zipfile.ZipFile(self.out/'MS3_SONG_CLIPS.zip') as z:
            for name in z.namelist():
                if not name.endswith('.mid'):continue
                cid=Path(name).stem;m=read(z.read(name));c=byid[cid]
                self.assertEqual(m.end,c['beats']);self.assertEqual(m.names[1:],list(song.INSTRUMENTS))
                self.assertEqual(sorted([round(t*48),round(d*48),track-1,p,v] for t,d,p,v,ch,track in m.notes),sorted(self.payloads[cid]),cid)
    def test_retained_brief_breaks_long_breaks_removed(self):
        ns=[]
        for unit in [1,2,4,7,8]:
            for beat in range(16):ns.append([unit*song.UNIT+beat*48,6,7,36,80])
        ranges,skipped,cells=song.driving_ranges(ns,10*song.UNIT)
        self.assertEqual(ranges,[[song.UNIT,5*song.UNIT],[7*song.UNIT,9*song.UNIT]])
    def test_deterministic(self):
        with contextlib.redirect_stdout(io.StringIO()):c,n,r=song.build(ROOT/'tools/music/sources',self.out/'again')
        self.assertEqual(c,self.catalog);self.assertEqual(n,self.payloads);self.assertEqual(r,self.audit)
    def test_shipping_guard(self):
        with self.assertRaises(ValueError):song.build(ROOT/'tools/music/sources',ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2')

if __name__=='__main__':unittest.main()
