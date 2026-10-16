# BrewMetrics 分析笔记（Agent 专用）

> 本文件面向 **AI agent / 后续维护者**，记录模型原理、数据质量现状、已知陷阱与回测结果。
> 人读的说明见 `readme.md`，CLI 用法见 `skill.md`。改动模型或数据前**务必先读本文**。

---

## 0 定位与文件分工

| 文件 | 读者 | 内容 |
|---|---|---|
| `readme.md` | 人 | 动机、公式推导、指标定义 |
| `skill.md` | agent（执行） | CLI 命令、输出字段、工作流 |
| `analysis_notes.md`（本文） | agent（分析） | 原理、坑、回测、待办 |

核心代码：`brew_metrics/calculations.py`（纯计算）、`data.py`（I/O 与逐批指标）、`schema.py`（规范与校验）、`ingredients.py`（原料库）、`display.py`、`cli.py`。

---

## 1 模型原理（务必理解，否则会误判数据）

### 1.1 唯一度量衡

$$\boxed{M_{act}(V,SG)=2.5\,(SG-1)\,V\,SG\quad[\text{kg}]}$$

一切"糖量"都由它算。比重反解是它的二次方程逆运算（`estimate_sg_from_sugar`）。

### 1.2 三个阶段的糖量与**正确口径**

| 量 | 计算 | 口径要点 |
|---|---|---|
| `sugar_mash` | `M_act(strike_water, SG_洗糟前)` | 糖化出糖总量 |
| `sugar_kettle` | `M_act(V_煮前**实测体积**, SG_煮前)` | **必须用实测收集体积** |
| `sugar_boil` | `M_act(V_煮后, SG_煮后)` | 进罐糖量 |

**⚠️ 头号口径陷阱**：把"洗糟后糖量"算成 `M_act(strike_water + sparge_water, SG_煮前)` 会**虚高**（实测虚高 0.03~1.3 kg）。原因：麦床残留麦汁的比重低于锅内麦汁，总水量口径把锅内浓度强加给了全部水量。旧版 `post_sparge_coefficient` 就是这个错误口径，**绝对值无物理意义**，已被 `sparge_recovery` 取代。

### 1.3 守恒与资格判定

- **同温端（硬约束）**：`sugar_kettle ≤ sugar_mash`，即残留率 `retention_ratio=(S_mash−S_kettle)/S_mash ≥ 0`。
  - 洗糟/煮沸**不能凭空产糖**；残留为负 = 记录错误。
  - 资格规则：`retention_ratio ∈ [0, 0.30]` → `hot_consistent=True` → 纳入经验值。
- **跨温端（仅提示）**：`sugar_boil ≤ sugar_kettle`。煮后通常冷测、煮前热测，故 `>1` 只报 `info`（疑温度未补偿），**不作为剔除依据**。
- **上界**：各阶段糖量 ≤ `W × rate`（理论糖量）。这批数据全部通过。

### 1.4 比值 vs 绝对量

- **同温端比值**（`sparge_recovery = S_kettle/S_mash`）对**共同温度偏差免疫**：若两处读数被同一因子 $f$ 压低，则 $\frac{fA}{fB}=\frac{A}{B}$。→ 可在热端未温补时放心使用。
- **绝对量**（`η_pre`、各糖量）受温度影响，**不可跨温端比较**，且不能单独作为精度依据。

### 1.5 分母（理论浸出率 rate）的真相

`W×rate` 只出现在**分母**，且在设计链路中**可约**：

$$W_{new}=W_{hist}\cdot\frac{M_{act}^{target}}{M_{act}^{hist}}\cdot\frac{rate_{hist}}{rate_{design}}$$

只要 $rate_{hist}=rate_{design}$，rate 完全约掉。因此：

- 把 rate 从 0.78 换成原料库真值，若历史与设计**用同一基准**，**预测比重几乎不变**（实测：麦芽量 6.393 → 6.393）。
- rate 的真正价值：① 让**绝对效率值可比/可解释**；② **混合/特种麦芽**时基准正确；③ 未来绝对量功能（色度/苦度/发酵度）。
- **混用基准是 bug**：只改一端会制造 3~7% 的假偏差。

