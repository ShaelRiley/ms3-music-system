-- Minimal engine boundary; all catalog/planning/mixing logic comes from production.
local E={now=10,callbacks={},hooks={},commands={},wire={},read={},stops=0,plays=0,cv={},announced={},frame=1/60,volumeWrites=0}
function CurTime() return E.now end;SysTime=CurTime
function FrameTime() return .1 end
function RealFrameTime() return E.frame end
engine={AbsoluteFrameTime=RealFrameTime,TickInterval=function() return .015 end}
function IsValid(x) return type(x)=='table' and x.valid~=false end
function isstring(x) return type(x)=='string' end
function Color(...) return {...} end
function math.Clamp(n,a,b) return math.min(b,math.max(a,n)) end
function math.Approach(n,t,s) return n<t and math.min(t,n+s) or math.max(t,n-s) end
function table.Copy(t) if type(t)~='table' then return t end local n={};for k,v in pairs(t) do n[k]=table.Copy(v) end;return n end
function table.Count(t) local n=0;for _ in pairs(t) do n=n+1 end;return n end
local V={};V.__index=V
function Vector(x,y,z) return setmetatable({x=x or 0,y=y or 0,z=z or 0},V) end
function V.__add(a,b) return Vector(a.x+b.x,a.y+b.y,a.z+b.z) end
function V.__sub(a,b) return Vector(a.x-b.x,a.y-b.y,a.z-b.z) end
function V.__mul(a,b) return Vector(a.x*b,a.y*b,a.z*b) end
function V:DistToSqr(b) local d=self-b;return d.x*d.x+d.y*d.y+d.z*d.z end
FCVAR_ARCHIVE,FCVAR_REPLICATED,FCVAR_NOTIFY=1,2,4
IN_SPEED,MOVETYPE_WALK=131072,2
bit={bor=function(a,b,c) return a|b|(c or 0) end}
local function cv(name,value)
 E.cv[name]=E.cv[name] or {value=tostring(value)};local c=E.cv[name]
 function c:GetBool() return self.value~='0' end
 function c:GetFloat() return tonumber(self.value) end
 function c:GetInt() return tonumber(self.value) end
 return c
end
CreateConVar=cv;CreateClientConVar=cv;GetConVar=function(name) return E.cv[name] end
cvars={AddChangeCallback=function(name,fn,id) E.callbacks[name]=E.callbacks[name] or {};E.callbacks[name][id]=fn end}
function E.set(name,v) E.cv[name].value=tostring(v);for _,f in pairs(E.callbacks[name] or {}) do f() end end
hook={Add=function(event,id,fn) E.hooks[id]=fn end}
concommand={Add=function(name,fn) E.commands[name]=fn end}
file={Read=function() end,CreateDir=function() end,Write=function() end}
local json={}
local function jsonKeys(v)
 if type(v)~='table' then return 0 end
 local n=0;for _,child in pairs(v) do n=n+1+jsonKeys(child) end;return n
