'use strict';
const assert=require('assert');
(async()=>{
const MS=(await import('../src/ms3-engine.js')).default;
let checks=0;function check(v,m){checks++;assert(v,m);}
class Param{constructor(){this.value=0;this.events=[];}setValueAtTime(value,at){this.events.push({value,at,type:'set'});}linearRampToValueAtTime(value,at){this.events.push({value,at,type:'ramp'});}cancelScheduledValues(at){this.events=this.events.filter(e=>e.at<at);}}
class Buffer{constructor(c,n,r){this.numberOfChannels=c;this.length=n;this.sampleRate=r;this.duration=n/r;this.data=Array.from({length:c},()=>new Float32Array(n));}getChannelData(c){return this.data[c];}}
function context(){return {currentTime:0,sampleRate:44100,destination:{},sources:[],decodes:[],state:'running',createBuffer:(c,n,r)=>new Buffer(c,n,r),createGain(){return {gain:new Param(),connect(){},disconnect(){}};},createBufferSource(){let x={connect(){},disconnect(){},start(at,offset=0){this.startAt=at;this.offset=offset;},stop(at=0){this.stopAt=at;}};this.sources.push(x);return x;},decodeAudioData(data,ok,fail){this.decodes.push({ok,fail});}};}
function fixture(ctx,id='a',scale=1,loop=true,beats=8){let p=Math.round(beats*60/130*ctx.sampleRate),b=ctx.createBuffer(2,p+24255,ctx.sampleRate);for(let c=0;c<2;c++)for(let i=0;i<b.length;i++)b.data[c][i]=scale*(i<p?.05*Math.sin(i*.014):.02*(1-(i-p)/24255)*Math.cos(i*.014));return {buffer:b,meta:{id,beats,duration:b.duration,energy:.5,entry:0,exit:0,next:[]},loop};}
function rig(){let ctx=context(),results=[],requests=[],tr=new MS.AudioTransport(ctx,(lane,id)=>requests.push({lane,id}),(token,on)=>results.push({token,on}));function add(id,scale=1,asset='role',loop=true,beats=8){let f=fixture(ctx,id,scale,loop,loop?beats:12),a=tr.assets[asset]||{id:asset,loop,role:loop?'T1':'VICTORY',bound:.15,clips:[]};a.clips.push(f.meta);tr.install(a);let e=tr.build(f.buffer,{asset:a,clip:f.meta});tr.cache[id]=e;tr.bytes+=e.bytes;return e;}tr.mix('floor',1);return {ctx,tr,add,results,requests};}
let r=rig(),a=r.add('a'),b=r.add('b',.8);r.tr.prepare('1','floor','a',1,1);check(r.ctx.sources.length===1,'one sample-clock source starts the resident phrase');check(r.ctx.sources[0].startAt===1,'start scheduled in future, not callback time');check(r.ctx.sources[0].offset===0,'no downbeat samples skipped');check(r.ctx.sources[0].loopStart===a.loopStart&&r.ctx.sources[0].loopEnd===a.buffer.duration,'musical loop excludes file tail');
const rawFixture=fixture(r.ctx).buffer;
for(let c=0;c<2;c++)for(let i=0;i<a.frames;i+=79){let raw=rawFixture.data[c];check(a.buffer.data[c][i]===raw[i],'first body unchanged');if(i<a.tail.length){check(a.tail.data[c][i]===raw[a.frames+i],'short saved release unchanged');check(Math.abs(a.buffer.data[c][a.frames+i]-raw[i]-raw[a.frames+i])<1e-8,'compact loop includes exactly one previous release');}}
r.ctx.currentTime=1.5;r.tr.tick();for(let pass=1;pass<4;pass++){r.tr.prepare(String(pass+1),'floor','a',1,1+pass*a.period);r.ctx.currentTime=1+pass*a.period+.01;r.tr.tick();}check(r.ctx.sources.length===1,'four passes do not reopen, seek, fade or restart');let gainBefore=MS.levelAt(r.tr.lanes.floor.envelope,r.ctx.currentTime);r.tr.prepare('5','floor','b',1,1+4*a.period);check(MS.levelAt(r.tr.lanes.floor.envelope,r.ctx.currentTime)===gainBefore,'preparing a future clip does not mute present audio');check(r.ctx.sources.length===3,'one successor plus exactly one outgoing tail');check(Math.abs(r.tr.jobs['5'].voice.norm-1.25)<1e-6,'bounded body-RMS match removes clip gain discontinuity');check(r.tr.jobs['5'].tail.source.offset===0&&r.tr.jobs['5'].tail.source.buffer===a.tail,'only outgoing release is transferred');check(r.tr.jobs['5'].voice.due===1+4*a.period,'successor stays on exact phrase grid');
r.tr.cancel('5');check(r.tr.lanes.floor.current.entry.id==='a','cancellation restores resident clip');check(r.ctx.sources[0].stopAt>80000,'cancellation replaces future stop instead of silencing resident');check(r.tr.voices.length===1,'cancelled future/tail sources released');
r.tr.prepare('6','floor','b',1,1+4*a.period);r.ctx.currentTime=1+4*a.period+.4;r.tr.tick();check(r.results.some(x=>x.token==='6'&&x.on),'audio-thread start is acknowledged after JS hitch');check(r.tr.lanes.floor.current.entry.id==='b','hitch cannot change the already scheduled successor');
let late=rig(),la=late.add('a');late.tr.prepare('1','floor','a',1,1);late.ctx.currentTime=1.01;late.tr.tick();let f=fixture(late.ctx,'unloaded');late.tr.assets.role.clips.push(f.meta);late.ctx.currentTime=la.period;late.tr.prepare('2','floor','unloaded',1,1+la.period);check(late.requests.length===1,'missing clip requests bounded local bytes');late.ctx.currentTime=1+la.period-.04;late.tr.tick();check(late.results.some(x=>x.token==='2'&&!x.on),'late preparation is not inserted off-grid');check(late.tr.lanes.floor.current.entry.id==='a'&&late.tr.lanes.floor.current.end===Infinity,'late preparation leaves resident sample-clock loop uninterrupted');late.tr.receive('unloaded','T2dnUw==');late.ctx.decodes[0].ok(f.buffer);check(late.ctx.sources.length===1,'late decode callback never starts stale audio');let future=1+2*la.period;late.tr.prepare('3','floor','unloaded',1,future);check(late.ctx.sources.at(-2).startAt===future,'late-loaded replacement waits for a fresh phrase boundary');
let off=rig(),oa=off.add('a');off.tr.prepare('1','floor','a',1,1);off.tr.stop();check(off.tr.bytes===0&&off.tr.voices.length===0&&Object.keys(off.tr.lanes).length===0,'Off disposes all nodes/buffers/jobs');check(off.ctx.sources.every(s=>s.stopAt===0),'Off immediately stops even future scheduled voices');
let victory=rig(),va=victory.add('victory',1,'win',false);victory.tr.prepare('1','floor','victory',1,1);check(!victory.ctx.sources[0].loop,'victory is once-only');check(victory.tr.lanes.floor.current.end===1+va.buffer.duration,'victory includes its authored release');
let stale=rig(),sf=fixture(stale.ctx,'x');stale.tr.install({id:'role',loop:true,role:'T1',bound:.15,clips:[sf.meta]});stale.tr.prepare('1','floor','x',1,1);stale.tr.receive('x','T2dnUw==');stale.tr.stop();stale.ctx.decodes[0].ok(sf.buffer);check(stale.tr.bytes===0&&stale.ctx.sources.length===0,'stale asynchronous decode cannot resurrect stopped playback');
let stairs=rig(),sa=stairs.add('a'),sb=stairs.add('b',1,'other');stairs.tr.prepare('1','floor','a',1,1);stairs.ctx.currentTime=2;stairs.tr.tick();stairs.tr.mix('floor',0);stairs.tr.mix('up',1);check(MS.levelAt(stairs.tr.lanes.floor.envelope,3)===1,'outgoing floor stays audible while incoming is not prepared');stairs.tr.prepare('2','up','b',1,4);check(MS.levelAt(stairs.tr.lanes.floor.envelope,3)===1,'stair handoff cannot fade outgoing before future incoming start');check(MS.levelAt(stairs.tr.lanes.floor.envelope,4.7)===0&&MS.levelAt(stairs.tr.lanes.up.envelope,4.7)===1,'stair blend is scheduled on audio timeline');stairs.tr.cancel('2');check(MS.levelAt(stairs.tr.lanes.floor.envelope,4.7)===1,'reversed unplayed stair handoff restores outgoing mix');
let quant=rig();let scheduler=new MS.Scheduler(130,quant.tr,()=>quant.ctx.currentTime,()=>{},'test');check(Math.abs(scheduler.timeForBeat(64000)-scheduler.origin-1000*Math.round(64*60/130*44100)/44100)<1e-10,'1000 phrase periods cannot drift from loop granules');
let comp=new MS.Composer('heard-only'),asset={clips:[{id:'a',entry:0,exit:0,energy:.5},{id:'b',entry:0,exit:0,energy:.5}]};let selected=comp.choose(asset,false);check(comp.last===null&&comp.history.length===0,'unheard preparations do not enter musical history');comp.accept(selected);check(comp.last===selected,'heard phrase commits its musical history');
for(const x of [r,late,off,victory,stale,stairs]){check(x.tr.bytes+x.tr.reserved<=32*1024*1024,'bounded PCM');check(x.tr.voices.length<=8,'bounded voices');check(Object.keys(x.tr.loads).length<=2,'bounded decode work');}
// Finished one-shots must release lane ownership as well as the cache ref.
victory.ctx.currentTime=1+va.buffer.duration+.1;victory.tr.reap();
check(victory.tr.lanes.floor.current===null,'finished fanfare clears resident lane reference');
check(va.refs===0&&victory.ctx.sources[0].buffer===null,'finished source disconnects and releases its buffer');
victory.add('after-victory');victory.tr.prepare('2','floor','after-victory',1,victory.ctx.currentTime+1);
check(!victory.tr.jobs['2'].previous&&!victory.tr.jobs['2'].tail,'successor never retains or crossfades a dead fanfare');
// Real-sized 16-bar buffers: two audible floors plus a prepared successor
// fit the unchanged 32 MiB PCM ceiling, including saved tails and decode reserve.
const large=rig(),lA=large.add('large-a',1,'role',true,64),lB=large.add('large-b',1,'other',true,64);
large.tr.mix('up',1);large.tr.prepare('1','floor','large-a',1,1);large.tr.prepare('2','up','large-b',1,1);
large.ctx.currentTime=2;large.tr.tick();
const lC=fixture(large.ctx,'large-c',.9,true,64);large.tr.assets.role.clips.push(lC.meta);
const boundary=1+lA.period;large.tr.prepare('3','floor','large-c',boundary-2,boundary);
check(large.requests.length===1&&large.tr.bytes+large.tr.reserved<=32*1024*1024,'third long buffer is admitted beside both floor voices');
large.tr.receive('large-c','T2dnUw==');large.ctx.decodes[0].ok(lC.buffer);
check(large.tr.jobs['3'].scheduled&&large.tr.bytes<=32*1024*1024,'real-sized successor decode keeps complete buffer/tail accounting bounded');
check(large.tr.bytes>30*1024*1024,'memory regression exercises actual long-body sizes, not tiny fixtures');
const lD=fixture(large.ctx,'large-d',1,true,64);large.tr.assets.other.clips.push(lD.meta);
large.tr.prepare('4','up','large-d',boundary-2,boundary);
check(large.results.some(v=>v.token==='4'&&!v.on)&&large.requests.length===1,'fourth live long buffer is refused before decode allocation');
check(large.tr.lanes.up.current.entry.id==='large-b','refused admission preserves healthy second-floor music');
large.ctx.currentTime=boundary+.6;large.tr.tick();
large.tr.prepare('5','up','large-d',1,large.ctx.currentTime+1);
check(large.requests.length===2&&large.tr.bytes+large.tr.reserved<=32*1024*1024,'completed outgoing tail frees room for next floor successor');
large.tr.receive('large-d','T2dnUw==');large.ctx.decodes[1].ok(lD.buffer);
check(large.tr.jobs['5'].scheduled&&large.tr.peakBytes<=32*1024*1024,'successive long-floor admissions remain bounded');
const memoryPeak=large.tr.peakBytes;large.tr.stop();check(large.tr.bytes===0,'long-form Off releases resident and prepared buffers');
// Constructor presence alone is not evidence that older HTML supports playback.
for(const kind of ['missing','throws','high-rate','modern']){
 let timers=[],ready=[],errors=[],closes=0,stats;
 let ctx=context();ctx.close=()=>{closes++;ctx.state='closed';};
 if(kind==='high-rate')ctx.sampleRate=48000;
 if(kind==='missing')delete ctx.createGain;
 if(kind==='throws')ctx.createGain=()=>{throw Error('gain API unavailable');};
 global.window={AudioContext:function(){return ctx;},performance:{now:()=>0},setTimeout:fn=>timers.push(fn),setInterval:()=>1,clearInterval:()=>{}};
 const noop=()=>{},bridge={readclip:noop,prepare:noop,cancel:noop,mix:noop,volume:noop,drop:noop,stop:noop,block:noop,victory:noop,error:e=>errors.push(e),ready:b=>ready.push(b),stats:s=>stats=JSON.parse(s)};
 const attached=MS.attach(bridge);timers.shift()();attached.stats();
 check(ready.length===1&&ready[0]===(kind==='modern'?'surge-sample-clock':'surge-rendered'),'capability negotiation completes exactly once: '+kind);
 check(errors.length===0,'unsupported audio API selects working native path: '+kind);
 if(kind!=='modern')check(closes===1&&!!stats.fallbackReason,'failed context is closed and fallback reason retained: '+kind);
 attached.destroy();check(closes===1,'context disposed exactly once: '+kind);delete global.window;
}
console.log(JSON.stringify({suite:'MS3_SAMPLE_CLOCK',checks,longFormPeakBytes:memoryPeak,actualAudio:false}));

})().catch(error=>{console.error(error);process.exitCode=1;});
