import {MS3Player} from './src/player.js';
const $ = id => document.getElementById(id);
const names = {T0:'Chill',T1:'Attention',T2:'Pressure',T3:'High tension',BOSS:'Boss',VICTORY:'Fanfare'};
try {
  const player = await MS3Player.load();
  // Exposed for embedding examples and diagnostics, not required by the UI.
  window.ms3Player = player;
  for (const [id, bank] of Object.entries(player.catalog.blocks)) {
    const option = document.createElement('option'); option.value = id; option.textContent = bank.title; $('bank').append(option);
  }
  $('bank').value = player.block;
  for (const id of ['play','boss','fanfare','bank','up','down']) $(id).disabled = false;
  function render() {
    const state = player.status();
    $('tension').textContent = `Tension ${state.tension}`; $('role').textContent = names[state.role];
    $('up').disabled = state.tension === 4 && state.role === 'T3'; $('down').disabled = state.tension === 1 && state.role === 'T0';
    $('play').disabled = state.playing; $('stop').disabled = !state.playing;
    $('details').textContent = JSON.stringify(state, null, 2);
    $('status').textContent = state.playing ? (state.currentClip ? `Playing ${state.currentClip} · Requested ${names[state.role]}` : 'Preparing the first passage…') : 'Ready. Press Play to start.';
  }
  for (const name of ['change','status','play','stop']) player.addEventListener(name,render);
  for (const name of ['error','warning']) player.addEventListener(name,e => {$('status').textContent=e.detail;});
  $('play').onclick = async () => { $('play').disabled=true; try {await player.play();}catch(error){render();$('status').textContent=error.message;} };
  $('stop').onclick = () => player.stop(); $('up').onclick=()=>player.tensionUp(); $('down').onclick=()=>player.tensionDown();
  $('boss').onclick=()=>player.boss(); $('fanfare').onclick=()=>player.fanfare();
  $('bank').onchange=()=>player.setBlock($('bank').value); $('volume').oninput=()=>player.setVolume(Number($('volume').value));
  window.addEventListener('pagehide',()=>player.destroy()); render();
} catch(error) { $('status').textContent=`Could not load music: ${error.message}`; }
