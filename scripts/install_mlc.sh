#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
version=3.13
url=https://downloadmirror.intel.com/926327/mlc_v3.13.tgz
sha256=a8537e8ff3fad626d75a383fabc224ccc4cc98a0111c9989f7fb26b639f12019
archive="$root/third_party/mlc_v${version}.tgz"
install_dir="$root/third_party/intel-mlc"

if [[ "${MLC_LICENSE_ACCEPTED:-}" != yes ]]; then
    printf '%s\n' \
        'Intel requires acceptance of its software license before downloading MLC.' \
        'Review: https://www.intel.com/content/www/us/en/download/736633/intel-memory-latency-checker-intel-mlc.html' \
        'Then rerun with MLC_LICENSE_ACCEPTED=yes.' >&2
    exit 2
fi

mkdir -p "$root/third_party"
curl -fsSL --connect-timeout 15 --max-time 120 "$url" -o "$archive"
printf '%s  %s\n' "$sha256" "$archive" | sha256sum --check --status
mkdir -p "$install_dir"
tar -xzf "$archive" -C "$install_dir"
chmod +x "$install_dir/Linux/mlc"
"$install_dir/Linux/mlc" --help 2>&1 | sed -n '1,2p'
printf 'installed=%s\nversion=%s\nsha256=%s\n' \
    "$install_dir/Linux/mlc" "$version" "$sha256"

