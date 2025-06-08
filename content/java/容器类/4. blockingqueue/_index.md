---
title: Blocking Queue
type: docs
sidebar:
  open: true
  
---


# 1. 什么是BlockingQueue?

> 阻塞队列 = 阻塞 + 队列。

- 队列：一种**先进先出**的数据结构，支持尾部添加、首部移除或查看等基础操作。
- 阻塞：除了队列提供的基本操作之外，还提供了支持**阻塞式插入和移除**的方式。

下面这些对BlockingQueue的介绍基本翻译自JavaDoc，非常详细。

> 1. 阻塞队列的顶级接口是`java.util.concurrent.BlockingQueue`,它继承了Queue，Queue又继承自Collection接口。
> 2. BlockingQueue 对插入操作、移除操作、获取元素操作提供了四种不同的方法用于不同的场景中使用：1、抛出异常；2、返回特殊值（null 或 true/false，取决于具体的操作）；3、阻塞等待此操作，直到这个操作成功；4、阻塞等待此操作，直到成功或者超时指定时间，第二节会有详细介绍。
> 3. BlockingQueue不接受null的插入，否则将抛出空指针异常，因为poll失败了会返回null，如果允许插入null值，就无法判断poll是否成功了。
> 4. BlockingQueue可能是有界的，如果在插入的时候发现队列满了，将会阻塞，而无界队列则有`Integer.MAX_VALUE`大的容量，并不是真的无界。
> 5. BlockingQueue通常用来作为生产者-消费者的队列的，但是它也支持Collection接口提供的方法，比如使用remove(x)来删除一个元素，但是这类操作并不是很高效，因此尽量在少数情况下使用，如：当一条入队的消息需要被取消的时候。
> 6. BlockingQueue的实现都是线程安全的，所有队列的操作或使用内置锁或是其他形式的并发控制来保证原子。但是一些批量操作如：`addAll`,`containsAll`, `retainAll`和`removeAll`不一定是原子的。如 addAll(c) 有可能在添加了一些元素后中途抛出异常，此时 BlockingQueue 中已经添加了部分元素。
> 7. BlockingQueue不支持类似close或shutdown等关闭操作。

