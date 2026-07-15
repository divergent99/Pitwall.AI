const $ = (id) => document.getElementById(id);
let simulation = null;
let uncertainty = null;
let previousRun = null;
let seasonData = null;
let strategyRounds = null;
let validationData = null;
let blindChallenge = null;
let voiceEnabled = true;
let replayFrame = null;
let simulationRequest = 0;
const colors = ['#c8ff35', '#54d7e8', '#ff6b35'];
const circuitRows = [
  ['melbourne','Australia · Melbourne',1,58,22.0,18,38,'MED DEG · BALANCED UNDERCUT'],['shanghai','China · Shanghai',2,56,23.0,18,38,'MED-HIGH DEG · STRONG UNDERCUT'],['suzuka','Japan · Suzuka',3,53,22.5,18,36,'HIGH LOAD · HIGH TYRE STRESS'],
  ['sakhir','Bahrain · Sakhir',4,57,23.5,18,39,'HIGH DEG · STRONG UNDERCUT'],['jeddah','Saudi Arabia · Jeddah',5,50,20.0,17,35,'LOW DEG · HIGH SPEED'],['miami','Miami',6,57,21.5,18,38,'MED DEG · TRACK EVOLUTION'],
  ['montreal','Canada · Montreal',7,70,19.5,22,46,'MED DEG · BRAKING LIMITED'],['monaco','Monaco',8,78,19.0,24,52,'LOW DEG · TRACK POSITION'],['barcelona','Barcelona-Catalunya',9,66,22.0,20,44,'HIGH DEG · STRONG UNDERCUT'],
  ['spielberg','Austria · Spielberg',10,71,20.0,22,47,'MED DEG · SHORT LAP'],['silverstone','Great Britain · Silverstone',11,52,21.5,18,34,'HIGH TYRE STRESS · WEATHER RISK'],['spa','Belgium · Spa-Francorchamps',12,44,23.5,15,30,'HIGH LOAD · WEATHER RISK'],
  ['budapest','Hungary · Budapest',13,70,21.0,21,46,'HIGH DEG · STRONG UNDERCUT'],['zandvoort','Netherlands · Zandvoort',14,72,20.5,22,48,'HIGH LOAD · NARROW WINDOW'],['monza','Italy · Monza',15,53,24.3,18,40,'LOW DEG · WEAK UNDERCUT'],
  ['madrid','Madrid',16,57,22.0,18,39,'ESTIMATED PROFILE · NEW CIRCUIT'],['baku','Azerbaijan · Baku',17,51,20.5,17,35,'LOW DEG · MAX DEPLOYMENT'],['marina-bay','Singapore · Marina Bay',18,62,20.5,18,38,'HIGH DEG · STRONG UNDERCUT'],
  ['austin','United States · Austin',19,56,20.5,18,38,'HIGH DEG · MIXED LOAD'],['mexico-city','Mexico · Mexico City',20,71,21.0,22,47,'MED DEG · HIGH ALTITUDE'],['sao-paulo','Brazil · São Paulo',21,71,20.0,22,46,'MED-HIGH DEG · WEATHER RISK'],
  ['las-vegas','Las Vegas',22,50,21.0,17,35,'LOW DEG · LOW GRIP'],['lusail','Qatar · Lusail',23,57,22.5,18,39,'VERY HIGH TYRE STRESS'],['yas-marina','Abu Dhabi · Yas Marina',24,58,22.0,18,39,'MED DEG · BALANCED UNDERCUT']
];
const circuits=Object.fromEntries(circuitRows.map(([id,name,round,laps,pitLoss,current,rain,profile])=>[id,{name,race:`Round ${String(round).padStart(2,'0')}`,round,laps,pitLoss,current,rain,profile:`${profile} · ${pitLoss.toFixed(1)}s PIT LOSS`,credit:`${name.toUpperCase()} · ACCURATE LAYOUT VECTOR © JULES ROY / F1DB · CC BY 4.0`} ]));

function populateCircuitSelect(){
  const select=$('circuitSelect'),selected=select.value;
  select.innerHTML=circuitRows.map(([id,name,round])=>`<option value="${id}" ${id===selected?'selected':''}>R${String(round).padStart(2,'0')} · ${name}</option>`).join('');
}

function initTrackGeometry() {
  const path=window.PITWALL_TRACKS?.[$('circuitSelect').value] || window.PITWALL_TRACK_PATH;
  ['trackPath','stageTrackPath'].forEach(id => $(id).setAttribute('d', path));
  const miniStart=$('trackPath').getPointAtLength(0), stageStart=$('stageTrackPath').getPointAtLength(0);
  $('replayCar').setAttribute('cx',miniStart.x); $('replayCar').setAttribute('cy',miniStart.y);
  $('stageCar').setAttribute('cx',stageStart.x); $('stageCar').setAttribute('cy',stageStart.y);
}

function scenario() {
  const total = Number($('totalLaps').value);
  const current = Math.min(Number($('currentLap').value), total - 1);
  return {
    circuit: $('circuitSelect').value,
    total_laps: total, current_lap: current, compound: $('compound').value,
    position: Number($('racePosition').value), track_temperature:Number($('trackTemperature').value),
    tyre_age: Number($('tyreAge').value), weather: 'DRY',
    rain_lap: $('rainEnabled').checked ? Math.max(current + 1, Number($('rainLap').value)) : null,
    safety_car_lap: $('safetyCar').value ? Number($('safetyCar').value) : null,
    gap_ahead: Number($('gapAheadInput').value), gap_behind: Number($('gapBehindInput').value), pit_loss: circuits[$('circuitSelect').value].pitLoss
  };
}

function tyre(compound) {
  return `<span class="tyre ${compound.toLowerCase()}">${compound[0]}</span>`;
}