end
E.jsonKeys=jsonKeys
local function stable(v)
 if type(v)~='table' then return tostring(v) end
 local keys={};for k in pairs(v) do keys[#keys+1]=k end;table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
 local out={};for _,k in ipairs(keys) do out[#out+1]=tostring(k)..'='..stable(v[k]) end
 return '{'..table.concat(out,',')..'}'
end
util={AddNetworkString=function() end,TableToJSON=function(v) local s=stable(v);json[s]=table.Copy(v);return s end,
 JSONToTable=function(s,ignoreLimits)
  local value=json[s];if not ignoreLimits and jsonKeys(value)>15000 then return nil end
  return table.Copy(value)
 end,Compress=function(s) return s end,Decompress=function(s) return s end}
net={Receive=function(name,fn) E.wire[name]=fn end,Start=function(name) E.packet={name=name,args={}} end}
for _,name in ipairs({'String','UInt','Data','Bool'}) do
 net['Write'..name]=function(v) table.insert(E.packet.args,v) end
 net['Read'..name]=function() return table.remove(E.read,1) end
end
net.Send=function(p) E.sent=E.sent or {};E.packet.player=p;E.sent[#E.sent+1]=E.packet
 if E.packet.name=='LOD_MusicPlaying' then E.announced[#E.announced+1]=E.packet end end
net.SendToServer=net.Send
function E.receive(name,...) E.read={...};E.wire[name](1024,E.player) end
sound={PlayURL=function() error('unbounded URL streaming is forbidden') end,
 PlayFile=function(path,flags,callback)
  assert(path:match('^sound/lod/ms2_surge/[a-z0-9_-]+%.ogg$'),'only validated local Surge phrases')
  assert(flags=='noplay noblock','asynchronous preparation cannot autoplay')
  local id=path:match('/([^/]+)%.ogg$');local bank=LOD.MusicNative.Bank;local meta=id=='bridge' and bank.bridge or bank.clips[id]
  local channel={valid=true,volume=0,id=id,peak=meta.peak}
  function channel:GetLength() return meta.duration end
  function channel:SetVolume(v) self.volume=v;E.volumeWrites=E.volumeWrites+1;if E.onVolumeWrite then E.onVolumeWrite() end end
  function channel:EnableLooping(v) self.loop=v end
  function channel:SetTime(seconds,fast) assert(fast==true,'phase recovery must seek without decode-to-position');self.seek=seconds;self.seekAt=E.now end
  function channel:GetVolume() return self.volume end
  function channel:GetTime()
   local position=self.played and E.now-(self.seekAt or self.played)+(self.seek or 0) or 0
   return self.loop and position%meta.duration or math.min(meta.duration,position)
  end
  function channel:GetState() return self.played and (self.loop or self:GetTime()<meta.duration) and 1 or 0 end
  function channel:Play() self.played=E.now;E.plays=E.plays+1 end
  function channel:Stop() if self.valid then E.stops=E.stops+1 end;self.valid=false end
  E.channels=E.channels or {};E.channels[#E.channels+1]=channel
  if E.deferOpens then E.opens=E.opens or {};E.opens[#E.opens+1]={callback=callback,channel=channel}
  else callback(channel) end
 end}
LOD={Config={Maze={Width=1,Height=1,CellSize=384,LevelHeight=384,Origin=Vector(),LayerOccupancy={{},{},{},{}}},Geometry={StairRun=320,StairSteps=24,StairWidth=96}},
 MazeGenerator={CellKey=function(x,y,z) return x..':'..y..':'..z end},MazeBuilder={CellCenter=function(_,c) return Vector(0,0,c.z*384) end}}
dofile('gamemodes/legend_of_deborah/gamemode/lod/sh_rng.lua')
dofile('gamemodes/legend_of_deborah/gamemode/lod/sv_maze_navigator.lua')
dofile('gamemodes/legend_of_deborah/gamemode/lod/sh_music.lua')
function E.catalog()
 local c={schema=2,revision='ms2-fixture',ppq=48,bpm=130,defaultBlock='delta',assets={},blocks={},sets={}}
 for _,id in ipairs({'alpha','beta','gamma','delta'}) do c.blocks[id]={version='v1',title=id,roles={}} end
 for _,role in ipairs({'T0','T1','T2','T3','BOSS','VICTORY'}) do
  local aid='delta-'..role:lower();local cid='delta_'..role:lower()..'_000'
  c.assets[aid]={id=aid,block='delta',role=role,loop=role~='VICTORY',clips={{id=cid,beats=role=='VICTORY' and 12 or 8,page='notes_000.lua',next={cid},energy=.5,entry=2,exit=2}}}
  c.blocks.delta.roles[role]=aid
 end
 c.blocks.delta.roles.INTERLUDE=c.blocks.delta.roles.T0
 c.sets.pair={revision='v1',title='Two',members={'beta','alpha','alpha'}}
 return c
end
-- GMod includes are relative to the currently executing Lua folder, not always
-- the gamemode root. Explicit gamemode paths also work in later callbacks.
E.luaDirectory='legend_of_deborah/gamemode/lod/'
E.includeCalls={};E.missingLua={}
local function luaPath(path)
 if not path:match('^legend_of_deborah/gamemode/') then path=E.luaDirectory..path end
 return path
end
local function mountedLua(path)
 if E.missingLua[path] then return false end
 local f=io.open('gamemodes/'..path,'rb');if not f then return false end;f:close();return true
end
file.Exists=function(path,realm)
 if realm~='LUA' or E.cacheOnly and CLIENT then return false end
 return mountedLua(path)
end
function include(path)
 path=luaPath(path);E.includeCalls[#E.includeCalls+1]=path
 if not mountedLua(path) then error("Couldn't include file '"..path.."' - File not found or is empty") end
 if not E.realBundle and path=='legend_of_deborah/gamemode/lod/ms2/catalog.lua' then return util.TableToJSON(E.catalog()) end
 if not E.realBundle and path=='legend_of_deborah/gamemode/lod/ms2/render.lua' then
  local c=E.catalog();local b={schema=1,revision='surge-fixture',catalogRevision=c.revision,patchRevision='lod-va-fixture',bpm=c.bpm,clips={},bridge={duration=4,peak=.04}}
  for _,a in pairs(c.assets) do for _,clip in ipairs(a.clips) do b.clips[clip.id]={beats=clip.beats,duration=clip.beats*60/c.bpm+.55,peak=.12,tailPeak=.01} end end
  return util.TableToJSON(b)
 end
 if not E.realBundle and path=='legend_of_deborah/gamemode/lod/ms2/notes_000.lua' then
  local notes={};for _,a in pairs(E.catalog().assets) do for _,c in ipairs(a.clips) do notes[c.id]={{0,48,0,62,85},{48,48,4,38,85}} end end
  return util.TableToJSON(notes)
 end
 return dofile('gamemodes/'..path)
end
vgui={Create=function(kind)
 local p={valid=true,functions={},calls={},kind=kind};E.panel=p
 function p:AddFunction(ns,name,fn) self.functions[ns..'.'..name]=fn end
 function p:QueueJavascript(raw) self.calls[#self.calls+1]=raw end
 function p:SetHTML(raw) self.html=raw;self:OnDocumentReady() end
 function p:Remove() self.valid=false end
 function p:SetSize() end;function p:SetPos() end;function p:SetMouseInputEnabled() end;function p:SetKeyboardInputEnabled() end
 function p:SetAllowLua(value) self.allowLua=value end;function p:SetVisible(value) self.visible=value end
 return p
end}
function E.completeOpens()
 local pending=E.opens or {};E.opens={};for _,o in ipairs(pending) do o.callback(o.channel) end
end
E.checks=0
function E.check(ok,msg) E.checks=E.checks+1;assert(ok,msg) end
function E.step(n) for _=1,n or 1 do E.now=E.now+.1;LOD.MusicDirector:Tick() end end
return E
