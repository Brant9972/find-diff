const puppeteer=require('puppeteer-core');
const assert=require('node:assert/strict');
(async()=>{
 const chrome=process.env.CHROME_BIN||'/usr/bin/google-chrome';
 const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-gpu']});
 try {
 const page=await browser.newPage(); await page.setViewport({width:390,height:844,isMobile:true,deviceScaleFactor:2});
 const errs=[];page.on('pageerror',e=>errs.push(String(e)));
 await page.goto('http://127.0.0.1:8099/pilot/',{waitUntil:'networkidle2'});
 await page.waitForFunction(()=>document.querySelector('#modalTitle')?.textContent==='這次真的來盲測',{timeout:25000});
 const summary=await page.evaluate(async()=>{
  const all=[];
  for(let i=0;i<SCENES.length;i++){
   const stage={name:SCENES[i].name,spots:[]};
   for(let k=0;k<SCENES[i].diffs.length;k++){
    const map=await HITMAP.one(SCENES[i].diffs[k]);
    const actual=HITMAP.contains(map,map.centre.x,map.centre.y,1);
    const nearby=HITMAP.contains(map,map.centre.x+9,map.centre.y,18);
    stage.spots.push({count:map.count,centre:map.centre,bounds:map.bounds,centred:actual,nearby});
   }
   all.push(stage);
  }
  return all;
 });
 assert.equal(summary.length,10);assert(summary.every(l=>l.spots.length===5));
 for(const s of summary)for(const p of s.spots){
  assert(p.count>=3, s.name+': no pixels');
  assert(p.centred,s.name+': centre off actual visual difference');
  assert(p.centre.x>=0&&p.centre.y>=0&&p.centre.x<=800&&p.centre.y<=460,s.name+': invalid coordinate');
 }
 await page.click('#modalGo');
 await page.waitForFunction(()=>document.querySelector('#message')?.textContent.includes('已校準完成'),{timeout:25000});
 const marker=summary[0].spots[3].centre;
 const rect=await page.$eval('#stageB',e=>{const b=e.getBoundingClientRect();return {left:b.left,top:b.top,width:b.width,height:b.height}});
 await page.mouse.click(rect.left+marker.x/800*rect.width,rect.top+marker.y/460*rect.height);
 await page.waitForFunction(()=>document.querySelector('#count')?.textContent==='1 / 5',{timeout:5000});
 // An obviously unrelated tap does not score a second correct answer.
 await new Promise(r=>setTimeout(r,500));
 await page.mouse.click(rect.left+795/800*rect.width,rect.top+455/460*rect.height);
 const count=await page.$eval('#count',e=>e.textContent);
 assert.equal(count,'1 / 5','unrelated tap should not register');
 assert.equal(errs.length,0,errs.join('\n'));
 console.log(JSON.stringify({result:'PASS',scenes:summary.length,checkedSpots:summary.reduce((n,x)=>n+x.spots.length,0),firstStageSteam:marker,mobileTapTest:'PASS',nonspotRejected:true},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});