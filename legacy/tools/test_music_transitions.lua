local e=dofile('tools/music_test_fixture.lua');local check=e.check
CLIENT=true;dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua');dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
local D=LOD.MusicDirector;local M=LOD.Music;D.ServerOn=true
local p=M.Plan(e.catalog(),{set='all'},17,'run:1',4,1);local q=M.Plan(e.catalog(),{set='all'},31,'run:2',4,1)
D.Plans[p.id]=p;D.Plans[q.id]=q;D:StartRenderer();e.panel.functions['lodms2.ready']('surge-rendered',e.now)
local function post(sequence,receipt,at)
 e.receive('LOD_MusicState',util.TableToJSON({sequence=sequence,epoch=1,plan=p.id,role='POST',targets={{block=p.floors[1],weight=1}},
  next=q.id,nextBlock=q.floors[1],policy='auto',canVictory=true,victory=receipt,startedAt=at or e.now,endsAt=e.now+6.5}))
end
post(1,'clear1');check(D:Desired().role=='VICTORY','accepted clear offers exactly one fanfare')
D:Sync();check(D.Victory.started and D.SeenVictory.clear1,'once-only receipt recorded at renderer admission')
post(2,'clear1');check(D.Victory.id=='clear1' and D.Victory.started,'duplicate packet preserves existing fanfare')
e.panel.functions['lodms2.victory']();local state=D:Desired()
check(state.role=='INTERLUDE' and state.targets[1].block==q.floors[1],'completion moves to upcoming first-floor Chill')
e.receive('LOD_MusicState',util.TableToJSON({sequence=3,epoch=1,plan=q.id,role='INTERLUDE',staged=true,targets={{block=q.floors[1],weight=1}}}))
check(D:Desired().targets[1].block==q.floors[1],'next staging retains assigned block')
D.Plans[p.id]=p;post(4,'clear1');check(not D.Victory,'later duplicate clear cannot replay after staging transition')
e.now=40;post(5,'clear2',e.now-20);D.Victory.endsAt=e.now-1
check(D:Desired().role=='INTERLUDE' and D.SeenVictory.clear2,'late fanfare is skipped without interrupting quiet music')
D:RememberVictory('clear3');check(table.Count(D.SeenVictory)<=2,'victory history remains bounded in endless play')
print('MUSIC_TRANSITIONS PASS '..e.checks)
