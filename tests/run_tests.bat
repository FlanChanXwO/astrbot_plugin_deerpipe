@echo off
REM DeerPipe Plugin Test Runner for Windows
REM Usage: run_tests.bat

cd ..
python tests/run_tests.py %*
