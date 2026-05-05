import sys
from loguru import logger


def get_logger(name: str):
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level}</level> | "
               "<cyan>{name}</cyan> | {message}",
        level="INFO",
        colorize=True,
    )
    return logger.bind(name=name)