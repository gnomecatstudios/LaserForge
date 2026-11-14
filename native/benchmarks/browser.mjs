// Start `pnpm dev --host 127.0.0.1` separately; this harness never changes app settings.
import { chromium } from '@playwright/test';
import { readFile } from 'node:fs/promises';
const fixturePath=process.argv[2];
if(!fixturePath) throw new Error('Usage: node native/benchmarks/browser.mjs /tmp/fixture.json');
const project=JSON.parse(await readFile(fixturePath,'utf8'));
const started=performance.now();
const browser=await chromium.launch({headless:true,
  ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}),
  args:['--no-sandbox','--disable-dev-shm-usage']});
try {
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  await page.goto(`${process.env.BENCHMARK_URL ?? 'http://127.0.0.1:5190'}/native/benchmarks/browser.html`);
  await page.waitForFunction(()=>window.benchmarkReady);
  const harness_startup_ms=performance.now()-started;
  const result=await page.evaluate(({project})=>window.runBenchmark(project),{project});
  console.log(JSON.stringify({...result,harness_startup_ms},null,2));
} finally {await browser.close();}
