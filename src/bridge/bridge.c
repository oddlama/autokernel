#include <string.h>
#include <strings.h>
#include <stdlib.h>

#include "lkc.h"
#include <ctype.h>
#include "base64.h"

void expr_to_json(struct expr* value);

const char* type_to_str(enum symbol_type type) {
	switch (type) {
		case S_UNKNOWN:   return "unknown";
		case S_BOOLEAN:   return "boolean";
		case S_TRISTATE:  return "tristate";
		case S_INT:       return "int";
		case S_HEX:       return "hex";
		case S_STRING:    return "string";
	}
	assert(false);
}

const char* prop_type_to_str(enum prop_type type) {
	switch (type) {
		case P_UNKNOWN:  return "unknown";
		case P_PROMPT:   return "prompt";
		case P_COMMENT:  return "comment";
		case P_MENU:     return "menu";
		case P_DEFAULT:  return "default";
		case P_CHOICE:   return "choice";
		case P_SELECT:   return "select";
		case P_IMPLY:    return "imply";
		case P_RANGE:    return "range";
		case P_SYMBOL:   return "symbol";
	}
	assert(false);
}

const char* expr_type_to_str(enum expr_type type) {
	switch (type) {
		case E_NONE:     return "none";
		case E_OR:       return "or";
		case E_AND:      return "and";
		case E_NOT:      return "not";
		case E_EQUAL:    return "equal";
		case E_UNEQUAL:  return "unequal";
		case E_LTH:      return "lth";
		case E_LEQ:      return "leq";
		case E_GTH:      return "gth";
		case E_GEQ:      return "geq";
		case E_LIST:     return "list";
		case E_SYMBOL:   return "symbol";
		case E_RANGE:    return "range";
	}
	assert(false);
}

const char* tristate_to_str(enum tristate tri) {
	switch (tri) {
		case no:  return "no";
		case mod: return "mod";
		case yes: return "yes";
	}
	assert(false);
}

void text_to_json(const char* text) {
	if (!text) {
		puts("null");
		return;
	}

	int dummy = 42;
	char* out = base64(text, strlen(text), &dummy);
	printf("\"%s\"", out);
	free(out);
}

void value_to_json(struct symbol* sym, struct symbol_value value) {
	printf("{\n");
	if (sym_is_choice(sym)) {
		printf("\"val\": \"%p\",\n", value.val);
	} else if (value.val == NULL) {
		printf("\"val\": \"null\",\n");
	} else {
		int dummy = 42;
		char* out = base64(value.val, strlen((const char*)value.val), &dummy);
		printf("\"val\": \"%s\",\n", out);
		free(out);
	}
	printf("\"tri\": \"%s\"\n", tristate_to_str(value.tri));
	printf("}\n");
}

void expr_part_to_json(const char* part, union expr_data* data, bool is_expr) {
	printf("\"%s\":", part);
	if (is_expr) {
		expr_to_json(data->expr);
	} else {
		printf("\"%p\"", data->sym);
	}
	printf(",");
}

void expr_to_json(struct expr* ex) {
	if (!ex) {
		printf("null\n");
		return;
	}
	printf("{\n");
	printf("\"type\": \"%s\",\n", expr_type_to_str(ex->type));
	switch (ex->type) {
		case E_NONE:
			assert(false);
			break;
		case E_OR:
		case E_AND:
			expr_part_to_json("left", &ex->left, true);
			expr_part_to_json("right", &ex->right, true);
			break;
		case E_NOT:
			expr_part_to_json("left", &ex->left, true);
			printf("\"right\": null,\n");
			break;
		case E_EQUAL:
		case E_UNEQUAL:
		case E_LTH:
		case E_LEQ:
		case E_GTH:
		case E_GEQ:
		case E_RANGE:
			expr_part_to_json("left", &ex->left, false);
			expr_part_to_json("right", &ex->right, false);
			break;
		case E_LIST:
			expr_part_to_json("left", &ex->left, true);
			expr_part_to_json("right", &ex->right, false);
			break;
		case E_SYMBOL:
			expr_part_to_json("left", &ex->left, false);
			printf("\"right\": null,\n");
			break;
	}
	printf("\"dummy\": null\n");
	printf("}\n");
}

