<!--
 * @Author       : zhangle
 * @Date         : 2026-01-01 10:41:04
 * @LastEditors  : zhangle
 * @LastEditTime : 2026-01-12 14:04:38
 * @Description  : happy new year
-->

# 酿造数据分析及配方设计

## 0 前言

很多精酿爱好者往往对克隆配方乐此不疲，但很多朋友包括我自己在内，我们对设备的掌握和对酿造过程的理解，真的能够支持我们去“克隆”一款我们感兴趣的配方吗？在我有限的酿造经历中，尝试过各种不同辅助软件进行配方设计，但最终结果经常与我预期存在一定差距，大多数时候我只能被迫忽视这种“随机偏差”。但我始终认为酿造过程不是玄学，不是估计，从麦芽厂商给出的定量报告、到配方中的各种指标，还有几乎每名酿造者都会测量记录的各种过程数据，都在传达着一个核心概念，那就配方是可以被精确实现的，或者说是酿造过程是可以被精准控制的。即便一次结果与预期不符，也能利用定量数据复盘整个过程，知道是哪个环节出了问题，找到原因采取措施，下次得到符合预期的变化。我不仅爱产出的啤酒，也爱设计和酿造的过程。于是我计划用我积累的一点数据结合粗浅的“理论”分析，自娱自乐式的开展一些有趣尝试，使得酿造不只是被动接受，而是通过反思和分析主动去控制和改进。

计划首先从酿造效率分析开始，其意义远远不止于节约成本，这是商酿大批次酿造需要考虑的，无论对于商酿还是家酿，进行酿造效率分析的重要性还在于更加精准的控制初始比重 ，控制好进罐前的麦汁质量，初始比重反映了麦汁的“浓度”，对最终成品的酒精度、麦芽风味和苦甜平衡都影响重大，是我们在酿造早期窥探最终成品质量的一个重要指标。这个指标可以综合反映出，水质调节、麦芽粉碎、糖化、洗糟和煮沸等流程，度量了从麦芽到进罐麦汁这个整个过程，很有必要，也很有趣。

很多软件需要填写酿造效率数值，这个数值本身就属于“魔法值”，需要预估，酿造效率本身又和麦芽种类、研磨程度、糖化设备、洗糟方法等等条件有关，导致初始比重经常和预期存在不可忽视的偏差。本项目，规范了数据记录格式，具备历史数据自动分析和可视化功能，支持基于历史数据辅助进行配方设计，其自动计算得到的每阶段比重预估值，可以用于和实际过程测量值进行比较。方便我定量监控好分析酿造过程，尽早发现可能存在的问题。如果大家感兴趣可以尝试积累一些酿造数据，进行分析得到与自己设备相符的模型，由于水平和业余时间有限，还存很多问题，也欢迎各位自行改造。


## 1 指标定义

### 1.1 Brewhouse Efficiency

$$ \text{Brewhouse Efficiency\%)} = \frac{ M_\text{Actual Extract Collected}}{ M_\text{Potential Extract from Grains}} \times 100\% $$

eg:
* 10 kg of Pale Malt (Potential extract: 80%)
* 1 kg of Crystal Malt (Potential extract: 74%)
* 麦汁体积50L，sg = 1.050

$$ M_P = 10 \times 80\% + 1 \times 74\% = 8.74 kg$$

$$ \eta_{brewhouse} = \frac{ M_\text{A}(6.5625)}{ M_\text{P}(8.74)} \times 100\%= 75\% $$

### 1.2 度量指标

首先，我们需要明确两个基础度量指标：
*   **比重 (Specific Gravity, SG)**：指的是特定温度下，麦汁密度与纯水密度的比值（纯水为 1.000），直观反映了麦汁的“浓度”。
*   **糖度 (Plato/Brix, $^\circ \text{P}$)**：它是一个质量百分比。例如 $12^\circ \text{P}$ 意味着在 $100\,\text{g}$ 的麦汁里，有 $12\,\text{g}$ 是可溶性糖分。

常用经验公式将比重转换为糖度：

$$ P \approx (SG - 1.000) \times 250 $$

### 1.3 麦汁含糖量计算公式

将所有步骤整合成一个最终公式。已知麦汁体积为 $V$ (单位： $\text{L}$)，比重为 $SG$：

$$M_{\text{act}}(V, SG) =  M_{\text{wort}} * P / 100$$

