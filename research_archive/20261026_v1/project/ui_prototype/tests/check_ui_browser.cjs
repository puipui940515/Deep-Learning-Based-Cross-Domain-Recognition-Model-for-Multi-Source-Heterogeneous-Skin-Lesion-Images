// Run against an already started local UI. Training is never confirmed or sent.
const { chromium } = require(process.argv[3] || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const base = process.argv[2] || 'http://127.0.0.1:8765';

(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors = [];
  const checks = [];
  let trainingRequests = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('response',async response=>{
    if(!response.url().endsWith('/api/predict')) return;
    try { const body=await response.text(); JSON.parse(body); }
    catch(error){console.error('Prediction response read failure:',error.message,response.headers());}
  });
  page.on('request', request => { if (request.url().includes('/api/training/start')) trainingRequests++; });
  try {
    await page.goto(base+'/prototype/skin-detect?variant=A');
    await page.getByRole('button',{name:'執行推論',exact:true}).waitFor();
    await page.waitForFunction(() => document.querySelector('#training-start') && document.querySelector('.training-intro')?.textContent.includes('ConvNeXt'));
    await page.locator('.training-console summary').click();
    await page.locator('#train-epochs').fill('7');
    await page.waitForTimeout(3000);
    assert.equal(await page.locator('#train-epochs').inputValue(),'7');
    assert.equal(await page.locator('.training-console').evaluate(el=>el.open),true);
    await page.locator('#experiment-tag').fill('中文 UI 驗證');
    await page.locator('#manual-site').selectOption({label:'上肢'});
    await page.locator('#model-select').selectOption('demo');
    await page.locator('#file-input').setInputFiles(path.join(root,'ui_prototype/external_test_2026-09-05/02_NV_黑色素細胞痣_皮內痣.jpg'));
    await page.waitForFunction(()=>document.querySelector('#dropzone img')?.complete);
    await page.locator('#variant-next').click();
    assert.equal(await page.locator('#experiment-tag').inputValue(),'中文 UI 驗證');
    assert.equal(await page.locator('#manual-site').inputValue(),'上肢');
    assert.equal(await page.locator('#train-epochs').inputValue(),'7');
    await page.locator('#variant-next').click();
    assert.equal(await page.locator('#manual-site').inputValue(),'上肢');
    await page.getByRole('button',{name:'執行',exact:true}).click();
    await page.locator('.prediction-name').waitFor();
    assert.match(await page.locator('.inspector').innerText(), /展示模式結果（假資料）/);
    assert.equal(await page.locator('#experiment-tag').inputValue(),'中文 UI 驗證');
    checks.push('三版型切換、欄位保留、訓練刷新不打斷輸入、展示推論');
    await page.locator('#variant-next').click();
    await page.locator('#model-select').selectOption('mixed_convnext');
    await page.locator('#include-heatmap').check();
    for(let repeat=0;repeat<3;repeat++) {
      await page.getByRole('button',{name:'執行推論',exact:true}).click();
      await page.waitForFunction(()=>!document.querySelector('#run-button').disabled,{},{timeout:120000});
      assert.equal(await page.locator('.error').count(),0,await page.locator('.error').allTextContents());
      assert.equal(await page.locator('.heatmap-figure img').count(),1);
    }
    assert.equal(await page.locator('.results .bars:not(.site) .bar-row').count(),7);
    if(await page.locator('.training-console').evaluate(el=>el.open)) await page.locator('.training-console summary').click();
    await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
    await page.screenshot({path:path.join(root,'ui_prototype/logs/UI完善_桌面_2026-10-13.png'),fullPage:false});
    checks.push('同一頁連續三次真實 ConvNeXt 推論、七類機率、Grad-CAM');
    await page.getByRole('link',{name:'使用手冊 ↗'}).waitFor();
    const manual=await page.request.get(base+'/manual');
    assert.equal(manual.status(),200);
    assert.match(await manual.text(),/SkinDetect UI 使用手冊/);
    // Dismiss the existing confirmation. Never create a real training task.
    if(!await page.locator('.training-console').evaluate(el=>el.open)) await page.locator('.training-console summary').click();
    await page.locator('#train-mode').selectOption('formal');
    let confirmation='';
    page.once('dialog',async dialog=>{confirmation=dialog.message();await dialog.dismiss();});
    await page.locator('#training-start').click();
    assert.match(confirmation,/既有三來源七分類/);
    assert.equal(trainingRequests,0);
    checks.push('手冊開啟、訓練確認顯示固定流程、取消後零訓練請求');
    await page.locator('.training-console summary').click();
    await page.setViewportSize({width:390,height:844});
    for(const variant of ['A','B','C']) {
      if(new URL(page.url()).searchParams.get('variant')!==variant) await page.locator('#variant-next').click();
      await page.locator('#run-button').waitFor();
      const dimensions=await page.evaluate(()=>({body:document.documentElement.scrollWidth,viewport:innerWidth}));
      assert.ok(dimensions.body<=dimensions.viewport, `Variant ${variant} overflow: ${JSON.stringify(dimensions)}`);
    }
    await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
    await page.screenshot({path:path.join(root,'ui_prototype/logs/UI完善_手機_2026-10-13.png'),fullPage:false});
    checks.push('390px 三版型無水平溢出');
    // An optional library failure must not prevent predictions from loading.
    await page.route('**/api/experiments',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'測試用紀錄庫錯誤'})}));
    await page.goto(base+'/prototype/skin-detect?variant=A');
    await page.locator('#run-button').waitFor();
    assert.match(await page.locator('#experiment-library').innerText(),/測試用紀錄庫錯誤/);
    checks.push('紀錄庫錯誤不阻斷推論畫面');
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,checks,training_requests:trainingRequests,browser_errors:errors},null,2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
