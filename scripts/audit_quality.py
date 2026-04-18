#!/usr/bin/env python3
"""정본 품질 감사 스크립트 (v4) — 심층 검사 자동 내장.

v3 대비 개선:
  - 1차 regex 탐지 후, 각 이슈마다 자동 심층 검사 3단계 수행:
    1) 원문 50자 context 추출 (DB psql)
    2) system-prompts.ts grep — 명시 금지어 여부 확인
    3) 대사 내부(" 내)/외부(서술) 문맥 판정
  - 최종 리포트: 실제 위반 / 회색지대 / FP (false positive) 자동 분류
  - word boundary 적용 (예: "한복" 은 "한복판" 같은 합성어 제외)
  - URL 내부 영어/한글 오매칭 방지

사용법:
  python3 scripts/audit_quality.py <run_id>

필수 환경:
  - docker exec textRpg-db psql 접근
  - server/src/llm/prompts/system-prompts.ts 접근 가능
"""
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ─── 경로 자동 탐색 ───
REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_PATH = REPO_ROOT / "server/src/llm/prompts/system-prompts.ts"
if not SYSTEM_PROMPT_PATH.exists():
    print(f"⚠️  system-prompts.ts not found at {SYSTEM_PROMPT_PATH} — 프롬프트 대조 skip")
    SYSTEM_PROMPT_TEXT = ""
else:
    SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

# ─── 탐지 패턴 ───
# 서술체 금지
HAPSYO_NARR_PAT = re.compile(r'[가-힣](습니다|입니다|했습니다|합니다)[.!?]')
PAST_TENSE_PAT = re.compile(r'[가-힣](었다|았다|이었다)[.!?]')
PRESENT_PAT = re.compile(r'[가-힣](는다|한다|린다|ㄴ다)[.!?]')

# 전지적 서술 금지 (프롬프트 line 53 명시)
META_NARR_FORBID = [
    ('궁금해졌다', 'meta_curiosity'),
    ('이해된다|이해됐다', 'meta_understanding'),
    ('결심했다|결심을 한다|마음먹었다', 'meta_decision'),
    ('흥미가 생겼다|흥미를 느꼈다', 'meta_interest'),
    ('느낌이 들었다', 'meta_feeling_v1'),
    ('느꼈다|느낀다', 'meta_feeling_v2'),  # 단독 "느낀다/느꼈다"만 — "느껴진다"는 회색
    ('생각했다|생각한다', 'meta_thought'),
    ('확신이 들었다|확신한다', 'meta_confidence'),
    ('하고 싶었다|싶은 마음이', 'meta_desire'),
    ('필요를 느낀다|필요성이 느껴진다', 'meta_need'),
    ('직감했다', 'meta_intuition'),
]

# word boundary 적용 — 합성어 제외 필수
EASTERN_FORBID = {
    '막걸리': r'(?<![가-힣])막걸리(?![가-힣])',
    '김치':   r'(?<![가-힣])김치(?![가-힣])',
    '온돌':   r'(?<![가-힣])온돌(?![가-힣])',
    '한복':   r'(?<![가-힣])한복(?![가-힣])',  # "한복판" 제외
    '된장':   r'(?<![가-힣])된장(?![가-힣])',
    '고추장': r'(?<![가-힣])고추장(?![가-힣])',
    '소주':   r'(?<![가-힣])소주(?![가-힣])',
    '막사':   r'(?<![가-힣])막사(?![가-힣])',
}
CURRENCY_FORBID = {
    '은화':   r'(?<![가-힣])은화(?![가-힣])',
    '금화':   r'(?<![가-힣])금화(?![가-힣])',
    '동전':   r'(?<![가-힣])동전(?![가-힣])',  # "동전주머니", "동전 주머니" 포함
    '닢':     r'(?<=[0-9])\s*닢(?![가-힣])',    # 숫자 뒤 "닢"만
}

URL_PAT = re.compile(r'/npc-portraits/[^\s\]"]+\.webp')
ENG_PAT = re.compile(r'\b[A-Za-z]{3,}\b')
ENG_ALLOW = {'NPC', 'ID', 'URL', 'HP', 'MP'}


# ─── 심층 검사 헬퍼 ───
def extract_context(txt: str, pos: int, radius: int = 50) -> str:
    start = max(0, pos - radius)
    end = min(len(txt), pos + radius)
    snippet = txt[start:end].replace('\n', '⏎')
    return snippet


