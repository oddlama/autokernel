#!/bin/bash

set -uo pipefail

BRIDGE_C="scripts/kconfig/autokernel_bridge.c"
BRIDGE_SO="scripts/kconfig/autokernel_bridge.so"

function die() { echo "error: $*" >&2; exit 1; }
function build_bridge() {
	umask 022

	sha256sum "$BRIDGE_C" > "$BRIDGE_C".sha256 \
		|| die "Could not compute sha256 of autokernel_bridge.c"

	o_files=()
	for i in conf confdata expr menu preprocess symbol util lexer.lex parser.tab autokernel_bridge; do
		o="scripts/kconfig/$i.autokernel.o"
		o_files+=("$o")
		gcc -g -Og -fPIC -Wp,-MMD,scripts/kconfig/."$i".o.d \
			-Wall -Wmissing-prototypes -Wstrict-prototypes \
			-fomit-frame-pointer -std=gnu11 -Wdeclaration-after-statement \
			-I ./scripts/kconfig -c -o "$o" scripts/kconfig/"$i".c \
			|| die "Failed to compile $i for autokernel bridge!"
	done

	gcc -g -Og -Wall -fPIC -shared -o "$BRIDGE_SO" "${o_files[@]}" \
		|| die "Failed to link autokernel bridge!"
}

# Intercept execution of the conf script and instead run our bridge.
if [[ "$1" == "-c" && "$2" == "scripts/kconfig/conf "* ]]; then
	# (Re)build bridge if necessary (e.g. autokernel update on preexisting kernel source with old bridge)
	{ [[ -e "$BRIDGE_SO" ]] \
		&& diff -q <(sha256sum "$BRIDGE_C") "$BRIDGE_C".sha256 &>/dev/null
	} || build_bridge

	echo "[AUTOKERNEL BRIDGE]"
	python -c 'import os, json; print(json.dumps({k:v for k,v in os.environ.items()}))'
else
	exec /bin/bash "$@"
fi
