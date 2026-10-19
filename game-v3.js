
// 100-level challenge engine. Reuses existing localStorage progress keys.
(function(){
'use strict';
const $=id=>document.getElementById(id),TOTAL=100;
const overlay=$('modal');
let current=0,level=null,found=new Set(),unlocked=1,best={},lastPlayed=0;
let seconds=120,hints=0,mistakes=0,usedHints=0,playing=false,zoom=false,timer=0,audio=null,syncing=false;
try{
 unlocked=Math.max(1,Math.min(TOTAL,Number(localStorage.getItem('eye_unlocked'))||1));
 best=JSON.parse(localStorage.getItem('eye_best')||'{}');
 lastPlayed=Math.max(0,Math.min(unlocked-1,Number(localStorage.getItem('eye_last_played'))||unlocked-1));
}catch(e){}
const save=()=>{try{localStorage.setItem('eye_unlocked',unlocked);localStorage.setItem('eye_best',JSON.stringify(best));localStorage.setItem('eye_last_played',String(lastPlayed));}catch(e){}};
function tone(n=650,d=.08){try{
 audio??=new(window.AudioContext||window.webkitAudioContext)();
 const o=audio.createOscillator(),g=audio.createGain();o.type='sine';o.frequency.value=n;g.gain.setValueAtTime(.038,audio.currentTime);g.gain.exponentialRampToValueAtTime(.0001,audio.currentTime+d);o.connect(g).connect(audio.destination);o.start();o.stop(audio.currentTime+d);
}catch(e){}}
function stats(){
 $('lv').textContent=String(current+1).padStart(3,'0')+' / 100';
 $('found').textContent=found.size+' / 5';
 $('time').textContent=String(Math.max(0,seconds));
 $('bar').style.width=(found.size/5*100)+'%';
 $('title').textContent=level.cfg.title+(level.alt?' · 番外篇':'');
 $('hintBtn').textContent='💡 提示 '+hints;
 $('hintBtn').disabled=!playing||hints===0;
 $('zoomBtn').textContent=zoom?'↙ 還原':'🔎 放大 2×';
}
function indicator(index,side,hint=false){
 const el=$('spots'+side),o=level.objs[level.target[index]];
 if(!el||!o)return;
 const mark=document.createElement('span');mark.className=hint?'ring hintRing':'ring';
 mark.style.left=((o.x+14*o.scale)/480*100)+'%';
 mark.style.top=((o.y+14*o.scale)/280*100)+'%';
 el.append(mark);
 if(hint)setTimeout(()=>mark.remove(),1600);
}
function draw(){
 for(const side of ['A','B']){
  const el=$('scene'+side);
  el.classList.toggle('zoomed',zoom);
  el.innerHTML='<div class="stage" id="stage'+side+'">'+sceneSvg(level,side)+'<div class="spots" id="spots'+side+'"></div></div>';
  const stage=$('stage'+side);
  stage.onclick=(event)=>{
   if(!playing)return;
   const b=stage.getBoundingClientRect();
   const x=(event.clientX-b.left)/b.width*480,y=(event.clientY-b.top)/b.height*280;
   onTap(x,y,side);
  };
  el.onscroll=()=>{
   if(!zoom||syncing)return;
   syncing=true;
   const other=$('scene'+(side==='A'?'B':'A'));
   other.scrollLeft=el.scrollLeft;other.scrollTop=el.scrollTop;
   syncing=false;
  };
  for(const i of found)indicator(i,side);
 }
 stats();
}
function onTap(x,y,side){
 let candidate=-1,dist=Infinity;
 level.target.forEach((id,i)=>{
  if(found.has(i))return;
  const o=level.objs[id],d=Math.hypot(x-(o.x+14*o.scale),y-(o.y+14*o.scale));
  if(d<dist){dist=d;candidate=i;}
 });
 if(candidate!==-1&&dist<=26){
  found.add(candidate);
  indicator(candidate,'A');indicator(candidate,'B');
  tone(570+found.size*105,.07);
  $('msg').textContent=['好眼力！','還有三個','抓到第三個！','差最後一個！','完成！'][found.size-1];
  stats();
  if(found.size===5){playing=false;clearInterval(timer);setTimeout(win,550);}
 }else{
  mistakes++;seconds=Math.max(0,seconds-6);tone(180,.1);$('msg').textContent='這裡沒有不同，扣 6 秒';
  const el=$('scene'+side);el.classList.remove('shake');void el.offsetWidth;el.classList.add('shake');
  stats();if(seconds<=0)lose();
 }
}
function setTimer(){clearInterval(timer);timer=setInterval(()=>{if(!playing)return;seconds--;stats();if(seconds<=0)lose();},1000);}
function openLevel(index){
 current=index;level=makeLevel(current);found=new Set();mistakes=0;usedHints=0;
 seconds=Math.max(94,145-Math.floor(current*.48));
 hints=current<16?2:current<60?1:0;playing=true;
 lastPlayed=index;save();overlay.hidden=true;
 $('msg').textContent='每張圖有 5 處不同，仔細觀察場景細節！';
 draw();setTimer();
}
function showModal(icon,title,html,action,other='',otherAction=null){
 playing=false;clearInterval(timer);
 $('modalEmoji').textContent=icon;$('modalTitle').textContent=title;$('modalText').innerHTML=html;
 $('levelPicker').hidden=true;$('modalMain').textContent=action.label;$('modalMain').onclick=action.fn;
 $('modalSecond').hidden=!other;
 if(other){$('modalSecond').textContent=other;$('modalSecond').onclick=otherAction;}
 overlay.hidden=false;
}
function win(){
 let star=mistakes===0&&usedHints===0&&seconds>40?3:mistakes<3&&seconds>20?2:1;
 best[current]=Math.max(Number(best[current])||0,star);
 unlocked=Math.max(unlocked,Math.min(TOTAL,current+2));save();
 const done=current===99;
 showModal(done?'🏆':'🎉',done?'100 關挑戰完成！':'第 '+(current+1)+' 關通關！',
 '<div style="font-size:28px;margin:4px 0">'+'⭐'.repeat(star)+'</div><b>'+level.cfg.title+'</b><br>剩 '+seconds+' 秒 · 失誤 '+mistakes+' 次<br><small>每個場景只有兩關，下一關會換全新主題！</small>',
 {label:done?'再從第一關挑戰':'下一關 →',fn:()=>openLevel(done?0:current+1)},'關卡地圖',picker);
}
function lose(){
 tone(160,.2);
 showModal('⏰','時間到','找到 '+found.size+' / 5 處。<br>可以先用兩倍放大觀察，再挑戰這一關。',
 {label:'↻ 重新挑戰',fn:()=>openLevel(current)},'關卡地圖',picker);
}
function picker(){
 showModal('🗺️','100 關地圖','50 種獨立主題 × 2 種視角。<br>目前解鎖 '+unlocked+' / 100 關。',
 {label:'返回本關',fn:()=>openLevel(current)});
 const p=$('levelPicker');p.hidden=false;p.innerHTML='';
 for(let i=0;i<TOTAL;i++){
  const b=document.createElement('button');b.textContent=i<unlocked?String(i+1):'🔒';
  b.title=SCENES[i%50].title+(i>=50?' · 另一個視角':'');
  if(i===current)b.classList.add('active');
  if(i>=unlocked)b.classList.add('locked');b.disabled=i>=unlocked;
  b.onclick=()=>openLevel(i);p.append(b);
 }
}
$('levelsBtn').onclick=picker;
$('hintBtn').onclick=()=>{
 if(!playing||hints<=0)return;
 const i=Array.from({length:5},(_,j)=>j).find(j=>!found.has(j));
 if(i===undefined)return;
 hints--;usedHints++;indicator(i,'A',true);indicator(i,'B',true);
 $('msg').textContent='提示光圈會顯示約 1.6 秒';stats();
};
$('zoomBtn').onclick=()=>{
 zoom=!zoom;draw();
 $('msg').textContent=zoom?'放大兩倍：左右滑動圖片，上下兩圖會同步移動':'已還原正常大小';
};
$('retryBtn').onclick=()=>openLevel(current);
$('pauseBtn').onclick=()=>{
 if(!playing)return;
 showModal('⏸️','已暫停','可以休息一下，倒數計時已停止。',
 {label:'繼續挑戰',fn:()=>{overlay.hidden=true;playing=true;stats();setTimer();}},
 '重新開始',()=>openLevel(current));
};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing)$('pauseBtn').click();});
level=makeLevel(0);draw();
showModal('👀','全新 100 關 · 場景大改版',
 '這次不再反覆使用同一排圖案。<br><b>50 種不同插畫主題</b>，每個主題只出現兩次，而且間隔 50 關。<br>每關找出 <b>5 個差異</b>；支持 2× 放大、同步捲動、自動存檔。<br><small>之前已解鎖的關卡會保留。</small>',
 {label:'開始挑戰 →',fn:()=>openLevel(0)},
 unlocked>1?'接續第 '+(lastPlayed+1)+' 關':'',unlocked>1?()=>openLevel(lastPlayed):null);
})();