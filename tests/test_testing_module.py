"""
Unit tests for the testing module.
These tests verify the testing framework detection and management works correctly.
"""
import os
import tempfile
import pytest

from interpreter_source.core.testing import (
    TestFrameworkDetector,
    TestManager,
    TestFramework,
)


class TestFrameworkDetection:
    """Tests for TestFrameworkDetector."""

    def test_detect_pytest_by_config(self):
        """Test detection of pytest by pytest.ini."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pytest.ini
            with open(os.path.join(tmpdir, "pytest.ini"), "w") as f:
                f.write("[pytest]\n")

            detector = TestFrameworkDetector()
            frameworks = detector.detect(tmpdir)

            assert len(frameworks) >= 1
            assert any(fw.framework == TestFramework.PYTEST for fw in frameworks)

    def test_detect_pytest_by_test_files(self):
        """Test detection of pytest by test file patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            with open(os.path.join(tmpdir, "test_example.py"), "w") as f:
                f.write("def test_something(): pass\n")

            detector = TestFrameworkDetector()
            frameworks = detector.detect(tmpdir)

            assert len(frameworks) >= 1
            pytest_fw = next((fw for fw in frameworks if fw.framework == TestFramework.PYTEST), None)
            assert pytest_fw is not None
            assert "test_example.py" in pytest_fw.test_files

    def test_detect_jest_by_config(self):
        """Test detection of Jest by jest.config.js."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create jest config
            with open(os.path.join(tmpdir, "jest.config.js"), "w") as f:
                f.write("module.exports = {};\n")
            # Create package.json (required)
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"devDependencies": {"jest": "^29.0.0"}}\n')

            detector = TestFrameworkDetector()
            frameworks = detector.detect(tmpdir)

            assert any(fw.framework == TestFramework.JEST for fw in frameworks)

    def test_detect_go_test(self):
        """Test detection of Go test framework."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create go.mod
            with open(os.path.join(tmpdir, "go.mod"), "w") as f:
                f.write("module example.com/test\n")

            detector = TestFrameworkDetector()
            frameworks = detector.detect(tmpdir)

            assert any(fw.framework == TestFramework.GO_TEST for fw in frameworks)

    def test_detect_no_tests(self):
        """Test detection when no tests are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = TestFrameworkDetector()
            frameworks = detector.detect(tmpdir)

            assert len(frameworks) == 0

    def test_skip_ignored_directories(self):
        """Test that ignored directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file in node_modules (should be ignored)
            node_modules = os.path.join(tmpdir, "node_modules")
            os.makedirs(node_modules)
            with open(os.path.join(node_modules, "test_example.py"), "w") as f:
                f.write("def test_something(): pass\n")

            detector = TestFrameworkDetector()
            frameworks = detector.detect(tmpdir)

            # Should not detect tests in node_modules
            assert len(frameworks) == 0


class TestTestManager:
    """Tests for TestManager."""

    def test_manager_initialization(self):
        """Test TestManager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TestManager(tmpdir)
            assert manager.project_path == os.path.abspath(tmpdir)

    def test_manager_has_tests_false(self):
        """Test has_tests property when no tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TestManager(tmpdir)
            assert manager.has_tests == False

    def test_manager_has_tests_true(self):
        """Test has_tests property when tests exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            with open(os.path.join(tmpdir, "test_example.py"), "w") as f:
                f.write("def test_something(): pass\n")

            manager = TestManager(tmpdir)
            assert manager.has_tests == True

    def test_manager_get_test_files(self):
        """Test get_test_files method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            with open(os.path.join(tmpdir, "test_one.py"), "w") as f:
                f.write("def test_one(): pass\n")
            with open(os.path.join(tmpdir, "test_two.py"), "w") as f:
                f.write("def test_two(): pass\n")

            manager = TestManager(tmpdir)
            files = manager.get_test_files()

            assert len(files) == 2
            assert "test_one.py" in files
            assert "test_two.py" in files

    def test_manager_get_test_command(self):
        """Test get_test_command method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            with open(os.path.join(tmpdir, "test_example.py"), "w") as f:
                f.write("def test_something(): pass\n")

            manager = TestManager(tmpdir)
            manager.detect()  # Need to detect first
            command = manager.get_test_command()

            assert command == "pytest"

    def test_manager_get_summary(self):
        """Test get_summary method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TestManager(tmpdir)
            summary = manager.get_summary()

            assert summary.has_tests == False

    def test_manager_detect_called_automatically(self):
        """Test that detect is called automatically when needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test_auto.py"), "w") as f:
                f.write("def test_auto(): pass\n")

            manager = TestManager(tmpdir)
            # Don't call detect manually, just access has_tests
            assert manager.has_tests == True
            # Detection should have been triggered
            assert manager._detected == True


class TestTestResult:
    """Tests for TestResult class."""

    def test_result_success(self):
        """Test TestResult success property."""
        from interpreter_source.core.testing.runner import TestResult, TestStatus

        result = TestResult(
            framework=TestFramework.PYTEST,
            status=TestStatus.PASSED,
            total=5,
            passed=5,
            failed=0,
        )
        assert result.success == True

    def test_result_failure(self):
        """Test TestResult with failures."""
        from interpreter_source.core.testing.runner import TestResult, TestStatus

        result = TestResult(
            framework=TestFramework.PYTEST,
            status=TestStatus.FAILED,
            total=5,
            passed=3,
            failed=2,
        )
        assert result.success == False

    def test_result_summary(self):
        """Test TestResult get_summary method."""
        from interpreter_source.core.testing.runner import TestResult, TestStatus

        result = TestResult(
            framework=TestFramework.PYTEST,
            status=TestStatus.PASSED,
            total=10,
            passed=10,
            failed=0,
            duration=1.5,
        )
        summary = result.get_summary()

        assert "PASSED" in summary
        assert "10/10" in summary
        assert "1.5" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
