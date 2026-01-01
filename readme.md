<!--
 * @Author       : zhangle
 * @Date         : 2026-01-01 10:41:04
 * @LastEditors  : zhangle
 * @LastEditTime : 2026-01-01 23:03:29
 * @Description  : happy new year
-->

# 酿造数据分析及配方设计

## Brewhouse Efficiency

$$ \text{Brewhouse Efficiency (\%)} = \frac{ M_\text{Actual Extract Collected}}{ M_\text{Potential Extract from Grains}} \times 100\% $$

eg:
* 10 kg of Pale Malt (Potential extract: 80%)
* 1 kg of Crystal Malt (Potential extract: 74%)
* 麦汁体积50L，sg = 1.050

$$ M_P = 10 \times 80\% + 1 \times 74\% = 8.74 kg$$

$$ \eta_{brewhouse} = \frac{ M_\text{A}(6.5625)}{ M_\text{P}(8.74)} \times 100\%= 75\% $$

## 度量指标

首先，我们需要明确两个基础度量指标：
*   **比重 (Specific Gravity, SG)**：指的是特定温度下，麦汁密度与纯水密度的比值（纯水为 1.000），直观反映了麦汁的“浓度”。
*   **糖度 (Plato/Brix, $^\circ \text{P}$)**：它是一个质量百分比。例如 $12^\circ \text{P}$ 意味着在 $100\,\text{g}$ 的麦汁里，有 $12\,\text{g}$ 是可溶性糖分。

常用经验公式将比重转换为糖度：

$$ P \approx (SG - 1.000) \times 250 $$

## 麦汁含糖量计算公式

将所有步骤整合成一个最终公式。已知麦汁体积为 $V$ (单位：$\text{L}$)，比重为 $SG$：

$$M_{\text{act}}(V, SG) =  M_{\text{wort}} * P / 100$$

其中：麦汁总重量$M_{\text{wort}} = 体积(V) \times 比重(SG)$, 带入经验比重糖度换算经验公式可得：

$$ M_{\text{act}}(V, SG) = 2.5 \times (SG - 1) \times V \times SG $$

### 实例讲解

假设熬煮完成得到 **$50\,\text{L}$** 的麦汁，测得比重为     **$1.050$**：

*   **第一步：求麦汁总重**
    $$50\,\text{L} \times 1.050 = 52.5\,\text{kg}$$
*   **第二步：求麦汁糖度**
    $$(1.050 - 1.000) \times 250 = 12.5^\circ \text{P}（即 12.5\% 的含糖量）$$
*   **第三步：求实际含糖量**
    $$52.5\,\text{kg} \times 12.5\% = 6.5625\,\text{kg}$$

**直接代入通用公式验证：**
$$M_{act} = 2.5 \times 0.05 \times 50 \times 1.050  = 6.5625\,\text{kg}$$

## 效率分析

传统的酿造效率采用最终进罐比重、体积计算整体效率，在整体效率测量的同时，方便对整个酿造过程进行监控和改进，我们加入了两个提取率和一个效率，可以帮助大家更加准确的掌握各个环节的实时效果，方便后续复盘，找出可能得改进之处。

### 洗糟前（糖化）提取率

我们在糖化结束后测量麦汁比重值$SG_\text{洗糟前}$，使用如下公式计洗糟前（糖化）提取率：

$$\eta_{\text{洗糟前}} = \frac{M_{\text{act}}(\text{糖化水量} , SG_{\text{洗糟前}})}{\sum (\text{麦芽重量} \times \text{理论浸出率})}$$

其中：总理论含糖量按实际使用麦芽理论浸出量计算，实际计算时可以简化为：总麦芽量*综合理论浸出率（例如0.78）

这个指标综合反映了糖化过程的质量，衡量的是“淀粉变糖”的效率，即麦芽中的淀粉在酶的作用下转化成了多少可溶性糖。具有测量简单，干扰较小的特点，尤其是无需测量体积（容易受麦芽使用量和麦床残留麦汁干扰）。虽然不同种批次麦芽使用有所区别，但基本偏差不会很大。其表征了从麦芽到麦汁的整体过程效率，受粉碎程度、糖化温度、PH值等因素影响。

### 洗糟后提取率

完成洗糟后测量麦汁，得到当前比重值$SG_\text{洗糟后}$，使用如下公式计算洗糟后提取率：

$$\eta_\text{洗糟后} = \frac{M_{\text{act}}(\text{(糖化水量+洗糟水量)} , SG_{\text{洗糟后}})}{\sum (\text{麦芽重量} \times \text{理论浸出率})}$$

这个指标在洗糟前提取率基础上引入了洗糟的环节，先说结论：洗糟会降低比重，但会提高效率。经过洗糟提取率会上升，洗糟水量越大，提取率上升的越多，如果不洗糟，$\eta_\text{洗糟后} = \eta_{\text{洗糟前}}$。结果略微有些反直觉，可以这样理解：在不增加麦芽（分母不变）的情况下，往煮沸锅里加入了更多糖（分子增加）。

### 煮沸后效率

完成煮沸后测量麦汁，得到当前比重值$SG_\text{煮沸后}$，使用如下公式计算煮沸后效率：

$$E_\text{煮沸后} = \frac{M_{\text{act}}(最终麦汁体积, SG_{\text{煮沸后}})}{\sum (\text{麦芽重量} \times \text{理论浸出率})}$$

注意，这个指标使用了效率而不是提取率，和提取率最重要的区别是计算时使用了最终麦汁体积，而不是糖化+洗糟水量，相比进罐体积，暂时未考虑锅底残留、管路死角等损耗，和前两项指标不具有绝对值上的可比性，用于衡量一次整体的效率。但在理想状态下（不考虑挂壁和蛋白凝固沉淀损失），煮沸后的总糖量应等于煮沸前的总糖量。水分蒸发只是改变了浓度，并没有产生新的糖分，提取率没有提高，但提高了麦汁的浓度。

# 配方设计

经过多次酿造，已经得到如下平均值

* mash_extraction_efficiency糖化后提取率
* sparge_extraction_efficiency洗糟后提取率
* grain_absorption_rate谷物吸收率
* post_boil_efficiency熬煮后效率
* boil_off_volume熬煮蒸发量

这些数值由brew/brewing_metrics_summary.csv读取, 现在根据以上数据进行设计：

输入酿造目标：煮沸后麦汁22L，比重为1.055，假设理论浸出率已知固定为0.78（支持按麦芽种类填写），水料比固定为3.2

1. 由煮沸后效率和浸出率，可计算得到需要麦芽的重量total_malt_weight
2. 根据水料比、total_malt_weight，得到糖化用水量strike_water
3. 根据糖化后提取率、糖化用水量、需要麦芽的重量、理论浸出率，可以估计出糖化后比重，用于过程监控
4. 根据熬煮蒸发量可以计算出熬煮前（洗糟后）体积pre_boil_volume，由grain_absorption_rate = (strike_water + sparge_water - pre_boil_volume) / total_malt_weight，可计算出洗糟水体积sparge_water
5. 可估计出洗糟后比重，用于过程监控