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
接入其他负载时需要显式指定映射。

`analysis/summarize_page_heat.py` 可将 JSONL 汇总为六维特征。例如：

```bash
python3 analysis/summarize_page_heat.py \
  /tmp/hotpage-perf-check/pebs-coverage-x20/mlc-page-heat.jsonl \
  --threshold 20 --workset-pages 16385 \
  --output /tmp/hotpage-perf-check/pebs-coverage-x20/features.json
```

单 CPU 采样只反映采样 CPU 所在 NUMA 节点；未观测节点的计数按 0 处理，
`observed_nodes` 和 `page_coverage` 会随结果一并记录。下一步要在多线程、
跨节点工作负载中采样并在 MLC 存活期间查询驻留节点，验证跨进程迁移。

## 覆盖率 pilot

64 MiB 工作集包含 16385 个映射页。`ITERATIONS=20` 的一次采集得到 5076 个有效
PEBS 样本，覆盖 4356 页（26.59%），单页最大计数为 4。以参考阈值 2 汇总时，
`avg_n0=0.3098`、`avg_n1=0`、`high_delta_pages=653`；阈值 20 时没有候选页。

因此论文的软件计数阈值 10/20/30 不能原样用于当前 PEBS 采样计数。正式实验需固定
采样周期和窗口长度，再重新标定阈值；或者将页计数按总样本量归一化后使用新的阈值空间。
此外，MLC 单核 idle-latency 模式只有 Node 0 的访问来源，不能验证双节点访问差特征。
