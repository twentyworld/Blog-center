---
title: README
type: docs
---

# 数据库系统

## 三范式

### 第一范式
在关系模型中，对域添加的一个规范要求，所有的域都应该是原子性的，即数据库表的每一列都是不可分割的原子数据项，而不能是集合，数组，记录等非原子数据项。
### 第二范式
在第一范式的基础上，非码属性必须完全依赖于候选码，**在第一范式基础上消除非主属性对主码的部分函数依赖**。
### 第三范式
在第一范式基础上，任何非主属性不依赖于其它非主属性，**在第二范式基础上消除传递依赖**。
