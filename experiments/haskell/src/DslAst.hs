module DslAst where

-- =============================================================================
-- Type Synonyms
-- =============================================================================

type Name = String
type DocString = String

-- =============================================================================
-- Types
-- =============================================================================

data Type = Type Name
    deriving (Show, Eq)

-- Primitive types
int :: Type
int = Type "int"

float :: Type
float = Type "float"

str :: Type
str = Type "str"

bool :: Type
bool = Type "bool"

void :: Type
void = Type "void"

-- =============================================================================
-- Literals
-- =============================================================================

data IntegerLiteral = IntegerLiteral Int
    deriving (Show, Eq)

data FloatLiteral = FloatLiteral Float
    deriving (Show, Eq)

data StringLiteral = StringLiteral String
    deriving (Show, Eq)

data BoolLiteral = BoolLiteral Bool
    deriving (Show, Eq)

data Literal
    = LitInt IntegerLiteral
    | LitFloat FloatLiteral
    | LitString StringLiteral
    | LitBool BoolLiteral
    deriving (Show, Eq)

-- =============================================================================
-- Expressions
-- =============================================================================

data Identifier = Identifier Name
    deriving (Show, Eq)

data LLMCall = LLMCall
    { prompt  :: String
    , context :: Maybe Expression
    }
    deriving (Show, Eq)

data Expression
    = ExprIdent Identifier
    | ExprLit Literal
    | ExprLLM LLMCall
    deriving (Show, Eq)

-- =============================================================================
-- Statements
-- =============================================================================

data LetBinding = LetBinding
    { letName  :: Name
    , letType  :: Type
    , letValue :: Expression
    }
    deriving (Show, Eq)

data ReturnStmt = ReturnStmt
    { returnValue :: Expression
    }
    deriving (Show, Eq)

data ExprStmt = ExprStmt
    { expr :: Expression
    }
    deriving (Show, Eq)

data Statement
    = StmtLet LetBinding
    | StmtReturn ReturnStmt
    | StmtExpr ExprStmt
    deriving (Show, Eq)

-- =============================================================================
-- Function Definition
-- =============================================================================

data TypedParam = TypedParam
    { paramName :: Name
    , paramType :: Type
    }
    deriving (Show, Eq)

data FunctionDef = FunctionDef
    { funcName       :: Name
    , funcParams     :: [TypedParam]
    , funcReturnType :: Maybe Type
    , funcDoc        :: Maybe DocString
    , funcBody       :: [Statement]
    }
    deriving (Show, Eq)

-- =============================================================================
-- Program
-- =============================================================================

data Program = Program
    { programFunctions :: [FunctionDef]
    }
    deriving (Show, Eq)
