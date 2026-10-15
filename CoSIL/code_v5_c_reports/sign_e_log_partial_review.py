"""Sign a source-only review of the first ten staged TRAIN e_log samples.

The review decisions below were made from the complete issue, archived base Git
source, actual old graph and actual cached runner evidence. This script anchors
that review; it never runs source tests, imports a model, or changes sample labels.
"""
from collections import Counter, deque
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/v5_pruner/C_preconstruction_actual"
WIT = BASE / "e_log_source_witnesses"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


REVIEWS = {
    1: ("retained_limited_evidence", False,
        "候选只把具名 constraints 项交给 _remove_option；真实入口 RemoveConstraint.state_forwards 也明确操作 constraints。issue 则是 ForeignKey 改 ManyToManyField 并删除 unique_together，金标 _generate_added_field 修的是迁移依赖。AlterUniqueTogether 的 state_forwards 实际调用 alter_model_options，以 unique_together 为键，不调用 remove_constraint。已核完整候选、金标、相关操作类和 base Git，没有找到此 issue 配置下候选参与该金标流程的证据，因此保留为证据有限的负例。整题运行时证据不合格，候选未被观察到不能证明无关；这里既不认证零噪声，也不把名称中的 constraint 与独立 constraints API 混为同一机制。"),
    2: ("retained_limited_evidence", False,
        "get_scope_node 返回给定 scope 对应的父 collector，不读取/改写 fixturedef.scope，也不输出 --fixtures 文本。金标 _showfixtures_main 在 perform_collect 后遍历 session._fixturemanager._arg2fixturedefs，并打印 fixturedef 的名称/文档；补丁增加已有 fixturedef.scope 的显示。已继续核两个实际调用路径：高作用域直接参数化把伪 FixtureDef 写入 metafunc._arg2fixturedefs 和 node._name2pseudofixturedef，而不是金标遍历的 FixtureManager 字典；真正注册进该字典的是 parsefactories 中以 marker.scope 构造的 FixtureDef，构造函数本身也不调用 get_scope_node。另一调用来自 FixtureRequest._getscopeitem，是执行时选择 scope 节点。没有核得候选供给该显示缺失的具体源码链，保留有限证据负例；perform_collect 在其他参数化场景可能执行该辅助函数，因此不能宣称任何 --fixtures 运行都不会经过它。旧 FTP 为 setup/teardown 异常，运行时缺席不是排除证明。"),
    3: ("retained_limited_evidence", False,
        "候选 _alter_many_to_many 调整已有 M2M 中间表及其端点；schema.alter_field 只有 old_type/new_type 均为 None 且两个自动生成 through 表存在时才调用它。issue 从普通 ForeignKey 改为 ManyToManyField，base autodetector.generate_altered_fields 对一端 M2M 一端 concrete 的情况明确走 _generate_removed_field 后 _generate_added_field，而不是 AlterField。新增自动 through 的 add_field 分支又直接 create_model。故已核得该 issue 类型转换流程与候选调用条件不相符，未发现它参与金标依赖排序的链路，保留有限证据负例。整题旧运行证据不完整，未观察到候选不作为无关证明；若另有旧/新双方均 M2M 的操作则需重新判断，当前 issue 没有该前提。"),
    4: ("retained_limited_evidence", False,
        "候选是 Operation.state_forwards 抽象桩，唯一执行语句为抛 NotImplementedError，要求具体子类实现。issue 展示的是 CreateModel、AddIndex、AlterOrderWithRespectTo 的生成顺序，金标 _detect_changes/generate_created_models 调整后两者的排序。已核 CreateModel.state_forwards 与 AlterOrderWithRespectTo.state_forwards 均提供实际实现，不回调抽象桩；迁移中 operation.state_forwards 的动态调用应落到具体 override，不能仅因接口名称相同就声称执行了基类此函数体。金标后续优化调用的是 operation.reduce，也不是该桩。没有 issue 自定义子类漏实现的证据，保留有限证据负例。旧运行覆盖不合格，不能凭未进入桩证明全局无关；这里明确区分抽象接口与候选的物理 def 函数体。"),
    5: ("conditional_risk", True,
        "候选 get_items 自身不设置模块模板 ns['members']，金标实际以 dir(obj) 设置 members 后 template.render；直接生成错误 stub 的根因在金标，不能把候选写成同一个修复点。仍有具体条件数据流：issue 给出的自定义模板把 members 中各项写进 generated/example.rst 的 .. autosummary::；generate_autosummary_docs 在 base 源码中确实写出金标返回的内容，扩展将 autosummary 指令注册为 Autosummary，其 run 从 self.content 提取 names 并调用该候选。当这个生成文件作为 Sphinx 文档被继续解析时，候选便消费包含误收 imported member 的 names。这个关联依赖后续文档解析，旧 trace 没有候选 entry，整题 runtime 又不合格，因而只签条件风险，不宣称该 FTP 或原 issue 实际执行到了候选，更不宣称它造成成员过滤 bug。为避免把有明确下游相关路径的函数硬标不相关，本条保守判 unsafe E，应从 TRAIN 中剔除，不能转造成正例。"),
    6: ("confirmed_source_relation", True,
        "AssertionRewriter 实际继承 ast.NodeVisitor。候选 visit_Assert 在 843 行 self.visit(assert_.test)，Python 3.9 的真实 NodeVisitor.visit 以节点类型拼 visit_Call 并 getattr 动态分派；base 类源码又在 Python>=3.5 条件下明确把 visit_Call 绑定到金标 visit_Call_35，旧版本绑定另一个金标 visit_Call_legacy。issue 的 assert all/any(...) 正是 Call 节点，因此候选是金标改写路径的明确上游；静态图看不到 getattr/方法别名并不能证无关。已有真实旧 trace 也同时记录 bootstrap 与 test_unroll_expression 上下文进入候选。这里只确认源码/实际 entry 关联，entry 不等于因果致错证明。全题旧 coverage 因 legacy 金标等未完整进入而不合格，保留其历史状态，不借单条 entry 升级全题资格。该 E 不安全，应剔 TRAIN，不能自动补正标签。"),
    7: ("confirmed_source_relation", True,
        "候选 Media.__add__ 把双方 _css_lists/_js_lists 合并到返回的 Media 对象；金标 _css/_js 属性直接消费这两个列表并调用金标 merge。issue 明确描述 ColorPicker().media + SimpleTextWidget().media 等加法顺序影响三对象归并，所以存在对象状态生产者→金标消费者的实在数据流，而不仅是同文件/相似函数名。旧 raw trace 中 merge_js_three_way、merge_css_three_way、combine_media 等失败测试上下文确实进入 __add__，没有把 bootstrap 当失败路径。静态 call 图只见 Media() 构造，遗漏的是属性写入/读取的数据流。确认关联不等于证明 __add__ 自身有 bug 或应被补丁修改；整题 FTP 不齐的 runtime 仍不合格。本条不能作为不相关 E，剔 TRAIN 而不转造正例。"),
    8: ("conditional_risk", True,
        "MatrixElement.doit 最终对 args[0] 执行 [i,j] 索引；MatrixElement.__new__ 可保留一般 MatrixExpr parent，BlockMatrix 又实际继承 MatrixExpr，其 __getitem__ 在合法索引时动态调用 self._entry，落到金标 BlockMatrix._entry。因此若一个未求值 MatrixElement 的 parent 为 BlockMatrix，特别是 doit(deep=False) 保留 parent 时，候选确有到金标的明确条件调用链。必须限定：issue 展示的 C[i,0] 是直接索引，base 的错误 _entry 会先返回 A 的元素，并不自动证明候选 doit 被运行；本题全部 FTP 实际失败且完整金标覆盖的合格缓存也没有观察到候选。故不签实际失败因果，只按保守不安全 E 签条件风险、剔 TRAIN。即使失败路径缺席，另一合法 parent/调用入口下的动态分派关系仍存在；这不是把 runtime 缺席当零风险，也不是补造正例标签。"),
    9: ("confirmed_source_relation", True,
        "候选 ModelBase._prepare 333 行实际调用 opts._prepare(cls)；Options._prepare 在无显式/继承主键时调用 _get_default_pk_class，该 helper 对导入的 pk_class 执行 issubclass(pk_class, AutoField)。AutoField 实际由 AutoFieldMeta 作为 metaclass，因而进入金标 __subclasscheck__，其 base 实现只认 BigAutoField/SmallAutoField 本体而非其子类。issue 完整 traceback 逐帧列出这条 _prepare→Options._prepare→_get_default_pk_class 路径，真实旧 trace 也在测试 default_auto_field_setting_bigautofield_subclass 的上下文进入候选。这是多跳和 metaclass 动态机制，不能因静态图未连通而标无关。仅签关联与实际 entry，不把候选作为补丁函数；整题另一个 FTP 未收集使 coverage 仍不合格，历史资格不改。本条剔 TRAIN，不补正标签。"),
    10: ("confirmed_source_relation", True,
         "base autowrap 以 CYTHON 选择 CythonCodeWrapper，并先通过 code_gen.routine('autofunc',expr,args) 得到金标产生的 Routine，随后 code_wrapper.wrap_code(routine)→_prepare_files(routine)→dump_pyx([routine])→候选 _partition_args(routine.arguments)。金标在未出现在 expr 的额外 argument 上构造 InputArgument(symbol) 时丢失 dimensions；候选正检查这些同一 argument 对象的 arg.dimensions 来区分/推断数组维度，并返回后续 Python wrapper 所用的 py_args。故 issue 明确给出的 cython+未使用 MatrixSymbol 场景存在输入元数据沿 Routine 传递的源码数据流，不能用缺少直接 call edge 判不相关。旧缓存没有有效 FTP report、未观察到候选，因此不宣称实际测试跑通/执行到此处，也不声称候选本体是缺失 dimensions 的根因；确认的是真实源码关系。本条剔 TRAIN，不转造正例。"),
}

