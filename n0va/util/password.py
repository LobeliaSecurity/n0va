import secrets
import string


# `of_length` 由来。読み取りやすさのため紛らわしい記号は含めない運用も可。
_SYMBOLS = """~!@#$%^&*()-_=+{}|<>?.,`."""


class RandomPassword:
    """ブラウザ風および任意長のランダムパスワード生成。"""

    @staticmethod
    def generate(
        length: int,
        *,
        upper: bool = True,
        lower: bool = True,
        digits: bool = True,
        symbols: bool = True,
    ) -> str:
        """
        指定した文字種からパスワードを生成する。有効な各種類から最低 1 文字ずつ含める。
        いずれかの種類も無効なら ValueError。
        """
        pools: list[str] = []
        if upper:
            pools.append(string.ascii_uppercase)
        if lower:
            pools.append(string.ascii_lowercase)
        if digits:
            pools.append(string.digits)
        if symbols:
            pools.append(_SYMBOLS)
        if not pools:
            raise ValueError("at least one character class required")
        need = len(pools)
        if length < need:
            raise ValueError(f"length must be at least {need} for selected character classes")
        alphabet = "".join(pools)
        chars: list[str] = []
        for pool in pools:
            chars.append(secrets.choice(pool))
        for _ in range(length - need):
            chars.append(secrets.choice(alphabet))
        # 暗号論的シャッフル
        for i in range(len(chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            chars[i], chars[j] = chars[j], chars[i]
        return "".join(chars)

    @staticmethod
    def from_preset(preset: str) -> str:
        """低 / 中 / 高のプリセット（長さと文字種が固定）。"""
        p = (preset or "").strip().lower()
        if p == "low":
            return RandomPassword.generate(12, upper=True, lower=True, digits=True, symbols=False)
        if p == "medium":
            return RandomPassword.generate(16, upper=True, lower=True, digits=True, symbols=True)
        if p == "high":
            return RandomPassword.generate(24, upper=True, lower=True, digits=True, symbols=True)
        raise ValueError(f"unknown preset: {preset!r}")

    @staticmethod
    def safari_style() -> str:
        R = "".join(
            [
                *[
                    secrets.choice(f"{string.ascii_letters}{string.digits}")
                    for x in range(6)
                ],
                "-",
                *[
                    secrets.choice(f"{string.ascii_letters}{string.digits}")
                    for x in range(6)
                ],
                "-",
                *[
                    secrets.choice(f"{string.ascii_letters}{string.digits}")
                    for x in range(6)
                ],
            ]
        )
        return R

    @staticmethod
    def firefox_style() -> str:
        """15 文字: 英字・数字・記号を混在（各種類から最低 1 文字）。"""
        return RandomPassword.generate(
            15, upper=True, lower=True, digits=True, symbols=True
        )

    @staticmethod
    def of_length(length: int) -> str:
        """英字・数字・記号を混在させた任意長（後方互換）。"""
        return RandomPassword.generate(
            length, upper=True, lower=True, digits=True, symbols=True
        )
