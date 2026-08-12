#!/usr/bin/env python3
"""C족 — 파이프라인 손실 (arch/101 §3-C).

같은 턴의 **입력 대 출력**을 대조한다. 후처리가 조용히 콘텐츠를 지우거나,
주입한 것이 서술에 반영되지 않는 부류. 실행은 정상이고 결과도 그럴듯해서
플레이테스트로는 안 잡힌다.

근거: arch/100 §17 — `ai_turn_logs.raw_completion` ↔ `turns.llm_output` 대조로
대사 소실 33.4%(413/1,237턴)·전멸 12턴을 발견했다. Step F-aux 가 화자 오귀속된
대사를 통째 삭제하고 있었다.

철칙(arch/101 §5): 분모 없는 판정 금지. 시간 창(--days)으로 봐야 수정 효과가
드러난다 — DB 는 과거 코드의 흔적을 계속 들고 있다.
"""
import argparse, json, pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB = ['docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At', '-c']
findings = []


def q1(sql):
    r = subprocess.run(DB + [sql], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    rows = [l for l in r.stdout.splitlines() if l.strip()]
    return rows[0] if rows else None


def report(name, violations, denominator, detail='', repro='', threshold=None):
    if denominator is None:
        verdict = 'ERROR'
    elif denominator == 0:
        verdict = 'UNDECIDABLE'
    elif threshold is not None:
        rate = violations / denominator
        verdict = 'OK' if rate <= threshold else 'VIOLATION'
    else:
        verdict = 'OK' if violations == 0 else 'VIOLATION'
    findings.append(dict(name=name, violations=violations, denominator=denominator,
                         verdict=verdict, detail=detail, repro=repro))


ap = argparse.ArgumentParser()
ap.add_argument('--days', type=int, default=7)
args = ap.parse_args()
W = f"AND t.created_at > now() - interval '{args.days} days'"

PAIR = f"""
  FROM turns t JOIN ai_turn_logs a ON a.run_id=t.run_id AND a.turn_no=t.turn_no
  WHERE t.llm_status='DONE' AND t.llm_output IS NOT NULL
    AND a.raw_completion IS NOT NULL AND t.node_type='LOCATION' {W}"""

QCNT = lambda col: f"(SELECT count(*) FROM regexp_matches({col}, '\"[^\"]{{3,}}\"','g'))"

# ── C1. 대사 소실 (원문 → 저장본) ───────────────────────────────────
base = f"""WITH p AS (SELECT {QCNT('a.raw_completion')} AS raw_q,
                           {QCNT('t.llm_output')} AS saved_q {PAIR})"""
d = q1(base + " SELECT count(*) FROM p WHERE raw_q > 0;")
v = q1(base + " SELECT count(*) FROM p WHERE raw_q > 0 AND saved_q < raw_q;")
lost = q1(base + " SELECT COALESCE(sum(raw_q-saved_q),0) FROM p WHERE saved_q < raw_q;")
#   [M2 감사 — 체크리스트 C4] 임계 0.40 은 **계약이 아니라 추세 기준선**이다.
#   소실의 57% 는 정당한 제3자 끼어들기 차단이라(arch/100 §17.2) "허용 소실률"
#   같은 설계 약속이 없다. 자동으로 정당/오삭제를 가를 수 없으므로, 실측
#   기준선 33.7%(2026-08-12) + 마진으로 **급증만** 잡는다. 절대 판정 아님.
report('대사 소실률 (추세 감시, 기준선 33.7%)', int(v or 0), int(d or 0),
       f"소실 대사 {lost}건 — 정당한 끼어들기 차단 포함. 계약 아님 (arch/100 §17.2)",
       'raw_completion ↔ llm_output 인용문 수', threshold=0.44)

# ── C2. 대사 전멸 — 말하는 정황만 남고 말이 없다 ────────────────────
v2 = q1(base + " SELECT count(*) FROM p WHERE raw_q > 0 AND saved_q = 0;")
report('대사 전멸 (전량 소실)', int(v2 or 0), int(d or 0),
       '서술은 발화를 묘사하는데 대사가 0건 — 플레이어가 내용을 못 본다',
       'raw_q>0 AND saved_q=0')

# ── C3. 서술 전량 소실 (저장본이 원문보다 현저히 짧다) ──────────────
base3 = f"""WITH p AS (SELECT length(a.raw_completion) AS r, length(t.llm_output) AS s {PAIR})"""
d3 = q1(base3 + " SELECT count(*) FROM p WHERE r > 200;")
v3 = q1(base3 + " SELECT count(*) FROM p WHERE r > 200 AND s < r * 0.5;")
report('서술 반토막 (저장본 < 원문 50%)', int(v3 or 0), int(d3 or 0),
       '후처리가 본문을 대량 삭제한 턴', repro='length 비교')

# ── C4. 주입한 fact 가 서술에 반영되는가 (불변식 27) ────────────────
#   [정정] 초판은 ui.questReveal 을 문자열로 봤으나 실제로는 객체
#   {npcId, factId, revealMode, matchedByTopic} 라 100% 오탐이 났다.
#   factId 를 콘텐츠 fact 설명으로 풀어 **핵심어가 서술에 등장하는지** 본다.
rows = subprocess.run(DB + [f"""
  SELECT COALESCE(s.scenario_id,'graymar_v1'),
         t.server_result->'ui'->'questReveal'->>'factId',
         COALESCE(t.server_result->'ui'->'questReveal'->>'revealMode','?'),
         replace(t.llm_output, chr(10), ' ')
  FROM turns t JOIN run_sessions s ON s.id=t.run_id
  WHERE t.llm_status='DONE' AND t.llm_output IS NOT NULL
    AND t.server_result->'ui'->'questReveal' ? 'factId' {W.replace('t.created_at','t.created_at')};
"""], capture_output=True, text=True).stdout.splitlines()

#   facts.json 구조: {version, description, facts: {factId: {..., keywords[]}}}
#   콘텐츠가 keywords 를 직접 들고 있으므로 description 에서 추출하지 않는다
#   (fact 공개 매칭도 같은 keywords 를 쓴다 — getFactsByKeywords).
facts_by_pack = {}
for ff in (ROOT / 'content').glob('*/facts.json'):
    data = json.loads(ff.read_text())
    raw = data.get('facts', data) if isinstance(data, dict) else data
    items = list(raw.values()) if isinstance(raw, dict) else raw
    facts_by_pack[ff.parent.name] = {
        f.get('factId'): (f.get('keywords') or [])
        for f in items if isinstance(f, dict)}
#   [정정 2] revealMode 별 분해. direct 는 "NPC가 직접 말해준다" 라 핵심어가
#   반드시 나와야 하지만, indirect/observe 는 **설계상 암시**라 핵심어 부재가
#   정상일 수 있다 (arch/58 factDelivery 3종). 게이트는 direct 에만 걸고
#   나머지는 계측으로 보고한다 — 설계가 약속하지 않은 것을 위반으로 세지 않는다.
from collections import Counter
tot, miss, samples = Counter(), Counter(), []
for line in rows:
    parts = line.split('|')
    if len(parts) < 4:
        continue
    pack, fact_id, mode, out = parts[0], parts[1], parts[2] or '?', '|'.join(parts[3:])
    kws = [k for k in facts_by_pack.get(pack, {}).get(fact_id, []) if len(k) >= 2]
    if len(kws) < 2:
        continue
    tot[mode] += 1
    if not any(k in out for k in kws):
        miss[mode] += 1
        if mode == 'direct' and len(samples) < 3:
            samples.append(f"{fact_id}({','.join(kws[:3])})")
metric = ' · '.join(f"{m} {miss[m]}/{tot[m]}" for m in ('direct', 'indirect', 'observe') if tot[m])
report('questReveal 서술 반영 — direct (불변식 27)', miss['direct'], tot['direct'],
       f"계측: {metric} — indirect/observe 는 설계상 암시라 게이트 제외. "
       + (' / '.join(samples) if samples else ''),
       'ui.questReveal.factId → facts.json keywords ↔ 서술')

# ── C5. LLM 실패율 ──────────────────────────────────────────────────
d5 = q1(f"SELECT count(*) FROM turns t WHERE t.llm_status IN ('DONE','FAILED') {W};")
v5 = q1(f"SELECT count(*) FROM turns t WHERE t.llm_status='FAILED' {W};")
report('LLM 실패율', int(v5 or 0), int(d5 or 0),
       '실패 턴은 서술 없이 커밋 — 플레이어가 재시도해야 한다',
       repro="llm_status='FAILED'", threshold=0.03)

MARK = {'VIOLATION': '❌', 'ERROR': '⚠️ ', 'UNDECIDABLE': '❔', 'OK': '✅'}
order = {'VIOLATION': 0, 'ERROR': 1, 'UNDECIDABLE': 2, 'OK': 3}
findings.sort(key=lambda f: order[f['verdict']])
print(f'# C족 파이프라인 손실 (최근 {args.days}일)\n')
for f in findings:
    pct = f" ({100*f['violations']/f['denominator']:.1f}%)" if f['denominator'] else ''
    print(f"{MARK[f['verdict']]} {f['name']:<32} {f['violations']}/{f['denominator']}{pct}")
    if f['detail']:
        print(f"      {f['detail'][:170]}")
cnt = {k: sum(1 for f in findings if f['verdict'] == k) for k in order}
print(f"\n위반 {cnt['VIOLATION']} · 판정불가 {cnt['UNDECIDABLE']} · 오류 {cnt['ERROR']} · 정상 {cnt['OK']}")
(pathlib.Path(__file__).parent / 'last_pipeline.json').write_text(
    json.dumps(findings, ensure_ascii=False, indent=2))