# Line ranges are in complete raw base Git modules, including auxiliary helpers.
SPANS = {
    1: [("django/db/migrations/state.py", 181, 188), ("django/db/migrations/state.py", 208, 238),
        ("django/db/migrations/operations/models.py", 533, 558), ("django/db/migrations/operations/models.py", 598, 607),
        ("django/db/migrations/operations/models.py", 1069, 1084)],
    2: [("src/_pytest/fixtures.py", 106, 168), ("src/_pytest/fixtures.py", 620, 633),
        ("src/_pytest/fixtures.py", 814, 840), ("src/_pytest/fixtures.py", 1280, 1300),
        ("src/_pytest/python.py", 1303, 1355)],
    3: [("django/db/backends/base/schema.py", 627, 633), ("django/db/backends/base/schema.py", 741, 778),
        ("django/db/backends/base/schema.py", 1241, 1272), ("django/db/migrations/autodetector.py", 1179, 1213)],
    4: [("django/db/migrations/operations/base.py", 54, 59), ("django/db/migrations/operations/models.py", 79, 87),
        ("django/db/migrations/operations/models.py", 572, 595), ("django/db/migrations/autodetector.py", 356, 370),
        ("django/db/migrations/optimizer.py", 40, 54)],
    5: [("sphinx/ext/autosummary/generate.py", 245, 257), ("sphinx/ext/autosummary/generate.py", 279, 290),
        ("sphinx/ext/autosummary/generate.py", 341, 386), ("sphinx/ext/autosummary/__init__.py", 238, 245),
        ("sphinx/ext/autosummary/__init__.py", 285, 327), ("sphinx/ext/autosummary/__init__.py", 750, 756),
        ("sphinx/ext/autosummary/__init__.py", 774, 776)],
    6: [("src/_pytest/assertion/rewrite.py", 608, 614), ("src/_pytest/assertion/rewrite.py", 814, 843),
        ("src/_pytest/assertion/rewrite.py", 967, 992), ("src/_pytest/assertion/rewrite.py", 1000, 1036)],
    7: [("django/forms/widgets.py", 61, 77), ("django/forms/widgets.py", 118, 156)],
    8: [("sympy/matrices/expressions/matexpr.py", 285, 298), ("sympy/matrices/expressions/matexpr.py", 696, 722),
        ("sympy/matrices/expressions/blockmatrix.py", 22, 26), ("sympy/matrices/expressions/blockmatrix.py", 235, 247)],
    9: [("django/db/models/base.py", 330, 333), ("django/db/models/options.py", 221, 250),
        ("django/db/models/options.py", 271, 287), ("django/db/models/fields/__init__.py", 2519, 2530)],
    10: [("sympy/utilities/autowrap.py", 136, 151), ("sympy/utilities/autowrap.py", 310, 317),
         ("sympy/utilities/autowrap.py", 363, 375), ("sympy/utilities/autowrap.py", 409, 437),
         ("sympy/utilities/autowrap.py", 616, 648), ("sympy/utilities/codegen.py", 695, 745),
         ("sympy/utilities/codegen.py", 862, 876)],
}


