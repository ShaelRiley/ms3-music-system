import MS3Engine from './ms3-engine.js';

const roles = ['T0', 'T1', 'T2', 'T3'];
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

/** Browser/WebView adapter. No game, DOM, backend service or synthesis dependency. */
export class MS3Player extends EventTarget {
  constructor(catalog, {bankURL, volume = .8, contextFactory, fetcher = fetch} = {}) {
    super();
    this.catalog = catalog;
    this.bankURL = new URL(bankURL || '../bank/', import.meta.url);
    this.fetcher = fetcher;
    this.contextFactory = contextFactory || (() => new AudioContext({sampleRate: 44100}));
    this.block = catalog.defaultBlock;
    this.tension = 1;
    this.role = 'T0';
    this.volume = clamp(volume, 0, 1);
    this.requests = new Map();
    this.generation = 0;
  }

  static async load({bankURL = new URL('../bank/', import.meta.url), ...options} = {}) {
    const base = new URL(bankURL, import.meta.url);
    const response = await (options.fetcher || fetch)(new URL('catalog.json', base));
    if (!response.ok) throw Error(`Cannot load music catalog: HTTP ${response.status}`);
    const catalog = await response.json();
    if (!catalog.blocks?.[catalog.defaultBlock] || !catalog.assets || catalog.bpm !== 130)
      throw Error('Unsupported MS3 catalog');
    return new MS3Player(catalog, {...options, bankURL: base});
  }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, {detail})); }
  resolve() {
    const block = this.catalog.blocks[this.block];
    const fallback = this.catalog.blocks[this.catalog.defaultBlock];
    const id = block.roles[this.role] || fallback.roles[this.role];
    const asset = this.catalog.assets[id];
    if (!asset) throw Error(`Missing arrangement: ${this.role}`);
    return asset;
  }

  async play() {
    if (this.starting) return this.starting;
    if (this.context) { await this.context.resume(); return; }
    const generation = ++this.generation;
    this.starting = (async () => {
      const context = this.context = this.contextFactory();
      try {
        await context.resume();
        if (generation !== this.generation) return;
        if (context.state !== 'running') throw Error('Audio is suspended; press Play to resume');
        if (context.sampleRate > 44100) throw Error('A 44.1 kHz audio context is required');
        const engine = MS3Engine;
        if (!engine) throw Error('MS3 engine is unavailable');
        this.transport = new engine.AudioTransport(context,
          (_, clip) => this.readClip(clip, generation),
          (token, played) => this.scheduler.result(token, played));
        this.scheduler = new engine.Scheduler(this.catalog.bpm, this.transport,
          () => context.currentTime,
          (name, value) => {
            if (name === 'victory') { this.role = roles[this.tension - 1]; this.update(); }
            this.emit(name, value);
          });
        this.update();
        this.interval = setInterval(() => {
          try { this.transport.tick(); this.scheduler.pump(); this.emit('status', this.status()); }
          catch (error) { this.fail(error); }
        }, 25);
        this.emit('play', this.status());
      } catch (error) { if (generation === this.generation) { this.stop(); throw error; } }
    })();
    try { await this.starting; } finally { this.starting = null; }
  }

  update() {
    if (!this.scheduler) return;
    const asset = this.resolve();
    this.scheduler.install(asset);
    this.transport.install(asset);
    // Assets retain source-ordered songs. Manual control changes the requested
    // role at the next safe beat boundary instead of waiting for an entire song.
    this.scheduler.update({role: this.role, staged: this.role === 'T0',
      seed: 'standalone', volume: this.volume, bpm: this.catalog.bpm,
      targets: [{lane: 'player', block: this.block, asset: asset.id, weight: 1}]});
    // Retain metadata for the resident source until any pending read finishes.
    for (const id of Object.keys(this.transport.assets)) {
      if (id !== asset.id && !Object.values(this.transport.loads).some(l => l.info.asset.id === id))
        delete this.transport.assets[id];
    }
    this.emit('change', this.status());
  }

  setTension(level) {
    if (!Number.isFinite(level)) throw TypeError('Tension must be finite');
    this.tension = clamp(Math.round(level), 1, 4);
    this.role = roles[this.tension - 1]; this.update();
  }
  tensionUp() { this.setTension(this.tension + 1); }
  tensionDown() { this.setTension(this.tension - 1); }
  setBlock(block) {
    if (!this.catalog.blocks[block]) throw Error(`Unknown bank: ${block}`);
    this.block = block; this.update();
  }
  setVolume(volume) {
    if (!Number.isFinite(volume)) throw TypeError('Volume must be finite');
    this.volume = clamp(volume, 0, 1);
    if (this.transport) this.transport.volume(this.volume);
    this.emit('change', this.status());
  }
  boss() { this.role = 'BOSS'; this.update(); }
  fanfare() { this.role = 'VICTORY'; this.update(); }

  async readClip(clip, generation) {
    if (this.requests.has(clip)) return;
    const row = Object.values(this.catalog.assets).flatMap(a => a.clips).find(c => c.id === clip);
    if (!row || !/^audio\/[a-z0-9_-]+\.ogg$/.test(row.path)) { this.fail(Error('Unsafe or missing clip')); return; }
    const controller = new AbortController(); this.requests.set(clip, controller);
    const timeout = setTimeout(() => controller.abort(), 2800);
    try {
      const response = await this.fetcher(new URL(row.path, this.bankURL), {signal: controller.signal});
      if (!response.ok) throw Error(`Cannot read ${clip}: HTTP ${response.status}`);
      const raw = new Uint8Array(await response.arrayBuffer());
      if (raw.length > 1_000_000 || !raw.length) throw Error('Clip byte limit exceeded');
      if (generation !== this.generation || !this.transport) return;
      let binary = '';
      for (let i = 0; i < raw.length; i += 8192) binary += String.fromCharCode(...raw.subarray(i, i + 8192));
      this.transport.receive(clip, btoa(binary));
    } catch (error) {
      if (generation === this.generation) {
        // A failed successor never silences the resident loop. Release its
        // admission reservation so a later musical boundary can retry.
        const transport = this.transport, load = transport?.loads[clip];
        if (load) { transport.reserved -= load.bytes; delete transport.loads[clip]; transport.failClip(clip); }
        this.emit('warning', String(error));
      }
    } finally {
      clearTimeout(timeout);
      if (this.requests.get(clip) === controller) this.requests.delete(clip);
    }
  }

  status() {
    const lane = this.scheduler?.lanes.player;
    return {playing: !!this.scheduler, block: this.block, tension: this.tension,
      role: this.role, volume: this.volume, currentAsset: lane?.playedAsset,
      currentClip: lane?.heardChoice?.id, audio: this.transport?.stats()};
  }
  fail(error) { this.stop(); this.emit('error', String(error)); }
  stop() {
    this.generation++;
    clearInterval(this.interval); this.interval = null;
    for (const request of this.requests.values()) request.abort();
    this.requests.clear();
    if (this.scheduler) this.scheduler.stop();
    this.scheduler = null; this.transport = null;
    const context = this.context; this.context = null;
    if (context) context.close().catch(() => {});
    this.emit('stop', this.status());
  }
  destroy() { this.stop(); }
}
