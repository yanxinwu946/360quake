from __future__ import annotations

import argparse
import asyncio
from typing import Annotated

import httpx
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from src.export import clean, item_url, nested
from src.jobs import Job
from src.quake import check_cookie, normalize_cookie, normalize_query, run_search
from src.regions import PROVINCES
from src.store import get_store

mcp = FastMCP(
    name="360Quake",
    instructions=(
        "360 Quake 网页检索。未登录先 login。"
        "search 用官方 Query String，单次最多 100 条；split=true 按中国分省合并。"
        "中文或空格加双引号，AND/OR/NOT 大写。"
        '例：domain:"x.com"  port:443 AND country_cn:"中国"  title:"登录"  app:"nginx"'
    ),
    version="2.0.0",
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=45.0, trust_env=False, follow_redirects=False)


def _hit(item: dict, unmask: bool) -> dict:
    url = item_url(item, unmask)
    title = clean(nested(item, "service.http.title")).replace("\n", " ")
    if len(title) > 80:
        title = title[:80].rstrip() + "…"
    org = clean(item.get("org"))
    hit = {}
    if url:
        hit["url"] = url
    if title:
        hit["title"] = title
    if org:
        hit["org"] = org
    return hit


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
)
def status() -> dict:
    """当前是否已登录。"""
    item = get_store().get_cookie()
    if not item:
        return {"ok": False}
    return {
        "ok": bool(item.get("ok")),
        "user": item.get("username") or item.get("name") or "",
    }


@mcp.tool(
    annotations=ToolAnnotations(idempotentHint=True, openWorldHint=True),
)
async def login(cookie: str) -> dict:
    """设置 360 Quake Cookie 并校验。从 quake.360.net 请求头复制。"""
    raw = normalize_cookie(cookie)
    if not raw or "=" not in raw:
        raise ToolError("Cookie 格式无效")
    store = get_store()
    store.set_cookie("", raw)
    async with _client() as client:
        try:
            info = await check_cookie(client, raw)
        except Exception as exc:
            store.mark_cookie(False, str(exc))
            raise ToolError(str(exc)) from None
    store.mark_cookie(True, info["message"], extra=info)
    return {"ok": True, "user": info.get("username") or ""}


@mcp.tool(
    timeout=180.0,
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
async def search(
    query: str,
    ctx: Context,
    size: Annotated[int, Field(ge=1, le=100)] = 50,
    split: Annotated[bool, Field(description="先限定中国，再按省分别检索后合并")] = False,
) -> dict:
    """检索资产，返回 url、标题、组织。"""
    store = get_store()
    cookie = store.get_cookie()
    if not cookie:
        raise ToolError("请先 login")
    text = normalize_query(query)
    if not text:
        raise ToolError("请输入检索语句")
    job = Job(query=text, size=size, regions=[en for en, _cn in PROVINCES] if split else [])
    unmask = store.unmask_ip()

    async with _client() as client:
        task = asyncio.create_task(run_search(job, client, cookie))
        while not task.done():
            await ctx.report_progress(progress=job.page, total=job.pages or 1)
            await asyncio.sleep(0.35)
        try:
            await task
        except Exception as exc:
            raise ToolError(str(exc)) from None

    if job.status != "done":
        raise ToolError(job.error or "检索失败")
    hits = [hit for item in job.data if (hit := _hit(item, unmask))]
    store.add_history(job.query, job.size, job.count)
    return {"n": len(hits), "hits": hits}


def run() -> None:
    parser = argparse.ArgumentParser(prog="quake-mcp")
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args, _unknown = parser.parse_known_args()
    if args.http:
        mcp.run(transport="http", host=args.host, port=args.port)
        return
    mcp.run()


if __name__ == "__main__":
    run()
