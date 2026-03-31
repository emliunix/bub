# builtins names are defined as const values so the compiler uniquely identifies it.
# and we build a dict for NameCache to lookup

from .types import Name


BUILTIN_BOOL = Name("builtins", "Bool", 1)
BUILTIN_TRUE = Name("builtins", "True", 2)
BUILTIN_FALSE = Name("builtins", "False", 3)

BUILTIN_LIST = Name("builtins", "List", 4)
BUILTIN_LIST_CONS = Name("builtins", "Cons", 5)
BUILTIN_LIST_NIL = Name("builtins", "Nil", 6)

BUILTIN_PAIR = Name("builtins", "Pair", 7)
BUILTIN_PAIR_MKPAIR = Name("builtins", "MkPair", 8)

BUILTIN_INT_PLUS = Name("builtins", "int_plus", 9)
BUILTIN_INT_MINUS = Name("builtins", "int_minus", 10)
BUILTIN_INT_MULTIPLY = Name("builtins", "int_multiply", 11)
BUILTIN_INT_DIVIDE = Name("builtins", "int_divide", 12)
BUILTIN_INT_EQ = Name("builtins", "int_eq", 13)
BUILTIN_INT_NEQ = Name("builtins", "int_neq", 14)
BUILTIN_INT_LT = Name("builtins", "int_lt", 15)
BUILTIN_INT_GT = Name("builtins", "int_gt", 16)
BUILTIN_INT_LE = Name("builtins", "int_le", 17)
BUILTIN_INT_GE = Name("builtins", "int_ge", 18)

BUILTIN_BOOL_AND = Name("builtins", "bool_and", 19)
BUILTIN_BOOL_OR = Name("builtins", "bool_or", 20)

BUILTIN_STRING_CONCAT = Name("builtins", "string_concat", 21)

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
        BUILTIN_LIST_CONS,
        BUILTIN_LIST_NIL,
        BUILTIN_PAIR,
        BUILTIN_PAIR_MKPAIR,
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

BUILTIN_OPS = {
    "+": BUILTIN_INT_PLUS,
    "-": BUILTIN_INT_MINUS,
    "*": BUILTIN_INT_MULTIPLY,
    "/": BUILTIN_INT_DIVIDE,
    "==": BUILTIN_INT_EQ,
    "!=": BUILTIN_INT_NEQ,
    "<": BUILTIN_INT_LT,
    ">": BUILTIN_INT_GT,
    "<=": BUILTIN_INT_LE,
    ">=": BUILTIN_INT_GE,
    "&&": BUILTIN_BOOL_AND,
    "||": BUILTIN_BOOL_OR,
    "++": BUILTIN_STRING_CONCAT,
}
