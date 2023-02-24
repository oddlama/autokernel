#!/usr/bin/env bash

set -uo pipefail

BRIDGE_C="scripts/kconfig/autokernel_bridge.c"
BRIDGE_SO="scripts/kconfig/autokernel_bridge.so"

function die() { echo "[1;31merror[m: $*" >&2; exit 1; }
function build_bridge() {
	umask 022

	rm "$BRIDGE_SO" &>/dev/null
	sha256sum "$BRIDGE_C" > "$BRIDGE_C".sha256 \
		|| die "Could not compute sha256 of autokernel_bridge.c"

	o_files=()
	if grep -q gnu11 Makefile; then
		detected_std=gnu11
	else
		detected_std=gnu89
	fi
	if grep -q 'common-objs' scripts/kconfig/Makefile; then
		INPUTS=($(awk '/^common-objs.*:=/,/^$/' scripts/kconfig/Makefile | grep -P -o "\S+(?=\.o)"))
		INPUTS+=(autokernel_bridge)
	else
		INPUTS=(conf zconf.tab autokernel_bridge)
	fi
	if grep -q "set_message_callback.*va" scripts/kconfig/lkc_proto.h; then
		message_callback_type="const char*, va_list"
	else
		message_callback_type="const char*"
	fi
	for i in "${INPUTS[@]}"; do
		if [[ "$i" == autokernel_bridge ]]; then
			getenv_override="" \
			std="gnu11"
		else
			getenv_override="-Dgetenv=autokernel_getenv"
			std="$detected_std"
		fi

		o="scripts/kconfig/$i.autokernel.o"
		o_files+=("$o")
		gcc -O3 -fPIC -Wp,-MMD,scripts/kconfig/."$i".o.d \
			-Wall -fomit-frame-pointer \
			-std="$std" \
			$getenv_override \
			"-DMESSAGE_CALLBACK_TYPE=$message_callback_type" \
			-I ./scripts/kconfig -c -o "$o" scripts/kconfig/"$i".c \
			|| die "Failed to compile $i for autokernel bridge!"
	done

	gcc -O3 -Wall -fPIC -shared -o "$BRIDGE_SO" "${o_files[@]}" \
		|| die "Failed to link autokernel bridge!"
}

# Intercept execution of the conf script and instead run our bridge.
if [[ "$1" == "-c" && "$2" == "scripts/kconfig/conf "* ]]; then
	[[ "4.2" == "$(sort -V <<< "4.2"$'\n'"$KERNELVERSION" | head -n1)" ]] \
		|| die "Unsupported kernel version: Requires kernel version >=4.2 (but got $KERNELVERSION)"

	# (Re)build bridge if necessary (e.g. autokernel update on preexisting kernel source with old bridge)
	{ [[ -e "$BRIDGE_SO" ]] \
		&& diff -q <(sha256sum "$BRIDGE_C") "$BRIDGE_C".sha256 &>/dev/null
	} || build_bridge

	echo "[AUTOKERNEL BRIDGE]"
	python -c 'import os, json; print(json.dumps({k:v for k,v in os.environ.items()}))'
else
	exec /bin/bash "$@"
fi
