---
title: 3. BO Spread
type: docs
math: true
---

# BO Spread

### **BO Spread (Basis Option Spread，基差期权价差) 详解**

### **定义与构成**

**BO Spread**（Basis Option Spread，基差期权价差）是一种**期权策略**，通过组合不同行权价或到期日的期权合约，间接对冲或投机**基差（Basis）**变动带来的风险。

- **基差（Basis）**：指同一资产的**现货价格（Spot Price）**与**期货价格（Futures Price）**之间的差额（基差 = 现货价 - 期货价）。
- **期权价差（Option Spread）**：同时买入和卖出期权（不同类型或条款）以构建风险/收益组合的策略。

---

### **核心逻辑**

BO Spread 的核心是**利用期权对冲基差波动**（Basis Risk），常见于商品、金融期货等市场。例如：

1. **商品生产商对冲场景**：
    - 持有现货（如原油），担心未来**基差扩大**（期货价下跌或现货价上涨）导致套保失效。
    - 构建看跌期权组合（Put Spread），限制基差不利变动的损失。
2. **投机场景**：
    - 押注基差收敛（如期货贴水转为升水），卖出价外看涨期权（OTM Call）并买入价内看跌期权（ITM Put），赚取基差方向性收益。

### **风险与适用性**

- **优势**：对冲基差不确定性的同时，限制最大损失（权利金成本可控）。
- **劣势**：需精准预测基差方向；需支付期权权利金，交易成本较高。
- **适用场景**：商品生产商、金融机构等需管理基差的实体。

## **案例说明**

以**黄金市场**为例：

---

### **步骤1：当前情况**

1. **现货黄金价格**：$1,800/盎司（你手里有一批黄金现货）。
2. **1个月期货价格**：$1,790/盎司 → **基差=现货-期货=+$10**。
3. **你的担忧**：担心期货价格会从$1,790再跌到$1,775（基差扩大到+$25 → $1,800 - $1,775），导致你套期保值（用期货锁定销售价格）的效果变差。

---

### **步骤2：构建BO Spread（基差期权价差）**

为了对冲期货下跌风险，你决定做一个期权组合：

- **买入看跌期权（Put）**（买保险）：
    - **行权价**：$1,780
    - **到期时间**：1个月
    - **支付权利金（假设）**：$20/盎司
- **卖出看涨期权（Call）**（赚补贴）：
    - **行权价**：$1,800
    - **到期时间**：1个月
    - **收取权利金（假设）**：$15/盎司

**总成本**：$20（买Put）- $15（卖Call）= **净支付$5/盎司**。

---

### **步骤3：盈亏分析**

**情景1：基差扩大（期货跌到$1,775）**

1. **现货端基差损失**：
    - 原基差=+$10 → 现在基差=+$25（期货跌了$15）
    - **损失**：$15/盎司（期货价格下跌导致套保失效）。
2. **期权端的收益**：
    - **买入的Put（$1,780行权价）**：
        - 期货实际价格$1,775 < 行权价$1,780 → **可赚$(1,780 - 1,775) = +$5**。
    - **卖出的Call（$1,800行权价）**：
        - 期货价格$1,775 < 行权价$1,800 → 对方不行权→ **保留$15权利金**。
3. **总盈亏**：
    - **期权收益**：$5（Put赚的钱） + $15（Call权利金）= $20
    - **净收益**：$20（期权） - $15（基差损失） - $5（净权利金成本）= **$0/盎司**→ **结论**：完全对冲了基差损失！

**情景2：基差缩小（期货涨到$1,800，基差消失）**

1. **现货端基差变化**：
    - 基差=+$10 → 基差=0 → **少赚了$10/盎司**。
2. **期权端的盈亏**：
    - **买入的Put（$1,780行权价）**：
        - 期货价格$1,800 > 行权价$1,780 → 期权作废 → **亏$20权利金**。
    - **卖出的Call（$1,800行权价）**：
        - 期货价格$1,800 = 行权价 → 可能被行权 → **需承担损失（假设最终平仓不交割）。**
3. **总盈亏**：
    - **期权净支出**：- $20（Put） + $15（Call）= -$5
    - **基差损失**：-$10/盎司
    - **总亏损**：-$5（期权） - $10（基差） = -$15/盎司

---

### **🎯 对比表格：一目了然**

| **场景** | **期货价格** | **基差变动** | **现货端盈亏** | **期权端盈亏** | **总盈亏（现货+期权）** |
| --- | --- | --- | --- | --- | --- |
| **基差扩大（期货下跌）** | $1,775 | +$15 | -$15 | +$20 | +$5 |
| **基差缩小（期货上涨）** | $1,800 | -$10 | -$10 | -$5 | -$15 |

---

### **📝 总结**

- **BO Spread的用途**：用少量权利金成本（$5/盎司）对冲基差剧烈波动的风险。
- **适用场景**：适合担心基差突然扩大（如商品价格崩盘）的现货持有者。
- **风险**：如果基差方向猜错（如基差缩小），仍需承担额外损失。

---