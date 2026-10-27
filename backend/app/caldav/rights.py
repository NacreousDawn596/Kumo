"""Radicale rights plugin: each user owns their principal + calendar only."""

from __future__ import annotations

from radicale import rights


class Rights(rights.BaseRights):
    def authorization(self, user: str, user_groups: set, path: str) -> str:
        path = path.strip("/")
        if not path:
            return "R"
        segments = path.split("/")
        if segments[0] != user:
            return ""
        if len(segments) == 1:
            return "Rri"
        return "rWw"
