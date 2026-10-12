from __future__ import annotations

import csv
import io
import json
from datetime import datetime

DENIED = {"暂无权限", "无权限"}

CATALOG = (
    ("ip", "IP", "ip"),
    ("port", "端口", "port"),
    ("transport", "传输", "transport"),
    ("service", "协议", "service.name"),
    ("version", "版本", "service.version"),
    ("domain", "域名", "domain"),
    ("hostname", "主机名", "hostname"),
    ("host", "站点", "service.http.host"),
    ("title", "标题", "service.http.title"),
    ("server", "Server", "service.http.server"),
    ("status_code", "状态码", "service.http.status_code"),
    ("x_powered_by", "X-Powered-By", "service.http.x_powered_by"),
    ("country", "国家", "location.country_cn"),
    ("province", "省份", "location.province_cn"),
    ("city", "城市", "location.city_cn"),
    ("isp", "运营商", "location.isp"),
    ("scene", "场景", "location.scene_cn"),
    ("org", "组织", "org"),
    ("asn", "ASN", "asn"),
    ("asname", "AS 名称", "location.asname"),
    ("components", "组件", ""),
    ("sys_tag", "系统标签", ""),
    ("time", "时间", ""),
    ("url", "URL", ""),
    ("cert", "证书", "service.cert"),
    ("os", "操作系统", "os_name"),
)

DEFAULT_FIELDS = [
    "ip",
    "port",
    "transport",
    "service",
    "domain",
    "title",
    "components",
    "country",
    "province",
    "city",
    "isp",
    "org",
    "asn",
    "time",
]

CATALOG_MAP = {key: {"id": key, "label": label, "path": path} for key, label, path in CATALOG}


def nested(item: dict, path: str):
    if not path:
        return ""
    value = item
    for part in path.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(part)
        if value is None:
            return ""
    return value


def clean(value) -> str:
    if value is None or value is False:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [clean(v) for v in value]
        return " / ".join(p for p in parts if p)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    if text in DENIED:
        return ""
    return text


def fmt_time(raw) -> str:
    text = clean(raw)
    if not text:
        return ""
    return text.replace("T", " ").replace("Z", "").split(".")[0]


def is_ip(text: str) -> bool:
    if not text or text in DENIED or "*" in text:
        return False
    if ":" in text:
        return all(c in "0123456789abcdefABCDEF:." for c in text)
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def ip_from_id(item: dict) -> str:
    rid = str(item.get("id") or "").strip()
    if not rid:
        return ""
    parts = rid.rsplit("_", 2)
    if len(parts) != 3:
        return ""
    candidate = parts[0]
    return candidate if is_ip(candidate) else ""


def display_ip(item: dict, unmask: bool = False) -> str:
    if unmask:
        real = ip_from_id(item)
        if real:
            return real
    return clean(item.get("ip"))


def item_url(item: dict, unmask: bool = False) -> str:
    service = item.get("service") or {}
    http = service.get("http") if isinstance(service, dict) else {}
    http = http if isinstance(http, dict) else {}
    name = str(service.get("name") or "").lower() if isinstance(service, dict) else ""
    ip = display_ip(item, unmask)
    host = http.get("host") or item.get("domain") or ip or ""
    port = item.get("port") or ""
    if name in ("http/ssl", "https", "tls", "ssl") or "https" in name:
        scheme = "https"
    elif "http" in name:
        scheme = "http"
    else:
        return f"{ip}:{port}" if ip and port else str(ip or "")
    if not host:
        return f"{ip}:{port}" if ip and port else str(ip or "")
    if (scheme == "https" and port in (443, "443")) or (scheme == "http" and port in (80, "80")):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def components_of(item: dict) -> str:
    names = []
    for row in item.get("components") or []:
        if not isinstance(row, dict):
            continue
        name = clean(row.get("product_name_cn") or row.get("product_name_en"))
        if name and name not in names:
            names.append(name)
    return " / ".join(names)


