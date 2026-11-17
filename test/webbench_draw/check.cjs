const {chromium} = require('../../artifacts/webbench-draw-runtime-20261117/node_modules/@playwright/test');
(async()=>{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error=>errors.push(String(error).slice(0,1200)));
  page.on('console', message=>{if(message.type()==='error')errors.push(message.text().slice(0,1200));});
  try {
    const response = await page.goto(process.argv[2]+'/index.html',{waitUntil:'networkidle',timeout:20000});
    if(!response || response.status()>=400) errors.push('index.html could not be loaded');
    await page.waitForTimeout(300);
  } catch(error) {errors.push(String(error).slice(0,1200));}
  await browser.close();
  console.log(JSON.stringify(errors.slice(0,12)));
})().catch(error=>{console.error(error);process.exit(1);});