def is_inside_dialogue(txt: str, pos: int) -> bool:
    """pos 위치가 따옴표 쌍 내부인지 판정 (pos 앞까지의 따옴표 개수가 홀수면 내부)"""
    return txt[:pos].count('"') % 2 == 1


def is_inside_url(txt: str, pos: int) -> bool:
    """pos 위치가 /npc-portraits/xxx.webp URL 내부인지"""
    for m in URL_PAT.finditer(txt):
        if m.start() <= pos < m.end():
            return True
    return False


def check_prompt_explicit(keyword: str) -> bool:
    """system-prompts.ts 에 keyword 가 명시 금지어로 언급되어 있는지"""
    if not SYSTEM_PROMPT_TEXT:
        return False
    # 프롬프트에서 키워드 주변 30자 검색 (금지/금지한다/하지마/마세요 컨텍스트 포함)
    for m in re.finditer(re.escape(keyword), SYSTEM_PROMPT_TEXT):
        start = max(0, m.start() - 30)
        end = min(len(SYSTEM_PROMPT_TEXT), m.end() + 30)
        ctx = SYSTEM_PROMPT_TEXT[start:end]
        if re.search(r'금지|금지한다|금지합니다|하지 마|하지마|마세요|피하세요|안 된다|안된다', ctx):
            return True
    return False


def classify_issue(
    keyword: str,
    turn_no: int,
    txt: str,
    pos: int,
) -> tuple[str, dict]:
    """이슈를 3단계 분류: 'real' | 'gray' | 'fp'

    Returns: (category, detail)
    """
    context = extract_context(txt, pos)
    in_dialogue = is_inside_dialogue(txt, pos)
    in_url = is_inside_url(txt, pos)
    prompt_explicit = check_prompt_explicit(keyword)

    detail = {
        'turn': turn_no,
        'keyword': keyword,
        'context': context,
        'in_dialogue': in_dialogue,
        'in_url': in_url,
        'prompt_explicit': prompt_explicit,
    }

    # FP 조건
    if in_url:
        detail['reason'] = 'URL 내부 오매칭'
        return 'fp', detail

    # 대사 내부의 2인칭/"너" 등은 문맥상 정당할 수 있음
    if in_dialogue and keyword in ('당신은', '당신이', '너는', '너를'):
        # "너"는 여전히 금지지만, 판정 전 원문 확인 필요
        if keyword.startswith('너'):
            detail['reason'] = f'대사 내부 NPC→플레이어 "{keyword}" (금지 규칙 적용)'
            return 'real', detail
        detail['reason'] = '대사 내부 2인칭 사용 (NPC 대사로는 정당)'
        return 'fp', detail

    # 프롬프트에 명시 금지어 → 실제 위반
    if prompt_explicit:
        detail['reason'] = f'system-prompts.ts 명시 금지어 + 서술 영역'
        return 'real', detail

    # 그 외는 회색지대
    detail['reason'] = '프롬프트 명시 없음 — 해석에 따라 위반'
    return 'gray', detail


# ─── 메인 실행 ───
def query_run(run_id: str) -> list:
    out = subprocess.check_output([
        'docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At', '-c',
        f"SELECT json_agg(json_build_object('t',turn_no,'txt',coalesce(llm_output,'')) ORDER BY turn_no) FROM turns WHERE run_id = '{run_id}'"
    ]).decode().strip()
    return json.loads(out) or []


