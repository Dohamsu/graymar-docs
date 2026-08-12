#!/usr/bin/env python3
"""A족 — 불변식 감시 (arch/101 §3-A).

CLAUDE.md `Critical Design Invariants` 중 **기계 검증 가능한 것**을 질의로
등록하고 매 회 재검한다. 불변식은 이 레포의 설계 계약인데 지금까지 아무도
검증하지 않았다.

철칙(arch/101 §5): **분모 없는 판정 금지.** 0건은 "그 상태가 N번 있었는데
0건"일 때만 유효하다. N=0 이면 verdict 는 UNDECIDABLE 이지 OK 가 아니다.
"""
import argparse, json, re, subprocess, sys, pathlib

# [M2 감사 2026-08-12 — 체크리스트 C3] 시간 창 정책.
#   DB 는 과거 코드의 흔적을 계속 들고 있어서, 위반 **건수**를 세는 검사는
#   창이 없으면 수정해도 숫자가 안 준다 (#9 Heat 가 11 로 고정돼 있었다).
#   반대로 **희귀 사건**(엔딩)과 **비율** 검사는 표본을 모아야 해서 전 기간이 맞다.
#   항목마다 어느 쪽인지 명시한다 — 기본값에 맡기지 않는다.
_ap = argparse.ArgumentParser()
_ap.add_argument('--days', type=int, default=7, help='위반 건수 검사의 시간 창')
ARGS = _ap.parse_args()
WINDOW = f"{ARGS.days} days"
W = f"AND created_at > now() - interval '{WINDOW}'"

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'server' / 'src'
DB = ['docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At', '-c']


