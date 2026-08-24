# 阶段 2：在线周期控制 pilot

该 pilot 在单个进程内运行多个控制周期。每个周期生成一组轮换的软件热度计数，计算六维特征，
按访问差阈值选择仍驻留在 CXL 的候选页，应用 `MAX_MIGRATIONS` 限制并迁移到 DRAM，随后
查询迁移后的页节点。这样先验证周期控制、限速和候选集合随窗口变化的行为。

运行：

```bash
./scripts/run_online_controller.sh
```

可通过环境变量调整：

```bash
MIB=64 CYCLES=5 THRESHOLD=20 MAX_MIGRATIONS=256 INTERVAL_MS=20 \
  ./scripts/run_online_controller.sh
```

当前热度仍是软件生成的计数，不是 DAMON/PEBS 透明采样；该限制不影响迁移控制器的周期和
限速验证，但不能作为论文真实热度复现结果。

64 MiB、阈值 20、每周期最多迁移 256 页、周期 20 ms 的首轮实验运行 5 个窗口。
每个窗口均识别 1638 个高差值页并按上限迁移 256 页，累计迁移 1280 页，迁移和驻留
复核错误为 0。完整控制路径（驻留查询、特征计算、候选筛选、迁移、复核）耗时将在每轮
JSON 的 `control_seconds` 中记录。
