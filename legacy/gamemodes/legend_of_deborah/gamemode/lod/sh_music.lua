-- MS2 retains its curated score; Surge phrases supply local playback. Plans and pressure
-- remain shared authority. No soundtrack URL, HTTP cache or media stream.
LOD = LOD or {}
LOD.Music = {}
local M=LOD.Music
M.Roles={"T0","T1","T2","T3","BOSS","VICTORY","INTERLUDE"}
M.RoleNames={T0="Chill (Tension 1)",T1="Tension 2",T2="Tension 3",T3="Tension 4",BOSS="Boss",VICTORY="Fanfare",INTERLUDE="Chill"}
M.Limits={blocks=256,assets=1792,catalogBytes=2097152,packetBytes=60000,planChunk=1024,metadataBytes=4096,
    metadataAssets=4,clipNotes=2048}
M.Tuning={tick=.2,fade=1.2,relax=6,dwell=4,escalate=.8,damageWindow=5,urgentHP=.2,dangerHP=.4,
    urgentTime=60,dangerTime=180,serverBudget=.0005,frameLimit=.035,recovery=5,pingLimit=180,pingRise=80,lossLimit=2}
-- include() is relative to its current Lua folder. Startup inside lod/ and
-- later callbacks must resolve the same files in GMod's virtual filesystem.
M.BundleRoot="legend_of_deborah/gamemode/lod/ms2/"
function M.IncludeBundled(name)
    if type(name)~="string" or not (name=="catalog.lua" or name=="engine.lua" or name=="files.lua" or name=="render.lua"
        or name:match("^notes_%d%d%d%.lua$")) then return nil,"invalid MS2 bundle file" end
    local path=M.BundleRoot..name
    -- Clients may include server-delivered Lua from the download cache. Only
    -- preflight the server's mounted files; include owns client availability.
    if SERVER and not file.Exists(path,"LUA") then return nil,"Missing MS2 file "..path.."; install the complete build" end
    local ok,value=pcall(include,path)
    if not ok or value==nil then return nil,"Could not load MS2 file "..path end
    return value
end
local function count(t) local n=0;for _ in pairs(t or {}) do n=n+1 end;return n end
function M.ID(s) return type(s)=="string" and #s>0 and #s<=64 and s:match("^[a-z0-9][a-z0-9_-]*$")~=nil end
function M.Text(s,size) return type(s)=="string" and #s>0 and #s<=(size or 128) and not s:find("[%z\1-\31\127]") end
function M.RoleLevel(role) return ({T0=0,T1=1,T2=2,T3=3,BOSS=4,INTERLUDE=0})[role] or 0 end
function M.Asset(a)
    return type(a)=="table" and M.ID(a.id) and M.ID(a.block) and M.RoleNames[a.role]~=nil and type(a.loop)=="boolean"
end
function M.ValidateCatalog(c)
    if type(c)~="table" or c.schema~=2 or not M.ID(c.revision) or c.ppq~=48
        or type(c.bpm)~="number" or c.bpm<60 or c.bpm>180 or type(c.blocks)~="table"
        or type(c.assets)~="table" or type(c.sets)~="table" or not c.blocks[c.defaultBlock]
        or count(c.blocks)>M.Limits.blocks or count(c.assets)>M.Limits.assets then return nil,"invalid MS2 catalog" end
    for id,a in pairs(c.assets) do
        if not M.Asset(a) or id~=a.id or not c.blocks[a.block] or type(a.clips)~="table" or #a.clips<1 or #a.clips>256
            or a.loop~=(a.role~="VICTORY") then return nil,"invalid MIDI arrangement "..tostring(id) end
        local ids={};local songBeats=0
        for index,clip in ipairs(a.clips) do
            local songLength=a.songFirst and type(clip.beats)=="number" and clip.beats>=4 and clip.beats<=64 and clip.beats%4==0
            if not M.ID(clip.id) or ids[clip.id] or (not songLength and clip.beats~=8 and clip.beats~=12 and clip.beats~=64)
                or type(clip.page)~="string" or not clip.page:match("^notes_%d%d%d%.lua$")
                or type(clip.next)~="table" or #clip.next>6 then return nil,"invalid MIDI phrase" end
            if a.songFirst then
                if not c.songFirst or not songLength or clip.songIndex~=index-1 or clip.offset~=songBeats
                    or type(clip.musicalFrames)~="number" or clip.musicalFrames%1~=0
                    or math.abs(clip.musicalFrames-clip.beats*60/c.bpm*44100)>2
                    or #clip.next~=1 or clip.next[1]~=a.clips[index%#a.clips+1].id then return nil,"invalid ordered song" end
                songBeats=songBeats+clip.beats
            elseif c.songFirst then return nil,"mixed song catalog" end
            ids[clip.id]=true
        end
        if a.songFirst and songBeats~=a.songBeats then return nil,"invalid song duration" end
        for _,clip in ipairs(a.clips) do for _,cid in ipairs(clip.next) do
            if not ids[cid] then return nil,"phrase successor leaves arrangement" end
        end end
    end
    for id,b in pairs(c.blocks) do
        if not M.ID(id) or not M.Text(b.title) or not M.ID(b.version) or type(b.roles)~="table" then return nil,"invalid Music Block" end
        for role,aid in pairs(b.roles) do
            local a=c.assets[aid]
            if not M.RoleNames[role] or not a or a.role~=(role=="INTERLUDE" and "T0" or role) then return nil,"wrong arrangement role" end
        end
    end
    for _,role in ipairs(M.Roles) do if not c.assets[c.blocks[c.defaultBlock].roles[role]] then return nil,"missing first-block default" end end
    for id,set in pairs(c.sets) do
        if not M.ID(id) or type(set.members)~="table" or #set.members<1 or #set.members>M.Limits.blocks then return nil,"invalid music set" end
        for _,bid in ipairs(set.members) do if not c.blocks[bid] then return nil,"unknown set member" end end
    end
    return c
