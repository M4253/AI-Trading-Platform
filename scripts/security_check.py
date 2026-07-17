#!/usr/bin/env python3
"""Fast offline security/configuration checks for the repository.

This complements dependency tooling. It intentionally scans only tracked files
and never prints matching contents, so a positive finding does not re-expose a
potential secret in command output.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATTERNS = {
    'AWS access key': re.compile(rb'AKIA[0-9A-Z]{16}'),
    'GitHub personal token': re.compile(rb'ghp_[A-Za-z0-9]{20,}'),
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}
GENERATED_SUFFIXES = ('.pyc', '.tsbuildinfo')
REQUIRED_IGNORED = ('.env', '.env.production', 'backend/data/trading.db', 'backend/data/broker_settings.db')


def git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(['git', *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def main() -> int:
    failures: list[str] = []
    tracked = [Path(item) for item in git('ls-files', '-z').stdout.decode('utf-8').split('\0') if item]
    for path in tracked:
        if path.name.endswith(GENERATED_SUFFIXES) or '.next' in path.parts or '__pycache__' in path.parts:
            failures.append(f'tracked generated artifact: {path}')
            continue
        absolute = ROOT / path
        if not absolute.is_file() or absolute.stat().st_size > 5_000_000:
            continue
        content = absolute.read_bytes()
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(content):
                failures.append(f'possible {label} in tracked file: {path}')
    for target in REQUIRED_IGNORED:
        if git('check-ignore', '-q', target).returncode != 0:
            failures.append(f'required ignored path is not excluded: {target}')

    ibkr = (ROOT / 'backend/broker/ibkr_broker.py').read_text(encoding='utf-8')
    if 'IBKR order execution is disabled' not in ibkr or 'self.paper = True' not in ibkr:
        failures.append('IBKR paper-only lock was not detected')

    if failures:
        print('SECURITY CHECK: FAIL')
        for failure in failures:
            print(f'- {failure}')
        return 1
    print(f'SECURITY CHECK: PASS ({len(tracked)} tracked files scanned; no high-confidence credential markers)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
