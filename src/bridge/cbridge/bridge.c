#include <unistd.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <sys/time.h>
#include <stdint.h>

#include "lkc.h"
#include <ctype.h>

bool autokernel_debug = true;
extern struct symbol symbol_yes, symbol_no, symbol_mod;
size_t n_symbols = 0;
size_t n_unknown_symbols = 0;
char** autokernel_env = NULL;

#define DEBUG(...) do { if (autokernel_debug) { printf("[bridge] " __VA_ARGS__); } } while(0)

static void dev_null_message_callback(const char* s) {}

/**
 * The compilation script redirects calls to getenv() inside
 * the kernel .c files to this function, which allow us to use
 * different environment variables for each bridge.
 */
char* autokernel_getenv(const char* name) {
	for (char** e = autokernel_env; *e; ++e) {
		size_t len_name = strlen(name);
		if (strncmp(name, *e, len_name) == 0 && (*e)[len_name] == '=') {
			return (*e) + (len_name + 1);
		}
	}
	return NULL;
}

/**
 * Copies the given environment so nothing can interfere with it.
 */
void init_environment(char const* const* env) {
	int i = 0;
	size_t count = 0;
	for (char const* const* e = env; *e; ++e) {
		++count;
	}
	autokernel_env = malloc(sizeof(char*) * (count + 1));
	autokernel_env[count] = NULL;
	for (char const* const* e = env; *e; ++e) {
		// Yes we theoretically leak this, but we need it anyway until shutdown.
		autokernel_env[i++] = strdup(*e);
	}
}

/**
 * Initializes the bridge:
 * 1. Replaces the environment with a local duplicate
 * 2. Loads and parses the kconfig file.
 * 3. Counts the amount of loaded symbols.
 */
void init(char const* const* env) {
	struct timeval start, now;
	struct symbol* sym;
	int i;
	char saved_working_directory[2048];

	// Never let the kconfig parser print any messages
	conf_set_message_callback(dev_null_message_callback);

	DEBUG("Initializing environment\n");
	init_environment(env);
	DEBUG("Kernel version: %s\n", autokernel_getenv("KERNELVERSION"));
	DEBUG("Kernel directory: %s\n", autokernel_getenv("abs_objtree"));

	// Save current working directory
	getcwd(saved_working_directory, 2048);

	// Parse Kconfig and load empty .config (/dev/null)
	gettimeofday(&start, NULL);
	if (chdir(autokernel_getenv("abs_objtree")) != 0) {
		perror("Failed to change directory");
	}
	conf_parse("Kconfig");
	if (conf_read("/dev/null") != 0) {
		dprintf(2, "Failed to read /dev/null as dummy config\n");
	}
	if (chdir(saved_working_directory) != 0) {
		perror("Failed to change back to original directory");
	}

	gettimeofday(&now, NULL);
	DEBUG("Parsed Kconfig in %.4fs\n", (double)(now.tv_usec - start.tv_usec) / 1000000 + (double)(now.tv_sec - start.tv_sec));
	start = now;

	// Pre-count symbols: Three static symbols plus all parsed symbols
	n_symbols = 3;
	n_unknown_symbols = 0;
	for_all_symbols(i, sym) {
		++n_symbols;
		if (sym->type == S_UNKNOWN) {
			++n_unknown_symbols;
		}
	}
	DEBUG("Found %ld symbols (+%ld unknown symbols)\n", n_symbols - n_unknown_symbols, n_unknown_symbols);
}

/**
 * Returns the count of all known symbols.
 */
size_t symbol_count() {
	return n_symbols;
}

/**
 * Returns a list of all known symbols.
 */
void get_all_symbols(struct symbol** out) {
	struct symbol* sym;
	int i;

	struct symbol** next = out;
	*(next++) = &symbol_yes;
	*(next++) = &symbol_no;
	*(next++) = &symbol_mod;
	for_all_symbols(i, sym) {
		*(next++) = sym;
	}
}

/**
 * Returns the minimum value for an int/hex symbol
 */
uint64_t sym_int_get_min(struct symbol* sym) {
	struct property* prop;
	switch (sym->type) {
		case S_INT:
			prop = sym_get_range_prop(sym);
			if (!prop)
				return 0;
			return strtoll(prop->expr->left.sym->curr.val, NULL, 10);
		case S_HEX:
			prop = sym_get_range_prop(sym);
			if (!prop)
				return 0;
			return strtoll(prop->expr->left.sym->curr.val, NULL, 16);
		default:
			return 0;
	}
}

/**
 * Returns the maximum value for an int/hex symbol
 */
uint64_t sym_int_get_max(struct symbol* sym) {
	struct property* prop;
	switch (sym->type) {
		case S_INT:
			prop = sym_get_range_prop(sym);
			if (!prop)
				return 0;
			return strtoll(prop->expr->right.sym->curr.val, NULL, 10);
		case S_HEX:
			prop = sym_get_range_prop(sym);
			if (!prop)
				return 0;
			return strtoll(prop->expr->right.sym->curr.val, NULL, 16);
		default:
			return 0;
	}
}

/**
 * Returns a list of all choice value symbols assiocated with a choice.
 * If out == nullptr this just returns the number of associated symbols.
 */
size_t get_choice_symbols(struct symbol* sym, struct symbol** out) {
	struct property* prop;
	struct symbol* choice_sym;
	struct expr* e;
	size_t i = 0;

	if (!sym_is_choice(sym)) {
		return 0;
	}

	prop = sym_get_choice_prop(sym);
	if (out) {
		expr_list_for_each_sym(prop->expr, e, choice_sym) {
			out[i++] = choice_sym;
		}
	} else {
		expr_list_for_each_sym(prop->expr, e, choice_sym) {
			++i;
		}
	}

	return i;
}

struct expr* sym_direct_deps_with_prompts(struct symbol* sym) {
	struct property* prop;
	struct expr* e = NULL;
	for_all_prompts(sym, prop) {
		e = expr_alloc_or(e, expr_copy(prop->visible.expr));
	}
	return expr_eliminate_dups(expr_alloc_and(e, expr_copy(sym->dir_dep.expr)));
}

size_t sym_prompt_count(struct symbol* sym) {
	struct property* prop;
	size_t count = 0;
	for_all_prompts(sym, prop) {
		++count;
	}
	return count;
}
