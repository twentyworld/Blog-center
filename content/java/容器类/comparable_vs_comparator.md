---
title: Comparable vs Comparator
type: docs
---

## Java 中 Comparable 和 Comparator 比较

### Comparable 简介

**<u>Comparable 是排序接口。</u>**

若一个类实现了 Comparable 接口，就意味着“该类支持排序”。 即然实现 Comparable 接口的类支持排序，假设现在存在“实现 Comparable 接口的类的对象的 List 列表(或数组)”，则该 List 列表(或数组)可以通过 Collections.sort（或 Arrays.sort）进行排序。

此外，“实现 Comparable 接口的类的对象”可以用作“有序映射(如 TreeMap)”中的键或“有序集合(TreeSet)”中的元素，而不需要指定比较器。

Comparable 接口仅仅只包括一个函数，它的定义如下：

```java
    package java.lang;
    import java.util.*;

    public interface Comparable<T> {
        public int compareTo(T o);
    }
```

说明：假设我们通过 x.compareTo(y) 来“比较 x 和 y 的大小”。若返回“负数”，意味着“x 比 y 小”；返回“零”，意味着“x 等于 y”；返回“正数”，意味着“x 大于 y”。

### Comparator 简介

**<u>Comparator 是比较器接口。</u>**

我们若需要控制某个类的次序，而该类本身不支持排序(即没有实现 Comparable 接口)；那么，我们可以建立一个“该类的比较器”来进行排序。这个“比较器”只需要实现 Comparator 接口即可。

也就是说，我们可以通过“实现 Comparator 类来新建一个比较器”，然后通过该比较器对类进行排序。

Comparator 接口仅仅只包括两个个函数，它的定义如下：
```java

    package java.util;
    
    public interface Comparator<T> {
    
        int compare(T o1, T o2);
    
        boolean equals(Object obj);
    }
```

1. 若一个类要实现 Comparator 接口：它一定要实现 compareTo(T o1, T o2) 函数，但可以不实现 equals(Object obj) 函数。为什么可以不实现 equals(Object obj) 函数呢？ 因为任何类，默认都是已经实现了 equals(Object obj)的。 Java 中的一切类都是继承于 java.lang.Object，在 Object.java 中实现了 equals(Object obj)函数；所以，其它所有的类也相当于都实现了该函数。
2. int compare(T o1, T o2) 是“比较 o1 和 o2 的大小”。返回“负数”，意味着“o1 比 o2 小”；返回“零”，意味着“o1 等于 o2”；返回“正数”，意味着“o1 大于 o2”。
