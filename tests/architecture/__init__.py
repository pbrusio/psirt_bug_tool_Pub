"""
Architecture Test Framework for CVE_EVAL_V2

This module implements the testing workflow defined in docs/ARCHITECTURE_AND_WORKFLOW.md
Section 9: Testing Workflow (Before/After, Iterative, Safety First)

Test Categories:
- baseline: Tests to establish current behavior before refactoring
- refactor: Tests for fallback behavior, thresholds, and caching
- comparison: Tests for output diff and performance checks
- observability: Tests for metrics and logging

Usage:
    # Run all architecture tests
    pytest tests/architecture/ -v

    # Run baseline tests only
    pytest tests/architecture/ -v -m baseline

    # Run with performance benchmarks (slower)
    pytest tests/architecture/ -v --benchmark

    # Run integration tests (requires live services)
    pytest tests/architecture/ -v --integration
"""

__version__ = "1.0.0"
