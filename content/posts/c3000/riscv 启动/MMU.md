+++
title = "riscv mmu"
date = 2025-11-12T00:00:00+08:00
tags = ["riscv", "memory", "linux", "c3000"]
categories = ["riscv_linux"]
+++

# MMU 硬件原理（priv-isa ）

## 页表目录：**`satp` ,** 结构如下（大端）

![Untitled](MMU/Untitled.png)

### PPN: 一级页表的 `physical page number`

### ASID：页表的标识号（软件配置），用于和 TLB 中的条目匹配，这样就可以达到 切换 进程时，不刷新 tlb 的效果（每个进程对应一个 ASID)

`asid 的位数和 hw 有关，不同硬件 asid bit 不一样，可以通过写 0xFFFF 到 ASID，然后回读，确认 bit 数`

### MODE：标识是几级页表，虚拟地址长度

![Untitled](MMU/Untitled%201.png)

- SV32（没有一些特殊属性（大页，页表类型））

![Untitled](MMU/Untitled%202.png)

- SV57

![image.png](MMU/image.png)

`如果实现了 svadu 扩展，硬件会自动更新 pte.D/A bit，就不需要在 page-fault 中处理 D/A bit`

`没有实现 svadu，需要实现 svade 扩展，在以下情况触发异常，然后再物理页中更新 D/A bit：`

- `访问物理页并且 A==0；`
- `写物理页并且 D==0；`

`D bit 会在回写完毕后，置 0；A bit 会在页表回收机制中，置 0；`

# 大页支持

## page_size == PMD_SIZE / PUD_SIZE

N 位好像只是告诉 MMU 这个 pte 是连续的pte，如果 `page_size == PMD_SIZE` 直接配置 pmd_t 为 pte 就可以了，对应的 pte.ppn[0] 要配置为 0

![Untitled](MMU/Untitled%203.png)

![Untitled](MMU/Untitled%204.png)

## page_size != PMD_SIZE / PUD_SIZE

需要配置 N 位，告诉 MMU 这个 pte 是**`一个 NAPOT 范围`**的一部分

![Untitled](MMU/Untitled%205.png)

目前只规定了 64k，page offset 怎么配套，没拿到 pte 前又不知道 pte 是大页？

spec 有说明翻译的流程：

![Untitled](MMU/Untitled%206.png)

大体架构：

![Untitled](MMU/Untitled%207.png)

**`riscv / arm64 大页的意思，都是使用连续的 ptes 映射大 size 的 page，每个 pte 映射的还是 4k，只是 tlb 可以将多个 pte 映射，只用一个 entry 表示 va 到 大 size page 的映射，减少大内存映射对 tlb entry 的使用`**

powerpc 的大页实现，是直接配置 psize 到 hpte

