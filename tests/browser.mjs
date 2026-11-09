import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,readFile,rm} from 'node:fs/promises';
import {tmpdir,homedir} from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
const scratch=await mkdtemp(path.join(tmpdir(),'bead-ui-'));
const status=path.join(scratch,'url.txt');
const python=process.env.BEAD_PYTHON||(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const exe=process.env.BEAD_EXE;
const child=spawn(exe||python,[...exe?[]:['launch.py'],'--no-browser','--status-file',status],{stdio:'ignore'});
let browser,page;
try{
 let url;
 for(let i=0;i<150;i++){try{url=await readFile(status,'utf8');break;}catch{}if(child.exitCode!==null)throw new Error('Application stopped before startup.');await new Promise(r=>setTimeout(r,200));}
 assert.ok(url,'No application URL');
 browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 page=await browser.newPage({viewport:{width:1440,height:980},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);
 const ready=async()=>{
  await page.waitForFunction(()=>document.getElementById('status').textContent.includes('Модель готова')||!document.getElementById('error').hidden,{},{timeout:60000});
  assert.equal(await page.locator('#error').isVisible(),false,await page.locator('#error').textContent());
 };
 await ready();
 assert.equal(await page.locator('.shape').count(),8);
 assert.equal(await page.locator('#canvas').isVisible(),true);
 assert.ok(await page.locator('#canvas').evaluate(c=>c.width>100));
 for(const shape of 'ABCDEFGH'){
  console.log('Checking shape',shape);
  await page.locator(`[data-shape="${shape}"]`).click();await ready();
  assert.equal(await page.locator('#download-stl').isEnabled(),true);
 }
 await page.locator('[data-shape="D"]').click();await ready();
 await page.locator('#details').evaluate(d=>d.open=true);
 await page.locator('#twist-number').fill('230');await ready();
 await page.locator('#bore-number').fill('6.4');await ready();
 assert.match(await page.locator('#bore-value').textContent(),/6,4/);
 await page.locator('#details').evaluate(d=>d.open=false);
 await mkdir('tests/artifacts',{recursive:true});
 await page.screenshot({path:'tests/artifacts/desktop.png',fullPage:true});
 for(const [button,extension] of [['download-stl','.stl'],['download-step','.step'],['download-fusion','.zip']]){
  const download=page.waitForEvent('download');await page.locator('#'+button).click();const file=await download;
  assert.ok(file.suggestedFilename().endsWith(extension));assert.equal(await file.failure(),null);
  await file.saveAs(path.join(scratch,'export'+extension));
 }
 const save=page.waitForEvent('download');await page.locator('#save-project').click();const config=await save;
 const configFile=path.join(scratch,'project.json');await config.saveAs(configFile);
 assert.equal(JSON.parse(await readFile(configFile,'utf8')).settings.shape,'D');
 await page.locator('#reset').click();await ready();
 await page.locator('#project-file').setInputFiles(configFile);
 await page.waitForFunction(()=>document.getElementById('bore-value').textContent.includes('6,4'));
 await ready();
 assert.match(await page.locator('#bore-value').textContent(),/6,4/);
 await page.locator('#bore-number').fill('10');
 await page.waitForSelector('#error:not([hidden])');assert.equal(await page.locator('#download-stl').isDisabled(),true);
 await page.locator('#reset').click();await ready();
 await page.locator('#help').click();assert.equal(await page.locator('#help-dialog').isVisible(),true);await page.locator('#help-done').click();
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'tests/artifacts/mobile.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 await page.locator('#stop').click();
 console.log('PASS: 8 shapes, editable dimensions, live CAD, exports, project round-trip, invalid wall, help, desktop/mobile, exit.');
}catch(error){
 await mkdir('tests/artifacts',{recursive:true});
 if(page){await page.screenshot({path:'tests/artifacts/failure.png',fullPage:true}).catch(()=>{});console.error('Visible status:',await page.locator('#status').textContent().catch(()=>''));console.error('Visible error:',await page.locator('#error').textContent().catch(()=>''));}
 const logpath=process.platform==='win32'?path.join(process.env.LOCALAPPDATA,'BeadStudio','app.log'):path.join(homedir(),'.local/state/bead-studio/app.log');
 console.error('Application log:',await readFile(logpath,'utf8').then(s=>s.slice(-6000)).catch(()=>''));
 throw error;
}finally{
 if(browser)await browser.close();
 child.kill();await rm(scratch,{recursive:true,force:true});
}
