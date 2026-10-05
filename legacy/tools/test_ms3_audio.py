#!/usr/bin/env python3
"""Real Chromium OfflineAudioContext continuity gate; no speakers or GMod claims.

Requires playwright and a Chromium executable (MS3_CHROMIUM or /usr/bin/chromium).
Pass --bank to exercise real committed Surge Ogg pairs in every looping arrangement.
"""
import argparse
import base64
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''async (input) => {
  const rate=44100, beats=input?input.beats:64, period=Math.round(beats*60/130*rate), tail=22050, origin=rate;
  const switchFrame=origin+4*period, length=origin+7*period;
  const ctx=new OfflineAudioContext(2,length,rate);
  const tr=new MS2.AudioTransport(ctx,()=>{throw Error('unexpected local-file request');},()=>{});
  function original(scale) {
    const b=ctx.createBuffer(2,period+tail,rate);
    for(let c=0;c<2;c++)for(let i=0;i<b.length;i++) {
      // Beat-grid transients plus a pad and a release: a timing/fade/OLA error
      // is measurable even when average levels happen to look similar.
      let beat=i%(period/8), x=i<period?
          .035*Math.sin(i*.021)+.055*Math.exp(-beat/160)*Math.cos(beat*.1):
          .018*(1-(i-period)/tail)*Math.sin(i*.021);
      b.getChannelData(c)[i]=scale*x;
    }
    return b;
  }
  async function decoded(data){const raw=atob(data),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return await ctx.decodeAudioData(bytes.buffer);}
  const a=input?await decoded(input.a):original(1),b=input?await decoded(input.b):original(.8),metas=[['a',a],['b',b]].map(([id,buffer])=>({id,beats,duration:buffer.duration,energy:.5,entry:0,exit:0}));
  const dryA=Float32Array.from(a.getChannelData(0)),dryB=Float32Array.from(b.getChannelData(0));
  const asset={id:'calm',role:'T0',loop:true,songFirst:!!input,bound:input?input.bound:.15,clips:metas};tr.install(asset);tr.mix('floor',1);
  for(const [i,buffer] of [a,b].entries()){const e=tr.build(buffer,{asset,clip:metas[i]});tr.cache[e.id]=e;tr.bytes+=e.bytes;}
  tr.prepare('1','floor','a',1,1);
  tr.prepare('2','floor','b',1,switchFrame/rate);
  const norm=tr.jobs['2'].voice.norm,master=MS2.levelAt(tr.masterEnvelope,2);
  const rendered=await ctx.startRendering(), actual=rendered.getChannelData(0),src=dryA,next=dryB;
  function reference(i){const el=i-origin,pos=el%period;let value=(el>=4*period?next[pos]*norm:src[pos]);
    if(el>=period){const prior=el>=5*period?next:src;value+=(prior[period+pos]||0)*(el>=5*period?norm:1);}return value*master;}

  let maxError=0,sumError=0,referencePower=0,samples=0,maxPeak=0;
  // Exclude only intentional initial fade-in. Include ALL six loop edges and
  // the successor boundary, with no per-edge masking or forgiving windows.
  for(let i=origin+rate;i<length;i++) {
    const elapsed=i-origin, position=elapsed%period;
    let expected=reference(i);
    let error=actual[i]-expected;maxError=Math.max(maxError,Math.abs(error));sumError+=error*error;referencePower+=expected*expected;samples++;
    maxPeak=Math.max(maxPeak,Math.abs(actual[i]));
  }
  if(maxError>2e-5)throw Error('Sample continuity differs from continuous overlap-add: '+maxError);
  if(maxPeak>.8)throw Error('Peak ceiling exceeded');
  const edgeWindows=[];for(let n=1;n<7;n++) {
    let edge=origin+n*period,lo=edge-2000,hi=edge+2000,ae=0,re=0;
    for(let i=lo;i<hi;i++){let x=reference(i);ae+=actual[i]*actual[i];re+=x*x;}
    const db=10*Math.log10(ae/re);if(Math.abs(db)>.002)throw Error('Join level discontinuity: '+db);edgeWindows.push(db);
  }
  return {suite:'MS3_OFFLINE_AUDIO',actualAudio:true,sampleRate:rate,renderedFrames:length,joins:6,successorJoins:1,
      maxAbsoluteSampleError:maxError,errorRMS:Math.sqrt(sumError/samples),relativeErrorDB:10*Math.log10(sumError/referencePower),maxPeak,joinLevelErrorDB:edgeWindows};
}'''
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bank',action='store_true');args=parser.parse_args()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('MS3_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.add_script_tag(content=(ROOT/'tools/music/ms2_engine.js').read_text())
        result=page.evaluate(SCRIPT)
        print(json.dumps(result))
        if args.bank:
            catalog=json.loads((ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2/catalog.lua').read_text().split('[==[',1)[1].rsplit(']==]',1)[0])
            manifest=json.loads((ROOT/'docs/MS2_SURGE_BANK.json').read_text());bank={c['id']:c for c in manifest['clips']}
            results=[]
            for asset in catalog['assets'].values():
                if not asset['loop']:continue
                ids=[asset['clips'][0]['id'],asset['clips'][1]['id']]
                rows=[bank[c['id']] for c in asset['clips']]
                data={'beats':asset['clips'][0]['beats'],'bound':max(c['decodedPeak'] for c in rows)+max(c['decodedTailPeak'] for c in rows)}
                for key,cid in zip(('a','b'),ids):data[key]=base64.b64encode((ROOT/bank[cid]['path']).read_bytes()).decode('ascii')
                results.append(page.evaluate(SCRIPT,data))
            print(json.dumps({'suite':'MS3_SURGE_BROWSER_AUDIO','arrangements':len(results),'actualDecodes':len(results)*2,
                              'joins':sum(r['joins'] for r in results),'maxAbsoluteSampleError':max(r['maxAbsoluteSampleError'] for r in results),
                              'maxJoinLevelErrorDB':max(abs(d) for r in results for d in r['joinLevelErrorDB']),
                              'maxPeak':max(r['maxPeak'] for r in results)}))
        browser.close()
if __name__=='__main__':main()
