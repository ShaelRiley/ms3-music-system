# MS2 Surge playback recovery

Parent: `795001f1fa27dc9c99a5d79ae845ed78a2a7a0da`, verified remote main before editing. The author reports no audible music. The supplied command was initially mistyped as `clod_music_client_status`; its unknown-command response does not diagnose playback. The interrupted discussion's later native diagnostic was not available for this repair. Do not infer its initial engine error.

## Reproduced defects and repair

After a renderer starts, `ReadyDeadline` survives readiness and teardown. A native failure after that deadline destroys the panel and sets a ten-second retry. The next 0.2-second pass sees the expired deadline even without a panel, replaces the native error with a startup error, and moves the retry ten seconds ahead again. Repeated passes prevent recovery indefinitely.

Readiness and teardown now clear the startup deadline. Timeout checking additionally requires a live initializing panel. Successful startup clears the previous backoff. Audio-open, duration and exception failures preserve the first native cause; the eight-second bridge-gap cap does not overwrite it. Duration mismatches report expected and actual length. `lod_music_client_status` adds `retryIn` and `startupPending`.

Before the production changes, the new `test_music_client.lua` case failed with `backoff does not slide or overwrite the native failure`, and the new `test_music_resources.lua` case failed with `gap timeout preserves the first native audio error`. Both returned exit code 1. They pass after the repair. The client regression also starts a fresh native phrase after backoff, tests a genuine unready-panel timeout, retries it, and checks Off/On after the old deadline. Resource tests retain the 15 native stall cases, eight-channel/two-open/32-MiB ceilings and bounded bridge behavior.

The live GDD 00 → 01 → 06/07 route was read. Existing MusicDirector/UI/lifecycle/resource rules and the explicit Surge brief govern this correction. No new design amendment is required. The previous Surge amendment remains authorized but unapplied.

## Automated evidence and native boundary

Receipts: `MS2_SURGE_RECOVERY_CHECKS.json`, `MS2_SURGE_RECOVERY_INTEGRATION.json` and `MS2_SURGE_RECOVERY_AUDIO.json`. Required checks are `python3 tools/test_music_gate.py --output <empty-directory>`, `python3 tools/test_checkpoint_g_integration.py --output <empty-directory>` and `node tools/test_music_audio.js`. The catalog, composer, rendered assets and server MusicDirector are unchanged.

These reproduce and resolve the retry/error-masking defects through production modules. They do not establish the cause of the first native failure or prove Garry's Mod audibility. Native acceptance remains pending. Fully quit GMod, update/install the exact published source, start LoD on `gm_flatgrass`, enable **Player Menu → Options → Music** and listen in staging. If silent, capture `lod_music_client_status` verbatim and preserve canonical `console_latest.txt` plus `rpg_summary_latest.txt`; the status now retains the original native cause during the fixed backoff.

Workshop and VPS are untouched.
