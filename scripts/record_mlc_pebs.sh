#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-/tmp/hotpage-perf-check}
mkdir -p "$output_dir"
data="$output_dir/mlc-pebs.data"
samples="$output_dir/mlc-page-heat.jsonl"

mlc=${MLC_BIN:-"$root/third_party/intel-mlc/Linux/mlc"}
if [[ ! -x "$mlc" ]]; then
    printf 'MLC not found: %s\n' "$mlc" >&2
    exit 2
fi

set +e
perf record -d --sample-cpu -e 'cpu/mem-loads,ldlat=30/P' -o "$data" -- \
    numactl --physcpubind="${CPU:-0}" "$mlc" --idle_latency -e -r \
    -c"${CPU:-0}" -j"${NODE:-2}" -b"${BUFFER_KIB:-65536}" -x"${ITERATIONS:-1}"
status=$?
set -e
if [[ $status -ne 0 ]]; then
    printf 'perf/MLC returned %s\n' "$status" >&2
    exit "$status"
fi

# perf samples contain the MLC PID; select the PID that owns the sampled mlc image.
pid=$(perf script -i "$data" -F pid,comm,dso 2>/dev/null | awk '
    $1 == "mlc" {split($2,a,"/"); print a[1]; exit}
    $2 == "mlc" {split($1,a,"/"); print a[1]; exit}
')
if [[ -z "$pid" ]]; then
    # perf reports the short comm as the first token when pid fields are absent.
    pid=$(perf script -i "$data" -F pid,comm 2>/dev/null | awk '
        $1 == "mlc" {split($2,a,"/"); print a[1]; exit}
        $2 == "mlc" {split($1,a,"/"); print a[1]; exit}
    ')
fi
if [[ -z "$pid" ]]; then printf 'could not identify MLC PID in perf samples\n' >&2; exit 1; fi
# The process exits before parsing. The parser selects its largest anonymous
# mapping from mmap events embedded in perf.data, which is MLC's workload buffer.
python3 "$root/analysis/parse_perf_mem.py" "$data" --pid "$pid" --jsonl "$samples"
printf 'data=%s\nsamples=%s\npid=%s\n' "$data" "$samples" "$pid"
