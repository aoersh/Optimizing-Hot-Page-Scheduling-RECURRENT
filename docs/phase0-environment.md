# 阶段 0：物理 CXL 环境验证

## 已确认的拓扑

服务器包含两个带 CPU 的 DRAM 节点和两个无 CPU 的 CXL 节点：

| CPU 位置 | DRAM | 近端 CXL | 跨插槽 CXL |
|---|---:|---:|---:|
| 插槽 0，CPU 0-15 | Node 0 | Node 2，距离 14 | Node 3，距离 24 |
| 插槽 1，CPU 16-31 | Node 1 | Node 3，距离 14 | Node 2，距离 24 |

Node 2 和 Node 3 是各 64 GiB、绑定到 `kmem` 驱动的 DAX 设备。权威的机器可读拓扑映射位于
`configs/server-topology.json`。

## 执行检查

在仓库根目录执行完整的、非破坏性的阶段 0 检查：

```bash
./scripts/run_phase0.sh
```

脚本会编译探针，在 `results/environment/` 下写入带时间戳的环境快照，随后在自身进程中为两组近端
CXL 节点分配并迁移 16 MiB 内存。它不会修改 sysctl、CPU 频率、内存在线状态或系统范围的
NUMA 策略。

直接测试其中一组节点：

```bash
make -C benchmarks
numactl --physcpubind=0 ./benchmarks/numa_probe --source 0 --target 2 --mib 16
```

每一行输出都是 JSON。成功运行时，`before` 阶段的所有页面应位于 `source_node`，`after` 阶段的
所有页面应位于 `target_node`。

## 已知限制

- 阶段 0 采集时 `PATH` 中没有 Intel MLC；随后已在仓库忽略目录安装 v3.13，详见
  `docs/mlc-installation.md`。
- `kernel.perf_event_paranoid=4` 阻止当前用户访问 CXL PMU 和 PEBS。
- DAMON sysfs 未在 `/sys/kernel/mm/damon/admin` 暴露。
- 已安装的 ndctl/cxl 用户态工具版本早于当前内核接口，无法完整解析 memdev 对象。因此，阶段 0
  以 sysfs、PCI、DAX 和 NUMA 映射作为事实依据。

下一步需要特权时，在获得批准后仅向实验进程授予最低限度的性能监控能力，然后重新测试 PMU/DAMON
访问。
