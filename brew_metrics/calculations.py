"""纯计算函数，无 I/O、无副作用"""

from typing import Optional


def sg_to_plato(sg: float) -> float:
    """将比重(SG)转换为糖度(Plato)"""
    return (sg - 1.000) * 250


def calculate_potential_extract(weight: float, rate: float) -> float:
    """计算麦芽的理论浸出物总量 (kg)"""
    return weight * rate


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

    # 糖化后比重
    sugar_mash = potential_total * pre_sparge_coeff
    pre_sparge_sg = estimate_sg_from_sugar(strike_water, sugar_mash)

    # 洗糟后比重（基于总水量）
    total_water = strike_water + sparge_water
    sugar_sparge = potential_total * post_sparge_coeff
    pre_boil_sg = estimate_sg_from_sugar(total_water, sugar_sparge)

    # 煮沸后比重（验证）
    sugar_boil = potential_total * post_boil_eff
    post_boil_sg = estimate_sg_from_sugar(volume, sugar_boil)

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
            "coefficient": round(post_sparge_coeff, 4),
            "volume_l": round(total_water, 2),
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
        "sugar_balance": sugar_balance,
    }
