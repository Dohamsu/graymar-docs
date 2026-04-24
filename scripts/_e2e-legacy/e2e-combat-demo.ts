/**
 * 창의 전투 MVP 엔드투엔드 데모
 * - CombatService를 직접 호출해 Tier 1/2/4/5 플래그가 모든 계층을 통과하는지 검증
 * - 실제 COMBAT 노드 진입이 플레이테스트로 어렵기 때문에 통합 시뮬레이션으로 대체
 */
import * as fs from 'fs';
import { CombatService } from '../server/src/engine/combat/combat.service.js';
import { RngService } from '../server/src/engine/rng/rng.service.js';
import { StatsService } from '../server/src/engine/stats/stats.service.js';
import { StatusService } from '../server/src/engine/status/status.service.js';
import { HitService } from '../server/src/engine/combat/hit.service.js';
import { DamageService } from '../server/src/engine/combat/damage.service.js';
import { EnemyAiService } from '../server/src/engine/combat/enemy-ai.service.js';
import { PropMatcherService } from '../server/src/engine/combat/prop-matcher.service.js';
import type { CombatTurnInput } from '../server/src/engine/combat/combat.service.js';
import type { ContentLoaderService } from '../server/src/content/content-loader.service.js';
import type { BattleStateV1, PermanentStats } from '../server/src/db/types/index.js';

const DIR = '/tmp/e2e-combat-demo';
fs.mkdirSync(DIR, { recursive: true });

const contentStub = {
  getItem: () => null,
} as unknown as ContentLoaderService;

const combatService = new CombatService(
  new RngService(),
  new StatsService(),
  new StatusService(),
  new HitService(),
  new DamageService(),
  new EnemyAiService(),
  contentStub,
);
const propMatcher = new PropMatcherService();

const playerStats: PermanentStats = {
  maxHP: 100,
  maxStamina: 5,
  atk: 15,
  def: 10,
  acc: 5,
  eva: 3,
  crit: 5,
  critDmg: 150,
  resist: 5,
  speed: 5,
};

const enemyStats: Record<string, PermanentStats> = {
  enemy_01: {
    maxHP: 100,
    maxStamina: 5,
    atk: 10,
    def: 5,
    acc: 5,
    eva: 3,
    crit: 5,
    critDmg: 150,
    resist: 5,
    speed: 5,
  },
};

function makeBattleState(): BattleStateV1 {
  return {
    version: 'battle_state_v1',
    phase: 'TURN',
    lastResolvedTurnNo: 0,
    rng: { seed: 'demo-seed', cursor: 0 },
    env: [],
    player: { hp: 100, stamina: 5, status: [] },
    enemies: [
      {
        id: 'enemy_01',
        name: '매수된 수비대원',
        hp: 100,
        maxHp: 100,
        status: [],
        personality: 'AGGRESSIVE',
        distance: 'ENGAGED',
        angle: 'FRONT',
      },
    ],
    environmentProps: [
      {
        id: 'chair_wooden',
        name: '나무 의자',
        keywords: ['의자', '나무 의자', '스툴'],
        effects: { damageBonus: 1.2, stunChance: 100 },
        oneTimeUse: true,
      },
      {
        id: 'bottle_glass',
        name: '유리병',
        keywords: ['병', '유리병', '술병'],
        effects: { damageBonus: 1.1, bleedStacks: 1 },
        oneTimeUse: true,
      },
    ],
  };
}

