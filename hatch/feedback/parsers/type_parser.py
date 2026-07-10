"""mypy 输出解析器"""

import re
from hatch.core.models import TypeCheckResult, TypeCheckError


class TypeCheckParser:

    PATTERN = re.compile(r"(\S+):(\d+):\s*(error|note):\s*(.+)")

    @staticmethod
    def parse(text: str) -> TypeCheckResult:
        errors: list[TypeCheckError] = []
        for line in text.strip().splitlines():
            if not line.strip():
                continue
            m = TypeCheckParser.PATTERN.match(line.strip())
            if m:
                errors.append(TypeCheckError(
                    file_path=m.group(1),
                    line=int(m.group(2)),
                    column=0,
                    severity=m.group(3),
                    message=m.group(4).strip(),
                ))
        return TypeCheckResult(errors=errors)