def run_audit(run_id: str):
    data = query_run(run_id)

    # 카테고리별 수집
    buckets = {
        'real': [],
        'gray': [],
        'fp': [],
    }
    stats = {
        'turns': 0,
        'chars': 0,
        'dialogues': 0,
        'narr_past': 0,
        'narr_present': 0,
        'narr_hapsyo': [],
        'exc_real': 0,
        'marker_coverage': (0, 0),  # marked, total
    }
    first_sent_start = Counter()
    npc_markers = Counter()

    total_marked = 0
    total_dialogue = 0

    for t in data:
        txt = t.get('txt', '') or ''
        if not txt:
            continue
        turn_no = t['t']
        stats['turns'] += 1
        stats['chars'] += len(txt)

        narr_only = re.sub(r'"[^"]*"', '', txt)

        # A. 예외 빠른 검사 (따옴표 홀수, 중첩 마커)
        if txt.count('"') % 2 == 1:
            stats['exc_real'] += 1
            buckets['real'].append({
                'cat': 'quote_odd',
                'turn': turn_no,
                'reason': '따옴표 홀수 — 대사 경계 오류',
                'context': '',
            })
        if '@[@[' in txt:
            stats['exc_real'] += 1
            buckets['real'].append({
                'cat': 'nested_marker',
                'turn': turn_no,
                'reason': '중첩 @마커 — 서버 후처리 실패',
                'context': '',
            })

        # B. 서술체
        for m in HAPSYO_NARR_PAT.finditer(narr_only):
            cat, detail = classify_issue('합쇼체', turn_no, txt, m.start())
            detail['cat'] = 'hapsyo_narr'
            buckets[cat].append(detail)

        for m in PAST_TENSE_PAT.finditer(narr_only):
            stats['narr_past'] += 1
        for m in PRESENT_PAT.finditer(narr_only):
            stats['narr_present'] += 1

        # C. 대사 카운팅
        dialogues = re.findall(r'"([^"]+)"', txt)
        for d in dialogues:
            if len(d) >= 2:
                total_dialogue += 1
        marked = len(re.findall(r'@\[[^\]]+\]\s*["\u201C]', txt))
        total_marked += marked

        # D. 전지적 서술 금지어
        for pat_str, label in META_NARR_FORBID:
            for m in re.finditer(pat_str, narr_only):
                # narr_only 에서 찾았으므로 원본 txt 에서 대응 pos 찾기
                needle = m.group(0)
                orig_pos = txt.find(needle)
                if orig_pos < 0:
                    continue
                cat, detail = classify_issue(needle, turn_no, txt, orig_pos)
                detail['cat'] = f'meta_narr:{label}'
                buckets[cat].append(detail)

        # E. 세계관
        for word, pat_str in EASTERN_FORBID.items():
            for m in re.finditer(pat_str, txt):
                cat, detail = classify_issue(word, turn_no, txt, m.start())
                detail['cat'] = 'eastern'
                buckets[cat].append(detail)
        for word, pat_str in CURRENCY_FORBID.items():
            for m in re.finditer(pat_str, txt):
                cat, detail = classify_issue(word, turn_no, txt, m.start())
                detail['cat'] = 'currency'
                buckets[cat].append(detail)
        # 영어 누출 (URL 제외)
        txt_no_url = URL_PAT.sub('', txt)
        for m in ENG_PAT.finditer(txt_no_url):
            word = m.group(0)
            if word in ENG_ALLOW or word.lower() in {'webp', 'png'}:
                continue
            buckets['real'].append({
                'cat': 'english',
                'turn': turn_no,
                'keyword': word,
                'reason': 'URL 외 영어 단어 누출',
                'context': extract_context(txt_no_url, m.start()),
                'in_dialogue': False,
                'in_url': False,
                'prompt_explicit': True,
            })
        # "너" 호칭 (대사 내부)
        for d_match in re.finditer(r'"([^"]+)"', txt):
            d_content = d_match.group(1)
            for ban in ['너는', '너를', '너에게']:
                if ban in d_content:
                    buckets['real'].append({
                        'cat': 'second_person_ban',
                        'turn': turn_no,
                        'keyword': ban,
                        'reason': f'NPC 대사 내 "{ban}" 사용 (프롬프트: 그대/당신만 허용)',
                        'context': d_content[:60],
                        'in_dialogue': True,
                        'in_url': False,
                        'prompt_explicit': True,
                    })

        # F. 서술 시작 "당신은"
        first_sent_m = re.match(r'([^.!?\n]{5,80})[.!?\n]', narr_only.strip())
        if first_sent_m:
            first = first_sent_m.group(1).strip()
            if re.match(r'^당신(은|이)\s', first):
                buckets['real'].append({
                    'cat': 'narr_start_2nd',
                    'turn': turn_no,
                    'keyword': '당신은/당신이',
                    'reason': '서술 첫 문장이 "당신은/당신이"로 시작 — 프롬프트 금지',
                    'context': first[:80],
                    'in_dialogue': False,
                    'in_url': False,
                    'prompt_explicit': True,
                })
            if re.match(r'^당신(은|이)', first):
                first_sent_start['당신'] += 1
            elif re.match(r'^@\[', first):
                first_sent_start['@NPC'] += 1
            elif re.match(r'^[가-힣]+(이|가)\s', first):
                first_sent_start['NPC/환경 주어'] += 1
            else:
                first_sent_start['기타'] += 1

        # G. NPC 마커
        for m in re.findall(r'@\[([^\]|]+)(?:\|[^\]]+)?\]', txt):
            npc_markers[m.strip()] += 1

    stats['marker_coverage'] = (total_marked, total_dialogue)
    return data, buckets, stats, first_sent_start, npc_markers


