+++
title = "RISC-V 性能监控规范"
date = 2026-03-26T19:22:22.781986+08:00
tags = ["riscv", "linux"]
categories = ["riscv_linux"]
+++
# RISC-V 性能监控规范

---

# 1. 概述

`cycle`、`time`、`instret`、`hpmcounter3-31` 是面向软件的计数器 CSR，可被任意特权级直接访问，但访问权限受 **mcounteren / scounteren** 控制。

## 1.1 计数器与硬件来源

| 软件可见名称 | 硬件来源 (M-Mode) | 说明 |
| --- | --- | --- |
| `cycle` | `mcycle` | CPU 周期数 |
| `time` | `mtime` | 时间基准 |
| `instret` | `minstret` | 执行指令数 |
| `hpmcounter3-31` | `mhpmcounter3-31` | 硬件性能事件计数器 (共29个) |

### 1.2 事件选择寄存器

**mhpmevent3 ~ mhpmevent31**（仅 M 模式可写，必须通过 OpenSBI 配置）用于配置 `mhpmcounter3-31` 监控的事件。

> **注意**：该寄存器为可选实现，事件定义由各厂商自行规定（如 SiFive、玄铁等厂商均有各自定义）。
> 

---

# 2. mcounteren (Machine Counter-Enable)

> 控制下级特权级对计数器的访问权限，sbi 会在
> 

**实现要求**：如果 Hart 实现了 U 模式，则必须实现 mcounteren；如果没有 U 模式，则不应存在此 CSR。

## 2.1 寄存器布局 (Bit 0-31)

```
Bit:  [31:4]   [2]   [1]   [0]
      HPM3-31   IR    TM    CY
```

## 2.2 各比特含义

| 比特位 | 配置值 | 含义 |
| --- | --- | --- |
| CY (0) | 0 | 在 S/U 模式读取 `cycle` 触发 illegal-instruction 异常 |
| CY (0) | 1 | 在 S/U 模式可正常读取 `cycle` |
| TM (1) | 0 | 在 S/U 模式读取 `time` 或操作 `stimecmp/vstimecmp` 触发异常 |
| TM (1) | 1 | 在 S/U 模式可正常读取 `time` 及读写 `stimecmp/vstimecmp` |
| IR (2) | 0 | 在 S/U 模式读取 `instret` 触发 illegal-instruction 异常 |
| IR (2) | 1 | 在 S/U 模式可正常读取 `instret` |
| HPM3-31 (3-31) | 0 | 在 S/U 模式读取对应 `hpmcounter` 触发 illegal-instruction 异常 |
| HPM3-31 (3-31) | 1 | 在 S/U 模式可正常读取对应 `hpmcounter` |

> **补充**：S 模式有对应的 CSR (`scounteren`)，用于控制 U 模式的访问权限。
> 

---

# 3. mcountinhibit (Machine Counter-Inhibit)

> 抑制计数器递增（仅 M 模式可写）
> 

## 3.1 寄存器布局 (Bit 0-31)

```
Bit:  [31:4]    [2]     [1]     [0]
      HPM3-31   IR      0       CY
```

## 3.2 各比特含义

| 比特位 | 配置值 | 含义 |
| --- | --- | --- |
| CY (0) | 0 | `mcycle` 正常计数 |
| CY (0) | 1 | `mcycle` 停止计数 |
| IR (2) | 0 | `minstret` 正常计数 |
| IR (2) | 1 | `minstret` 停止计数 |
| HPM3-31 (3-31) | 0 | 对应的 `mhpmcounter` 正常计数 |
| HPM3-31 (3-31) | 1 | 对应的 `mhpmcounter` 停止计数 |

> **补充**：S 模式有对应的 CSR (`scountinhibit`)，通过 Smcdeleg/Ssccfg 机制委托控制。
> 

---

# 4. sscofpmf 扩展 (Count Overflow and Mode-Based Filtering)

