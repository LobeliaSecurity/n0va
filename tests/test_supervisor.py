"""n0va.core.supervisor の分岐テスト。"""

from __future__ import annotations

import os
import sys

import pytest

from n0va.core import supervisor as sup


def test_is_worker_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(sup.Supervisor.CHILD_ENV, raising=False)
    assert sup.Supervisor.is_worker_process() is False
    monkeypatch.setenv(sup.Supervisor.CHILD_ENV, "1")
    assert sup.Supervisor.is_worker_process() is True


def test_should_use_supervisor_respects_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(sup.Supervisor.CHILD_ENV, raising=False)
    monkeypatch.delenv(sup.Supervisor.NO_SUPERVISE_ENV, raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert sup.Supervisor.should_use_supervisor(False) is False
    monkeypatch.setenv(sup.Supervisor.CHILD_ENV, "1")
    assert sup.Supervisor.should_use_supervisor(True) is False


def test_should_use_supervisor_no_supervise_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(sup.Supervisor.CHILD_ENV, raising=False)
    monkeypatch.setenv(sup.Supervisor.NO_SUPERVISE_ENV, "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert sup.Supervisor.should_use_supervisor(True) is False


def test_should_use_supervisor_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(sup.Supervisor.CHILD_ENV, raising=False)
    monkeypatch.delenv(sup.Supervisor.NO_SUPERVISE_ENV, raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_supervisor.py::x")
    assert sup.Supervisor.should_use_supervisor(True) is False


def test_can_supervise_argv_false_for_dash_c(monkeypatch: pytest.MonkeyPatch) -> None:
    old = sys.argv
    try:
        sys.argv = ["-c"]
        assert sup.Supervisor.can_supervise_argv() is False
    finally:
        sys.argv = old
