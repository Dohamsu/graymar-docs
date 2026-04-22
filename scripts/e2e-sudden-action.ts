/**
 * 돌발행동 맥락 보존 Phase 1 검증
 * architecture/43_sudden_action_context_preservation.md
 *
 * 시나리오:
 * 1) 신규 런 생성
 * 2) HUB → 장소 이동 → NPC 대화 유도
 * 3) "칼로 찌른다" 입력 (CRITICAL 돌발행동)
 * 4) DB 검사:
 *    · suddenAction 감지 → NPC emotional 변경 확인
 *    · triggerCombat → COMBAT 노드 전환
 *    · personalMemory.encounters에 KILL_ATTEMPT 기록
 */
import * as fs from 'fs';

const API = 'http://localhost:3000';
const DIR = '/tmp/e2e-sudden-action';
const EMAIL = `sudden_test_${Date.now()}@test.com`;
const PASSWORD = 'Test1234!!';
const NICKNAME = `돌발테스트${Date.now() % 10000}`;

let token = '';
let runId = '';

async function api<T = unknown>(
  method: 'GET' | 'POST',
  path: string,
  body?: unknown,
) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return {
    status: res.status,
    body: (await res.json().catch(() => null)) as T,
  };
}

async function getInfo() {
  const r = await fetch(`${API}/v1/runs/${runId}?turnsLimit=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const d = (await r.json()) as {
    run?: { currentTurnNo: number };
    currentNode?: { nodeType: string };
    runState?: Record<string, unknown>;
  };
  return {
    turn: d.run?.currentTurnNo ?? 0,
    nodeType: d.currentNode?.nodeType,
    runState: d.runState,
  };
}

async function submitAction(text: string, expected: number) {
  return api('POST', `/v1/runs/${runId}/turns`, {
    input: { type: 'ACTION', text },
    idempotencyKey: `t_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    expectedNextTurnNo: expected,
  });
}
async function submitChoice(choiceId: string, expected: number) {
  return api('POST', `/v1/runs/${runId}/turns`, {
    input: { type: 'CHOICE', choiceId },
    idempotencyKey: `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    expectedNextTurnNo: expected,
  });
}

async function main() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });

  console.log('▶ 회원가입 + 로그인');
  const reg = await api<{ token: string }>('POST', '/v1/auth/register', {
    email: EMAIL,
    password: PASSWORD,
    nickname: NICKNAME,
  });
  token = reg.body?.token ?? '';
  if (!token) { console.log('등록 실패'); process.exit(1); }

  console.log('▶ DESERTER 런 생성 (FIGHT 보너스)');
  const r = await api<{ run: { id: string } }>('POST', '/v1/runs', {
    presetId: 'DESERTER',
    gender: 'male',
    characterName: '돌발테스터',
  });
  if (!r.body?.run?.id) { console.log('런 실패:', r.body); process.exit(1); }
  runId = r.body.run.id;
  console.log(`  runId=${runId}`);

  // HUB → LOC_GUARD 이동 후 여러 턴 돌려 NPC 등장 유도
  let info = await getInfo();
  console.log(`\n초기: turn=${info.turn}, node=${info.nodeType}`);

  const MAX = 15;
  let suddenActionFired = false;
  let combatTriggered = false;
  let targetNpcId: string | null = null;

  for (let i = 0; i < MAX; i++) {
    info = await getInfo();
    console.log(`\n[${i + 1}] turn=${info.turn}, node=${info.nodeType}`);

    if (info.nodeType === 'HUB') {
      // 경비대로 이동 (NPC 다양)
      const res = await submitChoice('go_guard', info.turn + 1);
      console.log(`  → HUB: go_guard status=${res.status}`);
      await new Promise(r => setTimeout(r, 1500));
      continue;
    }

    if (info.nodeType === 'LOCATION') {
      // 처음 몇 턴은 관찰·대화로 NPC 등장 유도
      let input: string;
      if (i < 3) {
        input = '주변을 살펴본다';
      } else if (i < 5) {
        input = '경비병에게 말을 건다';
      } else {
        // 6턴 이후 CRITICAL 공격
        input = '경비병을 칼로 찌른다';
        console.log('  🔪 돌발행동 CRITICAL 시도!');
      }
      console.log(`  → LOCATION: "${input}"`);
      const res = await submitAction(input, info.turn + 1);
      console.log(`    status=${res.status}`);
      const data = res.body as { transition?: { nextNodeType?: string }; meta?: unknown };
      if (data?.transition?.nextNodeType === 'COMBAT') {
        combatTriggered = true;
        console.log('    🎯 COMBAT 트리거!');
      }

      if (i >= 5) {
        // 공격 직후 결과 검사
        await new Promise(r => setTimeout(r, 2000));
        info = await getInfo();
        const npcStates = info.runState?.npcStates as Record<string, {
          posture?: string;
          emotional?: { suspicion?: number; fear?: number; trust?: number };
          personalMemory?: {
            encounters?: Array<{ playerAction?: string; briefNote?: string }>;
            knownFacts?: string[];
          };
        }> | undefined;

        if (npcStates) {
          for (const [npcId, state] of Object.entries(npcStates)) {
            const encs = state.personalMemory?.encounters ?? [];
            const killEnc = encs.find(e =>
              e.playerAction?.includes('KILL_ATTEMPT') || e.briefNote?.includes('치명적')
            );
            if (killEnc) {
              suddenActionFired = true;
              targetNpcId = npcId;
              console.log(`\n    ✅ ${npcId} 상태 변경 감지:`);
              console.log(`       posture: ${state.posture}`);
              console.log(`       emotional: suspicion=${state.emotional?.suspicion}, fear=${state.emotional?.fear}, trust=${state.emotional?.trust}`);
              console.log(`       knownFacts: ${JSON.stringify(state.personalMemory?.knownFacts ?? [])}`);
              console.log(`       encounters last: ${JSON.stringify(encs[encs.length - 1])}`);
              break;
            }
          }
        }
        if (suddenActionFired) break;
      }
      await new Promise(r => setTimeout(r, 1500));
      continue;
    }

    if (info.nodeType === 'COMBAT') {
      combatTriggered = true;
      console.log('  이미 COMBAT');
      break;
    }
  }

  fs.writeFileSync(
    `${DIR}/result.json`,
    JSON.stringify({ runId, suddenActionFired, combatTriggered, targetNpcId }, null, 2),
  );

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('  최종 결과');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(`suddenAction 감지 + NPC 상태 반영: ${suddenActionFired ? '✅' : '❌'}`);
  console.log(`COMBAT 트리거: ${combatTriggered ? '✅' : '❌'}`);
  console.log(`대상 NPC: ${targetNpcId ?? 'N/A'}`);
}

main().catch(e => { console.error(e); process.exit(1); });
