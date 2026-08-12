#!/usr/bin/env python3
"""jsonb payload 키 ↔ 코드 읽기 키 대조 감사 (arch/100 §16).

## 무엇을 잡는가

서버 모듈 간에 오가는 payload 는 대부분 `Record<string, unknown>` 으로 캐스팅돼
타입 검사를 빠져나간다. 여기서 키 이름을 잘못 읽으면 **컴파일도 통과하고
테스트도 통과하고 결과도 그럴듯하다** — `?? 기본값` 폴백이 조용히 대신 들어가
기능만 꺼진다.

실측 사례 (2026-08-12, arch/100 §14):
    llm-worker 가 `ui.actionContext.actionType` 을 읽었으나 정본 키는
    `parsedType`. 폴백 `'TALK'` 가 100% 발동해 NpcReactionDirector 의 행동
    급변 인식·적대 분기·refusalLevel 단조성이 통째로 무발동이었다.
    전 DB 1,079턴 중 `actionType` 키 보유 0건.

## 원리

**DB jsonb 에 실제로 존재하는 키 집합이 정답지다.** 코드가 그 payload 에서
읽는 키가 정답지에 없으면 그 읽기는 항상 undefined 다.

## 한계 (오검출 3종 — 반드시 수동 대조할 것)

1. **폴백 체인은 정상이다.** `a?.parsedType ?? a?.actionType ?? '기본'` 처럼
   정본 키를 먼저 보는 방어 코드는 2순위 키가 DB 에 없어도 옳다.
2. **희귀 상태의 키는 판정 불가.** 엔딩·전투 종료처럼 드문 경로에서만 쓰이는
   키는 표본에 없을 뿐 오타가 아닐 수 있다. DB 에 그 상태가 몇 건인지 함께 볼 것.
3. **변수명 정규식이 거칠다.** `st`, `ui` 같은 짧은 이름은 동명이인을 긁는다.

따라서 이 스크립트의 출력은 **후보 목록**이지 결론이 아니다. 각 건마다
① 쓰기 지점 grep ② 폴백 체인 여부 ③ 해당 상태의 DB 표본 수를 확인한다.

## 사용

    python3 scripts/audit_payload_keys.py            # 전체
    python3 scripts/audit_payload_keys.py --lifetime # 기간 제한 없이(희귀 키용)
"""

import argparse
import re
import subprocess
import sys
from collections import defaultdict

SRC = 'server/src'
DB = ['docker', 'exec', 'textRpg-db', 'psql', '-U', 'user', '-d', 'textRpg', '-At', '-c']

# (라벨, 키 추출 SQL — {W} 에 기간 필터, payload 를 담는 변수명 정규식)
TARGETS = [
    (
        'ui.actionContext',
        "SELECT DISTINCT jsonb_object_keys(server_result->'ui'->'actionContext') "
        "FROM turns WHERE server_result->'ui' ? 'actionContext' {W};",
        r'\b(actionCtx\w*|acFor\w*)\b',
    ),
    (
        'server_result.ui',
        "SELECT DISTINCT jsonb_object_keys(server_result->'ui') FROM turns WHERE true {W};",
        r'\b(ui|uiAny|uiData|uiForRev|uiForIntroGate)\b',
    ),
    (
        'runState.npcStates[*]',
        "SELECT DISTINCT k FROM run_sessions s, jsonb_each(s.run_state->'npcStates') e, "
        "jsonb_object_keys(e.value) k WHERE true;",
        r'\b(npcState|npcSt)\b',
    ),
    (
        # `rs` 는 admin/party 의 DB row 변수와 충돌해 오검출이 많다 (user_id·
        # party_id·startedAt 등). 명시적 이름만 본다.
        'runState (최상위)',
        "SELECT DISTINCT jsonb_object_keys(run_state) FROM run_sessions WHERE true;",
        r'\b(runState|updatedRunState|postTickRunState)\b',
    ),
]

