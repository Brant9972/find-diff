/* Run in GitHub Actions against the committed site, without external image requests. */
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),http=require("node:http");
const puppeteer=require("puppeteer-core");
const root=path.resolve(__dirname,"..");
let realQuestions=[];
const roster=JSON.parse(fs.readFileSync(path.join(__dirname,"roster.json")));
assert(roster.singers.length>=300);
assert.equal(new Set(roster.singers.map(x=>x.id)).size,roster.singers.length);
assert.equal(new Set(roster.singers.map(x=>x.name)).size,roster.singers.length);
if(fs.existsSync(path.join(__dirname,"questions.json"))){
 const real=JSON.parse(fs.readFileSync(path.join(__dirname,"questions.json")));
 realQuestions=real.questions;
 assert.equal(real.playable,real.questions.length);
 assert(real.playable<=1000);
 for(const q of real.questions){
  assert(roster.singers.some(s=>s.id===q.id&&s.name===q.name));
  assert(fs.existsSync(path.join(__dirname,q.photo)),q.id+" missing portrait");
  assert(q.attribution.source&&q.attribution.license,q.id+" missing attribution");
 }
}
const realHints=JSON.parse(fs.readFileSync(path.join(__dirname,"hints.json")));
for(const q of realQuestions)assert(realHints.entries[q.id]?.singer?.title,"Missing singer work hint: "+q.id);
const actorBank=JSON.parse(fs.readFileSync(path.join(__dirname,"actors.json")));
const actorRoster=JSON.parse(fs.readFileSync(path.join(__dirname,"actors-roster.json"))).actors;
assert.equal(actorBank.playable,actorBank.questions.length);
assert(actorBank.playable<=1000);
assert(actorBank.playable>=20,"Actor mode needs at least 20 playable portraits");
assert.equal(new Set(actorBank.questions.map(q=>q.id)).size,actorBank.playable);
assert.equal(new Set(actorBank.questions.map(q=>q.name)).size,actorBank.playable);
for(const q of actorBank.questions){
 assert(actorRoster.some(a=>a.id===q.id&&a.name===q.name));
 assert(realHints.entries[q.id]?.actor?.title,"Missing actor work hint: "+q.id);
 assert(fs.existsSync(path.join(__dirname,q.photo)),q.id+" missing actor portrait");
 assert(q.attribution.source&&q.attribution.license);
}
const additionalBanks=[];
for(const [role,file,rosterFile,rosterKey] of [["variety","variety.json","variety-roster.json","variety"],["creator","creators.json","creators-roster.json","creators"]]){
 if(!fs.existsSync(path.join(__dirname,file)))continue;
 const bank=JSON.parse(fs.readFileSync(path.join(__dirname,file)));
 const roster=JSON.parse(fs.readFileSync(path.join(__dirname,rosterFile)))[rosterKey];
 assert.equal(bank.playable,bank.questions.length);
 assert(bank.playable>0&&bank.playable<=1000);
 assert.equal(new Set(bank.questions.map(q=>q.id)).size,bank.playable);
 assert.equal(new Set(bank.questions.map(q=>q.name)).size,bank.playable);
 for(const q of bank.questions){
  assert(roster.some(p=>p.id===q.id&&p.name===q.name),"Unknown "+role+" identity: "+q.id);
  assert(realHints.entries[q.id]?.[role]?.title,"Missing "+role+" work hint: "+q.id);
  assert(fs.existsSync(path.join(__dirname,q.photo)),q.id+" missing portrait");
  assert(q.attribution.source&&q.attribution.license,q.id+" missing attribution");
 }
 additionalBanks.push(...bank.questions);
}
realQuestions=[...new Map([...realQuestions,...actorBank.questions,...additionalBanks].map(q=>[q.id,q])).values()];
const eligibility=JSON.parse(fs.readFileSync(path.join(__dirname,"eligibility-review.json"))).entries;
for(const q of realQuestions){
 const r=eligibility[q.id];
 assert(r&&r.status==="approved"&&r.name===q.name&&r.reason&&r.sources.length,"Unapproved Taiwan eligibility: "+q.id);
}
assert.equal(new Set(realQuestions.map(q=>q.attribution.article)).size,realQuestions.length,"Same canonical person counted twice");
assert.equal(new Set(realQuestions.map(q=>q.attribution.source)).size,realQuestions.length,"Same portrait used for different people");
const rejectedPortraits=JSON.parse(fs.readFileSync(path.join(__dirname,"photo-review.json"))).rejected||[];
const sourceKey=url=>decodeURIComponent(url.split("/wiki/").pop()).replaceAll("_"," ").toLowerCase();
const rejectedKeys=new Set(rejectedPortraits.map(e=>sourceKey(e.source)));
const preserveExisting=process.argv.includes("--preserve-existing-portraits");
const priorPortraits=preserveExisting?JSON.parse(fs.readFileSync(path.join(__dirname,"actor-replacements-40-baseline-known-issues.json"))).questions:[];
for(const q of realQuestions){
 const unchangedPrior=["a1324","a1347"].includes(q.id)&&priorPortraits.some(p=>JSON.stringify(p)===JSON.stringify(q));
 if(rejectedKeys.has(sourceKey(q.attribution.source))&&unchangedPrior)console.warn("UNCHANGED BASELINE PORTRAIT OUTSIDE FORTY-PERSON SCOPE:",q.id);
 assert(!rejectedKeys.has(sourceKey(q.attribution.source))||unchangedPrior,"Previously rejected portrait reused: "+q.id);
}
let hintUnavailable=false,optionalUnavailable=false;
const missingHints=new Set();
const actorFixtures={questions:Array.from({length:25},(_,i)=>({id:"qa"+(101+i),name:"演員"+(i+1),aliases:["Actor "+(i+1)],photo:"photos/qa"+(101+i)+".jpg"}))};
const varietyFixtures={questions:[{id:"qa201",name:"吳宗憲",aliases:["綜藝測試"],photo:"photos/qa201.jpg"},{id:"qa202",name:"曾國城",aliases:[],photo:"photos/qa202.jpg"}]};
const creatorFixtures={questions:[{id:"qa301",name:"蔡阿嘎",aliases:["創作者測試"],photo:"photos/qa301.jpg"},{id:"qa302",name:"阿滴",aliases:[],photo:"photos/qa302.jpg"}]};
const fixtures={questions:[
 {id:"qa1",name:"測試甲",aliases:["Test Singer","测试甲"],photo:"photos/qa1.jpg"},
 {id:"qa2",name:"測試乙",aliases:["Test Two"],photo:"photos/qa2.jpg"}
]};
const svg='<svg xmlns="http://www.w3.org/2000/svg" width="600" height="720"><rect width="600" height="720" fill="#6b4d80"/><circle cx="220" cy="250" r="20" fill="white"/><circle cx="380" cy="250" r="20" fill="white"/></svg>';
const server=http.createServer((req,res)=>{
 const relative=decodeURIComponent(req.url.split("?")[0]);
 const file=path.join(root,relative.endsWith("/")?relative+"index.html":relative);
 if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
 fs.readFile(file,(err,data)=>{
  if(err){res.writeHead(404);res.end();return;}
  const ext=path.extname(file),types={".html":"text/html; charset=utf-8",".js":"text/javascript",".css":"text/css",".json":"application/json",".jpg":"image/jpeg"};
  res.setHeader("Content-Type",types[ext]||"application/octet-stream");res.end(data);
 });
});
(async()=>{
 await new Promise(resolve=>server.listen(8099,"127.0.0.1",resolve));
 const executable=["/usr/bin/google-chrome","/usr/bin/chromium","/usr/bin/chromium-browser"].find(p=>fs.existsSync(p));
 if(!executable)throw Error("No preinstalled Chrome");
 const browser=await puppeteer.launch({executablePath:executable,args:["--no-sandbox","--disable-dev-shm-usage"]});
 try{
  const page=await browser.newPage();await page.setViewport({width:390,height:844,deviceScaleFactor:2,isMobile:true,hasTouch:true});
  const errors=[];page.on("pageerror",e=>errors.push(String(e)));
  if(realQuestions.length){
   await page.goto("http://127.0.0.1:8099/singer/");
   await page.waitForFunction(()=>!document.getElementById("answer").disabled);
   const broken=await page.evaluate(async questions=>{
    const outcomes=await Promise.all(questions.map(q=>new Promise(resolve=>{
     const image=new Image();image.onload=()=>resolve((["actor_refresh_remaining40_20261022","expansion1000_20261022"].includes(q.batchId)?image.naturalWidth===600&&image.naturalHeight===720:image.naturalWidth>=180&&image.naturalHeight>=180)?null:q.id);
     image.onerror=()=>resolve(q.id);image.src=new URL(q.photo,location.href).href;
    })));
    return outcomes.filter(Boolean);
   },realQuestions);
   assert.deepEqual(broken,[],"Real portraits failed to decode in browser");
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
   fs.mkdirSync(path.join(root,"qa-output"),{recursive:true});
   await page.screenshot({path:path.join(root,"qa-output/singer-mobile-real.png"),fullPage:true});
  }
  await page.setRequestInterception(true);
  page.on("request",req=>{
   if(req.url().endsWith("/singer/hints.json")){
    if(hintUnavailable)return req.respond({status:503,contentType:"application/json",body:"{}"});
    const entries={};
    for(const [mode,bank] of [["singer",fixtures],["actor",actorFixtures],["variety",varietyFixtures],["creator",creatorFixtures]]){
     for(const q of bank.questions){
      if(missingHints.has(q.id))continue;
      entries[q.id]??={};entries[q.id][mode]={title:({singer:"線索歌曲",actor:"線索電影",variety:"線索節目",creator:"線索頻道"})[mode],kind:({singer:"音樂作品",actor:"影視作品",variety:"綜藝節目",creator:"網路作品"})[mode],source:"https://example.com/work"};
     }
    }
    return req.respond({status:200,contentType:"application/json",body:JSON.stringify({entries})});
   }
   for(const [file,bank] of [["variety.json",varietyFixtures],["creators.json",creatorFixtures]]){
    if(req.url().endsWith("/singer/"+file))return req.respond({status:optionalUnavailable&&file==="variety.json"?503:200,contentType:"application/json",body:JSON.stringify(bank)});
   }
   if(req.url().endsWith("/singer/actors.json"))return req.respond({status:200,contentType:"application/json",body:JSON.stringify(actorFixtures)});
   if(req.url().endsWith("/singer/questions.json"))return req.respond({status:200,contentType:"application/json",body:JSON.stringify(fixtures)});
   if(/\/photos\/qa\d+\.jpg$/.test(req.url()))return req.respond({status:200,contentType:"image/svg+xml",body:svg});
   req.continue();
  });
  await page.goto("http://127.0.0.1:8099/singer/");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.evaluate(()=>{
   localStorage.setItem("singer-face-quiz-v1",JSON.stringify({version:1,deck:["qa1","qa2"],pos:0,stage:0,tried:[],finished:false,won:false,score:0,correct:0,completed:0}));
  });
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  const snapshot=()=>page.evaluate(()=>JSON.parse(localStorage.getItem("singer-face-quiz-v1")));
  await page.evaluate(()=>localStorage.setItem("singer-face-quiz-v1",JSON.stringify({version:1,mode:"singer",roundSize:10,deck:["removed-eligibility-id","qa1","qa2"],pos:0,stage:4,hintUsed:true,tried:["舊猜測"],finished:true,won:false,score:80,correct:1,completed:1})));
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  const migrated=await snapshot();
  assert(!migrated.deck.includes("removed-eligibility-id"));assert.equal(migrated.deck[0],"qa1");
  assert.equal(migrated.stage,0);assert.equal(migrated.hintUsed,false);assert.equal(migrated.score,80);
  await page.evaluate(()=>localStorage.setItem("singer-face-quiz-v1",JSON.stringify({version:1,deck:["qa1","qa2"],pos:0,stage:0,tried:[],finished:false,won:false,score:0,correct:0,completed:0})));
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  async function guess(value){
   await page.$eval("#answer",(e,value)=>{e.value=value;},value);
   await page.$eval("#guessForm",e=>e.requestSubmit());
  }
  await guess("");assert.equal((await snapshot()).stage,0,"Blank answer consumed clue");
  await guess("錯誤答案一");assert.equal((await snapshot()).stage,1);
  await guess("錯誤答案一");assert.equal((await snapshot()).stage,1,"Repeated guess consumed clue");
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).stage,1,"Reload lost clue progress");
  await guess(" TEST-SINGER! ");
  assert.equal((await snapshot()).correct,1,"Alias case/punctuation normalization failed");
  assert.equal((await snapshot()).score,80);
  assert.equal(await page.$eval("#result strong",e=>e.textContent),"測試甲");
  await page.click("#next");await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).deck[(await snapshot()).pos],"qa2");
  for(let i=0;i<4;i++)await guess("錯誤答案"+i);
  assert.equal((await snapshot()).stage,4);
  assert.equal((await snapshot()).finished,false,"Full-face clue was skipped");
  await guess("仍然答錯");assert.equal((await snapshot()).finished,true);
  assert.equal((await snapshot()).score,80,"Failure changed score");
  await page.click("#next");
  assert.equal(await page.$eval("#photoMessage",e=>e.textContent),"這輪挑戰完成！");
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),"Mobile layout overflows");
  // A restored finished answer must not grant points for a second submission.
  await page.evaluate(()=>{
   localStorage.setItem("singer-face-quiz-v1",JSON.stringify({version:1,deck:["qa1","qa2"],pos:0,stage:0,tried:[],finished:true,won:true,score:100,correct:1,completed:1}));
  });
  await page.reload();await page.waitForFunction(()=>!document.getElementById("portrait").hidden);
  await guess("測試甲");assert.equal((await snapshot()).score,100,"Restored round scored twice");
  // New round sizes must stop at the chosen count and survive a growing bank.
  page.on("dialog",dialog=>dialog.accept());
  fixtures.questions=Array.from({length:30},(_,i)=>({id:"qa"+(i+1),name:"歌手"+(i+1),aliases:["Test "+(i+1)],photo:"photos/qa"+(i+1)+".jpg"}));
  await page.evaluate(()=>localStorage.clear());
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).deck.length,10,"New round did not default to 10");
  assert.equal(new Set((await snapshot()).deck).size,10,"10-question round repeats singers");
  assert.equal(await page.$eval("#round",e=>e.textContent),"1／10");
  await guess("猜錯一次");
  fixtures.questions.push({id:"qa31",name:"歌手31",aliases:[],photo:"photos/qa31.jpg"});
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).stage,1,"10-question clue progress was lost");
  assert.equal((await snapshot()).deck.length,10,"New bank entries extended a fixed round");
  for(let i=0;i<10;i++){
   const saved=await snapshot(),q=fixtures.questions.find(q=>q.id===saved.deck[saved.pos]);
   await guess(q.name);await page.click("#next");
   if(i<9)await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  }
  assert.equal((await snapshot()).pos,10);
  assert.equal((await snapshot()).correct,10);
  assert.equal((await snapshot()).score,980);
  assert.equal(await page.$eval("#photoMessage",e=>e.textContent),"這輪挑戰完成！");
  await page.reload();await page.waitForFunction(()=>!document.getElementById("startRound").disabled);
  assert.equal((await snapshot()).deck.length,10,"Completed round grew on reload");
  await page.select("#roundSize","20");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).deck.length,20);
  assert.equal((await snapshot()).roundSize,20);
  assert.equal(new Set((await snapshot()).deck).size,20);
  await guess("錯誤提示");
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal(await page.$eval("#roundSize",e=>e.value),"20");
  assert.equal((await snapshot()).stage,1);
  assert.equal((await snapshot()).deck.length,20);
  for(let i=0;i<20;i++){
   await page.click("#giveup");await page.click("#next");
   if(i<19)await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  }
  assert.equal((await snapshot()).pos,20);
  assert.equal((await snapshot()).score,0);
  assert.equal(await page.$eval("#photoMessage",e=>e.textContent),"這輪挑戰完成！");
  await page.select("#roundSize","all");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).deck.length,31,"All-question mode was removed");
  assert.equal((await snapshot()).roundSize,0);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"Round controls overflow mobile width");
  // Categories are a draft until explicitly started. Old saves stay in singer mode.
  assert.equal((await snapshot()).mode,"singer");
  const singerDeck=(await snapshot()).deck;
  actorFixtures.questions.push({...fixtures.questions[0]},{...fixtures.questions[1]});
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.select("#quizMode","actor");
  assert.deepEqual((await snapshot()).deck,singerDeck,"Draft category reset the active round");
  assert.equal((await snapshot()).mode,"singer");
  await page.select("#roundSize","20");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  let saved=await snapshot();
  const actorIds=new Set(actorFixtures.questions.map(q=>q.id));
  assert.equal(saved.mode,"actor");
  assert.equal(saved.deck.length,20);
  assert(saved.deck.every(id=>actorIds.has(id)),"Actor mode drew a singer-only question");
  assert.equal(await page.$eval(".edition",e=>e.textContent),"華語演員篇");
  await guess("錯誤提示");
  const actorCurrent=saved.deck[0];
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  saved=await snapshot();
  assert.equal(saved.mode,"actor");
  assert.equal(saved.stage,1);
  assert.equal(saved.deck[0],actorCurrent);
  assert.equal(await page.$eval("#quizMode",e=>e.value),"actor");
  for(let i=0;i<20;i++){
   const current=await snapshot(),q=actorFixtures.questions.find(q=>q.id===current.deck[current.pos]);
   await guess(q.name);await page.click("#next");
   if(i<19)await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  }
  assert.equal((await snapshot()).pos,20);
  assert.equal((await snapshot()).correct,20);
  assert.equal((await snapshot()).score,1980);
  await page.select("#quizMode","mixed");await page.select("#roundSize","10");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  saved=await snapshot();
  assert.equal(saved.mode,"mixed");
  assert.equal(saved.deck.length,10);
  assert.equal(new Set(saved.deck).size,10,"Shared singer/actors repeated");
  assert(saved.deck.some(id=>id.startsWith("qa1")&&Number(id.slice(2))>=101),"Mixed round has no actor-only questions");
  assert(saved.deck.some(id=>!actorIds.has(id)),"Mixed round has no singer-only questions");
  await guess("混合錯答");
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).mode,"mixed");
  assert.equal((await snapshot()).stage,1);
  await page.select("#roundSize","all");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  saved=await snapshot();
  assert.equal(saved.deck.length,60,"Mixed bank did not deduplicate shared people");
  assert.equal(new Set(saved.deck).size,60);
  await page.select("#quizMode","singer");await page.select("#roundSize","10");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert((await snapshot()).deck.every(id=>fixtures.questions.some(q=>q.id===id)),"Singer mode drew an actor-only question");
  await page.select("#quizMode","actor");await page.select("#roundSize","10");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.setViewport({width:320,height:740,deviceScaleFactor:2,isMobile:true,hasTouch:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"Category controls overflow narrow mobile width");
  await page.setViewport({width:390,height:844,deviceScaleFactor:2,isMobile:true,hasTouch:true});
  // Work hints are optional, charge only this question and survive reload.
  await page.select("#quizMode","singer");await page.select("#roundSize","10");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  const singerAnswer=async()=>{const s=await snapshot();return fixtures.questions.find(q=>q.id===s.deck[s.pos]).name;};
  assert(await page.$eval("#hintText",e=>e.hidden),"Hint leaked before use");
  await page.click("#hintButton");
  saved=await snapshot();
  assert.equal(saved.hintUsed,true);assert.equal(saved.stage,0);assert.equal(saved.score,0);
  assert(await page.$eval("#hintText",e=>e.textContent.includes("音樂作品")));
  assert(await page.$eval("#hintButton",e=>e.disabled));
  await page.$eval("#hintButton",e=>e.dispatchEvent(new MouseEvent("click",{bubbles:true})));
  await guess("多露一點");assert.equal((await snapshot()).stage,1);
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).hintUsed,true);
  assert(await page.$eval("#hintText",e=>!e.hidden));
  await guess(await singerAnswer());
  assert.equal((await snapshot()).score,60,"Hint plus one wrong guess should award 60");
  assert(await page.$eval("#result",e=>e.textContent.includes("+60 分")));
  await page.reload();await page.waitForFunction(()=>!document.getElementById("portrait").hidden);
  assert.equal((await snapshot()).score,60,"Finished hint answer scored twice on reload");
  await page.$eval("#hintButton",e=>e.dispatchEvent(new MouseEvent("click",{bubbles:true})));
  assert.equal((await snapshot()).score,60);
  await page.click("#next");await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).hintUsed,false,"Hint penalty carried into next question");
  assert(await page.$eval("#hintText",e=>e.hidden),"Previous answer's work clue leaked");
  await guess(await singerAnswer());assert.equal((await snapshot()).score,160,"Unassisted score changed");
  await page.click("#next");await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.click("#hintButton");
  for(let i=0;i<4;i++)await guess("提示後錯答"+i);
  assert.equal((await snapshot()).stage,4);assert.equal((await snapshot()).finished,false);
  await guess(await singerAnswer());assert.equal((await snapshot()).score,170,"Hint score floor should be 10");
  await page.click("#next");await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.click("#hintButton");await page.click("#giveup");
  assert.equal((await snapshot()).score,170,"Giving up after a hint changed total score");
  await page.click("#next");await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  saved=await snapshot();missingHints.add(saved.deck[saved.pos]);
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert(await page.$eval("#hintButton",e=>e.disabled),"Missing hint can be clicked");
  await page.$eval("#hintButton",e=>e.dispatchEvent(new MouseEvent("click",{bubbles:true})));
  assert.equal((await snapshot()).hintUsed,false,"Missing hint incurred a penalty");
  await guess(await singerAnswer());assert.equal((await snapshot()).score,270);
  await page.click("#next");await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.click("#hintButton");hintUnavailable=true;
  await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).hintUsed,true,"Hint file outage erased used status");
  assert.equal((await snapshot()).score,270);
  await guess(await singerAnswer());assert.equal((await snapshot()).score,350);
  hintUnavailable=false;missingHints.clear();
  await page.reload();await page.waitForFunction(()=>!document.getElementById("portrait").hidden);
  await page.select("#quizMode","actor");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  await page.click("#hintButton");
  assert(await page.$eval("#hintText",e=>e.textContent.includes("影視作品")),"Actor mode showed a music hint");
  await page.select("#quizMode","mixed");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  saved=await snapshot();
  await page.click("#hintButton");
  const expectedKind=[[actorFixtures,"影視作品"],[fixtures,"音樂作品"],[varietyFixtures,"綜藝節目"],[creatorFixtures,"網路作品"]].find(([bank])=>bank.questions.some(q=>q.id===saved.deck[saved.pos]))[1];
  assert(await page.$eval("#hintText",(e,kind)=>e.textContent.includes(kind),expectedKind),"Mixed mode chose the wrong work hint");
  // New category rounds isolate their people and use category-specific hints.
  for(const [mode,bank,kind,label] of [["variety",varietyFixtures,"綜藝節目","綜藝"],["creator",creatorFixtures,"網路作品","網路創作者"]]){
   await page.select("#quizMode",mode);await page.select("#roundSize","all");await page.click("#startRound");
   await page.waitForFunction(()=>!document.getElementById("answer").disabled);
   const s=await snapshot();
   assert.equal(s.mode,mode);assert.equal(s.deck.length,bank.questions.length);
   assert(s.deck.every(id=>bank.questions.some(q=>q.id===id)),"Category leaked unrelated people");
   assert.equal(await page.$eval("#quizMode option:last-child",e=>e.value),"mixed","Mixed must remain last for keyboard End");
   assert.equal(await page.title(),"猜"+label+"・五官挑戰");
   await page.click("#hintButton");
   assert(await page.$eval("#hintText",(e,k)=>e.textContent.includes(k),kind));
   await page.reload();await page.waitForFunction(()=>!document.getElementById("answer").disabled);
   assert.equal((await snapshot()).mode,mode);assert.equal((await snapshot()).hintUsed,true);
   const current=await snapshot();await guess(bank.questions.find(q=>q.id===current.deck[current.pos]).name);
   assert.equal((await snapshot()).score,80,"New category scoring changed");
  }
  // One missing optional bank cannot block another category or the legacy game.
  optionalUnavailable=true;await page.evaluate(()=>localStorage.clear());await page.reload();
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).mode,"singer");
  assert(await page.$eval('#quizMode option[value="variety"]',e=>e.disabled));
  assert(await page.$eval('#quizMode option[value="creator"]',e=>!e.disabled));
  await page.select("#quizMode","creator");await page.click("#startRound");
  await page.waitForFunction(()=>!document.getElementById("answer").disabled);
  assert.equal((await snapshot()).mode,"creator");
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"Work clue overflows mobile");
  assert.equal(errors.length,0,errors.join("\n"));
  fs.mkdirSync(path.join(root,"qa-output"),{recursive:true});
  await page.screenshot({path:path.join(root,"qa-output/singer-mobile.png"),fullPage:true});
  console.log("PASS: all real portraits, categories, rounds, work hints, optional scoring, no double charge, reload, 10-point floor, missing hints, source outage and mobile layout.");
 }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>server.close());