def q(sql):
    r = subprocess.run(DB + [sql], capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr.strip().splitlines()[:1]
    return [l for l in r.stdout.splitlines() if l.strip()], None


def one(sql):
    rows, err = q(sql)
    if err is not None:
        return None, err
    return (rows[0] if rows else None), None


def grep(pattern, path=SRC, extra=None):
    cmd = ['grep', '-rn', '-E', pattern, str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = [l for l in r.stdout.splitlines() if '.spec.ts' not in l and '__fixtures__' not in l]
    if extra:
        out = [l for l in out if extra(l)]
    return out


findings = []


def report(inv, name, violations, denominator, detail='', repro=''):
    """violations/denominator 로 verdict 산출 — 분모 0 이면 UNDECIDABLE."""
    if denominator is None:
        verdict = 'ERROR'
    elif denominator == 0:
        verdict = 'UNDECIDABLE'
    elif violations == 0:
        verdict = 'OK'
    else:
        verdict = 'VIOLATION'
    findings.append(dict(inv=inv, name=name, violations=violations,
                         denominator=denominator, verdict=verdict,
                         detail=detail, repro=repro))


# ── #3 Idempotency — 유니크 제약 2종 ────────────────────────────────
rows, err = q("""SELECT indexdef FROM pg_indexes
  WHERE tablename='turns' AND indexdef ILIKE '%UNIQUE%';""")
if rows is not None:
    has_turn = any('turn_no' in r and 'run_id' in r for r in rows)
    has_idem = any('idempotency_key' in r for r in rows)
    report(3, 'Idempotency 유니크 제약', (0 if has_turn else 1) + (0 if has_idem else 1), 2,
           f"(run_id,turn_no)={has_turn} (run_id,idempotency_key)={has_idem}",
           "psql: \\d turns")

# ── #6 Action slot cap = 3 ──────────────────────────────────────────
# [2회차 정정] 1회차는 server_result->state->actionSlots 를 봤으나 분모 0 —
#   실제 경로는 ui->actionSlots 다 (분모 없는 판정 금지 철칙에 걸려 UNDECIDABLE).
v, e = one(f"""SELECT count(*) FROM turns
  WHERE jsonb_array_length(COALESCE(server_result->'ui'->'actionSlots','[]'::jsonb)) > 3 {W};""")
d, _ = one(f"SELECT count(*) FROM turns WHERE server_result->'ui' ? 'actionSlots' {W};")
report(6, f'Action slot cap ≤ 3 ({WINDOW})', int(v or 0), int(d or 0),
       repro="server_result->state->actionSlots 길이 > 3")

# ── #9 Heat ±8 clamp / 0~100 ────────────────────────────────────────
#   [5회차] 시간 창 도입. DB 는 과거 코드의 흔적을 계속 들고 있어서, 수정해도
#   전 기간 집계는 줄지 않는다 (수정은 앞으로만 유효). 최근 창으로 봐야
#   "지금 코드가 계약을 지키는가" 를 판정할 수 있다.
v, e = one(f"""WITH h AS (
  SELECT run_id, turn_no, (server_result->'ui'->'worldState'->>'hubHeat')::numeric AS heat
  FROM turns WHERE server_result->'ui'->'worldState' ? 'hubHeat'
    AND created_at > now() - interval '{WINDOW}')
SELECT count(*) FROM (
  SELECT heat - lag(heat) OVER (PARTITION BY run_id ORDER BY turn_no) AS d FROM h) x
WHERE abs(d) > 8;""")
d, _ = one(f"""SELECT count(*) FROM turns WHERE server_result->'ui'->'worldState' ? 'hubHeat'
  AND created_at > now() - interval '{WINDOW}';""")
report(9, f'Heat 턴간 변동 ≤ ±8 ({WINDOW})', int(v or 0), int(d or 0),
       repro='인접 턴 hubHeat 차 — 시간 창 안')

v2, _ = one("""SELECT count(*) FROM turns
  WHERE (server_result->'ui'->'worldState'->>'hubHeat')::numeric NOT BETWEEN 0 AND 100;""")
report(9, 'Heat 범위 0~100', int(v2 or 0), int(d or 0))

# ── #17 Token Budget — 프롬프트 총량 백스톱 16,500 ───────────────────
v, e = one("""WITH p AS (
  SELECT (SELECT sum(length(m->>'content')) FROM jsonb_array_elements(llm_prompt) m) AS c
  FROM turns WHERE llm_prompt IS NOT NULL AND jsonb_typeof(llm_prompt)='array')
SELECT count(*) FROM p WHERE c > 16500;""")
d, _ = one("SELECT count(*) FROM turns WHERE llm_prompt IS NOT NULL AND jsonb_typeof(llm_prompt)='array';")
#   [5회차] 판정 기준 정정. enforceGrandTotal 은 특정 블록만 제거하는
#   best-effort 라 하드 상한이 아니다 (CLAUDE.md 불변식 17 문면도 이번에 정정).
#   실제 계약은 V12 게이트의 **발동률 ≤20%** 이므로 비율로 판정한다.
rate = (int(v or 0) / int(d)) if d and int(d) else 0.0
report(17, '프롬프트 초과 발동률 ≤20% (전 기간·비율)',
       0 if rate <= 0.20 else int(v or 0), int(d or 0),
       f'초과 {v}/{d} = {rate*100:.1f}% (상한 아님 — best-effort 백스톱)',
       'messages[].content 합계 > 16500 비율')

# ── #19 NATURAL 엔딩 최소 15턴 ──────────────────────────────────────
v, e = one("""SELECT count(*) FROM run_sessions s
  WHERE s.ending_summary IS NOT NULL
    AND (s.ending_summary->>'endingType') ILIKE '%ALL_RESOLVED%'
    AND (SELECT count(*) FROM turns t WHERE t.run_id=s.id) < 15;""")
d, _ = one("""SELECT count(*) FROM run_sessions
  WHERE ending_summary IS NOT NULL AND (ending_summary->>'endingType') ILIKE '%ALL_RESOLVED%';""")
report(19, 'NATURAL 엔딩 ≥ 15턴 (전 기간)', int(v or 0), int(d or 0))

# ── #31 프리셋 defaultTraitId 필수 ──────────────────────────────────
miss, tot = [], 0
for pf in sorted((ROOT / 'content').glob('*/presets.json')):
    data = json.loads(pf.read_text())
    ps = data if isinstance(data, list) else data.get('presets', [])
    for p in ps:
        tot += 1
        if not p.get('defaultTraitId'):
            miss.append(f"{pf.parent.name}/{p.get('presetId')}")
report(31, '프리셋 defaultTraitId 존재', len(miss), tot, ', '.join(miss[:6]),
       'content/*/presets.json')

# ── #42 speechStyle 어구 예시 금지 (따옴표 인용) ────────────────────
bad, tot = [], 0
# [2회차 정정] 1회차 정규식은 서로 다른 따옴표 쌍을 가로질러 매칭돼
#   NPC_MAIREL 의 "'그대'로 부른다 … 응답한" 같은 오탐을 냈다.
#   같은 종류의 따옴표 쌍 안쪽만 보고, 호칭 지정은 제외한다.
QUOTED = re.compile(r"'([^'\n]{4,40})'|\u2018([^\u2019\n]{4,40})\u2019")
ADDRESS_ONLY = re.compile(r'^(그대|당신|자네|너|여러분|우리|나)$')
# [5회차] 호칭 지정은 어구 예시가 아니다 — "X를 'Y'라 부른다" 는 세계관 명명
#   규약이라 speechStyle 이 반드시 명시해야 하고, 매 턴 복제돼도 그게 의도다.
#   ("상대 호칭은 '그대'" 를 면제하는 것과 같은 근거)
NAMING = re.compile(r"['\u2018][^'\u2019\n]{2,40}['\u2019]\s*(?:라|이라)\s*부른다")
for nf in sorted((ROOT / 'content').glob('*/npcs.json')):
    data = json.loads(nf.read_text())
    ns = data if isinstance(data, list) else data.get('npcs', [])
    for n in ns:
        ss = (n.get('personality') or {}).get('speechStyle')
        if not ss:
            continue
        tot += 1
        ss_scan = NAMING.sub(' ', ss)   # 호칭 지정 구간 제거 후 검사
        quoted = [g for m in QUOTED.finditer(ss_scan) for g in m.groups() if g]
        # 호칭 지정은 어구 예시가 아니다 (speechStyle 은 호칭을 명시해야 함)
        phrases = [x for x in quoted if not ADDRESS_ONLY.match(x.strip())]
        if phrases:
            bad.append(f"{nf.parent.name}/{n.get('npcId')}:{phrases[0][:20]}")
report(42, 'speechStyle 어구 예시 금지', len(bad), tot, ', '.join(bad[:6]),
       'content/*/npcs.json personality.speechStyle')

# ── #45 엔진 코드 콘텐츠 ID 리터럴 금지 ─────────────────────────────
#   [2회차 정정] CLAUDE.md 는 "접두사 규약 NPC_/LOC_/EVT_·enum 리터럴은 예외"
#   라고 명시한다. 1회차는 이 예외를 구현하지 않아 14건 전부 오탐이었다
#   (NPC_POSTURE_CHANGE·NPC_BEHAVIOR 등 enum, NPC_DYN_ 접두 상수).
#   판정 기준을 "**실제 콘텐츠 팩에 존재하는 ID**" 로 좁힌다.
real_ids = set()
for nf in (ROOT / 'content').glob('*/*.json'):
    try:
        txt = nf.read_text()
    except Exception:
        continue
    real_ids |= set(re.findall(r'"((?:NPC|LOC|EVT)_[A-Z0-9_]{2,})"', txt))
#   [3회차 정정] 2회차는 "콘텐츠 팩에 존재하는 ID" 로 좁혔으나 SignalChannel
#   같은 enum 값(NPC_BEHAVIOR)이 콘텐츠 JSON 에도 값으로 들어 있어 5건이 남았다.
#   db/types 에 선언된 enum 멤버는 콘텐츠 ID 가 아니므로 제외한다.
enum_members = set()
for tf in (SRC / 'db' / 'types').rglob('*.ts'):
    enum_members |= set(re.findall(r"'((?:NPC|LOC|EVT)_[A-Z0-9_]{2,})'", tf.read_text()))
real_ids -= enum_members
ALLOW_FILES = ('procedural-seeds.ts', 'content-loader.service.ts',
               'content.types.ts', 'test-support')
hits = []
for line in grep(r"['\"](NPC|LOC|EVT)_[A-Z0-9_]{2,}['\"]", SRC / 'engine'):
    if any(a in line for a in ALLOW_FILES):
        continue
    for lit in re.findall(r"['\"]((?:NPC|LOC|EVT)_[A-Z0-9_]{2,})['\"]", line):
        if lit in real_ids:
            hits.append(f"{line.split(':')[0].split('/')[-1]}:{line.split(':')[1]} {lit}")
engine_files = len(list((SRC / 'engine').rglob('*.ts')))
report(45, '엔진 콘텐츠 ID 리터럴 금지', len(hits), engine_files,
       ' / '.join(hits[:5]),
       "실제 팩 ID 와 일치하는 리터럴만 위반 (enum·접두규약 제외)")

# ── #49 timePhase = phaseV2 파생 미러 ───────────────────────────────
v, e = one(f"""WITH w AS (
  SELECT server_result->'ui'->'worldState' AS ws FROM turns
  WHERE server_result->'ui'->'worldState' ? 'timePhase'
    AND server_result->'ui'->'worldState' ? 'phaseV2' {W})
SELECT count(*) FROM w
WHERE (ws->>'timePhase') <> CASE WHEN ws->>'phaseV2' IN ('NIGHT','DUSK') THEN 'NIGHT' ELSE 'DAY' END;""")
d, _ = one(f"""SELECT count(*) FROM turns
  WHERE server_result->'ui'->'worldState' ? 'timePhase'
    AND server_result->'ui'->'worldState' ? 'phaseV2' {W};""")
report(49, f'timePhase = phaseV2 파생 미러 ({WINDOW})', int(v or 0), int(d or 0),
       repro='timePhase ↔ deriveTimePhaseFromV2(phaseV2) 불일치')

# ── 출력 ────────────────────────────────────────────────────────────
order = {'VIOLATION': 0, 'ERROR': 1, 'UNDECIDABLE': 2, 'OK': 3}
findings.sort(key=lambda f: (order[f['verdict']], f['inv']))
MARK = {'VIOLATION': '❌', 'ERROR': '⚠️ ', 'UNDECIDABLE': '❔', 'OK': '✅'}
print('# A족 불변식 감시\n')
for f in findings:
    print(f"{MARK[f['verdict']]} #{f['inv']:<3} {f['name']:<32} "
          f"{f['violations']}/{f['denominator']}")
    if f['detail']:
        print(f"      {f['detail'][:150]}")
cnt = {k: sum(1 for f in findings if f['verdict'] == k) for k in order}
print(f"\n위반 {cnt['VIOLATION']} · 판정불가 {cnt['UNDECIDABLE']} · 오류 {cnt['ERROR']} · 정상 {cnt['OK']}")
(pathlib.Path(__file__).parent / 'last_invariants.json').write_text(
    json.dumps(findings, ensure_ascii=False, indent=2))
