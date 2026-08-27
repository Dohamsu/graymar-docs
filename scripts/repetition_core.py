"""
서술 어휘 반복 감지 — 정본 (arch/92 §8).

`scripts/playtest.py` V9 반복 센서의 순수 로직. 스크립트 본문에 인라인으로 두면
오프라인 검증이 불가능해(스크립트가 top-level 실행) 게이트 실패 경로를 실런
없이는 확인할 수 없다. 서버 쪽 `narrative-filter.core` / `witness-reaction.core`
와 같은 정본+유닛 패턴으로 분리한다.

구 인라인 구현의 4대 결함을 여기서 함께 고친다 (77런 실측 근거):
  ① 윈도우별 이슈 적재 → 3턴 슬라이딩 윈도우라 한 반복이 최대 3윈도우에 걸려
     단일 반복이 3이슈로 계상됐다(임계 <=2 즉시 초과). 단어 단위로 dedupe.
  ② `[가-힣]{2,4}` 고정폭 절단 → 조사가 안 떨어져 감지 토큰 43종 중 53%가
     조사 종결 어절('소리가'·'장부의'·'고개를'). stem_word 로 정규화.
  ③ 대명사를 게이트로 이중 처벌 → arch/78 D5-1이 이미 측정·수용 중.
  ④ 제외 목록이 graymar 지명 하드코딩 → 활성 팩 콘텐츠에서 파생.
"""

import re
from collections import Counter
from typing import Iterable, NamedTuple

# 대명사 — V9 반복 센서와 D5 지칭 집계가 공유하는 정본.
PRONOUN_OPENERS = {
    "그는", "그가", "그의", "그를", "그도", "그에게",
    "그녀는", "그녀가", "그녀의", "그녀를", "그녀도", "그녀에게",
}
PRONOUN_STEMS = {"그", "그녀", "그것", "당신", "자신", "우리", "서로", "모두", "누군가", "무언가"}

# 범용 기능어 — 팩 무관. 지명·사물은 팩 콘텐츠에서 파생한다(build_stopwords).
FUNCTION_WORDS = {
    "당신", "자신", "있다", "없다", "있었", "하고", "이다", "했다", "하는", "것이", "있는",
    "위에", "앞에", "속에", "안에", "뒤에", "사이", "동안", "때문", "같은", "같이", "다시",
    "아직", "이미", "다른", "어떤", "무언", "그것", "이것", "저것", "하나", "여전",
    # [arch/110 ③] 접속사 스템 — '하지만'이 stem_word 조사 절단으로 '하지'가
    # 되어 게이트에 걸리던 준오탐 (run baa9eeee '하지'×5 실측)
    "하지", "그러", "그래", "그런데",
}

# 조사·어미 — 긴 것부터 시도해야 한다 ('으로'를 '로'보다 먼저).
_JOSA = (
    "으로써", "에게서", "으로", "에게", "에서", "이라", "라고", "처럼", "부터", "까지",
    "만은", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "만", "로",
)

# 게이트 임계 — 77런 실측 보정. 어휘 반복은 arch/78·82가 추적 중인 **만성 문제**라
# (45%의 런에 6회+ 반복 존재) 게이트는 만성 baseline이 아니라 **악화**를 잡아야 한다.
# 전량은 항상 계측으로 보고되므로 추이는 임계와 무관하게 관찰된다.
SEVERE_COUNT = 8   # 한 단어가 3턴 내 8회+ (실측 상위 9%). 턴 수 편향 없음.
MAX_DISTINCT = 5   # 서로 다른 단어 6종+ (실측 상위 4%). 광범위한 밋밋함 포착.
MIN_COUNT = 5      # 감지 하한 (계측 포함)
WINDOW = 3         # 슬라이딩 윈도우 턴 수


class Hit(NamedTuple):
    word: str
    count: int
    turn: int


def stem_word(w: str) -> str:
    """어절에서 조사를 떼어낸 stem. 2자 미만이 되면 원형 유지."""
    for j in _JOSA:
        if len(w) > len(j) + 1 and w.endswith(j):
            return w[: -len(j)]
    return w


def build_stopwords(place_words: Iterable[str] = ()) -> set:
    """게이트 제외 어휘 — 기능어 + 대명사 + 팩 지명."""
    return FUNCTION_WORDS | PRONOUN_OPENERS | PRONOUN_STEMS | {
        stem_word(p) for p in place_words if len(p) >= 2
    }


