"""
Architecture Test Results Manager

Handles saving, loading, and comparing test results over time.
Results are stored with date/version naming convention for tracking
changes across refactoring phases.

Reference: docs/ARCHITECTURE_AND_WORKFLOW.md Section 9

Naming Convention:
    {phase}_{YYYYMMDD}_{version}.json

    Examples:
    - baseline_20251214_v1.json
    - refactor_20251214_v2.json
    - comparison_20251215_v1.json

Directory Structure:
    tests/architecture/results/
    ├── baseline/           # Pre-refactor baseline results
    ├── refactor/           # During-refactor verification results
    ├── comparison/         # Post-refactor comparison results
    ├── benchmark/          # Performance benchmark results
    └── latest/             # Symlinks to most recent results per phase

Usage:
    # In tests
    def test_example(results_manager):
        result = {"test": "data", "passed": True}
        results_manager.save("baseline", "test_example", result)

    # From CLI
    pytest tests/architecture/ --save-results -v

    # Compare results
    python -c "from tests.architecture.results_manager import compare_results; compare_results('baseline', 'v1', 'v2')"
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class TestPhase(Enum):
    """Test phases from Section 9 of architecture doc"""
    BASELINE = "baseline"
    REFACTOR = "refactor"
    COMPARISON = "comparison"
    BENCHMARK = "benchmark"
    OBSERVABILITY = "observability"
    OTHER = "other"  # For unmarked architecture tests


@dataclass
class TestResult:
    """Individual test result"""
    test_name: str
    test_class: str
    test_file: str
    phase: str
    status: str  # passed, failed, skipped, error
    duration_ms: float
    timestamp: str
    details: Dict[str, Any]
    error_message: Optional[str] = None


@dataclass
class TestRunSummary:
    """Summary of a complete test run"""
    phase: str
    version: str
    date: str
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    total_duration_ms: float
    test_results: List[Dict]
    environment: Dict[str, Any]
    notes: str = ""


class ResultsManager:
    """
    Manages test result storage and comparison.

    Results are stored in tests/architecture/results/ with the following structure:
    - results/{phase}/{phase}_{date}_{version}.json
    - results/latest/{phase}_latest.json (symlink to most recent)
    """

    RESULTS_DIR = Path(__file__).parent / "results"

    def __init__(self, version: str = "v1"):
        """
        Initialize results manager.

        Args:
            version: Version tag for this test run (e.g., "v1", "v2", "pre-refactor")
        """
        self.version = version
        self.date = datetime.now().strftime("%Y%m%d")
        self.timestamp = datetime.now().isoformat()
        self._ensure_directories()
        self._current_run: Dict[str, List[TestResult]] = {}

    def _ensure_directories(self):
        """Create necessary directories"""
        for phase in TestPhase:
            phase_dir = self.RESULTS_DIR / phase.value
            phase_dir.mkdir(parents=True, exist_ok=True)

        # Latest symlinks directory
        latest_dir = self.RESULTS_DIR / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)

    def _get_filename(self, phase: str) -> str:
        """Generate filename with naming convention"""
        return f"{phase}_{self.date}_{self.version}.json"

    def _get_filepath(self, phase: str) -> Path:
        """Get full filepath for a phase result file"""
        return self.RESULTS_DIR / phase / self._get_filename(phase)

    def record_test(
        self,
        phase: str,
        test_name: str,
        test_class: str,
        test_file: str,
        status: str,
        duration_ms: float,
        details: Optional[Dict] = None,
        error_message: Optional[str] = None
    ):
        """
        Record a single test result.

        Args:
            phase: Test phase (baseline, refactor, comparison, benchmark)
            test_name: Name of the test function
            test_class: Name of the test class
            test_file: Name of the test file
            status: Test status (passed, failed, skipped, error)
            duration_ms: Test duration in milliseconds
            details: Additional test details/metrics
            error_message: Error message if test failed
        """
        if phase not in self._current_run:
            self._current_run[phase] = []

        result = TestResult(
            test_name=test_name,
            test_class=test_class,
            test_file=test_file,
            phase=phase,
            status=status,
            duration_ms=duration_ms,
            timestamp=datetime.now().isoformat(),
            details=details or {},
            error_message=error_message
        )

        self._current_run[phase].append(result)

    def save_phase_results(
        self,
        phase: str,
        notes: str = "",
        environment: Optional[Dict] = None
    ) -> Path:
        """
        Save all recorded results for a phase to disk.

        Args:
            phase: Test phase to save
            notes: Optional notes about this test run
            environment: Optional environment info

        Returns:
            Path to saved results file
        """
        if phase not in self._current_run:
            raise ValueError(f"No results recorded for phase: {phase}")

        results = self._current_run[phase]

        # Calculate summary stats
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        errors = sum(1 for r in results if r.status == "error")
        total_duration = sum(r.duration_ms for r in results)

        # Build environment info
        env_info = environment or {}
        env_info.update({
            "python_version": self._get_python_version(),
            "platform": self._get_platform(),
            "cwd": str(Path.cwd())
        })

        summary = TestRunSummary(
            phase=phase,
            version=self.version,
            date=self.date,
            timestamp=self.timestamp,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            total_duration_ms=total_duration,
            test_results=[asdict(r) for r in results],
            environment=env_info,
            notes=notes
        )

        # Save to file
        filepath = self._get_filepath(phase)
        with open(filepath, 'w') as f:
            json.dump(asdict(summary), f, indent=2)

        # Update latest symlink
        self._update_latest_symlink(phase, filepath)

        return filepath

    def _update_latest_symlink(self, phase: str, filepath: Path):
        """Update the 'latest' symlink for a phase"""
        latest_link = self.RESULTS_DIR / "latest" / f"{phase}_latest.json"

        # Remove existing symlink if present
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()

        # Create relative symlink
        relative_path = os.path.relpath(filepath, latest_link.parent)
        latest_link.symlink_to(relative_path)

    def load_results(self, phase: str, version: Optional[str] = None, date: Optional[str] = None) -> Optional[Dict]:
        """
        Load results for a phase.

        Args:
            phase: Test phase to load
            version: Specific version to load (default: latest)
            date: Specific date to load (default: today or latest)

        Returns:
            Results dictionary or None if not found
        """
        if version is None and date is None:
            # Load latest
            latest_link = self.RESULTS_DIR / "latest" / f"{phase}_latest.json"
            if latest_link.exists():
                with open(latest_link, 'r') as f:
                    return json.load(f)
            return None

        # Load specific version/date
        filename = f"{phase}_{date or self.date}_{version or self.version}.json"
        filepath = self.RESULTS_DIR / phase / filename

        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return None

    def list_results(self, phase: str) -> List[Dict]:
        """
        List all available results for a phase.

        Returns:
            List of {filename, date, version, filepath} dicts
        """
        phase_dir = self.RESULTS_DIR / phase
        if not phase_dir.exists():
            return []

        results = []
        for filepath in sorted(phase_dir.glob("*.json"), reverse=True):
            # Parse filename: {phase}_{date}_{version}.json
            parts = filepath.stem.split("_")
            if len(parts) >= 3:
                results.append({
                    "filename": filepath.name,
                    "date": parts[1],
                    "version": "_".join(parts[2:]),  # Handle versions with underscores
                    "filepath": str(filepath)
                })

        return results

    def compare_results(
        self,
        phase: str,
        version_a: str,
        version_b: str,
        date_a: Optional[str] = None,
        date_b: Optional[str] = None
    ) -> Dict:
        """
        Compare two result sets.

        Args:
            phase: Test phase to compare
            version_a: First version
            version_b: Second version
            date_a: Date for version_a (searches if not specified)
            date_b: Date for version_b (searches if not specified)

        Returns:
            Comparison report
        """
        results_a = self._find_and_load(phase, version_a, date_a)
        results_b = self._find_and_load(phase, version_b, date_b)

        if not results_a:
            raise ValueError(f"Results not found for {phase} {version_a}")
        if not results_b:
            raise ValueError(f"Results not found for {phase} {version_b}")

        return self._generate_comparison(results_a, results_b)

    def _find_and_load(self, phase: str, version: str, date: Optional[str] = None) -> Optional[Dict]:
        """Find and load results, searching by version if date not specified"""
        if date:
            return self.load_results(phase, version, date)

        # Search for version in available results
        available = self.list_results(phase)
        for result in available:
            if result["version"] == version:
                with open(result["filepath"], 'r') as f:
                    return json.load(f)

        return None

    def _generate_comparison(self, results_a: Dict, results_b: Dict) -> Dict:
        """Generate detailed comparison between two result sets"""
        # Use class::test_name as unique key to avoid collision between
        # tests with same name in different classes/files
        def get_test_key(r):
            return f"{r.get('test_class', 'NoClass')}::{r['test_name']}"

        tests_a = {get_test_key(r): r for r in results_a["test_results"]}
        tests_b = {get_test_key(r): r for r in results_b["test_results"]}

        all_tests = set(tests_a.keys()) | set(tests_b.keys())

        comparison = {
            "version_a": f"{results_a['date']}_{results_a['version']}",
            "version_b": f"{results_b['date']}_{results_b['version']}",
            "summary_a": {
                "passed": results_a["passed"],
                "failed": results_a["failed"],
                "skipped": results_a["skipped"],
                "total": results_a["total_tests"],
                "duration_ms": results_a["total_duration_ms"]
            },
            "summary_b": {
                "passed": results_b["passed"],
                "failed": results_b["failed"],
                "skipped": results_b["skipped"],
                "total": results_b["total_tests"],
                "duration_ms": results_b["total_duration_ms"]
            },
            "regressions": [],      # Tests that passed before but fail now
            "improvements": [],      # Tests that failed before but pass now
            "new_tests": [],         # Tests only in version_b
            "removed_tests": [],     # Tests only in version_a
            "status_changes": [],    # Any status change
            "performance_changes": []  # Significant duration changes (>50%)
        }

        for test_key in all_tests:
            in_a = test_key in tests_a
            in_b = test_key in tests_b

            if in_a and not in_b:
                comparison["removed_tests"].append(test_key)
            elif in_b and not in_a:
                comparison["new_tests"].append(test_key)
            else:
                test_a = tests_a[test_key]
                test_b = tests_b[test_key]

                # Status changes
                if test_a["status"] != test_b["status"]:
                    change = {
                        "test": test_key,
                        "before": test_a["status"],
                        "after": test_b["status"]
                    }
                    comparison["status_changes"].append(change)

                    if test_a["status"] == "passed" and test_b["status"] == "failed":
                        comparison["regressions"].append(change)
                    elif test_a["status"] == "failed" and test_b["status"] == "passed":
                        comparison["improvements"].append(change)

                # Performance changes (>50% slower or faster)
                if test_a["duration_ms"] > 0:
                    ratio = test_b["duration_ms"] / test_a["duration_ms"]
                    if ratio > 1.5 or ratio < 0.67:
                        comparison["performance_changes"].append({
                            "test": test_key,
                            "before_ms": test_a["duration_ms"],
                            "after_ms": test_b["duration_ms"],
                            "ratio": ratio,
                            "change": "slower" if ratio > 1 else "faster"
                        })

        # Overall assessment
        comparison["assessment"] = self._assess_comparison(comparison)

        return comparison

    def _assess_comparison(self, comparison: Dict) -> str:
        """Generate overall assessment of comparison"""
        if comparison["regressions"]:
            return f"REGRESSION: {len(comparison['regressions'])} test(s) regressed"
        elif comparison["improvements"]:
            return f"IMPROVED: {len(comparison['improvements'])} test(s) now passing"
        elif comparison["summary_b"]["passed"] >= comparison["summary_a"]["passed"]:
            return "STABLE: No regressions detected"
        else:
            return "NEEDS REVIEW: Some changes detected"

    @staticmethod
    def _get_python_version() -> str:
        """Get Python version"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    @staticmethod
    def _get_platform() -> str:
        """Get platform info"""
        import platform
        return f"{platform.system()} {platform.release()}"

    def clear_current_run(self):
        """Clear current run data"""
        self._current_run = {}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def save_test_results(
    phase: str,
    results: List[Dict],
    version: str = "v1",
    notes: str = ""
) -> Path:
    """
    Convenience function to save test results.

    Args:
        phase: Test phase (baseline, refactor, comparison, benchmark)
        results: List of test result dicts with keys: test_name, status, duration_ms, details
        version: Version tag
        notes: Optional notes

    Returns:
        Path to saved file
    """
    manager = ResultsManager(version=version)

    for result in results:
        manager.record_test(
            phase=phase,
            test_name=result.get("test_name", "unknown"),
            test_class=result.get("test_class", "unknown"),
            test_file=result.get("test_file", "unknown"),
            status=result.get("status", "unknown"),
            duration_ms=result.get("duration_ms", 0),
            details=result.get("details", {}),
            error_message=result.get("error_message")
        )

    return manager.save_phase_results(phase, notes=notes)


