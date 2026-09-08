from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or os.environ.get("AURUM_DATABASE_URL")
    if not url:
        raise RuntimeError("AURUM_DATABASE_URL must be configured")
    return sessionmaker(create_engine(url), expire_on_commit=False)
