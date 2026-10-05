"""Bounded Standard MIDI File reader used only by the MS2 offline compiler.

No audio, network, third-party dependencies or executable archive contents.
Times are quarter-note beats; tempo changes are retained for source analysis.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import struct


@dataclass
class Midi:
    notes: list
    tempos: list
    meters: list
    programs: dict
    names: list
    end: float


def write_clip(notes, bpm, beats):
    """Export one curated phrase as a DAW-editable format-1 MIDI file.

    Conductor plus the nine named virtual-instrument parts, at MS2's 48 PPQ.
    GM programs are audition hints; the game uses its own synthesizer voices.
    """
    def vlq(value):
        out=[value&127];value >>= 7
        while value: out.insert(0,(value&127)|128);value >>= 7
        return bytes(out)
    def track(events):
        data=bytearray();last=0
        for tick,order,message in sorted(events,key=lambda e:(e[0],e[1],e[2])):
            data.extend(vlq(tick-last));data.extend(message);last=tick
        data.extend(vlq(beats*48-last));data.extend(b'\xff\x2f\x00')
        return b'MTrk'+struct.pack('>I',len(data))+data
    def name(text):
        data=text.encode('ascii');return b'\xff\x03'+vlq(len(data))+data
    tempo=round(60_000_000/bpm)
    tracks=[track([(0,0,name('MS2 D Dorian')),(0,1,b'\xff\x51\x03'+tempo.to_bytes(3,'big')),
                   (0,2,b'\xff\x58\x04\x04\x02\x18\x08')])]
    names=('acid','industrial','strings','brass','bass','tom','snare','kick','hat')
    programs=(81,30,50,62,38)
    for inst,label in enumerate(names):
        channel=inst if inst<5 else 9;events=[(0,-2,name(label))]
        if inst<5: events.append((0,-1,bytes((0xc0|channel,programs[inst]))))
        for tick,gate,instrument,pitch,velocity in notes:
            if instrument!=inst: continue
            events.append((tick,1,bytes((0x90|channel,pitch,velocity))))
            events.append((tick+gate,0,bytes((0x80|channel,pitch,0))))
        tracks.append(track(events))
    return b'MThd'+struct.pack('>IHHH',6,1,len(tracks),48)+b''.join(tracks)


def read(data: bytes) -> Midi:
    if len(data) < 14 or len(data) > 4_000_000 or data[:4] != b'MThd':
        raise ValueError('not a bounded MIDI file')
    header_size = struct.unpack_from('>I', data, 4)[0]
    if header_size < 6 or len(data) < 8 + header_size:
        raise ValueError('truncated MIDI header')
    fmt, tracks, ppq = struct.unpack_from('>HHH', data, 8)
    if fmt not in (0, 1) or not 1 <= tracks <= 128 or not ppq or ppq & 0x8000:
        raise ValueError('requires format 0/1 and musical PPQ time')
    pos, notes, tempos, meters, programs, names = 8 + header_size, [], [], [], {}, []
    last_tick = 0
    for track in range(tracks):
        if pos + 8 > len(data) or data[pos:pos+4] != b'MTrk':
            raise ValueError('missing MIDI track')
        size = struct.unpack_from('>I', data, pos+4)[0]
        pos += 8
        end = pos + size
        if end > len(data):
            raise ValueError('truncated MIDI track')
        tick, running, active, held, pedal = 0, None, defaultdict(deque), defaultdict(list), {}

        def byte():
            nonlocal pos
            if pos >= end:
                raise ValueError('truncated MIDI event')
            value = data[pos]
            pos += 1
            return value

        def vlq():
            value = 0
            for _ in range(4):
                b = byte()
                value = value * 128 + (b & 127)
                if not b & 128:
                    return value
            raise ValueError('invalid MIDI VLQ')

        def finish(ch, pitch, start, velocity):
            if tick > start:
                notes.append((start/ppq, (tick-start)/ppq, pitch, velocity, ch, track))
                if len(notes) > 200_000:
                    raise ValueError('too many MIDI notes')

        while pos < end:
            tick += vlq()
            if tick > ppq * 32768:
                raise ValueError('MIDI musical duration limit exceeded')
            status = byte()
            if status < 128:
                if running is None:
                    raise ValueError('MIDI running status without channel event')
                pos -= 1
                status = running
            if status == 0xFF:
                meta, length = byte(), vlq()
                payload = data[pos:pos+length]
                pos += length
                if pos > end:
                    raise ValueError('truncated MIDI metadata')
                if meta == 0x51 and length == 3:
                    usec = int.from_bytes(payload, 'big')
                    if usec:
                        tempos.append((tick/ppq, 60_000_000/usec))
                elif meta == 0x58 and length >= 2:
                    meters.append((tick/ppq, payload[0], 2**payload[1]))
                elif meta in (3, 4):
                    names.append(payload.decode('utf-8', errors='replace'))
                # SMF meta events do not cancel running channel status.
                continue
            if status in (0xF0, 0xF7):
                length = vlq()
                pos += length
                if pos > end:
                    raise ValueError('truncated MIDI sysex')
                running = None
                continue
            if status >= 0xF0:
                raise ValueError('unsupported MIDI system event')
            running = status
            kind, ch = status >> 4, status & 15
            a, b = byte(), 0
            if kind not in (0xC, 0xD):
                b = byte()
            if a >= 128 or b >= 128:
                raise ValueError('invalid MIDI channel data')
            if kind == 9 and b:
                active[ch, a].append((tick, b))
            elif kind == 8 or kind == 9 and not b:
                if active[ch, a]:
                    start, velocity = active[ch, a].popleft()
                    if pedal.get(ch):
                        held[ch].append((a, start, velocity))
                    else:
                        finish(ch, a, start, velocity)
            elif kind == 0xB and a == 64:
                down = b >= 64
                if not down:
                    for pitch, start, velocity in held[ch]:
                        finish(ch, pitch, start, velocity)
                    held[ch] = []
                pedal[ch] = down
            elif kind == 0xB and a in (120, 123):
                for (channel, pitch), entries in active.items():
                    if ch == channel:
                        while entries:
                            finish(ch, pitch, *entries.popleft())
                for pitch, start, velocity in held[ch]:
                    finish(ch, pitch, start, velocity)
                held[ch] = []
            elif kind == 0xC:
                programs[ch] = a
        for (ch, pitch), entries in active.items():
            for start, velocity in entries:
                finish(ch, pitch, start, velocity)
        for ch, entries in held.items():
            for pitch, start, velocity in entries:
                finish(ch, pitch, start, velocity)
        last_tick = max(last_tick, tick)
    if len(notes) > 200_000:
        raise ValueError('too many MIDI notes')
    return Midi(sorted(notes), sorted(set(tempos)), sorted(set(meters)), programs, names, last_tick/ppq)
