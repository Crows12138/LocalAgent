"""
Test framework detection for LocalAgent.

Automatically detects which test frameworks are used in a project.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum, auto


class TestFramework(Enum):
    """Supported test frameworks."""
    PYTEST = auto()
    UNITTEST = auto()
    NOSE = auto()
    JEST = auto()
    MOCHA = auto()
    VITEST = auto()
    GO_TEST = auto()
    CARGO_TEST = auto()
    JUNIT = auto()
    UNKNOWN = auto()


@dataclass
class FrameworkInfo:
    """Information about a detected test framework."""
    framework: TestFramework
    config_file: Optional[str] = None
    test_directory: Optional[str] = None
    test_command: str = ""
    test_files: List[str] = field(default_factory=list)


class TestFrameworkDetector:
    """
    Detects test frameworks used in a project.

    Usage:
        detector = TestFrameworkDetector()
        frameworks = detector.detect("/path/to/project")
        for info in frameworks:
            print(f"Found {info.framework.name}: {info.test_command}")
    """

    # Config files that indicate test frameworks
    FRAMEWORK_INDICATORS = {
        TestFramework.PYTEST: {
            "config_files": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
            "patterns": [r"\[tool\.pytest", r"\[pytest\]"],
        },
        TestFramework.JEST: {
            "config_files": ["jest.config.js", "jest.config.ts", "jest.config.mjs"],
            "package_json_keys": ["jest"],
        },
        TestFramework.VITEST: {
            "config_files": ["vitest.config.js", "vitest.config.ts", "vite.config.ts"],
            "package_json_keys": ["vitest"],
        },
        TestFramework.MOCHA: {
            "config_files": [".mocharc.js", ".mocharc.json", ".mocharc.yaml"],
            "package_json_keys": ["mocha"],
        },
        TestFramework.GO_TEST: {
            "config_files": ["go.mod"],
        },
        TestFramework.CARGO_TEST: {
            "config_files": ["Cargo.toml"],
        },
        TestFramework.JUNIT: {
            "config_files": ["pom.xml", "build.gradle", "build.gradle.kts"],
        },
    }

    # Test file patterns
    TEST_PATTERNS = {
        "python": [
            r"test_.*\.py$",
            r".*_test\.py$",
            r"tests?\.py$",
        ],
        "javascript": [
            r".*\.test\.[jt]sx?$",
            r".*\.spec\.[jt]sx?$",
            r"__tests__/.*\.[jt]sx?$",
        ],
        "go": [
            r".*_test\.go$",
        ],
        "rust": [
            r".*tests?\.rs$",
        ],
        "java": [
            r".*Test\.java$",
            r".*Tests\.java$",
        ],
    }

    def __init__(self):
        self.root_path: Optional[str] = None

    def detect(self, path: str) -> List[FrameworkInfo]:
        """
        Detect test frameworks in a project.

        Args:
            path: Path to the project root

        Returns:
            List of detected frameworks with their info
        """
        self.root_path = str(Path(path).resolve())
        frameworks = []

        # Check for Python test frameworks
        python_framework = self._detect_python_framework()
        if python_framework:
            frameworks.append(python_framework)

        # Check for JavaScript test frameworks
        js_framework = self._detect_js_framework()
        if js_framework:
            frameworks.append(js_framework)

        # Check for Go
        if self._file_exists("go.mod"):
            frameworks.append(self._create_go_info())

        # Check for Rust
        if self._file_exists("Cargo.toml"):
            frameworks.append(self._create_rust_info())

        # Check for Java
        java_framework = self._detect_java_framework()
        if java_framework:
            frameworks.append(java_framework)

        return frameworks

    def _file_exists(self, filename: str) -> bool:
        """Check if a file exists in the project root."""
        return os.path.exists(os.path.join(self.root_path, filename))

    def _read_file(self, filename: str) -> Optional[str]:
        """Read a file from the project root."""
        filepath = os.path.join(self.root_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            return None

    def _find_test_files(self, patterns: List[str]) -> List[str]:
        """Find test files matching patterns."""
        test_files = []
        # Directories to skip
        skip_dirs = {
            "node_modules", "venv", ".venv", "__pycache__",
            ".git", "dist", "build", ".pytest_cache", ".mypy_cache",
            ".ruff_cache", "site-packages", "eggs", ".eggs",
            # Skip other projects that might be in the directory
            "OpenHands", "openhands", ".claude",
        }
        for root, dirs, files in os.walk(self.root_path):
            # Skip common non-test directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            rel_root = os.path.relpath(root, self.root_path)
            for file in files:
                rel_path = os.path.join(rel_root, file) if rel_root != "." else file
                for pattern in patterns:
                    if re.search(pattern, rel_path):
                        test_files.append(rel_path)
                        break

        return test_files[:50]  # Limit to first 50

    def _find_test_directory(self) -> Optional[str]:
        """Find the main test directory."""
        common_dirs = ["tests", "test", "spec", "__tests__"]
        for dir_name in common_dirs:
            if os.path.isdir(os.path.join(self.root_path, dir_name)):
                return dir_name
        return None

    def _detect_python_framework(self) -> Optional[FrameworkInfo]:
        """Detect Python test framework."""
        # Check for pytest indicators
        pytest_configs = ["pytest.ini", "conftest.py"]
        for config in pytest_configs:
            if self._file_exists(config):
                return self._create_pytest_info(config)

        # Check pyproject.toml for pytest
        pyproject = self._read_file("pyproject.toml")
        if pyproject and "[tool.pytest" in pyproject:
            return self._create_pytest_info("pyproject.toml")

        # Check setup.cfg for pytest
        setup_cfg = self._read_file("setup.cfg")
        if setup_cfg and "[pytest]" in setup_cfg:
            return self._create_pytest_info("setup.cfg")

        # Check for test files - if found, assume pytest (most common)
        test_files = self._find_test_files(self.TEST_PATTERNS["python"])
        if test_files:
            return self._create_pytest_info(None, test_files)

        return None

    def _create_pytest_info(
        self, config_file: Optional[str], test_files: List[str] = None
    ) -> FrameworkInfo:
        """Create pytest framework info."""
        if test_files is None:
            test_files = self._find_test_files(self.TEST_PATTERNS["python"])

        test_dir = self._find_test_directory()

        return FrameworkInfo(
            framework=TestFramework.PYTEST,
            config_file=config_file,
            test_directory=test_dir,
            test_command="pytest",
            test_files=test_files,
        )

    def _detect_js_framework(self) -> Optional[FrameworkInfo]:
        """Detect JavaScript test framework."""
        # Check package.json
        package_json = self._read_file("package.json")
        if not package_json:
            return None

        import json
        try:
            pkg = json.loads(package_json)
        except json.JSONDecodeError:
            return None

        deps = {
            **pkg.get("dependencies", {}),
            **pkg.get("devDependencies", {}),
        }
        scripts = pkg.get("scripts", {})

        # Check for Vitest
        if "vitest" in deps or self._file_exists("vitest.config.ts"):
            return self._create_vitest_info()

        # Check for Jest
        if "jest" in deps or "jest" in pkg or self._file_exists("jest.config.js"):
            return self._create_jest_info()

        # Check for Mocha
        if "mocha" in deps:
            return self._create_mocha_info()

        # Check test script
        test_script = scripts.get("test", "")
        if "vitest" in test_script:
            return self._create_vitest_info()
        if "jest" in test_script:
            return self._create_jest_info()
        if "mocha" in test_script:
            return self._create_mocha_info()

        return None

    def _create_jest_info(self) -> FrameworkInfo:
        """Create Jest framework info."""
        test_files = self._find_test_files(self.TEST_PATTERNS["javascript"])
        config = None
        for cfg in ["jest.config.js", "jest.config.ts", "jest.config.mjs"]:
            if self._file_exists(cfg):
                config = cfg
                break

        return FrameworkInfo(
            framework=TestFramework.JEST,
            config_file=config,
            test_directory=self._find_test_directory(),
            test_command="npx jest",
            test_files=test_files,
        )

    def _create_vitest_info(self) -> FrameworkInfo:
        """Create Vitest framework info."""
        test_files = self._find_test_files(self.TEST_PATTERNS["javascript"])
        config = None
        for cfg in ["vitest.config.ts", "vitest.config.js", "vite.config.ts"]:
            if self._file_exists(cfg):
                config = cfg
                break

        return FrameworkInfo(
            framework=TestFramework.VITEST,
            config_file=config,
            test_directory=self._find_test_directory(),
            test_command="npx vitest run",
            test_files=test_files,
        )

    def _create_mocha_info(self) -> FrameworkInfo:
        """Create Mocha framework info."""
        test_files = self._find_test_files(self.TEST_PATTERNS["javascript"])

        return FrameworkInfo(
            framework=TestFramework.MOCHA,
            config_file=None,
            test_directory=self._find_test_directory(),
            test_command="npx mocha",
            test_files=test_files,
        )

    def _create_go_info(self) -> FrameworkInfo:
        """Create Go test framework info."""
        test_files = self._find_test_files(self.TEST_PATTERNS["go"])

        return FrameworkInfo(
            framework=TestFramework.GO_TEST,
            config_file="go.mod",
            test_directory=None,
            test_command="go test ./...",
            test_files=test_files,
        )

    def _create_rust_info(self) -> FrameworkInfo:
        """Create Rust test framework info."""
        test_files = self._find_test_files(self.TEST_PATTERNS["rust"])

        return FrameworkInfo(
            framework=TestFramework.CARGO_TEST,
            config_file="Cargo.toml",
            test_directory=None,
            test_command="cargo test",
            test_files=test_files,
        )

    def _detect_java_framework(self) -> Optional[FrameworkInfo]:
        """Detect Java test framework."""
        if self._file_exists("pom.xml"):
            return FrameworkInfo(
                framework=TestFramework.JUNIT,
                config_file="pom.xml",
                test_directory="src/test",
                test_command="mvn test",
                test_files=self._find_test_files(self.TEST_PATTERNS["java"]),
            )
        if self._file_exists("build.gradle") or self._file_exists("build.gradle.kts"):
            config = "build.gradle" if self._file_exists("build.gradle") else "build.gradle.kts"
            return FrameworkInfo(
                framework=TestFramework.JUNIT,
                config_file=config,
                test_directory="src/test",
                test_command="./gradlew test",
                test_files=self._find_test_files(self.TEST_PATTERNS["java"]),
            )
        return None

    def get_primary_framework(self, path: str) -> Optional[FrameworkInfo]:
        """
        Get the primary test framework for a project.

        Returns the first detected framework, prioritizing by language.
        """
        frameworks = self.detect(path)
        return frameworks[0] if frameworks else None
