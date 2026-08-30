#!/usr/bin/env python3
"""
audit_content.py — 콘텐츠 팩 정합성 감사 (정본 스크립트)

arca 조사 리포트 §5-D(LoreForge 심층 점검) 이식. 서버 부팅 시 도는
ContentValidatorService(NPC 단위 4개 룰)가 보지 않는 **파일 간 참조 정합성과
도달성**을 저작 시점에 잡는다.

3계층:
  L1 참조 무결성 — 모든 ID 참조가 실제 정의로 해소되는가 (dangling reference)
  L2 팩 계약     — 불변식 45(questState 명명·resolutionConditions·payload.tags)
                   불변식 31(defaultTraitId), arcRoute enum 등 계약 위반
  L3 심층 점검   — 도달 불가 fact / 도달 불가 questState 전환 / 고아 정의.
                   "문법은 맞는데 플레이가 막히는" 결함. 여기가 진짜 값어치.

확인됨(ack) 처리:
  오탐이거나 의도된 항목은 --ack <FINDING_KEY> 로 등록하면
  content/<pack>/.audit-ack.json 에 기록되어 다음 실행부터 억제된다.
  (LoreForge 의 "확인됨 체크" 와 같은 개념 — 반복 오탐이 신호를 덮는 걸 막는다.)

사용:
  python3 scripts/audit_content.py                    # 전 팩
  python3 scripts/audit_content.py star_sand_v1       # 단일 팩
  python3 scripts/audit_content.py --show-acked       # 억제된 항목도 표시
  python3 scripts/audit_content.py --ack <KEY> [KEY2] # 확인됨 등록
  python3 scripts/audit_content.py --unack <KEY>      # 확인됨 해제
  python3 scripts/audit_content.py --json             # 기계 판독 출력

종료 코드: ERROR 1건 이상이면 1, 아니면 0 (CI 게이트용).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")

# ─────────────────────────── 계약 상수 ───────────────────────────

# 불변식 45 — questState 명명 규약
QUEST_STATE_RE = re.compile(r"^S[0-5]_[A-Z_]+$")
# arc-state.ts ArcRoute 정본
ARC_ROUTES = {"EXPOSE_CORRUPTION", "PROFIT_FROM_CHAOS", "ALLY_GUARD"}

# ID 접두사 → 정의가 사는 곳 (파일, 추출기)
#   추출기는 로드된 JSON 을 받아 정의된 ID 집합을 돌려준다.
ID_PREFIXES = ("NPC", "LOC", "EVT", "FACT", "INC", "ITEM", "EQ", "ENEMY", "SET", "SHOP")

# ID 형태지만 참조가 아닌 값 (enum·태그). 여기 있으면 L1 검사에서 제외한다.
NON_REFERENCE_VALUES = {
    "NPC_BEHAVIOR",  # SignalChannel enum
    "NPC_HINT",  # events payload.tags 의 태그어
    "NPC_ACTION",  # FactCategory enum
}
# 런타임 생성 ID — 콘텐츠에 정의가 없는 게 정상 (dynamic-npc.ts)
RUNTIME_ID_RE = re.compile(r"^NPC_DYN_\d+$")

# 참조로 취급하지 않을 키 (값이 ID 형태여도 무시)
#   entityAliases 는 설계상 "이 NPC 를 가리키는 다른 문자열" 목록이라
#   구 ID·오탈자 변형(NPC_EDRIC_VEIL 의 alias "NPC_EDRIC")이 들어 있는 게 정상이다.
NON_REFERENCE_KEYS = {"channel", "signalChannel", "entityAliases"}

# ID 형태를 쓰지만 자유 문자열인 키 — 끊긴 참조라도 ERROR 가 아닌 WARN 으로 낮춘다.
SOFT_REFERENCE_KEYS = {"tags"}


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        return {"__parse_error__": str(e)}


def as_list(obj, *keys):
    """dict 래핑(version/description + 본체) 과 순수 list 를 모두 받아 list 로 정규화."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                return list(v.values())
        # 래퍼 키를 못 찾으면 dict 자체가 맵일 수 있다
        vals = [v for v in obj.values() if isinstance(v, dict)]
        if vals:
            return vals
    return []


# ─────────────────────────── Finding ───────────────────────────


class Finding:
    __slots__ = ("severity", "rule", "where", "message", "key")

    def __init__(self, severity, rule, where, message):
        self.severity = severity  # ERROR | WARN | INFO
        self.rule = rule
        self.where = where  # "events_v2.json:EVT_X" 처럼 위치
        self.message = message
        self.key = f"{rule}:{where}"

    def to_dict(self):
        return {
            "severity": self.severity,
            "rule": self.rule,
            "where": self.where,
            "message": self.message,
            "key": self.key,
        }


# ─────────────────────────── 팩 로딩 ───────────────────────────


