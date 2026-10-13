from __future__ import annotations

import re

PROVINCES = (
    ("Beijing", "北京"),
    ("Tianjin", "天津"),
    ("Hebei", "河北"),
    ("Shanxi", "山西"),
    ("Nei Mongol", "内蒙古"),
    ("Liaoning", "辽宁"),
    ("Jilin", "吉林"),
    ("Heilongjiang", "黑龙江"),
    ("Shanghai", "上海"),
    ("Jiangsu", "江苏"),
    ("Zhejiang", "浙江"),
    ("Anhui", "安徽"),
    ("Fujian", "福建"),
    ("Jiangxi", "江西"),
    ("Shandong", "山东"),
    ("Henan", "河南"),
    ("Hubei", "湖北"),
    ("Hunan", "湖南"),
    ("Guangdong", "广东"),
    ("Guangxi", "广西"),
    ("Hainan", "海南"),
    ("Chongqing", "重庆"),
    ("Sichuan", "四川"),
    ("Guizhou", "贵州"),
    ("Yunnan", "云南"),
    ("Xizang", "西藏"),
    ("Shaanxi", "陕西"),
    ("Gansu", "甘肃"),
    ("Qinghai", "青海"),
    ("Ningxia", "宁夏"),
    ("Xinjiang", "新疆"),
    ("Taiwan", "台湾"),
    ("Hongkong", "香港"),
)

PROVINCE_MAP = {en: cn for en, cn in PROVINCES}


def has_province(query: str) -> bool:
    return bool(re.search(r"\bprovince(_cn|_en)?\s*:", query, re.I))


def has_country(query: str) -> bool:
    return bool(re.search(r"\bcountry(_cn|_en)?\s*:", query, re.I))


def _and(query: str, clause: str) -> str:
    q = query.strip()
    if not q:
        return clause
    if re.search(r"\bOR\b", q) and not (q.startswith("(") and q.endswith(")")):
        q = f"({q})"
    return f"{q} AND {clause}"


def with_china(query: str) -> str:
    if has_country(query):
        return query.strip()
    return _and(query, 'country_cn:"中国"')


def with_province(query: str, en: str) -> str:
    return _and(query, f'province:"{en}"')


def resolve_provinces(keys: list[str] | None) -> list[tuple[str, str]]:
    if not keys:
        return []
    out = []
    seen = set()
    for key in keys:
        en = str(key).strip()
        cn = PROVINCE_MAP.get(en)
        if not cn or en in seen:
            continue
        seen.add(en)
        out.append((en, cn))
    return out


def item_key(item: dict) -> str:
    rid = str(item.get("id") or "").strip()
    if rid:
        return rid
    return f"{item.get('ip')}:{item.get('port')}:{item.get('transport')}"
