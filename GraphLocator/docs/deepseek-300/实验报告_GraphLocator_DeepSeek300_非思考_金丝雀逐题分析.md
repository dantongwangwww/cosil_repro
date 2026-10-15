# GraphLocator DeepSeek-V4.1-Flash 金丝雀逐题分析

问题按固定 issue ID 对齐；空定位、失败、缺少结果、函数真值 NA 分别标记。预测是原始解析结果，不用真值回改。

## 1. astropy__astropy-12907

项目：`astropy/astropy`；base commit：`d16bfe05a744909de4b27f5875fe0d4ed41ce607`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "astropy/astropy/modeling/separable.py",
    "astropy/astropy/modeling/core.py"
  ],
  "found_modules": [
    "astropy/astropy/modeling/core.py::Model"
  ],
  "found_functions": [
    "astropy/astropy/modeling/separable.py::_compute_n_outputs",
    "astropy/astropy/modeling/core.py::Model.n_outputs",
    "astropy/astropy/modeling/core.py::Model.n_inputs",
    "astropy/astropy/modeling/separable.py::separability_matrix",
    "astropy/astropy/modeling/separable.py::_coord_matrix",
    "astropy/astropy/modeling/separable.py::_separable"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "astropy/modeling/separable.py",
      "_cstack"
    ]
  ],
  "predictions": [
    [
      "astropy/modeling/core.py",
      "Model.n_inputs"
    ],
    [
      "astropy/modeling/core.py",
      "Model.n_outputs"
    ],
    [
      "astropy/modeling/separable.py",
      "_compute_n_outputs"
    ],
    [
      "astropy/modeling/separable.py",
      "_coord_matrix"
    ],
    [
      "astropy/modeling/separable.py",
      "_separable"
    ],
    [
      "astropy/modeling/separable.py",
      "separability_matrix"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [
    [
      "astropy/modeling/core.py",
      "Model.n_inputs"
    ],
    [
      "astropy/modeling/core.py",
      "Model.n_outputs"
    ],
    [
      "astropy/modeling/separable.py",
      "_compute_n_outputs"
    ],
    [
      "astropy/modeling/separable.py",
      "_coord_matrix"
    ],
    [
      "astropy/modeling/separable.py",
      "_separable"
    ],
    [
      "astropy/modeling/separable.py",
      "separability_matrix"
    ]
  ],
  "missed_targets": [
    [
      "astropy/modeling/separable.py",
      "_cstack"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 116.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "因果收到目标实体但未保留",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "astropy/modeling/separable.py",
          "_cstack"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 14,
      "model_request": 14,
      "model_response": 14,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 13,
      "causal": 47
    },
    "predicted_function_count": 6,
    "seconds": 116.30815859511495
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 4
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 53987,
    "output": 9680
  }
}
```

## 2. django__django-11848

项目：`django/django`；base commit：`f0adf3b9b7a19cdee05368ff0c0c2d087f011180`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/http.py",
    "django/tests/utils_tests/test_http.py"
  ],
  "found_modules": [
    "django/tests/utils_tests/test_http.py::HttpDateProcessingTests"
  ],
  "found_functions": [
    "django/django/utils/http.py::parse_http_date",
    "django/tests/utils_tests/test_http.py::HttpDateProcessingTests.test_parsing_year_less_than_70"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/http.py",
      "parse_http_date"
    ]
  ],
  "predictions": [
    [
      "django/utils/http.py",
      "parse_http_date"
    ],
    [
      "tests/utils_tests/test_http.py",
      "HttpDateProcessingTests.test_parsing_year_less_than_70"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/utils/http.py",
      "parse_http_date"
    ]
  ],
  "false_positive": [
    [
      "tests/utils_tests/test_http.py",
      "HttpDateProcessingTests.test_parsing_year_less_than_70"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 95.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/utils/http.py",
          "parse_http_date"
        ]
      ],
      "seeds": [
        [
          "django/utils/http.py",
          "parse_http_date"
        ]
      ],
      "causal_received": [
        [
          "django/utils/http.py",
          "parse_http_date"
        ]
      ],
      "final": [
        [
          "django/utils/http.py",
          "parse_http_date"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 7,
      "model_request": 7,
      "model_response": 7,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 0,
      "causal": 7
    },
    "predicted_function_count": 2,
    "seconds": 95.24488079920411
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 13316,
    "output": 1097
  }
}
```

## 3. sympy__sympy-12481

项目：`sympy/sympy`；base commit：`c807dfe7569692cad24f02a08477b70c1679a4dd`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 16.67% | 100.00% | 28.57% | 命中 |

原始定位：

```json
{
  "found_files": [
    "sympy/sympy/combinatorics/permutations.py",
    "sympy/sympy/utilities/iterables.py",
    "sympy/sympy/core/compatibility.py"
  ],
  "found_modules": [
    "sympy/sympy/combinatorics/permutations.py::Cycle",
    "sympy/sympy/combinatorics/permutations.py::Permutation"
  ],
  "found_functions": [
    "sympy/sympy/combinatorics/permutations.py::Cycle.__init__",
    "sympy/sympy/combinatorics/permutations.py::Permutation.__new__",
    "sympy/sympy/utilities/iterables.py::has_dups",
    "sympy/sympy/utilities/iterables.py::flatten",
    "sympy/sympy/core/compatibility.py::is_sequence",
    "sympy/sympy/utilities/iterables.py::has_variety"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/combinatorics/permutations.py",
      "Permutation.__new__"
    ]
  ],
  "predictions": [
    [
      "sympy/combinatorics/permutations.py",
      "Cycle.__init__"
    ],
    [
      "sympy/combinatorics/permutations.py",
      "Permutation.__new__"
    ],
    [
      "sympy/core/compatibility.py",
      "is_sequence"
    ],
    [
      "sympy/utilities/iterables.py",
      "flatten"
    ],
    [
      "sympy/utilities/iterables.py",
      "has_dups"
    ],
    [
      "sympy/utilities/iterables.py",
      "has_variety"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "sympy/combinatorics/permutations.py",
      "Permutation.__new__"
    ]
  ],
  "false_positive": [
    [
      "sympy/combinatorics/permutations.py",
      "Cycle.__init__"
    ],
    [
      "sympy/core/compatibility.py",
      "is_sequence"
    ],
    [
      "sympy/utilities/iterables.py",
      "flatten"
    ],
    [
      "sympy/utilities/iterables.py",
      "has_dups"
    ],
    [
      "sympy/utilities/iterables.py",
      "has_variety"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 115.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "sympy/combinatorics/permutations.py",
          "Permutation.__new__"
        ]
      ],
      "seeds": [
        [
          "sympy/combinatorics/permutations.py",
          "Permutation.__new__"
        ]
      ],
      "causal_received": [
        [
          "sympy/combinatorics/permutations.py",
          "Permutation.__new__"
        ]
      ],
      "final": [
        [
          "sympy/combinatorics/permutations.py",
          "Permutation.__new__"
        ]
      ]
    },
    "search_unprocessed_matches": 508,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 22,
      "model_request": 22,
      "model_response": 22,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "search_page_summary": 5,
      "source_receipt": 9,
      "relevance_attempt": 9,
      "relevance_decisions": 9,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 64,
      "causal": 145
    },
    "predicted_function_count": 6,
    "seconds": 115.28666782937944
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 9,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 163617,
    "output": 6492
  }
}
```

## 4. scikit-learn__scikit-learn-25638

项目：`scikit-learn/scikit-learn`；base commit：`6adb209acd63825affc884abcd85381f148fb1b0`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 50.00% | 50.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "scikit-learn/sklearn/utils/multiclass.py"
  ],
  "found_modules": [],
  "found_functions": [
    "scikit-learn/sklearn/utils/multiclass.py::type_of_target",
    "scikit-learn/sklearn/utils/multiclass.py::unique_labels"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/utils/multiclass.py",
      "is_multilabel"
    ],
    [
      "sklearn/utils/multiclass.py",
      "type_of_target"
    ]
  ],
  "predictions": [
    [
      "sklearn/utils/multiclass.py",
      "type_of_target"
    ],
    [
      "sklearn/utils/multiclass.py",
      "unique_labels"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "sklearn/utils/multiclass.py",
      "type_of_target"
    ]
  ],
  "false_positive": [
    [
      "sklearn/utils/multiclass.py",
      "unique_labels"
    ]
  ],
  "missed_targets": [
    [
      "sklearn/utils/multiclass.py",
      "is_multilabel"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 92.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖部分目标",
    "coverage": {
      "search_received": [
        [
          "sklearn/utils/multiclass.py",
          "type_of_target"
        ]
      ],
      "seeds": [
        [
          "sklearn/utils/multiclass.py",
          "type_of_target"
        ]
      ],
      "causal_received": [
        [
          "sklearn/utils/multiclass.py",
          "is_multilabel"
        ],
        [
          "sklearn/utils/multiclass.py",
          "type_of_target"
        ]
      ],
      "final": [
        [
          "sklearn/utils/multiclass.py",
          "type_of_target"
        ]
      ]
    },
    "search_unprocessed_matches": 1,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 31,
      "causal": 51
    },
    "predicted_function_count": 2,
    "seconds": 92.79411212168634
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 137515,
    "output": 3763
  }
}
```

## 5. django__django-11910

项目：`django/django`；base commit：`d232fd76a85870daf345fd8f8d617fe7802ae194`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 11.11% | 100.00% | 20.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/autodetector.py",
    "django/django/db/migrations/questioner.py"
  ],
  "found_modules": [
    "django/django/db/migrations/autodetector.py::MigrationAutodetector",
    "django/django/db/migrations/questioner.py::MigrationQuestioner"
  ],
  "found_functions": [
    "django/django/db/migrations/autodetector.py::MigrationAutodetector.generate_altered_fields",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector.add_operation",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector._detect_changes",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector.generate_renamed_fields",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector._prepare_field_lists",
    "django/django/db/migrations/questioner.py::MigrationQuestioner.ask_rename",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector.deep_deconstruct",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector.generate_renamed_models",
    "django/django/db/migrations/autodetector.py::MigrationAutodetector._generate_through_model_map"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_altered_fields"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._detect_changes"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._generate_through_model_map"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._prepare_field_lists"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.add_operation"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.deep_deconstruct"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_altered_fields"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_renamed_fields"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_renamed_models"
    ],
    [
      "django/db/migrations/questioner.py",
      "MigrationQuestioner.ask_rename"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_altered_fields"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._detect_changes"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._generate_through_model_map"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._prepare_field_lists"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.add_operation"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.deep_deconstruct"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_renamed_fields"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_renamed_models"
    ],
    [
      "django/db/migrations/questioner.py",
      "MigrationQuestioner.ask_rename"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 182.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/autodetector.py",
          "MigrationAutodetector.generate_altered_fields"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/autodetector.py",
          "MigrationAutodetector.generate_altered_fields"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/autodetector.py",
          "MigrationAutodetector.generate_altered_fields"
        ]
      ],
      "final": [
        [
          "django/db/migrations/autodetector.py",
          "MigrationAutodetector.generate_altered_fields"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 22,
      "model_request": 22,
      "model_response": 22,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 3,
      "search_page_summary": 3,
      "seed_locations": 1,
      "causal_context": 18,
      "causal_parse": 18,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 56
    },
    "predicted_function_count": 9,
    "seconds": 182.79867200832814
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "generate_causal_graph": 18
  },
  "tokens": {
    "input": 132045,
    "output": 17863
  }
}
```

