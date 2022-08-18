#include <unistd.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <sys/time.h>
#include <stdint.h>

#include "lkc.h"
#include <ctype.h>

////////////////////////////////////////////////////////
// Base64 encoding

/**
 * This section is licensed as follows:
 *
 * Copyright (C) 2013 William Sherif
 *
 * This software is provided 'as-is', without any express or implied
 * warranty.  In no event will the authors be held liable for any damages
 * arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 *
 * 1. The origin of this software must not be misrepresented; you must not
 *    claim that you wrote the original software. If you use this software
 *    in a product, an acknowledgment in the product documentation would be
 *    appreciated but is not required.
 * 2. Altered source versions must be plainly marked as such, and must not be
 *    misrepresented as being the original software.
 * 3. This notice may not be removed or altered from any source distribution.
 *
 * https://github.com/superwills/NibbleAndAHalf
 *
 * Modified by autokernel.
 */

const static char* b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

// Converts binary data of length=len to base64 characters.
// Length of the resultant string is stored in flen
// (you must pass pointer flen).
char* base64(const void* binaryData, int len, int* flen) {
	const unsigned char* bin = (const unsigned char*)binaryData;
	char* res;

	int rc = 0;  // result counter
	int modulusLen = len % 3;
	int pad = ((modulusLen & 1) << 1) + ((modulusLen & 2) >> 1);  // 2 gives 1 and 1 gives 2, but 0 gives 0.

	*flen = 4 * (len + pad) / 3;
	res = (char*)malloc(*flen + 1);  // and one for the null
	if (!res) {
		return NULL;
	}

	int byteNo;
	for (byteNo = 0; byteNo <= len - 3; byteNo += 3) {
		unsigned char BYTE0 = bin[byteNo];
		unsigned char BYTE1 = bin[byteNo + 1];
		unsigned char BYTE2 = bin[byteNo + 2];
		res[rc++] = b64[BYTE0 >> 2];
		res[rc++] = b64[((0x3 & BYTE0) << 4) + (BYTE1 >> 4)];
		res[rc++] = b64[((0x0f & BYTE1) << 2) + (BYTE2 >> 6)];
		res[rc++] = b64[0x3f & BYTE2];
	}

	if (pad == 2) {
		res[rc++] = b64[bin[byteNo] >> 2];
		res[rc++] = b64[(0x3 & bin[byteNo]) << 4];
		res[rc++] = '=';
		res[rc++] = '=';
	} else if (pad == 1) {
		res[rc++] = b64[bin[byteNo] >> 2];
		res[rc++] = b64[((0x3 & bin[byteNo]) << 4) + (bin[byteNo + 1] >> 4)];
		res[rc++] = b64[(0x0f & bin[byteNo + 1]) << 2];
		res[rc++] = '=';
	}

	res[rc] = 0;
	return res;
}

////////////////////////////////////////////////////////
// JSON serializer

void serialize_expr(struct expr* value);

const char* type_to_str(enum symbol_type type) {
	switch (type) {
		case S_UNKNOWN: return "unknown";
		case S_BOOLEAN: return "boolean";
		case S_TRISTATE: return "tristate";
		case S_INT: return "int";
		case S_HEX: return "hex";
		case S_STRING: return "string";
	}
	assert(false);
}

const char* prop_type_to_str(enum prop_type type) {
	switch (type) {
		case P_UNKNOWN: return "unknown";
		case P_PROMPT: return "prompt";
		case P_COMMENT: return "comment";
		case P_MENU: return "menu";
		case P_DEFAULT: return "default";
		case P_CHOICE: return "choice";
		case P_SELECT: return "select";
		case P_IMPLY: return "imply";
		case P_RANGE: return "range";
		case P_SYMBOL: return "symbol";
	}
	assert(false);
}

const char* expr_type_to_str(enum expr_type type) {
	switch (type) {
		case E_NONE: return "none";
		case E_OR: return "or";
		case E_AND: return "and";
		case E_NOT: return "not";
		case E_EQUAL: return "equal";
		case E_UNEQUAL: return "unequal";
		case E_LTH: return "lth";
		case E_LEQ: return "leq";
		case E_GTH: return "gth";
		case E_GEQ: return "geq";
		case E_LIST: return "list";
		case E_SYMBOL: return "symbol";
		case E_RANGE: return "range";
	}
	assert(false);
}

const char* tristate_to_str(enum tristate tri) {
	switch (tri) {
		case no: return "no";
		case mod: return "mod";
		case yes: return "yes";
	}
	assert(false);
}

