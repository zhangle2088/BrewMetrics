"""数据规范（canonical schema）、规范化迁移与校验

规范约定
--------
- ``metadata.date``          必须为 ``"YYYY-MM-DD"`` 字符串
- ``metadata.batch_id``      字符串，全局唯一
- ``ingredients.malts``      可选；每条 ``{name, amount, potential_extract}``。
                             若全部条目都带 ``potential_extract``，则综合浸出率按重量
                             加权求得；否则回退到 ``ingredients.potential_extract``
- ``mash.process_logs``      统一为 ``{time_min, ph?, gravity?, note?}``
    * ``time_min`` 为距糖化开始的分钟数；无法解析的时钟时间保留在 ``time`` 字段
    * 仅保留有值的键，``None`` 字段一律省略
- ``mash.ph_readings``       已废弃，迁移时合并进 ``process_logs``
- ``measurements.<stage>``   ``stage`` ∈ {pre_sparge, pre_boil, post_boil, final}
"""

from __future__ import annotations

import copy
import re
from typing import Any, Optional

STAGES = {
    "pre_sparge": "洗糟前",
    "pre_boil": "熬煮前",
    "post_boil": "熬煮后",
    "final": "发酵结束",
}

# 无法解析为分钟数时保留原始写法的键名
_RAW_TIME_KEY = "time"

_ZERO_KEYWORDS = {"start", "初始", "开始", "begin", "起始", "0"}
_MIN_RE = re.compile(r"^(\d+)\s*(?:min|mins|分钟)$", re.IGNORECASE)


# ── 基础解析 ──────────────────────────────────────────────────────────────


