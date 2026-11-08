/* Regression: engineer console displays accepted names and live representative work hints. */
const assert=require("node:assert/strict"),fs=require("node:fs"),http=require("node:http"),path=require("node:path"),vm=require("node:vm");
const puppeteer=require("puppeteer-core");
const root=path.resolve(__dirname,"..");
const rel="singer/console-a11323ac9e6c9177808240d797a88257/index.html";
const html=fs.readFileSync(path.join(root,rel),"utf8");
const scriptTag=html.match(/<script>([\s\S]*?)<\/script>/);
assert(scriptTag,"Console JS missing");new vm.Script(scriptTag[1],{filename:rel});
for(const id of ["search","people","answerAliases","aliasCount","featuredWork","featuredWorkKind","featuredWorkSource","recordSelect"]){
  assert(html.includes('id="'+id+'"'),"Missing console UI field "+id);
}
const server=http.createServer((req,res)=>{
  const relPath=decodeURIComponent(req.url.split("?")[0]);
  const target=path.resolve(root,"."+relPath.replace(/\/$/,"/index.html"));
  if(!target.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  fs.readFile(target,(err,data)=>{
    if(err){res.writeHead(404);res.end();return;}
    const ext=path.extname(target);
    res.setHeader("Content-Type",({".html":"text/html; charset=utf-8",".js":"text/javascript",".json":"application/json",".jpg":"image/jpeg",".png":"image/png",".css":"text/css"})[ext]||"application/octet-stream");
    res.end(data);
  });
});
(async()=>{
  await new Promise(resolve=>server.listen(8097,"127.0.0.1",resolve));
  const chrome=["/usr/bin/google-chrome","/usr/bin/chromium","/usr/bin/chromium-browser"].find(p=>fs.existsSync(p));
  assert(chrome,"Chromium is required for console smoke test");
  const browser=await puppeteer.launch({executablePath:chrome,args:["--no-sandbox","--disable-dev-shm-usage"]});
  try{
    const page=await browser.newPage(),errors=[];
    page.on("pageerror",e=>errors.push(String(e)));
    await page.setViewport({width:390,height:844,isMobile:true,hasTouch:true,deviceScaleFactor:1});
    await page.setRequestInterception(true);
    page.on("request",request=>request.resourceType()==="image"?request.abort():request.continue());
    await page.goto("http://127.0.0.1:8097/"+rel,{waitUntil:"domcontentloaded"});
    await page.waitForFunction(()=>document.querySelector("#resultCount").textContent.startsWith("找到 "),{timeout:35000});
    async function query(text){
      await page.$eval("#search",(node,value)=>{node.value=value;node.dispatchEvent(new Event("input",{bubbles:true}));},text);
    }
    await query("馬東錫");
    await page.click('.person[data-id="kr2_20261108_09"]');
    const park=await page.evaluate(()=>({work:document.querySelector("#featuredWork").textContent,aliases:[...document.querySelectorAll("#answerAliases .alias-tag")].map(x=>x.textContent),kind:document.querySelector("#featuredWorkKind").textContent,source:document.querySelector("#featuredWorkSource").href}));
    assert.equal(park.work,"屍速列車");
    for(const a of ["馬東錫","馬東石","Ma Dong-seok","Don Lee"])assert(park.aliases.includes(a),a+" alias missing");
    assert(park.source.startsWith("https://"),"Hint source link missing");
    const layout=await page.$eval(".identity-overview",el=>({width:el.getBoundingClientRect().width,columns:getComputedStyle(el).gridTemplateColumns.split(" ").length}));
    assert(layout.width<=390,"Mobile identity cards overflow viewport");
    assert.equal(layout.columns,1,"Mobile identity cards should stack");
    await query("屍速列車");
    assert(await page.$eval("#people",el=>el.textContent.includes("馬東錫")),"Cannot search representative work");
    await query("Don Lee");
    assert(await page.$eval("#people",el=>el.textContent.includes("馬東錫")),"Cannot search accepted alias");
    await query("IU");
    await page.click('.person[data-id="kr20261108_13"]');
    const iu=await page.evaluate(()=>({work:document.querySelector("#featuredWork").textContent,aliases:document.querySelector("#answerAliases").textContent}));
    assert.equal(iu.work,"好日子");assert(iu.aliases.includes("李知恩"));
    await page.setViewport({width:1200,height:800,isMobile:false,hasTouch:false,deviceScaleFactor:1});
    const desktop=await page.$eval(".identity-overview",el=>getComputedStyle(el).gridTemplateColumns.split(" ").length);
    assert.equal(desktop,2,"Desktop cards should be side-by-side");
    assert.deepEqual(errors,[],"Console JavaScript errors");
    fs.mkdirSync(path.join(root,"qa-output"),{recursive:true});
    await page.screenshot({path:path.join(root,"qa-output/console-aliases-works.png"),fullPage:true});
    console.log("PASS: alias display, live work hint, links, searching by work/alias, mobile/desktop layout");
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
