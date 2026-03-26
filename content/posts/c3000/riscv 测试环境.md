+++
title = "riscv 测试环境"
date = 2026-03-26T19:22:22.782154+08:00
tags = ["riscv", "linux"]
categories = ["riscv_linux"]
+++
# riscv 测试环境

# 1. 构建 riscv 架构运行的 qemu

基于 riscv 的 ubuntu rootfs，编译 qemu，riscv 的 rootfs构建方式如下：

‣ 

```bash
# 1. 进入 riscv rootfs
sudo chroot your_riscv_ubuntu_rootfs /bin/bash

# 2. 安装编译 qemu 的必要库
apt install python3-pip ninja-build build-essential autoconf automake libtool pkg-config libblkid-dev gettext bison flex 

# 3. 安装静态编译 qemu 的 libmount.a
apt source util-linux
cd ./build-mount/util-linux-2.39.3
./configure --prefix=/usr/local --enable-static --disable-shared --disable-all-programs --enable-libmount --enable-libblkid --with-pic CFLAGS="-fvisibility=hidden"
make -j8
make install

# 4. 编译 qemu
cd qemu_dir
sed -i "s/imply\ TEST_DEVICES/imply\ TEST_DEVICES\n\ \ \ \ imply\ IOMMUFD/g" ./hw/riscv/Kconfig # virt 机器添加 iommufd 的支持
grep -rl "crc32c(" . | xargs sed -i 's/crc32c(/qemu_crc32c(/g'mkdir build # 防止 qemu 中定义的 crc32c 函数和 libblkid 中定义的 crc32 函数重复定义 
cd build
KERNEL_HDR_PATH=/home/jinglin/lrzx_workspace/linux-next/initfs/linux_header ../configure --target-list=riscv64-softmmu --enable-kvm --enable-iommufd --static --prefix=/opt/
make -j8
make install
```

# 2. 测试

## 2.1 修改内核

[0001-riscv-iommu-support-vfio-to-riscv.patch](0001-riscv-iommu-support-vfio-to-riscv.patch)

## 2.2 配置内核

```bash
# 1. 配置 kvm
CONFIG_KVM=m

# 2. 配置 iommu
CONFIG_IOMMU_SUPPORT=y
CONFIG_RISCV_IOMMU=y
CONFIG_RISCV_IOMMU_PCI=y

# 3. 配置 vfio
CONFIG_VFIO=y
CONFIG_VFIO_PCI=y # vfio-pci 设备驱动
CONFIG_KVM_VFIO=y # 目前 riscv 没有支持，需要修改代码

# 3. 配置 iommufd，通过用户态接口控制 vfio
CONFIG_IOMMUFD=y
CONFIG_VFIO_DEVICE_CDEV=y # 用于 iommufd
CONFIG_VFIO_NOIOMMU=y

# 4. 配置旧版 vfio 接口
CONFIG_VFIO_CONTAINER=y   # 用于 IOMMU type1，目前 riscv 没有支持，需要修改代码
CONFIG_VFIO_IOMMU_TYPE1=y
```

## 2.3 安装驱动

```bash
# 挂载文件系统
sudo mount -t ext2 ./your_rootfs.img /tmp

# 安装头文件 和 驱动
sudo make INSTALL_MOD_PATH=/tmp modules_install
sudo make INSTALL_HDR_PATH=/tmp/usr headers_install
```

## 2.4 测试 kvm

### 2.4.1 启动 host

```bash
# qemu 启动带 H 扩展的 cpu，virt 的cpu 默认带 H 扩展，或者显性使用 h=true
qemu-system-riscv64 -nographic -M virt,aia=aplic-imsic,aia-guests=4 -cpu rv64,h=true -m 2G \
        -device riscv-iommu-pci,addr=01.0,intremap=on \
        -device pcie-root-port,id=rp1,bus=pcie.0,chassis=1,slot=1,addr=02.0 \
        -device e1000e,netdev=net0,bus=rp1,addr=00.0,mac=52:54:00:12:34:56 \
        -netdev user,id=net0 \
        -kernel arch/riscv/boot/Image -append "root=/dev/vda rw console=ttyS0" \
        -drive if=none,file=./initramfs.cpio.test,format=raw,id=hd0 \
        -device virtio-blk-device,drive=hd0 \
        -monitor telnet:localhost:5678,server,nowait
```

### 2.4.2 启动 guest

```bash
# 1. 安装 kvm.ko
insmod /lib/modules/6.19.0-rc1-dirty/kernel/arch/riscv/kvm/kvm.ko

# 2. 启动虚拟机
/opt/bin/qemu-system-riscv64 -nographic -M virt -m 1G -accel kvm \
        -monitor telnet:localhost:5678,server,nowait \
        -kernel ./Image -initrd ./initramfs_24M.cpio \
        -append "root=/dev/ram0 console=ttyS0"
```

## 2.5 测试 iommu

`说明文档：linux/Documentation/driver-api/vfio.rst` 

        `qemu/docs/specs/riscv-iommu.rst,支持 iommu-sys 和 iommu-pci 两种模式` 

        `qemu/docs/devel/vfio-iommufd.rst`