其中：麦汁总重量 $M_{\text{wort}} = \text{体积}(V) \times \text{比重}(SG)$，带入经验比重糖度换算经验公式可得：

$$ M_{\text{act}}(V, SG) = 2.5 \times (SG - 1) \times V \times SG $$

#### 实例讲解

假设熬煮完成得到 **$50\,\text{L}$** 的麦汁，测得比重为     **$1.050$**：

*   **第一步：求麦汁总重**
    $$50\,\text{L} \times 1.050 = 52.5\,\text{kg}$$
*   **第二步：求麦汁糖度**
    $$(1.050 - 1.000) \times 250 = 12.5^\circ \text{P}（即 12.5\% 的含糖量）$$
*   **第三步：求实际含糖量**
    $$52.5\,\text{kg} \times 12.5\% = 6.5625\,\text{kg}$$

**直接代入通用公式验证：**
$$M_{act} = 2.5 \times 0.05 \times 50 \times 1.050  = 6.5625\,\text{kg}$$

## 2 效率分析

传统的酿造效率采用最终进罐比重、体积计算整体效率，在整体效率测量的同时，方便对整个酿造过程进行监控和改进，我们加入了两个提取系数和一个效率，可以帮助大家更加准确的掌握各个环节的实时效果，方便后续复盘，找出可能得改进之处。

### 2.1 洗糟前（糖化）提取系数

我们在糖化结束后测量麦汁比重值 $SG_\text{洗糟前}$，使用如下公式计洗糟前（糖化）提取系数：

$$\eta_{\text{洗糟前}} = \frac{M_{\text{act}}(\text{糖化锅初始水量} , SG_{\text{洗糟前}})}{\sum (\text{麦芽重量} \times \text{理论浸出率})}$$

其中：总理论含糖量按实际使用麦芽理论浸出量计算，实际计算时可以简化为：总麦芽量*综合理论浸出率（例如0.78）

这个指标综合反映了糖化过程的质量，衡量的是“淀粉变糖”的效率，即麦芽中的淀粉在酶的作用下转化成了多少可溶性糖。在糖化结束后一部分淀粉无法转化为糖分，未溶解在麦汁中，这是提取系数小于1的主要原因。注意使用糖化锅初始水量计算，无需测量糖化后体积（容易受麦芽使用量和麦床残留麦汁干扰）。度量了从麦芽到麦汁的整体过程效率，受粉碎程度、糖化温度、PH值等因素影响。

### 2.2 洗糟后提取系数

完成洗糟后测量麦汁，得到当前比重值 $SG_\text{洗糟后}$，使用如下公式计算洗糟后提取系数：

$$\eta_\text{洗糟后} = \frac{M_{\text{act}}(\text{(糖化锅初始水量+洗糟水量)} , SG_{\text{洗糟后}})}{\sum (\text{麦芽重量} \times \text{理论浸出率})}$$

麦汁的糖分会残留在麦床中，而洗糟过程的目的就是从麦床将残留的糖“冲洗”出来。但由于最终麦糟中还有残留糖分，也会造成效率损失。这个指标度量了糖化环节加上洗糟环节的总效率，受第一阶段提取率，和设备（麦床）形状、洗糟水温度、洗糟时间等因素影响。注意这个指标会大于1，因为比重使用了麦汁比重，但水量使用了总用水量，这导致绝对值本身没有物理意义。这样选择的原因还是为了进行内部比较与工艺控制，尽量排除误差较大的洗糟后麦汁体积作为输入。

### 2.3 煮沸后效率

完成煮沸后测量麦汁，得到当前比重值 $SG_\text{煮沸后}$，使用如下公式计算煮沸后效率：

$$E_\text{煮沸后} = \frac{M_{\text{act}}(最终麦汁体积, SG_{\text{煮沸后}})}{\sum (\text{麦芽重量} \times \text{理论浸出率})}$$

注意，这个指标使用了效率而不是提取率，计算时使用了最终糖化锅内麦汁体积，与进罐体积相比，暂时未考虑锅底残留、管路死角等损耗，用于衡量进罐前整体效率。

## 3 配方设计

### 3.1 历史数据获取

经过多次酿造，后运行BrewMetrics/batch_efficiency_analyzer.ipynb，可计算得到如下经验值（存储在brew/brewing_metrics_summary.csv中）

