# BrewMetrics Skill

家酿啤酒效率分析与配方设计 CLI 工具。覆盖完整酿造工作流：酿造前分析 → 酿造中记录+监控 → 酿造后报告。

## 环境准备

```bash
cd /Users/zhangle/SynologyDrive/IDC/IDC_notebook/BrewMetrics
uv pip install -e .
```

安装后提供 `brew-metrics` 命令。**所有命令加 `--json` 可获取结构化 JSON 输出**，供 agent 解析。

## 工作流总览

```
酿造前: design → add
酿造中: record (--process-log / --stage) × N
酿造后: show → analyze → design (下一批次)
```

---

## 命令参考

### `brew-metrics list` — 批次列表

查看所有历史批次。

```bash
brew-metrics list --json
```

**JSON 输出** → `data.batches[]`，每个元素字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 酿造日期 YYYY-MM-DD |
| recipe_name | string | 配方名 |
| batch_id | string | 批次号（全局唯一标识） |
| total_malt_weight | float | 麦芽重量 kg |
| strike_water | float | 糖化水 L |
| water_grain_ratio | float | 水料比 |
| target_temperature | float | 糖化温度 °C |
| final_ph | float\|null | 最后一次测量的 PH |

---

### `brew-metrics show <batch_id>` — 批次详情

显示完整酿造记录 + 自动计算的各阶段提取系数/效率。

```bash
brew-metrics show 20260227-C-IPA --json
```

**JSON 输出** → `data.record`（原始 YAML 数据）+ `data.efficiencies`（计算结果）：

efficiencies 关键字段：

| 字段 | 说明 |
|------|------|
| pre_sparge_coefficient | 洗糟前提取系数（度量糖化效果） |
| post_sparge_coefficient | 洗糟后提取系数（度量糖化+洗糟总效果） |
| post_boil_efficiency | 熬煮后效率（度量进罐前整体效率） |
| grain_absorption_rate | 谷物吸收率 L/kg |
| boil_off | 熬煮蒸发量 L |

---

### `brew-metrics add` — 创建新酿造记录

酿造前使用，在 `brew_data/` 下生成 YAML 文件。

```bash
brew-metrics add \
  --date 2026-05-25 \
  --recipe "SMaSH IPA" \
  --batch-id "20260525-S-IPA" \
  --total-malt-weight 7.5 \
  --potential-extract 0.78 \
  --strike-water 23 \
  --water-grain-ratio 3.06 \
  --target-temperature 64 \
  --sparge-water 7 \
  --json
```

**所有参数均为必填**。`--potential-extract` 为综合理论浸出率（单一麦芽取厂商值，混合麦芽取加权均值，常用 0.78）。

**JSON 输出** → `data.file`（文件路径）+ `data.batch_id`

---

### `brew-metrics record <batch_id>` — 记录测量数据

酿造中使用，两种模式互斥：

**模式 1：追加糖化过程日志**（糖化期间定时采样）

```bash
brew-metrics record 20260525-S-IPA --process-log --time-min 20 --ph 5.28 --gravity 1.058 --json
brew-metrics record 20260525-S-IPA --process-log --time-min 40 --ph 5.24 --gravity 1.083 --json
```

必填：`--process-log --time-min`。可选：`--ph`、`--gravity`。

**模式 2：记录阶段测量**（关键节点采样）

```bash
brew-metrics record 20260525-S-IPA --stage pre-sparge  --volume 15  --gravity 1.084 --json
brew-metrics record 20260525-S-IPA --stage pre-boil    --volume 26  --gravity 1.067 --json
brew-metrics record 20260525-S-IPA --stage post-boil   --volume 24  --gravity 1.075 --json
brew-metrics record 20260525-S-IPA --stage final       --volume 20  --gravity 1.008 --json
```

可选 `--stage` 值：`pre-sparge`、`pre-boil`、`post-boil`、`final`。可选：`--volume`、`--gravity`。

---

### `brew-metrics analyze` — 效率分析

酿造后使用，加载所有批次数据，计算各阶段提取系数/效率，输出汇总表和统计表，保存修剪均值到 CSV。

```bash
brew-metrics analyze --json
brew-metrics analyze -o brewing_metrics_summary.csv --json
```

**JSON 输出** → `data.table[]`（每批次效率数据）+ `data.stats[]`（各阶段统计）+ `data.csv_exported`

stats 中每个元素：

| 字段 | 说明 |
|------|------|
| 阶段 | 中文名 |
| 修剪后平均值 | 去除最大最小各2个值后的均值 |
| 修剪后标准差 | 修剪后标准差 |
| 原始平均值 | 全量均值 |
| 最小值 / 最大值 | 极值 |
| 样本数 | 有效数据条数 |

