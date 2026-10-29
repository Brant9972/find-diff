const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),puppeteer=require('puppeteer-core');
const base='https://brant9972.github.io/find-diff/singer/';
const files=['questions.json','actors.json','variety.json','hints.json'];
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const expected=Object.fromEntries(files.map(f=>[f,JSON.parse(fs.readFileSync(path.join(__dirname,f),'utf8'))]));
 let live,ready=false;
 for(let attempt=0;attempt<28;attempt++){
  try{
   live=Object.fromEntries(await Promise.all(files.map(async f=>{
    const res=await fetch(base+f+'?qa='+encodeURIComponent(process.env.GITHUB_SHA||'manual')+'&try='+attempt,{cache:'no-store',signal:AbortSignal.timeout(20000)});
    assert(res.ok,f+' HTTP '+res.status);return [f,await res.json()];
   })));
   ready=files.every(f=>JSON.stringify(expected[f])===JSON.stringify(live[f]));
   if(ready)break;
  }catch(e){console.log('Waiting for Pages:',String(e).slice(0,200));}
  console.log('Pages content not yet equal to checked-out SHA, attempt',attempt+1);await pause(12000);
 }
 assert(ready,'GitHub Pages did not deploy the exact current question/hint JSON');
 const banks=files.slice(0,3).map(f=>live[f].questions);
 const mixed=[...new Map(banks.flat().map(q=>[q.id,q])).values()];
 assert.equal(mixed.length,new Set(mixed.map(q=>q.name)).size,'Duplicate person names');
 for(const q of mixed){assert(live['hints.json'].entries[q.id],q.id+' missing hint');assert(q.photo&&q.reveal?.full,q.id+' missing photo/reveal');}
 for(const id of ['t1500_0255','t1500_0563'])assert(mixed.some(q=>q.id===id),id+' missing');
 const chrome=['/usr/bin/google-chrome','/usr/bin/chromium','/usr/bin/chromium-browser'].find(fs.existsSync);
 assert(chrome,'Chrome missing');
 const browser=await puppeteer.launch({executablePath:chrome,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();await page.setViewport({width:390,height:844,deviceScaleFactor:2,isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(base+'?qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>!document.getElementById('answer').disabled,{timeout:60000});
  assert.equal(await page.$('#quizMode option[value="creator"]'),null);
  const broken=await page.evaluate(async people=>(await Promise.all(people.map(q=>new Promise(resolve=>{
   const im=new Image();im.onload=()=>resolve(im.naturalWidth>=180?null:q.id);im.onerror=()=>resolve(q.id);im.src=q.photo;
  })))).filter(Boolean),mixed.filter(q=>q.id.startsWith('t1500_')));
  assert.deepEqual(broken,[],'New images broken');
  for(const [mode,count] of [['singer',banks[0].length],['actor',banks[1].length],['variety',banks[2].length],['mixed',mixed.length]]){
   await page.select('#quizMode',mode);await page.select('#roundSize','all');await page.click('#startRound');
   await page.waitForFunction(()=>!document.getElementById('answer').disabled,{timeout:20000});
   const state=await page.evaluate(()=>JSON.parse(localStorage.getItem('singer-face-quiz-v1')));
   assert.equal(state.mode,mode);assert.equal(state.deck.length,count);assert.equal(new Set(state.deck).size,count);
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile horizontal overflow');
  assert.deepEqual(errors,[],'Browser JS errors');
  fs.mkdirSync('qa-output',{recursive:true});await page.screenshot({path:'qa-output/live-mobile.png',fullPage:true});
  console.log('PASS LIVE',JSON.stringify({uniquePeople:mixed.length,bankCounts:banks.map(b=>b.length),expansionPhotosChecked:mixed.filter(q=>q.id.startsWith('t1500_')).length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});