> 该扩展已合入 RISC-V ISA 标准，定义了计数溢出控制及基于特权级的过滤机制。
> 

## 4.1 溢出中断

- 溢出中断使用 `mip/mie/sip/sie` CSR 的 **Bit 13** (LCOFIP/LCOFIE)

## 4.2 利用了 mhpmevent 寄存器部分格式 (64位)

```
Bit:  [63]   [62]   [61]   [60]   [59]   [58]  [57:0]
       OF    MINH   SINH   UINH  VSINH  VUINH   WPRI
```

## 4.3 各字段含义

| 字段 | 位置 (64位) | 位置 (32位 MHPMEVENTH) | 描述 |
| --- | --- | --- | --- |
| **OF** | Bit 63 | Bit 31 | 溢出状态位；计数溢出时置 1，1 也代表禁用溢出中断，因此溢出时会自动禁用中断 |
| **MINH** | Bit 62 | Bit 30 | M 模式下禁止对应事件计数 |
| **SINH** | Bit 61 | Bit 29 | S/HS 模式下禁止对应事件计数 |
| **UINH** | Bit 60 | Bit 28 | U 模式下禁止对应事件计数 |
| **VSINH** | Bit 59 | Bit 27 | VS 模式下禁止对应事件计数 |
| **VUINH** | Bit 58 | Bit 26 | VU 模式下禁止对应事件计数 |
| WPRI | Bits 57-0 | Bits 25-0 | 保留字段 |

> **初始化状态**：OpenSBI 初始化时设置 `MHPMEVENT_OF | MHPMEVENT_MINH`，即默认在 M 模式禁止计数并禁用溢出中断。
> 

> **cycle/instret 过滤**：smcntrpmf（Cycle and Instret Privilege Mode Filtering）扩展添加了 `mcyclecfg` / `minstretcfg` CSR，用于实现类似的特权级过滤功能。
> 

## 4.4 scountovf (Supervisor Count Overflow)

该扩展添加了 `scountovf` CSR (地址: 0x320)，每个比特对应 `mhpmevent3-31` 的 OF 标志位。

**作用**：允许 S 模式快速查询哪些事件发生溢出，无需陷入 M 模式读取 `mhpmevent3-31`。

```
scountovf Bit:  [31]    [30]   ...  [3]
                 OF      OF    ...  OF
                 ↓       ↓          ↓
            mhpmevent31 30     ...   3
```

---

# 5. smcdeleg/ssccfg (Counter Delegation)

> S 模式计数器委托机制
> 

在 RISC-V 架构中，部分计数器 CSR 默认只能由 M 模式访问。为了让 S 模式能够直接管理这些计数器，RISC-V 引入了 **Smcdeleg** 和 **Ssccfg** 扩展。

## 5.1 背景

默认情况下：

- `mhpmcounter`、`mhpmevent`、`mcountinhibit` 等 CSR 只有 M 模式可写
- S 模式需要通过 M 模式（通常是 OpenSBI）来配置这些寄存器

这增加了系统开销，因此引入了委托机制让 S 模式可以直接控制这些寄存器。

## 5.2 通过 sielect 选择寄存器，sireg 操作寄存器

当启用计数器委托后(`mencfg.CDE (Counter Delegation Enable) = 1`)，S 模式可以通过 `siselect` 和 `sireg` 来访问 M 模式的计数器相关 CSR：

| siselect 值 | sireg | sireg4 | sireg2 | sireg5 |
| --- | --- | --- | --- | --- |
| 0x40 | cycle | cycleh | cyclecfg | cyclecfgh |
| 0x41 | - | - | See below | - |
| 0x42 | instret | instreth | instretcfg | instretcfgh |
| 0x43 | hpmcounter3 | hpmcounter3h | hpmevent3 | hpmevent3h |
| ... | ... | ... | ... | ... |
| 0x5F | hpmcounter31 | hpmcounter31h | hpmevent31 | hpmevent31h |