end
function M.LoadBundled()
    local raw,err=M.IncludeBundled("catalog.lua")
    if type(raw)~="string" or #raw>M.Limits.catalogBytes then return nil,err or "bundled MIDI catalog unavailable" end
    -- The trusted, byte-bounded bundled bank exceeds GMod's default 15,000
    -- JSON keys. Wire messages retain the decoder's normal limits.
    local catalog=util.JSONToTable(raw,true)
    if type(catalog)~="table" then return nil,"Could not decode bundled MS2 catalog" end
    return M.ValidateCatalog(catalog)
end
function M.LoadRenderBank(catalog)
    local raw,err=M.IncludeBundled("render.lua")
    if type(raw)~="string" or #raw>512000 then return nil,err or "Missing Surge render bank; install the complete build" end
    local b=util.JSONToTable(raw,true)
    if type(b)~="table" or b.schema~=1 or b.catalogRevision~=catalog.revision or b.bpm~=catalog.bpm
        or not M.ID(b.revision) or not M.ID(b.patchRevision) or type(b.clips)~="table" then return nil,"Invalid Surge render bank" end
    local seen={}
    for _,a in pairs(catalog.assets) do for _,clip in ipairs(a.clips) do
        local r=b.clips[clip.id]
        if type(r)~="table" or r.beats~=clip.beats or (a.songFirst and r.musicalFrames~=clip.musicalFrames) or type(r.duration)~="number" or r.duration~=r.duration
            or r.duration<clip.beats*60/b.bpm or r.duration>clip.beats*60/b.bpm+1
            or type(r.peak)~="number" or r.peak~=r.peak or r.peak<=0 or r.peak>.9
            or type(r.tailPeak)~="number" or r.tailPeak~=r.tailPeak or r.tailPeak<0 or r.tailPeak>r.peak then return nil,"Invalid Surge phrase "..clip.id end
        seen[clip.id]=true
    end end
    for id in pairs(b.clips) do if not seen[id] then return nil,"Orphan Surge phrase "..tostring(id) end end
    if type(b.bridge)~="table" or type(b.bridge.duration)~="number" or b.bridge.duration~=b.bridge.duration
        or b.bridge.duration<1 or b.bridge.duration>8 or type(b.bridge.peak)~="number"
        or b.bridge.peak~=b.bridge.peak or b.bridge.peak<=0 or b.bridge.peak>.9 then return nil,"Invalid Surge bridge" end
    return b
end
-- A persistent song may outlive an ordinary floor/pressure preference. Its
-- local file still must belong to a server-supplied, current catalog plan.
function M.ClipAsset(catalog,targets,plans,lane,clip)
    if not catalog or not M.ID(lane) or not M.ID(clip) then return end
    local candidates={}
    if catalog.songFirst and lane=="song" then
        for _,plan in pairs(plans or {}) do
            if plan.revision==catalog.revision then for aid in pairs(plan.assets or {}) do candidates[aid]=true end end
        end
    else
        for _,t in ipairs(targets or {}) do if t.block==lane and t.weight>0 then candidates[t.asset]=true end end
    end
    for aid in pairs(candidates) do
        local a=catalog.assets[aid]
        for _,c in ipairs(a and a.clips or {}) do if c.id==clip then return a end end
    end