---

## 2 温度坑（本项目最大的数据质量来源）

### 2.1 现状

- 使用者**不测温度、不做温补**（明确决定）。手持比重计，标定温度通常 20 °C。
- 三处测量温度**不同**：洗糟前 ~63–68 °C、煮前热、煮后（冷却后）~20–30 °C。
- 后果：**热端读数系统性偏低**，冷端（煮后）基本准确。

### 2.2 它制造的两类"不自洽"

1. **煮后 > 煮前**（跨温端）：12 批中 8 批出现，最多 +30%。
2. **残留率为负**（同温端仍出现）：5 批（`20240907 −3.5%`、`20250203 −7.5%`、`20250308 −6.3%`、`20250615 −4.0%`、`20240817 曾被误判`）。
   - 修正方向**全部为把热端读数抬高**，与温度偏差方向一致。

### 2.3 处置原则（**不要试图做温度补偿**）

- 使用者无法测温度 → 不引入 `temperature` 字段。
- 改用**同温端比值**（`sparge_recovery`、`retention_ratio`）规避偏差。
- **绝对量只在同温端自洽的批次上统计**，并取中位数。
- 剩余的双向散布（残留率 −13.8%~+21.2%）说明还有**随机读数/取样误差**，不是单一温度偏移——所以不要指望"补一个常数"能修好。

### 2.4 旁证（回测交叉验证）

被剔除的 `20250203`、`20250308`，用**独立路径**（模型正向预测）得到 `Δ糖化后 = +0.0146 / +0.0175`——即模型认为它们的糖化前读数偏低 0.015~0.018，与剔除理由一致。

---

## 3 原料库（Brewtarget）

- 文件：`brew_metrics/ingredients_db.json`（248 条），由 Brewtarget `default_db.sqlite`（`main` 分支）生成。
- 口径：`potential_extract_asis = fine_yield_pct/100 × (1 − moisture/100)`，即**原样细粉浸出率**，与分母里麦芽"原样重量"一致。
- 匹配：`ingredients.lookup_malt`（精确 → 去供应商前缀 → 供应商+名 → token 相似度，阈值 0.5，宁不匹配也不错配）。
- 优先级：**原料库 > 记录值 `malt.potential_extract` > 综合值 `ingredients.potential_extract`**。
- 已知库内值：Maris Otter(Simpsons) 0.7857、Briess Pilsen 0.7688、Rice Flaked 0.70、Rye Flaked 0.783、Rice Hulls 0.0。
- **覆盖缺口**：Spelt 等无条目 → 回退；`Pilsner` 泛名会模糊命中（如 Weyermann）。
- **⚠️ 原料库是通用品牌值，不等于使用者那袋麦芽**；`source` 字段标明 `db`/`record`/`fallback`，分析时应报告覆盖率。

> 重要：更换原料库基准后，**必须重算全部历史系数**（`analyze`），否则历史与设计混用基准 → 假偏差。

---

## 4 回测（截至 2026-10，14 批数据）

### 4.1 方法

- 训练集 = **同温端自洽**且数据完整的 7 批：`20240629 / 20240817 / 20241001 / 20241228 / 20250401 / 20260115 / 20260227`。
- 用训练集取各过程量**中位数**，再对每批用**实际麦芽重量+水量**正向预测最终比重（`predict` 口径）。
- 分两种误差：**终点 ΔSG**（含体积误差）与**糖量 ΔSG**（用实测体积隔离体积误差）。

### 4.2 结果

| | n | \|Δ终点\|均 | \|Δ糖量\|均 | \|ΔV\|均 |
|---|---|---|---|---|
| 训练集（含自身） | 7 | 0.0042 | 0.0038 | 0.81 L |
| 测试集（独立） | 6 | 0.0060 | 0.0064 | 0.70 L |

**结论**：糖量链可信（独立误差 ~0.006 SG ≈ 1.5 °P）；误差有相当部分来自**体积模型**。

### 4.3 已知大偏差及其原因

