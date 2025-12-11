"""
Test manager for LocalAgent.

High-level API for test operations - detection, execution, and reporting.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .detector import TestFrameworkDetector, TestFramework, FrameworkInfo
from .runner import TestRunner, TestResult, TestStatus, TestCase


@dataclass
class TestSummary:
    """Summary of test status for a project."""
    has_tests: bool = False
    frameworks: List[FrameworkInfo] = field(default_factory=list)
    total_test_files: int = 0
    last_result: Optional[TestResult] = None

    def get_overview(self) -> str:
        """Get human-readable overview."""
        if not self.has_tests:
            return "No tests detected in this project"

        parts = []
        for fw in self.frameworks:
            parts.append(f"- {fw.framework.name}: {len(fw.test_files)} test files")

        overview = f"Test Frameworks Detected:\n" + "\n".join(parts)

        if self.last_result:
            overview += f"\n\nLast Run: {self.last_result.get_summary()}"

        return overview


class TestManager:
    """
    High-level test management for LocalAgent.

    Provides a simple API for:
    - Detecting test frameworks
    - Running tests
    - Getting test status
    - Running tests before/after code changes

    Usage:
        manager = TestManager("/path/to/project")
        manager.detect()

        # Run all tests
        result = manager.run()
        print(result.get_summary())

        # Run specific file
        result = manager.run_file("tests/test_auth.py")

        # Run tests matching pattern
        result = manager.run_pattern("test_login")
    """

    def __init__(self, project_path: Optional[str] = None, timeout: int = 300):
        """
        Initialize test manager.

        Args:
            project_path: Path to project root (defaults to cwd)
            timeout: Test execution timeout in seconds
        """
        self.project_path = str(Path(project_path or os.getcwd()).resolve())
        self.detector = TestFrameworkDetector()
        self.runner = TestRunner(timeout=timeout)

        self._frameworks: List[FrameworkInfo] = []
        self._primary_framework: Optional[FrameworkInfo] = None
        self._last_result: Optional[TestResult] = None
        self._detected = False

    def detect(self, force: bool = False) -> List[FrameworkInfo]:
        """
        Detect test frameworks in the project.

        Args:
            force: Force re-detection even if already detected

        Returns:
            List of detected frameworks
        """
        if self._detected and not force:
            return self._frameworks

        self._frameworks = self.detector.detect(self.project_path)
        self._primary_framework = self._frameworks[0] if self._frameworks else None
        self._detected = True

        return self._frameworks

    @property
    def has_tests(self) -> bool:
        """Whether the project has tests."""
        if not self._detected:
            self.detect()
        return len(self._frameworks) > 0

    @property
    def frameworks(self) -> List[FrameworkInfo]:
        """Get detected frameworks."""
        if not self._detected:
            self.detect()
        return self._frameworks

    @property
    def primary_framework(self) -> Optional[FrameworkInfo]:
        """Get the primary test framework."""
        if not self._detected:
            self.detect()
        return self._primary_framework

    @property
    def last_result(self) -> Optional[TestResult]:
        """Get the last test result."""
        return self._last_result

    def run(
        self,
        framework: Optional[TestFramework] = None,
        verbose: bool = False,
    ) -> Optional[TestResult]:
        """
        Run all tests.

        Args:
            framework: Specific framework to use (defaults to primary)
            verbose: Include verbose output

        Returns:
            TestResult or None if no tests found
        """
        if not self._detected:
            self.detect()

        fw = self._get_framework(framework)
        if not fw:
            return None

        self._last_result = self.runner.run_tests(
            self.project_path,
            fw,
            verbose=verbose,
        )
        return self._last_result

    def run_file(
        self,
        test_file: str,
        framework: Optional[TestFramework] = None,
    ) -> Optional[TestResult]:
        """
        Run tests in a specific file.

        Args:
            test_file: Path to test file (relative to project root)
            framework: Specific framework to use

        Returns:
            TestResult or None if no framework found
        """
        if not self._detected:
            self.detect()

        fw = self._get_framework(framework)
        if not fw:
            return None

        self._last_result = self.runner.run_tests(
            self.project_path,
            fw,
            test_filter=test_file,
        )
        return self._last_result

    def run_pattern(
        self,
        pattern: str,
        framework: Optional[TestFramework] = None,
    ) -> Optional[TestResult]:
        """
        Run tests matching a pattern.

        Args:
            pattern: Test name pattern (e.g., "test_login", "auth")
            framework: Specific framework to use

        Returns:
            TestResult or None if no framework found
        """
        if not self._detected:
            self.detect()

        fw = self._get_framework(framework)
        if not fw:
            return None

        # Format pattern for different frameworks
        if fw.framework == TestFramework.PYTEST:
            filter_str = f"-k {pattern}"
        elif fw.framework in (TestFramework.JEST, TestFramework.VITEST):
            filter_str = f"--testNamePattern={pattern}"
        elif fw.framework == TestFramework.GO_TEST:
            filter_str = f"-run {pattern}"
        else:
            filter_str = pattern

        self._last_result = self.runner.run_tests(
            self.project_path,
            fw,
            test_filter=filter_str,
        )
        return self._last_result

    def run_affected(
        self,
        changed_files: List[str],
        framework: Optional[TestFramework] = None,
    ) -> Optional[TestResult]:
        """
        Run tests that might be affected by changed files.

        Args:
            changed_files: List of changed file paths
            framework: Specific framework to use

        Returns:
            TestResult or None
        """
        if not self._detected:
            self.detect()

        fw = self._get_framework(framework)
        if not fw:
            return None

        # Find test files that might be related to changed files
        related_tests = self._find_related_tests(changed_files, fw)

        if not related_tests:
            # Run all tests if we can't determine affected ones
            return self.run(framework=framework)

        # Run related tests
        test_filter = " ".join(related_tests)
        self._last_result = self.runner.run_tests(
            self.project_path,
            fw,
            test_filter=test_filter,
        )
        return self._last_result

    def get_summary(self) -> TestSummary:
        """Get a summary of test status."""
        if not self._detected:
            self.detect()

        total_files = sum(len(fw.test_files) for fw in self._frameworks)

        return TestSummary(
            has_tests=len(self._frameworks) > 0,
            frameworks=self._frameworks,
            total_test_files=total_files,
            last_result=self._last_result,
        )

    def get_test_files(self, framework: Optional[TestFramework] = None) -> List[str]:
        """Get list of test files."""
        if not self._detected:
            self.detect()

        if framework:
            for fw in self._frameworks:
                if fw.framework == framework:
                    return fw.test_files
            return []

        # Return all test files
        all_files = []
        for fw in self._frameworks:
            all_files.extend(fw.test_files)
        return list(set(all_files))

    def get_test_command(self, framework: Optional[TestFramework] = None) -> Optional[str]:
        """Get the command to run tests."""
        fw = self._get_framework(framework)
        return fw.test_command if fw else None

    def verify_changes(
        self,
        changed_files: List[str],
        run_before: bool = False,
    ) -> Dict[str, Any]:
        """
        Verify code changes by running tests.

        Args:
            changed_files: List of files that were changed
            run_before: Whether to run tests before changes (for comparison)

        Returns:
            Dict with verification results
        """
        result = {
            "has_tests": self.has_tests,
            "verified": False,
            "tests_passed": False,
            "result": None,
            "message": "",
        }

        if not self.has_tests:
            result["message"] = "No tests found in project"
            return result

        # Run affected tests
        test_result = self.run_affected(changed_files)
        if not test_result:
            result["message"] = "Could not run tests"
            return result

        result["result"] = test_result
        result["verified"] = True
        result["tests_passed"] = test_result.success
        result["message"] = test_result.get_summary()

        return result

    def _get_framework(self, framework: Optional[TestFramework]) -> Optional[FrameworkInfo]:
        """Get framework info by type or return primary."""
        if framework:
            for fw in self._frameworks:
                if fw.framework == framework:
                    return fw
            return None
        return self._primary_framework

    def _find_related_tests(
        self,
        changed_files: List[str],
        framework: FrameworkInfo,
    ) -> List[str]:
        """Find test files related to changed files."""
        related = []

        for changed_file in changed_files:
            # Get base name without extension
            base = Path(changed_file).stem

            # Look for corresponding test file
            for test_file in framework.test_files:
                test_base = Path(test_file).stem

                # Check various naming patterns
                if (
                    f"test_{base}" in test_base
                    or f"{base}_test" in test_base
                    or f"{base}.test" in test_file
                    or f"{base}.spec" in test_file
                ):
                    related.append(test_file)

        return list(set(related))

    def get_context_for_llm(self) -> str:
        """
        Get test context information for LLM.

        Returns a string summarizing test status that can be included
        in LLM context.
        """
        if not self._detected:
            self.detect()

        if not self._frameworks:
            return "No test framework detected in this project."

        parts = ["## Test Information\n"]

        for fw in self._frameworks:
            parts.append(f"**Framework:** {fw.framework.name}")
            parts.append(f"**Command:** `{fw.test_command}`")
            parts.append(f"**Test Files:** {len(fw.test_files)}")

            if fw.test_directory:
                parts.append(f"**Test Directory:** {fw.test_directory}")

            parts.append("")

        if self._last_result:
            parts.append("**Last Test Run:**")
            parts.append(self._last_result.get_summary())

            if self._last_result.failed > 0:
                parts.append("\n**Failed Tests:**")
                for tc in self._last_result.get_failed_tests()[:5]:
                    parts.append(f"- {tc.name}")
                    if tc.message:
                        parts.append(f"  Error: {tc.message[:200]}")

        return "\n".join(parts)
