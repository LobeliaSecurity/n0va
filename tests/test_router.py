"""n0va.handler.router.Router の単体テスト。"""

from __future__ import annotations

import pytest

from n0va.handler.router import Router


def test_register_exact_match() -> None:
    r = Router()

    def h():
        return 1

    r.register("GET", "/a", h)
    assert r.get("GET", "/a") is h
    assert r.get("get", "/a") is h
    assert r.get("POST", "/a") is None


def test_unregister() -> None:
    r = Router()

    def h():
        pass

    r.register("GET", "/x", h, name="n1")
    r.unregister("GET", "/x")
    assert r.get("GET", "/x") is None


def test_unregister_by_name() -> None:
    r = Router()

    def h():
        pass

    r.register("POST", "/y", h, name="api")
    r.unregister_by_name("api")
    assert r.get("POST", "/y") is None


def test_register_regex_fullmatch() -> None:
    r = Router()

    async def user_id_handler():
        return "ok"

    r.register_regex("GET", r"/users/\d+", user_id_handler)
    assert r.get("GET", "/users/42") is user_id_handler
    assert r.get("GET", "/users/abc") is None


def test_regex_takes_precedence_over_order() -> None:
    """先に登録した正規表現が先にマッチする。"""
    r = Router()

    async def first():
        return 1

    async def second():
        return 2

    r.register_regex("GET", r"/[a-z]+", first)
    r.register_regex("GET", r"/[a-z]{3}", second)
    assert r.get("GET", "/abc") is first
