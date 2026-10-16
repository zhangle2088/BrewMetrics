"""纯计算函数，无 I/O、无副作用"""

from typing import Optional


def sg_to_plato(sg: float) -> float:
    """将比重(SG)转换为糖度(Plato)"""
    return (sg - 1.000) * 250


def calculate_potential_extract(weight: float, rate: float) -> float:
    """计算麦芽的理论浸出物总量 (kg)"""
    return weight * rate


def effective_potential_extract(ingredients: dict) -> Optional[float]:
    """综合理论浸出率。

    若给出 ``malts`` 明细且每条都带 ``potential_extract``，按重量加权求均值；
    否则回退到 ``ingredients.potential_extract``（单一综合值）。
    """
    if not isinstance(ingredients, dict):
        return None

    malts = ingredients.get("malts")
    if isinstance(malts, list) and malts:
        total_weight = 0.0
        weighted = 0.0
        usable = True
        for malt in malts:
            if not isinstance(malt, dict):
                usable = False
                break
            weight = malt.get("amount", malt.get("weight"))
            rate = malt.get("potential_extract")
            if weight is None or rate is None:
                usable = False
                break
            total_weight += float(weight)
            weighted += float(weight) * float(rate)
        if usable and total_weight > 0:
            return weighted / total_weight

    return ingredients.get("potential_extract")


def calculate_actual_extract(volume: float, sg: float) -> Optional[float]:
    """计算麦汁中的实际含糖量 (kg)"""
    if volume is None or sg is None:
        return None
    return 2.5 * (sg - 1.0) * volume * sg


def calculate_extraction_coefficient(
    weight: float, rate: float, volume: float, sg: float
) -> Optional[float]:
    """计算提取系数（小数形式，如 0.75 表示 75%）"""
    if volume is None or sg is None:
        return None
    potential = calculate_potential_extract(weight, rate)
    actual = calculate_actual_extract(volume, sg)
    if potential == 0 or actual is None:
        return None
    return round(actual / potential, 4)


def calculate_trimmed_stats(series) -> tuple:
    """计算去除最大最小各2个值后的统计量，返回 (trimmed_mean, trimmed_std)"""
    valid_data = series.dropna()
    if len(valid_data) <= 4:
        if len(valid_data) > 0:
            return float(valid_data.mean()), float(valid_data.std())
        return None, None
    sorted_data = valid_data.sort_values()
    trimmed_data = sorted_data.iloc[2:-2]
    return float(trimmed_data.mean()), float(trimmed_data.std())


def estimate_sg_from_sugar(volume: float, sugar: float) -> float:
    """根据糖量估计比重（二次方程求解）

    从 sugar = 2.5 * (sg - 1) * volume * sg 反解 sg
    """
    a = 2.5 * volume
    b = -2.5 * volume
    c = -sugar
    discriminant = b**2 - 4 * a * c
    return (-b + discriminant**0.5) / (2 * a)


def calculate_malt_weight(
    volume: float, sg: float, efficiency: float, rate: float
) -> float:
    """计算所需麦芽重量 (kg)

    efficiency: 小数形式，如 0.6823
    """
    actual_extract = calculate_actual_extract(volume, sg)
    return actual_extract / efficiency / rate


def calculate_recipe(
    volume: float, sg: float, rate: float, wgr: float, metrics: dict
) -> dict:
    """完整配方计算

    metrics 需包含: pre_sparge_coefficient, post_sparge_coefficient,
                    grain_absorption_rate, post_boil_efficiency, boil_off_volume
    """
    pre_sparge_coeff = metrics["pre_sparge_coefficient"]
    post_sparge_coeff = metrics["post_sparge_coefficient"]
    grain_absorption = metrics["grain_absorption_rate"]
    post_boil_eff = metrics["post_boil_efficiency"]
    boil_off = metrics["boil_off_volume"]

    # 麦芽重量
    malt_weight = calculate_malt_weight(volume, sg, post_boil_eff, rate)

    # 糖化用水
    strike_water = malt_weight * wgr

    # 熬煮前体积
    pre_boil_volume = volume + boil_off

    # 洗糟水
    sparge_water = grain_absorption * malt_weight + pre_boil_volume - strike_water

    # 理论总糖量
    potential_total = calculate_potential_extract(malt_weight, rate)

    # 糖化后（洗糟前）比重：基于糖化锅初始水量
    sugar_mash = potential_total * pre_sparge_coeff
    pre_sparge_sg = estimate_sg_from_sugar(strike_water, sugar_mash)

    # 煮沸后收获糖量（= 目标进罐糖量）
    sugar_boil = potential_total * post_boil_eff
    post_boil_sg = estimate_sg_from_sugar(volume, sugar_boil)

    # 熬煮前（洗糟后）比重：按质量守恒反推。
    # 煮沸过程只蒸发浓缩、不损失可溶糖，故熬煮前糖量 == 煮沸后糖量；
    # 体积取熬煮前实际体积。如此 pre_boil_sg 与 post_boil_sg 在蒸发量下自洽。
    # （旧实现用 post_sparge_coefficient『总水量口径』预测，与煮沸步骤不自洽，
    #   会出现「蒸发量不足以达到目标比重」的偏差。）
    sugar_sparge = sugar_boil
    pre_boil_sg = estimate_sg_from_sugar(pre_boil_volume, sugar_sparge)

    total_water = strike_water + sparge_water

    # 糖量平衡
    sugar_balance = [
        {
            "stage": "理论总糖量",
            "sugar_kg": round(potential_total, 3),
            "coefficient": 1.0,
            "volume_l": None,
            "sg": None,
        },
        {
            "stage": "糖化后提取",
            "sugar_kg": round(sugar_mash, 3),
            "coefficient": round(pre_sparge_coeff, 4),
            "volume_l": round(strike_water, 2),
            "sg": round(pre_sparge_sg, 4),
        },
        {
            "stage": "洗糟后收集",
            "sugar_kg": round(sugar_sparge, 3),
            "coefficient": None,
            "volume_l": round(pre_boil_volume, 2),
            "sg": round(pre_boil_sg, 4),
        },
        {
            "stage": "煮沸后收获",
            "sugar_kg": round(sugar_boil, 3),
            "coefficient": round(post_boil_eff, 4),
            "volume_l": round(volume, 2),
            "sg": round(post_boil_sg, 4),
        },
    ]

    return {
        "target_volume": volume,
        "target_sg": sg,
        "potential_rate": rate,
        "malt_weight": round(malt_weight, 3),
        "strike_water": round(strike_water, 2),
        "sparge_water": round(sparge_water, 2),
        "total_water": round(total_water, 2),
        "water_grain_ratio": wgr,
        "pre_boil_volume": round(pre_boil_volume, 2),
        "pre_sparge_sg": round(pre_sparge_sg, 4),
        "pre_boil_sg": round(pre_boil_sg, 4),
        "post_boil_sg": round(post_boil_sg, 4),
        "boil_off": round(boil_off, 2),
        # 历史参考：洗糟后提取系数（总水量口径）与谷物吸收率，仅用于监控对比
        "reference_post_sparge_coefficient": round(post_sparge_coeff, 4),
        "reference_grain_absorption_rate": round(grain_absorption, 4),
        "reference_post_boil_efficiency": round(post_boil_eff, 4),
        "sugar_balance": sugar_balance,
    }