> **注意**：OpenSBI 在初始化时会检测这些扩展的存在，并根据硬件能力自动配置相应功能。
> 

---

# 6. OpenSBI PMU 规范

OpenSBI 会根据 FDT 中的 `event_idx` 关联 `mhpmevent3-31` / `mhpmcounter3-31`，并提供了 SBI PMU 扩展接口，允许 S 模式配置和读取性能计数器。

**event_idx 编码格式**：

- `event_idx[19:16]` = type（事件类型）
- `event_idx[15:0]` = code（事件编码）

## 6.1 PMU 事件类型(type)

| 类型 | 类型 ID | 说明 |
| --- | --- | --- |
| `SBI_PMU_EVENT_TYPE_HW` | 0x00 | 硬件通用事件 |
| `SBI_PMU_EVENT_TYPE_HW_CACHE` | 0x01 | 缓存事件 |
| `SBI_PMU_EVENT_TYPE_HW_RAW` | 0x02 | 原始事件 (v1 版本) |
| `SBI_PMU_EVENT_TYPE_HW_RAW_V2` | 0x03 | 原始事件 (v2 版本) |
| `SBI_PMU_EVENT_TYPE_FW` | 0x0F | 固件事件 |

## 6.2 硬件通用事件 (type0, SBI_PMU_HW_*)

> 对应 perf 中 `PERF_TYPE_HARDWARE` 事件，perf list 时扫描 `event_symbols_hw` 数组得到；
> 

| 事件 ID(code) | 名称 | 说明 |
| --- | --- | --- |
| 0x00 | `SBI_PMU_HW_NO_EVENT` | 无事件 |
| 0x01 | `SBI_PMU_HW_CPU_CYCLES` | CPU 周期 |
| 0x02 | `SBI_PMU_HW_INSTRUCTIONS` | 执行指令数 |
| 0x03 | `SBI_PMU_HW_CACHE_REFERENCES` | 缓存引用 |
| 0x04 | `SBI_PMU_HW_CACHE_MISSES` | 缓存未命中 |
| 0x05 | `SBI_PMU_HW_BRANCH_INSTRUCTIONS` | 分支指令 |
| 0x06 | `SBI_PMU_HW_BRANCH_MISSES` | 分支预测失败 |
| 0x07 | `SBI_PMU_HW_BUS_CYCLES` | 总线周期 |
| 0x08 | `SBI_PMU_HW_STALLED_CYCLES_FRONTEND` | 前端停顿周期 |
| 0x09 | `SBI_PMU_HW_STALLED_CYCLES_BACKEND` | 后端停顿周期 |
| 0x0A | `SBI_PMU_HW_REF_CPU_CYCLES` | 参考 CPU 周期 |

## 6.3 缓存事件 (type1, SBI_PMU_HW_CACHE_*)

> 对应 perf 中 `PERF_TYPE_HW_CACHE` 事件，perf list 时扫描 `evsel__hw_cache` 数组得到；
> 

缓存事件由三部分组成：`cache_id` + `cache_op_id` + `cache_op_result`

**缓存 ID (cache_id)**：

| ID | 名称 | 说明 |
| --- | --- | --- |
| 0 | `SBI_PMU_HW_CACHE_L1D` | L1 数据缓存 |
| 1 | `SBI_PMU_HW_CACHE_L1I` | L1 指令缓存 |
| 2 | `SBI_PMU_HW_CACHE_LL` | 最后一级缓存 (LL) |
| 3 | `SBI_PMU_HW_CACHE_DTLB` | DTLB (数据 TLB) |
| 4 | `SBI_PMU_HW_CACHE_ITLB` | ITLB (指令 TLB) |
| 5 | `SBI_PMU_HW_CACHE_BPU` | 分支预测单元 |
| 6 | `SBI_PMU_HW_CACHE_NODE` | 节点缓存 |

**缓存操作 ID (cache_op_id)**：