function renderCards(data) {
  $('strategyCards').innerHTML = data.strategies.map((s, i) => `
    <article class="strategy-card ${s.id === data.recommendation ? 'best' : ''}" data-id="${s.id}">
      ${s.id === data.recommendation ? '<span class="best-tag">RECOMMENDED</span>' : ''}
      <small>PLAN 0${i + 1} · ${s.risk} RISK</small><h3>${s.name}</h3><p>${s.summary}</p>
      <div class="delta ${s.delta ? 'positive' : ''}">${s.delta ? '+' + s.delta.toFixed(1) + 's' : 'FASTEST'}</div>
      <div class="compound-row">${s.compounds.map((c, n) => `${n ? '<i></i>' : ''}${tyre(c)}`).join('')}</div>
    </article>`).join('');
}

function linePath(points, width, height, min, max) {
  return points.map((p, i) => {
    const x = 35 + (i / Math.max(points.length - 1, 1)) * (width - 55);
    const y = 12 + ((p.cumulative - min) / Math.max(max - min, 1)) * (height - 38);
    return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

function renderChart(data) {
  const svg = $('strategyChart');
  const w = 760, h = 220;
  const baseline = data.strategies[0].laps;
  const traces = data.strategies.map(s => s.laps.map((l,i) => ({...l, cumulative: Math.max(0, l.cumulative - baseline[i].cumulative)})));
  const values = traces.flatMap(points => points.map(l => l.cumulative));
  const min = 0, max = Math.max(...values, 1);
  let html = '';
  for (let i = 0; i < 5; i++) {
    const y = 15 + i * 43;
    html += `<line class="gridline" x1="35" y1="${y}" x2="745" y2="${y}"/><text class="axis-label" x="0" y="${y + 3}">${i ? '+' + ((max-min)*i/4).toFixed(1) : '0'}s</text>`;
  }
  data.strategies.forEach((s, i) => {
    const d = linePath(traces[i], w, h, min, max);
    html += `<path class="strategy-line" d="${d}" stroke="${colors[i]}"/>`;
    (i === 0 ? s.laps.filter(l => l.event) : []).forEach(l => {
      const idx = s.laps.indexOf(l), x = 35 + idx / Math.max(s.laps.length-1,1) * (w-55);
      html += `<line class="event-line" x1="${x}" y1="14" x2="${x}" y2="190"/><text class="event-label" x="${x+4}" y="25">L${l.lap} ${l.event}</text>`;
    });
  });
  svg.innerHTML = html;
  $('legend').innerHTML = data.strategies.map((s,i) => `<span style="--color:${colors[i]}">${s.name}</span>`).join('');
  const best = data.strategies[0];
  const tyreColors = {SOFT:'#ff3f3f',MEDIUM:'#ffd84a',HARD:'#eeeeee',INTERMEDIATE:'#4bdb76'};
  $('timeline').innerHTML = best.laps.map(l => `<span style="--tyre:${tyreColors[l.compound]}" title="Lap ${l.lap}: ${l.compound}"></span>`).join('');
}

function updateHeader(s) {
  $('lapBadge').textContent = s.current_lap; $('totalBadge').textContent = s.total_laps;
  $('positionBadge').textContent = s.position;
  $('gapAhead').textContent=`+${s.gap_ahead.toFixed(1)}s`;$('gapBehind').textContent=`+${s.gap_behind.toFixed(1)}s`;$('trackTemperatureBadge').textContent=`${Math.round(s.track_temperature)}°C`;
  $('trackStatus').textContent = s.rain_lap ? `RAIN IN ${s.rain_lap - s.current_lap} LAPS` : 'TRACK CLEAR';
}

function bestStrategy(data) { return data.strategies.find(item => item.id === data.recommendation); }

function renderDecisionIntel(data, s) {
  const best=bestStrategy(data), runner=data.strategies[1], rainRisk=s.rain_lap ? `Rain crossover timing around lap ${s.rain_lap}` : 'Traffic and degradation variance after the stop';
  const invalidation=s.rain_lap ? 'Rain shifts by more than 3 laps or a safety car changes the pit-loss window' : 'A safety car appears or the clean-air rejoin window closes';
  $('decisionIntel').innerHTML=`<div class="intel-head"><p class="eyebrow lime">WHY THIS CALL</p><span>MODEL EVIDENCE</span></div><div class="intel-grid"><div><small>TIME ADVANTAGE</small><strong>${runner.delta.toFixed(1)}s</strong><p>over ${runner.name.toLowerCase()}</p></div><div><small>KEY ASSUMPTION</small><strong>L${best.stops[0]} STOP</strong><p>${best.rationale[0]}</p></div><div><small>BIGGEST RISK</small><strong>${best.risk}</strong><p>${rainRisk}</p></div><div class="invalidate"><small>CALL INVALID IF</small><p>${invalidation}.</p></div></div>`;
}

function renderChange(previous, current, currentScenario) {
  if (!previous) { $('changePanel').hidden=true; return; }
  const before=bestStrategy(previous.simulation), after=bestStrategy(current), old=previous.scenario, changes=[];
  if(old.rain_lap!==currentScenario.rain_lap) changes.push(`rain ${old.rain_lap?'L'+old.rain_lap:'off'} → ${currentScenario.rain_lap?'L'+currentScenario.rain_lap:'off'}`);
  if(old.safety_car_lap!==currentScenario.safety_car_lap) changes.push(`safety car ${old.safety_car_lap?'L'+old.safety_car_lap:'off'} → ${currentScenario.safety_car_lap?'L'+currentScenario.safety_car_lap:'off'}`);
  if(old.tyre_age!==currentScenario.tyre_age) changes.push(`tyre age ${old.tyre_age} → ${currentScenario.tyre_age}`);
  if(old.compound!==currentScenario.compound) changes.push(`${old.compound} → ${currentScenario.compound}`);
  if(old.current_lap!==currentScenario.current_lap) changes.push(`race advanced L${old.current_lap} → L${currentScenario.current_lap}`);
  const oldMargin=previous.simulation.strategies[1].delta, newMargin=current.strategies[1].delta, flipped=before.id!==after.id;
  $('changePanel').hidden=false;
  $('changePanel').innerHTML=`<div class="change-signal ${flipped?'flipped':''}">${flipped?'CALL CHANGED':'CALL HELD'}</div><div class="change-copy"><p class="eyebrow">WHAT CHANGED?</p><h3>${flipped?`${before.name} → ${after.name}`:`${after.name} remains quickest`}</h3><p>${changes.length?changes.join(' · '):'The same race inputs were rerun'}. Winning margin ${oldMargin.toFixed(1)}s → ${newMargin.toFixed(1)}s.</p></div><button id="askWhyChange">ASK ORBIT WHY →</button>`;
  $('askWhyChange').addEventListener('click',()=>ask(`Why did the call ${flipped?'change from '+before.name+' to '+after.name:'stay with '+after.name}? The inputs changed: ${changes.join(', ')||'none'}. Explain the decisive trade-off.`));
}

async function runSimulation(event) {
  if (event) event.preventDefault();
  const requestId=++simulationRequest, button = document.querySelector('.run-btn');
  button.disabled = true; button.querySelector('span').textContent = 'SIMULATING 3 PLANS…';
  try {
    const s = scenario();
    const response = await fetch('/api/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(s)});
    if (!response.ok) throw new Error('The scenario is outside simulation limits.');
    const nextSimulation = await response.json();
    if(requestId!==simulationRequest)return;
    const prior = simulation && previousRun ? {scenario:previousRun.currentScenario,simulation} : null;
    simulation = nextSimulation;
    const best = simulation.strategies.find(x => x.id === simulation.recommendation);
    $('headline').textContent = simulation.headline;
    $('subhead').textContent = `${best.summary} First stop: lap ${best.stops[0]}.`;
    $('confidence').textContent = `${best.confidence}%`;
    $('confidenceRing').style.strokeDashoffset = 195 * (1 - best.confidence / 100);
    renderCards(simulation); renderChart(simulation); updateHeader(s); renderDecisionIntel(simulation,s); renderChange(prior,simulation,s);
    previousRun={currentScenario:{...s}};
    $('uncertaintyPanel').innerHTML = '<div class="uncertainty-loading">Running 240 uncertainty trials…</div>';
    runUncertainty(s);
  } catch (error) { if(requestId===simulationRequest)toast(error.message); }
  finally { if(requestId===simulationRequest){button.disabled = false; button.querySelector('span').textContent = 'RUN STRATEGY MODEL';} }
}

async function runUncertainty(s) {
  try {
    const response = await fetch('/api/monte-carlo', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)});
    if (!response.ok) throw new Error('Uncertainty model unavailable.');
    uncertainty = await response.json(); renderUncertainty(uncertainty);
  } catch (error) { $('uncertaintyPanel').innerHTML=`<div class="uncertainty-loading">${error.message}</div>`; }
}

function renderUncertainty(data) {
  const leader=data.strategies[0], rival=data.rival;
  $('uncertaintyPanel').innerHTML=`<div class="uncertainty-grid">
    <div class="uncertainty-stat"><small>MONTE CARLO · ${data.trials} RUNS</small><strong>${leader.win_probability}%</strong><em>${leader.name.toUpperCase()} WIN RATE</em></div>
    <div class="probability">${data.strategies.map((s,i)=>`<span>${s.name}</span><b>${s.win_probability}%</b><i style="--p:${s.win_probability}%;--c:${colors[i]}"></i>`).join('')}</div>
    <div class="rival-call"><small class="eyebrow">RIVAL REACTION · <b>${rival.pressure} PRESSURE</b></small><p>${rival.call} — response predicted on lap ${rival.predicted_response_lap}, with ${rival.undercut_risk}% undercut risk.</p></div>
  </div>`;
}

function addMessage(role, text, label) {
  const div = document.createElement('div'); div.className = `message ${role}`;
  div.innerHTML = `<small>${label}</small><p></p>`; div.querySelector('p').textContent = text;
  $('messages').appendChild(div); $('messages').scrollTop = $('messages').scrollHeight;
  return div;
}

async function ask(question) {
  if (!question.trim()) return;
  addMessage('user', question, 'YOU · NOW');
  const waiting = addMessage('orbit', 'Checking the strategy model…', 'ORBIT · ANALYSING');
  try {
    const response = await fetch('/api/engineer', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question, scenario:scenario(), simulation})});
    if (!response.ok) throw new Error('Radio connection failed.');
    const data = await response.json();
    waiting.querySelector('small').textContent = `ORBIT · ${data.model.toUpperCase()}`;
    waiting.querySelector('p').textContent = data.answer;
    if(data.trace?.length){const trace=document.createElement('div');trace.className='agent-trace';trace.innerHTML=`<b>AGENT TOOL TRACE</b>${data.trace.map((step,i)=>`<span><i>${String(i+1).padStart(2,'0')}</i><strong>${step.tool.replaceAll('_',' ')}</strong><em>${step.evidence||step.status}</em></span>`).join('')}`;waiting.appendChild(trace)}
    $('aiMode').textContent = data.mode === 'demo' ? 'DEMO' : 'LIVE AI';
    if (voiceEnabled) speak(data.answer);
  } catch (error) { waiting.querySelector('p').textContent = error.message; }
}

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const utterance=new SpeechSynthesisUtterance(text); utterance.rate=1.04; utterance.pitch=.82; utterance.volume=.9;
  const voices=speechSynthesis.getVoices(); utterance.voice=voices.find(v=>/Daniel|Google UK English Male|Microsoft Ryan/i.test(v.name)) || voices.find(v=>/^en/i.test(v.lang)) || null;
  speechSynthesis.speak(utterance);
}

