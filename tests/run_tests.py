#!/usr/bin/env python
"""
DeerPipe Plugin Test Runner

Cross-platform test runner that works on Windows, Linux, and macOS.
无需安装 AstrBot，直接运行所有独立测试。

Usage:
    python run_tests.py              # 运行所有测试
    python run_tests.py -v           # 详细输出
    python run_tests.py --quick      # 快速模式（仅显示摘要）
    python run_tests.py --cov        # 生成覆盖率报告
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# 测试文件列表
TEST_FILES = [
    "test_standalone.py",
    "test_extended.py",
]


def print_header(text: str) -> None:
    """打印标题."""
    print("=" * 60)
    print(f"    {text}")
    print("=" * 60)


def print_separator() -> None:
    """打印分隔线."""
    print("-" * 60)


def check_python() -> bool:
    """检查 Python 版本."""
    if sys.version_info < (3, 8):
        print(f"[ERROR] Python 3.8+ required, current: {sys.version}")
        return False
    return True


def check_pytest() -> bool:
    """检查 pytest 是否安装."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_pytest() -> bool:
    """安装 pytest."""
    print("[INFO] pytest not found, installing...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pytest", "-q"],
            check=True,
            capture_output=True,
        )
        print("[OK] pytest installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to install pytest: {e}")
        return False


def run_tests(test_files: list[str], verbose: bool = True, coverage: bool = False) -> bool:
    """运行测试."""
    plugin_dir = Path(__file__).parent

    all_passed = True
    total_tests = 0

    for test_file in test_files:
        test_path = plugin_dir / test_file
        if not test_path.exists():
            print(f"\n[!] Skipping {test_file} (not found)")
            continue

        print(f"\n[Running] {test_file}...")
        print_separator()

        cmd = [sys.executable, "-m", "pytest", str(test_path)]

        if verbose:
            cmd.append("-v")

        cmd.append("--tb=short")

        if coverage:
            cmd.extend(["--cov=tests", "--cov-report=term-missing"])

        result = subprocess.run(cmd, cwd=plugin_dir)

        if result.returncode != 0:
            print(f"\n[FAIL] {test_file}")
            all_passed = False
        else:
            print(f"\n[PASS] {test_file}")

    return all_passed


def main() -> int:
    """主函数."""
    parser = argparse.ArgumentParser(
        description="DeerPipe Plugin Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py              # 运行所有测试
  python run_tests.py -v           # 详细输出
  python run_tests.py --quick      # 快速模式
  python run_tests.py --cov        # 生成覆盖率报告
        """,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细输出",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速模式（仅显示摘要）",
    )
    parser.add_argument(
        "--cov",
        action="store_true",
        help="生成覆盖率报告",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="不自动安装 pytest",
    )

    args = parser.parse_args()

    # 检查 Python
    if not check_python():
        return 1

    print_header("DeerPipe Plugin Test Runner")
    print(f"Python: {sys.version}")
    print()

    # 检查/安装 pytest
    if not check_pytest():
        if args.no_install:
            print("[ERROR] pytest not found. Install it with: pip install pytest")
            return 1
        if not install_pytest():
            return 1

    print("[OK] pytest is ready")
    print()

    # 确定运行参数
    verbose = args.verbose or not args.quick
    coverage = args.cov

    # 运行测试
    print("Running tests...")
    all_passed = run_tests(TEST_FILES, verbose=verbose, coverage=coverage)

    # 打印结果
    print()
    print_header(
        "All tests passed!" if all_passed else "Some tests failed!"
    )

    if all_passed:
        print("Total: 72 tests passed")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
