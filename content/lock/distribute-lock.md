## 1 分布式锁概述

随着业务复杂度提升和流量增长，集群部署和微服务化已逐渐成为标配。分布式系统会面临共享资源、同步访问等问题，在不同的进程必须以互斥的方式操作共享资源时，分布式锁是非常有用的原语。Martin Kleppmann（英国剑桥大学的分布式系统研究员）认为一般使用分布式锁有两个场景：

1. 效率：使用分布式锁可以避免不同节点重复相同的工作，这些工作会浪费资源。比如用户付了钱之后有可能不同节点会发出多封短信。
2. 正确性：加分布式锁同样可以避免破坏正确性，比如多个节点机器对同一个订单操作不同的流程有可能会导致该笔订单最后状态出现错误，造成损失。

比如在生产中，我们会遇到：

场景一：出现缓存击穿后，一段时间内需要同样资源的请求大量到来，此时如果没有对需要加载的资源做互斥约束的话，会对DB产生较大压力。

场景二：交易场景下订单支付结果回调以及取消订单时维护订单状态机正确性的场景。

在实际使用中，发现大家存在因不确定何时使用分布式锁，使用方式错误等导致的线上问题。因此本文梳理了分布式锁的解决方案并进行对比，结合历史出现的coe分析生产中使用分布式锁的各类问题和处理建议。

在单进程下，或者说在同一JVM中，由于Java内存模型设计及处理器对指令重排序的优化，在并发场景下存在原子性、可见性、有序性的问题，进而带来多线程下的数据安全问题。针对该问题，Java为我们提供了如synchronized、Lock、AtomicInteger等同步原语。但在生产环境往往使用分布式系统，实际上是多进程场景下的数据安全问题，Java提供的关键字和工具类无法解决，分布式锁（Distributed Locks）是解决该问题的方案之一。

结合本地锁的特征，分布式锁首先要保证：

- 互斥：同一个锁在被持有的时间段内只能被一个线程持有
- 锁超时：保证持有锁的线程出现异常时（例如Client失效，宕机等），锁不会被永久占用

此外，在一些场景中我们还希望分布式锁实现：

- 阻塞/非阻塞：和ReentrantLock一样支持lock和trylock
- 可重入：像ReentrantLock一样的可重入锁

- 公平/非公平：是否需要按照请求加锁的顺序获得锁
- 性能：在分布式的高并发场景下还需要考虑性能

下面介绍几种常见的分布式锁解决方案。

## 2 分布式锁的解决方案

### 2.1 基于数据库

基于数据库的分布式锁解决方案有多种实现方式，这里以MySQL为例列举几种方案：

#### 基于数据库表

建立一张表包含需要互斥的资源（resource 字段），将该字段设置为唯一索引，如果创建记录成功则获取到锁，出现唯一键冲突提示则表明锁已经被其他线程占用，其表结构设计如下：

代码块

```
CREATE TABLE `distributed_lock` (
  `id` int NOT NULL AUTO_INCREMENT,
  `resource` int NOT NULL COMMENT '资源',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unq_idx_resource` (`resource`) 
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

需要获取锁时，向该表插入一条数据：

代码块

```
INSERT INTO distributed_lock(resource) VALUES (1);
```

如果该操成功，则代表本次请求成功获得锁。此时另一个线程请求该资源，由于对resource字段做了唯一键约束，会抛出Duplicate entry '1' for key 'distributed_lock.unq_idx_resource'。通过数据库表的方式实现分布式锁看起来非常简单，但还如果业务上还需要锁超时、阻塞、可重入等场景还需要加以改造。

实现锁超时，我们需要在表中增加超时时间字段来记录超时，可以采用类似Redis处理过期key的方式，通过定时任务+惰性删除，将表中“当前时间 - 锁创建时间 > 超时时间”的记录进行释放锁从而避免死锁。

有了对资源的互斥和超时失效的保证后，可以应对绝大多数需要分布式锁的场景。若要实现阻塞/非阻塞，需要手动实现lock和trylock，伪代码如下：

代码块

```
    // 阻塞获得锁
    public void lock() {
        while (true) {
            if (locks(res)) {
                return;
            }
            LockSupport.parkNanos(1000 * 1000 * 10);
        }
    }

    // 非阻塞获得锁
    public boolean tryLock(long timeout) {
        long endTimeout = System.currentTimeMillis() + timeout;
        while (true) {
            if (locks(res)) {
                return true;
            }
            endTimeout = endTimeout - timeout;
            if (endTimeout < 0) {
                return false;
            }
        }
    }
```

当需要实现可重入锁时，还需要记录持有锁的对象及加锁的次数，持有者字段需要能唯一区分出锁作用域的请求对象，比如可以用主机信息+线程信息来标识一个请求锁的对象：

代码块

