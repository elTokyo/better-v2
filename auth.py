"""
Авторизация пользователей через пароль.
Whitelist хранится в data/users.json.
"""
import json
import os
import logging
from datetime import datetime
from dataclasses import dataclass, field

import config

logger = logging.getLogger(__name__)

USERS_FILE = os.path.join(config.DATA_DIR, "users.json")


@dataclass
class AuthorizedUser:
    chat_id: int
    username: str          # @username из TG (может быть пустым)
    first_name: str        # имя из TG
    authorized_at: str     # когда авторизовался (ISO)
    banned: bool = False

    def to_dict(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "username": self.username,
            "first_name": self.first_name,
            "authorized_at": self.authorized_at,
            "banned": self.banned,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AuthorizedUser":
        return cls(
            chat_id=d["chat_id"],
            username=d.get("username", ""),
            first_name=d.get("first_name", ""),
            authorized_at=d.get("authorized_at", ""),
            banned=d.get("banned", False),
        )


def _read() -> dict:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_authorized(chat_id: int) -> bool:
    """Авторизован и не забанен."""
    data = _read()
    user = data.get(str(chat_id))
    if not user:
        return False
    return not user.get("banned", False)


def is_admin(chat_id: int) -> bool:
    return chat_id == config.ADMIN_CHAT_ID


def authorize(chat_id: int, username: str, first_name: str) -> AuthorizedUser:
    data = _read()
    user = AuthorizedUser(
        chat_id=chat_id,
        username=username or "",
        first_name=first_name or "",
        authorized_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    data[str(chat_id)] = user.to_dict()
    _write(data)
    logger.info(f"Авторизован новый пользователь: {chat_id} (@{username})")
    return user


def list_users() -> list[AuthorizedUser]:
    data = _read()
    return [AuthorizedUser.from_dict(u) for u in data.values()]


def remove_user(chat_id: int) -> bool:
    data = _read()
    if str(chat_id) in data:
        del data[str(chat_id)]
        _write(data)
        return True
    return False


def set_banned(chat_id: int, banned: bool) -> bool:
    data = _read()
    if str(chat_id) not in data:
        return False
    data[str(chat_id)]["banned"] = banned
    _write(data)
    return True
