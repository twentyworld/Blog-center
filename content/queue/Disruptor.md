# Disruptor

# 什么是 Disruptor

LMAX disruptor是一个高性能的线程间内存消息组件,也可以可以简单理解为生产者-消费者的消息发布订阅模式。它源于LMAX对并发性、性能和非阻塞算法的研究，如今已成为其交易所基础架构的核心部分。

Disruptor是一个高性能的异步处理队列框架，它最大特点是高性能，官方宣称在通用的硬件上每秒可以处理6百万订单。 

它允许开发者使用多线程技术去创建基于任务的工作流。Disruptor 能用来并行创建任务，同时保证多个处理过程的有序性。

那么,它是如何实现高性能的呢？它和JDK内置的队列有什么区别呢？

## JDK内置内存队列

Java内置了几种内存消息队列，如下所示：

队列同步方式是否有界数据结构ArrayBlockingQueue加锁ReentrantLock有界Object[]LinkedBlockingQueue加锁ReentrantLock无界(默认capacity=Integer.MAX_VALUE,认为是无界)LinkedListConcurrentLinkedQueueCAS无界LinkedListLinkedTransferQueueCAS无界LinkedList

CAS算法比通过加锁实现同步性能高很多，而从上表可以看出基于CAS实现的队列都是无界的，而有界队列是通过加锁实现同步的。在系统稳定性要求比较高的场景下，为了防止生产者速度过快，如果采用无界队列会最终导致内存溢出，因此,这种场景的要求下,只能选择有界队列。
而有界队列只有ArrayBlockingQueue或者带capacity的LinkedBlockingQueue，该队列是通过加锁实现的，在请求锁和释放锁时对性能开销很大，这时基于有界队列的高性能的Disruptor就应运而生。



JUC 队列总结有以下3点:

1. 锁的成本, 传统阻塞队列使用锁保证线程安全。而锁通过操作系统内核的上下文切换实现，会暂停线程去等待锁直到释放。执行这样的上下文切换，会丢失之前保存的数据和指令。由于消费者和生产者之间的速度差异，队列总是接近满或者空的状态。这种状态会导致高水平的写入争用。
2. 有界队列通常采用数组实现。但是采用数组实现又会引发另外一个问题false sharing(伪共享)。伪共享问题导致的性能低下。
3. 队列是垃圾的重要来源，队列中的元素和用于存储元素的节点对象需要进行频繁的重新分配。

##  Disruptor与ArrayBlockingQueue的比较

ArrayBlockingQueue的源码分析可以参考https://www.cnblogs.com/stevenczp/p/7158432.html，其核心思想如下：

1. Object[] items 作为底层容器
2. 内置一个ReentrantLock与两个Condition(notEmpty和notNull)
3. 任何对Queue的读写操作均用ReentrantLock加锁 -> 实现了线程安全的语义
4. 在队列空/满的情况下如果继续取出/插入元素，则利用Condition将工作线程阻塞，在符合条件的时候再将被阻塞的线程唤醒 -> 实现了阻塞队列的语义




这种实现在高并发的情况下存在一定的问题：

- 在任一时刻，只能有一个读/写线程在工作，其他的线程都被ReentrantLock所阻塞
- takeIndex与putIndex这两个被频繁访问的域在内存上距离很近，容易引起伪共享问题

Disruptor则很好的解决了这些问题，Disruptor 的目标就是快. java.util.concurrent.ArrayBlockingQueue 是一个非常优秀的有界队列实现。Disruptor 与之相比，性能更加的优秀。



# Disruptor使用场景

- 低延迟，高吞吐量，有界的队列
- 提高吞吐量，减少并发执行上下文之间的延迟并确保可预测延迟

Disruptor，主要用于对性能要求高、延迟极低的场景，它通过充分利用机器的性能来换取处理的高性能。如果有对性能要求高，对延迟要求低的需求，并且需要一个无锁的有界队列，来实现生产者/消费者模式，那么Disruptor将是你的不二选择。



