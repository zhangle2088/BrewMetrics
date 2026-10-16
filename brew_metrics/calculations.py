"""纯计算函数，无 I/O、无副作用"""

from typing import Optional


def sg_to_plato(sg: float) -> float:
    """将比重(SG)转换为糖度(Plato)"""
    return (sg - 1.000) * 250


def calculate_potential_extract(weight: float, rate: float) -> float:
    """计算麦芽的理论浸出物总量 (kg)"""
    return weight * rate


def effective_potential_extract(ingredients: dict, resolver=None) -> Optional[float]:
    """综合理论浸出率（按麦芽重量加权）。

    每条麦芽的浸出率取值优先级：
      1. ``resolver(name, supplier)`` —— 本地原料库（如 Brewtarget）校准值；
      2. ``malt.potential_extract``   —— 记录中的逐麦芽值；
      3. ``ingredients.potential_extract`` —— 综合回退值。

    ``resolver`` 未匹配返回 ``None`` 时自动回退，因此原料库可只覆盖部分麦芽。
    无 ``malts`` 明细时直接返回 ``ingredients.potential_extract``。
    """
    if not isinstance(ingredients, dict):
        return None

    fallback = ingredients.get("potential_extract")
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
            rate = None
            if resolver is not None:
                rate = resolver(malt.get("name"), malt.get("supplier"))
            if rate is None:
                rate = malt.get("potential_extract")
            if rate is None:
                rate = fallback
            if weight is None or rate is None:
                usable = False
                break
            total_weight += float(weight)
            weighted += float(weight) * float(rate)
        if usable and total_weight > 0:
            return weighted / total_weight

    return fallback


def explain_potential_extract(ingredients: dict, resolver=None) -> list:
    """逐麦芽列出浸出率取值及来源，便于核对原料库匹配情况。"""
    if not isinstance(ingredients, dict):
        return []
    fallback = ingredients.get("potential_extract")
    out = []
    for malt in ingredients.get("malts") or []:
        if not isinstance(malt, dict):
            continue
        weight = malt.get("amount", malt.get("weight"))
        db_rate = None
        if resolver is not None:
            db_rate = resolver(malt.get("name"), malt.get("supplier"))
        if db_rate is not None:
            rate, source = db_rate, "db"
        elif malt.get("potential_extract") is not None:
            rate, source = malt["potential_extract"], "record"
        else:
            rate, source = fallback, "fallback"
        out.append(
            {
                "name": malt.get("name"),
                "weight": weight,
                "rate": rate,
                "source": source,
            }
        )
    return out


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


def calculate_robust_stats(series) -> dict:
    """稳健统计：中位数、MAD（绝对中位差）、截尾均值、样本数。

    中位数对残余离群点不敏感，优于「去首尾各 N 个」的固定截尾；
    MAD 给出散布尺度；截尾均值保留以兼容旧口径。
    """
    valid = series.dropna()
    n = len(valid)
    if n == 0:
        return {"n": 0, "median": None, "mad": None, "trimmed_mean": None}
    median = float(valid.median())
    mad = float((valid - median).abs().median())
    trimmed_mean, _ = calculate_trimmed_stats(valid)
    return {
        "n": n,
        "median": median,
        "mad": mad,
        "trimmed_mean": trimmed_mean,
    }


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


