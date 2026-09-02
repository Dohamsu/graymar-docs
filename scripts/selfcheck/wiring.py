#!/usr/bin/env python3
"""W족 — 배선 정합 (arch/112 §9.2 P3-C 정적층).

코어 함수가 전부 통과한 채 **배선**에서 난 결함 부류를 정적으로 잡는다
(2026-09-02 실측: 결함 A 아크 무커밋 진행 — `currentRoute` 를 커밋 신호로 오용,
결함 B 유령 `[정보 전달]` — nano 가 답한 `factRevealed` 를 서버 대조 없이 하드 지시로).
DB 불필요 · LLM 호출 0 · 서버 재시작 불필요.

  W1  ui 부착 ↔ UIBundle 타입      — `result.ui.X =` 전수가 타입 필드인가 (arch/100 §14 "조용히 꺼진 배선")
  W1b 레거시 캐스트 계측            — `ui as Record<string, unknown>`/`ui as any` 로 타입을 우회하는 읽기·쓰기 수
  W2  nano 출력 필드 ↔ 소비·검증   — 프롬프트가 소비하는 nano JSON 필드 중 상태를 이름하는 것에 서버 검증/정규화가 있는가
  W3  아크 커밋 정본 단일성         — `arcState.currentRoute` 를 조건식에서 커밋 신호로 쓰는 코드 (정본은 isArcCommitted)

철칙(arch/101 §5): 분모 없는 판정 금지 · 위반 상위 건은 원문 대조 후에만 결함 보고.
수용 예외는 baseline.json entries[].id 가 'W' 로 시작하는 항목 (expires 유예).
"""
import argparse, datetime, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'server' / 'src'
findings = []


def report(name, violations, denominator, detail='', repro='', items=None):
    if denominator is None:
        verdict = 'ERROR'
    elif denominator == 0:
        verdict = 'UNDECIDABLE'
    else:
        verdict = 'OK' if violations == 0 else 'VIOLATION'
    findings.append(dict(name=name, violations=violations, denominator=denominator,
                         verdict=verdict, detail=detail, repro=repro, items=items or []))


def ts_files(sub=''):
    for p in (SRC / sub).rglob('*.ts'):
        if p.name.endswith('.spec.ts') or p.name.endswith('.d.ts'):
            continue
        yield p


def rel(p):
    return str(p.relative_to(ROOT))


def load_baseline():
    try:
        b = json.loads((pathlib.Path(__file__).parent / 'baseline.json').read_text())
    except Exception:
        return {}
    today = datetime.date.today().isoformat()
    out = {}
    for e in b.get('entries', []):
        if str(e.get('id', '')).startswith('W') and e.get('expires', '9999') >= today:
            out[e['id']] = e
    return out


BASE = load_baseline()

# ── W1. ui 부착 ↔ UIBundle ──────────────────────────────────────────
sr = (SRC / 'db' / 'types' / 'server-result.ts').read_text(encoding='utf-8')
m = re.search(r'export type UIBundle = \{(.*?)\n\};', sr, re.S)
ui_fields = set(re.findall(r'^  (\w+)\??:', m.group(1), re.M)) if m else set()

ATTACH = re.compile(r'(?:\.ui|\bui)(?: as (?:any|Record<string, unknown>)\))?\.(\w+)\s*=[^=]')
attach_sites = []   # (file, line, field, typed?)
for p in ts_files('turns'):
    for i, line in enumerate(p.read_text(encoding='utf-8').split('\n'), 1):
        # `ui.X =` 만 — `ui.X ==`·`ui.X ===` 제외, 대입 우변이 있는 문장만
        for mm in ATTACH.finditer(line):
            field = mm.group(1)
            attach_sites.append((rel(p), i, field, field in ui_fields))
untyped = [s for s in attach_sites if not s[3]]
untyped = [s for s in untyped if f"W1:{s[2]}" not in BASE]
report('W1 ui 부착 ↔ UIBundle 타입', len(untyped), len(attach_sites),
       ('미타입 필드: ' + ', '.join(sorted({f"{s[2]}({s[0].split('/')[-1]}:{s[1]})" for s in untyped})))
       if untyped else f'부착 필드 {len({s[2] for s in attach_sites})}종 전부 UIBundle 에 타입 있음',
       'grep -rnE "\\.ui\\.\\w+ =" server/src/turns ↔ db/types/server-result.ts UIBundle',
       [dict(file=s[0], line=s[1], field=s[2]) for s in untyped])