class Pack:
    def __init__(self, pack_id):
        self.pack_id = pack_id
        self.dir = os.path.join(CONTENT, pack_id)
        self.raw = {}
        self.parse_errors = []
        for fn in sorted(os.listdir(self.dir)):
            # 감사기 자신의 산출물(.audit-ack.json)은 콘텐츠가 아니다.
            # 스캔에 넣으면 ack 키에 든 ID 문자열이 다시 dangling 으로 잡힌다.
            if not fn.endswith(".json") or fn.startswith("."):
                continue
            d = load(os.path.join(self.dir, fn))
            if isinstance(d, dict) and "__parse_error__" in d:
                self.parse_errors.append((fn, d["__parse_error__"]))
                continue
            self.raw[fn] = d

        self.npcs = as_list(self.raw.get("npcs.json"), "npcs")
        self.locations = as_list(self.raw.get("locations.json"), "locations")
        self.events = as_list(self.raw.get("events_v2.json"), "events")
        self.incidents = as_list(self.raw.get("incidents.json"), "incidents")
        self.items = as_list(self.raw.get("items.json"), "items")
        self.enemies = as_list(self.raw.get("enemies.json"), "enemies")
        self.sets = as_list(self.raw.get("sets.json"), "sets")
        self.shops = as_list(self.raw.get("shops.json"), "shops")
        self.presets = as_list(self.raw.get("presets.json"), "presets")
        self.traits = as_list(self.raw.get("traits.json"), "traits")
        self.quest = self.raw.get("quest.json") or {}
        scen = self.raw.get("scenario.json") or {}
        self.narrative_mode = (
            scen.get("narrativeMode") if isinstance(scen, dict) else None
        ) or "AUTHORED"

        facts_raw = self.raw.get("facts.json") or {}
        facts_body = facts_raw.get("facts", facts_raw) if isinstance(facts_raw, dict) else {}
        if isinstance(facts_body, dict):
            self.facts = facts_body
        else:  # list 형태 대비
            self.facts = {f.get("factId"): f for f in facts_body if isinstance(f, dict)}

        self.defined = self._collect_defined()

    def _collect_defined(self):
        d = defaultdict(set)
        for n in self.npcs:
            if isinstance(n, dict) and n.get("npcId"):
                d["NPC"].add(n["npcId"])
                # entityAliases 는 "이 NPC 를 가리키는 다른 문자열" 선언이므로,
                # ID 형태의 별칭(NPC_EDRIC_VEIL 의 "NPC_EDRIC")은 유효한 지시 대상이다.
                for a in n.get("entityAliases") or []:
                    if isinstance(a, str) and a.startswith("NPC_"):
                        d["NPC"].add(a)
        for l in self.locations:
            if isinstance(l, dict) and l.get("locationId"):
                d["LOC"].add(l["locationId"])
        for e in self.events:
            if isinstance(e, dict) and e.get("eventId"):
                d["EVT"].add(e["eventId"])
        for i in self.incidents:
            if isinstance(i, dict) and i.get("incidentId"):
                d["INC"].add(i["incidentId"])
        for it in self.items:
            if isinstance(it, dict) and it.get("itemId"):
                iid = it["itemId"]
                d[iid.split("_")[0]].add(iid)
        for en in self.enemies:
            if isinstance(en, dict) and en.get("enemyId"):
                d["ENEMY"].add(en["enemyId"])
        for s in self.sets:
            if isinstance(s, dict) and s.get("setId"):
                d["SET"].add(s["setId"])
        for s in self.shops:
            if isinstance(s, dict) and s.get("shopId"):
                d["SHOP"].add(s["shopId"])
        for fid in self.facts:
            if fid:
                d["FACT"].add(fid)
        return d

    def ack_path(self):
        return os.path.join(self.dir, ".audit-ack.json")

    def load_acks(self):
        d = load(self.ack_path())
        if isinstance(d, dict) and isinstance(d.get("acknowledged"), list):
            return {a["key"]: a.get("note", "") for a in d["acknowledged"] if isinstance(a, dict)}
        return {}

    def save_acks(self, acks):
        payload = {
            "_comment": "audit_content.py 확인됨(ack) 목록. 오탐이거나 의도된 항목만 등록한다.",
            "acknowledged": [{"key": k, "note": v} for k, v in sorted(acks.items())],
        }
        with open(self.ack_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")


# ─────────────────────── L1 참조 무결성 ───────────────────────


def walk_refs(obj, filename, path, out, key=None):
    """JSON 트리를 훑어 (파일, JSON경로, 키, 값) 형태의 ID 참조 후보를 모은다."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk_refs(v, filename, f"{path}.{k}" if path else k, out, k)
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            walk_refs(v, filename, f"{path}[{idx}]", out, key)
    elif isinstance(obj, str):
        if key in NON_REFERENCE_KEYS or obj in NON_REFERENCE_VALUES:
            return
        if RUNTIME_ID_RE.match(obj):
            return
        prefix = obj.split("_")[0]
        if prefix in ID_PREFIXES and "_" in obj:
            out.append((filename, path, key, obj, prefix))


def check_l1_references(pack):
    findings = []
    refs = []
    for fn, data in pack.raw.items():
        walk_refs(data, fn, "", refs)

    # 정의 자체(선언 위치)는 참조로 세지 않는다
    DECL_KEYS = {
        "npcId": "NPC",
        "locationId": "LOC",
        "eventId": "EVT",
        "incidentId": "INC",
        "itemId": None,
        "enemyId": "ENEMY",
        "setId": "SET",
        "shopId": "SHOP",
        "factId": "FACT",
    }
    DECL_FILES = {
        "npcs.json": "npcId",
        "locations.json": "locationId",
        "events_v2.json": "eventId",
        "incidents.json": "incidentId",
        "items.json": "itemId",
        "enemies.json": "enemyId",
        "sets.json": "setId",
        "shops.json": "shopId",
        "facts.json": "factId",
    }

    seen = set()
    for fn, path, key, value, prefix in refs:
        # 선언부 스킵 (예: npcs.json 의 npcId 는 정의이지 참조가 아님)
        if DECL_FILES.get(fn) == key and path.count(".") <= 1:
            continue
        if value in pack.defined.get(prefix, ()):
            continue
        # ITEM/EQ 는 서로의 풀을 함께 본다 (items.json 이 둘 다 담음)
        if prefix in ("ITEM", "EQ") and value in (
            pack.defined.get("ITEM", set()) | pack.defined.get("EQ", set())
        ):
            continue
        where = f"{fn}:{path}"
        if where in seen:
            continue
        seen.add(where)
        soft = key in SOFT_REFERENCE_KEYS
        findings.append(
            Finding(
                "WARN" if soft else "ERROR",
                "SOFT_REF_UNKNOWN" if soft else "DANGLING_REF",
                where,
                f'"{value}" 참조가 팩 안에 정의되지 않음 (키 {key})'
                + ("  ※ 자유 문자열 필드라 치명은 아님" if soft else ""),
            )
        )
    return findings


# ─────────────────────── L2 팩 계약 ───────────────────────


def check_l2_contract(pack):
    f = []

    for fn, err in pack.parse_errors:
        f.append(Finding("ERROR", "JSON_PARSE", fn, f"JSON 파싱 실패: {err}"))

    # 불변식 45 — questState 명명
    states = pack.quest.get("states") or []
    for s in states:
        if not QUEST_STATE_RE.match(str(s)):
            f.append(
                Finding(
                    "ERROR",
                    "QUEST_STATE_NAMING",
                    f"quest.json:states:{s}",
                    f'questState "{s}" 가 S0_~S5_ 명명 규약 위반 (불변식 45)',
                )
            )

    # 불변식 45 — incidents.resolutionConditions 필수
    for inc in pack.incidents:
        if not isinstance(inc, dict):
            continue
        iid = inc.get("incidentId", "?")
        if not inc.get("resolutionConditions"):
            f.append(
                Finding(
                    "ERROR",
                    "INCIDENT_NO_RESOLUTION",
                    f"incidents.json:{iid}",
                    "resolutionConditions 누락 — 종결 불가 사건 (불변식 45)",
                )
            )

    # 불변식 45 — events payload.tags 필수
    for ev in pack.events:
        if not isinstance(ev, dict):
            continue
        eid = ev.get("eventId", "?")
        tags = (ev.get("payload") or {}).get("tags")
        if not tags:
            f.append(
                Finding(
                    "WARN",
                    "EVENT_NO_TAGS",
                    f"events_v2.json:{eid}",
                    "payload.tags 누락 — 이벤트 분류·매칭 신호 부재 (불변식 45)",
                )
            )

    # arch/108 — 자연스러운 장비 획득 필드 모양 검사 (사문 배선 방지).
    # 새 콘텐츠 필드는 엔진이 못 읽는 모양으로 저작되면 조용히 무시된다 — 필수 검사.
    item_ids = {
        i.get("itemId") for i in pack.items if isinstance(i, dict)
    } - {None}
    loc_ids = {
        l.get("locationId") for l in pack.locations if isinstance(l, dict)
    } - {None}
    for n in pack.npcs:
        if not isinstance(n, dict):
            continue
        nid = n.get("npcId", "?")
        gift = n.get("gift")
        if gift is not None:
            if not isinstance(gift, dict) or not gift.get("itemId"):
                f.append(Finding("ERROR", "NATURAL_ACQ_SHAPE", f"npcs.json:{nid}",
                                 "gift 는 {itemId[, trustMin, note]} 객체여야 함 (arch/108)"))
            elif gift["itemId"] not in item_ids:
                f.append(Finding("ERROR", "NATURAL_ACQ_REF", f"npcs.json:{nid}",
                                 f'gift.itemId "{gift["itemId"]}" 미정의 — 지급이 조용히 무시됨'))
            elif "trustMin" in gift and not isinstance(gift["trustMin"], (int, float)):
                f.append(Finding("ERROR", "NATURAL_ACQ_SHAPE", f"npcs.json:{nid}",
                                 "gift.trustMin 은 수치여야 함"))
        pt = n.get("personalTrade")
        if pt is not None:
            if not isinstance(pt, dict) or not pt.get("itemId"):
                f.append(Finding("ERROR", "NATURAL_ACQ_SHAPE", f"npcs.json:{nid}",
                                 "personalTrade 는 {itemId, price} 객체여야 함 (arch/108)"))
            elif pt["itemId"] not in item_ids:
                f.append(Finding("ERROR", "NATURAL_ACQ_REF", f"npcs.json:{nid}",
                                 f'personalTrade.itemId "{pt["itemId"]}" 미정의'))
            elif not isinstance(pt.get("price"), (int, float)) or pt["price"] <= 0:
                f.append(Finding("ERROR", "NATURAL_ACQ_SHAPE", f"npcs.json:{nid}",
                                 "personalTrade.price 는 양수여야 함 (0 이하는 엔진이 무동작)"))
        # arch/109 R1·R4 — 관계 성향 모양 검사. romanceable/companionable 이
        # bool 이 아니면 엔진(=== true 판정)이 조용히 false 취급 — 저작 사문화.
        rp = n.get("relationProfile")
        if rp is not None:
            if not isinstance(rp, dict):
                f.append(Finding("ERROR", "RELATION_PROFILE_SHAPE", f"npcs.json:{nid}",
                                 "relationProfile 은 {romanceable/companionable: bool} 객체여야 함 (arch/109)"))
            else:
                for key in ("romanceable", "companionable"):
                    if key in rp and not isinstance(rp[key], bool):
                        f.append(Finding("ERROR", "RELATION_PROFILE_SHAPE", f"npcs.json:{nid}",
                                         f'relationProfile.{key} 은 true/false 여야 함 — '
                                         f'문자열 "true" 는 엔진이 false 취급 (arch/109)'))
                unknown = set(rp.keys()) - {"romanceable", "companionable"}
                if unknown:
                    f.append(Finding("WARN", "RELATION_PROFILE_SHAPE", f"npcs.json:{nid}",
                                     f'relationProfile 미지원 키 {sorted(unknown)} — 엔진이 읽지 않음 (arch/109)'))
    # [arch/111] INCIDENT_PACING — 시간 상수가 시계 실효(0.4 tick/턴)에 맞는가.
    # 30일 실측: pressure 95 도달 32tick(80턴)·deadline 48tick(120턴)으로 저작돼
    # 자동 해소(ESCALATED·EXPIRED)가 554건 중 0건인 사문이었다 (arch/81 밤낮
    # 재설계 후 재기준화 누락 — arch/21 Part 11 아젠다 day>=2 와 같은 부류).
    # 새 incident 저작 시 같은 함정을 막는다.
    for inc in (pack.incidents or []):
        if not isinstance(inc, dict):
            continue
        iid = inc.get("incidentId", "?")
        stages = inc.get("stages") or []
        if stages and isinstance(stages[0], dict):
            ppt = stages[0].get("pressurePerTick")
            if isinstance(ppt, (int, float)) and ppt < 6:
                f.append(Finding("WARN", "INCIDENT_PACING", f"incidents.json:{iid}",
                                 f"stage0 pressurePerTick={ppt} < 6 — 시계 실효 0.4tick/턴에서 "
                                 f"방치 폭발(ESCALATED)까지 {round(95/max(ppt,1)/0.4)}턴+ 소요, 사실상 사문 (arch/111)"))
        rc = inc.get("resolutionConditions") or {}
        dt = rc.get("deadlineTicks")
        if isinstance(dt, (int, float)) and dt > 30:
            f.append(Finding("WARN", "INCIDENT_PACING", f"incidents.json:{iid}",
                             f"deadlineTicks={dt} > 30 (={round(dt/0.4)}턴) — 실플레이 도달 불가 (arch/111)"))
    for fid, fact in (pack.facts or {}).items():
        if not isinstance(fact, dict):
            continue
        cache = fact.get("cache")
        if cache is None:
            continue
        if not isinstance(cache, dict) or not cache.get("itemId") or not cache.get("locationId"):
            f.append(Finding("ERROR", "NATURAL_ACQ_SHAPE", f"facts.json:{fid}",
                             "cache 는 {itemId, locationId} 객체여야 함 (arch/108)"))
        else:
            if cache["itemId"] not in item_ids:
                f.append(Finding("ERROR", "NATURAL_ACQ_REF", f"facts.json:{fid}",
                                 f'cache.itemId "{cache["itemId"]}" 미정의'))
            if cache["locationId"] not in loc_ids:
                f.append(Finding("ERROR", "NATURAL_ACQ_REF", f"facts.json:{fid}",
                                 f'cache.locationId "{cache["locationId"]}" 미정의 — 도달 불가 은닉처'))

    # 불변식 31 — defaultTraitId 실존 + 스탯 배분
    trait_ids = set()
    for t in pack.traits:
        if isinstance(t, dict):
            tid = t.get("traitId") or t.get("id")
            if tid:
                trait_ids.add(tid)
    for p in pack.presets:
        if not isinstance(p, dict):
            continue
        pid = p.get("presetId", "?")
        dt = p.get("defaultTraitId")
        if not dt:
            f.append(
                Finding(
                    "ERROR",
                    "PRESET_NO_DEFAULT_TRAIT",
                    f"presets.json:{pid}",
                    "defaultTraitId 미지정 — 특성 없이 런 생성됨 (불변식 31)",
                )
            )
        elif trait_ids and dt not in trait_ids:
            f.append(
                Finding(
                    "ERROR",
                    "PRESET_TRAIT_DANGLING",
                    f"presets.json:{pid}",
                    f'defaultTraitId "{dt}" 가 traits.json 에 없음 (불변식 31)',
                )
            )

    # arcRoutes enum
    for r in pack.quest.get("arcRoutes") or []:
        if isinstance(r, dict):
            rid = r.get("routeId")
            if rid and rid not in ARC_ROUTES:
                f.append(
                    Finding(
                        "ERROR",
                        "ARC_ROUTE_ENUM",
                        f"quest.json:arcRoutes:{rid}",
                        f'routeId "{rid}" 가 ArcRoute 정본({"/".join(sorted(ARC_ROUTES))})에 없음',
                    )
                )

    # stateTransitions 키가 실제 상태쌍인가
    for k in (pack.quest.get("stateTransitions") or {}):
        if "→" not in k:
            f.append(
                Finding("WARN", "TRANSITION_KEY_FORMAT", f"quest.json:stateTransitions:{k}",
                        '전환 키가 "Sx_A→Sy_B" 형식이 아님')
            )
            continue
        a, b = k.split("→", 1)
        for s in (a, b):
            if states and s not in states:
                f.append(
                    Finding(
                        "ERROR",
                        "TRANSITION_UNKNOWN_STATE",
                        f"quest.json:stateTransitions:{k}",
                        f'"{s}" 가 states 목록에 없음',
                    )
                )
    return f


# ─────────────────────── L3 심층 점검 ───────────────────────


def check_l3_deep(pack):
    """문법은 맞는데 플레이가 막히는 결함을 찾는다."""
    f = []

    # fact 를 획득할 수 있는 경로 수집
    fact_from_event = defaultdict(list)  # factId -> [eventId]
    for ev in pack.events:
        if not isinstance(ev, dict):
            continue
        df = ev.get("discoverableFact")
        if df:
            fact_from_event[df].append(ev.get("eventId", "?"))

    fact_from_npc = defaultdict(list)  # factId -> [npcId]
    for fid, fact in pack.facts.items():
        if not isinstance(fact, dict):
            continue
        for npc in fact.get("knownBy") or []:
            fact_from_npc[fid].append(npc)

    fact_from_item = defaultdict(list)
    for it in pack.items:
        if isinstance(it, dict) and it.get("factKey"):
            fact_from_item[it["factKey"]].append(it.get("itemId", "?"))

    def obtainable(fid):
        return bool(fact_from_event.get(fid) or fact_from_npc.get(fid) or fact_from_item.get(fid))

    # ① 획득 경로가 전혀 없는 fact
    for fid in pack.facts:
        if not obtainable(fid):
            f.append(
                Finding(
                    "ERROR",
                    "FACT_UNOBTAINABLE",
                    f"facts.json:{fid}",
                    "이 fact 를 주는 이벤트(discoverableFact)·NPC(knownBy)·아이템(factKey)이 하나도 없음 — 발견 불가",
                )
            )

    # ② 도달 불가 questState 전환 (①의 파급 — 엔딩 차단)
    #    판정 계약은 quest-progression.service.ts 를 따른다:
    #      requiredFacts   = 전부 AND
    #      requiredAnyOf   = 그룹의 OR, 그룹 안은 AND (string[][])
    #      alternativeFacts= OR (실질 조건이 없을 때만 게이트로 동작)
    for k, tr in (pack.quest.get("stateTransitions") or {}).items():
        if not isinstance(tr, dict):
            continue
        req = list(tr.get("requiredFacts") or [])
        any_of = [g if isinstance(g, list) else [g] for g in (tr.get("requiredAnyOf") or [])]
        alts = list(tr.get("alternativeFacts") or [])

        referenced = req + [x for g in any_of for x in g] + alts
        missing = sorted({x for x in referenced if x not in pack.facts})
        if missing:
            f.append(
                Finding(
                    "ERROR",
                    "TRANSITION_FACT_DANGLING",
                    f"quest.json:stateTransitions:{k}",
                    f"요구 fact 가 facts.json 에 없음: {', '.join(missing)}",
                )
            )

        known = lambda x: x in pack.facts  # noqa: E731
        blocked_req = [x for x in req if known(x) and not obtainable(x)]
        if blocked_req:
            f.append(
                Finding(
                    "ERROR",
                    "TRANSITION_UNREACHABLE",
                    f"quest.json:stateTransitions:{k}",
                    f"requiredFacts 가 획득 불가라 이 전환에 영원히 도달 못함: "
                    f"{', '.join(blocked_req)} — 이후 상태·엔딩 차단",
                )
            )
        if any_of and not any(
            all(known(x) and obtainable(x) for x in g) for g in any_of
        ):
            groups = " / ".join("+".join(g) for g in any_of)
            f.append(
                Finding(
                    "ERROR",
                    "TRANSITION_UNREACHABLE",
                    f"quest.json:stateTransitions:{k}:anyOf",
                    f"requiredAnyOf 의 어떤 그룹도 전부 획득할 수 없음 ({groups}) — 이후 상태·엔딩 차단",
                )
            )

    # ③ fact.discoveryLocations 에 실제 그 fact 를 주는 이벤트가 없는 장소
    ev_loc = {e.get("eventId"): e.get("locationId") for e in pack.events if isinstance(e, dict)}
    npc_loc = {}
    for n in pack.npcs:
        if isinstance(n, dict) and n.get("npcId"):
            locs = set()
            if n.get("locationId"):
                locs.add(n["locationId"])
            for l in n.get("activityLocations") or []:
                locs.add(l)
            # schedule 로 확정되는 위치도 조우 가능 장소다 (npc-schedule.service)
            sched = n.get("schedule")
            if isinstance(sched, dict):
                blocks = [sched.get("default") or {}]
                blocks += [(o or {}).get("schedule") or {} for o in sched.get("overrides") or []]
                for blk in blocks:
                    if isinstance(blk, dict):
                        for ent in blk.values():
                            if isinstance(ent, dict) and ent.get("locationId"):
                                locs.add(ent["locationId"])
            npc_loc[n["npcId"]] = locs
    for fid, fact in pack.facts.items():
        if not isinstance(fact, dict):
            continue
        declared = set(fact.get("discoveryLocations") or [])
        if not declared:
            continue
        actual = {ev_loc.get(e) for e in fact_from_event.get(fid, [])}
        for npc in fact_from_npc.get(fid, []):
            actual |= npc_loc.get(npc, set())
        actual.discard(None)
        ghost = declared - actual
        if ghost and actual:
            f.append(
                Finding(
                    "WARN",
                    "FACT_LOCATION_MISMATCH",
                    f"facts.json:{fid}:discoveryLocations",
                    f"선언된 발견 장소 {sorted(ghost)} 에 이 fact 를 주는 이벤트·NPC 가 없음 (실제: {sorted(actual)})",
                )
            )

    # ④ fact.stage 가 실재하는 questState 를 가리키는가
    #    FactDefinition.stage 는 축약 표기가 정본이다 (content.types.ts:305 — 예: "S0→S1").
    #    엔진이 읽는 필드가 아니라 저작 주석이므로, 문자열 일치가 아니라
    #    "S<n> 서수가 states 에 실재하는가"만 본다.
    transitions = set(pack.quest.get("stateTransitions") or {})
    states = list(pack.quest.get("states") or [])
    ordinals = {s.split("_")[0] for s in states}  # {"S0","S1",...}
    for fid, fact in pack.facts.items():
        if not isinstance(fact, dict):
            continue
        stage = fact.get("stage")
        if not stage or stage in transitions or stage in states:
            continue
        found = re.findall(r"S[0-9]", stage)
        if not found:
            f.append(
                Finding("INFO", "FACT_STAGE_FORMAT", f"facts.json:{fid}:stage",
                        f'stage "{stage}" 에서 S<n> 표기를 찾지 못함')
            )
            continue
        unknown = sorted({s for s in found if s not in ordinals})
        if unknown:
            f.append(
                Finding(
                    "WARN",
                    "FACT_STAGE_UNKNOWN",
                    f"facts.json:{fid}:stage",
                    f'stage "{stage}" 가 존재하지 않는 상태 {unknown} 를 가리킴 '
                    f'(states: {", ".join(states)})',
                )
            )

    # ⑤ quest.facts 목록과 facts.json 불일치
    q_facts = set(pack.quest.get("facts") or [])
    if q_facts:
        for x in sorted(q_facts - set(pack.facts)):
            f.append(
                Finding("ERROR", "QUEST_FACT_DANGLING", f"quest.json:facts:{x}",
                        "quest.facts 에 있으나 facts.json 에 정의 없음")
            )
        for x in sorted(set(pack.facts) - q_facts):
            f.append(
                Finding("INFO", "FACT_NOT_IN_QUEST", f"facts.json:{x}",
                        "facts.json 에 있으나 quest.facts 목록에 없음 — 퀘스트 진행에 안 쓰이는 fact")
            )

    # ⑥ NPC 배치 — schedule 구조 사문 + 배치 경로 전무
    #    NpcSchedule 계약(server/src/db/types/npc-schedule.ts):
    #      { default: { DAWN|DAY|DUSK|NIGHT: { locationId, activity, interactable } },
    #        overrides?: [{ condition, schedule }] }
    #    npc-schedule.service.ts 는 schedule.default?.[timePhase] 만 읽는다.
    #    "DAY": "선술집에서 대기" 같은 산문 문자열은 조용히 무시되어 배치가 사라진다
    #    (arch/21 Part 11 의 agenda vs longTermAgenda 와 같은 사문 배선 부류).
    PHASES = ("DAWN", "DAY", "DUSK", "NIGHT")
    event_npcs = {
        (e.get("payload") or {}).get("primaryNpcId")
        for e in pack.events
        if isinstance(e, dict)
    }
    event_npcs.discard(None)

    for n in pack.npcs:
        if not isinstance(n, dict):
            continue
        nid = n.get("npcId")
        if not nid:
            continue

        sched = n.get("schedule")
        sched_locs = set()
        if isinstance(sched, dict):
            default = sched.get("default")
            if isinstance(default, dict):
                for ph in PHASES:
                    ent = default.get(ph)
                    if isinstance(ent, dict) and ent.get("locationId"):
                        sched_locs.add(ent["locationId"])
            for ov in sched.get("overrides") or []:
                for ent in (ov or {}).get("schedule", {}).values():
                    if isinstance(ent, dict) and ent.get("locationId"):
                        sched_locs.add(ent["locationId"])
            if not sched_locs:
                f.append(
                    Finding(
                        "ERROR",
                        "NPC_SCHEDULE_SHAPE",
                        f"npcs.json:{nid}:schedule",
                        "schedule 이 있으나 default.<DAWN|DAY|DUSK|NIGHT>.locationId 구조가 아님 — "
                        "npc-schedule.service 가 읽지 못해 배치가 조용히 사라짐(사문 배선)",
                    )
                )

        if n.get("tier") == "BACKGROUND":
            continue
        if npc_loc.get(nid) or sched_locs or nid in event_npcs:
            continue
        # AUTONOMOUS 팩(karnholt 계열)은 저작 배치 대신 PlotDirector 가 등장을 만든다.
        # 실측(45일)에서도 karnholt 5런 전부 npcLocations 가 비어 있으므로 결함이 아니다.
        autonomous = pack.narrative_mode == "AUTONOMOUS"
        f.append(
            Finding(
                "INFO" if autonomous else "WARN",
                "NPC_NO_LOCATION",
                f"npcs.json:{nid}",
                "locationId·activityLocations·schedule·이벤트 primaryNpcId 어디에도 없어 조우 경로가 없음"
                + ("  ※ AUTONOMOUS 팩은 디렉터가 등장을 만들므로 정상" if autonomous else ""),
            )
        )

    # ⑦ 이벤트가 하나도 없는 장소 (lazy 는 정상이나 CORE 동선이면 문제)
    loc_events = defaultdict(int)
    for e in pack.events:
        if isinstance(e, dict) and e.get("locationId"):
            loc_events[e["locationId"]] += 1
    for l in pack.locations:
        if not isinstance(l, dict):
            continue
        lid = l.get("locationId")
        if lid and loc_events.get(lid, 0) == 0:
            f.append(
                Finding(
                    "INFO",
                    "LOCATION_NO_EVENTS",
                    f"locations.json:{lid}",
                    "저작 이벤트 0건 — SituationGenerator 절차 생성에만 의존",
                )
            )

    # ⑧ 연결이 끊긴 장소 (adjacentLocations 그래프 도달성)
    adj = {}
    for l in pack.locations:
        if isinstance(l, dict) and l.get("locationId"):
            adj[l["locationId"]] = set(l.get("adjacentLocations") or [])
    if adj:
        # HUB 접근 가능 장소 + scenario 기본 장소를 시작점으로
        starts = set()
        scen = pack.raw.get("scenario.json") or {}
        if isinstance(scen, dict):
            hub = scen.get("hub") or {}
            if isinstance(hub, dict) and hub.get("defaultLocationId"):
                starts.add(hub["defaultLocationId"])
        for l in pack.locations:
            if isinstance(l, dict) and l.get("hubAccessible") and l.get("locationId"):
                starts.add(l["locationId"])
        if starts:
            seen, stack = set(starts), list(starts)
            while stack:
                cur = stack.pop()
                for nxt in adj.get(cur, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            for lid in sorted(set(adj) - seen):
                f.append(
                    Finding(
                        "WARN",
                        "LOCATION_UNREACHABLE",
                        f"locations.json:{lid}",
                        "hubAccessible 장소에서 adjacentLocations 를 따라 도달 불가",
                    )
                )

    # ⑨ factToIncident 참조
    defined_inc = pack.defined.get("INC", set())
    for fid, m in (pack.quest.get("factToIncident") or {}).items():
        if fid not in pack.facts:
            f.append(
                Finding("ERROR", "FACT_TO_INCIDENT_DANGLING", f"quest.json:factToIncident:{fid}",
                        "매핑 대상 fact 가 facts.json 에 없음")
            )
        for inc in (m or {}).get("incidents") or []:
            if inc not in defined_inc:
                f.append(
                    Finding("ERROR", "FACT_TO_INCIDENT_DANGLING",
                            f"quest.json:factToIncident:{fid}:{inc}",
                            "매핑 대상 incident 가 incidents.json 에 없음")
                )

    return f


# ─────────────────────────── 실행 ───────────────────────────

SEV_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}
SEV_MARK = {"ERROR": "✖", "WARN": "⚠", "INFO": "·"}


def audit_pack(pack_id):
    pack = Pack(pack_id)
    findings = []
    findings += check_l1_references(pack)
    findings += check_l2_contract(pack)
    findings += check_l3_deep(pack)
    findings.sort(key=lambda x: (SEV_ORDER[x.severity], x.rule, x.where))
    return pack, findings


def main():
    ap = argparse.ArgumentParser(description="콘텐츠 팩 정합성 감사")
    ap.add_argument("packs", nargs="*", help="검사할 팩 (생략 시 전 팩)")
    ap.add_argument("--ack", nargs="+", metavar="KEY", help="확인됨 등록")
    ap.add_argument("--unack", nargs="+", metavar="KEY", help="확인됨 해제")
    ap.add_argument("--note", default="", help="--ack 와 함께 쓸 메모")
    ap.add_argument("--show-acked", action="store_true", help="억제된 항목도 표시")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    all_packs = sorted(
        d for d in os.listdir(CONTENT)
        if os.path.isdir(os.path.join(CONTENT, d))
        and os.path.exists(os.path.join(CONTENT, d, "scenario.json"))
    )
    targets = args.packs or all_packs
    unknown = [p for p in targets if p not in all_packs]
    if unknown:
        print(f"알 수 없는 팩: {', '.join(unknown)}\n사용 가능: {', '.join(all_packs)}", file=sys.stderr)
        return 2

    # ack 편집 모드
    if args.ack or args.unack:
        if len(targets) != 1:
            print("--ack/--unack 은 팩을 하나만 지정해야 한다.", file=sys.stderr)
            return 2
        pack = Pack(targets[0])
        acks = pack.load_acks()
        for k in args.ack or []:
            acks[k] = args.note
            print(f"확인됨 등록: {k}")
        for k in args.unack or []:
            if acks.pop(k, None) is not None:
                print(f"확인됨 해제: {k}")
            else:
                print(f"(없음) {k}")
        pack.save_acks(acks)
        return 0

    report = {}
    total = defaultdict(int)
    for pid in targets:
        pack, findings = audit_pack(pid)
        acks = pack.load_acks()
        shown, suppressed = [], []
        for f in findings:
            (suppressed if f.key in acks and not args.show_acked else shown).append(f)
        report[pid] = {"findings": shown, "suppressed": len(suppressed), "acks": acks}
        for f in shown:
            total[f.severity] += 1

    if args.json:
        print(json.dumps(
            {p: {"suppressed": r["suppressed"],
                 "findings": [f.to_dict() for f in r["findings"]]}
             for p, r in report.items()},
            ensure_ascii=False, indent=2))
        return 1 if total["ERROR"] else 0

    for pid in targets:
        r = report[pid]
        fs = r["findings"]
        c = defaultdict(int)
        for f in fs:
            c[f.severity] += 1
        head = f"── {pid} ── ✖{c['ERROR']} ⚠{c['WARN']} ·{c['INFO']}"
        if r["suppressed"]:
            head += f"  (확인됨 {r['suppressed']}건 숨김)"
        print(f"\n{head}")
        if not fs:
            print("   정합성 이상 없음")
            continue
        cur = None
        for f in fs:
            if f.rule != cur:
                cur = f.rule
                print(f"  [{f.rule}]")
            acked = " (확인됨)" if f.key in r["acks"] else ""
            print(f"   {SEV_MARK[f.severity]} {f.where}{acked}\n       {f.message}")

    print(f"\n합계: ✖ ERROR {total['ERROR']} / ⚠ WARN {total['WARN']} / · INFO {total['INFO']}")
    if total["ERROR"]:
        print("오탐이거나 의도된 항목은 다음으로 억제:")
        print("  python3 scripts/audit_content.py <pack> --ack '<KEY>' --note '사유'")
    return 1 if total["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())
