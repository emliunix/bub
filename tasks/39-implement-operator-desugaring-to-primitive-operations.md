---
assignee: Implementor
expertise: ['Python', 'Parsing', 'Desugaring']
skills: ['python-project', 'testing']
type: implement
priority: medium
state: review
dependencies: ['tasks/38-implement-prelude-integration-for-primitives.md']
refers: []
kanban: tasks/33-kanban-systemf-pluggable-primitives-system.md
created: 2026-02-26T17:18:20.013049
---

# Task: Implement - Operator Desugaring to Primitive Operations

## Context
Implement operator desugaring to convert infix operators (+, -, *, etc.) to primitive operation calls. Operators desugar to `$prim` names which cannot be shadowed.

## Files
- systemf/src/systemf/surface/lexer.py
- systemf/src/systemf/surface/desugar.py
- systemf/src/systemf/surface/parser.py

## Description
Add operator tokens to lexer (+, -, *, /, ==, <, >, etc.). Update parser to handle infix operator expressions with proper precedence. Create desugaring table mapping operators to `$prim` names (+ → `$prim.int.plus`, - → `$prim.int.minus`, etc.). Implement desugaring pass that converts operator expressions to PrimOp applications. Handle operator precedence and associativity. Add comprehensive tests for operator expressions.

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 18:33:21] Implementation Complete

**Facts:**
Implemented operator desugaring system for SystemF surface language.

## Changes Made

### 1. Lexer (systemf/src/systemf/surface/lexer.py)
- Added arithmetic operators: +, -, *, / (PLUS, MINUS, STAR, SLASH)
- Added comparison operators: ==, <, >, <=, >= (EQ, LT, GT, LE, GE)
- Updated _create_typed_token() to handle new operator tokens

### 2. Token Types (systemf/src/systemf/surface/types.py)
- Added new TokenType constants for all operators
- Updated ALL set to include new token types

### 3. AST (systemf/src/systemf/surface/ast.py)
- Added SurfaceOp dataclass for infix operator expressions
- Added to SurfaceTermRepr union

### 4. Parser (systemf/src/systemf/surface/parser.py)
- Added operator token matchers (PLUS, MINUS, STAR, SLASH, EQ, LT, GT, LE, GE)
- Implemented precedence-climbing parser (make_op_parser function)
- Defined OPERATOR_PRECEDENCE levels (*,/ at 7; +,- at 6; comparisons at 5)
- Created op_expr_parser for parsing operator expressions
- Updated term_parser to use op_expr_parser
- Updated decl_term_parser with decl_op_expr_parser for declarations

### 5. Desugarer (systemf/src/systemf/surface/desugar.py)
- Added OPERATOR_TO_PRIM mapping table:
  - + -> $prim.int.plus
  - - -> $prim.int.minus
  - * -> $prim.int.multiply
  - / -> $prim.int.divide
  - == -> $prim.int.eq
  - < -> $prim.int.lt
  - > -> $prim.int.gt
  - <= -> $prim.int.le
  - >= -> $prim.int.ge
- Implemented _desugar_operators() method
- Updated _desugar_children() to handle SurfaceOp nodes
- Updated LetToLambdaDesugarer to handle SurfaceOp

### 6. Tests
- Added lexer operator tests (test_arithmetic_operators, test_comparison_operators, test_mixed_operators)
- Created comprehensive parser operator tests (TestOperatorExpressions class)
- Created dedicated operator desugar tests (test_operator_desugar.py)

## Features Implemented
- Infix operator parsing with proper precedence (*,/ > +,- > comparisons)
- Left-associative operators
- Parentheses support for overriding precedence
- Complete desugaring to primitive operation applications
- Support in let declarations and lambda bodies
- All operators map to $prim.int.* names that cannot be shadowed

## Test Results
- 220 surface tests passing
- 412 total tests passing (2 pre-existing failures unrelated to changes)
- Operator expressions correctly parse and desugar to primitive calls
- Operator precedence and associativity work correctly

**Analysis:**
-

**Conclusion:**
Status: ok

---

