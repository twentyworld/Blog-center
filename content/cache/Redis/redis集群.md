# Redis 集群数据

- [Redis 集群数据](#redis-集群数据)
  - [一、单机数据库的实现](#一单机数据库的实现)
    - [1. Redis数据库](#1-redis数据库)
      - [1.1 Redis服务器中的数据库](#11-redis服务器中的数据库)
      - [1.2.数据库的键空间](#12数据库的键空间)
      - [1.3 键的过期时间](#13-键的过期时间)
    - [1.4 **Redis**过期键删除策略](#14-redis过期键删除策略)
      - [1.4.1过期删除策略](#141过期删除策略)
        - [定时删除](#定时删除)
        - [惰性删除](#惰性删除)
        - [定期删除](#定期删除)
      - [1.4.2 Redis采用的过期策略](#142-redis采用的过期策略)
        - [惰性删除流程](#惰性删除流程)
        - [定期删除流程](#定期删除流程)
    - [2. RDB持久化](#2-rdb持久化)
      - [2.1 RDB文件的创建](#21-rdb文件的创建)
        - [2.1.1 save命令](#211-save命令)
        - [2.1.2bgsave命令](#212bgsave命令)
        - [2.1.3自动触发 RDB 持久化](#213自动触发-rdb-持久化)
    - [3.AOF持久化](#3aof持久化)
      - [3.1AOF的实现](#31aof的实现)
        - [3.1.1命令追加](#311命令追加)
        - [3.1.2 AOF 文件的写入与同步](#312-aof-文件的写入与同步)
      - [3.2AOF重写](#32aof重写)
        - [3.2.1AOF重写的实现原理](#321aof重写的实现原理)
        - [3.2.2AOF后台重写](#322aof后台重写)
    - [4.RDB和AOF优缺点](#4rdb和aof优缺点)
      - [4.1RDB优缺点](#41rdb优缺点)
      - [4.2.AOF优缺点](#42aof优缺点)
      - [4.3如何选择RDB和AOF](#43如何选择rdb和aof)
  - [多机数据库实现](#多机数据库实现)
    - [1. 复制](#1-复制)
      - [1.1 旧版复制功能的实现](#11-旧版复制功能的实现)
        - [1.1.1 同步](#111-同步)
        - [1.1.2 命令传播](#112-命令传播)
        - [1.1.3 旧版复制功能的缺陷](#113-旧版复制功能的缺陷)
      - [1.2 新版复制功能的实现](#12-新版复制功能的实现)
        - [1.2.1 部分重同步的实现](#121-部分重同步的实现)
          - [<1>复制偏移量](#1复制偏移量)
          - [<2>复制积压缓冲区](#2复制积压缓冲区)
          - [<3>服务器运行ID](#3服务器运行id)
    - [2. Sentinel(哨兵)](#2-sentinel哨兵)
      - [2.1 启动并初始化Sentinel](#21-启动并初始化sentinel)
        - [2.1.1 初始化服务器](#211-初始化服务器)
        - [2.1.2 使用Sentinel专用代码](#212-使用sentinel专用代码)
        - [2.1.3 初始化Sentinel状态](#213-初始化sentinel状态)
        - [2.1.4 初始化Sentinel状态的masters属性](#214-初始化sentinel状态的masters属性)
        - [2.1.5 创建连向主服务器的连接](#215-创建连向主服务器的连接)
      - [2.2 获取主服务器信息](#22-获取主服务器信息)
      - [2.3 获取从服务器信息](#23-获取从服务器信息)
      - [2.4 向主服务器和从服务器发送消息](#24-向主服务器和从服务器发送消息)
      - [2.5 接收来自主服务器和从服务器的频道信息](#25-接收来自主服务器和从服务器的频道信息)
        - [2.5.1 更新sentinels字典](#251-更新sentinels字典)
        - [2.5.2 创建连接其他Sentinel的命令连接](#252-创建连接其他sentinel的命令连接)
      - [2.6 检测主观下线状态](#26-检测主观下线状态)
      - [2.7 检测客观下线状态](#27-检测客观下线状态)
        - [2.7.1 发送SENTINEL is-master-down-by-addr命令](#271-发送sentinel-is-master-down-by-addr命令)
        - [2.7.2 接收 SENTINEL is-master-down-by-addr 命令](#272-接收-sentinel-is-master-down-by-addr-命令)
        - [2.7.3 接收 SENTINEL is-master-down-by-addr 命令的回复](#273-接收-sentinel-is-master-down-by-addr-命令的回复)
      - [2.8选举领头Sentinel](#28选举领头sentinel)
      - [2.9故障转移](#29故障转移)
        - [2.9.1 选出新的主服务器](#291-选出新的主服务器)
        - [2.9.2 修改从服务器的复制目标](#292-修改从服务器的复制目标)
        - [2.9.3 将旧的主服务器变为从服务器](#293-将旧的主服务器变为从服务器)

## 一、单机数据库的实现

### 1. Redis数据库

Redis数据设计如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/单机-image.png" alt="单机-image" style="zoom:50%;" />

#### 1.1 Redis服务器中的数据库

Redis服务器将所有数据库信息保存在redis.h/redisServer结构中，如下：

```c
struct redisServer {
  //一组数组，保存着服务器所有数据库
  redisDb *db;
  //服务器数据库数量
  int dbnum
}；
```

#### 1.2.数据库的键空间

Redis 是一个键值对（key-value pair）数据库服务器， 服务器中的每个数据库都由一个 redis.h/redisDb 结构表示， 其中， redisDb 结构的 dict 字典保存了数据库中的所有键值对， 我们将这个字典称为键空间（key space）。

键空间和用户所见的数据库是直接对应的：

- 键空间的键也就是数据库的键， 每个键都是一个字符串对象。
- 键空间的值也就是数据库的值， 每个值可以是字符串对象、列表对象、哈希表对象、集合对象和有序集合对象在内的任意一种 Redis 对象。

```c
typedef struct redisDb {

    // ...

    // 数据库键空间，保存着数据库中的所有键值对
    dict *dict;

    // ...

} redisDb;
```

#### 1.3 键的过期时间

通过EXPIRE <key> <ttl>可以设置键的生存时间，经过指定的秒数以后，服务器会自动删除超过生存时间的键。

redisDb中的expires字典保存数据库中所有键的过期时间，记为过期字典。

过期字典中的键是一个指针，指向键空间dict中的某个对象。

过期字典的值是一个long long类型的整数，保存过期字典键指向的数据库对象的过期时间。

```c
typedef struct redisDb {

    // ...

    // 过期字典，保存键的过期时间
    dict *expires;

    // ...

} redisDb;
```

### 1.4 **Redis**过期键删除策略

#### 1.4.1过期删除策略

##### 定时删除

含义：在设置key的过期时间的同时，为该key创建一个定时器，让定时器在key的过期时间来临时，对key进行删除

优点：保证内存被尽快释放

缺点：

- 若过期key很多，删除这些key会占用很多的CPU时间，在CPU时间紧张的情况下，CPU不能把所有的时间用来做要紧的事儿，还需要去花时间删除这些key
- 定时器的创建耗时，若为每一个设置过期时间的key创建一个定时器（将会有大量的定时器产生），性能影响严重

##### 惰性删除

含义：key过期的时候不删除，每次从数据库获取key的时候去检查是否过期，若过期，则删除，返回null。

优点：删除操作只发生在从数据库取出key的时候发生，而且只删除当前key，所以对CPU时间的占用是比较少的，而且此时的删除是已经到了非做不可的地步（如果此时还不删除的话，我们就会获取到了已经过期的key了）

缺点：若大量的key在超出超时时间后，很久一段时间内，都没有被获取过，那么可能发生内存泄露（无用的垃圾占用了大量的内存）

##### 定期删除

含义：每隔一段时间执行一次删除过期key操作

优点：

- 通过限制删除操作的时长和频率，来减少删除操作对CPU时间的占用
- 定期删除过期key

缺点

- 在内存友好方面，不如"定时删除"
- 在CPU时间友好方面，不如"惰性删除"

难点

- 合理设置删除操作的执行时长（每次删除执行多长时间）和执行频率（每隔多长时间做一次删除）（这个要根据服务器运行情况来定了）

#### 1.4.2 Redis采用的过期策略

**Redis采用的过期策略：**惰性删除+定期删除

##### 惰性删除流程

- 在进行get或set等操作时，先检查key是否过期，
- 若过期，删除key，然后执行相应操作；
- 若没过期，直接执行相应操作

##### 定期删除流程

简单而言，对每一个数据库随机删除小于等于指定个数个过期key

- 遍历每个数据库（就是redis.conf中配置的"database"数量，默认为16），检查当前库中的指定个数个key（默认是每个库检查20个key，注意相当于该循环执行20次，循环体时下边的描述）
- 如果当前库中没有一个key设置了过期时间，直接执行下一个库的遍历
- 随机获取一个设置了过期时间的key，检查该key是否过期，如果过期，删除key
- 判断定期删除操作是否已经达到指定时长，若已经达到，直接退出定期删除。

### 2. RDB持久化

RDB是一种快照存储持久化方式，具体就是将Redis某一时刻的内存数据保存到硬盘的文件当中，默认保存的文件名为dump.rdb，而在Redis服务器启动时，会重新加载dump.rdb文件的数据到内存当中恢复数据。

#### 2.1 RDB文件的创建

开启RDB持久化方式很简单，客户端可以通过向Redis服务器发送save或bgsave命令让服务器生成rdb文件，或者通过服务器配置文件指定触发RDB条件。

##### 2.1.1 save命令

save命令是一个同步操作。当客户端向服务器发送save命令请求进行持久化时，服务器会阻塞save命令之后的其他客户端的请求，直到数据同步完成。

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/单机-image-(2).png" alt="单机-image-(2)" style="zoom:50%;" />

##### 2.1.2bgsave命令

bgsave命令是后台异步执行快照操作，此时 Redis 仍然可以响应客户端请求。

具体操作是 Redis 进程执行 fork 操作创建子进程，RDB 持久化过程由子进程负责，完成后自动结束。Redis 只会在 fork 期间发生阻塞，但是一般时间都很短。图示，如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/单机-image-(3).png" alt="单机-image-(3)" style="zoom:50%;" />

##### 2.1.3自动触发 RDB 持久化

除了手动执行这两个命令外，还可以在配置文件中设置save选项，达到条件的时候就会自动的生成RDB。比如，save 900 1 表示在900秒内，如果发生了一次写操作，就触发bgsave命令生成RDB。

- save选项设置的内容，保存在redisService结构的saveparms属性中
- dirty计数器记录着从上次save/bgave 到现在发生了多少次写操作，每进行一次写操作，计数器就加1
- lastsave 是unix时间戳，记录上次save或bgsave的时间。 

```c
struct redisServer {
  //记录保存条件的数组
  struct saveparm *saveparms;
  //修改计数器
  long long dirty;
  //上次执行保存时间
  time_t lastsave;
}；

struct saveparm {
  //秒数
  time_t seconds;
  //服务器数据库数量
  int chranges
}；
```

RDB文件自动生成实现流程：

redis服务器会周期性的执行serverCron函数,默认的话是每100毫秒执行一次。 这个serverCron 函数先通过当前时间减去lastsave 获取时间间隔。

如果dirty 大于 saveparm.chranges 并且时间间隔大于saveparm.seconds ，那么就会触发bgsave 生成 RDB文件。

### 3.AOF持久化

RDB持久化是将进程数据写入文件，而AOF持久化(即Append Only File持久化)，则是将Redis执行的每次写命令记录到单独的日志文件中（有点像MySQL的binlog）；当Redis重启时再次执行AOF文件中的命令来恢复数据。

#### 3.1AOF的实现

AOF 持久化功能的实现可以分为命令追加（append）、文件写入、文件同步（sync）三个步骤。

Redis客户端和服务端之间使用一种名为RESP(REdis Serialization Protocol)的二进制安全文本协议进行通信，协议解析如下：

用SET命令来举例说明RESP协议的格式。

```c
 redis> SET mykey "Hello" "OK"
```

实际发送的请求数据：

```c
*3\r\n3\r\nSET\r\n5\r\nmykey\r\n$5\r\nHello\r\n
```

实际收到的响应数据：

```c
+OK\r\n
```

协议描述图，如下：

![8793587-3becf73b1945c422](https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/8793587-3becf73b1945c422.png)

##### 3.1.1命令追加

当 AOF 持久化功能处于打开状态时， 服务器在执行完一个写命令之后， 会以协议格式将被执行的写命令追加到服务器状态的 aof_buf 缓冲区的末尾：

```c
struct redisServer {

    // ...

    // AOF 缓冲区
    sds aof_buf;

    // ...
};

```

##### 3.1.2 AOF 文件的写入与同步

前置知识

> Redis提供了多种AOF缓存区的同步文件策略，策略涉及到操作系统的write函数和fsync函数，说明如下：
>
> 为了提高文件写入效率，在现代操作系统中，当用户调用write函数将数据写入文件时，操作系统通常会将数据暂存到一个内存缓冲区里，当缓冲区被填满或超过了指定时限后，才真正将缓冲区的数据写入到硬盘里。这样的操作虽然提高了效率，但也带来了安全问题：如果计算机停机，内存缓冲区中的数据会丢失；因此系统同时提供了fsync、fdatasync等同步函数，可以强制操作系统立刻将缓冲区中的数据写入到硬盘里，从而确保数据的安全性。

Redis 的服务器进程就是一个事件循环（loop）， 这个循环中的文件事件负责接收客户端的命令请求， 以及向客户端发送命令回复， 而时间事件则负责执行像 serverCron 函数这样需要定时运行的函数。

因为服务器在处理文件事件时可能会执行写命令， 使得一些内容被追加到 aof_buf 缓冲区里面， 所以在服务器每次结束一个事件之前， 它都会调用 flushAppendOnlyFile 函数， 考虑是否需要将 aof_buf 缓冲区中的内容写入和保存到 AOF 文件里

面， 这个过程可以用以下伪代码表示：

```c
def eventLoop():

    while True:

        # 处理文件事件，接收命令请求以及发送命令回复
        # 处理命令请求时可能会有新内容被追加到 aof_buf 缓冲区中
        processFileEvents()

        # 处理时间事件
        processTimeEvents()

        # 考虑是否要将 aof_buf 中的内容写入和保存到 AOF 文件里面
        flushAppendOnlyFile()

```

其中，flushAppendOnlyFile 函数的行为由服务器配置的 appendfsync 选项的值来决定， 各个不同值产生的行为如下表 所示。

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/单机-image-(4).png" alt="单机-image-(4)" style="zoom:50%;" />

####  3.2AOF重写

AOF持久化是通过保存写命令来记录数据库状态的，所以AOF文件中的内容会越来越多，文件的体积也会越来越大，如果不加以控制的话，体积过大的 AOF文件很可能对Redis服务器、甚至整个宿主计算机造成影响，并且AOF文件的体积越大，使用

AOF文件来进行数据还原所需的时间就越多。

为了解决AOF文件体积膨胀的问题，Redis提供了AOF文件重写（rewrite）功能，创建一个新的AOF文件来替代现有的AOF文件，新旧文件所保存的数据库状态相同，但新AOF文件不会包含任何冗余命令，所以体积会比旧的小得多。

##### 3.2.1AOF重写的实现原理

实现原理：从数据库中读取键现在的值，然后用一条命令去记录键值对，代替之前记录这个键值对的多条命令。

##### 3.2.2AOF后台重写

重写会进行大量的写入操作，会阻塞服务器线程，无法处理新的命令请求。为解决这个问题，Redis将AOF重写程序放到子进程里执行，这样，父进程就可以继续处理命令请求。

存在的问题：子进程在进行AOF重写期间，服务器进程还需要继续处理命令请求，而新的命令可能会对现有的数据库状态进行修改，从而产生数据库状态不一致。

解决方案如下：

1. 第一步：Redis服务器设置了一个AOF重写缓冲区，这个缓冲区在服务器创建子进程之后开始使用，当服务器执行完一个写命令之后，它会将这个写命令发送给AOF重写缓冲区

   图示，如下：

   <img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/单机-image-(5).png" alt="单机-image-(5)" style="zoom:50%;" />

2. 第二步：当子进程完成AOF重写工作之后，它会向父进程发送一个信号，父进程在接到该信号之后，会调用信号处理函数，执行以下工作：

- 将AOF重写缓冲区中的所有内容写入到新AOF文件中，这时新AOF文件与当前的数据库状态一致
- 对新的AOF文件进行改名，原子地覆盖现有的AOF文件，完成新旧两个AOF文件的替换

### 4.RDB和AOF优缺点

#### 4.1RDB优缺点

优点：

- RDB快照是一个压缩过的非常紧凑的文件，保存着某个时间点的数据集，适合做数据的备份，灾难恢复
- 可以最大化Redis的性能，在保存RDB文件，服务器进程只需fork一个子进程来完成RDB文件的创建，父进程不需要做IO操作
- 与AOF相比，恢复大数据集的时候会更快

缺点：

- RDB的数据安全性是不如AOF的，保存整个数据集的过程是比繁重的，根据配置可能要几分钟才快照一次，如果服务器宕机，那么就可能丢失几分钟的数据
- Redis数据集较大时，fork的子进程要完成快照会比较耗CPU、耗时

#### 4.2.AOF优缺点

优点：

- 数据更完整，安全性更高，秒级数据丢失（取决fsync策略，如果是everysec，最多丢失1秒的数据）
- AOF文件是一个只进行追加的日志文件，且写入操作是以Redis协议的格式保存的，内容是可读的，适合误删紧急恢复

缺点：

- 对于相同的数据集，AOF文件的体积要大于RDB文件，数据恢复也会比较慢

#### 4.3如何选择RDB和AOF

- 如果是数据不那么敏感，且可以从其他地方重新生成补回的，那么可以关闭持久化
- 如果是数据比较重要，不想再从其他地方获取，且可以承受数分钟的数据丢失，比如缓存等，那么可以只使用RDB
- 如果是用做内存数据库，要使用Redis的持久化，建议是RDB和AOF都开启，或者定期执行bgsave做快照备份，RDB方式更适合做数据的备份，AOF可以保证数据的不丢失

## 多机数据库实现

### 1. 复制

在Redis中，用户通过执行slaveof命令或者设置配置文件slaveof选项的方式，让一个服务器(从服务器)去复制(replicate)另一个服务器(主服务器)，这个复制过程就叫做主从复制。

#### 1.1 旧版复制功能的实现

Redis 的复制功能分为同步（sync）和命令传播（command propagate）两个操作：

- 同步操作用于将从服务器的数据库状态更新至主服务器当前所处的数据库状态。
- 而命令传播操作则用于在主服务器的数据库状态被修改， 导致主从服务器的数据库状态出现不一致时， 让主从服务器的数据库重新回到一致状态。

##### 1.1.1 同步

当客户端向从服务器发送 SLAVEOF 命令， 要求从服务器复制主服务器时， 从服务器首先需要执行同步操作。

从服务器对主服务器的同步操作需要通过向主服务器发送 SYNC 命令来完成， 以下是 SYNC 命令的执行步骤：

- 从服务器向主服务器发送 SYNC 命令。
- 收到 SYNC 命令的主服务器执行 BGSAVE 命令， 在后台生成一个 RDB 文件， 并使用一个缓冲区记录从现在开始执行的所有写命令。
- 当主服务器的 BGSAVE 命令执行完毕时， 主服务器会将 BGSAVE 命令生成的 RDB 文件发送给从服务器， 从服务器接收并载入这个 RDB 文件， 将自己的数据库状态更新至主服务器执行 BGSAVE 命令时的数据库状态。
- 主服务器将记录在缓冲区里面的所有写命令发送给从服务器， 从服务器执行这些写命令， 将自己的数据库状态更新至主服务器数据库当前所处的状态。

##### 1.1.2 命令传播

同步完成之后，主从服务器的数据库状态将保持一致，但这种状态并非不变的，每当主服务器执行客户端发送的写命令时，主服务器的数据库就可能被更改，导致主从服务器状态不再一致。

为了保持主从状态一致，服务器会将自己执行的写命令 ，也即是造成主从服务器不一致的那条写命令 ，发送给从服务器执行， 当从服务器执行了相同的写命令之后， 主从服务器将再次回到一致状态。

图示，如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image.png" alt="image" style="zoom:67%;" />

##### 1.1.3 旧版复制功能的缺陷

Redis中主从复制可以分为下面2种情况：

- **初次复制：**从服务器从来没复制过任何主服务器，或者从服务器当前复制的主服务器和上次复制的主服务器不同。
- **断线后重复制：**处于命令传播阶段的主从服务器因为网络原因而中断了复制，但从服务器通过自动重连重新连接了主服务器，并继续复制主服务器。

缺陷：**断线**重连后，需要重新复制**整个主服务器**，而不是从断线后的状态接着复制，效率低下。sync同步命令，是十分耗费资源的(主服务器重新生成RDB文件，占用其CPU、内存、磁盘等)。

#### 1.2 新版复制功能的实现

为了解决上面的问题，2.8版本后的Redis服务器开始使用psync命令代替sync命令来执行复制时的同步操作，该命令具有完整重同步(full resynchronization)和部分重同步(partial resynchronization)：

- **完整重同步：**用于处理初次复制情况，执行步骤基本和旧版sync命令**同步**的执行步骤一样。

- **部分重同步：**用于处理断线后重复制情况，当从服务器在断线后重新连接主服务器时，如果条件允许，主服务器可以将主从服务器连接断开期间执行的写命令发送给从服务器，从服务器只要接受并执行这些写命令，将数据库更新至主服务器当前所

  处的状态。

##### 1.2.1 部分重同步的实现

部分重同步功能主要由以下3个部分构成：

- 主服务器的复制偏移量(replication offset)和从服务器的复制偏移量
- 主服务器的复制积压缓冲区(replication backlog)
- 服务器的运行ID(run ID)

###### <1>复制偏移量

  执行复制的双方--主服务器和从服务器分别维护一个复制偏移量：

- 主服务器每次向从服务器传播N个字节的数据时，就将自己的复制偏移量的值加上N；
- 从服务器每次收到主服务器传来的N个字节的数据时，就将自己的复制偏移量加上N

  通过对比主从服务器的复制偏移量，程序就很容易地知道主从服务器是否处于一致状态：

- 如果主从服务器处于一致状态，那么主从服务器两者的偏移量总是相同的；
- 相反，如果主从服务器两者的偏移量并不相同，那么说明主从服务器并未处于一致状态。

###### <2>复制积压缓冲区

  复制积压缓冲区是由主服务器维护的一个固定长度(fixed-size)先进先出(FIFO)队列，默认大小为1MB。当主服务器进行命令传播时，它不仅会将写命令发送给所有从服务器，还会将写命令入队到复制积压缓冲区队列里面，如下图：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(1).png" alt="image-(1)" style="zoom:50%;" />

当从服务器重新连上主服务器时，从服务器会通过psync命令将自己的复制偏移量offset发送给主服务器，主服务器会根据这个复制偏移量来决定对从服务器执行何种同步操作：

- 如果offset偏移量之后的数据(即偏移量offset+1开始的数据)仍然存在于复制积压缓冲区里面，则主服务器将对从服务器执行部分重同步操作
- 相反，如果offset偏移量之后的数据已经不再复制积压缓冲区，那么主服务器将对从服务器执行完整重同步操作。

###### <3>服务器运行ID

实现部分重同步还需要服务器运行ID(run ID)：每个Redis服务器，不论主还是从服务器，都有自己的运行ID，其在服务器启动时自动生成，由40个随机的十六进制字符组成。

当从服务器对主服务器进行初次复制时，主服务器会将自己的运行ID传送给从服务器，从服务器则将这个ID保存。

当从服务器断线并重新连接上一个主服务器时，从服务器将向当前连接的主服务器发送之前保存的运行ID：

- 保存ID和当前主服务器运行ID相同，说明从服务器断线之前复制的就是这个主服务器，主服务器可以继续尝试执行部分重同步操作；
- 相反的，如果2个服务器ID不同，说明从服务器断线之前复制的不是这个主服务器，主服务器将对从服务器执行完整重同步操作。

详细执行流程如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(2).png" alt="image-(2)" style="zoom: 50%;" />

### 2. Sentinel(哨兵)

Sentinel(哨岗、哨兵)是Redis高可用性的解决方案：由一个或多个Sentinel实例组成的Sentinel系统可以监视任意多个主服务器，以及这个主服务器下的从服务器，并在被监视主服务器下线时，自动将下线主服务器下的某个从服务器升级为新的主服务

器，然后由新的主服务器代替已下线的主服务器继续处理命令请求。Sentinel系统如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(3).png" alt="image-(3)" style="zoom:50%;" />

#### 2.1 启动并初始化Sentinel

一个Sentinel实例启动时，它需要执行以下步骤：

- 初始化服务器
- 将普通Redis服务器使用的代码替换为Sentinel专用代码
- 初始化Sentinel 状态
- 根据给定的配置文件，初始化Sentinel的监视主服务器列表
- 创建连向主服务器的网络连接

##### 2.1.1 初始化服务器

Sentinel本质上是一个运行在特殊模式下的Redis服务器，Sentinel的启动第一步就是启动一个普通的Redis服务器。但是Sentinel和普通Redis服务器执行的工作不一样，所以Sentinel的初始化过程和普通Redis服务器并不完全相同。

Sentinel在初始化时，不需要载入RDB文件或者AOF文件。并且Sentinel向外提供的命令和普通Redis服务器也不是完全一样的，像SET这一类命令Sentinel是没有的。

##### 2.1.2 使用Sentinel专用代码

- 使用与普通Redis服务器不同的默认端口号
- 载入Sentinel需要使用的命令列表，Sentinle支持：PING、SENTINEL、INFO、SUBSCRIBE、UNSUBSCRIBE、PSUBSCRIBE和PUNSUBSCRIBE这七个命令

##### 2.1.3 初始化Sentinel状态

在应用了 Sentinel 的专用代码之后， 接下来， 服务器会初始化一个 sentinel.c/sentinelState 结构（后面简称“Sentinel 状态”）， 这个结构保存了服务器中所有和 Sentinel 功能有关的状态 （服务器的一般状态仍然由 redis.h/redisServer 结构保存）：

```c
struct sentinelState {

    // 当前纪元，用于实现故障转移
    uint64_t current_epoch;

    // 保存了所有被这个 sentinel 监视的主服务器
    // 字典的键是主服务器的名字
    // 字典的值则是一个指向 sentinelRedisInstance 结构的指针
    dict *masters;

    // 是否进入了 TILT 模式？
    int tilt;

    // 目前正在执行的脚本的数量
    int running_scripts;

    // 进入 TILT 模式的时间
    mstime_t tilt_start_time;

    // 最后一次执行时间处理器的时间
    mstime_t previous_time;

    // 一个 FIFO 队列，包含了所有需要执行的用户脚本
    list *scripts_queue;

} sentinel;
```

##### 2.1.4 初始化Sentinel状态的masters属性

Sentinel 状态中的 masters 字典记录了所有被 Sentinel 监视的主服务器的相关信息， 其中：

- 字典的键是被监视主服务器的名字。
- 而字典的值则是被监视主服务器对应的 sentinel.c/sentinelRedisInstance 结构。

```c
typedef struct sentinelRedisInstance {

    // 标识值，记录了实例的类型，以及该实例的当前状态
    int flags;

    // 实例的名字
    // 主服务器的名字由用户在配置文件中设置
    // 从服务器以及 Sentinel 的名字由 Sentinel 自动设置
    // 格式为 ip:port ，例如 "127.0.0.1:26379"
    char *name;

    // 实例的运行 ID
    char *runid;

    // 配置纪元，用于实现故障转移
    uint64_t config_epoch;

    // 实例的地址
    sentinelAddr *addr;

    // SENTINEL down-after-milliseconds 选项设定的值
    // 实例无响应多少毫秒之后才会被判断为主观下线（subjectively down）
    mstime_t down_after_period;
        // SENTINEL monitor <master-name> <IP> <port> <quorum> 选项中的 quorum 参数
    // 判断这个实例为客观下线（objectively down）所需的支持投票数量
    int quorum;

    // SENTINEL parallel-syncs <master-name> <number> 选项的值
    // 在执行故障转移操作时，可以同时对新的主服务器进行同步的从服务器数量
    int parallel_syncs;

    // SENTINEL failover-timeout <master-name> <ms> 选项的值
    // 刷新故障迁移状态的最大时限
    mstime_t failover_timeout;

    // ...

} sentinelRedisInstance;

typedef struct sentinelAddr {

    char *ip;

    int port;

} sentinelAddr;
```

##### 2.1.5 创建连向主服务器的连接

初始化Sentinel的最后一步是创建连向主服务器的网络连接。Sentinel将成为主服务器的客户端，它可以向主服务器发送命令，并从命令回复中获取相关信息。

Sentinel对每个被监视的主服务器会创建两个异步网络连接：

- 命令连接，这个连接专门用于向主服务器发送命令，并接收命令回复

- 订阅连接，这个连接专门用于订阅主服务器的sentinel:hello 频道

图示，如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(4).png" alt="image-(4)" style="zoom:50%;" />

#### 2.2 获取主服务器信息

Sentinel会以每10秒一次的频率，通过命令连接向被监视的主服务器发送INFO命令，并通过分析INFO的回复来获取主服务器当前的状态。

通过分析INFO的回复，Sentinel可以获取以下两个方面的信息：

- 主服务器本身的信息，包括run_id域记录的服务器运行ID，以及role域记录的服务器角色
- 主服务器下从服务器的信息，每个从服务器都由一个slave字符串开头的行记录，每行的ip记录了从服务器的IP地址，port记录了从服务器的端口号，根据ip和port的信息Sentinel无需用户来配置从服务器信息，即可自动发现从服务器。

根据run_id和role记录的信息，Sentinel对主服务器的实例进行更新。

从服务器的信息会更新至主服务器实例结构中的slaves字典中，这个字典记录了主服务器下从服务器的名单：

- 字典的键是由Sentinel自动设置的从服务器的名字，格式为：ip:port
- 字典的值则是对应从服务器的实例结构。

具体结构如下图所示：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(5).png" alt="image-(5)" style="zoom:80%;" />

#### 2.3 获取从服务器信息

当Sentinel发现主服务器有新的从服务器出现时，Sentinel除了会为这个新的从服务器创建相应的实体结构之外，Sentinel还会创建连接到从服务器的命令连接和订阅连接。
 在创建命令连接后，会以每10秒一次的频率发送INFO命令，并解析返回的信息。提取出如下信息对从服务器实例进行更新：

- 从服务器运行run_id
- 从服务器角色role
- 主服务器的ip地址和端口号
- 主服务器的连接状态：master_link_status
- 从服务器器优先级：slave_priority
- 从服务器的复制偏移量：slave_repl_offset
- 向主服务器和从服务器发送消息

#### 2.4 向主服务器和从服务器发送消息

默认情况下Sentinel会以两秒每次的频率，通过命令连接向所有被监视的主服务器和从服务器发送如下格式的命令：

```c
#s开头的参数是Sentinel的信息
#m开头的信息是主服务器的信息：如果Sentinel正在监视的为主服务器那么就是主服务器自身的信息；
#如果Sentinel监视的是从服务器那么就是从服务器复制的主服务器的信息
PUBLISH __sentinel__:hello "<s_ip>,<s_port>,<s_runid>,<s_epoch>,<m_name>,<m_ip>,<m_port>,<m_epoch>"
```

参数含义如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(6).png" alt="image-(6)" style="zoom:67%;" />

#### 2.5 接收来自主服务器和从服务器的频道信息

Sentinel当与一个主服务器或从服务器建立器订阅连接之后，Sentinel就会通过订阅连接向服务器发送以下命令来进行订阅消息：SUBSCRIBE __sentinel__:hello

Senetinel会一直对**sentinel**:hello继续订阅直到Sentinel与服务器断开连接为止。也就是说Sentinel既会通过命令连接向服务器发送**sentinel**:hello消息又会通过订阅连接从服务器接收消息。

对于监视同一个服务器的多个Sentinel来说，一个Sentinel发送的消息会被其他Sentinel接收到，这些信息会被用于更新其他Sentinel对于发送消息的Sentnel的认知，也会被用于更新其他Sentinel对于被监视服务的认知。

当一个Sentinel从**sentinel**:hello收到一条信息时，Sentinel会对这条信息进行分析，提取出信息中的<s_ip>,<s_port>,<s_runid>等上面提到的8个参数：

- 如果记录的<s_ip>与当前Sentinel一致，那么说明是自身发送的消息， 那么会丢弃这条消息
- 如果不一致，那么说明还有另外一个Sentinel在监视同一个服务器，接收消息的Sentinel会对器监视的主服务器实例结构中的sentinels字典进行更新

##### 2.5.1 更新sentinels字典

- sentinels字典中键为Sentinel的名字，格式：ip:port

- sentinels字典中值为对应的Sentinel的实例结构

图示，如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(7).png" alt="image-(7)" style="zoom:50%;" />

##### 2.5.2 创建连接其他Sentinel的命令连接

当Sentinel通过频道信息发现一个新的Sentinel 时，它不仅会为新Sentinel在sentinels字典中 创建相应的实例结构，还会创建一个连向新Sentinel 的命令连接，而新Sentinel也同样会创建连向这个 Sentinel的命令连接，最终监视同一主服务器的多个

Sentinel将形成相互连接的网络,如下图：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(8).png" alt="image-(8)" style="zoom:50%;" />

#### 2.6 检测主观下线状态

默认情况下Sentinel会向其监控的服务器（主服务器、从服务器、Sentinel）以每秒一次的频率发送PING命令，并通过PING命令的回复来判断具体实例的在线状态。实例回复可以分为以下两种情况：

- 有效回复：+PONG、-LOADING、-MASTERDOWN三种回复中的其中一种
- 无效回复：+PONG、-LOADING、-MASTERDOWN三种回复之外的回复，或者在指定时间内没有回复

Sentinel的配置文件中的down-after-milliseconds指定了Sentinel判断实例进入主观下线的时间长度：如果一个实例在down-after-milliseconds毫秒内连续向Sentinel返回无效回复，那么Sentinel会修改这个实例对应的实例结构，在flags属性中打开

SRI_S_DOWN标识，以此来表示实例进入主观下线状态。

具体如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(9).png" alt="image-(9)" style="zoom:67%;" />

#### 2.7 检测客观下线状态

当Sentinel将一个主服务器检测为主观下线后，为确认这个主服务器是否真的下线，它会向同时在监控这台主服务器的其他Sentinel进行询问，看他们是否也认为服务器进入下线状态（可以是主观下线或客观下线），如果Sentinel从其他Sentinel哪里接收到足够的数量的已下线判断后，Sentinel就会将主服务器判定为客观下线，对其执行故障转移
 检测客观下线主要分以下三步：

##### 2.7.1 发送SENTINEL is-master-down-by-addr命令

发送命令 `SENTINEL is-master-down-by-addr <ip> <port> <current_epoch> <runid>`，询问其他Sentinel是否同意主服务器已下线。

具体参数，如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(10).png" alt="image-(10)" style="zoom:50%;" />

##### 2.7.2 接收 SENTINEL is-master-down-by-addr 命令

当一个 Sentinel (目标 Sentinel)接收到另一个 Sentine丨（源 Sentinel)发来的 SENTINEL is-master-down-by命令时，目标Sentinel会分析并取出命令请求中包含的各个参数, 并根据其中的主服务器IP和端口号，检查主服务器是否已下线，然后向源Sentinel返回一 条包含三个参数的Multi Bulk回复作为SENTINEL is-master-down-by命令的回复：<down_state>；<leader_runid；<leader_epoch>

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(11).png" alt="image-(11)" style="zoom:50%;" />

##### 2.7.3 接收 SENTINEL is-master-down-by-addr 命令的回复

​      根据其他 Sentine发回的 SENTINEL is-master-down-by-addr 命令回复，Sentinel 将统计其他Sentinel同意主服务器已下线的数量，当这一数量超过Sentinel配置中设置的 quorum参数的值，那么该Sentinel就会认为主服务器已经进入客观下线状态。

Sentinel会将主服务器实例结构flags属性的SRI_0_D0WN标识打开，表示主服务器已经进入客观下线状态。

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(12).png" alt="image-(12)" style="zoom:67%;" />

#### 2.8选举领头Sentinel

当一个主服务器被判断为客观下线时，监视这个下线主服务器的各个Sentinel会进行协商，选举出一个领头Sentinel,并由领头Sentinel对下线主服务器执行故障转移操作。

**规则：**
  1.Sentinel设置局部领头Sentinel的规则是先到先得：最先向目标Sentinel发送设置要 求的源Sentinel将成为目标Sentinel的局部领头Sentinel,而之后接收到的所有设置 要求都会被目标Sentinel拒绝

  2.目标 Sentinel 在接收到 SENTINEL is-master-down-by-addr 命令之后，将向 源Sentinel返回一条命令回复，回复中的leader_runid参数和leader_epoch 参数分别记录了目标Seminel的局部领头Sentinel的运行ID和配置纪元

  3.源Sentinel在接收到目标Sentinel返回的命令回复之后，会检查回复中leader_ epoch参数的值和自己的配置纪元是否相同，如果相同的话，那么源Sentinel继续 取出回复中的leader_runid参数，如果leader_runid参数的值和源Sentinel 的运行ID —致，

那么表示目标Sentinel将源Sentinel设置成了局部领头Sentinel

  4.如果有某个Sentinel被半数以上的Sentinel设置成了局部领头Sentinel,那么这个 Sentinel成为领头Sentinel


   如果在给定时限内，没有一个Sentinel被选举为领头Sentinel，那么各个Sentinel将 在一段时间之后再次进行选举，直到选出领头Sentinel为止

#### 2.9故障转移

在选举产生出领头Sentinel之后，领头Sentinel将对已下线的主服务器执行故障转移操作

- 在已下线主服务器属下的所有从服务器里面，挑选出一个从服务器，并将其转换为 主服务器。
- 让已下线主服务器属下的所有从服务器改为复制新的主服务器。
- 将已下线主服务器设置为新的主服务器的从服务器，当这个旧的主服务器重新上线 时，它就会成为新的主服务器的从服务器。

##### 2.9.1 选出新的主服务器

删除列表中所有处于下线或者断线状态的从服务器，这可以保证列表中剩余的 从服务器都是正常在线的

删除列表中所有最近五秒内没有回复过领头Sentinel的INFO命令  这可以保证列表中剩余的从服务器都是最近成功进行过通信的

删除所有与已下线主服务器连接断开超过down-after-milliseconds * 10 毫秒的从服务器

之后，领头Sentinel将根据从服务器的优先级，对列表中剩余的从服务器进行排序， 并选出其中优先级最高的从服务器

如果有多个具有相同最高优先级的从服务器，那么领头Sentine丨将按照从服务器的 复制偏移量，对具有相同最高优先级的所有从服务器进行排序，并选出其中偏移量最大 的从服务器

如果有多个优先级最高、复制偏移量最大的从服务器，那么领头Sentinel将 按照运行丨D对这些从服务器进行排序，并选出其中运行ID最小的从服务器

图示如下：

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(13).png" alt="image-(13)" style="zoom:50%;" />

##### 2.9.2 修改从服务器的复制目标

当新的主服务器出现之后，领头Sentinel下一步要做的就是，让已下线主服务器属下 的所有从服务器去复制新的主服务器，这一动作可以通过向从服务器发SLAVEOF命令来实现。

<img src="https://raw.githubusercontent.com/twentyworld/knowledge-island/master/缓存体系/Redis/集群数据-image/image-(14).png" alt="image-(14)" style="zoom:50%;" />

##### 2.9.3 将旧的主服务器变为从服务器

因为旧的主服务器已经下线，所以这种设置是保存在serverl对应的实例结构里面的， 当serverl重新上线时，Sentinel就会向它发送命令，让它成为server2的从 服务器。
