from __future__ import annotations

import json

from core.config_registry import validate_registry


def main() -> int:
    result = validate_registry()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