def calculate_prediction(
    grist: list, strike_water: float, sparge_water: float, metrics: dict
) -> dict:
    """正向预测：由麦芽清单 + 水量 + 历史效率，预测最终体积与比重。

    ``grist`` 每项 ``{"name", "weight", "rate"}``（``rate`` 为原样浸出率，未匹配用综合值）。
    预测链路：
      理论糖量 = Σ(重量 × 浸出率)
      进罐糖量 = 理论糖量 × post_boil_efficiency
      最终体积 = strike + sparge − 谷物吸收 × 总麦芽重 − 蒸发量
      最终比重 = 反解 M_act(V, SG) = 进罐糖量
    """
    total_weight = sum(float(g["weight"]) for g in grist if g.get("weight") is not None)
    theory = sum(
        float(g["weight"]) * float(g["rate"])
        for g in grist
        if g.get("weight") is not None and g.get("rate") is not None
    )

    post_boil_eff = metrics["post_boil_efficiency"]
    grain_absorption = metrics["grain_absorption_rate"]
    boil_off = metrics["boil_off_volume"]
    pre_coeff = metrics.get("pre_sparge_coefficient")

    absorbed = grain_absorption * total_weight
    pre_boil_volume = strike_water + sparge_water - absorbed
    final_volume = pre_boil_volume - boil_off

    sugar_boil = theory * post_boil_eff
    final_sg = estimate_sg_from_sugar(final_volume, sugar_boil)
    # 煮沸不产糖：煮前与煮后糖量相同
    pre_boil_sg = estimate_sg_from_sugar(pre_boil_volume, sugar_boil)
    pre_sparge_sg = (
        estimate_sg_from_sugar(strike_water, theory * pre_coeff)
        if pre_coeff is not None
        else None
    )

    return {
        "grist": grist,
        "total_malt_weight": round(total_weight, 3),
        "weighted_rate": round(theory / total_weight, 4) if total_weight else None,
        "theoretical_sugar": round(theory, 3),
        "strike_water": round(strike_water, 2),
        "sparge_water": round(sparge_water, 2),
        "total_water": round(strike_water + sparge_water, 2),
        "grain_absorption": round(absorbed, 2),
        "pre_boil_volume": round(pre_boil_volume, 2),
        "boil_off": round(boil_off, 2),
        "final_volume": round(final_volume, 2),
        "sugar_boil": round(sugar_boil, 3),
        "pre_sparge_sg": round(pre_sparge_sg, 4) if pre_sparge_sg is not None else None,
        "pre_boil_sg": round(pre_boil_sg, 4),
        "final_sg": round(final_sg, 4),
        "reference_post_boil_efficiency": round(post_boil_eff, 4),
        "reference_grain_absorption_rate": round(grain_absorption, 4),
    }


def calculate_recipe(
    volume: float, sg: float, rate: float, wgr: float, metrics: dict
) -> dict:
    """完整配方计算

    metrics 需包含: pre_sparge_coefficient, sparge_recovery(或旧的
                    post_sparge_coefficient), grain_absorption_rate,
                    post_boil_efficiency, boil_off_volume
    """
    pre_sparge_coeff = metrics.get("pre_sparge_coefficient")
    sparge_recovery = metrics.get("sparge_recovery", metrics.get("post_sparge_coefficient"))
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

    # 糖化后（洗糟前）比重：基于糖化锅初始水量与提取系数
    sugar_mash = potential_total * pre_sparge_coeff
    pre_sparge_sg = estimate_sg_from_sugar(strike_water, sugar_mash)

    # 煮沸后收获糖量（= 目标进罐糖量）
    sugar_boil = potential_total * post_boil_eff
    post_boil_sg = estimate_sg_from_sugar(volume, sugar_boil)

    # 备选糖化后比重：由「洗糟回收率（同温端比值）× 目标进罐糖量」反推糖化出糖，
    # 再反解。该口径只用同温端比值与冷端目标，不含热端绝对读数，
    # 因此不受糖化阶段温度偏差影响，可作为首选监控目标。
    sugar_mash_recovery = (sugar_boil / sparge_recovery) if sparge_recovery else None
    pre_sparge_sg_recovery = (
        estimate_sg_from_sugar(strike_water, sugar_mash_recovery)
        if sugar_mash_recovery is not None
        else None
    )

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
        "pre_sparge_sg_recovery": (
            round(pre_sparge_sg_recovery, 4)
            if pre_sparge_sg_recovery is not None
            else None
        ),
        "pre_boil_sg": round(pre_boil_sg, 4),
        "post_boil_sg": round(post_boil_sg, 4),
        "boil_off": round(boil_off, 2),
        # 历史参考：洗糟回收率（同温端比值）与谷物吸收率，用于监控对比
        "reference_sparge_recovery": (
            round(sparge_recovery, 4) if sparge_recovery is not None else None
        ),
        "reference_grain_absorption_rate": round(grain_absorption, 4),
        "reference_post_boil_efficiency": round(post_boil_eff, 4),
        "sugar_balance": sugar_balance,
    }
