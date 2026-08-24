# 阶段 2：静态阈值控制器 pilot

由于当前服务器没有可用的 DAMON/PEBS 权限，本实验暂时用软件访问计数器模拟采样源：
10% 页面被赋予差值为 15、25、35 的三档 CPU 节点访问计数，其余页面保持均衡访问计数。控制器计算论文
六维特征，使用阈值 10、20、30 选择候选页，并通过 `move_pages()` 将候选页迁移到
CPU 所在的 DRAM 节点。

运行：

```bash
./scripts/run_static_controller.sh
```

该 pilot 的目标是跑通“特征计算 -> 静态阈值 -> 候选页 -> 批量迁移 -> 驻留验证”。
软件计数器不是透明的真实访问采样，结果只用于验证接口和控制逻辑，不作为论文最终热度数据。

64 MiB 工作集的首轮结果：

| 阈值 | 高差值/候选页 | Node 2 -> 0 | Node 3 -> 1 | 迁移错误 |
|---:|---:|---:|---:|---:|
| 10 | 1638 | 3.34 ms | 3.31 ms | 0 |
| 20 | 1092 | 1.83 ms | 1.91 ms | 0 |
| 30 | 546 | 0.93 ms | 0.94 ms | 0 |

每轮输出完整的 `total_pages`、`avg_n0`、`avg_n1`、`max_delta`、
`high_delta_pages`、`imbalance_ratio` 六维特征。三个阈值产生严格递减的候选集合，
且迁移后驻留页数与候选页数完全一致。

 目前没有DAMON/PEBS 权限？这会导致什么问题，有什么解决方案


■ unexpected status 503 Service Unavailable: Service temporarily unavailable (request id: 202608211000595328659618268d9d6qSjojOjw), url:
https://www.cctq.ai/v1/responses, cf-ray: a2e8cb357c942a86-LAX


› 目前没有DAMON/PEBS 权限？这会导致什么问题，有什么解决方案


• 是的，目前有两类限制，但性质不同：

  ## 1. DAMON：不是单纯权限问题

  当前未发现：

  /sys/kernel/mm/damon/admin

  这通常意味着：

  - 当前内核没有启用 DAMON 管理接口；
  - 或 Ubuntu 内核没有暴露该接口；
  - 或相关 tracefs/sysfs 接口受限。

  DAMON 主要用于观察进程内存区域的访问频率和变化趋势。

  ## 2. PEBS/perf：明确受到权限限制

  当前：

  kernel.perf_event_paranoid = 4

  因此普通用户不能使用许多硬件性能事件，包括：

  - PEBS 内存访问采样；
  - perf mem；
  - CXL PMU；
  - 部分 uncore/内存控制器计数器。

  我们已经确认 CXL PMU 设备存在，但当前用户无法读取。

  ## 对实验的影响

  论文的动态调度需要知道哪些页是热页。目前我们无法透明地获得真实逐页访问次数，因此：

  - avg_n0、avg_n1 不能直接使用真实硬件访问计数；
  - max_delta 和 high_delta_pages 只能使用近似值；
  - 不能严格复现论文的热页特征提取过程；
  - MLP 训练标签可能基于错误或不完整的热度数据；
  - 动态迁移结果可能退化为“预设热页迁移”，而不是真正的自适应调度。

  当前的 static_controller_bench 使用软件计数器，是为了先验证：

  特征计算 -> 阈值选择 -> 页面迁移 -> 驻留验证

  它能验证控制逻辑，但不能证明真实工作负载下热页识别正确。

  ## 推荐解决方案

  ### 方案一：申请最小性能监控权限

  优先推荐为实验用户或采样程序授予：

  CAP_PERFMON

  然后重新测试：

  perf stat -e cxl_pmu_mem0.0/clock_ticks/ -- true
  perf mem record ...

  这比直接使用 root 更符合最小权限原则。

  也可以临时调整：

  sudo sysctl -w kernel.perf_event_paranoid=2

  必要时再降低，但必须：

  - 记录原始值；
  - 实验前后恢复；
  - 不让脚本自动修改全局设置；
  - 在实验 manifest 中记录权限状态。

  ### 方案二：启用或升级 DAMON

  先检查内核配置：

  grep DAMON /boot/config-$(uname -r)

  如果内核支持但接口未出现，可以尝试：

  - 安装带完整 DAMON 支持的内核；
  - 加载相关模块；
  - 安装 damo 工具；
  - 检查 tracefs/sysfs 挂载和权限。

  如果当前 Ubuntu 内核没有完整支持，则需要升级内核或重新编译内核。该方案会改变实验环境，需要重新验证 CXL 驱动和 NUMA 拓扑。

  ### 方案三：实现 accessed-bit 采样

  如果无法获得 DAMON 或 PEBS，推荐实现 PTE accessed-bit 采样：

  1. 定期检查页面 accessed bit；
  2. 读取并清除标志；
  3. 在时间窗口内累计每页访问次数；
  4. 计算六个特征；
  5. 将热页交给 move_pages()。

  优点：

  - 不依赖 CXL PMU；
  - 可以得到页级热度；
  - 更适合透明监控 MLC。

  缺点：

  - 需要内核接口或内核模块；
  - 清除 accessed bit 有额外开销；
  - THP、大页和并发访问会增加实现复杂度。

  ### 方案四：对自研工作负载做软件插桩

  对于我们自己的 W21/W23/W27 近似程序，可以在每次访问时记录页号和访问类型。

  优点：

  - 热度计数准确；
  - 不需要 DAMON、PEBS 或额外权限；
  - 适合先训练 MLP 和验证控制器。

  缺点：

  - 不能透明监控 Intel MLC；
  - 插桩会改变工作负载性能；
  - 只能作为工程验证或训练数据来源。

  ### 方案五：只使用 NUMA 驻留信息

  可以继续使用：

  - /proc/<pid>/numa_maps
  - move_pages()
  - /proc/vmstat
  - 页面迁移统计

  但这些信息主要回答“页面在哪个节点”，不能回答“页面被访问了多少次”。因此适合：

  - 验证页面迁移；
  - 记录页面驻留；
  - 统计迁移成功率；

  不适合直接替代论文中的访问热度采样。

  ## 实际建议

  建议按这个顺序推进：

  1. 先保留当前软件计数器，完成 MLP 输入、静态控制和迁移闭环；
  2. 同时申请 CAP_PERFMON，测试 PEBS 和 CXL PMU；
  3. 检查内核 DAMON 支持；
  4. 如果两者都不可用，实现 accessed-bit 采样；
  5. 获取真实热度后，再生成正式训练集和论文对照结果。

  当前结论是：

  > 没有 DAMON/PEBS 不会阻止页面分配和迁移实验，但会阻止严格意义上的真实热页识别和论文级动态 MLP 复现。工程闭环可以继续，正式热度数据和最终模型训练需要补上真实采样机
  > 制。
 
