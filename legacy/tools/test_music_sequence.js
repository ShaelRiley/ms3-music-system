'use strict';
const assert=require('assert'),{performance}=require('perf_hooks');
const engine=require('./music/ms2_engine.js'),bank=require('./music/read_catalog.js');
let checks=0;function check(ok,msg){checks++;assert(ok,msg);}
const start=performance.now(),scale=new Set([0,2,4,5,7,9,11]);let clips=0,notes=0;
function metadata(id){const a=bank.asset(id);return {...a,songFirst:false,clips:a.clips.map(({notes,musicalFrames,songIndex,...c})=>({...c,beats:a.loop?64:12}))};}
for(const id of Object.keys(bank.catalog.assets)){
 const a=bank.asset(id),c=new engine.Composer('catalog:'+id);
 for(const clip of a.clips){clips++;notes+=clip.notes.length;check(clip.notes.length<=2048,'bounded source phrase');
  check(a.loop?clip.beats>=4&&clip.beats<=64&&clip.beats%4===0:clip.beats===12,'song delivery chunks are bounded bars; fanfares stay distinct');
  for(const n of clip.notes){check(n.length===5&&n[0]>=0&&n[0]<clip.beats*48&&n[1]>0&&n[0]+n[1]<=clip.beats*48,'authored source gates remain');
   if(n[2]<5)check(scale.has(n[3]%12),'D Dorian remains');}}
 let prior=null;
 for(let i=0;i<24;i++){const phrase=c.choose(a);if(a.clips.length>3)check(prior!==phrase.id,'recent phrases avoided');prior=phrase.id;}
}
const audit=require('../docs/MS3_SONG_AUDIT.json');
check(clips===224&&clips===audit.ordinaryClips+audit.fanfares&&notes===audit.notes,'whole source-audited song composition preserved');
check(engine.tempo(130,{remaining:0})===130,'fixed rendered tempo replaces old time stretch');
check(engine.expression({role:'T3',expression:1})===1,'cheap critical gain remains');
check(engine.expression({role:'BOSS',expression:0})===0,'ordinary boss does not fabricate expression');
// Legacy short-phrase fixture retains the original timing regression cases.
// Separate historical 64-beat timing fixtures below retain prior coverage.
// Actual song-first metadata/policy is exercised by test_ms3_song_sequence.js.
function rig(seed='test',acknowledgementDelay=0,longform=false){
 let now=0,state={seed:19,role:'T1',remaining:1800,volume:.55,targets:[{block:'a',asset:'a-t1',weight:1}]};
 const pending={},plays=[],announcements=[],mixes={},victories=[],acks=[];let stopCount=0;
 const sink={prepare:(token,lane,clip,delay,deadline)=>{check(Math.abs(deadline-now-delay)<1e-8,'absolute native deadline preserves grid');pending[token]={token,lane,clip,time:deadline};},cancel:token=>delete pending[token],
  mix:(id,g)=>mixes[id]=g,volume:()=>{},drop:id=>{delete mixes[id];for(const k in pending)if(pending[k].lane===id)delete pending[k];},
  stop:()=>{for(const k in pending)delete pending[k];for(const k in mixes)delete mixes[k];stopCount++;}};
 const scheduler=new engine.Scheduler(130,sink,()=>now,(type,value)=>type==='block'?announcements.push(value):victories.push(now),seed);
 function change(patch={}){state={...state,...patch};for(const t of state.targets){let a=metadata(t.asset);if(!longform&&a.loop)a={...a,clips:a.clips.map(c=>({...c,beats:8}))};scheduler.install(a);}scheduler.update(state);}
 function pump(){
  for(let i=acks.length-1;i>=0;i--)if(now>=acks[i].at){const a=acks.splice(i,1)[0];scheduler.result(a.token,a.played);}
  scheduler.pump();const starts={};for(const token of Object.keys(pending)){
  const p=pending[token];if(now>=p.time){delete pending[token];const on=now<=p.time+engine.lateTolerance&&!starts[p.lane];
   if(on){plays.push({...p,started:now});starts[p.lane]=true;}
   if(acknowledgementDelay)acks.push({token,played:on,at:now+acknowledgementDelay});else scheduler.result(token,on);}}
  check(Object.keys(pending).length<=2,'only one upcoming phrase per audible lane');}
 function step(seconds){for(let end=now+seconds;now<end;){now=Math.min(end,now+.025);pump();}}
 change();return {scheduler,plays,announcements,mixes,victories,pending,change,pump,step,jump:n=>{now+=n;},get now(){return now;},get stopCount(){return stopCount;}};
}
const r=rig();r.step(10);check(r.plays.length>=3,'A to B normal phrase sequencing');
const dwell=rig('phrase-dwell');dwell.step(33);
check(dwell.plays.length>=8,'dwell exercises two complete phrase residencies');
for(let i=0;i<8;i++)check(dwell.plays[i].clip===dwell.plays[Math.floor(i/4)*4].clip,'routine phrase holds for four successful passes');
check(dwell.plays[0].clip!==dwell.plays[4].clip,'fresh composition follows a fifteen-second-scale residence');
// A rejected preparation must retry on the held phrase's grid, rather than
// interrupt its repeat at the next four-beat half-phrase boundary.
const held=rig('resident-hold');held.step(3.8);const heldJob=Object.values(held.pending)[0];
held.jump(heldJob.time-held.now+.2);held.pump();const retryBeat=held.scheduler.lanes.a.nextBeat;
check(Math.abs(held.scheduler.timeForBeat(retryBeat)-heldJob.time-8*60/130)<1e-8,'failed replacement preserves the resident repeat boundary');
// Native starts can be correct while their QueueJavascript acknowledgement is
// delayed by the frame/DHTML boundary. This must not fabricate a failed start.
const delayedAck=rig('queued-ack',.3);delayedAck.step(20);
check(delayedAck.scheduler.resyncs===0,'delayed native acknowledgement does not discard already playing phrases');
for(let i=1;i<delayedAck.plays.length;i++)check(Math.abs(delayedAck.plays[i].time-delayedAck.plays[i-1].time-8*60/130)<1e-8,'delayed acknowledgement retains continuous eight-beat phrase boundaries');
for(let i=1;i<r.plays.length;i++)check(Math.abs(r.plays[i].time-r.plays[i-1].time-8*60/130)<1e-8,'phrases follow canonical future boundary');
check(r.announcements.join(',')==='a','initial block once');
r.change({role:'T2',targets:[{block:'a',asset:'a-t2',weight:1}]});r.step(4);
check(r.announcements.length===1,'tension never announces a block');check(r.plays.at(-1).clip.startsWith('a_t2_'),'new role rendered phrase');
r.change({targets:[{block:'a',asset:'a-t2',weight:.4},{block:'b',asset:'b-t2',weight:.6}]});r.step(4);
check(r.announcements.join(',')==='a,b','stair incoming block only');check(Math.abs(r.mixes.a-Math.sqrt(.4))<1e-10,'equal power whole-phrase lanes');
const a=r.scheduler.lanes.a,b=r.scheduler.lanes.b;
r.change({targets:[{block:'a',asset:'a-t2',weight:.8},{block:'b',asset:'b-t2',weight:.2}]});r.step(2);
check(r.scheduler.lanes.a===a&&r.scheduler.lanes.b===b,'reversal reuses two lanes');check(r.announcements.length===2,'reversal does not reannounce');
r.change({targets:[{block:'b',asset:'b-t2',weight:1}]});r.step(2);check(!r.scheduler.lanes.a,'retiring floor released');
const oldSeed=a.composer.random.value;r.change({targets:[{block:'a',asset:'a-t2',weight:1}]});r.step(4);
check(r.scheduler.lanes.a.composer.random.value!==oldSeed,'genuine return gets fresh presentation entropy');
for(const stall of [.1,.3,1,4,15])for(const mutation of ['none','role','reverse']){
 const x=rig('stall-'+stall+'-'+mutation);x.step(3.8);
 if(mutation==='reverse'){x.change({targets:[{block:'a',asset:'a-t1',weight:.3},{block:'b',asset:'b-t1',weight:.7}]});x.step(2);}
 const job=Object.values(x.pending)[0];check(job,'preparation precedes boundary');x.jump(Math.max(0,job.time-x.now)+stall);
 if(mutation==='role')x.change({role:'T3',targets:[{block:'a',asset:'a-t3',weight:1}]});
 if(mutation==='reverse')x.change({targets:[{block:'a',asset:'a-t1',weight:.8},{block:'b',asset:'b-t1',weight:.2}]});
 const count=x.plays.length;x.pump();
 if(stall<=engine.lateTolerance&&mutation!=='role')check(x.plays.length===count+1,'bounded frame delay admits only the current prepared phrase');
 else check(x.plays.length===count,'larger stall never starts an obsolete phrase');
 x.step(8);check(x.plays.length>count,'stall resumes at a future valid bar');
 for(const p of x.plays)check(p.started>=p.time&&p.started-p.time<=engine.lateTolerance+1e-8,'only bounded on-time start');
 const seen=new Set();for(const p of x.plays){const k=p.lane+':'+p.time;check(!seen.has(k),'one start per lane/boundary');seen.add(k);}
 check(Object.keys(x.scheduler.lanes).length<=2,'stalled stairs do not grow a third lane');x.scheduler.stop();
}
// Delayed preload completion and resume are obsolete acknowledgements, never
// opportunities to play several skipped phrases together.
const late=rig('late');late.pump();const token=Object.keys(late.pending)[0];late.jump(10);late.pump();
late.scheduler.result(token,true);check(late.announcements.length===0,'stale return cannot fabricate a block start');late.step(6);check(late.plays.length>0,'suspension recovers');
r.change({role:'VICTORY',targets:[{block:'a',asset:'a-victory',weight:1}]});r.step(12);
check(r.victories.length===1,'12-beat fanfare completes once');const end=r.plays.length;r.step(8);check(r.plays.length===end&&r.victories.length===1,'fanfare never loops');
r.change({role:'T0',targets:[{block:'b',asset:'b-t0',weight:1}]});r.step(6);check(r.plays.at(-1).clip.startsWith('b_t0_'),'post-victory Chill');
r.scheduler.stop();check(!Object.keys(r.pending).length&&!Object.keys(r.mixes).length&&r.stopCount===1,'Off disposes all preparations and audio');
const restart=rig('return');restart.jump(100);restart.pump();check(restart.plays.length===0,'On never replays missed score');restart.step(6);check(restart.plays.length>0,'On resumes future music');restart.scheduler.stop();
const rapid=rig('rapid');for(const block of ['a','b','c','d','e','f','g','h']){
 rapid.change({targets:[{block,asset:block+'-t1',weight:1}]});rapid.pump();check(Object.keys(rapid.scheduler.lanes).length<=3,'rapid replacement has bounded retirement tails');}