def parse_time_min(value: Any) -> Optional[int]:
    """把各种时间写法归一为「距糖化开始分钟数」，无法解析返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in _ZERO_KEYWORDS:
        return 0
    match = _MIN_RE.match(text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    # 时钟时间（如 09:30）无法定位到糖化分钟数
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── 规范化 ────────────────────────────────────────────────────────────────


def normalize_process_logs(
    logs: Optional[list], ph_readings: Optional[list] = None
) -> list:
    """统一 process_logs，并把旧的 ph_readings 合并进来。"""
    entries: list = []
    for raw in logs or []:
        if not isinstance(raw, dict):
            continue
        entry: dict = {}
        time_min = parse_time_min(raw.get("time_min", raw.get(_RAW_TIME_KEY)))
        if time_min is not None:
            entry["time_min"] = time_min
        elif raw.get(_RAW_TIME_KEY) is not None:
            entry[_RAW_TIME_KEY] = str(raw[_RAW_TIME_KEY])
        ph = _to_float(raw.get("ph"))
        gravity = _to_float(raw.get("gravity"))
        if ph is not None:
            entry["ph"] = ph
        if gravity is not None:
            entry["gravity"] = gravity
        if raw.get("note"):
            entry["note"] = raw["note"]
        entries.append(entry)

    # 合并 ph_readings：按 time_min 对齐，对不上的补一条
    for raw in ph_readings or []:
        if not isinstance(raw, dict):
            continue
        ph = _to_float(raw.get("value", raw.get("ph")))
        if ph is None:
            continue
        time_min = parse_time_min(raw.get(_RAW_TIME_KEY))
        merged = False
        if time_min is not None:
            for entry in entries:
                if entry.get("time_min") == time_min and "ph" not in entry:
                    entry["ph"] = ph
                    merged = True
                    break
        if not merged:
            entry = {}
            if time_min is not None:
                entry["time_min"] = time_min
            elif raw.get(_RAW_TIME_KEY) is not None:
                entry[_RAW_TIME_KEY] = str(raw[_RAW_TIME_KEY])
            entry["ph"] = ph
            _insert_by_time(entries, entry)

    return entries


def _insert_by_time(entries: list, entry: dict) -> None:
    """按 time_min 把新条目插入到保持原始书写顺序的列表中。

    已存在的条目维持原序（人工记录本身即按时间排列），仅对新增条目定位插入点。
    """
    time_min = entry.get("time_min")
    if time_min is None:
        entries.append(entry)
        return
    for idx, existing in enumerate(entries):
        existing_time = existing.get("time_min")
        if existing_time is not None and existing_time > time_min:
            entries.insert(idx, entry)
            return
    entries.append(entry)


def normalize_record(record: dict) -> tuple:
    """返回 (规范化后的副本, 变更说明列表)。幂等：已规范的记录不产生变更。"""
    rec = copy.deepcopy(record)
    changes: list = []

    metadata = rec.setdefault("metadata", {})
    batch_id = metadata.get("batch_id")
    if batch_id is not None and not isinstance(batch_id, str):
        metadata["batch_id"] = str(batch_id)
        changes.append("metadata.batch_id 规范为字符串")
    date_val = metadata.get("date")
    if date_val is not None and not isinstance(date_val, str):
        metadata["date"] = str(date_val)
        changes.append("metadata.date 规范为字符串")

    mash = rec.get("mash")
    if isinstance(mash, dict):
        logs = mash.get("process_logs")
        ph_readings = mash.get("ph_readings")
        if logs is not None or ph_readings is not None:
            new_logs = normalize_process_logs(logs, ph_readings)
            if new_logs != logs:
                mash["process_logs"] = new_logs
                changes.append("process_logs 规范化为 time_min/ph/gravity")
        if ph_readings is not None:
            mash.pop("ph_readings", None)
            changes.append("ph_readings 合并进 process_logs")

    return rec, changes


# ── 校验 ──────────────────────────────────────────────────────────────────


def validate_record(record: dict) -> list:
    """返回该批次的数据问题列表 [{level, field, message}]。"""
    issues: list = []

    def add(level, field, message):
        issues.append({"level": level, "field": field, "message": message})

    metadata = record.get("metadata") or {}
    if not metadata.get("batch_id"):
        add("error", "metadata.batch_id", "缺少批次号")
    if not metadata.get("date"):
        add("error", "metadata.date", "缺少日期")

    ingredients = record.get("ingredients") or {}
    if ingredients.get("total_malt_weight") is None:
        add("error", "ingredients.total_malt_weight", "缺少总麦芽重量")
    if ingredients.get("potential_extract") is None:
        add("warning", "ingredients.potential_extract", "缺少综合理论浸出率")

    mash = record.get("mash") or {}
    for key, label in (("strike_water", "糖化用水"), ("sparge_water", "洗糟水")):
        if mash.get(key) is None:
            add("warning", f"mash.{key}", f"缺少{label}")

    measurements = record.get("measurements") or {}
    for stage, label in STAGES.items():
        stage_data = measurements.get(stage) or {}
        if stage_data.get("gravity") is None:
            add("warning", f"measurements.{stage}.gravity", f"{label}缺少比重")
        if stage == "pre_sparge" and stage_data.get("gravity") is not None:
            if stage_data.get("volume") is None:
                add("info", f"measurements.{stage}.volume", f"{label}缺少体积（计算不受影响）")

    pre_boil_vol = (measurements.get("pre_boil") or {}).get("volume")
    post_boil_vol = (measurements.get("post_boil") or {}).get("volume")
    if pre_boil_vol is None or post_boil_vol is None:
        add("warning", "measurements", "熬煮前/后体积不全，无法计算蒸发量")

    for idx, entry in enumerate(mash.get("process_logs") or []):
        if not isinstance(entry, dict):
            add("warning", f"mash.process_logs[{idx}]", "日志条目不是对象")
            continue
        if entry.get("time_min") is None and entry.get(_RAW_TIME_KEY) is None:
            add("warning", f"mash.process_logs[{idx}]", "无法确定采样时间")

    return issues


def batch_signature(record: dict) -> tuple:
    """用于重复批次检测的指纹：配方 + 原料 + 用水 + 各阶段测量。"""
    metadata = record.get("metadata") or {}
    ingredients = record.get("ingredients") or {}
    mash = record.get("mash") or {}
    measurements = record.get("measurements") or {}

    parts = [
        metadata.get("recipe_name"),
        ingredients.get("total_malt_weight"),
        ingredients.get("potential_extract"),
        mash.get("strike_water"),
        mash.get("sparge_water"),
    ]
    for stage in STAGES:
        stage_data = measurements.get(stage) or {}
        parts += [stage_data.get("volume"), stage_data.get("gravity")]
    return tuple(parts)


def find_duplicate_batches(records: list) -> list:
    """返回疑似重复批次分组 [{batch_ids, reason}]。"""
    groups: dict = {}
    for record in records:
        groups.setdefault(batch_signature(record), []).append(
            (record.get("metadata") or {}).get("batch_id")
        )
    return [
        {"batch_ids": batch_ids, "reason": "配方与全部测量值完全一致"}
        for batch_ids in groups.values()
        if len(batch_ids) > 1
    ]