# Disruptor可以做什么

当前业界优秀的开源组件使用Disruptor的包括Log4j2、Apache Storm等，它可以用来作为高性能的有界内存队列，基于生产者消费者模式，实现一个或多个生产者对应多个消费者。也可以认为是观察者模式或者发布订阅模式的一种实现。





ProducerConsumerConsumerConsumer





最重要的一点,作为一个队列,Disruptor允许开发者使用多线程技术去创建基于任务的**工作流**。Disruptor用来并行创建任务，同时保证多个处理过程的有序性，并且它是没有锁的。







Producer1Producer2Consumer1-1Consumer1-2Consumer3Consumer2-1Consumer2-2



在以往需要完成类似功能时,一般需要借助CountDownLatch或CyclicBarrier组合才能完成

# 

# **Disruptor 核心概念**


先从了解 Disruptor 的核心概念开始，来了解它是如何运作的。下面介绍的概念模型，既是领域对象，也是映射到代码实现上的核心对象。

## RingBuffer

环形缓冲区。Disruptor最主要的组件，仅仅负责存储和更新事件对象。在一些更高级的应用场景中，Ring Buffer 可以由用户的自定义实现来完全替代。



## Event

在 Disruptor 的语义中，生产者和消费者之间进行交换的数据被称为一个事件(Event)。它不是一个被 Disruptor 定义的特定接口，完全由使用者自定义。



## EventHandler

代表了Disruptor中的一个消费者的接口。由用户实现，处理事件的逻辑代码。

## WorkHandler

在work模式下使用。由用户实现并且代表了Disruptor中的多个消费者的接口。



## Sequence

Disruptor使用Sequence来表示一个特殊组件处理的序号。这个类维护了一个long类型的value，采用的unsafe进行的更新操作。

通过顺序递增的序号Sequence来编号管理通过其进行交换的数据（事件），对数据(事件)的处理过程总是沿着序号逐个递增处理。

每一个消费者（EventProcessor）都维持着一个Sequence,用于跟踪标识某个特定的事件处理者( Consumer )的处理进度。虽然一个 AtomicLong 也可以用于标识进度，但定义 Sequence 来负责该问题还有另一个目的，那就是防止不同的 Sequence 之间的CPU缓存伪共享(Flase Sharing)问题。这也是 Disruptor 实现高性能的关键点之一。



## Sequencer

Sequencer 是 Disruptor 的真正核心。此接口有两个实现类 SingleProducerSequencer、MultiProducerSequencer ，两种生产者均实现了并发算法，为了在生产者和消费者之间进行准确快速的数据传递。



## WaitStrategy

用来权衡当消费者无法从RingBuffer取到新的事件时的处理策略。 Disruptor 定义了多种不同的策略，针对不同的场景，提供了不一样的性能表现.

当消费者速度快于生产者，消费者取不到新的事件槽来消费新事件，则会根据该策略进行处理，默认会堵塞(BlockingWaitStrategy)

Tips:当生产者快于消费者速度很多(通常是超过某个消费者一圈),生产者无法将新的事件放进RingBuffer时的处理策略,是自旋等待LockSupport.*parkNanos*(1),是否依赖WaitStrategy等待策略是官方的下一步TODO.



