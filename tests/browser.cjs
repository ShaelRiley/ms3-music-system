// Real Chromium playback and all-bank decode gate. No speakers/perception claim.
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const path=require('path'),assert=require('assert');
(async()=>{
 const root=path.resolve(__dirname,'..'),server=spawn('python3',['-m','http.server','8765','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:8765')).ok)break;}catch{}await new Promise(r=>setTimeout(r,50));}
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.MS3_CHROMIUM?{executablePath:process.env.MS3_CHROMIUM}:{})});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.ms3Player);
  assert.equal(await page.locator('#bank option').count(),8);
  await page.click('#play');await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='a-t0',{},{timeout:15000});
  for(let level=2;level<=4;level++){await page.click('#up');await page.waitForFunction(level=>window.ms3Player.status().currentAsset===`a-t${level-1}`,level,{timeout:15000});}
  await page.click('#down');await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='a-t2',{},{timeout:15000});
  await page.selectOption('#bank','b');await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='b-t2',{},{timeout:15000});
  await page.click('#boss');await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='b-boss',{},{timeout:15000});
  await page.click('#fanfare');await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='b-victory',{},{timeout:15000});
  await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='b-t2',{},{timeout:15000});
  const stats=await page.evaluate(()=>window.ms3Player.status().audio);assert(stats.pcmBytes<=32*1024*1024);assert(stats.voices<=8);assert(stats.scheduledTransitions>=6);
  await page.click('#stop');assert.equal(await page.evaluate(()=>window.ms3Player.status().playing),false);
  await page.click('#play');await page.waitForFunction(()=>window.ms3Player.status().currentAsset==='b-t2',{},{timeout:15000});await page.click('#stop');
  const decoded=await page.evaluate(async()=>{
   const manifest=await (await fetch('/bank/manifest.json')).json();const ctx=new AudioContext({sampleRate:44100});let count=0;
   for(const row of [...manifest.clips,manifest.bridge]){
    const response=await fetch('/bank/'+row.path);if(!response.ok)throw Error('missing '+row.path);
    const raw=await response.arrayBuffer(),buffer=await ctx.decodeAudioData(raw);
    if(buffer.numberOfChannels!==2||Math.abs(buffer.duration-row.duration)>.08)throw Error('shape '+row.path);
    for(let channel=0;channel<2;channel++){const samples=buffer.getChannelData(channel);let peak=0,power=0;for(const x of samples){if(!Number.isFinite(x))throw Error('nonfinite');peak=Math.max(peak,Math.abs(x));power+=x*x;}if(peak>.95||power/samples.length<1e-10)throw Error('level '+row.path);}
    count++;
   }
   await ctx.close();return count;
  });assert.equal(decoded,225);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({suite:'STANDALONE_BROWSER',actualAudio:true,decodedFiles:decoded,controls:'all tensions, bank, boss, fanfare return, stop/restart',stats}));
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
