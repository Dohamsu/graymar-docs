"""Comparable-run selection for the playtest's pooled quality gates."""

from hashlib import sha256
import json
from pathlib import Path


PUBLIC_LLM_SETTINGS_FIELDS = (
    "provider", "openaiModel", "claudeModel", "geminiModel", "maxRetries",
    "timeoutMs", "maxTokens", "temperature", "fallbackProvider", "fallbackModel",
)
REQUIRED_RUNTIME_FLAG_KEYS = (
    "LLM_ALTERNATE_MODEL", "LLM_MAIN_ALTERNATE_MODEL",
    "LLM_DIALOGUE_MODEL", "LLM_LIGHT_MODEL",
)


def make_gate_cohort(server_version, started_at, pack_dir, settings, runtime_flags, run_config):
    """Fingerprint one server process, authored pack, effective config and setup."""
    if not server_version or not started_at:
        return ""
    if any(field not in settings for field in PUBLIC_LLM_SETTINGS_FIELDS):
        return ""
    if not settings.get("provider") or any(key not in runtime_flags for key in REQUIRED_RUNTIME_FLAG_KEYS):
        return ""
    pack_files = sorted(Path(pack_dir).glob("*.json"))
    if not pack_files:
        return ""
    pack_digest = sha256()
    for file in pack_files:
        pack_digest.update(file.name.encode("utf-8"))
        pack_digest.update(b"\0")
        pack_digest.update(file.read_bytes())
        pack_digest.update(b"\0")
    comparable_inputs = {
        "server": server_version,
        "startedAt": started_at,
        "content": pack_digest.hexdigest(),
        "settings": settings,
        "runtimeFlags": runtime_flags,
        "run": run_config,
    }
    return sha256(json.dumps(comparable_inputs, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def select_gate_window(ledger, server_version, cohort, pool_runs):
    """Pool comparable runs only; unknown setup or version stands alone."""
    if pool_runs <= 0 or not ledger:
        return []
    if not server_version or not cohort:
        return ledger[-1:]
    return [
        row for row in ledger
        if isinstance(row, dict)
        and row.get("server") == server_version
        and row.get("cohort") == cohort
    ][-pool_runs:]
