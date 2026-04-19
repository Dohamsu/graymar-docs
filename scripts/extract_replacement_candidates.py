#!/usr/bin/env python3
"""반복 구문 / 치환 후보 자동 추출 스크립트.

30턴 run 의 llm_output 을 분석해 text_replacements.json 에 추가 후보가 될
반복 구문 / 표현 고착 / 클리셰 패턴을 추출한다.

추출 카테고리:
  1. 고빈도 trigram (3어절) — 전체 run 에서 5회+ 등장
  2. 고빈도 bigram (2어절) — 전체 run 에서 8회+ 등장
  3. 신체 반응 고착 — 특정 신체 부위 + 동작
  4. 배경 NPC 과등장 — 배경 NPC 이름 합계

사용법:
  python3 scripts/extract_replacement_candidates.py <run_id>

출력:
  - 콘솔 리포트 (카테고리별 후보 목록)
  - candidate_replacements_<timestamp>.json 저장 (사람 검토 후 JSON 에 병합)
"""
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def query_run(run_id: str) -> list:
    out = subprocess.check_output([
        'docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At', '-c',
        f"SELECT json_agg(json_build_object('t',turn_no,'txt',coalesce(llm_output,'')) ORDER BY turn_no) FROM turns WHERE run_id = '{run_id}'"
    ]).decode().strip()
    return json.loads(out) or []


def extract_ngrams(turns):
    """전체 run 에서 bigram/trigram 빈도 추출"""
    bigram = Counter()
    trigram = Counter()
    for t in turns:
        txt = (t.get('txt') or '').replace('"', ' ')
        # 대사 제외 (큰따옴표로 감싸진 부분 제거)
        narr = re.sub(r'"[^"]*"', '', txt)
        words = re.findall(r'[가-힣]+', narr)
        for i in range(len(words)):
            if i + 1 < len(words):
                if len(words[i]) >= 2 or len(words[i + 1]) >= 2:
                    bigram[f'{words[i]} {words[i+1]}'] += 1
            if i + 2 < len(words):
                if len(words[i]) >= 2 and len(words[i + 2]) >= 2:
                    trigram[f'{words[i]} {words[i+1]} {words[i+2]}'] += 1
    return bigram, trigram


def extract_body_patterns(turns):
    """신체 반응 + 동작 조합 빈도"""
    BODY_PARTS = ['눈', '손', '입술', '안경테', '어깨', '고개', '시선', '눈동자', '이마', '목소리', '손끝', '손가락']
    body_counts = Counter()
    for t in turns:
        txt = t.get('txt') or ''
        for part in BODY_PARTS:
            count = len(re.findall(f'(?<![가-힣]){part}(?![가-힣])', txt))
            if count > 0:
                body_counts[part] += count
    return body_counts


def extract_bg_npcs(turns):
    """배경 NPC 고유 별칭 빈도"""
    BG_NPCS = [
        '약초 노점의 노부인', '만취한 취객', '류트를 든 음유시인',
        '조용한 문서 실무자', '재빠른 골목 아이', '재빠른 구두닦이 소년',
        '목소리 큰 생선상인', '골동품 가게의 노인', '과일장수',
        '다정한 보육원 여인', '젊은 경비병',
    ]
    bg_counts = Counter()
    for t in turns:
        txt = t.get('txt') or ''
        for bg in BG_NPCS:
            c = txt.count(bg)
            if c > 0:
                bg_counts[bg] += c
    return bg_counts


def load_existing_rules():
    """현재 text_replacements.json 로드"""
    path = REPO_ROOT / 'content/graymar_v1/text_replacements.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main():
    if len(sys.argv) < 2:
        print('usage: extract_replacement_candidates.py <run_id>')
        sys.exit(1)
    run_id = sys.argv[1]

    print(f'>>> Run: {run_id}')
    turns = query_run(run_id)
    total_turns = sum(1 for t in turns if t.get('txt'))
    total_chars = sum(len(t.get('txt') or '') for t in turns)
    print(f'>>> Turns: {total_turns} / Chars: {total_chars}')

    bigram, trigram = extract_ngrams(turns)
    body = extract_body_patterns(turns)
    bg = extract_bg_npcs(turns)
    existing = load_existing_rules()

    # 현재 JSON 규칙에 이미 있는 문자열
    existing_strs = set()
    for rule in existing.get('npcApproach', {}).get('rules', []):
        existing_strs.add(rule['pattern'])
    for rule in existing.get('currency', {}).get('rules', []):
        existing_strs.add(rule['pattern'])
    for p in existing.get('repeatKillAll', {}).get('patterns', []):
        existing_strs.add(p)
    for p in existing.get('repeatSecondPlus', {}).get('patterns', []):
        existing_strs.add(p)

    print('\n=========================================')
    print('[1] 고빈도 trigram (3어절, 5회+)')
    print('=========================================')
    top_tri = [(k, v) for k, v in trigram.most_common(20) if v >= 5]
    for k, v in top_tri:
        already = ' [이미 JSON]' if any(k in ex or ex in k for ex in existing_strs) else ''
        print(f'  {v:3d}회: {k}{already}')

    print('\n=========================================')
    print('[2] 고빈도 bigram (2어절, 8회+)')
    print('=========================================')
    top_bi = [(k, v) for k, v in bigram.most_common(30) if v >= 8]
    for k, v in top_bi:
        already = ' [이미 JSON]' if any(k in ex or ex in k for ex in existing_strs) else ''
        print(f'  {v:3d}회: {k}{already}')

    print('\n=========================================')
    print('[3] 신체 부위 빈도')
    print('=========================================')
    per_turn_ratio = lambda n: f'{n/max(total_turns,1):.1f}/턴'
    for part, count in body.most_common():
        flag = ' ⚠️' if count / max(total_turns, 1) > 1.0 else ''
        print(f'  {count:3d}회 ({per_turn_ratio(count)}): {part}{flag}')

    print('\n=========================================')
    print('[4] 배경 NPC 등장 빈도')
    print('=========================================')
    for name, count in bg.most_common():
        flag = ' ❌ 과등장' if count >= 5 else (' ⚠️' if count >= 3 else '')
        print(f'  {count:3d}회: {name}{flag}')

    # JSON 후보 생성 (trigram 5회+ + bigram 10회+)
    kill_candidates = []
    for k, v in trigram.most_common():
        if v >= 5:
            if any(k in ex or ex in k for ex in existing_strs):
                continue
            # 정규식 escape + \s* 유연화
            pattern = k.replace(' ', r'\s+')
            kill_candidates.append({'phrase': k, 'count': v, 'regex': pattern})

    output_path = REPO_ROOT / f'playtest-reports/candidate_replacements_{int(time.time())}.json'
    report = {
        'runId': run_id,
        'totalTurns': total_turns,
        'totalChars': total_chars,
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'topTrigrams': [{'phrase': k, 'count': v} for k, v in top_tri],
        'topBigrams': [{'phrase': k, 'count': v} for k, v in top_bi],
        'bodyParts': dict(body),
        'bgNpcs': dict(bg),
        'killCandidates': kill_candidates[:10],  # 상위 10개 추천
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'\n>>> 후보 리포트 저장: {output_path.name}')


if __name__ == '__main__':
    main()
