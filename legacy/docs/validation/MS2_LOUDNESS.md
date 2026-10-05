# MS2 native phrase loudness repair

Parent: `b0f86dccedae3093355c239cd9608662b80cfd58`, verified remote main before editing. The author's fresh native report confirms music plays, but is barely audible. This resolves the prior unknown audibility outcome while establishing a level defect; broader native timing, timbre and performance acceptance is still open.

## Measurement and repair

The committed bank's median T0 decoded RMS is approximately −36.81 dBFS; multiplication by default player volume 0.55 gives −42.00 dBFS. Other role medians at that setting are approximately −35.7 to −36.7 dBFS. The decoded phrase peaks leave usable headroom. Garry's Mod's official `IGModAudioChannel:SetVolume` API supports amplification above 1, so a native master gain avoids resynthesis and changes to the almost-60-MB audio package.

The existing native playback seam now uses gain 4 (+12.04 dB), multiplied by the existing saved 0–1 preference. One common reduction caps the estimated score peak sum at 0.8 using each file's offline decoded peak. Count current phrases, release tails, floor crossfades and the unboosted ten-percent bridge. Apply eligible decreases before increases and bound every increase by remaining headroom, including native gains whose 30 Hz writes are not yet due. The guard preserves the floor blend and authored instrument dynamics without independent RMS normalization, sample analysis or DSP in gameplay. Resource ceilings and permissions are unchanged.

At default volume, modeled steady solo T0 median rises to −29.96 dBFS; other role medians rise to approximately −23.8 to −24.7 dBFS. The typical solo improvement is +12.04 dB; peaks and intentional overlaps can require a smaller boost. `MS2_LOUDNESS_LEVELS.json` records these projections. They are calculations from decoded metadata, not native mixer measurements or listening acceptance, and the ceiling bounds this score only.

## Regression and asset provenance

Before the gain change, the new production resource assertion failed: `quiet phrases receive a fourfold native boost at saved 55 percent volume`. It now confirms actual native gain 2.2 at preference 0.55 and 1.1 at preference 0.275. A native-volume-write observer checks the estimated summed peak after every write, including paced stale gains, role tails, stair reversals and bridge gaps. Loud equal and unequal stair lanes retain a common reduction and their square-root ratio. The existing 15 native stall cases, eight-channel/two-open/32-MiB budgets, cleanup, fixed retry and Options regressions remain in the required gate. Missing or unsafe clip/bridge peaks are rejected before playback.

`render.lua` now projects the existing `decodedPeak` measurements into runtime metadata. The producer changed only that projection; the complete bank manifest differs from the parent only in its whole-source renderer hash (`d29e5c861152fc91a2a60a09dfb9b6df0cbd9121cedc44c6e8a1f3345f7cc1fd`). This records current producer source, not a claim of fresh full-bank synthesis. A fresh one-phrase Surge render (`a_boss_010`) reproduces its committed PCM SHA256 and peak/RMS/DC metrics exactly; its encoded file still matches the prior manifest. All encoded hashes, source notes, patches, bank revision `ms2-surge-0f7591eb682f3b2b`, 1,403 files and 59,993,192 bytes remain identical. The complete actual decode gate independently checks every decoded peak used by the guard.

Live GDD 00 → 01 → 06/07 was read. The explicit author brief authorizes music tuning/documentation. The trusted read detected no protected controls at the insertion scope; Google returned `FAILED_PRECONDITION`. The live GDD was not changed. `MS2_LOUDNESS_GDD_AMENDMENTS.json` preserves the exact request and error.

## Finite gate and native boundary

Required receipts: `MS2_LOUDNESS_CHECKS.json`, `MS2_LOUDNESS_INTEGRATION.json` and `MS2_LOUDNESS_AUDIO.json`. Run `python3 tools/test_music_gate.py --output <empty-directory> --workers 4`, `python3 tools/test_checkpoint_g_integration.py --output <empty-directory> --workers 4` and `node tools/test_music_audio.js`. These establish production regression and actual asset-decode evidence; they do not prove installed Source mixer loudness.

Fresh results: **43/43 music suites**, **297/297 canonical integration suites**, **883 Lua syntax checks** and **1,403/1,403 actual audio decodes** pass. Both gate receipts have identical before/after source snapshots and no changes during execution. The focused resource suite passes 1,759 assertions, including the native-write headroom observer; bundle startup/admission passes 82. Only evidence files were added or amended after those gates.

Fully quit GMod, update/install exact published main, enable **Player Menu → Options → Music**, then listen in staging, danger and a stair crossing at the current volume setting. Confirm useful loudness, coherent balance and no distortion; lower the slider to confirm control. If a defect remains, preserve `lod_music_client_status` verbatim plus canonical `console_latest.txt` and `rpg_summary_latest.txt`. Loudness/balance, broader musical timing, co-op and Steam Deck performance remain pending human acceptance. Workshop and VPS are untouched.
