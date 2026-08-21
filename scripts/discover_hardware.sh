#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-"$repo_root/results/environment"}
timestamp=$(date +%Y%m%d-%H%M%S)
text_report="$output_dir/$timestamp.txt"
json_report="$output_dir/$timestamp.json"

mkdir -p "$output_dir"

run_section() {
    local title=$1
    shift
    printf '\n## %s\n' "$title"
    "$@" 2>&1 || printf '[command failed: %s]\n' "$*"
}

{
    printf '# Environment snapshot\n'
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
    printf 'git_revision=%s\n' "$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || printf unknown)"
    run_section kernel uname -a
    run_section os_release cat /etc/os-release
    run_section cpu lscpu
    run_section numa numactl --hardware
    run_section memory free -h
    run_section pci_cxl bash -c "lspci -Dnn | rg -i 'CXL|0502'"
    run_section cxl_modules bash -c "lsmod | rg '^(cxl|dax|device_dax|kmem)'"
    run_section cxl_sysfs find /sys/bus/cxl/devices -maxdepth 1 -printf '%f -> %l\n'
    run_section dax_sysfs bash -c 'for d in /sys/bus/dax/devices/dax*; do printf "%s size=" "$(basename "$d")"; cat "$d/size"; printf "target_node="; cat "$d/target_node"; printf "driver="; basename "$(readlink -f "$d/driver")"; done'
    run_section node_meminfo bash -c 'for n in /sys/devices/system/node/node[0-9]*; do printf "[%s]\n" "$(basename "$n")"; cat "$n/cpulist" "$n/distance"; rg "MemTotal|MemFree|HugePages_Total" "$n/meminfo"; done'
    run_section pmu_devices bash -c "find /sys/bus/event_source/devices -maxdepth 1 -printf '%f\n' | rg -i 'cxl|imc'"
    run_section kernel_policy sysctl kernel.numa_balancing vm.zone_reclaim_mode kernel.perf_event_paranoid kernel.kptr_restrict
    run_section tools bash -c 'for tool in gcc make numactl perf cxl ndctl daxctl jq mlc; do if command -v "$tool" >/dev/null; then printf "%s=%s\n" "$tool" "$(command -v "$tool")"; else printf "%s=missing\n" "$tool"; fi; done'
} >"$text_report"

jq -n \
    --arg schema_version "1" \
    --arg timestamp "$(date --iso-8601=seconds)" \
    --arg hostname "$(hostname)" \
    --arg kernel "$(uname -r)" \
    --arg git_revision "$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || printf unknown)" \
    --arg text_report "$(basename "$text_report")" \
    --argjson numa_balancing "$(cat /proc/sys/kernel/numa_balancing)" \
    --argjson perf_event_paranoid "$(cat /proc/sys/kernel/perf_event_paranoid)" \
    '{schema_version: ($schema_version | tonumber), timestamp: $timestamp,
      hostname: $hostname, kernel: $kernel, git_revision: $git_revision,
      policies: {numa_balancing: $numa_balancing,
                 perf_event_paranoid: $perf_event_paranoid},
      text_report: $text_report}' >"$json_report"

printf '%s\n%s\n' "$text_report" "$json_report"

