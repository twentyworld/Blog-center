---
title: 7. redo log
type: docs
---

# Redo log

redo log中文一般称之为重做日志，提供了前滚操作。**<u>其核心目的是为了保证事务的持久性。</u>**

> undo log是回滚日志，提供回滚操作。

### 基本概念

redo log包括两部分：

- **一是内存中的日志缓冲(redo log buffer)，该部分日志是易失性的；**
- **二是磁盘上的重做日志文件(redo log file)，该部分日志是持久的。**

<u>这样做是为了效率考虑，因为内存的读写效率要比磁盘读写效率高太多。</u>

在概念上，innodb通过`force log at commit`机制实现事务的持久性，即在事务提交的时候，必须先将该事务的所有事务日志写入到磁盘上的redo log file中进行持久化。

和大多数关系型数据库一样，InnoDB记录了对数据文件的物理更改，并保证总是日志先行，也就是所谓的WAL，即在持久化数据文件前，保证之前的redo日志已经写到磁盘。

### 文件存储

<u>InnoDB的redo log可以通过参数`innodb_log_files_in_group`配置成多个文件，另外一个参数`innodb_log_file_size`表示每个文件的大小。因此总的redo log大小为`innodb_log_files_in_group * innodb_log_file_size`。</u>

Redo log文件以`ib_logfile[number]`命名，日志目录可以通过参数`innodb_log_group_home_dir`控制。**Redo log 以顺序的方式写入文件文件，写满时则回溯到第一个文件，进行覆盖写。**（但在做redo checkpoint时，也会更新第一个日志文件的头部checkpoint标记，所以严格来讲也不算顺序写）。

Redo log文件是循环写入的，在覆盖写之前，总是要保证对应的脏页已经刷到了磁盘。在非常大的负载下，Redo log可能产生的速度非常快，导致频繁的刷脏操作，进而导致性能下降，<u>通常在未做checkpoint的日志超过文件总大小的76%之后，InnoDB 认为这可能是个不安全的点，会强制的preflush脏页，导致大量用户线程stall住。</u><u>如果可预期会有这样的场景，我们建议调大redo log文件的大小。</u>可以做一次干净的shutdown，然后修改Redo log配置，重启实例。

### LSN

LSN(log sequence number) 用于记录日志序号，它是一个不断递增的 unsigned long long 类型整数。在 InnoDB 的日志系统中，LSN 无处不在，**它既用于表示修改脏页时的日志序号，也用于记录checkpoint**，通过LSN，<u>可以具体的定位到其在redo log文件中的位置。</u>

为了管理脏页，在 Buffer Pool 的每个instance上都维持了一个flush list，flush list 上的 page 按照修改这些 page 的LSN号进行排序。因此定期做redo checkpoint点时，选择的 LSN 总是所有 bp instance 的 flush list 上最老的那个page（拥有最小的LSN）<u>。由于采用WAL的策略，每次事务提交时需要持久化 redo log 才能保证事务不丢。</u>而延迟刷脏页则起到了合并多次修改的效果，避免频繁写数据文件造成的性能问题。

<u>当当前未刷脏的最老lsn和当前lsn的距离超过`max_modified_age_async`（71%）时，且开启了选项`innodb_adaptive_flushing`时，page cleaner线程会去尝试做更多的dirty page flush工作，避免脏页堆积</u>。 当当前未刷脏的最老lsn和当前Lsn的距离超过`max_modified_age_sync`(76%)时，**用户线程需要去做同步刷脏，这是一个性能下降的临界点，会极大的影响整体吞吐量和响应时间。** 当上次checkpoint的lsn和当前lsn超过`max_checkpoint_age`(81%)，用户线程需要同步地做一次checkpoint，需要等待checkpoint写入完成。 当上次checkpoint的lsn和当前lsn的距离超过`max_checkpoint_age_async`（78%）但小于`max_checkpoint_age`（81%）时，用户线程做一次异步checkpoint（后台异步线程执行CHECKPOINT信息写入操作），无需等待checkpoint完成。

## Redo 写盘操作

内存中(buffer pool)未刷到磁盘的数据称为脏数据(dirty data)。由于数据和日志都以页的形式存在，所以脏页表示脏数据和脏日志。

**在innodb中，数据刷盘的规则只有一个：checkpoint。**但是触发checkpoint的情况却有几种。<u>不管怎样，checkpoint触发后，会将buffer中脏数据页和脏日志页都刷到磁盘。</u>

有几种场景可能会触发redo log写文件：

