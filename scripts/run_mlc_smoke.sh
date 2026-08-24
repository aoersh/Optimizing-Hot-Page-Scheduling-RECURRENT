#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mlc=${MLC_BIN:-"$root/third_party/intel-mlc/Linux/mlc"}
buffer_kib=${BUFFER_KIB:-65536}

if [[ ! -x "$mlc" ]]; then
    printf 'MLC not found: %s\nRun MLC_LICENSE_ACCEPTED=yes ./scripts/install_mlc.sh first.\n' "$mlc" >&2
    exit 2
fi

run_case() {
    local cpu=$1 node=$2 name=$3
    printf 'scenario=%s cpu=%s memory_node=%s\n' "$name" "$cpu" "$node"
    numactl --physcpubind="$cpu" "$mlc" --idle_latency -e -r \
        -c"$cpu" -j"$node" -b"$buffer_kib" -x1
}

run_case 0 0 socket0_local_dram
run_case 0 2 socket0_near_cxl
run_case 0 3 socket0_cross_socket_cxl
run_case 16 1 socket1_local_dram
run_case 16 3 socket1_near_cxl
run_case 16 2 socket1_cross_socket_cxl

