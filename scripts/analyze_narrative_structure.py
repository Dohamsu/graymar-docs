#!/usr/bin/env python3
"""서술 구조 수렴도 계측 정본 (arch/110).

최근 45일 LOCATION 턴의 오프닝 유형·문단 구조·종결 패턴 분포를 측정한다.
개시 다양화(opener-directive.core) 전후 비교용 — 목표 지표:
  - 최대 개시 유형 비율 ≤ 35% (배포 전 환경·시간대 60%)
  - 첫 두 단어 최빈 비율 < 3% (배포 전 "푸르스름한 여명이" 6.2%)
  - 대사(D) 개시 비율 > 0% (배포 전 0% — 대화 잠금 턴 리셋 금지 처방)
사용: python3 scripts/analyze_narrative_structure.py
"""
import subprocess, json, re, collections

SQL = """
SELECT json_build_object('n', llm_output) FROM turns
WHERE node_type='LOCATION' AND llm_status='DONE' AND llm_output IS NOT NULL
  AND created_at > now() - interval '45 days'
ORDER BY created_at DESC LIMIT 800;
"""
out = subprocess.run(
    ["docker","exec","textRpg-db","psql","-U","user","-d","textRpg","-t","-A","-c",SQL],
    capture_output=True, text=True).stdout
narratives = []
for line in out.splitlines():
    line=line.strip()
    if not line: continue
    try: narratives.append(json.loads(line)["n"])
    except Exception: pass

print(f"표본: {len(narratives)}턴\n")

# ── 1. 오프닝(첫 문장) 유형 분류 ──
def first_sentence(t):
    t = t.strip()
    # 첫 문단 첫 문장
    m = re.split(r'(?<=[.다요])\s', t, 1)
    return m[0][:80]

opener_type = collections.Counter()
opener_first_words = collections.Counter()
TIME_WEATHER = re.compile(r'^(이른 새벽|새벽|아침|한낮|정오|늦은 오후|오후|해질|황혼|저녁|밤|자정|깊은 밤|동이|여명|박명)')
SENSE = re.compile(r'(바람|공기|냄새|향|소리|빛|어둠|안개|비가|눈발|추위|온기|한기|습기|햇살|달빛|등불|그림자)')
for n in narratives:
    fs = first_sentence(n)
    w = fs.split()[0] if fs.split() else ''
    opener_first_words[w] += 1
    if TIME_WEATHER.match(fs): opener_type['시간대 개시'] += 1
    elif fs.startswith('@[') or re.match(r'^[가-힣]+[이가은는]의? ', fs) and not SENSE.search(fs.split()[0]): opener_type['인물 개시'] += 1
    elif SENSE.search(fs[:30]): opener_type['환경·감각 개시'] += 1
    else: opener_type['기타'] += 1

total = len(narratives)
print("── 첫 문장 유형 ──")
for k,v in opener_type.most_common():
    print(f"  {k}: {v} ({100*v/total:.1f}%)")

print("\n── 첫 단어 상위 15 ──")
for w,c in opener_first_words.most_common(15):
    print(f"  {w}: {c} ({100*c/total:.1f}%)")

# ── 2. 구조: 문단 수·첫 대사 위치·대사 유무 ──
para_counts = collections.Counter()
first_dialogue_para = collections.Counter()  # 대사가 처음 등장하는 문단 index (1-base)
struct_pattern = collections.Counter()  # 문단별 서술(N)/대사(D) 시퀀스
for n in narratives:
    paras = [p.strip() for p in re.split(r'\n\s*\n|\n/\s*\n| / ', n) if p.strip()]
    # 마커 형식: @[별칭|ID] "..."
    kinds = ['D' if p.startswith('@[') else 'N' for p in paras]
    para_counts[len(paras)] += 1
    seq = ''.join(kinds)
    struct_pattern[seq] += 1
    fd = seq.find('D')
    first_dialogue_para['없음' if fd<0 else fd+1] += 1

print("\n── 문단 수 분포 ──")
for k in sorted(para_counts):
    v=para_counts[k]; print(f"  {k}문단: {v} ({100*v/total:.1f}%)")

print("\n── 첫 대사 등장 문단 ──")
for k,v in sorted(first_dialogue_para.items(), key=lambda x:-x[1]):
    print(f"  {k}: {v} ({100*v/total:.1f}%)")

print("\n── 구조 시퀀스 상위 10 (N=서술, D=대사) ──")
for s,c in struct_pattern.most_common(10):
    print(f"  {s or '(단일)'}: {c} ({100*c/total:.1f}%)")

# ── 3. 종결 문장 패턴 ──
END_TYPE = collections.Counter()
for n in narratives:
    tail = n.strip()[-120:]
    last_para = [p for p in re.split(r'\n\s*\n|\n/\s*\n| / ', n) if p.strip()][-1]
    if last_para.startswith('@['): END_TYPE['대사로 종결'] += 1
    elif re.search(r'(소리|울리|들려|메아리)', last_para[-60:]): END_TYPE['소리로 종결'] += 1
    elif re.search(r'(시선|눈길|바라본|응시|살핀)', last_para[-60:]): END_TYPE['시선으로 종결'] += 1
    else: END_TYPE['기타(동작 등)'] += 1
print("\n── 종결 유형 ──")
for k,v in END_TYPE.most_common():
    print(f"  {k}: {v} ({100*v/total:.1f}%)")

# ── 4. 오프닝 상투구 (첫 문장 bigram) ──
big = collections.Counter()
for n in narratives:
    fs = first_sentence(n)
    ws = fs.split()
    if len(ws)>=2: big[' '.join(ws[:2])] += 1
print("\n── 첫 두 단어 상위 12 ──")
for w,c in big.most_common(12):
    print(f"  {w}: {c} ({100*c/total:.1f}%)")
