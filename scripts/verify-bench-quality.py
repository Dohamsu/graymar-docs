#!/usr/bin/env python3
"""
벤치마크 결과(두 모델의 10턴)에 대한 서술 품질 검증.

입력: playtest-reports/bench_gemma4_26_vs_31.json + DB 의 turns.llm_output
출력: 어체·따옴표·마커·메타서술·반복 위반 카운트 비교표
"""

import json
import re
import subprocess
from collections import Counter, defaultdict


# 어체 감지 (완화된 휴리스틱)
REGISTER_PATTERNS = {
    'HAOCHE':  r'(?:하오|이오|시오|겠소|없소|있소|했소|되오|보시오|마시오|드리오|주시오|[소오])\s*[.?!"…]?\s*$',
    'HAEYO':   r'(?:[해돼]요|이에요|예요|어요|아요|는데요|거예요|죠|세요)\s*[.?!"…]?\s*$',
    'BANMAL':  r'(?:[야해지]|이야|거야|는데|잖아|래|거든|[어었았]\b|겠어)\s*[.?!"…]?\s*$',
    'HAPSYO':  r'(?:습니다|십니다|합니다|입니다|지요|겠습니다|하십시오|주십시오|드립니다)\s*[.?!"…]?\s*$',
    'HAECHE':  r'(?:[지야]|거든|는데|이야|걸|잖아|는걸|어|었어|았어)\s*[.?!"…]?\s*$',
}

# 메타 서술 금지 패턴
META_PATTERNS = [
    (r'\b당신은\s', 'player_second_person_start'),   # "당신은" 문장 시작
    (r'\[NPC_[A-Z_0-9]+\]', 'npc_id_leak'),
    (r'\b[Tt]urn\s?\d+', 'turn_number_leak'),
    (r'\b(활성 단서|activeClues?|pendingHint)', 'active_clues_leak'),
    (r'\b(서술|내레이션|Narrator|narrator)\b', 'meta_narrator_leak'),
    (r'\{\{[^}]+\}\}', 'template_placeholder'),
]


def load_runs():
    bench = json.load(open('playtest-reports/bench_gemma4_26_vs_31.json'))
    results = []
    for m in bench['models']:
        run_id = m['runId']
        model_id = m['modelId']
        out = subprocess.check_output([
            'docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At',
            '-c',
            # JSON 배열로 받아 내부 | 충돌 회피
            f"SELECT json_agg(json_build_object('turnNo', turn_no, 'text', coalesce(llm_output, '')) ORDER BY turn_no) FROM turns WHERE run_id = '{run_id}'",
        ]).decode('utf-8').strip()
        turns = json.loads(out) if out else []
        results.append({'modelId': model_id, 'runId': run_id, 'turns': turns})
    return results


def extract_dialogues(text):
    """큰따옴표 대사 추출 + 짝 검사"""
    dialogues = []
    opens = [m.start() for m in re.finditer(r'["\u201C]', text)]
    closes = [m.start() for m in re.finditer(r'["\u201D]', text)]
    # 단순 매칭: 순서대로 짝
    pairs = []
    all_quotes = sorted([(p, 'open') for p in opens] + [(p, 'close') for p in closes])
    stack = []
    unmatched = 0
    for pos, kind in all_quotes:
        if kind == 'open':
            stack.append(pos)
        else:
            if stack:
                start = stack.pop()
                pairs.append((start, pos))
            else:
                unmatched += 1
    unmatched += len(stack)
    for s, e in pairs:
        dialogues.append(text[s + 1:e])
    return dialogues, unmatched


def classify_register(sentence):
    """문장을 어체 5종 중 하나로 분류 (매칭 안되면 None)"""
    matches = []
    for name, pat in REGISTER_PATTERNS.items():
        if re.search(pat, sentence):
            matches.append(name)
    # HAPSYO 가 HAECHE/HAEYO 보다 엄격 → 우선
    if 'HAPSYO' in matches:
        return 'HAPSYO'
    if 'HAOCHE' in matches:
        return 'HAOCHE'
    if 'HAEYO' in matches:
        return 'HAEYO'
    if 'BANMAL' in matches:
        return 'BANMAL'
    if 'HAECHE' in matches:
        return 'HAECHE'
    return None


