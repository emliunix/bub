# builtins names are defined as const values so the compiler uniquely identifies it.
# and we build a dict for NameCache to lookup

from .types import Name


BUILTIN_BOOL = Name("Bool", 1)
BUILTIN_TRUE = Name("True", 2)
BUILTIN_FALSE = Name("False", 3)
BUILTIN_LIST = Name("List", 6)
BUILTIN_PAIR = Name("Pair", 7)
BUILTIN_INT_PLUS = Name("int_plus", 8)
BUILTIN_INT_MINUS = Name("int_minus", 9)
BUILTIN_INT_MULTIPLY = Name("int_multiply", 10)
BUILTIN_INT_DIVIDE = Name("int_divide", 11)
BUILTIN_INT_EQ = Name("int_eq", 12)
BUILTIN_INT_NEQ = Name("int_neq", 13)
BUILTIN_INT_LT = Name("int_lt", 14)
BUILTIN_INT_GT = Name("int_gt", 15)
BUILTIN_INT_LE = Name("int_le", 16)
BUILTIN_INT_GE = Name("int_ge", 17)
BUILTIN_BOOL_AND = Name("bool_and", 18)
BUILTIN_BOOL_OR = Name("bool_or", 19)
BUILTIN_STRING_CONCAT = Name("string_concat", 20)

BUILTIN_ENDS = 1000


def build_builtins(mod_names: dict[str, list[Name]]) -> dict[tuple[str, str], int]:
    return {
        (mod, name.surface): name.unique
        for (mod, names) in mod_names.items()
        for name in names
    }


BUILTIN_UNIQUES: dict[tuple[str, str], int] = build_builtins({
    "builtins": [
        BUILTIN_BOOL,
        BUILTIN_TRUE,
        BUILTIN_FALSE,
        BUILTIN_LIST,
        BUILTIN_PAIR,
        BUILTIN_INT_PLUS,
        BUILTIN_INT_MINUS,
        BUILTIN_INT_MULTIPLY,
        BUILTIN_INT_DIVIDE,
        BUILTIN_INT_EQ,
        BUILTIN_INT_NEQ,
        BUILTIN_INT_LT,
        BUILTIN_INT_GT,
        BUILTIN_INT_LE,
        BUILTIN_INT_GE,
        BUILTIN_BOOL_AND,
        BUILTIN_BOOL_OR,
        BUILTIN_STRING_CONCAT,
    ]
})
