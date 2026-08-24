# Intel MLC 安装与验证

## 安装状态

- 官方版本：Intel Memory Latency Checker v3.13
- 官方下载编号：`736633`
- Linux 包：`mlc_v3.13.tgz`
- SHA-256：`a8537e8ff3fad626d75a383fabc224ccc4cc98a0111c9989f7fb26b639f12019`
- 本地路径：`third_party/intel-mlc/Linux/mlc`

Intel 要求下载前接受软件许可。审阅官方许可后，通过显式环境变量运行安装脚本：

```bash
MLC_LICENSE_ACCEPTED=yes ./scripts/install_mlc.sh
```

MLC 二进制、压缩包、许可证和 Intel 文档均不提交到本仓库。

## 非 root 运行方式

完整 MLC 默认会通过 MSR 修改硬件预取器状态，需要 root 和 `msr` 驱动。当前实验环境
无法获得该权限，因此使用官方支持的非 root 参数：

- `-e`：不修改硬件预取器；
- `-r`：随机访问，降低预取器对延迟结果的影响。

运行六种 DRAM/CXL 拓扑 smoke test：

```bash
./scripts/run_mlc_smoke.sh
```

首轮 CPU 0、64 MiB、100 万次随机依赖访问结果：Node 0 为 99.4 ns，近端 CXL
Node 2 为 312.0 ns，跨插槽 CXL Node 3 为 669.9 ns。结果层次与 NUMA distance 一致。

## 论文工作负载

v3.13 的帮助明确列出 `W21`、`W23`、`W27`，但三者仅能配合 `-o` per-thread
配置文件使用。下一步需要根据当前 CPU、DRAM/CXL 节点和工作集生成配置文件；不能简单地执行
`mlc -W21`。

