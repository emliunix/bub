# System F User Manual

A guide to using System F with LLM integration.

## Table of Contents

1. [Introduction](#introduction)
2. [Basic Syntax](#basic-syntax)
3. [LLM Functions](#llm-functions)
   - [Syntax Overview](#syntax-overview)
   - [Pragma Configuration](#pragma-configuration)
   - [Parameter Documentation](#parameter-documentation)
   - [Examples](#examples)
4. [REPL Commands](#repl-commands)
5. [Troubleshooting](#troubleshooting)

## Introduction

System F is an experimental dependently-typed programming language with integrated LLM (Large Language Model) function support. It allows you to define functions that delegate their implementation to an LLM at runtime, complete with type-safe prompts and structured parameter documentation.

## Basic Syntax

System F uses explicit type annotations for all global declarations:

```systemf
-- Regular function with type annotation
identity : forall a. a -> a
identity = \x -> x

-- Local let binding with optional type annotation
let x : Int = 42 in x + 1
```

### Type Annotations

- **Global declarations**: Type annotations are **required**
- **Local let bindings**: Type annotations are optional (can be inferred)

### Comments

```systemf
-- This is a regular comment

-- | This is a function-level docstring (appears before declaration)

-- ^ This is a parameter docstring (appears after type)
```

## LLM Functions

LLM functions use the `prim_op` keyword to declare functions without implementation. The actual computation is performed by calling an LLM at runtime.

### Syntax Overview

```systemf
{-# LLM model=<model> temperature=<temp> #-}
-- | Function description
prim_op functionName : ArgType
  -- ^ Description of first argument
  -> ArgType2
  -- ^ Description of second argument
  -> ReturnType
  -- ^ Description of return value
```

### Pragma Configuration

The `{-# LLM ... #-}` pragma configures how the LLM is called:

| Option | Description | Example |
|--------|-------------|---------|
| `model` | Model name (e.g., gpt-4, claude, claude-sonnet) | `model=gpt-4` |
| `temperature` | Sampling temperature (0.0 - 1.0) | `temperature=0.7` |

**Minimal pragma** (uses defaults):
```systemf
{-# LLM #-}
```

**Full configuration**:
```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
```

### Parameter Documentation

Parameter docs use the `-- ^` syntax attached to types:

```systemf
prim_op translate : String
  -- ^ The English text to translate
  -> String
  -- ^ The French translation
```

**Key points:**
- `-- ^` comments attach to the **type** on the left
- They can span multiple lines
- Each parameter in a curried function gets its own doc

**Multi-line docs**:
```systemf
prim_op classify : String
  -- ^ Comma-separated list of valid categories
  -- ^ Example: "positive, negative, neutral"
  -> String
  -- ^ The text to classify
  -> String
```

### Examples

#### Single Parameter

```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English text to French
prim_op translate : String
  -- ^ The English text to translate
  -> String
  -- The French translation
```

#### Multiple Parameters

```systemf
{-# LLM model=gpt-4 temperature=0.5 #-}
-- | Classify text into one of the provided categories
prim_op classify : String
  -- ^ Comma-separated list of valid categories
  -> String
  -- ^ The text to classify
  -> String
  -- ^ The selected category
```

#### With Custom Types

```systemf
data Maybe a = Nothing | Just a

{-# LLM model=gpt-4 temperature=0.2 #-}
-- | Extract structured data from unstructured text
prim_op extractName : String
  -- ^ Text containing a person's name
  -> Maybe String
  -- Just the name if found, Nothing otherwise
```

## REPL Commands

The System F REPL provides commands for inspecting LLM functions:

### `:llm` - List LLM Functions

```
> :llm
LLM Functions:
  translate - model=gpt-4, temp=0.7
  classify  - model=gpt-4, temp=0.5
  summarize - model=(default), temp=(default)
```

### `:llm <function>` - Show Function Details

```
> :llm translate
LLM Function: translate
Description: Translate English text to French
Model: gpt-4
Temperature: 0.7
Arguments:
  arg0 : String - The English text to translate
Returns: String
```

### Other Useful Commands

| Command | Description |
|---------|-------------|
| `:quit` or `:q` | Exit the REPL |
| `:help` or `:h` | Show help message |
| `:env` | Show current environment |
| `:{` | Start multi-line input |
| `:}` | End multi-line input |

## Troubleshooting

### "Missing type annotation" Error

**Problem**: Global declarations without type annotations.

**Solution**: Add explicit type annotations:
```systemf
-- Wrong:
func = \x -> x

-- Correct:
func : forall a. a -> a
func = \x -> x
```

### "Unknown LLM function" Error

**Problem**: The LLM function wasn't registered properly.

**Solution**: Check that:
1. The pragma uses `{-# LLM ... #-}` syntax
2. The declaration uses `prim_op` keyword
3. The file loaded without errors

### LLM Not Being Called

**Problem**: Regular function defined instead of LLM function.

**Solution**: Use `prim_op` instead of regular function definition:
```systemf
-- Wrong (regular function with no body):
translate : String -> String
translate = \text -> ???

-- Correct (LLM function):
{-# LLM #-}
-- | Translate text
prim_op translate : String -> String
```

### Parse Errors with `-- ^`

**Problem**: Parameter doc not being recognized.

**Solution**: Ensure `-- ^` appears immediately after the type:
```systemf
-- Wrong:
prim_op f : String
-> String
-- ^ doc

-- Correct:
prim_op f : String
  -- ^ doc
  -> String
```

### Type Errors

**Problem**: Type mismatch in LLM function usage.

**Solution**: Check that:
1. Argument types match the declared signature
2. Return type is what you expect
3. Custom types (like `Maybe`, `Either`) are defined before use

### REPL Shows "No LLM functions registered"

**Problem**: File loaded but LLM functions not recognized.

**Solution**: 
1. Check that declarations use `{-# LLM #-}` pragma
2. Use `:llm` command after loading a file
3. Check for any errors during file load

## Best Practices

1. **Always document parameters**: Use `-- ^` to describe what each argument does
2. **Specify temperature**: Use lower temperatures (0.0-0.3) for deterministic tasks, higher (0.7-0.9) for creative tasks
3. **Use custom types**: Leverage System F's type system with `Maybe`, `Either`, etc.
4. **Test incrementally**: Use the REPL to test LLM functions before adding them to larger programs
5. **Keep docs concise**: LLM prompts work better with clear, brief descriptions

## See Also

- [Design Document](design-llm-integration.md) - Technical details of LLM integration
- [Example Files](../systemf/tests/llm_examples.sf) - Working examples
- [README](../README.md) - Project overview and quick start
