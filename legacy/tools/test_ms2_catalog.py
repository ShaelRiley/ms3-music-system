#!/usr/bin/env python3
"""Bounded MIDI parsing, source lineage, reproducible curation and shipped bank."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/music'))
import midi
import build_ms2 as compiler
import song_score as longform


def vlq(n):
    out=[n&127];n >>= 7
    while n: out.insert(0,(n&127)|128);n >>= 7
    return bytes(out)


def smf(events,ppq=480,fmt=0):
    return b'MThd'+struct.pack('>IHHH',6,fmt,1,ppq)+b'MTrk'+struct.pack('>I',len(events))+events


def zip_bytes(entries):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items(): z.writestr(name,data)
    return buffer.getvalue()


def read_lua_json(path):
    return json.loads(path.read_text().split('[==[',1)[1].rsplit(']==]',1)[0])


def lua_value(value):
    """Supply Python-decoded real JSON to the Lua engine-boundary model."""
    if isinstance(value,dict):
        return '{'+','.join('['+lua_value(k)+']='+lua_value(v) for k,v in value.items())+'}'
    if isinstance(value,list): return '{'+','.join(map(lua_value,value))+'}'
    if value is None: return 'nil'
    if isinstance(value,bool): return 'true' if value else 'false'
    if isinstance(value,str): return json.dumps(value,ensure_ascii=False)
    return repr(value)


def json_keys(value):
    if isinstance(value,dict): return len(value)+sum(map(json_keys,value.values()))
    if isinstance(value,list): return len(value)+sum(map(json_keys,value))
    return 0


class Reader(unittest.TestCase):
    def test_portable_phrase_roundtrip(self):
        notes=[[0,48,0,62,100],[48,48,4,38,90],[24,6,7,36,95],[60,6,8,46,80]]
        result=midi.read(midi.write_clip(notes,130,8))
        expected=sorted((t/48,d/48,p,v,inst if inst<5 else 9,inst+1) for t,d,inst,p,v in notes)
        self.assertEqual(result.notes,expected)
        self.assertEqual(result.end,8)
        self.assertIn('MS2 D Dorian',result.names)

    def test_running_status_and_metadata(self):
        events=b'\x00\x90\x3e\x64'+vlq(240)+b'\xff\x01\x01x'+vlq(240)+b'\x3e\x00\x00\xff\x2f\x00'
        notes=midi.read(smf(events)).notes
        self.assertEqual(notes,[(0,1,62,100,0,0)])

    def test_sustain_and_retrigger(self):
        events=b'\x00\xb0\x40\x7f\x00\x90\x3e\x64'+vlq(240)+b'\x80\x3e\x00'+vlq(240)+b'\x90\x3e\x50'+vlq(240)+b'\x80\x3e\x00\x00\xb0\x40\x00'
        self.assertEqual(midi.read(smf(events)).notes,[(0,1.5,62,100,0,0),(1,.5,62,80,0,0)])

    def test_tempo_meter_program_and_end_cleanup(self):
        events=b'\x00\xff\x51\x03\x07\xa1\x20\x00\xff\x58\x04\x04\x02\x18\x08\x00\xc0\x50\x00\x90\x3e\x64'+vlq(480)+b'\xff\x2f\x00'
        result=midi.read(smf(events))
        self.assertEqual(result.tempos,[(0,120)])
        self.assertEqual(result.meters,[(0,4,4)])
        self.assertEqual(result.programs,{0:80})
        self.assertEqual(result.notes[0][1],1)

    def test_all_truncations_fail_safely(self):
        data=smf(b'\x00\x90\x3e\x64'+vlq(480)+b'\x80\x3e\x00')
        for length in range(len(data)):
            with self.subTest(length=length),self.assertRaises(ValueError): midi.read(data[:length])

    def test_unsupported_time_and_events(self):
        for data in (smf(b'',fmt=2),smf(b'',ppq=0),smf(b'',ppq=0xe728),
                     smf(b'\x00\x3e\x64'),smf(b'\x00\xf2\x01\x02'),
                     smf(b'\x81\x81\x81\x81\x01'),smf(vlq(480*32769)+b'\xff\x2f\x00')):
            with self.assertRaises(ValueError): midi.read(data)

    def test_sysex_and_all_notes_off(self):
        events=b'\x00\xf0\x02\x01\xf7\x00\x90\x3e\x64'+vlq(480)+b'\xb0\x7b\x00'
        self.assertEqual(midi.read(smf(events)).notes[0][1],1)


class Curation(unittest.TestCase):
    def test_short_transcribed_drums_are_preserved(self):
        source=midi.Midi([(0,1/480,36,90,9,0),(0,1/480,62,90,0,0)],[],[],{},[],1)
        notes=compiler.curate([('synth',source)],'T2')
        self.assertEqual(notes,[[0,6,7,36,90]])

    def test_mono_priority_and_mode_cleanup(self):
        source=midi.Midi([(0,2,63,90,0,0),(0,2,67,70,0,0),(1,1,66,100,0,0)],[],[],{},[],2)
        notes=compiler.curate([('synth',source)],'T2')
        self.assertEqual(len(notes),2)
        self.assertEqual(notes[0][1],48)
        self.assertTrue(all((n[3]-2)%12 in compiler.SCALE for n in notes))

    def test_archive_deduplication_and_ignored_recordings(self):
        data=smf(b'\x00\x90\x3e\x64'+vlq(480)+b'\x80\x3e\x00')
        inner=zip_bytes({'Block A Chill (synth).mid':data,'old.mp3':b'not a MIDI'})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'library.zip';path.write_bytes(zip_bytes({'one.zip':inner,'two.zip':inner,'empty.zip':zip_bytes({})}))
            self.assertEqual(len(compiler.inputs(path)),1)
            path.write_bytes(zip_bytes({'../Block A Chill (synth).mid':data}))
            with self.assertRaises(ValueError): compiler.inputs(path)

    def test_archive_depth_limit(self):
        data=smf(b'')
        for i in range(5): data=zip_bytes({f'layer{i}.zip':data})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'nested.zip';path.write_bytes(data)
            with self.assertRaises(ValueError): compiler.inputs(path)


class ShippedBank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2'
        cls.catalog=read_lua_json(cls.directory/'catalog.lua')
        cls.report=json.loads((ROOT/'docs/MS2_CATALOG.json').read_text())

    def test_gmod_catalog_admission_and_all_payloads(self):
        """Exercise production Lua with the full bank and GMod's 15k-key boundary."""
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp);rows=[]
            for name in ['catalog.lua',*self.catalog['pages']]:
                decoded=read_lua_json(self.directory/name)
                fixture=destination/name;fixture.write_text('return '+lua_value(decoded)+'\n')
                rows.append({'name':name,'fixture':str(fixture),'keys':json_keys(decoded)})
            # Keep the native 15,000-key regression boundary, not the retired
            # score's accidental number of keys/pages.
            rejected_pages=sum(row['keys']>15000 for row in rows[1:])
            self.assertGreater(rejected_pages,0)
            self.assertGreater(max(row['keys'] for row in rows[1:]),15000)
            decoded=read_lua_json(self.directory/'render.lua')
            fixture=destination/'render.lua';fixture.write_text('return '+lua_value(decoded)+'\n')
            rows.append({'name':'render.lua','fixture':str(fixture),'keys':json_keys(decoded)})
            script=destination/'admission.lua'
            script.write_text("""
local e=dofile('tools/music_test_fixture.lua')
local decoded={}
for _,entry in ipairs(ENTRIES) do
 local raw=dofile('gamemodes/legend_of_deborah/gamemode/lod/ms2/'..entry.name)
 decoded[raw]=entry
end
local original=util.JSONToTable
util.JSONToTable=function(raw,ignoreLimits,ignoreConversions)
 local entry=decoded[raw]
 if not entry then return original(raw,ignoreLimits,ignoreConversions) end
 if not ignoreLimits and entry.keys>15000 then return nil end
 return dofile(entry.fixture)
end
e.realBundle=true
local M=LOD.Music
local raw=assert(M.IncludeBundled('catalog.lua'))
assert((util.JSONToTable(raw)==nil)==CATALOG_REJECTED,'default native breadth matches the actual catalog size')
local rejected=0
for raw,entry in pairs(decoded) do
 if entry.name:match('^notes_') and not util.JSONToTable(raw) then rejected=rejected+1 end
end
assert(rejected==REJECTED_PAGES,'default native breadth also rejects the real note pages')
local catalog,err=M.LoadBundled()
assert(catalog,err or 'complete catalog failed native admission')
assert(table.Count(catalog.blocks)==8 and table.Count(catalog.assets)==48)
SERVER=true;CLIENT=false
LOD.RunManager={State={},GetPlayerState=function() return {} end}
player={GetAll=function() return {} end}
dofile('gamemodes/legend_of_deborah/gamemode/lod/sv_music.lua')
assert(LOD.MusicDirector.Catalog,'real server startup has the complete catalog')
CLIENT=true;SERVER=false;e.cacheOnly=true
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua')
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
local D=LOD.MusicDirector
D.ServerOn=true
local plan=assert(M.Plan(catalog,{set='all'},17,'complete-bank',4,1))
assert(e.jsonKeys(plan)<15000,'real wire plans fit the unchanged default decoder limit')
D.Plans[plan.id]=plan
D.Current={sequence=1,epoch=1,plan=plan.id,role='T0',staged=true,targets={{block=plan.floors[1],weight=1}}}
D:Tick();assert(e.panel,'real catalog starts the client renderer')
e.panel.functions['lodms2.ready']('surge-rendered',e.now);D:Sync()
assert(D.Ready and D.Synced and not D.Error,D.Error or 'real phrase data reaches playback')
local phrases=0
for id in pairs(catalog.assets) do
 local payload=assert(D:Payload(id),D.Error)
 for _,clip in ipairs(payload.clips) do
  phrases=phrases+1;assert(clip.notes==nil,'runtime never loads per-note score data')
  assert(D.RenderBank.clips[clip.id],'actual rendered phrase exists')
 end
end
assert(phrases==CLIP_COUNT,'every actual phrase admitted')
assert(table.Count(D.Pages)==0 and table.Count(D.Payloads)<=4,'runtime retains metadata only')
for _,path in ipairs(e.includeCalls) do assert(not path:find('/notes_',1,true),'runtime never decodes a note page') end
print('MS2_NATIVE_JSON PASS: actual catalog/key limits; 48 arrangements; '..phrases..' rendered phrases; no runtime note decoding')
""".replace('ENTRIES',lua_value(rows)).replace('CATALOG_REJECTED',lua_value(rows[0]['keys']>15000)).replace('REJECTED_PAGES',str(rejected_pages)).replace('CLIP_COUNT',str(self.report['clips'])))
            result=subprocess.run([sys.executable,str(ROOT/'tools/run_lua54.py'),str(script)],cwd=ROOT,
                                  text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout)

    def test_complete_bounded_lineage_and_graph(self):
        catalog=self.catalog;self.assertEqual(catalog['schema'],2)
        self.assertEqual(len(catalog['blocks']),8);self.assertEqual(len(catalog['assets']),48)
        self.assertEqual(catalog['phraseBars'],16);self.assertTrue(catalog['songFirst']);self.assertEqual(catalog['defaultBlock'],'a');self.assertEqual(catalog['scale'],'D Dorian')
        all_notes={}
        for name in catalog['pages']:
            data=(self.directory/name).read_bytes()
            self.assertLess(len(data),47000);self.assertLess(len(zlib.compress(data)),65536)
            all_notes.update(read_lua_json(self.directory/name))
        self.assertEqual({p.name for p in self.directory.glob('notes_*.lua')},set(catalog['pages']))
        used=set()
        for asset in catalog['assets'].values():
            ids={c['id'] for c in asset['clips']}
            self.assertTrue(0<len(ids)<=256);self.assertEqual(asset['bpm'],catalog['bpm'])
            for clip in asset['clips']:
                self.assertTrue(clip['beats'] in range(4,65,4) if asset['loop'] else clip['beats']==12)
                used.add(clip['id']);self.assertIn(clip['id'],all_notes)
                self.assertTrue(set(clip['next'])<=ids)
                self.assertTrue(0<=clip['energy']<=1 and 0<=clip['pulse']<=1)
                # Beat selection is source-section-level; short retained breaks may straddle a storage boundary.
                self.assertTrue(asset['songFirst'])
        self.assertEqual(set(all_notes),used)
        self.assertEqual(len(used),self.report['clips'])
        self.assertEqual(sum(map(len,all_notes.values())),self.report['notes'])
        self.assertLess(len(zlib.compress((self.directory/'catalog.lua').read_bytes())),65536)
        sources=list((ROOT/'tools/music/sources').glob('*.mid'))
        self.assertEqual(len(sources),465)
        declared={s['sha256'] for s in self.report['sources']}
        self.assertEqual({hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},declared)

    def test_source_folder_rebuild_matches_every_shipped_shard(self):
        with tempfile.TemporaryDirectory() as temp,contextlib.redirect_stdout(io.StringIO()):
            destination=Path(temp)
            catalog,_,_=longform.build(ROOT/'tools/music/sources',destination)
            destination=destination/'catalog'
            self.assertEqual(catalog['revision'],self.catalog['revision'])
            for name in ['catalog.lua','files.lua',*catalog['pages']]:
                self.assertEqual((destination/name).read_bytes(),(self.directory/name).read_bytes(),name)

    def test_portable_core_clip_bank(self):
        with zipfile.ZipFile(ROOT/'docs/MS2_CLIPS.zip') as archive:
            index=json.loads(archive.read('index.json'))
            self.assertEqual(index['revision'],self.catalog['revision'])
            self.assertEqual(len(index['clips']),self.report['clips'])
            notes=0
            for clip in index['clips']:
                exported=midi.read(archive.read(clip['file']))
                self.assertEqual(exported.end,clip['beats'])
                self.assertEqual(len(exported.names),10)
                notes+=len(exported.notes)
                self.assertTrue(all(n[4]==9 or (n[2]-2)%12 in compiler.SCALE for n in exported.notes))
            self.assertEqual(notes,self.report['notes'])

    def test_generated_control_engine_has_no_live_synthesis(self):
        source=(ROOT/'tools/music/ms2_engine.js').read_text()
        self.assertEqual((self.directory/'engine.lua').read_text(),'return [==['+source+']==]\n')
        self.assertNotIn('XMLHttpRequest',source);self.assertNotIn('fetch(',source)
        for name in ('createOscillator','createBiquadFilter','createPeriodicWave','WebSynth','NativeSynth'):
            self.assertNotIn(name,source)
        self.assertIn('surge-rendered',source)
        self.assertIn('surge-sample-clock',source)
        self.assertIn('createBufferSource',source)


if __name__=='__main__': unittest.main(verbosity=2)
