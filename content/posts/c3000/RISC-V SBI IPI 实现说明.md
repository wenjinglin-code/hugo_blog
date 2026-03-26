+++
title = "RISC-V SBI IPI 实现说明"
date = 2026-03-26T19:22:22.781865+08:00
tags = ["riscv", "linux"]
categories = ["riscv_linux"]
+++
# RISC-V SBI IPI 实现说明

# 1. 概述

**IPI（Inter-Processor Interrupt）** 是处理器间中断，用于在不同 **Hart（Hardware Thread，硬件线程）** 之间进行通信和同步。在 RISC-V 架构中，没有实现 **`AIA-IMSIC`** 时，Linux 内核需要使用 **SBI（Supervisor Binary Interface，监管者二进制接口）** 提供的接口来触发其他 Hart 的软件中断（各平台自定义实现）。

# 2. 系统架构

> 以 Andes PLICSW 为例
> 

## 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Linux Kernel                                │
│                                                                      │
│   sbi_send_ipi()                                                    │
│        │                                                              │
│        │           IRQ_S_SOFT (Supervisor Software Interrupt)       │
│        │           S 模式软件中断                                      │
│        ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                     IPI Mux Domain                            │   │
│   │   (Linux 侧模拟的 IPI 中断控制器，管理多个 IPI 事件类型)       │   │
│   └─────────────────────────────────────────────────────────────┘   │
│        │                                                              │
│        ▼                                                              │
│   sbi_ipi_handle()  ── 处理 IPI 中断 ──► 处理各个 IPI 事件          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ SBI Calls (ECALL)
                                   │ SBI 调用（环境调用）
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           OpenSBI                                   │
│                                                                      │
│   sbi_ecall_ipi_handler()  ── 处理 SBI IPI 调用                     │
│        │                                                              │
│        ▼                                                              │
│   sbi_ipi_send_smode()  ── 发送 IPI 到目标 Hart                     │
│        │                                                              │
│        ▼                                                              │
│   sbi_ipi_send_many()  ── 批量发送 IPI                              │
│        │                                                              │
│        ▼                                                              │
│   sbi_ipi_send()  ── 为每个目标 Hart 设置 IPI 类型并触发中断        │
│        │                                                              │
│        ▼                                                              │
│   sbi_ipi_raw_send()  ── 调用底层硬件驱动                           │
│        │                                                              │
│        ▼                                                              │
│   ipi_dev->ipi_send()  ── 触发目标 Hart 的 Software Interrupt       │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        硬件 IPI 设备                                 │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    Andes PLICSW                             │   │
│   │                  (PLIC Software - PLIC 软件中断)             │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   触发目标 Hart 的 mip.MSIP (Machine Software Interrupt Pending)    │
│   M 模式软件中断挂起位                                               │
└─────────────────────────────────────────────────────────────────────┘
```

## 2.2 IPI 中断触发流程

```
┌──────────────────────────┐      ┌──────────────────────────┐
│      Source Hart         │      │      Target Hart         │
│        (源 Hart)         │      │       (目标 Hart)        │
│                          │      │                          │
│  Linux Kernel           │      │  OpenSBI                 │
│  sbi_send_ipi()         │      │  sbi_ipi_process()       │
│         │                │      │         │                │
│         ▼                │      │         ▼                │
│  SBI ECALL               │      │  处理 ipi_type 中的      │
│  (IPI_SEND_IPI)          │      │  所有待处理 IPI 事件      │
│         │                │      │         │                │
│         ▼                │      │         ▼                │
│  OpenSBI                 │      │  sbi_ipi_process_smode   │
│  sbi_ipi_raw_send()      │      │  触发 S 模式的software interrupt│
│         │                │      │  (设置 mip.SSIP)        │
│         ▼                │      │  S 模式软件中断挂起位     │
│  PLICSW 触发              │───► │          │               │
│  (设置 pending 位)       │       │         ▼                │
│  触发目标 Hart 的         │       │  Linux Kernel            │
│   mip.MSIP              │       │  sbi_ipi_handle()        │
│   M 模式软件中断挂起位    │        │ 处理 IPI 事件，清除 sip.SSIP│
└──────────────────────────┘      └──────────────────────────┘
```

# 3. Linux Kernel 侧实现

## 3.1 IPI 初始化流程

Linux Kernel 通过 Device Tree（设备树）获取中断控制器信息，并初始化 IPI 机制。以下是主要初始化步骤：

```c
// arch/riscv/kernel/sbi-ipi.c

