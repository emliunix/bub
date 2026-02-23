module DslTests where

import DslAst
import Test.HUnit

-- =============================================================================
-- Test 1: minimal_function
-- =============================================================================

minimalFunctionInput :: String
minimalFunctionInput = "def empty():\n    pass"

minimalFunctionExpected :: Program
minimalFunctionExpected = Program
  [ FunctionDef
      { funcName = "empty"
      , funcParams = []
      , funcReturnType = Nothing
      , funcDoc = Nothing
      , funcBody = []
      }
  ]

-- =============================================================================
-- Test 2: function_with_params
-- =============================================================================

functionWithParamsInput :: String
functionWithParamsInput = "def add(x :: int, y :: int) -> int:\n    return x"

functionWithParamsExpected :: Program
functionWithParamsExpected = Program
  [ FunctionDef
      { funcName = "add"
      , funcParams = [TypedParam "x" int, TypedParam "y" int]
      , funcReturnType = Just int
      , funcDoc = Nothing
      , funcBody = [StmtReturn (ReturnStmt (ExprIdent (Identifier "x")))]
      }
  ]

-- =============================================================================
-- Test 3: function_with_docstring
-- =============================================================================

functionWithDocstringInput :: String
functionWithDocstringInput =
  "def greet(name :: str) -> str:\n" ++
  "    \"\"\"Return a greeting for the given name.\"\"\"\n" ++
  "    return name"

functionWithDocstringExpected :: Program
functionWithDocstringExpected = Program
  [ FunctionDef
      { funcName = "greet"
      , funcParams = [TypedParam "name" str]
      , funcReturnType = Just str
      , funcDoc = Just "Return a greeting for the given name."
      , funcBody = [StmtReturn (ReturnStmt (ExprIdent (Identifier "name")))]
      }
  ]

-- =============================================================================
-- Test 4: simple_let
-- =============================================================================

simpleLetInput :: String
simpleLetInput =
  "def test():\n" ++
  "    let x :: int = 42\n" ++
  "    return x"

simpleLetExpected :: Program
simpleLetExpected = Program
  [ FunctionDef
      { funcName = "test"
      , funcParams = []
      , funcReturnType = Nothing
      , funcDoc = Nothing
      , funcBody =
          [ StmtLet (LetBinding "x" int (ExprLit (LitInt (IntegerLiteral 42))))
          , StmtReturn (ReturnStmt (ExprIdent (Identifier "x")))
          ]
      }
  ]

-- =============================================================================
-- Test 5: simple_llm_call
-- =============================================================================

simpleLLMCallInput :: String
simpleLLMCallInput =
  "def summarize():\n" ++
  "    let result :: str = llm \"Summarize this\"\n" ++
  "    return result"

simpleLLMCallExpected :: Program
simpleLLMCallExpected = Program
  [ FunctionDef
      { funcName = "summarize"
      , funcParams = []
      , funcReturnType = Nothing
      , funcDoc = Nothing
      , funcBody =
          [ StmtLet (LetBinding "result" str (ExprLLM (LLMCall "Summarize this" Nothing)))
          , StmtReturn (ReturnStmt (ExprIdent (Identifier "result")))
          ]
      }
  ]

-- =============================================================================
-- Test 6: llm_call_with_context
-- =============================================================================

llmCallWithContextInput :: String
llmCallWithContextInput =
  "def analyze(code :: str):\n" ++
  "    let issues :: str = llm \"Find bugs\" with code\n" ++
  "    return issues"

llmCallWithContextExpected :: Program
llmCallWithContextExpected = Program
  [ FunctionDef
      { funcName = "analyze"
      , funcParams = [TypedParam "code" str]
      , funcReturnType = Nothing
      , funcDoc = Nothing
      , funcBody =
          [ StmtLet (LetBinding "issues" str (ExprLLM (LLMCall "Find bugs" (Just (ExprIdent (Identifier "code"))))))
          , StmtReturn (ReturnStmt (ExprIdent (Identifier "issues")))
          ]
      }
  ]

-- =============================================================================
-- Test 7: full_example
-- =============================================================================

fullExampleInput :: String
fullExampleInput =
  "def analyze_code(filename :: str) -> str:\n" ++
  "    \"\"\"Analyze source code for issues.\"\"\"\n" ++
  "    let content :: str = llm \"Read and summarize the file\"\n" ++
  "    let issues :: str = llm \"Find bugs\" with content\n" ++
  "    return issues"

fullExampleExpected :: Program
fullExampleExpected = Program
  [ FunctionDef
      { funcName = "analyze_code"
      , funcParams = [TypedParam "filename" str]
      , funcReturnType = Just str
      , funcDoc = Just "Analyze source code for issues."
      , funcBody =
          [ StmtLet (LetBinding "content" str (ExprLLM (LLMCall "Read and summarize the file" Nothing)))
          , StmtLet (LetBinding "issues" str (ExprLLM (LLMCall "Find bugs" (Just (ExprIdent (Identifier "content"))))))
          , StmtReturn (ReturnStmt (ExprIdent (Identifier "issues")))
          ]
      }
  ]

-- =============================================================================
-- Test Runner
-- =============================================================================

-- Placeholder parse function - to be implemented
parse :: String -> Program
parse _ = error "parse function not yet implemented"

-- All tests
tests :: Test
tests = TestList
  [ "minimal_function" ~: parse minimalFunctionInput ~?= minimalFunctionExpected
  , "function_with_params" ~: parse functionWithParamsInput ~?= functionWithParamsExpected
  , "function_with_docstring" ~: parse functionWithDocstringInput ~?= functionWithDocstringExpected
  , "simple_let" ~: parse simpleLetInput ~?= simpleLetExpected
  , "simple_llm_call" ~: parse simpleLLMCallInput ~?= simpleLLMCallExpected
  , "llm_call_with_context" ~: parse llmCallWithContextInput ~?= llmCallWithContextExpected
  , "full_example" ~: parse fullExampleInput ~?= fullExampleExpected
  ]

-- Main entry point for running tests
main :: IO ()
main = do
  putStrLn "Workflow DSL Test Suite"
  putStrLn "Total test cases: 7"
  putStrLn ""
  counts <- runTestTT tests
  putStrLn $ show counts
