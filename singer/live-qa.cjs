const assert=require('node:assert/strict');
const fs=require('node:fs');
const puppeteer=require('puppeteer-core');
(async()=>{
 const url='https://brant9972.github.io/find-diff/singer/';
 const files=['questions.json','actors.json','variety.json','creators.json'];
 const banks=await Promise.all(files.map(async f=>{const r=await fetch(url+f,{cache:'no-store'});assert(r.ok,f);return await r.json()}));
 const people=[...new Map(banks.flatMap(b=>b.questions).map(q=>[q.id,q])).values()];
 assert.equal(people.length,1000);
 const hints=await (await fetch(url+'hints.json',{cache:'no-store'})).json();
 for(const q of people)assert(hints.entries[q.id]);
 const executable=['/usr/bin/google-chrome','/usr/bin/chromium'].find(p=>fs.existsSync(p));
 const browser=await puppeteer.launch({executablePath:executable,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();await page.setViewport({width:390,height:844});
  await page.goto(url,{waitUntil:'networkidle0'});
  await page.waitForFunction(()=>!document.getElementById('answer').disabled);
  const broken=await page.evaluate(async qs=>{
   const failures=[];
   for(let i=0;i<qs.length;i+=20){
    const results=await Promise.all(qs.slice(i,i+20).map(q=>new Promise(resolve=>{const im=new Image();im.onload=()=>resolve(im.naturalWidth>=180?null:q.id);im.onerror=()=>resolve(q.id);im.src=q.photo;})));
    failures.push(...results.filter(Boolean));
   }
   return failures;
  },people);
  assert.deepEqual(broken,[]);
  for(const [mode,count] of [['singer',449],['actor',511],['variety',95],['creator',13],['mixed',1000]]){
   await page.select('#quizMode',mode);await page.select('#roundSize','all');await page.click('#startRound');
   await page.waitForFunction(()=>!document.getElementById('answer').disabled);
   const state=await page.evaluate(()=>JSON.parse(localStorage.getItem('singer-face-quiz-v1')));
   assert.equal(state.mode,mode);assert.equal(state.deck.length,count);assert.equal(new Set(state.deck).size,count);
   assert(await page.$eval('#poolInfo',(e,n)=>e.textContent.includes(String(n)),count));
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  fs.mkdirSync('qa-output',{recursive:true});await page.screenshot({path:'qa-output/live-1000-mobile.png',fullPage:true});
  console.log('PASS LIVE: 1000 deployed portraits, sourced hints, all five selectors, correct counts, unique mixed deck, mobile width');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

