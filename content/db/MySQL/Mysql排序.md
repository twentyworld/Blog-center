---
title: Mysql排序
type: docs
---

# Mysql排序

### 实际trace结果

```sql
select * from film where Producer like 'test%' and prod_time>'2015-12-01' order by actor_age;
```

笼统的来说，MySQL会按照：首先过滤数据，查找需要的数据:
对查找到的数据按照`order by actor_age`进行排序,并 按照`select *`将必要的数据按照`actor_age`依序返回给客户端。
空口无凭，我们可以利用`MySQL`的`optimize trace`来查看是否如上所述。
如果通过`optimize trace`看到更详细的`MySQL`优化器`trace`信息，可以查看阿里印风的博客初识5.6的`optimizer trace`。

依据`Producer like ‘test%’ and prod_time>’2015-12-01’`过滤数据，查找需要的数据:

```json
"attaching_conditions_to_tables": {
  "original_condition": "((`film`.`Producer` like 'test%') and (`film`.`prod_time` > '2015-12-01'))",
  "attached_conditions_computation": [
  ],
  "attached_conditions_summary": [
    {
      "table": "`film`",
      "attached": "((`film`.`Producer` like 'test%') and (`film`.`prod_time` > '2015-12-01'))"
    }
  ]
}
```

对查找到的数据按照`order by actor_age`进行排序,并按照`select *`将必要的数据按照`actor_age`依序返回给客户端:

``` json
      "join_execution": {
        "select#": 1,
        "steps": [
          {
            "filesort_information": [
              {
                "direction": "asc",
                "table": "`film`",
                "field": "actor_age"
              }
            ],
            "filesort_priority_queue_optimization": {
              "usable": false,
              "cause": "not applicable (no LIMIT)"
            },
            "filesort_execution": [
            ],
            "filesort_summary": {
              "rows": 1,
              "examined_rows": 5,
              "number_of_tmp_files": 0,
              "sort_buffer_size": 261872,
              "sort_mode": "<sort_key, packed_additional_fields>"
            }
          }
        ]
      }
```

这里，我们可以明显看到，MySQL在执行这个`select`的时候执行了针对film表.actor_age字段的asc排序操作。

```json
"filesort_information": [
              {
                "direction": "asc",
                "table": "film",
                "field": "actor_age"
              }
```

### 排序模式概览

我们这里主要关心MySQL到底是怎么排序的，采用了什么排序算法。

请关注这里:

```
"sort_mode": "<sort_key, packed_additional_fields>"
```

MySQL的sort_mode有三种。

摘录5.7.13中sql/filesort.cc源码如下：

```
  Opt_trace_object(trace, "filesort_summary")
    .add("rows", num_rows)
    .add("examined_rows", param.examined_rows)
    .add("number_of_tmp_files", num_chunks)
    .add("sort_buffer_size", table_sort.sort_buffer_size())
    .add_alnum("sort_mode",
               param.using_packed_addons() ?
               "<sort_key, packed_additional_fields>" :
               param.using_addon_fields() ?
               "<sort_key, additional_fields>" : "<sort_key, rowid>");
```

`< sort_key, rowid >`和`< sort_key, additional_fields >`看过其他介绍介绍MySQL排序文章的同学应该比较清楚，`< sort_key, packed_additional_fields >`相对较新。

`< sort_key, rowid >`对应的是MySQL 4.1之前的“原始排序模式”
`< sort_key, additional_fields >`对应的是MySQL 4.1以后引入的“修改后排序模式”
`< sort_key, packed_additional_fields >`是MySQL 5.7.3以后引入的进一步优化的”打包数据排序模式”
下面我们来一一介绍这三个模式：

#### 回表排序模式

- 根据索引或者全表扫描，按照过滤条件获得需要查询的排序字段值和row ID；
- 将要排序字段值和row ID组成键值对，存入sort buffer中；
- 如果sort buffer内存大于这些键值对的内存，就不需要创建临时文件了。否则，每次sort buffer填满以后，需要直接用qsort(快速排序算法)在内存中排好序，并写到临时文件中；
- 重复上述步骤，直到所有的行数据都正常读取了完成；
- 用到了临时文件的，需要利用磁盘外部排序，将row id写入到结果文件中；
- 根据结果文件中的row ID按序读取用户需要返回的数据。由于row ID不是顺序的，导致回表时是随机IO，为了进一步优化性能（变成顺序IO），MySQL会读一批row ID，并将读到的数据按排序字段顺序插入缓存区中(内存大小read_rnd_buffer_size)。

