"""Rich 终端表格渲染"""

import math

from rich.console import Console
from rich.table import Table

console = Console()


def _fmt(val, fmt=".2f"):
    """格式化数值，None/NaN 显示为 ---"""
    if val is None:
        return "---"
    if isinstance(val, float) and math.isnan(val):
        return "---"
    return format(val, fmt)


def show_batch_list(rows):
    """显示批次列表"""
    table = Table(title="酿造批次列表")
    table.add_column("日期")
    table.add_column("配方")
    table.add_column("批次号")
    table.add_column("麦芽(kg)", justify="right")
    table.add_column("糖化水(L)", justify="right")
    table.add_column("水料比", justify="right")
    table.add_column("温度(°C)", justify="right")
    table.add_column("PH", justify="right")

    for row in rows:
        table.add_row(
            str(row.get("date", "")),
            str(row.get("recipe_name", "")),
            str(row.get("batch_id", "")),
            _fmt(row.get("total_malt_weight")),
            _fmt(row.get("strike_water"), ".1f"),
            _fmt(row.get("water_grain_ratio")),
            _fmt(row.get("target_temperature"), ".0f"),
            _fmt(row.get("final_ph")),
        )
    console.print(table)


def show_batch_detail(record, efficiencies):
    """显示批次详情"""
    metadata = record.get("metadata", {})
    ingredients = record.get("ingredients", {})
    mash = record.get("mash", {})
    measurements = record.get("measurements", {})
    process_logs = mash.get("process_logs", [])

    # 基础信息
    info_table = Table(title="基础信息", show_header=False)
    info_table.add_column("项目", style="bold")
    info_table.add_column("数值")
    info_table.add_row("日期", str(metadata.get("date", "")))
    info_table.add_row("配方", str(metadata.get("recipe_name", "")))
    info_table.add_row("批次号", str(metadata.get("batch_id", "")))
    info_table.add_row("麦芽重量(kg)", _fmt(ingredients.get("total_malt_weight")))
    info_table.add_row("理论浸出率", _fmt(ingredients.get("potential_extract")))
    info_table.add_row("糖化水(L)", _fmt(mash.get("strike_water"), ".1f"))
    info_table.add_row("水料比", _fmt(mash.get("water_grain_ratio")))
    info_table.add_row("目标温度(°C)", _fmt(mash.get("target_temperature"), ".0f"))
    info_table.add_row("洗糟水(L)", _fmt(mash.get("sparge_water"), ".1f"))
    console.print(info_table)

    # 糖化过程日志
    if process_logs:
        log_table = Table(title="糖化过程日志")
        log_table.add_column("时间(min)", justify="right")
        log_table.add_column("PH", justify="right")
        log_table.add_column("比重", justify="right")
        for log in process_logs:
            log_table.add_row(
                str(log.get("time_min", "")),
                _fmt(log.get("ph")),
                _fmt(log.get("gravity"), ".4f"),
            )
        console.print(log_table)

    # 测量数据
    meas_table = Table(title="阶段测量")
    meas_table.add_column("阶段")
    meas_table.add_column("体积(L)", justify="right")
    meas_table.add_column("比重", justify="right")
    stage_names = {
        "pre_sparge": "洗糟前",
        "pre_boil": "熬煮前",
        "post_boil": "熬煮后",
        "final": "发酵结束",
    }
    for key, label in stage_names.items():
        m = measurements.get(key, {})
        meas_table.add_row(
            label,
            _fmt(m.get("volume"), ".1f"),
            _fmt(m.get("gravity"), ".4f"),
        )
    console.print(meas_table)

    # 计算效率
    eff_table = Table(title="计算效率")
    eff_table.add_column("指标")
    eff_table.add_column("数值", justify="right")
    eff_items = [
        ("洗糟前提取系数", efficiencies.get("pre_sparge_coefficient")),
        ("洗糟后提取系数", efficiencies.get("post_sparge_coefficient")),
        ("熬煮后效率", efficiencies.get("post_boil_efficiency")),
        ("谷物吸收率(L/kg)", efficiencies.get("grain_absorption_rate")),
        ("熬煮蒸发量(L)", efficiencies.get("boil_off")),
    ]
    for label, val in eff_items:
        eff_table.add_row(label, _fmt(val, ".4f"))
    console.print(eff_table)


