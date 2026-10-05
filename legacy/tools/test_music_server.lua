local e=dofile('tools/music_test_fixture.lua');local check=e.check
SERVER=true
local p={valid=true,staged=true,pos=Vector(100,100,0),on=1,ground=true}
function p:GetInfoNum() return self.on end
function p:ChatPrint() end
function p:GetNW2Bool() return self.staged end
function p:Alive() return true end
function p:OnGround() return self.ground end
function p:GetPos() return self.pos end
function p:IsPlayer() return true end
function p:Health() return self.hp or 100 end
function p:GetMaxHealth() return 100 end
function p:IsSuperAdmin() return self.admin end
e.player=p;player={GetAll=function() return {p} end}
local ps={deploymentComplete=true}
local graph={Cells={['1:1:0']={x=1,y=1,z=0},['1:1:1']={x=1,y=1,z=1}},Width=1,Height=1,Layers=2,VerticalEdges={},Progression={}}
local s={RunId='run1',CampaignEpoch=1,CampaignSeed=7,Level=1,BuildReady=true,Graph=graph}
LOD.RunManager={State=s,GetPlayerState=function() return ps end}
local events={};LOD.CombatRolls={_Send=function(_,owner,cat,text,family,fields) events[#events+1]={owner=owner,text=text,family=family,fields=fields} end}
LOD.CampaignTimeout={Remaining=function(_,clock) return clock.remaining end}
dofile('gamemodes/legend_of_deborah/gamemode/lod/sv_music.lua')
local D=LOD.MusicDirector;D.Catalog=e.catalog()
check(not D:Enabled(p),'master disabled by default')
local plan=D:Prepare(s,1)
local baseline=table.concat(plan.floors)
check(D:Configure('set','pair'),'valid set accepted')
check(table.concat(D:Prepare(s,1).floors)==baseline,'active plan remains frozen')
check(not D:Configure('set','missing') and D.Settings.set=='pair','invalid setting preserves prior selection')
local nextPlan=D:Prepare(s,2)
for _,id in ipairs(nextPlan.floors) do check(id=='alpha' or id=='beta','future plan applies saved restriction') end
local l=D:Listener(p);l.demand=true;local target=D:Target(p,l,s)
check(target.role=='INTERLUDE' and target.targets[1].block==plan.floors[1],'staging binds upcoming physical Floor1')
p.staged=false;local deployed=D:Target(p,l,s)
check(deployed.plan==target.plan and deployed.targets[1].block==target.targets[1].block,'portal no reroll/restart')
s.CampaignClock={remaining=50};target=D:Target(p,l,s)
check(target.role=='T3','uses effective canonical timer')
s.CampaignClock.remaining=800;e.now=e.now+7;D:Target(p,l,s);e.now=e.now+7;target=D:Target(p,l,s)
check(target.role=='T0','real time extension relaxes normally')
s.Graph.Progression.Warden={entry={x=1,y=1,z=0},court={['1:1:0']=true}}
s.Warden={started=true,dead=false};target=D:Target(p,l,s)
check(target.role=='BOSS','committed arena dedicated loop')
s.Level=20;s.Warden.dead=true;LOD.Hector={RescueAllowed=function() return false end}
target=D:Target(p,l,s);check(target.role=='BOSS','Gordon to Hector handoff keeps boss role')
LOD.Hector.RescueAllowed=function() return true end
target=D:Target(p,l,s);check(target.role=='T0','boss defeat alone is calm, not victory')
s.Level=1;s.Warden=nil;s.Graph.Progression.Warden=nil
-- Actual start ACK goes through canonical private record path, never a title from the client.
e.set('lod_music_enabled',1);for i=1,60 do e.now=e.now+.2;D:Update(p,s) end;l=D:Listener(p)
local bid=l.plans[1].floors[1];e.receive('LOD_MusicPlaying',l.sequence,1,bid)
check(#events==1 and events[1].family=='music' and events[1].text=='Now playing: '..plan.blocks[bid].title,'private canonical authored name')
e.now=e.now+1;e.receive('LOD_MusicPlaying',l.sequence,2,bid);check(#events==1,'duplicate confirmation deduplicated')
e.now=e.now+1;e.receive('LOD_MusicPlaying',l.sequence,3,'not-authorized');check(#events==1,'unassigned/spoofed block rejected')
s.LevelCleared=true;D:ClearAccepted(s);local receipt=s.MusicVictory
D:ClearAccepted(s);check(s.MusicVictory==receipt,'single accepted clear receipt')
target=D:Target(p,l,s);check(target.role=='POST' and target.canVictory,'only clear offers one-shot')
e.hooks.LOD_MusicLeave(p);check(not receipt.participants[p],'reconnect cannot replay clear')
s.Level=2;s.LevelCleared=false;s.BuildReady=false;target=D:Target(p,D:Listener(p),s)
check(target.role=='POST' and target.victory==receipt.id,'bridge survives successful old-maze cleanup')
s.BuildReady=true;p.staged=true;target=D:Target(p,D:Listener(p),s)
check(target.plan==nextPlan.id and target.role=='INTERLUDE','next staging exact preplanned Chill')
e.set('lod_music_enabled',0);D:Update(p,s);check(not D:Enabled(p),'server off overrides player on')
check(not D:Configure('post_victory','bad'),'invalid policy rejected')
for _,role in ipairs({'boss','victory','interlude'}) do
 check(D:Configure('universal_'..role,'1'),'independent override on')
 check(D:Configure('universal_'..role,'0'),'independent override off')
end
-- Explicit opt-out precedes plan generation, serialization and pressure work.
local M=LOD.Music;local targets=0;local targetMethod=D.Target
function D:Target(...) targets=targets+1;return targetMethod(self,...) end
local function demand(on,work)
 e.read={on,work};e.wire.LOD_MusicDemand(2,p)
end
e.set('lod_music_enabled',1);demand(false,false)
local sent=#e.sent
for i=1,100 do e.now=e.now+.2;D:Update(p,s) end
check(targets==0 and #e.sent==sent,'opted-out listener receives no plans/states and performs no target work')
demand(true,true);local compressed=0;local originalCompress=util.Compress
util.Compress=function(v) compressed=compressed+1;return originalCompress(v) end
local l=D:Listener(p);l.sent={};D.PlanPackets=setmetatable({}, {__mode='k'})
for i=1,60 do e.now=e.now+.2;D:Update(p,s) end
check(l.snapshot and l.snapshot.role=='INTERLUDE','re-enable resumes current staging Chill')
check(compressed==1,'immutable plan compressed once')
for _,packet in ipairs(e.sent) do
 if packet.name=='LOD_MusicPlan' then check(packet.args[4]<=M.Limits.planChunk,'plan pieces fit the 1 KiB body budget') end
end
local oldPackets=#e.sent;local originalJSON=util.TableToJSON;local serializations=0
util.TableToJSON=function(v) serializations=serializations+1;return originalJSON(v) end
for i=1,50 do e.now=e.now+.2;D:Update(p,s) end
check(#e.sent==oldPackets and serializations==0,'unchanged staging emits no packets or JSON work')
-- A second listener reuses the encoded plan, not another compression pass.
local second=setmetatable({valid=true,staged=true,on=1},{__index=p});local other=D:Listener(second);other.demand=true
for i=1,60 do e.now=e.now+.2;D:Update(second,s) end
check(compressed==1 and other.snapshot,'another listener shares immutable wire cache')
function p:PacketLoss() return self.loss or 0 end
p.loss=3;e.now=e.now+.2;local previous=targets;D:Update(p,s)
check(not l.budget and targets==previous,'packet loss suspends metadata and pressure work')
p.loss=0;e.now=e.now+2;D:Update(p,s);check(not l.budget,'server recovery hysteresis retains suspension')
e.now=e.now+4;D:Update(p,s);check(l.budget and targets>previous,'server resumes after healthy recovery')
l.sent={};l.sending={};l.planAt=nil;D.WireBudget=100
check(not D:SendPlan(p,l,nextPlan) and not next(l.sending),'plan defers when global gameplay-first metadata budget is exhausted')
D.WireBudget=nil
-- Staging can play from its frozen plan while geometry is still being built.
s.MusicVictory=nil;s.BuildReady=false
target=D:Target(p,l,s);check(target.role=='INTERLUDE' and target.targets[1].block==nextPlan.floors[1],'building does not silence staging Chill')
s.Failed=true;p.loss=3;e.now=e.now+.2;D:Update(p,s)
check(l.snapshot.stop==true,'failure stop bypasses optional congestion deferral')
e.now=e.now+1;e.read={true,true,true};e.wire.LOD_MusicDemand(3,p)
check(not l.snapshot and not next(l.sent) and l.on==nil,'client refresh can request bounded plan and permission resynchronization')
-- Exercise the actual operator diagnostic with native TextMsg-sized pieces.
local originalPrint=print;local printed;local messages={}
print=function(text) printed=text end
function p:EntIndex() return 1 end
function second:EntIndex() return 2 end
function p:ChatPrint(text)
 check(#text<=200,'status stays below the native TextMsg payload ceiling')
 check(utf8.len(text)~=nil,'diagnostic chunks preserve UTF-8 boundaries')
 messages[#messages+1]=text
end
p.admin=true;D.Warning=string.rep('é…',250)
e.commands.lod_music_status(p)
check(#messages>1 and table.concat(messages)==printed,'complete operator status survives bounded native messages')
local diagnostic=util.JSONToTable(printed:gsub('^%[LOD:MUSIC%] ',''))
check(diagnostic.system=='MS3' and diagnostic.delivery=='bundled-Surge/local-playback','server diagnostic describes the current renderer architecture')
check(diagnostic.enabled==GetConVar('lod_music_enabled'):GetBool(),'server diagnostic reports the real master value')
p.admin=false;local before=#messages;e.commands.lod_music_status(p)
check(#messages==before,'diagnostic remains operator-only')
print=originalPrint
print('MUSIC_SERVER PASS '..e.checks)
