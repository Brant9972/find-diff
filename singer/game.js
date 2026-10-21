(() => {
"use strict";
const KEY="singer-face-quiz-v1";
const $=id=>document.getElementById(id);
const el={};for(const id of ["round","correct","score","portrait","photoMessage","photoTag","message","answer","submit","guessForm","giveup","next","result","credits","creditText","creditLink","poolInfo","restart","saveWarning","roundSize","startRound","quizMode","hintPanel","hintButton","hintText","hintNote"])el[id]=$(id);
const labels=["眼睛","鼻子","嘴巴","下巴","全臉"],revealKeys=["eyes","nose","mouth","chin","full"];
let bank=[],singerBank=[],actorBank=[],byId=new Map(),state=null,loading=true,photoToken=0,empty=false,hints={};
const normalize=text=>String(text).normalize("NFKC").toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu,"");
function shuffle(items){const out=[...items];for(let i=out.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[out[i],out[j]]=[out[j],out[i]];}return out;}
const modeLabels={singer:"歌手",actor:"演員",mixed:"混合"};
function pool(mode){
 const items=mode==="actor"?actorBank:mode==="mixed"?[...singerBank,...actorBank]:singerBank;
 return [...new Map(items.map(q=>[q.id,q])).values()];
}
function setPool(mode){bank=pool(mode);byId=new Map(bank.map(q=>[q.id,q]));}
function makeDeck(mode,roundSize){
 const limit=roundSize||bank.length;
 if(mode!=="mixed")return shuffle(bank.map(q=>q.id)).slice(0,limit);
 // Alternate the two shuffled pools; shared singer/actors appear only once.
 const groups=[shuffle(singerBank.map(q=>q.id)),shuffle(actorBank.map(q=>q.id))];
 const ids=new Set();let turn=Math.random()<.5?0:1;
 while(ids.size<limit&&(groups[0].length||groups[1].length)){
  const group=groups[turn].length?groups[turn]:groups[1-turn];
  ids.add(group.pop());turn=1-turn;
 }
 return shuffle([...ids]);
}
function fresh(roundSize=10,mode="singer"){setPool(mode);return {version:1,mode,roundSize,deck:makeDeck(mode,roundSize),pos:0,stage:0,hintUsed:false,tried:[],finished:false,won:false,score:0,correct:0,completed:0};}
function updateRoundOption(){
 const count=pool(el.quizMode.value).length;
 el.roundSize.querySelector('option[value="all"]').textContent="全部（"+count+" 關）";
}
function showMode(){
 const mode=state.mode,label=modeLabels[mode];
 document.querySelector(".edition").textContent=mode==="mixed"?"歌手 × 演員":"華語"+label+"篇";
 document.querySelector(".eyebrow").textContent="看五官，猜"+(mode==="singer"?"聲音":"明星");
 document.querySelector(".sub").textContent="輸入"+(mode==="mixed"?"歌手或演員":label)+"名字。猜錯一次，就多露出一點。";
 document.querySelector(".play").setAttribute("aria-label","猜"+(mode==="mixed"?"明星":label)+"遊戲");
 el.portrait.alt="本題"+(mode==="mixed"?"明星":label)+"的五官線索";
 el.poolInfo.textContent=label+"模式 · "+bank.length+" 位 · 隨機不重複 · 自動記錄進度";
 document.title="猜"+(mode==="mixed"?"明星":label)+"・五官挑戰";
}
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch{el.saveWarning.hidden=false;}}
function restore(){
 try{
  const old=JSON.parse(localStorage.getItem(KEY)||"null");
  if(!old||old.version!==1||!Array.isArray(old.deck))return fresh();
  if(!Number.isInteger(old.pos)||old.pos<0||old.pos>old.deck.length)return fresh();
  const mode=["singer","actor","mixed"].includes(old.mode)?old.mode:"singer";
  setPool(mode);
  const current=old.deck[old.pos],valid=[...new Set(old.deck.filter(id=>byId.has(id)))];
  // Preserve the current question when a later build removes a failed photo.
  const prior=new Set(old.deck.slice(0,old.pos));
  const done=valid.filter(id=>prior.has(id)),remaining=valid.filter(id=>!prior.has(id));
  const roundSize=[10,20].includes(old.roundSize)?old.roundSize:0;
  const extra=old.pos===old.deck.length?[]:bank.map(q=>q.id).filter(id=>!valid.includes(id));
  const deck=[...done,...remaining,...shuffle(extra)].slice(0,roundSize||bank.length);
  const same=byId.has(current);
  return {version:1,mode,roundSize,deck,pos:Math.min(done.length,deck.length),
   stage:same&&Number.isInteger(old.stage)?Math.max(0,Math.min(4,old.stage)):0,
   hintUsed:same&&old.hintUsed===true,
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
function points(){return Math.max(10,(5-state.stage)*20-(state.hintUsed?20:0));}
function workHint(){
 const q=question(),entry=q&&hints[q.id];
 const hint=state.mode==="singer"?entry?.singer:state.mode==="actor"?entry?.actor:entry?.actor||entry?.singer;
 return hint&&typeof hint.title==="string"&&hint.title.trim()&&typeof hint.kind==="string"?hint:null;
}
function renderHint(){
 const q=question(),hint=workHint();
 el.hintPanel.hidden=!q||state.finished&&!state.hintUsed;
 el.hintButton.hidden=!!state.finished;
 el.hintButton.disabled=loading||state.finished||state.hintUsed||!hint;
 el.hintButton.textContent=state.hintUsed?"作品提示已使用":hint?"看作品提示":"這題暫無作品提示";
 el.hintText.hidden=!state.hintUsed;
 el.hintText.textContent=state.hintUsed?(hint?hint.kind+"：《"+hint.title+"》":"提示暫時無法載入，使用狀態已保留。"):"";
 el.hintNote.textContent=state.hintUsed?(state.finished?"已使用作品提示。":"本題答對可得 "+points()+" 分；五官線索照常揭露。"):hint?"本題答對少 20 分，最低 10 分；不影響五官線索。":"本題照常計分，五官線索仍可使用。";
}
el.hintButton.addEventListener("click",()=>{
 if(loading||!question()||state.finished||state.hintUsed||!workHint())return;
 state.hintUsed=true;save();renderHint();
});
function showResult(){
 const q=question();if(!q)return;
 el.result.replaceChildren();
 const name=document.createElement("strong");name.textContent=q.name;
 const note=document.createElement("p");note.textContent=state.won?"你認出來了！本題 +"+points()+" 分":"下次再認出這張熟悉的臉。";
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
 renderHint();
 if(q){reveal();if(state.finished)showResult();}
}
function finish(won){
 if(loading||state.finished||!question())return;
 state.finished=true;state.won=won;state.completed++;
 if(won){state.correct++;state.score+=points();}
 save();render();message(won?"答對了！":"答案是…",won?"good":"");
 el.next.focus({preventScroll:true});
}
function end(){
 loading=false;el.hintPanel.hidden=true;el.portrait.hidden=true;el.photoTag.hidden=true;el.photoMessage.hidden=false;
 el.photoMessage.textContent="這輪挑戰完成！";
 el.guessForm.hidden=true;el.giveup.hidden=true;el.next.hidden=true;el.credits.hidden=true;
 el.result.hidden=false;el.result.textContent="答對 "+state.correct+" 題，累積 "+state.score+" 分。";
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
 if(!answer){message("先輸入人物的名字。");return;}
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
 state.pos++;state.stage=0;state.hintUsed=false;state.tried=[];state.finished=false;state.won=false;
 save();loadQuestion();
});
function startRound(){
 if(empty){location.reload();return;}
 if(!bank.length)return;
 if(state&&(state.pos>0||state.tried.length||state.finished||state.hintUsed)&&!confirm("確定重新開始？本輪進度與積分將會重設。"))return;
 state=fresh(el.roundSize.value==="all"?0:Number(el.roundSize.value),el.quizMode.value);save();showMode();loadQuestion();
}
el.restart.addEventListener("click",startRound);
el.startRound.addEventListener("click",startRound);
el.quizMode.addEventListener("change",updateRoundOption);
async function init(){
 try{
  const responses=await Promise.all(["./questions.json","./actors.json"].map(url=>fetch(url,{cache:"no-store"})));
  if(responses.some(r=>!r.ok))throw Error("Question bank unavailable");
  const payloads=await Promise.all(responses.map(r=>r.json()));
  const valid=payload=>(payload.questions||[]).filter(q=>q.id&&q.name&&Array.isArray(q.aliases)&&/^photos\/[a-zA-Z0-9_-]+\.jpg$/.test(q.photo));
  singerBank=valid(payloads[0]);actorBank=valid(payloads[1]);
  if(!singerBank.length||!actorBank.length)throw Error("No prepared photos");
  try{
   const response=await fetch("./hints.json",{cache:"no-store"});
   if(response.ok)hints=(await response.json()).entries||{};
  }catch{hints={};}
  setPool("singer");state=restore();save();
  el.quizMode.value=state.mode;el.quizMode.disabled=false;
  el.roundSize.value=state.roundSize===0?"all":String(state.roundSize);
  updateRoundOption();el.roundSize.disabled=false;el.startRound.disabled=false;
  showMode();
  loadQuestion();
 }catch{
  empty=true;el.photoMessage.textContent="題庫暫時無法載入";
  message("題庫準備好後，點「重新載入」即可開始。");
  el.restart.textContent="重新載入";el.poolInfo.textContent="猜明星・五官挑戰";
 }
}
init();
})();