"""
Test runner for LocalAgent.

Executes tests and parses results from various test frameworks.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

from .detector import TestFramework, FrameworkInfo


class TestStatus(Enum):
    """Status of a test or test run."""
    PASSED = auto()
    FAILED = auto()
    SKIPPED = auto()
    ERROR = auto()
    UNKNOWN = auto()


@dataclass
class TestCase:
    """Result of a single test case."""
    name: str
    status: TestStatus
    duration: float = 0.0
    file: Optional[str] = None
    line: Optional[int] = None
    message: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class TestResult:
    """Result of a test run."""
    framework: TestFramework
    status: TestStatus
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    test_cases: List[TestCase] = field(default_factory=list)
    output: str = ""
    command: str = ""

    @property
    def success(self) -> bool:
        """Whether all tests passed."""
        return self.failed == 0 and self.errors == 0

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        status_str = "PASSED" if self.success else "FAILED"
        parts = [f"{status_str}: {self.passed}/{self.total} tests passed"]

        if self.failed > 0:
            parts.append(f"{self.failed} failed")
        if self.skipped > 0:
            parts.append(f"{self.skipped} skipped")
        if self.errors > 0:
            parts.append(f"{self.errors} errors")

        parts.append(f"in {self.duration:.2f}s")

        return " | ".join(parts)

    def get_failed_tests(self) -> List[TestCase]:
        """Get list of failed test cases."""
        return [t for t in self.test_cases if t.status in (TestStatus.FAILED, TestStatus.ERROR)]


class TestRunner:
    """
    Runs tests and parses results.

    Usage:
        runner = TestRunner()
        result = runner.run_tests("/path/to/project", framework_info)
        print(result.get_summary())
    """

    def __init__(self, timeout: int = 300):
        """
        Initialize test runner.

        Args:
            timeout: Maximum time in seconds for test execution
        """
        self.timeout = timeout

    def run_tests(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str] = None,
        verbose: bool = False,
    ) -> TestResult:
        """
        Run tests for a project.

        Args:
            project_path: Path to the project root
            framework: Framework info from detector
            test_filter: Optional filter to run specific tests
            verbose: Whether to include verbose output

        Returns:
            TestResult with parsed results
        """
        if framework.framework == TestFramework.PYTEST:
            return self._run_pytest(project_path, framework, test_filter, verbose)
        elif framework.framework == TestFramework.JEST:
            return self._run_jest(project_path, framework, test_filter, verbose)
        elif framework.framework == TestFramework.VITEST:
            return self._run_vitest(project_path, framework, test_filter, verbose)
        elif framework.framework == TestFramework.GO_TEST:
            return self._run_go_test(project_path, framework, test_filter, verbose)
        elif framework.framework == TestFramework.CARGO_TEST:
            return self._run_cargo_test(project_path, framework, test_filter, verbose)
        else:
            return self._run_generic(project_path, framework, test_filter, verbose)

    def run_single_file(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_file: str,
    ) -> TestResult:
        """Run tests in a single file."""
        return self.run_tests(project_path, framework, test_filter=test_file)

    def _run_command(
        self,
        command: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=full_env,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Test execution timed out after {self.timeout}s"
        except FileNotFoundError as e:
            return -1, "", f"Command not found: {e}"
        except Exception as e:
            return -1, "", f"Error running tests: {e}"

    def _run_pytest(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str],
        verbose: bool,
    ) -> TestResult:
        """Run pytest and parse results."""
        # Create temp file for JSON report
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_report = f.name

        cmd = [
            "python", "-m", "pytest",
            f"--json-report-file={json_report}",
            "--json-report",
            "-q",
        ]

        if verbose:
            cmd.append("-v")

        if test_filter:
            cmd.append(test_filter)

        exit_code, stdout, stderr = self._run_command(cmd, project_path)

        # Parse JSON report if available
        result = TestResult(
            framework=TestFramework.PYTEST,
            status=TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED,
            output=stdout + stderr,
            command=" ".join(cmd),
        )

        try:
            with open(json_report, "r") as f:
                report = json.load(f)
                result = self._parse_pytest_json(report, result)
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to parsing stdout
            result = self._parse_pytest_output(stdout + stderr, result)
        finally:
            try:
                os.unlink(json_report)
            except OSError:
                pass

        return result

    def _parse_pytest_json(self, report: Dict[str, Any], result: TestResult) -> TestResult:
        """Parse pytest JSON report."""
        summary = report.get("summary", {})

        result.total = summary.get("total", 0)
        result.passed = summary.get("passed", 0)
        result.failed = summary.get("failed", 0)
        result.skipped = summary.get("skipped", 0)
        result.errors = summary.get("error", 0)
        result.duration = report.get("duration", 0.0)

        # Parse individual tests
        for test in report.get("tests", []):
            status_map = {
                "passed": TestStatus.PASSED,
                "failed": TestStatus.FAILED,
                "skipped": TestStatus.SKIPPED,
                "error": TestStatus.ERROR,
            }

            test_case = TestCase(
                name=test.get("nodeid", ""),
                status=status_map.get(test.get("outcome", ""), TestStatus.UNKNOWN),
                duration=test.get("duration", 0.0),
            )

            # Extract failure info
            call = test.get("call", {})
            if call.get("longrepr"):
                test_case.traceback = call["longrepr"]

            result.test_cases.append(test_case)

        return result

    def _parse_pytest_output(self, output: str, result: TestResult) -> TestResult:
        """Parse pytest output when JSON is not available."""
        # Match summary line: "5 passed, 2 failed, 1 skipped in 1.23s"
        summary_match = re.search(
            r"(\d+) passed.*?(\d+) failed.*?in ([\d.]+)s",
            output,
            re.IGNORECASE,
        )
        if summary_match:
            result.passed = int(summary_match.group(1))
            result.failed = int(summary_match.group(2))
            result.duration = float(summary_match.group(3))
            result.total = result.passed + result.failed

        # Alternative: just passed
        passed_match = re.search(r"(\d+) passed.*?in ([\d.]+)s", output, re.IGNORECASE)
        if passed_match and not summary_match:
            result.passed = int(passed_match.group(1))
            result.total = result.passed
            result.duration = float(passed_match.group(2))

        return result

    def _run_jest(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str],
        verbose: bool,
    ) -> TestResult:
        """Run Jest and parse results."""
        cmd = ["npx", "jest", "--json"]

        if test_filter:
            cmd.extend(["--testPathPattern", test_filter])

        exit_code, stdout, stderr = self._run_command(cmd, project_path)

        result = TestResult(
            framework=TestFramework.JEST,
            status=TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED,
            output=stdout + stderr,
            command=" ".join(cmd),
        )

        # Parse JSON output
        try:
            # Jest outputs JSON to stdout
            report = json.loads(stdout)
            result = self._parse_jest_json(report, result)
        except json.JSONDecodeError:
            result = self._parse_jest_output(stdout + stderr, result)

        return result

    def _parse_jest_json(self, report: Dict[str, Any], result: TestResult) -> TestResult:
        """Parse Jest JSON output."""
        result.total = report.get("numTotalTests", 0)
        result.passed = report.get("numPassedTests", 0)
        result.failed = report.get("numFailedTests", 0)
        result.skipped = report.get("numPendingTests", 0)

        # Calculate duration from test results
        for test_result in report.get("testResults", []):
            for assertion in test_result.get("assertionResults", []):
                status_map = {
                    "passed": TestStatus.PASSED,
                    "failed": TestStatus.FAILED,
                    "pending": TestStatus.SKIPPED,
                }

                test_case = TestCase(
                    name=assertion.get("fullName", assertion.get("title", "")),
                    status=status_map.get(assertion.get("status", ""), TestStatus.UNKNOWN),
                    duration=assertion.get("duration", 0) / 1000,  # ms to s
                    file=test_result.get("name"),
                )

                if assertion.get("failureMessages"):
                    test_case.message = "\n".join(assertion["failureMessages"])

                result.test_cases.append(test_case)

        return result

    def _parse_jest_output(self, output: str, result: TestResult) -> TestResult:
        """Parse Jest output when JSON fails."""
        # Match: "Tests: 5 passed, 2 failed, 7 total"
        match = re.search(
            r"Tests:\s*(\d+)\s*passed.*?(\d+)\s*failed.*?(\d+)\s*total",
            output,
            re.IGNORECASE,
        )
        if match:
            result.passed = int(match.group(1))
            result.failed = int(match.group(2))
            result.total = int(match.group(3))

        return result

    def _run_vitest(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str],
        verbose: bool,
    ) -> TestResult:
        """Run Vitest and parse results."""
        cmd = ["npx", "vitest", "run", "--reporter=json"]

        if test_filter:
            cmd.append(test_filter)

        exit_code, stdout, stderr = self._run_command(cmd, project_path)

        result = TestResult(
            framework=TestFramework.VITEST,
            status=TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED,
            output=stdout + stderr,
            command=" ".join(cmd),
        )

        try:
            report = json.loads(stdout)
            # Vitest JSON format is similar to Jest
            result = self._parse_jest_json(report, result)
        except json.JSONDecodeError:
            pass

        return result

    def _run_go_test(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str],
        verbose: bool,
    ) -> TestResult:
        """Run Go tests and parse results."""
        cmd = ["go", "test", "-json", "./..."]

        if test_filter:
            cmd = ["go", "test", "-json", test_filter]

        exit_code, stdout, stderr = self._run_command(cmd, project_path)

        result = TestResult(
            framework=TestFramework.GO_TEST,
            status=TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED,
            output=stdout + stderr,
            command=" ".join(cmd),
        )

        # Parse JSON lines output
        passed = 0
        failed = 0
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            try:
                event = json.loads(line)
                action = event.get("Action")
                if action == "pass" and event.get("Test"):
                    passed += 1
                    result.test_cases.append(TestCase(
                        name=event.get("Test", ""),
                        status=TestStatus.PASSED,
                        duration=event.get("Elapsed", 0),
                    ))
                elif action == "fail" and event.get("Test"):
                    failed += 1
                    result.test_cases.append(TestCase(
                        name=event.get("Test", ""),
                        status=TestStatus.FAILED,
                        duration=event.get("Elapsed", 0),
                    ))
            except json.JSONDecodeError:
                continue

        result.passed = passed
        result.failed = failed
        result.total = passed + failed

        return result

    def _run_cargo_test(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str],
        verbose: bool,
    ) -> TestResult:
        """Run Cargo tests and parse results."""
        cmd = ["cargo", "test"]

        if test_filter:
            cmd.append(test_filter)

        cmd.append("--")
        cmd.append("--format=json")
        cmd.append("-Z")
        cmd.append("unstable-options")

        exit_code, stdout, stderr = self._run_command(cmd, project_path)

        result = TestResult(
            framework=TestFramework.CARGO_TEST,
            status=TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED,
            output=stdout + stderr,
            command=" ".join(cmd),
        )

        # Fallback to parsing text output
        match = re.search(r"(\d+) passed.*?(\d+) failed", stdout + stderr)
        if match:
            result.passed = int(match.group(1))
            result.failed = int(match.group(2))
            result.total = result.passed + result.failed

        return result

    def _run_generic(
        self,
        project_path: str,
        framework: FrameworkInfo,
        test_filter: Optional[str],
        verbose: bool,
    ) -> TestResult:
        """Run tests using the framework's command."""
        cmd = framework.test_command.split()

        if test_filter:
            cmd.append(test_filter)

        exit_code, stdout, stderr = self._run_command(cmd, project_path)

        return TestResult(
            framework=framework.framework,
            status=TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED,
            output=stdout + stderr,
            command=" ".join(cmd),
        )
