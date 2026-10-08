"""جرّب الفحص بدون ديسكورد:  python test_local.py sample_diff.txt"""
import sys

from cli_parser import parse, parse_blackbox
from report import as_text
from rules import analyze

path = sys.argv[1] if len(sys.argv) > 1 else "sample_diff.txt"
if path.lower().endswith((".bbl", ".bfl")):
    with open(path, "rb") as f:
        cfg = parse_blackbox(f.read())
else:
    with open(path, encoding="utf-8", errors="replace") as f:
        cfg = parse(f.read())
print(as_text(cfg, analyze(cfg)))
