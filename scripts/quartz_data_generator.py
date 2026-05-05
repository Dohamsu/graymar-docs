#!/usr/bin/env python3
"""
Quartz 데이터 그래프 생성기 (Phase 1~4 통합)

게임 콘텐츠 데이터(JSON)를 Quartz markdown 페이지로 자동 변환하여
NPC/장소/파벌/사건/단서/아이템 간 관계 그래프를 형성한다.

생성 폴더 (quartz/content/):
  npcs/        — 43 NPC (Phase 1)
  locations/   — 7 장소 (Phase 2)
  factions/    — 4 파벌 (Phase 2)
  quest/       — 퀘스트 상태 + 단서 (Phase 3)
  incidents/   — 사건 (Phase 3)
  items/       — 26 아이템 (Phase 4)

특징:
- frontmatter tags로 분류 (faction, tier, posture 등) → 그래프뷰 색상 분리
- wiki link로 모든 관계 표현 → 그래프뷰 엣지 자동 생성
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/dohamsu/Workspace/graymar")
DATA = ROOT / "content/graymar_v1"
OUT = ROOT / "quartz/content"


def load(name):
    return json.load(open(DATA / f"{name}.json", encoding="utf-8"))


def slugify_tag(s):
    """태그용 slug — 소문자 + 하이픈"""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fm(title, tags, extra=None):
    """frontmatter 생성"""
    lines = ["---", f"title: {title}", f"tags: [{', '.join(tags)}]"]
    if extra:
        for k, v in extra.items():
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def link(target, display=None):
    """wiki link"""
    if display:
        return f"[[{target}|{display}]]"
    return f"[[{target}]]"


# ======================================================
# Phase 1: NPC 페이지 (43개)
# ======================================================
def gen_npcs(npcs, locations, factions, incidents_data):
    out_dir = OUT / "npcs"
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    incidents_dict = {i["incidentId"]: i for i in incidents_data.get("incidents", [])}
    locations_dict = {l["locationId"]: l for l in locations}
    factions_dict = {f["factionId"]: f for f in factions}

    for npc in npcs:
        npc_id = npc["npcId"]
        name = npc["name"]
        alias = npc.get("unknownAlias", "")
        tier = npc.get("tier", "?")
        faction = npc.get("faction") or "NONE"
        posture = npc.get("basePosture", "?")
        gender = npc.get("gender", "")
        role = npc.get("role", "")

        # tags
        tags = ["npc", f"tier-{tier.lower()}", f"posture-{slugify_tag(posture)}"]
        if faction and faction != "NONE":
            tags.append(f"faction-{slugify_tag(faction)}")
        if gender:
            tags.append(f"gender-{gender}")

        body = []
        body.append(fm(name, tags))
        body.append("")
        body.append(f"# {name}")
        body.append("")
        if alias and alias != name:
            body.append(f"> **{alias}**")
            body.append("")
        body.append(f"**역할**: {role}")
        body.append("")

        # personality
        p = npc.get("personality") or {}
        if p.get("core"):
            body.append(f"## 본질")
            body.append(p["core"])
            body.append("")
        if p.get("speechStyle"):
            body.append(f"## 말투")
            body.append(p["speechStyle"])
            body.append("")
        if p.get("traits"):
            body.append(f"## 특성")
            for t in p["traits"]:
                body.append(f"- {t}")
            body.append("")
        if p.get("innerConflict"):
            body.append(f"## 내면 갈등")
            body.append(p["innerConflict"])
            body.append("")
        if p.get("softSpot"):
            body.append(f"## 약점")
            body.append(p["softSpot"])
            body.append("")
        if npc.get("agenda"):
            body.append(f"## 의도/의제")
            body.append(npc["agenda"])
            body.append("")

        # 관계 (NPC ↔ NPC)
        relations = (p or {}).get("npcRelations", {})
        if relations:
            body.append(f"## 관계")
            for other_id, rel_desc in relations.items():
                body.append(f"- {link(f'npcs/{other_id}', other_id)}: {rel_desc}")
            body.append("")

        # 소속 파벌
        if faction and faction != "NONE" and faction in factions_dict:
            body.append(f"## 소속")
            body.append(f"- {link(f'factions/{faction}')}")
            body.append("")

        # 활동 장소 (schedule)
        sched = npc.get("schedule", {}).get("default", {})
        if sched:
            body.append(f"## 활동 장소")
            for time_phase in ["DAWN", "DAY", "DUSK", "NIGHT"]:
                entry = sched.get(time_phase)
                if entry:
                    loc_id = entry.get("locationId")
                    activity = entry.get("activity", "")
                    if loc_id and loc_id in locations_dict:
                        body.append(f"- **{time_phase}**: {link(f'locations/{loc_id}')} — {activity}")
            body.append("")

        # 알고 있는 단서
        kf = npc.get("knownFacts") or []
        if kf:
            body.append(f"## 알고 있는 단서")
            for f in kf:
                fid = f.get("factId") if isinstance(f, dict) else f
                detail = f.get("detail", "") if isinstance(f, dict) else ""
                body.append(f"- {link(f'quest/facts/{fid}')}{': ' + detail if detail else ''}")
            body.append("")

        # 연관 사건
        li = npc.get("linkedIncidents") or []
        if li:
            body.append(f"## 연관 사건")
            for inc_id in li:
                inc = incidents_dict.get(inc_id)
                title = inc.get("title", inc_id) if inc else inc_id
                body.append(f"- {link(f'incidents/{inc_id}', title)}")
            body.append("")

        write(out_dir / f"{npc_id}.md", "\n".join(body))

    print(f"  ✓ NPC: {len(npcs)} pages")


# ======================================================
# Phase 2: 장소 + 파벌
# ======================================================
def gen_locations(locations, npcs):
    out_dir = OUT / "locations"
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    # NPC → 활동 장소 역매핑
    loc_to_npcs = {}
    for npc in npcs:
        sched = npc.get("schedule", {}).get("default", {})
        for tp, entry in sched.items():
            loc_id = entry.get("locationId") if isinstance(entry, dict) else None
            if loc_id:
                loc_to_npcs.setdefault(loc_id, []).append((npc["npcId"], npc["name"], tp))

    for loc in locations:
        loc_id = loc["locationId"]
        name = loc["name"]
        tags = ["location"]
        for t in loc.get("tags", []):
            tags.append(f"loc-tag-{slugify_tag(t)}")

        body = [fm(name, tags), "", f"# {name}", "", loc.get("description", ""), ""]

        if loc.get("nightDescription"):
            body.append("## 밤의 모습")
            body.append(loc["nightDescription"])
            body.append("")

        if loc.get("dangerLevel") is not None:
            body.append(f"**위험도**: {loc['dangerLevel']}")
            body.append("")

        # 인접 장소
        adj = loc.get("adjacentLocations") or []
        if adj:
            body.append("## 인접 장소")
            for a in adj:
                body.append(f"- {link(f'locations/{a}')}")
            body.append("")

        # 활동 NPC
        npcs_here = loc_to_npcs.get(loc_id, [])
        if npcs_here:
            body.append("## 이 장소에 있는 인물")
            seen = set()
            for npc_id, npc_name, tp in npcs_here:
                key = (npc_id, npc_name)
                if key in seen:
                    continue
                seen.add(key)
                body.append(f"- {link(f'npcs/{npc_id}', npc_name)}")
            body.append("")

        write(out_dir / f"{loc_id}.md", "\n".join(body))

    print(f"  ✓ Locations: {len(locations)} pages")


def gen_factions(factions, npcs):
    out_dir = OUT / "factions"
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    fac_to_npcs = {}
    for npc in npcs:
        f = npc.get("faction")
        if f:
            fac_to_npcs.setdefault(f, []).append(npc)

    for fac in factions:
        fac_id = fac["factionId"]
        name = fac["name"]
        tags = ["faction", f"faction-{slugify_tag(fac_id)}"]

        body = [fm(name, tags), "", f"# {name}", ""]

        if fac.get("initialReputation") is not None:
            body.append(f"**초기 평판**: {fac['initialReputation']}")
            body.append("")

        # 소속 NPC
        members = fac_to_npcs.get(fac_id, [])
        if members:
            body.append("## 소속 인물")
            for npc in members:
                target = "npcs/" + npc["npcId"]
                body.append(f"- {link(target, npc['name'])} — {npc.get('role', '')}")
            body.append("")

        write(out_dir / f"{fac_id}.md", "\n".join(body))

    print(f"  ✓ Factions: {len(factions)} pages")


# ======================================================
# Phase 3: 퀘스트 상태 + 단서 + 사건
# ======================================================
def gen_quest(quest, npcs, locations):
    states_dir = OUT / "quest/states"
    facts_dir = OUT / "quest/facts"
    for d in [states_dir, facts_dir]:
        if d.exists():
            for f in d.iterdir():
                f.unlink()
        d.mkdir(parents=True, exist_ok=True)

    # 단서 → NPC 역매핑
    fact_to_npcs = {}
    for npc in npcs:
        for f in npc.get("knownFacts") or []:
            fid = f.get("factId") if isinstance(f, dict) else f
            if fid:
                fact_to_npcs.setdefault(fid, []).append(npc)

    # facts 페이지 (quest.json의 facts dict)
    facts_dict = quest.get("facts") or {}
    for fact_id, fact_info in facts_dict.items():
        if isinstance(fact_info, dict):
            description = fact_info.get("description", "")
            category = fact_info.get("category", "")
        else:
            description = str(fact_info)
            category = ""

        tags = ["fact"]
        if category:
            tags.append(f"fact-cat-{slugify_tag(category)}")

        body = [fm(fact_id, tags), "", f"# {fact_id}", ""]
        if description:
            body.append(description)
            body.append("")
        if category:
            body.append(f"**카테고리**: {category}")
            body.append("")

        # 이 단서를 알고 있는 NPC
        knowers = fact_to_npcs.get(fact_id, [])
        if knowers:
            body.append("## 이 단서를 아는 인물")
            for npc in knowers:
                target = "npcs/" + npc["npcId"]
                body.append(f"- {link(target, npc['name'])}")
            body.append("")

        write(facts_dir / f"{fact_id}.md", "\n".join(body))

    # quest 상태 페이지 (S0~S5)
    state_descs = quest.get("stateDescriptions") or {}
    state_trans = quest.get("stateTransitions") or {}
    states = quest.get("states") or []

    for state in states:
        desc = state_descs.get(state, "")
        tags = ["quest-state"]

        body = [fm(state, tags), "", f"# {state}", ""]
        if desc:
            body.append(desc)
            body.append("")

        # 전환 조건 (이 state → 다음 state)
        next_trans = {k: v for k, v in state_trans.items() if k.startswith(f"{state}→")}
        if next_trans:
            body.append("## 다음 단계 진행 조건")
            for trans_key, trans_info in next_trans.items():
                target = trans_key.split("→")[1]
                body.append(f"### → {link(f'quest/states/{target}')}")
                body.append("")
                if trans_info.get("description"):
                    body.append(trans_info["description"])
                    body.append("")
                req = trans_info.get("requiredFacts") or []
                if req:
                    body.append("**필요 단서**:")
                    for f in req:
                        body.append(f"- {link(f'quest/facts/{f}')}")
                    body.append("")
                alt = trans_info.get("alternativeFacts") or []
                if alt:
                    body.append("**대체 경로 (alternativeFacts)**:")
                    for f in alt:
                        body.append(f"- {link(f'quest/facts/{f}')}")
                    body.append("")
                any_of = trans_info.get("requiredAnyOf") or []
                if any_of:
                    body.append("**필요 (둘 중 하나)**:")
                    for group in any_of:
                        body.append("- " + " AND ".join(link(f"quest/facts/{f}") for f in group))
                    body.append("")

        # 이전 state (어떤 state에서 이 state로 오나)
        prev_trans = {k: v for k, v in state_trans.items() if k.endswith(f"→{state}")}
        if prev_trans:
            body.append("## 이전 단계")
            for trans_key in prev_trans:
                source = trans_key.split("→")[0]
                body.append(f"- {link(f'quest/states/{source}')}")
            body.append("")

        write(states_dir / f"{state}.md", "\n".join(body))

    print(f"  ✓ Quest states: {len(states)}, facts: {len(facts_dict)} pages")


def gen_incidents(incidents_data, npcs, locations):
    out_dir = OUT / "incidents"
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    incs = incidents_data.get("incidents", [])

    # incident → linked NPC 역매핑
    inc_to_npcs = {}
    for npc in npcs:
        for inc_id in npc.get("linkedIncidents") or []:
            inc_to_npcs.setdefault(inc_id, []).append(npc)

    for inc in incs:
        inc_id = inc.get("incidentId")
        title = inc.get("title", inc_id)
        kind = inc.get("kind", "")
        location = inc.get("locationId")

        tags = ["incident"]
        if kind:
            tags.append(f"incident-{slugify_tag(kind)}")

        body = [fm(title, tags), "", f"# {title}", ""]
        if inc.get("description"):
            body.append(inc["description"])
            body.append("")
        if kind:
            body.append(f"**유형**: {kind}")
        if location:
            body.append(f"**장소**: {link(f'locations/{location}')}")
        body.append("")

        # 연관 NPC
        linked = inc_to_npcs.get(inc_id, [])
        if linked:
            body.append("## 연관 인물")
            for npc in linked:
                target = "npcs/" + npc["npcId"]
                body.append(f"- {link(target, npc['name'])}")
            body.append("")

        write(out_dir / f"{inc_id}.md", "\n".join(body))

    print(f"  ✓ Incidents: {len(incs)} pages")


# ======================================================
# Phase 4: 아이템 + 장비 드랍
# ======================================================
def gen_items(items, drops, locations):
    out_dir = OUT / "items"
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 아이템 → 드랍 장소 역매핑
    item_to_locs = {}
    for d in drops:
        for drop in d.get("drops", []):
            item_id = drop.get("itemId")
            loc_id = d.get("locationId")
            if item_id and loc_id:
                item_to_locs.setdefault(item_id, set()).add(loc_id)

    for item in items:
        item_id = item.get("itemId")
        name = item.get("name", item_id)
        item_type = item.get("type", "")

        tags = ["item"]
        if item_type:
            tags.append(f"item-type-{slugify_tag(item_type)}")
        if item.get("rarity"):
            tags.append(f"rarity-{slugify_tag(item.get('rarity'))}")

        body = [fm(name, tags), "", f"# {name}", ""]
        if item.get("description"):
            body.append(item["description"])
            body.append("")
        if item_type:
            body.append(f"**유형**: {item_type}")
        if item.get("rarity"):
            body.append(f"**희귀도**: {item['rarity']}")
        body.append("")

        # 연관 quest fact
        if item.get("factKey"):
            fact_key = item["factKey"]
            body.append(f"## 연관 단서")
            body.append(f"- {link('quest/facts/' + fact_key)}")
            body.append("")

        # 드랍 장소
        locs = item_to_locs.get(item_id, set())
        if locs:
            body.append("## 등장 장소")
            for loc_id in sorted(locs):
                body.append(f"- {link(f'locations/{loc_id}')}")
            body.append("")

        write(out_dir / f"{item_id}.md", "\n".join(body))

    print(f"  ✓ Items: {len(items)} pages")


# ======================================================
# Index 페이지 (각 폴더의 진입점)
# ======================================================
def gen_indexes():
    """각 폴더의 index 페이지로 카테고리 진입"""
    indexes = {
        "npcs/index.md": ("NPCs", "그레이마르의 인물 43명. tier별/파벌별 분류."),
        "locations/index.md": ("Locations", "그레이마르의 장소 7개."),
        "factions/index.md": ("Factions", "그레이마르의 파벌."),
        "quest/index.md": ("Quest", "메인 퀘스트 (states + facts)."),
        "incidents/index.md": ("Incidents", "도시에서 발생하는 사건."),
        "items/index.md": ("Items", "장비/소비/퀘스트 아이템."),
    }
    for path, (title, desc) in indexes.items():
        body = [fm(title, ["index"]), "", f"# {title}", "", desc, ""]
        body.append("> 폴더 안 모든 페이지를 좌측 Explorer에서 확인하거나 그래프뷰로 탐색하세요.")
        write(OUT / path, "\n".join(body))


def main():
    print("=== Quartz 데이터 생성기 시작 ===", flush=True)

    npcs = load("npcs")
    locations = load("locations")
    factions = load("factions")
    quest = load("quest")
    incidents = load("incidents")
    items = load("items")
    drops = load("equipment_drops")

    print(f"\n[Phase 1] NPC", flush=True)
    gen_npcs(npcs, locations, factions, incidents)

    print(f"\n[Phase 2] 장소 + 파벌", flush=True)
    gen_locations(locations, npcs)
    gen_factions(factions, npcs)

    print(f"\n[Phase 3] 퀘스트 + 사건", flush=True)
    gen_quest(quest, npcs, locations)
    gen_incidents(incidents, npcs, locations)

    print(f"\n[Phase 4] 아이템", flush=True)
    gen_items(items, drops, locations)

    print(f"\n[Index] 카테고리 진입 페이지", flush=True)
    gen_indexes()

    # 통계
    print(f"\n=== 완료 ===", flush=True)
    total = sum(1 for _ in OUT.rglob("*.md")) - sum(1 for _ in (OUT).glob("*.md"))
    print(f"  생성된 페이지 (npcs+locations+factions+quest+incidents+items+indexes): 약 {total}개", flush=True)


if __name__ == "__main__":
    main()
