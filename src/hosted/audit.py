import json
import logging
import sys
from datetime import datetime, timezone

# Dedicated logger so audit lines are greppable/stream-separable from app logs and can't be
# silenced by a root-logger level change. One JSON object per line (k8s-friendly stdout).
_logger = logging.getLogger("ahq.audit")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def audit_log(event: str, **fields) -> None:
    """
    One structured line per security-relevant hosted event (tool_call, auth.consent_ok, ...).
    Callers must never pass tool arguments or token values — arguments routinely contain
    credentials (script steps, vault payloads) and belong in no log.
    """
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    _logger.info(json.dumps(record, default=str))
