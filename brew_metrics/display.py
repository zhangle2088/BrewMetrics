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
    info_table.add_row("理论浸出率", _fmt(efficiencies.get("potential_extract")))
    if ingredients.get("malts"):
        for malt in ingredients["malts"]:
            name = malt.get("name", "?")
            amount = _fmt(malt.get("amount"), ".2f")
            rate = _fmt(malt.get("potential_extract"), ".2f")
            info_table.add_row(f"  麦芽 {name}", f"{amount} kg @ {rate}")
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
        ("洗糟回收率", efficiencies.get("sparge_recovery")),
        ("麦床残留率", efficiencies.get("retention_ratio")),
        ("熬煮后效率", efficiencies.get("post_boil_efficiency")),
        ("谷物吸收率(L/kg)", efficiencies.get("grain_absorption_rate")),
        ("熬煮蒸发量(L)", efficiencies.get("boil_off")),
    ]
    for label, val in eff_items:
        eff_table.add_row(label, _fmt(val, ".4f"))
    console.print(eff_table)

    # 糖量与自洽性
    sugar_table = Table(title="糖量与自洽性")
    sugar_table.add_column("项目")
    sugar_table.add_column("数值", justify="right")
    sugar_table.add_row("糖化出糖(kg)", _fmt(efficiencies.get("sugar_mash"), ".3f"))
    sugar_table.add_row("煮前收集(kg)", _fmt(efficiencies.get("sugar_kettle"), ".3f"))
    sugar_table.add_row("煮后进罐(kg)", _fmt(efficiencies.get("sugar_boil"), ".3f"))
    hot = efficiencies.get("retention_ratio")
    sugar_table.add_row(
        "煮后/煮前(应≤1)",
        _fmt(efficiencies.get("boil_ratio"), ".3f"),
    )
    console.print(sugar_table)

    if efficiencies.get("eligible"):
        console.print("[green]同温端自洽：纳入经验值统计[/green]")
    else:
        reason = []
        if efficiencies.get("retention_ratio") is not None and efficiencies["retention_ratio"] < 0:
            reason.append("残留率为负(物理不可能)")
        if efficiencies.get("boil_consistent") is False:
            reason.append("煮后糖量>煮前(疑温度偏差)")
        console.print(
            "[yellow]未通过同温端自洽，已从经验值统计中剔除"
            + (f"：{'；'.join(reason)}" if reason else "")
            + "[/yellow]"
        )


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
    table.add_column("洗糟回收率", justify="right")
    table.add_column("谷物吸收率", justify="right")
    table.add_column("蒸发量", justify="right")
    table.add_column("熬煮后效率", justify="right")
    table.add_column("资格", justify="center")

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
            _fmt(row.get("sparge_recovery"), ".3f"),
            _fmt(row.get("grain_absorption_rate"), ".3f"),
            _fmt(row.get("boil_off"), ".1f"),
            _fmt(row.get("post_boil_efficiency"), ".4f"),
            "[green]✓[/green]" if row.get("eligible") else "[red]✗[/red]",
        )
    console.print(table)


def show_prediction(result):
    """显示正向预测结果"""
    table = Table(title="正向预测（麦芽重量 + 水量 → 最终比重）")
    table.add_column("项目")
    table.add_column("数值", justify="right")

    items = [
        ("总麦芽(kg)", _fmt(result["total_malt_weight"], ".3f")),
        ("加权浸出率", _fmt(result["weighted_rate"], ".4f")),
        ("理论总糖(kg)", _fmt(result["theoretical_sugar"], ".3f")),
        ("糖化水(L)", _fmt(result["strike_water"], ".2f")),
        ("洗糟水(L)", _fmt(result["sparge_water"], ".2f")),
        ("谷物吸收(L)", _fmt(result["grain_absorption"], ".2f")),
        ("熬煮前体积(L)", _fmt(result["pre_boil_volume"], ".2f")),
        ("蒸发量(L)", _fmt(result["boil_off"], ".2f")),
        ("预计最终体积(L)", _fmt(result["final_volume"], ".2f")),
        ("进罐糖量(kg)", _fmt(result["sugar_boil"], ".3f")),
        ("糖化后比重(监控)", _fmt(result.get("pre_sparge_sg"), ".4f")),
        ("熬煮前比重(监控)", _fmt(result["pre_boil_sg"], ".4f")),
        ("[bold]预计最终比重[/bold]", f"[bold]{_fmt(result['final_sg'], '.4f')}[/bold]"),
    ]
    for label, val in items:
        table.add_row(label, val)
    console.print(table)

    grist_table = Table(title="麦芽清单与浸出率来源")
    grist_table.add_column("麦芽")
    grist_table.add_column("重量(kg)", justify="right")
    grist_table.add_column("浸出率", justify="right")
    grist_table.add_column("来源")
    for g in result.get("grist", []):
        src = {"db": "[green]原料库[/green]", "fallback": "[yellow]回退值[/yellow]"}.get(
            g.get("source"), str(g.get("source"))
        )
        grist_table.add_row(
            str(g.get("name")),
            _fmt(g.get("weight"), ".2f"),
            _fmt(g.get("rate"), ".4f"),
            src,
        )
    console.print(grist_table)