#define WRITE_LITERAL(s)                   \
	do {                                   \
		(void)!write(1, s, sizeof(s) - 1); \
	} while (0)
#define JSON_BEGIN_OBJ      \
	{                       \
		WRITE_LITERAL("{"); \
		const char* _obj_sep = "";
#define JSON_END_OBJ    \
	WRITE_LITERAL("}"); \
	}
#define JSON_BEGIN_LIST WRITE_LITERAL("[")
#define JSON_END_LIST WRITE_LITERAL("]")
#define JSON_COMMA WRITE_LITERAL(",")
#define JSON_NULL WRITE_LITERAL("null")

#define JSON_K(k)                                    \
	do {                                             \
		(void)!write(1, _obj_sep, strlen(_obj_sep)); \
		_obj_sep = ",";                              \
		const char* _k = (k);                        \
		WRITE_LITERAL("\"");                         \
		(void)!write(1, _k, strlen(_k));             \
		WRITE_LITERAL("\":");                        \
	} while (0)

#define JSON_V(v)                        \
	do {                                 \
		const char* _v = (v);            \
		WRITE_LITERAL("\"");             \
		(void)!write(1, _v, strlen(_v)); \
		WRITE_LITERAL("\"");             \
	} while (0)

#define JSON_KV(k, v) \
	do {              \
		JSON_K(k);    \
		JSON_V(v);    \
	} while (0)

#define JSON_KV_OR_NULL(k, v, cond) \
	do {                            \
		JSON_K(k);                  \
		if (cond) {                 \
			JSON_V(v);              \
		} else {                    \
			JSON_NULL;              \
		}                           \
	} while (0)

#define JSON_V_PRINTF(v, ...)        \
	do {                             \
		const char* _v = (v);        \
		WRITE_LITERAL("\"");         \
		dprintf(1, _v, __VA_ARGS__); \
		WRITE_LITERAL("\"");         \
	} while (0)

#define JSON_KV_PRINTF(k, v, ...)      \
	do {                               \
		JSON_K(k);                     \
		JSON_V_PRINTF(v, __VA_ARGS__); \
	} while (0)

#define JSON_KV_F(k, f, arg) \
	do {                     \
		JSON_K(k);           \
		(f)(arg);            \
	} while (0)

#define JSON_KV_F_CHECKED(k, f, arg) \
	do {                             \
		JSON_K(k);                   \
		if (arg) {                   \
			(f)(arg);                \
		} else {                     \
			JSON_NULL;               \
		}                            \
	} while (0)

#define JSON_KV_EXPR(k, expr) JSON_KV_F_CHECKED(k, serialize_expr, expr)
#define JSON_KV_EXPR_VAL(k, expr) JSON_KV_F(k, serialize_expr_value, expr)
#define JSON_KV_VAL(k, sym, val)   \
	do {                           \
		JSON_K(k);                 \
		serialize_value(sym, val); \
	} while (0)

#define JSON_V_BASE64(v)                                    \
	do {                                                    \
		const char* _v = (v);                               \
		if (_v) {                                           \
			WRITE_LITERAL("\"");                            \
			int base64len = 0;                              \
			char* out = base64(_v, strlen(_v), &base64len); \
			(void)!write(1, out, base64len);                \
			free(out);                                      \
			WRITE_LITERAL("\"");                            \
		} else {                                            \
			JSON_NULL;                                      \
		}                                                   \
	} while (0)

#define JSON_KV_BASE64(k, v) \
	do {                     \
		JSON_K(k);           \
		JSON_V_BASE64(v);    \
	} while (0)

void serialize_value(struct symbol* sym, struct symbol_value value) {
	JSON_BEGIN_OBJ;

	JSON_K("val");
	if (sym_is_choice(sym)) {
		JSON_V_PRINTF("%p", value.val);
	} else {
		JSON_V_BASE64(value.val);
	}

	JSON_KV("tri", tristate_to_str(value.tri));

	JSON_END_OBJ;
}

#define LEFT_EXPR                            \
	do {                                     \
		JSON_KV_EXPR("left", ex->left.expr); \
	} while (0)
#define RIGHT_EXPR                             \
	do {                                       \
		JSON_KV_EXPR("right", ex->right.expr); \
	} while (0)
#define LEFT_SYM                                    \
	do {                                            \
		JSON_KV_PRINTF("left", "%p", ex->left.sym); \
	} while (0)
