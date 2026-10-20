(() => {
"use strict";
const KEY="singer-face-quiz-v1";
const $=id=>document.getElementById(id);
const el={};for(const id of ["round","correct","score","portrait","photoMessage","photoTag","message","answer","submit","guessForm","giveup","next","result","credits","creditText","creditLink","poolInfo","restart","saveWarning","roundSize","startRound"])el[id]=$(id);
const labels=["眼睛","鼻子","嘴巴","下巴","全臉"],revealKeys=["eyes","nose","mouth","chin","full"];
let bank=[],byId=new Map(),state=null,loading=true,photoToken=0,empty=false;
const normalize=text=>String(text).normalize("NFKC").toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu,"");
function shuffle(items){const out=[...items];for(let i=out.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[out[i],out[j]]=[out[j],out[i]];}return out;}
function fresh(roundSize=10){return {version:1,roundSize,deck:shuffle(bank.map(q=>q.id)).slice(0,roundSize||bank.length),pos:0,stage:0,tried:[],finished:false,won:false,score:0,correct:0,completed:0};}
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch{el.saveWarning.hidden=false;}}
function restore(){
 try{
  const old=JSON.parse(localStorage.getItem(KEY)||"null");
  if(!old||old.version!==1||!Array.isArray(old.deck))return fresh();
  if(!Number.isInteger(old.pos)||old.pos<0||old.pos>old.deck.length)return fresh();
  const current=old.deck[old.pos],valid=[...new Set(old.deck.filter(id=>byId.has(id)))];
  // Preserve the current question when a later build removes a failed photo.
  const prior=new Set(old.deck.slice(0,old.pos));
  const done=valid.filter(id=>prior.has(id)),remaining=valid.filter(id=>!prior.has(id));
  const roundSize=[10,20].includes(old.roundSize)?old.roundSize:0;
  const extra=old.pos===old.deck.length?[]:bank.map(q=>q.id).filter(id=>!valid.includes(id));
  const deck=[...done,...remaining,...shuffle(extra)].slice(0,roundSize||bank.length);
  const same=byId.has(current);
  return {version:1,roundSize,deck,pos:Math.min(done.length,deck.length),
   stage:same&&Number.isInteger(old.stage)?Math.max(0,Math.min(4,old.stage)):0,
   tried:same&&Array.isArray(old.tried)?old.tried.filter(x=>typeof x==="string").slice(0,8):[],
   finished:same&&old.finished===true,won:same&&old.won===true,
   score:Number.isFinite(old.score)?Math.max(0,Math.min(1e7,old.score)):0,
   correct:Number.isInteger(old.correct)?Math.max(0,old.correct):0,
   completed:Number.isInteger(old.completed)?Math.max(0,old.completed):done.length};
 }catch{el.saveWarning.hidden=false;return fresh();}
}
function question(){return state&&byId.get(state.deck[state.pos]);}
function message(text,kind=""){el.message.textContent=text;el.message.className="message "+kind;}
function reveal(){
 const q=question();if(!q)return;
 const rect=q.reveal?.[revealKeys[state.stage]]||[[.08,.275,.92,.425],[.08,.275,.92,.59],[.08,.275,.92,.74],[.08,.275,.92,.92],[0,0,1,1]][state.stage];
 const r=state.finished?[0,0,1,1]:rect;
 el.portrait.style.clipPath="inset("+(r[1]*100)+"% "+((1-r[2])*100)+"% "+((1-r[3])*100)+"% "+(r[0]*100)+"%)";
 el.photoTag.textContent=state.finished?"答案揭曉":"線索 "+(state.stage+1)+"／5 · "+labels[state.stage];
 document.querySelectorAll("[data-stage]").forEach(node=>{
  const n=Number(node.dataset.stage);node.classList.toggle("active",n===state.stage&&!state.finished);
  node.classList.toggle("past",n<state.stage||state.finished);
  if(n===state.stage&&!state.finished)node.setAttribute("aria-current","step");else node.removeAttribute("aria-current");
 });
}
function showResult(){
 const q=question();if(!q)return;
 el.result.replaceChildren();
 const name=document.createElement("strong");name.textContent=q.name;
 const note=document.createElement("p");note.textContent=state.won?"你認出來了！本題 +"+((5-state.stage)*20)+" 分":"下次再認出這張熟悉的臉。";
 el.result.append(name,note);el.result.hidden=false;
 const a=q.attribution||{};
 el.creditText.textContent=[a.artist,a.credit,a.license,a.attribution].filter(Boolean).join(" · ");
 const source=a.source||a.article;
 if(source&&/^https:\/\//.test(source)){el.creditLink.href=source;el.creditLink.hidden=false;}else{el.creditLink.removeAttribute("href");el.creditLink.hidden=true;}
 el.credits.hidden=!source;el.credits.open=false;
}
function render(){
 el.round.textContent=state?String(Math.min(state.pos+1,state.deck.length))+"／"+state.deck.length:"—";
 el.correct.textContent=state?.correct||0;el.score.textContent=state?.score||0;
 const q=question(),active=!!q&&!state.finished&&!loading;
 el.answer.disabled=!active;el.submit.disabled=!active;el.giveup.disabled=!active;
 el.guessForm.hidden=!!state?.finished;el.giveup.hidden=!!state?.finished;
 el.next.hidden=!state?.finished||!q;el.result.hidden=!state?.finished||!q;
 if(!state?.finished)el.credits.hidden=true;
 if(q){reveal();if(state.finished)showResult();}
}
function finish(won){
 if(loading||state.finished||!question())return;
 state.finished=true;state.won=won;state.completed++;
 if(won){state.correct++;state.score+=(5-state.stage)*20;}
 save();render();message(won?"答對了！":"答案是…",won?"good":"");
 el.next.focus({preventScroll:true});
}
function end(){
 loading=false;el.portrait.hidden=true;el.photoTag.hidden=true;el.photoMessage.hidden=false;
 el.photoMessage.textContent="這輪挑戰完成！";
 el.guessForm.hidden=true;el.giveup.hidden=true;el.next.hidden=true;el.credits.hidden=true;
 el.result.hidden=false;el.result.textContent="答對 "+state.correct+" 位歌手，累積 "+state.score+" 分。";
 message("選擇關數，再開始新回合吧！","good");
 el.round.textContent=state.deck.length+"／"+state.deck.length;el.correct.textContent=state.correct;el.score.textContent=state.score;
}
function loadQuestion(){
 const q=question();if(!q){end();return;}
 const token=++photoToken;loading=true;
 el.answer.value="";el.result.hidden=true;el.credits.hidden=true;el.credits.open=false;
 el.portrait.hidden=true;el.photoTag.hidden=true;el.photoMessage.hidden=false;el.photoMessage.textContent="照片載入中…";
 render();message(state.finished?(state.won?"答對了！":"答案揭曉"):state.stage===0?"先從眼睛開始。":"繼續上一題：目前已露出"+labels[state.stage]+"。");
 const ready=()=>{
  if(token!==photoToken)return;loading=false;el.portrait.hidden=false;el.photoTag.hidden=false;el.photoMessage.hidden=true;render();
 };
 el.portrait.onload=ready;
 el.portrait.onerror=()=>{
  if(token!==photoToken)return;loading=true;el.photoMessage.textContent="這張照片暫時無法載入。";message("點「下一位」跳過，不扣分。","error");
  el.next.hidden=false;el.next.disabled=false;el.giveup.hidden=true;el.guessForm.hidden=true;
 };
 el.portrait.src=q.photo;
 if(el.portrait.complete&&el.portrait.naturalWidth)ready();
}
el.guessForm.addEventListener("submit",event=>{
 event.preventDefault();const q=question();if(!q||loading||state.finished)return;
 const answer=normalize(el.answer.value);
 if(!answer){message("先輸入歌手的名字。");return;}
 if([q.name,...q.aliases].some(alias=>normalize(alias)===answer)){finish(true);return;}
 if(state.tried.includes(answer)){message("這個名字猜過了，換一個試試。");return;}
 state.tried.push(answer);
 if(state.stage===4){finish(false);return;}
 state.stage++;save();render();message("還不是喔，多給你一個線索："+labels[state.stage]+"。","error");
 el.answer.select();
});
el.giveup.addEventListener("click",()=>finish(false));
el.next.addEventListener("click",()=>{
 if(!question())return;
 state.pos++;state.stage=0;state.tried=[];state.finished=false;state.won=false;
 save();loadQuestion();
});
function startRound(){
 if(empty){location.reload();return;}
 if(!bank.length)return;
 if(state&&(state.pos>0||state.tried.length||state.finished)&&!confirm("確定重新開始？本輪進度與積分將會重設。"))return;
 state=fresh(el.roundSize.value==="all"?0:Number(el.roundSize.value));save();loadQuestion();
}
el.restart.addEventListener("click",startRound);
el.startRound.addEventListener("click",startRound);
async function init(){
 try{
  const response=await fetch("./questions.json",{cache:"no-store"});
  if(!response.ok)throw Error("Question bank unavailable");
  const payload=await response.json();
  bank=(payload.questions||[]).filter(q=>q.id&&q.name&&Array.isArray(q.aliases)&&/^photos\/[a-zA-Z0-9_-]+\.jpg$/.test(q.photo));
  if(!bank.length)throw Error("No prepared photos");
  byId=new Map(bank.map(q=>[q.id,q]));state=restore();save();
  el.roundSize.value=state.roundSize===0?"all":String(state.roundSize);
  el.roundSize.querySelector('option[value="all"]').textContent="全部（"+bank.length+" 關）";
  el.roundSize.disabled=false;el.startRound.disabled=false;
  el.poolInfo.textContent=bank.length+" 位歌手 · 隨機不重複 · 自動記錄進度";
  loadQuestion();
 }catch{
  empty=true;el.photoMessage.textContent="歌手照片正在準備中";
  message("題庫準備好後，點「重新載入」即可開始。");
  el.restart.textContent="重新載入";el.poolInfo.textContent="猜歌手・五官挑戰";
 }
}
init();
})();