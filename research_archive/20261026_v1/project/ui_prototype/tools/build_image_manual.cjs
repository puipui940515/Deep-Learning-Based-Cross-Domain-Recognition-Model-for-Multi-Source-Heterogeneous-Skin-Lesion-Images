// Render the existing handbook as readable, numbered PNG pages with UI screenshots.
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { spawn } = require('node:child_process');
const { chromium } = require(process.argv[2] || 'playwright');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'UI使用手冊_圖片版');
const assets = path.join(output, '_素材');
const esc = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const uri = file => '[EMBEDDED_IMAGE_OMITTED] + fs.readFileSync(file).toString('base64');
const width = 1440, height = 1920;

function sectionsFromMarkdown(text) {
  const sections=[];
  let section=null, code=null, bullets=[];
  const flushBullets=()=>{if(bullets.length){section.blocks.push('<div class="bullet-group">'+bullets.join('')+'</div>');bullets=[];}};
  for(const line of text.split(/\r?\n/)) {
    if(line.startsWith('## ')) {flushBullets();section={title:line.slice(3),blocks:[]};sections.push(section);continue;}
    if(!section) continue;
    if(line.startsWith('```')) {
      flushBullets();
      if(code!==null) { section.blocks.push(`<pre>${esc(code.join('\n'))}</pre>`); code=null; }
      else code=[];
      continue;
    }
    if(code!==null) {code.push(line);continue;}
    if(line.startsWith('- ')) {bullets.push(`<div class="bullet"><span>•</span><p>${esc(line.slice(2))}</p></div>`);continue;}
    if(!line.trim())continue;
    flushBullets();
    if(line.startsWith('### ')) section.blocks.push(`<h3>${esc(line.slice(4))}</h3>`);
    else section.blocks.push(`<p>${esc(line)}</p>`);
  }
  flushBullets();
  return sections;
}

const css=`
*{box-sizing:border-box}body{margin:0;background:#eaf0f4;font-family:"Microsoft JhengHei",sans-serif;color:#1d2b36}
.sheet{width:${width}px;height:${height}px;position:relative;padding:68px 76px;background:#fff;margin:0}
.header{height:160px;border-bottom:2px solid #dce6eb;margin-bottom:32px;display:flex;justify-content:space-between;align-items:flex-start;gap:20px}
.eyebrow{font-size:23px;letter-spacing:2px;color:#2f6f9f;font-weight:700;margin-bottom:12px}
h1{font-size:47px;line-height:1.3;margin:0;letter-spacing:.5px}.brand{font-size:27px;white-space:nowrap;color:#245477;font-weight:800}
.content{height:1510px;overflow:hidden}p{font-size:27px;line-height:1.68;margin:0 0 20px;overflow-wrap:anywhere}
h3{font-size:33px;margin:24px 0 15px;color:#245477;line-height:1.4}
.bullet{display:flex;gap:16px;padding:0 0 4px}.bullet>span{color:#2f827d;font-size:32px;line-height:1.45}.bullet p{flex:1;margin-bottom:14px}
pre{font-family:Consolas,"Microsoft JhengHei",monospace;font-size:22px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;background:#edf4f8;color:#204d6c;border-left:6px solid #2f6f9f;border-radius:10px;padding:20px 24px;margin:8px 0 23px}
.footer{position:absolute;bottom:48px;left:76px;right:76px;border-top:2px solid #dce6eb;padding-top:17px;display:flex;justify-content:space-between;gap:20px;color:#667786;font-size:21px}
.footer .page-number{font-weight:800;color:#245477}.intro{font-size:30px;color:#587082;margin-bottom:28px}
.figure{border:2px solid #dce6eb;border-radius:16px;padding:16px;margin:4px 0 24px;background:#f8fbfd}
.figure img{display:block;width:100%;height:660px;object-fit:contain;max-height:760px}.figure figcaption{font-size:23px;line-height:1.5;margin:12px 2px 0;color:#587082}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0}.card{padding:25px;background:#edf4f8;border-radius:14px;min-height:140px}.card b{display:block;font-size:29px;color:#245477;margin-bottom:9px}.card p{font-size:25px;margin:0}
.callout{padding:23px 27px;border:2px solid #dbb977;border-radius:14px;background:#fff9ee;margin:24px 0}.callout p{font-size:26px;margin:0;color:#765317}
.credit{font-size:20px;line-height:1.6;color:#647481;margin-top:24px}
.shotrow{display:grid;grid-template-columns:420px 1fr;gap:28px;align-items:center;margin:6px 0 25px;height:650px}.shotrow img{height:620px;width:420px;object-fit:contain}.shotrow p{font-size:27px}.shotrow b{color:#245477}
`;

