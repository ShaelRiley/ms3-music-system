# MS2 complete-bank JSON admission repair

Implementation parent: `6abd1e2786a075888d27d6f510a3d48226f18353`, canonical `ShaelRiley/the-legend-of-deborah/main`.

The author reports continuing silence after the previous catalog-path repair and confirms that the Options change is visible. This is failed native playback evidence. The previous small catalog fixture and offline synthesizer results did not prove that GMod admits the shipped bank.

GMod's documented [util.JSONToTable](https://wiki.facepunch.com/gmod/util.JSONToTable) signature has `ignoreLimits` as its second argument. By default, decoding is limited to 15,000 total keys and returns nil on failure. Counting the actual shipped JSON reveals:

| Bundled data | Keys | Default native admission |
| --- | ---: | --- |
| Runtime catalog | 41,125 | Rejected |
| 62 of 63 note pages | 15,757–16,988 | Rejected |
| Final note page | Below 15,000 | Admitted |

The catalog fails on both server and client, and fixing that alone leaves almost every note page rejected. The production shared catalog loader and client note-page loader now pass `true` for `ignoreLimits` only after admitting a whitelisted, local bundled file within the existing byte cap. Catalog schema/graph validation, per-note validation, eight-page/four-arrangement cache limits and ordinary network/native callback decoding limits remain unchanged. Decode failures now name the catalog or note page instead of leaving the page failure without a diagnostic.

`tools/test_ms2_catalog.py` now counts and supplies every actual JSON file to the production Lua server/client paths through the engine-boundary fixture. The decoder double models the documented native key limit. It establishes that default decoding rejects the catalog and 62 note pages; the repaired path admits all 48 arrangements, 1,402 phrases and 170,860 notes, synchronizes an actual staging arrangement and respects cache bounds. The actual wire plan fits the unchanged decoder limit. The common music fixture also models the limit for existing network tests.

Reproduction before changing production: the new test fails at `invalid MS2 catalog`. With only the shared catalog fix, it fails at `real phrase data reaches playback`. With both bundled decodes repaired, it passes. The test belongs to the existing permanent `ms2_catalog` gate suite and does not depend on a small substitute score.

Final local result: **42/42 selected suites**, **881 Lua syntax checks**, complete-bank admission and actual offline Web Audio passed, with no source changes during the gate. [The complete receipt](MS2_JSON_CHECKS.json) preserves commands and log hashes. The gate includes MIDI recompilation and directly affected music/gameplay/lifecycle regressions; `MS2_CHROMIUM` enabled the production audio renderer. These results model loading and render audio outside GMod; the renderer-ready callback in the Lua fixture is simulated. They do not establish fresh native audibility.

Fully quit GMod, update/install main, launch LoD on gm_flatgrass, enable `lod_music_enabled 1; lod_music 1` and listen in staging/gameplay. If silence persists, run `lod_music_status; lod_music_client_status` and preserve the session's canonical `console_latest.txt` plus `rpg_summary_latest.txt`.