def compare_results(phase: str, version_a: str, version_b: str) -> Dict:
    """
    Convenience function to compare two result versions.

    Args:
        phase: Test phase to compare
        version_a: First version (e.g., "v1")
        version_b: Second version (e.g., "v2")

    Returns:
        Comparison report dict
    """
    manager = ResultsManager()
    return manager.compare_results(phase, version_a, version_b)


def list_available_results(phase: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    List all available results.

    Args:
        phase: Specific phase to list (or all if None)

    Returns:
        Dict of phase -> list of available results
    """
    manager = ResultsManager()

    if phase:
        return {phase: manager.list_results(phase)}

    return {p.value: manager.list_results(p.value) for p in TestPhase}


def print_comparison_report(comparison: Dict):
    """Pretty-print a comparison report"""
    print("\n" + "=" * 60)
    print("TEST RESULTS COMPARISON")
    print("=" * 60)
    print(f"\nComparing: {comparison['version_a']} -> {comparison['version_b']}")

    print(f"\nSummary A: {comparison['summary_a']['passed']}/{comparison['summary_a']['total']} passed")
    print(f"Summary B: {comparison['summary_b']['passed']}/{comparison['summary_b']['total']} passed")

    print(f"\nAssessment: {comparison['assessment']}")

    if comparison["regressions"]:
        print(f"\n--- REGRESSIONS ({len(comparison['regressions'])}) ---")
        for r in comparison["regressions"]:
            print(f"  - {r['test']}: {r['before']} -> {r['after']}")

    if comparison["improvements"]:
        print(f"\n--- IMPROVEMENTS ({len(comparison['improvements'])}) ---")
        for r in comparison["improvements"]:
            print(f"  + {r['test']}: {r['before']} -> {r['after']}")

    if comparison["new_tests"]:
        print(f"\n--- NEW TESTS ({len(comparison['new_tests'])}) ---")
        for t in comparison["new_tests"]:
            print(f"  + {t}")

    if comparison["removed_tests"]:
        print(f"\n--- REMOVED TESTS ({len(comparison['removed_tests'])}) ---")
        for t in comparison["removed_tests"]:
            print(f"  - {t}")

    if comparison["performance_changes"]:
        print(f"\n--- PERFORMANCE CHANGES ({len(comparison['performance_changes'])}) ---")
        for p in comparison["performance_changes"]:
            print(f"  {p['test']}: {p['before_ms']:.2f}ms -> {p['after_ms']:.2f}ms ({p['change']})")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Example usage
    print("Available results:")
    for phase, results in list_available_results().items():
        print(f"\n{phase}:")
        for r in results:
            print(f"  - {r['filename']}")
