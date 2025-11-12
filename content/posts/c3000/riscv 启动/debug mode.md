+++
title = "riscv debug mode"
date = 2025-11-12T00:00:00+08:00
tags = ["riscv", "debug", "linux", "c3000"]
categories = ["riscv_linux"]
+++

# 概况

![Untitled](debug%20mode/Untitled.png)

`debug mode` 是特殊的处理器模式，仅在 `hart` 由于外部调试而暂停时使用。

调试器想让 hart 进入 debug mode，步骤如下：

1. 配置 dmcontrol.dmactive = 0，复位 debug mouble(DM)
2. 配置 dmcontrol.dmactive = 1，使能 debug mouble(DM)
3. 配置好要选择的 hart (dmcontrol.hasel)
4. 配置 dmcontrol.haltreq = 1，让选择的 harts 进入 debug mode

# debug mode registers

`只能在 debug mode 模式下访问`

## dcsr(Debug Control and Status)

![Untitled](debug%20mode/Untitled%201.png)

| **Field** | **Description** | **Access** | **Reset** |
| --- | --- | --- | --- |
| **debuger** | debug spec 版本 | R | Preset |
| **ebreakx** | 0：ebreak 指令触发 `breakpoint 异常`；

1：ebreak 指令进入 `debug mode`； | WARL | 0 |
| **cause** | 进入 debug mode 的原因

1 (ebreak)：ebreak 指令执行，需要配置；

2 (trigger)：一个 Trigger Module trigger（hw_breakpoint） 被触发，而且配置为 `action=1`；

3 (haltreq)：调试器请求进入 debug mode（dmcontrol.haltreq = 1），不用配置

4 (step)：因为 dcsr.step = 1，hart 单步执行触发；

… | R | 0 |
| **step** | 配置 hart 单步执行，方法如下:
1. hart 处于 debug mode；
2. 配置 dcsr.step = 1；
3. hart 继续运行，退出 debug mode
4. hart 执行一条指令，停止运行，进入 debug mode，dcsr.cause = 4； |  |  |

## dpc(Debug PC)

用于记录进入 debug mode 时的地址，不同的原因，记录的地址不一样：

| cause | virtual addres in dpc |
| --- | --- |
| ebreak | ebreak 指令对应的地址（当前指令的地址） |
| trigger module | 下一条指令的地址 |
| halt request | 下一条指令的地址 |
| single step | 下一条指令的地址 |

# Triggers Module(硬件断点的实现，可以实现 memory 访问的监控）

独立于 Debug Module，理论上可以直接 csr 访问配置，具体需要看 spec 确定

可以配置成触发`breakpoint 异常`，或者 进入 `debug mode`