| ID | 名称 | 说明 |
| --- | --- | --- |
| 0 | `SBI_PMU_HW_CACHE_OP_READ` | 读操作 |
| 1 | `SBI_PMU_HW_CACHE_OP_WRITE` | 写操作 |
| 2 | `SBI_PMU_HW_CACHE_OP_PREFETCH` | 预取操作 |

**缓存操作结果 (cache_op_result)**：

| ID | 名称 | 说明 |
| --- | --- | --- |
| 0 | `SBI_PMU_HW_CACHE_RESULT_ACCESS` | 访问 |
| 1 | `SBI_PMU_HW_CACHE_RESULT_MISS` | 未命中 |

**事件编码公式**：

```
code = (cache_id << 3) | (cache_op_id << 1) | cache_op_result
```

例如：L1D 缓存读未命中 = (0 << 3) | (0 << 1) | 1 = 1

## 6.4 固件事件 (type15, SBI_PMU_FW_*)

> 对应 perf 中 `PERF_TYPE_RAW` 事件，通过 sysfs 中的文件获取
> 

固件事件由 OpenSBI 在执行特定操作时自动递增（纯软件事件），用于统计 M 模式发生各种异常和调用的次数。

| 事件 ID(code) | 名称 | 触发条件 |
| --- | --- | --- |
| 0 | `SBI_PMU_FW_MISALIGNED_LOAD` | 未对齐 Load 陷入 |
| 1 | `SBI_PMU_FW_MISALIGNED_STORE` | 未对齐 Store 陷入 |
| 2 | `SBI_PMU_FW_ACCESS_LOAD` | 访问-fault (Load) |
| 3 | `SBI_PMU_FW_ACCESS_STORE` | 访问-fault (Store) |
| 4 | `SBI_PMU_FW_ILLEGAL_INSN` | 非法指令陷入 |
| 5 | `SBI_PMU_FW_SET_TIMER` | 设置定时器 |
| 6 | `SBI_PMU_FW_IPI_SENT` | 发送 IPI |
| 7 | `SBI_PMU_FW_IPI_RECVD` | 接收 IPI |
| 8 | `SBI_PMU_FW_FENCE_I_SENT` | 发送 FENCE.I |
| 9 | `SBI_PMU_FW_FENCE_I_RECVD` | 接收 FENCE.I |
| 10 | `SBI_PMU_FW_SFENCE_VMA_SENT` | 发送 SFENCE.VMA |
| 11 | `SBI_PMU_FW_SFENCE_VMA_RCVD` | 接收 SFENCE.VMA |
| 12 | `SBI_PMU_FW_SFENCE_VMA_ASID_SENT` | 发送 SFENCE.VMA (带 ASID) |
| 13 | `SBI_PMU_FW_SFENCE_VMA_ASID_RCVD` | 接收 SFENCE.VMA (带 ASID) |
| 14 | `SBI_PMU_FW_HFENCE_GVMA_SENT` | 发送 HFENCE.GVMA (VMALL) |
| 15 | `SBI_PMU_FW_HFENCE_GVMA_RCVD` | 接收 HFENCE.GVMA |
| 16 | `SBI_PMU_FW_HFENCE_GVMA_VMID_SENT` | 发送 HFENCE.GVMA (带 VMID) |
| 17 | `SBI_PMU_FW_HFENCE_GVMA_VMID_RCVD` | 接收 HFENCE.GVMA (带 VMID) |
| 18 | `SBI_PMU_FW_HFENCE_VVMA_SENT` | 发送 HFENCE.VVMA |
| 19 | `SBI_PMU_FW_HFENCE_VVMA_RCVD` | 接收 HFENCE.VVMA |
| 20 | `SBI_PMU_FW_HFENCE_VVMA_ASID_SENT` | 发送 HFENCE.VVMA (带 ASID) |
| 21 | `SBI_PMU_FW_HFENCE_VVMA_ASID_RCVD` | 接收 HFENCE.VVMA (带 ASID) |