function toggleVoice() {
  voiceEnabled=!voiceEnabled; $('voiceToggle').classList.toggle('active',voiceEnabled);
  $('voiceToggle').textContent=voiceEnabled?'◖))':'MUTE';
  if (!voiceEnabled && 'speechSynthesis' in window) speechSynthesis.cancel();
  toast(`ORBIT voice ${voiceEnabled?'enabled':'muted'}.`);
}

function replayRace() {
  if (!simulation) return;
  const best=simulation.strategies.find(s=>s.id===simulation.recommendation), path=$('stageTrackPath'), car=$('stageCar'), miniPath=$('trackPath'), miniCar=$('replayCar');
  if (replayFrame) {
    cancelAnimationFrame(replayFrame); replayFrame=null;
    document.body.classList.remove('replay-active');
    $('replayBtn').textContent='▶ PLAY STRATEGY';
    $('lapBadge').textContent=scenario().current_lap;
    const startPoint=path.getPointAtLength(0), miniStart=miniPath.getPointAtLength(0); car.setAttribute('cx',startPoint.x); car.setAttribute('cy',startPoint.y); miniCar.setAttribute('cx',miniStart.x); miniCar.setAttribute('cy',miniStart.y);
    $('replayStage').hidden=true;
    toast('Replay stopped and reset.');
    return;
  }
  const firstLap=best.laps[0], selectedSpeed=Number($('replaySpeed').value); $('replayStage').hidden=false; $('replayStrategyName').textContent=best.name; $('stageTotal').textContent=scenario().total_laps; $('stageLap').textContent=firstLap.lap; $('stageTyre').textContent=firstLap.compound; $('stageTime').textContent=`${firstLap.lap_time.toFixed(3)}s`; $('stageEvent').textContent=firstLap.event||'PUSH'; $('stageScale').textContent=`${selectedSpeed===1?'REAL-TIME':selectedSpeed+'×'} · ~${(firstLap.lap_time/selectedSpeed).toFixed(1)} seconds per lap`; $('stageProgress').style.width='0%'; $('stageCall').textContent='Executing the recommended race plan.';
  const length=path.getTotalLength(), start=performance.now(), speed=Number($('replaySpeed').value), lapDurations=best.laps.map(lap=>lap.lap_time*1000/speed), duration=lapDurations.reduce((sum,value)=>sum+value,0);
  document.body.classList.add('replay-active'); $('replayBtn').textContent='■ STOP PLAYBACK';
  function frame(now){
    const elapsed=Math.max(0,Math.min(duration,now-start)), progress=elapsed/duration; let lapIndex=0, elapsedBeforeLap=0;
    while(lapIndex<lapDurations.length-1 && elapsed>=elapsedBeforeLap+lapDurations[lapIndex]){elapsedBeforeLap+=lapDurations[lapIndex];lapIndex+=1}
    const lapProgress=progress===1?1:Math.max(0,Math.min(1,(elapsed-elapsedBeforeLap)/lapDurations[lapIndex]));
    const lap=best.laps[lapIndex], point=path.getPointAtLength(lapProgress*length), miniPoint=miniPath.getPointAtLength(lapProgress*miniPath.getTotalLength());
    car.setAttribute('cx',point.x); car.setAttribute('cy',point.y); miniCar.setAttribute('cx',miniPoint.x); miniCar.setAttribute('cy',miniPoint.y); $('lapBadge').textContent=lap.lap; $('stageLap').textContent=lap.lap; $('stageTyre').textContent=lap.compound; $('stageTime').textContent=`${lap.lap_time.toFixed(3)}s`; $('stageEvent').textContent=lap.event||'PUSH'; $('stageProgress').style.width=`${progress*100}%`; $('replayScrubber').value=progress*100;
    if(lap.event) $('stageCall').textContent=`Box this lap. Fit ${lap.compound.toLowerCase()} tyres and rejoin on the target delta.`;
    if(progress<1){replayFrame=requestAnimationFrame(frame)}else{document.body.classList.remove('replay-active');$('replayBtn').textContent='▶ PLAY STRATEGY';$('stageCall').textContent=`Playback complete. ${best.name} remains the model's fastest plan.`;replayFrame=null;toast(`${best.name} playback complete.`)}
  }
  replayFrame=requestAnimationFrame(frame);
}

