(()=>{
"use strict";
const $=id=>document.getElementById(id),N=10,saveKey='eye_blind_pilot_v1';
let current=0,found=new Set(),unlocked=1,best={},last=0,seconds=165,hints=2,wrong=0,usedHints=0,playing=false,zoom=false,timer=null,syncLock=false,audio=null,hitmaps=[],generation=0,lastTapAt=0,loading=false;
try{const old=JSON.parse(localStorage.getItem(saveKey)||'{}');unlocked=Math.min(10,Math.max(1,old.unlocked||1));best=old.best||{};last=Math.min(unlocked-1,Math.max(0,old.last||0));}catch(e){}
const store=()=>{try{localStorage.setItem(saveKey,JSON.stringify({unlocked,best,last}));}catch(e){}};
function beep(freq=600,len=.09){try{audio??=new(window.AudioContext||window.webkitAudioContext)();const o=audio.createOscillator(),g=audio.createGain();o.type='sine';o.frequency.value=freq;g.gain.setValueAtTime(.035,audio.currentTime);g.gain.exponentialRampToValueAtTime(.0001,audio.currentTime+len);o.connect(g).connect(audio.destination);o.start();o.stop(audio.currentTime+len);}catch(e){}}
const scene=()=>SCENES[current];
async function prepareHits(level,token){
 loading=true;hitmaps=[];
 $('message').textContent='正在校準 5 個差異的實際位置…';
 stats();
 try{
   const maps=await Promise.all(SCENES[level].diffs.map(d=>HITMAP.one(d)));
   if(token!==generation||level!==current)return;
   if(maps.length!==5||maps.some(v=>!v?.mask||v.count<3))throw new Error('incomplete masks');
   hitmaps=maps;loading=false;playing=true;lastTapAt=0;
   $('message').textContent='已校準完成！請仔細比對兩張圖片。';
   stats();loop();
 }catch(error){
   if(token!==generation)return;
   loading=false;
   dialog('⚠️','判定資料載入失敗','為避免你明明答對卻無法點中，這關已暫停。請重新載入頁面再試。',{label:'重新整理',fn:()=>location.reload()});
 }
}
function picture(side){let s=scene();return '<svg viewBox="0 0 800 460" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" role="img" aria-label="'+s.name+'，圖片'+(side?'B':'A')+'">'+defs+s.base()+s.diffs.map(d=>d[3](side)).join('')+R(0,0,800,460,'url(#grain)')+'</svg>';}
function mark(i,side,hint=false){
 const hit=hitmaps[i],el=$('rings'+side);if(!el||!hit)return;
 let ring=document.createElement('span');ring.className='ring'+(hint?' hint':'');
 ring.style.left=(hit.centre.x/8)+'%';ring.style.top=(hit.centre.y/460*100)+'%';
 ring.style.width=(hit.ringWidth/800*100)+'%';
 el.appendChild(ring);if(hint)setTimeout(()=>ring.remove(),1500);
}
function stats(){
$('level').textContent=String(current+1).padStart(2,'0')+' / 10';
$('count').textContent=found.size+' / 5';$('seconds').textContent=Math.max(0,seconds);
$('sceneTitle').textContent=scene().name;$('sceneSub').textContent=scene().subtitle;
[...$('dots').children].forEach((d,i)=>d.classList.toggle('done',i<found.size));
$('hintBtn').textContent='💡 提示 '+hints;$('hintBtn').disabled=!playing||loading||hints===0;
$('zoomBtn').textContent=zoom?'↙ 縮小':'⌕ 放大 2×';
}
function render(){
for(const side of ['A','B']){
const frame=$('frame'+side),stage=$('stage'+side);
frame.classList.toggle('zoom',zoom);
stage.innerHTML=picture(side==='B')+'<div class="rings" id="rings'+side+'"></div>';
stage.onclick=e=>{if(!playing)return;const b=stage.getBoundingClientRect();const x=(e.clientX-b.left)/b.width*800,y=(e.clientY-b.top)/b.height*460;tap(x,y,side);};
frame.onscroll=()=>{if(!zoom||syncLock)return;syncLock=true;const other=$('frame'+(side==='A'?'B':'A'));other.scrollLeft=frame.scrollLeft;other.scrollTop=frame.scrollTop;setTimeout(()=>syncLock=false,0);};
found.forEach(i=>mark(i,side));
}
stats();
}
function tap(x,y,side){
 if(!playing||loading||hitmaps.length!==5)return;
 // 400ms cooldown blocks frantic tapping without making deliberate tapping feel sluggish.
 const now=Date.now();if(now-lastTapAt<400)return;lastTapAt=now;
 const sw=$('stage'+side).getBoundingClientRect().width||390;
 // A strict finger-size allowance: ~8 CSS px, smaller in image coordinates when zoomed.
 const tolerance=Math.min(21,Math.max(10.5,800/sw*8));
 let ix=-1;
 for(let i=0;i<5;i++){
   if(found.has(i))continue;
   if(HITMAP.contains(hitmaps[i],x,y,tolerance)){ix=i;break;}
 }
 if(ix>=0){
   found.add(ix);beep(590+found.size*95);mark(ix,'A');mark(ix,'B');
   $('message').textContent=['找到了！','還有三處','有眼力！','剩最後一處！','全部找齊！'][found.size-1];stats();
   if(found.size===5){playing=false;clearInterval(timer);setTimeout(win,480);}
 }else{
   wrong++;seconds=Math.max(0,seconds-5);beep(180,.12);$('message').textContent='這裡沒有真正的不同，扣 5 秒';
   let el=$('frame'+side);el.classList.remove('shake');void el.offsetWidth;el.classList.add('shake');
   stats();if(seconds===0)lose();
 }
}
function loop(){clearInterval(timer);timer=setInterval(()=>{if(!playing)return;seconds--;stats();if(seconds<=0)lose();},1000);}
function load(i){
if(i<0||i>=N||i>=unlocked)return;const token=++generation;current=i;last=i;store();found=new Set();seconds=155+(i%3)*10;wrong=0;usedHints=0;hints=i<4?2:1;playing=false;loading=true;clearInterval(timer);hitmaps=[];$('overlay').hidden=true;render();prepareHits(i,token);
}
function dialog(emoji,title,html,main,alt='',altFn=null){
playing=false;clearInterval(timer);
$('emoji').textContent=emoji;$('modalTitle').textContent=title;$('modalText').innerHTML=html;
$('modalGo').textContent=main.label;$('modalGo').onclick=main.fn;
$('modalAlt').hidden=!alt;if(alt){$('modalAlt').textContent=alt;$('modalAlt').onclick=altFn;}
$('levelGrid').hidden=true;$('overlay').hidden=false;
}
function win(){let stars=(wrong===0&&usedHints===0&&seconds>55)?3:(wrong<3&&seconds>15)?2:1;
best[current]=Math.max(best[current]||0,stars);unlocked=Math.max(unlocked,Math.min(N,current+2));store();
let done=current===N-1;
dialog(done?'🏆':'🎉',done?'10 關盲測完成！':'第 '+(current+1)+' 關完成！','<div style="font-size:29px;margin-bottom:6px">'+'⭐'.repeat(stars)+'</div>'+scene().name+'<p>剩餘 '+seconds+' 秒，點錯 '+wrong+' 次。</p>',
{label:done?'重玩第 1 關':'下一關 →',fn:()=>load(done?0:current+1)},'選關',picker);
}
function lose(){beep(155,.18);dialog('⏳','這關還沒結束','這次找到了 '+found.size+' / 5 處。可以放大兩張圖仔細對照。',{label:'再試一次',fn:()=>load(current)},'選關',picker);}
function picker(){
dialog('▦','盲測關卡','這個試玩版有 10 個獨立場景，你可以重玩已解鎖的關卡。',{label:'返回目前關卡',fn:()=>load(current)});
let p=$('levelGrid');p.hidden=false;p.innerHTML='';
for(let i=0;i<N;i++){let b=document.createElement('button');b.textContent=i<unlocked?String(i+1):'🔒';b.title=SCENES[i].name;b.disabled=i>=unlocked;b.classList.toggle('active',i===current);b.classList.toggle('locked',i>=unlocked);b.onclick=()=>load(i);p.append(b);}
}
$('mapBtn').onclick=picker;
$('restartBtn').onclick=()=>load(current);
$('hintBtn').onclick=()=>{if(!playing||loading||hints<1)return;const i=scene().diffs.findIndex((d,i)=>!found.has(i));if(i<0)return;hints--;usedHints++;mark(i,'A',true);mark(i,'B',true);$('message').textContent='黃色光圈會顯示約 1.5 秒';stats();};
$('zoomBtn').onclick=()=>{zoom=!zoom;render();$('message').textContent=zoom?'已放大兩倍，可滑動圖片仔細比對。':'已恢復原始大小。';};
$('pauseBtn').onclick=()=>{if(!playing)return;dialog('⏸️','暫停中','時間已經停止，你可以休息一下。',{label:'繼續遊戲',fn:()=>{$('overlay').hidden=true;playing=true;stats();loop();}},'重玩這關',()=>load(current));};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing)$('pauseBtn').click();});
if(SCENES.length!==10||typeof HITMAP==='undefined'){dialog('⚠️','關卡載入異常','找到 '+SCENES.length+' / 10 個場景，請重新整理頁面。',{label:'重新整理',fn:()=>location.reload()});return;}
render();
dialog('👀','這次真的來盲測','<b>10 張獨立構圖</b>，每關 5 處由人工設計的差異。<br>不再有固定的出題物件，也不需要故事敘述。<br><b>上下任一張都能點，放大兩倍可同步滑動。</b><br>原本 100 關版完全不受影響。',{label:'開始第一關 →',fn:()=>load(0)},unlocked>1?'接續第 '+(last+1)+' 關':'',unlocked>1?()=>load(last):null);
})();