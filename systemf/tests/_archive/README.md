# Archived Tests

This directory contains deprecated test files that are no longer maintained.
These tests use old APIs that have been refactored or removed.

## Contents

### test_llm_integration.py
**Status:** Deprecated  
**Reason:** Uses old `Elaborator` class API which no longer exists.  
**Replacement:** New LLM integration approach uses `prim_op` syntax instead of `{-# LLM #-}` pragmas.  
**Tests:** 13 tests for LLM pragma parsing, elaboration, and evaluation.

### test_repl_llm.py  
**Status:** Deprecated  
**Reason:** Tests REPL LLM integration using old API.  
**Replacement:** REPL LLM commands need redesign for new architecture.  
**Tests:** 14 tests for `:llm` command and LLM function registration.

## Notes

- These tests are preserved for reference during redesign
- Do not run these tests - they will fail due to missing imports
- When LLM integration is redesigned, use these as reference for test scenarios
- Last working version: before SurfaceNode refactor and Elaborator replacement

## Related Files Still in tests/

These files have some broken tests but also working ones:
- `test_llm_files.py` - 3 parsing tests work, 5 elaboration tests broken
- `test_tool_calls.py` - 13 infrastructure tests work, 11 parsing tests broken

Consider fixing or individually skipping broken tests in those files rather than archiving the whole file.