function closeReplay() {
  if (replayFrame) replayRace();
  else $('replayStage').hidden=true;
}

function changeReplaySpeed() {
  if (!simulation) return;
  const speed=Number($('replaySpeed').value), best=simulation.strategies.find(s=>s.id===simulation.recommendation), seconds=(best.laps[0].lap_time/speed).toFixed(1);
  $('stageScale').textContent=`${speed===1?'REAL-TIME':speed+'×'} · ~${seconds} seconds per lap`;
  if (replayFrame) { replayRace(); replayRace(); toast(`Playback restarted at ${speed===1?'real-time':speed+'×'} — about ${seconds}s per lap.`); }
}

function seekReplay(percent) {
  if (!simulation) return;
  if (replayFrame) { cancelAnimationFrame(replayFrame); replayFrame=null; document.body.classList.remove('replay-active'); $('replayBtn').textContent='▶ PLAY STRATEGY'; }
  const best=simulation.strategies.find(s=>s.id===simulation.recommendation), progress=Number(percent)/100, totalTime=best.laps.reduce((sum,lap)=>sum+lap.lap_time,0), targetTime=progress*totalTime; let lapIndex=0, timeBeforeLap=0;
  while(lapIndex<best.laps.length-1 && targetTime>=timeBeforeLap+best.laps[lapIndex].lap_time){timeBeforeLap+=best.laps[lapIndex].lap_time;lapIndex+=1}
  const lap=best.laps[lapIndex], lapProgress=progress===1?1:Math.max(0,Math.min(1,(targetTime-timeBeforeLap)/lap.lap_time));
  const stagePath=$('stageTrackPath'), miniPath=$('trackPath'), point=stagePath.getPointAtLength(lapProgress*stagePath.getTotalLength()), miniPoint=miniPath.getPointAtLength(lapProgress*miniPath.getTotalLength());
  $('stageCar').setAttribute('cx',point.x);$('stageCar').setAttribute('cy',point.y);$('replayCar').setAttribute('cx',miniPoint.x);$('replayCar').setAttribute('cy',miniPoint.y);$('stageLap').textContent=lap.lap;$('lapBadge').textContent=lap.lap;$('stageTyre').textContent=lap.compound;$('stageTime').textContent=`${lap.lap_time.toFixed(3)}s`;$('stageEvent').textContent=lap.event||'PUSH';$('stageProgress').style.width=`${percent}%`;
}

