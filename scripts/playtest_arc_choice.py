"""Priority choices used by the long-run playtest harness."""


def select_priority_arc_choice(choices, arc_committed):
    """Finish a committed arc; commit an available route at most once."""
    for choice in choices:
        if choice.get("id") == "arc_finale":
            return choice
    if not arc_committed:
        for choice in choices:
            if str(choice.get("id", "")).startswith("arc_commit_"):
                return choice
    return None
