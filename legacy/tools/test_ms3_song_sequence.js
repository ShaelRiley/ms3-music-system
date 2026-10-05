'use strict';
// Full songs, continuously changing requests, delayed chunks, and cue exceptions.
const assert=require('assert'),engine=require('./music/ms2_engine.js'),bank=require('./music/read_catalog.js');
let checks=0;function check(value,message){checks++;assert(value,message);}
function meta(id){const a=bank.asset(id);return {...a,clips:a.clips.map(({notes,...c})=>c)};}
function rig(continuous=false){
 let now=0,failed=null,state={songFirst:true,planKey:'test',seed:17,role:'T1',staged:false,targets:[{block:'a',asset:'a-t1',weight:1}]};
 const pending={},plays=[],announcements=[],victories=[],mixes={};
 const sink={continuous,context:{sampleRate:44100},volume(){},mix(id,g){mixes[id]=g;},cancel(t){delete pending[t]},drop(id){delete mixes[id]},stop(){Object.keys(pending).forEach(k=>delete pending[k]);},prepare(token,lane,clip,delay,time){pending[token]={token,lane,clip,time};}};
 const s=new engine.Scheduler(130,sink,()=>now,(k,v)=>{(k==='block'?announcements:victories).push(v)},'song-test');
 function change(patch){state={...state,...patch};for(const t of state.targets)s.install(meta(t.asset));s.update(state);}
 function pump(){s.pump();for(const p of Object.values(pending)){if(now+1e-9>=p.time){delete pending[p.token];const played=p.clip!==failed;if(played)plays.push(p);else failed=null;s.result(p.token,played);}}
  check(Object.keys(pending).length<=1,'only one upcoming song chunk');check(Object.keys(s.lanes).length<=1,'ordinary requests never create layered floor songs');check(Object.keys(s.assets).length<=3,'only active plus requested assets');}
 function step(seconds){let end=now+seconds;while(now<end){now=Math.min(end,now+.025);pump();}}
 change({});return {s,plays,announcements,victories,pending,mixes,change,step,pump,reject(clip){failed=clip},get now(){return now}};
}
for(const continuous of [false,true]){
 const r=rig(continuous),song=meta('a-t1'),duration=song.clips.reduce((n,c)=>n+c.musicalFrames/44100,0);
 for(let i=0;i<Math.ceil(duration/2);i++){
  r.change({role:i%2?'T3':'T2',targets:i%3?[{block:'b',asset:'b-t3',weight:1}]:[{block:'c',asset:'c-t2',weight:.6},{block:'d',asset:'d-t2',weight:.4}]});
  r.step(2);
 }
 check(r.plays.length===song.clips.length,'entire song survives frequent pressure and stair preferences');
 check(r.plays.map(p=>p.clip).join(',')===song.clips.map(c=>c.id).join(','),'every source-ordered part once, none shuffled/skipped');
 for(let i=1;i<r.plays.length;i++)check(Math.abs(r.plays[i].time-r.plays[i-1].time-song.clips[i-1].musicalFrames/44100)<1e-8,'exact contiguous frame duration including partial chunks');
 r.change({role:'T3',targets:[{block:'b',asset:'b-t3',weight:1}]});r.step(4);
 check(r.plays.at(-1).clip===meta('b-t3').clips[0].id,'latest desired song starts at its beginning only after completion');
 check(r.announcements.join(',')==='a,b','announcements describe actually started compositions, not transient floor requests');
 const start=r.now;r.change({role:'BOSS',targets:[{block:'a',asset:'a-boss',weight:1}]});r.step(5);
 check(r.plays.at(-1).clip===meta('a-boss').clips[0].id&&r.plays.at(-1).time-start<5,'boss exception remains responsive');
 r.change({role:'VICTORY',targets:[{block:'a',asset:'a-victory',weight:1}]});r.step(10);const count=r.plays.length;
 r.step(10);check(r.victories.length===1&&r.plays.length===count,'victory once, not a song loop');
 r.change({staged:true,role:'T0',targets:[{block:'a',asset:'a-t0',weight:1}]});r.step(5);
 check(r.plays.at(-1).clip===meta('a-t0').clips[0].id,'staging starts full calm composition');
 r.change({staged:false,role:'T1',targets:[{block:'a',asset:'a-t1',weight:1}]});r.step(5);
 check(r.plays.at(-1).clip===song.clips[0].id,'leaving staging starts driving edit');
 r.s.stop();check(Object.keys(r.pending).length===0,'Off drops scheduled music');
 const delayed=rig(continuous);delayed.step(10);delayed.reject(song.clips[1].id);delayed.step(52);
 check(delayed.plays.length===2&&delayed.plays[1].clip===song.clips[1].id,'late second chunk retries that chunk instead of skipping melody');
 check(Math.abs(delayed.plays[1].time-delayed.plays[0].time-2*song.clips[0].musicalFrames/44100)<1e-8,'recovery waits for resident whole-chunk repeat');
 delayed.s.stop();
}
// Every actual song's chronological indices are honored by the production composer.
for(const a of Object.values(bank.catalog.assets)){
 const c=new engine.Composer('ordered:'+a.id);
 for(let i=0;i<a.clips.length*2;i++)check(c.choose(a).id===a.clips[i%a.clips.length].id,'all real song parts play in exact order');
}
console.log(JSON.stringify({suite:'MS3_SONG_SEQUENCE',checks,songs:48,backends:2}));