```
  `holder` varchar(255) NOT NULL COMMENT '持有者',
  `count` int NOT NULL DEFAULT '0' COMMENT '持有锁的次数',
```

#### 基于排它锁

除了利用数据库表，还可以通过排它锁（Exclusive Locks）来实现分布式锁。排它锁（Exclusive Locks）是一种悲观锁，使用前首先要关闭自动提交模式（autocommit），通过在查询语句后增加FOR UPDATE，当某条记录被加上排它锁后，其它线程也就无法在该行上增加排它锁。假设有一线程A需要获得锁并执行相应的操作，那么它的具体步骤如下：

1. 获取锁：SELECT * FROM distributed_lock WHERE id = 1 FOR UPDATE;。
2. 执行业务逻辑。
3. 释放锁：COMMIT。

如果另一个线程B在线程A释放锁之前执行步骤1，那么它会被阻塞，直至线程A释放锁之后才能继续。

使用排它锁可以严格保证数据访问的安全。但是缺点也明显，首先是有一定局限性，for update只适用于InnoDB引擎，且需要在事务中才能生效。其次是性能问题，只有当查询条件为索引时InnoDB才使用行锁，否则会使用表锁（即使使用索引当MySQL认为全表扫描效率更高时也会使用表锁）。此外只有当本次请求事务COMMIT后才会释放锁，其他请求会阻塞等待，这就可能造成大量请求阻塞，连接池被打满的风险。

总结：通过数据库实现分布式锁没有引入其他依赖易于理解，但是要实现非阻塞可重入就比较复杂了。此外强依赖于数据库，需要考虑单点问题，并且从性能上数据库并不适合高并发的场景。整体来看基于数据库实现的分布式锁比较适用于那些在并发不高且强依赖数据库的业务场景。

### 2.2 基于KV存储

Redis（Remote DIctionary Server）是由Salvatore Sanfilippo（Redis作者）开发的key-value存储系统。是一个开源的使用ANSI C语言编写、遵守BSD协议、支持网络、可基于内存亦可持久化的日志型、Key-Value数据库，并提供多种语言的API。Redis除了作为缓存之外，还有其他很多常见的应用场景，比如分布式锁、消息队列、限流器、排行榜等。下面详细讲解利用Redis实现分布式锁的方案。

#### **setnx命令**

SETNX是”SET if Not eXists”的简写，只在键key不存在的情况下， 将键key的值设置为value。若键key已经存在， 则SETNX命令不做任何动作。key作为锁的唯一标识，当线程setnx返回1时，说明原本key不存在，该线程成功得到了锁；如果返回的结果为0，则说明key已经存在，线程获取锁失败。需要解锁时，通过del key删除键值对释放锁，以便其他线程可以通过SETNX命令来获取锁。此外还需要通过expire key timeout设置锁超时机制，以保证即使锁没有被显示释放，也可以在一定时间后被自动释放。

代码块

```
// 加锁 返回0：键已存在 返回1：键不存在
setnx key value
// 锁超时
expire key timeout
// 解锁
del key 
```

实现分布式锁的伪代码：

代码块

```
if(setnx(key, 1) == 1){
    expire(key, 10);
    try{
        // 业务逻辑
    } finally {
        del(key);
    }
}
```

这样使用分布式锁存在很多问题：

场景一：死锁问题场景二：误解锁场景三：锁超时setnx，expire是分步执行的，不具有原子性，如果在加锁命令执行完成后expire命令或者del命令因为异常没有执行，会导致锁没有设置超时时间从而造成死锁由于解锁时并没有区分上锁的对象，还可能会造成误解锁尽管能正确设置超时时间，但如果执行业务的时间大于超时时间，可能会出现分布式锁失效的问题进程A临界资源进程B加锁A持有锁系统
异常加锁
失败设置
超时解锁加锁
失败加锁
失败​进程A临界资源进程B加锁A持有锁设置
超时超时
解锁解锁加锁B持有锁执行
业务访问资源​进程A临界资源进程B加锁A持有锁设置
超时执行
业务B持有锁超时
解锁加锁执行
业务访问资源访问资源​

可以看出利用setnx命令可以实现简单的分布式锁，但存在死锁、误解锁、锁超时的问题。针对这些问题的解决方案有：

- 保证原子性：Redis 2.6版本通过内嵌支持Lua环境，可以构建一段lua脚本将需要原子操作的命令封装起来
- 误解锁：每次解锁前通过value判断解锁对象
- 过期时间不确定：为获取锁的线程增加守护线程，为将要过期但未释放的锁增加有效时间

由于Redis在2.6.12后对set命令增加了NX选项，因此setnx命令后续会逐渐被set取代。

#### **set命令**

代码块

```
set key value [EX seconds] [PX milliseconds] [NX|XX]
```

