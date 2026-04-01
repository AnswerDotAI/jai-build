#!/usr/bin/env bash
set -euo pipefail

src_dir="${1:?Usage: build.sh <jai-source-dir>}"
src_dir="$(cd "$src_dir" && pwd -P)"
dist_dir="$(pwd -P)/dist"

: "${CXX:=g++-14}"

version_from_configure() {
  sed -n 's/^AC_INIT(\[jai\], \[\([^]]*\)\].*/\1/p' "$src_dir/configure.ac" | head -n1
}

if [[ -n "${JAI_RELEASE_TAG:-}" ]]; then
  version="${JAI_RELEASE_TAG#refs/tags/}"
  version="${version#v}"
else
  version="$(version_from_configure)"
  [[ -n "${GITHUB_SHA:-}" ]] && version+="+git.${GITHUB_SHA::7}"
fi

asset_base="jai-${version}-linux-amd64-glibc"
stage_dir="$(pwd -P)/.pkg/$asset_base"

rm -rf .pkg dist
mkdir -p "$stage_dir/bash-completion" "$dist_dir"

cd "$src_dir"
./autogen.sh
./configure \
  --prefix=/usr \
  CXX="$CXX" \
  CXXFLAGS="${CXXFLAGS:-} -O2 -pipe" \
  LDFLAGS="${LDFLAGS:-} -static-libstdc++ -static-libgcc -Wl,--as-needed"

make -j"$(nproc)"

./jai --version >/dev/null
./jai --print-defaults >/dev/null

install -m 0755 jai "$stage_dir/jai"
install -m 0644 jai.1 "$stage_dir/jai.1"
install -m 0644 jai.conf "$stage_dir/jai.conf"
install -m 0644 bash-completion/jai "$stage_dir/bash-completion/jai"
install -m 0644 README.md INSTALL COPYING "$stage_dir/"

cat > "$stage_dir/INSTALL-LINUX.txt" <<'EOF'
Recommended install commands:

  sudo install -D -o root -g root -m 4511 jai /usr/bin/jai
  sudo install -D -m 0644 jai.conf /usr/lib/sysusers.d/jai.conf
  sudo install -D -m 0644 jai.1 /usr/share/man/man1/jai.1
  sudo install -D -m 0644 bash-completion/jai /usr/share/bash-completion/completions/jai
  sudo systemd-sysusers /usr/lib/sysusers.d/jai.conf

Notes:
- libstdc++ and libgcc are linked statically; glibc remains dynamic.
- Alpine/musl is out of scope for this artifact.
EOF

{
  echo "Built on: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "Compiler: $($CXX --version | head -1)"
  echo
  echo "Dynamic NEEDED entries:"
  objdump -p ./jai | awk '/NEEDED/ { print "  " $2 }'
  echo
  echo "Highest referenced GLIBC symbol version:"
  readelf --version-info ./jai \
    | sed -n 's/.*Name: \(GLIBC_[0-9.]*\).*/\1/p' \
    | sort -Vu | tail -1 | sed 's/^/  /'
} > "$stage_dir/BUILD-INFO.txt"

strip "$stage_dir/jai" || true

cd "$(dirname "$stage_dir")"
tar -czf "$dist_dir/$asset_base.tar.gz" "$asset_base"

cd "$dist_dir"
sha256sum "$asset_base.tar.gz" > SHA256SUMS.txt

echo "Created $dist_dir/$asset_base.tar.gz"
