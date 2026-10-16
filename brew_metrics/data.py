"""YAML 加载/保存、CSV 读写、效率计算"""

from pathlib import Path
from typing import Optional

import yaml
import pandas as pd

from .calculations import (
    calculate_extraction_coefficient,
    calculate_trimmed_stats,
)

BREW_DATA_DIR = Path(__file__).parent.parent / "brew_data"


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
    data_dir: Path = None,
) -> dict:
    """创建新酿造记录并保存为 YAML"""
    data_dir = data_dir or BREW_DATA_DIR
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

    filename = date.replace("-", "") + ".yaml"
    path = data_dir / filename
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

    process_logs = mash.get("process_logs", [])
    final_ph = None
    if process_logs:
        final_ph = process_logs[-1].get("ph")

    result = {
        "date": metadata.get("date"),
        "recipe_name": metadata.get("recipe_name"),
        "batch_id": metadata.get("batch_id"),
        "total_malt_weight": ingredients.get("total_malt_weight"),
        "potential_extract": ingredients.get("potential_extract"),
        "notes": ingredients.get("notes", ""),
        "strike_water": mash.get("strike_water"),
        "water_grain_ratio": mash.get("water_grain_ratio"),
        "sparge_water": mash.get("sparge_water"),
        "final_ph": final_ph,
        "target_temperature": mash.get("target_temperature"),
    }

    total_malt = ingredients.get("total_malt_weight")
    potential = ingredients.get("potential_extract")
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

    return result


def build_efficiency_table(data_dir: Path = None) -> pd.DataFrame:
    """构建效率汇总表"""
    records = load_brew_records(data_dir)
    all_efficiencies = [calculate_stage_efficiencies(r) for r in records]
    return pd.DataFrame(all_efficiencies)


def build_stats_table(df: pd.DataFrame) -> list:
    """计算各阶段修剪后统计量"""
    stages = [
        ("洗糟前提取系数", "pre_sparge_coefficient"),
        ("洗糟后提取系数", "post_sparge_coefficient"),
        ("谷物吸收率", "grain_absorption_rate"),
        ("熬煮后效率", "post_boil_efficiency"),
        ("熬煮蒸发量", "boil_off"),
    ]

    stats_rows = []
    summary_metrics = {}
    for stage_name, col_name in stages:
        valid_data = df[col_name].dropna()
        trimmed_mean, trimmed_std = calculate_trimmed_stats(df[col_name])

        if trimmed_mean is not None:
            # CSV 列名映射
            csv_key = col_name if col_name != "boil_off" else "boil_off_volume"
            summary_metrics[csv_key] = trimmed_mean

        stats_rows.append(
            {
                "阶段": stage_name,
                "修剪后平均值": trimmed_mean,
                "修剪后标准差": trimmed_std,
                "原始平均值": float(valid_data.mean()) if len(valid_data) > 0 else None,
                "最小值": float(valid_data.min()) if len(valid_data) > 0 else None,
                "最大值": float(valid_data.max()) if len(valid_data) > 0 else None,
                "样本数": len(valid_data),
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
