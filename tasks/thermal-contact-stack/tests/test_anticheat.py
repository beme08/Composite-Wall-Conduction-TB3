from __future__ import annotations
import os, re, unittest
from pathlib import Path
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
SOURCE_FILES = sorted(list((APP_DIR / "thermal_stack").rglob("*.py")) + list((APP_DIR / "scripts").rglob("*.py")))
FORBIDDEN = [("hidden/verifier path", r"/tests\b|tests/fixtures|hidden_cases|reference_solver|/solution\b|/logs\b"), ("reward or verifier environment", r"reward\.txt|LOG_DIR|REWARD_FILE|RESULTS_PATH|HIDDEN_CASES_PATH"), ("encoded answer table", r"\b(?:base64|b64decode|urlsafe_b64decode|b85decode|a85decode|fromhex)\b"), ("network access", r"\b(?:socket|urllib|urllib3|requests|httpx|aiohttp|http\.client|ftplib)\b"), ("repository history access", r"\.git\b"), ("hardcoded hidden case id", r"\bh0(?:0[1-9]|1[0-2])_[a-z0-9_]+\b")]
def _all_source() -> str:
    return "\n".join(f"# >>> {p}\n{p.read_text(encoding='utf-8')}" for p in SOURCE_FILES)
class AntiCheatTests(unittest.TestCase):
    def test_app_source_present(self) -> None: self.assertTrue(SOURCE_FILES, f"no source files found under {APP_DIR}")
    def test_no_specific_cheat_routes_in_app_source(self) -> None:
        text = _all_source(); failures = []
        for label, pattern in FORBIDDEN:
            for match in re.finditer(pattern, text):
                prefix = text.rfind("# >>> ", 0, match.start()); line_end = text.find("\n", prefix); source = text[prefix:line_end] if prefix != -1 else "unknown source"; snippet = text[max(0, match.start() - 35):match.end() + 35]
                failures.append(f"{label}: {source}: ...{snippet!r}")
        self.assertFalse(failures, "\n".join(failures[:10]))
if __name__ == "__main__": unittest.main()
