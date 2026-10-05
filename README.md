# MS3 Music Player

The Legend of Deborah's complete Music System 3 bank, extracted as a portable
browser/WebView player and reusable JavaScript module. No Garry's Mod, server,
streaming subscription or live synthesizer is needed for playback.

## Run the player

From this folder, run `python3 -m http.server 8080 --bind 127.0.0.1`, then open
<http://localhost:8080>. Press **Play**. Use **− / +** for tension 1–4, choose a
bank A–H, or select **Boss** or **Fanfare**. Stop releases all audio and reads.
Fanfare plays once, then returns to the selected tension. Volume is independent.
Browser audio starts through the Play gesture; opening the HTML directly as a
`file://` URL does not supply the fetchable bank. No npm install is required.

## Embed in a new project

Copy `src/` and `bank/` to any HTTP-served browser, Electron or WebView project.
Serve JavaScript with its normal JavaScript MIME type and Ogg files as audio.

```js
import {MS3Player} from './src/player.js';
const music = await MS3Player.load({bankURL: new URL('./bank/', import.meta.url)});
// Call from a click/tap handler:
await music.play();
music.setTension(3); // 1 = Chill, 2 = Attention, 3 = Pressure, 4 = High tension
music.tensionUp();
music.tensionDown();
music.setBlock('c');
music.boss();
music.fanfare();
music.setVolume(.8);
music.stop();
```

The player extends `EventTarget`: `change`, `play`, `stop`, `status`, `warning`,
`error`, `block` and `victory` events expose their payload in `event.detail`.
`status()` supplies the requested role and actual heard asset/clip separately.
`destroy()` releases audio, timers, HTTP requests and the context.

## Transition behavior

MS3's audio-clock transport schedules prepared recordings on musical boundaries,
retains resident loops until a successor decodes, and preserves release tails.
Each arrangement follows its source-ordered song. Unlike Deborah's song-first
game policy, manual tension and bank changes request the next safe boundary
instead of waiting for the complete song. Most switches take a few seconds;
delayed reads retain the audible passage. Different tension arrangements contain
different compositions; musical boundary alignment does not guarantee identical
melodic material between them. The transport admits at most 32 MiB of decoded
PCM, four cached clips, two loads and eight voices at 44.1 kHz. Assets are served
locally by default. Browser/WebView hosts must support Web Audio and Ogg Vorbis;
other engines need an adapter to their native audio APIs.

## Preserved source and provenance

`bank/audio/` contains all **224 original Ogg clips plus the bridge**, unchanged
by byte hash. Eight banks supply **48 arrangements**: 40 complete ordered song
edits and eight one-shot fanfares. `bank/catalog.json` adds only recording metadata
and portable paths to the original arrangement catalog.

`legacy/` preserves the original MIDI library, compiled note shards, Lua
integration, synthesis tools, patch/binding definitions, tests, manifests and
historical validation. `preservation.json` records every original path, SHA-256
and relocation from Deborah commit `d252a7acf2f64919ff6dd6457f5ca4f9c24db94f`.
To run an original builder or validator, reconstruct that original layout in a
temporary directory: copy `legacy/` there, then copy `bank/audio/` to
`gamemodes/legend_of_deborah/content/sound/lod/ms2_surge/`. Consult the archived
renderer README for pinned synthesis dependencies and upstream license notices.
The extracted browser engine changes its module export wrapper and guards the optional game song-completion policy; its DSP-free
transport is the preserved production implementation.

This extraction grants no new license to source compositions or recordings.
They retain their existing rights and the author's stated provenance. Surge is
an offline renderer under its upstream GPL-3.0 terms; its binaries are not shipped
or required by the player. The legacy renderer documentation and lock preserve
its attribution and rebuild information.

## Verify

`npm test` verifies exact preservation hashes, all recorded bank hashes, manual
control/lifecycle behavior and the original transport regression suite.
`node tests/browser.cjs` additionally exercises real browser playback, all-role
switches, fanfare return, lifecycle and bank decoding (requires Playwright and
its Chromium installation). Native game listening is a separate acceptance
step; no claim of an undetectable melodic transition is made by source tests.
