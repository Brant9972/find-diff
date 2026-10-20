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
 assert(real.playable<=300);
 for(const q of real.questions){
  assert(roster.singers.some(s=>s.id===q.id&&s.name===q.name));
  assert(fs.existsSync(path.join(__dirname,q.photo)),q.id+" missing portrait");
  assert(q.attribution.source&&q.attribution.license,q.id+" missing attribution");
 }
}
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
     const image=new Image();image.onload=()=>resolve(image.naturalWidth===600&&image.naturalHeight===720?null:q.id);
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
  assert.equal(errors.length,0,errors.join("\n"));
  fs.mkdirSync(path.join(root,"qa-output"),{recursive:true});
  await page.screenshot({path:path.join(root,"qa-output/singer-mobile.png"),fullPage:true});
  console.log("PASS: real photos, aliases, clue/score persistence, 10/20-question endings, bank growth, all mode and mobile layout.");
 }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>server.close());