def print_report(run_id: str, buckets: dict, stats: dict, first_start: Counter, npc_markers: Counter):
    print('=' * 70)
    print(f'RUN: {run_id}  |  turns: {stats["turns"]}  |  chars: {stats["chars"]}')
    print(f'avg narrative: {stats["chars"] // max(stats["turns"], 1)}자  |  dialogues: {stats["marker_coverage"][1]}')
    print('=' * 70)

    real = buckets['real']
    gray = buckets['gray']
    fp = buckets['fp']

    print(f'\n[🎯 자동 분류 결과]')
    print(f'  ❌ 실제 위반 (real)   : {len(real):3d}건')
    print(f'  ⚠️  회색지대 (gray)    : {len(gray):3d}건')
    print(f'  ✅ FP (false positive): {len(fp):3d}건')

    # ── 실제 위반 상세 ──
    if real:
        print(f'\n[❌ 실제 위반 {len(real)}건]')
        by_cat = defaultdict(list)
        for it in real:
            by_cat[it.get('cat', '?')].append(it)
        for cat, items in by_cat.items():
            print(f'  [{cat}] {len(items)}건')
            for it in items[:3]:
                kw = it.get("keyword", "?")
                ctx = it.get("context", "")
                print(f'    턴 {it["turn"]:3d} "{kw}": ...{ctx[:100]}...')
                print(f'         이유: {it.get("reason","?")}')
            if len(items) > 3:
                print(f'    ... +{len(items) - 3}건 더')

    # ── 회색지대 상세 ──
    if gray:
        print(f'\n[⚠️  회색지대 {len(gray)}건 — 재해석 필요]')
        by_cat = defaultdict(list)
        for it in gray:
            by_cat[it.get('cat', '?')].append(it)
        for cat, items in by_cat.items():
            print(f'  [{cat}] {len(items)}건')
            for it in items[:2]:
                kw = it.get("keyword", "?")
                ctx = it.get("context", "")
                print(f'    턴 {it["turn"]:3d} "{kw}": ...{ctx[:100]}...')
                print(f'         이유: {it.get("reason","?")}')

    # ── FP 요약 ──
    if fp:
        by_cat = defaultdict(int)
        for it in fp:
            by_cat[it.get('cat', '?')] += 1
        print(f'\n[✅ FP {len(fp)}건 — 자동 제외]')
        for cat, n in by_cat.items():
            print(f'    [{cat}] {n}건 (URL 내부/대사 내 정당 사용 등)')

    # ── 통계 ──
    print(f'\n[기본 통계]')
    total_endings = stats['narr_past'] + stats['narr_present']
    past_pct = stats['narr_past'] / total_endings * 100 if total_endings else 0
    print(f'  과거형 비율: {past_pct:.1f}%  (past={stats["narr_past"]} / present={stats["narr_present"]})')
    marked, total = stats['marker_coverage']
    cov = marked / total * 100 if total else 0
    print(f'  marker_coverage: {cov:.1f}%  ({marked}/{total})')
    print(f'  첫 문장 시작 분포: {dict(first_start)}')
    print(f'  top NPC markers: {dict(npc_markers.most_common(5))}')

    # ── 점수 ──
    real_weighted = len(real) * 3
    gray_weighted = len(gray) * 0.5
    score = max(0, 100 - real_weighted - gray_weighted)
    print(f'\n[종합 점수]')
    print(f'  실제 위반 {len(real)}건 × 3 + 회색 {len(gray)}건 × 0.5 = {real_weighted + gray_weighted}')
    print(f'  >>> 품질 점수: {score:.1f}/100')


def main():
    if len(sys.argv) < 2:
        print("usage: audit_quality.py <run_id>")
        sys.exit(1)
    run_id = sys.argv[1]
    data, buckets, stats, first_start, npc_markers = run_audit(run_id)
    print_report(run_id, buckets, stats, first_start, npc_markers)


if __name__ == '__main__':
    main()
