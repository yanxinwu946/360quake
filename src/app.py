from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.export import CATALOG, item_url, project, render, stats
from src.jobs import Job, JobHub
from src.paths import CONFIG, WEB
from src.quake import check_cookie, normalize_cookie, normalize_query, run_search
from src.regions import PROVINCES
from src.store import Store


class CookieIn(BaseModel):
    name: str = ""
    cookie: str | None = None


class SearchIn(BaseModel):
    query: str
    size: int = Field(default=100, ge=1, le=100)
    split: bool = False


class FieldsIn(BaseModel):
    fields: list[str | dict]
    unmask_ip: bool | None = None


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = Store(CONFIG)
    app.state.jobs = JobHub()
    app.state.http = httpx.AsyncClient(timeout=45.0, trust_env=False, follow_redirects=False)
    yield
    await app.state.http.aclose()


app = FastAPI(title="360Quake", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


def store() -> Store:
    return app.state.store


def hub() -> JobHub:
    return app.state.jobs


def http() -> httpx.AsyncClient:
    return app.state.http


@app.get("/")
async def index():
    return Response((WEB / "index.html").read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")


@app.get("/api/state")
async def api_state():
    snap = store().snapshot()
    return {
        "account": public_account(snap.get("cookie")),
        "history": snap["history"],
        "settings": snap["settings"],
        "catalog": [{"id": key, "label": label, "path": path} for key, label, path in CATALOG],
        "provinces": [{"id": en, "label": cn} for en, cn in PROVINCES],
    }


@app.put("/api/account")
async def api_put_account(body: CookieIn):
    cookie = normalize_cookie(body.cookie or "")
    if not cookie or "=" not in cookie:
        raise HTTPException(400, "Cookie 格式无效")
    item = store().set_cookie(body.name.strip(), cookie)
    return public_account(item)


@app.patch("/api/account")
async def api_patch_account(body: CookieIn):
    fields = {}
    if body.name.strip():
        fields["name"] = body.name.strip()
    if body.cookie:
        cookie = normalize_cookie(body.cookie)
        if not cookie or "=" not in cookie:
            raise HTTPException(400, "Cookie 格式无效")
        fields["cookie"] = cookie
        fields["ok"] = None
        fields["message"] = ""
    if not fields:
        raise HTTPException(400, "没有需要更新的内容")
    item = store().patch_cookie(**fields)
    if not item:
        raise HTTPException(404, "请先添加账号")
    return public_account(item)


@app.delete("/api/account")
async def api_delete_account():
    if not store().delete_cookie():
        raise HTTPException(404, "请先添加账号")
    return {"ok": True}


@app.post("/api/account/check")
async def api_check_account():
    item = store().get_cookie()
    if not item:
        raise HTTPException(404, "请先添加账号")
    try:
        info = await check_cookie(http(), item["cookie"])
        store().mark_cookie(True, info["message"], extra=info)
        return {"ok": True, **info}
    except Exception as exc:
        store().mark_cookie(False, str(exc))
        raise HTTPException(400, str(exc))


@app.put("/api/fields")
async def api_put_fields(body: FieldsIn):
    fields = store().set_fields(body.fields, body.unmask_ip)
    return {"fields": fields, "unmask_ip": store().unmask_ip()}


@app.post("/api/search")
async def api_search(body: SearchIn):
    query = normalize_query(body.query)
    if not query:
        raise HTTPException(400, "请输入检索语句")
    cookie = store().get_cookie()
    if not cookie:
        raise HTTPException(400, "请先添加账号")
    regions = [en for en, _ in PROVINCES] if body.split else []
    job = hub().add(Job(query=query, size=body.size, regions=regions))

    async def runner():
        try:
            await run_search(job, http(), cookie)
            if job.status == "done":
                store().add_history(job.query, job.size, job.count)
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)

    job.task = asyncio.create_task(runner())
    return job.snapshot()


@app.get("/api/search/{job_id}")
async def api_job(job_id: str):
    job = hub().get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    payload = job.snapshot()
    if job.status == "done":
        rows = [project(item, store().fields(), store().unmask_ip()) for item in job.data]
        payload["stats"] = stats(rows)
    return payload


@app.get("/api/search/{job_id}/rows")
async def api_rows(job_id: str, offset: int = 0, limit: int = 20000):
    job = hub().get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    fields = store().fields()
    unmask = store().unmask_ip()
    rows = [
        {"_i": i, "_url": item_url(item, unmask), **project(item, fields, unmask)}
        for i, item in enumerate(job.data)
    ]
    return {
        "total": len(rows),
        "offset": offset,
        "rows": rows[offset : offset + limit],
        "stats": stats(rows),
        "fields": fields,
    }


@app.get("/api/search/{job_id}/item/{index}")
async def api_item(job_id: str, index: int):
    job = hub().get(job_id)
    if not job or index < 0 or index >= len(job.data):
        raise HTTPException(404, "记录不存在")
    return job.data[index]


@app.post("/api/search/{job_id}/cancel")
async def api_cancel(job_id: str):
    job = hub().get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    job.cancel.set()
    job.status = "cancelled"
    return job.snapshot()


@app.get("/api/search/{job_id}/stream")
async def api_stream(job_id: str):
    job = hub().get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")

    async def events():
        while True:
            payload = json.dumps(job.snapshot(), ensure_ascii=False)
            yield f"data: {payload}\n\n"
            if job.status in {"done", "error", "cancelled"}:
                break
            await asyncio.sleep(0.25)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/search/{job_id}/export")
async def api_export(job_id: str, fmt: str = "json"):
    job = hub().get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status != "done":
        raise HTTPException(400, "检索尚未完成")
    try:
        name, mime, body = render(job.data, fmt, store().fields(), store().unmask_ip())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return Response(
        content=body.encode("utf-8"),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def run() -> None:
    uvicorn.run("src.app:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