# ── W1b. 레거시 캐스트 계측 ─────────────────────────────────────────
CAST = re.compile(r'\bui as (?:Record<string, unknown>|any)')
cast_sites = []
for p in ts_files():
    for i, line in enumerate(p.read_text(encoding='utf-8').split('\n'), 1):
        if CAST.search(line):
            cast_sites.append((rel(p), i, line.strip()[:90]))
by_file = {}
for f, _, _ in cast_sites:
    by_file[f.split('/')[-1]] = by_file.get(f.split('/')[-1], 0) + 1
report('W1b ui 캐스트 우회 (계측)', 0, max(len(cast_sites), 1),
       f"{len(cast_sites)}곳 — " + ' · '.join(f"{k} {v}" for k, v in sorted(by_file.items(), key=lambda x: -x[1])[:6])
       + ' (타입이 있는 필드를 캐스트로 읽는 레거시. 0 이 목표, 증가는 회귀)',
       'grep -rn "ui as Record<string, unknown>\\|ui as any" server/src',
       [dict(file=f, line=i, code=c) for f, i, c in cast_sites])

# ── W2. nano 출력 필드 ↔ 소비·검증 ─────────────────────────────────
def iface_fields(path, name):
    t = (SRC / path).read_text(encoding='utf-8')
    mm = re.search(r'export interface ' + name + r' \{(.*?)\n\}', t, re.S)
    if not mm:
        return []
    # 최상위 필드만 (중첩 객체 내부 제외: 들여쓰기 2칸)
    return re.findall(r'^  (\w+)\??:', mm.group(1), re.M)

consumers = ''
for p in ('llm/prompts/prompt-builder.service.ts', 'llm/llm-worker.service.ts', 'llm/context-builder.service.ts'):
    consumers += (SRC / p).read_text(encoding='utf-8')
STATE_LIKE = re.compile(r'(?i:fact|npc|signal|shift|level|type|delivery|choices|stance)|[a-z]Id$')
VALIDATE_CTX = re.compile(r'VALID|ALLOWED|validat|includes\(|normalize|clamp|find\(|has\(|new Set|Array\.isArray|typeof |=== null|\? .* : null', re.I)

def validation_refs(field, director_path, core_glob):
    refs = []
    t = (SRC / director_path).read_text(encoding='utf-8').split('\n')
    for i, line in enumerate(t):
        if re.search(r'\b\w+\.' + field + r'\b', line):
            window = '\n'.join(t[max(0, i - 3): i + 8])  # 파서가 raw 를 받아 6줄 뒤에서 clamp 하는 패턴까지
            if VALIDATE_CTX.search(window):
                refs.append(f"{director_path.split('/')[-1]}:{i + 1}")
    for p in (SRC / 'llm').glob(core_glob):
        if p.name.endswith('.spec.ts'):
            continue
        if re.search(r'\b' + field + r'\b', p.read_text(encoding='utf-8')):
            refs.append(p.name)
    return refs

w2_rows, w2_viol, w2_den = [], 0, 0
for iface, path, var, core_glob in (
    ('NanoEventResult', 'llm/nano-event-director.service.ts', 'nanoEventHint', 'nano-*.core.ts'),
    ('NpcReactionResult', 'llm/npc-reaction-director.service.ts', 'npcReaction', 'npc-reaction*.core.ts'),
):
    for field in iface_fields(path, iface):
        used = len(re.findall(r'\b' + var + r'\??\.' + field + r'\b', consumers))
        if used == 0:
            continue
        state_like = bool(STATE_LIKE.search(field))
        refs = validation_refs(field, path, core_glob) if state_like else []
        row = dict(iface=iface, field=field, consumed=used, state_like=state_like, validated=bool(refs), refs=refs[:3])
        w2_rows.append(row)
        if state_like:
            w2_den += 1
            if not refs and f"W2:{iface}.{field}" not in BASE:
                w2_viol += 1