1. sharp checkpoint：在重用redo log文件(例如切换日志文件)的时候，将所有已记录到redo log中对应的脏数据刷到磁盘。
2. fuzzy checkpoint：一次只刷一小部分的日志到磁盘，而非将所有脏日志刷盘。有以下几种情况会触发该检查点：
   - master thread checkpoint：由master线程控制，**每秒或每10秒**刷入一定比例的脏页到磁盘。
   - flush_lru_list checkpoint：从MySQL5.6开始可通过 innodb_page_cleaners 变量指定专门负责脏页刷盘的page cleaner线程的个数，该线程的目的是为了保证lru列表有可用的空闲页。
   - async/sync flush checkpoint：同步刷盘还是异步刷盘。例如还有非常多的脏页没刷到磁盘(非常多是多少，有比例控制)，这时候会选择同步刷到磁盘，但这很少出现；如果脏页不是很多，可以选择异步刷到磁盘，如果脏页很少，可以暂时不刷脏页到磁盘
   - dirty page too much checkpoint：脏页太多时强制触发检查点，目的是为了保证缓存有足够的空闲空间。too much的比例由变量 innodb_max_dirty_pages_pct 控制，MySQL 5.6默认的值为75，即当脏页占缓冲池的百分之75后，就强制刷一部分脏页到磁盘。

MySQL支持用户自定义在commit时如何将log buffer中的日志刷log file中。我们所熟悉的参数`innodb_flush_log_at_trx_commit` 就是作用于事务提交时，这也是最常见的场景：

- 当设置该值为1时，每次事务提交都要做一次fsync，这是最安全的配置，即使宕机也不会丢失事务；
- 当设置为2时，则在事务提交时只做write操作，只保证写到系统的page cache，因此实例crash不会丢失事务，但宕机则可能丢失事务；
- 当设置为0时，事务提交不会触发redo写操作，而是留给后台线程每秒一次的刷盘操作，因此实例crash将最多丢失1秒钟内的事务。

显然对性能的影响是随着持久化程度的增加而增加的。通常我们建议在日常场景将该值设置为1，但在系统高峰期临时修改成2以应对大负载。

由于各个事务可以交叉的将事务日志拷贝到log buffer中，因而一次事务提交触发的写redo到文件，可能隐式的帮别的线程“顺便”也写了redo log，从而达到group commit的效果。

### Redo checkpoint

InnoDB的redo log采用覆盖循环写的方式，而不是拥有无限的redo空间；即使拥有理论上极大的redo log空间，为了从崩溃中快速恢复，及时做checkpoint也是非常有必要的。

InnoDB的master线程大约每隔10秒会做一次redo checkpoint，但不会去preflush脏页来推进checkpoint点。

通常普通的低压力负载下，page cleaner线程的刷脏速度足以保证可作为检查点的lsn被及时的推进。但如果系统负载很高时，redo log推进速度过快，而page cleaner来不及刷脏，这时候就会出现用户线程陷入同步刷脏并做同checkpoint的境地，这种策略的目的是为了保证redo log能够安全的写入文件而不会覆盖最近的检查点。

### 事务恢复

<u>在启动innodb的时候，不管上次是正常关闭还是异常关闭，总是会进行恢复操作。</u>

因为redo log记录的是数据页的物理变化，因此恢复的时候速度比逻辑日志(如二进制日志)要快很多。而且，innodb自身也做了一定程度的优化，让恢复速度变得更快。

重启innodb时，checkpoint如果已经完整刷到磁盘上data page上的LSN，因此恢复时仅需要恢复从checkpoint开始的日志部分。例如，当数据库在上一次checkpoint的LSN为10000时宕机，且事务是已经提交过的状态。启动数据库时会检查磁盘中数据页的LSN，如果数据页的LSN小于日志中的LSN，则会从检查点开始恢复。

还有一种情况，在宕机前正处于checkpoint的刷盘过程，且数据页的刷盘进度超过了日志页的刷盘进度。这时候一宕机，数据页中记录的LSN就会大于日志页中的LSN，在重启的恢复过程中会检查到这一情况，这时超出日志进度的部分将不会重做，因为这本身就表示已经做过的事情，无需再重做。

另外，事务日志具有幂等性，所以多次操作得到同一结果的行为在日志中只记录一次。而二进制日志不具有幂等性，多次操作会全部记录下来，在恢复的时候会多次执行二进制日志中的记录，速度就慢得多。例如，某记录中id初始值为2，通过update将值设置为了3，后来又设置成了2，在事务日志中记录的将是无变化的页，根本无需恢复；而二进制会记录下两次update操作，恢复时也将执行这两次update操作，速度比事务日志恢复更慢。