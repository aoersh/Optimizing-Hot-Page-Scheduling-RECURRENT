# PEBS 真实页面热度 pilot

## 采集

当前 `kernel.perf_event_paranoid=0` 已允许 PEBS load 采样。运行：

```bash
CPU=0 NODE=2 ./scripts/record_mlc_pebs.sh
```

脚本使用 MLC v3.13 的 64 MiB 随机 idle latency 工作负载，记录：

- `cpu/mem-loads,ldlat=30/P`；
- 数据地址（`-d`）；
- 采样 CPU（`--sample-cpu`）；
- MLC PID 的地址空间过滤；
- 从 `perf.data` 的 mmap 事件中自动选择 MLC 最大的匿名映射（64 MiB 工作集）；
- 4 KiB 页级访问次数和 CPU NUMA 节点。

输出 JSONL 每行对应一个数据页：

```json
{"accesses_by_node": {"0": 12}, "page": "0xb0000000", "samples": 12}
```

## 当前限制

这是统计采样，不是每次访问的完整 trace；默认采样周期约 4000 个事件。页面过滤不依赖
进程结束后的 `/proc/PID/maps`，但“最大匿名映射即工作集”是针对当前 MLC 模式的假设，后续
接入其他负载时需要显式指定映射。下一步要在 MLC 存活期间查询这些页面的驻留节点，生成
`avg_n0`/`avg_n1` 等六维特征，并验证对 MLC 页面进行跨进程迁移。
