# MS3 native bridge and long-song recovery

Parent: `2c4d2df97fb274478daae1e35bec8e609cd23267`. The author verified that
GitHub, Workshop item 3791535712 and the public VPS contained this revision.
Native reports now show server/client authorization enabled and renderer ready,
but audio was sporadic in staging and the dungeon, then resumed on the same
build. This is failed continuity evidence, not completed native acceptance.

The reported sample-clock failure was `MS3 local audio decode timed out`, followed
by `surge-rendered` fallback. Its first staging channel was stopped (`state=0`)
at exactly its 30.088458049886622-second file end. Historical `started=true`
and estimated gain did not establish currently audible playback.

## Reproduced boundaries

- The production local-audio bridge interpolated default RFC 2045 Base64 into a
  JavaScript string. [GMod's default encoder inserts line breaks](https://wiki.facepunch.com/gmod/util.Base64Encode),
  producing invalid JavaScript before the decode callback. Inline encoding fixes
  this boundary without changing audio bytes, decoder budgets or the renderer.
- A 200 ms frame hitch past a native 64-beat boundary missed resident renewal.
  The scheduler correctly retained song order, but its next whole-chunk retry
  was 29.34 seconds away. The existing resident now rejoins its current phase
  even after missed frames/EOF; one-shots, Off, stale preparation rejection,
  future boundaries, channel limits and PCM limits remain unchanged.
- Server status exceeded Source's TextMsg limit and retained stale MS2 labels.
  Bounded UTF-8-safe diagnostic pieces preserve the existing operator check;
  current backend labels and actual authorization/native-playing fields remove
  misleading readiness-only diagnostics.

These were existing startup/fallback defects exposed once authorization worked;
the authorization commit did not change synthesis, arrangement or scheduling.

`test_ms3_audio_bridge.py` executes the real Lua callback, native-compatible
Base64 encoding, JavaScript parsing and exact comparison of two committed audio
files, including the largest. It also checks unauthorized, invalid, missing,
oversized, stale and rate-limited requests. `test_music_native_hitch.lua` models
real EOF, 200 ms/800 ms/multi-period stalls and phase-aligned successor recovery.
Both belong to the complete music and canonical integration gates. Existing
server/client boundary tests cover truthful, bounded diagnostics.

After verified source publication, repeat Workshop then matching VPS deployment.
Fully restart/update the client and listen through several chunks in staging,
portal entry and dungeon traversal, plus Off/On and reconnect. Retain two client
status lines a second apart if a gap recurs. Native sound, continuity and Steam
Deck performance remain evidence-dependent; headless passes do not accept them.
