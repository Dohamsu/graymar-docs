"""Execution integrity for the playtest's V0 quality gate."""


def turns_executed_pass(successful_turns, requested_turns, ended_naturally, submit_errors):
    """A partial run cannot pass if a turn submission failed, even if it continued."""
    return (
        successful_turns > 0
        and not submit_errors
        and (ended_naturally or successful_turns >= requested_turns * 0.5)
    )