function shareReplay() {
  const s=scenario(), params=new URLSearchParams({circuit:s.circuit,lap:s.current_lap,total:s.total_laps,pos:s.position,temp:s.track_temperature,ga:s.gap_ahead,gb:s.gap_behind,age:s.tyre_age,compound:s.compound,rain:s.rain_lap??'',sc:s.safety_car_lap??''});
  const url=`${location.origin}${location.pathname}?${params}`;
  navigator.clipboard?.writeText(url).then(()=>toast('Replay link copied.')).catch(()=>{prompt('Copy replay link',url)});
  history.replaceState(null,'',url);
}

function hydrateReplay() {
  const p=new URLSearchParams(location.search); if(!p.has('lap')) return;
  if(p.has('circuit') && circuits[p.get('circuit')]) $('circuitSelect').value=p.get('circuit');
  $('currentLap').value=p.get('lap');$('currentLapOut').textContent=p.get('lap');$('totalLaps').value=p.get('total')||57;$('racePosition').value=p.get('pos')||4;$('positionBadge').textContent=p.get('pos')||4;$('trackTemperature').value=p.get('temp')||31;$('gapAheadInput').value=p.get('ga')||2.4;$('gapBehindInput').value=p.get('gb')||1.8;$('tyreAge').value=p.get('age')||18;$('compound').value=p.get('compound')||'MEDIUM';
  const rain=p.get('rain');$('rainEnabled').checked=Boolean(rain);$('rainField').style.display=rain?'block':'none';if(rain){$('rainLap').value=rain;$('rainLapOut').textContent=rain}$('safetyCar').value=p.get('sc')||'';
}

function selectCircuit({run=true,preserve=false}={}) {
  const config=circuits[$('circuitSelect').value];
  $('raceName').textContent=config.race; $('circuitProfile').textContent=config.profile; $('trackCredit').textContent=config.credit; document.querySelector('.track-map').setAttribute('aria-label',`${config.name} schematic circuit map`);
  if(!preserve){$('totalLaps').value=config.laps; $('currentLap').max=config.laps-1; $('currentLap').value=config.current; $('currentLapOut').textContent=config.current; $('rainLap').max=config.laps-1; $('rainLap').value=config.rain; $('rainLapOut').textContent=config.rain;}
  initTrackGeometry(); previousRun=null;
  if(run){runSimulation();toast(`${config.name} profile loaded — strategy physics updated.`)}
}

function initOnboarding(){
  const seen=localStorage.getItem('pitwall_seen');$('onboarding').hidden=Boolean(seen)||new URLSearchParams(location.search).has('lap');
  $('enterPitwall').addEventListener('click',()=>{$('onboarding').hidden=true;localStorage.setItem('pitwall_seen','1')});
}

function toast(text) { const el=$('toast'); el.textContent=text; el.classList.add('show'); setTimeout(()=>el.classList.remove('show'),3000); }

function renderTelemetry() {
  if (!simulation) return '<p>Run the strategy model to populate telemetry.</p>';
  const best = simulation.strategies.find(s => s.id === simulation.recommendation);
  const laps = best.laps.slice(0, 10);
  const cleanLaps = best.laps.filter(l => !l.event);
  const fastest = Math.min(...cleanLaps.map(l => l.lap_time));
  const tyreHealth = Math.max(18, 100 - scenario().tyre_age * ({SOFT:3.2,MEDIUM:2.25,HARD:1.55}[scenario().compound] || 2));
  const avg = cleanLaps.slice(0, 5).reduce((sum,l)=>sum+l.lap_time,0) / Math.min(cleanLaps.length,5);
  const compoundColor = {SOFT:'#ff3f3f',MEDIUM:'#ffd84a',HARD:'#eee',INTERMEDIATE:'#4bdb76'};
  return `<div class="aux-head"><div><p class="eyebrow lime">LIVE MODEL OUTPUT</p><h2>Telemetry</h2><p>Synthetic race signals generated by the deterministic strategy engine.</p></div><span class="aux-badge">PLAN · ${best.name.toUpperCase()}</span></div>
    <div class="telemetry-metrics">
      <div class="telemetry-metric"><small>PROJECTED FASTEST</small><strong>${fastest.toFixed(3)}s</strong><em>OPTIMAL WINDOW</em></div>
      <div class="telemetry-metric"><small>TYRE HEALTH</small><strong>${Math.round(tyreHealth)}%</strong><em>${scenario().compound} · ${scenario().tyre_age} LAPS</em></div>
      <div class="telemetry-metric"><small>5-LAP PACE</small><strong>${avg.toFixed(3)}s</strong><em>MODEL AVERAGE</em></div>
      <div class="telemetry-metric"><small>PIT WINDOW</small><strong>L${best.stops[0]}</strong><em>${best.risk} RISK</em></div>
    </div>
    <div class="telemetry-grid">
      <div class="telemetry-card"><h3>Projected system health</h3><div class="telemetry-bars">
        <div class="telemetry-bar"><span>TYRES</span><i style="--width:${tyreHealth}%;--bar:${compoundColor[scenario().compound]}"></i><b>${Math.round(tyreHealth)}%</b></div>
        <div class="telemetry-bar"><span>FUEL</span><i style="--width:${Math.round(simulation.race_state.remaining/scenario().total_laps*100)}%"></i><b>${simulation.race_state.remaining} laps</b></div>
        <div class="telemetry-bar"><span>WEATHER</span><i style="--width:${scenario().rain_lap ? 68 : 12}%;--bar:${scenario().rain_lap ? '#54d7e8' : '#c8ff35'}"></i><b>${scenario().rain_lap ? 'CHANGE' : 'STABLE'}</b></div>
        <div class="telemetry-bar"><span>CONF.</span><i style="--width:${best.confidence}%"></i><b>${best.confidence}%</b></div>
      </div></div>
      <div class="telemetry-card"><h3>Next ten laps</h3><table class="lap-table"><thead><tr><th>LAP</th><th>TIME</th><th>TYRE</th><th>EVENT</th></tr></thead><tbody>${laps.map(l=>`<tr><td>${l.lap}</td><td>${l.lap_time.toFixed(3)}</td><td><span class="compound-pill" style="color:${compoundColor[l.compound]}">${l.compound[0]}</span></td><td>${l.event || '—'}</td></tr>`).join('')}</tbody></table></div>
    </div>`;
}

