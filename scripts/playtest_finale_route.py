"""Goal-directed graymar playtest inputs; never changes game state directly."""


FACT_ACTIONS = (
    ("FACT_WAGE_FRAUD_PATTERN", "에드릭 베일에게 공물 장부의 임금 지급액과 실제 출납이 어떻게 다른지 묻는다"),
    ("FACT_TAMPERED_LOGS", "에드릭 베일에게 장부 셋째 칸 넷째 줄의 필체와 잉크 조작 흔적을 확인해 달라고 묻는다"),
    ("FACT_INSIDE_JOB", "에드릭 베일에게 장부에 접근할 수 있던 내부자가 누구이며 누가 기록을 고쳤는지 묻는다"),
)
STAGE_ACTIONS = (
    "에드릭 베일과 함께 찢긴 교대표와 이중 장부 사본을 조사한다",
    "벨론 대위에게 찢긴 교대표와 장부 조작 증거를 제시하고 조사 허가를 요청한다",
    "벨론 대위와 함께 마이렐의 은닉 장부 원본을 확보하고 마이렐을 대면한다",
)
ROUTE_STAGE_ACTIONS = {
    "EXPOSE_CORRUPTION": STAGE_ACTIONS,
    "PROFIT_FROM_CHAOS": (
        "쉐도우에게 동쪽 부두 밀수 경로 지도를 35골드에 구입한다",
        "빈민가에서 동쪽 부두 밀수 증거를 노동 길드와 상인 길드의 협상 카드로 제시하고 중개 대가를 요구한다",
        "빈민가에서 양쪽 세력의 거래 증거를 마지막 교섭 카드로 제시해 대가를 요구하고 추격을 벗어난다",
    ),
    "ALLY_GUARD": (
        "벨론 대위에게 찢긴 교대표와 장부 흔적을 제시하고 조사 허가를 요청한다",
        "벨론 대위와 야간 순찰 기록 및 마이렐 부하의 하역 묵인 증거를 조사한다",
        "벨론 대위와 병영에서 마이렐의 은닉 장부를 확보하고 마이렐을 대면한다",
    ),
}

EARLY_QUEST_ACTIONS = {
    "S3": "하를룬에게 동쪽 부두의 야간 하역과 밀수품이 길드 공식 화물에 섞여 시장으로 들어오는 경로를 묻는다",
    "S4": "경비대 수비대장과 함께 마이렐 수사 관련 비공식 내사 기록과 의심 대상 명단을 조사한다",
}


def finale_fallback_choices(choices):
    """Generic playtest behavior must not commit or finish a goal-directed run."""
    return [c for c in choices if not str(c.get("id") or "").startswith(("arc_commit_", "arc_finale"))]


def verify_finale_route(route, arc_state, turn_logs, stage_mode="full", quest_state=None):
    """Distinguish a three-stage finale from the S5 early safety-net finale."""
    terminal = next((t for t in reversed(turn_logs) if t.get("nodeOutcome") == "RUN_ENDED"), None)
    ending = (terminal or {}).get("endingResult") or {}
    stages = sorted(set(((arc_state or {}).get("stageProgress") or {}).get("completedStages") or []))
    actual_route = (arc_state or {}).get("currentRoute")
    explicit = bool(terminal and terminal.get("input") == "FINALE:arc_finale")
    full_three_stages = all(i in stages for i in (1, 2, 3))
    quest_before_finale = (terminal or {}).get("questStateBefore")
    correct_stage_mode = full_three_stages if stage_mode == "full" else (
        not full_three_stages and quest_before_finale == "S5_RESOLVE"
    )
    return {
        "pass": bool(explicit and actual_route == route and ending.get("arcRoute") == route and correct_stage_mode),
        "stageMode": stage_mode,
        "requestedRoute": route,
        "committedRoute": actual_route,
        "endingRoute": ending.get("arcRoute"),
        "completedStages": stages,
        "explicitFinale": explicit,
        "fullThreeStages": full_three_stages,
        "questState": quest_state,
        "questStateBeforeFinale": quest_before_finale,
    }


def choose_finale_input(state, choices, stage_locations, route="EXPOSE_CORRUPTION", stage_mode="full"):
    """Choose one ordinary player input toward the selected authored finale.

    Returns None if this pack/state has no safe goal-directed input. The caller
    may then use its existing generic player behavior. No facts are injected.
    """
    node = (state.get("currentNode") or {}).get("nodeType")
    run = state.get("runState") or {}
    quest = run.get("questState") or "S0_ARRIVE"
    arc = run.get("arcState") or {}
    progress = arc.get("stageProgress") or {}
    choice_ids = {c.get("id") for c in choices}

    committed = bool(arc.get("currentRoute")) and (
        isinstance(arc.get("committedAt"), int) or (arc.get("commitment") or 0) >= 2
    )
    if committed and arc.get("currentRoute") != route:
        raise ValueError(f"Finale route mismatch: expected {route}, actual {arc.get('currentRoute')}")

    completed = set(progress.get("completedStages") or [])
    if "arc_finale" in choice_ids and (
        (stage_mode == "early" and quest == "S5_RESOLVE" and not all(i in completed for i in (1, 2, 3)))
        or (stage_mode == "full" and all(i in completed for i in (1, 2, 3)))
    ):
        return {"type": "CHOICE", "choiceId": "arc_finale"}
    next_stage = next((i for i in range(1, len(stage_locations) + 1) if i not in completed), None)
    if committed and stage_mode == "early":
        target_location = (
            "LOC_HARBOR" if quest.startswith("S3_") else
            "LOC_GUARD" if quest.startswith(("S4_", "S5_")) else
            "LOC_MARKET"
        )
    else:
        target_location = stage_locations[next_stage - 1] if committed and next_stage else "LOC_MARKET"

    if node == "HUB":
        if "accept_quest" in choice_ids:
            return {"type": "CHOICE", "choiceId": "accept_quest"}
        if not committed and quest.startswith(("S3_", "S4_", "S5_")):
            commit_id = f"arc_commit_{route.lower()}"
            if commit_id in choice_ids:
                return {"type": "CHOICE", "choiceId": commit_id}
        go_id = "go_" + target_location.removeprefix("LOC_").lower()
        if go_id in choice_ids:
            return {"type": "CHOICE", "choiceId": go_id}
        return None

    if node != "LOCATION":
        return None
    current_location = (run.get("worldState") or {}).get("currentLocationId")
    if current_location != target_location or (not committed and quest.startswith(("S3_", "S4_", "S5_"))):
        return {"type": "ACTION", "text": "다른 장소로 이동한다"}

    if committed and next_stage:
        if stage_mode == "early":
            if quest.startswith("S3_"):
                return {"type": "ACTION", "text": EARLY_QUEST_ACTIONS["S3"]}
            if quest.startswith("S4_"):
                return {"type": "ACTION", "text": EARLY_QUEST_ACTIONS["S4"]}
            return {"type": "ACTION", "text": "아무 거래도 시작하지 않고 현장의 움직임을 지켜본다"}
        actions = ROUTE_STAGE_ACTIONS.get(route)
        if not actions:
            return None
        return {"type": "ACTION", "text": actions[next_stage - 1]}
    if not committed:
        facts = set(run.get("discoveredQuestFacts") or [])
        for fact_id, action in FACT_ACTIONS:
            if fact_id not in facts:
                return {"type": "ACTION", "text": action}
        return {"type": "ACTION", "text": FACT_ACTIONS[-1][1]}
    return None