# 키가 아닌 것 — 배열/문자열/Map 메서드와 흔한 프로퍼티
NOISE = {
    'map', 'filter', 'find', 'forEach', 'length', 'slice', 'push', 'join', 'includes',
    'some', 'every', 'keys', 'values', 'entries', 'toString', 'then', 'catch', 'split',
    'trim', 'replace', 'match', 'indexOf', 'concat', 'sort', 'reduce', 'flatMap', 'has',
    'get', 'set', 'add', 'delete', 'size', 'startsWith', 'endsWith', 'substring', 'at',
    'findIndex', 'reverse', 'splice', 'shift', 'pop', 'toFixed', 'padStart', 'repeat',
}


def db_keys(sql: str) -> set:
    out = subprocess.run(DB + [sql], capture_output=True, text=True)
    if out.returncode != 0:
        print(f'  [DB 오류] {out.stderr.strip().splitlines()[:1]}', file=sys.stderr)
        return set()
    return {l.strip() for l in out.stdout.splitlines() if l.strip()}


def strip_comments(text: str) -> str:
    """주석 제거 — 한국어 주석의 조사가 키로 오검출된다 ('endingResult가' 등).
    줄 번호 보존을 위해 블록 주석은 개행만 남긴다."""
    text = re.sub(r'/\*[\s\S]*?\*/', lambda m: '\n' * m.group(0).count('\n'), text)
    return '\n'.join(re.sub(r'//.*$', '', l) for l in text.split('\n'))


def ts_files() -> list:
    out = subprocess.run(['find', SRC, '-name', '*.ts'], capture_output=True, text=True)
    return [f for f in out.stdout.split()
            if not f.endswith('.spec.ts') and '__fixtures__' not in f]


def code_reads(varpat: str, files: list) -> dict:
    hits = defaultdict(list)
    for f in files:
        try:
            text = strip_comments(open(f, encoding='utf-8').read())
        except Exception:
            continue
        for m in re.finditer(varpat + r'\??\.\s*([A-Za-z_]\w*)', text):
            key = m.group(m.lastindex)
            hits[key].append(f'{f}:{text[:m.start()].count(chr(10)) + 1}')
    return hits


def is_fallback_chain(loc: str, key: str) -> bool:
    """같은 표현식 안에서 이 키 앞에 `??` 가 오면 폴백 2순위 — 정상 방어 코드."""
    path, line = loc.rsplit(':', 1)
    try:
        lines = open(path, encoding='utf-8').read().split('\n')
    except Exception:
        return False
    i = int(line) - 1
    window = '\n'.join(lines[max(0, i - 3):i + 1])
    return '??' in window and window.rindex('??') < window.rindex(key)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=30, help='DB 표본 기간 (기본 30일)')
    ap.add_argument('--lifetime', action='store_true', help='기간 제한 없음 (희귀 키 판정용)')
    args = ap.parse_args()

    where = '' if args.lifetime else f"AND created_at > now() - interval '{args.days} days'"
    files = ts_files()
    print(f'# payload 키 대조 감사 — 소스 {len(files)}파일 · '
          f'표본 {"전체" if args.lifetime else f"{args.days}일"}\n')

    total = 0
    for label, sql, varpat in TARGETS:
        actual = db_keys(sql.replace('{W}', where))
        if not actual:
            print(f'## {label}\n   (DB 표본 없음 — 생략)\n')
            continue
        reads = code_reads(varpat, files)
        susp = {k: v for k, v in reads.items()
                if k not in actual and k not in NOISE and not k.startswith('_')}
        print(f'## {label}')
        print(f'   DB 실제 키 {len(actual)}종 · 코드 읽기 {len(reads)}종 · 불일치 후보 {len(susp)}종')
        for k, locs in sorted(susp.items(), key=lambda x: -len(x[1])):
            chain = all(is_fallback_chain(l, k) for l in locs)
            mark = '↩ 폴백체인(정상 가능성 높음)' if chain else '✗ 확인 필요'
            if not chain:
                total += 1
            print(f'     {mark}  {k}  ({len(locs)}곳)')
            for l in locs[:3]:
                print(f'          {l}')
        print()

    print(f'폴백 체인을 제외한 확인 필요 후보: {total}건')
    print('\n각 건마다 ① 쓰기 지점 grep ② 해당 상태의 DB 표본 수를 확인할 것 '
          '(모듈 docstring 의 "한계 3종" 참조).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