const presets = [
  {id:'dry',name:'Clean-air sprint',desc:'A dry race with no interruptions. Compare pure degradation against pit loss.',tags:['DRY','NO SAFETY CAR','1-STOP'],values:{lap:18,age:18,rain:false,sc:''}},
  {id:'rain',name:'Crossover gamble',desc:'Rain approaches in twenty laps. Decide whether to create clean air or protect track position.',tags:['LIGHT RAIN','CROSSOVER L38','VARIABLE'],values:{lap:18,age:18,rain:true,rainLap:38,sc:''}},
  {id:'safety',name:'Safety-car window',desc:'A neutralisation is projected four laps away, cutting the effective pit-lane loss.',tags:['SAFETY CAR L22','DISCOUNTED STOP','TACTICAL'],values:{lap:18,age:20,rain:false,sc:'22'}},
  {id:'cliff',name:'Tyre-cliff defence',desc:'An ageing soft tyre forces an immediate call: box now or hold position.',tags:['SOFT','AGE 19','HIGH DEG'],values:{lap:24,age:19,rain:false,sc:'',compound:'SOFT'}}
];

function renderScenarios() {
  return `<div class="aux-head"><div><p class="eyebrow lime">COUNTERFACTUAL LAB</p><h2>Scenario presets</h2><p>Load a race state, then explore how the recommended call changes.</p></div><span class="aux-badge">4 PRESETS</span></div><div class="scenario-grid">${presets.map((p,i)=>`<article class="scenario-preset"><span class="number">0${i+1}</span><h3>${p.name}</h3><p>${p.desc}</p><div class="scenario-tags">${p.tags.map(t=>`<span>${t}</span>`).join('')}</div><button class="apply-scenario" data-preset="${p.id}">LOAD & RUN →</button></article>`).join('')}</div>`;
}

async function renderSeason() {
  $('auxPanel').innerHTML='<div class="season-loading">Loading verified 2026 snapshot…</div>';
  if(!seasonData){const response=await fetch('/api/season/2026');seasonData=await response.json()}
  if(!strategyRounds){const response=await fetch('/api/strategy/rounds');strategyRounds=await response.json()}
  if(!validationData){const response=await fetch('/api/strategy/validation');validationData=await response.json()}
  const d=seasonData, next=d.rounds.find(r=>r.status==='upcoming');
  $('auxPanel').innerHTML=`<div class="season-head"><div><p class="eyebrow lime">2026 SEASON INTELLIGENCE</p><h2>Championship command centre</h2><p>Official published facts separated from PitWall model estimates.</p></div><div class="source-stamp"><b>OFFICIAL SNAPSHOT</b><span>${d.snapshot_date}</span></div></div>
  <div class="season-kpis"><div><small>ROUNDS ANNOUNCED</small><strong>${d.summary.announced_rounds}</strong></div><div><small>COMPLETED</small><strong>${d.summary.active_results_rounds}</strong></div><div><small>GRID</small><strong>${d.summary.drivers}</strong><em>11 TEAMS</em></div><div><small>NEXT</small><strong>${next.name}</strong><em>${next.venue}</em></div></div>
  <div class="season-layout"><section class="season-main"><div class="season-section-head"><div><p class="eyebrow">FULL CALENDAR</p><h3>All 24 announced rounds</h3></div><span>SPRINT · ◆</span></div><div class="calendar-grid">${d.rounds.map(r=>`<article class="round ${r.status}"><b>${String(r.round).padStart(2,'0')}</b><div><small>${r.date}</small><strong>${r.name}${r.sprint?' ◆':''}</strong><span>${r.venue}</span></div><em>${r.status}</em>${r.winner?`<p>WINNER · ${r.winner}<br>${r.team}</p>`:''}</article>`).join('')}</div></section>
  <aside class="season-side"><div class="standings-panel"><p class="eyebrow lime">DRIVER STANDINGS</p>${d.drivers.map(x=>`<div><b>${x.position}</b><strong>${x.code}</strong><span>${x.name}<small>${x.team}</small></span><em>${x.points}</em></div>`).join('')}</div><div class="standings-panel teams"><p class="eyebrow lime">TEAM STANDINGS</p>${d.teams.map(x=>`<div><b>${x.position}</b><span>${x.name}<small>${x.power_unit} PU</small></span><em>${x.points}</em></div>`).join('')}</div></aside></div>
  <section class="qual-lab"><div class="qual-head"><div><p class="eyebrow lime">Q1 · Q2 · Q3 MONTE CARLO</p><h3>Qualifying probability lab</h3><p>PitWall estimate using published championship form—not an official prediction.</p></div><div class="qual-controls"><select id="qualCircuit">${d.rounds.filter(r=>r.status==='upcoming').map(r=>`<option>${r.venue}</option>`).join('')}</select><label><input id="qualWet" type="checkbox"> WET</label><button id="runQualifying">RUN 2,000 TRIALS →</button></div></div><div id="qualResults" class="qual-results"><p>Select conditions and run the model.</p></div></section>
  <section class="season-bottom"><div><p class="eyebrow lime">FASTEST LAPS SO FAR</p>${d.fastest_laps.map((x,i)=>`<span><b>${i+1}</b>${x.grand_prix}<strong>${x.driver}</strong><em>${x.time}</em></span>`).join('')}</div><div class="aduo"><p class="eyebrow lime">FIA ADUO TRACKER</p><h3>ICE development allowances</h3><p>The FIA’s private ICE Performance Index—not race pace—determines eligibility.</p><div class="aduo-scale"><i>&lt;2%<small>NONE</small></i><i>2–4%<small>$3.0M</small></i><i>4–6%<small>$4.65M</small></i><i>6–8%<small>$6.35M</small></i><i>8–10%<small>$8M</small></i><i>10%+<small>$11M</small></i></div><p class="data-warning">Exact manufacturer deficits are not inferred from standings. Published FIA eligibility only.</p></div></section>`;
  const backtest=document.createElement('section');
  backtest.className='backtest-lab';
  backtest.innerHTML=`<div class="backtest-head"><div><p class="eyebrow lime">24-ROUND STRATEGY MODEL</p><h3>Forecast vs race execution</h3><p>Compare the model baseline with the winner's first officially recorded stop.</p></div><div><select id="backtestRound">${strategyRounds.rounds.map(r=>`<option value="${r.round}" ${r.round===11?'selected':''}>R${String(r.round).padStart(2,'0')} · ${r.race} · ${r.status.toUpperCase()}</option>`).join('')}</select><button id="runBacktest">COMPARE →</button></div></div><div class="leakage-note"><b>NO-LEAKAGE RULE</b>${strategyRounds.methodology.leakage_rule}. Completed-race forecasts are labelled retrospective baselines—not claims of pre-race predictions.</div><div id="backtestResult"></div>`;
  $('auxPanel').querySelector('.season-layout').before(backtest);
  const score=document.createElement('section');score.className='validation-scorecard';score.innerHTML=`<div><p class="eyebrow lime">MODEL VALIDATION · HONEST SCORECARD</p><h3>What the historical baseline actually achieved</h3><p>${validationData.disclosure}</p></div><span><small>VALIDATED</small><strong>${validationData.coverage.validated_rounds}/${validationData.coverage.completed_rounds}</strong></span><span><small>MEAN STOP ERROR</small><strong>${validationData.metrics.mean_absolute_stop_lap_error} LAPS</strong></span><span><small>WINDOW HIT RATE</small><strong>${validationData.metrics.pit_window_hit_rate}%</strong></span><span><small>SOURCE GAPS</small><strong>${validationData.coverage.source_gaps.length}</strong><em>${validationData.coverage.source_gaps.join(', ')||'NONE'}</em></span>`;backtest.before(score);
  const challenge=document.createElement('section');challenge.className='blind-challenge';challenge.innerHTML=`<div><p class="eyebrow lime">BLIND HISTORICAL CHALLENGE</p><h3>Make the call before the reveal</h3><p>Load only the retrospective baseline, commit to its stop window, then reveal the winner's official execution.</p></div><select id="blindRound">${strategyRounds.rounds.filter(r=>r.status==='completed'&&r.actual?.first_stop_lap!=null).map(r=>`<option value="${r.round}">R${String(r.round).padStart(2,'0')} · ${r.race}</option>`).join('')}</select><button id="startBlind">LOAD BLIND →</button><div id="blindResult"><span>Actual execution remains hidden.</span></div>`;score.before(challenge);$('startBlind').addEventListener('click',startBlindChallenge);
  $('runQualifying').addEventListener('click',runQualifying);
  $('runBacktest').addEventListener('click',runBacktest);
  $('backtestRound').addEventListener('change',()=>{
    $('backtestResult').classList.add('comparison-stale');
    $('runBacktest').textContent='COMPARE SELECTED ROUND →';
  });
  runBacktest();
}