#define RIGHT_SYM                                     \
	do {                                              \
		JSON_KV_PRINTF("right", "%p", ex->right.sym); \
	} while (0)
#define RIGHT_NULL       \
	do {                 \
		JSON_K("right"); \
		JSON_NULL;       \
	} while (0)

void serialize_expr(struct expr* ex) {
	if (!ex) {
		JSON_NULL;
		return;
	}

	JSON_BEGIN_OBJ;
	JSON_KV("type", expr_type_to_str(ex->type));

	switch (ex->type) {
		case E_NONE: assert(false); break;
		case E_OR:
		case E_AND:
			LEFT_EXPR;
			RIGHT_EXPR;
			break;
		case E_NOT:
			LEFT_EXPR;
			RIGHT_NULL;
			break;
		case E_EQUAL:
		case E_UNEQUAL:
		case E_LTH:
		case E_LEQ:
		case E_GTH:
		case E_GEQ:
		case E_RANGE:
			LEFT_SYM;
			RIGHT_SYM;
			break;
		case E_LIST:
			LEFT_EXPR;
			RIGHT_SYM;
			break;
		case E_SYMBOL:
			LEFT_SYM;
			RIGHT_NULL;
			break;
	}
	JSON_END_OBJ;
}

void serialize_expr_value(struct expr_value value) {
	JSON_BEGIN_OBJ;
	JSON_KV_EXPR("expr", value.expr);
	JSON_KV("tri", tristate_to_str(value.tri));
	JSON_END_OBJ;
}

void serialize_menu(struct menu* menu) {
	JSON_BEGIN_OBJ;
	JSON_KV_EXPR("visibility", menu->visibility);
	JSON_KV_EXPR("dep", menu->dep);
	JSON_KV_PRINTF("flags", "%d", menu->flags);
	JSON_KV_BASE64("help", menu->help);
	JSON_END_OBJ;
}

void props_to_json_list(struct property* prop) {
	JSON_BEGIN_LIST;
	const char* sep = "";
	for (struct property* p = prop; p; p = p->next) {
		(void)!write(1, sep, strlen(sep));
		sep = ",";
		JSON_BEGIN_OBJ;
		JSON_KV("type", prop_type_to_str(p->type));
		JSON_KV_BASE64("text", p->text);
		JSON_KV_EXPR_VAL("visible", p->visible);
		JSON_KV_EXPR("expr", p->expr);
		JSON_KV_F("menu", serialize_menu, p->menu);
		JSON_KV_OR_NULL("file", p->file->name, p->file);
		JSON_KV_PRINTF("lineno", "%d", p->lineno);
		JSON_END_OBJ;
	}
	JSON_END_LIST;
}

void serialize_symbol(struct symbol* sym) {
	JSON_BEGIN_OBJ;
	JSON_KV_PRINTF("ptr", "%p", sym);
	JSON_KV_OR_NULL("name", sym->name, sym->name);
	JSON_KV("type", type_to_str(sym->type));
	JSON_KV_VAL("curr", sym, sym->curr);
	JSON_K("def");
	JSON_BEGIN_OBJ;
	JSON_KV_VAL("user", sym, sym->def[0]);
	JSON_KV_VAL("auto", sym, sym->def[1]);
	JSON_KV_VAL("def3", sym, sym->def[2]);
	JSON_KV_VAL("def4", sym, sym->def[3]);
	JSON_END_OBJ;
	JSON_KV("visible", tristate_to_str(sym->visible));
	JSON_KV_PRINTF("flags", "%d", sym->flags);
	JSON_K("properties");
	props_to_json_list(sym->prop);
	JSON_KV_EXPR_VAL("dir_dep", sym->dir_dep);
	JSON_KV_EXPR_VAL("rev_dep", sym->rev_dep);
	JSON_KV_EXPR_VAL("implied", sym->implied);
	JSON_END_OBJ;
}

