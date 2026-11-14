#!/usr/bin/env bash
# Keep the compile-time contract targets out of the instrumented coverage run.
#
# The shared coverage action runs workspace nextest with no filter argument, so
# the exclusion goes into the project's own nextest profile: `default-filter` is
# the set of tests `cargo nextest run` executes when the command line names
# none. Nothing is removed from the crate, so an explicit `[[test]]`
# declaration keeps pointing at a source file that still exists and the targets
# still compile; only their test functions are deselected.
#
# `make test`, `make coverage` and `make test-ui` are unaffected, because an
# explicit `-E` filter and an explicit profile each take precedence over
# `default-filter`.

set -euo pipefail

config=.config/nextest.toml
filter_expression='not binary(compile_*)'

shopt -s nullglob
targets=(tests/compile_*.rs)
if [ "${#targets[@]}" -eq 0 ]; then
  echo 'No compile-time UI targets (tests/compile_*.rs); coverage runs every test.'
  exit 0
fi

if [ ! -f "$config" ]; then
  echo "Excluding the compile-time UI targets needs $config, which is missing." >&2
  exit 1
fi

# `-I` isolates the interpreter from the checkout: the project directory is on
# neither sys.path nor PYTHONPATH, so a planted module cannot shadow the
# standard library import below.
python3 -I - "$config" "$filter_expression" <<'PY'
"""Add the compile-time UI exclusion to the default nextest profile."""

import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
filter_expression = sys.argv[2]
text = config_path.read_text(encoding="utf-8")
profile = tomllib.loads(text).get("profile", {}).get("default", {})
existing = profile.get("default-filter")
if existing == filter_expression:
    print(f"{config_path} already excludes the compile-time UI targets")
    raise SystemExit(0)
if existing is not None:
    print(
        f"{config_path} sets its own default-filter {existing!r}, so the",
        "coverage run would execute the compile-time UI targets outside the",
        "serialized group. Add the exclusion to that filter.",
        file=sys.stderr,
    )
    raise SystemExit(1)

header = "[profile.default]"
lines = text.splitlines(keepends=True)
for index, line in enumerate(lines):
    if line.strip() == header:
        lines.insert(index + 1, f'default-filter = "{filter_expression}"\n')
        break
else:
    print(f"{config_path} has no {header} table", file=sys.stderr)
    raise SystemExit(1)

updated = "".join(lines)
if tomllib.loads(updated)["profile"]["default"]["default-filter"] != filter_expression:
    print(f"{config_path} did not take the exclusion filter", file=sys.stderr)
    raise SystemExit(1)
config_path.write_text(updated, encoding="utf-8")
print(f"{config_path}: the default profile now excludes {filter_expression}")
PY