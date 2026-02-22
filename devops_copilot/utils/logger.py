import logging
import sys
from rich.logging import RichHandler

def setup_logger(name: str = "agentnexus") -> logging.Logger:
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    logger = logging.getLogger(name)
    return logger

logger = setup_logger()