![img](https://km.sankuai.com/api/file/cdn/196093131/211592712?contentType=1&isNewContent=false&isNewContent=false)


Disruptor 定义了 com.lmax.disruptor.WaitStrategy 接口用于抽象 Consumer 如何等待新事件，这是策略模式的应用。
Disruptor 提供了多个 WaitStrategy 的实现，每种策略都具有不同性能和优缺点，根据实际运行环境的 CPU 的硬件特点选择恰当的策略，并配合特定的 JVM 的配置参数，能够实现不同的性能提升。

- BlockingWaitStrategy 最低效的策略，但其对CPU的消耗最小并且在各种不同部署环境中能提供更加一致的性能表现；因此其是默认的WaitStrategy
- SleepingWaitStrategy 性能表现跟 BlockingWaitStrategy 差不多，对 CPU 的消耗也类似，但其对生产者线程的影响最小，适合用于异步日志类似的场景；使用LockSupport.parkNanos方法
- YieldingWaitStrategy 性能是最好的，适合用于低延迟的系统。在要求极高性能且事件处理线数小于 CPU 逻辑核心数的场景中，推荐使用此策略；例如，CPU开启超线程的特性。使用Thread.yield方法
- BusySpinWaitStrategy 自旋等待，类似自旋锁. 低延迟但同时对CPU资源的占用也多



**小结一下：**

WaitStrategy实际上是延时与CPU资源占用的权衡

如果追求最低的延时（ns级别），那就必须保证消费者一直是是热的，不能被系统调度走，因此可以使用BusySpinWaitStrategy

如果不需要那么低的延时，那么基于锁的BlockingWaitStrategy可能更加适合



## EventProcessor

主要事件循环，处理Disruptor中的Event，并且拥有消费者的Sequence。它有一个实现类是BatchEventProcessor，包含了event loop有效的实现，并且将回调到一个EventHandler接口的实现对象。

当调用 disruptor.handleEventsWith 设置消息的处理器时，我们提供的 Event Handler 会被包装为 BatchEventProcessor。在 Disruptor 启动的时候，就启动对应的线程去轮询消息并处理。每一个消息都要经过使用 EventProcessor 注册的所有消费者处理。

## WorkProcessor

确保每个sequence只被一个processor消费，在同一个WorkPool中的处理多个WorkProcessor不会消费同样的sequence,即消息只会被多个消费者中的某一个消费



## Producer

生产者，泛指调用 Disruptor 发布事件的用户代码，同样,Disruptor 没有定义接口。

生产者使用两阶段提交的方式来发布事件（第一阶段是先在环形队列ringbuffer中预占一个空位sequence，第二阶段是向这个空位中写入数据，竞争只发生在第一阶段），并使用CAS操作来解决冲突，而不是使用昂贵的Lock



## Sequence Barrier

由Sequencer生成，并且包含了已经发布的Sequence的引用，用于保持对RingBuffer的Sequence 和Consumer依赖的其它Consumer的 Sequence 的引用。 Sequence Barrier 还定义了决定 Consumer 是否还有可处理的事件的逻辑。

Disruptor利用SequenceBarrier来作为消费者的读屏障，利用消费的sequence作为生产者的写屏障。



# Disruptor如何实现高性能

Disruptor实现高性能主要体现在去掉了锁，采用CAS算法，同时内部通过环形队列Ring Buffer实现有界队列。



## 环形数据结构RingBuffer

数据结构采用ringbuffer。其实可以理解成一个数组entries。每一个slot存储一个事件对象。初始化时，就已经分配好内存，而且新发布的数据只会覆盖，所以更少的GC。

同时，采用数组而非链表。数组对处理器的缓存机制(空间局域性，预加载相邻近的缓存行)更加友好。



RingBuffer队列大小固定，且每个元素槽都以一个long整数sequence进行编号，RingBuffer中只有一个游标维护着一个指向下一个可用位置的序号，生产者每次向RingBuffer中写入一个元素时都需要向RingBuffer申请一个可写入的序列号，如果此时RingBuffer中有可用节点，RingBuffer就向生产者返回这个可用节点的序号，如果没有，那么就等待。同样消费者消费的元素序号也必须是生产者已经写入了的元素序号。



 

01234567



ringbuffer拥有一个序号，这个序号指向数组中下一个可用的元素。如下图右边的图片表示序号，这个序号指向数组的索引2的位置。

 

01234567index





随着不停地填充这个buffer（可能也会有相应的读取），这个序号会一直增长，直到绕过这个环。



01234567indexindexincrease





RingBuffer和常用的环形队列之间的区别是，不删除buffer中的数据，也就是说这些数据一直存放在buffer中，直到有新的数据覆盖他们。ringbuffer本身并不控制是否进行覆盖,决定是否覆盖是生产者-消费者行为模式的一部分.



采用ringbuffer这种数据结构的优点

1. 在可靠消息传递方面有很好的性能

2. 它是数组，所以要比链表快，而且有一个容易预测的访问模式。因为数组内元素的内存地址的连续性存储的,这是对CPU缓存友好的—也就是说，在硬件级别，数组中的元素是会被预加载的，因此在ringbuffer当中，cpu无需时不时去主存加载数组中的下一个元素。（因为只要一个元素被加载到缓存行，其他相邻的几个元素也会被加载进同一个缓存行）

3. 可以为数组预先分配内存，使得数组对象一直存在（除非程序终止）。这就意味着不需要花大量的时间用于垃圾回收。不像链表那样，需要为每一个添加到其上面的对象创造节点对象。当删除节点时，需要执行相应的内存清理操作。

   

## 内存预分配

RingBuffer使用数组Object[] entries作为存储元素，如下图所示，初始化RingBuffer时，会将所有的entries的每个元素指定为特定的Event，这时候event中的detail属性是null；后面生产者向RingBuffer中写入消息时，RingBuffer不是直接将entries[i]指向其他的event对象，而是先获取event对象，然后更改event对象的detail属性；消费者在消费时，也是从RingBuffer中读取出event，然后取出其detail属性。

可以看出，生产/消费过程中，RingBuffer的entities[i]元素并未发生任何变化，**未产生临时对象**，entities及其元素对象一直存活，直到RingBuffer消亡。故而可以最小化GC的频率，提升性能。

![img](https://km.sankuai.com/api/file/cdn/196093131/211753826?contentType=1&isNewContent=false)



## 缓存行填充

如果两个不同的变量位于同一个缓存行，则在并发情况下，会互相影响到彼此的缓存有效性，进而影响到性能，这叫做‘伪共享’fasle sharing。为了避开‘伪共享’，Disruptor3.0在Sequence.java中使用多个long变量填充，从而确保一个序号独占一个缓存行。Disruptor采用缓存行填充机制的形式解决了fasle sharing。



> 缓存行 (Cache Line) 便是 CPU Cache 中的最小单位，CPU Cache 由若干缓存行组成，一个缓存行的大小通常是 64 字节（这取决于 CPU），并且它有效地引用主内存中的一块地址。一个 Java 的 long 类型是 8 字节，因此在一个缓存行中可以存 8 个 long 类型的变量。

Cache line 有64个字节大小，共8个long 大小，左右都填充了7个long,7*8=56,加上value本身占8字节，所以可以确保序号变量独占长度为64byte缓存行。实际的序号value都不会和其他变量序号在一个缓存行中.

![img](https://km.sankuai.com/api/file/cdn/196093131/211449972?contentType=1&isNewContent=false)



Disruptor项目中有较多的精心设计的填充式代码.

![img](https://km.sankuai.com/api/file/cdn/196093131/211689097?contentType=1&isNewContent=false)

![img](https://km.sankuai.com/api/file/cdn/196093131/211718412?contentType=1&isNewContent=false)



## 元素位置定位

Disruptor中维护了一个long类型的sequence(序列)。每次根据位运算操作可以快速定位到实际index，sequence&(bufferSize -1)=index，比如bufferSize=8，9&(8-1)=1。

代码块

Java

```
private int calculateIndex(final long sequence){
  return ((int) sequence) & (bufferSize - 1);
}
```

disruptor在构造时要求队列的大小必须为2^n。通过位运算，加快定位的速度。序号sequence采取递增的形式。sequence是long类型，即使100万QPS的处理速度，也需要30万年才能用完,因此不用担心sequence溢出。



## 无锁设计

每个生产者或者消费者线程，会先申请可以操作的元素在数组中的位置，申请到之后，直接在该位置写入或者读取数据。整个过程通过原子变量CAS，保证操作的线程安全。

线程同时访问，由于他们都通过sequence访问ringBuffer，通过CAS取代了加锁，这也是并发编程的原则：把同步块最小化到一个变量上。

Disruptor使用了sun.misc.Unsafe原子操作实现cas,关于Unsafe 更多解析,查看https://tech.meituan.com/2019/02/14/talk-about-java-magic-class-unsafe.html



序号栅栏（SequenceBarrier）和序号（Sequence）搭配使用，协调和管理消费者与生产者的工作节奏，避免了锁的使用。各个消费者和生产者持有自己的序号，这些序号的变化必须满足如下基本条件：

- 消费者序号数值必须小于生产者序号数值；
- 消费者序号数值必须小于其前置（依赖关系）消费者的序号数值；
- 生产者序号数值不能大于消费者中最小的序号数值，以避免生产者速度过快，将还未来得及消费的消息覆盖。



## 批处理

当生产者节奏快于消费者，消费者可以通过‘批处理’快速追赶，消费者可以一次性从RingBuffer中获取多个已经准备好的entries，从而提高效率。

SequenceBarrier的waitFor()方法

代码块

Java

```
 public long waitFor(final long sequence)
        throws AlertException, InterruptedException, TimeoutException{
        checkAlert();
        long availableSequence = waitStrategy.waitFor(sequence, cursorSequence, dependentSequence, this);
        if (availableSequence < sequence){
            return availableSequence;
        }
        //返回最大的可访问sequence,消费者扫描从nextSequence到availableSequence全部的事件
        return sequencer.getHighestPublishedSequence(sequence, availableSequence);
    }
```





# Disruptor代码示例



基于Disruptor进行编程，先了解下大概流程的示意图，其中红色部分是需要我们编写和实现的类。

EventProducer是一个语义概念,可以不显式编程;

工作流的任务类型才需要实现WorkHandler,ThreadFactory则给了默认实现类DaemonThreadFactory,ExceptionHandler也给了默认实现类FatalExceptionHandler





Message原始消息`EventTranslator``将原始消息转换成事件event``Event事件``包含原始消息内容`EventProducer生产者EventFactory消息事件工厂类Ring bufferEventHandler事件处理类创建线程Executor事件处理线程池ThreadFactory事件处理线程工厂类ExceptionHandler异常处理类WorkHandler任务流处理类







引入dependency

代码块

XML

```
<dependency>
  <groupId>com.lmax</groupId>
  <artifactId>disruptor</artifactId>
  <version>3.4.2</version>
</dependency>
```



## 示例1-简单生产-消费

首先实现一个简单的用例，生产者负责将输入的字符串输出到队列，消费者简单打印出来.



ProducerringbufferConsumer



### MessageEvent-承载消息的事件

事件(Event)就是通过 Disruptor 进行交换的数据类型。

代码块

Java

```
@Data
public class MessageEvent {
    private String message;
}
```



### MessageEventFactory事件工厂

事件工厂(Event Factory)定义了如何实例化前面定义的事件(Event)，需要实现接口com.lmax.disruptor.EventFactory<T>。

Disruptor 通过 EventFactory 在 RingBuffer 中**预创建** Event 的实例。一个 Event 实例实际上被用作一个“数据槽”，发布者发布前，先从 RingBuffer 获得一个 Event 的实例，然后往 Event 实例中填充数据，之后再发布到 RingBuffer 中，之后由 Consumer 获得该 Event 实例并从中读取数据。

代码块

Java

```
public class MessageEventFactory implements EventFactory<MessageEvent> {
    @Override
    public MessageEvent newInstance() {
        return new MessageEvent();
    }
}
```



### MessageEventHandler事件处理器,消费者

定义事件处理的具体实现，通过实现接口 com.lmax.disruptor.EventHandler<T> 定义事件处理的具体实现。

此处执行速度要足够快。否则会影响RingBuffer后续没有空间加入新的数据。因此，不能做业务耗时操作。建议另外开启 java 线程池处理消息。

代码块

Java

```
public class MessageEventHandler implements EventHandler<MessageEvent> {
    @Override
    public void onEvent(MessageEvent event, long sequence, boolean endOfBatch) {
        System.out.println(sequence + "-" + event);
    }
}
```



### 生产者和Translator,消息转换类，负责将消息转换为事件

RingBuffer是消息存储结构，为环形存储结构，每个单元存储一条消息。当ringbuffer中数据填满后，环就会阻塞，等待消费者消费掉数据。当所有消费者消费掉环中一个数据，新的消息才可以加入环中。每个环插入数据后，都会分配下一个位置的编号，即sequence。

Disruptor的事件发布过程是一个**两阶段提交**的过程：
第一步：先从 RingBuffer 获取下一个可以写入的事件的序号sequece；
第二步：获取对应的事件对象event，将数据填充事件对象；
第三部：将事件提交到 RingBuffer;
事件只有在提交之后才会通知 EventProcessor 进行处理；



代码块

Java

```
public class MessageEventProducerWithTranslator {
    private final RingBuffer<MessageEvent> ringBuffer;

    public MessageEventProducerWithTranslator(RingBuffer<MessageEvent> ringBuffer) {
        this.ringBuffer = ringBuffer;
    }

    private static final EventTranslatorOneArg<MessageEvent, String> TRANSLATOR =
            new EventTranslatorOneArg<MessageEvent, String>() {
                @Override
                public void translateTo(MessageEvent event, long sequence, String message) {
                    event.setMessage(message);
                }
            };

    public void onData(String message) {
        ringBuffer.publishEvent(TRANSLATOR, message);
    }
}
```

translateTo方法将消息转换成java对象格式。也就是事件对象Event，后续消费者EventHandler处理器直接操作Event对象，获取消息各属性信息。
onData()方法，将生产者生产的消息放入RingBuffer中。



### 测试类

生产者-消费者启动类，其依靠构造Disruptor对象，调用start()方法完成启动线程。



代码块

Java

```
public class SimpleDisruptorTest {
    public static void main(String[] args) {
        int bufferSize = 1024;
        MessageEventFactory factory = new MessageEventFactory();
        Disruptor<MessageEvent> disruptor = new Disruptor<>(factory, bufferSize, DaemonThreadFactory.INSTANCE);
        disruptor.handleEventsWith(new MessageEventHandler());
        disruptor.start();

        RingBuffer<MessageEvent> ringBuffer = disruptor.getRingBuffer();
        MessageEventProducerWithTranslator producer = new MessageEventProducerWithTranslator(ringBuffer);
        for (long l = 0; true; l++) {
            producer.onData("Hello world");
        }
    }
}
```



执行结果如下,不断打印,速度非常快

![img](https://km.sankuai.com/api/file/cdn/196093131/211722013?contentType=1&isNewContent=false)



### java8的lamda写法,非常简洁

代码块

Java

```
public class SimpleDisruptorTest {
    /**
     * 事件-用来承载消息内容
     */
    @Data
    static class MessageEvent {
        private String message;
    }

    public static void main(String[] args) {
        // RingBuffer大小,必须是2的指数
        int bufferSize = 2 ^ 10;

        // 构造Disruptor
        // EventFactory为MessageEvent::new,引用构造方法
        // ThreadFactory使用官方实现
        Disruptor<MessageEvent> disruptor = new Disruptor<>(MessageEvent::new, bufferSize, DaemonThreadFactory.INSTANCE);

        // EventHandler事件处理类,仅仅打印
        disruptor.handleEventsWith((event, sequence, endOfBatch) -> {
                    System.out.println(sequence + "-" + event.getMessage());
                }
        );

        // 启动disruptor, 事件处理消费者线程
        disruptor.start();

        // 获取用于发布的ring buffer
        RingBuffer<MessageEvent> ringBuffer = disruptor.getRingBuffer();
        for (long l = 0; l < 100000L; l++) {
            //EventTranslator
            ringBuffer.publishEvent((event, sequence, buffer) -> event.setMessage("Hello world"));
        }
    }
}
```



## 示例2 -广播(菱形消费)

实现如图所示的简单的工作流程,两个消费组分开同时消费同一组消息,consumer3在1,2之后进行



ProducerringbufferConsumer1_1Consumer1_2Consumer3Consumer2_1Consumer2_2







代码块

Java

```
public class BroadcastDisruptorTestJava8 {
    /**
     * 事件
     * 用来承载消息内容
     */
    @Data
    static class MessageEvent {
        private String message;
    }

    private static final EventHandler consumer1_1 = (EventHandler<MessageEvent>) (event, sequence, endOfBatch) -> System.out.println("consumer1_1--" + sequence + "-" + event.getMessage());
    private static final EventHandler consumer1_2 = (EventHandler<MessageEvent>) (event, sequence, endOfBatch) -> System.out.println("consumer1_2--" + sequence + "-" + event.getMessage());
    
    private static final EventHandler consumer2_1 = (EventHandler<MessageEvent>) (event, sequence, endOfBatch) -> System.out.println("consumer2_1--" + sequence + "-" + event.getMessage());
    private static final EventHandler consumer2_2 = (EventHandler<MessageEvent>) (event, sequence, endOfBatch) -> System.out.println("consumer2_2--" + sequence + "-" + event.getMessage());
    
    private static final EventHandler consumer3 = (EventHandler<MessageEvent>) (event, sequence, endOfBatch) -> System.out.println("consumer3--" + sequence + "-" + event.getMessage());


    public static void main(String[] args) {
        // RingBuffer大小,必须是2的指数
        int bufferSize = 2 ^ 10;

        // 构造Disruptor
        // EventFactory为MessageEvent::new,引用构造方法
        // ThreadFactory使用官方实现
        Disruptor<MessageEvent> disruptor = new Disruptor<>(MessageEvent::new, bufferSize, DaemonThreadFactory.INSTANCE);

        disruptor.handleEventsWith(consumer1_1, consumer2_1);
        disruptor.after(consumer2_1).then(consumer2_2);
        disruptor.after(consumer1_1).then(consumer1_2);
        disruptor.after(consumer1_2, consumer2_2).then(consumer3);

        // 启动disruptor, 事件处理消费者线程
        disruptor.start();

        // 获取用于发布的ring buffer
        RingBuffer<MessageEvent> ringBuffer = disruptor.getRingBuffer();
        for (long l = 0; l < 100L; l++) {
            //EventTranslator
            ringBuffer.publishEvent((event, sequence, buffer) -> event.setMessage("Hello world"));
        }
    }
}
```



运行结果如图,可以看出consumer1_2总是consumer1_1之后,而3是在1,2之后,而consumer1和consumer1,2是在并行重复消费消息

![img](https://km.sankuai.com/api/file/cdn/196093131/211752664?contentType=1&isNewContent=false&isNewContent=false)

## 示例3 -工作组

类似kafka中同一个消费组概念,同一消费组内不重复消费,事件处理逻辑需实现com.lmax.disruptor.WorkHandler

com.lmax.disruptor.dsl.Disruptor#handleEventsWithWorkerPool(final WorkHandler<T>... workHandlers)

//todo





参考文档

缓存行,更多参考 https://www.cnkirito.moe/cache-line/      http://ifeve.com/falsesharing/

disruptor官方介绍 https://github.com/LMAX-Exchange/disruptor/wiki/Introduction

High performance alternative to bounded queues for exchanging data between concurrent threads http://lmax-exchange.github.io/disruptor/files/Disruptor-1.0.pdf

Disruptor Getting-Started https://github.com/LMAX-Exchange/disruptor/wiki/Getting-Started

剖析Disruptor:为什么会这么快 http://ifeve.com/disruptor/