+++
title = "riscv 启动"
date = 2025-11-12T00:00:00+08:00
tags = ["riscv", "bringup", "linux", "c3000"]
categories = ["riscv_linux"]
+++

[riscv linux 参考启动流程_rsic-v的bootload-CSDN博客](https://blog.csdn.net/u011011827/article/details/121416872)

# Opensbi

## 简介

[OpenSBI-Firmware固件 - 知乎 (zhihu.com)](https://zhuanlan.zhihu.com/p/630058209)

```c
// opensbi 能编译出三种固件(FW_PAYLOAD FW_JUMP FW_DYNAMIC), 用于不同的启动方式
// fw_dynamic: 固件运行时通过a2寄存器从上一个启动阶段获取有关下一个启动阶段的信息fw_dynamic_info，包含：引导加载程序或操作系统的内核。
{
 unsigned long magic;
 unsigned long version;
 unsigned long next_addr;
 unsigned long next_mode;
 unsigned long options;
 unsigned long boot_hart;/*避免由于重定位机制重写前一启动阶段造成的启动时崩溃，可指定HART
作为首选启动HART*/
}__packed;

// fw_jump: 固件假设下一引导阶段入口地址固定，不直接包含下一阶段的二进制代码
// make PLATFORM=generic FW_JUMP_ADDR=0X80200000

// fw_payload: 固件包含OpenSBI固件执行后启动阶段的二进制代码。不同于fw_jump固件的指定地址跳转，fw_payload固件将bootloader或os镜像直接打包进来。
// make PLATFORM=generic FW_PAYLOAD_PATH=uboot.bin
// make PLATFORM=generic FW_PAYLOAD_PATH=Image
```

## 代码分析

```c
sbi_hart_init
|- hart_detect_features // 解析 hart 支持的功能
	 |- val = hart_pmp_get_allowed_addr(); // 获取支持的 pmp 地址位数，和地址的颗粒大小
	 |  |- csr_write_allowed(CSR_PMPADDR0, (ulong)&trap, PMP_ADDR_MASK); // 往 csr_pmpaddr0 写入 ((_ULL(0x1) << 54) - 1), 53 位 1
	 |	|																																 // isa spec 规定 addr_field 只有	53 bit
	 |	|- val = csr_read_allowed(CSR_PMPADDR0, (ulong)&trap); // 回读 csr_pmpaddr0 , 判断 addr_field 哪写位可以写入
	 |	|		                                                   // 从而判断 pmp 地址位数，和地址的颗粒大小
	 |- hfeatures->pmp_gran =  1 << (__ffs(val) + 2); // __ffs(val) 表示获取 val 中首个为 1 的位号
	 |- hfeatures->pmp_addr_bits = __fls(val) + 1; // __fls(val) 表示获取 val 中最后为 1 的位号	  

sbi_boot_print_hart
|- bi_printf("Boot HART PMP Granularity : %lu\n", sbi_hart_pmp_granularity(scratch)); // 打印 pmp 地址颗粒
|  |- return hfeatures->pmp_gran;
|- sbi_printf("Boot HART PMP Address Bits: %d\n", sbi_hart_pmp_addrbits(scratch)); // 打印 pmp 地址位数   
	 |- return hfeatures->pmp_addr_bits;       
	 
// qemu 中 pmpaddr 操作
// qemu/target/riscv/pmp.c
pmpaddr_csr_write
|- env->pmp_state.pmp[addr_index].addr_reg = val; // 改写 pmpaddr，可见这里直接改写了，
																									// 不同 soc pmpaddr 颗粒不一样，应该需要 mark 一下 val 再赋值 																												 	  
```

# ABI

## 各个寄存器的作用

[RISC-V通用寄存器及函数调用规范 | Half Coder (gitee.io)](https://lgl88911.gitee.io/2021/02/15/RISC-V%E9%80%9A%E7%94%A8%E5%AF%84%E5%AD%98%E5%99%A8%E5%8F%8A%E5%87%BD%E6%95%B0%E8%B0%83%E7%94%A8%E8%A7%84%E8%8C%83/)

[RISC-V 入门 Part2: ABI && Calling Convention - 知乎 (zhihu.com)](https://zhuanlan.zhihu.com/p/261294574)

| Register | ABI Name | Saver(保存者) | 作用 |
| --- | --- | --- | --- |
| x0 | zero | — | 硬编码恒为0 |
| x1 | ra/rd | Caller(调用者) | 函数调用的返回地址 |
| x2 | sp | Callee(被调用者) | 堆栈指针 |
| x3 | gp | — | 全局指针 |
| x4 | tp  | — | 线程指针(current)（有一小段时间是在 CSR_SCRATCH 中） |
| x5-7 | t0-2 | Caller | 临时寄存器 |
| x8 | s0/fp | Callee | 保存寄存器/帧指针 |
| x9 | s1 | Callee | 保存寄存器 |
| x10-11 | a0-1 | Caller | 函数参数/返回值 |
| x12-17 | a2-7 | Caller | 函数参数，linux kernel a7 作为系统调用号 |
| x18-27 | s2-11 | Callee | 保存寄存器 |
| x28-31 | t3-6 | Caller | 临时寄存器 |

## 测试分析

### 带帧指针的情况

> **`-fno-omit-frame-pointer`**：强制保留 FP（牺牲少量性能）。
> 
> 
> 这个时候，`FP` 表示这个函数栈空间的开始，`SP` 表示这个函数栈空间的结束，可以用 `FP，SP` 检查栈溢出； 
> 
> ```bash
> # fp,sp 在栈中的位置，如下：
> # 函数中的局部变量使用 FP 索引，
> 													hight
> 													+-----------------+
> 													| last func stack |
> 	s0（当前函数的帧指针）->	+-----------------+ 
> 													|    ret addr     | <- ra（当前函数执行完毕后返回的位置）
> 													|  last func fp   | <- 上一个函数的帧指针
> 													| ...             |  
> 													| ...             | <- 当前函数的局部变量 
> 	sp（当前函数的栈顶）     | ...             |  
> 	---------------------->	+-----------------+
> s0（下一个函数的帧指针）   |    ret addr     | <- ra（下一个函数执行完毕后返回的位置）
> 													|  last func fp   | <- 上一个函数的帧指针
> 													| ...             |  
> 													| ...             | <- 当前函数的局部变量 
> 	sp（下一个函数的栈顶）   | ...             |  
> 	---------------------->	+-----------------+
> ```
> 

riscv_test.c

```c
#include <stdio.h>

int func(int c) {
        int a = 0, b = 0;
        a == a + b;
        return a;
}

void main(void){
        long long val = 0x12345678;

        func(1);

        printf("val = %llx\n", val);
}
```

```bash
riscv64-buildroot-linux-gnu-gcc ./riscv_test.c -o ./riscv_test
riscv64-buildroot-linux-gnu-objdump -d ./riscv_test

...
0000000000000694 <func>:
 694:   7179                    addi    sp,sp,-48 # 更新sp，sp = sp - 48
 696:   f422                    sd      s0,40(sp) # 将栈帧压栈，用于 ra 没有被用，所以不用压栈
 698:   1800                    addi    s0,sp,48  # 更新栈帧
 69a:   87aa                    mv      a5,a0
 69c:   fcf42e23                sw      a5,-36(s0)
 6a0:   fe042423                sw      zero,-24(s0)
 6a4:   fe042623                sw      zero,-20(s0)
 6a8:   fe842783                lw      a5,-24(s0)
 6ac:   853e                    mv      a0,a5     # a0 作为返回值
 6ae:   7422                    ld      s0,40(sp) # 恢复栈帧
 6b0:   6145                    addi    sp,sp,48  # 恢复 sp
 6b2:   8082                    ret

00000000000006b4 <main>:
 6b4:   1101                    addi    sp,sp,-32
 6b6:   ec06                    sd      ra,24(sp)  # 将 ra 压栈
 6b8:   e822                    sd      s0,16(sp)  # 将 s0(fp) 压栈
 6ba:   1000                    addi    s0,sp,32   # 配置 sp 为新的 fp
...
 6c8:   4505                    li      a0,1       # a0 用作第一个参数
 6ca:   fcbff0ef                jal     694 <func> # 会将 6ce 填入 ra/rd
 6ce:   fe843583                ld      a1,-24(s0)
 6d2:   00000517                auipc   a0,0x0     # 获取当前的 pc，即 6d2
 6d6:   01e50513                addi    a0,a0,30   # 6f0 <_IO_stdin_used+0x8>
 6da:   ec7ff0ef                jal     5a0 <printf@plt>
...
```

### 不带帧指针的情况（栈回溯）

> **禁用帧指针**：使用 `-**fomit-frame-pointer**` 选项。
> 
> 
> **优化级别**：在 `-**O1**` 及以上优化级别时，GCC/Clang **默认禁用帧指针**，无需显式指定
> 
> **原理：**使用 **`CFI （Call Frame Information, 调用帧信息）`**，计算调用栈，CFI 存储在如下地方：
> 
> - **`.debug_frame`**：**`-g`** 生成完整的 **`DWARF`** 调试信息( **`.debug_info`**：描述函数、变量、类型等源码级信息;
>     
>                                                                                                    **`.debug_line`**：源码行号与机器码地址的映射;
>     
>                                                                                                    **`.debug_frame`** 或 **`.eh_frame`**：栈展开规则)
>     
> - **`.eh_frame`** ：用于异常处理（如 C++ 异常）默认生成，使用**`-fno-asynchronous-unwind-tables`** 禁用
> 
> 1. **CFI 指令**：为每个 PC 位置定义如何展开栈帧。
>     - 例如：“在地址 0x400500，恢复寄存器 **`CFA`** 的方法是  **`CFA = SP + 16`**”。
> 2. **展开过程**：
>     - 根据当前 PC 值查找对应的 **CFI（FDE）**指令。
>     - 解析指令计算上一级栈帧的 `CFA` 和 `RA`。
>     - 重复直到栈底。
> 3. **`.eh_frame section`** 中的信息
>     - **CIE（Common Information Entry，公共信息条目）：** 共用的规则，所有函数的 `FDE` 的基础规则；
>     - **FDE（Frame Description Entry，帧描述条目 ）：**单个函数的规则， 包含代码的地址范围，包含如下内容：
>         - **CFA（Call Frame Addr）**: 帧地址
>         - **CFI 指令：**
>             - **`DW_CFA_def_cfa_register`**: 定义用于计算 CFA（规范帧地址）的寄存器（如 **`SP`**）。
>             - **`DW_CFA_def_cfa_offset`**:  定义 CFA（规范帧地址）计算偏移（如 **`8`**）。
>             - **`DW_CFA_def_cfa`**: 定义 CFA（规范帧地址）的计算方式（如 **`CFA = SP + 8`**）。
>             - **`DW_CFA_offset <reg>, <offset>`**: 寄存器 **`<reg>`** 的值保存在 CFA + **`<offset>`** 处。
>             - **`DW_CFA_advance_loc <delta>`**: 更新当前代码位置（用于分段定义规则）。
>             - **`DW_CFA_remember_state`** / **`DW_CFA_restore_state`**: 表面某个状态/寄存器 的 保存/恢复。
> 
> ```bash
> # cfa,sp 在栈中的位置，如下，可见减少了 fp 的操作，减少了指令数：
> # 函数中的局部变量使用 SP 索引，
> 													hight
> 													+-----------------+
> 													| last func stack |
> 						 			 cfa -> +-----------------+ 
> 													|    ret addr     | <- ra（当前函数执行完毕后返回的位置）
> 													| ...             |  
> 													| ...             | <- 当前函数的局部变量 
> 	sp（当前函数的栈顶）     | ...             |  
> 	---------------------->	+-----------------+
>   cfa                     |    ret addr     | <- ra（下一个函数执行完毕后返回的位置）
> 													| ...             |  
> 													| ...             | <- 当前函数的局部变量 
> 	sp（下一个函数的栈顶）    | ...             |  
> 	---------------------->	+-----------------+
> ```
> 

stack_call_test.c

```c
#include <stdio.h>
#include <stdlib.h>

void func1(int a) {
        int b = a;
        b = b + a;

        printf("b = %d\n", a);
}

void func2(int a) {
        int b = a;
        b = b + a;

        func1(b);
}

void func3(int a) {
        int b = a;
        b = b + a;

        func2(b);
}

void main(void) {
        func3(2);
}
```

分析（比 x86 好分析， x86的 sp 寄存器，可以通过 push/pop 指令改变）

```bash
# 反汇编代码
riscv64-linux-gnu-gcc ./stack_call_test.c -o ./stack_call_test -g -static -fomit-frame-pointer
riscv64-linux-gnu-objdump -d ./stack_call_test
...
0000000000010602 <main>:
   10602:       1141                    addi    sp,sp,-16
   10604:       e406                    sd      ra,8(sp)
   10606:       4509                    li      a0,2
   10608:       fd5ff0ef                jal     105dc <func3>
   1060c:       0001                    nop
   1060e:       60a2                    ld      ra,8(sp)
   10610:       0141                    addi    sp,sp,16
   10612:       8082                    ret
...

# 查看 .eh_frame section 信息
# CIE: 
# FDE:
# CFA: 调用帧地址
Contents of the .eh_frame section:

00000000 0000000000000010 00000000 CIE
  Version:               3
  Augmentation:          "zR"
  Code alignment factor: 1
  Data alignment factor: -4        # 栈的增长方向和数据对齐，即向下增长，4 字节对齐
  Return address column: 1         # 返回地址的寄存器编号，即 x1(ra)
  Augmentation data:     1b
  DW_CFA_def_cfa_register: r2 (sp) # 默认的用于计算 cfa 的寄存器
  DW_CFA_nop
...
# 描述 pc=0000000000010602..0000000000010614 范围内，fde 的信息（pc -> cfa -> sp -> ra），
# 根据当前 pc 找到对应 fde 中的对应规则，结合 curr_sp 可以获取到上一级函数的返回地址，然后逐级递归就可以找到整个调用栈了
00000078 000000000000001c 0000007c FDE cie=00000000 pc=0000000000010602..0000000000010614
  DW_CFA_advance_loc: 2 to 0000000000010604    # 执行到 2 个字节到达 0x10604，
  DW_CFA_def_cfa_offset: 16                    # cfa 的值相对 sp(cfa reg) 偏移了 16，即 cfa = curr_sp + 16
  DW_CFA_advance_loc: 2 to 0000000000010606    # 再执行到 2 个字节到达 0x10606，
  DW_CFA_offset: r1 (ra) at cfa-8              # ra 就被保存到了 cfa - 8，即 curr_sp + 8 = (curr_sp + 16)cfa - 8
  DW_CFA_advance_loc: 10 to 0000000000010610   # 再执行到 10 个字节到达 0x10610，
  DW_CFA_restore: r1 (ra)                      # ra(上一级函数的返回地址) 就被还原
  DW_CFA_advance_loc: 2 to 0000000000010612    # 再执行到 2 个字节到达 0x10612，
  DW_CFA_def_cfa_offset: 0                     # cfa 的值相对 sp(cfa reg) 偏移了 16，即 cfa = curr_sp + 16
  DW_CFA_nop
...
```

# ISA

`label 编译后的数值 = offset = label - pc`

- **`auipc`** (Add Upper Immediate to PC)，即将立即数加到 PC（程序计数器）的上半部分，将一个 20 位的立即数**`imm`**左移 12 位（乘以 4096），然后将结果与当前指令的 PC 的上半部分相加，最后将结果存储到目标寄存器**`rd`**中。
    
    ```c
    auipc rd, imm
    ```
    
- **`j`**（Jump）：无条件跳转到指定地址。这将会无条件跳转到标签 **`label`** 所表示的地址。
    
    ```c
    j label
    ```
    
- **`jal`**（Jump and Link）：跳转到指定地址，并将当前指令的下一条指令地址（PC+4）保存到目标寄存器中**`ra`**。这将会跳转到标签 **`label`** 所表示的地址，并将返回地址存储到目标寄存器中。
    
    ```c
    jal ra, offset
    ```
    
- **`beq`**（Branch if Equal）：如果寄存器 **`rs1`** 和 **`rs2`** 的值相等，那么将会跳转到标签 **`label`** 所表示的地址。
    
    ```c
    beq rs1, rs2, label
    ```
    
- **`bne`**（Branch if Not Equal）：如果寄存器 **`rs1`** 和 **`rs2`** 的值不相等，那么将会跳转到标签 **`label`** 所表示的地址。
    
    ```c
    bne rs1, rs2, label
    ```
    
- **`bge`** （Branch if Greater Than or Equal）：如果寄存器 **`rs1`** 大于或等于 **`rs2`**，那么将会跳转到标签 **`label`** 所表示的地址。
    
    ```c
    bge rs1, rs2, label
    ```
    
- **`bgeu`** （Branch if Greater Than or Equal Unsigned）：如果寄存器 **`rs1`** 无符号值大于或等于 **`rs2`** 无符号值，那么将会跳转到标签 **`label`** 所表示的地址。
    
    ```c
    bgeu rs1, rs2, label
    ```
    
- **`bltu`** （Branch if Less Than Unsigned）：如果寄存器 **`rs1`** 无符号值小于 **`rs2`** 无符号值，那么将会跳转到标签 **`label`** 所表示的地址。
    
    ```c
    bltu rs1, rs2, label
    ```
    
    （其余条件跳转指令使用方法类似）
    
- **`jalr`**（Jump and Link Register）：跳转到指定地址，并将当前指令的下一条指令地址（PC+4）保存到目标寄存器中。这将会跳转到地址 **`rs1 + offset`** 所表示的地址，并将返回地址（当前指令的下一条指令地址，PC+4）存储到目标寄存器 **`ra`** 中。
    
    ```c
    jalr ra, rs1, offset
    ```
    
- **`call`** 是 伪指令，被定义为 **`auipc`** 和 **`jalr`** 指令的组合
    
    ```c
    call label
    
    // call 指令展开后的形式
    // 其中 %pcrel_hi(label) 和 %pcrel_lo(label) 是汇编器提供的伪指令
    // 用于计算相对地址的高位和低位部分。
    auipc ra, %pcrel_hi(label)
    jalr ra, ra, %pcrel_lo(label)
    ```
    
- sfence.vma *// 刷新当前 hart 的 tlb*

## CSR

```bash
# Unprivileged csr
cycle	# cpu 运行的 cycle 数
time	# 可以认为是 timebase
instret	# cpu 运行的指令数

# Machine-Level
mhartid # 硬件线程id
mstatus # 机器状态寄存器，保存发生中断时，cpu 的状态，类似 msr，包含特权信息，也可以修改其，配合 mret 到达某个特权级
mie # 机器中断使能寄存器，各个中断使能位
mip # 机器中断ping
mtvec # 机器中断处理向量基地址，mode = 0，所有异常以 base 作为 向量入口；mode = 1，所有异常以 base * 中断向量 作为 向量入口
mtval # 机器中断处理异常信息
mcause # 机器中断原因，中断处理向量编号 
mepc # 机器陷入中断的地址
misa # ip 支持的扩展，每个 bit 表示一位
mtime # 是从 time 寄存器获取值，可以认为是 timebase‘
mtimecmp # time 比较寄存器，time >= mtimecmp 会触发 m-timer 中断

# Supervisor-Level
sstatus # 超级用户状态寄存器，保存发生中断时，cpu 的状态
sie # 超级用户中断使能寄存器，各个中断使能位
sip # 超级用户中断ping
stvec # 超级用户中断处理向量基地址
stval # 超级用户中断处理异常信息
scause # 超级用户中断原因，中断处理向量编号
sepc # 超级用户陷入中断的地址
stimecmp # time 比较寄存器，time >= stimecmp 会触发 s-timer 中断

satp # 超级用户虚拟地址转换和保护寄存器，控制 mmu 的开关和模式，页表目录
# c906 扩展的
smir # 超级用户模式 MMU Index 寄存器
smel # 超级用户模式 MMU EntryLo 寄存器，tlb 的 ppn
smeh # 超级用户模式 MMU EntryHi 寄存器，tlb 的 vpn
smcir # 超级用户模式 MMU 控制寄存器

# Hypervisor-Level
htimedelta # vs mode 中 time = time - htimedelta，进入 vs 前，会配置 htimedelta，保证 vs 获取到准确的 time，类似 arm 中的 offset
vstimecmp # time 比较寄存器，time >= vtimecmp 会触发 vs-timer 中断，vs 模式，vstimecmp 等价于 stimecmp
```

## 特权等级切换

![Untitled](Untitled.png)

```c
// 所有进程创建都会走这里
copy_thread
|- childregs->status = SR_PP | SR_PIE; // s/m 模式才走这里，内核调用才走这 kernel_thread / user_mode_thread
|- *childregs = *(current_pt_regs()); // u 模式，直接拷贝父进程的 regs，sys_clone / sys_clone3
|- p->thread.ra = (unsigned long)ret_from_fork; // 配置 进程的返回地址

// u 模式才走这
start_thread
|- regs->status = SR_PIE; // 特权等级为 0(SR_PP = 0, 表示 u-mode)
```

## Debug Mode

[debug mode](riscv%20%E5%90%AF%E5%8A%A8/debug%20mode.md)

## riscv profle

```bash
# RISC-V Profile 是 RISC-V 指令集架构中用于定义特定应用场景下处理器配置的标准。
# 这些配置文件（Profiles）旨在确保不同厂商的 RISC-V 处理器在特定市场中具有兼容性和一致性，
# 从而支持二进制软件生态系统的开发和部署。
# RVA23 Profile：旨在对 RISC-V 64 位应用处理器的实现进行对齐，
#								 确保二进制软件生态系统可以依赖于一组保证存在的扩展。
# RVB23 Profile：旨在为定制的 64 位应用处理器提供支持，这些处理器通常运行丰富的操作系统栈，
#                通常作为标准操作系统源代码分布的自定义构建。
# 详情查看: https://github.com/riscv/riscv-profiles/releases
# 其中描述了一些必须支持的扩展，但是根据扩展名字无法在最新的 isa (isa-20240411) 中找到，
# 但是根据 Sstvecd 描述，在 priv-isa-asciidoc 中 7.1.2 中有对应的描述，
# 判断这些扩展是在某些 isa 版本后默认支持的，但是没有描述名字；
# 或者说这些扩展只是一些规范，主要是看 soc 厂家是否按照这些实现某些指令的操作
# 因此这些应该是某些 isa 版本后，必须实现的标椎
• Ziccif: Main memory supports instruction fetch with atomicity requirement
• Ziccrse: Main memory supports forward progress on LR/SC sequences
• Ziccamoa: Main memory supports all atomics in A
• Ziccamoc Main memory supports atomics in Zacas
• Zicclsm: Main memory supports misaligned loads/stores
• Za64rs: Reservation set size of at most 64 bytes
• Zic64b: Cache block size is 64 bytes
...
• Sstvecd: stvec supports Direct mode

# qemu tcg 默认支持这些扩展功能（虽然 qemu 没有区分这些扩展，但是还是会根据用户配置，在 dts 中添加这些扩展的名字），
# 具体查看 commit '68c9e54beae82c08c0dd433a7baed36dabb425f8'
# 只需要 isa priv_spec > v1.12，就会在 dts 中添加这些扩展的名字
cat /sys/firmware/devicetree/base/cpus/cpu@0/riscv,isa
rv64imafdch_zic64b_zicbom_zicbop_zicboz_ziccamoa_ziccif_zicclsm_ziccrse_zicntr_zicsr_zifencei_zihintntl_zihintpause_zihpm_zmmul_za64rs_zaamo_zalrsc_zawrs_zfa_zfh_zfhmin_zca_zcd_zba_zbb_zbc_zbs_zkt_ssccptr_sscounterenw_sstc_sstvala_sstvecd_svadu_svinval_svnapot_svpbmt_svvptc

```

# 编译选项

```bash
RISCV_ABI=lp64 # 使用软件浮点
RISCV_ABI=lp64d # 使用硬件件浮点

# 查看 abi
readelf -h your_test_bin
ELF Header:
  Magic:   7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00 
...
  Flags:                             0x1, RVC, **soft-float ABI**
...
```

# linux 调试

```bash
# 编译
make ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- -j16

# 运行
# virt,aclint=on,aia=aplic-imsic 表示启用 aia，使用 aplic-imsic 作为中断控制器
# https://www.qemu.org/docs/master/system/riscv/virt.html
qemu-system-riscv64 -smp 8 -m 1g -M virt,aclint=on,aia=aplic-imsic -bios fw_jump.elf -kernel arch/riscv/boot/Image -initrd rootfs.cpio -append "console=ttyS0 rw root=/dev/ram" -nographic

# 使用虚拟网络，和网卡
qemu-system-riscv64 -nographic -machine virt -cpu rv64,v=true -m 1G -kernel ./arch/riscv/boot/Image \
-append "console=ttyS0 rw root=/dev/vda" \
-drive if=none,file=/home/jingl/buildroot/output/images/rootfs.ext4,format=raw,id=hd0 \
-device virtio-blk-device,drive=hd0 \
-device virtio-net-device,netdev=usernet \
-netdev user,id=usernet,hostfwd=tcp::22222-:22 \
-monitor telnet:localhost:5678,server,nowait
# 如果没有打印log，可以打开配置（CONFIG_SERIAL_8250_CONSOLE，CONFIG_SERIAL_OF_PLATFORM），或者直接使用 sbi 打印，ttyS0 -> hvc0
# 使用虚拟设备，需要打开配置（CONFIG_VIRTIO_BLK（virtio 块设备），CONFIG_VIRTIO_NET（virtio 网络））

# 调试
gdb-multiarch ./vmlinux
add-symbol-file vmlinux 0x80202000 -s .head.text 0x80200000 -s .rodata 0x80e00000 -s .init.text 0x80a00000

# 0x80202000 来源 kernel_map.phys_addr， riscv 不是从 0 启动
```

# Image 生成

```bash
# arch/riscv/boot/Makefile
...
OBJCOPYFLAGS_Image :=-O binary -R .note -R .note.gnu.build-id -R .comment -S
OBJCOPYFLAGS_xipImage :=-O binary -R .note -R .note.gnu.build-id -R .comment -S
...

# 等价于执行 $(cmd_objcopy)，$(if_changed) -> $(cmd_objcopy)
$(obj)/Image: vmlinux FORCE
	$(call if_changed,objcopy)

# scripts/Makefile.lib
# $(OBJCOPY) $(OBJCOPYFLAGS) $(OBJCOPYFLAGS_Image) vmlinux $(obj)/Image
quiet_cmd_objcopy = OBJCOPY $@
cmd_objcopy = $(OBJCOPY) $(OBJCOPYFLAGS) $(OBJCOPYFLAGS_$(@F)) $< $@

# Image 就是 vmlinux 的 bin
```

# 启动流程(_start → start_kernel)

```c
// 这个阶段不会解析 dtb，只是初始化了初级的页表，用于正常访问链接地址，
// 初始化函数可以正常运行，是因为偏移不大，都是用相对地址进行跳转，所以没有问题；
// powerpc 这个阶段，会解析 dtb，初始页表，early console 等，这时候用的就是链接地址，
// 因为 powerpc 实地址模式下，0xc000xxx 会转换为 0xxxx，去掉高位地址，
// 因此可以在 early 阶段，无需 mmu 可以直接使用链接地址；
// riscv 固件从 0x80200000 启动 kernel
// a0 = boot_cpu_hartid, a1 = dtb_addr
_start
|- _start_kernel
	|- setup_vm // 建立早期的页表目录
		 |- set_satp_mode(dtb_pa); // 检查支持的 mmu 模式，并配置 satp_mode
		 |- create_pgd_mapping(early_pg_dir, FIXADDR_START,
			   fixmap_pgd_next, PGDIR_SIZE, PAGE_TABLE); // **early_pg_dir** 中为 fixmap 创建页表，没创建 pte，用于 early_ioremap
		 |- create_pgd_mapping(trampoline_pg_dir, kernel_map.virt_addr,
			   trampoline_pgd_next, PGDIR_SIZE, PAGE_TABLE); // **trampoline_pg_dir** 创建内核的页表映射, 只映射了前面的 4k，看代码，是用来第一次使能 mmu，va != pa 导致异常，用到的中间页表，其实感觉没啥用
		 |- create_kernel_page_table(early_pg_dir, true); // **early_pg_dir** 目录的 kernel 映射
		 |- create_fdt_early_page_table(__fix_to_virt(FIX_FDT), dtb_pa); // **early_pg_dir** 目录中，fixmap 虚拟空间中，建立 dtb 映射
	|- relocate_enable_mmu // 第一次用 **trampoline_pg_dir** ，触发异常后进入 CSR_TVEC 中的虚拟地址，然后再次切换到 **early_pg_dir** 
	|- .Lsetup_trap_vector // 配置异常向量的入口地址 handle_exception
	|- soc_early_init // 设备初始前的 soc 初始化（如 clk）
	|- start_kernel
```

# /proc/cpuinfo 数据来源

```c
// '5.4, 6.12' 都是来源 'dts' 中的 'riscv,isa' 属性
// 只是 '6.12' 会将根据 'riscv,isa' 属性，进一步处理，去掉一些不支持的扩展
// 5.4 
// arch/riscv/kernel/cpu.c
c_show
|- if (!of_property_read_string(node, "riscv,isa", &isa)) print_isa(m, isa);
	 |- static const char *ext = "mafdcsu"; // 会检查是否只有这些，超过这些会报 "unsupported ISA xxxx in device tree"

// 6.12
// arch/riscv/kernel/cpu.c
c_show
|- print_isa(m, hart_isa[cpu_id].isa, cpu_id); // 根据 hart_isa[cpu_id].isa 位图，打印 isa 字符串
	
	// hart_isa 初始化
	riscv_fill_hwcap_from_isa_string
	|- struct riscv_isainfo *isainfo = &hart_isa[cpu];
	|- of_property_read_string(node, "riscv,isa", &isa);
	|- riscv_parse_isa_string(isa, source_isa); // 筛选 isa
		 |- match_isa_ext(ext, ext_end, bitmap); // 和 riscv_isa_ext 中的 ext 匹配的，配置对应的 bit
		 |	   const struct riscv_isa_ext_data riscv_isa_ext[] = {
		 |	 				__RISCV_ISA_EXT_DATA(i, RISCV_ISA_EXT_i),
		 |          ...
		 |	 				__RISCV_ISA_EXT_DATA(ziccrse, RISCV_ISA_EXT_ZICCRSE),
		 |	        ...
		 |	   };
		 |- riscv_resolve_isa(source_isa, isainfo->isa, &this_hwcap, isa2hwcap); // 拷贝 isainfo->isa
```

# 异常、中断

[异常,中断](riscv%20%E5%90%AF%E5%8A%A8/%E5%BC%82%E5%B8%B8,%E4%B8%AD%E6%96%AD.md)

# PMP（物理内存保护）

处理器中每个核都有一个独立的 PMP 单元，用于限制核对物理内存的访问

如果该核对任意一级页表所在的物理地址没有访问权限，那么这次地址翻译将会失败，并触发访问错误（access fault），陷入到 M-mode 中。

理论上我们也可以在内核启动后对代码段和只读数据段`用 PMP 禁止写入操作来保证内核代码和只读数据`的完整性。

PMP 规定了一系列 CSR（控制与状态寄存器，Control and Status Register）来划分物理内存区域和配置权限，这些 CSR 只能由 M-mode 的特权软件访问。这些 CSR 包括用于划分物理地址的 `pmpaddr` 寄存器和用于配置权限的 `pmpcfg` 寄存器。

每个 PMP 区域对应一个 8 比特的 `pmpcfg` 条目。

![Untitled](Untitled%201.png)

# Timer

![Untitled](Untitled%202.png)

```c
static inline cycles_t get_cycles(void)
{
	return csr_read(CSR_TIME);
}
#define get_cycles get_cycles
// 类似 get_tb, TIME 每个特权等级都可以访问

# STIMECMP 用于配置 riscv_timer_interrupt 触发时间，需要硬件实现扩展，减少进入 m mode
csr_write(CSR_STIMECMP, next_tval);
```

# MMU

[MMU](riscv%20%E5%90%AF%E5%8A%A8/MMU.md)

# NUMA 实现

## 框图

![Untitled](4009d323-9409-4c20-8973-0ec34e1ac515.png)

可以认为 node 的空间是个二维空间：
xy 中每个都相同，距离是 10；
xy 有一个是不同，距离是 20；
xy 中两个都不同，距离是 40；

## dts

```bash
# numa-node-id 属性作为 nid
# cpu,memory 节点应该包含 numa-node-id 属性 

# numa-distance-map-v1 用来描述 distance 的 map
# 参考 Documentation/devicetree/bindings/numa.txt
Example:
4 nodes 的距离如下：
0_______20______1
|               |
|               |
20             20
|               |
|               |
|_______________|
3       20      2

即：
0 -> 1 = 20
1 -> 2 = 20
2 -> 3 = 20
3 -> 0 = 20
0 -> 2 = 40
1 -> 3 = 40

dts 描述：
distance-map {
	 compatible = "numa-distance-map-v1";
	 distance-matrix = <0 0  10>,
			   <0 1  20>,
			   <0 2  40>,
			   <0 3  20>,
			   <1 0  20>,
			   <1 1  10>,
			   <1 2  20>,
			   <1 3  40>,
			   <2 0  40>,
			   <2 1  20>,
			   <2 2  10>,
			   <2 3  20>,
			   <3 0  20>,
			   <3 1  40>,
			   <3 2  20>,
			   <3 3  10>;
};
```

## 代码

```c
// 初始化
start_kernel
|- setup_arch
	 |- misc_mem_init
		  |- arch_numa_init();
			   |- numa_init(of_numa_init)
				 |	|- ret = numa_alloc_distance(); // drivers/base/arch_numa.c 通用接口
				 |	   |- numa_distance[i * numa_distance_cnt + j] = i == j ? LOCAL_DISTANCE : REMOTE_DISTANCE; // 描述 i -> j 的距离
				 |- ret = init_func(); // of_numa_init
					  |- of_numa_parse_cpu_nodes(); // 解析 cpu 的 numa id
						|- r = of_numa_parse_memory_nodes(); // 解析 memory 的 nid
						|- return of_numa_parse_distance_map(); // 解析 node 间的距离
							 |- np = of_find_compatible_node(NULL, NULL, "numa-distance-map-v1"); // 获取 numa-distance-map
							 |- ret = of_numa_parse_distance_map_v1(np); // 解析 numa-distance 
								  |- numa_set_distance(nodea, nodeb, distance);
									   |- numa_distance[from * numa_distance_cnt + to] = distance;
						
						   
// 使用，根据距离配置zonelist
build_zonelists
|- node = find_next_best_node(local_node, &used_mask)
	 |- val = node_distance(node, n); // __node_distance
		  |- return numa_distance[from * numa_distance_cnt + to];
```

# 虚拟化

[虚拟化](riscv%20%E5%90%AF%E5%8A%A8/%E8%99%9A%E6%8B%9F%E5%8C%96.md)

# dtb 嵌入 kernel

```bash
CONFIG_NONPORTABLE
> Platform type > [*] Allow configurations that result in non-portable kernels

CONFIG_BUILTIN_DTB
> Boot options > [*] Built-in device tree > (test/file) Built-in device tree source # dts文件在 arch/riscv/boot/dts/ 目录的相对路径，不要加后缀.dts

# 内核需要如下修改
1. 
mkdir arch/riscv/boot/dts/test
cp your_dts arch/riscv/boot/dts/test 
echo "dtb-y += file.dtb" > arch/riscv/boot/dts/test/Makefile
# arch/riscv/boot/dts/Makefile 添加 subdir-y += test

2.
mkdir arch/riscv/boot/dts/test
cp your_dts arch/riscv/boot/dts/test
# arch/riscv/boot/dts/Makefile 添加 dtb-y += $(srctree)/file.dtb
# 只要添加好 dtb 的路径，编译的时候，会自动找对于的 path/xxx.dts 进行编译
# %.dtb.o <- %.dtb.S <- %.dtb <- %.dts # scripts/Makefile.build
```

# early_console

`内核本来就有实现 EARLYCON_DECLARE(sbi, early_sbi_setup); // drivers/tty/serial/earlycon-riscv-sbi.c`

```c
// 使用 earlycon=sbi 启用
setup_arch
|- parse_early_param // 解析命令行，调用 early_param(xxx) 注册的接口
	 |- param_setup_earlycon // early_param("earlycon", param_setup_earlycon);
		  |- early_sbi_setup // EARLYCON_DECLARE(sbi, early_sbi_setup);
```

- 自己实现的 early console
    
    [0001-add-early-console.patch](riscv%20%E5%90%AF%E5%8A%A8/0001-add-early-console.patch)
    
    ```c
    // 启动配置 CONFIG_HVC_RISCV_SBI、CONFIG_RISCV_EARLY_CONSOLE
    // 注册 第一个 console
    setup_arch
    |- early_console_init
    	 |- hvc_sbi_early_init
    	 |	|- hvc_sbi_early_init_common(); // 配置 riscv_early_console_putc
    	 |	|- add_preferred_console("riscv_early_con", 0, NULL); // preferred_console 占个位，防止被 tty0 注册的时候，注销掉 riscv_early_console  
    	 |	|                                                     // 注不注册 hvc_console，后面通过 console=hvc 来决定
    	 |- register_early_console();	// 注册 riscv_early_console  
    
    parse_early_param
    |- console_setup
    	 |- __add_preferred_console(buf, idx, options, brl_options, true); // console=hvc 就添加 console 到 console_cmdline
    
    console_init
    |- hvc_console_init
    	 |- register_console(&hvc_console); // 不会注册成功
    			|- try_enable_preferred_console
    				 |- newcon->index = c->index; // 填充 hvc_console->index, c->index == 上面 add_preferred_console / __add_preferred_console 的 idx 参数
    				 |- err = console_call_setup(newcon, c->options); // 会出错
    					  |- hvc_console_setup
    							 |- if (vtermnos[co->index] == -1) return -ENODEV;
    							 
    hvc_sbi_init
    |- hvc_alloc // 配置 vtermnos[co->index] 
    	 |- hvc_check_console(i); // 重新注册 hvc_console
    	    |- register_console(&hvc_console); // 注册成功
    ```