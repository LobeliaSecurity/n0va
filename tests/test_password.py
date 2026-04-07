"""n0va.util.password.RandomPassword の単体テスト。"""

from __future__ import annotations

import re

import pytest

from n0va.util.password import RandomPassword


def test_generate_requires_one_class() -> None:
    with pytest.raises(ValueError, match="at least one character class"):
        RandomPassword.generate(8, upper=False, lower=False, digits=False, symbols=False)


def test_generate_length_vs_pools() -> None:
    with pytest.raises(ValueError, match="length must be at least"):
        RandomPassword.generate(2, upper=True, lower=True, digits=True, symbols=True)


def test_generate_includes_each_enabled_class() -> None:
    pwd = RandomPassword.generate(
        32, upper=True, lower=True, digits=True, symbols=False
    )
    assert len(pwd) == 32
    assert re.search(r"[A-Z]", pwd)
    assert re.search(r"[a-z]", pwd)
    assert re.search(r"\d", pwd)
    assert not re.search(
        r"[" + re.escape(RandomPassword.SYMBOL_CHARSET) + r"]", pwd
    )


def test_from_preset() -> None:
    low = RandomPassword.from_preset("low")
    assert len(low) == 12
    med = RandomPassword.from_preset("medium")
    assert len(med) == 16
    high = RandomPassword.from_preset("high")
    assert len(high) == 24
    with pytest.raises(ValueError, match="unknown preset"):
        RandomPassword.from_preset("nope")


def test_safari_style_format() -> None:
    s = RandomPassword.safari_style()
    assert re.fullmatch(
        r"[A-Za-z0-9]{6}-[A-Za-z0-9]{6}-[A-Za-z0-9]{6}", s
    ), s


def test_firefox_style_length_and_classes() -> None:
    s = RandomPassword.firefox_style()
    assert len(s) == 15
    assert re.search(r"[A-Z]", s)
    assert re.search(r"[a-z]", s)
    assert re.search(r"\d", s)
    assert re.search(r"[" + re.escape(RandomPassword.SYMBOL_CHARSET) + r"]", s)


def test_of_length() -> None:
    s = RandomPassword.of_length(20)
    assert len(s) == 20
