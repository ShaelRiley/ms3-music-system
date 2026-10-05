# MS3 — source-ordered song-first playback

## Scope and failed native evidence

Implementation parent: `a73cafd2a7678bafe4bf84e8b4132af449546baa`. Preserve intervening Gordon/gameplay work. The user reports that the previously delivered sixteen-bar system remains musically disjunct. That report is failed perceptual acceptance, even though its earlier timing/reference tests passed.

Two implementation causes are removed: selection of a small ranked subset of source windows with randomized successors, and restarting the entire instrument performance at each storage boundary. Ordinary floor and pressure changes also no longer cut off the ongoing song. The existing sample-clock/native transports and their resource/safety limits are extended, not replaced by another music system.

## Source and audio

All 465 original MIDI stems map to eight blocks and 48 arrangements: 40 ordinary song edits plus eight twelve-beat fanfares. Every retained source section plays chronologically. All driving-proxy cells are retained, and isolated four-bar breaks remain. Long non-driving sections and introductions/outros are omitted outside staging. Staging retains all source time in each T0 arrangement. The detection proxy is heuristic, not an aesthetic listening judgment.

No per-chunk foreground reassignment, competing-melody thinning, invented fill or excerpt ranking is used by the active builder. Canonical nine-voice mapping, D-Dorian/range/polyphony and retrigger cleanup remain. There are 181,635 intact score notes; 182,091 exported chunk entries include sustain ties crossing storage boundaries. Song edits span 81.2–238.2 seconds. Source-audit retained-time percentages vary, because some originals contain substantial non-driving material; this is not a claim of retaining every original MIDI event.

Catalog `ms3-song-12d32fcdc64c14ff` matches Surge bank `ms2-surge-ab9647db59ad7497`: 216 ordinary delivery chunks, eight fanfares and the existing ambient bridge, totaling 225 files and **59,316,556 bytes**. Largest file: **347,542 bytes**. Each arrangement was rendered as one complete performance before PCM slicing. Concatenated pre-encoding bodies reconstruct the whole performance hash exactly. The actual encoded files were decoded during rendering. Only the terminal song chunk contains the real terminal release; internal release pads are silent. Full-song patches, conditioning and timbres are unchanged.

Successful render run: **37035115023**, rendered candidate **63bb05855c275f6c2b8543af67d5c389b5ab9379**. The preliminary 96-MB allowance was not needed: final metadata/lock restore the original 60-MB ceiling without changing any audio bytes. Client PCM remains at 32 MiB. Do not infer native heap from tracked-buffer accounting.

## Player behavior

One ordinary composition plays in chronological order. Ordinary pressure and floor/stair changes are retained as next-song preferences, admitted near the full-song boundary. No unrelated two-floor song blend occurs during an ordinary crossing. Boss entry/exit, actual once-only victory, Off, staging changes and a new dungeon plan remain responsive exceptions. Maze T0 preference uses the driving T1 composition; staging and post-victory calm retain T0.

Source sample-frame periods govern chunk boundaries. Per-chunk RMS matching is disabled. A missing successor is retried after a resident repeat, not skipped; only successful starts advance chronology. File admission remains limited to catalog clips referenced by server-supplied matching plans, including a still-playing song whose floor/pressure preference changed. Logger announcements describe the block actually starting. Status includes `song.asset`, `song.part`, `song.completed` and `song.requested`.

## Focused evidence

The local music gate passed **48/48 checks** and parsed **909 Lua files**. Local focused gates passed: eleven source/rebuild/coverage/MIDI tests; sixteen actual catalog/native-loader/source-rebuild tests; eighteen plan/staging/native song-policy checks; song-first scheduler traversal across changing pressure/stairs on both backend policies; legacy composer, sample-clock ownership/memory and native-resource regressions; manual byte parity and reader tests.

Actual Chromium rolling-decode song traversal passed for a-t1, b-t2 and h-t0, including each complete composition followed by its first chunk again: **699.69 seconds**, **23 joins**, **26 actual decodes**. Maximum absolute sample error versus an independent assembled decoded reference: **2.994e-8**; tracked PCM peak: **33,483,960 bytes**, below 33,554,432. No per-chunk gain normalization was admitted. These are offline audio-thread and accounting results, not real-time GMod or subjective listening acceptance.

The final independent full-matrix/music/decode/browser receipts will be stored in `MS3_SONG_RECEIPT.json` only after the complete gates finish. No completed full-gate result is asserted here before that receipt exists.

## Remaining external and native boundaries

Direct access/search of the requested YouTube video yielded no usable content. No video-specific arrangement method is claimed. The approach preserves the actual source compositions rather than fabricating guidance. The live GDD write returned `FAILED_PRECONDITION`; its final intended amendment and discarded provisional budget are recorded in `MS3_SONG_GDD_AMENDMENT.md`. The manual and repository design documentation are updated.

Native gate: fully quit GMod, update/install the exact published main, start LoD on gm_flatgrass and enable Options → Music. Spend one complete song in ordinary maze play while crossing stairs and encountering changing danger. Listen for recognizable source development and preserved continuity, then hear staging/deployment, boss, genuine victory and Off/On. Inspect `lod_music_client_status` twice and retain `console_latest.txt` and `rpg_summary_latest.txt` if a defect persists. Native audibility, decoded heap, Steam Deck FPS and subjective song/edit quality remain pending. No Workshop or VPS deployment.

## Final independent validation

Actions run 37042487301 passed 302/302 integration suites with no source changes, 48/48 music checks, 909 Lua syntax files, all 225 real recording decodes, 240 real browser joins across 40 arrangements, and three complete browser song traversals plus wrap. Exact source fingerprints and all per-suite receipts are in MS3_SONG_RECEIPT.json. Only this result paragraph and the evidence receipt were added after the gates; no production code, score or audio changed. Native listening remains pending.
