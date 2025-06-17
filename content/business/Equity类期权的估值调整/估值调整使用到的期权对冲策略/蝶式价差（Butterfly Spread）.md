---
title: 蝶式价差（Butterfly Spread）
type: docs
---

# 蝶式价差（Butterfly Spread）

<aside>
❗

**蝶式价差是一把波动率手术刀，需精确把控标的资产波动范围、时间窗口与交易成本。掌握其数学本质与希腊字母动态，方能在低风险场景中收割时间价值！**
中性策略（Market Neutral），认为标的资产不会显著偏离中间行权价（Central Strike Price K2）。

</aside>

![image.png](%E8%9D%B6%E5%BC%8F%E4%BB%B7%E5%B7%AE%EF%BC%88Butterfly%20Spread%EF%BC%89%201f2d848d2086805787c4ea3de4cb86f1/image.png)

![image.png](%E8%9D%B6%E5%BC%8F%E4%BB%B7%E5%B7%AE%EF%BC%88Butterfly%20Spread%EF%BC%89%201f2d848d2086805787c4ea3de4cb86f1/image%201.png)

<aside>
👉🏻

**上面的图片，可以被理解成，是两份不同的购买策略的组合：**

- **买了K1的call, 买了K3的call**
- **卖了K2的call**

**然后组合一下这两份的策略，就是上面的图。**

</aside>

## **蝶式价差的基本定义**

### **1. 核心逻辑**

- **目标定位**：通过**做空波动率**（Short Volatility），押注标的资产价格在到期日（Expiration）前**窄幅震荡**（Limited Price Movement），捕捉**时间价值衰减**（Time Decay）收益。
- **市场观点**：中性策略（Market Neutral），认为标的资产不会显著偏离中间行权价（Central Strike Price K2）。

### **2. 策略命名与形象比喻**

- **"蝶式"来源**：损益图的对称形状（左右翼）形似蝴蝶翅膀，中间行权价K2对应"蝶身"。
- **各腿关系**：包含四个期权合约（买入2份外侧行权价期权+卖出2份中间行权价期权）。

### **蝶式价差的分类与构建**

---

**1. 看涨蝶式（Call Butterfly）**

**合约组合**：

- **买入（Long）**1份较低行权价K1的Call（左侧翼）。
- **卖出（Short）**2份中间行权价K2的Call（蝶身）。
- **买入（Long）**1份较高行权价K3的Call（右侧翼）。

**2. 看跌蝶式（Put Butterfly）**

**构建逻辑**与Call Butterfly对称（用Put代替Call）：

- **买入**1份K1 Put（左侧翼）。
- **卖出**2份K2 Put。
- **买入**1份K3 Put（右侧翼）。

**3. 铁蝶式（Iron Butterfly）**

**混合构建**（兼顾Call和Put）：

- Long 1份K1 Put（左侧翼）。
- Short 1份K2 Call + Short 1份K2 Put（蝶身）。
- Long 1份K3 Call（右侧翼）。

**优点**：可能降低保证金需求（交易所将Call和Put保证金叠加计算）。

<aside>
👉🏻

**行权价关系**：K1 < K2 < K3，且间隔相等（K2-K1 = K3-K2 = d）。

</aside>

---

### **三、数学原理与损益结构**

### 1. **初始成本预算**

- **净权利金成本**：

$$
\text{Cost} = (C_{K1} + C_{K3} - 2C_{K2}) \quad (\text{Call Butterfly})
$$

$$
  \text{Cost} = (P_{K1} + P_{K3} - 2P_{K2}) \quad (\text{Put Butterfly})
$$

- 实际交易中通常为**净支出**（Debit Spread）。

### 2. **到期日损益公式**

- **Call或Put Butterfly的损益相同**（构建对称性）：

$$
  \text{Profit} = 
  \begin{cases} 
    S_T - K1 - \text{Net Debit} & \text{if } S_T \leq K1 \\
    \text{Max Profit} & \text{if } S_T = K2 \\
    K3 - S_T - \text{Net Debit} & \text{if } S_T \geq K3 \\
    \text{线性插值} & \text{if } K1 < S_T < K2 \text{ 或 } K2 < S_T < K3
  \end{cases}
$$

### 3. **关键价格点量化**

![image.png](%E8%9D%B6%E5%BC%8F%E4%BB%B7%E5%B7%AE%EF%BC%88Butterfly%20Spread%EF%BC%89%201f2d848d2086805787c4ea3de4cb86f1/image%202.png)

### **四、希腊字母动态分析**

蝶式价差具有独特的**多维度风险暴露特征**，需动态管理Greeks：

| **Greek** | **方向与动态行为** | **对冲策略建议** |
| --- | --- | --- |
| **Delta** (Δ) | 在K2附近接近中性，远离K2时Delta绝对值增长 | 调整现货头寸或使用期货对冲 |
| **Gamma** (Γ) | 中间行权价附近Gamma为负（加速损失） | 避免在价格快速波动时持仓 |
| **Theta** (θ) | 每日正向收入（时间价值加速衰减） | 临近到期时Theta收益最大化 |
| **Vega** (ν) | 整体负Vega（波动率上升导致亏损） | 警惕隐含波动率飙升 |

**示例**：若标的价趋近K2，Delta趋近0，Vega和Gamma暴露逐渐平缓；若价格突破K1或K3，Delta迅速扩大，Gamma加速损失。

### **蝶式 vs 其他中性策略**

| **策略** | **蝶式价差** | **铁鹰式（Iron Condor）** | **跨式空头（Short Straddle）** |
| --- | --- | --- | --- |
| **最大盈利** | 最高且集中在中点 | 较低但盈利区间宽 | 无上限但需无限保证金 |
| **希腊字母风险** | 陡峭Gamma曲线 | 更低Vega暴露 | 极高负Gamma和Vega |
| **交易成本** | 需4份合约（高摩擦成本） | 4份合约 | 2份合约 |
| **适用波动率环境** | 极低IV（成本低） | 中等IV | 极高IV（权利金贵） |

---