async function startBlindChallenge(){
  const button=$('startBlind');button.disabled=true;button.textContent='LOADING…';const response=await fetch(`/api/strategy/backtest/${$('blindRound').value}`);blindChallenge=await response.json();const f=blindChallenge.forecast;
  $('blindResult').innerHTML=`<article><small>ORBIT BASELINE</small><strong>${f.start_compound} → ${f.target_compound}</strong><b>BOX L${f.first_stop_lap}</b><p>Target window L${f.pit_window[0]}–L${f.pit_window[1]} · ${f.uncertainty} uncertainty</p></article><div class="blind-mask"><span>ACTUAL STOP HIDDEN</span><button id="revealBlind">COMMIT & REVEAL →</button></div>`;$('revealBlind').addEventListener('click',revealBlindChallenge);button.disabled=false;button.textContent='RESET CHALLENGE';
}

function revealBlindChallenge(){
  const d=blindChallenge,a=d.actual,v=d.validation;$('blindResult').innerHTML+=`<article class="blind-reveal"><small>OFFICIAL EXECUTION</small><strong>${a.winner}</strong><b>FIRST STOP L${a.first_stop_lap}</b><p>${a.stop_count} recorded stop${a.stop_count===1?'':'s'} · ${a.winner_team}</p></article><article class="blind-verdict"><small>VERDICT</small><strong>${v.pit_window_hit?'WINDOW HIT':'WINDOW MISS'}</strong><b>${v.agreement_score}% AGREEMENT</b><p>${v.explanation}</p><a href="${a.source}" target="_blank" rel="noreferrer">VERIFY OFFICIAL SOURCE ↗</a></article>`;$('revealBlind').disabled=true;$('revealBlind').textContent='CALL LOCKED';
}

async function runBacktest(){
  const button=$('runBacktest'),result=$('backtestResult'),round=$('backtestRound').value;
  button.disabled=true;button.textContent='COMPARING…';result.classList.remove('comparison-stale');result.classList.add('comparison-loading');
  try {
  const response=await fetch(`/api/strategy/backtest/${round}`);if(!response.ok)throw new Error('Comparison data is unavailable.');
  const d=await response.json(),f=d.forecast,a=d.actual,v=d.validation;
  const actualCard=a?`<h4>${a.winner}</h4><strong>${a.first_stop_lap==null?'SOURCE GAP':'L'+a.first_stop_lap}</strong><p>${a.winner_team} · ${a.stop_count==null?'stop count pending':a.stop_count+' recorded stop'+(a.stop_count===1?'':'s')}</p>${a.source?`<a href="${a.source}" target="_blank" rel="noreferrer">OFFICIAL PIT SUMMARY ↗</a>`:''}`:`<h4>Not raced</h4><strong>—</strong><p>Actual execution will appear after an official result is published.</p>`;
  const counter=d.counterfactual?`<h4>Earlier-stop test</h4><strong>L${d.counterfactual.first_stop_lap}</strong><p>${d.counterfactual.claim}</p>`:`<h4>Awaiting execution</h4><strong>—</strong><p>Counterfactual comparison requires an actual race stop.</p>`;
  const validation=v?.status==='validated'?`<h4>${v.pit_window_hit?'WINDOW HIT':'WINDOW MISS'}</h4><strong>${v.agreement_score}%</strong><p>${v.explanation}</p>`:v?.status==='source-gap'?`<h4>Source gap</h4><strong>—</strong><p>${v.explanation}</p>`:`<h4>Forecast only</h4><strong>—</strong><p>No validation score before race completion.</p>`;
  result.innerHTML=`<div class="backtest-meta"><span>R${String(d.round).padStart(2,'0')} · ${d.race}</span><b>${f.classification.toUpperCase()}</b><em>Generated ${f.generated_at}</em><i>COMPARISON UPDATED</i></div><div class="backtest-flow"><article class="backtest-card"><small>01 · MODEL BASELINE</small><h4>${f.start_compound} → ${f.target_compound}</h4><strong>L${f.first_stop_lap}</strong><p>Target window L${f.pit_window[0]}–L${f.pit_window[1]} · ${f.uncertainty} uncertainty</p></article><article class="backtest-card actual"><small>02 · ACTUAL EXECUTION</small>${actualCard}</article><article class="backtest-card counter"><small>03 · COUNTERFACTUAL</small>${counter}</article><article class="backtest-card validation"><small>04 · VALIDATION</small>${validation}</article></div>`;
  result.classList.remove('comparison-loading');result.classList.add('comparison-updated');setTimeout(()=>result.classList.remove('comparison-updated'),500);
  } catch(error){result.classList.remove('comparison-loading');toast(error.message)}
  finally{button.disabled=false;button.textContent='COMPARE →'}
}

