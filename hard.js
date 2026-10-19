(function(){
"use strict";
const $=id=>document.getElementById(id);
const TOTAL=100, VW=420, VH=260;
const labels=["古書圖書館","雨夜霓虹城","玻璃溫室","深夜壽司店","電子晶片工坊","星際導航圖","水晶收藏室","甜點展示櫃","深海生物站","復古玩具店"];
const styles=[
 ["#2d283f","#49405a","#71617b","#221e35","#e8bd78","#a7d3d8"],
 ["#102a42","#25445a","#3d6272","#10263c","#fdcf78","#ff7898"],
 ["#213d35","#426a51","#6d9070","#1b382f","#d4e7a9","#e9ae79"],
 ["#47323d","#765160","#9e6c62","#352832","#ffca86","#92c5bf"],
 ["#172d40","#234d5d","#346c73","#0b2535","#86eac5","#e1ab60"],
 ["#172d52","#2e4274","#354e80","#0e2448","#d1e3ff","#ffc489"],
 ["#3c2e5a","#625187","#8b78ac","#261c42","#f6dba4","#7fded7"],
 ["#543144","#815363","#ae7876","#412536","#ffe5af","#df9dbd"],
 ["#123b53","#23627b","#4888a0","#102e49","#afecea","#ffcc91"],
 ["#433c51","#61576b","#897d8c","#2d293c","#f6d99f","#8ccfca"]
];
const R=(x,y,w,h,color,other="")=>'<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="'+color+'" '+other+'/>';
const C=(x,y,r,color,other="")=>'<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+color+'" '+other+'/>';
const L=(x,y,X,Y,color,w=1.5,other="")=>'<path d="M'+x+' '+y+' L'+X+' '+Y+'" fill="none" stroke="'+color+'" stroke-width="'+w+'" stroke-linecap="round" '+other+'/>';
const P=(points,color,other="")=>'<polygon points="'+points+'" fill="'+color+'" '+other+'/>';
const E=(x,y,rx,ry,color)=>'<ellipse cx="'+x+'" cy="'+y+'" rx="'+rx+'" ry="'+ry+'" fill="'+color+'"/>';
function rand(seed){let n=seed|0||1;return()=>{n^=n<<13;n^=n>>>17;n^=n<<5;return(n>>>0)/4294967296;};}
function makeLevel(lv){
 const theme=Math.floor(lv/10),r=rand((lv+1337)*419841),cols=10+Math.floor(lv/10),rows=6+Math.floor(lv/23);
 const x0=10,y0=31,cw=400/cols,ch=217/rows,items=[];
 for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){
  items.push({x:x0+x*cw,y:y0+y*ch,cx:x0+(x+.5)*cw,cy:y0+(y+.5)*ch,w:cw,h:ch,row:y,col:x,kind:Math.floor(r()*5),hue:Math.floor(r()*5),shift:Math.floor(r()*3),seed:r()});
 }
 let picks=[],tries=0;
 while(picks.length<5&&tries++<2000){
  let i=Math.floor(r()*items.length),c=items[i];
  if(picks.includes(i))continue;
  if(picks.every(k=>Math.hypot(c.cx-items[k].cx,c.cy-items[k].cy)>48))picks.push(i);
 }
 if(picks.length<5){for(let i=0;i<items.length&&picks.length<5;i++)if(!picks.includes(i))picks.push(i);}
 return {lv,theme,cols,rows,items,diffs:picks,style:styles[theme]};
}
function symbol(c,theme,v,style){
 const a=style[4],b=style[5],f=["#f4a5a7","#f4d191","#9cd9c5","#a7b9ee","#dca9ea"][c.hue];
 const ink="#243244",lite="#f7efd9";
 let s=R(1,1,22,22,style[1],'rx="2" opacity=".62"');
 switch(theme){
 case 0:{
  s+=R(2,4,6,16,f,'rx="1"')+R(9,2,6,18,a,'rx="1"')+R(16,5,6,15,b,'rx="1"');
  s+=L(3.5,8,6.5,8,ink,1)+L(3.5,11,6.5,11,ink,1)+L(10.5,7,13.5,7,ink,1);
  s+=L(17,10,21,10,ink,1)+R(11,12,3,1.7,v?style[2]:lite)+R(17.5,14,3,1.4,lite);break;
 }
 case 1:{
  s+=R(3,2,18,20,ink,'rx="1"')+R(5,4,6,6,f)+R(13,4,6,6,b)+R(5,12,6,7,a)+R(13,12,6,7,f);
  s+=R(6,5,1.5,4,ink)+R(14,13,1.5,5,ink);
  s+=R(v?17:15,6,2,2,lite)+L(4,21,20,21,a,1);break;
 }
 case 2:{
  s+=R(6,13,12,9,f,'rx="2"')+R(5,13,14,2,a)+L(12,13,12,4,ink,1.2);
  s+=E(8,7,4,2.6,b)+E(16,6,4,2.8,a)+E(9,11,3,2,b);
  s+=E(v?17:15,11,2.2,1.6,v?style[2]:a)+L(9,17,15,17,ink,1);break;
 }
 case 3:{
  s+=E(12,12,10,9,lite)+E(12,12,7.5,6.5,ink);
  s+=E(12,12,5,4.5,f)+C(9,11,1,a)+C(14,14,1,a)+C(13,9,1,a);
  s+=v?"":C(10,14,.95,lite);s+=L(3,21,21,21,a,1);break;
 }
 case 4:{
  s+=R(3,3,18,18,ink,'rx="2"')+R(7,7,10,10,f,'rx="1"');
  s+=L(1,6,7,6,b,1.4)+L(17,11,23,11,b,1.4)+L(12,1,12,7,b,1.4)+L(9,17,9,23,b,1.4);
  s+=C(12,12,2,ink)+C(8,8,1,a)+C(16,15,1,a)+(v?"":L(3,15,7,15,b,1.3));break;
 }
 case 5:{
  s+=C(12,12,8,ink)+L(4,12,20,12,b,.8)+L(12,4,12,20,b,.8);
  s+=C(8,7,2,f)+C(16,15,1.6,a)+C(7,17,1,b);
  s+=L(17,6,17,11,lite,1.2)+(v?"":L(14.5,8.5,19.5,8.5,lite,1.2));
  s+=C(19,19,1.1,lite);break;
 }
 case 6:{
  s+=P("12,2 20,9 17,19 7,19 4,9",f)+P("12,2 12,19 4,9",b,'opacity=".55"');
  s+=L(4,9,20,9,lite,.8)+L(12,2,17,19,ink,.6)+L(12,2,7,19,ink,.6);
  s+=C(12,8,1.3,v?style[2]:lite)+C(19,4,1,b);break;
 }
 case 7:{
  s+=E(12,20,10,2,ink)+R(5,12,14,7,a,'rx="2"')+E(12,12,7,4,f);
  s+=C(12,7,3,b)+C(9,11,1,lite)+C(15,13,1,lite);
  s+=v?C(15,8,.7,style[2]):C(15,8,1.4,lite);break;
 }
 case 8:{
  s+=E(12,12,7,4.5,f)+P("5,12 1,8 1,16",b)+P("12,9 16,5 16,11",a);
  s+=C(15,11,1.1,ink)+L(9,14,12,15,lite,1);
  s+=C(5,4,1.4,a)+C(9,3,.8,b)+(v?"":C(17,5,1.3,b));break;
 }
 case 9:{
  s+=R(5,5,14,13,b,'rx="2"')+R(8,1,8,5,f,'rx="2"')+R(8,18,3,4,ink)+R(14,18,3,4,ink);
  s+=C(9,10,1.5,lite)+C(15,10,1.5,lite)+L(9,14,15,14,ink,1.2);
  s+=C(12,3,1.3,v?style[2]:a);break;
 }
 }
 return s;
}
function renderSvg(level,side){
 const st=level.style;
 let svg='<svg viewBox="0 0 420 260" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="'+labels[level.theme]+' 圖片'+(side?'B':'A')+'">';
 svg+='<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="'+st[0]+'"/><stop offset="1" stop-color="'+st[1]+'"/></linearGradient></defs>';
 svg+=R(0,0,420,260,'url(#bg)')+R(0,0,420,25,st[3]);
 svg+='<text x="13" y="17" fill="'+st[4]+'" font-family="system-ui,sans-serif" font-size="11" font-weight="800" letter-spacing="1.5">'+labels[level.theme]+'</text>';
 svg+='<text x="405" y="17" fill="'+st[5]+'" font-family="system-ui,sans-serif" font-size="10" text-anchor="end">STAGE '+String(level.lv+1).padStart(3,"0")+'</text>';
 for(let i=0;i<level.rows;i++){
  const y=31+i*(217/level.rows);
  svg+=R(7,y,406,217/level.rows,st[2],'opacity="'+(i%2?'.16':'.26')+'"');
  svg+=L(6,y+217/level.rows-2,414,y+217/level.rows-2,st[4],.9,'opacity=".34"');
 }
 level.items.forEach((c,i)=>{
  const isDiff=side===1&&level.diffs.includes(i);
  const scaleX=(c.w-3)/24,scaleY=(c.h-3)/24;
  svg+='<g transform="translate('+(c.x+1.5).toFixed(2)+' '+(c.y+1.5).toFixed(2)+') scale('+scaleX.toFixed(4)+' '+scaleY.toFixed(4)+')">'+symbol(c,level.theme,isDiff,st)+'</g>';
 });
 return svg+'</svg>';
}
const $modal=$("modal");
let current=0,active=null,found=new Set(),playing=false,timer=null,seconds=0,hints=0,errors=0,unlocked=1,best={},zoom=false,lastPlayed=0;
try{
 unlocked=Math.max(1,Math.min(100,Number(localStorage.getItem("eye_unlocked"))||1));
 best=JSON.parse(localStorage.getItem("eye_best")||"{}");
 lastPlayed=Math.max(0,Math.min(unlocked-1,Number(localStorage.getItem("eye_last_played"))||unlocked-1));
}catch(e){}
function save(){
 try{localStorage.setItem("eye_unlocked",String(unlocked));localStorage.setItem("eye_best",JSON.stringify(best));localStorage.setItem("eye_last_played",String(lastPlayed));}catch(e){}
}
function setText(){
 $("lv").textContent=String(current+1).padStart(3,"0")+" / 100";
 $("found").textContent=found.size+" / 5";
 $("time").textContent=Math.max(0,seconds);
 $("bar").style.width=(found.size*20)+"%";
 $("title").textContent=labels[active.theme]+" · 極難";
 $("hintBtn").textContent="💡 提示（"+hints+"）";
 $("hintBtn").disabled=hints<1||!playing;
 $("zoomBtn").textContent=zoom?"↙ 縮小":"🔎 放大 2×";
}
function mark(i,side,hint=false){
 const el=$("spots"+side),c=active.items[active.diffs[i]];if(!el||!c)return;
 const ring=document.createElement("div");ring.className="ring"+(hint?" hintRing":"");
 ring.style.left=(c.cx/VW*100)+"%";ring.style.top=(c.cy/VH*100)+"%";
 el.append(ring);if(hint)setTimeout(()=>ring.remove(),1600);
}
let lockScroll=false;
function render(){
 ["A","B"].forEach((name,side)=>{
  const el=$("scene"+name);
  el.classList.toggle("zoomed",zoom);
  el.innerHTML='<div class="stage" id="stage'+name+'">'+renderSvg(active,side)+'<div class="spots" id="spots'+name+'"></div></div>';
  const stage=$("stage"+name);
  stage.addEventListener("click",e=>{
   if(!playing)return;
   const rect=stage.getBoundingClientRect(),x=(e.clientX-rect.left)*VW/rect.width,y=(e.clientY-rect.top)*VH/rect.height;
   tap(x,y,name);
  });
  for(const i of found)mark(i,side===0?"A":"B");
  el.onscroll=()=>{
   if(!zoom||lockScroll)return;
   lockScroll=true;const partner=$("scene"+(name==="A"?"B":"A"));
   partner.scrollLeft=el.scrollLeft;partner.scrollTop=el.scrollTop;
   lockScroll=false;
  };
 });
 setText();
}
function tap(x,y,side){
 let which=-1,d=Infinity;
 for(let j=0;j<5;j++){
  if(found.has(j))continue;
  const p=active.items[active.diffs[j]],dist=Math.hypot(x-p.cx,y-p.cy);
  if(dist<d){d=dist;which=j;}
 }
 if(which>=0&&d<Math.max(12,17-current*.045)){
  found.add(which);mark(which,"A");mark(which,"B");
  beep(660,.07);$("msg").textContent=["抓到了！","還有 3 個！","漂亮！","最後一個！","完美！"][found.size-1];
  setText();
  if(found.size===5){playing=false;clearInterval(timer);setTimeout(win,550);}
 }else{
  seconds=Math.max(0,seconds-6);errors++;$("msg").textContent="這裡沒有不同！扣 6 秒";
  const el=$("scene"+side);el.classList.remove("shake");void el.offsetWidth;el.classList.add("shake");
  beep(160,.1);setText();if(seconds<=0)lose();
 }
}
let audio=null;
function beep(freq,duration){try{audio??=new(window.AudioContext||window.webkitAudioContext)();const o=audio.createOscillator(),g=audio.createGain();o.frequency.value=freq;g.gain.setValueAtTime(.04,audio.currentTime);g.gain.exponentialRampToValueAtTime(.001,audio.currentTime+duration);o.connect(g).connect(audio.destination);o.start();o.stop(audio.currentTime+duration);}catch(e){}}
function loop(){clearInterval(timer);timer=setInterval(()=>{if(!playing)return;seconds--;setText();if(seconds<=0)lose();},1000);}
function load(lv){
 current=lv;active=makeLevel(lv);found=new Set();
 seconds=Math.max(70,140-Math.floor(lv*.67));
 hints=lv<15?2:lv<55?1:0;errors=0;playing=true;
 lastPlayed=current;save();
 $modal.hidden=true;$("msg").textContent="找出 5 個極細微差異";
 render();loop();
}
function show(emoji,title,desc,action,secondary="",onSecond=null){
 playing=false;clearInterval(timer);
 $("modalEmoji").textContent=emoji;$("modalTitle").textContent=title;$("modalText").innerHTML=desc;
 $("levelPicker").hidden=true;$("modalMain").textContent=action.text;$("modalMain").onclick=action.fn;
 $("modalSecond").hidden=!secondary;
 if(secondary){$("modalSecond").textContent=secondary;$("modalSecond").onclick=onSecond;}
 $modal.hidden=false;
}
function win(){
 beep(850,.22);
 const totalHints=current<15?2:current<55?1:0;
 const stars=errors===0&&hints===totalHints&&seconds>35?3:errors<3&&seconds>20?2:1;
 best[current]=Math.max(best[current]||0,stars);
 unlocked=Math.max(unlocked,Math.min(100,current+2));
 save();
 const done=current===99;
 show(done?"🏆":"🎉",done?"100 關全數通關！":"第 "+(current+1)+" 關完成！",
 '<div style="font-size:27px;margin:8px 0">'+"⭐".repeat(stars)+'</div>剩餘 <b>'+seconds+'</b> 秒，點錯 <b>'+errors+'</b> 次。<p>越往後物件越密、細節越小。</p>',
 {text:done?"從第 1 關重玩":"下一關 →",fn:()=>load(done?0:current+1)},"選擇關卡",picker);
}
function lose(){
 beep(150,.2);
 show("⏰","時間到！","已找到 "+found.size+" / 5 處差異。<br>可以開啟 2× 放大查看細節。",
 {text:"↻ 再試一次",fn:()=>load(current)},"選擇關卡",picker);
}
function picker(){
 show("🗺️","百關挑戰","已解鎖 "+unlocked+" / 100 關。既有進度會保留。",{text:"返回本關",fn:()=>load(current)});
 const p=$("levelPicker");p.hidden=false;p.innerHTML="";
 for(let i=0;i<100;i++){
  const btn=document.createElement("button");btn.textContent=i<unlocked?String(i+1):"🔒";
  btn.disabled=i>=unlocked;if(i===current)btn.classList.add("active");
  if(i>=unlocked)btn.classList.add("locked");
  btn.onclick=()=>load(i);p.append(btn);
 }
}
$("levelsBtn").onclick=picker;
$("hintBtn").onclick=()=>{
 if(!playing||hints<=0)return;
 let idx=Array.from({length:5},(_,i)=>i).find(i=>!found.has(i));
 if(idx===undefined)return;
 hints--;mark(idx,"A",true);mark(idx,"B",true);
 $("msg").textContent="黃色圈圈是提示位置！";setText();
};
$("zoomBtn").onclick=()=>{
 zoom=!zoom;render();
 $("msg").textContent=zoom?"已放大 2 倍，可滑動查看細節（兩張圖同步）":"已恢復正常大小";
};
$("retryBtn").onclick=()=>load(current);
$("pauseBtn").onclick=()=>{
 if(!playing)return;
 show("⏸️","遊戲暫停","暫停期間不會扣時間。",
 {text:"繼續挑戰",fn:()=>{$modal.hidden=true;playing=true;loop();setText();}},
 "重新挑戰",()=>load(current));
};
document.addEventListener("visibilitychange",()=>{if(document.hidden&&playing)$("pauseBtn").click();});
active=makeLevel(0);render();
show("🕵️","地獄級找碴 · 100 關",
 "這版不再是明顯的物件交換！<br>每關從 <b>60–190 個細節</b> 中找出 <b>5 處微小變化</b>。<br>可按 <b>放大 2×</b>，上下圖會一起捲動。<br>點錯扣 6 秒，過關自動存檔。",
 {text:"開始挑戰 →",fn:()=>load(0)},
 unlocked>1?"接續上次進度（第 "+(lastPlayed+1)+" 關）":"",unlocked>1?()=>load(lastPlayed):null);
})();