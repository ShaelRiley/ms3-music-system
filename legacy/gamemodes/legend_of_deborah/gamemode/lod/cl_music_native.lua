-- Bundled Surge phrases, opened lazily. Native frame timing is bounded:
-- a missed deadline is skipped, never played from an asynchronous callback.
if LOD.MusicNative and LOD.MusicNative.Stop then LOD.MusicNative:Stop() end
LOD.MusicNative={Lanes={},Records={},Opens={},Serial=0,Generation=0,Peak=0,Skipped=0,Errors=0,PhaseJoins=0,LateOpens=0,MaxStartDelay=0,HeldLoops=0}
local N,M=LOD.MusicNative,LOD.Music
local MAX_CHANNELS,MAX_OPENS,MAX_PCM=8,2,32*1024*1024
local LATE,OPEN_LATE,FADE=.15,.06,.7
local MASTER_GAIN,PEAK_CEILING=4,.8
local function stop(channel) if IsValid(channel) then channel:Stop() end end
function N:Count() local n=0;for _ in pairs(self.Records) do n=n+1 end;for _,r in pairs(self.Opens) do if not self.Records[r.key] then n=n+1 end end;return n end
function N:Bytes()
    local n=0;for _,r in pairs(self.Records) do n=n+r.bytes end
    for _,r in pairs(self.Opens) do if not self.Records[r.key] then n=n+r.bytes end end;return n
end
function N:Configure(catalog,bank,callback)
    self:Stop();self.Catalog=catalog;self.Bank=bank;self.Callback=callback;self.Ready=true;self.Volume=.55;self.Errors=0;self.Error=nil
    self.Bounds={}
    for id,a in pairs(catalog.assets) do
        local peak,tail=0,0
        for _,c in ipairs(a.clips) do local m=bank.clips[c.id];peak=math.max(peak,m.peak);tail=math.max(tail,m.tailPeak) end
        self.Bounds[id]=peak+(a.loop and tail or 0)
    end
end
function N:Stop()
    self.Generation=self.Generation+1;self.Ready=false
    for _,r in pairs(self.Records) do r.cancelled=true;stop(r.channel) end
    -- Uncancellable native opens continue to occupy the two-open ceiling until
    -- their stale callbacks dispose the channel. Off/On cannot grow this pool.
    for _,r in pairs(self.Opens) do r.cancelled=true end
    self.Records={};self.Lanes={};self.Bridge=nil;self.GapSince=nil;self.Callback=nil;self.ClockOffset=nil;self.HeadroomScale=1
end
function N:SyncClock(stamp)
    if type(stamp)~="number" or stamp~=stamp or stamp<0 or stamp>9e15 then return false end
    -- One fixed epoch conversion. A delayed JS→Lua message must not move its
    -- old deadline into the future merely by arriving late.
    self.ClockOffset=SysTime()-stamp;return true
end
function N:Result(r,played)
    if r.reported then return end;r.reported=true
    if r.token and self.Callback then self.Callback(r.token,played) end
end
function N:Release(r)
    if not r then return end;r.cancelled=true;stop(r.channel);self.Records[r.key]=nil
end
function N:Cancel(token)
    for _,r in pairs(self.Records) do
        if r.token==token and not r.started then self:Release(r);return end
    end
end
function N:SetVolume(volume) self.Volume=math.Clamp(tonumber(volume) or 0,0,1) end
function N:SetMix(id,value)
    if not self.Ready or not M.ID(id) then return end
    value=math.Clamp(tonumber(value) or 0,0,1)
    local now=SysTime();local l=self.Lanes[id]
    if l and l.value==value then return end
    if not l then
        if table.Count(self.Lanes)>=4 then return end
        l={value=0,from=0,at=now};self.Lanes[id]=l
    end
    local current=l.from+(l.value-l.from)*math.Clamp((now-l.at)/FADE,0,1)
    l.from=current;l.value=value;l.at=now
end
function N:Drop(id)
    for _,r in pairs(self.Records) do if r.lane==id then self:Release(r) end end
    self.Lanes[id]=nil