- pre_sparge_coefficient(洗糟前提取系数)
- post_sparge_coefficient(洗糟后提取系数)
- grain_absorption_rate(谷物吸收率)
- post_boil_efficiency(熬煮后效率)
- boil_off_volume(熬煮蒸发量)

### 3.2 开展配方设计

根据以上数据进行设计，按以下过程可开展配方设计

输入为：煮沸后目标麦汁，目标比重，假设理论浸出率已知固定（支持按麦芽种类填写），水料比固定

1. 由煮沸后效率和浸出率，可计算得到需要麦芽的重量total_malt_weight
2. 根据水料比、total_malt_weight，得到糖化用水量strike_water
3. 根据熬煮蒸发量可以计算出熬煮前（洗糟后）体积pre_boil_volume，由grain_absorption_rate*total_malt_weight = (strike_water + sparge_water - pre_boil_volume) ，可计算出洗糟水体积sparge_water
4. 根据pre_sparge_coefficient、strike_water、total_malt_weight、理论浸出率，可以估计出糖化后比重，用于过程监控
5. 根据post_sparge_coefficient、strike_water、sparge_water、total_malt_weight、理论浸出率，可以估计洗糟后比重，用于过程监控
   
## 4 酿造实例

### 4.1 配方设计

按如下目标和系数开展配方设计：

目标值：
- V_final = 22.0 L
- SG_final = 1.060

已用常数/系数
- pre_sparge_coefficient = 0.7077
- post_sparge_coefficient = 0.7947
- grain_absorption_rate = 0.862 L/kg
- post_boil_efficiency = 0.6869
- boil_off_volume = 1.70 L
- 水料比 W/G = 3.2 L/kg
- 理论浸出率 = 0.78

计算结果（保留适当位数）

1) 目标进罐可溶糖质量（M_act_final）
- M_act_final = 2.5 × (SG − 1) × V × SG = 2.5 × 0.06 × 22 × 1.06 = 3.498 kg

2) 需要的总麦芽量 total_malt_weight
- total_malt_weight = M_act_final / (理论浸出率 × post_boil_efficiency) = 3.498 / (0.78 × 0.6869) ≈ 6.53 kg

3) 糖化用水 strike_water
- strike_water = W/G × total_malt_weight = 3.2 × 6.53 ≈ 20.90 L

4) 熬煮前体积 pre_boil_volume
- pre_boil_volume = V_final + boil_off_volume = 22.00 + 1.70 = 23.70 L

5) 谷物吸水量
- grain_absorption = 0.862 × total_malt_weight ≈ 0.862 × 6.53 ≈ 5.63 L

6) 洗糟水量 sparge_water
- sparge_water = pre_boil_volume − strike_water + grain_absorption = 23.70 − 20.90 + 5.63 ≈ 8.43 L
- 总用水 ≈ strike + sparge ≈ 20.90 + 8.43 = 29.33 L

7) 理论总可溶糖（麦芽 × 理论浸出率）
- total_theoretical_sugar = 6.53 × 0.78 ≈ 5.094 kg

8) 糖化结束（洗糟前）可溶糖与预测比重（用于过程监控）
- M_act_pre ≈ pre_sparge_coefficient × total_theoretical_sugar = 0.7077 × 5.094 ≈ 3.605 kg
- 求解 2.5·(SG_pre − 1)·V_strike·SG_pre = M_act_pre，V_strike = strike_water ≈ 20.90 L
- 得 SG_pre ≈ 1.0648

9) 洗糟后可溶糖与预测比重（用于过程监控）
- M_act_post ≈ post_sparge_coefficient × total_theoretical_sugar = 0.7947 × 5.094 ≈ 4.048 kg
- 用 V_total = strike + sparge ≈ 29.33 L 解得 SG_post ≈ 1.0520

关键汇总（近似）
- 总麦芽量：≈ 6.53 kg (可按实际称量偏好取 6.50 或 6.55 kg)
- 糖化用水（strike）：≈ 20.90 L
- 洗糟水（sparge）：≈ 8.43 L
- 熬煮前体积（pre-boil）：23.70 L
- 目标煮后体积：22.00 L
- 目标煮后比重：1.060
- 预计糖化结束比重（pre-sparge）：≈ 1.065
- 预计洗糟后比重（post-sparge）：≈ 1.052

### 4.2 实际酿造结果

## 5 分析及结论