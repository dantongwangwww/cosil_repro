"""Archive real Git/AST witnesses for the root's ten C anchor reviews.

This verifies preconstruction TRAIN evidence only. It does not create labels,
run tests, import a judge, or read a sealed pruner_test file.
"""
from pathlib import Path
import ast
import hashlib
import io
import json
import subprocess
import tokenize

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "results/v5_pruner/C_preconstruction_actual/review_source_runtime_evidence_TRAIN30.json"
OUTPUT = ROOT / "results/v5_pruner/C_preconstruction_actual/root_anchor_Git_AST_witnesses.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Definitions(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.nodes = {}

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.nodes[(".".join(self.scope + [node.name]), node.lineno)] = node
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def main():
    records = json.loads(PACKET.read_text())["records"]
    files = {}
    witnesses = []
    extras = {
        26: ["sympy/stats/crv.py", "sympy/stats/crv_types.py", "sympy/integrals/integrals.py", "sympy/integrals/meijerint.py", "sympy/integrals/transforms.py"],
        28: ["tests/settings_tests/tests.py", "django/test/testcases.py", "django/test/utils.py"],
        29: ["tests/test_utils/tests.py", "django/test/testcases.py", "django/test/utils.py"],
    }
    for index in range(20, 30):
        record = records[index]
        issue = record["source_binding"]["issue_record"]
        mirror = ROOT / "mirror_cache" / (issue["repo"].split("/")[-1] + ".git")
        expected = [record["candidate"], *record["gold"].values()]
        for filename in sorted({item["file"] for item in expected} | set(extras.get(index + 1, []))):
            key = issue["base_commit"] + ":" + filename
            if key not in files:
                prefix = ["git", "--git-dir", str(mirror)]
                blob = subprocess.run(prefix + ["rev-parse", key], capture_output=True, check=True).stdout.decode().strip()
                data = subprocess.run(prefix + ["cat-file", "blob", blob], capture_output=True, check=True).stdout
                encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
                source = data.decode(encoding)
                files[key] = {"repo": issue["repo"], "base_commit": issue["base_commit"], "file": filename,
                              "blob_sha1": blob, "file_sha256": sha(data), "source": source}
            file = files[key]
            definitions = Definitions()
            definitions.visit(ast.parse(file["source"]))
            lines = file["source"].splitlines(keepends=True)
            for item in expected:
                if item["file"] != filename:
                    continue
                qualified, line = item["function_id"].split("::", 1)[1].rsplit("@", 1)
                node = definitions.nodes[(qualified, int(line))]
                source = "".join(lines[node.lineno - 1:node.end_lineno])
                assert file["blob_sha1"] == item["base_blob_sha1"]
                assert source == item["full_source"]
                assert sha(source.encode()) == item["full_source_sha256"]
                witnesses.append({"review_index": index + 1, "instance_id": issue["instance_id"],
                                  "function_id": item["function_id"], "blob_sha1": file["blob_sha1"],
                                  "full_source_sha256": item["full_source_sha256"],
                                  "physical_def_line": node.lineno, "end_line": node.end_lineno,
                                  "candidate": item is record["candidate"]})
    result = {"status": "passed_real_Git_AST_root_anchor_sources", "packet_path": str(PACKET),
              "packet_sha256": sha(PACKET.read_bytes()), "checked_candidates": 10,
              "checked_function_witnesses": len(witnesses), "witnesses": witnesses, "base_files": files,
              "labels_created": False, "models_loaded": False, "tests_run": False, "sealed_test_decoded": False,
              "interpretation": "Source identity verification; review judgments and runtime/causal limitations are separate."}
    with OUTPUT.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(OUTPUT), "sha256": sha(OUTPUT.read_bytes()), "functions": len(witnesses)}))


if __name__ == "__main__":
    main()