#### 不回表排序模式

- 根据索引或者全表扫描，按照过滤条件获得需要查询的数据；
- 将要排序的列值和用户需要返回的字段组成键值对，存入sort buffer中；
- 如果sort buffer内存大于这些键值对的内存，就不需要创建临时文件了。否则，每次sort buffer填满以后，需要直接用qsort(快速排序算法)在内存中排好序，并写到临时文件中；
- 重复上述步骤，直到所有的行数据都正常读取了完成；
- 用到了临时文件的，需要利用磁盘外部排序，将排序后的数据写入到结果文件中；
- 直接从结果文件中返回用户需要的字段数据，而不是根据row ID再次回表查询。

#### 打包数据排序模式

第三种排序模式的改进仅仅在于将char和varchar字段存到sort buffer中时，更加紧缩。

在之前的两种模式中，存储了“yes”3个字符的定义为VARCHAR(255)的列会在内存中申请255个字符内存空间，但是5.7.3改进后，只需要存储2个字节的字段长度和3个字符内存空间（用于保存”yes”这三个字符）就够了，内存空间整整压缩了50多倍,可以让更多的键值对保存在sort buffer中。

#### 三种模式比较

第二种模式是第一种模式的改进，避免了二次回表，采用的是用空间换时间的方法。

但是由于sort buffer就那么大，如果用户要查询的数据非常大的话，很多时间浪费在多次磁盘外部排序，导致更多的IO操作，效率可能还不如第一种方式。

所以，MySQL给用户提供了一个max_length_for_sort_data的参数。当“排序的键值对大小” > max_length_for_sort_data时，MySQL认为磁盘外部排序的IO效率不如回表的效率，会选择第一种排序模式；反之，会选择第二种不回表的模式。

第三种模式主要是解决变长字符数据存储空间浪费的问题，对于实际数据不多，字段定义较长的改进效果会更加明显。

很多文章写到这里可能就差不多了，但是大家忘记关注一个问题了：“如果排序的数据不能完全放在sort buffer内存里面，是怎么通过外部排序完成整个排序过程的呢？”

要解决这个问题，我们首先需要简单查看一下外部排序到底是怎么做的。

## 五、外部排序

### 5.1 普通外部排序

#### 5.1.1 两路外部排序

我们先来看一下最简单，最普遍的两路外部排序算法。

假设内存只有100M，但是排序的数据有900M，那么对应的外部排序算法如下：

- 从要排序的900M数据中读取100MB数据到内存中，并按照传统的内部排序算法（快速排序）进行排序；
- 将排序好的数据写入磁盘；
- 重复1，2两步，直到每个100MB chunk大小排序好的数据都被写入磁盘；
- 每次读取排序好的chunk中前10MB（= 100MB / (9 chunks + 1)）数据，一共9个chunk需要90MB，剩下的10MB作为输出缓存；
- 对这些数据进行一个“9路归并”，并将结果写入输出缓存。如果输出缓存满了，则直接写入最终排序结果文件并清空输出缓存；如果9个10MB的输入缓存空了，从对应的文件再读10MB的数据，直到读完整个文件。最终输出的排序结果文件就是900MB排好序的数据了。

#### 5.1.2 多路外部排序

上述排序算法是一个两路排序算法（先排序，后归并）。但是这种算法有一个问题，假设要排序的数据是50GB而内存只有100MB，那么每次从500个排序好的分片中取200KB（100MB / 501 约等于200KB）就是很多个随机IO。效率非常慢，对应可以这样来改进：

- 从要排序的50GB数据中读取100MB数据到内存中，并按照传统的内部排序算法（快速排序）进行排序；
- 将排序好的数据写入磁盘；
- 重复1，2两步，直到每个100MB chunk大小排序好的数据都被写入磁盘；
- 每次取25个分片进行归并排序，这样就形成了20个（500/25=20）更大的2.5GB有序的文件；
- 对这20个2.5GB的有序文件进行归并排序，形成最终排序结果文件。
- 对应的数据量更大的情况可以进行更多次归并。