| 批次 | Δ终点 | 原因 |
|---|---|---|
| 20260227 Cold IPA | −0.0104 | 实测 `E_post=0.796` 远高于训练中位 0.665——**真实批次差异**（高米片比、高收得） |
| 20241116-A-BW | −0.0119 | 8 kg 大麦酒，超出经验区间 |
| 20260529-S-SAISON | −0.0112 | 含 Spelt，原料库无数据（回退值） |

---

## 5 经验值现状与口径

`analyze` 输出的 `brewing_metrics_summary.csv`（均为**同温端自洽批次的中位数**）：

| 列 | 值 | 纳入 |
|---|---|---|
| `pre_sparge_coefficient` | 0.7725 | 7 |
| `sparge_recovery` | 0.8487 | 7 |
| `retention_ratio` | 0.1513 | 7 |
| `grain_absorption_rate` | 0.8723 | 12 |
| `post_boil_efficiency` | 0.6715 | 13 |
| `boil_off_volume` | 2.00 | 12 |

- 体积量（吸收率、蒸发量）不依赖比重 → 不设资格门槛，纳入全部有值批次。
- `post_boil_efficiency` 依赖**冷端**读数（可靠）→ 也纳入全部有煮后数据的批次；若希望"整批可疑就整体剔除"，把它的 gate 改成 `hot_consistent`（n=7、值 0.6647）。

---

## 6 已知坑 / 待办

1. **`design` 的默认参数硬编码**：`--potential-rate`(0.78) 与 `--water-grain-ratio`(3.06) 写死在 `cli.py`，**不来自 CSV**；`readme` 曾误标"取自 CSV"。
2. **11/14 批无麦芽明细**：只有 3 批列了 `malts`，原料库只对它们生效；其余靠综合值 0.78。补录麦芽名可显著提升分母质量。
3. **`E_post` 批次间波动大**（0.60~0.85），单一中位数偏粗。建议按目标比重区间 / 是否含辅料**分层取中位数**。
4. **体积模型偏弱**：`grain_absorption`、`boil_off` 取中位数，ΔV 达 0.7~2.1 L。可考虑按批次建模。
5. **回测未固化**：建议加 `analyze --backtest`，每次更新数据自动跑 LOO 误差表，作为模型退化体检。
6. **不要加温度字段/温补**（使用者决定），一律用同温端比值方案。
7. 旧指标 `post_sparge_coefficient`（总水量口径）仍在 `data.calculate_stage_efficiencies` 中计算，**仅遗留兼容，勿用于分析**。

---

## 7 可直接复用的分析片段

```python
import glob, yaml, statistics as st
from brew_metrics import data
from brew_metrics.calculations import (calculate_prediction, effective_potential_extract,
                                       estimate_sg_from_sugar)

recs = [yaml.safe_load(open(f)) for f in sorted(glob.glob("brew_data/*.yaml"))]
eff  = [data.calculate_stage_efficiencies(r) for r in recs]   # 逐批过程量+资格
byid = {r["metadata"]["batch_id"]: r for r in recs}

# 训练集 = 同温端自洽批次；经验值取中位数
train = [r for r in eff if r.get("eligible") and r.get("post_boil_sg") is not None]
med = lambda k: st.median([r[k] for r in train if r.get(k) is not None])
metrics = {"pre_sparge_coefficient": med("pre_sparge_coefficient"),
           "sparge_recovery":        med("sparge_recovery"),
           "grain_absorption_rate":  med("grain_absorption_rate"),
           "post_boil_efficiency":   med("post_boil_efficiency"),
           "boil_off_volume":        med("boil_off")}

# 正向预测：麦芽重量 + 水量 → 最终比重
row = eff[0]; r = byid[row["batch_id"]]
rate = effective_potential_extract(r["ingredients"], data._resolve_malt_rate)
res = calculate_prediction(
    [{"name": "x", "weight": r["ingredients"]["total_malt_weight"], "rate": rate}],
    r["mash"]["strike_water"], r["mash"]["sparge_water"], metrics)
print(res["final_sg"], res["pre_sparge_sg"], res["pre_boil_sg"])
```

**关键区分**：分析时务必分清 `sugar_kettle`（实测体积口径）与任何"总水量口径"；永远不要在跨温端读数上做绝对量比较。