CSV 列：`pre_sparge_coefficient`, `post_sparge_coefficient`, `grain_absorption_rate`, `post_boil_efficiency`, `boil_off_volume`

---

### `brew-metrics design` — 配方设计

酿造前使用，基于历史效率数据推算原料用量和过程监控目标值。

```bash
brew-metrics design --volume 22 --sg 1.068 --json
brew-metrics design --volume 22 --sg 1.068 --potential-rate 0.78 --water-grain-ratio 3.06 --json
```

必填：`--volume`（目标煮沸后体积 L）、`--sg`（目标煮沸后比重）。

**JSON 输出** → `data.recipe` + `data.sugar_balance[]`

recipe 关键字段：

| 字段 | 说明 |
|------|------|
| malt_weight | 所需麦芽重量 kg |
| strike_water | 糖化用水 L |
| sparge_water | 洗糟水 L |
| total_water | 总用水 L |
| pre_sparge_sg | 糖化后预计比重（监控目标） |
| pre_boil_sg | 洗糟后预计比重（监控目标） |
| post_boil_sg | 煮沸后预计比重（验证值） |
| pre_boil_volume | 熬煮前体积 L |

sugar_balance[] 四行：

| stage | 说明 |
|-------|------|
| 理论总糖量 | malt_weight × potential_rate |
| 糖化后提取 | × pre_sparge_coefficient |
| 洗糟后收集 | × post_sparge_coefficient |
| 煮沸后收获 | × post_boil_efficiency |

---

## 数据格式（brew_data/*.yaml）

```yaml
metadata:
  date: "2026-02-27"         # YYYY-MM-DD
  recipe_name: "Cold IPA"
  batch_id: "20260227-C-IPA" # 全局唯一

units:
  weight: "kg"
  volume: "L"
  temperature: "C"
  gravity: "SG"

ingredients:
  total_malt_weight: 7.5     # kg
  potential_extract: 0.78    # 综合理论浸出率

mash:
  strike_water: 23           # 糖化用水 L
  water_grain_ratio: 3.06    # 水料比
  target_temperature: 64     # °C
  sparge_water: 7            # 洗糟水 L
  process_logs:              # 糖化过程定时采样
    - time_min: 0
      ph: 5.15
      gravity: 1.037
    - time_min: 40
      ph: 5.24
      gravity: 1.083

measurements:
  pre_sparge:                # 洗糟前（糖化结束时）
    volume: 15
    gravity: 1.084
  pre_boil:                  # 熬煮前（收集完洗糟水后）
    volume: 26
    gravity: 1.067
  post_boil:                 # 熬煮后（入发酵罐前）
    volume: 24
    gravity: 1.075
  final:                     # 发酵结束
    volume: null
    gravity: 1.008
```

---

## 核心公式

```
含糖量:     M_act(V, SG) = 2.5 × (SG - 1) × V × SG
提取系数:    η = M_act(V, SG) / (麦芽重量 × 理论浸出率)
比重反解:    从 M = 2.5×(SG-1)×V×SG 反解 SG（二次方程）
麦芽重量:    W = M_act / η / 理论浸出率
```

提取系数计算用水量选择：
- **洗糟前系数**：使用 `strike_water`（糖化锅初始水量）
- **洗糟后系数**：使用 `strike_water + sparge_water`（总水量）
- **熬煮后效率**：使用实际测量麦汁体积

---

## Agent 使用场景

### 场景 1：酿造前 — 新批次规划

```
1. analyze --json       → 获取最新效率统计
2. design --volume X --sg Y --json → 计算配方
3. add --date ... --recipe ... --json → 创建记录
```

### 场景 2：酿造中 — 过程记录与监控

```
1. record <id> --process-log --time-min 20 --ph 5.3 --gravity 1.060 --json
2. record <id> --process-log --time-min 40 --ph 5.2 --gravity 1.082 --json
3. record <id> --stage pre-sparge --volume 15 --gravity 1.084 --json
4. record <id> --stage pre-boil --volume 26 --gravity 1.067 --json
5. record <id> --stage post-boil --volume 24 --gravity 1.075 --json
```

监控对比：将实际测量值与 `design` 输出的 `pre_sparge_sg`、`pre_boil_sg` 比较，偏差 > 0.003 时建议提醒用户关注。

### 场景 3：酿造后 — 复盘分析

```
1. record <id> --stage final --volume 20 --gravity 1.008 --json
2. show <id> --json       → 查看该批次完整效率
3. analyze --json         → 更新全局效率统计和 CSV
```

### 场景 4：查询历史

```
1. list --json            → 浏览所有批次
2. show <id> --json       → 查看某批次详情
```
