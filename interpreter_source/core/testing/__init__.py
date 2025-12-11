"""
Testing module for LocalAgent.

Provides test framework detection, discovery, execution, and result parsing.
Supports pytest, unittest, jest, mocha, and other common test frameworks.
"""

from .detector import TestFrameworkDetector, TestFramework
from .runner import TestRunner, TestResult, TestStatus
from .manager import TestManager

__all__ = [
    "TestFrameworkDetector",
    "TestFramework",
    "TestRunner",
    "TestResult",
    "TestStatus",
    "TestManager",
]