def reachable(edges, source, targets):
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["caller"], []).append(edge["callee"])
    queue = deque([(source, [source])])
    visited = {source}
    while queue:
        node, path = queue.popleft()
        if node in targets:
            return path
        for other in adjacency.get(node, []):
            if other not in visited:
                visited.add(other)
                queue.append((other, path + [other]))
    return None


def main():
    packet = BASE / "review_source_runtime_evidence_TRAIN30.json"
    samples_path = BASE / "human_review_pending_TRAIN30.jsonl"
    assert sha(packet) == "b68ecb051e256b17d0540c3f8a9c9ca52b603c1592ac2fb0c573b3056b561af2"
    assert sha(samples_path) == "c78b8a79f87adfc43897853aab910c63355404653b77b00703d6a41490eeef9f"
    audit_path = WIT / "source_binding_audit.json"
    assert sha(audit_path) == "a9bafee869783cd5465e5c1c234c4a8e229b0657b2e876d37f096e54aa8f2a5a"
    audit = json.loads(audit_path.read_text())
    records = json.loads(packet.read_text())["records"]
    samples = [json.loads(x) for x in samples_path.read_text().splitlines()]
    stdlib_origin = Path("/tmp/v5-runtime-python39/lib/python3.9/ast.py")
    stdlib_archive = WIT / "06_runtime_python39_stdlib_ast.py"
    with stdlib_archive.open("xb") as handle:
        handle.write(stdlib_origin.read_bytes())
    stdlib_lines = stdlib_archive.read_text().splitlines()
    stdlib_source = "\n".join(stdlib_lines[404:410]) + "\n"
    assert "visitor = getattr(self, method, self.generic_visit)" in stdlib_source
    assert "return visitor(node)" in stdlib_source
    reviewed = []
    for index, (case, record, sample) in enumerate(zip(audit["cases"], records, samples), 1):
        assert index <= 10 and case["index"] == index
        assert object_sha(record) == case["record_sha256"]
        assert object_sha(sample) == case["sample_sha256"]
        assert sample["label"] is False and sample["split"] == "train"
        assert case["identity"] == record["identity"]
        assert sha(case["graph_path"]) == case["graph_sha256"]
        assert sha(case["runtime_result_path"]) == case["runtime_result_sha256"]
        witnesses = []
        for file, first, last in SPANS[index]:
            module = case["modules"][file]
            assert sha(module["path"]) == module["sha256"]
            lines = Path(module["path"]).read_text().splitlines()
            assert last <= len(lines)
            source = "\n".join(lines[first - 1:last]) + "\n"
            witnesses.append({"source_file": file, **module, "start_line": first, "end_line": last,
                              "span_sha256": hashlib.sha256(source.encode()).hexdigest(), "source": source})
        if index == 6:
            witnesses.append({"source_file": "Python 3.9 stdlib ast.py (actual cached runner Python)",
                              "origin_path": str(stdlib_origin), "path": str(stdlib_archive),
                              "sha256": sha(stdlib_archive), "start_line": 405, "end_line": 410,
                              "span_sha256": hashlib.sha256(stdlib_source.encode()).hexdigest(), "source": stdlib_source,
                              "scope": "stdlib dynamic dispatch witness; not project base Git source"})
        for trace in case["candidate_entry_raw_trace_witnesses"]:
            assert sha(trace["trace_path"]) == trace["trace_sha256"]
        graph = json.loads(Path(case["graph_path"]).read_text())
        edges = graph["edges"]
        candidate = case["identity"]["function_id"]
        gold = list(record["gold"])
        graph_observation = {
            "graph_path": case["graph_path"], "graph_sha256": case["graph_sha256"],
            "candidate_incoming_edges": [x for x in edges if x["callee"] == candidate],
            "candidate_outgoing_edges": [x for x in edges if x["caller"] == candidate],
            "candidate_to_any_gold_static_path": reachable(edges, candidate, set(gold)),
            "gold_to_candidate_static_paths": {x: reachable(edges, x, {candidate}) for x in gold},
            "interpretation": "lexical direct-call graph observations only; missing path is not causal irrelevance proof",
        }
        classification, label_error, note = REVIEWS[index]
        reviewed.append({"index": index, "identity": case["identity"], **case["identity"],
                         "record_sha256": case["record_sha256"], "sample_sha256": case["sample_sha256"],
                         "base_commit": case["base_commit"], "relation_classification": classification,
                         "label_error": label_error, "review_note": note,
                         "input_label": False, "input_label_was_changed": False, "input_split": "train",
                         "proposed_handling": "exact TRAIN exclusion; no positive relabel" if label_error else "retain limited-evidence static negative",
                         "source_witnesses": witnesses, "full_candidate_and_gold_source_verified": True,
                         "issue_sha256": record["source_binding"]["issue_record_sha256"],
                         "gold_sha256": record["source_binding"]["gold_record_sha256"],
                         "source_binding_audit_path": str(audit_path), "source_binding_audit_sha256": sha(audit_path),
                         "graph_observation": graph_observation,
                         "runtime_observation": {k: case[k] for k in ["runtime_result_path", "runtime_result_sha256", "runtime_qualified", "candidate_in_failed_context", "candidate_in_bootstrap", "candidate_entry_raw_trace_witnesses"]},
                         "runtime_observation_limit": "Observed entry is not proof of bug cause; an unqualified whole issue remains unqualified. Entry absence is not proof of irrelevance."})
    assert len(reviewed) == 10
    out = {"status": "partial_source_review_signed_for_staged_packet_only", "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
           "reviewer": "Codex/机械证据逐条审阅（非真人核验签字）", "scope": "C new TRAIN30 #1–10 e_log; no input labels rewritten",
           "packet_path": str(packet), "packet_sha256": sha(packet), "samples_path": str(samples_path), "samples_sha256": sha(samples_path),
           "source_binding_audit_path": str(audit_path), "source_binding_audit_sha256": sha(audit_path),
           "review_script_path": str(Path(__file__).resolve()), "review_script_sha256": sha(__file__),
           "records": reviewed, "summary": {"reviewed": 10, "unsafe_E": sum(x["label_error"] for x in reviewed),
           "classifications": dict(Counter(x["relation_classification"] for x in reviewed)), "unsafe_indices": [x["index"] for x in reviewed if x["label_error"]]},
           "semantics": "label_error is the conservative unsafe-E review flag; conditional risk is not confirmed causal involvement or a new positive label. The 10 are selected audit cases, not a population noise estimate.",
           "final_raw_signature_condition": "Root must match these complete sample/record identities and canonical SHA against final actual packet/raw before creating final typed refs. This partial receipt does not cite a nonexistent final raw or freeze C training.",
           "new_tests_run": 0, "model_calls": 0, "gpu_used": False, "pruner_test_decoded": False, "input_labels_changed": False}
    target = BASE / "partial_review_e_log.json"
    with target.open("x") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"path": str(target), "sha256": sha(target), "summary": out["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
