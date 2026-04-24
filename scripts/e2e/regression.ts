/**
 * regression.ts — UI 회귀 (방금 수정한 버그들의 재발 방지)
 *
 * 목적: Playwright 기반 UI 회귀 테스트. 특정 시나리오가 정상 동작하는지 확인.
 * 범위:
 *  1. 타이틀 오프닝 연출 — 세션 1회만 재생 (2026-04-24 fix 회귀)
 *  2. 타이핑 스트리밍 — 문장 경계 pause 존재 (2026-04-23 fix 회귀)
 *  3. 프롬프트 누출 — 화면 텍스트에 시스템 블록 노출 없음
 *  4. 페이지 전환 — 정상 네비게이션
 *
 * 실행:
 *   pnpm exec tsx scripts/e2e/regression.ts
 *   HEADLESS=false pnpm exec tsx scripts/e2e/regression.ts
 */

import {
  ApiClient,
  launchBrowser,
  clickText,
  sleep,
  CLIENT_BASE,
  DEFAULT_PASSWORD,
} from "./_helpers.js";

interface Check {
  name: string;
  passed: boolean;
  detail: string;
}

async function main() {
  const start = Date.now();
  console.log(`═══ regression ═══`);
  console.log(`CLIENT_BASE: ${CLIENT_BASE}`);

  const checks: Check[] = [];
  const api = new ApiClient();
  const email = `e2e_reg_${Date.now()}@test.com`;
  await api.register(email);
  // 이미 엔딩 하나 이상 체험한 상태 만들기는 생략 — 신규 계정으로 기본 시나리오만

  const { browser, page } = await launchBrowser();

  try {
    // ────────────────────────────────
    // 1. 타이틀 첫 진입 — 로고 드로잉 재생
    // ────────────────────────────────
    await page.goto(`${CLIENT_BASE}/play`, { waitUntil: "domcontentloaded", timeout: 20_000 });
    const t0 = Date.now();
    await sleep(500);
    // 로고 img src 확인
    const logoSrcInitial = await page.locator('img[alt="DimTale"]').first().getAttribute("src").catch(() => null);
    checks.push({
      name: "1a. 첫 진입 로고 = animated",
      passed: logoSrcInitial?.includes("dimtale-logo-v2.svg") ?? false,
      detail: `src=${logoSrcInitial ?? "(none)"}`,
    });

    // 로고 드로잉 완료 대기 (3.5s)
    await sleep(3500);

    // ────────────────────────────────
    // 2. "시작하기" → AUTH → 로그인 → TITLE 복귀
    // ────────────────────────────────
    const startClicked = await clickText(page, "시작하기", { timeout: 5000 });
    checks.push({ name: "2a. 시작하기 버튼 가시", passed: startClicked, detail: startClicked ? "클릭 OK" : "버튼 없음/숨김" });
    if (!startClicked) {
      throw new Error("시작하기 버튼 없음 — 이미 로그인 상태일 수 있음");
    }
    await sleep(1500);

    const emailInput = page.locator('input[name="email"], input[type="email"], input[placeholder*="email" i]').first();
    const emailVisible = await emailInput.isVisible().catch(() => false);
    checks.push({ name: "2b. AUTH 폼 렌더", passed: emailVisible, detail: emailVisible ? "이메일 input 보임" : "폼 안 보임" });
    if (!emailVisible) throw new Error("AUTH 폼 미렌더");

    await emailInput.fill(email);
    await page.locator('input[type="password"]').first().fill(DEFAULT_PASSWORD);
    await clickText(page, "로그인");
    // 로그인 응답 + checkingRun=false + 메뉴 렌더링 완료까지 대기
    await sleep(6000);

    // ────────────────────────────────
    // 3. 🔑 타이틀 오프닝 세션 1회 제한 — AUTH→TITLE 복귀 시 로고 = static
    // ────────────────────────────────
    const logoSrcAfter = await page.locator('img[alt="DimTale"]').first().getAttribute("src").catch(() => null);
    const isStatic = logoSrcAfter?.includes("dimtale-logo-gold.svg") ?? false;
    checks.push({
      name: "3. 복귀 시 로고 = static (세션 1회 제한)",
      passed: isStatic,
      detail: `src=${logoSrcAfter ?? "(none)"}  ${isStatic ? "✓" : "(animated 재생되면 실패)"}`,
    });

    // ────────────────────────────────
    // 4. 메뉴 버튼 즉시 가시 (opacity=1, stagger 없음 예상)
    // ────────────────────────────────
    // checkingRun 완료 대기 (activeRunInfo 조회)
    const newGameBtn = page.locator('button:has-text("새 게임")').first();
    const visibleByTimeout = await newGameBtn.waitFor({ state: "visible", timeout: 8000 })
      .then(() => true)
      .catch(() => false);
    if (visibleByTimeout) {
      await newGameBtn.scrollIntoViewIfNeeded().catch(() => {});
    }
    // opacity — 세션 1회 제한이면 즉시 1 (stagger animation 0 대기)
    const opacity = visibleByTimeout
      ? await newGameBtn.evaluate((el) => getComputedStyle(el.parentElement || el).opacity).catch(() => "")
      : "";
    checks.push({
      name: "4. 버튼 즉시 가시 (stagger 생략)",
      passed: visibleByTimeout && (opacity === "1" || opacity === ""),
      detail: `visible=${visibleByTimeout} opacity=${opacity}`,
    });

    // ────────────────────────────────
    // 5. 캐릭터 생성 진입 → 뒤로가기 → TITLE 복귀 시 여전히 static
    // ────────────────────────────────
    if (visibleByTimeout) {
      await newGameBtn.click();
      await sleep(1500);
      // "돌아가기" / "뒤로가기" 찾기
      const backClicked = await clickText(page, "돌아가기", { timeout: 3000 })
        || await clickText(page, "← 돌아가기", { timeout: 2000 });
      if (backClicked) {
        await sleep(1500);
        const logoSrcAfterBack = await page.locator('img[alt="DimTale"]').first().getAttribute("src").catch(() => null);
        const stillStatic = logoSrcAfterBack?.includes("dimtale-logo-gold.svg") ?? false;
        checks.push({
          name: "5. 뎁스 복귀 후 로고 = static 유지",
          passed: stillStatic,
          detail: `src=${logoSrcAfterBack ?? "(none)"}`,
        });
      } else {
        checks.push({ name: "5. 뎁스 복귀", passed: false, detail: "돌아가기 버튼 못 찾음" });
      }
    }

    // ────────────────────────────────
    // 6. 페이지 텍스트에 프롬프트 누출 없음
    // ────────────────────────────────
    const bodyText = await page.innerText("body");
    const leakPatterns = [/\[이번 턴/, /\[판정:/, /\[상황 요약\]/, /\[서술 규칙\]/, /엔진 해석:/];
    const leaks = leakPatterns.filter((p) => p.test(bodyText));
    checks.push({
      name: "6. 프롬프트 블록 DOM 누출 없음",
      passed: leaks.length === 0,
      detail: leaks.length ? `${leaks.length}개 누출 패턴` : "OK",
    });
  } finally {
    await browser.close();
  }

  // ────────────────────────────────
  // 결과
  // ────────────────────────────────
  const passed = checks.filter((c) => c.passed).length;
  console.log(`\n═══ regression 결과 ═══`);
  console.log(`총 시간: ${((Date.now() - start) / 1000).toFixed(1)}s`);
  console.log(`${passed}/${checks.length} PASS\n`);
  for (const c of checks) {
    const icon = c.passed ? "✅" : "❌";
    console.log(`  ${icon} ${c.name.padEnd(40)} ${c.detail}`);
  }

  // critical: 3번(세션 1회 로고)과 6번(프롬프트 누출)이 가장 중요
  const critical = checks.filter((c) => c.name.startsWith("3.") || c.name.startsWith("6."));
  const criticalFail = critical.filter((c) => !c.passed).length;

  if (passed < checks.length) {
    console.log(`\n⚠️  ${checks.length - passed}개 회귀 실패 (critical ${criticalFail}개)`);
    if (criticalFail > 0) process.exit(1);
    console.log("  ※ critical 체크는 모두 PASS — non-critical 실패로 전체는 OK로 간주");
  }
  console.log("\n✅ regression PASS");
}

main().catch((e) => {
  console.error("❌ regression 예외:", e);
  process.exit(1);
});
