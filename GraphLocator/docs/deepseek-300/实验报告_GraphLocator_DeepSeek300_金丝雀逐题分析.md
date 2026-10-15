# GraphLocator DeepSeek-V4.1-Flash 金丝雀逐题分析

问题按固定 issue ID 对齐；空定位、失败、缺少结果、函数真值 NA 分别标记。预测是原始解析结果，不用真值回改。

## 1. astropy__astropy-12907

项目：`astropy/astropy`；base commit：`d16bfe05a744909de4b27f5875fe0d4ed41ce607`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 0.00% | 0.00% | 0.00% | NA |

原始定位：

```json
{}
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
  "predictions": [],
  "unresolved": []
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 2. django__django-11848

项目：`django/django`；base commit：`f0adf3b9b7a19cdee05368ff0c0c2d087f011180`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/utils_tests/test_http.py",
    "django/django/utils/http.py"
  ],
  "found_modules": [
    "django/tests/utils_tests/test_http.py::HttpDateProcessingTests"
  ],
  "found_functions": [
    "django/tests/utils_tests/test_http.py::HttpDateProcessingTests.test_parsing_year_less_than_70",
    "django/django/utils/http.py::parse_http_date"
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

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 414.9 秒。

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
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 4,
      "search_page_summary": 3,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 9,
      "causal": 7
    },
    "predicted_function_count": 2,
    "seconds": 414.86998250801116
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "relevance_json": 2,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 20849,
    "output": 60394
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
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "sympy/sympy/combinatorics/permutations.py",
    "sympy/sympy/utilities/iterables.py"
  ],
  "found_modules": [
    "sympy/sympy/combinatorics/permutations.py::Permutation"
  ],
  "found_functions": [
    "sympy/sympy/combinatorics/permutations.py::Permutation.__new__",
    "sympy/sympy/utilities/iterables.py::flatten",
    "sympy/sympy/utilities/iterables.py::has_dups"
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
      "Permutation.__new__"
    ],
    [
      "sympy/utilities/iterables.py",
      "flatten"
    ],
    [
      "sympy/utilities/iterables.py",
      "has_dups"
    ]
  ],
  "unresolved": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 528.3 秒。

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
      "request_preflight": 19,
      "model_request": 19,
      "model_response": 19,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 10,
      "search_page_summary": 4,
      "source_receipt": 8,
      "relevance_attempt": 8,
      "relevance_decisions": 8,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 64,
      "causal": 62
    },
    "predicted_function_count": 3,
    "seconds": 528.3429093305022
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 8,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 103512,
    "output": 82152
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
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 33.33% | 50.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "scikit-learn/sklearn/utils/_array_api.py",
    "scikit-learn/sklearn/utils/multiclass.py"
  ],
  "found_modules": [
    "scikit-learn/sklearn/utils/_array_api.py::_NumPyApiWrapper"
  ],
  "found_functions": [
    "scikit-learn/sklearn/utils/_array_api.py::_NumPyApiWrapper.asarray",
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
      "sklearn/utils/_array_api.py",
      "_NumPyApiWrapper.asarray"
    ],
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

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 440.8 秒。

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
      "request_preflight": 14,
      "model_request": 14,
      "model_response": 14,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "search_action_error": 1,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 31,
      "causal": 78
    },
    "predicted_function_count": 3,
    "seconds": 440.82430287171155
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "search_action_repair": 1,
    "relevance_json": 4,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 124145,
    "output": 67461
  }
}
```

## 5. django__django-11910

项目：`django/django`；base commit：`d232fd76a85870daf345fd8f8d617fe7802ae194`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 0.00% | 0.00% | 0.00% | NA |

原始定位：

```json
{}
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
  "predictions": [],
  "unresolved": []
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 6. sympy__sympy-21055

项目：`sympy/sympy`；base commit：`748ce73479ee2cd5c861431091001cc18943c735`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 0.00% | 0.00% | 0.00% | NA |

原始定位：

```json
{}
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
  "predictions": [],
  "unresolved": []
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 7. mwaskom__seaborn-3190

项目：`mwaskom/seaborn`；base commit：`4a9e54962a29c12a8b103d75f838e0e795a6974d`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 0.00% | 0.00% | 0.00% | NA |

原始定位：

```json
{}
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
  "predictions": [],
  "unresolved": []
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

