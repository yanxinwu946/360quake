from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from src.regions import has_province, item_key, resolve_provinces, with_province

WEB_URL = "https://quake.360.net/api/search/query_string/quake_service"
USER_URL = "https://quake.360.net/api/user/info"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PAGE_SIZE = 100


class QuakeError(Exception):
    def __init__(self, message: str, code=None):
        super().__init__(message)
        self.code = code


def normalize_cookie(raw: str) -> str:
    text = raw.strip().replace("\r", "").replace("\n", "")
    if text.lower().startswith("cookie:"):
        text = text[7:].strip()
    return text


def normalize_query(raw: str) -> str:
    query = raw.strip()
    if query.startswith("服务数据 |"):
        query = query[len("服务数据 |"):].strip()
    if query and ":" not in query:
        return f'domain:"{query.strip().strip('"')}"'
    return query


def _headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Origin": "https://quake.360.net",
        "Referer": "https://quake.360.net/quake/search",
        "Cookie": cookie,
    }


def _payload(query: str, start: int, size: int) -> dict:
    return {
        "query": query,
        "size": min(size, PAGE_SIZE),
        "latest": True,
        "ignore_cache": False,
        "start": start,
        "device": {
            "device_type": "PC",
            "os": "Windows",
            "os_version": "10.0",
            "language": "zh_CN",
            "network": "3g",
            "browser_info": "Chrome（版本: 131.0.0.0  内核: Blink）",
            "user_agent": UA,
            "date": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        },
    }


def _parse_body(response: httpx.Response) -> dict:
    if response.status_code in (401, 403):
        raise QuakeError("Cookie 已失效", response.status_code)
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "html" in content_type or text[:20].lstrip().startswith("<"):
        raise QuakeError("Cookie 已失效或未登录")
    response.raise_for_status()
    body = response.json()
    code = body.get("code")
    if code not in (0, "0"):
        message = body.get("message") or f"查询失败 ({code})"
        if str(code) == "u3017" or "暂不支持该字段" in str(message):
            message = f"{message}。当前账号无该字段权限。"
        raise QuakeError(message, code)
    data = body.get("data") or []
    if not isinstance(data, list):
        data = []
    return {"data": data, "meta": body.get("meta") or {}}


async def search_page(
    client: httpx.AsyncClient,
    cookie: str,
    query: str,
    start: int,
    size: int,
) -> dict:
    response = await client.post(
        WEB_URL,
        headers=_headers(cookie),
        json=_payload(query, start, size),
    )
    return _parse_body(response)


def _parse_user(body: dict) -> dict:
    data = body.get("data") or {}
    user = data.get("user") or {}
    roles = data.get("role") or []
    role = ""
    if roles and isinstance(roles[0], dict):
        role = roles[0].get("fullname") or ""
    info = {
        "username": user.get("fullname") or user.get("username") or "",
        "role": role,
        "month": data.get("month_remaining_credit"),
        "persistent": data.get("persistent_credit") if data.get("persistent_credit") is not None else data.get("constant_credit"),
        "api": data.get("free_query_api_count"),
        "ban": data.get("ban_status") or "",
        "credit": data.get("credit"),
    }
    bits = [info["username"], info["role"]]
    if info["month"] is not None:
        bits.append(f"月度 {info['month']}")
    if info["persistent"] is not None:
        bits.append(f"长效 {info['persistent']}")
    if info["api"] is not None:
        bits.append(f"API {info['api']}")
    if info["ban"]:
        bits.append(info["ban"])
    info["message"] = " · ".join(x for x in bits if x)
    return info


async def check_cookie(client: httpx.AsyncClient, cookie: str) -> dict:
    response = await client.get(USER_URL, headers=_headers(cookie))
    if response.status_code in (401, 403):
        raise QuakeError("Cookie 已失效", response.status_code)
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "html" in content_type or text[:20].lstrip().startswith("<"):
        raise QuakeError("Cookie 已失效或未登录")
    response.raise_for_status()
    body = response.json()
    code = body.get("code")
    if code not in (0, "0"):
        raise QuakeError(body.get("message") or f"账号信息失败 ({code})", code)
    return _parse_user(body)


async def _search_once(client: httpx.AsyncClient, cookie: str, query: str, size: int) -> list[dict]:
    try:
        result = await search_page(client, cookie, query, 0, size)
        return result["data"][:size]
    except QuakeError as exc:
        if str(exc.code) != "q3005":
            raise
        await asyncio.sleep(1.6)
        result = await search_page(client, cookie, query, 0, size)
        return result["data"][:size]


async def run_search(job, client: httpx.AsyncClient, cookie: dict) -> None:
    size = min(job.size, PAGE_SIZE)
    regions = [] if has_province(job.query) else resolve_provinces(job.regions)
    queries = [(job.query, "")] if not regions else [(with_province(job.query, en), cn) for en, cn in regions]
    job.pages = len(queries)
    merged: list[dict] = []
    seen: set[str] = set()
    try:
        for index, (query, label) in enumerate(queries, start=1):
            if job.cancel.is_set():
                job.status = "cancelled"
                return
            job.using = label
            job.page = index
            try:
                rows = await _search_once(client, cookie["cookie"], query, size)
            except QuakeError as exc:
                if str(exc.code) in {"q3005"} and merged:
                    continue
                raise
            for item in rows:
                key = item_key(item)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
            job.data = merged
            job.count = len(merged)
            if index < len(queries):
                await asyncio.sleep(0.22)
        if job.cancel.is_set():
            job.status = "cancelled"
            return
        job.status = "done"
    except Exception as exc:
        if job.cancel.is_set():
            job.status = "cancelled"
            return
        job.status = "error"
        job.error = str(exc)
        raise