### 2.5.1 启动 host

```bash
# qemu 启动带 H 扩展的 cpu，virt 的cpu 默认带 H 扩展，或者显性使用 h=true
# 可以使用命令行 iommu.passthrough=0 riscv_iommu.force_isolation=1 强制开启 mmu
# iommu.passthrough=0：禁用物理透传，强制启用 DMA 地址转换。
# riscv_iommu.force_isolation=1：强制为每个设备创建独立的 IOMMU 域, 这是 amd 的参数
# iommufd.allow_unsafe_interrupts=1 vfio_iommu_type1.allow_unsafe_interrupts=1 riscv vfio 支持不完善，需要强制允许 不安全中断
qemu-system-riscv64 -nographic -M virt,aia=aplic-imsic,aia-guests=4,iommu-sys=on
				-cpu rv64,h=true -m 2G \
        -device e1000e,netdev=net0,mac=52:54:00:12:34:56 \
        -netdev user,id=net0,net=10.0.2.0/24,dhcpstart=10.0.2.11 \
        -kernel arch/riscv/boot/Image -append "root=/dev/vda rw console=ttyS0 iommufd.allow_unsafe_interrupts=1 vfio_iommu_type1.allow_unsafe_interrupts=1" \
        -drive if=none,file=./initramfs.cpio.test,format=raw,id=hd0 \
        -device virtio-blk-device,drive=hd0 \
        -monitor telnet:localhost:5678,server,nowait
        
# 查看有没有成功注册 iommu
dmesg | grep -i iommu
[    0.335548][    T1] iommu: Default domain type: Translated
[    0.335614][    T1] iommu: DMA domain TLB invalidation policy: strict mode
[    2.154343][   T42] riscv,iommu 3010000.iommu: using MSIs
[    2.288427][   T42] pci 0000:00:00.0: Adding to iommu group 0
[    2.289751][   T42] pci 0000:00:01.0: Adding to iommu group 1

# 检测设备由 iommu 隔离，目录存在表示，设备挂在 iommu 的隔离组上
ls /sys/bus/pci/devices/0000\:00\:01.0/iommu_group/
# iommu_group/devices/ 可以查看同一个 group 下的所有设备
```

### 2.5.2 启动 guest

```bash
# 1. 安装 kvm.ko
insmod /lib/modules/6.19.0-rc1-dirty/kernel/arch/riscv/kvm/kvm.ko
# 1.1 启动网卡
# dhclient eth0
udhcpc -i eth0

# 2. 查看 e1000e 的，pci 设备号，可见设备号为 0000:00:01.0
# lspci -k
dmesg | grep -i e1000e
[    1.285484][    T1] e1000e: Intel(R) PRO/1000 Network Driver
[    1.285530][    T1] e1000e: Copyright(c) 1999 - 2015 Intel Corporation.
[    2.358821][   T42] e1000e 0000:00:01.0: enabling device (0000 -> 0002)
[    2.390194][   T42] e1000e 0000:00:01.0: Interrupt Throttling Rate (ints/sec) set to dynamic conservative mode
[    2.579401][   T42] e1000e 0000:00:01.0 eth0: (PCI Express:2.5GT/s:Width x1) 52:54:00:12:34:56
[    2.580600][   T42] e1000e 0000:00:01.0 eth0: Intel(R) PRO/1000 Network Connection
[    2.581626][   T42] e1000e 0000:00:01.0 eth0: MAC: 3, PHY: 8, PBA No: 000000-000

# 3. 查看 e1000e 的 Vendor ID 和 Device ID
cat /sys/bus/pci/devices/0000\:00\:01.0/vendor 
0x8086
cat /sys/bus/pci/devices/0000\:00\:01.0/device 
0x10d3

# 4. 绑定 e1000e 到 vfio-pci
# 4.1 解除内核的 pci 驱动
echo "0000:00:01.0" > /sys/bus/pci/devices/0000\:00\:01.0/driver/unbind 
[145416.412840] e1000e 0000:00:01.0 eth0: NIC Link is Down
# 4.2 添加 e1000e 由 vfio-pci 管理
echo "8086 10d3" > /sys/bus/pci/drivers/vfio-pci/new_id

# 5. 查看 e1000e 设备是否绑定成功
lspci -k
00:01.0 Class 0200: 8086:10d3 vfio-pci
00:00.0 Class 0600: 1b36:0008

# 2. 启动虚拟机, 00:01.0 为 pci 的 id
# 使用 iommufd 驱动 vfio: -object iommufd,id=iommufd0 -device vfio-pci,host=00:01.0,iommufd=iommufd0
/opt/bin/qemu-system-riscv64 -nographic -M virt,aia=aplic-imsic -m 1G -accel kvm \
				-device vfio-pci,host=00:01.0 \
        -monitor telnet:localhost:5678,server,nowait \
        -kernel ./Image -initrd ./initramfs_24M.cpio \
        -append "root=/dev/ram0 console=ttyS0
```