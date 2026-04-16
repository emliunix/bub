# builtins names are defined as const values so the compiler uniquely identifies it.
# and we build a dict for NameCache to lookup

from .types import Name

BUILTIN_UNIT = Name("builtins", "Unit", 1)
BUILTIN_MK_UNIT = Name("builtins", "MkUnit", 2)

BUILTIN_BOOL = Name("builtins", "Bool", 3)
BUILTIN_TRUE = Name("builtins", "True", 4)
BUILTIN_FALSE = Name("builtins", "False", 5)

BUILTIN_LIST = Name("builtins", "List", 6)
BUILTIN_LIST_CONS = Name("builtins", "Cons", 7)
BUILTIN_LIST_NIL = Name("builtins", "Nil", 8)

BUILTIN_PAIR = Name("builtins", "Pair", 9)
BUILTIN_PAIR_MKPAIR = Name("builtins", "MkPair", 10)

BUILTIN_INT_PLUS = Name("builtins", "int_plus", 11)
BUILTIN_INT_MINUS = Name("builtins", "int_minus", 12)
BUILTIN_INT_MULTIPLY = Name("builtins", "int_multiply", 13)
BUILTIN_INT_DIVIDE = Name("builtins", "int_divide", 14)
BUILTIN_INT_EQ = Name("builtins", "int_eq", 15)
BUILTIN_INT_NEQ = Name("builtins", "int_neq", 16)
BUILTIN_INT_LT = Name("builtins", "int_lt", 17)
BUILTIN_INT_GT = Name("builtins", "int_gt", 18)
BUILTIN_INT_LE = Name("builtins", "int_le", 19)
BUILTIN_INT_GE = Name("builtins", "int_ge", 20)

BUILTIN_BOOL_AND = Name("builtins", "bool_and", 21)
BUILTIN_BOOL_OR = Name("builtins", "bool_or", 22)

BUILTIN_STRING_CONCAT = Name("builtins", "string_concat", 23)

BUILTIN_ENDS = 1000


BUILTIN_NAMES: dict[str, list[Name]] = {
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
}

BUILTIN_BIN_OPS = {
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
