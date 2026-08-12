#!/usr/bin/env python3
"""E족 — 콘텐츠 정합 (arch/101 §3-E).

코드가 콘텐츠에 대해 **암묵적으로 가정하는 것**을 검사한다. 콘텐츠는 코드
리뷰를 안 거치고 늘어나므로 가정이 조용히 깨진다.

근거: arch/100 §17.3 — `buildCandidateList` 가 unknownAlias 의 끝 단어를 화자
후보 이름에 넣는데, 역할명이 겹치는 NPC 들이 같은 이름을 갖게 되어 화자가
뒤바뀌고 대사가 삭제됐다 (전멸 12턴 중 9턴이 이 충돌).
"""
import json, pathlib, re, sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTENT = ROOT / 'content'
CLIENT_PUB = ROOT / 'client' / 'public'

findings = []


def report(name, violations, denominator, detail='', repro=''):
    verdict = ('ERROR' if denominator is None else
               'UNDECIDABLE' if denominator == 0 else
               'OK' if violations == 0 else 'VIOLATION')
    findings.append(dict(name=name, violations=violations,
                         denominator=denominator, verdict=verdict,
                         detail=detail, repro=repro))


def npcs_of(pack):
    f = CONTENT / pack / 'npcs.json'
    if not f.exists():
        return []
    d = json.loads(f.read_text())
    return d if isinstance(d, list) else d.get('npcs', [])


packs = sorted(p.name for p in CONTENT.iterdir() if p.is_dir())

# ── E1. 화자 후보 이름 충돌 ─────────────────────────────────────────
#   insertMarkers 가 쓰는 후보 이름 = name + unknownAlias + 별칭 끝 단어.
#   같은 이름이 2명 이상에게 붙으면 화자 귀속이 후보 순서에 의존한다.
collisions, total_names = [], 0
for pack in packs:
    names = defaultdict(set)
    for n in npcs_of(pack):
        alias = n.get('unknownAlias') or ''
        cand = [n.get('name'), alias]
        if alias and len(alias.split()) > 1:
            cand.append(alias.split()[-1])      # buildCandidateList 와 동일 규칙
        if n.get('shortAlias'):
            cand.append(n['shortAlias'])        # F-aux focusedNames 규칙
        for c in filter(None, cand):
            names[c].add(n['npcId'])
    total_names += len(names)
    for nm, ids in names.items():
        if len(ids) > 1:
            collisions.append(f"{pack}:{nm}←{len(ids)}명({','.join(sorted(ids))[:44]})")
report('화자 후보 이름 충돌', len(collisions), total_names,
       ' / '.join(collisions[:6]),
       'unknownAlias 끝 단어·shortAlias 가 팩 내 유일한가')

# ── E2. 초상화 에셋 실존 ────────────────────────────────────────────
missing, refs = [], 0
for pack in packs:
    for n in npcs_of(pack):
        url = n.get('portraitUrl') or n.get('imageUrl')
        if not url or not url.startswith('/'):
            continue
        refs += 1
        if not (CLIENT_PUB / url.lstrip('/')).exists():
            missing.append(f"{pack}:{n['npcId']}:{url}")
report('초상화 에셋 실존', len(missing), refs, ' / '.join(missing[:4]),
       'npcs.json portraitUrl ↔ client/public')

# ── E3. 프리셋 traitId 참조 무결성 (불변식 31) ──────────────────────
bad, tot = [], 0
for pack in packs:
    tf, pf = CONTENT / pack / 'traits.json', CONTENT / pack / 'presets.json'
    if not (tf.exists() and pf.exists()):
        continue
    td = json.loads(tf.read_text())
    trait_ids = {t.get('traitId') for t in (td if isinstance(td, list) else td.get('traits', []))}
    pd = json.loads(pf.read_text())
    for p in (pd if isinstance(pd, list) else pd.get('presets', [])):
        dt = p.get('defaultTraitId')
        if not dt:
            continue
        tot += 1
        if dt not in trait_ids:
            bad.append(f"{pack}:{p.get('presetId')}→{dt}")
report('프리셋 defaultTraitId 참조 실존', len(bad), tot, ' / '.join(bad[:4]),
       'presets.defaultTraitId ↔ traits.json')

# ── E4. questState 명명 규약 (arch/63 팩 계약) ──────────────────────
bad, tot = [], 0
PAT = re.compile(r'^S[0-5]_[A-Z_]+$')
for pack in packs:
    qf = CONTENT / pack / 'quest.json'
    if not qf.exists():
        continue
    txt = qf.read_text()
    for st in set(re.findall(r'"(S\d_[A-Z_]+)"', txt)):
        tot += 1
        if not PAT.match(st):
            bad.append(f"{pack}:{st}")
report('questState 명명 규약 S0~S5', len(bad), tot, ' / '.join(bad[:4]),
       'quest.json questState 명명')

# ── E5. NPC 티어 값 유효성 (불변식 23) ──────────────────────────────
VALID = {'CORE', 'SUB', 'BACKGROUND'}
bad, tot = [], 0
for pack in packs:
    for n in npcs_of(pack):
        tot += 1
        t = n.get('tier')
        if t not in VALID:
            bad.append(f"{pack}:{n['npcId']}:{t}")
report('NPC tier ∈ CORE/SUB/BACKGROUND', len(bad), tot, ' / '.join(bad[:4]))

MARK = {'VIOLATION': '❌', 'ERROR': '⚠️ ', 'UNDECIDABLE': '❔', 'OK': '✅'}
order = {'VIOLATION': 0, 'ERROR': 1, 'UNDECIDABLE': 2, 'OK': 3}
findings.sort(key=lambda f: order[f['verdict']])
print('# E족 콘텐츠 정합\n')
for f in findings:
    print(f"{MARK[f['verdict']]} {f['name']:<30} {f['violations']}/{f['denominator']}")
    if f['detail']:
        print(f"      {f['detail'][:190]}")
cnt = {k: sum(1 for f in findings if f['verdict'] == k) for k in order}
print(f"\n위반 {cnt['VIOLATION']} · 판정불가 {cnt['UNDECIDABLE']} · 정상 {cnt['OK']}")
(pathlib.Path(__file__).parent / 'last_content.json').write_text(
    json.dumps(findings, ensure_ascii=False, indent=2))