def extract_place_words(locations_json) -> set:
    """locations.json 에서 지명·이동 키워드를 뽑는다 (구: graymar 8개 하드코딩)."""
    out = set()
    locs = locations_json["locations"] if isinstance(locations_json, dict) else locations_json
    for loc in locs or []:
        for key in ("name", "shortName"):
            v = loc.get(key)
            if isinstance(v, str):
                for tok in re.findall(r"[가-힣]{2,8}", v):
                    out.add(stem_word(tok))
        for kw in (loc.get("moveKeywords") or []):
            if isinstance(kw, str) and len(kw) >= 2:
                out.add(stem_word(kw))
    return out


def extract_address_terms(npcs_json) -> set:
    """npcs.json speechStyle 에서 저작된 상대 호칭을 뽑는다 (arch/110 ③).

    "상대 호칭은 '자네'" 처럼 콘텐츠가 지정한 호칭은 연속 대화 턴에서
    구조적으로 밀도가 높다 (실측 run baa9eeee: 에드 5턴 대화에 '자네'×5 →
    V9 too_many 성분). 하드코딩 대신 콘텐츠 파생(불변식 45 정신) —
    게이트에서만 제외하고 계측 리포트에는 남긴다.
    """
    out = set()
    npcs = npcs_json if isinstance(npcs_json, list) else (npcs_json or {}).get("npcs", [])
    for n in npcs or []:
        style = ((n.get("personality") or {}).get("speechStyle")) or ""
        for m in re.finditer(r"호칭은\s*'([^']{2,8})'", style):
            out.add(stem_word(m.group(1)))
    return out


def extract_fact_keywords(facts_json) -> set:
    """facts.json 에서 팩 주제어를 뽑는다 (arch/110 ③ — V9 준오탐 억제).

    퀘스트 소재어('이름'·'꿈' 등)는 대화가 그 주제를 도는 동안 구조적으로
    밀도가 높다 (별빛모래 '이름'×16 → V9 FAIL 실측 — 팩 퀘스트 소재 자체가
    이름). NPC 실명·별칭과 같은 원칙: **게이트에서만 제외**하고 계측
    리포트에는 남긴다.
    """
    out = set()
    facts = facts_json.get("facts") if isinstance(facts_json, dict) else facts_json
    vals = facts.values() if isinstance(facts, dict) else (facts or [])
    for f in vals:
        for kw in f.get("keywords") or []:
            if not isinstance(kw, str):
                continue
            for tok in re.findall(r"[가-힣]{2,8}", kw):
                out.add(stem_word(tok))
    return out


def detect(narratives: list, turns: list, stopwords: set, alias_pool: Iterable[str] = ()):
    """
    3턴 윈도우 반복 감지. `narratives[i]` 는 `turns[i]` 턴의 서술.

    반환: (hits, alias_hits) — 둘 다 count 내림차순. alias_hits(NPC 실명·콘텐츠
    별칭)는 게이트 제외 대상이다. 3턴 대화 중 이름이 5~8회 나오는 건 정상이며
    arch/78 D5-2가 CONTENT_ALIAS 로 이미 분류·보고 중이다.
    """
    aliases = [a for a in alias_pool if a]
    best = {}  # stem -> (최대 카운트, 그 카운트가 나온 턴) — 윈도우 중복을 여기서 흡수
    for i in range(WINDOW - 1, len(narratives)):
        combined = " ".join(narratives[max(0, i - WINDOW + 1): i + 1])
        # @마커 내부 텍스트 제거 (NPC 별칭이 마커로 반복 카운트되는 것 방지)
        combined = re.sub(r"@\[[^\]]+\]", "", combined)
        counts = Counter(
            s for s in (stem_word(w) for w in re.findall(r"[가-힣]{2,8}", combined))
            if len(s) >= 2
        )
        for word, cnt in counts.most_common():
            if cnt < MIN_COUNT:
                break
            if word in stopwords:
                continue
            if cnt > best.get(word, (0, 0))[0]:
                best[word] = (cnt, turns[i])

    hits, alias_hits = [], []
    for word, (cnt, turn) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        is_alias = any(word == a or word in a or a in word for a in aliases)
        (alias_hits if is_alias else hits).append(Hit(word, cnt, turn))
    return hits, alias_hits


def evaluate_gate(hits: list):
    """
    (failed, severe, too_many) — 판정을 불린 하나로 확정한다. 구 구현처럼
    이슈 리스트 길이를 임계와 다시 비교하면 '심각 1건' 같은 케이스가 건수
    비교를 통과해 조용히 새 나간다.
    """
    severe = [h for h in hits if h.count >= SEVERE_COUNT]
    too_many = len(hits) > MAX_DISTINCT
    return (bool(severe) or too_many), severe, too_many
