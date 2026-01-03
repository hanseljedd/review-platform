;(function(){
  var KEY = 'bf_pomodoro_state'
  var d = document
  var w = window
  function ms(m){return m*60000}
  function now(){return Date.now()}
  function read(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return {}}}
  function write(s){localStorage.setItem(KEY,JSON.stringify(s))}
  function pad(n){n=Math.max(0,Math.floor(n));return n<10?('0'+n):String(n)}
  function format(msLeft){var s=Math.max(0,Math.floor(msLeft/1000));var m=Math.floor(s/60);var sec=s%60;return pad(m)+':'+pad(sec)}
  var state=read()
  if(!state||!state.version){state={version:1,studyMin:25,restMin:5,longMin:20,phase:'study',cyclesCompleted:0,awaitLong:false,running:false,paused:false,remainingMs:ms(25),endTs:0,collapsed:false}}
  var root=d.createElement('div');root.className='pomodoro-widget'
  var row=d.createElement('div');row.className='pomodoro-row'
  var phaseEl=d.createElement('div');phaseEl.className='pomodoro-phase'
  var timeEl=d.createElement('div');timeEl.className='pomodoro-time'
  var cycleEl=d.createElement('div');cycleEl.className='pomodoro-cycle'
  var collapseBtn=d.createElement('button');collapseBtn.className='pomodoro-collapse';collapseBtn.title='Collapse';collapseBtn.textContent='−'
  row.appendChild(phaseEl);row.appendChild(timeEl);row.appendChild(cycleEl);row.appendChild(collapseBtn)
  var controls=d.createElement('div');controls.className='pomodoro-controls'
  var startBtn=d.createElement('button');startBtn.className='pomodoro-btn';startBtn.textContent='Start'
  var pauseBtn=d.createElement('button');pauseBtn.className='pomodoro-btn';pauseBtn.textContent='Pause'
  var resetBtn=d.createElement('button');resetBtn.className='pomodoro-btn';resetBtn.textContent='Reset'
  var gearBtn=d.createElement('button');gearBtn.className='pomodoro-gear';gearBtn.textContent='⚙'
  controls.appendChild(startBtn);controls.appendChild(pauseBtn);controls.appendChild(resetBtn);controls.appendChild(gearBtn)
  root.appendChild(row);root.appendChild(controls)
  var modal=d.createElement('div');modal.className='pomodoro-modal'
  var backdrop=d.createElement('div');backdrop.className='pomodoro-modal-backdrop'
  var card=d.createElement('div');card.className='pomodoro-modal-card'
  var form=d.createElement('div');form.className='pomodoro-form'
  var lblStudy=d.createElement('label');lblStudy.textContent='Study (min)'
  var inpStudy=d.createElement('input');inpStudy.type='number';inpStudy.min='1'
  var lblRest=d.createElement('label');lblRest.textContent='Short Rest (min)'
  var inpRest=d.createElement('input');inpRest.type='number';inpRest.min='1'
  var lblLong=d.createElement('label');lblLong.textContent='Long Rest (min)'
  var inpLong=d.createElement('input');inpLong.type='number';inpLong.min='1'
  var applyNowLbl=d.createElement('label');applyNowLbl.textContent='Apply to current phase'
  var applyNow=d.createElement('input');applyNow.type='checkbox'
  form.appendChild(lblStudy);form.appendChild(inpStudy);form.appendChild(lblRest);form.appendChild(inpRest);form.appendChild(lblLong);form.appendChild(inpLong);form.appendChild(applyNowLbl);form.appendChild(applyNow)
  var actions=d.createElement('div');actions.className='pomodoro-modal-actions'
  var saveBtn=d.createElement('button');saveBtn.className='pomodoro-btn';saveBtn.textContent='Save'
  var cancelBtn=d.createElement('button');cancelBtn.className='pomodoro-btn';cancelBtn.textContent='Cancel'
  actions.appendChild(cancelBtn);actions.appendChild(saveBtn)
  card.appendChild(form);card.appendChild(actions)
  modal.appendChild(backdrop);modal.appendChild(card)
  d.body.appendChild(root);d.body.appendChild(modal)
  // Position persistence
  function clamp(v,min,max){return Math.min(max,Math.max(min,v))}
  function applyPosition(){var x=state.posX,y=state.posY;if(typeof x==='number'&&typeof y==='number'){root.style.left=x+'px';root.style.top=y+'px';root.style.right='auto';root.style.bottom='auto'}}
  function setPosition(x,y){var maxX=w.innerWidth-root.offsetWidth;var maxY=w.innerHeight-root.offsetHeight;state.posX=clamp(x,0,Math.max(0,maxX));state.posY=clamp(y,0,Math.max(0,maxY));write(state);applyPosition()}
  function ensureInViewport(){if(typeof state.posX==='number'&&typeof state.posY==='number'){setPosition(state.posX,state.posY)}}
  function phaseLabel(p){return p==='study'?'Study':(p==='rest'?'Rest':'Long Rest')}
  function durationForPhase(p){if(p==='study')return ms(state.studyMin);if(p==='rest')return ms(state.restMin);return ms(state.longMin)}
  function setPhase(p,msDur){state.phase=p;state.endTs=now()+msDur;state.running=true;state.paused=false;state.remainingMs=msDur;write(state)}
  var ac=null
  function initAudio(){try{if(!ac){ac=new (w.AudioContext||w.webkitAudioContext)()}}catch(e){ac=null}}
  function beep(){if(!ac)return;var o=ac.createOscillator();var g=ac.createGain();o.connect(g);g.connect(ac.destination);o.type='sine';o.frequency.value=660;g.gain.setValueAtTime(0.0001,ac.currentTime);g.gain.exponentialRampToValueAtTime(0.2,ac.currentTime+0.02);o.start();o.stop(ac.currentTime+0.25)}
  function notifyPhaseChange(){beep()}
  function nextPhase(){if(state.phase==='study'){if(state.awaitLong){state.awaitLong=false;setPhase('long',durationForPhase('long'));notifyPhaseChange();return}setPhase('rest',durationForPhase('rest'));notifyPhaseChange();return}if(state.phase==='rest'){state.cyclesCompleted=Math.min(3,(state.cyclesCompleted||0)+1);if(state.cyclesCompleted===3){state.awaitLong=true}setPhase('study',durationForPhase('study'));notifyPhaseChange();return}if(state.phase==='long'){state.cyclesCompleted=0;state.awaitLong=false;setPhase('study',durationForPhase('study'));notifyPhaseChange();return}}
  function start(){if(state.paused){state.endTs=now()+Math.max(0,state.remainingMs||0);state.running=true;state.paused=false;write(state);return}if(!state.running){setPhase(state.phase,durationForPhase(state.phase))}}
  function pause(){if(state.running){state.remainingMs=Math.max(0,(state.endTs||now())-now());state.running=false;state.paused=true;write(state)}}
  function reset(){state.phase='study';state.cyclesCompleted=0;state.awaitLong=false;state.running=false;state.paused=false;state.remainingMs=durationForPhase('study');state.endTs=0;write(state)}
  function openSettings(){inpStudy.value=state.studyMin;inpRest.value=state.restMin;inpLong.value=state.longMin;applyNow.checked=false;modal.classList.add('show')}
  function closeSettings(){modal.classList.remove('show')}
  cancelBtn.onclick=function(){closeSettings()}
  saveBtn.onclick=function(){var s=Math.max(1,parseInt(inpStudy.value||state.studyMin,10));var r=Math.max(1,parseInt(inpRest.value||state.restMin,10));var l=Math.max(1,parseInt(inpLong.value||state.longMin,10));state.studyMin=s;state.restMin=r;state.longMin=l;if(applyNow.checked){if(state.running){state.endTs=now()+durationForPhase(state.phase)}else{state.remainingMs=durationForPhase(state.phase)}}write(state);closeSettings()}
  gearBtn.onclick=openSettings
  startBtn.onclick=function(){initAudio();start()}
  pauseBtn.onclick=function(){initAudio();pause()}
  resetBtn.onclick=function(){initAudio();reset();render()}
  collapseBtn.onclick=function(){state.collapsed=!state.collapsed;write(state);applyCollapsed()}
  backdrop.onclick=closeSettings
  function applyCollapsed(){if(state.collapsed){root.classList.add('collapsed');collapseBtn.textContent='+'}else{root.classList.remove('collapsed');collapseBtn.textContent='−'}}
  function render(){phaseEl.textContent=phaseLabel(state.phase);cycleEl.textContent='Cycle '+String(state.cyclesCompleted||0)+'/3';var rem=state.running?Math.max(0,(state.endTs||now())-now()):Math.max(0,state.remainingMs||durationForPhase(state.phase));timeEl.textContent=format(rem);applyCollapsed()}
  var lastWrite=0
  function tick(){if(state.running){var left=(state.endTs||now())-now();if(left<=0){nextPhase()}else{state.remainingMs=left}if(now()-lastWrite>800){write(state);lastWrite=now()}}render()}
  render()
  setInterval(tick,500)
  w.addEventListener('storage',function(ev){if(ev.key===KEY){state=read();render()}})
  // Drag logic
  var dragging=false, startX=0,startY=0,origX=0,origY=0
  function dragStart(ev){var btn=ev.target.closest('button');if(btn)return; dragging=true; root.classList.add('dragging'); startX=(ev.touches?ev.touches[0].clientX:ev.clientX); startY=(ev.touches?ev.touches[0].clientY:ev.clientY); origX=(typeof state.posX==='number'?state.posX:(w.innerWidth-root.offsetWidth-16)); origY=(typeof state.posY==='number'?state.posY:(w.innerHeight-root.offsetHeight-16)); d.addEventListener('mousemove',dragMove); d.addEventListener('mouseup',dragEnd); d.addEventListener('touchmove',dragMove,{passive:false}); d.addEventListener('touchend',dragEnd)}
  function dragMove(ev){if(!dragging)return; ev.preventDefault(); var cx=(ev.touches?ev.touches[0].clientX:ev.clientX); var cy=(ev.touches?ev.touches[0].clientY:ev.clientY); var nx=origX+(cx-startX); var ny=origY+(cy-startY); setPosition(nx,ny)}
  function dragEnd(){if(!dragging)return; dragging=false; root.classList.remove('dragging'); d.removeEventListener('mousemove',dragMove); d.removeEventListener('mouseup',dragEnd); d.removeEventListener('touchmove',dragMove); d.removeEventListener('touchend',dragEnd)}
  row.addEventListener('mousedown',dragStart); row.addEventListener('touchstart',dragStart,{passive:true})
  // Initialize position
  applyPosition(); ensureInViewport(); w.addEventListener('resize',ensureInViewport)
})();