void __init sbi_ipi_init(void)
{
	// ...

	/*
	 * 步骤 1: 向 intc domain 获取 RV_IRQ_SOFT (Supervisor Software Interrupt)
	 *         的 Linux 中断号
	 *         RV_IRQ_SOFT 是 S 模式软件中断的中断号
	 */
	sbi_ipi_virq = irq_create_mapping(domain, RV_IRQ_SOFT);
	if (!sbi_ipi_virq) {
		pr_err("unable to create INTC IRQ mapping\\n");
		return;
	}

	/*
	 * 步骤 2: 创建 Linux 模拟的 IPI 中断控制器 (ipi_mux_domain)
	 *         - virq: 该控制器的硬件中断号对应的 Linux 中断号
	 *         - sbi_send_ipi: 触发中断控制器中断的接口
	 *         - BITS_PER_BYTE: 支持的 IPI 事件类型数量（8 种）
	 */
	virq = ipi_mux_create(BITS_PER_BYTE, sbi_send_ipi);

	// ...

	/*
	 * 步骤 3: 为 RV_IRQ_SOFT 设置链式中断处理函数
	 *         当目标 Hart 收到 IPI 时，会调用 sbi_ipi_handle
	 */
	irq_set_chained_handler(sbi_ipi_virq, sbi_ipi_handle);

	// ...

	/*
	 * 步骤 4: 为 virq 注册对应中断处理函数，处理各个 IPI 事件类型
	 */
	riscv_ipi_set_virq_range(virq, BITS_PER_BYTE);
	pr_info("providing IPIs using SBI IPI extension\\n");

	// ...
}
```

## 3.2 IPI 发送流程

```c
// arch/riscv/kernel/sbi-ipi.c

/*
 * Linux 发送 IPI 的入口函数
 * 通过 SBI 调用通知目标 Hart
 */
static void __sbi_send_ipi_v02(unsigned int cpu)
{
	/*
	 * 调用 SBI 接口发送 IPI
	 * SBI_EXT_IPI: IPI 扩展 ID (0x73504900)
	 * SBI_EXT_IPI_SEND_IPI: 发送 IPI 函数 ID (0x0)
	 * 1UL: hmask - 目标 Hart 位掩码（只发送到 hbase 对应的 hart）
	 * cpuid_to_hartid_map(cpu): hbase - 目标 Hart 的起始 Hart ID
	 *
	 * ECALL 会触发从 S 模式到 M 模式的切换
	 */
	ret = sbi_ecall(SBI_EXT_IPI, SBI_EXT_IPI_SEND_IPI,
			1UL, cpuid_to_hartid_map(cpu), 0, 0, 0, 0);
}
```

# 4. OpenSBI 核心实现

## 4.1 核心数据结构

### IPI 硬件设备结构体

```c
// include/sbi/sbi_ipi.h

/** IPI 硬件设备 */
struct sbi_ipi_device {
	/** 设备名称 */
	char name[32];

	/** 发送 IPI 到目标 Hart */
	void (*ipi_send)(u32 hart_index);

	/** 清除当前 Hart 的 IPI 状态 */
	void (*ipi_clear)(void);
};
```

## 4.3 IPI 发送流程

```c
// lib/sbi/sbi_ipi.c

/*
 * 发送 IPI 到多个目标 Hart
 *
 * @param hmask: 目标 Hart 位掩码
 * @param hbase: 目标 Hart 的起始 Hart ID
 * @param event: IPI 事件类型（bit 编号）
 * @param data: 传递给 IPI 事件处理函数的数据
 *
 * @return 0 表示成功，负数表示错误码
 */