function runTurn(rawInput: string) {
  const battleState = makeBattleState();
  const propMatch = propMatcher.classify(
    rawInput,
    battleState.environmentProps ?? [],
  );
  const input: CombatTurnInput = {
    turnNo: 1,
    node: { id: 'demo_node', type: 'COMBAT', index: 0 },
    envTags: [],
    actionPlan: {
      units: [{ type: 'ATTACK_MELEE', targetId: 'enemy_01' }],
      consumedSlots: { base: 2, used: 1, bonusUsed: false },
      staminaCost: 1,
      policyResult: 'ALLOW',
      parsedBy: 'RULE',
      tier: propMatch.tier,
      prop: propMatch.prop,
      improvised: propMatch.improvised,
      flags: propMatch.flags,
      excludeFromArcRoute: propMatch.tier >= 4,
      excludeFromCommitment: propMatch.tier >= 4,
    },
    battleState,
    playerStats,
    enemyStats,
    enemyNames: { enemy_01: '매수된 수비대원' },
  };

  const output = combatService.resolveCombatTurn(input);
  const enemyHpBefore = battleState.enemies[0].hp;
  const enemyHpAfter = output.nextBattleState.enemies[0].hp;

  return {
    rawInput,
    propMatch,
    actionPlanTier: input.actionPlan.tier,
    actionPlanProp: input.actionPlan.prop?.name ?? null,
    actionPlanFlags: input.actionPlan.flags ?? null,
    excludeFromArcRoute: input.actionPlan.excludeFromArcRoute ?? false,
    serverFlags: output.serverResult.flags,
    enemyHpDelta: enemyHpAfter - enemyHpBefore,
    enemyStatusAdded: output.nextBattleState.enemies[0].status.map((s) => ({
      id: s.id,
      duration: s.duration,
      stacks: s.stacks,
    })),
    playerStatusAdded: output.nextBattleState.player.status.map((s) => ({
      id: s.id,
      duration: s.duration,
      stacks: s.stacks,
    })),
    events: output.serverResult.events.map((e) => ({
      kind: e.kind,
      text: e.text,
      tags: e.tags,
    })),
    environmentPropsRemaining: output.nextBattleState.environmentProps?.map(
      (p) => p.id,
    ),
  };
}

const scenarios = [
  { label: 'Tier 3 (평범)', input: '정면에서 검을 휘두른다' },
  { label: 'Tier 1 (의자)', input: '옆에 있는 의자를 집어 던진다' },
  { label: 'Tier 1 (유리병)', input: '술병을 깨뜨려 적에게 던진다' },
  { label: 'Tier 2 (날카로움)', input: '바닥의 유리 파편을 밟게 한다' },
  { label: 'Tier 2 (모래)', input: '모래를 얼굴에 뿌린다' },
  { label: 'Tier 4 (환상)', input: '드래곤 브레스!' },
  { label: 'Tier 4 (순간이동)', input: '순간이동해 등 뒤로 돌아간다' },
  { label: 'Tier 5 (추상)', input: 'HP를 회복한다' },
];

console.log('='.repeat(60));
console.log('창의 전투 MVP 엔드투엔드 데모');
console.log('='.repeat(60));

const results = scenarios.map((sc) => {
  console.log(`\n── ${sc.label} — "${sc.input}" ──`);
  const r = runTurn(sc.input);
  console.log(`  분류: Tier ${r.actionPlanTier}`);
  if (r.actionPlanProp) console.log(`  프롭: ${r.actionPlanProp}`);
  if (r.actionPlanFlags)
    console.log(`  플래그: ${JSON.stringify(r.actionPlanFlags)}`);
  if (r.excludeFromArcRoute) console.log('  (성향 추적 제외)');
  console.log(`  적 HP 변화: ${r.enemyHpDelta}`);
  console.log(
    `  적 상태이상: ${r.enemyStatusAdded.map((s) => s.id).join(', ') || '없음'}`,
  );
  console.log(
    `  플레이어 상태이상: ${r.playerStatusAdded.map((s) => s.id).join(', ') || '없음'}`,
  );
  console.log(`  서버 flags: ${JSON.stringify(r.serverFlags)}`);
  return { ...sc, ...r };
});

fs.writeFileSync(`${DIR}/results.json`, JSON.stringify(results, null, 2));
console.log(`\n✓ 저장: ${DIR}/results.json`);

// 요약 표
console.log('\n='.repeat(60));
console.log('요약표');
console.log('='.repeat(60));
console.log('| 시나리오 | Tier | 피해 | 상태 | 플래그 |');
for (const r of results) {
  const status = r.enemyStatusAdded.map((s) => s.id).join(',') || '-';
  const flags =
    [
      r.serverFlags?.fantasy && 'fantasy',
      r.serverFlags?.abstract && 'abstract',
      r.serverFlags?.propUsed && `prop:${r.serverFlags.propUsed.name}`,
    ]
      .filter(Boolean)
      .join(' ') || '-';
  console.log(
    `| ${r.label.padEnd(14)} | T${r.actionPlanTier} | ${String(r.enemyHpDelta).padStart(4)} | ${status.padEnd(10)} | ${flags} |`,
  );
}