async function runQualifying(){
  const button=$('runQualifying');button.disabled=true;button.textContent='SIMULATING…';
  const circuit=$('qualCircuit').value,wet=$('qualWet').checked,response=await fetch(`/api/qualifying?circuit=${encodeURIComponent(circuit)}&trials=2000&wet=${wet}`),data=await response.json();
  $('qualResults').innerHTML=`<div class="energy-strip"><div><small>DEPLOYMENT DEMAND</small><strong>${data.energy_strategy.deployment_demand}</strong></div><div><small>HARVEST OPPORTUNITY</small><strong>${data.energy_strategy.harvest_opportunity}</strong></div><div><small>ACTIVE AERO</small><strong>${data.energy_strategy.active_aero}</strong></div><p><b>ENERGY CALL</b>${data.energy_strategy.boost_call}<small>7 MJ recharge parameter · 350 kW peak superclip · +150 kW race Boost cap</small></p></div><div class="qual-table"><div class="qual-row head"><span>GRID</span><span>DRIVER</span><span>TEAM</span><span>Q2</span><span>Q3</span><span>POLE</span></div>${data.results.map(x=>`<div class="qual-row"><b>P${x.expected_grid}</b><strong>${x.driver}<small>${x.code}</small></strong><span>${x.team}</span><em>${x.q2_probability}%</em><em>${x.q3_probability}%</em><em>${x.pole_probability}%</em></div>`).join('')}</div><p class="model-disclosure">PITWALL ESTIMATE · ${data.trials} TRIALS · ${data.assumptions.join(' · ')}</p>`;
  button.disabled=false;button.textContent='RUN 2,000 TRIALS →';
}

async function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.view === view));
  $('strategyView').hidden = view !== 'strategy';
  $('auxPanel').hidden = view === 'strategy';
  if (view === 'telemetry') $('auxPanel').innerHTML = renderTelemetry();
  if (view === 'scenarios') {
    $('auxPanel').innerHTML = renderScenarios();
    document.querySelectorAll('.apply-scenario').forEach(button => button.addEventListener('click', () => applyPreset(button.dataset.preset)));
  }
  if (view === 'season') await renderSeason();
}

async function applyPreset(id) {
  const p = presets.find(item => item.id === id).values;
  $('currentLap').value=p.lap; $('currentLapOut').textContent=p.lap; $('tyreAge').value=p.age;
  $('rainEnabled').checked=p.rain; $('rainField').style.display=p.rain?'block':'none';
  if (p.rainLap) { $('rainLap').value=p.rainLap; $('rainLapOut').textContent=p.rainLap; }
  $('safetyCar').value=p.sc; $('compound').value=p.compound || 'MEDIUM';
  switchView('strategy'); await runSimulation(); toast('Scenario loaded and simulated.');
}

populateCircuitSelect();
$('racePosition').innerHTML=Array.from({length:22},(_,i)=>`<option value="${i+1}" ${i===3?'selected':''}>P${i+1}${i===0?' · LEADER':i>=10?' · TRAFFIC':''}</option>`).join('');
$('scenarioForm').addEventListener('submit', runSimulation);
$('chatForm').addEventListener('submit', e => {e.preventDefault(); const q=$('question').value; $('question').value=''; ask(q);});
document.querySelectorAll('.quick-prompts button').forEach(b => b.addEventListener('click',()=>ask(b.textContent)));
document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click',()=>switchView(button.dataset.view)));
$('voiceToggle').classList.add('active');
$('voiceToggle').addEventListener('click',toggleVoice);
$('replayBtn').addEventListener('click',replayRace);
$('closeReplay').addEventListener('click',closeReplay);
$('replayScrubber').addEventListener('input',e=>seekReplay(e.target.value));
$('replaySpeed').addEventListener('change',changeReplaySpeed);
$('shareBtn').addEventListener('click',shareReplay);
$('circuitSelect').addEventListener('change',()=>selectCircuit());
$('racePosition').addEventListener('change',e=>{$('positionBadge').textContent=e.target.value;runSimulation();});
['trackTemperature','gapAheadInput','gapBehindInput'].forEach(id=>$(id).addEventListener('change',runSimulation));
$('currentLap').addEventListener('input', e => $('currentLapOut').textContent=e.target.value);
$('rainLap').addEventListener('input', e => $('rainLapOut').textContent=e.target.value);
$('rainEnabled').addEventListener('change', e => $('rainField').style.display=e.target.checked?'block':'none');
$('totalLaps').addEventListener('change', e => { $('currentLap').max=e.target.value-1; $('rainLap').max=e.target.value-1; });
hydrateReplay(); selectCircuit({run:false,preserve:new URLSearchParams(location.search).has('lap')}); initOnboarding(); runSimulation();