### 5.2 MySQL外部排序

#### 5.2.1 MySQL外部排序算法

那MySQL使用的外部排序是怎么样的列，我们以回表排序模式为例：

- 根据索引或者全表扫描，按照过滤条件获得需要查询的数据；
- 将要排序的列值和row ID组成键值对，存入sort buffer中；
- 如果sort buffer内存大于这些键值对的内存，就不需要创建临时文件了。否则，每次sort buffer填满以后，需要直接用qsort(快速排序模式)在内存中排好序，作为一个block写到临时文件中。跟正常的外部排序写到多个文件中不一样，MySQL只会写到一个临时文件中，并通过保存文件偏移量的方式来模拟多个文件归并排序；
- 重复上述步骤，直到所有的行数据都正常读取了完成；
- 每MERGEBUFF (7) 个block抽取一批数据进行排序，归并排序到另外一个临时文件中，直到所有的数据都排序好到新的临时文件中；
- 重复以上归并排序过程，直到剩下不到MERGEBUFF2 (15)个block。

> 通俗一点解释：
> 第一次循环中，一个block对应一个sort buffer（大小为sort_buffer_size）排序好的数据；每7个做一个归并。
> 第二次循环中，一个block对应MERGEBUFF (7) 个sort buffer的数据，每7个做一个归并。
> …
> 直到所有的block数量小于MERGEBUFF2 (15)。

- 最后一轮循环，仅将row ID写入到结果文件中；
- 根据结果文件中的row ID按序读取用户需要返回的数据。为了进一步优化性能，MySQL会读一批row ID，并将读到的数据按排序字段要求插入缓存区中(内存大小read_rnd_buffer_size)。

这里我们需要注意的是：

1. MySQL把外部排序好的分片写入同一个文件中，通过保存文件偏移量的方式来区别各个分片位置；
2. MySQL每MERGEBUFF (7)个分片做一个归并，最终分片数达到MERGEBUFF2 (15)时，做最后一次归并。这两个值都写死在代码中了……

#### 5.2.2 sort_merge_passes

MySQL手册中对Sort_merge_passes的描述只有一句话

> The number of merge passes that the sort algorithm has had to do. If this value is large, you should consider increasing the value of the sort_buffer_size system variable.

这段话并没有把`sort_merge_passes`到底是什么，该值比较大时说明了什么，通过什么方式可以缓解这个问题。

我们把上面MySQL的外部排序算法搞清楚了，这个问题就清楚了。

其实`sort_merge_passes`对应的就是MySQL做归并排序的次数，也就是说，如果`sort_merge_passes`值比较大，说明`sort_buffer`和要排序的数据差距越大，我们可以通过增大`sort_buffer_size`或者让填入`sort_buffer_size`的键值对更小来缓解`sort_merge_passes`归并排序的次数。

对应的，我们可以在源码中看到证据。

上述`MySQL`外部排序的算法中第5到第7步，是通过`sql/filesort.cc`文件中`merge_many_buff()`函数来实现，第5步单次归并使用`merge_buffers()`实现，源码摘录如下：

```
int merge_many_buff(Sort_param *param, Sort_buffer sort_buffer,
                    Merge_chunk_array chunk_array,
                    size_t *p_num_chunks, IO_CACHE *t_file)
{
...
for (i=0 ; i < num_chunks - MERGEBUFF * 3 / 2 ; i+= MERGEBUFF)
{
  if (merge_buffers(param,                  // param
                    from_file,              // from_file
                    to_file,                // to_file
                    sort_buffer,            // sort_buffer
                    last_chunk++,           // last_chunk [out]
                    Merge_chunk_array(&chunk_array[i], MERGEBUFF),
                    0))                     // flag
  goto cleanup;
}
if (merge_buffers(param,
                  from_file,
                  to_file,
                  sort_buffer,
                  last_chunk++,
                  Merge_chunk_array(&chunk_array[i], num_chunks - i),
                  0))
  break;                                    /* purecov: inspected */
```

截取部分merge_buffers()的代码如下：

```
int merge_buffers(Sort_param *param, IO_CACHE *from_file,
                  IO_CACHE *to_file, Sort_buffer sort_buffer,
                  Merge_chunk *last_chunk,
                  Merge_chunk_array chunk_array,
                  int flag)
{
...
  current_thd->inc_status_sort_merge_passes();
...
}
```


