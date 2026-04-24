/**
 * 포트폴리오 스크린샷 4장 캡처
 * 1. 메인 플레이 화면 (HUB/LOCATION 서술 + 선택지)
 * 2. NPC 관계 변화 장면
 * 3. 퀘스트 메뉴 (SidePanel > QuestTab)
 * 4. 엔딩 아카이브 (여정 기록)
 *
 * 파트 A: 새 계정 → 회원가입 → 캐릭터 생성 6단계 → 플레이 → 1~3번 캡처
 * 파트 B: 엔딩 보유 계정 재로그인 → 여정 기록 → 4번 캡처
 */
import * as fs from 'fs';
import { chromium, type Page } from 'playwright';

const BASE = 'https://dimtale.com';
const DIR = '/tmp/portfolio-screenshots';

const EMAIL_NEW = `portfolio_${Date.now()}@test.com`;
const PASSWORD = 'Test1234!!';
const NICKNAME = `포폴${Date.now() % 10000}`;

const EMAIL_ENDING = 'playtest_1776907639@test.com';

const VIEWPORT = { width: 1440, height: 900 };
const HEADLESS = true;
const TURN_WAIT = 12000; // 턴당 대기 (스트리밍 + 타이핑 여유)

async function shot(page: Page, path: string, label: string, fullPage = false) {
  await page.screenshot({ path, fullPage });
  console.log(`📸 ${label}`);
}

async function clickButton(page: Page, re: RegExp, timeout = 3000): Promise<boolean> {
  const btn = page.getByRole('button', { name: re }).last();
  if (await btn.isVisible({ timeout }).catch(() => false)) {
    await btn.click({ force: true });
    return true;
  }
  // 대체: 텍스트 기반
  const txt = page.getByText(re).last();
  if (await txt.isVisible({ timeout: 1000 }).catch(() => false)) {
    await txt.click({ force: true });
    return true;
  }
  return false;
}

async function login(page: Page, email: string, password: string) {
  const emailInput = page.locator('input[name="email"], input[type="email"]').first();
  if (!(await emailInput.isVisible({ timeout: 5000 }).catch(() => false))) return false;
  await emailInput.fill(email);
  await page.locator('input[name="password"], input[type="password"]').first().fill(password);
  const btns = page.locator(
    'button:has-text("로그 인"), button:has-text("로그인"), button[type="submit"]',
  );
  await btns.nth((await btns.count()) - 1).click();
  await page.waitForTimeout(5000);
  return true;
}

async function register(page: Page) {
  const registerTab = page.getByRole('button', { name: /회원가입|가입/ }).first();
  if (await registerTab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await registerTab.click();
    await page.waitForTimeout(700);
  }
  await page.locator('input[name="email"], input[type="email"]').first().fill(EMAIL_NEW);
  await page.locator('input[name="password"], input[type="password"]').first().fill(PASSWORD);
  const nick = page.locator('input[name="nickname"]').first();
  if (await nick.isVisible({ timeout: 1500 }).catch(() => false)) await nick.fill(NICKNAME);
  await page.locator('button[type="submit"]').last().click();
  await page.waitForTimeout(5000);
}