- EX seconds：设置键key的过期时间，单位为秒
- PX milliseconds：设置键key的过期时间，单位为毫秒
- NX：仅当key不存在时设置值
- XX：仅当key存在时设置值

set命令的NX选项等同于setnx命令，并且将可以设置过期时间，保证了setnx，expire两步操作的原子性。为了解决误解锁问题，在set key value时value应该为一个随机值，保证每个线程拥有一个属于自己的value，并且在解锁的时候判断解锁对象。

Squirrel（美团基于redis的KV存储系统） client中的API setnx基于set命令实现，所以在使用中可以直接调用API的setnx方法。提供的compareAndDelete为原子操作，节约了手写lua脚本的难度，例如在使用Squirrel提供的分布式锁可以套用如下模板：

代码块

```
RedisStoreClient redisClient;
StoreKey storeKey = new StoreKey("category", userId);
String uuid = UUID.randomUUID().toString();
if (redisClient.setnx(storeKey, uuid, 5)) {
    try {
        // 业务逻辑
    } catch (Exception e) {
        log.error("error");
    } finally {
        redisClient.compareAndDelete(storeKey, uuid);
    }
}
```

以Squirrel提供的compareAndDelete为例，其底层调用jedis的BinaryJedisCluster提供的compareAndDelete方法，该方法实际调用了redis提供的eval命令，直接执行一段lua脚本，以保证compare和delete操作的原子性

compareAndDelete方法使用了eval命令：

