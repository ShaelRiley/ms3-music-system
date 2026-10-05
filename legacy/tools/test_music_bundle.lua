-- Reproduce nested GMod include resolution and exercise the real startup seams.
local e=dofile('tools/music_test_fixture.lua');local check=e.check
local root='legend_of_deborah/gamemode/lod/ms2/'
local ok=pcall(include,'lod/ms2/catalog.lua')
check(not ok,'old root-relative path fails from the nested music module')
for _,directory in ipairs({'legend_of_deborah/gamemode/','legend_of_deborah/gamemode/lod/',''}) do
 e.luaDirectory=directory
 check(LOD.Music.LoadBundled(),'catalog loads during startup and rootless callbacks')
end
e.luaDirectory='legend_of_deborah/gamemode/lod/'
SERVER=true;CLIENT=false
LOD.RunManager={State={},GetPlayerState=function() return {} end}
player={GetAll=function() return {} end}
dofile('gamemodes/legend_of_deborah/gamemode/lod/sv_music.lua')
check(LOD.MusicDirector.Catalog,'server startup admits the bundled catalog')
CLIENT=true;SERVER=false
e.cacheOnly=true
check(not file.Exists(root..'catalog.lua','LUA'),'remote client has no loose catalog file')
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua')
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
local D=LOD.MusicDirector
D.ServerOn=true
local plan=assert(LOD.Music.Plan(e.catalog(),{set='all'},17,'bundle-run',4,1))
D.Plans[plan.id]=plan
D.Current={sequence=1,epoch=1,plan=plan.id,role='T0',staged=true,targets={{block=plan.floors[1],weight=1}}}
D:Tick()
check(e.panel and e.panel.html:find('MS2',1,true),'client loads the actual phrase-control engine')
e.panel.functions['lodms2.ready']('surge-rendered',e.now);D:Sync()
check(D.Ready and D.Synced and next(D.Payloads),'client hands phrase metadata and state to playback')
-- Peak metadata is part of safe gain admission, not an optional diagnostic.
local M=LOD.Music;local original=M.IncludeBundled
local render=util.JSONToTable(assert(original('render.lua')),true)
local clipId=next(render.clips);local clip=render.clips[clipId];local peak=clip.peak
local function alteredBank() return util.TableToJSON(render) end
M.IncludeBundled=function(name) if name=='render.lua' then return alteredBank() end;return original(name) end
for _,bad in ipairs({0,-.1,1,'0.2'}) do
 clip.peak=bad;check(not M.LoadRenderBank(D.Catalog),'unsafe phrase peak is rejected before native amplification')
end
clip.peak=nil;check(not M.LoadRenderBank(D.Catalog),'missing phrase peak is rejected before native amplification')
clip.peak=peak;render.bridge.peak=0
check(not M.LoadRenderBank(D.Catalog),'unsafe bridge peak is rejected before native amplification')
render.bridge.peak=.04
local tailPeak=clip.tailPeak
for _,bad in ipairs({-.1,peak+1,'0.1'}) do
 clip.tailPeak=bad;check(not M.LoadRenderBank(D.Catalog),'unsafe tail peak is rejected before steady join admission')
end
clip.tailPeak=nil;check(not M.LoadRenderBank(D.Catalog),'missing tail peak is rejected before steady join admission')
clip.tailPeak=tailPeak
check(M.LoadRenderBank(D.Catalog),'complete finite peak metadata admits playback')
M.IncludeBundled=original
e.realBundle=true
local files=assert(LOD.Music.IncludeBundled('files.lua'))
for _,name in ipairs(files) do
 local raw=assert(LOD.Music.IncludeBundled(name))
 check(type(raw)=='string' and #raw>0,'real distributed score file loads: '..name)
end
e.realBundle=false
SERVER=true;CLIENT=false
local missing=root..'catalog.lua';e.missingLua[missing]=true
local calls=#e.includeCalls
local catalog,err=LOD.Music.LoadBundled()
check(not catalog and err:find(missing,1,true),'missing mount reports its exact virtual path')
check(#e.includeCalls==calls,'missing catalog skips the noisy engine include')
e.missingLua[missing]=nil
check(LOD.Music.LoadBundled(),'a complete mount can recover')
print('MUSIC_BUNDLE PASS '..e.checks)
