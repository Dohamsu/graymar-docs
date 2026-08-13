#!/usr/bin/env python3
"""
벤치마크 결과(두 모델의 10턴)에 대한 서술 품질 검증.

입력: playtest-reports/bench_gemma4_26_vs_31.json + DB 의 turns.llm_output
출력: 어체·따옴표·마커·메타서술·반복 위반 카운트 비교표
"""

import json
import re
import sys
import subprocess
from pathlib import Path
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


def latest_bench():
    """가장 최근 bench_*.json — 하드코딩 경로가 stale 이라 기본값을 자동 선택한다."""
    files = sorted(Path('playtest-reports').glob('bench_*.json'),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    files = [f for f in files if 'quality' not in f.name]
    if not files:
        raise SystemExit('playtest-reports/bench_*.json 이 없다 — 먼저 bench-models.py 를 돌려라')
    return files[0]


def load_runs(path=None):
    path = Path(path) if path else latest_bench()
    print(f'입력: {path}')
    bench = json.load(open(path))
    results = []
    for m in bench['models']:
        run_id = m['runId']
        model_id = m['modelId']
        out = subprocess.check_output([
            'docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At',
            '-c',
            # JSON 배열로 받아 내부 | 충돌 회피
            # [2026-08-13] llm_model_used 를 함께 받는다 — 런 단위로 집계하면
            # **교차 모델(3:7, 턴%10∈{2,5,8})이 오귀속**된다. 실측: Luna 런의
            # 무마커 대사 1건이 실은 DeepSeek 턴이라 Luna 가 94.1% 로 저평가됐다
            # (실제 100%). 모델 비교에서 이 오염은 결론을 뒤집을 수 있다.
            f"SELECT json_agg(json_build_object('turnNo', turn_no, 'text', coalesce(llm_output, ''), 'model', llm_model_used) ORDER BY turn_no) FROM turns WHERE run_id = '{run_id}'",
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

    # 4.5 [2026-08-13] **마커 커버리지** — 따옴표 대사에 화자 마커가 붙은 비율.
    #     실제 저장 형식은 `@[이름|/npc-portraits/x.webp] "대사"` (같은 줄 선행).
    #     마커가 없으면 초상화·화자 표시가 모두 실패해 "누가 말했는지 모르는 대사"가
    #     된다. DeepSeek 이 73.3% 로 무너져 있던 축이자 모델 교체의 핵심 판정 기준.
    #     주의: turns 에 raw_completion 이 없어 **서버 후처리 이후** 값이다 —
    #     모델의 원 형식 준수율이 아니라 플레이어 체감 귀속률을 잰다.
    #     문서 인용(장부·쪽지)은 대사가 아니므로 분리 집계.
    marked = unmarked_dialogue = unmarked_doc = 0
    for m in re.finditer(r'["\u201C]([^"\u201D\n]{4,})["\u201D]', text):
        line_start = text.rfind('\n', 0, m.start()) + 1
        prefix = text[line_start:m.start()]
        if re.search(r'@\[[^\]]+\]\s*$', prefix) or re.search(r'\S\s*:\s*$', prefix):
            marked += 1
        elif re.search(
            r'(적혀|쓰여|씌어|적힌|새겨|문구|글귀|글씨|서명|필체|장부|쪽지|편지|영수증|'
            r'전표|문서|종이|벽보|전단|간판|표지|읽힌다|읽는다|읽어)\s*[^"“]{0,12}$',
            prefix,
        ):
            unmarked_doc += 1
        else:
            unmarked_dialogue += 1

    # 4.6 모더레이션 거부 — is_moderated 모델(OpenAI 계열) 도입 시 필수 감시.
    #     정치음모 RPG 는 협박·폭력 서술이 정상 경로라 거부가 곧 진행 불능이다.
    refusal = bool(re.search(
        r'(죄송(하지만|합니다)|도와드릴 수 없|응답할 수 없|생성할 수 없|정책(에|상) (따라|위배)|'
        r"I'm sorry|I cannot|can't assist|violates)", text))

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
        'markedDialogue': marked,
        'unmarkedDialogue': unmarked_dialogue,
        'unmarkedDoc': unmarked_doc,
        'refusal': refusal,
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
    labeled = sum(r['markedDialogue'] for r in per_turn)
    unlabeled = sum(r['unmarkedDialogue'] for r in per_turn)
    docq = sum(r['unmarkedDoc'] for r in per_turn)
    refusals = sum(1 for r in per_turn if r['refusal'])
    return {
        'turns': len(per_turn),
        'markedDialogue_total': labeled,
        'unmarkedDialogue_total': unlabeled,
        'unmarkedDoc_total': docq,
        'markerCoverage_pct': round(100 * labeled / max(1, labeled + unlabeled), 1),
        'refusalTurns': refusals,
        'dialogueCount_total': dialogues,
        'unmatchedQuotes_total': unmatched,
        'markerCount_total': markers,
        'rawMarkerLeak_total': raw_markers,
        'registerDistribution': dict(reg_total),
        'metaViolations': dict(meta_total),
        'sentencePerLineRatio_avg': round(sentence_ratio, 2),
    }


def main():
    runs = load_runs(sys.argv[1] if len(sys.argv) > 1 else None)
    report = {}
    for r in runs:
        own, other = [], 0
        for t in r['turns']:
            if not t.get('text'):
                continue
            used = (t.get('model') or '').strip()
            # 교차 모델 턴은 제외 — 이 런의 "설정 모델"이 실제로 쓴 턴만 센다
            if used and used != r['modelId']:
                other += 1
                continue
            own.append(analyze(t['text'], t['turnNo']))
        summary = summarize(own)
        summary['excludedCrossModelTurns'] = other
        report[r['modelId']] = {'runId': r['runId'], 'summary': summary, 'perTurn': own}

    out_path = 'playtest-reports/bench_quality_verify.json'
    with open(out_path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'Saved: {out_path}')

    print('\n=== SUMMARY COMPARISON ===')
    rows = []
    for model, data in report.items():
        s = data['summary']
        rows.append((model, s))
        print(f"\n[{model}]  turns={s['turns']}"
              f"  (교차모델 제외 {s['excludedCrossModelTurns']}턴)")
        print(f"  dialogues={s['dialogueCount_total']}  markers={s['markerCount_total']}")
        print(f"  ★ 마커커버리지={s['markerCoverage_pct']}%  "
              f"(마커 {s['markedDialogue_total']} / 무마커대사 {s['unmarkedDialogue_total']} "
              f"/ 문서인용 {s['unmarkedDoc_total']})")
        print(f"  ★ 모더레이션 거부 턴={s['refusalTurns']}/{s['turns']}")
        print(f"  unmatchedQuotes={s['unmatchedQuotes_total']}  rawMarkerLeak={s['rawMarkerLeak_total']}")
        print(f"  registers={s['registerDistribution']}")
        print(f"  metaViolations={s['metaViolations']}")
        print(f"  avg sentence-per-line ratio={s['sentencePerLineRatio_avg']}")


if __name__ == '__main__':
    main()