int sbi_ipi_send_many(ulong hmask, ulong hbase, u32 event, void *data)
{
	// ...

	/* 发送 IPI 到每个目标 Hart */
	do {
		retry_needed = false;
		sbi_hartmask_for_each_hartindex(i, &target_mask) {
			rc = sbi_ipi_send(scratch, i, event, data);
			// ...
		}
	} while (retry_needed);

	/* 同步所有 IPI，确保所有目标 Hart 都收到 IPI */
	sbi_ipi_sync(scratch, event);

	return rc;
}

/*
 * 发送 IPI 到单个远程 Hart
 *
 * @param scratch: 当前 Hart 的 scratch 区域
 * @param remote_hartindex: 目标 Hart 的 hart index
 * @param event: IPI 事件类型（bit 编号）
 * @param data: 传递给 IPI 事件处理函数的数据
 */
static int sbi_ipi_send(struct sbi_scratch *scratch, u32 remote_hartindex,
			u32 event, void *data)
{
	// ...

	/*
	 * 在远程 Hart 的 scratch 区域设置 IPI 类型并触发中断
	 *
	 * 多个 Hart 可能同时向同一个远程 Hart 发送 IPI
	 * 使用原子操作确保只有一个 Hart 触发底层硬件发送
	 * linux 调用下来使用的是 ipi_smode_event
	 * 只有当 ipi_data->ipi_type 为 0, 没有事件需要处理时，才能发
	 */
	if (!__atomic_fetch_or(&ipi_data->ipi_type, BIT(event), __ATOMIC_RELAXED))
		ret = sbi_ipi_raw_send(remote_hartindex);

	// ...
}

/*
 * 底层 IPI 发送函数
 * 调用硬件设备驱动的 ipi_send 回调
 *
 * @param hartindex: 目标 Hart 的 hart index
 */
int sbi_ipi_raw_send(u32 hartindex)
{
	if (!ipi_dev || !ipi_dev->ipi_send)
		return SBI_EINVAL;

	/*
	 * 内存屏障：确保在此函数之前完成的内存或 MMIO 写入
	 * 不会在 ipi_send() 设备回调的内存或 MMIO 写入之后被观察到
	 */
	wmb();

	ipi_dev->ipi_send(hartindex);
	return 0;
}
```

## 4.4 IPI 事件处理

```c
// lib/sbi/sbi_ipi.c

/**
 * 处理当前 Hart 的所有待处理 IPI 事件
 * 在 M 模式处理完 IPI 后返回 S 模式之前调用
 */
void sbi_ipi_process(void)
{
	unsigned long ipi_type;
	unsigned int ipi_event;
	const struct sbi_ipi_event_ops *ipi_ops;
	struct sbi_scratch *scratch = sbi_scratch_thishart_ptr();
	struct sbi_ipi_data *ipi_data =
			sbi_scratch_offset_ptr(scratch, ipi_data_off);

	sbi_pmu_ctr_incr_fw(SBI_PMU_FW_IPI_RECVD);

	/* 清除硬件 IPI 状态 */
	sbi_ipi_raw_clear();

	/* 原子地交换出所有待处理的 IPI 类型并清零 */
	ipi_type = atomic_raw_xchg_ulong(&ipi_data->ipi_type, 0);

	/* 遍历所有 IPI 事件类型，处理每个待处理的 IPI */
	ipi_event = 0;
	while (ipi_type) {
		if (ipi_type & 1UL) {
			/* 调用对应事件类型的处理函数 */
			ipi_ops = ipi_ops_array[ipi_event];
			if (ipi_ops)
				ipi_ops->process(scratch);
		}
		ipi_type = ipi_type >> 1;
		ipi_event++;
	}
}

/**
 * S 模式 IPI 事件处理函数
 * 设置 S 模式软件中断挂起位（SSIP），通知目标 Hart 有 IPI 待处理
 */
static void sbi_ipi_process_smode(struct sbi_scratch *scratch)
{
	/* 设置 mip.SSIP（S 模式软件中断挂起位） */
	csr_set(CSR_MIP, MIP_SSIP);
}

/**
 * Halt IPI 事件处理函数
 * 请求目标 Hart 进入休眠状态
 */
static void sbi_ipi_process_halt(struct sbi_scratch *scratch)
{
	sbi_hsm_hart_stop(scratch, true);
}
```

## 4.5 IPI 初始化

```c
// lib/sbi/sbi_ipi.c