end
function N:Open(r)
    if not self.Ready or self:Count()>=MAX_CHANNELS or table.Count(self.Opens)>=MAX_OPENS or self:Bytes()+r.bytes>MAX_PCM then
        self:Result(r,false);return false
    end
    self.Serial=self.Serial+1;r.key=self.Serial;r.generation=self.Generation
    self.Records[r.key]=r;self.Opens[r.key]=r;self.Peak=math.max(self.Peak,self:Count())
    local ok,err=pcall(sound.PlayFile,r.path,"noplay noblock",function(channel,code,name)
        self.Opens[r.key]=nil
        if r.cancelled or r.generation~=self.Generation or not self.Ready or self.Records[r.key]~=r then stop(channel);return end
        if not IsValid(channel) then
            self.Error=self.Error or "Surge phrase open failed: "..r.clip.." ("..tostring(code)..": "..tostring(name)..")"
            self.Errors=self.Errors+1;self:Result(r,false);self:Release(r);return
        end
        local length=channel:GetLength()
        if type(length)~="number" or length~=length or math.abs(length-r.duration)>.08 then
            stop(channel);self.Error=self.Error or "Surge phrase duration mismatch: "..r.clip
                .." (expected "..tostring(r.duration)..", got "..tostring(length)..")";self.Errors=self.Errors+1
            self:Result(r,false);self:Release(r);return
        end
        r.channel=channel;r.readyAt=SysTime();channel:SetVolume(0);r.lastGain=0;channel:EnableLooping(r.bridge==true)
        -- The Think loop alone may start it, at its still-valid deadline.
    end)
    if not ok then self.Opens[r.key]=nil;self.Error=self.Error or tostring(err);self.Errors=self.Errors+1;self:Result(r,false);self:Release(r);return false end
    return true
end
function N:Prepare(token,lane,clip,delay,deadline)
    if not self.Ready or type(token)~="string" or not token:match("^%d+$") or #token>12
        or not M.ID(lane) or not M.ID(clip) or not self.Lanes[lane]
        or type(delay)~="number" or delay~=delay or delay<0 or delay>1.1
        or not self.ClockOffset or type(deadline)~="number" or deadline~=deadline then return end
    local meta=self.Bank.clips[clip];if not meta then self.Error="Unknown rendered phrase "..clip;return end
    local d=LOD.MusicDirector
    local asset=M.ClipAsset(self.Catalog,d and d.AudibleTargets,d and d.Plans,lane,clip)
    if not asset then return end
    for _,r in pairs(self.Records) do
        if r.token==token then return end
        if r.lane==lane and not r.started then self:Release(r) end
    end
    local now=SysTime();local due=deadline+self.ClockOffset;local lead=due-now;local musical=meta.musicalFrames and meta.musicalFrames/44100 or meta.beats*60/self.Bank.bpm
    if lead< -LATE or lead>1.1 then
        self.Skipped=self.Skipped+1;self:Result({token=token},false);return
    end
    if asset.role=="VICTORY" and d and d.Victory and CurTime()+math.max(0,lead)+musical>d.Victory.endsAt then
        self:Result({token=token},false);return
    end
    self:Open({token=token,lane=lane,clip=clip,path="sound/lod/ms2_surge/"..clip..".ogg",
        due=due,musical=musical,duration=meta.duration,peak=meta.peak,tailPeak=meta.tailPeak,asset=asset.id,loop=asset.loop,
        bytes=math.ceil(meta.duration*44100)*8})
end
function N:RecordPeak(r,now)
    return not r.bridge and r.started and now>=r.started+r.musical and r.tailPeak or r.peak
end
function N:WrittenPeak(includeBridge)
    local peak=0;local now=SysTime()
    for _,r in pairs(self.Records) do
        if r.started and not r.cancelled and (includeBridge or not r.bridge) then peak=peak+self:RecordPeak(r,now)*(r.lastGain or 0) end
    end
    return peak
end
function N:ApplyGains(now,ordered,total)
    -- One common master reduction preserves the authored floor blend. Peaks
    -- are measured offline; no samples, FFT or live normalization are needed.
    local bridge=self.Bridge
    local reserve=self.Bank.bridge.peak*math.max(.10*self.Volume,bridge and bridge.lastGain or 0)
    local capacity=math.max(0,PEAK_CEILING-reserve)
    local scale=total>0 and math.min(1,capacity/total) or 1;self.HeadroomScale=scale
    -- Reduce before increasing, including channels still waiting for their
    -- paced write. The actual written sum, not just its target, owns headroom.
    for _,r in ipairs(ordered) do
        if r.started and not r.cancelled then
            r.targetGain=r.targetGain*scale
            if now>=(r.nextGain or 0) and r.targetGain<(r.lastGain or 0)-.001 then
                r.channel:SetVolume(r.targetGain);r.lastGain=r.targetGain;r.nextGain=now+1/30
            end
        end
    end
    local used=self:WrittenPeak(false)
    for _,r in ipairs(ordered) do
        if r.started and not r.cancelled and now>=(r.nextGain or 0) then
            local peak=self:RecordPeak(r,now)
            local value=math.min(r.targetGain,(r.lastGain or 0)+math.max(0,capacity-used)/math.max(peak,1e-9))
            if value>(r.lastGain or 0)+.001 then
                used=used+peak*(value-(r.lastGain or 0))
                r.channel:SetVolume(value);r.lastGain=value;r.nextGain=now+1/30
            end
        end
    end
