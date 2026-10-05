import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {MS3Player} from '../src/player.js';
import Engine from '../src/ms3-engine.js';
const catalog = JSON.parse(fs.readFileSync(new URL('../bank/catalog.json', import.meta.url)));
test('manual tension mapping, clamping, bank inheritance and independent role controls',()=>{
  const player = new MS3Player(catalog);
  assert.equal(player.resolve().id,'a-t0');
  for(let i=2;i<=4;i++){player.tensionUp();assert.equal(player.resolve().role,'T'+(i-1));}
  player.tensionUp();assert.equal(player.tension,4);
  player.setBlock('h');assert.equal(player.resolve().id,'h-t3');
  player.boss();assert.equal(player.resolve().id,'h-boss');
  player.fanfare();assert.equal(player.resolve().id,'h-victory');
  player.tensionDown();assert.equal(player.resolve().id,'h-t2');
  player.setTension(-20);assert.equal(player.tension,1);
  player.setVolume(50);assert.equal(player.volume,1);
  assert.throws(()=>player.setTension(NaN));assert.throws(()=>player.setVolume(Infinity));assert.throws(()=>player.setBlock('missing'));
});
test('real scheduler accepts manual switches promptly while keeping source-order songs',()=>{
  let now=0;const pending=new Map(),heard=[];
  const sink={continuous:true,context:{sampleRate:44100},volume(){},mix(){},drop(){},stop(){},cancel(t){pending.delete(t);},prepare(t,l,c,d,at){pending.set(t,{c,at});}};
  const player=new MS3Player(catalog);
  player.transport={install(){},assets:{},loads:{},volume(){},stats(){return {}}};
  player.scheduler=new Engine.Scheduler(130,sink,()=>now,()=>{},'manual-test');player.update();
  function step(seconds){for(let end=now+seconds;now<end;now+=.025){player.scheduler.pump();for(const [t,p] of pending){if(p.at<=now){heard.push(p);pending.delete(t);player.scheduler.result(t,true);}}}}
  step(5);assert.equal(heard.at(-1).c,'a_t0_song_000');
  const before=now;player.setTension(4);step(5);assert.equal(heard.at(-1).c,'a_t3_song_000');assert(heard.at(-1).at-before<5);
  step(40);assert.equal(heard.at(-1).c,'a_t3_song_001');
  step(240);assert(heard.length>8,'complete songs repeat without the deferred game policy');
  player.setBlock('b');step(5);assert.equal(heard.at(-1).c,'b_t3_song_000');
});
test('stop cancels outstanding reads, interval, transport and stale decode ownership',()=>{
  const player=new MS3Player(catalog);let aborted=0,stopped=0,closed=0;
  player.requests.set('one',{abort(){aborted++;}});player.scheduler={stop(){stopped++;}};player.context={close(){closed++;return Promise.resolve();}};
  player.stop();assert.equal(aborted,1);assert.equal(stopped,1);assert.equal(closed,1);assert.equal(player.requests.size,0);assert.equal(player.status().playing,false);
});
