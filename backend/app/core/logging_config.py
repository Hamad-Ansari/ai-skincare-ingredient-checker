"""Application logging configuration."""

import logging


def configure_logging(level: str) -> None:
    """Configure a minimal log format that does not include request bodies or secrets."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
