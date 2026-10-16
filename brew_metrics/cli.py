"""Typer CLI 入口"""

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer

from . import data
from .calculations import calculate_recipe
from .display import (
    show_batch_detail,
    show_batch_list,
    show_efficiency_table,
    show_recipe_summary,
    show_stats_table,
    show_sugar_balance,
)

app = typer.Typer(help="BrewMetrics - 酿造效率分析工具")


class BrewEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, float) and math.isnan(obj):
            return None
        return super().default(obj)


def _sanitize(obj):
    """递归清理 NaN 为 None，date 转 string"""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _json_out(data):
    print(json.dumps({"status": "success", "data": _sanitize(data)}, cls=BrewEncoder, ensure_ascii=False, indent=2))


def _resolve_data_dir(data_dir: Optional[Path]) -> Path:
    return data_dir if data_dir is not None else data.BREW_DATA_DIR


# ── list ──────────────────────────────────────────────────────────────────


@app.command(name="list")
def list_cmd(
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="数据目录路径"),
):
    """显示所有酿造批次"""
    data_dir = _resolve_data_dir(data_dir)
    records = data.load_brew_records(data_dir)

    rows = []
    for record in records:
        metadata = record.get("metadata", {})
        ingredients = record.get("ingredients", {})
        mash = record.get("mash", {})
        process_logs = mash.get("process_logs", [])
        final_ph = None
        if process_logs:
            final_ph = process_logs[-1].get("ph")

        rows.append(
            {
                "date": metadata.get("date"),
                "recipe_name": metadata.get("recipe_name"),
                "batch_id": metadata.get("batch_id"),
                "total_malt_weight": ingredients.get("total_malt_weight"),
                "strike_water": mash.get("strike_water"),
                "water_grain_ratio": mash.get("water_grain_ratio"),
                "target_temperature": mash.get("target_temperature"),
                "final_ph": final_ph,
            }
        )

    if json_output:
        _json_out({"batches": rows})
    else:
        show_batch_list(rows)


# ── show ──────────────────────────────────────────────────────────────────


@app.command()
def show(
    batch_id: str = typer.Argument(help="批次号"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="数据目录路径"),
):
    """显示批次详情"""
    data_dir = _resolve_data_dir(data_dir)
    path = data.find_batch(batch_id, data_dir)
    if path is None:
        print(f"错误: 批次 {batch_id} 不存在", file=sys.stderr)
        raise typer.Exit(1)

    import yaml

    with open(path, "r", encoding="utf-8") as f:
        record = yaml.safe_load(f)

    efficiencies = data.calculate_stage_efficiencies(record)

    if json_output:
        _json_out({"record": record, "efficiencies": efficiencies})
    else:
        show_batch_detail(record, efficiencies)


# ── add ───────────────────────────────────────────────────────────────────


@app.command()
def add(
    date_val: str = typer.Option(..., "--date", help="酿造日期 (YYYY-MM-DD)"),
    recipe: str = typer.Option(..., "--recipe", help="配方名称"),
    batch_id: str = typer.Option(..., "--batch-id", help="批次号"),
    total_malt_weight: float = typer.Option(..., "--total-malt-weight", help="总麦芽重量 (kg)"),
    potential_extract: float = typer.Option(..., "--potential-extract", help="理论浸出率"),
    strike_water: float = typer.Option(..., "--strike-water", help="糖化用水量 (L)"),
    water_grain_ratio: float = typer.Option(..., "--water-grain-ratio", help="水料比"),
    target_temperature: float = typer.Option(..., "--target-temperature", help="目标糖化温度 (°C)"),
    sparge_water: float = typer.Option(..., "--sparge-water", help="洗糟水量 (L)"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="数据目录路径"),
):
    """创建新酿造记录"""
    data_dir = _resolve_data_dir(data_dir)
    result = data.create_new_record(
        date=date_val,
        recipe=recipe,
        batch_id=batch_id,
        total_malt_weight=total_malt_weight,
        potential_extract=potential_extract,
        strike_water=strike_water,
        water_grain_ratio=water_grain_ratio,
        target_temperature=target_temperature,
        sparge_water=sparge_water,
        data_dir=data_dir,
    )

    if json_output:
        _json_out(result)
    else:
        print(f"已创建: {result['file']}")
        print(f"批次号: {result['batch_id']}")


