"""pytest 输出解析器"""

import re
from hatch.core.models import TestResult, TestError


class TestResultParser:

    @staticmethod
    def parse(text: str) -> TestResult:
        passed = len(re.findall(r"::(\w+)\s+PASSED", text))
        failed = len(re.findall(r"::(\w+)\s+FAILED", text))
        total = passed + failed
        if total == 0:
            total_match = re.search(r"collected\s+(\d+)\s+items?", text)
            pass_match = re.search(r"(\d+)\s+passed", text)
            fail_match = re.search(r"(\d+)\s+failed", text)
            if total_match:
                total = int(total_match.group(1))
            if pass_match:
                passed = int(pass_match.group(1))
            if fail_match:
                failed = int(fail_match.group(1))

        errors: list[TestError] = []
        fail_blocks = re.split(r"={5,}\s*FAILURES\s*={5,}", text)
        if len(fail_blocks) > 1:
            failures_text = fail_blocks[1]
            test_blocks = re.split(r"\n_+\s*\n", failures_text)
            for block in test_blocks:
                if not block.strip():
                    continue
                name_match = re.search(r"_+\s+(\w+)\s+_+", block)
                if not name_match:
                    continue
                test_name = name_match.group(1)
                err_type = "Unknown"
                msg = ""
                expected = None
                actual = None
                err_match = re.search(r"(\w+Error)\b", block)
                if err_match:
                    err_type = err_match.group(1)
                assert_match = re.search(r"assert\s+(.+?)\s*$", block, re.MULTILINE)
                if assert_match:
                    parts = assert_match.group(1).split("==")
                    if len(parts) == 2:
                        expected = parts[1].strip()
                        actual = parts[0].strip()
                errors.append(TestError(
                    test_name=test_name,
                    error_type=err_type,
                    message=block.strip()[:200],
                    file_path="",
                    expected=expected,
                    actual=actual,
                ))
        return TestResult(total=total, passed=passed, failed=failed, errors=errors)