def show_efficiency_table(df):
    """显示效率汇总表"""
    table = Table(title="酿造提取系数/效率汇总表")
    table.add_column("日期")
    table.add_column("配方")
    table.add_column("麦芽(kg)", justify="right")
    table.add_column("糖化水", justify="right")
    table.add_column("水料比", justify="right")
    table.add_column("PH", justify="right")
    table.add_column("温度", justify="right")
    table.add_column("洗糟前系数", justify="right")
    table.add_column("洗糟水", justify="right")
    table.add_column("洗糟后系数", justify="right")
    table.add_column("谷物吸收率", justify="right")
    table.add_column("蒸发量", justify="right")
    table.add_column("熬煮后效率", justify="right")

    for _, row in df.iterrows():
        table.add_row(
            str(row.get("date", "")),
            str(row.get("recipe_name", "")),
            _fmt(row.get("total_malt_weight")),
            _fmt(row.get("strike_water"), ".1f"),
            _fmt(row.get("water_grain_ratio")),
            _fmt(row.get("final_ph")),
            _fmt(row.get("target_temperature"), ".0f"),
            _fmt(row.get("pre_sparge_coefficient"), ".4f"),
            _fmt(row.get("sparge_water"), ".1f"),
            _fmt(row.get("post_sparge_coefficient"), ".4f"),
            _fmt(row.get("grain_absorption_rate"), ".3f"),
            _fmt(row.get("boil_off"), ".1f"),
            _fmt(row.get("post_boil_efficiency"), ".4f"),
        )
    console.print(table)


def show_stats_table(stats_rows):
    """显示统计表"""
    table = Table(title="各阶段提取系数/效率统计（去除最大最小各2个值）")
    table.add_column("阶段")
    table.add_column("修剪后均值", justify="right")
    table.add_column("修剪后标准差", justify="right")
    table.add_column("原始均值", justify="right")
    table.add_column("最小值", justify="right")
    table.add_column("最大值", justify="right")
    table.add_column("样本数", justify="right")

    for row in stats_rows:
        table.add_row(
            str(row["阶段"]),
            _fmt(row["修剪后平均值"], ".4f"),
            _fmt(row["修剪后标准差"], ".4f"),
            _fmt(row["原始平均值"], ".4f"),
            _fmt(row["最小值"], ".4f"),
            _fmt(row["最大值"], ".4f"),
            str(row["样本数"]),
        )
    console.print(table)


def show_recipe_summary(result):
    """显示配方设计汇总"""
    table = Table(title="配方设计")
    table.add_column("项目")
    table.add_column("数值", justify="right")

    items = [
        ("目标体积(L)", _fmt(result["target_volume"], ".2f")),
        ("目标比重", _fmt(result["target_sg"], ".4f")),
        ("理论浸出率", _fmt(result["potential_rate"])),
        ("麦芽重量(kg)", _fmt(result["malt_weight"], ".3f")),
        ("糖化用水(L)", _fmt(result["strike_water"], ".2f")),
        ("洗糟水(L)", _fmt(result["sparge_water"], ".2f")),
        ("总用水量(L)", _fmt(result["total_water"], ".2f")),
        ("水料比", _fmt(result["water_grain_ratio"])),
        ("糖化后比重", _fmt(result["pre_sparge_sg"], ".4f")),
        ("熬煮前体积(L)", _fmt(result["pre_boil_volume"], ".2f")),
        ("洗糟后比重", _fmt(result["pre_boil_sg"], ".4f")),
        ("煮沸后比重", _fmt(result["post_boil_sg"], ".4f")),
        ("熬煮蒸发量(L)", _fmt(result["boil_off"], ".2f")),
    ]
    for label, val in items:
        table.add_row(label, val)
    console.print(table)

    console.print("\n[bold]监控说明：[/bold]")
    console.print(f"  糖化后比重目标: {result['pre_sparge_sg']:.4f} (基于糖化水{result['strike_water']:.2f}L)")
    console.print(f"  洗糟后比重目标: {result['pre_boil_sg']:.4f} (基于总水量{result['total_water']:.2f}L)")
    console.print(f"  煮沸后比重目标: {result['post_boil_sg']:.4f} (基于煮沸后体积{result['target_volume']:.2f}L)")


def show_sugar_balance(sugar_balance):
    """显示糖量平衡表"""
    table = Table(title="糖量平衡与浓度变化分析")
    table.add_column("阶段")
    table.add_column("糖量(kg)", justify="right")
    table.add_column("累计提取系数", justify="right")
    table.add_column("体积(L)", justify="right")
    table.add_column("比重", justify="right")

    for row in sugar_balance:
        table.add_row(
            row["stage"],
            _fmt(row["sugar_kg"], ".3f"),
            _fmt(row["coefficient"], ".4f"),
            _fmt(row["volume_l"], ".2f") if row["volume_l"] is not None else "---",
            _fmt(row["sg"], ".4f") if row["sg"] is not None else "---",
        )
    console.print(table)