int main(int argc, char** argv) {
	if (argc != 2) {
		dprintf(2, "usage: %s <Kconfig>\n", argv[0]);
		return 1;
	}

	struct timeval start, now;
	gettimeofday(&start, NULL);

	// Parse Kconfig and load empty .config (/dev/null)
	conf_parse(argv[1]);
	conf_read("/dev/null");

	gettimeofday(&now, NULL);
	dprintf(2,
	        "%7.4fs -- Loaded Kconfig\n",
	        (double)(now.tv_usec - start.tv_usec) / 1000000 + (double)(now.tv_sec - start.tv_sec));
	start = now;

	// Serialize all symbols
	struct symbol* sym;
	int i;
	JSON_BEGIN_OBJ;
	JSON_K("symbols");
	JSON_BEGIN_LIST;
	for_all_symbols(i, sym) {
		serialize_symbol(sym);
		JSON_COMMA;
	}
	serialize_symbol(sym_lookup("n", 0));
	JSON_COMMA;
	serialize_symbol(sym_lookup("m", 0));
	JSON_COMMA;
	serialize_symbol(sym_lookup("y", 0));
	JSON_END_LIST;
	JSON_END_OBJ;

	gettimeofday(&now, NULL);
	dprintf(2,
	        "%7.4fs -- Serialize symbols\n",
	        (double)(now.tv_usec - start.tv_usec) / 1000000 + (double)(now.tv_sec - start.tv_sec));
	start = now;

	return 0;
}

////////////////////////////////////////////////////////
// BINARY serializer

#define WRITE_DIRECT(var) write(1, &(var), sizeof(var));
#define WRITE_CAST(type, var)        \
	do {                             \
		type _v = (type)(var);       \
		write(1, &_v, sizeof(type)); \
	} while (0)

#define WRITE_STR(str)                        \
	do {                                      \
		uint32_t len = str ? strlen(str) : 0; \
		write(1, &len, sizeof(len));          \
		if (str) {                            \
			write(1, str, len);               \
		}                                     \
	} while (0)

// void bin_serialize_value(struct symbol* sym, struct symbol_value value) {
//	if (sym_is_choice(sym)) {
//		JSON_V_PRINTF("%p", value.val);
//	} else {
//		JSON_V_BASE64(value.val);
//	}
//
//	JSON_KV("tri", tristate_to_str(value.tri));
// }
//
// void bin_serialize_symbol(struct symbol* sym) {
//	WRITE_CAST(uint64_t, sym); // id (address as unique id)
//	WRITE_STR(sym->name);
//	WRITE_DIRECT(sym->type);
//	WRITE_DIRECT(sym->curr);
//	JSON_KV_VAL("curr", sym, sym->curr);
//	JSON_K("def");
//	JSON_BEGIN_OBJ;
//	JSON_KV_VAL("user", sym, sym->def[0]);
//	JSON_KV_VAL("auto", sym, sym->def[1]);
//	JSON_KV_VAL("def3", sym, sym->def[2]);
//	JSON_KV_VAL("def4", sym, sym->def[3]);
//	JSON_END_OBJ;
//	JSON_KV("visible", tristate_to_str(sym->visible));
//	JSON_KV_PRINTF("flags", "%d", sym->flags);
//	JSON_K("properties");
//	props_to_json_list(sym->prop);
//	JSON_KV_EXPR_VAL("dir_dep", sym->dir_dep);
//	JSON_KV_EXPR_VAL("rev_dep", sym->rev_dep);
//	JSON_KV_EXPR_VAL("implied", sym->implied);
//	JSON_END_OBJ;
// }
//
// int bin_main(int argc, char** argv) {
//	if (argc != 2) {
//		dprintf(2, "usage: %s <Kconfig>\n", argv[0]);
//		return 1;
//	}
//
//	struct timeval start, now;
//	gettimeofday(&start, NULL);
//
//	// Parse Kconfig and load empty .config (/dev/null)
//	conf_parse(argv[1]);
//	conf_read("/dev/null");
//
//	gettimeofday(&now, NULL);
//	dprintf(2,
//	        "%7.4fs -- Loaded Kconfig\n",
//	        (double)(now.tv_usec - start.tv_usec) / 1000000 + (double)(now.tv_sec - start.tv_sec));
//	start = now;
//
//	struct symbol* sym;
//	int i;
//
//	// Count symbols
//	int n_symbols = 0;
//	for_all_symbols(i, sym) {
//		++n_symbols;
//	}
//
//	// Serialize all symbols
//	for_all_symbols(i, sym) {
//		bin_serialize_symbol(sym);
//	}
//	bin_serialize_symbol(sym_lookup("n", 0));
//	bin_serialize_symbol(sym_lookup("m", 0));
//	bin_serialize_symbol(sym_lookup("y", 0));
//
//	gettimeofday(&now, NULL);
//	dprintf(2,
//	        "%7.4fs -- Serialize symbols\n",
//	        (double)(now.tv_usec - start.tv_usec) / 1000000 + (double)(now.tv_sec - start.tv_sec));
//	start = now;
//
//	return 0;
// }
