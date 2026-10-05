-- Existing MusicDirector plans; bundled Surge phrases, lightweight composition.
if LOD.MusicDirector and LOD.MusicDirector.Stop then LOD.MusicDirector:Stop() end
LOD.MusicDirector=LOD.MusicDirector or {}
local D,M,N=LOD.MusicDirector,LOD.Music,LOD.MusicNative
D.Plans={};D.PlanParts={};D.Payloads={};D.Pages={};D.SeenVictory={};D.Serial=D.Serial or 0
D.Generation=(D.Generation or 0)+1;D.ServerOn=false;D.Ready=false;D.SentAssets={}
D.SeenVictoryOrder={}
D.Volume=CreateClientConVar("lod_music_volume","0.55",true,false,"Procedural music volume",0,1)
D.Preference=CreateClientConVar("lod_music","1",true,true,"Allow local LoD music when the server enables it",0,1)
function D:Enabled()
    -- The server owns master permission; only its effective switch crosses
    -- the realm boundary. Dedicated clients need no local master convar.
    return self.ServerOn and self.Preference:GetBool() and self.Volume:GetFloat()>0
end
function D:CanEnableServer()
    local p=LocalPlayer()
    return IsValid(p) and (p:IsSuperAdmin() or p.IsListenServerHost and p:IsListenServerHost()) or false
end
function D:OptionEnabled()
    return self.Preference:GetBool() and (not self:CanEnableServer() or self.ServerOn) or false
end
function D:SetMusicOption(on)
    RunConsoleCommand("lod_music",on and "1" or "0")
    -- RunConsoleCommand is queued. Send the explicit On intent now; the server
    -- grants master permission only to its host/superadmins. Off stays personal.
    if on then self:Demand(true,true) end
