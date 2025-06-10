---
title: Flink-state
type: docs
---

# State 和 CheckPoint机制（深究可以自行阅读官方文档）

- [State 和 CheckPoint机制（深究可以自行阅读官方文档）](#state-和-checkpoint机制深究可以自行阅读官方文档)
- [State](#state)
  - [**Operator State**](#operator-state)
  - [KeyedState](#keyedstate)
  - [Broadcast 广播状态](#broadcast-广播状态)
- [CheckPoint](#checkpoint)
  - [Barrier](#barrier)
    - [单流的Barrier](#单流的barrier)
    - [并行barrier](#并行barrier)
  - [Checkpoint 的协调与发起](#checkpoint-的协调与发起)
      - [CheckpointCoordinator](#checkpointcoordinator)
  - [Failover](#failover)
- [SavePoint](#savepoint)
  - [Flink Savepoint 触发方式](#flink-savepoint-触发方式)
  - [Flink Savepoint 注意点](#flink-savepoint-注意点)

流式计算的数据往往是转瞬即逝， 当然，真实业务场景不可能说所有的数据都是进来之后就走掉，没有任何东西留下来，那么留下来的东西其实就是称之为 state，中文可以翻译成状态。

而且，最恐怖的是：batch计算时，如果某个task失败，可以很容易重新运行这个task，但是对于流，某个消息处理失败，如果不想丢失数据，需要通知源端重发这条消息，如果有涉及到状态的计算，状态也要一起回滚，否则，计算会出现不准确，这时只能保证at least once语义。要实现在消息处理出错或者任务挂掉时，能够快速的回滚到某个状态，实现exactly-once语义，比较复杂，要付出不少成本。

Checkpoint是Flink实现容错机制最核心的功能，它能够根据配置周期性地基于Stream中各个Operator/task的状态来生成快照，从而将这些状态数据定期持久化存储下来，当Flink程序一旦意外崩溃时，重新运行程序时可以有选择地从这些快照进行恢复，从而修正因为故障带来的程序数据异常。

State
=====

前言

本文不包含一些State的深层次调用、调度、failover，以及对应可能产生的问题-> 解决办法。

这里简要一些关键词：Flink使用大状态、RocksDB的问题、增量、种种吧, 没必要去做。

如有需要，会给这里单独做一个分享，这里如果要上生产环境的话，要很多东西去做。以前做一个项目，三个月的时间，一半时间都在这里，设计的东西很复杂。

我司内部文档：[Flink大状态管理](https://km.sankuai.com/page/190434340)

在Flink中，State中主要分为Operator State以及KeyedState，在Flink 1.5之后，又推出了BroadCast State，它通常使用在两个流进行连接处理，其中一个流的数据是一些不常改变的数据，比如一些配置规则等等，另一个流需要连接这个Broadcast DataStream进行操作等场景。

![](https://km.sankuai.com/api/file/cdn/486174401/488534980?contentType=1&isNewContent=false&isNewContent=false)

> Stateful Flink applications are optimized for **local state access**. Task state is always maintained in memory or, if the state size exceeds the available memory, in access-efficient on-disk data structures. Hence, tasks perform all computations by accessing local, often in-memory, **state yielding very low processing latencies.** **Flink guarantees exactly-once state consistency in case of failures by periodically and asynchronously checkpointing the local state to durable storage.**

**Operator State**
------------------

Operator State是指在一个job中的一个task中的每一个operator对应着一个state，比如在一个job中，涉及到map，filter，sink等操作，那么在这些operator中，每一个可以对应着一个state（并行度为1），如果是多个并行度，那么每一个并行度都对应着一个state。对于Operator State主要有ListState可以进行使用。

KeyedState
----------

它主要应用在KeyedDataStream中，上面的Operator State中 ，每一个并行度对应着一个state，KeyState是指一个key对应着一个state，这意味着如果在一个应用中需要维护着很多的key，那么保存它的state必然会给应用带来额外的开销。

它主要提供了以下的state：

*   Value State：ValueState 分区的单值状态。
    
*   Map State：MapState<UK,UV> 分区的键值状态。
    
*   List State：ListState 分区的列表状态。
    
*   Reducing State：ReducingState 每次调用 add(T) 添加新元素，会调用 ReduceFunction 进行聚合。传入类型和返回类型相同。
    
*   Aggregating State：AggregatingState<IN,OUT> 每次调用 add(T) 添加新元素，会调用ReduceFunction 进行聚合。传入类型和返回类型可以不同。
    

需要注意的是，以上所述的State对象，仅仅用于与状态进行交互（更新、删除、清空等），而真正的状态值，有可能是存在内存、磁盘、或者其他分布式存储系统中。相当于我们只是持有了这个状态的句柄。实际上，这些状态有三种存储方式：

这个就是我们说的状态后端 StateBackend

*   MemoryStateBackend 内存
    
*   FsStateBackend 文件系统
    
*   RockDBStateBackend DB
    

上面的两中state的分类是可以组合的，所以大家会在代码库里面看到的实现大概是这样的：

代码块

Java

class RocksDBListState<K, N, V\> extends AbstractRocksDBState<K, N, List<V\>> implements InternalListState<K, N, V\> {}

class HeapValueState<K, N, V\> extends AbstractHeapState<K, N, V\> implements InternalValueState<K, N, V\> {}

*   Flink 支持 Standalone 和 on Yarn 的集群部署模式，同时支持 Memory、FileSystem、RocksDB 三种状态存储后端（StateBackends）。由于线上作业需要，测试了这三种 StateBackends 在两种集群部署模式上的性能差异。其中，Standalone 时的存储路径为 JobManager 上的一个文件目录，on Yarn 时存储路径为 HDFS 上一个文件目录。
    
*   **使用 FileSystem 和 Memory 的吞吐差异不大，使用 RocksDB 的吞吐仅其余两者的十分之一左右。**
    
*   **Standalone 和 on Yarn 的总体差异不大**，使用 FileSystem 和 Memory 时 on Yarn 模式下吞吐稍高，使用 RocksDB 时 Standalone 模式下的吞吐稍高。
    

**StateDescriptor**

State 既然是暴露给用户的，那么就需要有一些属性需要指定：state 名称、val serializer、state type info。这些属性被封装在 StateDescriptor 抽象中。用户通过 AbstractKeyedStateBackend 的接口 getXXXState() 将 StateDescriptor 传给底层 State 实现。

**State partition/动态伸缩**

由于 KeyedStateBackend 是 task/op 级别的实例，每个 task/op 会拿着自己的 KeyedStateBackend 去做快照，我们都知道，每个 task/op 都会在运行时会处理部分的 key element【对于 KeyedStream 来说】，相应的 task-op 写出的快照状态也是只包含对应 key element 的部分，当 task-op 对应的 Operator 扩大/缩小 并发之后，之前快照的状态 key 就没有办法与当前的算子再一一对应了，这样就需要一些思路一定程度上解决这个问题。

**State TTL**

对于每一个keyed State，还可以设置TTL过期时间，它会将过期的state删除掉，通过下面的方式来设置TTL。从Flink 1.6版本开始，社区为状态引入了TTL（time-to-live，生存时间）机制，支持Keyed State的自动过期，有效解决了状态数据在无干预情况下无限增长导致OOM的问题。State TTL的用法很简单，[官方文档](https://links.jianshu.com/go?to=https%3A%2F%2Fci.apache.org%2Fprojects%2Fflink%2Fflink-docs-release-1.10%2Fdev%2Fstream%2Fstate%2Fstate.html%23state-time-to-live-ttl)中给出的示例代码如下。

代码块

Java

StateTtlConfig ttlConfig \= StateTtlConfig

 .newBuilder(Time.seconds(1))

 .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)

 .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)

 .build();

ValueStateDescriptor<String\> stateDescriptor \= new ValueStateDescriptor<>("text state", String.class);

stateDescriptor.enableTimeToLive(ttlConfig);

**StateTtlConfig**

代码块

Java

private final UpdateType updateType;

private final StateVisibility stateVisibility;

private final TtlTimeCharacteristic ttlTimeCharacteristic;

private final Time ttl;

private final CleanupStrategies cleanupStrategies;

该类中有5个成员属性，它们就是用户需要指定的全部参数了。**它们的含义在注释中已经解释得很清楚了。**

1.  **TTL**：表示状态的过期时间，是一个 org.apache.flink.api.common.time.Time 对象。一旦设置了 TTL，那么如果上次访问的时间戳 + TTL 超过了当前时间，则表明状态过期了（这是一个简化的说法，严谨的定义请参考 org.apache.flink.runtime.state.ttl.TtlUtils 类中关于 expired 的实现） 。
    
2.  **UpdateType**：表示状态时间戳的更新的时机，是一个 Enum 对象。如果设置为 Disabled，则表明不更新时间戳；如果设置为 OnCreateAndWrite，则表明当状态创建或每次写入时都会更新时间戳；如果设置为 OnReadAndWrite，则除了在状态创建和写入时更新时间戳外，读取也会更新状态的时间戳。
    
3.  **StateVisibility**：表示对已过期但还未被清理掉的状态如何处理，也是 Enum 对象。如果设置为 ReturnExpiredIfNotCleanedUp，那么即使这个状态的时间戳表明它已经过期了，但是只要还未被真正清理掉，就会被返回给调用方；如果设置为 NeverReturnExpired，那么一旦这个状态过期了，那么永远不会被返回给调用方，只会返回空状态，避免了过期状态带来的干扰。
    
4.  **TimeCharacteristic 以及 TtlTimeCharacteristic**：表示 State TTL 功能所适用的时间模式，仍然是 Enum 对象。前者已经被标记为 Deprecated（废弃），推荐新代码采用新的 TtlTimeCharacteristic 参数。截止到 Flink 1.8，只支持 ProcessingTime 一种时间模式，对 EventTime 模式的 State TTL 支持还在开发中。
    
5.  **CleanupStrategies**：表示过期对象的清理策略，目前来说有三种 Enum 值。当设置为 FULL\_STATE\_SCAN\_SNAPSHOT 时，对应的是 EmptyCleanupStrategy 类，表示对过期状态不做主动清理，当执行完整快照（Snapshot / Checkpoint）时，会生成一个较小的状态文件，但本地状态并不会减小。唯有当作业重启并从上一个快照点恢复后，本地状态才会实际减小，因此可能仍然不能解决内存压力的问题。为了应对这个问题，Flink 还提供了增量清理的枚举值，分别是针对 Heap StateBackend 的 INCREMENTAL\_CLEANUP（对应 IncrementalCleanupStrategy 类），以及对 RocksDB StateBackend 有效的 ROCKSDB\_COMPACTION\_FILTER（对应 RocksdbCompactFilterCleanupStrategy 类）. 对于增量清理功能，Flink 可以被配置为每读取若干条记录就执行一次清理操作，而且可以指定每次要清理多少条失效记录；对于 RocksDB 的状态清理，则是通过 JNI 来调用 C++ 语言编写的 FlinkCompactionFilter 来实现，底层是通过 RocksDB 提供的后台 Compaction 操作来实现对失效状态过滤的。
    

再往下的技术原理就不赘述了。

Broadcast 广播状态
--------------

广播状态模式指的一种流应用程序，其中低吞吐量的事件流（例如，包含一组规则）被广播到某个 operator 的所有并发实例中，然后针对来自另一条原始数据流中的数据（例如金融或信用卡交易）进行计算。 具体情况没用过，也可能是目前没有适合的场景网上套，所以就不太敢解释。

CheckPoint
==========

**在Flink中 CheckPoint默认是关闭的。想要使用的时候，需要打开开光。**

CheckPoint的 mode有两种，Exactly-once 和 At-least-once。 这两种模式，取决于系统配置。至少一次要求系统 sink 算子 幂等。

流式作业的特点是7\*24小时运行，数据不重复消费，不丢失，保证只计算一次，数据实时产出不延迟，但是当状态很大，内存容量限制，或者实例运行奔溃，或需要扩展并发度等情况下，如何保证状态正确的管理，在任务重新执行的时候能正确执行，状态管理就显得尤为重要。

这里大家可能很好奇，为什么花大量时间在说这个TTL，因为TTL会引入我们最重要的机制：checkpoint。

对于一个拓扑结构，只有上游算子 checkpoint 完成，下游算子的 checkpoint 才能开始并有意义，又因为下游算子的消费速率并不统一【有的 channel 快，有的 channel 慢】，barrier 就是这样一种协调上下游算子的机制。

Flink 的 checkpoint 使用的算法是Chandy-Lamport算法的核心原理，原论文地址 [https://www.microsoft.com/en-us/research/uploads/prod/2016/12/Determining-Global-States-of-a-Distributed-System.pdf](https://www.microsoft.com/en-us/research/uploads/prod/2016/12/Determining-Global-States-of-a-Distributed-System.pdf) 。

其中作者之一Leslie Lamport就是Paxos的作者，本论文也是Flink实现分布式snapshot和exactly-once语义的基础，虽然算法意义巨大但其原理并不高深，很多人独立思考也可以想到，只是没有论文中的严格数学证明而已，作者也认为其核心思想很straighforward。

关于算法的逻辑就不再赘述了，这里主要介绍一下算法在Flink中的实现方式。

Barrier
-------

我们首先要介绍一个 Barrier(屏障)， 这里面的屏障的核心理解比较像我们以前经常了解的两个概念点：内存屏障(volatile里面的屏障概念)、CyclicBarrier类。

> These barriers are injected into the data stream and flow with the records as part of the data stream. Barriers never overtake records, they flow strictly in line. A barrier separates the records in the data stream into the set of records that goes into the current snapshot, and the records that go into the next snapshot. Each barrier carries the ID of the snapshot whose records it pushed in front of it. Barriers do not interrupt the flow of the stream and are hence very lightweight. Multiple barriers from different snapshots can be in the stream at the same time, which means that various snapshots may happen concurrently.
>
> \-- From [apache-flink-doc](https://ci.apache.org/projects/flink/flink-docs-release-1.11/concepts/stateful-stream-processing.html#barriers)

一般而言，整个流式系统的consumer仅包含一个source，但是Flink是允许我们接受超过一个source的流的，多个流一般通过boardCast的概念来扩展(付费内容，这里面就不展开了).

**Flink的checkpoint机制可以与(stream和state)的持久化存储交互的前提是： 持久化的source（如kafka），它需要支持在一定时间内重放事件。**

这种sources的典型例子是持久化的消息队列（比如Apache Kafka，RabbitMQ等）或文件系统（比如HDFS，S3，GFS等） 用于state的持久化存储，例如分布式文件系统（比如HDFS，S3，GFS等）

* * *

### 单流的Barrier

1: 屏障作为数据流的一部分随着记录被注入到数据流中。屏障永远不会赶超通常的流记录，它会严格遵循顺序。

2: 屏障将数据流中的记录隔离成一系列的记录集合，并将一些集合中的数据加入到当前的快照中，而另一些数据加入到下一个快照中。

3: 每一个屏障携带着快照的ID，快照记录着ID并且将其放在快照数据的前面。

4: 屏障不会中断流处理，因此非常轻量级。

**JobManager 统一通知 source operator 发射 barrier 事件，并向下游广播，当下游算子收到这样的事件后，它就知道自己处于两次 checkpoint 之间【一次新的 checkpoint 将被发起】：下游算子 op-1 收到了它所有的 InputChannel 的某次 checkpint 的 barrier 事件后【意味着上游算子的一次 checkpoint 已完成】，自身也可以做 checkpoint，并且在 checkpoint 之后继续将 checkpoint 事件广播到 op-1 的下游算子。**

### 并行barrier

1：不止一个输入流的时的operator，需要在快照屏障上对齐(align)输入流，才会发射出去。

2：可以看到1,2,3会一直放在Input buffer，直到另一个输入流的快照到达Operator

大家需要注意的是，若果在 exactly-once 语义下，消费端会延迟处理，对齐不同 channel 的 barrier。

Checkpoint 的协调与发起
-----------------

Checkpoint 统一由 JobManager 发起，中间涉及到 JobManager 和 TaskManager 的交互，一轮快照可以分为 4 个阶段：

*   JobManager checkpoint 的发起
    
*   barrier 的逐级传播
    
*   op/task 的 checkpint 以及 ack 消息回传
    
*   JobManager commit 消息的广播
    

#### CheckpointCoordinator

Checkpoint 默认的并发为1。针对 Flink DataStream 任务，程序需要经历从 **StreamGraph -> JobGraph -> ExecutionGraph -> 物理执行图四个步骤**，其中在 ExecutionGraph 构建时，会初始化 CheckpointCoordinator。

JobManager 中对 checkpoint 全局协调控制的核心抽象是 CheckpointCoordinator，它的功能主要包括两部分：

* * *

1.  发起起始 checkpoint trigger-event 消息给 op/task 并收取 op/task 完成该轮 checkpoint 之后的 ack 信息
    
2.  维护 op/task 上报的 ack 消息中附带的状态句柄：state-handle 的全局视图
    

**CheckpointCoordinator 可以同时并发执行多个 checkpoint**，一次发起并尚未完全 ack 的 checkpint 被抽象为 PendingCheckpoint，当 PendingCheckpoint 被完全 ack 后即可转化一个 CompletedCheckpoint，一个 CompletedCheckpoint 代表一轮成功的分布式快照，该抽象可以拿来在 JobManager 端备份做高可用容错策略。

由于一次发起的分布式快照并不一定执行的顺利【快速的执行完】，会出现各种异常情况，比如执行耗时导致后面发起的快照已执行完而自己却还没有结束、比如整体快照效率低下导致快照任务排队、比如快照期间发生了异常等。**CheckpointCoordinator 就是扮演了从 checkpoint 发起到完全结束的整个生命周期的状态、策略协调的作用。**

Failover
--------

state + checkpoint 一起，这些数据都是持久化的，现在从这里面把checkpoint的state数据提取出来(最新的，这里面底层是有一些关于全量、增量的checkpoint的)**，结合事件回放(**注意，并不是所有的connector都支持回放**)。**

SavePoint
=========

> 参考：
>
> *   [https://ci.apache.org/projects/flink/flink-docs-release-1.11/ops/state/savepoints.html](https://ci.apache.org/projects/flink/flink-docs-release-1.11/ops/state/savepoints.html)
>     
> *   [Flink实时计算-深入理解Checkpoint和Savepoint](https://zhuanlan.zhihu.com/p/79526638?utm_source=wechat_session)
>     

后续Flink社区会把CheckPoint和savePoint合并，目前已经是savePoint持有指向checkPoint的指针。目前逻辑已经公用一套了。整的乱七八糟的，一直没下的原因是：增加功能容易，删除功能，除非机缘到了，一般都不太可以。

现在已经做了能做的大部分了：功能重复、代码复用、指针持有存储。仅仅是指令不同了。后面只能看我佛是否慈悲了。

**Flink Savepoint 你可以把它当做在某个时间点程序状态全局镜像，以后程序在进行升级，或者修改并发度等情况，还能从保存的状态位继续启动恢复。**Flink Savepoint 一般存储在 HDFS 上面，它需要用户主动进行触发。如果是用户自定义开发的实时程序，比如使用DataStream进行开发，建议为每个算子定义一个 uid，这样我们在修改作业时，即使导致程序拓扑图改变，由于相关算子 uid 没有变，那么这些算子还能够继续使用之前的状态，如果用户没有定义 uid ， Flink 会为每个算子自动生成 uid，如果用户修改了程序，可能导致之前的状态程序不能再进行复用。

**Flink Checkpoint 是一种容错恢复机制。**这种机制保证了实时程序运行时，即使突然遇到异常也能够进行自我恢复。Checkpoint 对于用户层面，是透明的，用户会感觉程序一直在运行。Flink Checkpoint 是 Flink 自身的系统行为，用户无法对其进行交互，用户可以在程序启动之前，设置好实时程序 Checkpoint 相关参数，当程序启动之后，剩下的就全交给 Flink 自行管理。当然在某些情况，比如 Flink On Yarn 模式，某个 Container 发生 OOM 异常，这种情况程序直接变成失败状态，此时 Flink 程序虽然开启 Checkpoint 也无法恢复，因为程序已经变成失败状态，所以此时可以借助外部参与启动程序，比如外部程序检测到实时任务失败时，从新对实时任务进行拉起。

*   概念： Checkpoint 是 自动容错机制 ，Savepoint 程序全局状态镜像 。
    
*   目的： Checkpoint 是程序自动容错，快速恢复 。Savepoint是 程序修改后继续从状态恢复，程序升级等。
    
*   用户交互： Checkpoint 是 Flink 系统行为 。Savepoint是用户触发。
    
*   状态文件保留策略：Checkpoint默认程序删除，可以设置CheckpointConfig中的参数进行保留 。Savepoint会一直保存，除非用户删除 。
    

Flink Savepoint 触发方式
--------------------

Flink Savepoint 触发方式目前有三种：

1\. 使用 **flink savepoint** 命令触发 Savepoint,其是在程序运行期间触发 savepoint。

2\. 使用 **flink cancel -s** 命令，取消作业时，并触发 Savepoint。

3\. 使用 Rest API 触发 Savepoint，格式为：**\*\*/jobs/:jobid /savepoints\*\***

Flink Savepoint 注意点
-------------------

1\. 使用 **flink cancel -s** 命令取消作业同时触发 Savepoint 时，会有一个问题，可能存在触发 Savepoint 失败。比如实时程序处于异常状态(比如 Checkpoint失败)，而此时你停止作业，同时触发 Savepoint,这次 Savepoint 就会失败，这种情况会导致，在实时平台上面看到任务已经停止，但是实际实时作业在 Yarn 还在运行。针对这种情况，需要捕获触发 Savepoint 失败的异常，当抛出异常时，可以直接在 Yarn 上面 Kill 掉该任务。

2\. 使用 DataStream 程序开发时，最好为每个算子分配 \`uid\`,这样即使作业拓扑图变了，相关算子还是能够从之前的状态进行恢复，默认情况下，Flink 会为每个算子分配 \`uid\`,这种情况下，当你改变了程序的某些逻辑时，可能导致算子的 \`uid\` 发生改变，那么之前的状态数据，就不能进行复用，程序在启动的时候，就会报错。

3\. 由于 Savepoint 是程序的全局状态，对于某些状态很大的实时任务，当我们触发 Savepoint，可能会对运行着的实时任务产生影响，个人建议如果对于状态过大的实时任务，触发 Savepoint 的时间，不要太过频繁。根据状态的大小，适当的设置触发时间。

4\. 当我们从 Savepoint 进行恢复时，需要检查这次 Savepoint 目录文件是否可用。可能存在你上次触发 Savepoint 没有成功，导致 HDFS 目录上面 Savepoint 文件不可用或者缺少数据文件等，这种情况下，如果在指定损坏的 Savepoint 的状态目录进行状态恢复，任务会启动不起来。

最后，如果感觉这地方写的不太好，或者感觉表达的不清楚，可以看一下这篇文章，基本上写出了所有的东西：

[https://ci.apache.org/projects/flink/flink-docs-release-1.11/concepts/stateful-stream-processing.html](https://ci.apache.org/projects/flink/flink-docs-release-1.11/concepts/stateful-stream-processing.html)

*   [Flink State 最佳实践](https://zhuanlan.zhihu.com/p/136722111)
    
*   [Flink实时计算-深入理解Checkpoint和Savepoint](https://zhuanlan.zhihu.com/p/79526638?utm_source=wechat_session)
    

