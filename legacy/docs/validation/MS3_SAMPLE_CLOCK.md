# MS3 — continuous rendered score

Author direction: repair rhythmic and dynamic clip segmentation in the current Music System 3. Parent source: `90510057c608f8e2beec9debc6ceec36b35d14f3`. This is a source repair, not Workshop/VPS deployment or native listening acceptance.

## Demonstrated mechanism and repair

The prior native transport starts at a rendered-frame deadline and fast-seeks past elapsed samples. That can remove downbeat attacks. Its emergency resident repeat also seeks a channel and cuts its rendered release. More fading cannot make these operations sample-clock accurate.

Capable DHTML clients now use `AudioBufferSourceNode` to play the same bundled, offline-rendered Surge Oggs. This is not a synthesizer, oscillator, runtime Surge dependency or HTTP soundtrack. The existing MusicDirector still owns permissions, floor/role selection, staging, stairs, victory and announcements. Older or blocked HTML audio falls back to the existing native channel player; diagnostics distinguish the transports. A sample-clock decode failure falls back once instead of creating a silent retry loop. Only one backend is audible.

A looping buffer contains an untouched first body and a second body with the previous recorded tail folded into its start. Native audio-thread looping repeats that second body. Four ordinary passes use one source with no reopen, seek, boundary fade or per-pass volume write. A replacement is decoded in advance and starts at a future eight-beat boundary. The previous release is transferred once. Late preparation leaves healthy resident music running; long control-thread stalls alone do not cut it. The phrase clock and loop points share the same integer sample count. Victory remains once-only and may enter on its beat boundary.

Successor choice favors cadence and similar energy rather than rising energy plus large random jumps. Only heard choices enter history. Per-arrangement body-RMS anchoring, bounded to ±3 dB, reduces incidental phrase-level jumps without flattening intended role dynamics. Master gain 4, saved volume and a conservative 0.8 shared peak ceiling remain; ordinary same-arrangement joins do not change the master reserve. Genuine role interruptions retain a short cutoff release. Floor changes use scheduled 0.7-second mix ramps; an unprepared incoming floor does not mute the outgoing floor.

## Bounds and trust

Four cached decoded clips; two asynchronous loads; eight source voices; 32 MiB estimated decoded PCM. Decode slots remain reserved until completion or teardown. The Lua bridge checks current authoritative targets, catalog membership, safe IDs, Ogg header and a 256 KiB encoded-file ceiling, and admits at most two local reads per 100 ms. No arbitrary file path or unrestricted Lua bridge. Cancellation restores resident playback, stale callbacks cannot resurrect stopped music, and Off/teardown destroys all sources and buffers.

## Finite tests and evidence boundary

`node tools/test_ms3_transport.js` exercises production buffer assembly, exact future starts, four-pass residency, RMS matching, release transfer, cancellation, delayed acknowledgements, late decoding, retry boundaries, stair handoff/reversal, stale callbacks, Off, once-only victory, history commits, grid drift and resource bounds. Initial local run: 8,298 assertions passed. Follow-up coverage adds finished-fanfare reference cleanup and missing/throwing HTML audio APIs; these must fall back once without a silent readiness retry.

`python3 tools/test_ms3_audio.py` uses an actual Chromium OfflineAudioContext, not a mocked speaker. Its transient/pad/release fixture tests six musical joins, including a changed recording at four passes, against a continuously constructed overlap-add reference without masking boundary samples. Initial measured maximum sample error was 2.76e-8; maximum join-level error was below 0.000001 dB. This validates the transport arithmetic, not subjective native sound quality.

`python3 tools/test_ms3_audio.py --bank` additionally decodes and renders the first/last committed Ogg pair in every looping arrangement. Full source gates remain `python3 tools/test_music_gate.py`, `python3 tools/test_ms2_surge_bank.py --decode` and `python3 tools/test_checkpoint_g_integration.py`. CI logs/artifacts record actual outcomes; this document does not pre-claim a CI pass.

## GDD synchronization

Live GDD identity remains `1OSpgiWyiGmUCLFdq--WmCSZe6KQIr7_UTkQZklPV8lY`. Navigation followed 00 → 01 → relevant 05/07 rules. Existing live text still describes older streamed playback because prior amendments were rejected. The author expressly authorizes this correction. The current atomic prepend to tabs 01/05/07 was also rejected by Google with HTTP 400 `FAILED_PRECONDITION` (precondition check failed). **The live GDD was not updated.** Authorized replacement rules are preserved in `docs/validation/MS3_GDD_AMENDMENT.md`; do not misreport them as applied.

## Native acceptance still required

Fully quit GMod, update/install the exact published main and enable Music through Options. Listen through repeated staging phrases, danger changes and a stair crossing/reversal. Success means stable downbeats, no recurring fade dip, no audible technical segmentation, functional saved volume and clean Off/On with acceptable Steam Deck performance. `lod_music_client_status` should show `system="MS3"`, `backend="surge-sample-clock"` and decoded-buffer statistics. A `surge-rendered` backend means compatibility fallback; it does not establish sample-accurate native continuity. Run the status command twice one second apart if needed because HTML statistics arrive asynchronously. Preserve console_latest.txt and rpg_summary_latest.txt for contradictory runtime evidence.
