#!/bin/bash

set -uo pipefail

function die() { echo "[1;31merror[m: $*" >&2; exit 1; }

TMP="$(mktemp -d)"
[[ $TMP == /tmp* ]] || exit 1
trap 'rm -rf -- "$TMP"' EXIT

DOWNLOAD_TMP_DIR="/var/tmp/kernels"
mkdir -p "$DOWNLOAD_TMP_DIR" || die "mkdir"

KERNEL_VERSIONS=(
#	3.0 3.1 3.2 3.3 3.4 3.5 3.6 3.7 3.8 3.9 3.10 3.11 3.12 3.13 3.14 3.15 3.16 3.17 3.18 3.19
#	4.0 4.1 4.2 4.3 4.4 4.5 4.6 4.7 4.8 4.9 4.10 4.11 4.12 4.13 4.14 4.15 4.16 4.17 4.18 4.19 4.20
#	5.0 5.1 5.2 5.3 5.4 5.5 5.6 5.7 5.8 5.9 5.10 5.11 5.12 5.13 5.14 5.15 5.16 5.17 5.18 5.19
	6.0
)

CONFIG_PROVIDERS=(
	defaults
	defconfig
	debian
	arch
	nix
)

function download_kernel() {
	local kver="$1"
	local out="$DOWNLOAD_TMP_DIR/linux-${kver}.tar.xz"
	[[ ! -e "$out" ]] || return

	local major="${kver%%.*}"
	local url="https://cdn.kernel.org/pub/linux/kernel/v${major}.x/linux-${kver}.tar.xz"
	curl -L "$url" -o "$out" \
		|| die "Could not fetch $url"
}

function get_config_url() {
	local out="$1"
	local url="$2"
	local provider="$3"
	[[ ! -e "$out" ]] || return

	curl -L "$url" -o "$out" \
		|| die "Could not fetch $url"
}

function get_defaults_config() {
	# no-op (don't create out -> we get defaults)
	true
}

function get_defconfig_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	(cd "$kdir" && make defconfig) \
		|| die "make defconfig failed"
	cp "$kdir/.config" "$out"
}

function get_debian_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	die "not implemented: get_debian_config"
}

function get_arch_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	die "not implemented: get_arch_config"
}

function get_nix_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	die "not implemented: get_nix_config"
}

function get_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	local provider="$4"
	"get_${provider}_config" "$out" "$kdir" "$kver" \
		|| die "Could not fetch config for kver=$kver provider=$provider"
}

function unpack_kernel() {
	local kver="$1"
	local file="$DOWNLOAD_TMP_DIR/linux-${kver}.tar.xz"
	mkdir -p "$TMP/$kver" \
		|| die "Could not create directory $TMP/$kver"
	(cd "$TMP/$kver" && pv "$file" | tar xJ) \
		|| die "Could not extract $file"
}

function index_kernel() {
	local kdir="$1"
	local kver="$2"
	local provider="$3"

	local config="$DOWNLOAD_TMP_DIR/config-${kver}-${provider}"
	get_config "$config" "$kdir" "$kver" "$provider"

	local params=()
	[[ -e "$config" ]] && params+=(--kconf "$config")
	cargo run --features=index --bin autokernel-index -- \
		--kernel-dir "$kdir" analyze --name "$provider" "${params[@]}" \
		|| die "Failed to analyze kernel kdir=$kdir kver=$kver provider=$provider"
}

function delete_unpacked_kernel() {
	local kver="$1"
	rm -rf -- "${TMP:?}/$kver" \
		|| die "Could not remove $TMP/$kver"
}

function main() {
	echo "[32mAnalyzing[m ${#KERNEL_VERSIONS[@]} kernels with ${#CONFIG_PROVIDERS[@]} config providers"
	local kdir
	for kver in "${KERNEL_VERSIONS[@]}"; do
		echo "[33mKernel[m linux-$kver"
		download_kernel "$kver"

		unpack_kernel "$kver"
		kdir=$(echo "$TMP/$kver/"linux-*)
		for provider in "${CONFIG_PROVIDERS[@]}"; do
			echo "[34mProvider[m $provider"
			index_kernel "$kdir" "$kver" "$provider"
		done
		delete_unpacked_kernel "$kver"
	done
}

main
