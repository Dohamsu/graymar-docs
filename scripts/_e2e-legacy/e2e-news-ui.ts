import { chromium, type Page } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-news-ui';
let stepNum = 0;

async function ss(page: Page, name: string) {
  stepNum++;
  const filename = `${String(stepNum).padStart(2, '0')}_${name}`;
  await page.screenshot({ path: `${DIR}/${filename}.png`, fullPage: false });
  console.log(`  📸 ${filename}.png`);
}

async function clickText(page: Page, text: string, opts?: { force?: boolean; timeout?: number }) {
  try {
    const btn = page.getByText(text, { exact: false });
    if (await btn.isVisible({ timeout: opts?.timeout ?? 3000 }).catch(() => false)) {
      if (await btn.isDisabled().catch(() => false)) return false;
      await btn.click({ force: opts?.force, timeout: 5000 });
      await page.waitForTimeout(1000);
      return true;
    }
  } catch {}
  return false;
}

async function run() {
  fs.mkdirSync(DIR, { recursive: true });
  for (const f of fs.readdirSync(DIR)) {
    if (f.endsWith('.png')) fs.unlinkSync(`${DIR}/${f}`);
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const email = `e2e_${Date.now()}@test.com`;

  console.log('=== E2E 호외 UI 테스트 ===\n');

  // 1. 회원가입
  console.log('[1] 회원가입...');
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(3000);
  await clickText(page, '시작하기', { force: true });
  await page.waitForTimeout(1000);
  await clickText(page, '회원가입');
  await page.waitForTimeout(500);
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', 'Test1234!!');
  const nick = page.locator('input[name="nickname"]');
  if (await nick.isVisible({ timeout: 1000 }).catch(() => false)) await nick.fill('호외테스트');
  await clickText(page, '가입하기');
  await page.waitForTimeout(3000);

  // 2. 캐릭터 생성
  console.log('[2] 캐릭터 생성...');
  await clickText(page, '새 게임');
  await page.waitForTimeout(2000);
  const presets = page.locator('button, [role="button"]');
  for (let i = 0; i < Math.min(await presets.count(), 15); i++) {
    const txt = await presets.nth(i).textContent() ?? '';
    if (txt.includes('탈영') || txt.includes('부두')) { await presets.nth(i).click(); break; }
  }
  await page.waitForTimeout(1000);
  await clickText(page, '남성');
  await page.waitForTimeout(500);
  for (let step = 0; step < 10; step++) {
    const body = await page.textContent('body') ?? '';
    if (body.includes('행동을 입력') || body.includes('무엇을 하겠는가')) break;
    for (const btn of ['모험 시작', '다 음', '다음', '건너뛰기', '이 초상화', '확인']) {
      if (await clickText(page, btn, { timeout: 800 })) { await page.waitForTimeout(1500); break; }
    }
  }
  await page.waitForTimeout(5000);
  console.log('  게임 진입 완료');

  // 3. UI에서 직접 턴 진행 (reload 없이!)
  const ACTIONS = [
    '시장 거리로 향한다',       // HUB choice
    '주변을 조사한다',           // LOCATION action
    '사람들에게 위협한다',       // 적극적 행동
    '수상한 곳을 잠입한다',     // 적극적 행동
    '뇌물을 건넨다',             // 적극적 행동
    '싸움을 건다',               // 적극적 행동
    '도움을 준다',               // 우호 행동
    '다른 장소로 이동한다',     // 장소 이동
  ];

  for (let turn = 0; turn < 10; turn++) {
    console.log(`\n[턴 ${turn + 1}/10]`);

    // 선택지가 있으면 클릭, 없으면 텍스트 입력
    const choiceButtons = page.locator('[class*="cursor-pointer"]');
    const choiceCount = await choiceButtons.count();
    let submitted = false;

    // 선택지 시도
    if (choiceCount > 0) {
      for (let c = 0; c < Math.min(choiceCount, 5); c++) {
        const choiceText = await choiceButtons.nth(c).textContent() ?? '';
        if (choiceText.includes('시장') || choiceText.includes('경비') || choiceText.includes('항구') || choiceText.includes('빈민')) {
          console.log(`  선택지 클릭: "${choiceText.slice(0, 20)}"`);
          await choiceButtons.nth(c).click();
          submitted = true;
          break;
        }
      }
      if (!submitted && choiceCount > 0) {
        const firstChoice = await choiceButtons.first().textContent() ?? '';
        console.log(`  선택지 클릭: "${firstChoice.slice(0, 20)}"`);
        await choiceButtons.first().click();
        submitted = true;
      }
    }

    // 선택지 없으면 직접 입력
    if (!submitted) {
      const input = page.locator('input[placeholder*="행동"], textarea[placeholder*="행동"], input[type="text"]').first();
      if (await input.isVisible({ timeout: 2000 }).catch(() => false)) {
        const action = ACTIONS[turn % ACTIONS.length];
        await input.fill(action);
        console.log(`  입력: "${action}"`);
        // 제출 버튼 클릭
        const submitBtn = page.locator('button[type="submit"], button:has(svg)').last();
        if (await submitBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await submitBtn.click();
          submitted = true;
        }
      }
    }

    if (!submitted) {
      console.log('  ⚠️ 제출 실패 — 건너뜀');
      await ss(page, `turn_${turn + 1}_skip`);
      continue;
    }

    // LLM 응답 대기 (최대 60초)
    console.log('  LLM 대기...');
    const startWait = Date.now();
    while (Date.now() - startWait < 60000) {
      await page.waitForTimeout(2000);

      // 호외 모달 감지
      const newsModal = page.locator('text=그레이마르 호외');
      if (await newsModal.isVisible({ timeout: 500 }).catch(() => false)) {
        console.log('  📰 호외 모달 감지!');
        await ss(page, `turn_${turn + 1}_NEWS`);
        await clickText(page, '닫기', { timeout: 2000 });
        await page.waitForTimeout(500);
        break;
      }

      // 새 선택지나 입력창이 나타나면 LLM 완료
      const body = await page.textContent('body') ?? '';
      if (body.includes('무엇을 하겠는가') || body.includes('행동을 입력')) {
        console.log('  LLM 완료');
        break;
      }
    }

    // 스크롤 + 캡처
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await ss(page, `turn_${turn + 1}`);
  }

  console.log('\n=== 완료 ===');
  console.log(`스크린샷: ${DIR}/`);
  await browser.close();
}

run().catch(console.error);
