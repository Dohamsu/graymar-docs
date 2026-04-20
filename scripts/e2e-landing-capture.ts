import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-landing';

async function run() {
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.goto(`${BASE}/`);
  await page.waitForTimeout(3500);

  // Hero 캡처
  await page.screenshot({ path: `${DIR}/01_hero.png`, fullPage: false });
  console.log('📸 01_hero.png');

  // 아래로 스크롤 (Features)
  await page.evaluate(() => window.scrollTo(0, window.innerHeight));
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/02_features.png`, fullPage: false });
  console.log('📸 02_features.png');

  // Story 섹션
  await page.evaluate(() => {
    const el = document.querySelector('#story');
    if (el) el.scrollIntoView({ behavior: 'instant' });
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/03_story.png`, fullPage: false });
  console.log('📸 03_story.png');

  // How to play
  await page.evaluate(() => {
    const el = document.querySelector('#how-to-play');
    if (el) el.scrollIntoView({ behavior: 'instant' });
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/04_howtoplay.png`, fullPage: false });
  console.log('📸 04_howtoplay.png');

  // FAQ
  await page.evaluate(() => {
    const el = document.querySelector('#faq');
    if (el) el.scrollIntoView({ behavior: 'instant' });
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/05_faq.png`, fullPage: false });
  console.log('📸 05_faq.png');

  // Final CTA (최하단)
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/06_final_cta.png`, fullPage: false });
  console.log('📸 06_final_cta.png');

  // 전체
  await page.screenshot({ path: `${DIR}/00_fullpage.png`, fullPage: true });
  console.log('📸 00_fullpage.png');

  await browser.close();
}

run().catch((e) => { console.error(e); process.exit(1); });
