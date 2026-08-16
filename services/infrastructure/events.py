"""Minimal product events without message or transaction contents."""

import logging

logger = logging.getLogger("benny.metrics")
logger.setLevel(logging.INFO)


def log_event(name: str, user_id, **fields):
    details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    logger.info("event=%s user_id=%s %s", name, user_id, details)
