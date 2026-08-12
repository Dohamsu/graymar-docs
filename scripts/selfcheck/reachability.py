#!/usr/bin/env python3
"""D족 — 도달성 (arch/101 §3-D).

임계·게이트 상수가 **실제 분포에서 도달 가능한가**. 상수는 설계 의도이고
분포는 현실인데, 둘이 어긋나면 기능이 조용히 꺼진다.

근거: arch/100 §12~13 — `AGITATION_FEAR_THRESHOLD=60` 인데 fear 의 p99 가
**0.0** 이었다. 감정→행동화 4종 중 도주·회피·신고 3종이 사실상 발동 불가였고,
전 DB 14,861 NPC 행 중 조건 충족이 각 2건이었다.

판정:
  임계 > max      → UNREACHABLE  (기능이 꺼져 있다)
  임계 > p99      → NEAR_DEAD    (상위 1% 만 도달 — 사실상 꺼짐)
  임계 < p50      → ALWAYS_ON    (상시 발동 — 게이트가 무의미)
  그 외           → OK
"""
import argparse, json, pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'server' / 'src'
DB = ['docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At', '-c']


def stats(jsonb_path, table='run_sessions', unnest=None):
    """jsonb 경로의 분포 (max·p99·p50·nonzero비율·표본수)."""
    if unnest:
        sql = f"""WITH v AS (SELECT ({unnest})::numeric AS x FROM {table} s,
                     jsonb_each(s.run_state->'npcStates') e WHERE {unnest} IS NOT NULL)
        SELECT count(*), max(x),
               percentile_cont(0.99) WITHIN GROUP (ORDER BY x),
               percentile_cont(0.50) WITHIN GROUP (ORDER BY x),
               count(*) FILTER (WHERE x <> 0) FROM v;"""
    else:
        sql = f"""WITH v AS (SELECT ({jsonb_path})::numeric AS x FROM {table} WHERE {jsonb_path} IS NOT NULL)
        SELECT count(*), max(x),
               percentile_cont(0.99) WITHIN GROUP (ORDER BY x),
               percentile_cont(0.50) WITHIN GROUP (ORDER BY x),
               count(*) FILTER (WHERE x <> 0) FROM v;"""
    r = subprocess.run(DB + [sql], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    parts = r.stdout.strip().split('|')
    if len(parts) < 5 or not parts[0]:
        return None
    n = int(parts[0])
    if n == 0:
        return None
    f = lambda x: float(x) if x else 0.0
    return dict(n=n, max=f(parts[1]), p99=f(parts[2]), p50=f(parts[3]), nz=int(parts[4]))


# 코드 상수 추출 (quest-balance.config.ts)
cfg = (SRC / 'engine' / 'hub' / 'quest-balance.config.ts').read_text()
def const(name, default=None):
    m = re.search(rf'{name}\s*:\s*(-?\d+(?:\.\d+)?)', cfg)
    return float(m.group(1)) if m else default

EMO = "e.value->'emotional'->>'%s'"
# (라벨, 상수명, 분포 경로)
AXES = [
    ('FLEE/AVOID (fear)',   'AGITATION_FEAR_THRESHOLD',       EMO % 'fear'),
    ('REPORT (suspicion)',  'AGITATION_SUSPICION_THRESHOLD',  EMO % 'suspicion'),
    ('APPROACH (trust)',    'AGITATION_APPROACH_TRUST',       EMO % 'trust'),
    ('APPROACH (attach)',   'AGITATION_APPROACH_ATTACHMENT',  EMO % 'attachment'),
]

findings = []
for label, cname, path in AXES:
    thr = const(cname)
    st = stats(path, unnest=path)
    if thr is None or st is None:
        findings.append((label, cname, thr, None, 'ERROR', ''))
        continue
    if thr > st['max']:
        v = 'UNREACHABLE'
    elif thr > st['p99']:
        v = 'NEAR_DEAD'
    elif thr < st['p50']:
        v = 'ALWAYS_ON'
    else:
        v = 'OK'
    findings.append((label, cname, thr, st, v,
                     f"max {st['max']:.0f} · p99 {st['p99']:.0f} · p50 {st['p50']:.0f} · "
                     f"0아님 {100*st['nz']/st['n']:.1f}% (n={st['n']})"))

MARK = {'UNREACHABLE': '❌', 'NEAR_DEAD': '⚠️ ', 'ALWAYS_ON': '⚠️ ', 'ERROR': '⚠️ ', 'OK': '✅'}
print('# D족 도달성 — 임계 상수 ↔ 실제 분포\n')
for label, cname, thr, st, v, detail in findings:
    t = f"{thr:.0f}" if thr is not None else '?'
    print(f"{MARK[v]} {label:<22} 임계 {t:>4}  [{v}]")
    if detail:
        print(f"      {detail}")
bad = sum(1 for f in findings if f[4] in ('UNREACHABLE', 'NEAR_DEAD', 'ALWAYS_ON'))
print(f"\n도달 불가·사실상 사문화 {bad} · 정상 {sum(1 for f in findings if f[4]=='OK')}")
(pathlib.Path(__file__).parent / 'last_reachability.json').write_text(
    json.dumps([{'label': f[0], 'const': f[1], 'threshold': f[2],
                 'dist': f[3], 'verdict': f[4]} for f in findings],
               ensure_ascii=False, indent=2))
