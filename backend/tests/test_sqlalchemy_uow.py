from __future__ import annotations

import pytest

from aurum.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


class FakeSession:
    def __init__(self, *, commit_error: bool = False, rollback_error: bool = False) -> None:
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.begun = self.committed = self.rolled_back = self.closed = False

    def begin(self) -> None:
        self.begun = True

    def commit(self) -> None:
        self.committed = True
        if self.commit_error:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rolled_back = True
        if self.rollback_error:
            raise RuntimeError("rollback failed")

    def close(self) -> None:
        self.closed = True


def test_uow_commits_and_closes_one_session() -> None:
    session = FakeSession()
    uow = SqlAlchemyUnitOfWork(lambda: session)  # type: ignore[arg-type]
    with uow:
        assert uow.require_session() is session
    assert session.begun and session.committed and session.closed
    assert uow.session is None


def test_uow_closes_and_clears_session_when_commit_fails() -> None:
    session = FakeSession(commit_error=True)
    uow = SqlAlchemyUnitOfWork(lambda: session)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="commit failed"):
        with uow:
            pass
    assert session.rolled_back and session.closed
    assert uow.session is None


def test_uow_closes_and_clears_session_when_block_and_rollback_fail() -> None:
    session = FakeSession(rollback_error=True)
    uow = SqlAlchemyUnitOfWork(lambda: session)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="rollback failed"):
        with uow:
            raise ValueError("application failure")
    assert session.closed
    assert uow.session is None
