const { chromium } = require(process.argv[2]);
const base = process.argv[3];
const probe = JSON.parse(process.argv[4]);

async function measure(page) {
  const loc = page.locator(probe.watch);
  if (probe.measure === 'count') return loc.count();
  if (probe.measure === 'visible') return loc.first().isVisible();
  if (await loc.count() === 0) return null;
  if (probe.measure === 'text') return (await loc.first().textContent({ timeout: 1500 })).slice(0,1024);
  return loc.first().evaluate(el => el.value == null ? null : String(el.value).slice(0,1024));
}

(async () => {
  const browser = await chromium.launch();
  const readings = [];
  try {
    for (let i = 0; i < 2; i++) {
      const page = await browser.newPage();
      try {
        await page.goto(base + '/index.html', { waitUntil: 'networkidle', timeout: 15000 });
        const before = await measure(page);
        for (const step of probe.actions) {
          const loc = page.locator(step.selector).first();
          if (step.event === 'press') await loc.press(step.key, {timeout: 1800});
          else if (step.event === 'contextmenu') await loc.click({button: 'right', timeout: 1800});
          else if (step.event === 'dblclick') await loc.dblclick({timeout: 1800});
          else await loc.click({timeout: 1800});
        }
        await page.waitForTimeout(120);
        readings.push({ before, after: await measure(page) });
      } catch (err) {
        readings.push({ error: String(err).slice(0,700) });
      } finally { await page.close(); }
    }
  } finally { await browser.close(); }
  process.stdout.write(JSON.stringify(readings));
})().catch(err => { console.error(err); process.exit(1); });