可以看到：每个merge_buffers()都会增加sort_merge_passes，也就是说每一次对MERGEBUFF (7)个block归并排序都会让sort_merge_passes加一，sort_merge_passes越多表示排序的数据太多，需要多次merge pass。解决的方案无非就是缩减要排序数据的大小或者增加sort_buffer_size。

打个小广告，在我们的qmonitor中就有sort_merge_pass的性能指标和参数值过大的报警设置。

## 六、trace结果解释

说明白了三种排序模式和外部排序的方法，我们回过头来看一下trace的结果。

### 6.1 是否存在磁盘外部排序

`"number_of_tmp_files": 0`

number_of_tmp_files表示有多少个分片，如果number_of_tmp_files不等于0，表示一个sort_buffer_size大小的内存无法保存所有的键值对，也就是说，MySQL在排序中使用到了磁盘来排序。

### 6.2 是否存在优先队列优化排序

由于我们的这个SQL里面没有对数据进行分页限制，所以filesort_priority_queue_optimization并没有启用

```
"filesort_priority_queue_optimization": {              "usable": false,              "cause": "not applicable (no LIMIT)"            },
```


而正常情况下，使用了Limit会启用优先队列的优化。优先队列类似于FIFO先进先出队列。

算法稍微有点改变，以回表排序模式为例。

#### sort_buffer_size足够大

如果Limit限制返回N条数据，并且N条数据比sort_buffer_size小，那么MySQL会把sort buffer作为priority queue，在第二步插入priority queue时会按序插入队列；在第三步，队列满了以后，并不会写入外部磁盘文件，而是直接淘汰最尾端的一条数据，直到所有的数据都正常读取完成。

算法如下：

- 根据索引或者全表扫描，按照过滤条件获得需要查询的数据
- 将要排序的列值和row ID组成键值对，按序存入中priority queue中
- 如果priority queue满了，直接淘汰最尾端记录。
- 重复上述步骤，直到所有的行数据都正常读取了完成
- 最后一轮循环，仅将row ID写入到结果文件中
- 根据结果文件中的row ID按序读取用户需要返回的数据。为了进一步优化性能，MySQL会读一批row ID，并将读到的数据按排序字段要求插入缓存区中(内存大小read_rnd_buffer_size)。

#### sort_buffer_size不够大

否则，N条数据比sort_buffer_size大的情况下，MySQL无法直接利用sort buffer作为priority queue，正常的文件外部排序还是一样的，只是在最后返回结果时，只根据N个row ID将数据返回出来。具体的算法我们就不列举了。

这里MySQL到底是否选择priority queue是在sql/filesort.cc的check_if_pq_applicable()函数中确定的，具体的代码细节这里就不展开了。

另外，我们也没有讨论Limit m,n的情况，如果是Limit m,n， 上面对应的“N个row ID”就是“M+N个row ID”了，MySQL的Limit m,n 其实是取m+n行数据，最后把M条数据丢掉。

从上面我们也可以看到sort_buffer_size足够大对Limit数据比较小的情况，优化效果是很明显的。

## 七、MySQL其他相关排序参数

### 7.1 max_sort_length

这里需要区别max_sort_length和max_length_for_sort_data。

max_length_for_sort_data是为了让MySQL选择< sort_key, rowid >还是< sort_key, additional_fields >的模式。

而max_sort_length是键值对的大小无法确定时（比如用户要查询的数据包含了 SUBSTRING_INDEX(col1, ‘.’,2)）MySQL会对每个键值对分配max_sort_length个字节的内存，这样导致内存空间浪费，磁盘外部排序次数过多。

### 7.2 innodb_disable_sort_file_cache

innodb_disable_sort_file_cache设置为ON的话，表示在排序中生成的临时文件不会用到文件系统的缓存，类似于O_DIRECT打开文件。

### 7.3 innodb_sort_buffer_size

这个参数其实跟我们这里讨论的SQL排序没有什么关系。innodb_sort_buffer_size设置的是在创建InnoDB索引时，使用到的sort buffer的大小。

以前写死为1M，现在开放出来，允许用户自定义设置这个参数了。