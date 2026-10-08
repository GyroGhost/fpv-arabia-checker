"""جرّب الفحص بدون ديسكورد:  python test_local.py sample_diff.txt"""
import sys

from cli_parser import parse
from report import as_text
from rules import analyze

path = sys.argv[1] if len(sys.argv) > 1 else "sample_diff.txt"
with open(path, encoding="utf-8", errors="replace") as f:
    cfg = parse(f.read())
print(as_text(cfg, analyze(cfg)))