## 6. sympy__sympy-21055

项目：`sympy/sympy`；base commit：`748ce73479ee2cd5c861431091001cc18943c735`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "sympy/sympy/assumptions/refine.py",
    "sympy/sympy/functions/elementary/complexes.py",
    "sympy/sympy/assumptions/ask.py",
    "sympy/sympy/core/logic.py"
  ],
  "found_modules": [
    "sympy/sympy/assumptions/refine.py::handlers_dict",
    "sympy/sympy/functions/elementary/complexes.py::arg",
    "sympy/sympy/core/logic.py::Not"
  ],
  "found_functions": [
    "sympy/sympy/assumptions/refine.py::refine",
    "sympy/sympy/assumptions/refine.py::refine_abs",
    "sympy/sympy/assumptions/ask.py::ask",
    "sympy/sympy/core/logic.py::Not.arg"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/assumptions/refine.py",
      "refine_arg"
    ]
  ],
  "predictions": [
    [
      "sympy/assumptions/ask.py",
      "ask"
    ],
    [
      "sympy/assumptions/refine.py",
      "refine"
    ],
    [
      "sympy/assumptions/refine.py",
      "refine_abs"
    ],
    [
      "sympy/core/logic.py",
      "Not.arg"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [
    [
      "sympy/assumptions/ask.py",
      "ask"
    ],
    [
      "sympy/assumptions/refine.py",
      "refine"
    ],
    [
      "sympy/assumptions/refine.py",
      "refine_abs"
    ],
    [
      "sympy/core/logic.py",
      "Not.arg"
    ]
  ],
  "missed_targets": [
    [
      "sympy/assumptions/refine.py",
      "refine_arg"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 153.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "目标函数实体未送达模型",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [],
      "final": []
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 16,
      "model_request": 16,
      "model_response": 16,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 4,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 9,
      "causal": 146
    },
    "predicted_function_count": 4,
    "seconds": 153.47831879369915
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 129305,
    "output": 3192
  }
}
```

## 7. mwaskom__seaborn-3190

项目：`mwaskom/seaborn`；base commit：`4a9e54962a29c12a8b103d75f838e0e795a6974d`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 20.00% | 100.00% | 33.33% | 命中 |

原始定位：

```json
{
  "found_files": [
    "seaborn/seaborn/_core/scales.py"
  ],
  "found_modules": [
    "seaborn/seaborn/_core/scales.py::ContinuousBase",
    "seaborn/seaborn/_core/scales.py::PseudoAxis"
  ],
  "found_functions": [
    "seaborn/seaborn/_core/scales.py::ContinuousBase._setup",
    "seaborn/seaborn/_core/scales.py::ContinuousBase._get_transform",
    "seaborn/seaborn/_core/scales.py::_make_identity_transforms",
    "seaborn/seaborn/_core/scales.py::PseudoAxis.update_units",
    "seaborn/seaborn/_core/scales.py::PseudoAxis.convert_units"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "seaborn/_core/scales.py",
      "ContinuousBase._setup"
    ]
  ],
  "predictions": [
    [
      "seaborn/_core/scales.py",
      "ContinuousBase._get_transform"
    ],
    [
      "seaborn/_core/scales.py",
      "ContinuousBase._setup"
    ],
    [
      "seaborn/_core/scales.py",
      "PseudoAxis.convert_units"
    ],
    [
      "seaborn/_core/scales.py",
      "PseudoAxis.update_units"
    ],
    [
      "seaborn/_core/scales.py",
      "_make_identity_transforms"
    ]
  ],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "seaborn/_core/scales.py",
      "ContinuousBase._setup"
    ]
  ],
  "false_positive": [
    [
      "seaborn/_core/scales.py",
      "ContinuousBase._get_transform"
    ],
    [
      "seaborn/_core/scales.py",
      "PseudoAxis.convert_units"
    ],
    [
      "seaborn/_core/scales.py",
      "PseudoAxis.update_units"
    ],
    [
      "seaborn/_core/scales.py",
      "_make_identity_transforms"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 46.6 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "seaborn/_core/scales.py",
          "ContinuousBase._setup"
        ]
      ],
      "seeds": [
        [
          "seaborn/_core/scales.py",
          "ContinuousBase._setup"
        ]
      ],
      "causal_received": [
        [
          "seaborn/_core/scales.py",
          "ContinuousBase._setup"
        ]
      ],
      "final": [
        [
          "seaborn/_core/scales.py",
          "ContinuousBase._setup"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 15,
      "model_request": 15,
      "model_response": 15,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 6,
      "relevance": 5,
      "causal": 25
    },
    "predicted_function_count": 5,
    "seconds": 46.552610555663705
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 54504,
    "output": 3508
  }
}
```

