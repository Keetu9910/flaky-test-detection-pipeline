#!/usr/bin/env python3
"""Picks the tests FlakeSync should run:  Z = N - (X ∪ Y)

N = tests that passed in a normal run of this module (read from surefire reports)
X = tests iDFlakies flagged for this project, Y = tests NonDex flagged
Z = everything left, i.e. the tests neither tool flagged

Usage: select_flakesync_candidates.py <module_dir> <rows_dir>
  rows_dir holds the iDFlakies/NonDex rows artifacts (idflakies.csv, nondex.csv).
Env: MAX_TESTS (default 30; 0 = no cap)
Prints test_names=... and skip_reason=... for $GITHUB_OUTPUT, and writes the
N / X / Y / Z numbers to the job summary.
"""
import csv, glob, os, re, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_common import TEST_COL, norm_test

module_dir, rows_dir = sys.argv[1], sys.argv[2]
max_tests = int(os.environ.get("MAX_TESTS") or 30)
log = lambda *a: print(*a, file=sys.stderr)

# Tests whose class mentions threads/async/timing go first, so the cap keeps the
# likeliest timing-dependent tests.
CONCURRENCY = re.compile(r"\b(Thread|Runnable|Executor\w*|CompletableFuture|Future|CountDownLatch|"
                         r"Semaphore|CyclicBarrier|synchronized|volatile|Atomic\w+|Awaitility|"
                         r"TimeUnit|ScheduledExecutorService)\b|Thread\.sleep|timeout\s*=")


def base(name):
    """pkg.Class.method[1] / method() / Class#method  ->  pkg.Class.method"""
    return re.split(r"[\[(]", norm_test(name), 1)[0].strip()


# ---- N: tests that passed in the baseline run ----
passed, failed = set(), set()
reports = glob.glob(os.path.join(module_dir, "**", "surefire-reports", "TEST-*.xml"), recursive=True)
for path in reports:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        continue
    for tc in root.iter("testcase"):
        cls, name = tc.get("classname", ""), tc.get("name", "")
        if not cls or not name:
            continue
        t = base(f"{cls}.{name}")
        kids = {c.tag for c in tc}
        if kids & {"failure", "error"}:
            failed.add(t)
        elif "skipped" not in kids:
            passed.add(t)
N = passed - failed


# ---- X and Y: what iDFlakies and NonDex flagged ----
def flagged(tool):
    out = set()
    for p in glob.glob(os.path.join(rows_dir, "**", f"{tool}.csv"), recursive=True):
        with open(p, newline="", errors="ignore") as fh:
            for r in csv.DictReader(fh):
                if r.get(TEST_COL):
                    out.add(base(r[TEST_COL]))
    return out


X, Y = flagged("idflakies"), flagged("nondex")
Z = N - (X | Y)


def mentions_concurrency(test):
    rel = test.rsplit(".", 1)[0].split("$")[0].replace(".", os.sep) + ".java"
    for src in glob.glob(os.path.join(module_dir, "**", rel), recursive=True):
        try:
            if CONCURRENCY.search(open(src, errors="ignore").read()):
                return True
        except OSError:
            pass
    return False


hint = {t: mentions_concurrency(t) for t in Z}
ranked = sorted(Z, key=lambda t: (not hint[t], t))
chosen = ranked[:max_tests] if max_tests > 0 else ranked

skip_reason = ""
if not reports:
    skip_reason = "the baseline test run produced no surefire reports, so N is unknown"
elif not chosen:
    skip_reason = "Z is empty: every passing test was already flagged by iDFlakies or NonDex"

summary = (f"N (tests passing in a normal run): {len(N)}\n"
           f"X (flagged by iDFlakies):          {len(X)}\n"
           f"Y (flagged by NonDex):             {len(Y)}\n"
           f"X and Y (flagged by both):         {len(X & Y)}\n"
           f"Z = N - (X or Y):                  {len(Z)}\n"
           f"  of which mention threads/timing: {sum(hint.values())}\n"
           f"FlakeSync will test:               {len(chosen)}"
           + (f" (capped at {max_tests})" if max_tests and len(Z) > max_tests else "") + "\n"
           + (f"Skipped: {skip_reason}\n" if skip_reason else ""))
log(summary)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
        fh.write("## FlakeSync test selection\n\n```\n" + summary + "```\n")

print("test_names=" + ",".join(t.rsplit(".", 1)[0] + "#" + t.rsplit(".", 1)[1] for t in chosen if "." in t))
print("skip_reason=" + skip_reason)