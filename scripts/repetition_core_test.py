"""
repetition_core 유닛 (arch/92 §8) — 의존성 없이 실행:  python3 scripts/repetition_core_test.py

구 인라인 구현에서는 게이트 **실패** 경로를 실런 없이 확인할 수 없었다.
여기서 4대 결함 각각과 양쪽 게이트 경로를 합성 입력으로 고정한다.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repetition_core as rc  # noqa: E402

_fails = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}  {detail}")
        _fails.append(name)


def turns_of(*narratives):
    """서술 리스트 → (narratives, turnNos) — 턴 번호는 1부터."""
    return list(narratives), list(range(1, len(narratives) + 1))


print("[stem_word] 조사 분리")
check("'소리가' → '소리'", rc.stem_word("소리가") == "소리", rc.stem_word("소리가"))
check("'장부의' → '장부'", rc.stem_word("장부의") == "장부", rc.stem_word("장부의"))
check("'고개를' → '고개'", rc.stem_word("고개를") == "고개", rc.stem_word("고개를"))
check("'으로' 우선 ('불빛으로'→'불빛')", rc.stem_word("불빛으로") == "불빛", rc.stem_word("불빛으로"))
# 2자 미만이 되면 원형 유지 — '바다'를 '바'로 깎지 않는다
check("'바다' 유지", rc.stem_word("바다") == "바다", rc.stem_word("바다"))
check("'그녀는' 유지 아님('그녀')", rc.stem_word("그녀는") == "그녀", rc.stem_word("그녀는"))

print("\n[결함 ①] 윈도우 중복 계수 제거 — 한 반복은 1건")
# '찻잔'이 T1에 6회. 3턴 윈도우가 T3까지 밀리며 같은 6회를 3번 본다.
n, t = turns_of("찻잔 찻잔 찻잔 찻잔 찻잔 찻잔.", "조용하다.", "조용하다.", "조용하다.", "조용하다.")
hits, _ = rc.detect(n, t, rc.build_stopwords(), [])
check("'찻잔' 1건으로 dedupe", len([h for h in hits if h.word == "찻잔"]) == 1, str(hits))
check("카운트는 최대값 6", hits and hits[0].count == 6, str(hits))

print("\n[결함 ②] 조사 변형이 한 stem 으로 합산")
n, t = turns_of("상자를 열었다. 상자에 손을 넣었다. 상자의 바닥. 상자가 흔들린다. 상자와 벽. 상자로 향한다.", "", "")
hits, _ = rc.detect(n, t, rc.build_stopwords(), [])
check("'상자' 6회로 합산", any(h.word == "상자" and h.count == 6 for h in hits), str(hits))

print("\n[결함 ③] 대명사는 게이트에서 제외")
n, t = turns_of("그녀는 웃었다. 그녀의 손. 그녀가 돌아본다. 그녀를 본다. 그녀는 말한다. 그녀도 웃는다.", "", "")
hits, _ = rc.detect(n, t, rc.build_stopwords(), [])
check("대명사 감지 0건", not any("그녀" in h.word for h in hits), str(hits))

print("\n[결함 ④] 팩 지명은 게이트에서 제외 (콘텐츠 파생)")
place = rc.extract_place_words([{"name": "꿈잠 여관", "shortName": "여관", "moveKeywords": ["여관", "꿈잠"]}])
n, t = turns_of("여관 여관 여관 여관 여관 여관.", "", "")
hits, _ = rc.detect(n, t, rc.build_stopwords(place), [])
check("'여관' 제외됨", not any(h.word == "여관" for h in hits), str(hits))
check("지명 미선언 팩에선 감지됨", any(
    h.word == "여관" for h in rc.detect(n, t, rc.build_stopwords(), [])[0]))

print("\n[콘텐츠 별칭] 게이트 제외 + 계측 분리")
n, t = turns_of("이렌 이렌 이렌 이렌 이렌 이렌.", "", "")
hits, alias_hits = rc.detect(n, t, rc.build_stopwords(), ["이렌"])
check("게이트 대상 0건", len(hits) == 0, str(hits))
check("계측에는 남음", any(h.word == "이렌" and h.count == 6 for h in alias_hits), str(alias_hits))

print("\n[게이트] 심각도 경로 — 단일 단어 8회+")
severe_hits = [rc.Hit("찻잔", rc.SEVERE_COUNT, 3)]
failed, severe, too_many = rc.evaluate_gate(severe_hits)
check("심각 1건만으로 FAIL", failed is True)
check("severe 로 분류", len(severe) == 1 and not too_many)
# 구 구현 회귀: 리스트 길이(1)를 임계(5)와 비교하면 통과해 버렸다
check("건수 비교로 새지 않음", not (len(severe_hits) <= rc.MAX_DISTINCT and not failed))

print("\n[게이트] 건수 경로 — 서로 다른 단어 6종+")
many_hits = [rc.Hit(f"단어{i}", 5, i) for i in range(rc.MAX_DISTINCT + 1)]
failed, severe, too_many = rc.evaluate_gate(many_hits)
check("건수 초과로 FAIL", failed is True and too_many and not severe)

print("\n[게이트] 통과 경로 — baseline 은 통과시킨다")
base_hits = [rc.Hit("좌판", 6, 3), rc.Hit("소리", 6, 5)]
failed, severe, too_many = rc.evaluate_gate(base_hits)
check("6회 2종은 PASS (만성 baseline)", failed is False, f"severe={severe} many={too_many}")
check("임계 경계 5종은 PASS", rc.evaluate_gate([rc.Hit(f"w{i}", 5, i) for i in range(rc.MAX_DISTINCT)])[0] is False)
check("빈 입력 PASS", rc.evaluate_gate([])[0] is False)

print("\n[주제어] extract_fact_keywords — 팩 fact 키워드 파생 (arch/110 ③)")
_facts = {"facts": {"F1": {"keywords": ["이름", "첫 공통몽", "꿈"]}, "F2": {"keywords": None}}}
_kw = rc.extract_fact_keywords(_facts)
check("단일어·복합어 토큰화 (1글자 '꿈'은 detect 대상 밖이라 제외)", "이름" in _kw and "공통몽" in _kw and "꿈" not in _kw)
check("리스트형 입력도 허용", "이름" in rc.extract_fact_keywords([{"keywords": ["이름"]}]))
check("빈 입력 무동작", rc.extract_fact_keywords({}) == set())
_n, _t = turns_of("이름 이름 이름 이름 이름 이름을 물었다.", "조용하다.", "바람이 분다.")
check(
    "주제어는 stopwords 합류 시 게이트 미적중",
    rc.detect(_n, _t, rc.build_stopwords(_kw), [])[0] == [],
)

print("\n[호칭] extract_address_terms — speechStyle 저작 호칭 파생 (arch/110 ③)")
_npcs = [
    {"personality": {"speechStyle": "건조한 해체. 상대 호칭은 '자네'."}},
    {"personality": {"speechStyle": "낮은 하오체. 상대 호칭은 '그대'."}},
    {"personality": {"speechStyle": "호칭 지정 없음."}},
]
_addr = rc.extract_address_terms(_npcs)
check("자네·그대 추출", _addr == {"자네", "그대"})
check("dict 래핑({'npcs':...})도 허용", rc.extract_address_terms({"npcs": _npcs}) == {"자네", "그대"})
check("빈 입력 무동작", rc.extract_address_terms([]) == set())
_n2, _t2 = turns_of("자네 자네 자네 자네 자네 말일세.", "조용하다.", "바람이 분다.")
check("호칭은 stopwords 합류 시 게이트 미적중", rc.detect(_n2, _t2, rc.build_stopwords(_addr), [])[0] == [])
check("접속사 스템 '하지'는 기본 기능어", "하지" in rc.FUNCTION_WORDS)

print("\n[경계] 짧은 런 — 윈도우보다 턴이 적으면 무동작")
n, t = turns_of("찻잔 찻잔 찻잔 찻잔 찻잔 찻잔.", "조용하다.")
check("2턴 런에서 예외 없이 0건", rc.detect(n, t, rc.build_stopwords(), [])[0] == [])


print("\n[게이트] 턴 비례 임계 (arch/111 후속 — 40턴 롱런 준오탐)")
_hits11=[rc.Hit(f"w{i}",5,i) for i in range(11)]
check("40턴 런: 종수 11은 PASS (임계 13)", rc.evaluate_gate(_hits11, total_turns=40)[0] is False)
check("15턴 런: 종수 11은 여전히 FAIL (판정 불변)", rc.evaluate_gate(_hits11, total_turns=15)[0] is True)
check("턴 수 미전달 시 기존 동작(임계 5)", rc.evaluate_gate(_hits11)[0] is True)
check("severe 는 턴 수와 무관", rc.evaluate_gate([rc.Hit("w",9,3)], total_turns=40)[0] is True)

print("\n[입력 어휘] 플레이어 입력·선택지 라벨 제외 (2026-09-01 QC 시리즈)")
_pw = rc.extract_player_input_words(
    ["소리가 오는 물목을 짚는다", "이렌에게 열쇠 하나에 대해 더 캐묻는다", None, 123]
)
check("입력 어절 스템 추출 (소리·열쇠·물목)", {"소리", "열쇠", "물목"} <= _pw)
check("빈 입력 무동작", rc.extract_player_input_words([]) == set())
_n3, _t3 = turns_of(
    "열쇠 열쇠가 열쇠를 열쇠의 열쇠 홈이 보인다.",
    "열쇠 열쇠가 다시 보인다.",
    "조용하다.",
)
check(
    "입력 어휘 stopword 합류 시 게이트 미적중",
    rc.detect(_n3, _t3, rc.build_stopwords(_pw), [])[0] == [],
)
check(
    "입력에 없는 어휘 반복은 종전대로 검출",
    rc.detect(_n3, _t3, rc.build_stopwords(), [])[0] != [],
)

print("\n" + "=" * 52)
if _fails:
    print(f"실패 {len(_fails)}건: {', '.join(_fails)}")
    sys.exit(1)
print("전체 통과")
