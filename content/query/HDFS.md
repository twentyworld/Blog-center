---
title: HDFS
type: docs
---

# HDFS

## 1. 背景

在现代的企业环境中，单机容量往往无法存储大量数据，需要跨机器存储。统一管理分布在集群上的文件系统称为分布式文件系统。而一旦在系统中，引入网络，就不可避免地引入了所有网络编程的复杂性，例如挑战之一是如果保证在节点不可用的时候数据不丢失。

传统的网络文件系统（NFS）虽然也称为分布式文件系统，但是其存在一些限制。由于NFS中，文件是存储在单机上，因此无法提供可靠性保证，当很多客户端同时访问NFS Server时，很容易造成服务器压力，造成性能瓶颈。另外如果要对NFS中的文件中进行操作，需要首先同步到本地，这些修改在同步到服务端之前，其他客户端是不可见的。某种程度上，NFS不是一种典型的分布式系统，虽然它的文件的确放在远端（单一）的服务器上面。

## 2. HDFS设计原则

HDFS设计之初就非常明确其应用场景，适用与什么类型的应用，不适用什么应用，有一个相对明确的指导原则。

### 2.1 设计目标

- **存储非常大的文件**：这里非常大指的是几百M、G、或者TB级别。实际应用中已有很多集群存储的数据达到PB级别。

  > 根据Hadoop官网，Yahoo！的Hadoop集群约有10万颗CPU，运行在4万个机器节点上。更多世界上的Hadoop集群使用情况，参考[Hadoop官网](https://wiki.apache.org/hadoop/PoweredBy).

- **采用流式的数据访问方式**: HDFS基于这样的一个假设：<u>最有效的数据处理模式是一次写入、多次读取数据集经常从数据源生成或者拷贝一次，然后在其上做很多分析工作 。</u>分析工作经常读取其中的大部分数据，即使不是全部。 因此读取整个数据集所需时间比读取第一条记录的延时更重要。

- **运行于商业硬件上**: Hadoop不需要特别贵的、reliable的（可靠的）机器，可运行于普通商用机器（可以从多家供应商采购） ，商用机器不代表低端机器。在集群中（尤其是大的集群），节点失败率是比较高的HDFS的目标是确保集群在节点失败的时候不会让用户感觉到明显的中断。

### 2.2 HDFS不适合的应用类型

有些场景不适合使用HDFS来存储数据。下面列举几个：

1） **低延时的数据访问** 
对延时要求在毫秒级别的应用，不适合采用HDFS。HDFS是为高吞吐数据传输设计的,因此可能牺牲延时HBase更适合低延时的数据访问。

2）**大量小文件** 
文件的元数据（如目录结构，文件block的节点列表，block-node mapping）保存在NameNode的内存中， 整个文件系统的文件数量会受限于NameNode的内存大小。 
经验而言，一个文件/目录/文件块一般占有150字节的元数据内存空间。如果有100万个文件，每个文件占用1个文件块，则需要大约300M的内存。因此十亿级别的文件数量在现有商用机器上难以支持。

3）**多方读写，需要任意的文件修改** 
HDFS采用追加（append-only）的方式写入数据。不支持文件任意offset的修改。不支持多个写入器（writer）。

## 3. HDFS核心概念

### 3.1 Blocks

物理磁盘中有块的概念，磁盘的物理Block是磁盘操作最小的单元，读写操作均以Block为最小单元，一般为512 Byte。文件系统在物理Block之上抽象了另一层概念，文件系统Block物理磁盘Block的整数倍。通常为几KB。Hadoop提供的df、fsck这类运维工具都是在文件系统的Block级别上进行操作。

HDFS的Block块比一般单机文件系统大得多，默认为128M。HDFS的文件被拆分成block-sized的chunk，chunk作为独立单元存储。比Block小的文件不会占用整个Block，只会占据实际大小。例如， 如果一个文件大小为1M，则在HDFS中只会占用1M的空间，而不是128M。

**HDFS的Block为什么这么大？** 
是为了最小化查找（seek）时间，控制定位文件与传输文件所用的时间比例。假设定位到Block所需的时间为10ms，磁盘传输速度为100M/s。如果要将定位到Block所用时间占传输时间的比例控制1%，则Block大小需要约100M。 
但是如果Block设置过大，在MapReduce任务中，Map或者Reduce任务的个数 如果小于集群机器数量，会使得作业运行效率很低。

**Block抽象的好处** 
block的拆分使得单个文件大小可以大于整个磁盘的容量，构成文件的Block可以分布在整个集群， 理论上，单个文件可以占据集群中所有机器的磁盘。 
Block的抽象也简化了存储系统，对于Block，无需关注其权限，所有者等内容（这些内容都在文件级别上进行控制）。 
Block作为容错和高可用机制中的副本单元，即以Block为单位进行复制。

### 3.2 Namenode & Datanode

整个HDFS集群由Namenode和Datanode构成master-worker（主从）模式。Namenode负责构建命名空间，管理文件的元数据等，而Datanode负责实际存储数据，负责读写工作。

#### Namenode

Namenode存放文件系统树及所有文件、目录的元数据。元数据持久化为2种形式：

- namespcae image
- edit log

但是持久化数据中不包括Block所在的节点列表，及文件的Block分布在集群中的哪些节点上，这些信息是在系统重启的时候重新构建（通过Datanode汇报的Block信息）。 
在HDFS中，Namenode可能成为集群的单点故障，Namenode不可用时，整个文件系统是不可用的。HDFS针对单点故障提供了2种解决机制： 
1）**备份持久化元数据** 
将文件系统的元数据同时写到多个文件系统， 例如同时将元数据写到本地文件系统及NFS。这些备份操作都是同步的、原子的。

2）**Secondary Namenode** 
Secondary节点定期合并主Namenode的namespace image和edit log， 避免edit log过大，通过创建检查点checkpoint来合并。它会维护一个合并后的namespace image副本， 可用于在Namenode完全崩溃时恢复数据。

Secondary Namenode通常运行在另一台机器，因为合并操作需要耗费大量的CPU和内存。其数据落后于Namenode，因此当Namenode完全崩溃时，会出现数据丢失。 通常做法是拷贝NFS中的备份元数据到Second，将其作为新的主Namenode。 
在HA（High Availability高可用性）中可以运行一个Hot Standby，作为热备份，在Active Namenode故障之后，替代原有Namenode成为Active Namenode。

#### Datanode

数据节点负责存储和提取Block，读写请求可能来自namenode，也可能直接来自客户端。数据节点周期性向Namenode汇报自己节点上所存储的Block相关信息。

### 3.3 Block Caching

DataNode通常直接从磁盘读取数据，但是频繁使用的Block可以在内存中缓存。默认情况下，一个Block只有一个数据节点会缓存。但是可以针对每个文件可以个性化配置。 
作业调度器可以利用缓存提升性能，例如MapReduce可以把任务运行在有Block缓存的节点上。 
用户或者应用可以向NameNode发送缓存指令（缓存哪个文件，缓存多久）， 缓存池的概念用于管理一组缓存的权限和资源。

### 3.4 HDFS Federation

我们知道NameNode的内存会制约文件数量，HDFS Federation提供了一种横向扩展NameNode的方式。在Federation模式中，每个NameNode管理命名空间的一部分，例如一个NameNode管理/user目录下的文件， 另一个NameNode管理/share目录下的文件。 
每个NameNode管理一个namespace volumn，所有volumn构成文件系统的元数据。每个NameNode同时维护一个Block Pool，保存Block的节点映射等信息。各NameNode之间是独立的，一个节点的失败不会导致其他节点管理的文件不可用。 
客户端使用mount table将文件路径映射到NameNode。mount table是在Namenode群组之上封装了一层，这一层也是一个Hadoop文件系统的实现，通过viewfs:协议访问。

### 3.5 HDFS HA(High Availability高可用性)

在HDFS集群中，NameNode依然是单点故障（SPOF: Single Point Of Failure）。元数据同时写到多个文件系统以及Second NameNode定期checkpoint有利于保护数据丢失，但是并不能提高可用性。 
这是因为NameNode是唯一一个对文件元数据和file-block映射负责的地方， 当它挂了之后，包括MapReduce在内的作业都无法进行读写。

当NameNode故障时，常规的做法是使用元数据备份重新启动一个NameNode。元数据备份可能来源于：

- 多文件系统写入中的备份
- Second NameNode的检查点文件

启动新的Namenode之后，需要重新配置客户端和DataNode的NameNode信息。另外重启耗时一般比较久，稍具规模的集群重启经常需要几十分钟甚至数小时，造成重启耗时的原因大致有： 
1） 元数据镜像文件载入到内存耗时较长。 
2） 需要重放edit log 
3） 需要收到来自DataNode的状态报告并且满足条件后才能离开安全模式提供写服务。

#### Hadoop的HA方案

采用HA的HDFS集群配置两个NameNode，分别处于Active和Standby状态。当Active NameNode故障之后，Standby接过责任继续提供服务，用户没有明显的中断感觉。一般耗时在几十秒到数分钟。 
HA涉及到的主要实现逻辑有

1） **主备需共享edit log存储。** 
主NameNode和待命的NameNode共享一份edit log，当主备切换时，Standby通过回放edit log同步数据。 
共享存储通常有2种选择

- NFS：传统的网络文件系统
- QJM：quorum journal manager

QJM是专门为HDFS的HA实现而设计的，用来提供高可用的edit log。QJM运行一组journal node，edit log必须写到大部分的journal nodes。通常使用3个节点，因此允许一个节点失败，类似ZooKeeper。注意QJM没有使用ZK，虽然HDFS HA的确使用了ZK来选举主Namenode。一般推荐使用QJM。

2）**DataNode需要同时往主备发送Block Report** 
因为Block映射数据存储在内存中（不是在磁盘上），为了在Active NameNode挂掉之后，新的NameNode能够快速启动，不需要等待来自Datanode的Block Report，DataNode需要同时向主备两个NameNode发送Block Report。

3）**客户端需要配置failover模式**（失效备援模式，对用户透明） 

Namenode的切换对客户端来说是无感知的，通过客户端库来实现。客户端在配置文件中使用的HDFS URI是逻辑路径，映射到一对Namenode地址。客户端会不断尝试每一个Namenode地址直到成功。

4）**Standby替代Secondary NameNode** 
如果没有启用HA，HDFS独立运行一个守护进程作为Secondary Namenode。定期checkpoint，合并镜像文件和edit日志。

如果当主Namenode失败时，备份Namenode正在关机（停止 Standby），运维人员依然可以从头启动备份Namenode，这样比没有HA的时候更省事，算是一种改进，因为重启整个过程已经标准化到Hadoop内部，无需运维进行复杂的切换操作。

NameNode的切换通过代failover controller来实现。failover controller有多种实现，默认实现使用ZooKeeper来保证只有一个Namenode处于active状态。

每个Namenode运行一个轻量级的failover controller进程，该进程使用简单的心跳机制来监控Namenode的存活状态并在Namenode失败时触发failover。Failover可以由运维手动触发，例如在日常维护中需要切换主Namenode，这种情况graceful(优雅的) failover，非手动触发的failover称为ungraceful failover。

在ungraceful failover的情况下，没有办法确定失败（被判定为失败）的节点是否停止运行，也就是说触发failover后，之前的主Namenode可能还在运行。QJM一次只允许一个Namenode写edit log，但是之前的主Namenode仍然可以接受读请求。Hadoop使用fencing来杀掉之前的Namenode。Fencing通过收回之前Namenode对共享的edit log的访问权限、关闭其网络端口使得原有的Namenode不能再继续接受服务请求。使用STONITH技术也可以将之前的主Namenode关机。

最后，HA方案中Namenode的切换对客户端来说是不可见的，前面已经介绍过，主要通过客户端库来完成。