end
function N:BridgeGap(now,gap)
    if not gap then self.GapSince=nil
    elseif not self.GapSince then self.GapSince=now end
    -- One short bridge only. A repeated failure is surfaced, never hidden by an
    -- eternal drone or a second engine. It is capped at eight seconds per gap.
    if gap and now-self.GapSince>=8 then
        self.Error=self.Error or "Surge phrase gap exceeds eight seconds";self.Errors=math.max(self.Errors,3)
        self:Release(self.Bridge);self.Bridge=nil;return
    end
    local wanted=gap and now-(self.GapSince or now)>.15 and now-self.GapSince<8 and self.Errors<3
    if wanted and not self.Bridge and self.Bank.bridge then
        local m=self.Bank.bridge;local r={bridge=true,clip="bridge",path="sound/lod/ms2_surge/bridge.ogg",
            due=now,duration=m.duration,peak=m.peak,bytes=math.ceil(m.duration*44100)*8}
        if self:Open(r) then self.Bridge=r end
    end
    local r=self.Bridge;if not r then return end
    if r.cancelled then self.Bridge=nil;return end
    if r.channel and not r.started and wanted then r.channel:Play();r.started=now;r.gain=0 end
    local target=wanted and .10*self.Volume or 0
    r.gain=math.Approach(r.gain or 0,target,.5*math.min(.05,now-(self.LastTick or now)))
    local value=math.min(r.gain,math.max(0,PEAK_CEILING-self:WrittenPeak(false))/r.peak)
    if r.channel and now>=(r.nextGain or 0) and math.abs(value-(r.lastGain or 0))>.001 then
        r.channel:SetVolume(value);r.lastGain=value;r.nextGain=now+1/30
    end
    if not wanted and r.gain<=0 then self:Release(r);self.Bridge=nil end