void expr_value_to_json(struct expr_value value) {
	printf("{\n");
	if (value.expr) {
		printf("\"expr\": "); expr_to_json(value.expr); printf(",\n");
	}
	printf("\"tri\": \"%s\"\n", tristate_to_str(value.tri));
	printf("}\n");
}

void menu_to_json(struct menu* menu) {
	printf("{\n");
	printf("\"visibility\":"); expr_to_json(menu->visibility); printf(",");
	printf("\"dep\":"); expr_to_json(menu->dep); printf(",");
	printf("\"flags\": \"%d\",", menu->flags);
	printf("\"help\":"); text_to_json(menu->help);
	printf("}\n");
}

void props_to_json(struct property * prop) {
	struct property* p = prop;
	bool first = true;
	while (p) {
		if (!first) {
 			printf(",\n");
		} else {
			first = false;
		}
		printf("{\n");
		printf("\"type\": \"%s\",\n", prop_type_to_str(p->type));
		printf("\"text\": "); text_to_json(p->text); printf(",\n");
		printf("\"visible\": "); expr_value_to_json(p->visible); printf(",\n");
		if (p->expr) {
			printf("\"expr\": "); expr_to_json(p->expr); printf(",\n");
		}
		if (p->menu) {
			printf("\"menu\": "); menu_to_json(p->menu); printf(",\n");
		}
		if (p->file) {
			printf("\"file\": \"%s\",\n", p->file->name);
		}
		printf("\"lineno\": \"%d\"\n", p->lineno);
		printf("}\n");
		p = p->next;
	}
}

void print_symbol(struct symbol* sym) {
	printf("{\n");
	printf("\"ptr\": \"%p\",\n", sym);
	printf("\"name\": \"%s\",\n", sym->name);
	printf("\"type\": \"%s\",\n", type_to_str(sym->type));
	printf("\"curr\": "); value_to_json(sym, sym->curr); printf(",\n");
	printf("\"def\": {\n");
	printf("\"user\": "); value_to_json(sym, sym->def[0]); printf(",\n");
	printf("\"auto\": "); value_to_json(sym, sym->def[1]); printf(",\n");
	printf("\"def3\": "); value_to_json(sym, sym->def[2]); printf(",\n");
	printf("\"def4\": "); value_to_json(sym, sym->def[3]); printf("\n");
	printf("},\n");
	printf("\"visible\": \"%s\",\n", tristate_to_str(sym->visible));
	printf("\"flags\": \"%d\",\n", sym->flags);
	printf("\"properties\": [\n");
	props_to_json(sym->prop);
	printf("],\n");
	printf("\"dir_dep\": "); expr_value_to_json(sym->dir_dep); printf(",\n");
	printf("\"rev_dep\": "); expr_value_to_json(sym->rev_dep); printf(",\n");
	printf("\"implied\": "); expr_value_to_json(sym->implied); printf("\n");
	printf("}");
}

int main(int argc, char** argv) {
	if (argc != 3) {
		dprintf(2, "usage: %s ./Kconfig .config", argv[0]);
		return 1;
	}

	// Parse Kconfig and load values from .config
	conf_parse(argv[1]);
	conf_read(argv[2]);

	// Serialize all symbols
	struct symbol *sym;
	int i;
	printf("{\"symbols\": [\n");
	for_all_symbols(i, sym) {
		print_symbol(sym);
		printf(",\n");
	}
	print_symbol(sym_lookup("n", 0));
	printf(",\n");
	print_symbol(sym_lookup("m", 0));
	printf(",\n");
	print_symbol(sym_lookup("y", 0));
	printf("]}\n");

	return 0;
}