## 6.5 原始事件 (type2/3, Raw Event)

> 对应 perf 中 `PERF_TYPE_RAW` 事件，通过 sysfs 中的文件获取
> 

原始事件允许直接使用硬件事件选择器。

| 事件 | event_idx | event_data |
| --- | --- | --- |
| **RAW v1** | 0x20000,type=0x2,code=0x0 | mhpmevent[47:0] |
| **RAW v2** | 0x20000,type=0x3,code=0x0 | mhpmevent[55:0] |

对于原始事件，`event_data` 直接用作 `mhpmevent` 的值，`event_data` 需要匹配 Device Tree 中 `riscv,raw-event-to-mhpmcounters` 属性的规则（`fdt_value == event_data & fdt_mask`），对应 `/sys/bus/event_source/devices/cpu/events/xx` 中记录的 event 字段。

---

# 7. RISC-V PMU Device Tree 规范

RISC-V PMU 通过 Device Tree 向操作系统描述硬件性能监控能力。PMU 节点需要位于 `/cpus` 节点下或作为 CPU 节点的子节点。

## 7.1 必需属性

| 属性名称 | 类型 | 描述 |
| --- | --- | --- |
| `compatible` | string | 必须为 `"riscv,pmu"` |

## 7.2 可选属性

| 属性名称 | 类型 | 描述 |
| --- | --- | --- |
| `riscv,event-to-mhpmevent` | array | PMU 事件 ID 到 `mhpmevent` 编码的映射（一对一） |
| `riscv,event-to-mhpmcounters` | array | 事件 ID 范围到计数器位图的映射（一对多） |
| `riscv,raw-event-to-mhpmcounters` | array | 原始事件 event_data 到计数器位图的映射（用于 Raw Event） |

## 7.3 属性详解

## 7.3.1 riscv,event-to-mhpmevent

该属性定义了 SBI PMU 事件 ID（event_idx）到硬件 `mhpmevent` 值的映射。每个元素包含三个 32 位值：

```
<event_idx mhpmevent_upper mhpmevent_lower>
```

- `event_idx`：20 位事件编码（高 4 位为 type，低 16 位为 code），和 sbi pmu 规范定义的一致
- `mhpmevent`：写入 `mhpmevent` CSR 的值

**示例**（HiFive Unmatched）：

```
riscv,event-to-mhpmevent =
    /* SBI_PMU_HW_CACHE_REFERENCES -> U74 event */
    <0x00003 0x00000000 0x1801>,
    /* SBI_PMU_HW_CACHE_MISSES -> U74 event */
    <0x00004 0x00000000 0x0302>,
    /* L1D_READ_MISS -> U74 event */
    <0x10001 0x00000000 0x0202>;
```

## 7.3.2 riscv,event-to-mhpmcounters

该属性定义了事件 ID 范围到可用计数器的映射。每个元素包含三个值：

```
<first_event_idx last_event_idx counter_bitmap>
```

- `first_event_idx`：事件 ID 起始值
- `last_event_idx`：事件 ID 结束值
- `counter_bitmap`：可用计数器位图（bit N 对应 hpmcounterN）

**示例**：

```
riscv,event-to-mhpmcounters =
    /* 事件 0x00001-0x00001 使用计数器 0 */
    <0x00001 0x00001 0x00000001>,
    /* 事件 0x00002-0x00002 使用计数器 2 */
    <0x00002 0x00002 0x00000004>,
    /* 事件 0x00003-0x0000A 使用计数器 3-8 */
    <0x00003 0x0000A 0x00000ff8>,
    /* 事件 0x10000-0x10033 使用计数器 12-19 */
    <0x10000 0x10033 0x000ff000>;
```

## 7.3.3 riscv,raw-event-to-mhpmcounters

该属性定义了原始事件 data 到计数器的映射，用于支持厂商自定义的 Raw Event。每个元素包含五个值：

```
<invariant_upper invariant_lower variant_upper variant_lower counter_bitmap>
```

