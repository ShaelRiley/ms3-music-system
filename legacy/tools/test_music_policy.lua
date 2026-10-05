local e=dofile('tools/music_test_fixture.lua');local M=LOD.Music;local check=e.check
local c=e.catalog();check(M.ValidateCatalog(c),'MS2 catalog accepts all role defaults')
local p=assert(M.Plan(c,{set='all',post_victory='auto'},17,'run:1',4,1))
local q=assert(M.Plan(c,{set='all',post_victory='auto'},17,'run:1',4,1))
check(table.concat(p.floors)==table.concat(q.floors),'dedicated music seed reproduces floors')
local seen={};for _,id in ipairs(p.floors) do seen[id]=true end
check(table.Count(seen)==4,'distinct floors with sufficient blocks')
check(#M.Pool(c,'pair')==2,'deduplicated sorted sets')
local small=assert(M.Plan(c,{set='pair'},17,'run:2',8,1))
for _,id in ipairs(small.floors) do check(id=='alpha' or id=='beta','restricted pool never broadens') end
check(not M.Pool(c,'missing'),'unknown sets rejected')
for _,role in ipairs(M.Roles) do
 local candidates=M.Candidates(c,c.blocks.alpha,role,{})
 check(#candidates==1 and candidates[1].source=='first-block-default','correct per-role inherited source '..role)
end
local b=c.blocks.alpha;b.roles.BOSS='delta-boss'
check(M.Candidates(c,b,'BOSS',{})[1].source=='custom','custom first')
check(M.Candidates(c,b,'BOSS',{universal_boss=true})[1].source=='first-block-default','universal override excludes custom')
c.blocks.alpha.title='Changed';c.blocks.delta.roles.T0='changed'
check(p.blocks.alpha.title=='alpha' and p.assets['delta-t0'].id=='delta-t0','plan sources/titles frozen')
local bad=e.catalog();bad.schema=1;check(not M.ValidateCatalog(bad),'streaming catalogs rejected')
bad=e.catalog();bad.assets['delta-t0'].clips[1].page='../unsafe.lua';check(not M.ValidateCatalog(bad),'unsafe note page rejected')
bad=e.catalog();bad.blocks.delta.roles.VICTORY='delta-boss';check(not M.ValidateCatalog(bad),'role mismatch rejected')
bad=e.catalog();bad.assets['delta-t0'].clips[1].next={'unknown'};check(not M.ValidateCatalog(bad),'broken transition graph rejected')
local state=M.Pressure(nil,{staging=true,hits=8,hp=.01,remaining=1,recent=true},0)
check(state.value==0,'staging remains calm')
state=M.Pressure(state,{hits=0,hp=1,remaining=800,recent=true},1)
state=M.Pressure(state,{hits=0,hp=1,remaining=800,recent=true},5)
check(state.value==1,'controlled escalation retained')
state=M.Pressure(state,{hits=3,hp=.1,remaining=800,recent=true},6)
check(state.value==3,'urgent survival bypasses dwell')
print('MUSIC_POLICY PASS '..e.checks)
