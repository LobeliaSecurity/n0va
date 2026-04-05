from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple

RouteKey = Tuple[str, str]


class Router:
    """
    メソッド名 + パス文字列でハンドラを登録するルータ。
    実行時に `register` / `unregister` で動的に変更可能。
    """

    def __init__(self) -> None:
        self._routes: Dict[RouteKey, Callable[..., Any]] = {}
        self._names: Dict[str, RouteKey] = {}
        self._regex_routes: List[Tuple[str, Pattern[str], Callable[..., Any]]] = []

    def register(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
        *,
        name: Optional[str] = None,
    ) -> None:
        key = (method.upper(), path)
        self._routes[key] = handler
        if name is not None:
            self._names[name] = key

    def unregister(self, method: str, path: str) -> None:
        key = (method.upper(), path)
        self._routes.pop(key, None)
        to_del = [n for n, k in self._names.items() if k == key]
        for n in to_del:
            del self._names[n]

    def unregister_by_name(self, name: str) -> None:
        key = self._names.pop(name, None)
        if key is not None:
            self._routes.pop(key, None)

    def register_regex(
        self,
        method: str,
        pattern: str,
        handler: Callable[..., Any],
    ) -> None:
        """`path` 全体に `re.fullmatch` するルート（REST の `/resource/123` 等）。"""
        self._regex_routes.append((method.upper(), re.compile(pattern), handler))

    def get(self, method: str, path: str) -> Optional[Callable[..., Any]]:
        key = (method.upper(), path)
        if key in self._routes:
            return self._routes[key]
        mu = method.upper()
        for m, rx, h in self._regex_routes:
            if m == mu and rx.fullmatch(path):
                return h
        return None