rapid.scheduler.stop();
// The shipping score must advance after ONE full 16-bar source passage.
const long=rig('actual-sixteen-bar',0,true);long.step(95);
check(long.plays.length===4,'actual long-form score plays four passages over 95 seconds');
for(let i=1;i<long.plays.length;i++){
 check(Math.abs(long.plays[i].time-long.plays[i-1].time-64*60/130)<1e-8,'long passages advance on full sixty-four-beat boundaries');
 check(long.plays[i].clip!==long.plays[i-1].clip,'no artificial four-pass short-phrase extension');
}
const longRole=rig('responsive-long-role',0,true);longRole.step(6);const changedAt=longRole.now;
longRole.change({role:'BOSS',targets:[{block:'a',asset:'a-boss',weight:1}]});longRole.step(4);
check(longRole.plays.at(-1).clip.startsWith('a_boss_')&&longRole.plays.at(-1).time-changedAt<3,'boss response does not wait sixteen bars');
longRole.change({targets:[{block:'a',asset:'a-boss',weight:.5},{block:'b',asset:'b-boss',weight:.5}]});longRole.step(4);
check(longRole.plays.at(-1).clip.startsWith('b_boss_'),'long-form second-floor handoff is responsive');
const longHeld=rig('long-whole-resident',0,true);longHeld.step(29.8);const longJob=Object.values(longHeld.pending)[0];
check(longJob,'long successor prepared before whole-passage boundary');
longHeld.jump(longJob.time-longHeld.now+.3);longHeld.pump();
check(Math.abs(longHeld.scheduler.timeForBeat(longHeld.scheduler.lanes.a.nextBeat)-longJob.time-64*60/130)<1e-8,'failed same-role successor leaves the resident full passage intact');
longHeld.change({role:'T3',targets:[{block:'a',asset:'a-t3',weight:1}]});longHeld.step(4);
check(longHeld.plays.at(-1).clip.startsWith('a_t3_'),'failed old-role replacement cannot delay fresh danger sixteen bars');
long.scheduler.stop();longRole.scheduler.stop();longHeld.scheduler.stop();
// A legacy bridge without bundled-byte support must retain native playback.
// AudioContext is now allowed only for rendered AudioBuffer playback, never synthesis.
let init,tick,backend;global.window={AudioContext:function(){throw Error('live synthesis forbidden');},setTimeout:fn=>init=fn,setInterval:fn=>{tick=fn;return 1;},clearInterval:()=>{}};
const renderer=engine.attach({ready:v=>backend=v,prepare:()=>{},cancel:()=>{},mix:()=>{},volume:()=>{},drop:()=>{},stop:()=>{},block:()=>{},victory:()=>{},error:e=>{throw Error(e);},stats:()=>{}});
init();renderer.install(metadata('a-t1'));renderer.state({seed:1,bpm:130,role:'T1',targets:[{block:'a',asset:'a-t1',weight:1}]});tick();
check(backend==='surge-rendered','actual active backend is unambiguous');renderer.destroy();delete global.window;
console.log(JSON.stringify({suite:'MS2_RENDERED_SEQUENCE',checks,clips,notes,stallCases:15,maxPrepared:r.scheduler.maxQueue,milliseconds:+(performance.now()-start).toFixed(1)}));
