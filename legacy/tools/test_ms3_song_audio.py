#!/usr/bin/env python3
"""Actual Chromium song traversal with bounded rolling decode and dry reference.

OfflineAudioContext suspension models advance preparation, not real-time GMod
performance. No speaker/listening acceptance is inferred from sample parity.
"""
import base64,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=r'''async (input)=>{
 const rate=44100, origin=rate, sequence=input.clips.concat([input.clips[0]]);
 let cursor=origin;
 const starts=sequence.map(c=>{const start=cursor;cursor+=c.musicalFrames;return start;});
 const ctx=new OfflineAudioContext(2,cursor,rate), reference=new Float32Array(cursor);
 const sourceDecode=ctx.decodeAudioData.bind(ctx);let decodeWait=Promise.resolve(),at=0;
 ctx.decodeAudioData=(bytes,ok,bad)=>{
  const index=at, c=sequence[index],start=starts[index];
  decodeWait=sourceDecode(bytes).then(buffer=>{
   const data=buffer.getChannelData(0);
   for(let n=0;n<data.length&&start+n<reference.length;n++)reference[start+n]+=data[n];
   return ok(buffer);
  },bad);return decodeWait;
 };
 const byid=Object.fromEntries(input.clips.map(c=>[c.id,c]));
 const tr=new MS2.AudioTransport(ctx,(lane,clip)=>tr.receive(clip,byid[clip].encoded),()=>{});
 const asset={id:input.id,role:input.role,loop:true,songFirst:true,bound:input.bound,clips:input.clips};
 tr.install(asset);tr.mix('song',1);
 const waits=starts.slice(1).map(start=>ctx.suspend(start/rate-.8));
 function queue(i){at=i;tr.prepare(String(i+1),'song',sequence[i].id,starts[i]/rate-ctx.currentTime,starts[i]/rate);}
 queue(0);await decodeWait;
 if(!tr.jobs['1'].scheduled)throw Error('initial full-song preparation failed');
 const rendering=ctx.startRendering();
 for(let i=1;i<sequence.length;i++){
  await waits[i-1];tr.tick();tr.reap();queue(i);await decodeWait;
  const job=tr.jobs[String(i+1)];
  if(!job||!job.scheduled||job.voice.norm!==1)throw Error('song continuation failed or changed source dynamics');
  if(tr.bytes+tr.reserved>32*1024*1024)throw Error('song exceeded PCM ceiling');
  ctx.resume();
 }
 const output=await rendering,actual=output.getChannelData(0),master=MS2.levelAt(tr.masterEnvelope,2);
 let error=0,peak=0,delta=0;
 for(let i=2*rate;i<cursor;i++){
  error=Math.max(error,Math.abs(actual[i]-reference[i]*master));peak=Math.max(peak,Math.abs(actual[i]));
  if(i>2*rate)delta=Math.max(delta,Math.abs((actual[i]-actual[i-1])-(reference[i]-reference[i-1])*master));
 }
 if(error>2e-5||delta>3e-5||peak>.8)throw Error('continuous song reference mismatch '+JSON.stringify({error,delta,peak}));
 const result={song:input.id,seconds:(cursor-origin)/rate,joins:sequence.length-1,actualDecodes:sequence.length,
  maxAbsoluteSampleError:error,maxDerivativeError:delta,peak,trackedPCMBytes:tr.peakBytes};
 tr.stop();return result;
}'''
def main():
    catalog=json.loads((ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2/catalog.lua').read_text().split('[==[',1)[1].rsplit(']==]',1)[0])
    manifest=json.loads((ROOT/'docs/MS2_SURGE_BANK.json').read_text());bank={c['id']:c for c in manifest['clips']}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('MS3_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.add_script_tag(content=(ROOT/'tools/music/ms2_engine.js').read_text())
        results=[]
        for aid in ('a-t1','b-t2','h-t0'):
            asset=catalog['assets'][aid];rows=[bank[c['id']] for c in asset['clips']]
            data=dict(id=aid,role=asset['role'],bound=max(r['decodedPeak'] for r in rows)+max(r['decodedTailPeak'] for r in rows),clips=[])
            for c in asset['clips']:
                row=bank[c['id']]
                data['clips'].append({**c,'duration':row['duration'],'encoded':base64.b64encode((ROOT/row['path']).read_bytes()).decode('ascii')})
            result=page.evaluate(SCRIPT,data);results.append(result);print(json.dumps(result),flush=True)
        browser.close()
    print(json.dumps(dict(suite='MS3_COMPLETE_SONG_AUDIO',songs=results,actualAudio=True,nativeGModAccepted=False)))
if __name__=='__main__':main()
