-- Production plan/file authorization, staging selection, and native residency.
local e=dofile('tools/music_test_fixture.lua');local check=e.check
CLIENT=true;dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua');dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
local D,M,N=LOD.MusicDirector,LOD.Music,LOD.MusicNative
local c=e.catalog();c.songFirst=true
for _,a in pairs(c.assets) do
 a.songFirst=true;a.songBeats=0
 for i,clip in ipairs(a.clips) do
  clip.offset=a.songBeats;clip.songIndex=i-1;clip.musicalFrames=math.floor(clip.beats*60/130*44100+.5);a.songBeats=a.songBeats+clip.beats
 end
end
check(M.ValidateCatalog(c)==c,'complete ordered song catalog validates')
for _,mutation in ipairs({'songIndex','offset','musicalFrames','songBeats'}) do
 local broken=table.Copy(c);local a=broken.assets['delta-t1']
 if mutation=='songBeats' then a.songBeats=a.songBeats+4 else a.clips[1][mutation]=a.clips[1][mutation]+5 end
 check(not M.ValidateCatalog(broken),'malformed ordered song rejected: '..mutation)
end
D.Catalog=c;local plan=assert(M.Plan(c,{set='all'},17,'song-plan',4,1));D.Plans={[plan.id]=plan}
local bid=plan.floors[1]
D.Current={plan=plan.id,role='T0',staged=true,targets={{block=bid,weight=1}},seed=17}
check(D:Desired().targets[1].asset=='delta-t0','staging retains full calm composition')
D.Current.staged=false
check(D:Desired().targets[1].asset=='delta-t1','calm maze pressure retains a driving edit')
D.Current.role='POST';D.Current.policy='off'
check(D:Desired().targets[1].asset=='delta-t0','post-victory calm remains intentional')
D.Current.role='T3';D.AudibleTargets={{block=bid,weight=1,asset='delta-t3'}}
check(M.ClipAsset(c,D.AudibleTargets,D.Plans,'song','delta_t1_000')==c.assets['delta-t1'],'old song remains authorized after ordinary preference changes')
check(not M.ClipAsset(c,D.AudibleTargets,{},'song','delta_t1_000'),'no plan cannot authorize a song read')
local stale=table.Copy(plan);stale.revision='outdated'
check(not M.ClipAsset(c,D.AudibleTargets,{stale},'song','delta_t1_000'),'stale catalog plan cannot authorize a song read')
check(not M.ClipAsset(c,D.AudibleTargets,D.Plans,'song','../bad'),'arbitrary paths cannot authorize a song read')
local restricted=table.Copy(plan);restricted.assets['delta-t1']=nil
check(not M.ClipAsset(c,D.AudibleTargets,{restricted},'song','delta_t1_000'),'unassigned local assets cannot authorize a song read')
check(not M.ClipAsset(c,D.AudibleTargets,D.Plans,'unregistered','delta_t1_000'),'unregistered lanes cannot authorize a song read')
local bank={bpm=130,clips={},bridge={duration=4,peak=.04}}
for _,a in pairs(c.assets) do for _,clip in ipairs(a.clips) do
 bank.clips[clip.id]={beats=clip.beats,musicalFrames=clip.musicalFrames,duration=clip.musicalFrames/44100+.55,peak=.12,tailPeak=.01}
end end
local results={};N:Configure(c,bank,function(token,on) results[token]=on end)
N:SyncClock(e.now);N:SetMix('song',1);N:SetVolume(.55)
local start=e.now+1;N:Prepare('1','song','delta_t1_000',1,start)
e.now=start;N:Tick();check(results['1'],'native starts old composition even though desired tension has changed')
local record;for _,r in pairs(N.Records) do if r.token=='1' then record=r end end
check(record and record.musical==bank.clips.delta_t1_000.musicalFrames/44100,'native uses the exact continuous-performance frame period')
local holds=N.HeldLoops;e.now=start+record.musical;N:Tick()
check(N.HeldLoops==holds+1,'native song lane holds resident chunk while preparation is late')
N:Stop();check(N:Count()==0,'Off releases native song records')
print('MS3_SONG_POLICY PASS '..e.checks)
