from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock

from src.export import DEFAULT_FIELDS, resolve_fields
from src.paths import CONFIG


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_id() -> str:
    return uuid.uuid4().hex[:10]


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()
        self.data = {
            "cookie": None,
            "history": [],
            "settings": {"default_size": 100, "fields": list(DEFAULT_FIELDS), "unmask_ip": False},
        }
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        self.data.update(loaded)
        cookies = self.data.pop("cookies", None)
        if not self.data.get("cookie") and cookies:
            chosen = next((c for c in cookies if c.get("enabled")), cookies[0] if cookies else None)
            self.data["cookie"] = chosen
        settings = self.data.setdefault("settings", {})
        settings.setdefault("default_size", 100)
        settings.setdefault("unmask_ip", False)
        settings["unmask_ip"] = bool(settings.get("unmask_ip"))
        settings["fields"] = resolve_fields(settings.get("fields"))
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy(self.data)

    def get_cookie(self) -> dict | None:
        with self._lock:
            return deepcopy(self.data["cookie"]) if self.data.get("cookie") else None

    def set_cookie(self, name: str, cookie: str) -> dict:
        item = self.data.get("cookie") or {}
        item.update({
            "id": item.get("id") or new_id(),
            "name": name or item.get("name") or "账号",
            "cookie": cookie,
            "ok": None,
            "message": "",
            "updated": _now(),
        })
        with self._lock:
            self.data["cookie"] = item
            self._save()
            return deepcopy(item)

    def patch_cookie(self, **fields) -> dict | None:
        with self._lock:
            item = self.data.get("cookie")
            if not item:
                return None
            for key, value in fields.items():
                item[key] = value
            item["updated"] = _now()
            self._save()
            return deepcopy(item)

    def delete_cookie(self) -> bool:
        with self._lock:
            if not self.data.get("cookie"):
                return False
            self.data["cookie"] = None
            self._save()
            return True

    def mark_cookie(self, ok: bool, message: str = "", extra: dict | None = None) -> None:
        with self._lock:
            item = self.data.get("cookie")
            if not item:
                return
            item["ok"] = ok
            item["message"] = message
            item["updated"] = _now()
            if extra:
                for key in ("username", "role", "month", "persistent", "api", "ban"):
                    if key in extra:
                        item[key] = extra[key]
                if extra.get("username") and (not item.get("name") or item.get("name") == "账号"):
                    item["name"] = extra["username"]
            self._save()

    def fields(self) -> list[dict]:
        with self._lock:
            return resolve_fields(self.data["settings"].get("fields"))

    def unmask_ip(self) -> bool:
        with self._lock:
            return bool(self.data["settings"].get("unmask_ip"))

    def set_fields(self, fields, unmask_ip=None) -> list[dict]:
        resolved = resolve_fields(fields)
        with self._lock:
            self.data["settings"]["fields"] = resolved
            if unmask_ip is not None:
                self.data["settings"]["unmask_ip"] = bool(unmask_ip)
            self._save()
            return deepcopy(resolved)

    def add_history(self, query: str, size: int, count: int) -> None:
        item = {"query": query, "size": size, "count": count, "ts": _now()}
        with self._lock:
            history = [item, *[h for h in self.data["history"] if h.get("query") != query]]
            self.data["history"] = history[:40]
            self._save()


_instance: Store | None = None


def get_store() -> Store:
    global _instance
    if _instance is None:
        _instance = Store(CONFIG)
    return _instance


def public_account(item: dict | None) -> dict | None:
    if not item:
        return None
    raw = item.get("cookie") or ""
    preview = raw[:18] + "…" if len(raw) > 18 else raw
    return {
        "id": item["id"],
        "name": item.get("name") or "",
        "ok": item.get("ok"),
        "message": item.get("message") or "",
        "preview": preview,
        "updated": item.get("updated") or "",
        "username": item.get("username") or "",
        "role": item.get("role") or "",
        "month": item.get("month"),
        "persistent": item.get("persistent"),
        "api": item.get("api"),
        "ban": item.get("ban") or "",
    }
