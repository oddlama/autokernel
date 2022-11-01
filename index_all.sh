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

function major_minor() {
	local ver="${1%"="*}"
	ver="${ver%%"-"*}"
	local major="${ver%%.*}"
	local minor="${ver#*.}"
	minor="${minor%%.*}"
	echo "$major.$minor"
}

declare -A DEBIAN_TAGS
function load_debian_tags() {
	echo "[32mLoading[m debian config metadata"
	local raw_debian_tags
	raw_debian_tags=$(git ls-remote --tags https://salsa.debian.org/kernel-team/linux.git \
		| grep 'refs/tags/debian/[0-9]\+\.[0-9]\+\(\.[0-9]\+\)\?-[0-9]\+\^{}$' \
		| sed -e 's/\([a-f0-9]*\).*refs.tags.debian.\(.*\)\^{}/\2=\1/' \
		| sort -V) \
		|| die "Could not fetch debian kernel config tags"

	local ARRAY
	readarray -t ARRAY <<< "$raw_debian_tags" || return 1
	for i in "${ARRAY[@]}"; do
		local commit="${i##*"="}"
		local mm
		mm=$(major_minor "$i") || die "mm"
		DEBIAN_TAGS["$mm"]="$commit"
	done
}

function download_kernel() {
	local kver="$1"
	local out="$DOWNLOAD_TMP_DIR/linux-${kver}.tar.xz"
	[[ ! -e "$out" ]] || return

	local major="${kver%%.*}"
	local url="https://cdn.kernel.org/pub/linux/kernel/v${major}.x/linux-${kver}.tar.xz"
	curl -L "$url" -o "$out" \
		|| die "Could not fetch $url"
}

function download_config() {
	local out="$1"
	local url="$2"
	[[ ! -e "$out" ]] || return 0

	echo "[32mDownloading[m $url"
	curl -L "$url" -o "$out" \
		|| die "Could not fetch $url"
}

function get_defaults_config() {
	# no-op (don't create outfile -> defaults are used)
	true
}

function get_defconfig_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	rm "$kdir/.config" &>/dev/null
	(cd "$kdir" && make defconfig >/dev/null) \
		|| die "make defconfig failed"
	cp "$kdir/.config" "$out"
}

function get_debian_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	local mm
	mm=$(major_minor "$kver") || die "mm"

	[[ -v "DEBIAN_TAGS[$mm]" ]] || return 2
	local url="https://salsa.debian.org/kernel-team/linux/-/raw/${DEBIAN_TAGS[$mm]}/debian/config/config?inline=false"
	download_config "$out" "$url" \
		|| die "Could not download $url"
}

ARCH_COMMITS=(
	["4.18"]=3c50e4f43d575714980505f41bf82f7ec2156776
	["4.19"]=38db1d25f1f21e2a3ff989602bfddde777f0d258
	["4.20"]=30025f12df0c0fe8a8b38f19c2703c1184d2e6c8
	["5.0"]=f08c4c99a415d351d1278c87353118618cdd9398
	["5.1"]=4ad50977f91633c9f76ba0e235ea0f2416919e03
	["5.2"]=86e7329f57e68db6e0aa0e35d72de2e01934fc64
	["5.3"]=b3f2036697aa3d4c18fb2b8f199eb2e553439640
	["5.4"]=b2ed2627c32e5e701eb946cbc8d94788eea68c77
	["5.5"]=0c02ea8a83252bc5a96c67d6eaad437743fec67f
	["5.6"]=6e594f9a3ef6235980b57f2b2b1dabfa9901fc1b
	["5.7"]=0a5f6d8d54e8427be5f4f58ee82a9054ac66d217
	["5.8"]=66bc562dd8be4139bb3bcbd160732d29424f42ce
	["5.9"]=f28b69a517f6e7c6f0fda82a615b431d6a4201b6
	["5.10"]=8d616f398077da888b1cb301de8680559a0ffed0
	["5.11"]=360c9b9247afe5406c33b9b49f6274186b9dc04c
	["5.12"]=5510ef53e5a6b440e7e3c5b42cc92e4c90e13dd3
	["5.13"]=7fce66ef7b29bb71ae15c6b95b8151c5f7f9c05c
	["5.14"]=06ba009871eda45912956419669bcfdf50e51663
	["5.15"]=2140822d84313e9aa634c0022907f5e2fe6eb2df
	["5.16"]=ed2a6db8bed0fbe827379540ad90787e8c821de3
	["5.17"]=4d83339db0b7eae05853293e6e9184444d5e8e41
	["5.18"]=f48f90461259703c5b2e0e68991b27820622af0c
	["5.19"]=fb4814741911e77738f31f1d3a11623af3c6a0d1
	["6.0"]=1d265e30a6301ac159c3bc60ae24f2180f76473f
)
function get_arch_config() {
	local out="$1"
	local kdir="$2"
	local kver="$3"
	local mm
	mm=$(major_minor "$kver") || die "mm"

	[[ -v "DEBIAN_TAGS[$mm]" ]] || return 2
	local url="${ARCH_TAGS[$mm]}"
	download_config "$out" "$url" \
		|| die "Could not download $url"
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

	# Return 0 -> OK
	# Return 1 -> ERR
	# Return 2 -> NO ASSOCIATED CONFIG
	# Return _ -> OTHER ERR
	"get_${provider}_config" "$out" "$kdir" "$kver"
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
	local ret="$?"
	if [[ "$ret" -eq 0 ]]; then
		true
	elif [[ "$ret" -eq 2 ]]; then
		echo "[31mNo config[m can be provided for this kernel version"
		return
	else
		die "Error while fetching config for kver=$kver provider=$provider"
	fi

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


load_debian_tags
main
