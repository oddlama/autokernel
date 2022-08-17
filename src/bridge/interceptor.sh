#!/bin/bash

set -uo pipefail

function die() { echo "error: $*" >&2; exit 1; }
function build_bridge() {
	umask 022

	sha256sum scripts/kconfig/autokernel_bridge.c > scripts/kconfig/autokernel_bridge.c.sha256 \
		|| die "Could not compute sha256 of autokernel_bridge.c"

	gcc -O3 -fsanitize=address \
		-Wp,-MMD,scripts/kconfig/.autokernel_bridge.o.d -Wall -Wstrict-prototypes \
		-fomit-frame-pointer -std=gnu11 -D_DEFAULT_SOURCE -D_XOPEN_SOURCE=600 \
		-c -o scripts/kconfig/autokernel_bridge.o scripts/kconfig/autokernel_bridge.c \
		|| die "Failed to compile autokernel bridge!"

	gcc -O3 -fsanitize=address \
		-o scripts/kconfig/autokernel_bridge \
		scripts/kconfig/autokernel_bridge.o \
		scripts/kconfig/confdata.o \
		scripts/kconfig/expr.o \
		scripts/kconfig/lexer.lex.o \
		scripts/kconfig/menu.o \
		scripts/kconfig/parser.tab.o \
		scripts/kconfig/preprocess.o \
		scripts/kconfig/symbol.o \
		scripts/kconfig/util.o \
		|| die "Failed to link autokernel bridge!"
}

# Intercept execution of the conf script and instead run our bridge.
if [[ "$1" == "-c" && "$2" == "scripts/kconfig/conf "* ]]; then
	# (Re)build bridge if necessary (e.g. autokernel update on preexisting kernel source with old bridge)
	{ [[ -e scripts/kconfig/autokernel_bridge ]] \
		&& diff -q <(sha256sum scripts/kconfig/autokernel_bridge.c) scripts/kconfig/autokernel_bridge.c.sha256 &>/dev/null
	} || build_bridge

	rm out.json # TODO
	echo "---- AUTOKERNEL BRIDGE BEGIN ----"
	# TODO exec scripts/kconfig/autokernel_bridge Kconfig
	scripts/kconfig/autokernel_bridge Kconfig | tee out.json
	python -m json.tool out.json > out_pretty.json
else
	exec /bin/bash "$@"
fi
