import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./codeguard.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import logging
    import traceback
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    logger = logging.getLogger("codeguard.database")

    try:
        config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
        logger.info("Alembic config path: %s", config_path)
        logger.info("Starting Alembic database upgrade to head")

        config = Config(str(config_path))

        command.upgrade(config, "head")

        logger.info("Alembic database upgrade completed successfully")

    except Exception:
        logger.exception("ALEMBIC MIGRATION FAILED")
        traceback.print_exc()
        raise