end
function N:Tick()
    if not self.Ready then return end
    if self.Volume<=0 then self:Stop();return end
    local now=SysTime();local startedThisFrame={};local audible=false;local total=0
    -- Records contain <=8 items; stable due/key order makes overlapping or
    -- deliberately malformed preparations unable to start twice in one lane.
    local ordered={};for _,r in pairs(self.Records) do if not r.bridge then ordered[#ordered+1]=r end end
    table.sort(ordered,function(a,b) return a.due==b.due and a.key<b.key or a.due<b.due end)
    local ready={};local wanted={};local lanePeaks={}
    if self.Catalog.songFirst and self.Lanes.song then wanted.song=true end
    for _,t in ipairs(LOD.MusicDirector and LOD.MusicDirector.AudibleTargets or {}) do if t.weight>0 then wanted[t.block]=t.asset end end
    for _,r in ipairs(ordered) do
        if not r.started and r.channel and now>=r.due and now<=r.due+LATE and r.readyAt<=r.due+OPEN_LATE then ready[r.lane]=true end
    end
    for _,r in ipairs(ordered) do
        local boundary=r.started and r.started+r.musical
        if boundary and r.loop and not r.retireAt and wanted[r.lane] and not ready[r.lane]
            and IsValid(r.channel) and now>=boundary then
            -- A frame hitch must not strand the resident channel at EOF until
            -- the next long-phrase retry. Rejoin only its current musical phase;
            -- missed repeats create no catch-up work or new audio allocation.
            boundary=r.started+math.max(1,math.floor((now-r.started)/r.musical))*r.musical
            -- Exclude the release tail, preserving the original musical grid.
            r.channel:SetTime(now-boundary,true);r.channel:Play();r.started=boundary;r.playedAt=now
            r.holdSince=r.holdSince or boundary;self.HeldLoops=self.HeldLoops+1
            for _,pending in ipairs(ordered) do if pending.lane==r.lane and not pending.started and pending.due<=now then
                self.Skipped=self.Skipped+1;self:Result(pending,false);self:Release(pending)
            end end
        end
    end
    for _,r in ipairs(ordered) do
        local l=self.Lanes[r.lane]
        if r.cancelled or not l then self:Release(r)
        elseif not r.started and now>r.due+LATE then
            if not r.channel or r.readyAt>r.due+OPEN_LATE then self.LateOpens=self.LateOpens+1 end
            self.Skipped=self.Skipped+1;self:Result(r,false);self:Release(r)
        elseif not r.started and r.channel and now>=r.due then
            if r.readyAt>r.due+OPEN_LATE or startedThisFrame[r.lane] then
                if r.readyAt>r.due+OPEN_LATE then self.LateOpens=self.LateOpens+1 end
                self.Skipped=self.Skipped+1;self:Result(r,false);self:Release(r)
            else
                -- One current phrase plus one retiring tail per lane. Interrupt
                -- an old role at this bar; ordinary phrase tails finish naturally.
                for _,old in pairs(self.Records) do
                    if old~=r and old.lane==r.lane and old.started then
                        if old.retireAt then self:Release(old)
                        elseif now>=old.started+old.musical-LATE then old.retireAt=old.started+old.duration;old.interrupted=old.asset~=r.asset
                        else old.retireAt=math.min(old.started+old.duration,now+.12);old.interrupted=true end
                    end
                end
                -- The file was prepared in advance. A bounded frame hitch
                -- trims elapsed samples instead of losing an entire phrase.
                -- Keep its original epoch so stairs and the next phrase align.
                local elapsed=math.max(0,now-r.due)
                if elapsed>0 then r.channel:SetTime(elapsed,true) end
                r.started=r.due;r.playedAt=now;r.startDelay=elapsed;startedThisFrame[r.lane]=true
                if elapsed>OPEN_LATE then self.PhaseJoins=self.PhaseJoins+1 end
                self.MaxStartDelay=math.max(self.MaxStartDelay,elapsed)
                r.channel:Play();self.Errors=0;self.Error=nil;self:Result(r,true)
            end
        end
        if r.started and not r.cancelled then
            local ends=r.retireAt or r.started+r.duration
            if now>=ends then self:Release(r)
            else
                local mix=l.from+(l.value-l.from)*math.Clamp((now-l.at)/FADE,0,1)
                -- Routine joins retain constant gain and the rendered release.
                -- Only a genuine role interruption needs a short cutoff ramp.
                local envelope=r.interrupted and math.Clamp((ends-now)/.12,0,1) or 1
                local value=mix*self.Volume*envelope*MASTER_GAIN
                r.targetGain=value
                if r.interrupted then total=total+self:RecordPeak(r,now)*value
                else lanePeaks[r.lane]=math.max(lanePeaks[r.lane] or 0,self.Bounds[r.asset]*value) end
                if value>0 then audible=true end
            end
        end
    end
    for _,peak in pairs(lanePeaks) do total=total+peak end
    self:ApplyGains(now,ordered,total)
    self:BridgeGap(now,not audible and next(self.Lanes)~=nil)
    self.LastTick=now
end
function N:Status()
    local current,prepared,voices={},{},{}
    for _,r in pairs(self.Records) do if r.lane then
        if r.started then current[r.lane]=r.clip else prepared[r.lane]=r.clip end
    end end
    for _,r in pairs(self.Records) do if IsValid(r.channel) then
        local voice={clip=r.clip,lane=r.lane,bridge=r.bridge==true,gain=r.lastGain or 0,startDelay=r.startDelay,started=r.started~=nil}
        local ok,err=pcall(function()
            voice.nativeVolume=r.channel:GetVolume();voice.position=r.channel:GetTime();voice.state=r.channel:GetState()
            voice.playing=voice.state==1
        end)
        if not ok then voice.nativeStatusError=tostring(err) end
        voices[#voices+1]=voice
    end end
    return {currentClips=current,preparedClips=prepared,bridge=self.Bridge~=nil,channels=self:Count(),peakChannels=self.Peak,
        pendingOpens=table.Count(self.Opens),estimatedPCMBytes=self:Bytes(),nativeLateSkipped=self.Skipped,error=self.Error,
        playerVolume=self.Volume,masterGain=MASTER_GAIN,headroomScale=self.HeadroomScale,
        estimatedMusicPeak=self:WrittenPeak(true),peakCeiling=PEAK_CEILING,voices=voices,
        nativePhaseJoins=self.PhaseJoins,nativeLateOpens=self.LateOpens,maxNativeStartDelay=self.MaxStartDelay,nativeHeldLoops=self.HeldLoops}
end
