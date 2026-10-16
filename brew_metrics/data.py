"""YAML 加载/保存、CSV 读写、效率计算"""

from pathlib import Path
from typing import Optional

import yaml
import pandas as pd

from . import ingredients as ingredients_db
from .calculations import (
    calculate_actual_extract,
    calculate_extraction_coefficient,
    calculate_robust_stats,
    effective_potential_extract,
    explain_potential_extract,
)
from .schema import find_duplicate_batches, normalize_record, validate_record

BREW_DATA_DIR = Path(__file__).parent.parent / "brew_data"


def _resolve_malt_rate(name, supplier=None):
    """从本地原料库解析麦芽「原样细粉浸出率」，未匹配返回 None。"""
    return ingredients_db.resolve_extract_rate(name, supplier)


def find_batch(batch_id: str, data_dir: Path = None) -> Optional[Path]:
    """按 batch_id 查找 YAML 文件"""
    data_dir = data_dir or BREW_DATA_DIR
    for yaml_file in data_dir.glob("*.yaml"):
        with open(yaml_file, "r", encoding="utf-8") as f:
            record = yaml.safe_load(f)
            if record.get("metadata", {}).get("batch_id") == batch_id:
                return yaml_file
    return None


def load_brew_records(data_dir: Path = None) -> list:
    """加载所有酿造记录 YAML 文件"""
    data_dir = data_dir or BREW_DATA_DIR
    records = []
    for yaml_file in sorted(data_dir.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            records.append(yaml.safe_load(f))
    return records


def load_brew_records_with_paths(data_dir: Path = None) -> list:
    """加载所有记录，返回 [(path, record)]"""
    data_dir = data_dir or BREW_DATA_DIR
    pairs = []
    for yaml_file in sorted(data_dir.glob("*.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            pairs.append((yaml_file, yaml.safe_load(f)))
    return pairs


def save_brew_record(record: dict, path: Path):
    """保存酿造记录到 YAML 文件"""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(record, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def create_new_record(
    date: str,
    recipe: str,
    batch_id: str,
    total_malt_weight: float,
    potential_extract: float,
    strike_water: float,
    water_grain_ratio: float,
    target_temperature: float,
    sparge_water: float,
    force: bool = False,
    data_dir: Path = None,
) -> dict:
    """创建新酿造记录并保存为 YAML。

    文件名以 batch_id 命名（全局唯一）；若同名文件已存在则报错，
    避免同一天多批次因日期同名而互相覆盖。``force=True`` 可强制覆盖。
    """
    data_dir = data_dir or BREW_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    # 唯一性检查：文件名冲突，或 batch_id 已存在于其它文件
    existing = find_batch(batch_id, data_dir)
    if existing is not None and not force:
        raise FileExistsError(f"批次 {batch_id} 已存在：{existing}")

    record = {
        "metadata": {
            "date": date,
            "recipe_name": recipe,
            "batch_id": batch_id,
        },
        "units": {
            "weight": "kg",
            "volume": "L",
            "temperature": "C",
            "gravity": "SG",
        },
        "ingredients": {
            "total_malt_weight": total_malt_weight,
            "potential_extract": potential_extract,
        },
        "mash": {
            "strike_water": strike_water,
            "water_grain_ratio": water_grain_ratio,
            "target_temperature": target_temperature,
            "sparge_water": sparge_water,
            "process_logs": [],
        },
        "measurements": {
            "pre_sparge": {"volume": None, "gravity": None},
            "pre_boil": {"volume": None, "gravity": None},
            "post_boil": {"volume": None, "gravity": None},
            "final": {"volume": None, "gravity": None},
        },
    }

    filename = batch_id.strip() + ".yaml"
    path = data_dir / filename
    if path.exists() and not force and find_batch(batch_id, data_dir) is None:
        raise FileExistsError(f"文件已存在：{path}")
    save_brew_record(record, path)
    return {"file": str(path), "batch_id": batch_id}


def update_measurement(
    batch_id: str,
    stage: str,
    volume: Optional[float],
    gravity: Optional[float],
    data_dir: Path = None,
) -> dict:
    """更新指定阶段的测量数据"""
    data_dir = data_dir or BREW_DATA_DIR
    path = find_batch(batch_id, data_dir)
    if path is None:
        raise FileNotFoundError(f"批次 {batch_id} 不存在")

    with open(path, "r", encoding="utf-8") as f:
        record = yaml.safe_load(f)

    # CLI stage 名 (pre-sparge) 转 YAML 键名 (pre_sparge)
    yaml_stage = stage.replace("-", "_")

    if "measurements" not in record:
        record["measurements"] = {}
    if yaml_stage not in record["measurements"]:
        record["measurements"][yaml_stage] = {}

    updated_fields = []
    if volume is not None:
        record["measurements"][yaml_stage]["volume"] = volume
        updated_fields.append("volume")
    if gravity is not None:
        record["measurements"][yaml_stage]["gravity"] = gravity
        updated_fields.append("gravity")

    save_brew_record(record, path)
    return {"batch_id": batch_id, "stage": yaml_stage, "updated_fields": updated_fields}


def add_process_log(
    batch_id: str,
    time_min: int,
    ph: Optional[float],
    gravity: Optional[float],
    data_dir: Path = None,
) -> dict:
    """追加糖化过程日志"""
    data_dir = data_dir or BREW_DATA_DIR
    path = find_batch(batch_id, data_dir)
    if path is None:
        raise FileNotFoundError(f"批次 {batch_id} 不存在")

    with open(path, "r", encoding="utf-8") as f:
        record = yaml.safe_load(f)

    if "mash" not in record:
        record["mash"] = {}
    if "process_logs" not in record["mash"]:
        record["mash"]["process_logs"] = []

    log_entry = {"time_min": time_min}
    if ph is not None:
        log_entry["ph"] = ph
    if gravity is not None:
        log_entry["gravity"] = gravity

    record["mash"]["process_logs"].append(log_entry)
    save_brew_record(record, path)
    return {"batch_id": batch_id, "log_entry": log_entry}


def calculate_stage_efficiencies(record: dict) -> dict:
    """计算单个记录各阶段的提取系数/效率"""
    metadata = record.get("metadata", {})
    ingredients = record.get("ingredients", {})
    measurements = record.get("measurements", {})
    mash = record.get("mash", {})

    process_logs = mash.get("process_logs") or []
    # 取最后一次非空 PH（末条日志可能只有 note，无 PH）
    final_ph = None
    for entry in process_logs:
        if isinstance(entry, dict) and entry.get("ph") is not None:
            final_ph = entry["ph"]

    result = {
        "date": metadata.get("date"),
        "recipe_name": metadata.get("recipe_name"),
        "batch_id": metadata.get("batch_id"),
        "total_malt_weight": ingredients.get("total_malt_weight"),
        "potential_extract": effective_potential_extract(ingredients, _resolve_malt_rate),
        "potential_extract_breakdown": explain_potential_extract(
            ingredients, _resolve_malt_rate
        ),
        "notes": ingredients.get("notes", ""),
        "strike_water": mash.get("strike_water"),
        "water_grain_ratio": mash.get("water_grain_ratio"),
        "sparge_water": mash.get("sparge_water"),
        "final_ph": final_ph,
        "target_temperature": mash.get("target_temperature"),
    }

    total_malt = ingredients.get("total_malt_weight")
    potential = effective_potential_extract(ingredients, _resolve_malt_rate)
    strike_water = mash.get("strike_water")
    sparge_water = mash.get("sparge_water")

    # 洗糟前提取系数（使用糖化锅初始水量）
    pre_sparge = measurements.get("pre_sparge", {})
    result["pre_sparge_volume"] = pre_sparge.get("volume")
    result["pre_sparge_sg"] = pre_sparge.get("gravity")
    result["pre_sparge_coefficient"] = calculate_extraction_coefficient(
        total_malt, potential, strike_water, pre_sparge.get("gravity")
    )

    # 洗糟后提取系数（使用总水量）
    pre_boil = measurements.get("pre_boil", {})
    total_water_volume = None
    if strike_water is not None and sparge_water is not None:
        total_water_volume = strike_water + sparge_water

    result["pre_boil_volume"] = pre_boil.get("volume")
    result["pre_boil_sg"] = pre_boil.get("gravity")
    result["post_sparge_coefficient"] = calculate_extraction_coefficient(
        total_malt, potential, total_water_volume, pre_boil.get("gravity")
    )

    # 熬煮后效率（使用实际麦汁体积）
    post_boil = measurements.get("post_boil", {})
    result["post_boil_volume"] = post_boil.get("volume")
    result["post_boil_sg"] = post_boil.get("gravity")
    result["post_boil_efficiency"] = calculate_extraction_coefficient(
        total_malt, potential, post_boil.get("volume"), post_boil.get("gravity")
    )

    # 熬煮蒸发量
    if result["pre_boil_volume"] is not None and result["post_boil_volume"] is not None:
        result["boil_off"] = result["pre_boil_volume"] - result["post_boil_volume"]
    else:
        result["boil_off"] = None

    # 谷物吸收率
    if (
        strike_water is not None
        and sparge_water is not None
        and result["pre_boil_volume"] is not None
        and total_malt is not None
        and total_malt > 0
    ):
        result["grain_absorption_rate"] = (
            strike_water + sparge_water - result["pre_boil_volume"]
        ) / total_malt
    else:
        result["grain_absorption_rate"] = None

    # ── 糖量与守恒指标 ──────────────────────────────────────────────────
    # 三个阶段的绝对糖量。注意：洗糟后糖量用「实测煮前体积」（真实收集体积），
    # 不能用「糖化水+洗糟水」的总水量——麦床残留麦汁比重低于锅内，总水量口径会虚高。
    sugar_mash = (
        calculate_actual_extract(strike_water, pre_sparge.get("gravity"))
        if strike_water is not None and pre_sparge.get("gravity") is not None
        else None
    )
    sugar_kettle = (
        calculate_actual_extract(pre_boil.get("volume"), pre_boil.get("gravity"))
        if pre_boil.get("volume") is not None and pre_boil.get("gravity") is not None
        else None
    )
    sugar_boil = (
        calculate_actual_extract(post_boil.get("volume"), post_boil.get("gravity"))
        if post_boil.get("volume") is not None and post_boil.get("gravity") is not None
        else None
    )
    result["sugar_mash"] = sugar_mash
    result["sugar_kettle"] = sugar_kettle
    result["sugar_boil"] = sugar_boil

    # 同温端比值：洗糟回收率、麦床残留率。两端同温，共同温度偏差会约掉，
    # 因此比绝对糖量/效率更可靠，可在热端读数未做温补时仍纳入经验值。
    if sugar_mash and sugar_mash > 0 and sugar_kettle is not None:
        result["sparge_recovery"] = sugar_kettle / sugar_mash
        result["retention_ratio"] = (sugar_mash - sugar_kettle) / sugar_mash
    else:
        result["sparge_recovery"] = None
        result["retention_ratio"] = None

    # 跨温端比值：煮沸守恒（煮后糖量应 ≤ 煮前糖量）。煮后通常冷测、煮前热测，
    # 因此该比值 >1 只作提示，不作为硬剔除依据。
    if sugar_kettle and sugar_kettle > 0 and sugar_boil is not None:
        result["boil_ratio"] = sugar_boil / sugar_kettle
    else:
        result["boil_ratio"] = None

    # 资格判定：同温端守恒（残留率为负即物理不可能，视为记录错误而剔除）
    result["hot_consistent"] = (
        result["retention_ratio"] is not None
        and -0.02 <= result["retention_ratio"] <= 0.30
    )
    result["boil_consistent"] = (
        result["boil_ratio"] is not None and result["boil_ratio"] <= 1.02
    )
    result["eligible"] = bool(result["hot_consistent"])

    return result


def build_efficiency_table(data_dir: Path = None) -> pd.DataFrame:
    """构建效率汇总表"""
    records = load_brew_records(data_dir)
    all_efficiencies = [calculate_stage_efficiencies(r) for r in records]
    return pd.DataFrame(all_efficiencies)


"""各过程量的资格口径。

- gate 为该量依赖的资格列：热端/比值量只纳入 ``hot_consistent`` 批次，
  避免被同温端不自洽（残留率为负）的记录污染；
- gate 为 ``None`` 表示该量不依赖比重（体积量），纳入全部有值批次；
- 经验值取**中位数**（对残余离群点稳健），并报告 MAD 与纳入/剔除数。
"""
STAGE_METRICS = [
    ("洗糟前提取系数", "pre_sparge_coefficient", "hot_consistent"),
    ("洗糟回收率", "sparge_recovery", "hot_consistent"),
    ("麦床残留率", "retention_ratio", "hot_consistent"),
    ("谷物吸收率", "grain_absorption_rate", None),
    ("熬煮后效率", "post_boil_efficiency", None),
    ("熬煮蒸发量", "boil_off", None),
]

# CSV 列名映射（内部列名 → 导出列名）
CSV_KEY = {"boil_off": "boil_off_volume"}


def build_stats_table(df: pd.DataFrame) -> tuple:
    """按资格口径计算各过程量的稳健经验值。"""
    stats_rows = []
    summary_metrics = {}
    total = len(df)

    for stage_name, col_name, gate in STAGE_METRICS:
        if col_name not in df.columns:
            continue

        sub = df
        if gate is not None and gate in df.columns:
            sub = df[df[gate].fillna(False).astype(bool)]

        series = sub[col_name]
        valid_data = series.dropna()
        stat = calculate_robust_stats(series)

        if stat["median"] is not None:
            summary_metrics[CSV_KEY.get(col_name, col_name)] = stat["median"]

        stats_rows.append(
            {
                "阶段": stage_name,
                "经验值(中位)": stat["median"],
                "MAD": stat["mad"],
                "截尾均值": stat["trimmed_mean"],
                "最小值": float(valid_data.min()) if len(valid_data) > 0 else None,
                "最大值": float(valid_data.max()) if len(valid_data) > 0 else None,
                "纳入": stat["n"],
                "剔除": total - stat["n"],
            }
        )

    return stats_rows, summary_metrics


def save_summary_csv(metrics: dict, output_path: str):
    """保存修剪后平均值到 CSV"""
    df = pd.DataFrame([metrics])
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


def load_summary_metrics(csv_path: str = None) -> dict:
    """从 CSV 加载历史效率数据"""
    csv_path = csv_path or str(BREW_DATA_DIR.parent / "brewing_metrics_summary.csv")
    df = pd.read_csv(csv_path)
    return df.iloc[0].to_dict()


# ── 校验 / 迁移 ────────────────────────────────────────────────────────────


def validate_records(data_dir: Path = None) -> dict:
    """校验所有批次的数据规范，并检测疑似重复批次。"""
    data_dir = data_dir or BREW_DATA_DIR
    batches = []
    records = []
    for path, record in load_brew_records_with_paths(data_dir):
        metadata = record.get("metadata") or {}
        records.append(record)
        batches.append(
            {
                "file": path.name,
                "batch_id": metadata.get("batch_id"),
                "issues": validate_record(record),
            }
        )
    duplicates = find_duplicate_batches(records)
    return {"batches": batches, "duplicates": duplicates}


def migrate_records(data_dir: Path = None, write: bool = False) -> list:
    """把数据文件规范化为 canonical schema。

    - ``process_logs`` 统一为 ``time_min/ph/gravity``，合并 ``ph_readings``
    - ``date``/``batch_id`` 规范为字符串
    - 文件名统一为 ``<batch_id>.yaml``

    ``write=False``（默认）仅做演练，返回将要发生的变更。
    """
    data_dir = data_dir or BREW_DATA_DIR
    results = []
    for path, record in load_brew_records_with_paths(data_dir):
        new_record, changes = normalize_record(record)
        batch_id = (new_record.get("metadata") or {}).get("batch_id")

        target = data_dir / f"{batch_id}.yaml" if batch_id else path
        renamed = target != path
        if renamed and target.exists():
            changes = [f"目标文件已存在，跳过重命名：{target.name}"] + changes
            target = path
            renamed = False

        if renamed:
            changes = [f"重命名 {path.name} -> {target.name}"] + changes

        item = {
            "file": path.name,
            "batch_id": batch_id,
            "target_file": target.name,
            "changes": changes,
        }
        results.append(item)

        if write and changes:
            save_brew_record(new_record, target)
            if renamed:
                path.unlink()
    return results
