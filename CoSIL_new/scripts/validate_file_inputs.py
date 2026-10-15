"""Require all benchmark file-level records before starting the function-level phase."""
import json
import os
from pathlib import Path
import sys
from datasets import load_from_disk

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
expected = {row["instance_id"] for row in load_from_disk(os.environ["COSIL_DATASET"])}
actual = [row["instance_id"] for row in rows]
if len(rows) != 300 or len(set(actual)) != 300 or set(actual) != expected:
    raise SystemExit("Need the same 300 unique file-level results before the function phase")
if any(not isinstance(row.get("found_files"), list) for row in rows):
    raise SystemExit("Missing found_files list in a file-level record")
print("Validated 300 unique file-level records from the new repository")