/*
 * IPI 子系统初始化
 *
 * @param scratch: 当前 Hart 的 scratch 区域
 * @param cold_boot: 是否是冷启动（true 表示首次启动，false 表示从 S 模式返回）
 *
 * @return 0 表示成功，负数表示错误码
 */
int sbi_ipi_init(struct sbi_scratch *scratch, bool cold_boot)
{
	int ret;
	struct sbi_ipi_data *ipi_data;

	if (cold_boot) {
		/* 分配 scratch 空间用于存储 IPI 数据 */
		ipi_data_off = sbi_scratch_alloc_offset(sizeof(*ipi_data));
		if (!ipi_data_off)
			return SBI_ENOMEM;

		/* 注册 S 模式 IPI 事件 */
		ret = sbi_ipi_event_create(&ipi_smode_ops);
		if (ret < 0)
			return ret;
		ipi_smode_event = ret;

		/* 注册 Halt IPI 事件 */
		ret = sbi_ipi_event_create(&ipi_halt_ops);
		if (ret < 0)
			return ret;
		ipi_halt_event = ret;

		/* 初始化平台 IPI 支持（解析设备树并注册 IPI 设备） */
		ret = sbi_platform_ipi_init(sbi_platform_ptr(scratch));
		if (ret)
			return ret;
	}

	/* 初始化当前 Hart 的 IPI 数据 */
	ipi_data = sbi_scratch_offset_ptr(scratch, ipi_data_off);
	ipi_data->ipi_type = ATOMIC_INIT(0);

	/* 清除当前 Hart 的待处理 IPI */
	sbi_ipi_raw_clear();

	/* 使能 M 模式软件中断 (M 模式下的 MSIP) */
	csr_set(CSR_MIE, MIP_MSIP);

	return 0;
}
```

# 5. Andes PLICSW 设备驱动

**PLICSW（PLIC Software）** 是 **Andes Technology（晶心科技）** 提供的软件中断解决方案，作为 **PLIC（Platform Level Interrupt Controller，平台级中断控制器）** 的扩展。

## 5.1 设备驱动注册

```c
// lib/utils/ipi/fdt_ipi_plicsw.c

/*
 * 注册一个 fdt_driver 驱动，用于扫描设备树（Device Tree）中的 "andestech,plicsw" 节点
 */
static const struct fdt_match ipi_plicsw_match[] = {
	{ .compatible = "andestech,plicsw" },
	{ },
};

const struct fdt_driver fdt_ipi_plicsw = {
	.match_table = ipi_plicsw_match,
	.init = fdt_plicsw_cold_ipi_init,
};
```

## 5.2 驱动实现

```c
// lib/utils/ipi/andes_plicsw.c

/*
 * PLICSW IPI 发送函数
 * 通过设置 pending 寄存器触发目标 Hart 的软件中断
 *
 * @param hart_index: 目标 Hart 的 hart index
 */
static void plicsw_ipi_send(u32 hart_index)
{
	ulong pending_reg;
	u32 interrupt_id, word_index, pending_bit;
	u32 target_hart = sbi_hartindex_to_hartid(hart_index);

	if (plicsw.hart_count <= target_hart)
		ebreak();

	/*
	 * 每个 Hart 分配一个 bit
	 * Bit 0 硬连线到 0，不可使用
	 * Bit (X+1) 表示 IPI 发送到 Hart X
	 */
	interrupt_id = target_hart + 1;
	word_index   = interrupt_id / 32;
	pending_bit  = interrupt_id % 32;
	pending_reg  = plicsw.addr + PLICSW_PENDING_BASE + word_index * 4;

	/*
	 * 写 1 到对应 bit 触发目标 Hart 的 mip.MSIP
	 * MSIP (Machine Software Interrupt Pending) 是 M 模式软件中断挂起位
	 */
	writel_relaxed(BIT(pending_bit), (void *)pending_reg);
}

