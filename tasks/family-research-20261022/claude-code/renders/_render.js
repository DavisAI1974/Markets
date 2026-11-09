const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('file://' + process.cwd() + '/_local.html', { waitUntil: 'networkidle' });
  await p.screenshot({ path: '_look_light.png', fullPage: true });
  const figs = await p.locator('section.fig').all();
  for (const f of figs) {
    const id = await f.getAttribute('id');
    await f.screenshot({ path: 'fig-' + id + '.png' });
  }
  const over = await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  await p.pdf({ path: 'ng-dipole-renders.pdf', format: 'A4', landscape: true, printBackground: true, margin: { top: '12mm', bottom: '12mm', left: '10mm', right: '10mm' } });
  await p.emulateMedia({ colorScheme: 'dark' });
  await p.screenshot({ path: '_look_dark.png', fullPage: false });
  const m = await ctx.newPage();
  await m.setViewportSize({ width: 400, height: 800 });
  await m.goto('file://' + process.cwd() + '/_local.html', { waitUntil: 'networkidle' });
  const overM = await m.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  await m.screenshot({ path: '_look_phone.png', fullPage: false });
  console.log(JSON.stringify({ figures: figs.length, overflow_desktop: over, overflow_phone: overM, errors: errs }));
  await b.close();
})();
