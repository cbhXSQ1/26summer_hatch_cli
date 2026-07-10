"""flake8 输出解析器"""

import re
from hatch.core.models import LintResult, LintIssue


class LintResultParser:

    PATTERN = re.compile(r"(\S+):(\d+):(\d+):\s+(\w+)\s+(.+)")

    @staticmethod
    def parse(text: str) -> LintResult:
        issues: list[LintIssue] = []
        for line in text.strip().splitlines():
            if not line.strip():
                continue
            m = LintResultParser.PATTERN.match(line.strip())
            if m:
                issues.append(LintIssue(
                    file_path=m.group(1),
                    line=int(m.group(2)),
                    column=int(m.group(3)),
                    code=m.group(4),
                    message=m.group(5).strip(),
                ))
        return LintResult(issues=issues)