async function createCharacter(page: Page) {
  // 타이틀 → "새 게임"
  console.log('  · 새 게임 클릭');
  if (!(await clickButton(page, /^\s*새\s*게임\s*$/, 3000))) {
    console.log('  ⚠️  새 게임 버튼 미발견 — HTML 덤프');
    const t = await page.evaluate(() => document.body.innerText.slice(0, 400));
    console.log(t);
  }
  await page.waitForTimeout(1800);

  // 모달 "새 캐릭터 생성" 또는 "이전 캐릭터로 시작" — 없으면 그냥 넘어감
  const newCharBtn = page.getByRole('button', { name: /새 캐릭터/ }).first();
  if (await newCharBtn.isVisible({ timeout: 1200 }).catch(() => false)) {
    await newCharBtn.click();
    await page.waitForTimeout(1000);
  }

  // Step 0: SELECT_PRESET — "탈영병" 카드 + 성별 "남성" + 다 음
  console.log('  · 프리셋 선택 (탈영병)');
  const presetCard = page.getByText(/탈영병/).first();
  if (await presetCard.isVisible({ timeout: 3000 }).catch(() => false)) {
    await presetCard.click({ force: true });
    await page.waitForTimeout(500);
  }
  const maleBtn = page.getByRole('button', { name: /남성/ }).first();
  if (await maleBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await maleBtn.click({ force: true });
    await page.waitForTimeout(400);
  }
  // "다 음" 공백 포함 regex
  await clickButton(page, /다\s*음/, 2000);
  await page.waitForTimeout(1500);

  // Step 1: CHARACTER_PORTRAIT — "이 초상화로 진행"
  console.log('  · 초상화 진행');
  await clickButton(page, /이\s*초상화로\s*진행|이\s*초상화/, 3000);
  await page.waitForTimeout(2000);

  // Step 2: CHARACTER_NAME — 이름 입력 + "다 음"
  console.log('  · 이름 입력');
  const nameInput = page
    .locator('input[placeholder*="이름"], input[name="characterName"], input[type="text"]')
    .first();
  if (await nameInput.isVisible({ timeout: 2500 }).catch(() => false)) {
    await nameInput.fill('이름 없는 용병');
    await page.waitForTimeout(500);
  }
  await clickButton(page, /다\s*음/, 2500);
  await page.waitForTimeout(1500);

  // Step 3: CHARACTER_STATS — 기본 배분 유지 + "다 음"
  console.log('  · 스탯 기본 + 다음');
  await clickButton(page, /다\s*음/, 3000);
  await page.waitForTimeout(1500);

  // Step 4: CHARACTER_TRAIT — 첫 특성 선택 + "다 음"
  console.log('  · 특성 선택');
  const traitCard = page
    .locator('button, div[class*="cursor-pointer"]')
    .filter({ hasText: /전투의 기억|거리 감각|은빛|도박|피의 맹세|밤의/ })
    .first();
  if (await traitCard.isVisible({ timeout: 3000 }).catch(() => false)) {
    await traitCard.click({ force: true });
    await page.waitForTimeout(600);
  }
  await clickButton(page, /다\s*음/, 3000);
  await page.waitForTimeout(1500);

  // Step 5: CHARACTER_CONFIRM — "모험 시작"
  console.log('  · 모험 시작');
  await clickButton(page, /모험\s*시작|여정\s*시작|게임\s*시작/, 3000);

  console.log('  · 게임 진입 + 초기 턴 로딩');
  await page.waitForTimeout(16000);
}

async function submitAction(page: Page, text: string, wait = TURN_WAIT) {
  const input = page
    .locator('textarea, input[placeholder*="행동"], input[type="text"]')
    .last();
  if (!(await input.isVisible({ timeout: 2500 }).catch(() => false))) return false;
  await input.fill(text);
  await page.waitForTimeout(300);
  const send = page.getByRole('button', { name: /전송|보내기|입력/ }).last();
  if (await send.isVisible({ timeout: 800 }).catch(() => false)) {
    await send.click({ force: true });
  } else {
    await input.press('Enter');
  }
  await page.waitForTimeout(wait);
  return true;
}