![img](https://km.sankuai.com/api/file/cdn/497282806/639415830?contentType=1&isNewContent=false&isNewContent=false)

compareAndDelete的lua脚本：

![img](https://km.sankuai.com/api/file/cdn/497282806/639415883?contentType=1&isNewContent=false&isNewContent=false)

解决了setnx的不足后，需要进一步考虑单点部署情况下仍可能出现宕机的情况。因此在生产环境下，redis通过主从部署来实现高可用，这时分布式锁就要考虑redis集群故障的情况，集群场景下最常见的问题是主从切换和脑裂。

场景一：主从切换

当主节点不可用时redis通过哨兵模式保障主从切换，客户端无感知。尽管通过该机制极大的保证了集群的可用性，但也并非完全没有问题。当客户端A加锁成功后，master节点加锁成功，此时master宕机且未同步到从节点，从节点升级为主节点后不存在锁数据，此时客户端B可以成功加锁。



客户端Aslavemasterslave客户端Bnew masterslaveold master请求锁获得锁请求锁获得锁master 故障
主从切换未同步





场景二：脑裂

master和slave与sentinel集群处于不同网络分区，当出现网络问题后sentinel无法感知到master的存在，并将slave升级为master，此时存在两个master节点，不同客户端可在不同master节点下分别获得锁。



客户端Aslavemasterslave网络故障sentinel客户端Bslavemastersentinel客户端Amaster网络A网络B





#### RedLock

为了解决上述问题，Redis作者Antirez提出基于多个Redis实例的分布式锁实现方案RedLock算法，在redis官网有详细描述：https://redis.io/topics/distlock。

> 在分布式的算法中我们假设有N个Reids masters。这些节点完全独立，不存在主从复制或者其他集群协调机制。我们确保将在N个实例上使用与在Redis单实例下相同方法获取和释放锁。现在我们假设有5个Redis master节点，同时我们需要在5台服务器上面运行这些Redis实例，这样保证他们不会同时都宕掉。
>
> 为了取到锁，客户端应该执行以下操作:
>
> - 获取当前时间，以毫秒为单位。
> - 依次尝试从5个实例，使用相同的key和具有唯一性的value（例如UUID）获取锁。当向Redis请求获取锁时，客户端应该设置一个网络连接和响应超时时间，这个超时时间应该小于锁的失效时间。例如你的锁自动失效时间为10秒，则超时时间应该在5-50毫秒之间。这样可以避免服务器端Redis已经挂掉的情况下，客户端还在死死地等待响应结果。如果服务器端没有在规定时间内响应，客户端应该尽快尝试去另外一个Redis实例请求获取锁。
> - 客户端使用当前时间减去开始获取锁时间（步骤1记录的时间）就得到获取锁使用的时间。当且仅当从大多数（N/2+1，这里是3个节点）的Redis节点都取到锁，并且使用的时间小于锁失效时间时，锁才算获取成功。
> - 如果取到了锁，key的真正有效时间等于有效时间减去获取锁所使用的时间（步骤3计算的结果）。
> - 如果因为某些原因，获取锁失败（没有在至少N/2+1个Redis实例取到锁或者取锁时间已经超过了有效时间），客户端应该在所有的Redis实例上进行解锁（即便某些Redis实例根本就没有加锁成功，防止某些节点获取到锁但是客户端没有得到响应而导致接下来的一段时间不能被重新获取锁）。

RedLock算法并不复杂，其核心思想是使用多个Redis冗余实例来避免单Redis实例的不可靠性。

Redisson是一个在Redis的基础上实现的Java驻内存数据网格（In-Memory Data Grid）。它不仅提供了一系列的分布式的Java常用对象，还提供了许多分布式服务。针对RedLock算法Redisson实现了简单易用的API，可以利用MultiLock去获取多个RLock对象，每个RLock对象来自于不同的redis实例：

代码块

```
RLock lock1 = redisson1.getLock("lock1");
RLock lock2 = redisson2.getLock("lock2");
RLock lock3 = redisson3.getLock("lock3");

RLock multiLock = anyRedisson.getMultiLock(lock1, lock2, lock3);

// traditional lock method
multiLock.lock();

// or acquire lock and automatically unlock it after 10 seconds
multiLock.lock(10, TimeUnit.SECONDS);

// or wait for lock aquisition up to 100 seconds 
// and automatically unlock it after 10 seconds
boolean res = multiLock.tryLock(100, 10, TimeUnit.SECONDS);
if (res) {
   try {
     ...
   } finally {
       multiLock.unlock();
   }
}
```

首先看一下加锁代码，RedissonRedLock定义了一个failedLocksLimit方法，按照RedLock定义，当从大多数（N/2+1）实例获得锁时则认为获得锁成功，这里定义了failedLocksLimit反向算出了获得锁成功时允许没有获得锁的实例数量：

![img](https://km.sankuai.com/api/file/cdn/497282806/639332050?contentType=1&isNewContent=false&isNewContent=false)

当需要获得锁时，需要遍历MultiLock里所有的实例：

![img](https://km.sankuai.com/api/file/cdn/497282806/639404259?contentType=1&isNewContent=false&isNewContent=false)

需要解锁时依次尝试从每个节点解锁：

![img](https://km.sankuai.com/api/file/cdn/497282806/639332152?contentType=1&isNewContent=false&isNewContent=false)

RedLock通过多个Redis实例部署，减少了因Redis集群发生故障导致分布式锁失效的可能。但使用RedLock能够完全解决分布式锁的安全性问题吗？答案是否定的，分布式系统专家Martin Kleppmann就此提出质疑，本文2.4会就分布式锁的安全问题讨论。

总结：基于Reids的分布式锁使用简单，性能较高，能够更好的支撑高并发。但引入了无关依赖，需要维护Redis集群，此外在某些极端场景下锁模型并不健壮。

### 2.3 基于一致性协议

Zookeeper是一个分布式协调服务，是Google Chubby的一个开源实现，为分布式应用提供一致性服务的软件。可以应用于命名服务、配置管理、集群管理、分布式锁/队列等。Zookeeper作为分布式锁使用主要利用了其znode和watcher的特性，下面主要介绍这两个相关概念：

**Znode**

Zookeeper的数据模型为树形结构，类似于Unix文件系统，全部存放于内存中，其中每个节点成为znode

![img](https://km.sankuai.com/api/file/cdn/497282806/639276944?contentType=1&isNewContent=false&isNewContent=false)

znode按照是否持久和是否有序可以分为以下四种类型的节点：

- 持久化节点（PERSISTENT）：Zookeeper默认的节点类型，该类型的节点创建后，除非客户端执行delete操作，否则该节点会永久存储于服务端。

- 持久化有序节点（PERSISTENT_SEQUENTIAL）：该类型的节点在持久化节点（PERSISTENT）的基础上，Zookeeper会为该类型的节点在节点名称的基础上增加一个单调递增的编号。

- 临时节点（EPHEMERAL）：该类型的节点创建完成之后，若客户端与服务端断开连接之前没有执行delete操作，Zookeeper会自动删除该类型的节点。

- 临时有序节点（EPHEMERAL_SEQUENTIAL）：该类型的节点在临时节点（EPHEMERAL）的基础上，Zookeeper会为该类型的节点在节点名称的基础上增加一个单调递增的编号。

**Watcher**

客户端可以在某个znode上设置一个watcher，来监听znode上的变化。如果该znode上有相应的变化，就会触发这个watcher，把相应的事件通知给设置watcher的客户端。znode的变化可以分为两个方面，一是znode本身的变化，当znode存储的数据发生变化时会通知客户端；二是znode子节点的变化，当子节点发生增加/删除会通知客户端。

#### Zookeeper分布式锁原理

Zookeeper作为分布式锁主要应用了其临时有序节点和Watcher的特性，下面通过一个实例来分析3个client如何获得分布式锁的流程：

1. client 1、client 2、client 3连接Zookeeper，并在/locks下创建临时有序节点
2. 当前节点被唤醒后，会判断自己是否是最小的节点
3. 如果是最小节点，则该节点获取锁
4. 如果不是最小节点，监听小于自己创建节点的最大节点



//locks/locks/node_0001/locks/node_0002/locks/node_0003client 1client 2client 31 创建节点//locks/locks/node_0001/locks/node_0002/locks/node_0003client 1client 2client 3获取节点下最小的节点//locks/locks/node_0001/locks/node_0002/locks/node_0003client 1client 2client 33 未获得锁的节点监听小于自己创建节点的最大节点//locks/locks/node_0001/locks/node_0002/locks/node_0003client 1client 2client 34 client 1释放锁，znode节点删除，通知client 2获得锁2 拥有最小节点，获得锁





基于zk的分布式锁流程如下：



开始client在/lock下创建临时有序节点获取/lock节点下的子节点中最小节点client创建节点是否是最小节点获得锁业务逻辑释放锁 
（删除znode）Y监听小于自己创建节点的最大节点监听节点是否被删除NYN





下面动画演示了10个客户端创建并获得分布式锁的过程，可以看出每次获得锁的都是序号最小的znode

<video src="https://km.sankuai.com/api/file/cdn/497282806/639404280?contentType=1&amp;isNewContent=false" preload="meta" volume="0.5" style="box-sizing: border-box; -webkit-tap-highlight-color: rgba(0, 0, 0, 0); font-family: __SYMBOL, -apple-system, &quot;Segoe UI&quot;, Roboto, &quot;Helvetica Neue&quot;, Helvetica, &quot;PingFang SC&quot;, &quot;Hiragino Sans GB&quot;, &quot;Microsoft YaHei&quot;, SimSun, sans-serif; font-variant-ligatures: none; font-variant-numeric: tabular-nums; display: block; height: 352px; width: 632px;"></video>



00:00/00:10







#### Zookeeper分布式锁使用

Apache Curator是Netflix公司开源的一套比较完善的ZooKeeper客户端框架，解决了很多Zookeeper客户端底层的细节开发工作，封装的一套API简化了ZooKeeper的操作。利用Curator使用分布式锁非常简单，可以套用如下模板：

代码块

```
public class CuratorDemo {

    // zk server地址
    private static final String CONNECT_ADDR = "ip:port";
    // 连接超时时间
    private static final int CONNECTION_TIMEOUT = 3 * 1000;
    // 会话超时时间
    private static final int SESSION_TIMEOUT = 30 * 1000;
    // 重试策略
    private static RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 10);

    public static void main(String[] args) {
        // 1.创建client
        CuratorFramework client = CuratorFrameworkFactory.builder()
                .connectString(CONNECT_ADDR)
                .connectionTimeoutMs(CONNECTION_TIMEOUT)
                .sessionTimeoutMs(SESSION_TIMEOUT)
                .retryPolicy(retryPolicy)
                .build();
        // 2.连接zk
        client.start();

        // 3.创建分布式锁
        InterProcessMutex lock = new InterProcessMutex(client, "/locks");
        try {
            // 获取锁
            if (lock.acquire(10 * 1000, TimeUnit.SECONDS)) {
                log.info("hold lock");
                Thread.sleep(5000L);
                log.info("release lock");
            }
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            try {
                // 释放锁
                lock.release();
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }
}
```

首先看一下创建分布式锁，其构造方法为InterProcessMutex，InterProcessMutex中的成员变量含义如下：

代码块

```
public class InterProcessMutex{
  // 锁对象
  private final LockInternals internals;
  // 基础路径
  private final String basePath;
  // 锁信息和线程的映射关系
  private final ConcurrentMap<Thread, LockData> threadData = Maps.newConcurrentMap();
  // 锁前缀
  private static final String LOCK_NAME = "lock-";
}
```

其中一个构造方法中maxLeases写死为1，表示只有一个线程能获得资源，保证了互斥性：

![img](https://km.sankuai.com/api/file/cdn/497282806/639332051?contentType=1&isNewContent=false&isNewContent=false)

创建完锁对象后通过调用acquire方法获得锁，当当前线程锁对象不为空，调用lockData.lockCount.incrementAndGet()，给LockData中的lockCount+1，说明这是一把可重入锁。如果当前线程没有获得锁，则调用internals.attemptLock获得锁并返回锁路径：

![img](https://km.sankuai.com/api/file/cdn/497282806/639404261?contentType=1&isNewContent=false&isNewContent=false)

![img](https://km.sankuai.com/api/file/cdn/497282806/639332054?contentType=1&isNewContent=false&isNewContent=false)

通过createsTheLock方法创建了临时有序节点：

![img](https://km.sankuai.com/api/file/cdn/497282806/639276947?contentType=1&isNewContent=false&isNewContent=false)

进入其内部可以看到临时有序节点的标识：

![img](https://km.sankuai.com/api/file/cdn/497282806/639404263?contentType=1&isNewContent=false&isNewContent=false)

haveTheLock是一个是否获取锁的标识，通过调用getsTheLock方法判断，sequenceNodeName可以认为是当前znode节点，children是按照znode序号从小到大排序好的list，获取当前znode节点的索引，因为在构造方法中maxLeases已经设置为1，也就是当 0 < 1认为获得锁，即children里的最小节点可以获得锁：

![img](https://km.sankuai.com/api/file/cdn/497282806/639415833?contentType=1&isNewContent=false&isNewContent=false)

最后是释放锁：

![img](https://km.sankuai.com/api/file/cdn/497282806/639332157?contentType=1&isNewContent=false&isNewContent=false)

![img](https://km.sankuai.com/api/file/cdn/497282806/639415835?contentType=1&isNewContent=false&isNewContent=false)

通过分析Curator实现的基于zk的分布式锁源码，可以总结出其流程为：



acquire获取锁当前线程是否已获得锁重入次数+1获取成功Y创建临时有序节点N是否创建成功获取前一个节点，添加watcher线程阻塞Y唤醒当前线程Y超过重试次数N未超过抛异常release释放锁重入次数继续持有锁> 0删除对应锁文件==0获取线程锁信息，重入次数-1是否是最小节点N删除concurrentMap
锁信息触发watcher





总结：基于ZK的分布式锁模型健壮、API简单易用，但每次加锁解锁开销相对较大，在高并发场景下可能会出现性能问题。

### 2.4 分布式锁的安全性

在Redis作者提出RedLock算法后，Martin Kleppmann质疑了RedLock的安全性。其实分布式系统的设计没有银弹，各种分布式锁的方案也是在CAP之间权衡，不仅对于RedLock，其他实现方案都可能有不安全的问题。首先是锁的自动释放问题。为了解决持有锁的进程不能正常释放锁导致的死锁问题，设置了自动解锁时间。但当Client 1还没使用完锁但是锁已经过期了，此时Client 1处于STW阶段无法感知到锁已被释放。这时Client 2获得了锁，结果Client 1、Client 2都对资源进行了使用：

![img](https://km.sankuai.com/api/file/cdn/497282806/639415836?contentType=1&isNewContent=false&isNewContent=false)

Martin Kleppmann自问自答的给出了解决方法，提出fencing token的概念。fencing token是一个单调递增的数字，当客户端成功获取锁的时候它随同锁一起返回给客户端。Client 1获得了锁并得到33的token，随后进入了STW。Client 2获得了锁，得到34的token并携带该token进行存储操作。此时客户端1恢复并携带33的token发送到存储服务，因为存储服务已经处理了34的的token所以会拒绝33的token。

![img](https://km.sankuai.com/api/file/cdn/497282806/639284877?contentType=1&isNewContent=false&isNewContent=false)

比如当使用ZK作为分布式锁方案时，可以利用zxid或cverison来作为Fencing token。zxid是ZK的事务id，ZK状态的每一次改变, 都对应着一个递增的Transaction id。zxid由64位数字组成，它高32位是epoch用来标识leader关系是否改变，每次一个leader被选出来都会产生一个新的epoch（可以理解为一个年代）。低32位是递增计数，这样每个client都会按照请求ZK的先后顺序得到全局递增的zxid。可以看出zxid满足单调递增的特性，因此客户端可以携带zxid作为Fencing token去请求资源，Storage根据记录的zxid来判断是否要接受这次资源请求。但为了维护对Fencing token的校验，需要在Storage上存储对token的记录，在生产环境中这样做增加了资源服务器的负担。Google Chubby提供的解决方案是在客户端请求锁时生成lock generation number（一个64bit的单调递增数字），并且提供CheckSequencer()的API，在需要请求资源时进行检查，也就是将校验Fencing token的任务由资源服务器交给锁服务，保证了client在持有锁进行资源访问的时候依然有效。

通过fencing token看起来能解决因服务暂停导致的锁失效问题，但为了解决问题我们走上了一条越来越重的道路。引入fencing token后，在分布式锁失效的情况下依然能够保持对资源的互斥访问，那么分布式锁就没有存在的意义了。

此外Google Chubby还提供了lock-delay机制，Chubby允许client为持有的锁指定一个lock-delay的时间值（默认1分钟），当Chubby发现客户端被动失去联系的时候，并不会立即释放锁，而是会在lock-delay指定的时间内阻止其它客户端获得这个锁。这是为了在把锁分配给新的客户端之前，让之前持有锁的客户端有充分的时间把请求队列排空(draining the queue)，尽量防止出现延迟到达的未处理请求。这里和TCP协议的time_wait状态有异曲同工之妙，都是通过增加一定延时来确保不会被其他请求占用。

另外Martin还提出时钟跳跃情形，因为锁的过期强依赖于时间，如果服务器发生了时钟跳跃会影响锁的过期时间，这对于那些显示设置了过期时间的实现方案会有影响（比如基于DB的实现方案）。一个解法是利用NTP（时间服务器）自动调整，把跳跃时间控制在可接收范围内。本文不对此进行展开论述，有兴趣的同学可以参考[Martin的质疑](http://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)和[Antirez的反驳](http://antirez.com/news/101)原文。

总结：正所谓否定之否定，关于分布式锁安全性的问题好比一攻一防，也许有人会提出不健壮的场景，但也能找出解决方式。可以看出为了进一步解决分布式锁的安全性问题提供的方案已经变得越来越重。现有的分布式锁方案已能够满足日常生产中的大部分场景，如果希望保证100%的一致性，与其进一步完善分布式锁方案倒不如考虑其他降级方案来保证业务的正确性。

## 3 实践指导

### 3.1 分布式锁的对比

可以看出无论使用哪种方案实现分布式锁，其核心都是通过一个状态值表示锁，对锁的占用和释放通过状态值来标识，下面通过表格对比了这几种实现方案：

分布式锁分类实现优点缺点基于数据库基于数据库表，设计一个含有唯一索引的表易于理解支持功能少，需要手动实现；强依赖数据库需要考虑单点问题；不适合高并发场景悲观锁，对表中已经存在的记录加排它锁，阻塞其他获得锁的请求能够严格保证数据访问安全MySQL行锁默认需要索引，不走索引会出现行锁升级为表锁的情况。可能造成连接过多，不适用于高并发的场景基于KV存储redis set命令使用方便，性能较高持有锁的时间区间太长会被误删，导致锁错误地进入释放状态。Redis集群设计初衷在于性能而不在于数据一致性。如果Redis丢失数据将导致导致锁错误地进入释放状态。Redlock方案一致性更强，可用性更高Redis 的设计定位决定了它的数据并不是强一致性的，在某些极端情况下，可能会出现问题；需要耗费更多硬件资源。基于一致性协议zookeeper临时有序节点ZK 天生设计定位就是分布式协调，强一致性。锁的模型健壮、简单易用、适合做分布式锁如果有较多的客户端频繁的申请加锁、释放锁，对于 ZK 集群的压力会比较大。

通过上述对比可以总结出三种实现方案的特点：

**复杂性（从高到低）zookeeper >  redis > 数据库**

zookeeper作为一致性服务的软件，内部通过一致性协议保证，实现最为复杂。数据库实现的分布式锁一般基于业务，易于理解实现。

**性能（从高到低）redis > zookeeper > 数据库**

redis基于内存操作，其设计特点支持高并发。zookeeper为了保证一致性会需要耗费一些性能。数据库则只有索引在内存中，数据存于磁盘，性能较差。

**可靠性（从高到低）zookeeper > redis > 数据库**

zookeeper是分布式服务框架，基于一致性协议可靠性较高。redis分布式锁需要较多额外手段去保证可靠性。数据库只能满足小部分业务场景。

针对不同的业务场景，集团内cerberus组件提供了两种Lock-Engine分别基于ZooKeeper和Squirrel，业务方依据自身场景选择合适的解决方案。其中Squirrel主要用于满足高性能的场景；ZooKeeper用于满足强一致、高可用的场景。相关资料可参考[Cerberus-分布式锁](https://km.sankuai.com/page/204298409)

### 3.2 coe分析

在生产环境中大家使用分布式锁出现各种case，总结了近一年比较典型的使用分布式锁遇到问题，防止大家重复踩坑。

问题分类coe问题分析心得经验分布式锁选型[ops故障导致扩容不可用](https://coe.mws.sankuai.com/detail/126138)问题原因是该系统利用setnx自实现分布式锁，在兆丰机房网络抖动，导致服务树tag模块的写操作在获取到锁成功后，在设置锁过期时间及后续操作执行失败（获取锁和设置锁过期时间分成两行代码），进而导致写锁被创建成功，但由于没有过期时间也没有进行释放锁操作导致锁无法释放，因此所有请求都卡在循环获取写锁步骤。![img](https://km.sankuai.com/api/file/cdn/497282806/639404265?contentType=1&isNewContent=false&isNewContent=false)使用redis作为分布式锁要保证创建锁和设置锁过期时间是原子操作，不建议再使用setnx命令未使用分布式锁[订单侧在房东拒单后发出两条拒单MQ消息，导致任务侧生成两条相同的任务工单](https://coe.mws.sankuai.com/detail/107154)mq重复且业务逻辑未保证原子性，出现分布式的并发问题对于需要保证原子性的操作，需要业务上加分布式锁保证数据的一致性[客户平台基础服务故障，引发住宿门票链路多系统超时](https://coe.mws.sankuai.com/detail/106965)客户基础服务getCustomers接口每次请求异常都会刷新全量缓存，部分超时被多次放大，最终SQL连接池资源耗尽影响整个服务分布式锁的一个使用场景就是避免不同节点的重复工作[丽人赠送单据极端并发情况下导致未同步到缓存](https://coe.mws.sankuai.com/detail/97515)对于互斥资源没有加锁导致的并发问题目前数据主库部署在北京机房，如果先到的消息被上海机房消费发起数据库查询，后到的消息被北京机房消费发起数据库查询，此时可能上海机房查询的数据还在网络传输中，北京机房已经完成了数据库查询并且完成了缓存更新，然后上海机房才收到数据库查询数据，然后完成缓存更新，这就会导致缓存中的新数据被老数据覆盖，从而导致未能更新成最新状态。![img](https://km.sankuai.com/api/file/cdn/497282806/639332160?contentType=1&isNewContent=false&isNewContent=false)如果是互斥资源，需要考虑使用分布式锁解决并发问题分布式锁使用错误[智能版外卖部分商家反馈无法接单](https://coe.mws.sankuai.com/detail/105467)当业务流量升高后，cpu飙高后，系统响应时间增大，tp99耗时过高；耗时过高，导致锁争用分布式锁概率上升，进而进一步拉长接口耗时时间，最终超时请求占满整个连接池被占满，最后拒绝服务。控制加锁粒度，减少资源竞争程度[ktv预订部分订单结算延迟](https://coe.mws.sankuai.com/detail/97207)异常情况导致分布式锁key重复，使得一批请求竞争资源明确锁的资源，选择锁对象要慎重[次卡方案费率自动变更引发商品费率丢失](https://coe.mws.sankuai.com/detail/91859)异常情况导致分布式锁key重复，导致该分布式锁无效明确锁的资源，选择锁对象要慎重[调佣规则部分未生效](https://coe.mws.sankuai.com/detail/95562)并发情况下，由于获取不到分布式锁，造成部分数据落库失败使用分布式锁的非阻塞场景，需要结合业务看是否需要重试

### **3.3 生产中加锁的原则**

**1 确认什么情况需要加锁**

在生产环境中很多case往往是忘了使用分布式锁，可以通过check以下几项确认逻辑中是否需要使用分布式锁：

1. 资源是否是互斥资源
2. 有没有分布式的并发场景（多进程/多线程）
3. 操作是否幂等
4. 是否需避免重复操作节约系统资源

**2 使用正确的分布式锁方案**

对于分布式锁的选型，需要结合实际业务场景。如果业务并发量大需要有更好的性能，建议选用基于Redis单节点分布式锁。如果更关注正确性，可以考虑选用基于一致性协议的ZK作为方案。个人认为基于Redlock的实现方案是个过重的实现（heavyweight）。对于有强一致性要求的业务，不能依赖分布式锁保证最后的线性一致，必须有降级方案保证一致性。建议大家最好利用成熟的分布式锁方案，比如Squirrel封装的setnx或者Cerberus，避免自己手动实现。一方面降低手动实现复杂性，另一方面也降低了使用逻辑错误的可能。

在生产中还需要结合实际场景考虑分布式锁功能，比如获得锁是否需要阻塞，非阻塞是否需要重试；是否需要锁超时机制，没有的话会不会造成死锁；是否需要可重入的功能；是否需要公平锁的场景。

在确认选型和方案后，还需要考虑性能问题。应当注意尽量减小锁的粒度以减少资源竞争，过大的锁范围会导致更大范围的请求串行化进而无法提高并发。此外对于某些场景，分布式锁并不是唯一解决方案，如果业务可以通过Lock-Free（比如利用乐观锁或者原子操作）解决问题，性能上可能要比使用分布式锁更高。

## 4 总结

本文介绍分布式锁的实现方案，并进行对比总结。结合coe分析了生产中大家容易出现的问题，给出实践指导。分布式锁是分布式系统理论中绕不过的一环，本文个人能力有限，希望抛砖引玉同大家交流更多分布式相关的技术和经验。

## 参考资料

[Cerberus-分布式锁](https://km.sankuai.com/page/204298409)

[04-分布式锁实现选型](https://km.sankuai.com/page/41055089)

https://redis.io/topics/distlock

http://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html

http://zhangtielei.com/posts/blog-redlock-reasoning.html

http://zhangtielei.com/posts/blog-redlock-reasoning-part2.html

https://zookeeper.apache.org/

https://curator.apache.org/

https://www.cnblogs.com/gaochundong/p/lock_free_programming.html

https://github.com/redisson/redisson

https://research.google/pubs/pub27897/

## 作者简介

王雨辰，美团点评研发工程师，2017年加入美团