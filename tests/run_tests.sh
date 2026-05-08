#!/bin/bash
# DeerPipe Plugin Test Runner for Unix/Linux/macOS
# Usage: ./run_tests.sh [options]

cd "$(dirname "$0")/.." || exit 1
python3 tests/run_tests.py "$@" || python tests/run_tests.py "$@"