end
function D:RememberVictory(id)
    if self.SeenVictory[id] then return end
    self.SeenVictory[id]=true;self.SeenVictoryOrder[#self.SeenVictoryOrder+1]=id
    if #self.SeenVictoryOrder>2 then self.SeenVictory[table.remove(self.SeenVictoryOrder,1)]=nil end
end
function D:Stop()
    self.Generation=(self.Generation or 0)+1
    if IsValid(self.Panel) then self.Panel:Remove() end
    self.Panel=nil;self.Ready=false;self.ReadyDeadline=nil;self.Backend=nil;self.Stats=nil;self.SentAssets={};self.Synced=nil;self.Payloads={};self.Pages={};self.PlanParts={}
    if self.Victory then self.Victory.finished=true;self:RememberVictory(self.Victory.id) end
    N:Stop()
    local accent=LOD.AdventurePresentation
    if accent and accent.soundMusical then accent:Reset() end
end
function D:Duck(seconds) self.DuckUntil=math.max(self.DuckUntil or 0,CurTime()+(seconds or 1));self.Synced=nil end
function D:Announce(bid)
    if not self:Enabled() or not M.ID(bid) or bid==self.LastBlock then return end
    local allowed=false
    for _,t in ipairs(self.AudibleTargets or {}) do if t.block==bid and t.weight>0 then allowed=true end end
    if self.Catalog and self.Catalog.songFirst then
        for _,plan in pairs(self.Plans) do if plan.revision==self.Catalog.revision and plan.blocks[bid] then allowed=true end end
    end
    if not allowed then return end
    self.LastBlock=bid;self.Serial=self.Serial+1
    net.Start("LOD_MusicPlaying");net.WriteUInt(self.Current and self.Current.sequence or 0,32)
    net.WriteUInt(self.Serial,32);net.WriteString(bid);net.SendToServer()
end
function D:Payload(aid)
    local known=self.Payloads[aid];if known then known.used=SysTime();return known.data end
    local a=self.Catalog and self.Catalog.assets[aid];if not a then return nil end
    local payload={id=a.id,role=a.role,loop=a.loop,clips={},bound=0,songFirst=a.songFirst,songBeats=a.songBeats}
    local full,tail=0,0
    for _,clip in ipairs(a.clips) do
        if not self.RenderBank or not self.RenderBank.clips[clip.id] then self.Error="Missing Surge phrase "..clip.id;return end
        local meta=self.RenderBank.clips[clip.id]
        full=math.max(full,meta.peak);tail=math.max(tail,meta.tailPeak)
        payload.clips[#payload.clips+1]={id=clip.id,beats=clip.beats,energy=clip.energy,entry=clip.entry,exit=clip.exit,next=clip.next,motifs=clip.motifs,handoffs=clip.handoffs,duration=meta.duration,songIndex=clip.songIndex,musicalFrames=meta.musicalFrames}
    end
    payload.bound=full+(a.loop and tail or 0)
    self.Payloads[aid]={data=payload,used=SysTime()}
    if table.Count(self.Payloads)>M.Limits.metadataAssets then
        local oldest
        for id,p in pairs(self.Payloads) do if id~=aid and (not oldest or p.used<self.Payloads[oldest].used) then oldest=id end end
        if oldest then self.Payloads[oldest]=nil end
    end
    return payload
end
function D:StartRenderer()
    if IsValid(self.Panel) or SysTime()<(self.RetryAt or 0) then return end
    if not self.Catalog then self.Catalog,self.Error=M.LoadBundled() end
    if not self.Catalog then self.RetryAt=SysTime()+10;return end
    if not self.RenderBank then self.RenderBank,self.Error=M.LoadRenderBank(self.Catalog) end
    if not self.RenderBank then self.RetryAt=SysTime()+10;return end
    local engineSource,err=M.IncludeBundled("engine.lua")
    if type(engineSource)~="string" then self.Error=err or "Missing MS2 renderer";self.RetryAt=SysTime()+10;return end
    local panel=vgui.Create("DHTML");self.Panel=panel
    if not IsValid(panel) then self.Error="MS2 HTML renderer unavailable";self.RetryAt=SysTime()+10;return end
    local generation=self.Generation
    N:Configure(self.Catalog,self.RenderBank,function(token,played)
        if generation==D.Generation and D:Enabled() and IsValid(D.Panel) then
            -- Native tokens are decimal IDs. TableToJSON accepts tables only.
            D.Panel:QueueJavascript("lodScore.result("..tostring(tonumber(token))..","..tostring(played)..");")
        end
    end)
    panel:SetSize(1,1);panel:SetPos(0,0);panel:SetMouseInputEnabled(false);panel:SetKeyboardInputEnabled(false)
    panel:SetAllowLua(false);panel.Paint=function() end
    -- Keep IsVisible true: a hidden DHTML does not process its JavaScript queue.
    panel:SetVisible(true)
    function panel:OnDocumentReady()
        local function live() return generation==D.Generation and D:Enabled() end
        self:AddFunction("lodms2","ready",function(backend,stamp)
            if not live() then return end
            if backend~="surge-sample-clock" and (backend~="surge-rendered" or not N:SyncClock(stamp)) then
                D.Error="Surge phrase clock did not initialize";D.RetryAt=SysTime()+10;D:Stop();return
            end
            if backend=="surge-sample-clock" then N:Stop() end -- exactly one audible backend
            D.Ready=true;D.ReadyDeadline=nil;D.RetryAt=nil;D.Backend=backend;D.Error=nil;D.Synced=nil
        end)
        self:AddFunction("lodms2","readclip",function(lane,clip)
            if not live() or D.Backend~="surge-sample-clock" or not M.ID(lane) or not M.ID(clip) then return end
            -- This bridge reads only a currently authorized, bundled score file.
            -- No arbitrary paths, HTTP, network soundtrack or unrestricted Lua.
            local allowed=M.ClipAsset(D.Catalog,D.AudibleTargets,D.Plans,lane,clip)
            if not allowed then self:QueueJavascript('lodScore.audio("'..clip..'","");');return end
            local now=SysTime()
            if now>=(D.ClipReadWindow or 0) then D.ClipReadWindow=now+.1;D.ClipReadCount=0 end
            D.ClipReadCount=(D.ClipReadCount or 0)+1
            if D.ClipReadCount>2 then self:QueueJavascript('lodScore.audio("'..clip..'","");');return end
            local path="sound/lod/ms2_surge/"..clip..".ogg"
            local size=file.Size(path,"GAME");local bytes
            if size and size>0 and size<=1024*1024 then bytes=file.Read(path,"GAME") end
            if type(bytes)~="string" or #bytes>1024*1024 or bytes:sub(1,4)~="OggS" then bytes=nil end
            -- RFC 2045 wrapping contains raw newlines, invalid inside this JS string.
            local encoded=bytes and util.Base64Encode(bytes,true) or ""
            self:QueueJavascript('lodScore.audio("'..clip..'","'..encoded..'");')
        end)
        self:AddFunction("lodms2","block",function(bid) if live() then D:Announce(bid) end end)
        self:AddFunction("lodms2","victory",function() if live() and D.Victory then D.Victory.finished=true;D.Synced=nil end end)
        self:AddFunction("lodms2","mix",function(lane,value) if live() then N:SetMix(lane,value) end end)
        self:AddFunction("lodms2","volume",function(volume,quality)
            if not live() then return end
            N:SetVolume(math.Clamp(tonumber(volume) or 0,0,1),quality)
        end)
        self:AddFunction("lodms2","drop",function(id) if live() then N:Drop(id) end end)
        self:AddFunction("lodms2","prepare",function(token,lane,clip,delay,deadline) if live() then N:Prepare(token,lane,clip,delay,deadline) end end)
        self:AddFunction("lodms2","cancel",function(token) if live() then N:Cancel(token) end end)
        self:AddFunction("lodms2","stop",function() if live() then N:Stop() end end)
        self:AddFunction("lodms2","stats",function(raw) if live() and type(raw)=="string" and #raw<2000 then D.Stats=util.JSONToTable(raw) end end)
        self:AddFunction("lodms2","error",function(err)
            if not live() then return end
            D.Error=tostring(err):sub(1,512)
            -- A capability/decode failure falls back once, rather than trapping
            -- an otherwise working client in repeated silent AudioContext retries.
            if D.Backend=="surge-sample-clock" then D.NativeFallbackReason=D.Error;D.PreferNative=true;D.RetryAt=SysTime()+.1
            else D.RetryAt=SysTime()+10 end
            D:Stop()
        end)
        self:QueueJavascript("window.lodScore=MS2.attach(lodms2,"..tostring(not D.PreferNative)..");")
    end
    panel:SetHTML('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'"><script>'..engineSource..'</script>')
    self.ReadyDeadline=SysTime()+5
end
function D:Candidate(plan,bid,role)
    local b=plan and plan.blocks[bid]
    for _,c in ipairs(b and b.roles[role] or {}) do if self.Catalog.assets[c.asset] then return c.asset end end
    if role=="INTERLUDE" then return self:Candidate(plan,bid,"T0") end
end
function D:Desired()
    local s=self.Current;if not s or s.stop then return end
    local plan=self.Plans[s.plan];if not plan then return end
    local role=s.role;local targets=s.targets;local v=self.Victory
    if v and not v.finished then
        local required=12*60/self.Catalog.bpm+.5
        if not v.started and CurTime()+required>v.endsAt then v.finished=true;self:RememberVictory(v.id)
        else plan=self.Plans[v.plan];targets={{block=v.block,weight=1}};role="VICTORY" end
    end
    if role=="POST" then
        local nextPlan=self.Plans[s.next]
        if s.policy=="auto" and nextPlan and s.nextBlock then plan=nextPlan;targets={{block=s.nextBlock,weight=1}} end
        role=s.policy=="off" and "T0" or "INTERLUDE"
    end
    if not plan then return end
    if plan.revision~=self.Catalog.revision then self.Error="MS2 client/server catalog mismatch; install the same build";return end
    -- Calm maze pressure selects a driving composition; only staging keeps
    -- the full calm arrangement including its authored beatless passages.
    if self.Catalog.songFirst and not s.staged and role=="T0" and s.role~="POST" then role="T1" end
    local state={songFirst=self.Catalog.songFirst,planKey=plan.id,targets={},role=role,remaining=s.remaining or -1,expression=s.expression or 0,staged=s.staged,
        seed=plan.seed or 0,bpm=self.Catalog.bpm,quality=self.Quality or 1,
        volume=self.Volume:GetFloat()*(CurTime()<(self.DuckUntil or 0) and .55 or 1)}
    for _,t in ipairs(targets or {}) do
        local aid=t.block and self:Candidate(plan,t.block,role)
        if aid and t.weight>0 then state.targets[#state.targets+1]={block=t.block,asset=aid,weight=t.weight} end
    end
    return state
end
function D:Sync()
    if not self.Ready then return end
    local state=self:Desired();if not state or #state.targets==0 then return end
    local raw=util.TableToJSON(state);if raw==self.Synced then return end
    local sent={}
    for _,t in ipairs(state.targets) do
        if not self.SentAssets[t.asset] then
            local payload=self:Payload(t.asset);if not payload then return end
            self.Panel:QueueJavascript("lodScore.install("..util.TableToJSON(payload)..");")
        end
        sent[t.asset]=true
    end
    self.AudibleTargets=state.targets;self.PlaybackRole=state.role;self.SentAssets=sent
    self.Panel:QueueJavascript("lodScore.state("..raw..");");self.Synced=raw
    if state.role=="VICTORY" and self.Victory then self.Victory.started=true;self:RememberVictory(self.Victory.id) end
end
function D:Demand(resync,enableMaster)
    local on=(enableMaster==true or self.Preference:GetBool()) and self.Volume:GetFloat()>0
    if on==self.DemandOn and not resync and not enableMaster then return end
    self.DemandOn=on
    net.Start("LOD_MusicDemand");net.WriteBool(on);net.WriteBool(true);net.WriteBool(resync==true)
    net.WriteBool(enableMaster==true);net.SendToServer()
end
function D:Tick()
    if not self:Enabled() then if self.WasEnabled then self:Stop() end;self.WasEnabled=false;return end
    self.WasEnabled=true
    if SysTime()>=(self.NextTick or 0) then
        self.NextTick=SysTime()+.2
        local frame=engine and engine.AbsoluteFrameTime and engine.AbsoluteFrameTime() or RealFrameTime()
        self.FrameAverage=(self.FrameAverage or frame)*.9+frame*.1
        if self.FrameAverage>M.Tuning.frameLimit then self.RecoverAt=SysTime()+M.Tuning.recovery end
        self.Quality=SysTime()<(self.RecoverAt or 0) and 0 or 1
        self:StartRenderer()
        if not self.Ready and IsValid(self.Panel) and self.ReadyDeadline and SysTime()>self.ReadyDeadline then
            self.Error="MS2 renderer did not initialize";self.RetryAt=SysTime()+10;self:Stop()
        end
        self:Sync()
    end
    if self.Backend=="surge-rendered" then
        N:Tick()
        if N.Errors>=3 then self.Error=N.Error or "Surge phrase backend failed";self.RetryAt=SysTime()+10;self:Stop() end
    end
end
net.Receive("LOD_MusicPlan",function()
    if not D:Enabled() then return end
    local id=net.ReadString();local part=net.ReadUInt(16);local total=net.ReadUInt(16);local n=net.ReadUInt(16)
    if #id>160 or total<1 or total>math.ceil(M.Limits.packetBytes/M.Limits.planChunk)
        or part<1 or part>total or n<1 or n>M.Limits.planChunk then return end
    if part==1 then
        if table.Count(D.PlanParts)>=2 then D.PlanParts={} end
        D.PlanParts[id]={next=1,total=total,data={}}
    end
    local receiving=D.PlanParts[id];if not receiving or receiving.next~=part or receiving.total~=total then return end
    receiving.data[part]=net.ReadData(n);receiving.next=part+1;if part~=total then return end
    local bytes=table.concat(receiving.data);D.PlanParts[id]=nil;if #bytes>M.Limits.packetBytes then return end
    local raw=util.Decompress(bytes,M.Limits.packetBytes);if not raw or #raw>M.Limits.packetBytes then return end
    local plan=util.JSONToTable(raw)
    if type(plan)~="table" or plan.schema~=2 or plan.id~=id or type(plan.blocks)~="table" or type(plan.assets)~="table"
        or type(plan.floors)~="table" or #plan.floors>8 or not M.ID(plan.revision) then return end
    for aid,a in pairs(plan.assets) do if not M.Asset(a) or aid~=a.id then return end end
    D.Plans[id]=plan;D.Synced=nil
end)
net.Receive("LOD_MusicState",function(bits)
    if bits>32768 or not D:Enabled() then return end
    local s=util.JSONToTable(net.ReadString())
    if type(s)~="table" or type(s.sequence)~="number" or type(s.targets or {})~="table" or #(s.targets or {})>2 then return end
    if D.Current and s.sequence<=D.Current.sequence then return end
    if D.Current and s.epoch~=D.Current.epoch then D:Stop();D.LastBlock=nil;D.SeenVictory={};D.SeenVictoryOrder={};D.Victory=nil end
    D.Current=s;D.Synced=nil
    if s.stop then D:Stop();return end
    if s.role=="POST" and s.canVictory and not D.SeenVictory[s.victory] and s.startedAt>=(D.VictoryAfter or 0) then
        if not D.Victory or D.Victory.id~=s.victory then D.Victory={id=s.victory,plan=s.plan,block=s.targets[1].block,endsAt=s.endsAt} end
    elseif s.victory and not s.canVictory then D:RememberVictory(s.victory) end
    local keep={[s.plan]=true};if s.next then keep[s.next]=true end
    if D.Victory and not D.Victory.finished then keep[D.Victory.plan]=true end
    for id in pairs(D.Plans) do if not keep[id] then D.Plans[id]=nil end end
    if D.Victory and D.Victory.finished and s.role~="POST" then D.Victory=nil end
end)
net.Receive("LOD_MusicBudget",function() D.ServerBudget=net.ReadBool() end)
net.Receive("LOD_MusicSwitch",function()
    local on=net.ReadBool();if on~=D.ServerOn then D.VictoryAfter=CurTime() end
    D.ServerOn=on;if not D:Enabled() then D:Stop() end
end)
local function preferenceChanged()
    D.VictoryAfter=CurTime();D.Synced=nil;if not D:Enabled() then D:Stop() end;D:Demand()
end
cvars.AddChangeCallback("lod_music",preferenceChanged,"LOD_MusicPreference")
cvars.AddChangeCallback("lod_music_volume",preferenceChanged,"LOD_MusicVolume")
hook.Add("InitPostEntity","LOD_MusicDemand",function() D:Demand(true) end)
if timer then timer.Simple(0,function() if IsValid(LocalPlayer()) then D:Demand(true) end end) end
hook.Add("Think","LOD_MusicMix",function()
    local ok,err=pcall(D.Tick,D);if not ok then D.Error=tostring(err);D.RetryAt=SysTime()+10;D:Stop() end
end)
hook.Add("ShutDown","LOD_MusicShutdown",function() D:Stop() end)
concommand.Add("lod_music_client_status",function()
    if D.Ready and IsValid(D.Panel) then D.Panel:QueueJavascript("lodScore.stats();") end
    print("[LOD:MUSIC] "..util.TableToJSON({system="MS3",enabled=D:Enabled(),backend=D.Backend,ready=D.Ready,
        serverAuthorized=D.ServerOn,preference=D.Preference:GetBool(),volume=D.Volume:GetFloat(),demand=D.DemandOn,
        plan=D.Current and D.Current.plan,catalog=D.Catalog and D.Catalog.revision,quality=D.Quality,
        metadataAssets=table.Count(D.Payloads),stats=D.Stats,renderBank=D.RenderBank and D.RenderBank.revision,
        patchBank=D.RenderBank and D.RenderBank.patchRevision,role=D.Ready and D.PlaybackRole or nil,
        blocks=D.AudibleTargets,playback=D.Backend=="surge-sample-clock" and (D.Stats and D.Stats.audio or {}) or N:Status(),error=D.Error,
        nativeFallbackReason=D.NativeFallbackReason,
        retryIn=math.max(0,(D.RetryAt or 0)-SysTime()),
        startupPending=not D.Ready and IsValid(D.Panel),streamedBytes=0}))
end)
