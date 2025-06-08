

# Flink 是真的不错

- [Flink 是真的不错](#flink-是真的不错)
- [一、Flink 架构](#一flink-架构)
  - [有界、无界（统一）](#有界无界统一)
  - [架构和拓扑](#架构和拓扑)
- [二、Flink 应用层面](#二flink-应用层面)
  - [Flink 是有状态的](#flink-是有状态的)
- [三、广义Flink应用场景](#三广义flink应用场景)
- [四、Flink 一些关键词](#四flink-一些关键词)
  - [时间语义 Time](#时间语义-time)
  - [**窗口 Window**](#窗口-window)
  - [Watermark(这个词比较难翻译，水位线、水印)](#watermark这个词比较难翻译水位线水印)
  - [Side Outputs 旁路输出](#side-outputs-旁路输出)
  - [状态 State 和 CheckPoint 机制](#状态-state-和-checkpoint-机制)
  - [内存管理](#内存管理)
  - [启动机制](#启动机制)
  - [背压(也译作反压) Back Pressure](#背压也译作反压-back-pressure)
- [五、使用](#五使用)
  - [数据源](#数据源)
  - [DataStream](#datastream)
  - [KeyedStream](#keyedstream)
- [六、横向对比](#六横向对比)
    - [**社区能力**](#社区能力)
    - [**架构**](#架构)
    - [**事件时间**](#事件时间)
    - [**容错机制**](#容错机制)
    - [**共同点**](#共同点)
- [在投放这边有什么适应场景吗？](#在投放这边有什么适应场景吗)
- [我司如何上线，使用的怎么样](#我司如何上线使用的怎么样)
- [聊聊Flink的社区，以及Flink的展望](#聊聊flink的社区以及flink的展望)
  - [Flink的社区环境](#flink的社区环境)
  - [Flink的未来](#flink的未来)
- [引用](#引用)

**Apache Flink is a framework and distributed processing engine for stateful computations over** _**unbounded and bounded**_ **data streams. Flink has been designed to run in** _**all common cluster environments**_**, perform computations at** _**in-memory speed**_ **and at** _**any scale**_**.**

> Apache Flink 是一个在无界和有界数据流上进行状态计算的框架和分布式处理引擎。 Flink 已经可以在所有常见的集群环境中运行，并以 in-memory 的速度和任意的规模进行计算。

Flink 起始于2010年，有很多关于实时系统里面的概念都是先于世界。基本上可以总结一下：实时计算方向，全世界一个能打的都没有。**如果现在存在没有接入Flink的系统，要么是已经上线的系统老旧，要么是技术负责人老旧。Flink无差别兼容其他实时系统。**

\-- 一次Flink在上海的技术峰会，一个CTO的过激言论。

# 一、Flink 架构  
## 有界、无界（统一）

======================

**Flink 认为 有界流是一种特殊的无界流。**

换句话来说，其实 有界无界并没有完全的融合。

打开DataSet和DataStream两个类，二者支持的API都非常丰富且十分类似，比如常用的map、fliter、join等常见的transformation函数。但是并没有合并的打算，其主要目的是持有更多的能力，进一步挤占兄弟的市场。

对于DataSet而言，Source部分来源于文件、表或者Java集合；而DataStream的Source来源于一般都是消息中间件比如Kafka等。由于Flink DataSet和DataStream API的高度相似，就不重复介绍了，显得文章过于陈冗。下面介绍的举例，主要以DataStream为主。

架构和拓扑
-----

当 Flink 集群启动后，首先会启动一个 JobManger 和一个或多个的 TaskManager。由 Client 提交任务给 JobManager，JobManager 再调度任务到各个 TaskManager 去执行，然后 TaskManager 将心跳和统计信息汇报给 JobManager。TaskManager 之间以流的形式进行数据的传输。上述三者均为独立的 JVM 进程。

![](https://km.sankuai.com/api/file/cdn/483965620/486648343?contentType=1&isNewContent=false&isNewContent=false)

*   **Client** 为提交 Job 的客户端，可以是运行在任何机器上（与 JobManager 环境连通即可）。提交 Job 后，Client 可以结束进程（Streaming的任务），也可以不结束并等待结果返回。
    
*   **JobManager** 主要负责调度 Job 并协调 Task 做 checkpoint，职责上很像 Storm 的 Nimbus。从 Client 处接收到 Job 和 JAR 包等资源后，会生成优化后的执行计划，并以 Task 的单元调度到各个 TaskManager 去执行。
    
*   **TaskManager** 在启动的时候就设置好了槽位数（Slot），每个 slot 能启动一个 Task，Task 为线程。从 JobManager 处接收需要部署的 Task，部署启动后，与自己的上游建立 Netty 连接，接收数据并处理。
    

这种架构方式，与storm倒是存在不同，感觉可能要优化。虽然这种方式可以有效提高 CPU 利用率，但是个人不太喜欢这种设计，因为不仅缺乏资源隔离机制，同时也不方便调试。类似 Storm 的进程模型，一个JVM 中只跑该 Job 的 Tasks 实际应用中更为合理。

> 如果正常启动一个Flink Job，在web上执行时，web会暴露一些简单的逻辑执行计划图。如果有兴趣可以去试试。然后print DataStream 去[https://flink.apache.org/visualizer/](https://flink.apache.org/visualizer/)展示一下数据。

**Flink 中的执行图可以分成四层：StreamGraph -> JobGraph -> ExecutionGraph -> 物理执行图。**

*   **StreamGraph：**是根据用户通过 Stream API 编写的代码生成的最初的图。用来表示程序的拓扑结构。
    
*   **JobGraph：**StreamGraph经过优化后生成了 JobGraph，提交给 JobManager 的数据结构。主要的优化为，将多个符合条件的节点 chain 在一起作为一个节点，这样可以减少数据在节点之间流动所需要的序列化/反序列化/传输消耗。
    
*   **ExecutionGraph：**JobManager 根据 JobGraph 生成ExecutionGraph。ExecutionGraph是JobGraph的并行化版本，是调度层最核心的数据结构。
    
*   **物理执行图：**JobManager 根据 ExecutionGraph 对 Job 进行调度后，在各个TaskManager 上部署 Task 后形成的“图”，并不是一个具体的数据结构。
    

以有两个并行度的operator为例

![](https://km.sankuai.com/api/file/cdn/483965620/486901213?contentType=1&isNewContent=false&isNewContent=false)

**StreamGraph**：根据用户通过 Stream API 编写的代码生成的最初的图。

*   StreamNode：用来代表 operator 的类，并具有所有相关的属性，如并发度、入边和出边等。
    
*   StreamEdge：表示连接两个StreamNode的边。
    

**JobGraph：**StreamGraph经过优化后生成了 JobGraph，提交给 JobManager 的数据结构。

*   JobVertex：经过优化后符合条件的多个StreamNode可能会chain在一起生成一个JobVertex，即一个JobVertex包含一个或多个operator，JobVertex的输入是JobEdge，输出是IntermediateDataSet。
    
*   IntermediateDataSet：表示JobVertex的输出，即经过operator处理产生的数据集。producer是JobVertex，consumer是JobEdge。
    
*   JobEdge：代表了job graph中的一条数据传输通道。source 是 IntermediateDataSet，target 是 JobVertex。即数据通过JobEdge由IntermediateDataSet传递给目标JobVertex。
    

**ExecutionGraph：**JobManager 根据 JobGraph 生成ExecutionGraph。ExecutionGraph是JobGraph的并行化版本，是调度层最核心的数据结构。

*   ExecutionJobVertex：和JobGraph中的JobVertex一一对应。每一个ExecutionJobVertex都有和并发度一样多的 ExecutionVertex。
    
*   ExecutionVertex：表示ExecutionJobVertex的其中一个并发子任务，输入是ExecutionEdge，输出是IntermediateResultPartition。
    
*   IntermediateResult：和JobGraph中的IntermediateDataSet一一对应。一个IntermediateResult包含多个IntermediateResultPartition，其个数等于该operator的并发度。
    
*   IntermediateResultPartition：表示ExecutionVertex的一个输出分区，producer是ExecutionVertex，consumer是若干个ExecutionEdge。
    
*   ExecutionEdge：表示ExecutionVertex的输入，source是IntermediateResultPartition，target是ExecutionVertex。source和target都只能是一个。
    
*   Execution：是执行一个 ExecutionVertex 的一次尝试。当发生故障或者数据需要重算的情况下 ExecutionVertex 可能会有多个 ExecutionAttemptID。一个 Execution 通过 ExecutionAttemptID 来唯一标识。JM和TM之间关于 task 的部署和 task status 的更新都是通过 ExecutionAttemptID 来确定消息接受者。
    

**物理执行图：**JobManager 根据 ExecutionGraph 对 Job 进行调度后，在各个TaskManager 上部署 Task 后形成的“图”，并不是一个具体的数据结构。

*   Task：Execution被调度后在分配的 TaskManager 中启动对应的 Task。Task 包裹了具有用户执行逻辑的 operator。
    
*   ResultPartition：代表由一个Task的生成的数据，和ExecutionGraph中的IntermediateResultPartition一一对应。
    
*   ResultSubpartition：是ResultPartition的一个子分区。每个ResultPartition包含多个ResultSubpartition，其数目要由下游消费 Task 数和 DistributionPattern 来决定。
    
*   InputGate：代表Task的输入封装，和JobGraph中JobEdge一一对应。每个InputGate消费了一个或多个的ResultPartition。
    
*   InputChannel：每个InputGate会包含一个以上的InputChannel，和ExecutionGraph中的ExecutionEdge一一对应，也和ResultSubpartition一对一地相连，即一个InputChannel接收一个ResultSubpartition的输出。
    

现在再重新看一张图：

JobGraph 之上除了 StreamGraph 还有 OptimizedPlan。OptimizedPlan 是由 Batch API 转换而来的。StreamGraph 是由 Stream API 转换而来的。为什么 API 不直接转换成 JobGraph？因为，Batch 和 Stream 的图结构和优化方法有很大的区别，比如 Batch 有很多执行前的预分析用来优化图的执行，而这种优化并不普适于 Stream，所以通过 OptimizedPlan 来做 Batch 的优化会更方便和清晰，也不会影响 Stream。JobGraph 的责任就是统一 Batch 和 Stream 的图，用来描述清楚一个拓扑图的结构，并且做了 chaining 的优化，chaining 是普适于 Batch 和 Stream 的，所以在这一层做掉。ExecutionGraph 的责任是方便调度和各个 tasks 状态的监控和跟踪，所以 ExecutionGraph 是并行化的 JobGraph。而“物理执行图”就是最终分布式在各个机器上运行着的tasks了。所以可以看到，这种解耦方式极大地方便了我们在各个层所做的工作，各个层之间是相互隔离的。

如果想对底层架构有更多的认识，可以参见一些网络资源。关于一些更加底层的东西：选Job manager leader、上面的图的创建、使用之类的工作。本文不牵涉太深。

二、Flink 应用层面
============

> 引用自：官方文档：[Apache Flink 是什么？](https://flink.apache.org/zh/flink-applications.html)

分层API

> 下面我说的基本上每一个术语、接口、能力，都是可以定制、重写的，这一点是我感觉Flink比较厉害的。

*   ProcessFunction：[ProcessFunction](https://ci.apache.org/projects/flink/flink-docs-stable/dev/stream/operators/process_function.html)是 Flink 所提供的最具表达力的接口。ProcessFunction 可以处理一或两条输入数据流中的单个事件或者归入一个特定窗口内的多个事件。它提供了对于时间和状态的细粒度控制。开发者可以在其中任意地修改状态，也能够注册定时器用以在未来的某一时刻触发回调函数。因此，你可以利用 ProcessFunction 实现许多[有状态的事件驱动应用](https://flink.apache.org/zh/usecases.html#eventDrivenApps)所需要的基于单个事件的复杂业务逻辑。
    
*   DataStream API: [DataStream API](https://ci.apache.org/projects/flink/flink-docs-stable/dev/datastream_api.html) 为许多通用的流处理操作提供了处理原语。这些操作包括窗口、逐条记录的转换操作，在处理事件时进行外部数据库查询等。DataStream API 支持 Java 和 Scala 语言，预先定义了例如map()、reduce()、aggregate() 等函数。你可以通过扩展实现预定义接口或使用 Java、Scala 的 lambda 表达式实现自定义的函数。
    
*   SQL & Table API: Flink 支持两种关系型的 API，[Table API 和 SQL](https://ci.apache.org/projects/flink/flink-docs-stable/dev/table/index.html)。这两个 API 都是批处理和流处理统一的 API，这意味着在无边界的实时数据流和有边界的历史记录数据流上，关系型 API 会以相同的语义执行查询，并产生相同的结果。Table API 和 SQL 借助了 [Apache Calcite](https://calcite.apache.org/) 来进行查询的解析，校验以及优化。它们可以与 DataStream 和 DataSet API 无缝集成，并支持用户自定义的标量函数，聚合函数以及表值函数。
    

说点题外话, 以我接触的众多 数据based 技术产品而言，大家一般都在做一个原则，就是一般都要支持SQL。

1.  Blink最近一年都在合并到Flink，主要优化点（甚至可以说核心代码的全部）都是提高了SQL映射到ExecutionGraph上的能力。阿里买了Flink的母公司也是为了不能让任何人影响他做技术影响力输出。
    
2.  更奇怪的，基本上现在所有的技术框架都在支持SQL的最主要目的有两个：
    
    *   有一部分人不会写代码，但是还想要自己去操作，脑子的需求一个接一个，手里的SQL都可以适配 (这个就厉害了，我以前的BA(就是产品)是 各种SQL、报表生成，各种B工具玩的溜得飞起. 我们国内的BA就啥都不会)
        
    *   有一部分人不能接受需求到上线之间的时间鸿沟，SQL可以弥补这些（也包括Flink搞的其他的上层API）
        

**但是下面将要表述的一般性原则，或者一般性Flink热点技术，是基于底层API的，甚至DataStream API都相对少。敬请原谅**

Flink 是有状态的
-----------

有状态、无状态的产品，在解决业务能力上有天差地别的影响力。

Flink 中的算子可以是有状态的。这意味着如何处理一个事件可能取决于该事件之前所有事件数据的累积结果。Flink 中的状态不仅可以用于简单的场景（例如统计仪表板上每分钟显示的数据），也可以用于复杂的场景（例如训练作弊检测模型）。

涉及到有状态的应用的容错，尤其是实时计算而言，向来比较复杂。关于Flink是如何做到的，会在后面说。

通过状态快照和流重放两种方式的组合，Flink 能够提供可容错的，精确一次计算的语义。这些状态快照在执行时会获取并存储分布式 pipeline 中整体的状态，它会将数据源中消费数据的偏移量记录下来，并将整个 job graph 中算子获取到该数据（记录的偏移量对应的数据）时的状态记录并存储下来。当发生故障时，Flink 作业会恢复上次存储的状态，重置数据源从状态中记录的上次消费的偏移量开始重新进行消费处理。而且状态快照在执行时会异步获取状态并存储，并不会阻塞正在进行的数据处理逻辑。

三、广义Flink应用场景
=============

事件驱动应用

数据分析

ETL（数据管道-> 提取 - 转换 - 加载）

要不大家直接去看文档吧，Flink的文档，写的不咋地。因为现在还在上升期，所以一些文档做的还是不怎么好，但是tutorial还是写的不错的。

四、Flink 一些关键词
=============

时间语义 Time
---------

> [流式分析](https://ci.apache.org/projects/flink/flink-docs-master/zh/learn-flink/streaming_analytics.html). 应该不算抄

Flink 明确支持以下三种时间语义:

*   _事件时间(event time)：_ 事件产生的时间，记录的是设备生产(或者存储)事件的时间
    
*   _摄取时间(ingestion time)：_ Flink 读取事件时记录的时间
    
*   _处理时间(processing time)：_ Flink pipeline 中具体算子处理事件的时间
    

这三种语义表明了实时数据处理的要求。换句话说，目前一般而言，实时数据处理应用在接入Flink时，都是带有**时间维度上的需求。Flink默认使用的是processing time。如果需要使用event time，是要显式设置的：**

代码块

Java

env.setStreamTimeCharacteristic(TimeCharacteristic.EventTime);

**窗口 Window**
-------------

> 扩展阅读：[https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/windows.html](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/windows.html)

*   滑动窗口、滚动窗口、session window
    
*   WindowAssigner、Trigger、Evictor
    

上面是一些流处理工具都应该具有的能力。

下面简单说一下Window的实现原理：

首先上图中的组件都位于一个算子（window operator）中，数据流源源不断地进入算子，每一个到达的元素都会被交给 WindowAssigner。WindowAssigner 会决定元素被放到哪个或哪些窗口（window），可能会创建新窗口。因为一个元素可以被放入多个窗口中，所以同时存在多个窗口是可能的。注意，Window本身只是一个ID标识符，其内部可能存储了一些元数据，如TimeWindow中有开始和结束时间，但是并不会存储窗口中的元素。窗口中的元素实际存储在 Key/Value State 中，key为Window，value为元素集合（或聚合值）。为了保证窗口的容错性，该实现依赖了 Flink 的 State 机制（参见 [state 文档](https://ci.apache.org/projects/flink/flink-docs-master/apis/streaming/state.html)）。

每一个窗口都拥有一个属于自己的 Trigger，Trigger上会有定时器，用来决定一个窗口何时能够被计算或清除。每当有元素加入到该窗口，或者之前注册的定时器超时了，那么Trigger都会被调用。Trigger的返回结果可以是 continue（不做任何操作），fire（处理窗口数据），purge（移除窗口和窗口中的数据），或者 fire + purge。一个Trigger的调用结果只是fire的话，那么会计算窗口并保留窗口原样，也就是说窗口中的数据仍然保留不变，等待下次Trigger fire的时候再次执行计算。一个窗口可以被重复计算多次知道它被 purge 了。在purge之前，窗口会一直占用着内存。

当Trigger fire了，窗口中的元素集合就会交给Evictor（如果指定了的话）。Evictor 主要用来遍历窗口中的元素列表，并决定最先进入窗口的多少个元素需要被移除。剩余的元素会交给用户指定的函数进行窗口的计算。如果没有 Evictor 的话，窗口中的所有元素会一起交给函数进行计算。

如果有时间，可以看一下源码实现，关于 WindowAssigner、Trigger、Evictor的实现原理还是比较简单的。

我以大家在阅读一些资料时常使用的一些使用方式为例，介绍一下代码的行文逻辑：

Count Window 实现

```java
// tumbling count window
public WindowedStream<T, KEY, GlobalWindow\> countWindow(long size) {
 return window(GlobalWindows.create())  // create window stream using GlobalWindows
 .trigger(PurgingTrigger.of(CountTrigger.of(size))); // trigger is window size
}
```

```java
// sliding count window
public WindowedStream<T, KEY, GlobalWindow\> countWindow(long size, long slide) {
 return window(GlobalWindows.create())
 .evictor(CountEvictor.of(size))  // evictor is window size
 .trigger(CountTrigger.of(slide)); // trigger is slide size
}
```

第一个函数是申请翻滚计数窗口，参数为窗口大小。第二个函数是申请滑动计数窗口，参数分别为窗口大小和滑动大小。它们都是基于 GlobalWindows 这个 WindowAssigner 来创建的窗口，该assigner会将所有元素都分配到同一个global window中，所有GlobalWindows的返回值一直是 GlobalWindow 单例。基本上自定义的窗口都会基于该assigner实现。

翻滚计数窗口并不带evictor，只注册了一个trigger。该trigger是带purge功能的 CountTrigger。也就是说每当窗口中的元素数量达到了 window-size，trigger就会返回fire+purge，窗口就会执行计算并清空窗口中的所有元素，再接着储备新的元素。从而实现了tumbling的窗口之间无重叠。

滑动计数窗口的各窗口之间是有重叠的，但我们用的 GlobalWindows assinger 从始至终只有一个窗口，不像 sliding time assigner 可以同时存在多个窗口。所以trigger结果不能带purge，也就是说计算完窗口后窗口中的数据要保留下来（供下个滑窗使用）。另外，trigger的间隔是slide-size，evictor的保留的元素个数是window-size。也就是说，每个滑动间隔就触发一次窗口计算，并保留下最新进入窗口的window-size个元素，剔除旧元素。

Watermark(这个词比较难翻译，水位线、水印)
--------------------------

假设这个流的数字代表了事件时间。但是流入的顺序被乱序了，在处理这些数据之前，一定要先做排序。可以思考一下Flink是如何做的排序的。Flink找了很简单的办法，现持有数据，等一会儿，不要着急把数据给分发出去。

就是这么个简单的工作，这里面牵涉到了一些balance， **延迟和正确性，流处理都有这个问题，如果对一个有要求，就势必要放弃另一个。watermarks 最接近的翻译叫：水印。就是给每一个事件都打一个时间戳，让Flink事件带有的时间戳，然后排序。**

```java

```

Side Outputs 旁路输出
-----------------

一般只有一些底层操作方法(RichFunction)才会支持旁路输出。\*\*ProcesFunction.

旁路输出是指：如果有一些事件延迟了超过了watermark最大允许乱序时间，这时，一些对数据的真实度容忍能力很低的系统而言，可以通过旁路输出的方式去做补偿。

状态 State 和 CheckPoint 机制
------------------------

[State 和 CheckPoint机制（深究可以自行阅读官方文档）](https://km.sankuai.com/page/486174401)

内存管理
----

> 引用自：[https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/asyncio.html](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/asyncio.html)

给大家简要说说都做了什么吧。面临问题，很多的组件使用的都是JVM作为底层进程。好处固然很多，但是有一些问题。比如：

1.  空间浪费。Boolean占据16字节，8字节的对象头，1字节的boolean， 对象填充7字节。但是，实际上，只需要一个bit就够了，浪费空间 16 \* 8 - 1个bit。
    
2.  Full GC 影响性能，尤其是实时计算系统。在内存动辄几十上百G的GC操作，会花费分钟级的时间。
    
3.  OOM问题，这个不分技术，分人。但是问题的确在。
    

其实数据方向的工具现在都在做自己的内存管理，这其中也包括Flink。

Flink做了很多的工作，其中包括：

*   申请内存池（用完释放，给其他计算提供资源）
    
*   数据过大，使用逻辑视图存储到磁盘，防止OOM.
    
*   优化内存存储，通过便宜量查询到数据
    
*   量身定制的序列化框架
    

当然，还有最重要的，堆外内存：超大内存JVM启动不受影响、高效IO（zero-copy）、内存多进程共享。或者换句话来说，对外内存很适合这种分布式大堆的框架。

启动机制
----

背压(也译作反压) Back Pressure
-----------------------

**Flink 没有使用任何复杂的机制来解决反压问题，因为根本不需要那样的方案！它利用自身作为纯数据流引擎的优势来优雅地响应反压问题。**

Storm的背压比较水，通过zk来协调.

Storm 是通过监控 Bolt 中的接收队列负载情况，如果超过高水位值就会将反压信息写到 Zookeeper ，Zookeeper 上的 watch 会通知该拓扑的所有 Worker 都进入反压状态，最后 Spout 停止发送 tuple。具体实现可以看这个 JIRA [STORM-886](https://github.com/apache/storm/pull/700)。

Jstrom 减轻了zk的压力，但是也是通过通知所有worker进入反压状态来完成反压场景的。

Flink 在运行时主要由 **operators** 和 **streams** 两大组件构成。每个 operator 会消费中间态的流，并在流上进行转换，然后生成新的流。对于 Flink 的网络机制一种形象的类比是，Flink 使用了高效有界的分布式阻塞队列，就像 Java 通用的阻塞队列（BlockingQueue）一样。一个较慢的接受者会降低发送者的发送速率，因为一旦队列满了（有界队列）发送者会被阻塞。Flink 解决反压的方案就是这种感觉。

在 Flink 中，这些分布式阻塞队列就是这些逻辑流，而队列容量是通过缓冲池（LocalBufferPool）来实现的。每个被生产和被消费的流都会被分配一个缓冲池。缓冲池管理着一组缓冲(Buffer)，缓冲在被消费后可以被回收循环利用。

内部实现：Netty 水位值机制

当输出缓冲中的字节数超过了高水位值, 则 Channel.isWritable() 会返回false。当输出缓存中的字节数又掉到了低水位值以下, 则 Channel.isWritable() 会重新返回true。Flink 中发送数据的核心代码在 PartitionRequestQueue 中，该类是 server channel pipeline 的最后一层。发送数据关键代码如下所示。

官方 背压benchmark: [How Apache Flink™ handles backpressure](https://www.ververica.com/blog/how-flink-handles-backpressure)， 在这里放一张图就够了。

> The figure shows the average throughput as a percentage of the maximum attained throughput (**we achieved up to 8 million elements per second in the single JVM**) of the producing (yellow) and consuming (green) tasks as it varies by time. To measure average throughput, we measure the number of records processed by the tasks every 5 seconds.

首先，我们运行生产task到它最大生产速度的60%（我们通过Thread.sleep()来模拟降速）。消费者以同样的速度处理数据。然后，我们将消费task的速度降至其最高速度的30%。你就会看到背压问题产生了，正如我们所见，生产者的速度也自然降至其最高速度的30%。接着，停止消费task的人为降速，之后生产者和消费者task都达到了其最大的吞吐。接下来，我们再次将消费者的速度降至30%，pipeline给出了立即响应：生产者的速度也被自动降至30%。最后，我们再次停止限速，两个task也再次恢复100%的速度。总而言之，我们可以看到：生产者和消费者在 pipeline 中的处理都在跟随彼此的吞吐而进行适当的调整，这就是我们希望看到的反压的效果。

\-- 翻译片段 [How Apache Flink™ handles backpressure](https://www.ververica.com/blog/how-flink-handles-backpressure)

五、使用
====

> 以DataStream API为例

废话不多说，先上代码（一个价值老钱的项目，都在这及时行代码里面）

Java

 private void run() {

 dataSourcePopulator.populateDatabase();

 System.out.println("list" + listeningTopic);



 StreamExecutionEnvironment env \= StreamExecutionEnvironment.getExecutionEnvironment();



 FlinkKafkaConsumer011<String\> consumer \= FlinkKafkaConsumerFactory.getFlinkKafkaConsumer("raw-data");

 consumer.setStartFromLatest();

 DataStream<String\> stream \= env.addSource(consumer);

 stream.assignTimestampsAndWatermarks(emitter);



 KeyedStream<SensorData, GroupKey\> groupedDataSource \=

 stream.map(jsonMapFunction).filter(nullFilterFunction).keyBy(keySelector);

 WindowedStream<SensorData, GroupKey, CountTimeCompositeWindow\> windowedStream \=

 groupedDataSource.window(windowAssigner).trigger(PurgingTrigger.of(windowTrigger));



 windowedStream.apply(algorithmWindowFunction)

 .map(stringMapFunction)

 .addSink(new FlinkKafkaProducer011<>(producesTopic, new SimpleStringSchema(), properties));



 try {

 env.execute();

 } catch (Exception e) {

 throw new ServerStartUpException("Can not start up calculator service.", e);

 }

 }

数据源
---

我参加了大大小小几十个Flink的分享、会议， 基本上大家都是从kafka、数据中心里读数据。当然Flink 本身提供的能力很多（很多的志愿者给Flink增加了很多的SourceFunction的实现。有兴趣可以去github看看）。在Flink的代码仓库里，我们一般称之为 Flink connector

DataStream
----------

DataStream 是 Flink 流处理 API 中最核心的数据结构。它代表了一个运行在多个分区上的并行流。一个 DataStream 可以从 StreamExecutionEnvironment 通过env.addSource(SourceFunction) 获得。

DataStream 上的转换操作都是逐条的，比如 map()，flatMap()，filter()。DataStream 也可以执行 rebalance（再平衡，用来减轻数据倾斜）和 broadcaseted（广播）等分区转换。

如上图的执行图所示，DataStream 各个算子会并行运行，算子之间是数据流分区。如 Source 的第一个并行实例（S1）和 flatMap() 的第一个并行实例（m1）之间就是一个数据流分区。而在 flatMap() 和 map() 之间由于加了 rebalance()，它们之间的数据流分区就有3个子分区（m1的数据流向3个map()实例）。这与 Apache Kafka 是很类似的，把流想象成 Kafka Topic，而一个流分区就表示一个 Topic Partition，流的目标并行算子实例就是 Kafka Consumers。

KeyedStream
-----------

KeyedStream用来表示根据指定的key进行分组的数据流。一个KeyedStream可以通过调用DataStream.keyBy()来获得。而在KeyedStream上进行任何transformation都将转变回DataStream。在实现中，KeyedStream是把key的信息写入到了transformation中。每条记录只能访问所属key的状态，其上的聚合函数可以方便地操作和保存对应key的状态。

[](http://wuchong.me/blog/2016/05/20/flink-internals-streams-and-operations-on-streams/#WindowedStream-amp-AllWindowedStream)WindowedStream & AllWindowedStream

---------------------------------------------------------------------------------------------------------------------------------------------------------------

WindowedStream代表了根据key分组，并且基于WindowAssigner切分窗口的数据流。所以WindowedStream都是从KeyedStream衍生而来的。而在WindowedStream上进行任何transformation也都将转变回DataStream。

上述 WindowedStream 的样例代码在运行时会转换成如下的执行图：

[](http://img3.tbcdn.cn/5476e8b07b923/TB1G2HqJVXXXXb4aXXXXXXXXXXX)

Flink 的窗口实现中会将到达的数据缓存在对应的窗口buffer中（一个数据可能会对应多个窗口）。当到达窗口发送的条件时（由Trigger控制），Flink 会对整个窗口中的数据进行处理。Flink 在聚合类窗口有一定的优化，即不会保存窗口中的所有值，而是每到一个元素执行一次聚合函数，最终只保存一份数据即可。

在key分组的流上进行窗口切分是比较常用的场景，也能够很好地并行化（不同的key上的窗口聚合可以分配到不同的task去处理）。不过有时候我们也需要在普通流上进行窗口的操作，这就是 AllWindowedStream。AllWindowedStream是直接在DataStream上进行windowAll(...)操作。AllWindowedStream 的实现是基于 WindowedStream 的（Flink 1.1.x 开始）。Flink 不推荐使用AllWindowedStream，因为在普通流上进行窗口操作，就势必需要将所有分区的流都汇集到单个的Task中，而这个单个的Task很显然就会成为整个Job的瓶颈。

[](http://wuchong.me/blog/2016/05/20/flink-internals-streams-and-operations-on-streams/#JoinedStreams-amp-CoGroupedStreams)JoinedStreams & CoGroupedStreams

-----------------------------------------------------------------------------------------------------------------------------------------------------------

双流 Join 也是一个非常常见的应用场景。深入源码你可以发现，JoinedStreams 和 CoGroupedStreams 的代码实现有80%是一模一样的，JoinedStreams 在底层又调用了 CoGroupedStreams 来实现 Join 功能。除了名字不一样，一开始很难将它们区分开来，而且为什么要提供两个功能类似的接口呢？？

实际上这两者还是很点区别的。首先 co-group 侧重的是group，是对同一个key上的两组集合进行操作，而 join 侧重的是pair，是对同一个key上的每对元素进行操作。co-group 比 join 更通用一些，因为 join 只是 co-group 的一个特例，所以 join 是可以基于 co-group 来实现的（当然有优化的空间）。而在 co-group 之外又提供了 join 接口是因为用户更熟悉 join（源于数据库吧），而且能够跟 DataSet API 保持一致，降低用户的学习成本。

JoinedStreams 和 CoGroupedStreams 是基于 Window 上实现的，所以 CoGroupedStreams 最终又调用了 WindowedStream 来实现。

[](http://wuchong.me/blog/2016/05/20/flink-internals-streams-and-operations-on-streams/#ConnectedStreams)ConnectedStreams

-------------------------------------------------------------------------------------------------------------------------

在 DataStream 上有一个 union 的转换 dataStream.union(otherStream1, otherStream2, ...)，用来合并多个流，新的流会包含所有流中的数据。union 有一个限制，就是所有合并的流的类型必须是一致的。ConnectedStreams 提供了和 union 类似的功能，用来连接**两个**流，但是与 union 转换有以下几个区别：

1.  ConnectedStreams 只能连接两个流，而 union 可以连接多于两个流。
    
2.  ConnectedStreams 连接的两个流类型可以不一致，而 union 连接的流的类型必须一致。
    
3.  ConnectedStreams 会对两个流的数据应用不同的处理方法，并且双流之间可以共享状态。这在第一个流的输入会影响第二个流时, 会非常有用。
    

如下 ConnectedStreams 的样例，连接 input 和 other 流，并在input流上应用map1方法，在other上应用map2方法，双流可以共享状态（比如计数）。

Transformations

---------------

**Flink DataSteam Transformations**

Transformation

Description

Transformation

Description

**Map**  
DataStream → DataStream

Takes one element and produces one element. A map function that doubles the values of the input stream:

**DataStream<Integer\>** dataStream **\=** _//..._ dataStream**.**map**(new** **MapFunction<Integer,** **Integer\>()** **{** @Override **public** **Integer** **map(Integer** value**)** **throws** **Exception** **{** **return** 2 **\*** value**;** **}** **});**

**FlatMap**  
DataStream → DataStream

Takes one element and produces zero, one, or more elements. A flatmap function that splits sentences to words:

dataStream**.**flatMap**(new** **FlatMapFunction<String,** **String\>()** **{** @Override **public** **void** **flatMap(String** value**,** **Collector<String\>** out**)** **throws** **Exception** **{** **for(String** word: value**.**split**(**" "**)){** out**.**collect**(**word**);** **}** **}** **});**

**Filter**  
DataStream → DataStream

Evaluates a boolean function for each element and retains those for which the function returns true. A filter that filters out zero values:

dataStream**.**filter**(new** **FilterFunction<Integer\>()** **{** @Override **public** **boolean** **filter(Integer** value**)** **throws** **Exception** **{** **return** value **!=** 0**;** **}** **});**

**KeyBy**  
DataStream → KeyedStream

Logically partitions a stream into disjoint partitions. All records with the same key are assigned to the same partition. Internally, _keyBy()_ is implemented with hash partitioning. There are different ways to [specify keys](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/state/state.html#keyed-datastream).

This transformation returns a _KeyedStream_, which is, among other things, required to use [keyed state](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/state/state.html#keyed-state).

dataStream**.**keyBy**(**value **\->** value**.**getSomeKey**())** _// Key by field "someKey"_ dataStream**.**keyBy**(**value **\->** value**.**f0**)** _// Key by the first element of a Tuple_

**Attention** A type **cannot be a key** if:

1.  it is a POJO type but does not override the _hashCode()_ method and relies on the _Object.hashCode()_ implementation.
    
2.  it is an array of any type.
    

**Reduce**  
KeyedStream → DataStream

A "rolling" reduce on a keyed data stream. Combines the current element with the last reduced value and emits the new value.  


A reduce function that creates a stream of partial sums:

keyedStream**.**reduce**(new** **ReduceFunction<Integer\>()** **{** @Override **public** **Integer** **reduce(Integer** value1**,** **Integer** value2**)** **throws** **Exception** **{** **return** value1 **+** value2**;** **}** **});**

**Fold**  
KeyedStream → DataStream

A "rolling" fold on a keyed data stream with an initial value. Combines the current element with the last folded value and emits the new value.  


A fold function that, when applied on the sequence (1,2,3,4,5), emits the sequence "start-1", "start-1-2", "start-1-2-3", ...

**DataStream<String\>** result **\=** keyedStream**.**fold**(**"start"**,** **new** **FoldFunction<Integer,** **String\>()** **{** @Override **public** **String** **fold(String** current**,** **Integer** value**)** **{** **return** current **+** "-" **+** value**;** **}** **});**

**Aggregations**  
KeyedStream → DataStream

Rolling aggregations on a keyed data stream. The difference between min and minBy is that min returns the minimum value, whereas minBy returns the element that has the minimum value in this field (same for max and maxBy).

keyedStream**.**sum**(**0**);** keyedStream**.**sum**(**"key"**);** keyedStream**.**min**(**0**);** keyedStream**.**min**(**"key"**);** keyedStream**.**max**(**0**);** keyedStream**.**max**(**"key"**);** keyedStream**.**minBy**(**0**);** keyedStream**.**minBy**(**"key"**);** keyedStream**.**maxBy**(**0**);** keyedStream**.**maxBy**(**"key"**);**

**Window**  
KeyedStream → WindowedStream

Windows can be defined on already partitioned KeyedStreams. Windows group the data in each key according to some characteristic (e.g., the data that arrived within the last 5 seconds). See [windows](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/windows.html) for a complete description of windows.

dataStream**.**keyBy**(**value **\->** value**.**f0**).**window**(TumblingEventTimeWindows.**of**(Time.**seconds**(**5**)));** _// Last 5 seconds of data_

**WindowAll**  
DataStream → AllWindowedStream

Windows can be defined on regular DataStreams. Windows group all the stream events according to some characteristic (e.g., the data that arrived within the last 5 seconds). See [windows](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/windows.html) for a complete description of windows.

**WARNING:** This is in many cases a **non-parallel** transformation. All records will be gathered in one task for the windowAll operator.

dataStream**.**windowAll**(TumblingEventTimeWindows.**of**(Time.**seconds**(**5**)));** _// Last 5 seconds of data_

**Window Apply**  
WindowedStream → DataStream  
AllWindowedStream → DataStream

Applies a general function to the window as a whole. Below is a function that manually sums the elements of a window.

**Note:** If you are using a windowAll transformation, you need to use an AllWindowFunction instead.

windowedStream**.**apply **(new** **WindowFunction<Tuple2<String,Integer\>,** **Integer,** **Tuple,** **Window\>()** **{** **public** **void** **apply** **(Tuple** tuple**,** **Window** window**,** **Iterable<Tuple2<String,** **Integer\>>** values**,** **Collector<Integer\>** out**)** **throws** **Exception** **{** **int** sum **\=** 0**;** **for** **(**value t: values**)** **{** sum **+=** t**.**f1**;** **}** out**.**collect **(new** **Integer(**sum**));** **}** **});** _// applying an AllWindowFunction on non-keyed window stream_ allWindowedStream**.**apply **(new** **AllWindowFunction<Tuple2<String,Integer\>,** **Integer,** **Window\>()** **{** **public** **void** **apply** **(Window** window**,** **Iterable<Tuple2<String,** **Integer\>>** values**,** **Collector<Integer\>** out**)** **throws** **Exception** **{** **int** sum **\=** 0**;** **for** **(**value t: values**)** **{** sum **+=** t**.**f1**;** **}** out**.**collect **(new** **Integer(**sum**));** **}** **});**

**Window Reduce**  
WindowedStream → DataStream

Applies a functional reduce function to the window and returns the reduced value.

windowedStream**.**reduce **(new** **ReduceFunction<Tuple2<String,Integer\>>()** **{** **public** **Tuple2<String,** **Integer\>** **reduce(Tuple2<String,** **Integer\>** value1**,** **Tuple2<String,** **Integer\>** value2**)** **throws** **Exception** **{** **return** **new** **Tuple2<String,Integer\>(**value1**.**f0**,** value1**.**f1 **+** value2**.**f1**);** **}** **});**

**Window Fold**  
WindowedStream → DataStream

Applies a functional fold function to the window and returns the folded value. The example function, when applied on the sequence (1,2,3,4,5), folds the sequence into the string "start-1-2-3-4-5":

windowedStream**.**fold**(**"start"**,** **new** **FoldFunction<Integer,** **String\>()** **{** **public** **String** **fold(String** current**,** **Integer** value**)** **{** **return** current **+** "-" **+** value**;** **}** **});**

**Aggregations on windows**  
WindowedStream → DataStream

Aggregates the contents of a window. The difference between min and minBy is that min returns the minimum value, whereas minBy returns the element that has the minimum value in this field (same for max and maxBy).

windowedStream**.**sum**(**0**);** windowedStream**.**sum**(**"key"**);** windowedStream**.**min**(**0**);** windowedStream**.**min**(**"key"**);** windowedStream**.**max**(**0**);** windowedStream**.**max**(**"key"**);** windowedStream**.**minBy**(**0**);** windowedStream**.**minBy**(**"key"**);** windowedStream**.**maxBy**(**0**);** windowedStream**.**maxBy**(**"key"**);**

**Union**  
DataStream\* → DataStream

Union of two or more data streams creating a new stream containing all the elements from all the streams. Note: If you union a data stream with itself you will get each element twice in the resulting stream.

dataStream**.**union**(**otherStream1**,** otherStream2**,** **...);**

**Window Join**  
DataStream,DataStream → DataStream

Join two data streams on a given key and a common window.

dataStream**.**join**(**otherStream**)** **.**where**(<**key selector**\>).**equalTo**(<**key selector**\>)** **.**window**(TumblingEventTimeWindows.**of**(Time.**seconds**(**3**)))** **.**apply **(new** **JoinFunction** **()** **{...});**

**Interval Join**  
KeyedStream,KeyedStream → DataStream

Join two elements e1 and e2 of two keyed streams with a common key over a given time interval, so that e1.timestamp + lowerBound <= e2.timestamp <= e1.timestamp + upperBound

_// this will join the two streams so that_ _// key1 == key2 && leftTs - 2 < rightTs < leftTs + 2_ keyedStream**.**intervalJoin**(**otherKeyedStream**)** **.**between**(Time.**milliseconds**(-**2**),** **Time.**milliseconds**(**2**))** _// lower and upper bound_ **.**upperBoundExclusive**(true)** _// optional_ **.**lowerBoundExclusive**(true)** _// optional_ **.**process**(new** **IntervalJoinFunction()** **{...});**

**Window CoGroup**  
DataStream,DataStream → DataStream

Cogroups two data streams on a given key and a common window.

dataStream**.**coGroup**(**otherStream**)** **.**where**(**0**).**equalTo**(**1**)** **.**window**(TumblingEventTimeWindows.**of**(Time.**seconds**(**3**)))** **.**apply **(new** **CoGroupFunction** **()** **{...});**

**Connect**  
DataStream,DataStream → ConnectedStreams

"Connects" two data streams retaining their types. Connect allowing for shared state between the two streams.

**DataStream<Integer\>** someStream **\=** _//..._ **DataStream<String\>** otherStream **\=** _//..._ **ConnectedStreams<Integer,** **String\>** connectedStreams **\=** someStream**.**connect**(**otherStream**);**

**CoMap, CoFlatMap**  
ConnectedStreams → DataStream

Similar to map and flatMap on a connected data stream

connectedStreams**.**map**(new** **CoMapFunction<Integer,** **String,** **Boolean\>()** **{** @Override **public** **Boolean** **map1(Integer** value**)** **{** **return** **true;** **}** @Override **public** **Boolean** **map2(String** value**)** **{** **return** **false;** **}** **});** connectedStreams**.**flatMap**(new** **CoFlatMapFunction<Integer,** **String,** **String\>()** **{** @Override **public** **void** **flatMap1(Integer** value**,** **Collector<String\>** out**)** **{** out**.**collect**(**value**.**toString**());** **}** @Override **public** **void** **flatMap2(String** value**,** **Collector<String\>** out**)** **{** **for** **(String** word: value**.**split**(**" "**))** **{** out**.**collect**(**word**);** **}** **}** **});**

**Split**  
DataStream → SplitStream

Split the stream into two or more streams according to some criterion.

**SplitStream<Integer\>** split **\=** someDataStream**.**split**(new** **OutputSelector<Integer\>()** **{** @Override **public** **Iterable<String\>** **select(Integer** value**)** **{** **List<String\>** output **\=** **new** **ArrayList<String\>();** **if** **(**value **%** 2 **\==** 0**)** **{** output**.**add**(**"even"**);** **}** **else** **{** output**.**add**(**"odd"**);** **}** **return** output**;** **}** **});**

**Select**  
SplitStream → DataStream

Select one or more streams from a split stream.

**SplitStream<Integer\>** split**;** **DataStream<Integer\>** even **\=** split**.**select**(**"even"**);** **DataStream<Integer\>** odd **\=** split**.**select**(**"odd"**);** **DataStream<Integer\>** all **\=** split**.**select**(**"even"**,**"odd"**);**

**Iterate**  
DataStream → IterativeStream → DataStream

Creates a "feedback" loop in the flow, by redirecting the output of one operator to some previous operator. This is especially useful for defining algorithms that continuously update a model. The following code starts with a stream and applies the iteration body continuously. Elements that are greater than 0 are sent back to the feedback channel, and the rest of the elements are forwarded downstream. See [iterations](https://ci.apache.org/projects/flink/flink-docs-release-1.11/dev/stream/operators/#iterations) for a complete description.

**IterativeStream<Long\>** iteration **\=** initialStream**.**iterate**();** **DataStream<Long\>** iterationBody **\=** iteration**.**map **(**_/\*do something\*/_**);** **DataStream<Long\>** feedback **\=** iterationBody**.**filter**(new** **FilterFunction<Long\>(){** @Override **public** **boolean** **filter(Long** value**)** **throws** **Exception** **{** **return** value **\>** 0**;** **}** **});** iteration**.**closeWith**(**feedback**);** **DataStream<Long\>** output **\=** iterationBody**.**filter**(new** **FilterFunction<Long\>(){** @Override **public** **boolean** **filter(Long** value**)** **throws** **Exception** **{** **return** value **<=** 0**;** **}** **});**

六、横向对比
======

本文无意评价优劣，只是聊聊特点。对比的点其实比较少，目前能互相称之为对手的只有三个：Spark streaming、storm、Flink。算了，称之为对手的还是Spark streaming、Flink吧。

感觉这个文档，还算比较好的，[Flink 性能测试报告](https://km.sankuai.com/page/28194924)。我开始看过一个flink官方出的benchmark测试，基本上就是没把storm当人。storm也算是脱离了第一梯队了，没什么比较的意义了。

先说结论，Flink在流处理方面略比Spark streaming强, Spark本身作为一个内存计算框架，很优秀，但是正是这种架构，出身于批处理架构的底层思路，导致Spark streaming的延迟一定高于一秒(批处理的最小单元是1秒)，但是Flink的各种benchmark已经证明了毫秒级延迟并非官方吹嘘。Spark streaming 把流处理当做特殊的批处理、Flink把有界流当特殊的流处理。

### **社区能力**

Flink社区是目前commit个数最对的apache项目。

虽然一个Spark streaming本身社区能力不够，但是Spark比较特殊在，目前的用户很多，从技术的角度，更愿意迁移到Spark streaming，而不是Flink。这一点主要是同一个技术栈下面的各种搭配使用能力，相互削峰平谷。这一点Flink比不了。

社区能力心在基本上可以检验一个产品能走多远，这在现在开源为王的时代，尤为可见。

### **架构**

Streaming：微批处理

Flink: 事件（主要是IO事件，回调）

流处理上 Flink一定是在技术特性上领先Spark streaming的，其主要原因还是其架构的特点，但是这两年的升级，已经有很大进步

Flink的抽象要比Spark好，所以在学习曲线上被spark压了一头。算好也不算好吧。

### **事件时间**

Flink支持3个时间，Spark Streaming 只支持处理时间，Structured streaming 支持处理时间和事件时间，同时支持 watermark 机制处理滞后数据。

### **容错机制**

对于 Spark Streaming 任务，我们可以设置 checkpoint，然后假如发生故障并重启，我们可以从上次 checkpoint 之处恢复，但是这个行为只能使得数据不丢失，可能会重复处理，不能做到恰一次处理语义。

Flink 支持Exactly once的语义，通过类似事务的方式提交从 source 到sink的端到端的two phase commit。

### **共同点**

**两个工具越来越像，虽然只有一个会胜出，但是另一个绝不会凋零。**

本来在搜索一些异同点的时候，想着，总得有人夸Spark streaming，但是看到的言论，对Spark挺严苛的。大学的时候，只在用storm、听说Spark streaming很吊，没停过Flink。

现在听到的全是Flink，甚至没人敢讲自己用的是stlorm了。这本身不对，其实Spark的进步很快。Flink的一些contributor、committer都去支持spark streaming去了，很简单，大家都要恰饭，公司里面不会只用Flink，用Hadoop生态的一般占比100%，那spark就时很优秀，或许有个好爹，比你优秀有用多了，有点扎心了。

Flink和Spark streaming的各种能力，都是相对很相似的。比如说：chandy-lamport算法的应用，SQL的支持、watermark、时间语义、exactly-once

在投放这边有什么适应场景吗？
==============

投放有适应场景吗？

实时 商户通知 监控 上下文

*   kafka
    
*   db
    

实时 数据监控、异常监控

目前行业一般用作的都是监控(监控万物，切面、关注点)，我以前的使用经历是：做机床数据监控、做金融风控(接入多个source)，做业务异常监控。

我司如何上线，使用的怎么样
=============

聊聊Flink的社区，以及Flink的展望
=====================

Flink的社区环境
----------

本来Flink的社区环境比较好，然后阿里巴巴被引入了，我前段时间去看看Flink的PR，有一个PR 有130w代码要被合并到master上去，是阿里巴巴基于Flink做的Blink， 先别管代码有多厉害（声称30%-60%的性能提升，极端场景1000%， 主要集中在Flink SQL那块），就是这个代码量，谁能合的了。憨憨

最近半年，Flink在跟Blink积极联系，想着能把Blink的代码合并的，但是Blink的代码质量不符合，我都傻眼了，啥代码都敢往上提，估计是内部review没有仔细审核。估计还要一段时间，最近订阅邮件好多他们的邮件。但是Blink做的努力还是很多的，推进了Flink在国内疯狂发育。目前看到大家都知道Flink的存在，还是让那群老外很开心的。其实阿里巴巴在技术上的布局还是很有野心的，前端时间review了下apache的理事、PMC、Committer好像阿里巴巴的人有点多。阿里巴巴买下了Flink的母公司，其实想想也能明白。。。。

Flink目前仍可以保持每一个Ticket、Jira在很短的时间内被响应，这得益于众多的PMC、committer对项目的持续关注，虽然目前的Flink已经不缺contributor了，但是大家也可以关注一下apache的其他软件，有很多，其实很缺人， 目前apache有项目400+ 但是committer才8000左右。

以后有时间，可以给大家讲讲 Apache这个价值200亿美元的组织身上的故事、组织架构、前世今生，还有他现状。还是挺有意思的。开源的内核哲学、apache全球运营的管理过程。

多说一句，我建议大家把：哪个版本升级了什么技术，作为技能点的一个部分。

Flink的未来
--------

Flink只会越来越好，我有幸，看到了几个版本，其实Flink每个版本都会经历一写很大的改变，每一个版本的更新都伴随着一次与同门师兄弟的拉锯战。

Flink的未来只会越来越棒，在几十个PMC/commiter的带领下，700+的contributor还在继续在自己的社会主义里添砖加瓦。当前的版本，Flink的主旨依旧是与Blink的结合，吸收Blink的精华。

引用
==

*   [阿里为什么要拿下Flink？](https://m.sohu.com/a/288908399_185201)
    
*   [Apache 流框架 Flink，Spark Streaming，Storm对比分析（一）](https://blog.csdn.net/wangyiyungw/article/details/80237270)
    
*   [Apache 流框架 Flink，Spark Streaming，Storm对比分析（二）](https://blog.csdn.net/wangyiyungw/article/details/80237410)
    
*   [Flink Window分析及Watermark解决乱序数据机制深入剖析-Flink牛刀小试](https://juejin.im/post/6844903721441181709)
    


