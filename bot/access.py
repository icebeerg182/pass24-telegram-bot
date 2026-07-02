"""Управление доступом к боту (список Telegram user ID)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("pass24-bot.access")

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "allowed_users.json"


class AccessControl:
    def __init__(
        self,
        env_allowed: set[int],
        env_admins: set[int],
        store_path: Path | None = None,
    ):
        self.env_allowed = set(env_allowed)
        self.admins = set(env_admins)
        self.store_path = store_path or DEFAULT_STORE
        self.dynamic_allowed = self._load()

    def _load(self) -> set[int]:
        if not self.store_path.exists():
            return set()
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            return {int(x) for x in data.get("allowed", [])}
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
            log.warning("Cannot read %s: %s", self.store_path, e)
            return set()

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"allowed": sorted(self.dynamic_allowed)}
        self.store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def is_open(self) -> bool:
        """Пустые списки = доступ всем (не рекомендуется)."""
        return not (self.env_allowed or self.dynamic_allowed or self.admins)

    def all_allowed(self) -> set[int]:
        return self.env_allowed | self.dynamic_allowed | self.admins

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admins

    def is_allowed(self, user_id: int | None) -> bool:
        if user_id is None:
            return False
        if self.is_open():
            return True
        return user_id in self.all_allowed()

    def allow(self, user_id: int) -> bool:
        """True если пользователь добавлен впервые."""
        if user_id in self.all_allowed():
            return False
        self.dynamic_allowed.add(user_id)
        self._save()
        return True

    def deny(self, user_id: int) -> bool:
        """True если пользователь был в динамическом списке."""
        if user_id in self.env_allowed or user_id in self.admins:
            return False
        if user_id not in self.dynamic_allowed:
            return False
        self.dynamic_allowed.discard(user_id)
        self._save()
        return True

    def list_users(self) -> dict[str, list[int]]:
        return {
            "admins": sorted(self.admins),
            "env": sorted(self.env_allowed),
            "bot": sorted(self.dynamic_allowed),
        }
