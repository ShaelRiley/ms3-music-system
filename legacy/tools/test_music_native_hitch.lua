-- Native channels really stop at EOF; late Think frames must phase-rejoin the
-- existing resident song, not leave silence until a 29.5-second retry boundary.
local e=dofile('tools/music_test_fixture.lua');local check=e.check
CLIENT=true
local root='gamemodes/legend_of_deborah/gamemode/lod/'
dofile(root..'cl_music_native.lua');dofile(root..'cl_music.lua')
local D,N=LOD.MusicDirector,LOD.MusicNative
local catalog=e.catalog();catalog.songFirst=true
local period=1302646/44100 -- actual a_t0_song_000 musicalFrames
local duration=period+.55
local bank={bpm=130,bridge={duration=4,peak=.04},clips={}}
for _,a in pairs(catalog.assets) do
 a.songFirst=true
 for _,clip in ipairs(a.clips) do
  clip.beats=64;clip.musicalFrames=1302646;clip.songIndex=0
  bank.clips[clip.id]={beats=64,musicalFrames=1302646,duration=duration,peak=.166,tailPeak=.089}
 end
end
D.Catalog=catalog;D.Plans={test={revision=catalog.revision,assets=catalog.assets}}
D.AudibleTargets={{block='delta',asset='delta-t0',weight=1}}
local results={};local serial=0
local function prepare(id,delay)
 serial=serial+1;local token=tostring(serial)
 N:Prepare(token,'song',id or 'delta_t0_000',delay,e.now+delay);return token
end
local function setup(loop)
 N:Configure(catalog,bank,function(token,played) results[token]=played end)
 N:SyncClock(e.now);N:SetMix('song',1)
 local id=loop==false and 'delta_victory_000' or 'delta_t0_000'
 local token=prepare(id,1);e.now=e.now+1;N:Tick()
 check(results[token]==true,'initial native preparation starts normally')
 return e.channels[#e.channels],e.now
end
for _,late in ipairs({.2,.8,period*3+.2}) do
 local channel,start=setup();local count=#e.channels;local plays=e.plays;local holds=N.HeldLoops
 e.now=start+period+late
 if late>.55 then
  check(channel:GetState()==0 and channel:GetTime()==duration,'native boundary actually reaches stopped EOF')
  check(N:Status().voices[1].playing==false,'diagnostic distinguishes a stopped channel from its historical start')
 end
 N:Tick()
 local phase=late%period
 check(N.HeldLoops==holds+1 and e.plays==plays+1,'one bounded phase-rejoin, never a catch-up loop')
 check(#e.channels==count and N:Count()==1 and N:Bytes()<32*1024*1024,'resident recovery allocates no extra channel or PCM')
 check(math.abs(channel:GetTime()-phase)<1e-7 and channel:GetState()==1,'existing channel resumes on the original musical phase')
 check(N:Status().voices[1].playing==true,'native playing diagnostic follows actual resumed state')
 -- A healthy successor still starts on the next original boundary, with only
 -- its ordinary release tail overlap; the recovered old chunk is not sticky.
 local boundary=start+(math.floor((e.now-start)/period)+1)*period
 e.now=boundary-1;local nextToken=prepare('delta_t0_000',1)
 e.now=boundary;N:Tick();check(results[nextToken]==true,'future ready successor replaces recovered resident on time')
 e.now=boundary+.56;N:Tick();check(N:Count()==1,'retiring tail remains bounded')
end
local channel,start=setup();e.now=start+period-1;local lateToken=prepare('delta_t0_000',1)
e.now=start+period+.2;N:Tick()
check(results[lateToken]==false and channel:GetState()==1,'expired successor stays rejected while the resident resumes')
channel,start=setup(false);local holds=N.HeldLoops;e.now=start+duration+.8;N:Tick()
check(N.HeldLoops==holds and not channel.valid and N:Count()==0,'once-only fanfare never acquires looping recovery')
channel,start=setup();local count=#e.channels;N:Stop();e.now=start+period*3;N:Tick()
check(N:Count()==0 and #e.channels==count and not channel.valid,'Off prevents every stale resident revival')
print('MUSIC_NATIVE_HITCH PASS '..e.checks..': real EOF, long songs, 200ms/multi-period stalls, one-shot/Off and phase-aligned successors')
