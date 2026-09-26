"""Comparable-run selection for the playtest's pooled quality gates."""


def select_gate_window(ledger, server_version, pool_runs):
    """Pool only runs from the same server build; unknown builds stand alone."""
    if pool_runs <= 0 or not ledger:
        return []
    if not server_version:
        return ledger[-1:]
    return [
        row for row in ledger
        if isinstance(row, dict) and row.get("server") == server_version
    ][-pool_runs:]
