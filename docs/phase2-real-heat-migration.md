# 阶段 2：真实 PEBS 热度驱动迁移闭环

## 验收范围

本阶段最终闭环为：共享工作集（CXL Node 2）-> PEBS 页级采样 -> Node 0/1 访问差特征
-> 候选页排序与限速 -> 跨进程 `move_pages()` -> 迁移后驻留复核。

运行入口：

```bash
MIB=4 DURATION=10 SAMPLE_SECONDS=3 SAMPLE_PERIOD=1000 \
  MIN_DELTA=2 MAX_MIGRATIONS=64 \
  ./scripts/run_real_heat_migration.sh /tmp/hotpage-perf-check/real-heat-migration-pilot
```

## Pilot 结果

- 工作集：4 MiB，1024 页，初始全部位于 CXL Node 2；
- PEBS 原始样本 7307，工作集内有效样本 7265，覆盖 975/1024 页；
- Node 0 和 Node 1 各选择 64 个高差页，共 128 页；
- Node 0 候选迁移到 DRAM Node 0：64/64 验证成功；
- Node 1 候选迁移到 DRAM Node 1：64/64 验证成功；
- 两次迁移的系统调用返回值、逐页状态和迁移后驻留查询均无错误；
- `ptrace_scope=1` 未阻止同一用户的跨进程 `move_pages()`。

结果文件包括 `pebs.data`、页热度 JSONL、六维特征 JSON 和迁移 JSON；原始文件仅保留在
`/tmp`，不进入 Git。

## 阶段 2 结论

真实 PEBS 热度已经能够驱动候选页选择和跨 NUMA 迁移，且迁移后驻留可逐页验证。阶段 2
的工程验收完成。阶段 3 仍需使用 W21/W23/W27、90:10/75:25 矩阵生成正式参数扫描数据；
当前 pilot 的 PEBS 计数和受控负载不作为论文最终训练标签。
