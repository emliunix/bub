#!/bin/bash
set -e

echo "Building workflow-dsl Haskell project..."

if command -v stack &> /dev/null; then
    echo "Using Stack..."
    stack build
    echo "Build complete! Run with: stack exec workflow-dsl"
elif command -v cabal &> /dev/null; then
    echo "Using Cabal..."
    cabal update
    cabal build
    echo "Build complete! Run with: cabal run workflow-dsl"
else
    echo "Error: Neither Stack nor Cabal found. Please install one of them."
    exit 1
fi
