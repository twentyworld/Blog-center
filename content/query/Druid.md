---
title: 3. Druid
type: docs
---

# 1 Druid概述

[Druid](http://druid.io/) ("德鲁伊")是由广告分析公司[MetaMarkets](https://metamarkets.com/)开源的分布式OLAP存储与查询系统，主要用于大规模事件流数据（Event Stream Data）的实时摄入（Real Time Ingest）与交互式OLAP分析。

Druid的主要特点包括：

1）**实时数据摄入**：支持从流式系统（Storm/Samza）或消息系统（Kafka）中摄入数据，并使这些数据可以被分析，大大缩减了从事件产生到事件可以被分析的时间间隔。

2）**交互式聚合/OLAP查询**：Druid通过列式存储和位图索引，能够实现毫秒级响应复杂的多维过滤与聚集查询。

3）**支撑面向用户的数据分析产品**：Druid的设计能够满足用户级数据产品对多租户和高并发（1000+）的需求。

4）**高可用**：系统无单点，支持滚动升级和在线扩展

5）**高可扩展**：可扩展至处理万亿事件、PB数据、和1000+QPS

## 1.1 问题域及系统需求

上面提到，Druid处理的对象为「事件流数据」。这类数据通常来自于业务系统的事务日志，数据量庞大，主要组成为一个自增的时间戳（事件产生的时间）、多个描述事件发生上下文的维度信息（用户、产品等）、和多个可以被聚合分析的度量值（Metrics）。表1-1给出了事件流数据的一个例子，其中包含Page, Username, Gender, City四个维度属性，和Characters Added, Characters Removed两个度量属性。

![表1-1 维基百科的编辑事件流数据](druid.assets/4e1cd45f-ab9e-439c-af35-9c8d3ec66218.png)

Druid的目标是能够对这类数据进行快速地聚合查询，例如回答“2011年1月1日，有多少来自旧金山的女性对Justin Bieber的Wiki页面进行了编辑？”，或者“2011年2月，Ke$ha的Wiki页面编辑的平均增加字符数是多少？”这样的问题。熟悉OLAP的同学可以看出，这是典型的多维分析查询场景。与之不相交的另一类需求是明细数据查询，例如，Druid并不适合用来回答“取出2011年1月1日，Justin Bieber的Wiki页面编辑事件中添加次数超过2000字符的事件”这样的问题。

除此之外，Druid还需要满足以下系统需求：

- 交互式查询：为了前端可视化工具可以有很好的用户体验，查询必须秒级响应
- 低数据延迟：产生的数据必须很快进入系统并被用户查询到
- 高并发：系统需要支持1000+的并发用户，并提供隔离机制支持多租户模式
- 高可用：服务故障会导致公司业务遭受重大损失，因此不可用时间应当降到最低

## 1.2 与相关系统的对比

OLAP领域作为近几年非常火的领域，涌现出了不少系统。我们可以把这些相关系统归入以下三类，并和Druid做对比。

### 1.2.1 MPP系统

MPP系统采用关系模型和关系数据库技术来处理OLAP查询，通过并发查询处理技术来提高查询性能和系统的扩展性，典型的例子包括Presto, Impala等。

与Druid相比，MPP系统的优势是支持的查询模式更加灵活，提供SQL接口，并且有成熟的配套设施（SDK，运维工具等）。但是处理大数据集时，MPP系统有比较高昂的Scan和Join开销，很难做到秒级响应。另外MPP系统通常依赖一个数据批量装载进入系统的过程，因此很难满足「低数据延迟」的需求。

### 1.2.2 预计算系统

预计算系统的想法很简单：当数据是Append-Only，并且查询模式比较固定（针对维度属性进行group by，计算度量的聚合值）时，可以提前将各种维度组合的结果计算出来，存入KV NoSQL数据库（例如HBase）。查询处理时将查询转化为针对特定Key的Scan操作，直接从NoSQL取出结果。典型的例子包括Apache Kylin，[Twitter Rainbird](http://www.slideshare.net/kevinweil/rainbird-realtime-analytics-at-twitter-strata-2011)等。

与Druid相比，预计算系统在查询处理时“几乎”没有现场计算，查询性能和并发能力非常理想。然而，由于预计算的过程需要枚举维度的各种组合，当需要支持很多维度（20+）的任意组合查询时，预计算就变的不可行了。Druid由于是现场做聚合，因此能支持上百个维度。

### 1.2.3 搜索系统

一般就是建立倒排索引。

# 2 数据存储

Druid本身的架构比较复杂，因此本文采取自底向上的方式，先由本节介绍Druid如何将数据组织成Read-Optimized的结构，这是Druid实现交互式查询性能的关键。接着在第3节中，介绍从Hadoop离线批量导入数据，并且提供查询服务的方法。然后在第4节中，介绍通过RealTime Node实时摄入数据，从而降低数据延迟的方案。最后在第5节中给出Druid的完整架构。

## 2.1 数据分区

任何一个分布式存储/计算系统，都需要对数据进行合理的分区，从而实现存储与计算的均衡，以及[数据并行化](https://en.wikipedia.org/wiki/Data_parallelism)。Druid由于处理的是事件数据，每条记录都带有时间戳，因此根据时间字段对数据进行分区，例如每小时一个分区，是很自然的选择。但是，仍然还有两个问题值得考虑：

1）**数据分布的不均匀性**：每个时间段的事件数量可能是不均匀的，例如外卖的下单事件会呈现出两个明显的高峰。不均匀性轻则会导致数据处理时间的倾斜，重则会导致系统故障（例如处理特大分区的节点OOM）。

2）**存储明细数据的开销**：分析事件流数据时，由于数据产生速度太快、数据量太大，因此我们往往不关心某个具体的事件，而更关注某个时间窗口的聚合值。考虑到每条事件都有存储和计算的开销，因此对输入数据进行轻度的汇总有助于提升系统性能。

综合以上考虑，数据在Druid中的组织方式如图2-1所示。这里的输入数据以在线广告的场景为例，包含publisher, advertiser, gender, country四个维度属性，click和price两个度量属性。

![图2-1 Druid的数据分区过程](druid.assets/cd43c03f-d7bb-4b76-834c-280b4c81b3de.png)

首先，用户需要在数据摄入说明（Ingestion Spec）中指定查询的最细粒度（queryGranularity），这样系统可以根据queryGranularity对输入数据进行轻度汇总。例如，当queryGranularity指定为MINUTE时，Druid会对每分钟的事件进行汇总，将维度值都相同的事件进行聚合。最小的查询粒度为毫秒。

其次，用户在数据摄入说明中指定分区的粒度（segmentGranularity），例如每小时一个分区，这样每小时的数据可以被单独存储和查询。为了应对上面提到的「数据分布的不均匀性」，Druid支持用户对同一个分区的数据进行**「**二级分区**」**，每一个二级分区叫做一个Shard。二级分区通过partitionsSpec对象指定（见[这篇文档](http://druid.io/docs/0.8.3/ingestion/batch-ingestion.html)的Partitioning Specification小节），用户可以指定每个Shard的目标行数以及Shard策略。Druid目前支持Hash（基于所有维度属性的Hash值）和Range（基于某个维度属性的取值范围）两种Shard策略。上面的例子中，1点与3点的分区只包含一个Shard，2点的分区由于数据比较多，于是包含两个Shard。

持久化之后的Shard称作「Segment」。Segment是Druid中数据存储、复制、均衡、以及计算的基本单元，由dataSource_beginTime_endTime_version_shardNumber串唯一标识。Segment具有不可变性，一个Segment一旦生成就无法修改，但是可以通过生成一个新版本的Segment代替旧版本的Segment。

## 2.2 Segment

为了加快查询性能，Druid的Segment采用了列式存储（Column-Store），即将同一列的数据存储在一起。相比行式存储（Row-Store），列式存储在处理OLAP查询时有两个主要优势：

1）可以只读取需要的列，减少不必要的I/O

2）由于每列的数据类型相同，因此压缩时可以有更高的压缩比，进一步减少I/O

下面深入介绍一下Segment的存储格式以及采用的优化。

### 2.2.1 存储格式

以图2-1中的Shard为例，图2-2展示了该Shard经过Indexing生成的Segment的结构。

![6c6b35bd-a874-4599-b64f-3a0a0b614a93](druid.assets/6c6b35bd-a874-4599-b64f-3a0a0b614a93.png)

首先，Druid按列写出各个维度属性的值，再按列写出各个度量属性的值，最后写出timestamp列的值。为了减少进程打开的文件数，Druid并没有为每列单独写一个文件，而是将各列的数据合并（smoosh）到一个数据文件00000.smoosh中。查询处理时，Druid会将数据文件mmap到进程中，读取需要的数据。由于Java的mmap最大只能处理2G的文件，因此如果当前的数据文件过大，Druid会将一部分列写入第二个数据文件00001.smoosh，以此类推。

除了数据文件，每个Segment还包括一个版本文件version.bin和元信息文件meta.smoosh。元信息文件记录了各列在数据文件中的起始和结束偏移量，这样Druid就可以定位到需要读取的列在文件中的位置，并加载到内存中处理了。

具体到每一列的存储，则主要分为列元信息（ColumnDescriptor）和列的二进制数据两部分。列元信息描述了列的数据类型和序列化方法。对于整型/浮点型的Timestamp列以及度量列来说，序列化方法比较简单，直接写出各个long/double的值，然后压缩即可。维度列的序列化稍微复杂一些，下面单独说明。

### 2.2.2 维度列的存储

Druid使用字典编码（Dictionary Encoding）和位图索引（Bitmap Index）来存储每个维度列。如图2-3所示，每列的存储内容为列元信息、字典、字典编码后的值，以及位图索引四部分。

Druid把所有维度列都看做string类型，而字典编码是高效存储字符串的经典方式。以gender列为例，假设该列只有"Male"和"Female"两种值，那么可以用0来表示"Female"，1来表示"Male"，这样每个值只需要1位的存储空间就够了。当然除了存储经过编码后的数据，还需要存储一份记录该映射关系的字典（Dictionary），以便在读取的时候将编码值转换成对应的字符串。

位图索引用于快速定位到符合过滤条件的数据行号，减少读取的数据量，是数据仓库系统普遍使用的一种优化技术。和其他数据库索引（例如B+树索引）的逻辑概念类似，位图索引也是记录每个被索引的值到包含该值的行号列表的映射，即value -> rowid list。不同点在于，其他索引的rowid list使用链表或数组表示，而位图索引使用位图来表示rowid list。例如图2-3中的"[bing.com](http://bing.com/)"只出现在第四行，因此它对应的rowid list为位图[0,0,0,1]。

![图2-3 维度列的存储（以advertiser为例）](druid.assets/869ccf64-9976-4ece-8840-b8a81d742456.png)

采用位图表示rowid list的主要优势是可以通过高效的布尔运算找到满足多个过滤条件的行号。例如图2-4中，查询的过滤条件为publisher="[ultratrimfast.com](http://ultratrimfast.com/)" AND advertiser="[google.com](http://google.com/)"，Druid可以从publisher列的位图索引中找到"[ultratrimfast.com](http://ultratrimfast.com/)"对应的位图[0,1,1,1]，从advertiser列的位图索引中找到"[google.com](http://google.com/)"对应的位图[1,1,1,0]，然后对这两个位图做AND操作就能知道同时满足这两个过滤条件的行号。

采用位图表示rowid list的劣势是更高的存储开销。例如对8,000,000行数据建立位图索引，每个位图大约1MB。如果被索引的列有100个不同值，则该列的位图索引就大约有100MB。然而实际上由于位图可以很好地被压缩，并且存在直接对压缩后的位图进行布尔运算的算法（例如Druid使用的[Roaring Bitmap](http://roaringbitmap.org/)），存储效率的问题变得可以接受。

![图2-4 位图计算](druid.assets/616e3974-8894-4871-bc28-4a63a40136c9.png)

综上所述，**字典编码更紧凑地存储了维度列，而位图索引的应用可以大大提高处理过滤条件的性能**。

# 3 离线摄入与服务

围绕Segments，最简单的应用方式就是离线批量导入数据，提供查询服务。

## 3.1 数据导入

图3-1演示了Druid离线数据摄入的主要思想。首先通过[HadoopDruidIndexer](http://druid.io/docs/0.8.2/ingestion/batch-ingestion.html)提交Indexing作业，将输入数据转换为Segments文件。然后需要一个计算单元来处理每个Segment的数据分析，这个计算单元就是Druid中的 **Historical Node**。

![图3-1 Druid离线数据摄入](druid.assets/5c27d610-de66-4be1-a821-2f6e596243b4.png)

 Historical Node是Druid最主要的计算节点，用于处理对Segments的查询。在能够服务Segment之前， Historical Node需要首先将Segment从HDFS（或其他[Deep Storage](http://druid.io/docs/0.8.2/dependencies/deep-storage.html)）下载到本地磁盘，然后将Segment数据文件mmap到进程的地址空间。

Historical Node采用了Shared-Nothing架构，状态信息记录在Zookeeper中，可以很容易地进行伸缩。 Historical Node在Zookeeper中宣布自己和所服务的Segments，也通过Zookeeper接收加载/丢弃Segment的命令。

最后，由于Segment的不可变性，可以通过复制Segment到多个 Historical Node来实现容错和负载均衡。

## 3.2 查询处理

由于每个 Historical Node只负责一部分的Segments，当用户查询的Segments分布在多个 Historical Node上时，需要将查询分发给这些 Historical Node执行，合并各个 Historical Node的执行结果，才能得到最终的查询结果。这种Scatter-Gather的查询处理方式在并行计算系统中非常常见。在Druid中，负责接收并路由用户查询的角色叫做Broker Node，如图3-2所示。

![图3-2 Scatter-Gather查询处理](druid.assets/45bbcf7d-630f-468e-a795-ee8f2de79edf.png)



Broker Node也是“无状态”的，因此可以配置多个Broker Node来避免单点（SPoF）。Broker Node从Zookeeper中获取集群中存在哪些Segments，以及每个Segment分布在哪些 Historical Node的信息。Broker Node会自己保留一份“元信息”的快照，以备Zookeeper故障时使用。

除了协调整个查询的执行，Broker Node还承担着缓存查询结果的职责。由于Segments的不可变性，针对某个Segment的相同查询语句总是返回同样的查询结果，因此Segment查询结果的缓存只需要考虑淘汰机制，不需要考虑失效机制。

## 3.3 查询接口

用户可以通过HTTP提交查询，查询本身使用JSON来表达。

Druid包括三个主要的查询类型：[Timeseries](http://druid.io/docs/0.8.3/querying/timeseriesquery.html), [TopN](http://druid.io/docs/0.8.3/querying/topnquery.html), [GroupBy](http://druid.io/docs/0.8.2/querying/groupbyquery.html)。GroupBy是最灵活的查询类型，支持对多个维度进行过滤、分组，支持postAggregation，以及类似order by和limit的功能，但也是性能开销最大的查询类型。而Timeseries和TopN则是在特定场景下对GroupBy查询的优化。受篇幅限制，这里不详细介绍每种查询类型如何使用了，感兴趣的可以查阅文档，或者参考我们[为Druid适配的Star Schema Benchmark查询](http://git.sankuai.com/projects/DATA/repos/olap/browse/benchmarks/druid_queries)。下面简单介绍一下比较有Druid特色的TopN查询的实现思路。

TopN即按照某个（或某些）聚合值的特定排序规则，查看某个（或某些）维度排名前N的值。例如，查看最近一个月，美团总销售额最高的3个团购。TopN查询的实现难点和性能瓶颈主要来自于在对高基数（High Cardinality）维度计算TopN时，每个数据分区返回的结果集过大，导致合并结果集的开销很大。假设数据按天分区，有100万个团购项，那么最坏情况下，每个数据分区会返回100万行结果，计算一个月的数据总共需要合并3000万条结果。如果是查询花销最大的3个用户呢？很明显，中间结果集会更大。

Druid解决这个问题的方法是牺牲结果的准确度，换取查询性能的提升，即实现近似的TopN算法。具体的实现方式是每个分区（Druid中的每个Segment）只返回Top 1000的结果。例如先计算每天的Top 1000个团购项，再从中算出最近一月的Top 3的团购项。这种计算方式虽然既不保证结果排名的正确性，又不保证结果聚合值的正确性（可能比实际的聚合值小），但在实际场景下却能很好地工作，因为很多业务场景都满足全局TopN来自于各数据分区Top M（M >> N）的特点。

另外，当被聚合维度的基数小于1000时，TopN返回的结果就一定是精确的了。在这种情况下，Druid仍然推荐使用TopN查询，主要原因是TopN查询针对单维度的聚集做了优化（使用数组集合代替HashMap聚合），因此性能会更好。

# 4 实时摄入与服务

第2节和第3节介绍的内容已经能够实现交互式查询了，本节介绍如何实现低数据延迟。由于实时数据摄入并不是我们目前关注的重点，因此这部分只做简要介绍，我们本身也没有实践过。

低数据延迟依赖系统具有实时数据摄入，以及对摄入的数据提供查询的能力。在Druid中，负责这部分工作的节点叫做RealTime Node。

RealTime Node可以从Kafka等[数据源](http://druid.io/docs/0.8.2/ingestion/firehose.html)实时消费事件数据，并通过实时索引提供对这些数据的查询服务。RealTime Node的实时索引只保留最新的数据，老的数据会被周期性的转换成Segments，先存储在本地磁盘的临时目录，再上传到DeepStorage并通知Historical Node下载。在Segment被Historical Node服务之前，该Segment的查询由RealTime Node提供。为了避免RealTime Node的堆内存OOM，Segment会被加载到off heap内存。该过程如图4-1所示。

![图4-1 RealTime Node同时提供In-Memory Index和Persisted Index的查询](druid.assets/c24b2d72-94dd-4f29-b020-8717f449e579.png)



与Segment采用Read-Optimized结构不同，RealTime Node的In-Memory Index是Write-Optimized结构，用来支撑数据摄入的高吞吐率。

RealTime Node与Historical Node提供完全相同的查询接口，这样Broker Node就可以从RealTime Node获得最新数据的查询结果，从Historical Node获得历史数据的查询结果。Segments可以完全由RealTime Indexing产生，即完全通过流式处理，类似Storm，但是具有更强大的交互查询能力。也可以采用如图4-2所示的[Lambda架构](https://en.wikipedia.org/wiki/Lambda_architecture)，即同时采用流式处理和批处理，既能提供查询实时数据的能力，又能保证数据的准确性（批处理产生的Segments具有更高的版本号，覆盖流处理产生的Segments）。

![图4-2 ](druid.assets/ea99d68c-26b5-4802-b6e5-a1f3df89e51d.png)

# 5 总体架构

讲到这里，我们可以直接来看Druid的总体架构（图5-1），把前面提到的各个部分串联起来。

![图5-1 Druid总体架构](druid.assets/4484b206-41d4-4b97-94e1-c4ad287b60f5.png)



图中，RealTime Node，Historical Node和Broker Node已经前面章节已经详述过了，它们是数据摄入和查询处理的主要角色。这里多出来一个Coordinator Node，它是干什么的呢？

## 5.1 Coordinator Node

3.1节有提到，由于Segments的不可变性，因此可以通过复制、移动Segment到其他Historical Node实现容错和负载均衡。而这些决策就是由Coordinator Node来完成的。

因此简而言之，Coordinator Node就是管理Segment在各个Historical Node存储的决策者。它会周期性的分析当前集群的Segments分布情况，决定哪些Segments需要移动，哪些Segments需要复制，并通过Zookeeper向Historical Node下达装载/移除Segments的命令。

Coordinator Node有两个外部依赖，Zookeeper和MySQL（或其他[Metadata Storage](http://druid.io/docs/0.8.2/dependencies/metadata-storage.html)）。

## 5.2 Zookeeper

Zookeeper在Druid集群中承担了多个职能，包括：

1）维护集群的当前状态。例如记录当前活跃的Historical Node列表

2）充当节点间通讯的媒介。例如上面提到的Coordinator Node与Historical Node是间接通过Zookeeper通讯的

3）选主。例如用户可以配置多个Coordinator Node，它们之间通过Zookeeper选主

## 5.3 MySQL

MySQL中记录了一些“不适合”存储在Zookeeper中的元信息，例如：

1）集群可用的Segments元信息

2）用于均衡Segments的[规则](http://druid.io/docs/0.8.2/operations/rule-configuration.html)配置

3）配置变更的审计日志

# 6 性能评估

我们使用[Star Schema Benchmark](http://wiki.sankuai.com/pages/viewpage.action?pageId=401941066)（下文简称“SSB”）对Druid的性能进行了测试，具体的测试集群配置和测试方法见[《StarSchemaBenchmark测试计划-2.4Druid》](https://km.sankuai.com/page/28286962#StarSchemaBenchmark测试计划-2.4Druid)。

## 6.1 数据导入效率

数据导入效率（包括导入时间和数据膨胀率）是衡量OLAP系统的重要指标之一。与预计算系统相比，Druid在导入时只需要对数据进行轻度汇总，不需要枚举计算所有维度的组合，因此导入时间和数据膨胀率都要相对小很多。实际的测试数据也印证了这一点。

| 数据规模 | 数据行数      | 原始数据大小 | Druid导入时间 | Kylin导入时间 | Druid Segment平均大小 |
| -------- | ------------- | ------------ | ------------- | ------------- | --------------------- |
| SF2      | 11,998,051    | 4.6G         | 6分钟         | 103分钟       | 6MB                   |
| SF20     | 119,994,746   | 46.7G        | 22分钟        | 138分钟       | 58MB                  |
| SF200    | 1,200,018,603 | 471.4G       | 80分钟        | 240分钟       | 520MB                 |



## 6.2 Scan & Aggregate效率

Scan和Aggregate作为OLAP查询处理中的两个基础运算，它们的执行效率可以基本反映一个OLAP系统的查询处理效率。我们使用单核每秒处理的行数（rows/sec/core）来反映这两个操作的速率，实际生产环境中可以通过增加并行度来提升总体的速率。

Scan速率测试查询：

```
{
  "queryType": "timeseries",
  "dataSource": "ssb_sf200",
  "granularity": "all",
  "aggregations": [
    { "type": "count", "name": "count" }
  ],
  "intervals": [ "1991-01-01/1999-01-01" ]
}
```

测试结果说明Druid单核的Scan速率大约为60~80M行每秒。

| 工作线程数 | 时间(s) | rows/sec | rows/sec/core |
| ---------- | ------- | -------- | ------------- |
| 16         | 1.176   | 1020M    | 63M           |
| 8          | 1.81    | 666M     | 83M           |
| 4          | 3.66    | 327M     | 81M           |

Aggregate速率测试查询：

```
{
  "queryType": "timeseries",
  "dataSource": "ssb_sf200",
  "granularity": "all",
  "aggregations": [
    { "type": "longSum", "name": "revenue", "fieldName": "lo_revenue" }
  ],
  "intervals": [ "1991-01-01/1999-01-01" ]
}
```

测试结果说明Druid单核的Aggregate速率大约为14~18M行每秒。

| 工作线程数 | 时间(s) | rows/sec | rows/sec/core |
| ---------- | ------- | -------- | ------------- |
| 4          | 16.87   | 71M      | 17.8M         |
| 8          | 9.04    | 132M     | 16.6M         |
| 16         | 5.3     | 226M     | 14M           |

作为对比，Druid社区给出的[测试结果](http://druid.io/blog/2014/03/17/benchmarking-druid.html)为Scan速率53.5M行每秒，Aggregate速率为36.2M行每秒。测试方法的不同导致结果有差异，但是在同一个数量级。

## 6.3 SSB测试结果

图6-1展示了Druid在三种数据规模下的SSB测试结果。关于测试方法，额外说明几点：

1）机器的物理内存为128G，足够装下三个数据集。并且图中的测试结果是在数据集已经完全加载到page cache后得到的。

2）图中每个查询的执行时间取的是三次执行的均值，并且测试时禁用了Broker Node和Historical Node的结果缓存。

3）三种数据规模的segment数都是80，并且所有基准查询的intervals都为“1991-01-01/1999-01-01”，日期限制是通过对维度属性的Filter条件指定的。因此，每个查询都需要处理所有80个Segments。

![图6-1 Druid SSB测试结果](druid.assets/1ca6a1aa-7ad5-4d56-b010-fafdf3d84a19.png)

从图中可以看出：

1）在中小数据规模（SF2/SF20）下，几乎所有查询都能在1秒内返回结果；大数据规模（SF200）下，查询响应时间方差较大，个别查询执行较慢。

2）每组查询，随着满足过滤条件的行数递减，查询执行时间也随之递减。

我们通过打开[性能metrics](http://druid.io/docs/latest/operations/metrics.html)对执行较慢的查询进行了分析，发现影响性能的主要原因有两点：

1）这些查询使用了[JavaScript过滤器](http://druid.io/docs/0.8.2/querying/filters.html#javascript-filter)，因此无法利用Segment的位图索引进行快速过滤。例如执行最慢的[Q1-1](http://git.sankuai.com/mvc/projects/DATA/repos/olap/browse/benchmarks/druid_queries/Q1-1.json)只包含一个非JavaScript过滤器"d_year=1993"，过滤因子为1/7。而[Q1-2](http://git.sankuai.com/mvc/projects/DATA/repos/olap/browse/benchmarks/druid_queries/Q1-2.json)非JavaScript过滤器的过滤因子为1/84，因此执行要快很多。

2）所有查询都需要处理80个Segments，而Historical Node设置的工作线程数为31，因此需要执行三轮。

所以，我们可以通过以下途径提升查询性能：

1）对时间范围的筛选尽量通过查询的intervals属性指定，减少需要处理segment数量

2）避免使用JavaScript过滤器以充分利用位图索引。然而，由于Druid把所有维度属性都看做string类型，目前对数值型维度的范围过滤条件只能通过JavaScript过滤器实现。

3）合理配置工作线程数，推荐为cores - 1

4）部署多个Historical Node提升查询处理的并发度

## 6.4 扩展性

为了评估Druid的可扩展性，验证通过提高并发度提升查询性能的可行性，我们测试了部署两个Historical Node时，执行SF200的测试结果，并与前面只有一个Historical Node的结果进行对比，见图6-2。

![图6-2 增加Historical Node前后性能对比](druid.assets/00fadc82-d72c-4ca7-a7d3-8b2ae7419027.png)

可以看出，对于之前执行较慢的查询，扩容后的查询性能提升了将近1倍，验证了我们在上一节的慢查询分析结论。

扩容后主要的性能损失来自于增加的Broker Node开销，这点对于GroupBy查询（Q2/Q3/Q4组）比较明显。而对于扩容前就很快的查询，例如Q3-2/Q3-3/Q3-4/Q4-3，性能的提升就更小了，这也在情理之中。

另外值得一提的是，Druid的扩容操作是比较简单的。启动新的Historical Node后，Coordinator Node会通过Zookeeper自动发现新节点，并开始均衡数据，均衡的效果也很理想，见下表。

| Host                    | Type       | Max Size        | Current Size   | Percent Used |
| ----------------------- | ---------- | --------------- | -------------- | ------------ |
| rz-data-hdp-dn1340:8081 | historical | 300,000,000,000 | 23,939,293,179 | 7.979764393  |
| rz-data-hdp-dn1342:8080 | historical | 300,000,000,000 | 23,349,763,725 | 7.783254575  |

## 6.5 小节

Druid的整体性能表现令人满意。一方面，由于数据导入时只对数据做轻度汇总，Druid的导入速度快，数据膨胀率低。另一方面，通过采用内存计算、列式存储、位图索引等技术，Druid可以达到单核每秒6000万行的Scan速率以及单核每秒1400万行的Aggregate速率，并且能够通过水平扩展Historical Node来处理更大的数据集，实现交互式的查询体验。

然而我们也注意到，Druid的性能表现和集群配置是否合理有很强的相关性，这增加了Druid的使用门槛和运维成本。在处理大数据集时，用户需要根据数据集的规模以及查询的模式特点合理地选择硬件配置、节点配置、甚至是优化查询语句。一方面这要求用户对Druid的原理有比较深入的了解，另一方面配置调优的过程本身也可能是一个试错迭代的过程。

# 7 总结

Druid的出现解决了以Hadoop为核心的数据平台的两个固有问题：

1）OLAP查询的性能问题

2）从数据产生到数据产生价值的延迟问题

为了解决问题一，Druid从搜索引擎、列式存储数据库中获取灵感，将原始数据转为Read-Optimized结构，并通过内存计算提升查询性能。（Historical Node）

为了解决问题二，Druid借鉴流式处理系统，直接从消息系统摄入数据，并通过实时索引构建，响应对实时数据的查询。（RealTime Node）

巧妙的是，Druid利用事件数据的不可变性，通过Segment的Handoff，实现了在一个系统中同时解决上面的两个问题。

架构上，Druid可以和Kafka、Storm等开源系统构成Realtime Analytics Data Stack ([RAD Stack](http://druid.io/blog/2014/05/07/open-source-leaders-sound-off-on-the-rise-of-the-real-time-data-stack.html))，实现Realtime Data Pipeline和Realtime Data Serving的一条龙服务。也可以和现有的Hadoop Data Pipeline整合，走Lambda架构。

性能上，Druid比预计算系统的数据导入效率更高，并且通过合理的配置，可以实现十亿数据的秒级查询。

# 8 参考文献

\1) Introducing Druid, http://druid.io/blog/2011/04/30/introducing-druid.html

\2) Druid Paper, http://static.druid.io/docs/druid.pdf

\3) Druid Segment, http://druid.io/docs/0.8.2/design/segments.html

\4) Not Exactly! Fast Queries Via Approximation Algorithms, https://www.youtube.com/watch?v=Hpd3f_MLdXo

5）Real Time Analytics with Open Source Technologies, https://www.youtube.com/watch?v=kJMYVpnW_AQ