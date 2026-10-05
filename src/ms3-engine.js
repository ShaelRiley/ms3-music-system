/* MS3 rendered Surge score. ES5 control plane; no live note synthesis.
 * Capable clients schedule decoded bundled recordings on the audio clock.
 * Older HTML engines retain the bounded native compatibility backend. */
const MS3Engine = (function(){
    'use strict';
    var LOOKAHEAD=1.0,LATE=.15,ACK_WAIT=1.0,PHRASE_PASSES=1;
    function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
    function hash(s){var h=2166136261,i;s=String(s);for(i=0;i<s.length;i++)h=((h^s.charCodeAt(i))*16777619)>>>0;return h||1;}
    function Random(seed){this.value=hash(seed);}
    Random.prototype.next=function(){this.value=(1664525*this.value+1013904223)>>>0;return this.value/4294967296;};
    function passesFor(c){return c.songIndex!==undefined||c.beats===64?PHRASE_PASSES:4;}
    function expression(s){return !s.staged&&s.expression===1&&(s.role==='T3'||s.role==='BOSS')?1:0;}
    function Composer(seed){this.random=new Random(seed);this.history=[];this.last=null;}
    Composer.prototype.choose=function(asset,commit){
        var r=this.random,last=this.last,candidates=[],preferred={},i,c,dist;
        // A song is an ordered performance. Chunk boundaries are storage only.
        if(asset.songFirst){
            var index=-1;
            for(i=0;i<asset.clips.length;i++)if(last&&asset.clips[i].id===last.id)index=i;
            c=asset.clips[(index+1)%asset.clips.length];
            if(commit!==false)this.accept(c);return c;
        }
        if(last){
            for(i=0;i<(last.next||[]).length;i++)preferred[last.next[i]]=1-i*.08;
            var handoff=last.handoffs&&last.handoffs[asset.role];
            if(handoff)preferred[handoff.to]=1.5;
        }
        for(i=0;i<asset.clips.length;i++){
            c=asset.clips[i];if(last&&c.id===last.id&&asset.clips.length>1)continue;
            if(asset.clips.length>3&&this.history.indexOf(c.id)!==-1)continue;
            dist=last?Math.min((c.entry-last.exit+12)%12,(last.exit-c.entry+12)%12):0;
            var shared=0,m;for(m=0;m<(c.motifs||[]).length;m++)if(last&&(last.motifs||[]).indexOf(c.motifs[m])!==-1)shared++;
            candidates.push({clip:c,score:(preferred[c.id]||0)+.28*Math.min(2,shared)-1.5*(last?Math.abs(c.energy-last.energy):0)-.12*dist+r.next()*.15});
        }
        candidates.sort(function(a,b){return b.score-a.score;});
        c=candidates.length?candidates[0].clip:asset.clips[0];if(commit!==false)this.accept(c);return c;
    };
    Composer.prototype.accept=function(c){if(this.last&&this.last.id===c.id)return;this.last=c;this.history.push(c.id);if(this.history.length>3)this.history.shift();};
    function Scheduler(base,sink,clock,callback,seed){
        this.base=base;this.bpm=base;
        // Quantize the full sixteen-bar period, not eight separately rounded tiles.
        // The first installed looping asset also admits legacy eight-beat fixtures.
        this.gridReady=false;
        this.beatSeconds=sink.continuous?Math.round(64*60/base*sink.context.sampleRate)/(64*sink.context.sampleRate):60/base;this.sink=sink;this.clock=clock;this.callback=callback||function(){};
        this.origin=clock()+LOOKAHEAD;this.assets={};this.lanes={};this.jobs={};this.serial=0;this.visits={};
        this.enabled=true;this.state={role:'T0'};this.skipped=0;this.resyncs=0;this.maxQueue=0;this.ackTimeouts=0;
        this.performanceSeed=seed===undefined?String(Date.now())+':'+Math.random():seed;
    }
    Scheduler.prototype.clipBeats=function(c){return c.musicalFrames?c.musicalFrames/44100/this.beatSeconds:c.beats;};
    Scheduler.prototype.songState=function(s,complete){
        this.requestedState=s;
        var best=null,i,t,a,context;
        for(i=0;i<(s.targets||[]).length;i++){
            t=s.targets[i];if(t.weight>0&&this.assets[t.asset]&&(!best||t.weight>best.weight))best=t;
        }
        if(!best)return s;
        a=this.assets[best.asset];
        context=String(s.planKey||s.seed)+':'+(s.staged?'staging':'maze')+':'+(a.role==='BOSS'||a.role==='VICTORY'?a.role:'ordinary');
        if(!this.songTarget||this.songContext!==context||complete){
            this.songTarget={block:best.block,asset:best.asset,weight:1,lane:'song'};
            this.songContext=context;this.songEnd=null;
        }
        var out={};for(var key in s)out[key]=s[key];
        out.role=this.assets[this.songTarget.asset].role;
        out.targets=[this.songTarget];return out;
    };
    Scheduler.prototype.timeForBeat=function(beat){return this.origin+beat*this.beatSeconds;};
    Scheduler.prototype.boundary=function(now,beats,lead){return Math.max(0,Math.ceil((now+(lead===undefined?LOOKAHEAD:lead)-this.origin)/this.beatSeconds/beats)*beats);};
    Scheduler.prototype.install=function(a){
        if(!a||!a.id||!a.clips||!a.clips.length||a.clips.length>256)throw Error('invalid phrase arrangement');
        for(var i=0;i<a.clips.length;i++){
            var c=a.clips[i],valid=a.songFirst?c.beats>=4&&c.beats<=64&&c.beats%4===0:c.beats===8||c.beats===12||c.beats===64;
            if(!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(c.id)||!valid)throw Error('invalid rendered phrase');
            if(a.songFirst&&(c.songIndex!==i||!isFinite(c.musicalFrames)||c.musicalFrames%1!==0||Math.abs(c.musicalFrames-c.beats*60/130*44100)>2))throw Error('invalid song position');
        }
        if(!this.gridReady&&a.loop&&this.sink.continuous){
            var beats=a.songFirst?64:a.clips[0].beats,rate=this.sink.context.sampleRate;
            this.beatSeconds=Math.round(beats*60/this.base*rate)/(beats*rate);this.gridReady=true;
        }
        this.assets[a.id]=a;
    };
    Scheduler.prototype.cancel=function(l){if(l.pending){this.sink.cancel(l.pending);delete this.jobs[l.pending];l.pending=null;}};
    Scheduler.prototype.update=function(s,complete,atBeat){
        if(s.songFirst)s=this.songState(s,complete);
        var now=this.clock(),wanted={},i,t,l,id,retired=[];this.state=s;this.enabled=true;
        this.sink.volume((s.volume===undefined?.55:s.volume)*(1+.08*expression(s)),s.quality);
        for(i=0;i<(s.targets||[]).length&&i<2;i++){
            t=s.targets[i];if(t.weight<=0||!this.assets[t.asset])continue;id=t.lane||t.block;wanted[id]=true;l=this.lanes[id];
            if(!l){
                this.visits[id]=(this.visits[id]||0)+1;
                l={id:id,asset:t.asset,nextBeat:this.boundary(now,s.role==='VICTORY'?1:(this.sink.continuous?8:4),s.role==='VICTORY'?.25:LOOKAHEAD),
                    composer:new Composer(s.seed+':'+this.performanceSeed+':'+id+':'+this.visits[id]),began:false};this.lanes[id]=l;
            }else if(l.asset!==t.asset){
                this.cancel(l);l.asset=t.asset;l.finished=false;l.clip=null;l.passes=0;
                l.nextBeat=this.boundary(now,s.role==='VICTORY'?1:(this.sink.continuous?8:4),s.role==='VICTORY'?.25:LOOKAHEAD);
            }
            if(atBeat!==undefined)l.nextBeat=atBeat;
            l.block=t.block;l.retire=null;l.weight=t.weight;this.sink.mix(id,Math.sqrt(t.weight),now);
        }
        for(id in this.lanes)if(!wanted[id]){
            l=this.lanes[id];if(!l.retire){this.cancel(l);l.retire=now+1.2;this.sink.mix(id,0,now);}retired.push(l);
        }
        retired.sort(function(a,b){return a.retire-b.retire;});
        while(retired.length>2){l=retired.shift();this.sink.drop(l.id);delete this.lanes[l.id];}
        var used={};for(id in this.lanes)used[this.lanes[id].asset]=true;
        if(this.requestedState)for(i=0;i<this.requestedState.targets.length;i++)used[this.requestedState.targets[i].asset]=true;
        for(id in this.assets)if(!used[id])delete this.assets[id];
    };
    Scheduler.prototype.result=function(token,played){
        var j=this.jobs[token];if(!j)return;delete this.jobs[token];var l=this.lanes[j.lane];
        if(!l||l.pending!==token)return;l.pending=null;
        if(played){
            l.playedAsset=j.asset;l.passes=(l.passes||0)+1;if(j.choice)l.composer.accept(j.choice);
            l.heardChoice=j.choice;l.heardBeat=j.atBeat;
            if(!l.began||l.announcedBlock!==l.block){l.began=true;l.announcedBlock=l.block;this.callback('block',l.block||l.id);}
            var asset=this.assets[j.asset];
            if(this.state.songFirst&&asset&&asset.songFirst&&asset.loop&&j.choice.songIndex===asset.clips.length-1)this.songEnd=j.atBeat+j.beats;
            if(!j.loop){l.finished=true;this.victoryEnd=j.time+j.beats*this.beatSeconds;}
        }else{
            this.skipped++;this.resyncs++;
            if(!j.loop){l.finished=true;this.callback('victory','');}
            else if(l.began&&l.playedAsset===l.asset){
                // A native hold repeats the resident phrase. Retry on this
                // lane's original whole-passage grid, never halfway through it.
                if(this.state.songFirst&&l.heardChoice){
                    var span=this.clipBeats(l.heardChoice);
                    l.nextBeat=l.heardBeat+Math.max(1,Math.ceil((this.clock()+LOOKAHEAD-this.timeForBeat(l.heardBeat))/(span*this.beatSeconds)))*span;
                }else l.nextBeat+=Math.max(0,Math.ceil((this.clock()+LOOKAHEAD-this.timeForBeat(l.nextBeat))/(j.beats*this.beatSeconds)))*j.beats;
            }else l.nextBeat=this.boundary(this.clock(),this.sink.continuous?8:4);
        }
    };
    Scheduler.prototype.pump=function(){
        if(!this.enabled)return;var now=this.clock(),id,l,a,t,c,j,queued=0;
        if(this.songEnd!==null&&this.songEnd!==undefined&&this.timeForBeat(this.songEnd)<=now+LOOKAHEAD){
            var boundary=this.songEnd;this.songEnd=null;this.completedSongs=(this.completedSongs||0)+1;
            this.update(this.requestedState,true,boundary);
        }
        for(id in this.lanes){
            l=this.lanes[id];if(l.retire&&now>=l.retire){this.sink.drop(id);delete this.lanes[id];continue;}if(l.retire||l.finished)continue;
            a=this.assets[l.asset];if(!a)continue;
            if(l.pending){
                j=this.jobs[l.pending];
                // Native timing owns start eligibility. QueueJavascript can
                // deliver its result after a correct start; that round trip
                // must not reuse the much shorter audible-start tolerance.
                if(j&&j.time<now-ACK_WAIT){this.ackTimeouts++;this.sink.cancel(l.pending);this.result(l.pending,false);}else continue;
                if(l.finished)continue;
            }
            t=this.timeForBeat(l.nextBeat);
            if(t<now-LATE){
                this.skipped++;this.resyncs++;
                if(a.loop&&l.began&&l.clip&&l.playedAsset===l.asset)l.nextBeat+=Math.ceil((now+LOOKAHEAD-t)/(l.clip.beats*this.beatSeconds))*l.clip.beats;
                else l.nextBeat=this.boundary(now,this.sink.continuous?8:4);
                t=this.timeForBeat(l.nextBeat);
            }
            if(t<=now+LOOKAHEAD+.001){
                // One preparation per lane/pump. Never drain overdue debt.
                if(a.loop&&l.clip&&(l.passes||0)<passesFor(l.clip))c=l.clip;
                else{c=l.composer.choose(a,false);l.clip=c;l.passes=0;}
                var token=String(++this.serial);
                j={lane:id,asset:a.id,clip:c.id,beats:this.clipBeats(c),atBeat:l.nextBeat,time:t,loop:a.loop,choice:c};this.jobs[token]=j;l.pending=token;
                l.nextBeat+=j.beats;this.sink.prepare(token,id,c.id,Math.max(0,t-now),t);
            }
        }
        for(id in this.jobs)queued++;this.maxQueue=Math.max(this.maxQueue,queued);
        if(this.victoryEnd&&now>=this.victoryEnd){this.victoryEnd=null;this.callback('victory','');}
    };
    Scheduler.prototype.stop=function(){this.enabled=false;this.jobs={};this.lanes={};this.assets={};this.victoryEnd=null;this.songEnd=null;this.songTarget=null;this.requestedState=null;this.sink.stop();};
    // Rendered-audio transport, NOT a synthesizer. The audio rendering thread
    // owns all starts, loop points and releases; JS only prepares future work.
    var AUDIO_LEAD=.05,PCM_LIMIT=32*1024*1024,CLIP_LIMIT=4,LOAD_LIMIT=2,VOICE_LIMIT=8;
    function AudioTransport(context,request,result){
        this.context=context;this.request=request;this.result=result;this.continuous=true;
        this.cache={};this.loads={};this.jobs={};this.lanes={};this.assets={};this.voices=[];this.references={};this.error=null;this.errors=0;
        this.bytes=0;this.reserved=0;this.generation=0;this.stopped=false;this.playerVolume=.55;
        this.master=context.createGain();this.master.gain.value=0;this.master.connect(context.destination);
        this.masterEnvelope=[{at:context.currentTime,value:0}];this.missed=0;this.held=0;this.transitions=0;this.peakVoices=0;this.peakBytes=0;
    }
    AudioTransport.prototype.install=function(asset){
        if(!isFinite(asset.bound)||asset.bound<=0||asset.bound>2)throw Error('MS3 invalid arrangement bound');
        this.assets[asset.id]=asset;
    };
    AudioTransport.prototype.metadata=function(lane,clip){
        var id,a,i;for(id in this.assets){a=this.assets[id];for(i=0;i<a.clips.length;i++)if(a.clips[i].id===clip)return {clip:a.clips[i],asset:a};}
        return null;
    };
    AudioTransport.prototype.reap=function(){
        var now=this.context.currentTime,kept=[],i,v;
        for(i=0;i<this.voices.length;i++){v=this.voices[i];if(v.end<=now||v.ended){
            if(!v.disposed){
                v.disposed=true;v.entry.refs--;
                var lane=this.lanes[v.lane];if(lane&&lane.current===v)lane.current=null;
                try{v.source.disconnect();v.source.onended=null;v.source.buffer=null;v.gain.disconnect();}catch(ignore){}
            }
        }else kept.push(v);}
        this.voices=kept;
    };
    AudioTransport.prototype.room=function(bytes){
        this.reap();var ids=Object.keys(this.cache),self=this;
        ids.sort(function(a,b){return self.cache[a].used-self.cache[b].used;});
        while(ids.length&&(Object.keys(this.cache).length>=CLIP_LIMIT||this.bytes+this.reserved+bytes>PCM_LIMIT)){
            var id=ids.shift(),e=this.cache[id],busy=e.refs>0,k;
            for(k in this.jobs)if(this.jobs[k].clip===id)busy=true;
            if(!busy){this.bytes-=e.bytes;delete this.cache[id];}
        }
        return Object.keys(this.cache).length+Object.keys(this.loads).length<CLIP_LIMIT&&this.bytes+this.reserved+bytes<=PCM_LIMIT;
    };
    AudioTransport.prototype.build=function(buffer,info){
        var rate=buffer.sampleRate,c=info.clip,period=c.musicalFrames?Math.round(c.musicalFrames*rate/44100):Math.round(c.beats*60/130*rate),channels=buffer.numberOfChannels;
        if(channels!==2||Math.abs(buffer.duration-c.duration)>.08||period<1||buffer.length<=period||buffer.length>period*2)throw Error('MS3 decoded phrase shape mismatch: '+c.id);
        var tailFrames=buffer.length-period,loop=!!info.asset.loop;
        // Save only the short release, then reuse the decoded file's tail space
        // for head+release. Loop [tailFrames,period+tailFrames). The first body
        // remains untouched; every later body receives exactly one prior tail.
        // No extra period-sized allocation and no JS callbacks at loop edges.
        var tail=loop?this.context.createBuffer(channels,tailFrames,rate):null;
        var ch,i,x,sum=0,peak=0,tailPeak=0,src,out;
        for(ch=0;ch<channels;ch++){
            src=buffer.getChannelData(ch);out=tail&&tail.getChannelData(ch);
            for(i=0;i<src.length;i++){
                x=src[i];if(!isFinite(x))throw Error('MS3 non-finite phrase: '+c.id);
                peak=Math.max(peak,Math.abs(x));
                if(i<period)sum+=x*x;
                else{tailPeak=Math.max(tailPeak,Math.abs(x));if(out)out[i-period]=x;}
            }
            if(out)for(i=0;i<tailFrames;i++)src[period+i]=src[i]+out[i];
        }
        var rms=Math.sqrt(sum/(period*channels));
        if(rms<.00002||peak>.95)throw Error('MS3 invalid decoded level: '+c.id);
        return {id:c.id,asset:info.asset.id,role:info.asset.role,meta:c,buffer:buffer,tail:tail,
            period:period/rate,frames:period,loopStart:tailFrames/rate,rms:rms,peak:peak,tailPeak:tailPeak,
            bytes:(buffer.length+(tail?tail.length:0))*channels*4,refs:0,used:this.context.currentTime,loop:loop};
    };
    AudioTransport.prototype.receive=function(clip,encoded){
        var self=this,load=this.loads[clip];if(!load||load.decoding||this.stopped)return;
        var generation=this.generation;load.decoding=true;
        function complete(error,buffer){
            if(generation!==self.generation||self.stopped||self.loads[clip]!==load)return;
            delete self.loads[clip];self.reserved-=load.bytes;
            var e;
            try{if(error)throw error;e=self.build(buffer,load.info);if(self.bytes+self.reserved+e.bytes>PCM_LIMIT)throw Error('MS3 PCM admission exceeded');}
            catch(failure){self.error=String(failure);self.errors++;self.failClip(clip);return;}
            self.errors=0;self.error=null;
            self.cache[clip]=e;self.bytes+=e.bytes;self.peakBytes=Math.max(self.peakBytes,self.bytes+self.reserved);
            var tokens=Object.keys(self.jobs),i,j;for(i=0;i<tokens.length;i++){j=self.jobs[tokens[i]];if(j&&j.clip===clip&&!j.scheduled)self.schedule(j,e);}
        }
        try{
            if(typeof encoded!=='string'||!encoded.length||encoded.length>1400000)throw Error('MS3 missing/bounded local audio');
            var raw=atob(encoded),bytes=new Uint8Array(raw.length),i;for(i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
            // Callback form also works in older Chromium. Never start in the
            // decode callback unless the original FUTURE deadline still fits.
            this.context.decodeAudioData(bytes.buffer,function(buffer){complete(null,buffer);},function(){complete(Error('MS3 decode failed'));});
        }catch(error){complete(error);}
    };
    AudioTransport.prototype.failClip=function(clip){
        var tokens=Object.keys(this.jobs),i,j;for(i=0;i<tokens.length;i++){j=this.jobs[tokens[i]];if(j&&j.clip===clip&&!j.scheduled){delete this.jobs[j.token];this.missed++;this.result(j.token,false);}}
    };
    AudioTransport.prototype.prepare=function(token,lane,clip,delay,due){
        if(this.stopped)return;var info=this.metadata(lane,clip),l=this.lanes[lane],now=this.context.currentTime;
        if(!info||!l||due<now+AUDIO_LEAD){this.missed++;this.result(token,false);return;}
        var j={token:token,lane:lane,clip:clip,due:due,info:info};this.jobs[token]=j;
        l.requestedAt=now;
        if(this.cache[clip]){this.schedule(j,this.cache[clip]);return;}
        if(this.loads[clip])return;
        var estimate=(Math.ceil((info.clip.duration+(info.asset.loop?info.clip.duration-info.clip.beats*60/130:0))*this.context.sampleRate)+4)*8;
        if(Object.keys(this.loads).length>=LOAD_LIMIT||!this.room(estimate)){delete this.jobs[token];this.missed++;this.result(token,false);return;}
        this.loads[clip]={info:info,bytes:estimate,at:now};this.reserved+=estimate;
        this.peakBytes=Math.max(this.peakBytes,this.bytes+this.reserved);this.request(lane,clip);
    };
    AudioTransport.prototype.voice=function(entry,lane,due,tail,norm){
        this.reap();if(this.voices.length>=VOICE_LIMIT)throw Error('MS3 voice admission exceeded');
        var ctx=this.context,source=ctx.createBufferSource(),gain=ctx.createGain();
        source.buffer=tail?entry.tail:entry.buffer;source.loop=!tail&&entry.loop;
        if(source.loop){source.loopStart=entry.loopStart;source.loopEnd=entry.buffer.duration;}
        gain.gain.value=norm;source.connect(gain);gain.connect(lane.gain);
        var v={entry:entry,source:source,gain:gain,norm:norm,tail:!!tail,lane:lane.id,due:due,end:tail?due+entry.tail.duration:(entry.loop?Infinity:due+entry.buffer.duration)};
        source.onended=function(){v.ended=true;};entry.refs++;entry.used=ctx.currentTime;
        source.start(due);
        this.voices.push(v);this.peakVoices=Math.max(this.peakVoices,this.voices.length);return v;
    };
    AudioTransport.prototype.schedule=function(j,e){
        this.reap();
        var ctx=this.context,now=ctx.currentTime,l=this.lanes[j.lane],old=l&&l.current;
        if(old&&old.end<=j.due)old=null; // no release/cancellation ownership of an already finished fanfare
        if(!l||j.due<now+AUDIO_LEAD){delete this.jobs[j.token];this.missed++;this.result(j.token,false);return;}
        if(old&&old.entry.id===e.id&&old.end>j.due){
            // Resident looping is already running on the sample clock. Do not
            // reopen, seek, restart, fade or create another source each pass.
            j.scheduled=true;j.resident=true;l.confirmed=j.due;this.held++;return;
        }
        this.reap();if(this.voices.length+(old?2:1)>VOICE_LIMIT){delete this.jobs[j.token];this.missed++;this.result(j.token,false);return;}
        var reference=this.references[e.asset];if(!reference)this.references[e.asset]=reference=e.rms;
        var norm=j.info.asset.songFirst?1:clamp(reference/e.rms,1/Math.SQRT2,Math.SQRT2);
        j.previous=old;j.previousBound=l.bound;
        // The bound is arrangement-wide and fixed across ordinary successors.
        // One conservative lane budget covers a full incoming phrase plus an
        // interrupted previous arrangement. Routine successors do not change it.
        l.bound=Math.max(j.info.asset.bound,l.bound||0);
        if(old&&old.entry.asset!==e.asset)l.bound=Math.max(l.bound,(old.entry.peak+e.peak+old.entry.tailPeak+e.tailPeak));
        j.voice=this.voice(e,l,j.due,false,norm);j.scheduled=true;l.current=j.voice;l.confirmed=j.due;
        if(old){
            var turns=(j.due-old.due)/old.entry.period;
            if(old.entry.loop&&Math.abs(turns-Math.round(turns))<.002){
                j.tail=this.voice(old.entry,l,j.due,true,old.norm);
                old.source.stop(j.due);old.end=j.due;
            }else{
                // Victory can interrupt at a beat rather than an ordinary
                // phrase boundary. That exceptional cut gets a short release.
                old.gain.gain.setValueAtTime(old.norm,j.due);old.gain.gain.linearRampToValueAtTime(0,j.due+.12);
                old.source.stop(j.due+.12);old.end=j.due+.12;
            }
        }
        this.applyMix();this.transitions++;
    };
    AudioTransport.prototype.cancel=function(token){
        var j=this.jobs[token];if(!j)return;delete this.jobs[token];var now=this.context.currentTime,l=this.lanes[j.lane];
        if(j.voice&&j.due>now){
            j.voice.source.stop(now);j.voice.end=now;if(j.tail){j.tail.source.stop(now);j.tail.end=now;}
            if(j.previous&&!j.previous.ended){
                // A later stop replaces a not-yet-reached stop in Web Audio.
                j.previous.source.stop(now+86400);j.previous.end=now+86400;
                j.previous.gain.gain.cancelScheduledValues(now);j.previous.gain.gain.setValueAtTime(j.previous.norm,now);
            }
            if(l&&l.current===j.voice){l.current=j.previous;l.bound=j.previousBound;}
            this.applyMix();
        }
        this.reap();
    };
    function levelAt(points,when){
        var prev=points[0],next,i;if(when<=prev.at)return prev.value;
        for(i=1;i<points.length;i++){next=points[i];if(when<=next.at)return prev.value+(next.value-prev.value)*(when-prev.at)/(next.at-prev.at);prev=next;}
        return prev.value;
    }
    AudioTransport.prototype.mix=function(id,value){
        var l=this.lanes[id],ctx=this.context;if(!l){
            if(Object.keys(this.lanes).length>=4)return;
            l={id:id,gain:ctx.createGain(),weight:0,envelope:[{at:ctx.currentTime,value:0}]};
            l.gain.gain.value=0;l.gain.connect(this.master);this.lanes[id]=l;
        }
        value=clamp(value,0,1);if(l.weight===value&&!l.retired)return;
        l.retired=false;l.weight=value;this.applyMix();
    };
    AudioTransport.prototype.volume=function(value){
        value=clamp(value,0,1);if(value===this.playerVolume)return;this.playerVolume=value;this.applyMix();
    };
    AudioTransport.prototype.applyMix=function(){
        // Rebuild the small future automation horizon after a real state change.
        // A queued incoming source must NOT replace the audible outgoing source
        // in the present-time mix. Source starts, not JS ticks, own this horizon.
        var now=this.context.currentTime,events=[now],i,v,id,l,at,active,power,targets,normalizer,current,goal,total=0;
        for(i=0;i<this.voices.length;i++){v=this.voices[i];if(!v.disposed&&!v.ended&&v.due>now&&events.indexOf(v.due)<0)events.push(v.due);}
        events.sort(function(a,b){return a-b;});
        var envelopes={},maxima={};
        for(id in this.lanes){l=this.lanes[id];current=levelAt(l.envelope,now);envelopes[id]=[{at:now,value:current}];maxima[id]=current;}
        for(i=0;i<events.length;i++){
            at=events[i];active={};power=0;targets={};
            for(var n=0;n<this.voices.length;n++){
                v=this.voices[n];if(!v.tail&&!v.ended&&v.due<=at&&v.end>at&&this.lanes[v.lane])active[v.lane]=true;
            }
            for(id in active){l=this.lanes[id];power+=l.weight*l.weight;}
            // If a floor is still decoding, retain the audible floor instead
            // of fading to nothing. Retired voices are released after handoff.
            if(power===0){for(id in active){targets[id]=1;power++;}}
            else for(id in active)targets[id]=this.lanes[id].weight;
            normalizer=power>0?1/Math.sqrt(power):1;
            for(id in this.lanes){
                var points=envelopes[id];goal=(targets[id]||0)*normalizer;current=levelAt(points,at);
                // Keep a scheduled ramp if it already leads to this target.
                if(Math.abs(points[points.length-1].value-goal)<1e-9)continue;
                while(points.length>1&&points[points.length-1].at>=at)points.pop();
                if(points[points.length-1].at===at)points[points.length-1].value=current;
                else points.push({at:at,value:current});
                points.push({at:at+.7,value:goal});maxima[id]=Math.max(maxima[id],goal,current);
            }
        }
        // Reserve each lane's full+tail bound, including the largest value it
        // can take during a crossfade. The master never pumps at routine joins.
        for(id in this.lanes)total+=(this.lanes[id].bound||0)*maxima[id]*Math.SQRT2;
        var master=Math.min(4*this.playerVolume,total>0?.8/total:4*this.playerVolume);
        current=levelAt(this.masterEnvelope,now);
        this.master.gain.cancelScheduledValues(now);
        // Headroom reductions precede increases. Only deliberate floor/role or
        // volume changes may lower this reserve; ordinary clip joins are fixed.
        if(master<current){this.master.gain.setValueAtTime(master,now);this.masterEnvelope=[{at:now,value:master}];}
        else {this.master.gain.setValueAtTime(current,now);this.master.gain.linearRampToValueAtTime(master,now+.7);this.masterEnvelope=[{at:now,value:current},{at:now+.7,value:master}];}
        for(id in this.lanes){
            l=this.lanes[id];l.envelope=envelopes[id];l.gain.gain.cancelScheduledValues(now);
            l.gain.gain.setValueAtTime(l.envelope[0].value,now);
            for(i=1;i<l.envelope.length;i++)l.gain.gain.linearRampToValueAtTime(l.envelope[i].value,l.envelope[i].at);
        }
    };
    AudioTransport.prototype.drop=function(id){
        var tokens=Object.keys(this.jobs),i,j,l=this.lanes[id];
        for(i=0;i<tokens.length;i++){j=this.jobs[tokens[i]];if(j&&j.lane===id)this.cancel(j.token);}
        if(!l)return;if(!l.current){this.releaseLane(id);return;}l.retired=true;l.weight=0;l.retiredAt=this.context.currentTime;this.applyMix();
    };
    AudioTransport.prototype.releaseLane=function(id){
        var now=this.context.currentTime,l=this.lanes[id];
        for(var i=0;i<this.voices.length;i++)if(this.voices[i].lane===id){try{this.voices[i].source.stop(now);}catch(ignore){}this.voices[i].end=now;}
        if(l)try{l.gain.disconnect();}catch(ignore){}delete this.lanes[id];this.reap();this.applyMix();
    };
    AudioTransport.prototype.tick=function(){
        if(this.stopped)return;var now=this.context.currentTime,tokens=Object.keys(this.jobs),i,j,id;
        this.reap();
        for(i=0;i<tokens.length;i++){
            j=this.jobs[tokens[i]];if(!j)continue;
            if(j.scheduled&&now>=j.due){delete this.jobs[j.token];this.result(j.token,true);}
            else if(!j.scheduled&&now>=j.due-AUDIO_LEAD){delete this.jobs[j.token];this.missed++;this.result(j.token,false);}
        }
        for(id in this.loads)if(now-this.loads[id].at>3){
            // A decoding request continues occupying its slot until callback or
            // full renderer teardown; repeated failure cannot grow async work.
            this.error='MS3 local audio decode timed out';if(!this.loads[id].failed){this.loads[id].failed=true;this.errors++;}this.failClip(id);
        }
        if(this.errors>=3||(this.error&&!this.voices.length))throw Error(this.error||'MS3 repeated decode failure');
        for(id in this.lanes){var l=this.lanes[id];
            if(l.retired&&levelAt(l.envelope,now)<=.0001&&now>l.retiredAt+.7)this.releaseLane(id);
            // A resident musical loop remains bounded even during a long JS
            // stall. Do not cut healthy music merely because preparation is late.
            l.waiting=!!(l.current&&l.current.entry.loop&&now>(l.confirmed||l.current.due)+l.current.entry.period);
        }
    };
    AudioTransport.prototype.stop=function(){
        if(this.stopped)return;this.stopped=true;this.generation++;
        for(var i=0;i<this.voices.length;i++){try{this.voices[i].source.stop();this.voices[i].source.disconnect();this.voices[i].gain.disconnect();}catch(ignore){}}
        for(var id in this.lanes)try{this.lanes[id].gain.disconnect();}catch(ignore){}
        this.master.disconnect();this.voices=[];this.jobs={};this.cache={};this.loads={};this.lanes={};this.assets={};this.references={};this.bytes=0;this.reserved=0;
    };
    AudioTransport.prototype.stats=function(){return {transport:'sample-clock',bufferLayout:'compact-tail-loop',decodedClips:Object.keys(this.cache).length,pendingDecodes:Object.keys(this.loads).length,
        waitingLanes:Object.keys(this.lanes).filter(function(id){return this.lanes[id].waiting;},this).length,pcmBytes:this.bytes+this.reserved,peakPCMBytes:this.peakBytes,voices:this.voices.length,peakVoices:this.peakVoices,
        missedPreparations:this.missed,residentPasses:this.held,scheduledTransitions:this.transitions,sampleRate:this.context.sampleRate,error:this.error};};

    function attach(bridge,allowAudio){
        var scheduler,transport,context,interval,closed=false,initializing=true,backend,fallbackReason;
        var hostClock=window.performance&&window.performance.now?function(){return window.performance.now()/1000;}:function(){return Date.now()/1000;};
        var nativeSink={prepare:function(token,lane,clip,delay,deadline){bridge.prepare(token,lane,clip,delay,deadline);},cancel:function(token){bridge.cancel(token);},
            mix:function(id,g){bridge.mix(id,g);},volume:function(v,q){bridge.volume(v,q);},drop:function(id){bridge.drop(id);},stop:function(){bridge.stop();}};
        function disposeContext(){if(context){try{var closing=context.close();if(closing&&closing.catch)closing.catch(function(){});}catch(ignore){}context=null;}}
        function finish(useAudio,reason){
            if(!initializing||closed)return;
            var sink=nativeSink,clock=hostClock;
            if(useAudio){
                try{
                    // Some older HTML engines expose AudioContext but not the
                    // complete buffer/gain API. Construction failure must still
                    // take the native path, not consume readiness and go silent.
                    for(var i=0,required=['createGain','createBufferSource','createBuffer','decodeAudioData'];i<required.length;i++)
                        if(typeof context[required[i]]!=='function')throw Error('MS3 incomplete audio API: '+required[i]);
                    if(context.sampleRate>44100)throw Error('MS3 requested 44100 Hz unavailable; use bounded native playback');
                    transport=new AudioTransport(context,function(lane,clip){bridge.readclip(lane,clip);},function(token,played){scheduler.result(token,played);});
                }catch(error){useAudio=false;transport=null;reason=String(error);}
            }
            if(useAudio){sink=transport;clock=function(){return context.currentTime;};backend='surge-sample-clock';}
            else{disposeContext();backend='surge-rendered';}
            initializing=false;fallbackReason=reason||null;
            scheduler=new Scheduler(130,sink,clock,function(name,value){if(name==='block')bridge.block(value);else bridge.victory();});
            interval=window.setInterval(function(){try{
                // Report work the audio thread already performed BEFORE the
                // control scheduler considers acknowledgement timeouts.
                if(transport){if(context.state==='closed')throw Error('MS3 audio context closed');transport.tick();}
                scheduler.pump();
            }catch(e){bridge.error(String(e));scheduler.stop();}},25);
            bridge.ready(backend,clock());
        }
        // No autoplay-policy workarounds: try the supported context, then use
        // native audio when unavailable/suspended. Never run both at once.
        window.setTimeout(function(){
            if(closed)return;
            var Constructor=window.AudioContext||window.webkitAudioContext;
            if(allowAudio===false||!bridge.readclip||!Constructor){finish(false,'Audio clock unavailable or disabled');return;}
            try{
                context=new Constructor({sampleRate:44100});
                if(context.state==='running'||context.state===undefined){finish(true);return;}
                var resumed=context.resume();
                if(resumed&&resumed.then)resumed.then(function(){if(context&&context.state==='running')finish(true);},function(){finish(false,'Audio context resume rejected');});
                window.setTimeout(function(){if(initializing)finish(context&&context.state==='running','Audio context did not start');},400);
            }catch(e){finish(false,String(e));}
        },0);
        function halt(){closed=true;if(interval)window.clearInterval(interval);if(scheduler)scheduler.stop();disposeContext();}
        return {install:function(a){if(scheduler){scheduler.install(a);if(transport)transport.install(a);}},
            state:function(s){if(!scheduler)return;if((s.bpm||130)!==scheduler.base)throw Error('rendered bank tempo mismatch');scheduler.update(s);if(transport)transport.assets=scheduler.assets;},
            audio:function(clip,data){if(transport&&!closed)transport.receive(clip,data);},
            result:function(token,played){if(scheduler&&!transport)scheduler.result(String(token),played);},stop:halt,
            stats:function(){if(!scheduler)return;var stats={backend:backend,bpm:scheduler.base,lateSkipped:scheduler.skipped,resyncs:scheduler.resyncs,
                prepared:Object.keys(scheduler.jobs).length,peakPrepared:scheduler.maxQueue,ackTimeouts:scheduler.ackTimeouts,phrasePasses:PHRASE_PASSES,fallbackReason:fallbackReason};
                if(scheduler.state.songFirst){var lane=scheduler.lanes.song;stats.song={asset:lane&&lane.playedAsset,part:lane&&lane.heardChoice&&lane.heardChoice.songIndex+1,completed:scheduler.completedSongs||0,requested:scheduler.requestedState&&scheduler.requestedState.targets};}
                if(transport)stats.audio=transport.stats();bridge.stats(JSON.stringify(stats));},destroy:halt};
    }
    return {AudioTransport:AudioTransport,levelAt:levelAt,Composer:Composer,Scheduler:Scheduler,Random:Random,expression:expression,tempo:function(base){return base;},attach:attach,lookahead:LOOKAHEAD,lateTolerance:LATE,acknowledgementWait:ACK_WAIT,phrasePasses:PHRASE_PASSES};
})();
export default MS3Engine;
