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


def choose_finale_input(state, choices, stage_locations):
    """Choose one ordinary player input toward EXPOSE_CORRUPTION's authored finale.

    Returns None if this pack/state has no safe goal-directed input. The caller
    may then use its existing generic player behavior. No facts are injected.
    """
    node = (state.get("currentNode") or {}).get("nodeType")
    run = state.get("runState") or {}
    quest = run.get("questState") or "S0_ARRIVE"
    arc = run.get("arcState") or {}
    progress = arc.get("stageProgress") or {}
    choice_ids = {c.get("id") for c in choices}

    if "arc_finale" in choice_ids:
        return {"type": "CHOICE", "choiceId": "arc_finale"}

    committed = bool(arc.get("currentRoute")) and (
        isinstance(arc.get("committedAt"), int) or (arc.get("commitment") or 0) >= 2
    )
    completed = set(progress.get("completedStages") or [])
    next_stage = next((i for i in range(1, len(stage_locations) + 1) if i not in completed), None)
    target_location = stage_locations[next_stage - 1] if committed and next_stage else "LOC_MARKET"

    if node == "HUB":
        if "accept_quest" in choice_ids:
            return {"type": "CHOICE", "choiceId": "accept_quest"}
        if not committed and quest.startswith(("S3_", "S4_", "S5_")):
            commit_id = "arc_commit_expose_corruption"
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
        return {"type": "ACTION", "text": STAGE_ACTIONS[next_stage - 1]}
    if not committed:
        facts = set(run.get("discoveredQuestFacts") or [])
        for fact_id, action in FACT_ACTIONS:
            if fact_id not in facts:
                return {"type": "ACTION", "text": action}
        return {"type": "ACTION", "text": FACT_ACTIONS[-1][1]}
    return None