unval = [r for r in w2_rows if r['state_like'] and not r['validated'] and f"W2:{r['iface']}.{r['field']}" not in BASE]
report('W2 nano 상태형 출력 필드 ↔ 서버 검증', w2_viol, w2_den,
       ('미검증 상태형 필드: ' + ', '.join(f"{r['iface']}.{r['field']}(소비 {r['consumed']})" for r in unval)) if unval
       else f"상태형 {w2_den}필드 전부 검증·정규화 참조 있음 · 자유 텍스트 {sum(1 for r in w2_rows if not r['state_like'])}필드는 계측만",
       'nano JSON 필드 → prompt-builder/worker 소비 ↔ director 검증 블록·normalize*Core',
       w2_rows)

# ── W3. 아크 커밋 정본 단일성 ────────────────────────────────────────
COND = re.compile(r'(\bif \(|&&|\|\||\?\s|^\s*!|\breturn\b)')
SETTER_OK = re.compile(r'arcRouteTag|commitmentDelta|switchRoute|currentRoute: |currentRoute !== null|isArcCommitted|commitment === 3|\?\? \'\'|\?\? null|\?\? undefined|as string|`')
w3 = []
for p in ts_files():
    if p.name in ('arc.service.ts', 'arc-stage.core.ts', 'arc-state.ts', 'region-state.ts'):
        continue
    lines = p.read_text(encoding='utf-8').split('\n')
    for i, line in enumerate(lines, 1):
        if 'currentRoute' not in line or line.strip().startswith(('//', '*')):
            continue
        # 조건이 여러 줄이면 앞 2줄에 정본(isArcCommitted)이 있는지 본다 — 삼항 연속행 오탐(C6)
        if not COND.search(line) or SETTER_OK.search('\n'.join(lines[max(0, i - 3): i])):
            continue
        key = f"W3:{p.name}:{line.strip()[:40]}"
        if key in BASE:
            continue
        w3.append(dict(file=rel(p), line=i, code=line.strip()[:110]))
den3 = sum(1 for p in ts_files() for l in p.read_text(encoding='utf-8').split('\n') if 'currentRoute' in l)
report('W3 아크 커밋 판정 정본 단일성', len(w3), den3,
       ('조건식에서 currentRoute 를 커밋 신호로 사용: ' + ' · '.join(f"{x['file'].split('/')[-1]}:{x['line']}" for x in w3)
        + ' — 정본은 arc-stage.core isArcCommitted (ARC_HINT 이벤트가 커밋 전에도 currentRoute 를 채운다)') if w3
       else 'isArcCommitted 이외의 커밋 판정 없음',
       'grep -rn currentRoute server/src | 조건식 · setter/표시/로그 제외', w3)

# ── 출력 ────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--json', action='store_true')
args = ap.parse_args()
MARK = {'VIOLATION': '❌', 'ERROR': '⚠️ ', 'UNDECIDABLE': '❔', 'OK': '✅'}
order = {'VIOLATION': 0, 'ERROR': 1, 'UNDECIDABLE': 2, 'OK': 3}
findings.sort(key=lambda f: order[f['verdict']])
if args.json:
    print(json.dumps(findings, ensure_ascii=False, indent=2))
else:
    print('# W족 배선 정합 (arch/112 P3-C)\n')
    for f in findings:
        pct = f" ({100 * f['violations'] / f['denominator']:.1f}%)" if f['denominator'] else ''
        print(f"{MARK[f['verdict']]} {f['name']:<34} {f['violations']}/{f['denominator']}{pct}")
        if f['detail']:
            print(f"      {f['detail'][:300]}")
        if f['name'].startswith('W3') and f['items']:
            for x in f['items']:
                print(f"      · {x['file']}:{x['line']}  {x['code']}")
        if f['name'].startswith('W2') and f['items']:
            print('      ' + ' · '.join(f"{r['field']}{'✓' if r['validated'] else ('✗' if r['state_like'] else '~')}" for r in f['items']))
    cnt = {k: sum(1 for f in findings if f['verdict'] == k) for k in order}
    print(f"\n위반 {cnt['VIOLATION']} · 판정불가 {cnt['UNDECIDABLE']} · 오류 {cnt['ERROR']} · 정상 {cnt['OK']}")
    if BASE:
        print(f"(baseline 수용 {len(BASE)}건 적용)")
(pathlib.Path(__file__).parent / 'last_wiring.json').write_text(
    json.dumps(findings, ensure_ascii=False, indent=2))