/* 注册 PLICSW 设备 */
static struct sbi_ipi_device plicsw_ipi = {
	.name      = "andes_plicsw",
	.ipi_send  = plicsw_ipi_send,
	.ipi_clear = plicsw_ipi_clear
};
```

# 6. SBI IPI 扩展接口

## 6.1 ECALL 处理

```c
// lib/sbi/sbi_ecall_ipi.c

/*
 * SBI IPI 扩展 ECALL 处理函数
 * 处理来自 S 模式的 IPI 相关调用
 *
 * @param extid: 扩展 ID（SBI_EXT_IPI）
 * @param funcid: 函数 ID
 * @param regs: 触发 ECALL 时的寄存器状态
 * @param out: ECALL 返回值结构体
 *
 * @return 0 表示成功，负数表示错误码
 */
static int sbi_ecall_ipi_handler(unsigned long extid, unsigned long funcid,
				 struct sbi_trap_regs *regs,
				 struct sbi_ecall_return *out)
{
	int ret = 0;

	if (funcid == SBI_EXT_IPI_SEND_IPI) {
		/*
		 * 发送 IPI 到 S 模式
		 * a0: hmask - 目标 Hart 位掩码
		 * a1: hbase - 目标 Hart 的起始 Hart ID
		 */
		ret = sbi_ipi_send_smode(regs->a0, regs->a1);
	} else {
		ret = SBI_ENOTSUPP;
	}

	return ret;
}

/* 注册 SBI IPI 扩展 */
struct sbi_ecall_extension ecall_ipi = {
	.name			= "ipi",
	.extid_start		= SBI_EXT_IPI,       // 0x73504900 ('SPI' << 8)
	.extid_end		= SBI_EXT_IPI,
	.register_extensions	= sbi_ecall_ipi_register_extensions,
	.handle			= sbi_ecall_ipi_handler,
};
```

## 6.2 SBI IPI 函数 ID

```c
// include/sbi/sbi_ecall_interface.h

/** SBI IPI 扩展 ID：0x73504900 = ('SPI' << 8) */
#define SBI_EXT_IPI			0x73504900

/** SBI IPI 发送函数 ID */
#define SBI_EXT_IPI_SEND_IPI		0x0
```

## 6.3 调用流程

```
Linux Kernel                         OpenSBI
    │                                   │
    │  ECALL (a7=SBI_EXT_IPI,          │
    │         a0=hmask, a1=hbase)      │
    │  S 模式发起的环境调用              │
    ├──────────────────────────────────►│
    │                                   │
    │                                   ├──► sbi_ecall_ipi_handler()
    │                                   │         │
    │                                   │         ▼
    │                                   │    sbi_ipi_send_smode()
    │                                   │         │
    │                                   │         ▼
    │                                   │    sbi_ipi_send_many()
    │                                   │         │
    │                                   │         ▼
    │                                   │    sbi_ipi_raw_send()
    │                                   │         │
    │                                   │         ▼
    │                                   │    plicsw_ipi_send()
    │                                   │    (写 pending 寄存器)          
    │                                   │
    │  返回 (a0=返回值)                   │
    ◄───────────────────────────────────┤
```

# 7. 初始化流程总结

## 7.1 系统启动顺序

```
1. OpenSBI 冷启动 (cold_boot=true)
   │
   ├── sbi_ipi_init(scratch, true)
   │   ├── 分配 IPI 数据空间（scratch 区域）
   │   ├── 注册 IPI 事件类型（SMODE, HALT）
   │   └── sbi_platform_ipi_init()
   │       └── fdt_ipi_init()
   │           └── 扫描设备树中的 IPI 设备
   │               └── andestech,plicsw
   │                   └── fdt_plicsw_cold_ipi_init()
   │                       └── plicsw_cold_ipi_init()
   │                           └── sbi_ipi_set_device(&plicsw_ipi)
   │
   ├── 使能 M 模式软件中断 (csr_set(CSR_MIE, MIP_MSIP))
   │
   └── 启动 Linux Kernel

2. Linux Kernel 启动
   │
   └── sbi_ipi_init()
       ├── 获取 RV_IRQ_SOFT（S 模式软件中断）的中断号
       ├── 创建 ipi_mux_domain（IPI 复用域）
       └── 设置中断处理函数
```