- `invariant`：事件的不变部分
- `variant_mask`：事件的变体掩码（用于匹配事件范围）
- `counter_bitmap`：可用计数器位图

匹配公式：`invariant == event_data & variant_mask`，则使用对应的计数器。

**示例**：

```
riscv,raw-event-to-mhpmcounters =
    /* 精确匹配 event_data 0x0002 */
    <0x0000 0x0002 0xffffffff 0xffffffff 0x00000f8>,
    /* 匹配 event_data 0-4 */
    <0x0 0x0 0xffffffff 0xfffffff0 0x00000ff0>,
    /* 匹配 0xffffffff0000000f - 0xffffffff000000ff */
    <0xffffffff 0x0 0xffffffff 0xffffff0f 0x00000ff0>;
```

## 7.4 依赖关系

- `riscv,event-to-mhpmevent` 依赖 `riscv,event-to-mhpmcounters`
- 如果不提供这些属性，Linux 将无法使用 SBI PMU 扩展

---

# 8. Linux Perf 集成

## 8.1 Perf 事件类型

Perf 支持两类事件源：

1. **通用事件** (Hardware/Software/Cache Event)
    - 通过 `perf list hw/sw/cache` 查看
    - 通过静态数组 `event_symbols_hw/evsel__hw_cache` 固定扫描的事件
    - 示例: `cycles`, `instructions`, `cache-misses`
    - 类型: `hw`, `sw`
2. **PMU 定制事件** (Raw Event)
    - 需要厂商在 Device Tree 中定义
    - 通过 `perf list pmu` 查看
    - 通过 `/sys/bus/event_source/devices/cpu/events/` 目录下的文件暴露给 pmu
    - 类型: `raw`

## 8.2 Perf 扫描流程

```
1. Perf 启动
   ↓
2. 查找 cpu 通用的 event 事件 (静态数组定义，如 cache-misses, branch-misses 等)
   ↓
3. 查找自定义的 pmu event，扫描 /sys/bus/event_source/devices/cpu/ 或者 pmu 的 json 文件
   ↓
4. 判断硬件支持情况
   ↓
5. 创建对应的 perf event
```

---

# 附录：相关 CSR 寄存器汇总

| CSR 名称 | 地址 | 描述 |
| --- | --- | --- |
| `mcycle` / `cycle` | 0xB00 / 0xC00 | 周期计数器 (M-mode / S-mode) |
| `mtime` / `time` | 0x701 / 0xC01 | 时间计数器 (M-mode / S-mode) |
| `minstret` / `instret` | 0xB02 / 0xC02 | 指令 retired 计数器 |
| `mhpmcounter3-31` / `hpmcounter3-31` | 0xB03-0xB1F / 0xC03-0xC1F | 硬件性能事件计数器 |
| `mcounteren` | 0x306 | M 模式计数器访问使能 |
| `scounteren` | 0x106 | S 模式计数器访问使能 (控制 U 模式) |
| `mcountinhibit` | 0x320 | M 模式计数器禁止 |
| `scountinhibit` | 0x120 | S 模式计数器禁止 |
| `mcyclecfg` | 0x321 | M 模式时钟计数配置 (smcntrpmf 扩展) |
| `minstretcfg` | 0x322 | M 模式指令计数配置 (smcntrpmf 扩展) |
| `mhpmevent3-31` | 0x323-0x33F | 硬件性能事件选择器 |
| `scountovf` | 0xDA0 | S 模式溢出标志 (sscofpmf 扩展) |

---

# 9. 代码分析流程

[RISC-V Perf 代码原理分析](.//RISC-V%20Perf%20%E4%BB%A3%E7%A0%81%E5%8E%9F%E7%90%86%E5%88%86%E6%9E%90.md)

# 附录：相关规范文档

- RISC-V ISA Manual - Volume II: Privileged Architecture
- RISC-V SBI Specification (v3.0+)