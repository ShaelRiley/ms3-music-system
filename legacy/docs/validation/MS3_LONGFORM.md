# MS3 — sixteen-bar source integration

## Implementation

Repair parent: `208a1af11c4448a054cc24e81603ed3446c0c55f`. Source/render candidate `ea104e8fcb59fe0e24f4bfa244edf436b265e462` was produced by successful Actions render run **37003508659**. Final source publication must additionally pass the complete gates listed below.

All 465 original MIDI stems map to 157 contiguous 64-beat passages across 40 looping arrangements and eight 12-beat fanfares, retaining eight blocks and all 48 roles. Catalog `ms3-s16-e5961c1e5e7bf8cd` contains 121,557 notes. The 24 recurring block fingerprint candidates and complete foreground parts guide rearrangement, not an assumed human judgment of motif quality. The audit preserves source bytes/hashes, windows, foreground/motif anchors, thinning decisions and 39 source percussion candidates. Seven weak non-adjacent combat/boss exits receive baked final-bar tom/snare/hat replacements. They preserve melody/bass/kick and are not runtime-triggered overlays. No two-bar tiling, new melodic notes or time stretching is used.

Surge bank `ms2-surge-1d9386ddd67218a5` contains 165 clips plus the existing D/A ambient bridge, **46,853,341 bytes**, largest file **333,786 bytes**. Source-note hashes, PCM/encoded hashes, exact durations, measured levels, renderer, patches and pinned Surge build identity are in `MS2_SURGE_BANK.json`. Patches/timbres are unchanged.

The compact transport saves only the short release; it folds head+release into decoded tail space and loops [tailLength, period+tailLength), preserving the first dry pass. Three real-size long recordings plus reservations peak at **32,427,776 bytes**, below the unchanged 32-MiB limit. A fourth live recording is deferred, resident audio continues, and retirement permits subsequent admission. Ordinary passages advance after one complete pass. Changed roles/stairs use short boundaries; unready successors never truncate healthy music. Native fallback remains mutually exclusive and frame-timed, not sample-accurate.

## Focused evidence already observed

- Source arrangement: **14 tests** (including MIDI round-trip, original lineage, protected foreground/motif, bass/kick, retriggers, polyphony, deterministic outputs, bounded shards, export and seven exact source-derived exit fills).
- Composer: **218,756 assertions**, real 64-beat catalog, 15 stall cases, one-pass advance, ready role/stair responsiveness and late successor recovery.
- Sample-clock ownership/memory: **5,432 assertions**, three actual-size long buffers, fourth-buffer refusal/recovery, tails, cancellation, cleanup and unsupported 48-kHz context fallback.
- Native resources: **2,032 assertions**, 15 stall cases and channel peak 8; preserving healthy music while replacement/role preparation is late.
- Music gate: **45/45**, syntax **875 Lua files** on the integrated bank.
- Full-bank ffmpeg decode: **166/166 recordings**.
- Actual Chromium synthetic long-form overlap-add: six joins, maximum absolute sample error **2.05e-8** against independent dry-reference buffers.
- Actual Chromium Surge pairs: **40 looping arrangements, 80 decodes, 240 loop/successor joins**, max absolute sample error **6.54e-8**, maximum reference-relative join-level error **7.95e-7 dB**, output peak **0.494078**. This proves the transport matches the reference, not that all compositional joins are perceptually invisible.

Final immutable-tree integration/music receipts and source fingerprints are recorded in `MS3_LONGFORM_RECEIPT.json` when the final gate completes. No passing full-matrix result is asserted before that receipt exists.

## Failed evidence and boundaries

First render run **37003316051** passed source verification/remapping but failed because ffmpeg was missing on the runner. The follow-up installed the explicit dependency and completed full rendering, decode and isolated-branch publication. No partial render was promoted to main.

A preliminary serial local matrix was stopped by the agent to freeze documentation and run the final matrix with per-suite receipts/four workers. Its partial log is not full validation. The original two-bar transport/bank and earlier failed native music reports remain historical evidence, not new acceptance.

YouTube reference `https://www.youtube.com/watch?v=8yu502IyV0o`: direct retrieval/cache miss and exact-ID search yielded no usable source; yt-dlp required sign-in. No video-specific arrangement method is claimed. The live GDD tuning insertion again returned `FAILED_PRECONDITION`; exact unapplied text is in `MS3_LONGFORM_GDD_AMENDMENT.md`. Explicit author direction is retained. No Workshop or VPS deployment occurred.

## Native acceptance still required

Fully quit GMod, update/install the published main, launch LoD on `gm_flatgrass`, and enable Player Menu → Options → Music. Listen through at least two whole passages (roughly one minute), danger, stairs/reversal and Off/On; continue normal play through boss and a genuine rescue/fanfare. Verify audible evolving sixteen-bar motifs, stable loudness, unobtrusive joins, responsive role changes, once-only fanfare, immediate Off and acceptable Steam Deck performance. A present source fill should sound like part of the arrangement, not a second kit. If problems persist, run `lod_music_client_status` twice and retain `console_latest.txt` and `rpg_summary_latest.txt`. Native output, subjective guide/arrangement quality, actual decoder heap and FPS have not been accepted by automated evidence.

## Final independent checkpoint result

GitHub Actions completed **299/299 integration suites with zero source changes during the gate**, **45/45 music checks**, **166 actual recording decodes**, and **240 real browser loop/successor joins across 40 arrangements**. `MS3_LONGFORM_RECEIPT.json` contains the exact validated source fingerprints and complete per-suite receipts. Only this evidence receipt and this result paragraph were added after the immutable gates; no production code, score or recording changed afterward. Native listening remains pending.
