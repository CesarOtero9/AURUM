from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker


class SqlAlchemyUnitOfWork:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self.session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._sessions()
        self.session.begin()
        return self

    def require_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("Persistence adapters require an active UnitOfWork")
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        session = self.session
        if session is None:
            return None
        try:
            if exc_type is None:
                session.commit()
            else:
                session.rollback()
        except BaseException:
            # A failed commit may leave a transaction open; attempt cleanup while
            # preserving the original persistence failure.
            try:
                session.rollback()
            finally:
                raise
        finally:
            try:
                session.close()
            finally:
                self.session = None
        return None
