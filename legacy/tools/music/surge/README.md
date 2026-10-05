# LoD offline Surge toolchain

Surge XT is an **external offline synthesis tool**. The addon contains rendered LoD audio and LoD code/data. It neither links nor loads Surge, and players need no synth installation. No factory presets or factory sample/wavetable content is used.

Pinned upstream: [surge-synthesizer/surge](https://github.com/surge-synthesizer/surge), stable tag `release_xt_1.3.4`, exact source commit `f7b97c682ade0b87da85ca5968b63d5c7c98e68d`. Surge XT is GPL-3.0-or-later; [upstream license](https://github.com/surge-synthesizer/surge/blob/f7b97c682ade0b87da85ca5968b63d5c7c98e68d/LICENSE) and [complete pinned source](https://github.com/surge-synthesizer/surge/tree/f7b97c682ade0b87da85ca5968b63d5c7c98e68d) provide attribution/source availability. This describes the implementation boundary, without making a legal claim about generated audio.

`lock.json` pins the source, binding patch hash, sample rate, renderer revision, release allowance, Vorbis quality and package thresholds. `patches.json` is the project-owned **Freight Workstation** parameter bank: explicit native-unit values, named control-group paths, ten physical patches/nine logical voices, modulation routes and gain staging. `bank.py` resolves those paths through `getPatch()` and validates parameter ranges; it uses no undocumented numerical offsets.

`surgepy_lod.patch` supplies small offline host glue: seeded RNGs, zeroed raw backing storage before C++ construction (so heap reuse cannot affect inactive voice state), fixed transport, no factory loading, modulation-state refresh, and explicit parameter activation. It changes no DSP algorithm. Surge's detached-tag build reports `1.3.HEAD.f7b97c6`; the recorded exact commit is the stable 1.3.4 source. Custom filter activation is essential: an unhosted init patch otherwise leaves its filter deactivated even when its type changes.

## Regenerate

Use Linux with a C++17 compiler, Git, CMake, Python development headers, ffmpeg with libvorbis, numpy and scipy. Python 3.12/GCC 13.3 were used for this checkpoint. Keep the external source and binaries outside the game repository. `prepare.py` builds just the Python binding/core DSP, excluding plugins, GUI, Lua and MTS integration.

```bash
python3 -m pip install numpy scipy cmake
python3 tools/music/surge/prepare.py --source /tmp/lod-surge-source --build /tmp/lod-surge-build --jobs 4
python3 tools/music/build_ms2_surge.py --surge-module /tmp/lod-surge-build/src/surge-python --jobs 4
python3 tools/test_ms2_surge_bank.py --decode
```

A relocated Python may need `prepare.py --python-library /actual/path/libpython3.12.so.1.0`. The helper also checks common runtime-relative library locations. Source/submodule revisions must match the upstream pin. The sole permitted tracked external edit is the locked binding patch.

The builder reads all existing compiled catalog/note shards, validates 1,402 clips/170,860 notes, renders fresh seeded synth instances, and checks isolated voice audibility/repeatability in forward and reverse order. Acid additionally requires held-note spectral-centroid movement. Every final file is actually decoded and checked for finite data, silence, clipping and duration. Fixed gains retain source dynamics; mastering never normalizes individual clips.

Intermediate stereo PCM WAV/cache receipts stay in ignored `build/ms2-surge/`. Cache keys include renderer, patch, binding and source-note hashes; PCM hashes detect changed intermediates. Final Ogg serial IDs/checksums are canonicalized to remove muxer entropy. Byte-for-byte regeneration requires the recorded platform, ffmpeg/libvorbis and numerical toolchain; other compiler/library versions can legitimately change float/encoding output and must produce a newly validated manifest. The bank records the actual encoder/version and source hashes.

Outputs are 1,402 runtime phrases plus one quiet bridge, `lod/ms2/render.lua`, `docs/MS2_SURGE_BANK.json`, and a compact audition/cue sheet in `docs/validation/`. `--limit 12` is a smoke render only and deliberately does not publish runtime metadata. The full render rejects missing clips, unsafe levels, malformed durations and a bank exceeding the selected 60,000,000-byte budget. 100,000,000 bytes is a separate design-review boundary.

Normal CI checks the **committed** assets, hashes, actual Ogg identification/granule durations, provenance and scheduler/lifecycle. It does not install or compile Surge. Rebuilding the curated MIDI source library is a separate authoring operation, unnecessary for timbre regeneration.
