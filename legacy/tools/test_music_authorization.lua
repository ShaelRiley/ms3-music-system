-- Execute real client/server MusicDirectors in isolated Lua realms. Only the
-- engine packet, userinfo, VGUI and JSON boundaries are doubled; no client
-- server-master convar is manufactured or replicated into the client realm.
local function realm()
 local env=setmetatable({}, {__index=_G});env._G=env
 env.dofile=function(path) return assert(loadfile(path,'t',env))() end
 local fixture=env.dofile('tools/music_test_fixture.lua')
 return env,fixture
end
local s,se=realm();s.SERVER=true;s.CLIENT=false
local check=se.check
local p={valid=true,preference=1}
function p:IsListenServerHost() return self.host==true end
function p:IsSuperAdmin() return self.admin==true end
function p:GetInfoNum(_,default) return self.preference or default end
function p:GetNW2Bool() return true end
function p:Health() return 100 end
function p:GetMaxHealth() return 100 end
function p:ChatPrint() end
s.player={GetAll=function() return {p} end}
local state={RunId='authorization',CampaignEpoch=1,CampaignSeed=7,Level=1,BuildReady=true}
s.LOD.RunManager={State=state,GetPlayerState=function() return {} end}
s.dofile('gamemodes/legend_of_deborah/gamemode/lod/sv_music.lua')
local server=s.LOD.MusicDirector;local master=s.GetConVar('lod_music_enabled')
function master:SetBool(on) se.set('lod_music_enabled',on and 1 or 0) end
local c,ce,client,music,pending
local received={};local serverCursor=1;local clientCursor=1
local function makeClient(preference,volume)
 c,ce=realm();c.CLIENT=true;c.SERVER=false
 if preference then c.CreateClientConVar("lod_music",tostring(preference));p.preference=preference end
 if volume then c.CreateClientConVar("lod_music_volume",tostring(volume)) end
 c.LocalPlayer=function() return p end
 c.util.TableToJSON=s.util.TableToJSON;c.util.JSONToTable=s.util.JSONToTable
 local callback=c.cvars.AddChangeCallback
 c.cvars.AddChangeCallback=function(name,fn,id)
  check(c.GetConVar(name)~=nil,'client callback must name a real local convar: '..name)
  callback(name,fn,id)
 end
 c.dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua')
 c.dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
 client=c.LOD.MusicDirector;pending={};clientCursor=1
 c.RunConsoleCommand=function(name,value) pending[#pending+1]={name,value} end
 local originalCreate=c.vgui.Create;local controls={}
 c.vgui.Create=function(kind)
  if kind=='DHTML' then return originalCreate(kind) end
  local panel={valid=true,wide=980,Label={SetTextColor=function() end}}
  for _,name in ipairs({'SetPos','Center','SetTitle','MakePopup','SetFont','SetTextColor','SizeToContents','SetMinMax','SetDecimals','SetConVar'}) do panel[name]=function() end end
  function panel:SetSize(w) self.wide=w end
  function panel:GetWide() return self.wide end
  function panel:SetText(text) self.text=text end
  function panel:SetChecked(on) self.checked=on end
  function panel:GetChecked() return self.checked end
  function panel:Remove() self.valid=false end
  controls[#controls+1]=panel;return panel
 end
 c.ScrW=function() return 1280 end;c.ScrH=function() return 720 end
 c.input={LookupBinding=function() return 'shift' end}
 c.LOD.PlayerOptions={};c.LOD.UI={Colors={ink={}},IsMinigameLocked=function() return false end,
  SelectPage=function() end,CloseButton=function() end,PageLinks=function() end}
 c.dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_player_options.lua')
 c.LOD.PlayerOptions:Open()
 for _,control in ipairs(controls) do if control.text=='Music' then music=control end end
 check(music and #pending==0,'opening the production Options UI is read-only')
 check(c.GetConVar('lod_music_enabled')==nil,'dedicated client has no local server master')
end
local function flushCommands()
 for _,row in ipairs(pending) do ce.set(row[1],row[2]) end
 pending={};p.preference=client.Preference:GetInt()
end
local function clientPackets()
 while clientCursor<=#(ce.sent or {}) do
  local packet=ce.sent[clientCursor];clientCursor=clientCursor+1
  if packet.name=='LOD_MusicDemand' then
   se.read=s.table.Copy(packet.args);se.wire.LOD_MusicDemand(#packet.args,p)
  end
 end
end
local function serverPackets()
 while serverCursor<=#(se.sent or {}) do
  local packet=se.sent[serverCursor];serverCursor=serverCursor+1
  if packet.player==p and ce.wire[packet.name] then
   received[packet.name]=(received[packet.name] or 0)+1
   ce.read=c.table.Copy(packet.args);ce.wire[packet.name](1024)
  end
 end
end
local function pump(backend)
 for _=1,20 do
  se.now=se.now+.2;ce.now=se.now
  clientPackets();server:Update(p,state);serverPackets();ce.hooks.LOD_MusicMix()
  if backend and ce.panel and ce.panel.valid and not client.Ready then
   ce.panel.functions['lodms2.ready'](backend,ce.now);client:Sync()
  end
 end
 music:Think()
end
local function choose(on)
 music:SetChecked(on);music:OnChange(on)
end
local function status()
 local line;c.print=function(value) line=value end
 ce.commands.lod_music_client_status()
 return assert(c.util.JSONToTable(assert(line):gsub('^%[LOD:MUSIC%] ','')))
end
makeClient()
ce.hooks.LOD_MusicDemand();pump()
check(not master:GetBool() and not client:Enabled() and not client.Ready,'startup demand cannot enable a default-Off server')
choose(true);clientPackets();flushCommands();pump()
check(not master:GetBool() and not client.ServerOn,'normal Options On cannot elevate server permission')
master:SetBool(true);serverPackets();pump()
check(client.ServerOn==true and client:Enabled()==true,'server switch authorizes opted-in dedicated client without a local master')
check(received.LOD_MusicSwitch and received.LOD_MusicPlan and received.LOD_MusicState,'real server switch and chunked plan/state reach the client')
check(client.Current and next(client.Plans) and ce.panel.valid,'authorization starts the renderer with real server metadata')
local pendingStatus=status()
check(pendingStatus.enabled and not pendingStatus.ready and pendingStatus.startupPending,'diagnostics expose genuine initializing renderer state')
ce.panel.functions['lodms2.ready']('surge-sample-clock',ce.now);client:Sync()
local readyStatus=status()
check(readyStatus.system=='MS3' and readyStatus.enabled and readyStatus.ready and not readyStatus.startupPending
 and readyStatus.backend=='surge-sample-clock' and readyStatus.streamedBytes==0,'diagnostics reflect actual ready callback and bundled backend')
check(readyStatus.serverAuthorized and readyStatus.preference and readyStatus.volume>0 and readyStatus.demand,'status exposes actual authorization inputs')
check(music:GetChecked() and client.Synced,'Options and renderer reflect authorization')
-- Off wins immediately, before its packet/userinfo reaches the server.
local oldPanel=ce.panel;local staleReady=oldPanel.functions['lodms2.ready']
choose(false);flushCommands()
check(not client:Enabled() and not client:OptionEnabled() and not oldPanel.valid,'local Off tears down playback immediately')
local offStatus=status();check(offStatus.serverAuthorized and not offStatus.preference and not offStatus.enabled,'diagnostic distinguishes immediate local Off from pending server revocation')
staleReady('surge-sample-clock',ce.now);check(not client.Ready,'stale renderer callback cannot resurrect Off playback')
clientPackets();serverPackets();check(not client.ServerOn and master:GetBool(),'personal Off revokes only that listener, never the server master')
choose(true);clientPackets();flushCommands();pump('surge-sample-clock')
check(client:Enabled() and client.Ready and music:GetChecked(),'Options On restores authorized playback')
ce.set('lod_music_volume',0)
check(not client:Enabled() and not client.Ready and not client.DemandOn,'zero volume immediately stops renderer and demand')
clientPackets();serverPackets();check(not client.ServerOn,'zero volume receives server revocation')
ce.set('lod_music_volume',.99);pump('surge-rendered')
check(client:Enabled() and client.Ready and client.Backend=='surge-rendered','nonzero volume restores authorization and native fallback without restart')
master:SetBool(false);serverPackets()
check(not client.ServerOn and not client:Enabled() and not client.Ready,'server master Off immediately stops authorized playback')
master:SetBool(true);serverPackets();pump('surge-sample-clock')
check(client:Enabled() and client.Ready,'server master On reauthorizes eligible listener')
-- Same-realm metadata resync and a fresh dedicated-client reconnect each use
-- the normal startup demand, not a console master override.
local planId=client.Current.plan;client:Stop();client.Plans={};client.Current=nil
ce.hooks.LOD_MusicDemand();pump('surge-sample-clock')
check(client.Ready and client.Current.plan==planId and client.Plans[planId],'InitPostEntity resync restores frozen plan and authorization')
ce.hooks.LOD_MusicShutdown();se.hooks.LOD_MusicLeave(p)
check(server.Listeners[p]==nil,'disconnect releases server listener')
makeClient();ce.now=se.now
check(not client.ServerOn and not client:Enabled(),'new client starts unauthorized')
ce.hooks.LOD_MusicDemand();pump('surge-sample-clock')
check(client.Ready and client:Enabled() and client.Current.plan==planId,'rejoin authorizes automatically with unchanged frozen assignment')
-- Presentation errors are contained by the real Think hook; gameplay state is
-- unchanged and playback can initialize after the bounded retry.
client:Stop();local before=s.util.TableToJSON(state);local create=c.vgui.Create
c.vgui.Create=function(kind) if kind=='DHTML' then error('fixture renderer failure') end;return create(kind) end
pump();check(not client.Ready and client.Error:find('fixture renderer failure',1,true),'renderer failure stays nonfatal and reports its real reason')
check(s.util.TableToJSON(state)==before,'renderer failure does not mutate gameplay')
c.vgui.Create=create;se.now=client.RetryAt+1;ce.now=se.now;pump('surge-sample-clock')
check(client.Ready,'renderer recovers after fixed backoff')
-- Authorized operators can enable the master only through explicit Options On.
for _,role in ipairs({'admin','host'}) do
 p.admin=false;p.host=false;p[role]=true;master:SetBool(false);serverPackets();music:Think()
 check(not client:OptionEnabled() and not music:GetChecked(),'operator checkbox reflects server denial without local master: '..role)
 ce.hooks.LOD_MusicDemand();pump()
 check(not master:GetBool(),'operator reconnect does not implicitly enable master: '..role)
 choose(true);clientPackets();flushCommands();pump('surge-sample-clock')
 check(master:GetBool() and client.ServerOn and music:GetChecked(),'explicit operator Options On grants authoritative permission: '..role)
 choose(false);flushCommands();clientPackets();serverPackets()
 check(master:GetBool() and not client:Enabled(),'operator Off remains personal: '..role)
 choose(true);clientPackets();flushCommands();pump('surge-sample-clock')
end
p.admin=false;p.host=false
for _,saved in ipairs({{0,.99},{1,0}}) do
 ce.hooks.LOD_MusicShutdown();se.hooks.LOD_MusicLeave(p)
 makeClient(saved[1],saved[2]);ce.now=se.now
 ce.hooks.LOD_MusicDemand();pump()
 check(not client.ServerOn and not client:Enabled() and not client.Ready,'rejoin preserves saved Off/zero-volume preference')
end
check(c.GetConVar('lod_music_enabled')==nil and not ce.callbacks.lod_music_enabled,'client never creates or observes a fake server-master convar')
print('MUSIC_AUTHORIZATION PASS '..se.checks..': isolated realms, actual packet flow, Options, mute/volume, reconnect, diagnostics and nonfatal renderer')
