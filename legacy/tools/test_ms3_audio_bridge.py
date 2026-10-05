#!/usr/bin/env python3
"""Run the production Lua-to-JavaScript audio bridge with native Base64 wrapping.

Real bank bytes cross the actual readclip callback and a JavaScript parser;
headless decoding here is not native GMod listening acceptance.
"""
import base64
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    bank = json.loads((ROOT / 'docs/MS2_SURGE_BANK.json').read_text())
    clips = [next(c for c in bank['clips'] if c['id'] == 'a_t0_song_000'),
             max(bank['clips'], key=lambda c: c['bytes'])]
    with tempfile.TemporaryDirectory(prefix='ms3-audio-bridge-') as directory:
        out = Path(directory)
        for i, clip in enumerate(clips):
            data = (ROOT / clip['path']).read_bytes()
            (out / f'{i}.ogg').write_bytes(data)
            # Facepunch util.Base64Encode defaults to RFC 2045's 76-column wrap.
            # https://wiki.facepunch.com/gmod/util.Base64Encode
            (out / f'{i}.b64').write_bytes(base64.encodebytes(data))
        script = r'''
local e=dofile('tools/music_test_fixture.lua');local check=e.check
CLIENT=true
local root='gamemodes/legend_of_deborah/gamemode/lod/'
dofile(root..'cl_music_native.lua');dofile(root..'cl_music.lua')
local D,M=LOD.MusicDirector,LOD.Music
D.ServerOn=true
local plan=M.Plan(e.catalog(),{set='all'},17,'bridge',4,1);D.Plans[plan.id]=plan
D.Current={sequence=1,epoch=1,plan=plan.id,role='INTERLUDE',staged=true,targets={{block=plan.floors[1],weight=1}},remaining=-1}
D:Tick();e.panel.functions['lodms2.ready']('surge-sample-clock',e.now);D:Sync()
local target=D.AudibleTargets[1];local clip=D.Catalog.assets[target.asset].clips[1].id
local callback=e.panel.functions['lodms2.readclip'];local panel=e.panel
local bytes,encoded,reads,reportedSize,badHeader=nil,nil,0,nil,false
local function read(path) local f=assert(io.open(path,'rb'));local value=f:read('*a');f:close();return value end
file.Size=function(path,realm)
 check(path=='sound/lod/ms2_surge/'..clip..'.ogg' and realm=='GAME','bridge keeps its authorized local path')
 return reportedSize or #bytes
end
file.Read=function() reads=reads+1;return badHeader and 'not an Ogg' or bytes end
util.Base64Encode=function(value,inline)
 check(value==bytes,'encoding receives exactly the local file')
 return inline and encoded:gsub('[\r\n]','') or encoded
end
local function save(name)
 local f=assert(io.open(OUT..'/'..name..'.js','wb'));f:write(panel.calls[#panel.calls]);f:close()
end
for i=0,1 do
 bytes=read(OUT..'/'..i..'.ogg');encoded=read(OUT..'/'..i..'.b64');e.now=e.now+.2
 callback(target.block,clip);save('allowed-'..i)
end
local before=reads;e.now=e.now+.2;callback('not-assigned',clip);save('denied')
check(reads==before,'unauthorized lane never reads a file')
reportedSize=1024*1024+1;e.now=e.now+.2;callback(target.block,clip);save('oversized')
check(reads==before,'oversized payload rejected before reading')
reportedSize=-1;e.now=e.now+.2;callback(target.block,clip);save('missing')
check(reads==before,'missing payload never read')
reportedSize=nil;badHeader=true;e.now=e.now+.2;callback(target.block,clip);save('bad-header');badHeader=false
local calls=#panel.calls;callback(target.block,'../untrusted');check(#panel.calls==calls,'invalid clip ID never reaches JS')
e.now=e.now+.2;callback(target.block,clip);callback(target.block,clip);before=reads
callback(target.block,clip);save('rate');check(reads==before,'third immediate read remains rate bounded')
D:Stop();calls=#panel.calls;callback(target.block,clip);check(#panel.calls==calls,'stale bridge callback cannot read after Stop')
print('MS3_AUDIO_BRIDGE_LUA PASS '..e.checks)
'''
        (out / 'probe.lua').write_text('local OUT=' + json.dumps(directory) + '\n' + script)
        subprocess.run(['python3', 'tools/run_lua54.py', str(out / 'probe.lua')], cwd=ROOT, check=True)
        javascript = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=process.argv[1];let calls=0,bytes=0;
for(let i=0;i<2;i++){
 const expected=fs.readFileSync(path.join(root,i+'.ogg'));
 vm.runInNewContext(fs.readFileSync(path.join(root,'allowed-'+i+'.js'),'utf8'),{
  lodScore:{audio(clip,encoded){calls++;const actual=Buffer.from(encoded,'base64');assert(actual.equals(expected),'bridge changed audio bytes');bytes+=actual.length;}}
 });
}
for(const name of ['denied','oversized','missing','bad-header','rate']){
 let rejected=false;
 vm.runInNewContext(fs.readFileSync(path.join(root,name+'.js'),'utf8'),{lodScore:{audio(clip,data){assert.strictEqual(data,'');rejected=true;}}});
 assert(rejected,'missing bounded rejection: '+name);
}
assert.strictEqual(calls,2);
console.log(JSON.stringify({suite:'MS3_AUDIO_BRIDGE',files:calls,exactBytes:bytes,rejections:5,javascriptParsed:true}));
'''
        subprocess.run(['node', '-e', javascript, directory], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
