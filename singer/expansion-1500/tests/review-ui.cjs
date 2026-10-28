/* Existing migrated review pages must work offline and export ID/hash-bound decisions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const puppeteer = require('puppeteer-core');
(async () => {
  const root = path.resolve(__dirname, '../..');
  const latest = JSON.parse(fs.readFileSync(path.join(root, 'expansion-1500/pipeline/latest.json')));
  const file = path.join(root, path.dirname(latest.reviewIndex), 'review.html');
  const server = http.createServer((req,res) => {
    const target=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));
    if(!target.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
    fs.readFile(target,(error,data)=>{if(error){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',target.endsWith('.html')?'text/html; charset=utf-8':target.endsWith('.jpg')?'image/jpeg':'application/octet-stream');res.end(data);});
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  server.unref();
  const browser = await puppeteer.launch({executablePath: process.env.CHROME_BIN || '/usr/bin/chromium', args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.setViewport({width:390,height:844});
    await page.goto('http://127.0.0.1:'+server.address().port+'/'+path.relative(root,file));
    await page.select('#filter','pending_review');
    const expected = latest.summary.pendingReviewPeople;
    assert.equal(await page.$$eval('article', rows => rows.length), expected);
    assert(expected > 0, 'Must exercise actual migrated candidates');
    await page.waitForFunction(() => [...document.querySelectorAll('.candidate img')].some(im => im.complete && im.naturalWidth === 600));
    assert(await page.$$eval('.stage', stages => stages.length >= 5));
    // Capture the exported Blob without writing a reviewer decision into the repository.
    await page.evaluate(() => {
      URL.createObjectURL = blob => {window.exportedBlob = blob; return 'blob:fixture';};
      URL.revokeObjectURL = () => {};
      HTMLAnchorElement.prototype.click = function() {};
    });
    await page.type('#reviewer','UI test reviewer (fixture only)');
    await page.select('.candidate select','rejected');
    await page.type('.candidate textarea','Fixture decision; do not import.');
    await page.click('#export');
    const exported = await page.evaluate(async () => JSON.parse(await window.exportedBlob.text()));
    assert.equal(exported.decisions.length,1);
    assert(exported.decisions[0].personId && exported.decisions[0].candidateId && exported.decisions[0].gameSha256);
    const targetId=await page.evaluate(()=>JSON.parse(document.querySelector('#data').textContent).find(p=>p.status==='pending_review').personId);
    await page.type('#search',targetId);
    assert.equal(await page.$$eval('article', rows => rows.length),1);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Review page overflows mobile');
    assert.deepEqual(errors,[]);
    if (process.env.REVIEW_SCREENSHOT) await page.screenshot({path: process.env.REVIEW_SCREENSHOT,fullPage:true});
    console.log('PASS: offline review, migrated portraits, five reveal stages, filter, mobile layout, ID/hash-bound decision export');
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error => {console.error(error);process.exitCode=1;});
