---
title: 跨式组合（Strangle）
type: docs
---
# 跨式组合（Strangle）

![[https://optionalpha.com/strategies/long-strangle](https://optionalpha.com/strategies/long-strangle)](%E8%B7%A8%E5%BC%8F%E7%BB%84%E5%90%88%EF%BC%88Strangle%EF%BC%89%201f2d848d208680b682e4ea6f028207f7/image.png)

[https://optionalpha.com/strategies/long-strangle](https://optionalpha.com/strategies/long-strangle)

![[https://optionalpha.com/strategies/short-strangle](https://optionalpha.com/strategies/short-strangle)](%E8%B7%A8%E5%BC%8F%E7%BB%84%E5%90%88%EF%BC%88Strangle%EF%BC%89%201f2d848d208680b682e4ea6f028207f7/image%201.png)

[https://optionalpha.com/strategies/short-strangle](https://optionalpha.com/strategies/short-strangle)

### **一、策略定义与核心逻辑**

### 1. **基础构成**

- **买入跨式组合（Long Strangle）**：同时买入**虚值认购期权**与**虚值认沽期权** *（行权价不同，位于当前标的价格两侧）。

$$
  \text{成本} = C(K_{\text{Call}}) + P(K_{\text{Put}})
$$

- **卖出跨式组合（Short Strangle）**：卖出上述组合，收取权利金，承担义务。

$$
  \text{收益} = \text{总权利金收入} = C(K_{\text{Call}}) + P(K_{\text{Put}})
$$

### 2. **市场预期与哲学本质**

- **买方逻辑**：押注标的**极端波动**（无论方向），波动幅度超过盈亏平衡点。
如：重大财报、选举结果、央行决议前，隐含波动率（IV）低估时建仓。
- **卖方逻辑**：赌**价格稳定**，IV将因事件结束而坍塌（波动率套利）。
如：IV处于历史高位（IV Rank >80%），事件后价格回归均值。

### **二、损益函数与数学模型**

### 1. **买入跨式到期损益**

$$
\text{Profit} = 
\begin{cases} 
(K_{\text{Put}} - S_T) - \text{Net Debit}, & S_T < K_{\text{Put}} \\ 
-\text{Net Debit}, & K_{\text{Put}} \leq S_T \leq K_{\text{Call}} \\ 
(S_T - K_{\text{Call}}) - \text{Net Debit}, & S_T > K_{\text{Call}} 
\end{cases}
$$

**盈利条件**：

$$
 |S_T - S_0| > \text{盈亏平衡波动幅度}
$$

具体平衡点：

$$
BEP_{\text{lower}} = K_{\text{Put}} + \text{Net Debit} \\ 
BEP_{\text{upper}} = K_{\text{Call}} - \text{Net Debit}
$$

**例**：标的现价100，买入95 Put（支3）和105 Call（支4），总成本7。

→ 下方平衡点：95+7=102（需标的价格≤93才会盈利）；
→上方平衡点：105−7=98（需标的价格≥112才会盈利）。

### 2. **卖出跨式到期损益**

卖方损益与买方相反，最大盈利为权利金总量，但亏损理论无上限。

---

### **三、希腊字母的时空演化**

### 1. **Gamma-Vega敏感度矩阵**

| 区域 | Gamma（曲率） | Vega（波动率暴露） | Theta（时间衰减） |
| --- | --- | --- | --- |
| **价格接近K_Put** | 正且陡增 | 正（买方受益） | 负（时间损） |
| **价格介于两K之间** | 接近零 | 正 | 负 |
| **价格接近K_Call** | 正且陡增 | 正 | 负 |
- **买方痛点**：需价格剧烈波动以抵消双Theta损耗。时间价值每日流失（“双倍衰减”）。
- **卖方优势**：时间天然盟友，但需严密监控尾部风险（Gamma爆炸）。

### 2. **波动率曲面影响（IV Skew）**

- **波动率微笑（Volatility Smile）**：虚值Put常伴随IV高于虚值Call（股灾恐惧溢价）。
买方策略成本结构需匹配IV形态 → 在“微笑”陡峭时慎买跨式（Put可能定价偏高）。

---

### **四、实战场景与案例推演**

### 1. **经典买方案例：2020年原油负价格事件**

- **背景**：2020年4月，WTI原油期货首次跌至负值。
- **假设预判**：某交易者于事件前买入10Put（权利金0.5）和30Call（1.5），总成本$2。
- **结果**：期货暴跌至−37→Put行权价值=10 - (-37)=47，扣除成本净利=47−2=45（2250%回报）。Call失效。
- **启示**：黑天鹅事件中，跨式组合可捕获单侧极端波动。

### 2. **卖方案例：美联储决议后的IV坍缩**

- **前置条件**：
SPX现价4500，IV因联储会议升至35%（历史均值20%）。
卖出4500-4600 Call和4400-4300 Put组合，收取权利金$15。
- **理想结果**：
议息后市场平稳，IV降至22% → 组合价值缩水至5，平仓获利10。
- **风险警示**：若决议后市场暴涨/暴跌，卖方需立即对冲或止损。

---

### **五、高阶增强策略与变体**

### 1. **铁秃鹰（Iron Condor）变形**

- **规则**：卖出跨式组合同时买入更虚值期权保护。

$$
\text{构建} = \text{Short Strangle} + \text{Long OTM Call} + \text{Long OTM Put}
$$

- **效果**：限定最大亏损，但牺牲部分权利金收入。
- **损益比优化**：适用于IV极高但不愿承担无限风险的场景。

### 2. **Gamma Scalping（买方高频对冲）**

1. 建立Long Strangle头寸。
2. 当价格突破Gamma敏感区时，反手交易标的资产对冲Delta。
3. 反复操作，利用波动赚取短线收益，同时保留长尾爆发可能。

**核心公式**：

$$
\text{利润} \approx \frac{1}{2} \Gamma (\Delta S)^2 - \text{交易成本}
$$

---

### **六、致命陷阱与风控框架**

### 1. **买方三大死敌**

- **IV坍塌**：事件后波动率骤降，组合价值腰斩（即使价格波动满足条件）。
- **时间衰减**：持有超30天时，Theta损耗超过潜在Gamma收益。
- **行权价误算**：选择过近的K导致权利金过高，突破需求骤增。

### 2. **卖方末日情景**

- **肥尾事件（Fat Tail）**：如2015年瑞郎脱钩欧元、2021年GameStop轧空，波动超出历史极值。
- **追加保证金（Margin Call）**：价格单边突破时，券商强制平仓引发实际亏损。

### 3. **风控红线规则**

- **买方**：
    - 仅用风险资金的≤2%投入单笔Long Strangle。
    - 事件日前5天建仓，到期前1天平仓（避免归零风险）。
- **卖方**：
    - 保证金覆盖率保持≥200%。
    - 价格突破近期ATR×2时，立即买入平价期权对冲。