end
function M.Pool(c,selection)
    local out,seen={},{}
    if selection=="all" then for id in pairs(c.blocks) do out[#out+1]=id end
    else
        local set=c.sets[selection];if not set then return nil,"unknown Music Block Set" end
        for _,id in ipairs(set.members) do if c.blocks[id] and not seen[id] then out[#out+1]=id;seen[id]=true end end
    end
    table.sort(out);if #out==0 then return nil,"empty music selection" end;return out
end
function M.Candidates(c,b,role,settings)
    local out,seen={},{}
    local function add(id,source)
        if id and c.assets[id] and not seen[id] then out[#out+1]={asset=id,source=source};seen[id]=true end
    end
    if not settings["universal_"..role:lower()] then add(b.roles[role],"custom") end
    add(c.blocks[c.defaultBlock].roles[role],"first-block-default")
    return out
end
function M.Plan(c,settings,seed,id,floors,epoch)
    local pool,err=M.Pool(c,settings.set or "all");if not pool then return nil,err end
    local plan={schema=2,id=id,epoch=epoch,revision=c.revision,seed=seed,settings=table.Copy(settings),
        defaultBlock=c.defaultBlock,eligible={},floors={},blocks={},assets={},created=CurTime()}
    for _,bid in ipairs(pool) do plan.eligible[bid]=c.blocks[bid].version end
    local rng=LOD.RNG.New(LOD.Seeds.Derive(seed,"music:physical-floors:v1"));local bag={}
    for z=1,floors do
        if #bag==0 then for _,bid in ipairs(pool) do bag[#bag+1]=bid end end
        local bid=table.remove(bag,rng:Int(1,#bag));plan.floors[z]=bid
        local b=c.blocks[bid]
        if not plan.blocks[bid] then
            local p={title=b.title,version=b.version,roles={}};plan.blocks[bid]=p
            for _,role in ipairs(M.Roles) do
                p.roles[role]=M.Candidates(c,b,role,settings)
                for _,candidate in ipairs(p.roles[role]) do
                    local a=c.assets[candidate.asset]
                    plan.assets[a.id]={id=a.id,block=a.block,role=a.role,loop=a.loop}
                end
            end
        end
    end
    return plan
end
function M.Pressure(previous, sample, now)
    local p=previous or {value=0,changed=now}; local target=0
    if not sample.staging then
        if sample.recent then target=1 end
        if sample.hits>=3 or sample.hp<=M.Tuning.dangerHP or sample.remaining<=M.Tuning.dangerTime then target=2 end
        if sample.hp<=M.Tuning.urgentHP or sample.remaining<=M.Tuning.urgentTime then target=3 end
    end
    if target~=p.target then p.target=target;p.since=now end
    local wait=target>p.value and M.Tuning.escalate or M.Tuning.relax
    if sample.staging or target==3 or now-p.since>=wait and now-p.changed>=M.Tuning.dwell then
        if p.value~=target then p.value=target;p.changed=now end
    end
    return p
end
-- Uses feet and the built stair flight, never camera height or nearest-floor Z.
function M.Floors(graph, pos, grounded, previous)
    local mc,gc=LOD.Config.Maze,LOD.Config.Geometry
    for _,e in ipairs(graph.VerticalEdges or {}) do
        local low=e.a.z<e.b.z and e.a or e.b
        local center=LOD.MazeNavigator:CellCenter(low)
        local dir=({E={1,0},N={0,1},W={-1,0},S={0,-1}})[e.LODStairDirection or "E"]
        local x,y=pos.x-center.x,pos.y-center.y
        local along=x*dir[1]+y*dir[2];local across=-x*dir[2]+y*dir[1]
        local f=math.Clamp((along+gc.StairRun)/gc.StairRun,0,1)
        local treadRise=mc.LevelHeight/(gc.StairSteps or 24)
        if along>=-gc.StairRun-8 and along<=8 and math.abs(across)<=gc.StairWidth*.5
            and math.abs(pos.z-center.z-f*mc.LevelHeight)<=treadRise+24 and grounded then
            return low.z+1,low.z+2,f
        end
    end
    if not grounded and previous then return previous,previous,0 end
    local cell=LOD.MazeNavigator:WorldToCell(graph,pos)
    if not cell then return previous or 1,previous or 1,0 end
    local floor=cell.z+1
    return floor,floor,0
end
