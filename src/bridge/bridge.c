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
char** autokernel_env = NULL;

#define DEBUG(...) do { if (autokernel_debug) { printf("[bridge] " __VA_ARGS__); } } while(0)

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

	DEBUG("Initializing environment\n");
	init_environment(env);
	DEBUG("Kernel version: %s\n", autokernel_getenv("KERNELVERSION"));
	DEBUG("Kernel directory: %s\n", autokernel_getenv("abs_objtree"));

	// Save current working directory
	char saved_working_directory[2048];
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
	for_all_symbols(i, sym) { ++n_symbols; }
	DEBUG("Found %ld symbols\n", n_symbols);
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