def resolve_fields(raw) -> list[dict]:
    if not raw:
        raw = DEFAULT_FIELDS
    out = []
    seen = set()
    for item in raw:
        if isinstance(item, str):
            spec = CATALOG_MAP.get(item)
            if not spec:
                continue
            field = dict(spec)
        elif isinstance(item, dict):
            path = str(item.get("path") or "").strip()
            fid = str(item.get("id") or "").strip()
            if fid in CATALOG_MAP and not path:
                field = dict(CATALOG_MAP[fid])
            else:
                if not path:
                    continue
                field = {
                    "id": fid or path,
                    "label": str(item.get("label") or path).strip() or path,
                    "path": path,
                }
        else:
            continue
        if field["id"] in seen:
            continue
        seen.add(field["id"])
        out.append(field)
    return out or [dict(CATALOG_MAP[k]) for k in DEFAULT_FIELDS]


def extract_field(item: dict, field: dict, unmask_ip: bool = False) -> str:
    fid = field.get("id") or ""
    if fid == "ip":
        return display_ip(item, unmask_ip)
    if fid == "components":
        return components_of(item)
    if fid == "sys_tag":
        return clean(item.get("sys_tag"))
    if fid == "time":
        return fmt_time(item.get("time"))
    if fid == "url":
        return item_url(item, unmask_ip)
    if fid == "title":
        return clean(nested(item, "service.http.title")).replace("\n", " ")
    path = field.get("path") or (CATALOG_MAP.get(fid) or {}).get("path") or ""
    return clean(nested(item, path))


def project(item: dict, fields=None, unmask_ip: bool = False) -> dict:
    cols = resolve_fields(fields)
    row = {}
    for field in cols:
        row[field["id"]] = extract_field(item, field, unmask_ip)
    return row


def stats(rows: list[dict]) -> dict:
    ips = {row.get("ip") for row in rows if row.get("ip")}
    ports = {str(row.get("port")) for row in rows if row.get("port") not in ("", None)}
    countries = {row.get("country") for row in rows if row.get("country")}
    return {
        "count": len(rows),
        "ips": len(ips),
        "ports": len(ports),
        "countries": len(countries),
    }


def filename(fmt: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = {"json": "json", "csv": "csv", "url": "txt", "ip": "txt", "host": "txt", "domain": "txt"}.get(fmt, "txt")
    return f"quake_{fmt}_{stamp}.{ext}"


def render(data: list[dict], fmt: str, fields=None, unmask_ip: bool = False) -> tuple[str, str, str]:
    fmt = fmt.lower()
    name = filename(fmt)
    cols = resolve_fields(fields)
    if fmt == "json":
        payload = data
        if unmask_ip:
            payload = []
            for item in data:
                row = dict(item)
                real = ip_from_id(item)
                if real:
                    row["ip"] = real
                payload.append(row)
        body = json.dumps({"code": 0, "data": payload, "count": len(payload)}, ensure_ascii=False, indent=2)
        return name, "application/json; charset=utf-8", body
    rows = [project(item, cols, unmask_ip) for item in data]
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([field["label"] for field in cols])
        for row in rows:
            writer.writerow([row.get(field["id"], "") for field in cols])
        return name, "text/csv; charset=utf-8", "\ufeff" + buf.getvalue()
    lines: list[str] = []
    if fmt == "url":
        lines = [item_url(item, unmask_ip) for item in data]
    elif fmt == "ip":
        lines = list(dict.fromkeys(display_ip(item, unmask_ip) for item in data if display_ip(item, unmask_ip)))
    elif fmt == "host":
        lines = [
            f"{display_ip(item, unmask_ip)}:{item.get('port')}"
            for item in data
            if display_ip(item, unmask_ip) and item.get("port") not in ("", None)
        ]
    elif fmt == "domain":
        lines = list(dict.fromkeys(item.get("domain") for item in data if item.get("domain")))
    else:
        raise ValueError("不支持的导出格式")
    body = "\n".join(line for line in lines if line) + ("\n" if lines else "")
    return name, "text/plain; charset=utf-8", body