riscv 大页新的patch：[[PATCH RESEND v2 0/9] Merge arm64/riscv hugetlbfs contpte support - Alexandre Ghiti (kernel.org)](https://lore.kernel.org/all/20240508113419.18620-1-alexghiti@rivosinc.com/)

## 相关代码

```c
arch_make_huge_pte
|- entry = pte_mknapot(entry, order);
	 |- return __pte((pte_val(pte) & napot_mask) | napot_bit | _PAGE_NAPOT);
		
// arch/riscv/include/asm/pgtable-64.h
/*
 * rv64 PTE format:
 * | 63 | 62 61 | 60 54 | 53  10 | 9             8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0
 *   N      MT     RSV    PFN      reserved for SW   D   A   G   U   X   W   R   V
 */
#define _PAGE_PFN_MASK  GENMASK(53, 10)

/*
 * [63] Svnapot definitions:
 * 0 Svnapot disabled
 * 1 Svnapot enabled
 */
#define _PAGE_NAPOT_SHIFT	63
#define _PAGE_NAPOT		BIT(_PAGE_NAPOT_SHIFT)

// page 类型
/*
 * [62:61] Svpbmt Memory Type definitions:
 *
 *  00 - PMA    Normal Cacheable, No change to implied PMA memory type
 *  01 - NC     Non-cacheable, idempotent, weakly-ordered Main Memory
 *  10 - IO     Non-cacheable, non-idempotent, strongly-ordered I/O memory
 *  11 - Rsvd   Reserved for future standard use
 */
#define _PAGE_NOCACHE_SVPBMT	(1UL << 61)
#define _PAGE_IO_SVPBMT		(1UL << 62)
#define _PAGE_MTMASK_SVPBMT	(_PAGE_NOCACHE_SVPBMT | _PAGE_IO_SVPBMT)

// arm64 的大页实现，也是配置 entry
pte_t arch_make_huge_pte(pte_t entry, unsigned int shift, vm_flags_t flags)
{
	size_t pagesize = 1UL << shift;

	entry = pte_mkhuge(entry);
	if (pagesize == CONT_PTE_SIZE) {
		entry = pte_mkcont(entry);
	} else if (pagesize == CONT_PMD_SIZE) {
		entry = pmd_pte(pmd_mkcont(pte_pmd(entry)));
	} else if (pagesize != PUD_SIZE && pagesize != PMD_SIZE) {
		pr_warn("%s: unrecognized huge page size 0x%lx\n",
			__func__, pagesize);
	}
	return entry;
}
```

# va → pa 的转换

## va 范围

![Untitled](MMU/Untitled%208.png)

## 相关代码

```c
// arch/riscv/include/asm/page.h
// kernel_mapping 结构体解析
struct kernel_mapping {
	unsigned long page_offset;         // PAGE_OFFSET(线性映射的起始地址)
	unsigned long virt_addr;           // KERNEL_LINK_ADDR + kernel_map.virt_offset， 就是链接地址
	unsigned long virt_offset;         // kernel 随机化用到，默认是 0
	uintptr_t phys_addr;               // kernel 被加载到的物理地址
	uintptr_t size;                    // kernel 代码的大小（_end - _start）
	unsigned long va_pa_offset;        // page_offset - phys_ram_base, 内存映射才用到
	unsigned long va_kernel_pa_offset; // virt_addr + virt_offset - phys_addr, kernel 获取一些变量的物理地址用到
	unsigned long va_kernel_xip_pa_offset;
#ifdef CONFIG_XIP_KERNEL
	uintptr_t xiprom;
	uintptr_t xiprom_sz;
#endif
};

#define __virt_to_phys(x)	__va_to_pa_nodebug(x)
| #define __va_to_pa_nodebug(x)	({						\
|	unsigned long _x = x;							\
|	is_linear_mapping(_x) ?							\
|		linear_mapping_va_to_pa(_x) : kernel_mapping_va_to_pa(_x);	\
|	})
	| #define linear_mapping_va_to_pa(x)	((unsigned long)(x) - kernel_map.va_pa_offset)
	| #define kernel_mapping_va_to_pa(y) ({						\
	| unsigned long _y = (unsigned long)(y);					\
	| (IS_ENABLED(CONFIG_XIP_KERNEL) && _y < kernel_map.virt_addr + XIP_OFFSET) ? \
	| 	(_y - kernel_map.va_kernel_xip_pa_offset) :			\
	| 	(_y - kernel_map.va_kernel_pa_offset - XIP_OFFSET);		\
	| })

// 可见 kernel 不在 linear 范围内
#define is_kernel_mapping(x)	\
	((x) >= kernel_map.virt_addr && (x) < (kernel_map.virt_addr + kernel_map.size)) // x >= 0xffffffff80000000 && x < 0xffffffff80000000 + (_end - _start)

#define is_linear_mapping(x)	\
	((x) >= PAGE_OFFSET && (!IS_ENABLED(CONFIG_64BIT) || (x) < PAGE_OFFSET + KERN_VIRT_SIZE))  // x >= 0xff60000000000000(CONFIG_PAGE_OFFSET) && x < 0xffa0000000000000(0xff60000000000000 + 2^57(0x0100000000000000) * 2^-2)

// VMALLOC 等的地址范围
#define VMALLOC_START    (PAGE_OFFSET - VMALLOC_SIZE)
#define FIXADDR_START    (FIXADDR_TOP - FIXADDR_SIZE)

// arch/riscv/include/asm/pgtable.h
/*
 * Task size is 0x4000000000 for RV64 or 0x9fc00000 for RV32.
 * Note that PGDIR_SIZE must evenly divide TASK_SIZE.
 * Task size is:
 * -        0x9fc00000	(~2.5GB) for RV32.
 * -      0x4000000000	( 256GB) for RV64 using SV39 mmu
 * -    0x800000000000	( 128TB) for RV64 using SV48 mmu
 * - 0x100000000000000	(  64PB) for RV64 using SV57 mmu
 *
 * Note that PGDIR_SIZE must evenly divide TASK_SIZE since "RISC-V
 * Instruction Set Manual Volume II: Privileged Architecture" states that
 * "load and store effective addresses, which are 64bits, must have bits
 * 63–48 all equal to bit 47, or else a page-fault exception will occur."
 * Similarly for SV57, bits 63–57 must be equal to bit 56.
 */
// 用户态最大地址
#define TASK_SIZE	TASK_SIZE_64

```

# 内核页表初始化流程

## **early_pg_dir、trampoline_pg_dir、** **swapper_pg_dir 的作用**

![Untitled](MMU/Untitled%209.png)

## 代码流程

```c
_start_kernel
|- setup_vm // 建立早期的页表目录
	 |- set_satp_mode(dtb_pa); // 检查支持的 mmu 模式，并配置 satp_mode，对应 STAP:MODE
	 |- create_pgd_mapping(early_pg_dir, FIXADDR_START,
		   fixmap_pgd_next, PGDIR_SIZE, PAGE_TABLE); // **early_pg_dir** 中为 fixmap 创建页表，没创建 pte，用于 early_ioremap
	 |- create_pgd_mapping(trampoline_pg_dir, kernel_map.virt_addr,
		   trampoline_pgd_next, PGDIR_SIZE, PAGE_TABLE); // **trampoline_pg_dir** 创建内核的页表映射, 只映射了前面的 2M，看代码，是用来第一次使能 mmu，va != pa 导致异常，是使pc 变为 va，用到的中间页表
	 |- create_kernel_page_table(early_pg_dir, true); // **early_pg_dir** 目录的 kernel 映射
	 |- create_fdt_early_page_table(__fix_to_virt(FIX_FDT), dtb_pa); // **early_pg_dir** 目录中，fixmap 虚拟空间中，建立 dtb 映射（**dtb_early_va -> dtb_pa**）
|- relocate_enable_mmu // 第一次用 **trampoline_pg_dir** ，触发异常后进入 CSR_TVEC 中配置的虚拟地址，然后再次切换到 **early_pg_dir**

setup_arch
|- paging_init
	 |- setup_bootmem(); // 保留内存到 memblock
		  |- kernel_map.**va_pa_offset** = PAGE_OFFSET - phys_ram_base; // physical addr = virtual addr - va_pa_offset = virtual addr - PAGE_OFFSET + phys_ram_base 
	 |- setup_vm_final
		  |- create_pgd_mapping(swapper_pg_dir, FIXADDR_START, __pa_symbol(fixmap_pgd_next), PGDIR_SIZE, PAGE_TABLE); // **swapper_pg_dir** 中为 fixmap 创建页表，没创建 pte，用于 early_ioremap
		  |- create_linear_mapping_page_table(); // **swapper_pg_dir** 中对所有没使用的内存和 kernel 进行到 PAGE_OFFSET 的线性映射
		  |- create_kernel_page_table(swapper_pg_dir, false); // **swapper_pg_dir** 中对kernel 到 kernel_mapping.virt_addr 的映射
			|- csr_write(CSR_SATP, PFN_DOWN(__pa_symbol(swapper_pg_dir)) | satp_mode); // 切换页表目录，使用 swapper_pg_dir 作为 init_mm.pgd（初始值就是 swapper_pg_dir）
```

# 进程相关

## 进程页表初始化流程

```c
// 进程创建                                  
run_init_process/do_execve/do_execveat -> kernel_execve/do_execveat_common ->  alloc_bprm  -> bprm_mm_init -> mm_alloc 
                                                                                                                      \									
                                                                                                                       \                                // arch 相关       // 拷贝 init_mm.pgd          // 拷贝内核页表
                                                                                                                      	 mm_init -> **mm_alloc_pgd(mm)** -> pgd_alloc(mm); -> sync_kernel_mappings(pgd); -> memcpy(pgd + USER_PTRS_PER_PGD, init_mm.pgd + USER_PTRS_PER_PGD,(PTRS_PER_PGD - USER_PTRS_PER_PGD) * sizeof(pgd_t));
                                                                                                                       /         -> init_new_context(p, mm) -> atomic_long_set(**&mm->context.id**, 0); // 初始化 mm->context.id 为 0
                                                                                                                      /                           // 拷贝用户态页表
kernel_thread/clone/clone3             -> kernel_clone                     -> copy_process -> copy_mm      -> dup_mm	-> dup_mmap(mm, oldmm); -> copy_page_range(tmp, mpnt); -> copy_p4d_range -> ... -> __copy_present_ptes -> wrprotect_ptes(src_mm, addr, src_pte, nr); // 配置父进程 pte 不可写
                                                                                                                                                                                                                             -> pte = pte_wrprotect(pte); // 配置子进程 pte 不可写
```

## asid 分配

### isa

最新的 isa 说明 asid 是 per cpu 私有的，后面可能会扩展 全局的asid

![Untitled](MMU/Untitled%2010.png)

但是旧的版本 建议软件共用 asid，而且现在最新的代码也是共用 asid 的，**后面可以提一下 patch** 

![Untitled](MMU/Untitled%2011.png)

### 代码流程

![Untitled](MMU/Untitled%2012.png)

```c
// 相关变量  
&per_cpu(active_context, cpu)  // 表示当前正在用的 asid
&per_cpu(reserved_context, cpu) // 更新 asid 版本时，保留的上一个正在用的asid

// 早期启动阶段，配置的
num_asids = 1 << asid_bits;
asid_mask = num_asids - 1;
atomic_long_set(&current_version, num_asids); // asid 的初始版本
context_asid_map = bitmap_zalloc(num_asids, GFP_KERNEL); // asid 的分配map

// 进程切换
__schedule
|- rq = context_switch(rq, prev, next, &rf);
   |- switch_mm_irqs_off(prev->active_mm, next->mm, next); // switch_mm
		  |- set_mm(prev, next, cpu);
				 |- set_mm_asid(next, cpu); // 配置 asid，asid 都是在轮到进程运行的时候，才开始初始化
						|- cntx = __new_context(mm); // **mm->context.id (1 << asid_bits | asid)** 没有被配置 asid，分配新的 asid
						|	 |- if (cntx != 0) // 已经分配过 asid 但是版本不匹配，才到这
						|	 |  |- unsigned long newcntx = ver | (cntx & asid_mask);
						|	 |	|- if (check_update_reserved_context(cntx, newcntx)) return newcntx; 
						|	 |	|	 |- if (per_cpu(**reserved_context**, cpu) == cntx) { hit = true; per_cpu(reserved_context, cpu) = newcntx;} // 如果 cntx 是更新 asid 版本时，**保留的上一个正在用的asid，则不用分配，已经占位了** 
						|	 |	|- if (!__test_and_set_bit(cntx & asid_mask, context_asid_map)) return newcntx; // 如果新版本asid，这个 asid 没被用，可以直接用
						|	 |	|- asid = find_next_zero_bit(context_asid_map, num_asids, cur_idx); // 查找没有用的asid
						|	 | 	|- ver = atomic_long_add_return_relaxed(num_asids, &current_version); // 如果 asid 用完了，更新版本，current_version = current_version + num_asids;
						|	 |	|- __flush_context(); // 去除原有的asid
						|	 |	|	 |- bitmap_zero(context_asid_map, num_asids); // 清空 context_asid_map
						|	 |	|	 |- for_each_possible_cpu(i) 
						|	 |	|	 |  |- cntx = atomic_long_xchg_relaxed(&per_cpu(active_context, i), 0); // old_active_context = active_context; active_context = 0; return old_active_context;
						|	 |	|	 |  |- __set_bit(cntx & asid_mask, context_asid_map);
						|	 |	|	 |  |- per_cpu(**reserved_context**, i) = cntx; // **保留上个版本的 active_context** 
						|	 |	|	 |- __set_bit(0, context_asid_map); // 保留 init_mm (kernel) 用的 asid
						|	 |	|	 |- cpumask_setall(&**context_tlb_flush_pending**); // 配置 context_tlb_flush_pending ，**需要刷新 tlb** 
						|	 |  |- asid = find_next_zero_bit(context_asid_map, num_asids, 1);
						|	 |  |- return asid | ver; // 返回 cntx
						|- if (cpumask_test_and_clear_cpu(cpu, &context_tlb_flush_pending)) need_flush_tlb = true; // **是否需要刷新 tlb** 
						|- atomic_long_set(&mm->context.id, cntx); // **mm->context.id** 填充 
						|- csr_write(CSR_SATP, virt_to_pfn(mm->pgd) | ((cntx & asid_mask) << SATP_ASID_SHIFT) | satp_mode); // 更新 stap
						|- if (need_flush_tlb) local_flush_tlb_all(); // **根据需要刷新 tlb，更新过 asid 版本才需要刷新，所以可以多个进程的 tlb 同时存在** 
							 |- __asm__ __volatile__ ("sfence.vma" : : : "memory"); // 刷掉所有的 tlb
```

## tlb 刷新

```c
change_pte_range/dup_mmap
flush_tlb_mm
|- __flush_tlb_range(mm_cpumask(mm), get_mm_asid(mm), 0, FLUSH_TLB_MAX_SIZE, PAGE_SIZE);
	 |- on_each_cpu_mask(cmask, __ipi_flush_tlb_range_asid, &ftd, 1); // 其他cpu，会通过 ipi 唤醒对应的cpu，让其执行
	 |  |- smp_call_function_many_cond(mask, func, info, scf_flags, cond_func);
	 |- local_flush_tlb_range_asid(start, size, stride, asid); // 当前cpu
		  |- local_flush_tlb_page_asid(start, asid);
			   |- __asm__ __volatile__ ("sfence.vma %0, %1" : : "r" (addr), "r" (asid) : "memory");
```

# Hugepage

`Documentation/admin-guide/mm/hugetlbpage.rst`

## 使用

```bash
mkdir /mnt/huge
mount none /mnt/huge -t hugetlbfs

# 配置可用的 hugepage 数量
echo 20 > /proc/sys/vm/nr_hugepages
| static ssize_t nr_hugepages_store(struct kobject *kobj,
| 	       struct kobj_attribute *attr, const char *buf, size_t len)
| {
| 	return nr_hugepages_store_common(false, kobj, buf, len);
| }
| HSTATE_ATTR(nr_hugepages);
```