local e=dofile('tools/music_test_fixture.lua');local check=e.check
CLIENT=true;dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua');dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
local D=LOD.MusicDirector;local M=LOD.Music;D.ServerOn=true
local p=M.Plan(e.catalog(),{set='all'},17,'run:1',4,1);D.Plans[p.id]=p
D.Current={sequence=1,epoch=1,plan=p.id,role='INTERLUDE',staged=true,targets={{block=p.floors[1],weight=1}},remaining=-1}
D:Tick();local panel=e.panel;check(panel.visible and panel.allowLua==false,'invisible painting retains JS processing without arbitrary Lua')
D.Error='old startup failure';panel.functions['lodms2.ready']('surge-rendered',e.now);D:Sync()
check(D.Ready and D.Synced,'actual local phrase metadata and current state handed to renderer')
check(not D.ReadyDeadline,'ready renderer has no pending startup timeout')
check(table.Count(D.Payloads)==1,'one current arrangement loaded')
check(not D.Error,'valid phrases accepted')
-- A failed native backend after its startup deadline must leave one fixed
-- backoff, rather than repeatedly timing out the already removed HTML panel.
local N=LOD.MusicNative
e.now=e.now+6;N.Errors=3;N.Error='Surge phrase open failed: delta_t0_000 (2: BASS_ERROR_FILEOPEN)'
D:Tick();local retryAt=D.RetryAt;local failedPanel=panel
check(not D.Ready and not failedPanel.valid,'native failure tears down the renderer')
check(D.Error==N.Error,'native failure reason is surfaced')
e.now=e.now+.25;D:Tick()
check(D.RetryAt==retryAt and D.Error==N.Error,'backoff does not slide or overwrite the native failure')
e.now=retryAt-.01;D:Tick();check(e.panel==failedPanel,'retry waits for its fixed deadline')
e.now=retryAt+.25;D:Tick();panel=e.panel
check(panel~=failedPanel and panel.valid,'native failure creates one fresh renderer after backoff')
panel.functions['lodms2.ready']('surge-rendered',e.now);D:Sync()
check(D.Ready and D.Synced and not D.Error,'recovered renderer receives the retained current plan')
local target=D.AudibleTargets[1];local clip=D.Catalog.assets[target.asset].clips[1].id
panel.functions['lodms2.mix'](target.block,1)
panel.functions['lodms2.prepare']('1',target.block,clip,1,e.now+1)
local plays=e.plays;e.now=e.now+1;D:Tick()
check(e.plays==plays+1 and D.Ready and N.Errors==0,'recovered native channel starts a fresh phrase on time')
local calls=#panel.calls;D:Sync();check(#panel.calls==calls,'unchanged state adds no JS work')
D:Announce(p.floors[1]);local n=#e.announced
D.Current.role='T3';D.Synced=nil;D:Sync();D:Announce(p.floors[1]);check(#e.announced==n,'tension change does not repeat block name')
D.Current.targets={{block=p.floors[1],weight=.5},{block=p.floors[2],weight=.5}};D.Synced=nil;D:Sync()
D:Announce(p.floors[2]);check(#e.announced==n+1,'incoming stairs block announced once')
D:Announce('unassigned');check(#e.announced==n+1,'unknown callback cannot announce a block')
local oldReady=panel.functions['lodms2.ready'];e.set('lod_music',0)
check(not D.Ready and not panel.valid and not next(D.Payloads),'Off destroys renderer and releases metadata caches')
oldReady('surge-rendered',e.now);check(not D.Ready,'stale browser callback cannot resurrect playback')
local decoded=0;util.Decompress=function() decoded=decoded+1 end
e.receive('LOD_MusicPlan','ignored',1,1,4,'data');check(decoded==0,'Off skips plan decoding')
e.set('lod_music',1);e.now=e.now+.25;D:Tick();local unready=e.panel
check(unready~=panel and unready.valid and D.ReadyDeadline,'On after an expired deadline starts a fresh panel')
e.now=D.ReadyDeadline+.25;D:Tick();retryAt=D.RetryAt
check(not unready.valid and not D.ReadyDeadline,'real startup timeout removes only its own pending deadline')
e.now=e.now+.25;D:Tick()
check(D.RetryAt==retryAt and D.Error=='MS2 renderer did not initialize','startup timeout also keeps a fixed retry deadline')
e.now=retryAt+.25;D:Tick();panel=e.panel
check(panel~=unready and panel.valid,'startup timeout recovers after one backoff')
panel.functions['lodms2.ready']('surge-rendered',e.now);D:Sync()
check(D.Ready and not D.ReadyDeadline and not D.RetryAt,'successful startup clears both lifecycle deadlines')
print('MUSIC_CLIENT PASS '..e.checks)
