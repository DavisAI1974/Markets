const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const src = fs.readFileSync('ng-case-views.html', 'utf8');
  fs.writeFileSync('_local_cases.html', src);
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('file://' + process.cwd() + '/_local_cases.html', { waitUntil: 'networkidle' });
  const cases = await p.locator('section.case').all();
  const out = [];
  for (const c of cases) {
    const id = await c.getAttribute('id');
    const n = id.replace('case-', '').padStart(2, '0');
    await c.screenshot({ path: 'case-' + n + '.png' });
    const views = await c.locator('.view').all();
    let k = 0;
    for (const v of views) {
      k += 1;
      await v.screenshot({ path: 'case-' + n + '-view' + k + '.png' });
    }
    out.push({ id, views: views.length });
  }
  const over = await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  await p.pdf({ path: 'ng-case-views.pdf', format: 'A4', landscape: true, printBackground: true, margin: { top: '10mm', bottom: '10mm', left: '8mm', right: '8mm' } });
  await p.emulateMedia({ colorScheme: 'dark' });
  await p.screenshot({ path: '_cases_dark.png', fullPage: false });
  console.log(JSON.stringify({ cases: out, overflow_desktop: over, errors: errs }));
  await b.close();
})();