(async()=>{
  fs.mkdirSync(assets,{recursive:true});
  const child=spawn('C:\\anaconda3\\python.exe',['-X','utf8','-u',path.join(root,'ui_prototype/server.py'),'--port','8766','--device','cpu','--no-open'],{cwd:root,windowsHide:true,stdio:'ignore'});
  let browser;
  try {
    let ready=false;
    for(let attempt=0;attempt<40;attempt++) {
      if(child.exitCode!==null) throw new Error('Temporary screenshot service did not start');
      try {ready=(await fetch('http://127.0.0.1:8766/api/health')).ok;}catch{}
      if(ready)break;
      await new Promise(resolve=>setTimeout(resolve,250));
    }
    if(!ready)throw new Error('Screenshot service unavailable');
    browser=await chromium.launch({channel:'msedge',headless:true});
    const ui=await browser.newPage({viewport:{width:1440,height:1200},deviceScaleFactor:2});
    let libraryReady=false;
    for(let attempt=0;attempt<3;attempt++) {
      await ui.goto('http://127.0.0.1:8766/prototype/skin-detect?variant=A');
      await ui.locator('#run-button').waitFor();
      await ui.waitForFunction(()=>document.querySelector('.training-intro')?.textContent.includes('ConvNeXt'));
      libraryReady=await ui.locator('#experiment-stage-filter').count()>0;
      if(libraryReady)break;
      console.log('Screenshot library read failed; reloading for a valid, unmodified UI screenshot.');
    }
    if(!libraryReady)throw new Error('Cannot capture experiment library: '+await ui.locator('.experiment-library').innerText());
    await ui.locator('#experiment-tag').fill('圖文手冊示範');
    await ui.locator('#manual-site').selectOption({label:'上肢'});
    await ui.locator('.controls').screenshot({path:path.join(assets,'推論設定.png')});
    await ui.locator('.training-console summary').click();
    await ui.locator('.training-console').screenshot({path:path.join(assets,'訓練控制台.png')});
    await ui.locator('.experiment-library').evaluate(el=>window.scrollTo({top:el.offsetTop-100,behavior:'instant'}));
    const box=await ui.locator('.experiment-library').boundingBox();
    await ui.screenshot({path:path.join(assets,'實驗紀錄.png'),clip:{x:box.x,y:box.y,width:box.width,height:Math.min(box.height,700)}});
    await ui.close();

    const sections=sectionsFromMarkdown(fs.readFileSync(path.join(root,'UI使用手冊.md'),'utf8'));
    const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
    await page.setContent(`<html lang="zh-Hant"><meta charset="utf-8"><style>${css}</style><body></body></html>`);
    const overview=uri(path.join(root,'ui_prototype/logs/UI完善_桌面_2026-10-13.png'));
    const cover=`<p class="intro">看圖操作，從啟動、影像推論到訓練與紀錄</p>
      <figure class="figure"><img src="${overview}" style="max-height:690px"><figcaption>目前 UI 的實際截圖。圖中分數僅示範輸出位置，不是模型效能評估。</figcaption></figure>
      <div class="cards"><div class="card"><b>01　啟動</b><p>在根目錄執行 start_ui.ps1，保留服務視窗。</p></div><div class="card"><b>02　選圖與設定</b><p>選擇疾病模型，上傳 JPG／PNG／WEBP，填寫實驗標記。</p></div><div class="card"><b>03　查看結果</b><p>執行推論，查看七類機率、熱力圖與模型資訊。</p></div><div class="card"><b>04　訓練與紀錄</b><p>展開既有訓練控制台；依階段讀取實驗快照。</p></div></div>
      <div class="callout"><p>推論使用哪個模型，與訓練入口使用哪個流程，是兩個獨立設定。此 UI 訓練入口尚未接入 CP-005／NoiseFilter v2 多日排程。</p></div>
      <p class="credit">本圖文版完整保留原手冊內容。範例皮膚影像：Raimundo Pastor／CC BY 4.0；截圖與熱力圖為衍生展示，來源見「來源說明.md」。</p>`;
    const extras={
      '3. 單張影像推論':`<div class="shotrow"><img src="${uri(path.join(assets,'推論設定.png'))}"><aside><h3>操作位置對照</h3><p><b>上方選單：</b>決定疾病推論權重。</p><p><b>中間欄位：</b>實驗標記、人工拍攝部位。</p><p><b>下方勾選：</b>額外部位輸出與 Grad-CAM。</p><p><b>藍色按鈕：</b>準備好圖片後，按「執行推論」。</p></aside></div>`,
      '5. 透過 UI 訓練':`<figure class="figure"><img src="${uri(path.join(assets,'訓練控制台.png'))}" style="max-height:660px"><figcaption>實際控制台截圖；此處只有設定畫面，沒有啟動訓練。</figcaption></figure>`,
      '6. 推論紀錄與實驗紀錄':`<figure class="figure"><img src="${uri(path.join(assets,'實驗紀錄.png'))}" style="max-height:600px"><figcaption>實驗紀錄庫：選擇階段，再展開卡片讀取已有的圖表與資料。</figcaption></figure>`
    };
    const manifest=await page.evaluate(({sections,extras,cover})=>{
      const pages=[];
      function sheet(title,continued=false) {
        const element=document.createElement('section');element.className='sheet';
        element.innerHTML=`<header class="header"><div><div class="eyebrow">圖文使用手冊 · 2026-10-13</div><h1>${title}${continued?'（續）':''}</h1></div><span class="brand">SkinDetect</span></header><main class="content"></main><footer class="footer"><span>本機研究 UI ｜ 完整操作說明</span><span class="page-number"></span></footer>`;
        document.body.append(element);pages.push({element,title});return element.querySelector('.content');
      }
      sheet('SkinDetect UI 使用手冊').innerHTML=cover;
      for(const section of sections) {
        let content=sheet(section.title), continued=false;
        const blocks=extras[section.title]?[extras[section.title],...section.blocks]:section.blocks;
        for(const block of blocks) {
          const item=document.createElement('div');item.className='flow-item';item.innerHTML=block;
          content.append(item);
          if(content.scrollHeight>content.clientHeight) {
            item.remove();
            const heading=content.lastElementChild?.querySelector('h3')?content.lastElementChild:null;
            if(heading)heading.remove();
            content=sheet(section.title,true);
            if(heading)content.append(heading);
            content.append(item);continued=true;
            if(content.scrollHeight>content.clientHeight)throw new Error('An item cannot fit: '+section.title);
          }
        }
      }
      pages.forEach((p,i)=>{p.element.id='page-'+(i+1);p.element.querySelector('.page-number').textContent=String(i+1).padStart(2,'0')+' / '+String(pages.length).padStart(2,'0');});
      return pages.map((p,i)=>({number:i+1,title:p.title,id:p.element.id}));
    },{sections,extras,cover});
    await page.waitForFunction(()=>[...document.images].every(image=>image.complete&&image.naturalWidth>0));
    await page.evaluate(()=>document.fonts.ready);
    const overflow=await page.locator('.content').evaluateAll(elements=>elements.map((el,i)=>({page:i+1,overflow:el.scrollHeight-el.clientHeight})).filter(x=>x.overflow>0));
    if(overflow.length)throw new Error('Overflow after image load: '+JSON.stringify(overflow));
    const coverage=await page.evaluate(sections=>{
      const normalized=document.body.textContent.replace(/\s/g,'');
      const missing=[];
      for(const section of sections)for(const html of section.blocks){
        const element=document.createElement('div');element.innerHTML=html;
        if(!normalized.includes(element.textContent.replace(/\s/g,'')))missing.push(section.title);
      }
      return missing;
    },sections);
    if(coverage.length)throw new Error('Missing handbook text: '+coverage.join(', '));
    const sheets=await page.locator('.sheet').evaluateAll(elements=>elements.map(el=>el.outerHTML));
    for(const item of manifest) {
      item.file=String(item.number).padStart(2,'0')+'_'+item.title.replace(/[\\/:*?"<>|]/g,'_')+'.png';
      // Capture each sheet at origin: avoid Chromium clipping on a very tall document.
      await page.setContent(`<html lang="zh-Hant"><meta charset="utf-8"><style>${css}</style><body>${sheets[item.number-1]}</body></html>`);
      await page.waitForFunction(()=>[...document.images].every(image=>image.complete&&image.naturalWidth>0));
      await page.evaluate(()=>document.fonts.ready);
      await page.screenshot({path:path.join(output,item.file),fullPage:false});
    }
    fs.writeFileSync(path.join(output,'index.html'),`<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SkinDetect 圖片使用手冊</title><style>body{margin:0;background:#eaf0f4;font-family:"Microsoft JhengHei",sans-serif;color:#234b66}header{max-width:1000px;margin:30px auto;padding:0 20px}h1{font-size:28px}nav{display:flex;gap:8px;flex-wrap:wrap}a{color:#245477}nav a{background:white;padding:7px 10px;border-radius:7px;text-decoration:none;font-size:13px}figure{max-width:1000px;margin:26px auto;padding:0 12px}img{width:100%;display:block;box-shadow:0 6px 30px #28455525}figcaption{padding:8px;font-size:13px}figure:target{outline:3px solid #65a2c7}</style><header><h1>SkinDetect 圖片使用手冊</h1><p>${manifest.length} 張分頁 PNG。點擊圖片可開啟原尺寸；保留完整原手冊文字。</p><nav>${manifest.map(p=>`<a href="#p${p.number}">${p.number} · ${esc(p.title)}</a>`).join('')}</nav></header>${manifest.map(p=>`<figure id="p${p.number}"><a href="${encodeURIComponent(p.file)}" target="_blank"><img loading="lazy" src="${encodeURIComponent(p.file)}" alt="${esc(p.title)}"></a><figcaption>${p.number} / ${manifest.length} · ${esc(p.title)}</figcaption></figure>`).join('')}</html>`,'utf8');
    fs.writeFileSync(path.join(output,'頁面索引.json'),JSON.stringify({source:'UI使用手冊.md',generated_at:new Date().toISOString(),width,height,pages:manifest},null,2),'utf8');
    fs.writeFileSync(path.join(output,'文字版.txt'),fs.readFileSync(path.join(root,'UI使用手冊.md'),'utf8'),'utf8');
    const galleryPath=path.join(output,'index.html');
    fs.writeFileSync(galleryPath,fs.readFileSync(galleryPath,'utf8').replace('<nav>','<p><a href="文字版.txt">開啟文字原檔，方便複製指令</a></p><nav>'),'utf8');
    console.log(JSON.stringify({output,pages:manifest.length,files:manifest.map(p=>p.file)},null,2));
  } finally {
    if(browser)await browser.close();
    child.kill();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
