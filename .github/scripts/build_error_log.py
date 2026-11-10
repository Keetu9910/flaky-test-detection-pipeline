#!/usr/bin/env python3
"""Builds error_log.csv: one row per project and tool, saying what happened.

An empty result can mean "no flaky tests" or "the tool never ran". This log tells
them apart, so every project in the run is accounted for.

Runs in the aggregate job after the artifacts are downloaded.
Usage: build_error_log.py <artifacts_dir> <flaky_tests.csv>
The list of projects comes from the MATRIX environment variable (the prepare job's output).
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_common import norm_module, norm_url

ART = sys.argv[1] if len(sys.argv) > 1 else "artifacts"
FLAKY_CSV = sys.argv[2] if len(sys.argv) > 2 else "flaky_tests.csv"
TOOLS = {"idflakies": ".dtfixingtools", "nondex": ".nondex", "flakesync": ".flakesync"}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Checked in this order; the first one found in the log is reported.
PATTERNS = [
    ("OUT_OF_MEMORY", r"OutOfMemoryError|GC overhead limit exceeded"),
    ("JAVA_VERSION_MISMATCH", r"invalid target release|Unsupported class file major version"
                              r"|UnsupportedClassVersionError|release version \d+ not supported"
                              r"|(Source|Target) option \d+ is no longer supported"),
    ("DEPENDENCY_RESOLUTION", r"Could not resolve dependencies|Could not find artifact"
                              r"|Could not transfer artifact|Non-resolvable parent POM"
                              r"|Failed to read artifact descriptor|Could not resolve plugin"),
    ("COMPILATION_ERROR", r"COMPILATION ERROR|Compilation failure"),
    ("PLUGIN_ERROR", r"No plugin found for prefix|Failed to execute goal edu\.(illinois|utexas)"),
    ("NO_TESTS_FOUND", r"No tests to run|No tests were executed"),
    ("BUILD_FAILURE", r"BUILD FAILURE"),
]


def find_dir(name):
    path = os.path.join(ART, name)
    return path if os.path.isdir(path) else None


def has_results(res_dir, marker):
    if not res_dir:
        return False
    for _root, dirs, _files in os.walk(res_dir):
        if marker in dirs:
            return True
    return False


def read_log(log_dir, tool):
    if not log_dir:
        return None
    for root, _dirs, files in os.walk(log_dir):
        if f"{tool}_log.txt" in files:
            with open(os.path.join(root, f"{tool}_log.txt"), errors="ignore") as fh:
                return ANSI.sub("", fh.read())
    return None


def first_problem(text):
    for category, pattern in PATTERNS:
        m = re.search(pattern, text)
        if m:
            start = text.rfind("\n", 0, m.start()) + 1
            end = text.find("\n", m.end())
            return category, text[start:end if end != -1 else None].strip()[:250]
    return None, ""


def timed_out(text):
    if "Time budget used up" in text:
        return True
    # Maven always prints "Total time:" when it finishes. If the last Maven run started
    # but never printed it, the run was killed (the time limit).
    return text.rfind("Scanning for projects") > text.rfind("Total time:")


# ---- projects in this run ----
try:
    matrix = json.loads(os.environ.get("MATRIX") or "{}").get("include", [])
except ValueError:
    matrix = []
if not matrix:   # fall back to the artifact names
    seen = set()
    for name in sorted(os.listdir(ART)) if os.path.isdir(ART) else []:
        m = re.match(r"^(idflakies|nondex|flakesync)-results-(.+)-([0-9a-f]{7,40})$", name)
        if m and (m.group(2), m.group(3)) not in seen:
            seen.add((m.group(2), m.group(3)))
            matrix.append({"repo_name": m.group(2), "sha": m.group(3)})
    print("::warning::MATRIX not available; projects were taken from the artifact names")

# ---- flaky tests per tool and project ----
flaky = {}
if os.path.exists(FLAKY_CSV):
    with open(FLAKY_CSV, newline="", encoding="utf-8", errors="ignore") as fh:
        for r in csv.DictReader(fh):
            key = ((r.get("Tool") or "").strip().lower(), norm_url(r.get("Project URL", "")),
                   (r.get("SHA Detected") or "").strip(), norm_module(r.get("Module Path", "")))
            flaky[key] = flaky.get(key, 0) + 1

rows = []
for m in matrix:
    repo_name, sha = m.get("repo_name", ""), m.get("sha", "")
    url, module = m.get("repo_url", ""), m.get("module_path", ".")
    tests_given = [t for t in (m.get("test_names") or "").split(",") if t.strip()]
    for tool, marker in TOOLS.items():
        res_dir = find_dir(f"{tool}-results-{repo_name}-{sha}")
        log = read_log(find_dir(f"{tool}_logs_{repo_name}_{sha}"), tool)
        produced = has_results(res_dir, marker)
        found = flaky.get((tool, norm_url(url), sha, norm_module(module)), 0)
        row = {"tool": tool, "project_url": url, "sha": sha, "module": module,
               "flaky_found": found, "tests_run": "", "warning": ""}

        if tool == "flakesync":
            if not tests_given:
                rows.append({**row, "status": "SKIPPED", "category": "NO_TEST_NAMES",
                             "detail": "IDoFT lists no test names for this project, so FlakeSync had nothing to run"})
                continue
            started = len(re.findall(r"^=== flakesync: \S+ \(main\) ===", log or "", re.M))
            row["tests_run"] = f"{started}/{len(tests_given)}"

        if log is None:
            if res_dir:
                detail = ("The tool never wrote a log: the job stopped at an earlier step "
                          "(install, Java setup or plugin build)")
                if tool == "idflakies":
                    detail += ", or iDFlakies was skipped because the project uses Java 11/17"
                rows.append({**row, "status": "ERROR", "category": "DETECTOR_DID_NOT_RUN",
                             "detail": detail + ". Open this job's log to see which step is red."})
            else:
                rows.append({**row, "status": "ERROR", "category": "JOB_FAILED_EARLY",
                             "detail": "No artifacts at all: the job failed before saving anything "
                                       "(for example the repository or commit could not be checked out)"})
            continue

        category, line = first_problem(log)
        if timed_out(log):
            rows.append({**row, "status": "PARTIAL" if produced else "ERROR", "category": "TIMEOUT",
                         "detail": "Hit the time limit" + (", results are from the runs that finished"
                                                           if produced else " before producing results")})
        elif produced:
            rows.append({**row, "status": "OK", "category": "NONE", "detail": "",
                         "warning": f"{category}: {line}" if category else ""})
        else:
            rows.append({**row, "status": "ERROR", "category": category or "NO_RESULTS",
                         "detail": line or f"The tool ran but wrote no {marker} folder; check its log"})

order = {"ERROR": 0, "PARTIAL": 1, "SKIPPED": 2, "OK": 3}
rows.sort(key=lambda r: (order[r["status"]], r["tool"], r["project_url"], r["module"]))

cols = ["tool", "project_url", "sha", "module", "status", "category", "detail",
        "flaky_found", "tests_run", "warning"]
with open("error_log.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

# ---- summary ----
lines = [f"Projects in this run: {len(matrix)}", "",
         f"{'Tool':<10} {'OK':>4} {'PARTIAL':>8} {'SKIPPED':>8} {'ERROR':>6}   OK but 0 flaky"]
for tool in TOOLS:
    mine = [r for r in rows if r["tool"] == tool]
    count = lambda s: sum(1 for r in mine if r["status"] == s)
    zero = sum(1 for r in mine if r["status"] == "OK" and r["flaky_found"] == 0)
    lines.append(f"{tool:<10} {count('OK'):>4} {count('PARTIAL'):>8} {count('SKIPPED'):>8} {count('ERROR'):>6}   {zero}")
problems = [r for r in rows if r["status"] in ("ERROR", "PARTIAL")]
lines += ["", "Problems:" if problems else "Problems: none"]
for r in problems:
    lines.append(f"  {r['status']:<7} {r['tool']:<9} {r['project_url']} ({r['module']}): {r['category']} - {r['detail']}")

text = "\n".join(lines) + "\n"
with open("error_summary.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as fh:
        fh.write("## Error log\n\n```\n" + text + "```\n")