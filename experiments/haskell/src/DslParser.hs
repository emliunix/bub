{-# LANGUAGE OverloadedStrings #-}
module DslParser where

import Control.Applicative
import Control.Monad (void)
import Data.Char (isAlpha, isAlphaNum, isDigit, isSpace)
import Data.Maybe (fromMaybe)
import qualified Data.Text as T
import Text.Trifecta hiding (symbol, stringLiteral)
import Text.Trifecta.Delta
import Text.Parser.Char
import Text.Parser.Combinators (between)
import Text.Parser.LookAhead (lookAhead)
import Text.Parser.Token hiding (symbol, stringLiteral)
import qualified Text.Parser.Token.Highlight as Highlight

import DslAst

-- =============================================================================
-- Parser Configuration
-- =============================================================================

-- | The parser monad type
type DSLParser = Parser

-- | Reserved keywords
keywords :: [String]
keywords = ["def", "let", "return", "llm", "with", "True", "False", "int", "str", "bool", "float", "void"]

-- =============================================================================
-- Lexer / Tokenizer
-- =============================================================================

-- | Skip whitespace including newlines but track indentation
whitespace :: DSLParser ()
whitespace = skipMany (satisfy isSpace)

-- | Skip inline whitespace (no newlines)
inlineWhitespace :: DSLParser ()
inlineWhitespace = skipMany (satisfy (\c -> isSpace c && c /= '\n'))

-- | Skip comments (from # to end of line)
comment :: DSLParser ()
comment = char '#' *> skipMany (satisfy (/= '\n'))

-- | Skip whitespace and comments
sc :: DSLParser ()
sc = skipMany (inlineWhitespace *> optional comment *> inlineWhitespace)

-- | Skip whitespace including newlines
scn :: DSLParser ()
scn = skipMany (whitespace *> optional comment *> whitespace)

-- | Lexeme wrapper - applies trailing whitespace
lexeme :: DSLParser a -> DSLParser a
lexeme p = p <* sc

-- | Symbol parser
symbol :: String -> DSLParser String
symbol s = lexeme (string s)

-- | Keyword parser (not followed by alphanumeric)
keyword :: String -> DSLParser ()
keyword kw = lexeme $ string kw *> notFollowedBy (satisfy isAlphaNum)

-- | Reserved word check
isReserved :: String -> Bool
isReserved s = s `elem` keywords

-- | Identifier parser (non-reserved)
identifierRaw :: DSLParser String
identifierRaw = lexeme $ do
    first <- satisfy (\c -> isAlpha c || c == '_')
    rest <- many (satisfy (\c -> isAlphaNum c || c == '_'))
    let name = first : rest
    if isReserved name
        then unexpected $ "reserved keyword: " ++ name
        else return name

-- | Type name parser (can be reserved type names or identifiers)
typeNameRaw :: DSLParser String
typeNameRaw = lexeme $ do
    first <- satisfy (\c -> isAlpha c || c == '_')
    rest <- many (satisfy (\c -> isAlphaNum c || c == '_'))
    return (first : rest)

-- =============================================================================
-- Indentation-Sensitive Parsing
-- =============================================================================

-- | Indentation state
newtype IndentState = IndentState { indentLevels :: [Int] }
    deriving (Show)

-- | Get current indentation level
currentIndent :: IndentState -> Int
currentIndent (IndentState []) = 0
currentIndent (IndentState (x:_)) = x

-- | Push a new indentation level
pushIndent :: Int -> IndentState -> IndentState
pushIndent i (IndentState is) = IndentState (i:is)

-- | Pop current indentation level
popIndent :: IndentState -> IndentState
popIndent (IndentState []) = IndentState []
popIndent (IndentState (_:is)) = IndentState is

-- | Parse indentation at the start of a line
parseIndentation :: DSLParser Int
parseIndentation = do
    _ <- many (char ' ')
    length <$> many (char ' ')

-- | Check if we're at an indent level
checkIndent :: Int -> DSLParser ()
checkIndent expected = do
    actual <- length <$> many (char ' ')
    if actual == expected
        then return ()
        else unexpected $ "indentation level " ++ show actual ++ ", expected " ++ show expected

-- | Indentation-sensitive block (stateless approach)
-- Parses a block at a specific indentation level
indentedBlock :: DSLParser a -> DSLParser [a]
indentedBlock p = do
    -- Get the current column position after the colon
    _ <- newline
    spaces <- many (char ' ')
    let baseIndent = length spaces
    if baseIndent == 0
        then unexpected "expected indented block"
        else do
            -- Parse first statement at this indent level
            first <- p
            -- Parse rest of block at same or greater indentation
            rest <- many $ try $ do
                _ <- newline
                spaces' <- many (char ' ')
                let indent = length spaces'
                if indent >= baseIndent
                    then p
                    else unexpected "dedent"
            return (first : rest)

-- | Alternative: Manual indentation tracking via sepEndBy1
indentedStatements :: DSLParser a -> DSLParser [a]
indentedStatements p = do
    _ <- newline
    spaces <- many (char ' ')
    let minIndent = length spaces
    if minIndent == 0
        then unexpected "expected indented block (4 spaces)"
        else do
            let stmt = try $ do
                    spaces' <- lookAhead (many (char ' '))
                    let indent = length spaces'
                    if indent == minIndent
                        then p
                        else unexpected $ "wrong indentation level: " ++ show indent
            sepEndBy1 stmt newline

-- =============================================================================
-- Literal Parsers
-- =============================================================================

-- | Parse a string literal (single or double quotes)
stringLiteral :: DSLParser String
stringLiteral = lexeme $ do
    quote <- char '"' <|> char '\''
    chars <- many (satisfy (/= quote))
    _ <- char quote
    return chars

-- | Parse a triple-quoted string (docstring)
tripleQuotedString :: DSLParser String
tripleQuotedString = lexeme $ do
    _ <- string "\"\"\""
    content <- manyTill anyChar (string "\"\"\"")
    return content

-- | Parse an integer literal
integerLiteral :: DSLParser Integer
integerLiteral = lexeme $ do
    sign <- option 1 (char '-' >> return (-1))
    digits <- some digit
    return $ sign * read digits

-- | Parse a float literal
floatLiteral :: DSLParser Float
floatLiteral = lexeme $ do
    sign <- option 1.0 (char '-' >> return (-1.0))
    intPart <- some digit
    _ <- char '.'
    fracPart <- some digit
    return $ sign * read (intPart ++ "." ++ fracPart)

-- | Parse a boolean literal
boolLiteral :: DSLParser Bool
boolLiteral = (keyword "True" >> return True) <|> (keyword "False" >> return False)

-- | Parse any literal
literal :: DSLParser Literal
literal = choice
    [ LitBool <$> BoolLiteral <$> boolLiteral
    , try $ LitFloat <$> FloatLiteral <$> floatLiteral
    , LitInt <$> IntegerLiteral . fromIntegral <$> integerLiteral
    , LitString <$> StringLiteral <$> stringLiteral
    ]

-- =============================================================================
-- Type Parsers
-- =============================================================================

-- | Parse a primitive or user-defined type
typeParser :: DSLParser Type
typeParser = lexeme $ do
    name <- typeNameRaw
    return $ Type name

-- =============================================================================
-- Expression Parsers
-- =============================================================================

-- | Parse an identifier expression
identifierExpr :: DSLParser Expression
identifierExpr = ExprIdent . Identifier <$> identifierRaw

-- | Parse a literal expression
literalExpr :: DSLParser Expression
literalExpr = ExprLit <$> literal

-- | Parse an LLM call
llmCall :: DSLParser LLMCall
llmCall = do
    keyword "llm"
    prompt <- stringLiteral
    context <- optional $ keyword "with" *> expression
    return $ LLMCall prompt context

-- | Parse an LLM call expression
llmExpr :: DSLParser Expression
llmExpr = ExprLLM <$> llmCall

-- | Parse any expression
expression :: DSLParser Expression
expression = choice
    [ try llmExpr
    , literalExpr
    , identifierExpr
    ]

-- =============================================================================
-- Statement Parsers
-- =============================================================================

-- | Parse a typed parameter: name :: type
typedParam :: DSLParser TypedParam
typedParam = do
    name <- identifierRaw
    symbol "::"
    typ <- typeParser
    return $ TypedParam name typ

-- | Parse parameter list: (x :: int, y :: str)
paramList :: DSLParser [TypedParam]
paramList = between (symbol "(") (symbol ")") $ commaSep typedParam

-- | Parse a let binding: let name :: type = expression
letBinding :: DSLParser LetBinding
letBinding = do
    keyword "let"
    name <- identifierRaw
    symbol "::"
    typ <- typeParser
    symbol "="
    value <- expression
    return $ LetBinding name typ value

-- | Parse a return statement: return expression
returnStmt :: DSLParser ReturnStmt
returnStmt = do
    keyword "return"
    value <- expression
    return $ ReturnStmt value

-- | Parse any statement
statement :: DSLParser Statement
statement = choice
    [ StmtLet <$> letBinding
    , StmtReturn <$> returnStmt
    , StmtExpr <$> (ExprStmt <$> expression)
    ]

-- =============================================================================
-- Function Definition Parser
-- =============================================================================

-- | Parse a function definition
functionDef :: DSLParser FunctionDef
functionDef = do
    keyword "def"
    name <- identifierRaw
    params <- paramList
    
    -- Optional return type
    retType <- optional $ do
        symbol "->"
        typeParser
    
    symbol ":"
    
    -- Optional docstring
    doc <- optional $ do
        scn
        tripleQuotedString
    
    -- Body block
    body <- indentedBlock statement
    
    return $ FunctionDef name params retType doc body

-- =============================================================================
-- Program Parser
-- =============================================================================

-- | Parse a complete program
program :: DSLParser Program
program = do
    scn  -- Skip leading whitespace/comments
    funcs <- many functionDef
    scn  -- Skip trailing whitespace
    eof
    return $ Program funcs

-- =============================================================================
-- Public API
-- =============================================================================

-- | Parse a string into a Program
parseDSL :: String -> Result Program
parseDSL = parseString program mempty

-- | Parse a file into a Program
parseDSLFile :: FilePath -> IO (Result Program)
parseDSLFile = parseFromFileEx program

-- | Test parsing with detailed error output
testParse :: String -> IO ()
testParse input = case parseDSL input of
    Success prog -> do
        putStrLn "Parse successful!"
        print prog
    Failure err -> do
        putStrLn "Parse failed:"
        print $ _errDoc err