async function partA() {
  console.log('▶ [파트 A] 새 계정 + 플레이');
  const browser = await chromium.launch({ headless: HEADLESS });
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log(`[browser error] ${msg.text().slice(0, 150)}`);
  });

  await page.goto(`${BASE}/play`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2500);
  await shot(page, `${DIR}/debug-A0-initial.png`, 'debug-A0-initial.png (최초 도착)');

  // "시작하기" 버튼이 보이면 클릭 (랜딩 → 게임 라우팅)
  await clickButton(page, /시작하기/, 2000);
  await page.waitForTimeout(2500);
  await shot(page, `${DIR}/debug-A1-auth.png`, 'debug-A1-auth.png (AUTH 화면)');

  await register(page);
  await shot(page, `${DIR}/debug-A2-title.png`, 'debug-A2-title.png (회원가입 후)');

  await createCharacter(page);

  // ── 스크린샷 1: 메인 플레이 ──
  await page.waitForTimeout(2500);
  await shot(page, `${DIR}/1-main-play.png`, '1-main-play.png (메인 플레이 화면)');

  // 관계 변화 유도 턴
  console.log('  · T1 대화');
  await submitAction(page, '주변을 살펴본다', 14000);
  console.log('  · T2 NPC 접촉');
  await submitAction(page, '경비병에게 말을 건다', 14000);
  console.log('  · T3 위협으로 관계 변화');
  await submitAction(page, '칼을 겨눠 위협한다', 16000);

  await page.waitForTimeout(2000);
  await shot(page, `${DIR}/2-npc-relation.png`, '2-npc-relation.png (NPC 관계 변화)');

  // ── 스크린샷 3: 퀘스트 메뉴 ──
  // SidePanel 열기: 오른쪽 상단 아이콘 / 햄버거 / 메뉴 버튼
  console.log('  · SidePanel 열기');
  const openSidePanel = async () => {
    // 여러 selector 시도
    const tries = [
      'button[aria-label*="메뉴"]',
      'button[aria-label*="menu"]',
      'button[aria-label*="패널"]',
      'button:has-text("☰")',
      'button[title*="메뉴"]',
    ];
    for (const sel of tries) {
      const b = page.locator(sel).first();
      if (await b.isVisible({ timeout: 700 }).catch(() => false)) {
        await b.click({ force: true });
        return true;
      }
    }
    return false;
  };
  await openSidePanel();
  await page.waitForTimeout(900);

  // 퀘스트 탭 클릭
  console.log('  · 퀘스트 탭 클릭');
  const questTab = page.getByRole('button', { name: /퀘스트/ }).first();
  if (await questTab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await questTab.click({ force: true });
  } else {
    const tabAny = page
      .locator('[role="tab"], button, div[class*="tab"]')
      .filter({ hasText: /퀘스트/ })
      .first();
    if (await tabAny.isVisible({ timeout: 1500 }).catch(() => false)) {
      await tabAny.click({ force: true });
    }
  }
  await page.waitForTimeout(1500);
  await shot(page, `${DIR}/3-quest-menu.png`, '3-quest-menu.png (퀘스트 메뉴)');

  await browser.close();
}

async function partB() {
  console.log('\n▶ [파트 B] 기존 엔딩 계정 → 여정 기록');
  const browser = await chromium.launch({ headless: HEADLESS });
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/play`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(4000);
  // "시작하기" 두 번 시도
  await clickButton(page, /시작하기/, 5000);
  await page.waitForTimeout(3000);
  await clickButton(page, /시작하기/, 2000);
  await page.waitForTimeout(2500);
  await login(page, EMAIL_ENDING, PASSWORD);

  await clickButton(page, /여정 기록/, 3000);
  await page.waitForTimeout(2500);

  // 첫 카드 클릭
  const card = page
    .locator('button, [role="button"], div[class*="cursor-pointer"]')
    .filter({ hasText: /여정|황금|그림자|일\s|턴|용병/ })
    .first();
  if (await card.isVisible({ timeout: 2000 }).catch(() => false)) {
    await card.click({ force: true });
    await page.waitForTimeout(3500);
  }

  await shot(page, `${DIR}/4-ending-archive.png`, '4-ending-archive.png (여정 요약)');
  await shot(page, `${DIR}/4-ending-archive-full.png`, '4-ending-archive-full.png', true);

  await browser.close();
}

async function main() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });

  await partA();
  await partB();

  console.log(`\n✓ 완료 — ${DIR}`);
  for (const f of fs.readdirSync(DIR).sort()) {
    const st = fs.statSync(`${DIR}/${f}`);
    console.log(`  ${f}  ${Math.round(st.size / 1024)}KB`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
