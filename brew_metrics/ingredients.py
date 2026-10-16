"""本地原料库（由 Brewtarget ``default_db`` 生成）查询与匹配。

数据文件 ``ingredients_db.json`` 由 ``brew_metrics/ingredients_db.json`` 提供，
字段 ``potential_extract_asis = fine_yield_pct/100 * (1 - moisture/100)``，
即「原样细粉浸出率」——与 BrewMetrics 分母里用的麦芽**原样重量**口径一致。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent / "ingredients_db.json"


@lru_cache(maxsize=1)
def load_db() -> dict:
    if not _DB_PATH.exists():
        return {"fermentables": {}}
    with open(_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _index() -> dict:
    return load_db().get("fermentables", {})


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _strip_supplier_prefix(name: str) -> str:
    s = name.strip().lower()
    for sep in (" - ", " – ", "-"):
        if sep in s:
            return s.split(sep, 1)[1].strip()
    return s


def lookup_malt(name: str, supplier: Optional[str] = None) -> Optional[dict]:
    """按名称（可带供应商）在本地原料库中查找，返回条目或 ``None``。

    匹配优先级：精确名 → 去供应商前缀 → 供应商+名称 → token 相似度。
    token 相似度阈值取得较高，避免"Pilsner"这类泛名误配到不相关条目。
    """
    if not name:
        return None
    idx = _index()
    if not idx:
        return None

    key = name.strip().lower()
    cand = _strip_supplier_prefix(name)

    if key in idx:
        return idx[key]
    if cand in idx:
        return idx[cand]

    sup = (supplier or "").strip().lower()
    if sup:
        for e in idx.values():
            esup = (e.get("supplier") or "").lower()
            ename = e["name"].lower()
            if esup == sup and (cand == ename or cand == _strip_supplier_prefix(ename)):
                return e

    t = _tokens(cand)
    if not t:
        return None
    best, best_score = None, 0.0
    for e in idx.values():
        ename = e["name"].lower()
        et = _tokens(ename)
        if not et:
            continue
        inter = len(t & et)
        if inter == 0:
            continue
        score = inter / len(t | et)
        # 名称整体出现在库条目里 → 明显更强
        if cand and cand in ename:
            score += 0.6
        if sup and (e.get("supplier") or "").lower() == sup:
            score += 0.3
        if score > best_score:
            best, best_score = e, score
    # 阈值：要求较高置信度，否则宁可不匹配（回退到记录值）
    if best is not None and best_score >= 0.5:
        return best
    return None


def resolve_extract_rate(name: str, supplier: Optional[str] = None) -> Optional[float]:
    """返回该麦芽的「原样细粉浸出率」，未匹配到返回 ``None``。"""
    entry = lookup_malt(name, supplier)
    if entry is None:
        return None
    return entry.get("potential_extract_asis")


def format_match(name: str, supplier: Optional[str] = None) -> str:
    """调试用：返回匹配结果的可读描述。"""
    entry = lookup_malt(name, supplier)
    if entry is None:
        return f"{name}: 未匹配"
    return (
        f"{name} -> {entry['name']} "
        f"(as-is {entry.get('potential_extract_asis')}, moisture {entry.get('moisture_pct')}%)"
    )