# ── record ────────────────────────────────────────────────────────────────


@app.command()
def record(
    batch_id: str = typer.Argument(help="批次号"),
    process_log: bool = typer.Option(False, "--process-log", help="追加糖化过程日志"),
    stage: Optional[str] = typer.Option(None, "--stage", help="阶段: pre-sparge, pre-boil, post-boil, final"),
    time_min: Optional[int] = typer.Option(None, "--time-min", help="糖化时间(分钟，配合 --process-log)"),
    ph: Optional[float] = typer.Option(None, "--ph", help="PH值"),
    gravity: Optional[float] = typer.Option(None, "--gravity", help="比重"),
    volume: Optional[float] = typer.Option(None, "--volume", help="体积(L)"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="数据目录路径"),
):
    """记录测量数据"""
    data_dir = _resolve_data_dir(data_dir)

    if process_log:
        if time_min is None:
            print("错误: --process-log 需要配合 --time-min", file=sys.stderr)
            raise typer.Exit(1)
        result = data.add_process_log(batch_id, time_min, ph, gravity, data_dir)
    elif stage is not None:
        result = data.update_measurement(batch_id, stage, volume, gravity, data_dir)
    else:
        print("错误: 请指定 --process-log 或 --stage", file=sys.stderr)
        raise typer.Exit(1)

    if json_output:
        _json_out(result)
    else:
        if process_log:
            print(f"已追加过程日志: {result['log_entry']}")
        else:
            print(f"已更新批次 {result['batch_id']} 的 {result['stage']} 阶段: {result['updated_fields']}")


# ── analyze ───────────────────────────────────────────────────────────────


@app.command()
def analyze(
    output: str = typer.Option("brewing_metrics_summary.csv", "--output", "-o", help="输出 CSV 路径"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="数据目录路径"),
):
    """分析所有批次的效率"""
    data_dir = _resolve_data_dir(data_dir)
    df = data.build_efficiency_table(data_dir)
    stats_rows, summary_metrics = data.build_stats_table(df)

    csv_exported = False
    if summary_metrics:
        data.save_summary_csv(summary_metrics, output)
        csv_exported = True

    if json_output:
        table_data = _sanitize(df.to_dict(orient="records"))
        _json_out(
            {
                "table": table_data,
                "stats": stats_rows,
                "csv_exported": csv_exported,
            }
        )
    else:
        show_efficiency_table(df)
        show_stats_table(stats_rows)
        if csv_exported:
            print(f"\n数据已导出到 {output}")


# ── design ────────────────────────────────────────────────────────────────


@app.command()
def design(
    volume: float = typer.Option(..., "--volume", help="目标煮沸后体积 (L)"),
    sg: float = typer.Option(..., "--sg", help="目标煮沸后比重"),
    potential_rate: float = typer.Option(0.78, "--potential-rate", help="理论浸出率"),
    water_grain_ratio: float = typer.Option(3.06, "--water-grain-ratio", help="水料比"),
    metrics: Optional[str] = typer.Option(None, "--metrics", help="效率 CSV 路径"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
):
    """配方设计"""
    metrics_data = data.load_summary_metrics(metrics)
    result = calculate_recipe(volume, sg, potential_rate, water_grain_ratio, metrics_data)

    if json_output:
        _json_out({"recipe": result, "sugar_balance": result["sugar_balance"]})
    else:
        show_recipe_summary(result)
        show_sugar_balance(result["sugar_balance"])
