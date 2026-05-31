"""로깅 초기화 — `final_term.*` 네임스페이스만 핸들러 부착 (root 미간섭)."""

import logging
import os
import sys

LOGGER_NAME = "final_term"
DEFAULT_LEVEL = logging.INFO


def setup_logging(level: int | str | None = None) -> logging.Logger:
    """멱등. 환경변수 `FINAL_TERM_LOG_LEVEL` (기본 INFO)."""
    if level is None:
        env = os.getenv("FINAL_TERM_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env, DEFAULT_LEVEL)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