def show_stats_table(stats_rows):
    """显示经验值统计表（同温端资格筛选 + 中位数）"""
    table = Table(title="各过程量经验值（同温端自洽筛选后取中位数）")
    table.add_column("过程量")
    table.add_column("经验值(中位)", justify="right")
    table.add_column("MAD", justify="right")
    table.add_column("截尾均值", justify="right")
    table.add_column("最小值", justify="right")
    table.add_column("最大值", justify="right")
    table.add_column("纳入", justify="right")
    table.add_column("剔除", justify="right")

    for row in stats_rows:
        table.add_row(
            str(row["阶段"]),
            _fmt(row["经验值(中位)"], ".4f"),
            _fmt(row["MAD"], ".4f"),
            _fmt(row["截尾均值"], ".4f"),
            _fmt(row["最小值"], ".4f"),
            _fmt(row["最大值"], ".4f"),
            str(row["纳入"]),
            str(row["剔除"]),
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
        ("糖化后比重(回收率口径)", _fmt(result.get("pre_sparge_sg_recovery"), ".4f")),
        ("熬煮前体积(L)", _fmt(result["pre_boil_volume"], ".2f")),
        ("洗糟后比重", _fmt(result["pre_boil_sg"], ".4f")),
        ("煮沸后比重", _fmt(result["post_boil_sg"], ".4f")),
        ("熬煮蒸发量(L)", _fmt(result["boil_off"], ".2f")),
        ("历史洗糟回收率(参考)", _fmt(result.get("reference_sparge_recovery"), ".4f")),
        ("历史谷物吸收率(参考)", _fmt(result.get("reference_grain_absorption_rate"), ".4f")),
    ]
    for label, val in items:
        table.add_row(label, val)
    console.print(table)

    console.print("\n[bold]监控说明：[/bold]")
    console.print(f"  糖化后比重目标: {result['pre_sparge_sg']:.4f} (基于糖化水{result['strike_water']:.2f}L、提取系数)")
    if result.get("pre_sparge_sg_recovery") is not None:
        console.print(
            f"  糖化后比重目标(回收率口径): {result['pre_sparge_sg_recovery']:.4f} "
            f"(同温端回收率×目标进罐糖量反推，抗热端温度偏差)"
        )
    console.print(f"  熬煮前比重目标: {result['pre_boil_sg']:.4f} (基于熬煮前体积{result['pre_boil_volume']:.2f}L，与煮沸后经蒸发量守恒)")
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


def show_validation(result):
    """显示数据规范校验结果"""
    batches = result["batches"]
    duplicates = result["duplicates"]

    table = Table(title="数据规范校验")
    table.add_column("文件")
    table.add_column("批次号")
    table.add_column("级别")
    table.add_column("问题")

    total_issues = 0
    for batch in batches:
        issues = batch["issues"]
        if not issues:
            table.add_row(batch["file"], str(batch["batch_id"]), "[green]OK[/green]", "-")
            continue
        for issue in issues:
            total_issues += 1
            level = issue["level"]
            style = {"error": "red", "warning": "yellow"}.get(level, "dim")
            table.add_row(
                batch["file"],
                str(batch["batch_id"]),
                f"[{style}]{level}[/{style}]",
                f"{issue['field']}: {issue['message']}",
            )
    console.print(table)

    if duplicates:
        dup_table = Table(title="疑似重复批次")
        dup_table.add_column("批次号")
        dup_table.add_column("原因")
        for group in duplicates:
            dup_table.add_row(
                ", ".join(str(b) for b in group["batch_ids"]), group["reason"]
            )
        console.print(dup_table)
    else:
        console.print("[green]未发现重复批次[/green]")

    console.print(
        f"\n共 {len(batches)} 个批次，{total_issues} 条提示，"
        f"{len(duplicates)} 组疑似重复"
    )


def show_migration(results, write):
    """显示数据规范化迁移结果"""
    title = "数据规范化迁移" + ("（已写入）" if write else "（演练，未改动）")
    table = Table(title=title)
    table.add_column("文件")
    table.add_column("批次号")
    table.add_column("变更")

    changed = 0
    for item in results:
        changes = item.get("changes") or []
        if changes:
            changed += 1
        table.add_row(
            item["file"],
            str(item.get("batch_id")),
            "\n".join(changes) if changes else "-",
        )
    console.print(table)
    console.print(
        f"\n共 {len(results)} 个文件，{changed} 个需要变更"
        + ("" if write else "（加 --write 才会落盘）")
    )
