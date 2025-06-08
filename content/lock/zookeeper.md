# 章节目录
- [章节目录](#章节目录)
- [1. zookeeper 是什么](#1-zookeeper-是什么)
  - [1.1. zookeeper的设计目标](#11-zookeeper的设计目标)
- [2. Zookeeper的实现逻辑](#2-zookeeper的实现逻辑)
  - [2.1. Znode](#21-znode)
    - [2.1.1. znode的字段](#211-znode的字段)
      - [2.1.1.1. zxid 说明](#2111-zxid-说明)
      - [2.1.1.2. version 说明](#2112-version-说明)
      - [2.1.1.3. ACL(Access Control List,访问控制列表 )](#2113-aclaccess-control-list访问控制列表-)
    - [2.1.2. zookeeper的节点类型](#212-zookeeper的节点类型)
      - [2.1.2.1. 持久节点](#2121-持久节点)
      - [2.1.2.2. 持久顺序节点](#2122-持久顺序节点)
      - [2.1.2.3. 临时节点(EPHEMERAL)](#2123-临时节点ephemeral)
      - [2.1.2.4. 临时顺序节点(EPHEMERAL SEQUENTIAL)](#2124-临时顺序节点ephemeral-sequential)
    - [2.1.3. 节点客户端方法](#213-节点客户端方法)
  - [2.2. Watches](#22-watches)
    - [2.2.1. watches架构](#221-watches架构)
      - [2.2.1.1. 监听的作用域](#2211-监听的作用域)
      - [2.2.1.2. watch注册流程](#2212-watch注册流程)
      - [2.2.1.3. Watcher通知流程](#2213-watcher通知流程)
    - [2.2.2. watches 示例](#222-watches-示例)
- [3. ZAB 选举与一致性](#3-zab-选举与一致性)
  - [3.1. 概念理解](#31-概念理解)
    - [3.1.1. Zookeeper 服务器的角色](#311-zookeeper-服务器的角色)
    - [3.1.2. Zookeeper 服务器的状态](#312-zookeeper-服务器的状态)
    - [3.1.3. Zookeeper 通信](#313-zookeeper-通信)
    - [3.1.4. Zookeeper 集群](#314-zookeeper-集群)
  - [3.2. ZAB 协议](#32-zab-协议)
    - [3.2.1. ZAB 协议上的一些基础概念](#321-zab-协议上的一些基础概念)
      - [3.2.1.1. **election epoch**](#3211-election-epoch)
      - [3.2.1.2. zxid](#3212-zxid)
    - [3.2.2. ZAB 协议的几个阶段](#322-zab-协议的几个阶段)
    - [3.2.3. 触发选主的场景](#323-触发选主的场景)
      - [3.2.3.1. leader节点异常](#3231-leader节点异常)
      - [3.2.3.2. 多数Follower节点异常](#3232-多数follower节点异常)
  - [3.3. ZAB 选主阶段](#33-zab-选主阶段)
    - [3.3.1. 启动中的Leader选举](#331-启动中的leader选举)
    - [3.3.2. 运行中的leader选举](#332-运行中的leader选举)
    - [3.3.3. Leader选举的代码实现](#333-leader选举的代码实现)
- [4. zookeeper的一些实现](#4-zookeeper的一些实现)
  - [4.1. 配置(注册)中心](#41-配置注册中心)
  - [4.2. 分布式锁](#42-分布式锁)
  - [4.3. 分布式队列](#43-分布式队列)
  - [4.4. 分布式ID生成](#44-分布式id生成)
# 1. zookeeper 是什么
依据官方网站：
> ZooKeeper is a centralized service for maintaining configuration information, naming, providing distributed synchronization, and providing group services.All of these kinds of services are used in some form or another by distributed applications. Each time they are implemented there is a lot of work that goes into fixing the bugs and race conditions that are inevitable. Because of the difficulty of implementing these kinds of services, applications initially usually skimp on them, which make them brittle in the presence of change and difficult to manage. Even when done correctly, different implementations of these services lead to management complexity when the applications are deployed.

翻译成中文，可以简单的来说：**Zookeeper是一个高性能，分布式的，开源分布式应用协调服务**。zookeeper主要开源实现了Google的Chubby。
<u>ZooKeeper是一个典型的分布式数据一致性的解决方案，分布式应用程序可以基于它实现诸如数据发布/订阅、负载均衡、命名服务。分布式协调/通知。集群管理、Master选举、分布式锁和分布式队列等功能。</u>它就像一个同时运行在很多主机上的文件系统，只要集群中有超过一半的主机有效，则这个“文件系统”上所有（有效）主机上面的数据都是一致的，其中内部数据看起来就像文件系统一样，也是/app1/p_1这种样式，只不过它每一层都是节点（Znode），比如app1这个节点，它既是数据本身（可以存放数据），也是“目录”，它的下一层的节点是它的子节点。我们对Zookeeper的操作也就是对这个结构的增删查改操作。

![zookeeper](https://raw.githubusercontent.com/twentyworld/knowledge-island/master/谨记/zookeeper-image/zookeeper.png)

## 1.1. zookeeper的设计目标

1.**最终一致性**：<u>client不论连接到哪个Server，展示给它都是同一个视图，这是zookeeper最重要的功能。</u>

2.**可靠性**：<u>具有简单、健壮、良好的性能，如果消息m被到一台服务器接受，那么它将被所有的服务器接受。</u>

3.**实时性**：<u>Zookeeper保证客户端将在一个时间间隔范围内获得服务器的更新信息，或者服务器失效的信息。</u>但由于网络延时等原因，Zookeeper不能保证两个客户端能同时得到刚更新的数据，如果需要最新数据，应该在读数据之前调用sync()接口。

4.**等待无关（wait-free）**：<u>慢的或者失效的client不得干预快速的client的请求，使得每个client都能有效的等待</u>。

5.**原子性**：更新只能成功或者失败，没有中间状态。

6**.顺序性**：<u>包括全局有序和偏序两种：全局有序是指如果在一台服务器上消息a在消息b前发布，则在所有Server上消息a都将在消息b前被发布；偏序是指如果一个消息b在消息a后被同一个发送者发布，a必将排在b前面。</u>

关于更多的特性，可以去官网的概论查看，如果想获得更好的体验，[可点击前往][zookeepe-overview]。

# 2. Zookeeper的实现逻辑

## 2.1. Znode

### 2.1.1. znode的字段

> 关于官网中，对znode的描述在这篇文档里，如果有兴趣可以[点击前往][zookeeper-znode]。

znode主要有一下字段：

```c
struct{
    czxid;// create ZXID，即该数据节点被创建时的事务id
    mzxid;// modified ZXID，即该节点最终一次更新时的事务id
    pzxid;// 该节点的子节点列表最后一次修改时的事务id，只有子节点列表变更才会更新pZxid，子节点内容变更不会更新
    ctime;// create time，即该节点的创建时间
    mtime;// modified time，即该节点最后一次的更新时间
    version;// 数据节点内容版本号，节点创建时为0，每更新一次节点内容(不管内容有无变化)该版本号的值增加1
    cversion;//子节点版本号，当前节点的子节点每次变化时值增加1
    aversion;// 节点的ACL版本号，表示该节点ACL信息变更次数
    ephemeralOwner;// 创建该临时节点的会话的sessionId；如果当前节点为持久节点，则ephemeralOwner=0
    dataLength;// 数据节点内容长度
    numChildren;// 当前节点的子节点个数
}
```

一些关键的解释：

#### 2.1.1.1. zxid 说明

事务id。Zookeeper中每个变化都会产生一个全局唯一的zxid。通过它可确定更新操作的先后顺序。例如，zxid1小于zxid2，则说明zxid1操作先执行，zxid2后执行； zxid对于整个Zookeeper都是唯一的，即使操作的是不同的znode。

#### 2.1.1.2. version 说明

<u>就是本文上面字段中的version。</u>每一个znode都有一个数据版本号，每次对znode做更新操作时值自增。ZooKeeper中一些更新操作，例如setData和delete根据版本号有条件地执行。多个客户端对同一个znode进行更新操作时，因为数据版本号，才能保证更新操作的先后顺序性。例如，客户端A正在对znode节点做更新操作，此时如果另一个客户端B同时更新了这个znode，则A的版本号已经过期，那么A调用setData不会成功。

#### 2.1.1.3. ACL(Access Control List,访问控制列表 )

ZooKeeper提供了一套完善的ACL权限控制机制保障数据安全性。

- 对于身份认证，提供了以下几种方式。

| 身份认证方式 | 解释                                                         |
| ------------ | ------------------------------------------------------------ |
| world        | 默认方式，所有用户都可无条件访问，组合形式为：world:anyone:[permissions] |
| digest       | 用户名:密码认证方式，最常用，组合形式为：digest:username:BASE64(SHA1(password)):[permissions] |
| ip           | 对指定ip进行限制，组合形式为：ip:127.0.0.1:[permissions]     |
| auth         | 认证登录形式，需要用户获取权限后才可访问，组合形式为 auth:userpassword:[permissions] |

对于znode权限，提供了以下5种操作权限。

| 权限   | 简写 | 解释                                               |
| ------ | ---- | -------------------------------------------------- |
| CREATE | C    | 允许授权对象在当前节点下创建子节点                 |
| DELETE | D    | 允许授权对象在当前节点下删除子节点                 |
| WRITE  | W    | 允许授权对象在当前节点进行更新操作                 |
| READ   | R    | 允许授权对象在当前节点获取节点内容或获取子节点列表 |
| ADMIN  | A    | 允许授权对象对当前节点进行ACL相关的设置操作        |

### 2.1.2. zookeeper的节点类型

<u>在 ZooKeeper中,每个数据节点都是有生命周期的,其生命周期的长短取决于数据节点的节点类型。</u>

在 ZooKeeper中,节点类型可以分为**持久节点(PERSISTENT)、临时节点(EPHEMERAL)和顺序节点(SEQUENTIAL)三大类**,具体在节点创建过程中,通过组合使用,可以生成以下四种组合型节点类型:

#### 2.1.2.1. 持久节点

持久节点是 ZooKeeper中最常见的一种节点类型。<u>所谓持久节点,是指该数据节点被创建后，就会一直存在于 ZooKeeper服务器上，直到有删除操作来主动清除这个节点。</u>

#### 2.1.2.2. 持久顺序节点

持久顺序节点的基本特性和持久节点是一致的，额外的特性表现在顺序性上。<u>在ZooKeeper中，每个父节点都会为它的第一级子节点维护一份顺序，用于记录下每个子节点创建的先后顺序。</u> 基于这个顺序特性，**在创建子节点的时候，可以设置这个标记，那么在创建节点过程中,，ZooKeeper会自动为给定节点名加上一个数字后缀，作为一个新的、完整的节点名。**另外需要注意的是,这个数字后缀的上限是整型的最大值。

#### 2.1.2.3. 临时节点(EPHEMERAL)

<u>和持久节点不同的是，临时节点的生命周期和客户端的会话绑定在一起，也就是说，如果客户端会话失效，那么这个节点就会被自动清理掉。</u>注意，**这里提到的是客户端会话失效，而非TCP连接断开**。另外，ZooKeeper规定了不能基于临时节点来创建子节点，即临时节点只能作为叶子节点。

#### 2.1.2.4. 临时顺序节点(EPHEMERAL SEQUENTIAL)

临时顺序节点的基本特性和临时节点也是一致的，同样是在临时节点的基础上，添加了顺序的特性。

### 2.1.3. 节点客户端方法

略，可实验查看，本身方法不多，多为path方法和watch方法

## 2.2. Watches

> 同样，zookeeper官网也对watches做了一下详尽的介绍，如果感兴趣，[可以前往查看][zookeeper-watches]。
>
> 这里引入一篇文章，对于watches的描述比较细致，同时有关于zk是如何实现watches的，有兴趣可以点击前往：[[zookeeper]zookeeper系列三：zookeeper中watcher的使用及原理][https://blog.csdn.net/zkp_java/article/details/82711810]

  Zookeeper提供了数据的发布/订阅功能，多个订阅者可同时监听某一特定主题对象，当该主题对象的自身状态发生变化时(例如节点内容改变、节点下的子节点列表改变等)，会实时、主动通知所有订阅者。<u>该机制在被订阅对象发生变化时会异步通知客户端，因此客户端不必在Watcher注册后轮询阻塞，从而减轻了客户端压力。</u>

### 2.2.1. watches架构

Watcher实现由三个部分组成：

- Zookeeper服务端
- Zookeeper客户端
- 客户端的ZKWatchManager对象

客户端首先将Watcher注册到服务端，同时将Watcher对象保存到客户端的Watch管理器中。当ZooKeeper服务端监听的数据状态发生变化时，服务端会主动通知客户端，接着客户端的Watch管理器会触发相关Watcher来回调相应处理逻辑，从而完成整体的数据发布/订阅流程。

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/谨记/zookeeper-image/watches.png" alt="watches 架构" style="zoom:50%;" />

zk客户端向zk服务器注册watcher的同时，会将watcher对象存储在客户端的watchManager。

**Zk服务器触发watcher事件后，会向客户端发送通知，客户端线程从watchManager中回调watcher执行相应的功能。**

| 特性           | 说明                                                         |
| -------------- | ------------------------------------------------------------ |
| 客户端顺序回调 | **Watcher回调是顺序串行化执行的，只有回调后客户端才能看到最新的数据状态。一个Watcher回调逻辑不应该太多，以免影响别的watcher执行** |
| 轻量级         | WatchEvent是最小的通信单元，结构上只包含通知状态、事件类型和节点路径，并不会告诉数据节点变化前后的具体内容； |
| 时效性         | Watcher只有在当前session彻底失效时才会无效，若在session有效期内快速重连成功，则watcher依然存在，仍可接收到通知； |
| 一次性         | **Watcher是一次性的，一旦被触发就会移除，再次使用时需要重新注册** |

#### 2.2.1.1. 监听的作用域

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/谨记/zookeeper-image/watch-listen.png" alt="watch-listen" style="zoom:67%;" />

加入小红旗是一个watcher，当小红旗被创建并注册到node1节点(会有相应的API实现)后，就会监听node1+node_a+node_b或node_a+node_b。**这里两种情况是因为在创建watcher注册时会有多种途径。并且watcher不能监听到孙节点**。**<u>请注意，watcher设置后，一旦触发一次后就会失效，如果要想一直监听，需要在process回调函数里重新注册相同的 watcher。</u>**

#### 2.2.1.2. watch注册流程

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/谨记/zookeeper-image/watch-logic.png" alt="watch-logic" style="zoom: 67%;" />

1. 客户端发送的请求中只包含是否需要注册Watcher，不会将Watcher实体发送
2. Packet构造函数中的参数WatchRegistration是Watcher的封装体，用于服务响应成功后将Watcher保存到ZKWatchManager中

#### 2.2.1.3. Watcher通知流程

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/谨记/zookeeper-image/watch-inform-logic.png" alt="watch-inform-logic" style="zoom:67%;" />

### 2.2.2. watches 示例

具体实现就不说了，使用到了或者以后对这一块儿有迷惑的地方在深入的去说。

# 3. ZAB 选举与一致性

为了高可用和数据安全起见，zk集群一般都是由几个节点构成(由n/2+1，投票机制决定，肯定是奇数个节点)。多节点证明它们之间肯定会有数据的通信，同时，为了能够使zk集群对外是透明的，一个整体对外提供服务，那么客户端访问zk服务器的数据肯定是要数据同步，也即**数据一致性**。

zk集群是Leader/Follower模式来保证数据同步的。整个集群同一时刻只能有一个Leader，其他都是Follower或Observer。Leader是通过选举选出来的，这里涉及到ZAB协议(原子消息广播协议)。

## 3.1. 概念理解

> 概念理解copy自[品味Zookeeper之选举及数据一致性][https://www.jianshu.com/p/57fecbe70540], 写的比较形象。

为了更好理解下文，先说ZAB协议，它是选举过程和数据写入过程的基石。ZAB的核心是定义会改变zk服务器数据状态的事务请求的处理方式。

ZAB的理解：所有事务请求是由一个全局唯一的服务器来协调处理，这个的服务器就是Leader服务器，
 其它服务器都是Follower服务器或Observer服务器。Leader服务器负责将一个客户端的请求转换成那个一个**事务Proposalͧ(提议)**，将该Proposal分发给集群中所有的Follower服务器。然后Leader服务器需要等待所有Follower服务器的应答，当Leader服务器收到超过**半数**的Follower服务器进行了明确的应答后，Leader会再次向所有的Follower服务器分发Commit消息，要求其将前一个Proposal进行提交。

注意**事务提议**这个词，就类似 **人大代表大会提议** ，提议就代表会有应答，之间有通信。因此在zk的ZAB协议为了可靠性和可用性，会有**投票**，**应答**等操作来保证整个zk集群的正常运行。

总的来说就是，涉及到客户端对zk集群数据改变的行为都先由Leader统一响应，然后再把请求转换为事务转发给其他所有的Follower，Follower应答并处理事务，最后再反馈。如果客户端只是读请求，那么zk集群所有的节点都可以响应这个请求。

### 3.1.1. Zookeeper 服务器的角色

1. Leader: 事务请求的唯一调度和处理者，保证集群事务处理的顺序序性，集群内部各服务器的调度者。
2. Follower: 处理客户端非事务请求，转发事务请求给Leader服务器，参与事务请求Proposal的投票，参与Leader的选举投票。
3. Observer：处理客户端非事务请求，转发事务请求给Leader服务器，不参加任何形式的投票，包括选举和事务投票(超过半数确认)，Observer的存在是为了提高zk集群对外提供读性能的能力。

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/谨记/zookeeper-image/zookeeper-server-status.png" alt="zookeeper-server-status" style="zoom:67%;" />

### 3.1.2. Zookeeper 服务器的状态

- LOOKING：寻找Leader状态，当服务器处于这种状态时，表示当前没有Leader，需要进入选举流程。

- FOLLOWING：从机状态，表明当前服务器角色是Follower

- OBSERVING：观察者状态，表明当前服务器角色是Observer

- LEADING：领导者状态，表明当前服务器角色是Leader

ServerState 类维护服务器四种状态。

zk服务器的状态是随着机器的变化而变化的。比如Leader宕机了，服务器状态就变为LOOKING，通过选举后，某机器成为Leader，服务器状态就转换为LEADING。其他情况类似。

### 3.1.3. Zookeeper 通信

zokeeper通信有两个特点：

1. 使用的通信协议是**TCP协议**。在集群中到底是怎么连接的呢？还记得在配置zookeeper时要创建一个data目录并在其他创建一个myid文件并写入唯一的数字吗？zk服务器的TCP连接方向就是依赖这个myid文件里面的数字大小排列。数小的向数大的发起TCP连接。比如有3个节点，myid文件内容分别为1,2,3。zk集群的tcp连接顺序是1向2发起TCP连接，2向3发起TCP连接。如果有n个节点，那么tcp连接顺序也以此类推。这样整个zk集群就会连接起来。

2. zk服务器是多端口的。例如配置如下：

   ```yaml
     tickTime=2000
     dataDir=/home/liangjf/app/zookeeper/data
     dataLogDir=/home/liangjf/app/zookeeper/log
     clientPort=2181
     initLimit=5
     syncLimit=2
     server.1=192.168.1.1:2888:3888
     server.2=192.168.1.2:2888:3888
     server.3=192.168.1.3:2888:3888
   ```

   - 第1个端口是通信和数据同步端口，默认是2888
   - 第2个端口是投票端口，默认是3888

### 3.1.4. Zookeeper 集群

在 zookeeper 中，客户端会随机连接到 zookeeper 集群中的一个节点，如果是读请求，就直接从当前节点中读取数据，如果是写请求，那么请求会被转发给 leader 提交事务，然后 leader 会广播事务，只要有超过半数节点写入成功，那么写请求就会被提交。

<u>通常 zookeeper 是由 2n+1 台 server 组成，每个 server 都知道彼此的存在</u>。对于 2n+1 台 server，只要有 n+1 台（大多数）server 可用，整个系统保持可用。我们已经了解到，一个 zookeeper 集群如果要对外提供可用的服务，那么集群中必须要有过半的机器正常工作并且彼此之间能够正常通信，基于这个特性，如果向搭建一个能够允许 F 台机器down 掉的集群，那么就要部署 2*F+1 台服务器构成的zookeeper 集群。

　**之所以要满足这样一个等式，是因为一个节点要成为集群中的 leader，需要有超过及群众过半数的节点支持，这个涉及到 leader 选举算法。同时也涉及到事务请求的提交投票。**

　<u>所有事务请求必须由一个全局唯一的服务器来协调处理，这个服务器就是 Leader 服务器，其他的服务器就是follower</u>。leader 服务器把客户端的失去请求转化成一个事务 Proposal（提议），并把这个 Proposal 分发给集群中的所有 Follower 服务器。之后 Leader 服务器需要等待所有Follower 服务器的反馈，一旦超过半数的 Follower 服务器进行了正确的反馈，那么 Leader 就会再次向所有的Follower 服务器发送 Commit 消息，要求各个 follower 节点对前面的一个 Proposal 进行提交;、

## 3.2. ZAB 协议

> 本文大量依赖文章:[ZAB协议选主过程详解][https://zhuanlan.zhihu.com/p/27335748],可点击前往以获得更好的体验。

**ZAB 协议是为分布式协调服务ZooKeeper专门设计的一种支持崩溃恢复的一致性协议。基于该协议，ZooKeeper 实现了一种主从模式的系统架构来保持集群中各个副本之间的数据一致性。**

<u>ZAB协议运行过程中，所有的客户端更新都发往Leader，Leader写入本地日志后再复制到所有的Follower节点。</u>

**一旦Leader节点故障无法工作，ZAB协议能够自动从Follower节点中重新选择出一个合适的替代者，这个过程被称为选主，选主也是ZAB协议中最为重要和复杂的过程。**

### 3.2.1. ZAB 协议上的一些基础概念

在描述详细的选主过程之前，有必要交代一些概念，以便对接下来的大段文字不会有丈二和尚的感觉。

#### 3.2.1.1. **election epoch**

<u>这是分布式系统中极其重要的概念，由于分布式系统的特点，无法使用精准的时钟来维护事件的先后顺序，因此，Lampert提出的Logical Clock就成为了界定事件顺序的最主要方式。</u>

<u>分布式系统中以消息标记事件，所谓的Logical Clock就是为每个消息加上一个逻辑的时间戳。在ZAB协议中，每个消息都被赋予了一个zxid，zxid全局唯一。</u>**<u>zxid有两部分组成：高32位是epoch，低32位是epoch内的自增id，由0开始。每次选出新的Leader，epoch会递增，同时zxid的低32位清0。</u>**这其实像极了咱们古代封建王朝的君主更替，每一次的江山易主，君王更替。

#### 3.2.1.2. zxid

每个消息的编号，在分布式系统中，事件以消息来表示，事件发生的顺序以消息的编号来标记。在ZAB协议中，这就是zxid。<u>ZAB协议中，消息的编号只能由Leader节点来分配，这样的好处是我们就可以通过zxid来准确判断事件发生的先后，记住，是任意事件，这也是分布式系统中，由全局唯一的主节点来处理更新事件带来的极大好处。</u>

<u>分布式系统运行的过程中，Leader节点必然会发生改变，一致性协议必须能够正确处理这种情况，保证在Leader发生变化的时候，新的Leader期间，产生的zxid必须要大于老的Leader时生成的zxid。这就得通过上面说的epoch机制了，具体实现会在下面的选主过程中详细描述。</u>

这里，我们可以引入一个推论：**<u>在选主阶段，zookeeper对外不提供服务。因为zxid是由主节点来分配的。这一点很重要。</u>**

### 3.2.2. ZAB 协议的几个阶段

1. 发现(选举Leader过程)
2. 同步(选出Leader后，Follower和Observer需进行数据同步)
3. 广播(同步之后，集群对外工作响应请求，并进行消息广播，实现数据在集群节点的副本存储)

### 3.2.3. 触发选主的场景

一般在这些场景下会出现选主阶段：

1. **节点启动时**： 每个节点启动的时候状态都是LOOKING，处于观望状态，接下来就是要进行选主了。
2. **Leader节点异常**
3. **多数Follower节点异常**

#### 3.2.3.1. leader节点异常

Leader节点运行后会周期性地向Follower发送心跳信息（称之为ping），如果一个Follower未收到Leader节点的心跳信息，Follower节点的状态会从FOLLOWING转变为LOOKING。大致流程如下面的代码：

在Follower节点的主要处理流程中：

```java
void followLeader() throws InterruptedException {
try {
    ......
    while (this.isRunning()) {
        readPacket(qp);
        processPacket(qp);
    }
    // 如果上面的while循环内出现异常
    // 注意：长时间没有收到Leader的消息也是异常
} catch (Exception e) {
    // 出现异常就退出了while循环
    // 也就结束了Follower的处理流程
}
```

接下来进入节点运行的主循环：

```java
public void run() {
    while (running) {
        switch (getPeerState()) {
        case FOLLOWING:
            try {
                setFollower(makeFollower(logFactory));
                follower.followLeader();
            } catch (Exception e) {
                ......
            } finally {
                follower.shutdown();
                setFollower(null);
                // 状态更新为LOOKING
                updateServerState();
            }
            break;
            //......
    }
}
```

此后，该Follower就会再次进入选主阶段。

#### 3.2.3.2. 多数Follower节点异常

Leader节点也会检测Follower节点的状态，如果多数Follower节点不再响应Leader节点（可能是Leader节点与Follower节点之间产生了网络分区），那么Leader节点可能此时也不再是合法的Leader了，也必须要进行一次新的选主。

Leader节点启动时会接收Follower的主动连接请求，对于每一个Follower的新连接，Leader会创建一个LearnerHandler对象来处理与该Follower的消息通信。

LearnerHandler创建一个独立线程，在主循环内不停地接受Follower的消息并根据消息类型决定如何处理。除此以外，每收到Follower的消息时，便更新下一次消息的过期时间，这个过程在代码：

```java
public void run() {
    ......
    while (true) {
        qp = new QuorumPacket();
        ia.readRecord(qp, "packet");
        //......
        // 收到Follower的消息后
        // 设置下一个消息的过期时间
        tickOfNextAckDeadline = leader.self.tick.get() + leader.self.syncLimit;
        //......
    }
    //......
}
```

在Leader节点的主循环流程中，会判断多数派节点的消息状态，如下：

```java
void lead() throws IOException, InterruptedException {
    //......
    while (true) {
        //......
        // 判断每个每个Follower节点的状态
        // 是否与Leader保持同步
        for (LearnerHandler f : getLearners()) {
            if (f.synced()) {   
                syncedAckSet.addAck(f.getSid());
            }
        }
        //......
    }
    if (!tickSkip && !syncedAckSet.hasAllQuorums()) {
        // 如果失去了大多数Follower节点的认可，就跳出Leader主循环，进入选主流程
        break;
    }
    //......
}

// LearnerHandler::synced()逻辑
// 即判断当前是否已经过了期望得到的Follower的下一个消息的期限：tickOfNextAckDeadline
public boolean synced() {
    return isAlive() && leader.self.tick.get() <= tickOfNextAckDeadline;
}
```

## 3.3. ZAB 选主阶段

上面说了，选主阶段主要由以下场景可能构成:

1. **节点启动时**： 每个节点启动的时候状态都是LOOKING，处于观望状态，接下来就是要进行选主了。
2. **Leader节点异常**
3. **多数Follower节点异常**

下面会简述一下，这些场景下分别是怎么选举的。

### 3.3.1. 启动中的Leader选举

> 每个节点启动的时候状态都是 LOOKING，处于观望状态，接下来就开始进行选主流程进行 Leader 选举，至少需要两台机器，我们选取 3 台机器组成的服务器集群为例。在集群初始化阶段，当有一台服务器 Server1 启动时，它本身是无法进行和完成 Leader 选举，当第二台服务器 Server2 启动时，这个时候两台机器可以相互通信，每台机器都试图找到 Leader，于是进入 Leader 选举过程。

1. 每个 Server 发出一个投票。由于是初始情况，Server1和 Server2 都会将自己作为 Leader 服务器来进行投票，**每次投票会包含所推举的服务器的 myid 和 ZXID、epoch，**使用(myid, ZXID,epoch)来表示，此时 Server1的投票为(1, 0, 0)，Server2 的投票为(2, 0, 0)，然后各自将这个投票发给集群中其他机器。

   > **<font color=red size=3>实际上 zxid里是包含了epoch的，我们在上面也有说到。所以上面的0是包含了epoch的，这里只是一种形象化的说话，请大家注意，实际上的样子应该是(1, 0)。如果给大家造成了困扰，敬请原谅</font>**

2. 每个server也需要接受来自各个服务器的投票。<u>集群的每个服务器收到投票后，首先判断该投票的有效性，如检查是否是本轮投票（epoch）、是否来自LOOKING状态的服务器。</u>

3. 处理投票。针对每一个投票，服务器都需要将别人的投票和自己的投票进行判断，PK 规则如下：

   - **优先检查 ZXID**。ZXID 比较大的服务器优先作为Leader。

   - **如果 ZXID 相同，那么就比较 myid**， myid 较大的服务器作为 Leader 服务器。

     > 对于 Server1 而言，它的投票是(1, 0)，接收 Server2的投票为(2, 0)，首先会比较两者的 ZXID，均为 0，再比较 myid，此时 Server2 的 myid 最大，于是更新自己的投票为(2, 0)，然后重新投票，对于 Server2 而言，<u>它不需要更新自己的投票，只是再次向集群中所有机器发出上一次投票信息即可。</u>

4. 统计投票。每次投票后，服务器都会统计投票信息，判断是否已经有过半机器接受到相同的投票信息，对于 Server1、Server2 而言，都统计出集群中已经有两台机器接受了(2, 0)的投票信息，此时便认为已经选出了 Leader。

5. 改变服务器状态。一旦确定了 Leader，每个服务器就会更新自己的状态，如果是 Follower，那么就变更为FOLLOWING，如果是 Leader，就变更为 LEADING。

### 3.3.2. 运行中的leader选举

> 上面说的是 启动过程中，leader是如何选举的。如果你看上面的选主场景，可以看到，实际上是有三个，但是后面两个都可以被拢成一个状态：leader失效了。(多数follower异常，并不是follower的问题，而是 leader的问题，比如说：收不到消息了，或者其他follower进行了新的一轮选主，并且选出了新的leader)

当集群中的 leader 服务器出现宕机或者不可用的情况时，那么整个集群将无法对外提供服务，而是进入新一轮的Leader 选举，服务器运行期间的 Leader 选举和启动时期的 Leader 选举基本过程是一致的。

1. 变更状态。Leader 挂后，余下的非 Observer 服务器都会将自己的服务器状态变更为 LOOKING，然后开始进入 Leader 选举过程。
2. 每个 Server 会发出一个投票。在运行期间，每个服务器上的 ZXID 可能不同，此时假定 Server1 的 ZXID 为123，Server3的ZXID为122；在第一轮投票中，Server1和 Server3 都会投自己，产生投票(1, 123，1)，(3, 122，1)，然后各自将投票发送给集群中所有机器。接收来自各个服务器的投票。与启动时过程相同。
3. 处理投票。与启动时过程相同，此时，Server1 将会成为 Leader。
4. 统计投票。与启动时过程相同。
5. 改变服务器的状态。与启动时过程相同

### 3.3.3. Leader选举的代码实现

> 本小节的代码主要是跟着这篇文章走的：[深入分析Zookeeper的Leader 选举实现原理][https://www.cnblogs.com/wuzhenzhao/p/9983231.html]，因为文章的描述比较多，直接贴在这里了，为了更好的体验，可点击前往。

上面我们对选举的流程做了一些比较简单的理论描述，如果大家感兴趣的话，在这一小节里面，对代码的实现做了一些描述。源码是（zookeeper-3.4.12）,我们从 QuorumPeerMain 类的 main 方法开始：

```java
public static void main(String[] args) {
        QuorumPeerMain main = new QuorumPeerMain();
        try {//初始化主要逻辑
            main.initializeAndRun(args);
        }
　　　　　//...异常捕获
        LOG.info("Exiting normally");
        System.exit(0);
    }
```

进入 main.initializeAndRun(args) 可以看到：

```java
protected void initializeAndRun(String[] args)
        throws ConfigException, IOException
    {
        QuorumPeerConfig config = new QuorumPeerConfig();
        if (args.length == 1) {
            config.parse(args[0]);
        }
        // 启动后台定时任务异步执行清除任务，删除垃圾数据
        // Start and schedule the the purge task
        DatadirCleanupManager purgeMgr = new DatadirCleanupManager(config
                .getDataDir(), config.getDataLogDir(), config
                .getSnapRetainCount(), config.getPurgeInterval());
        purgeMgr.start();
        //判断是集群还是单机
        if (args.length == 1 && config.servers.size() > 0) {
            // 集群
            runFromConfig(config);
        } else {
            LOG.warn("Either no config or no quorum defined in config, running "
                    + " in standalone mode");
            // there is only server in the quorum -- run as standalone
            //单机
            ZooKeeperServerMain.main(args);
        }
    }
```

进入集群启动模式下的方法：

```java
public void runFromConfig(QuorumPeerConfig config) throws IOException {
      try {
          ManagedUtil.registerLog4jMBeans();
      } catch (JMException e) {
          LOG.warn("Unable to register log4j JMX control", e);
      }
  
      LOG.info("Starting quorum peer");
      try {// 初始化NIOServerCnxnFactory
          ServerCnxnFactory cnxnFactory = ServerCnxnFactory.createFactory();
          cnxnFactory.configure(config.getClientPortAddress(),
                                config.getMaxClientCnxns());
         // 逻辑主线程 进行投票，选举
          quorumPeer = getQuorumPeer();
          // 进入一系列的配置
          quorumPeer.setQuorumPeers(config.getServers());
          quorumPeer.setTxnFactory(new FileTxnSnapLog(
                  new File(config.getDataLogDir()),
                  new File(config.getDataDir())));
          quorumPeer.setElectionType(config.getElectionAlg());
          quorumPeer.setMyid(config.getServerId()); //配置 myid
          quorumPeer.setTickTime(config.getTickTime());
          quorumPeer.setInitLimit(config.getInitLimit());
          quorumPeer.setSyncLimit(config.getSyncLimit());
          quorumPeer.setQuorumListenOnAllIPs(config.getQuorumListenOnAllIPs());
          quorumPeer.setCnxnFactory(cnxnFactory);
          quorumPeer.setQuorumVerifier(config.getQuorumVerifier());
          // 为客户端提供写的server 即2181访问端口的访问功能
          quorumPeer.setClientPortAddress(config.getClientPortAddress());
          quorumPeer.setMinSessionTimeout(config.getMinSessionTimeout());
          quorumPeer.setMaxSessionTimeout(config.getMaxSessionTimeout());
          quorumPeer.setZKDatabase(new ZKDatabase(quorumPeer.getTxnFactory()));
          quorumPeer.setLearnerType(config.getPeerType());
          quorumPeer.setSyncEnabled(config.getSyncEnabled());

          // sets quorum sasl authentication configurations
          quorumPeer.setQuorumSaslEnabled(config.quorumEnableSasl);
          if(quorumPeer.isQuorumSaslAuthEnabled()){
              quorumPeer.setQuorumServerSaslRequired(config.quorumServerRequireSasl);
              quorumPeer.setQuorumLearnerSaslRequired(config.quorumLearnerRequireSasl);
              quorumPeer.setQuorumServicePrincipal(config.quorumServicePrincipal);
              quorumPeer.setQuorumServerLoginContext(config.quorumServerLoginContext);
              quorumPeer.setQuorumLearnerLoginContext(config.quorumLearnerLoginContext);
          }

          quorumPeer.setQuorumCnxnThreadsSize(config.quorumCnxnThreadsSize);
         // 初始化的工作
          quorumPeer.initialize();
          // 启动主线程，QuorumPeer 重写了 Thread.start 方法
          quorumPeer.start();
          quorumPeer.join();//使得线程之间的并行执行变为串行执行
      } catch (InterruptedException e) {
          // warn, but generally this is ok
          LOG.warn("Quorum Peer interrupted", e);
      }
    }
```

重点可关注在最后几行中的方法 `quorumPeer.start();`, 这个方法重写了 Thread.start()方法

```java
@Override
public synchronized void start() {
        //载入本地DB数据 主要还是epoch
        loadDataBase();
　　　　　//启动ZooKeeperThread线程
        cnxnFactory.start();    
        //启动leader选举线程    
        startLeaderElection();
        super.start();
}
```

loadDataBase()方法主要的目的是从本地文件中恢复并获取最新的zxid。

```java
private void loadDataBase() {
        File updating = new File(getTxnFactory().getSnapDir(),
                                 UPDATING_EPOCH_FILENAME);
        try {//载入本地数据
            zkDb.loadDataBase();
            // load the epochs 加载ZXID
            long lastProcessedZxid = zkDb.getDataTree().lastProcessedZxid;
            // 根据zxid的高32位是epoch号，低32位是事务id进行抽离epoch号
            long epochOfZxid = ZxidUtils.getEpochFromZxid(lastProcessedZxid);
            try {//从${data}/version-2/currentEpochs文件中加载当前的epoch号
                currentEpoch = readLongFromFile(CURRENT_EPOCH_FILENAME);
                //从 zxid中提取的epoch比文件里的epoch要大的话，并且没有正在修改epoch
                if (epochOfZxid > currentEpoch && updating.exists()) {
                    setCurrentEpoch(epochOfZxid);//设置位大的epoch
                    if (!updating.delete()) {
                        throw new IOException("Failed to delete " +
                                              updating.toString());
                    }
                }
            } 
　　　　　　　 // ........
            //如果如果还比他大 抛出异常
            if (epochOfZxid > currentEpoch) {
                throw new IOException("The current epoch, " + ZxidUtils.zxidToString(currentEpoch) + ", is older than the last zxid, " + lastProcessedZxid);
            }
            try {//再比较 acceptedEpoch
                acceptedEpoch = readLongFromFile(ACCEPTED_EPOCH_FILENAME);
            }
            // ........
            if (acceptedEpoch < currentEpoch) {
                throw new IOException("The accepted epoch, " + ZxidUtils.zxidToString(acceptedEpoch) + " is less than the current epoch, " + ZxidUtils.zxidToString(currentEpoch));
            }
　　　　　　　// .......
}
```

还是上面的方法，其最重要的选举算法：`startLeaderElection();` 也是目前zookeeper优化后使用的选举算法：

```java
synchronized public void startLeaderElection() {
        try { // 根据myid zxid epoch 3个选举参数创建Voto 对象，准备选举
            currentVote = new Vote(myid, getLastLoggedZxid(), getCurrentEpoch());
        } catch(IOException e) {
            RuntimeException re = new RuntimeException(e.getMessage());
            re.setStackTrace(e.getStackTrace());
            throw re;
        }
        for (QuorumServer p : getView().values()) {
            if (p.id == myid) {
                myQuorumAddr = p.addr;
                break;
            }
        }
        if (myQuorumAddr == null) {
            throw new RuntimeException("My id " + myid + " not in the peer list");
        }
        if (electionType == 0) {//如果是这个选举策略，代表 LeaderElection选举策略
            try {//创建 UDP Socket
                udpSocket = new DatagramSocket(myQuorumAddr.getPort());
                responder = new ResponderThread();
                responder.start();
            } catch (SocketException e) {
                throw new RuntimeException(e);
            }
        }//根据类型创建选举算法
        this.electionAlg = createElectionAlgorithm(electionType);
    }
```

进入选举算法的初始化 createElectionAlgorithm()：配置选举算法，选举算法有 3 种，可以通过在 zoo.cfg 里面进行配置，默认是 FastLeaderElection 选举:

```java
protected Election createElectionAlgorithm(int electionAlgorithm){
        Election le=null;
        // 选择选举策略
        //TODO: use a factory rather than a switch
        switch (electionAlgorithm) {
        case 0:
            le = new LeaderElection(this);
            break;
        case 1:
            le = new AuthFastLeaderElection(this);
            break;
        case 2:
            le = new AuthFastLeaderElection(this, true);
            break;
        case 3://Leader选举IO负责类
            qcm = createCnxnManager();
            QuorumCnxManager.Listener listener = qcm.listener;
            if(listener != null){
                // 启动已绑定端口的选举线程，等待其他服务器连接
                listener.start();
                //基于 TCP的选举算法
                le = new FastLeaderElection(this, qcm);
            } else {
                LOG.error("Null listener when initializing cnx manager");
            }
            break;
        default:
            assert false;
        }
        return le;
    }
```

继续看 FastLeaderElection 的初始化动作，主要初始化了业务层的发送队列和接收队列 ：

```java
public FastLeaderElection(QuorumPeer self, QuorumCnxManager manager){
        this.stop = false;
        this.manager = manager;
        starter(self, manager);
}

// ***********************************************

private void starter(QuorumPeer self, QuorumCnxManager manager) {
        this.self = self;
        proposedLeader = -1;
        proposedZxid = -1;
       // 投票 发送队列 阻塞
        sendqueue = new LinkedBlockingQueue<ToSend>();
        // 投票 接受队列 阻塞
        recvqueue = new LinkedBlockingQueue<Notification>();
        this.messenger = new Messenger(manager);
}
```

FastLeaderElection 初始化完成以后，调用 super.start()，最终运行 QuorumPeer 的run 方法：

```java
public void run() {
        setName("QuorumPeer" + "[myid=" + getId() + "]" +
                cnxnFactory.getLocalAddress());
        // 省略通过JMX初始化。来监控一些属性的代码
        try {
            // Main loop  主循环
            while (running) {
                switch (getPeerState()) {
                case LOOKING: //LOOKING 状态，则进入选举
                    if (Boolean.getBoolean("readonlymode.enabled")) {
　　　　　　　　　　　　　　 // 创建 ReadOnlyZooKeeperServer，但是不立即启动
                        final ReadOnlyZooKeeperServer roZk = new ReadOnlyZooKeeperServer(
                                logFactory, this,
                                new ZooKeeperServer.BasicDataTreeBuilder(),
                                this.zkDb);
    　　　　　　　　　　　　//通过 Thread 异步解耦
                        Thread roZkMgr = new Thread() {
                            public void run() {
                                try {
                                    // lower-bound grace period to 2 secs
                                    sleep(Math.max(2000, tickTime));
                                    if (ServerState.LOOKING.equals(getPeerState())) {
                                        roZk.startup();
                                    }
　　　　　　　　　　　　　　　　　　　// .......　　
                            }
                        };
                        try {//启动
                            roZkMgr.start();
                            setBCVote(null);
                           // 通过策略模式来决定当前用那个算法选举
                            setCurrentVote(makeLEStrategy().lookForLeader());
                        // .........
                    } else {
                        try {
                            setBCVote(null);
                            setCurrentVote(makeLEStrategy().lookForLeader());
                        //........
                    }
                    break;
//****************************************************************************
                case OBSERVING: // Observing 针对 Observer角色的节点
                    try {
                        LOG.info("OBSERVING");
                        setObserver(makeObserver(logFactory));
                        observer.observeLeader();
                    } catch (Exception e) {
                        LOG.warn("Unexpected exception",e );                        
                    } finally {
                        observer.shutdown();
                        setObserver(null);
                        setPeerState(ServerState.LOOKING);
                    }
                    break;
//*****************************************************************************
                case FOLLOWING:// 从节点状态
                    try {
                        LOG.info("FOLLOWING");
                        setFollower(makeFollower(logFactory));
                        follower.followLeader();
                    } catch (Exception e) {
                        LOG.warn("Unexpected exception",e);
                    } finally {
                        follower.shutdown();
                        setFollower(null);
                        setPeerState(ServerState.LOOKING);
                    }
                    break;
//**********************************************************************
                case LEADING: // leader 节点
                    LOG.info("LEADING");
                    try {
                        setLeader(makeLeader(logFactory));
                        leader.lead();
                        setLeader(null);
                    } catch (Exception e) {
                        LOG.warn("Unexpected exception",e);
                    } finally {
                        if (leader != null) {
                            leader.shutdown("Forcing shutdown");
                            setLeader(null);
                        }
                        setPeerState(ServerState.LOOKING);
                    }
                    break;
                }
            }
        }
　　 // ..........
}
```

由于是刚刚启动，是 LOOKING 状态。所以走第一条分支。调用 setCurrentVote(makeLEStrategy().lookForLeader());，最终根据上一步选择的策略应该运行 FastLeaderElection 中的选举算法，看一下 lookForLeader（）；

```java
//开始选举 Leader
public Vote lookForLeader() throws InterruptedException {
　　　　 // ...省略一些代码
        try {
            // 收到的投票
            HashMap<Long, Vote> recvset = new HashMap<Long, Vote>();
            // 存储选举结果 
            HashMap<Long, Vote> outofelection = new HashMap<Long, Vote>();

            int notTimeout = finalizeWait;
 　　　　　　 // AtomicLong logicalclock = new AtomicLong();
            synchronized(this){
                logicalclock.incrementAndGet(); // 增加逻辑时钟
                // 修改自己的zxid epoch 
                updateProposal(getInitId(), getInitLastLoggedZxid(), getPeerEpoch());
            }
            sendNotifications(); // 发送投票

            // Loop in which we exchange notifications until we find a leader
            while ((self.getPeerState() == ServerState.LOOKING) &&
                    (!stop)){ // 主循环  直到选举出leader
                /*
                 * Remove next notification from queue, times out after 2 times
                 * the termination time
                 */
                //从IO进程里面 获取投票结果，自己的投票也在里面
                Notification n = recvqueue.poll(notTimeout,TimeUnit.MILLISECONDS);

                // 如果没有获取到足够的通知久一直发送自己的选票，也就是持续进行选举
                if(n == null){
                    // 如果空了 就继续发送  直到选举出leader
                    if(manager.haveDelivered()){
                        sendNotifications();
                    } else {
                    // 消息没发出去，可能其他集群没启动 继续尝试连接
                        manager.connectAll();
                    }
                    /// 延长超时时间 
                    int tmpTimeOut = notTimeout*2;
                    notTimeout = (tmpTimeOut < maxNotificationInterval?
                            tmpTimeOut : maxNotificationInterval);
                    LOG.info("Notification time out: " + notTimeout);
                }
                // 收到投票消息 查看是否属于本集群内的消息
                else if(self.getVotingView().containsKey(n.sid)) {
                    switch (n.state) {// 判断收到消息的节点状态
                    case LOOKING:
                        // If notification > current, replace and send messages out
                        // 判断epoch 是否大于 logicalclock ，如是，则是新一轮选举
                        if (n.electionEpoch > logicalclock.get()) {
                            logicalclock.set(n.electionEpoch); // 更新本地logicalclock
                            recvset.clear(); // 清空接受队列
                            // 一次性比较 myid epoch zxid 看此消息是否胜出
                            if(totalOrderPredicate(n.leader, n.zxid, n.peerEpoch, //此方法看下面代码
                                    getInitId(), getInitLastLoggedZxid(), getPeerEpoch())) {
                                //投票结束修改票据为 leader票据
                                updateProposal(n.leader, n.zxid, n.peerEpoch);
                            } else {//否则票据不变
                                updateProposal(getInitId(),
                                        getInitLastLoggedZxid(),
                                        getPeerEpoch());
                            }
                            sendNotifications(); // 继续广播票据，让其他节点知道我现在的投票
                         //如果是epoch小于当前  忽略
                        } else if (n.electionEpoch < logicalclock.get()) {
                            break;
                        //如果 epoch 相同 跟上面一样的比较 更新票据 广播票据
                        } else if (totalOrderPredicate(n.leader, n.zxid, n.peerEpoch,
                                proposedLeader, proposedZxid, proposedEpoch)) {
                            updateProposal(n.leader, n.zxid, n.peerEpoch);
                            sendNotifications();
                        }

                       // 把最终票据放进接受队列 用来做最后判断
                        recvset.put(n.sid, new Vote(n.leader, n.zxid, n.electionEpoch, n.peerEpoch));
                       // 判断选举是否结束 默认算法是否超过半数同意 见下面代码
                        if (termPredicate(recvset,
                                new Vote(proposedLeader, proposedZxid,
                                        logicalclock.get(), proposedEpoch))) {

                            // 一直等待 notification 到达 直到超时就返回null
　　　　　　　　　　　　　　　　 // final static int finalizeWait = 200;
                            while((n = recvqueue.poll(finalizeWait,
                                    TimeUnit.MILLISECONDS)) != null){
                                if(totalOrderPredicate(n.leader, n.zxid, n.peerEpoch,
                                        proposedLeader, proposedZxid, proposedEpoch)){
                                    recvqueue.put(n);
                                    break;
                                }
                            }
                            // 确定 leader 
                            if (n == null) {
                                // 修改状态
                                self.setPeerState((proposedLeader == self.getId()) ?
                                        ServerState.LEADING: learningState());
                                //返回最终投票结果
                                Vote endVote = new Vote(proposedLeader,
                                                        proposedZxid,
                                                        logicalclock.get(),
                                                        proposedEpoch);
                                leaveInstance(endVote);
                                return endVote;
                            }
                        }
                        break;
                    // 如果收到的选票状态 不是LOOKING 比如刚刚加入已经选举好的集群 
                    // Observer 不参与选举
                    case OBSERVING:
                        LOG.debug("Notification from observer: " + n.sid);
                        break;
                   
                    case FOLLOWING:
                    case LEADING:
                        // 判断 epoch 是否相同
                        if(n.electionEpoch == logicalclock.get()){
                            recvset.put(n.sid, new Vote(n.leader,
                                                          n.zxid,
                                                          n.electionEpoch,
                                                          n.peerEpoch));
                            // 投票是否结束 结束的话确认leader 是否有效
                            // 如果结束 修改自己的投票并且返回
                            if(ooePredicate(recvset, outofelection, n)) {
                                self.setPeerState((n.leader == self.getId()) ?
                                        ServerState.LEADING: learningState());

                                Vote endVote = new Vote(n.leader, 
                                        n.zxid, 
                                        n.electionEpoch, 
                                        n.peerEpoch);
                                leaveInstance(endVote);
                                return endVote;
                            }
                        }

                        //在加入一个已建立的集群之前，确认大多数人都在跟随同一个Leader。
                        outofelection.put(n.sid, new Vote(n.version,
                                                            n.leader,
                                                            n.zxid,
                                                            n.electionEpoch,
                                                            n.peerEpoch,
                                                            n.state));
           
                        if(ooePredicate(outofelection, outofelection, n)) {
                            synchronized(this){
                                logicalclock.set(n.electionEpoch);
                                self.setPeerState((n.leader == self.getId()) ?
                                        ServerState.LEADING: learningState());
                            }
                            Vote endVote = new Vote(n.leader,
                                                    n.zxid,
                                                    n.electionEpoch,
                                                    n.peerEpoch);
                            leaveInstance(endVote);
                            return endVote;
                        }
                        break;
                    default:
                        LOG.warn("Notification state unrecognized: {} (n.state), {} (n.sid)",
                                n.state, n.sid);
                        break;
                    }
                } else {
                    LOG.warn("Ignoring notification from non-cluster member " + n.sid);
                }
            }
            return null;
        } 
　　　// .......
}

```

以上代码就是整个选举的核心。

1. 首先更新logicalclock并通过 updateProposal 修改自己的选票信息，并且通过 sendNotifications 进行发送选票。
2. 进入主循环进行本轮投票。
3. 从recvqueue队列中获取一个投票信息，如果没有获取到足够的选票通知一直发送自己的选票，也就是持续进行选举，否则进入步骤4。
4. 判断投票信息中的选举状态：
   1. LOOKING状态：
      - 如果对方的Epoch大于本地的logicalclock，则更新本地的logicalclock并清空本地投票信息统计箱recvset，并将自己作为候选和投票中的leader进行比较，选择大的作为新的投票，然后广播出去，否则进入下面步骤2。
      - 如果对方的Epoch小于本地的logicalclock，则忽略对方的投票，重新进入下一轮选举流程，否则进入下面步骤3。
      - 如果对方的Epoch等于本地的logicalclock，则比较当前本地被推选的leader和投票中的leader，选择大的作为新的投票，然后广播出去。
      - 把对方的投票信息保存到本地投票统计箱recvset中，判断当前被选举的leader是否在投票中占了大多数（大于一半的server数量），如果是则需再等待finalizeWait时间（从recvqueue继续poll投票消息）看是否有人修改了leader的候选，如果有则再将该投票信息再放回recvqueue中并重新开始下一轮循环，否则确定角色，结束选举。
   2. OBSERVING状态：不参与选举。
   3. FOLLOWING/LEADING：
      - 如果对方的Epoch等于本地的logicalclock，把对方的投票信息保存到本地投票统计箱recvset中，判断对方的投票信息是否在recvset中占大多数并且确认自己确实为leader，如果是则确定角色，结束选举，否则进入下面步骤2。
      - 将对方的投票信息放入本地统计不参与投票信息箱outofelection中，判断对方的投票信息是否在outofelection中占大多数并且确认自己确实为leader，如果是则更新logicalclock为当前epoch，并确定角色，结束选举，否则进入下一轮选举。

# 4. zookeeper的一些实现

## 4.1. 配置(注册)中心



## 4.2. 分布式锁



## 4.3. 分布式队列



## 4.4. 分布式ID生成



引用：

- [zookeeper官网][zookeepe-master]
- [品味Zookeeper之选举及数据一致性][https://www.jianshu.com/p/57fecbe70540]
- [一文了解Zookeeper的Watcher机制][https://www.jianshu.com/p/c68b6b241943]
- [ZAB协议选主过程详解][https://zhuanlan.zhihu.com/p/27335748]
- [[zookeeper]zookeeper系列三：zookeeper中watcher的使用及原理][https://blog.csdn.net/zkp_java/article/details/82711810]



[zookeepe-master]:https://zookeeper.apache.org/doc/current/zookeeperOver.html\

[zookeepe-overview]:https://zookeeper.apache.org/doc/current/zookeeperOver.html\

[zookeeper-znode ]:https://zookeeper.apache.org/doc/current/zookeeperProgrammers.html#sc_zkDataModel_znodes\
[zookeeper-watches]: https://zookeeper.apache.org/doc/r3.4.12/zookeeperProgrammers.html#ch_zkWatches\