def analyze(text, turn_no):
    issues = []

    # 1. 따옴표 짝 + 대사 추출
    dialogues, unmatched_quotes = extract_dialogues(text)
    if unmatched_quotes:
        issues.append(('unmatched_quotes', unmatched_quotes))

    # 2. 어체 분류
    reg_counts = Counter()
    for d in dialogues:
        d = d.strip()
        if len(d) < 4:
            continue
        reg = classify_register(d)
        reg_counts[reg or 'UNKNOWN'] += 1

    # 3. 메타서술 위반
    meta_hits = []
    for pat, label in META_PATTERNS:
        for m in re.finditer(pat, text):
            # "당신은" 시작은 문장 경계 추가 검증
            if label == 'player_second_person_start':
                start = m.start()
                # 문장 시작 판단: 직전 문자가 없거나 . ! ? \n
                prev = text[start - 1] if start > 0 else '\n'
                if prev not in '.!?\n ' and start != 0:
                    continue
            meta_hits.append(label)

    # 4. 연속 단일 문장 줄바꿈 비율 (문장별 \n 남아있는지)
    lines = text.split('\n')
    sent_like_lines = [l for l in lines if l.strip() and not l.strip().startswith('@[')]
    short_sentences = [l for l in sent_like_lines if len(l) < 80 and re.search(r'[.!?。]\s*$', l.strip())]
    newline_per_sentence_ratio = len(short_sentences) / max(1, len(sent_like_lines))

    # 5. @마커 형식
    marker_all = re.findall(r'@\[([^\]]+)\]', text)
    marker_bad = [m for m in marker_all if '|' in m and '/npc-portraits/' not in m]  # pipe 가 있지만 URL 아님
    # raw marker (no @ prefix + npc-portraits URL)
    raw_marker = re.findall(r'(?:^|[^@])\[[^\]|]+\|/npc-portraits/[^\]]+\]', text)

    return {
        'turnNo': turn_no,
        'textLen': len(text),
        'dialogueCount': len(dialogues),
        'unmatchedQuotes': unmatched_quotes,
        'registerCounts': dict(reg_counts),
        'metaHits': Counter(meta_hits),
        'sentencePerLineRatio': round(newline_per_sentence_ratio, 2),
        'markerCount': len(marker_all),
        'rawMarkerLeak': len(raw_marker),
    }


def summarize(per_turn):
    reg_total = Counter()
    meta_total = Counter()
    unmatched = sum(r['unmatchedQuotes'] for r in per_turn)
    dialogues = sum(r['dialogueCount'] for r in per_turn)
    markers = sum(r['markerCount'] for r in per_turn)
    raw_markers = sum(r['rawMarkerLeak'] for r in per_turn)
    sentence_ratio = sum(r['sentencePerLineRatio'] for r in per_turn) / len(per_turn) if per_turn else 0
    for r in per_turn:
        for k, v in r['registerCounts'].items():
            reg_total[k] += v
        for k, v in r['metaHits'].items():
            meta_total[k] += v
    return {
        'turns': len(per_turn),
        'dialogueCount_total': dialogues,
        'unmatchedQuotes_total': unmatched,
        'markerCount_total': markers,
        'rawMarkerLeak_total': raw_markers,
        'registerDistribution': dict(reg_total),
        'metaViolations': dict(meta_total),
        'sentencePerLineRatio_avg': round(sentence_ratio, 2),
    }


def main():
    runs = load_runs()
    report = {}
    for r in runs:
        per = [analyze(t['text'], t['turnNo']) for t in r['turns'] if t.get('text')]
        summary = summarize(per)
        report[r['modelId']] = {'runId': r['runId'], 'summary': summary, 'perTurn': per}

    out_path = 'playtest-reports/bench_quality_verify.json'
    with open(out_path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'Saved: {out_path}')

    print('\n=== SUMMARY COMPARISON ===')
    rows = []
    for model, data in report.items():
        s = data['summary']
        rows.append((model, s))
        print(f"\n[{model}]  turns={s['turns']}")
        print(f"  dialogues={s['dialogueCount_total']}  markers={s['markerCount_total']}")
        print(f"  unmatchedQuotes={s['unmatchedQuotes_total']}  rawMarkerLeak={s['rawMarkerLeak_total']}")
        print(f"  registers={s['registerDistribution']}")
        print(f"  metaViolations={s['metaViolations']}")
        print(f"  avg sentence-per-line ratio={s['sentencePerLineRatio_avg']}")


if __name__ == '__main__':
    main()
