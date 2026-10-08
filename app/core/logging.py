import logging

from app.core.config import settings


logger = logging.getLogger("certiflow")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.propagate = False
