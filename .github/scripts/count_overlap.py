#!/usr/bin/env python3
"""Counts flaky tests found by iDFlakies, by NonDex, and by both.

Reads flaky_tests.csv (made by merge_rows.py) and writes overlap_summary.txt.
A test is identified by project URL + commit + module + test name, so the
same test name in two different projects counts as two tests.
"""
import csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_common import TEST_COL, norm_module, norm_test, norm_url

path = sys.argv[1] if len(sys.argv) > 1 else "flaky_tests.csv"
found = {"idflakies": set(), "nondex": set()}

if os.path.exists(path):
    with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
        for r in csv.DictReader(fh):
            tool = (r.get("Tool") or "").strip().lower()
            if tool in found and r.get(TEST_COL):
                found[tool].add((
                    norm_url(r.get("Project URL", "")),
                    (r.get("SHA Detected") or "").strip(),
                    norm_module(r.get("Module Path", "")),
                    norm_test(r[TEST_COL]),
                ))
else:
    print(f"::warning::{path} not found, so all counts are 0")

idf, ndx = found["idflakies"], found["nondex"]
both = sorted(idf & ndx)

lines = [
    f"iDFlakies flaky tests: {len(idf)}",
    f"NonDex flaky tests:    {len(ndx)}",
    f"Found by both:         {len(both)}",
    f"Found by either:       {len(idf | ndx)}",
    "",
]
if both:
    lines.append("Tests found by both tools:")
    lines += [f"  {url} | module {module} | {test}" for url, _sha, module, test in both]
else:
    lines.append("Tests found by both tools: none")

text = "\n".join(lines) + "\n"
with open("overlap_summary.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)

summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as fh:
        fh.write("## iDFlakies vs NonDex\n\n```\n" + text + "```\n")