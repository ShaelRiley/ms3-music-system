# MS2 loading repair

Implementation parent: `bc3cf1967ebdc77e98c5fc028ef6337c9e7139fe`, canonical `ShaelRiley/the-legend-of-deborah/main`.

The author reported no in-game music and an engine error including `lod\\ms2\\catalog.lua` from `sh_music.lua` line 53, called by `sv_music.lua` during `init.lua` startup. This is contradictory native evidence; the earlier 41/41 source/offline-audio result never established native acceptance. The shipped catalog is nonempty (369,983 bytes); all 66 score Lua files are present.

GMod [include documentation](https://wiki.facepunch.com/gmod/Global.include) requires a current-file-relative path or a full gamemode virtual path. The original test fixture treated every include as relative to the gamemode root and hid the nested-path defect. The fixture now models the nested music folder and rootless callbacks. Running the new regression against the original loader fails at catalog admission. After repair, `test_music_bundle.lua` checks server startup, the actual client engine, note/state delivery, all real score files, missing-mount diagnostics and recovery.

The shared loader now admits only catalog/engine/registry/numbered-note filenames, resolves `legend_of_deborah/gamemode/lod/ms2/`, and checks the server's mounted LUA file before include. Client availability is owned by include so server-delivered Lua does not depend on a loose local file. The regression models that client boundary. Server client-file distribution uses the same explicit virtual location. Client page/engine failures preserve the precise diagnostic. The catalog, synthesizer and authored note data are unchanged. At the author's direction, the Options music description is static and the outdated server-disabled message is removed.

Final local result: 42/42 selected suites, 881 Lua syntax checks, production audio rendering passed, and source unchanged during the gate. The bundle regression reports 75 checks, including a client with no loose Lua catalog file. [Complete receipt](MS2_LOADING_CHECKS.json) preserves the commands and log hashes.

Finite validation: `python3 tools/test_music_gate.py --output <empty directory outside the source tree>`; optional `MS2_CHROMIUM` enables actual offline audio. The new bundle regression belongs to the permanent gate. Native GMod audibility remains unobserved after repair. Fully quit/update/install, then launch LoD on gm_flatgrass and enable `lod_music_enabled 1; lod_music 1`. If the defect persists, preserve the canonical console_latest.txt and rpg_summary_latest.txt.
