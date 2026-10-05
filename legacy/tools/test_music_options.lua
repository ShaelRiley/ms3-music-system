local e=dofile('tools/music_test_fixture.lua');local check=e.check
SERVER=true;CLIENT=false
local host={valid=true,host=true}
function host:IsListenServerHost() return self.host end
function host:IsSuperAdmin() return self.admin==true end
function host:GetInfoNum(_,default) return self.preference or default end
function host:GetNW2Bool() return true end
function host:Health() return 100 end
function host:GetMaxHealth() return 100 end
function host:ChatPrint() end
player={GetAll=function() return {host} end}
local state={RunId='options',CampaignEpoch=1,CampaignSeed=7,Level=1,BuildReady=true}
LOD.RunManager={State=state,GetPlayerState=function() return {} end}
dofile('gamemodes/legend_of_deborah/gamemode/lod/sv_music.lua')
local server=LOD.MusicDirector;local demand=e.wire.LOD_MusicDemand
-- The real setter dispatches both the server and replicated-client callbacks.
local master=GetConVar('lod_music_enabled')
function master:SetBool(on) e.set('lod_music_enabled',on and 1 or 0) end
LOD.MusicDirector=nil;SERVER=false;CLIENT=true
LocalPlayer=function() return host end
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music_native.lua')
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_music.lua')
local client=LOD.MusicDirector
local pending={}
function RunConsoleCommand(name,value) pending[#pending+1]={name,value} end
local function flushPreference()
 for _,row in ipairs(pending) do e.set(row[1],row[2]) end
 pending={};host.preference=client.Preference:GetInt()
end
local originalCreate=vgui.Create;local controls={}
vgui.Create=function(kind)
 if kind=='DHTML' then return originalCreate(kind) end
 local p={valid=true,kind=kind,wide=980,Label={SetTextColor=function() end}}
 for _,name in ipairs({'SetPos','Center','SetTitle','MakePopup','SetFont','SetTextColor','SizeToContents','SetMinMax','SetDecimals'}) do p[name]=function() end end
 function p:SetSize(w) self.wide=w end
 function p:GetWide() return self.wide end
 function p:SetText(text) self.text=text end
 function p:SetChecked(on) self.checked=on end
 function p:GetChecked() return self.checked end
 function p:SetConVar(name) self.convar=name;self.checked=GetConVar(name) and GetConVar(name):GetBool() end
 function p:Remove() self.valid=false end
 controls[#controls+1]=p;return p
end
ScrW=function() return 1280 end;ScrH=function() return 720 end
input={LookupBinding=function() return 'shift' end}
LOD.PlayerOptions={};LOD.UI={Colors={ink={}},IsMinigameLocked=function() return false end,
 SelectPage=function() end,CloseButton=function() end,PageLinks=function() end}
dofile('gamemodes/legend_of_deborah/gamemode/lod/cl_player_options.lua')
LOD.PlayerOptions:Open()
local music
for _,control in ipairs(controls) do if control.text=='Music' then music=control end end
check(music and not music:GetChecked(),'host checkbox reflects disabled server music, not only the saved preference')
check(type(music.OnChange)=='function','actual Options checkbox owns its enable action')
local function choose(on)
 music:SetChecked(on);music:OnChange(on)
end
local function acceptDemand(p)
 local packet=e.sent[#e.sent];check(packet.name=='LOD_MusicDemand','Options uses the existing music demand channel')
 e.read=table.Copy(packet.args);demand(4,p)
end
host.preference=0;e.set('lod_music',0)
choose(true);acceptDemand(host)
check(GetConVar('lod_music_enabled'):GetBool(),'host Options enables the server master before the queued client cvar arrives')
flushPreference();check(client.Preference:GetBool(),'Options saves local music preference')
-- Deliver the real server's paced plan/state/switch packets to the client.
local sent=1
for i=1,30 do
 e.now=e.now+.2;server:Update(host,state)
 while sent<=#e.sent do
  local packet=e.sent[sent];sent=sent+1
  if packet.name~='LOD_MusicDemand' and e.wire[packet.name] then e.receive(packet.name,table.unpack(packet.args)) end
 end
 client:Tick()
 if e.panel and e.panel.valid and not client.Ready then e.panel.functions['lodms2.ready']('surge-rendered',e.now);client:Sync() end
end
check(client:Enabled() and client.Current and next(client.Plans),'Options alone admits host playback through real server metadata')
check(client.Ready and client.Synced,'Options selection reaches the renderer note/state handoff')
choose(false);flushPreference();acceptDemand(host)
check(not client:Enabled() and not client.Ready,'Options Off stops local playback')
check(GetConVar('lod_music_enabled'):GetBool(),'one player Off leaves the shared master enabled')
GetConVar('lod_music_enabled'):SetBool(false);music:Think()
check(not music:GetChecked(),'host checkbox follows an external master Off')
local guest=setmetatable({valid=true,host=false,preference=1},{__index=host})
e.read={true,true,true,true};e.now=e.now+1;demand(4,guest)
check(not GetConVar('lod_music_enabled'):GetBool(),'ordinary remote client cannot enable the server master')
guest.admin=true;e.now=e.now+1;e.read={true,true,true,true};demand(4,guest)
check(GetConVar('lod_music_enabled'):GetBool(),'superadmin Options may enable the server master')
GetConVar('lod_music_enabled'):SetBool(false)
e.read={true,true,true};e.now=e.now+1;demand(3,host)
check(not GetConVar('lod_music_enabled'):GetBool(),'ordinary startup demand preserves the default-Off server policy')
print('MUSIC_OPTIONS PASS '..e.checks)
