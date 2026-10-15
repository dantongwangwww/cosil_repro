# GraphLocator DeepSeek-V4.1-Flash 阶段逐题分析

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
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

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

## 2. astropy__astropy-14182

项目：`astropy/astropy`；base commit：`a5917978be39d13cd90b517e1de4e7a539ffaa48`。

状态：complete；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "astropy/astropy/io/ascii/fixedwidth.py",
    "astropy/astropy/io/ascii/rst.py",
    "astropy/astropy/io/ascii/tests/test_rst.py"
  ],
  "found_modules": [
    "astropy/astropy/io/ascii/rst.py::RST",
    "astropy/astropy/io/ascii/rst.py::SimpleRSTHeader",
    "astropy/astropy/io/ascii/rst.py::SimpleRSTData",
    "astropy/astropy/io/ascii/fixedwidth.py::FixedWidthHeader"
  ],
  "found_functions": [
    "astropy/astropy/io/ascii/tests/test_rst.py::test_write_normal",
    "astropy/astropy/io/ascii/rst.py::SimpleRSTHeader.get_fixedwidth_params"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "astropy/io/ascii/rst.py",
      "RST.__init__"
    ],
    [
      "astropy/io/ascii/rst.py",
      "RST.read"
    ],
    [
      "astropy/io/ascii/rst.py",
      "RST.write"
    ]
  ],
  "predictions": [
    [
      "astropy/io/ascii/rst.py",
      "SimpleRSTHeader.get_fixedwidth_params"
    ],
    [
      "astropy/io/ascii/tests/test_rst.py",
      "test_write_normal"
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
      "astropy/io/ascii/rst.py",
      "SimpleRSTHeader.get_fixedwidth_params"
    ],
    [
      "astropy/io/ascii/tests/test_rst.py",
      "test_write_normal"
    ]
  ],
  "missed_targets": [
    [
      "astropy/io/ascii/rst.py",
      "RST.__init__"
    ],
    [
      "astropy/io/ascii/rst.py",
      "RST.read"
    ],
    [
      "astropy/io/ascii/rst.py",
      "RST.write"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 106.0 秒。

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
          "astropy/io/ascii/rst.py",
          "RST.__init__"
        ],
        [
          "astropy/io/ascii/rst.py",
          "RST.write"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 502,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 9,
      "search_page_summary": 5,
      "source_receipt": 7,
      "relevance_attempt": 7,
      "relevance_decisions": 7,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 51,
      "causal": 10
    },
    "predicted_function_count": 2,
    "seconds": 105.95518319960684
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 7,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 53039,
    "output": 5845
  }
}
```

## 3. astropy__astropy-14365

项目：`astropy/astropy`；base commit：`7269fa3e33e8d02485a647da91a5a2a60a06af61`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 50.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "astropy/astropy/io/ascii/qdp.py"
  ],
  "found_modules": [],
  "found_functions": [
    "astropy/astropy/io/ascii/qdp.py::_line_type",
    "astropy/astropy/io/ascii/qdp.py::_get_type_from_list_of_lines"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "astropy/io/ascii/qdp.py",
      "_get_tables_from_qdp_file"
    ],
    [
      "astropy/io/ascii/qdp.py",
      "_line_type"
    ]
  ],
  "predictions": [
    [
      "astropy/io/ascii/qdp.py",
      "_get_type_from_list_of_lines"
    ],
    [
      "astropy/io/ascii/qdp.py",
      "_line_type"
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
      "astropy/io/ascii/qdp.py",
      "_line_type"
    ]
  ],
  "false_positive": [
    [
      "astropy/io/ascii/qdp.py",
      "_get_type_from_list_of_lines"
    ]
  ],
  "missed_targets": [
    [
      "astropy/io/ascii/qdp.py",
      "_get_tables_from_qdp_file"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 61.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖部分目标",
    "coverage": {
      "search_received": [
        [
          "astropy/io/ascii/qdp.py",
          "_line_type"
        ]
      ],
      "seeds": [
        [
          "astropy/io/ascii/qdp.py",
          "_line_type"
        ]
      ],
      "causal_received": [
        [
          "astropy/io/ascii/qdp.py",
          "_get_tables_from_qdp_file"
        ],
        [
          "astropy/io/ascii/qdp.py",
          "_line_type"
        ]
      ],
      "final": [
        [
          "astropy/io/ascii/qdp.py",
          "_line_type"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 9,
      "model_request": 9,
      "model_response": 9,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 4,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 4,
      "causal": 3
    },
    "predicted_function_count": 2,
    "seconds": 61.01279382687062
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 19138,
    "output": 1001
  }
}
```

## 4. astropy__astropy-14995

项目：`astropy/astropy`；base commit：`b16c7d12ccbc7b2d20364b89fb44285bcbfede54`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "astropy/astropy/nddata/mixins/ndarithmetic.py",
    "astropy/astropy/nddata/nddata_withmixins.py"
  ],
  "found_modules": [
    "astropy/astropy/nddata/mixins/ndarithmetic.py::NDArithmeticMixin",
    "astropy/astropy/nddata/nddata_withmixins.py::NDDataRef"
  ],
  "found_functions": [
    "astropy/astropy/nddata/mixins/ndarithmetic.py::NDArithmeticMixin._arithmetic_mask",
    "astropy/astropy/nddata/mixins/ndarithmetic.py::NDArithmeticMixin._arithmetic"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "astropy/nddata/mixins/ndarithmetic.py",
      "NDArithmeticMixin._arithmetic_mask"
    ]
  ],
  "predictions": [
    [
      "astropy/nddata/mixins/ndarithmetic.py",
      "NDArithmeticMixin._arithmetic"
    ],
    [
      "astropy/nddata/mixins/ndarithmetic.py",
      "NDArithmeticMixin._arithmetic_mask"
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
      "astropy/nddata/mixins/ndarithmetic.py",
      "NDArithmeticMixin._arithmetic_mask"
    ]
  ],
  "false_positive": [
    [
      "astropy/nddata/mixins/ndarithmetic.py",
      "NDArithmeticMixin._arithmetic"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 78.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "astropy/nddata/mixins/ndarithmetic.py",
          "NDArithmeticMixin._arithmetic_mask"
        ]
      ],
      "seeds": [
        [
          "astropy/nddata/mixins/ndarithmetic.py",
          "NDArithmeticMixin._arithmetic_mask"
        ]
      ],
      "causal_received": [
        [
          "astropy/nddata/mixins/ndarithmetic.py",
          "NDArithmeticMixin._arithmetic_mask"
        ]
      ],
      "final": [
        [
          "astropy/nddata/mixins/ndarithmetic.py",
          "NDArithmeticMixin._arithmetic_mask"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 9,
      "model_request": 9,
      "model_response": 9,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 8
    },
    "predicted_function_count": 2,
    "seconds": 78.73894008994102
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 31634,
    "output": 2641
  }
}
```

## 5. astropy__astropy-6938

项目：`astropy/astropy`；base commit：`c76af9ed6bb89bfba45b9f5bc1e635188278e2fa`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "astropy/astropy/io/fits/fitsrec.py",
    "astropy/astropy/io/fits/util.py"
  ],
  "found_modules": [
    "astropy/astropy/io/fits/fitsrec.py::FITS_rec"
  ],
  "found_functions": [
    "astropy/astropy/io/fits/fitsrec.py::FITS_rec._scale_back_ascii",
    "astropy/astropy/io/fits/fitsrec.py::FITS_rec._scale_back",
    "astropy/astropy/io/fits/util.py::encode_ascii"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "astropy/io/fits/fitsrec.py",
      "FITS_rec._scale_back_ascii"
    ]
  ],
  "predictions": [
    [
      "astropy/io/fits/fitsrec.py",
      "FITS_rec._scale_back"
    ],
    [
      "astropy/io/fits/fitsrec.py",
      "FITS_rec._scale_back_ascii"
    ],
    [
      "astropy/io/fits/util.py",
      "encode_ascii"
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
      "astropy/io/fits/fitsrec.py",
      "FITS_rec._scale_back_ascii"
    ]
  ],
  "false_positive": [
    [
      "astropy/io/fits/fitsrec.py",
      "FITS_rec._scale_back"
    ],
    [
      "astropy/io/fits/util.py",
      "encode_ascii"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 78.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "astropy/io/fits/fitsrec.py",
          "FITS_rec._scale_back_ascii"
        ]
      ],
      "seeds": [
        [
          "astropy/io/fits/fitsrec.py",
          "FITS_rec._scale_back_ascii"
        ]
      ],
      "causal_received": [
        [
          "astropy/io/fits/fitsrec.py",
          "FITS_rec._scale_back_ascii"
        ]
      ],
      "final": [
        [
          "astropy/io/fits/fitsrec.py",
          "FITS_rec._scale_back_ascii"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 9,
      "model_request": 9,
      "model_response": 9,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 3,
      "search_page_summary": 3,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 0,
      "causal": 18
    },
    "predicted_function_count": 3,
    "seconds": 78.19742173328996
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 28837,
    "output": 4037
  }
}
```

## 6. astropy__astropy-7746

项目：`astropy/astropy`；base commit：`d5bd3f68bb6d5ce3a61bdce9883ee750d1afade5`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "astropy/astropy/wcs/wcs.py"
  ],
  "found_modules": [
    "astropy/astropy/wcs/wcs.py::WCS"
  ],
  "found_functions": [
    "astropy/astropy/wcs/wcs.py::WCS._denormalize_sky",
    "astropy/astropy/wcs/wcs.py::WCS._normalize_sky",
    "astropy/astropy/wcs/wcs.py::WCS._return_single_array",
    "astropy/astropy/wcs/wcs.py::WCS._return_list_of_arrays",
    "astropy/astropy/wcs/wcs.py::WCS._array_converter",
    "astropy/astropy/wcs/wcs.py::WCS.wcs_pix2world"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "astropy/wcs/wcs.py",
      "WCS._array_converter._return_list_of_arrays"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._array_converter._return_single_array"
    ]
  ],
  "predictions": [
    [
      "astropy/wcs/wcs.py",
      "<unresolved>:WCS._return_list_of_arrays"
    ],
    [
      "astropy/wcs/wcs.py",
      "<unresolved>:WCS._return_single_array"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._array_converter"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._denormalize_sky"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._normalize_sky"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS.wcs_pix2world"
    ]
  ],
  "unresolved": [
    {
      "file": "astropy/wcs/wcs.py",
      "name": "WCS._return_single_array",
      "reason": "absent"
    },
    {
      "file": "astropy/wcs/wcs.py",
      "name": "WCS._return_list_of_arrays",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [
    [
      "astropy/wcs/wcs.py",
      "<unresolved>:WCS._return_list_of_arrays"
    ],
    [
      "astropy/wcs/wcs.py",
      "<unresolved>:WCS._return_single_array"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._array_converter"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._denormalize_sky"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._normalize_sky"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS.wcs_pix2world"
    ]
  ],
  "missed_targets": [
    [
      "astropy/wcs/wcs.py",
      "WCS._array_converter._return_list_of_arrays"
    ],
    [
      "astropy/wcs/wcs.py",
      "WCS._array_converter._return_single_array"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 68.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "因果收到目标实体但未保留",
    "coverage": {
      "search_received": [
        [
          "astropy/wcs/wcs.py",
          "WCS._array_converter._return_list_of_arrays"
        ],
        [
          "astropy/wcs/wcs.py",
          "WCS._array_converter._return_single_array"
        ]
      ],
      "seeds": [
        [
          "astropy/wcs/wcs.py",
          "WCS._array_converter._return_list_of_arrays"
        ],
        [
          "astropy/wcs/wcs.py",
          "WCS._array_converter._return_single_array"
        ]
      ],
      "causal_received": [
        [
          "astropy/wcs/wcs.py",
          "WCS._array_converter._return_list_of_arrays"
        ],
        [
          "astropy/wcs/wcs.py",
          "WCS._array_converter._return_single_array"
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
      "search_result": 6,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 11,
      "causal": 27
    },
    "predicted_function_count": 6,
    "seconds": 68.0457926793024
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 49190,
    "output": 4080
  }
}
```

## 7. django__django-10914

项目：`django/django`；base commit：`e7fd69d051eaa67cb17f172a39b57253e9cb831a`。

状态：complete；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | NA |

原始定位：

```json
{
  "found_files": [
    "django/django/core/files/storage.py",
    "django/django/core/files/move.py"
  ],
  "found_modules": [
    "django/django/core/files/storage.py::FileSystemStorage"
  ],
  "found_functions": [
    "django/django/core/files/storage.py::FileSystemStorage._save",
    "django/django/core/files/move.py::file_move_safe"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [
    [
      "django/core/files/move.py",
      "file_move_safe"
    ],
    [
      "django/core/files/storage.py",
      "FileSystemStorage._save"
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
      "django/core/files/move.py",
      "file_move_safe"
    ],
    [
      "django/core/files/storage.py",
      "FileSystemStorage._save"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 114.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "NA",
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
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 5,
      "search_matches": 5,
      "search_page_summary": 5,
      "search_result": 4,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 6,
      "causal": 32
    },
    "predicted_function_count": 2,
    "seconds": 114.69037531968206
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 31655,
    "output": 3302
  }
}
```

## 8. django__django-10924

项目：`django/django`；base commit：`bceadd2788dc2dad53eba0caae172bd8522fd483`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 20.00% | 100.00% | 33.33% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/__init__.py",
    "django/django/forms/fields.py",
    "django/tests/field_deconstruction/tests.py",
    "django/tests/forms_tests/field_tests/test_filepathfield.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/__init__.py::Field",
    "django/django/db/models/fields/__init__.py::FilePathField",
    "django/django/forms/fields.py::FilePathField",
    "django/tests/field_deconstruction/tests.py::FieldDeconstructionTests"
  ],
  "found_functions": [
    "django/django/db/models/fields/__init__.py::Field.formfield",
    "django/django/db/models/fields/__init__.py::FilePathField.formfield",
    "django/tests/field_deconstruction/tests.py::FieldDeconstructionTests.test_file_path_field",
    "django/django/db/models/fields/__init__.py::FilePathField.__init__",
    "django/django/db/models/fields/__init__.py::FilePathField.deconstruct"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "FilePathField.formfield"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/__init__.py",
      "Field.formfield"
    ],
    [
      "django/db/models/fields/__init__.py",
      "FilePathField.__init__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "FilePathField.deconstruct"
    ],
    [
      "django/db/models/fields/__init__.py",
      "FilePathField.formfield"
    ],
    [
      "tests/field_deconstruction/tests.py",
      "FieldDeconstructionTests.test_file_path_field"
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
      "django/db/models/fields/__init__.py",
      "FilePathField.formfield"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/fields/__init__.py",
      "Field.formfield"
    ],
    [
      "django/db/models/fields/__init__.py",
      "FilePathField.__init__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "FilePathField.deconstruct"
    ],
    [
      "tests/field_deconstruction/tests.py",
      "FieldDeconstructionTests.test_file_path_field"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 166.1 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/fields/__init__.py",
          "FilePathField.formfield"
        ]
      ],
      "seeds": [
        [
          "django/db/models/fields/__init__.py",
          "FilePathField.formfield"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/__init__.py",
          "FilePathField.formfield"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/__init__.py",
          "FilePathField.formfield"
        ]
      ]
    },
    "search_unprocessed_matches": 778,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 22,
      "model_request": 22,
      "model_response": 22,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 9,
      "search_page_summary": 5,
      "source_receipt": 8,
      "relevance_attempt": 8,
      "relevance_decisions": 8,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 51,
      "causal": 81
    },
    "predicted_function_count": 5,
    "seconds": 166.08135658316314
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 8,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 65718,
    "output": 5759
  }
}
```

## 9. django__django-11001

项目：`django/django`；base commit：`ef082ebb84f00e38af4e8880d04e8365c2766d34`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 100.00% | 28.57% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/compiler.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/compiler.py::SQLCompiler"
  ],
  "found_functions": [
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_order_by",
    "django/django/db/models/sql/compiler.py::SQLCompiler.__init__",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_extra_select",
    "django/django/db/models/sql/compiler.py::SQLCompiler.pre_sql_setup",
    "django/django/db/models/sql/compiler.py::SQLCompiler.as_sql",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_group_by"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.__init__"
    ]
  ],
  "predictions": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.__init__"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_extra_select"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.pre_sql_setup"
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
      "django/db/models/sql/compiler.py",
      "SQLCompiler.__init__"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_extra_select"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.pre_sql_setup"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 106.6 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.__init__"
        ]
      ],
      "seeds": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.__init__"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.__init__"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.__init__"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 3,
      "search_page_summary": 3,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 39
    },
    "predicted_function_count": 6,
    "seconds": 106.57840261328965
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "relevance_json": 1,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 63144,
    "output": 4637
  }
}
```

## 10. django__django-11019

项目：`django/django`；base commit：`93e892bb645b16ebaf287beb5fe7f3ffe8d10408`。

状态：complete；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 33.33% | 25.00% | 命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 40.00% | 66.67% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/widgets.py"
  ],
  "found_modules": [
    "django/django/forms/widgets.py::Media",
    "django/django/forms/widgets.py::MultiWidget",
    "django/django/forms/widgets.py::MediaOrderConflictWarning"
  ],
  "found_functions": [
    "django/django/forms/widgets.py::Media._js",
    "django/django/forms/widgets.py::Media.__init__",
    "django/django/forms/widgets.py::MultiWidget._get_media",
    "django/django/forms/widgets.py::Media.merge",
    "django/django/forms/widgets.py::Media.__add__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/widgets.py",
      "Media._css"
    ],
    [
      "django/forms/widgets.py",
      "Media._js"
    ],
    [
      "django/forms/widgets.py",
      "Media.merge"
    ]
  ],
  "predictions": [
    [
      "django/forms/widgets.py",
      "Media.__add__"
    ],
    [
      "django/forms/widgets.py",
      "Media.__init__"
    ],
    [
      "django/forms/widgets.py",
      "Media._js"
    ],
    [
      "django/forms/widgets.py",
      "Media.merge"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget._get_media"
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
      "django/forms/widgets.py",
      "Media._js"
    ],
    [
      "django/forms/widgets.py",
      "Media.merge"
    ]
  ],
  "false_positive": [
    [
      "django/forms/widgets.py",
      "Media.__add__"
    ],
    [
      "django/forms/widgets.py",
      "Media.__init__"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget._get_media"
    ]
  ],
  "missed_targets": [
    [
      "django/forms/widgets.py",
      "Media._css"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 168.6 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖部分目标",
    "coverage": {
      "search_received": [
        [
          "django/forms/widgets.py",
          "Media.merge"
        ]
      ],
      "seeds": [
        [
          "django/forms/widgets.py",
          "Media.merge"
        ]
      ],
      "causal_received": [
        [
          "django/forms/widgets.py",
          "Media._css"
        ],
        [
          "django/forms/widgets.py",
          "Media._js"
        ],
        [
          "django/forms/widgets.py",
          "Media.merge"
        ]
      ],
      "final": [
        [
          "django/forms/widgets.py",
          "Media._js"
        ],
        [
          "django/forms/widgets.py",
          "Media.merge"
        ]
      ]
    },
    "search_unprocessed_matches": 5,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 20,
      "model_request": 20,
      "model_response": 20,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "output_truncated": 2,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 5,
      "causal": 23
    },
    "predicted_function_count": 5,
    "seconds": 168.61443938780576
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 41137,
    "output": 12849
  }
}
```

## 11. django__django-11039

项目：`django/django`；base commit：`d5276398046ce4a102776a1e67dcac2884d80dfe`。

状态：empty；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/migrations/test_commands.py"
  ],
  "found_modules": [],
  "found_functions": []
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/management/commands/sqlmigrate.py",
      "Command.handle"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/core/management/commands/sqlmigrate.py",
      "Command.handle"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 98.4 秒。

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
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 5,
      "causal": 0
    },
    "predicted_function_count": 0,
    "seconds": 98.35998074710369
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 29805,
    "output": 1404
  }
}
```

## 12. django__django-11049

项目：`django/django`；base commit：`17455e924e243e7a55e8a38f45966d8cbb27c273`。

状态：complete；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | NA |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/__init__.py",
    "django/tests/model_fields/test_durationfield.py",
    "django/django/forms/fields.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/__init__.py::DurationField",
    "django/tests/model_fields/test_durationfield.py::TestFormField",
    "django/tests/model_fields/test_durationfield.py::TestValidation",
    "django/django/forms/fields.py::DurationField"
  ],
  "found_functions": [
    "django/django/db/models/fields/__init__.py::DurationField.formfield",
    "django/tests/model_fields/test_durationfield.py::TestFormField.test_formfield",
    "django/django/db/models/fields/__init__.py::DurationField.to_python",
    "django/tests/model_fields/test_durationfield.py::TestValidation.test_invalid_string"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [
    [
      "django/db/models/fields/__init__.py",
      "DurationField.formfield"
    ],
    [
      "django/db/models/fields/__init__.py",
      "DurationField.to_python"
    ],
    [
      "tests/model_fields/test_durationfield.py",
      "TestFormField.test_formfield"
    ],
    [
      "tests/model_fields/test_durationfield.py",
      "TestValidation.test_invalid_string"
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
      "django/db/models/fields/__init__.py",
      "DurationField.formfield"
    ],
    [
      "django/db/models/fields/__init__.py",
      "DurationField.to_python"
    ],
    [
      "tests/model_fields/test_durationfield.py",
      "TestFormField.test_formfield"
    ],
    [
      "tests/model_fields/test_durationfield.py",
      "TestValidation.test_invalid_string"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 159.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "NA",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [],
      "final": []
    },
    "search_unprocessed_matches": 631,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 23,
      "model_request": 23,
      "model_response": 23,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "search_page_summary": 5,
      "source_receipt": 9,
      "relevance_attempt": 9,
      "relevance_decisions": 9,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 68,
      "causal": 12
    },
    "predicted_function_count": 4,
    "seconds": 159.46662650536746
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 9,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 43924,
    "output": 6947
  }
}
```

## 13. django__django-11099

项目：`django/django`；base commit：`d26b2424437dabeeca94d7900b37d2df4410da0c`。

状态：complete；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | NA |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/auth/validators.py",
    "django/tests/auth_tests/test_validators.py"
  ],
  "found_modules": [
    "django/django/contrib/auth/validators.py::ASCIIUsernameValidator",
    "django/tests/auth_tests/test_validators.py::UsernameValidatorsTests",
    "django/django/contrib/auth/validators.py::UnicodeUsernameValidator"
  ],
  "found_functions": [
    "django/tests/auth_tests/test_validators.py::UsernameValidatorsTests.test_unicode_validator",
    "django/tests/auth_tests/test_validators.py::UsernameValidatorsTests.test_ascii_validator"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [
    [
      "tests/auth_tests/test_validators.py",
      "UsernameValidatorsTests.test_ascii_validator"
    ],
    [
      "tests/auth_tests/test_validators.py",
      "UsernameValidatorsTests.test_unicode_validator"
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
      "tests/auth_tests/test_validators.py",
      "UsernameValidatorsTests.test_ascii_validator"
    ],
    [
      "tests/auth_tests/test_validators.py",
      "UsernameValidatorsTests.test_unicode_validator"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 129.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "NA",
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
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 0,
      "causal": 2
    },
    "predicted_function_count": 2,
    "seconds": 129.45456155575812
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 15873,
    "output": 3330
  }
}
```

## 14. django__django-11133

项目：`django/django`；base commit：`879cc3da6249e920b8d54518a0ae06de835d7373`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/http/response.py"
  ],
  "found_modules": [
    "django/django/http/response.py::HttpResponseBase",
    "django/django/http/response.py::HttpResponse"
  ],
  "found_functions": [
    "django/django/http/response.py::HttpResponseBase.make_bytes",
    "django/django/http/response.py::HttpResponse.content"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/http/response.py",
      "HttpResponseBase.make_bytes"
    ]
  ],
  "predictions": [
    [
      "django/http/response.py",
      "<unresolved>:HttpResponse.content"
    ],
    [
      "django/http/response.py",
      "HttpResponseBase.make_bytes"
    ]
  ],
  "unresolved": [
    {
      "file": "django/http/response.py",
      "name": "HttpResponse.content",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/http/response.py",
      "HttpResponseBase.make_bytes"
    ]
  ],
  "false_positive": [
    [
      "django/http/response.py",
      "<unresolved>:HttpResponse.content"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 99.9 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [
        [
          "django/http/response.py",
          "HttpResponseBase.make_bytes"
        ]
      ],
      "causal_received": [
        [
          "django/http/response.py",
          "HttpResponseBase.make_bytes"
        ]
      ],
      "final": [
        [
          "django/http/response.py",
          "HttpResponseBase.make_bytes"
        ]
      ]
    },
    "search_unprocessed_matches": 778,
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
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 36,
      "causal": 5
    },
    "predicted_function_count": 2,
    "seconds": 99.86706846673042
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 22874,
    "output": 3249
  }
}
```

## 15. django__django-11179

项目：`django/django`；base commit：`19fc6376ce67d01ca37a91ef2f55ef769f50513a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/deletion.py",
    "django/django/db/models/base.py"
  ],
  "found_modules": [
    "django/django/db/models/deletion.py::Collector",
    "django/django/db/models/base.py::Model"
  ],
  "found_functions": [
    "django/django/db/models/deletion.py::Collector.can_fast_delete",
    "django/django/db/models/deletion.py::Collector.delete",
    "django/django/db/models/base.py::Model.delete"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/deletion.py",
      "Collector.delete"
    ]
  ],
  "predictions": [
    [
      "django/db/models/base.py",
      "Model.delete"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.can_fast_delete"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.delete"
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
      "django/db/models/deletion.py",
      "Collector.delete"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/base.py",
      "Model.delete"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.can_fast_delete"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 168.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ],
      "seeds": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ],
      "final": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
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
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 6,
      "relevance": 29,
      "causal": 17
    },
    "predicted_function_count": 3,
    "seconds": 168.77685586642474
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 36805,
    "output": 3224
  }
}
```

## 16. django__django-11283

项目：`django/django`；base commit：`08a4ee06510ae45562c228eefbdcaac84bd38c7a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 7.69% | 100.00% | 14.29% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/options.py",
    "django/django/db/models/base.py",
    "django/django/db/migrations/state.py",
    "django/django/db/models/utils.py",
    "django/django/db/models/fields/related.py",
    "django/django/db/models/signals.py",
    "django/django/contrib/auth/migrations/0011_update_proxy_permissions.py",
    "django/tests/auth_tests/test_migrations.py"
  ],
  "found_modules": [
    "django/django/db/models/options.py::Options",
    "django/django/db/models/base.py::ModelBase",
    "django/django/db/migrations/state.py::StateApps",
    "django/django/db/models/signals.py::ModelSignal",
    "django/tests/auth_tests/test_migrations.py::update_proxy_permissions"
  ],
  "found_functions": [
    "django/django/db/models/options.py::Options._prepare",
    "django/django/db/models/base.py::ModelBase.__new__",
    "django/django/db/models/options.py::Options.setup_proxy",
    "django/django/db/models/options.py::Options.contribute_to_class",
    "django/django/db/migrations/state.py::StateApps.__init__",
    "django/django/db/models/utils.py::make_model_tuple",
    "django/django/db/models/fields/related.py::lazy_related_operation",
    "django/django/db/models/signals.py::ModelSignal._lazy_method",
    "django/django/db/models/fields/related.py::create_many_to_many_intermediary_model",
    "django/django/contrib/auth/migrations/0011_update_proxy_permissions.py::update_proxy_model_permissions",
    "django/django/db/models/base.py::ModelBase._prepare",
    "django/django/db/models/options.py::Options.__init__",
    "django/django/db/models/options.py::Options._get_fields"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/auth/migrations/0011_update_proxy_permissions.py",
      "update_proxy_model_permissions"
    ]
  ],
  "predictions": [
    [
      "django/contrib/auth/migrations/0011_update_proxy_permissions.py",
      "update_proxy_model_permissions"
    ],
    [
      "django/db/migrations/state.py",
      "StateApps.__init__"
    ],
    [
      "django/db/models/base.py",
      "ModelBase.__new__"
    ],
    [
      "django/db/models/base.py",
      "ModelBase._prepare"
    ],
    [
      "django/db/models/fields/related.py",
      "create_many_to_many_intermediary_model"
    ],
    [
      "django/db/models/fields/related.py",
      "lazy_related_operation"
    ],
    [
      "django/db/models/options.py",
      "Options.__init__"
    ],
    [
      "django/db/models/options.py",
      "Options._get_fields"
    ],
    [
      "django/db/models/options.py",
      "Options._prepare"
    ],
    [
      "django/db/models/options.py",
      "Options.contribute_to_class"
    ],
    [
      "django/db/models/options.py",
      "Options.setup_proxy"
    ],
    [
      "django/db/models/signals.py",
      "ModelSignal._lazy_method"
    ],
    [
      "django/db/models/utils.py",
      "make_model_tuple"
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
      "django/contrib/auth/migrations/0011_update_proxy_permissions.py",
      "update_proxy_model_permissions"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/state.py",
      "StateApps.__init__"
    ],
    [
      "django/db/models/base.py",
      "ModelBase.__new__"
    ],
    [
      "django/db/models/base.py",
      "ModelBase._prepare"
    ],
    [
      "django/db/models/fields/related.py",
      "create_many_to_many_intermediary_model"
    ],
    [
      "django/db/models/fields/related.py",
      "lazy_related_operation"
    ],
    [
      "django/db/models/options.py",
      "Options.__init__"
    ],
    [
      "django/db/models/options.py",
      "Options._get_fields"
    ],
    [
      "django/db/models/options.py",
      "Options._prepare"
    ],
    [
      "django/db/models/options.py",
      "Options.contribute_to_class"
    ],
    [
      "django/db/models/options.py",
      "Options.setup_proxy"
    ],
    [
      "django/db/models/signals.py",
      "ModelSignal._lazy_method"
    ],
    [
      "django/db/models/utils.py",
      "make_model_tuple"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 281.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/contrib/auth/migrations/0011_update_proxy_permissions.py",
          "update_proxy_model_permissions"
        ]
      ],
      "final": [
        [
          "django/contrib/auth/migrations/0011_update_proxy_permissions.py",
          "update_proxy_model_permissions"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 26,
      "model_request": 26,
      "model_response": 26,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 18,
      "causal_parse": 18,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 13,
      "causal": 88
    },
    "predicted_function_count": 13,
    "seconds": 281.5229741083458
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 3
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [
    [
      "django/db/models/utils.py",
      "make_model_tuple"
    ]
  ],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 18
  },
  "tokens": {
    "input": 156135,
    "output": 21570
  }
}
```

## 17. django__django-11422

项目：`django/django`；base commit：`df46b329e0900e9e4dc1d60816c1dce6dfc1094e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 14.29% | 100.00% | 25.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/template/backends/django.py",
    "django/django/utils/autoreload.py",
    "django/tests/utils_tests/test_autoreload.py"
  ],
  "found_modules": [
    "django/django/template/backends/django.py::Template",
    "django/tests/utils_tests/test_autoreload.py::TestIterModulesAndFiles",
    "django/django/utils/autoreload.py::BaseReloader",
    "django/django/utils/autoreload.py::StatReloader"
  ],
  "found_functions": [
    "django/django/template/backends/django.py::Template.origin",
    "django/django/utils/autoreload.py::iter_modules_and_files",
    "django/tests/utils_tests/test_autoreload.py::TestIterModulesAndFiles.test_module_without_spec",
    "django/django/utils/autoreload.py::StatReloader.tick",
    "django/django/utils/autoreload.py::BaseReloader.watched_files",
    "django/django/utils/autoreload.py::iter_all_python_module_files",
    "django/django/utils/autoreload.py::BaseReloader.watch_file"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/autoreload.py",
      "iter_modules_and_files"
    ]
  ],
  "predictions": [
    [
      "django/template/backends/django.py",
      "Template.origin"
    ],
    [
      "django/utils/autoreload.py",
      "BaseReloader.watch_file"
    ],
    [
      "django/utils/autoreload.py",
      "BaseReloader.watched_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.tick"
    ],
    [
      "django/utils/autoreload.py",
      "iter_all_python_module_files"
    ],
    [
      "django/utils/autoreload.py",
      "iter_modules_and_files"
    ],
    [
      "tests/utils_tests/test_autoreload.py",
      "TestIterModulesAndFiles.test_module_without_spec"
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
      "django/utils/autoreload.py",
      "iter_modules_and_files"
    ]
  ],
  "false_positive": [
    [
      "django/template/backends/django.py",
      "Template.origin"
    ],
    [
      "django/utils/autoreload.py",
      "BaseReloader.watch_file"
    ],
    [
      "django/utils/autoreload.py",
      "BaseReloader.watched_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.tick"
    ],
    [
      "django/utils/autoreload.py",
      "iter_all_python_module_files"
    ],
    [
      "tests/utils_tests/test_autoreload.py",
      "TestIterModulesAndFiles.test_module_without_spec"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 140.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ],
      "seeds": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ],
      "causal_received": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ],
      "final": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 19,
      "model_request": 19,
      "model_response": 19,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 13,
      "causal_parse": 13,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 5,
      "causal": 25
    },
    "predicted_function_count": 7,
    "seconds": 140.68714419472963
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 13
  },
  "tokens": {
    "input": 36037,
    "output": 5866
  }
}
```

## 18. django__django-11564

项目：`django/django`；base commit：`580e644f24f1c5ae5b94784fb73a9953a178fd26`。

状态：complete；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/templatetags/static.py"
  ],
  "found_modules": [
    "django/django/templatetags/static.py::StaticNode"
  ],
  "found_functions": [
    "django/django/templatetags/static.py::StaticNode.__init__",
    "django/django/templatetags/static.py::StaticNode.handle_token",
    "django/django/templatetags/static.py::do_static",
    "django/django/templatetags/static.py::static",
    "django/django/templatetags/static.py::StaticNode.render",
    "django/django/templatetags/static.py::StaticNode.url",
    "django/django/templatetags/static.py::StaticNode.handle_simple"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/conf/__init__.py",
      "LazySettings.MEDIA_URL"
    ],
    [
      "django/conf/__init__.py",
      "LazySettings.STATIC_URL"
    ],
    [
      "django/conf/__init__.py",
      "LazySettings._add_script_prefix"
    ]
  ],
  "predictions": [
    [
      "django/templatetags/static.py",
      "StaticNode.__init__"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.handle_simple"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.handle_token"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.render"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.url"
    ],
    [
      "django/templatetags/static.py",
      "do_static"
    ],
    [
      "django/templatetags/static.py",
      "static"
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
      "django/templatetags/static.py",
      "StaticNode.__init__"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.handle_simple"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.handle_token"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.render"
    ],
    [
      "django/templatetags/static.py",
      "StaticNode.url"
    ],
    [
      "django/templatetags/static.py",
      "do_static"
    ],
    [
      "django/templatetags/static.py",
      "static"
    ]
  ],
  "missed_targets": [
    [
      "django/conf/__init__.py",
      "LazySettings.MEDIA_URL"
    ],
    [
      "django/conf/__init__.py",
      "LazySettings.STATIC_URL"
    ],
    [
      "django/conf/__init__.py",
      "LazySettings._add_script_prefix"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 159.4 秒。

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
    "search_unprocessed_matches": 34,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 24,
      "model_request": 24,
      "model_response": 24,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 7,
      "relevance_attempt": 7,
      "relevance_decisions": 7,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 12,
      "causal_parse": 12,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 42,
      "causal": 13
    },
    "predicted_function_count": 7,
    "seconds": 159.4151015272364
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 7,
    "generate_causal_graph": 12
  },
  "tokens": {
    "input": 44359,
    "output": 8099
  }
}
```

## 19. django__django-11583

项目：`django/django`；base commit：`60dc957a825232fdda9138e2f8878b2ca407a7c9`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 20.00% | 100.00% | 33.33% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/autoreload.py"
  ],
  "found_modules": [
    "django/django/utils/autoreload.py::WatchmanReloader",
    "django/django/utils/autoreload.py::BaseReloader",
    "django/django/utils/autoreload.py::StatReloader"
  ],
  "found_functions": [
    "django/django/utils/autoreload.py::WatchmanReloader._update_watches",
    "django/django/utils/autoreload.py::BaseReloader.watched_files",
    "django/django/utils/autoreload.py::iter_modules_and_files",
    "django/django/utils/autoreload.py::iter_all_python_module_files",
    "django/django/utils/autoreload.py::StatReloader.snapshot_files"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/autoreload.py",
      "iter_modules_and_files"
    ]
  ],
  "predictions": [
    [
      "django/utils/autoreload.py",
      "BaseReloader.watched_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.snapshot_files"
    ],
    [
      "django/utils/autoreload.py",
      "WatchmanReloader._update_watches"
    ],
    [
      "django/utils/autoreload.py",
      "iter_all_python_module_files"
    ],
    [
      "django/utils/autoreload.py",
      "iter_modules_and_files"
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
      "django/utils/autoreload.py",
      "iter_modules_and_files"
    ]
  ],
  "false_positive": [
    [
      "django/utils/autoreload.py",
      "BaseReloader.watched_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.snapshot_files"
    ],
    [
      "django/utils/autoreload.py",
      "WatchmanReloader._update_watches"
    ],
    [
      "django/utils/autoreload.py",
      "iter_all_python_module_files"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 109.4 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ],
      "seeds": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ],
      "causal_received": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ],
      "final": [
        [
          "django/utils/autoreload.py",
          "iter_modules_and_files"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 7,
      "causal": 30
    },
    "predicted_function_count": 5,
    "seconds": 109.39046682137996
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 46313,
    "output": 4786
  }
}
```

## 20. django__django-11620

项目：`django/django`；base commit：`514efa3129792ec2abb2444f3e7aeb3f21a38386`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 50.00% | 100.00% | 66.67% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/urls/resolvers.py",
    "django/django/core/exceptions.py",
    "django/django/urls/exceptions.py"
  ],
  "found_modules": [
    "django/django/urls/resolvers.py::RoutePattern"
  ],
  "found_functions": [
    "django/django/urls/resolvers.py::RoutePattern.match"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/views/debug.py",
      "technical_404_response"
    ]
  ],
  "predictions": [
    [
      "django/urls/resolvers.py",
      "RoutePattern.match"
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
      "django/urls/resolvers.py",
      "RoutePattern.match"
    ]
  ],
  "missed_targets": [
    [
      "django/views/debug.py",
      "technical_404_response"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 156.4 秒。

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
    "search_unprocessed_matches": 25,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 17,
      "model_request": 17,
      "model_response": 17,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 32,
      "causal": 8
    },
    "predicted_function_count": 1,
    "seconds": 156.40840136632323
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 58727,
    "output": 5514
  }
}
```

## 21. django__django-11630

项目：`django/django`；base commit：`65e86948b80262574058a94ccaae3a9b59c3faea`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/checks/model_checks.py",
    "django/tests/check_framework/test_model_checks.py"
  ],
  "found_modules": [
    "django/tests/check_framework/test_model_checks.py::DuplicateDBTableTests"
  ],
  "found_functions": [
    "django/django/core/checks/model_checks.py::check_all_models",
    "django/tests/check_framework/test_model_checks.py::DuplicateDBTableTests.test_collision_across_apps",
    "django/tests/check_framework/test_model_checks.py::DuplicateDBTableTests.test_collision_in_same_app"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/checks/model_checks.py",
      "check_all_models"
    ]
  ],
  "predictions": [
    [
      "django/core/checks/model_checks.py",
      "check_all_models"
    ],
    [
      "tests/check_framework/test_model_checks.py",
      "DuplicateDBTableTests.test_collision_across_apps"
    ],
    [
      "tests/check_framework/test_model_checks.py",
      "DuplicateDBTableTests.test_collision_in_same_app"
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
      "django/core/checks/model_checks.py",
      "check_all_models"
    ]
  ],
  "false_positive": [
    [
      "tests/check_framework/test_model_checks.py",
      "DuplicateDBTableTests.test_collision_across_apps"
    ],
    [
      "tests/check_framework/test_model_checks.py",
      "DuplicateDBTableTests.test_collision_in_same_app"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 111.4 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/checks/model_checks.py",
          "check_all_models"
        ]
      ],
      "seeds": [
        [
          "django/core/checks/model_checks.py",
          "check_all_models"
        ]
      ],
      "causal_received": [
        [
          "django/core/checks/model_checks.py",
          "check_all_models"
        ]
      ],
      "final": [
        [
          "django/core/checks/model_checks.py",
          "check_all_models"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 9,
      "model_request": 9,
      "model_response": 9,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 5
    },
    "predicted_function_count": 3,
    "seconds": 111.3682378185913
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 23015,
    "output": 2914
  }
}
```

## 22. django__django-11742

项目：`django/django`；base commit：`fee75d2aed4e58ada6567c464cfd22e89dc65f4a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 100.00% | 28.57% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/__init__.py",
    "django/django/utils/itercompat.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/__init__.py::Field",
    "django/django/db/models/fields/__init__.py::CharField"
  ],
  "found_functions": [
    "django/django/db/models/fields/__init__.py::Field.check",
    "django/django/db/models/fields/__init__.py::Field.__init__",
    "django/django/db/models/fields/__init__.py::Field._get_flatchoices",
    "django/django/db/models/fields/__init__.py::Field._check_choices",
    "django/django/db/models/fields/__init__.py::Field.is_value",
    "django/django/utils/itercompat.py::is_iterable"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field._check_choices"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/__init__.py",
      "<unresolved>:Field.is_value"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__init__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field._check_choices"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field._get_flatchoices"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.check"
    ],
    [
      "django/utils/itercompat.py",
      "is_iterable"
    ]
  ],
  "unresolved": [
    {
      "file": "django/db/models/fields/__init__.py",
      "name": "Field.is_value",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/db/models/fields/__init__.py",
      "Field._check_choices"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/fields/__init__.py",
      "<unresolved>:Field.is_value"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__init__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field._get_flatchoices"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.check"
    ],
    [
      "django/utils/itercompat.py",
      "is_iterable"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 196.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/fields/__init__.py",
          "Field._check_choices"
        ]
      ],
      "seeds": [
        [
          "django/db/models/fields/__init__.py",
          "Field._check_choices"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/__init__.py",
          "Field._check_choices"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/__init__.py",
          "Field._check_choices"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 20,
      "model_request": 20,
      "model_response": 20,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 12,
      "causal_parse": 12,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 5,
      "causal": 102
    },
    "predicted_function_count": 6,
    "seconds": 196.77603626903147
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [
    [
      "django/utils/itercompat.py",
      "is_iterable"
    ]
  ],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 12
  },
  "tokens": {
    "input": 181822,
    "output": 8689
  }
}
```

## 23. django__django-11797

项目：`django/django`；base commit：`3346b78a8a872286a245d1e77ef4718fc5e6be1a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/compiler.py",
    "django/django/db/models/query_utils.py",
    "django/django/db/models/expressions.py",
    "django/django/utils/hashable.py",
    "django/django/db/models/aggregates.py",
    "django/django/db/models/lookups.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/compiler.py::SQLCompiler",
    "django/django/db/models/query_utils.py::QueryWrapper",
    "django/django/db/models/expressions.py::Ref",
    "django/django/db/models/expressions.py::OrderBy",
    "django/django/db/models/aggregates.py::Aggregate",
    "django/django/db/models/lookups.py::Lookup",
    "django/django/db/models/expressions.py::BaseExpression"
  ],
  "found_functions": [
    "django/django/db/models/sql/compiler.py::SQLCompiler.as_subquery_condition",
    "django/django/db/models/sql/compiler.py::SQLCompiler.compile",
    "django/django/db/models/query_utils.py::QueryWrapper.as_sql",
    "django/django/db/models/expressions.py::Ref.as_sql",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_select",
    "django/django/db/models/sql/compiler.py::SQLCompiler.as_sql",
    "django/django/db/models/sql/compiler.py::SQLCompiler.collapse_group_by",
    "django/django/db/models/expressions.py::OrderBy.get_group_by_cols",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_group_by",
    "django/django/db/models/sql/compiler.py::SQLCompiler.pre_sql_setup",
    "django/django/utils/hashable.py::make_hashable",
    "django/django/db/models/aggregates.py::Aggregate.get_group_by_cols",
    "django/django/db/models/lookups.py::Lookup.get_group_by_cols",
    "django/django/db/models/expressions.py::BaseExpression.get_group_by_cols",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_default_columns",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_select_from_parent",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_related_selections"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/lookups.py",
      "Exact.process_rhs"
    ]
  ],
  "predictions": [
    [
      "django/db/models/aggregates.py",
      "Aggregate.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "BaseExpression.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "Ref.as_sql"
    ],
    [
      "django/db/models/lookups.py",
      "Lookup.get_group_by_cols"
    ],
    [
      "django/db/models/query_utils.py",
      "QueryWrapper.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "<unresolved>:SQLCompiler.get_select_from_parent"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_subquery_condition"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.collapse_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.compile"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_default_columns"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_select"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.pre_sql_setup"
    ],
    [
      "django/utils/hashable.py",
      "make_hashable"
    ]
  ],
  "unresolved": [
    {
      "file": "django/db/models/sql/compiler.py",
      "name": "SQLCompiler.get_select_from_parent",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [
    [
      "django/db/models/aggregates.py",
      "Aggregate.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "BaseExpression.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "Ref.as_sql"
    ],
    [
      "django/db/models/lookups.py",
      "Lookup.get_group_by_cols"
    ],
    [
      "django/db/models/query_utils.py",
      "QueryWrapper.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "<unresolved>:SQLCompiler.get_select_from_parent"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_subquery_condition"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.collapse_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.compile"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_default_columns"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_select"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.pre_sql_setup"
    ],
    [
      "django/utils/hashable.py",
      "make_hashable"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/lookups.py",
      "Exact.process_rhs"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 302.9 秒。

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
      "request_preflight": 27,
      "model_request": 27,
      "model_response": 27,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 6,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 19,
      "causal_parse": 19,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 9,
      "relevance": 15,
      "causal": 65
    },
    "predicted_function_count": 17,
    "seconds": 302.89804198779166
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 19
  },
  "tokens": {
    "input": 165576,
    "output": 23821
  }
}
```

## 24. django__django-11815

项目：`django/django`；base commit：`e02f67ef2d03d48128e7a118bf75f0418e24e8ac`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/serializer.py",
    "django/django/db/migrations/writer.py"
  ],
  "found_modules": [
    "django/django/db/migrations/serializer.py::BaseSimpleSerializer",
    "django/django/db/migrations/serializer.py::FloatSerializer",
    "django/django/db/migrations/serializer.py::EnumSerializer",
    "django/django/db/migrations/writer.py::MigrationWriter"
  ],
  "found_functions": [
    "django/django/db/migrations/serializer.py::BaseSimpleSerializer.serialize",
    "django/django/db/migrations/serializer.py::FloatSerializer.serialize",
    "django/django/db/migrations/serializer.py::EnumSerializer.serialize",
    "django/django/db/migrations/writer.py::MigrationWriter.serialize"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/serializer.py",
      "EnumSerializer.serialize"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/serializer.py",
      "BaseSimpleSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "EnumSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "FloatSerializer.serialize"
    ],
    [
      "django/db/migrations/writer.py",
      "MigrationWriter.serialize"
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
      "django/db/migrations/serializer.py",
      "EnumSerializer.serialize"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/serializer.py",
      "BaseSimpleSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "FloatSerializer.serialize"
    ],
    [
      "django/db/migrations/writer.py",
      "MigrationWriter.serialize"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 119.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ],
      "final": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 15,
      "model_request": 15,
      "model_response": 15,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 6,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 3,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 32,
      "causal": 20
    },
    "predicted_function_count": 4,
    "seconds": 119.52056255377829
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "relevance_json": 5,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 30498,
    "output": 5806
  }
}
```

## 25. django__django-11848

项目：`django/django`；base commit：`f0adf3b9b7a19cdee05368ff0c0c2d087f011180`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

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

## 26. django__django-11905

项目：`django/django`；base commit：`2f72480fbd27896c986c45193e1603e35c0b19a7`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/related_lookups.py",
    "django/django/db/models/lookups.py",
    "django/tests/lookup/tests.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/related_lookups.py::RelatedIsNull",
    "django/django/db/models/lookups.py::IsNull",
    "django/tests/lookup/tests.py::LookupTests"
  ],
  "found_functions": [
    "django/tests/lookup/tests.py::LookupTests.test_custom_lookup_none_rhs",
    "django/django/db/models/lookups.py::IsNull.as_sql"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/lookups.py",
      "IsNull.as_sql"
    ]
  ],
  "predictions": [
    [
      "django/db/models/lookups.py",
      "IsNull.as_sql"
    ],
    [
      "tests/lookup/tests.py",
      "LookupTests.test_custom_lookup_none_rhs"
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
      "django/db/models/lookups.py",
      "IsNull.as_sql"
    ]
  ],
  "false_positive": [
    [
      "tests/lookup/tests.py",
      "LookupTests.test_custom_lookup_none_rhs"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 160.1 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/db/models/lookups.py",
          "IsNull.as_sql"
        ]
      ],
      "final": [
        [
          "django/db/models/lookups.py",
          "IsNull.as_sql"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 5,
      "causal": 5
    },
    "predicted_function_count": 2,
    "seconds": 160.11704465001822
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 21627,
    "output": 2251
  }
}
```

## 27. django__django-11910

项目：`django/django`；base commit：`d232fd76a85870daf345fd8f8d617fe7802ae194`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 11.11% | 100.00% | 20.00% | 命中 |

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

## 28. django__django-11964

项目：`django/django`；base commit：`fc2b1cc926e34041953738e58fa6ad3053059b22`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/enums.py"
  ],
  "found_modules": [
    "django/django/db/models/enums.py::Choices",
    "django/django/db/models/enums.py::TextChoices",
    "django/django/db/models/enums.py::ChoicesMeta",
    "django/django/db/models/enums.py::IntegerChoices"
  ],
  "found_functions": []
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/enums.py",
      "Choices.__str__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/models/enums.py",
      "Choices.__str__"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 166.8 秒。

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
    "search_unprocessed_matches": 615,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 19,
      "model_request": 19,
      "model_response": 19,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "search_page_summary": 5,
      "source_receipt": 8,
      "relevance_attempt": 8,
      "relevance_decisions": 8,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 64,
      "causal": 8
    },
    "predicted_function_count": 0,
    "seconds": 166.78835381101817
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 8,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 42602,
    "output": 5063
  }
}
```

## 29. django__django-11999

项目：`django/django`；base commit：`84633905273fc916e3d17883810d9969c03f73c2`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/model_fields/tests.py",
    "django/django/db/models/fields/__init__.py",
    "django/tests/string_lookup/models.py",
    "django/tests/model_fields/models.py",
    "django/tests/string_lookup/tests.py",
    "django/django/db/models/base.py"
  ],
  "found_modules": [
    "django/tests/model_fields/tests.py::GetFieldDisplayTests",
    "django/django/db/models/fields/__init__.py::Field",
    "django/tests/string_lookup/models.py::Whiz",
    "django/tests/model_fields/models.py::WhizDelayed",
    "django/tests/model_fields/models.py::Whiz",
    "django/django/db/models/fields/__init__.py::CharField",
    "django/tests/string_lookup/tests.py::StringLookupTests",
    "django/django/db/models/base.py::Model"
  ],
  "found_functions": [
    "django/tests/model_fields/tests.py::GetFieldDisplayTests.test_get_FIELD_display_translated",
    "django/django/db/models/fields/__init__.py::Field.contribute_to_class",
    "django/tests/model_fields/tests.py::GetFieldDisplayTests.test_choices_and_field_display",
    "django/django/db/models/base.py::Model._get_FIELD_display"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field.contribute_to_class"
    ]
  ],
  "predictions": [
    [
      "django/db/models/base.py",
      "Model._get_FIELD_display"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.contribute_to_class"
    ],
    [
      "tests/model_fields/tests.py",
      "GetFieldDisplayTests.test_choices_and_field_display"
    ],
    [
      "tests/model_fields/tests.py",
      "GetFieldDisplayTests.test_get_FIELD_display_translated"
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
      "django/db/models/fields/__init__.py",
      "Field.contribute_to_class"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/base.py",
      "Model._get_FIELD_display"
    ],
    [
      "tests/model_fields/tests.py",
      "GetFieldDisplayTests.test_choices_and_field_display"
    ],
    [
      "tests/model_fields/tests.py",
      "GetFieldDisplayTests.test_get_FIELD_display_translated"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 188.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [
        [
          "django/db/models/fields/__init__.py",
          "Field.contribute_to_class"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/__init__.py",
          "Field.contribute_to_class"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/__init__.py",
          "Field.contribute_to_class"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 17,
      "model_request": 17,
      "model_response": 17,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 7,
      "causal": 24
    },
    "predicted_function_count": 4,
    "seconds": 188.18023844156414
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 152725,
    "output": 5640
  }
}
```

## 30. django__django-12113

项目：`django/django`；base commit：`62254c5202e80a68f4fe6572a2be46a3d953de1a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/backends/base/creation.py",
    "django/django/db/backends/sqlite3/base.py",
    "django/django/db/backends/base/schema.py",
    "django/django/db/backends/sqlite3/schema.py",
    "django/django/db/transaction.py",
    "django/django/db/backends/sqlite3/features.py",
    "django/django/db/backends/base/base.py",
    "django/django/db/backends/utils.py",
    "django/tests/test_sqlite.py",
    "django/tests/admin_views/test_multidb.py",
    "django/django/db/backends/sqlite3/client.py",
    "django/django/db/backends/mysql/base.py",
    "django/django/db/backends/oracle/base.py",
    "django/django/db/backends/postgresql/base.py",
    "django/django/db/backends/sqlite3/creation.py"
  ],
  "found_modules": [
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation",
    "django/django/db/backends/base/creation.py::TEST_DATABASE_PREFIX",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor",
    "django/tests/admin_views/test_multidb.py::MultiDatabaseTests"
  ],
  "found_functions": [
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.destroy_test_db",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation._create_test_db",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation._destroy_test_db",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation._execute_create_test_db",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.create_test_db",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation._get_test_db_name",
    "django/tests/admin_views/test_multidb.py::MultiDatabaseTests.setUpTestData",
    "django/tests/admin_views/test_multidb.py::MultiDatabaseTests.test_change_view",
    "django/tests/admin_views/test_multidb.py::MultiDatabaseTests.test_add_view",
    "django/tests/admin_views/test_multidb.py::MultiDatabaseTests.test_delete_view"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/backends/sqlite3/creation.py",
      "DatabaseCreation.test_db_signature"
    ]
  ],
  "predictions": [
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._destroy_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._execute_create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._get_test_db_name"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.destroy_test_db"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.setUpTestData"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.test_add_view"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.test_change_view"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.test_delete_view"
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
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._destroy_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._execute_create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation._get_test_db_name"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.destroy_test_db"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.setUpTestData"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.test_add_view"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.test_change_view"
    ],
    [
      "tests/admin_views/test_multidb.py",
      "MultiDatabaseTests.test_delete_view"
    ]
  ],
  "missed_targets": [
    [
      "django/db/backends/sqlite3/creation.py",
      "DatabaseCreation.test_db_signature"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 329.9 秒。

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
    "search_unprocessed_matches": 218,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 32,
      "model_request": 32,
      "model_response": 32,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 22,
      "causal_parse": 22,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 32,
      "causal": 71
    },
    "predicted_function_count": 10,
    "seconds": 329.9045613547787
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 22
  },
  "tokens": {
    "input": 182788,
    "output": 19941
  }
}
```

## 31. django__django-12125

项目：`django/django`；base commit：`89d41cba392b759732ba9f1db4ff29ed47da6a56`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/__init__.py",
    "django/django/db/migrations/operations/models.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/__init__.py::Field",
    "django/django/db/migrations/operations/models.py::CreateModel"
  ],
  "found_functions": [
    "django/django/db/migrations/operations/models.py::CreateModel.deconstruct"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/serializer.py",
      "TypeSerializer.serialize"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/operations/models.py",
      "CreateModel.deconstruct"
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
      "django/db/migrations/operations/models.py",
      "CreateModel.deconstruct"
    ]
  ],
  "missed_targets": [
    [
      "django/db/migrations/serializer.py",
      "TypeSerializer.serialize"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 205.3 秒。

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
    "search_unprocessed_matches": 116,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 14,
      "source_receipt": 13,
      "relevance_attempt": 13,
      "relevance_decisions": 13,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "output_truncated": 2,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 37,
      "causal": 89
    },
    "predicted_function_count": 1,
    "seconds": 205.2881856067106
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 13,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 76109,
    "output": 10837
  }
}
```

## 32. django__django-12184

项目：`django/django`；base commit：`5d674eac871a306405b0fbbaeb17bbeba9c68bf3`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/urls/resolvers.py"
  ],
  "found_modules": [
    "django/django/urls/resolvers.py::RegexPattern"
  ],
  "found_functions": [
    "django/django/urls/resolvers.py::RegexPattern.match",
    "django/django/urls/resolvers.py::_route_to_regex"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/urls/resolvers.py",
      "RegexPattern.match"
    ]
  ],
  "predictions": [
    [
      "django/urls/resolvers.py",
      "RegexPattern.match"
    ],
    [
      "django/urls/resolvers.py",
      "_route_to_regex"
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
      "django/urls/resolvers.py",
      "RegexPattern.match"
    ]
  ],
  "false_positive": [
    [
      "django/urls/resolvers.py",
      "_route_to_regex"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 109.9 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/urls/resolvers.py",
          "RegexPattern.match"
        ]
      ],
      "seeds": [
        [
          "django/urls/resolvers.py",
          "RegexPattern.match"
        ]
      ],
      "causal_received": [
        [
          "django/urls/resolvers.py",
          "RegexPattern.match"
        ]
      ],
      "final": [
        [
          "django/urls/resolvers.py",
          "RegexPattern.match"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 17
    },
    "predicted_function_count": 2,
    "seconds": 109.88453759718686
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 24023,
    "output": 5068
  }
}
```

## 33. django__django-12284

项目：`django/django`；base commit：`c5e373d48cbdd923575956fed477b63d66d9603f`。

状态：empty；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [],
  "found_modules": [],
  "found_functions": []
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field.contribute_to_class"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field.contribute_to_class"
    ]
  ]
}
```

搜索终止：`empty_seeds:search_round_limit`；因果终止：`legacy_causal_stop`；耗时 69.1 秒。

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
      "request_preflight": 15,
      "model_request": 15,
      "model_response": 15,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "search_action_error": 1,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 5,
      "causal": 0
    },
    "predicted_function_count": 0,
    "seconds": 69.12385674845427
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "search_action_repair": 1,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 15457,
    "output": 1300
  }
}
```

## 34. django__django-12286

项目：`django/django`；base commit：`979f61abd322507aafced9627702362e541ec34e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/checks/translation.py",
    "django/tests/check_framework/test_translation.py"
  ],
  "found_modules": [
    "django/tests/check_framework/test_translation.py::TranslationCheckTests"
  ],
  "found_functions": [
    "django/django/core/checks/translation.py::check_language_settings_consistent",
    "django/tests/check_framework/test_translation.py::TranslationCheckTests.test_inconsistent_language_settings"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/checks/translation.py",
      "check_language_settings_consistent"
    ]
  ],
  "predictions": [
    [
      "django/core/checks/translation.py",
      "check_language_settings_consistent"
    ],
    [
      "tests/check_framework/test_translation.py",
      "TranslationCheckTests.test_inconsistent_language_settings"
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
      "django/core/checks/translation.py",
      "check_language_settings_consistent"
    ]
  ],
  "false_positive": [
    [
      "tests/check_framework/test_translation.py",
      "TranslationCheckTests.test_inconsistent_language_settings"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 95.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/checks/translation.py",
          "check_language_settings_consistent"
        ]
      ],
      "seeds": [
        [
          "django/core/checks/translation.py",
          "check_language_settings_consistent"
        ]
      ],
      "causal_received": [
        [
          "django/core/checks/translation.py",
          "check_language_settings_consistent"
        ]
      ],
      "final": [
        [
          "django/core/checks/translation.py",
          "check_language_settings_consistent"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 9,
      "model_request": 9,
      "model_response": 9,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 4,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 2
    },
    "predicted_function_count": 2,
    "seconds": 95.74523327033967
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 10987,
    "output": 1461
  }
}
```

## 35. django__django-12308

项目：`django/django`；base commit：`2e0f04507b17362239ba49830d26fec504d46978`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 14.29% | 100.00% | 25.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/admin/utils.py",
    "django/django/contrib/admin/templatetags/admin_list.py",
    "django/django/forms/fields.py",
    "django/tests/forms_tests/field_tests/test_jsonfield.py"
  ],
  "found_modules": [
    "django/django/forms/fields.py::JSONField",
    "django/tests/forms_tests/field_tests/test_jsonfield.py::JSONFieldTest"
  ],
  "found_functions": [
    "django/django/contrib/admin/utils.py::display_for_value",
    "django/django/contrib/admin/templatetags/admin_list.py::items_for_result",
    "django/django/contrib/admin/utils.py::display_for_field",
    "django/django/forms/fields.py::JSONField.prepare_value",
    "django/tests/forms_tests/field_tests/test_jsonfield.py::JSONFieldTest.test_prepare_value",
    "django/tests/forms_tests/field_tests/test_jsonfield.py::JSONFieldTest.test_custom_encoder_decoder",
    "django/django/contrib/admin/utils.py::lookup_field"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/utils.py",
      "display_for_field"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/templatetags/admin_list.py",
      "items_for_result"
    ],
    [
      "django/contrib/admin/utils.py",
      "display_for_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "display_for_value"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_field"
    ],
    [
      "django/forms/fields.py",
      "JSONField.prepare_value"
    ],
    [
      "tests/forms_tests/field_tests/test_jsonfield.py",
      "JSONFieldTest.test_custom_encoder_decoder"
    ],
    [
      "tests/forms_tests/field_tests/test_jsonfield.py",
      "JSONFieldTest.test_prepare_value"
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
      "django/contrib/admin/utils.py",
      "display_for_field"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/admin/templatetags/admin_list.py",
      "items_for_result"
    ],
    [
      "django/contrib/admin/utils.py",
      "display_for_value"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_field"
    ],
    [
      "django/forms/fields.py",
      "JSONField.prepare_value"
    ],
    [
      "tests/forms_tests/field_tests/test_jsonfield.py",
      "JSONFieldTest.test_custom_encoder_decoder"
    ],
    [
      "tests/forms_tests/field_tests/test_jsonfield.py",
      "JSONFieldTest.test_prepare_value"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 198.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/admin/utils.py",
          "display_for_field"
        ]
      ],
      "seeds": [
        [
          "django/contrib/admin/utils.py",
          "display_for_field"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/admin/utils.py",
          "display_for_field"
        ]
      ],
      "final": [
        [
          "django/contrib/admin/utils.py",
          "display_for_field"
        ]
      ]
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
      "search_result": 6,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 18,
      "causal": 55
    },
    "predicted_function_count": 7,
    "seconds": 198.3372324621305
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
    "input": 76462,
    "output": 4005
  }
}
```

## 36. django__django-12453

项目：`django/django`；base commit：`b330b918e979ea39a21d47b61172d112caf432c3`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 12.50% | 100.00% | 22.22% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/commands/loaddata.py",
    "django/django/db/backends/base/creation.py",
    "django/django/db/migrations/loader.py",
    "django/django/test/testcases.py"
  ],
  "found_modules": [
    "django/django/core/management/commands/loaddata.py::Command",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation",
    "django/django/db/migrations/loader.py::MigrationLoader",
    "django/django/test/testcases.py::TransactionTestCase"
  ],
  "found_functions": [
    "django/django/core/management/commands/loaddata.py::Command.loaddata",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.serialize_db_to_string",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.get_objects",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.deserialize_db_from_string",
    "django/django/test/testcases.py::TransactionTestCase._fixture_setup",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.create_test_db",
    "django/django/db/migrations/loader.py::MigrationLoader.load_disk",
    "django/django/db/migrations/loader.py::MigrationLoader.migrations_module"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.deserialize_db_from_string"
    ]
  ],
  "predictions": [
    [
      "django/core/management/commands/loaddata.py",
      "Command.loaddata"
    ],
    [
      "django/db/backends/base/creation.py",
      "<unresolved>:BaseDatabaseCreation.get_objects"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.deserialize_db_from_string"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.serialize_db_to_string"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.load_disk"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.migrations_module"
    ],
    [
      "django/test/testcases.py",
      "TransactionTestCase._fixture_setup"
    ]
  ],
  "unresolved": [
    {
      "file": "django/db/backends/base/creation.py",
      "name": "BaseDatabaseCreation.get_objects",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.deserialize_db_from_string"
    ]
  ],
  "false_positive": [
    [
      "django/core/management/commands/loaddata.py",
      "Command.loaddata"
    ],
    [
      "django/db/backends/base/creation.py",
      "<unresolved>:BaseDatabaseCreation.get_objects"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.serialize_db_to_string"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.load_disk"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.migrations_module"
    ],
    [
      "django/test/testcases.py",
      "TransactionTestCase._fixture_setup"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 149.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.deserialize_db_from_string"
        ]
      ],
      "seeds": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.deserialize_db_from_string"
        ]
      ],
      "causal_received": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.deserialize_db_from_string"
        ]
      ],
      "final": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.deserialize_db_from_string"
        ]
      ]
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
      "search_result": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 11,
      "causal_parse": 11,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 0,
      "causal": 44
    },
    "predicted_function_count": 8,
    "seconds": 149.03366599790752
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 11
  },
  "tokens": {
    "input": 67194,
    "output": 6642
  }
}
```

## 37. django__django-12470

项目：`django/django`；base commit：`142ab6846ac09d6d401e26fc8b6b988a583ac0f5`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 9.09% | 100.00% | 16.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/compiler.py",
    "django/django/db/models/sql/query.py",
    "django/django/db/models/expressions.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/compiler.py::SQLCompiler",
    "django/django/db/models/expressions.py::OrderBy",
    "django/django/db/models/expressions.py::F",
    "django/django/db/models/sql/query.py::Query"
  ],
  "found_functions": [
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_order_by",
    "django/django/db/models/sql/compiler.py::SQLCompiler.find_ordering_name",
    "django/django/db/models/sql/compiler.py::SQLCompiler.__init__",
    "django/django/db/models/sql/compiler.py::SQLCompiler.as_sql",
    "django/django/db/models/sql/compiler.py::SQLCompiler._setup_joins",
    "django/django/db/models/sql/query.py::get_order_dir",
    "django/django/db/models/expressions.py::OrderBy.asc",
    "django/django/db/models/expressions.py::OrderBy.desc",
    "django/django/db/models/expressions.py::OrderBy.__init__",
    "django/django/db/models/expressions.py::F.asc",
    "django/django/db/models/sql/query.py::Query.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.find_ordering_name"
    ]
  ],
  "predictions": [
    [
      "django/db/models/expressions.py",
      "F.asc"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.__init__"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.asc"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.desc"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.__init__"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler._setup_joins"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.find_ordering_name"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.__init__"
    ],
    [
      "django/db/models/sql/query.py",
      "get_order_dir"
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
      "django/db/models/sql/compiler.py",
      "SQLCompiler.find_ordering_name"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/expressions.py",
      "F.asc"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.__init__"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.asc"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.desc"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.__init__"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler._setup_joins"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.__init__"
    ],
    [
      "django/db/models/sql/query.py",
      "get_order_dir"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 227.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.find_ordering_name"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.find_ordering_name"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 29,
      "model_request": 29,
      "model_response": 29,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 19,
      "causal_parse": 19,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 5,
      "causal": 207
    },
    "predicted_function_count": 11,
    "seconds": 227.72077976353467
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 19
  },
  "tokens": {
    "input": 191173,
    "output": 22160
  }
}
```

## 38. django__django-12497

项目：`django/django`；base commit：`a4881f5e5d7ee38b7e83301331a0b4962845ef8a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/related.py",
    "django/tests/invalid_models_tests/test_relative_fields.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/related.py::ManyToManyField",
    "django/tests/invalid_models_tests/test_relative_fields.py::RelativeFieldTests"
  ],
  "found_functions": [
    "django/django/db/models/fields/related.py::ManyToManyField._check_relationship_model",
    "django/tests/invalid_models_tests/test_relative_fields.py::RelativeFieldTests.test_ambiguous_relationship_model"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/related.py",
      "ManyToManyField._check_relationship_model"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/related.py",
      "ManyToManyField._check_relationship_model"
    ],
    [
      "tests/invalid_models_tests/test_relative_fields.py",
      "RelativeFieldTests.test_ambiguous_relationship_model"
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
      "django/db/models/fields/related.py",
      "ManyToManyField._check_relationship_model"
    ]
  ],
  "false_positive": [
    [
      "tests/invalid_models_tests/test_relative_fields.py",
      "RelativeFieldTests.test_ambiguous_relationship_model"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 116.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/fields/related.py",
          "ManyToManyField._check_relationship_model"
        ]
      ],
      "seeds": [
        [
          "django/db/models/fields/related.py",
          "ManyToManyField._check_relationship_model"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/related.py",
          "ManyToManyField._check_relationship_model"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/related.py",
          "ManyToManyField._check_relationship_model"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 6,
      "model_request": 6,
      "model_response": 6,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 6
    },
    "predicted_function_count": 2,
    "seconds": 115.97143219504505
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 22299,
    "output": 1656
  }
}
```

## 39. django__django-12589

项目：`django/django`；base commit：`895f28f9cbed817c00ab68770433170d83132d90`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 100.00% | 28.57% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/expressions.py",
    "django/django/db/models/sql/compiler.py",
    "django/django/db/models/sql/query.py"
  ],
  "found_modules": [
    "django/django/db/models/expressions.py::Ref",
    "django/django/db/models/sql/compiler.py::SQLCompiler",
    "django/django/db/models/sql/query.py::Query",
    "django/django/db/models/expressions.py::BaseExpression",
    "django/django/db/models/expressions.py::OrderBy"
  ],
  "found_functions": [
    "django/django/db/models/expressions.py::Ref.get_group_by_cols",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_group_by",
    "django/django/db/models/sql/query.py::Query.set_group_by",
    "django/django/db/models/expressions.py::BaseExpression.get_group_by_cols",
    "django/django/db/models/expressions.py::OrderBy.get_group_by_cols",
    "django/django/db/models/sql/compiler.py::SQLCompiler.collapse_group_by"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query.set_group_by"
    ]
  ],
  "predictions": [
    [
      "django/db/models/expressions.py",
      "BaseExpression.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "Ref.get_group_by_cols"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.collapse_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.set_group_by"
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
      "django/db/models/sql/query.py",
      "Query.set_group_by"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/expressions.py",
      "BaseExpression.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "OrderBy.get_group_by_cols"
    ],
    [
      "django/db/models/expressions.py",
      "Ref.get_group_by_cols"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.collapse_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 177.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/db/models/sql/query.py",
          "Query.set_group_by"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/query.py",
          "Query.set_group_by"
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
      "seed_locations": 1,
      "causal_context": 10,
      "causal_parse": 10,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 28
    },
    "predicted_function_count": 6,
    "seconds": 177.2011667145416
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2,
    "duplicate_new_source_binding_changed": 3
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 10
  },
  "tokens": {
    "input": 62620,
    "output": 10019
  }
}
```

## 40. django__django-12700

项目：`django/django`；base commit：`d51c50d836c5cf8db5566da17963f871be554615`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/views/debug.py"
  ],
  "found_modules": [
    "django/django/views/debug.py::SafeExceptionReporterFilter"
  ],
  "found_functions": [
    "django/django/views/debug.py::SafeExceptionReporterFilter.cleanse_setting",
    "django/django/views/debug.py::SafeExceptionReporterFilter.get_safe_settings"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/views/debug.py",
      "SafeExceptionReporterFilter.cleanse_setting"
    ]
  ],
  "predictions": [
    [
      "django/views/debug.py",
      "SafeExceptionReporterFilter.cleanse_setting"
    ],
    [
      "django/views/debug.py",
      "SafeExceptionReporterFilter.get_safe_settings"
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
      "django/views/debug.py",
      "SafeExceptionReporterFilter.cleanse_setting"
    ]
  ],
  "false_positive": [
    [
      "django/views/debug.py",
      "SafeExceptionReporterFilter.get_safe_settings"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 114.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/views/debug.py",
          "SafeExceptionReporterFilter.cleanse_setting"
        ]
      ],
      "seeds": [
        [
          "django/views/debug.py",
          "SafeExceptionReporterFilter.cleanse_setting"
        ]
      ],
      "causal_received": [
        [
          "django/views/debug.py",
          "SafeExceptionReporterFilter.cleanse_setting"
        ]
      ],
      "final": [
        [
          "django/views/debug.py",
          "SafeExceptionReporterFilter.cleanse_setting"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 8,
      "causal": 7
    },
    "predicted_function_count": 2,
    "seconds": 114.68060819152743
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 22310,
    "output": 2113
  }
}
```

## 41. django__django-12708

项目：`django/django`；base commit：`447980e72ac01da1594dd3373a03ba40b7ee6f80`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/backends/base/schema.py"
  ],
  "found_modules": [
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor"
  ],
  "found_functions": [
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._delete_composed_index",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._constraint_names",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.alter_index_together",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.alter_unique_together"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_index_together"
    ]
  ],
  "predictions": [
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._constraint_names"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._delete_composed_index"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_index_together"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_unique_together"
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
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_index_together"
    ]
  ],
  "false_positive": [
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._constraint_names"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._delete_composed_index"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_unique_together"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 203.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/backends/base/schema.py",
          "BaseDatabaseSchemaEditor.alter_index_together"
        ]
      ],
      "seeds": [
        [
          "django/db/backends/base/schema.py",
          "BaseDatabaseSchemaEditor.alter_index_together"
        ]
      ],
      "causal_received": [
        [
          "django/db/backends/base/schema.py",
          "BaseDatabaseSchemaEditor.alter_index_together"
        ]
      ],
      "final": [
        [
          "django/db/backends/base/schema.py",
          "BaseDatabaseSchemaEditor.alter_index_together"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 12,
      "causal": 17
    },
    "predicted_function_count": 4,
    "seconds": 202.9577055843547
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 36692,
    "output": 6219
  }
}
```

## 42. django__django-12747

项目：`django/django`；base commit：`c86201b6ed4f8256b0a0520c08aa674f623d4127`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 14.29% | 100.00% | 25.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/deletion.py",
    "django/tests/delete/tests.py",
    "django/django/db/models/query.py"
  ],
  "found_modules": [
    "django/django/db/models/deletion.py::Collector",
    "django/tests/delete/tests.py::FastDeleteTests",
    "django/django/db/models/query.py::QuerySet"
  ],
  "found_functions": [
    "django/django/db/models/deletion.py::Collector._has_signal_listeners",
    "django/django/db/models/deletion.py::Collector.can_fast_delete",
    "django/django/db/models/deletion.py::get_candidate_relations_to_delete",
    "django/django/db/models/deletion.py::Collector.collect",
    "django/tests/delete/tests.py::FastDeleteTests.test_fast_delete_instance_set_pk_none",
    "django/django/db/models/deletion.py::Collector.delete",
    "django/django/db/models/query.py::QuerySet.delete"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/deletion.py",
      "Collector.delete"
    ]
  ],
  "predictions": [
    [
      "django/db/models/deletion.py",
      "Collector._has_signal_listeners"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.can_fast_delete"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.collect"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.delete"
    ],
    [
      "django/db/models/deletion.py",
      "get_candidate_relations_to_delete"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.delete"
    ],
    [
      "tests/delete/tests.py",
      "FastDeleteTests.test_fast_delete_instance_set_pk_none"
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
      "django/db/models/deletion.py",
      "Collector.delete"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/deletion.py",
      "Collector._has_signal_listeners"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.can_fast_delete"
    ],
    [
      "django/db/models/deletion.py",
      "Collector.collect"
    ],
    [
      "django/db/models/deletion.py",
      "get_candidate_relations_to_delete"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.delete"
    ],
    [
      "tests/delete/tests.py",
      "FastDeleteTests.test_fast_delete_instance_set_pk_none"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 250.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ],
      "seeds": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ],
      "final": [
        [
          "django/db/models/deletion.py",
          "Collector.delete"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 22,
      "model_request": 22,
      "model_response": 22,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 11,
      "causal_parse": 11,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 7,
      "relevance": 33,
      "causal": 30
    },
    "predicted_function_count": 7,
    "seconds": 250.7484837276861
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 11
  },
  "tokens": {
    "input": 89356,
    "output": 8621
  }
}
```

## 43. django__django-12856

项目：`django/django`；base commit：`8328811f048fed0dd22573224def8c65410c9f2e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/base.py",
    "django/django/db/models/constraints.py"
  ],
  "found_modules": [
    "django/django/db/models/base.py::Model",
    "django/django/db/models/constraints.py::UniqueConstraint"
  ],
  "found_functions": [
    "django/django/db/models/base.py::Model._check_constraints",
    "django/django/db/models/base.py::Model._check_local_fields",
    "django/django/db/models/base.py::Model.check"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/base.py",
      "Model._check_constraints"
    ]
  ],
  "predictions": [
    [
      "django/db/models/base.py",
      "Model._check_constraints"
    ],
    [
      "django/db/models/base.py",
      "Model._check_local_fields"
    ],
    [
      "django/db/models/base.py",
      "Model.check"
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
      "django/db/models/base.py",
      "Model._check_constraints"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/base.py",
      "Model._check_local_fields"
    ],
    [
      "django/db/models/base.py",
      "Model.check"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 142.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/base.py",
          "Model._check_constraints"
        ]
      ],
      "seeds": [
        [
          "django/db/models/base.py",
          "Model._check_constraints"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/base.py",
          "Model._check_constraints"
        ]
      ],
      "final": [
        [
          "django/db/models/base.py",
          "Model._check_constraints"
        ]
      ]
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
      "search_result": 7,
      "search_page_summary": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 26,
      "causal": 38
    },
    "predicted_function_count": 3,
    "seconds": 142.48442270606756
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 44486,
    "output": 2711
  }
}
```

## 44. django__django-12908

项目：`django/django`；base commit：`49ae7ce50a874f8a04cd910882fb9571ff3a0d7a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 11.11% | 100.00% | 20.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/query.py",
    "django/django/db/models/sql/compiler.py",
    "django/django/db/models/sql/query.py"
  ],
  "found_modules": [
    "django/django/db/models/query.py::QuerySet",
    "django/django/db/models/sql/compiler.py::SQLCompiler",
    "django/django/db/models/sql/query.py::Query"
  ],
  "found_functions": [
    "django/django/db/models/query.py::QuerySet._combinator_query",
    "django/django/db/models/query.py::QuerySet.union",
    "django/django/db/models/query.py::QuerySet.intersection",
    "django/django/db/models/query.py::QuerySet.difference",
    "django/django/db/models/sql/compiler.py::SQLCompiler.as_sql",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_combinator_sql",
    "django/django/db/models/query.py::QuerySet.distinct",
    "django/django/db/models/sql/query.py::Query.add_distinct_fields",
    "django/django/db/models/query.py::QuerySet._chain"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/query.py",
      "QuerySet.distinct"
    ]
  ],
  "predictions": [
    [
      "django/db/models/query.py",
      "QuerySet._chain"
    ],
    [
      "django/db/models/query.py",
      "QuerySet._combinator_query"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.difference"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.distinct"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.intersection"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.union"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_combinator_sql"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_distinct_fields"
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
      "django/db/models/query.py",
      "QuerySet.distinct"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/query.py",
      "QuerySet._chain"
    ],
    [
      "django/db/models/query.py",
      "QuerySet._combinator_query"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.difference"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.intersection"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.union"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.as_sql"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_combinator_sql"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_distinct_fields"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 239.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/query.py",
          "QuerySet.distinct"
        ]
      ],
      "seeds": [
        [
          "django/db/models/query.py",
          "QuerySet.distinct"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/query.py",
          "QuerySet.distinct"
        ]
      ],
      "final": [
        [
          "django/db/models/query.py",
          "QuerySet.distinct"
        ]
      ]
    },
    "search_unprocessed_matches": 91,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 22,
      "model_request": 22,
      "model_response": 22,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 13,
      "causal_parse": 13,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 10,
      "relevance": 32,
      "causal": 110
    },
    "predicted_function_count": 9,
    "seconds": 238.9920179983601
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 13
  },
  "tokens": {
    "input": 119940,
    "output": 8665
  }
}
```

## 45. django__django-12915

项目：`django/django`；base commit：`4652f1f0aa459a7b980441d629648707c32e36bf`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/staticfiles/handlers.py",
    "django/django/core/handlers/base.py"
  ],
  "found_modules": [
    "django/django/contrib/staticfiles/handlers.py::StaticFilesHandlerMixin",
    "django/django/contrib/staticfiles/handlers.py::ASGIStaticFilesHandler",
    "django/django/core/handlers/base.py::BaseHandler"
  ],
  "found_functions": [
    "django/django/contrib/staticfiles/handlers.py::StaticFilesHandlerMixin.get_response",
    "django/django/contrib/staticfiles/handlers.py::ASGIStaticFilesHandler.__call__",
    "django/django/core/handlers/base.py::BaseHandler.get_response_async",
    "django/django/contrib/staticfiles/handlers.py::ASGIStaticFilesHandler.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/staticfiles/handlers.py",
      "StaticFilesHandlerMixin.get_response_async"
    ]
  ],
  "predictions": [
    [
      "django/contrib/staticfiles/handlers.py",
      "ASGIStaticFilesHandler.__call__"
    ],
    [
      "django/contrib/staticfiles/handlers.py",
      "ASGIStaticFilesHandler.__init__"
    ],
    [
      "django/contrib/staticfiles/handlers.py",
      "StaticFilesHandlerMixin.get_response"
    ],
    [
      "django/core/handlers/base.py",
      "BaseHandler.get_response_async"
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
      "django/contrib/staticfiles/handlers.py",
      "ASGIStaticFilesHandler.__call__"
    ],
    [
      "django/contrib/staticfiles/handlers.py",
      "ASGIStaticFilesHandler.__init__"
    ],
    [
      "django/contrib/staticfiles/handlers.py",
      "StaticFilesHandlerMixin.get_response"
    ],
    [
      "django/core/handlers/base.py",
      "BaseHandler.get_response_async"
    ]
  ],
  "missed_targets": [
    [
      "django/contrib/staticfiles/handlers.py",
      "StaticFilesHandlerMixin.get_response_async"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 133.6 秒。

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
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 29,
      "causal": 14
    },
    "predicted_function_count": 4,
    "seconds": 133.64773578103632
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 26926,
    "output": 4526
  }
}
```

## 46. django__django-12983

项目：`django/django`；base commit：`3bc4240d979812bd11365ede04c028ea13fdc8c6`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/text.py",
    "django/django/template/defaultfilters.py"
  ],
  "found_modules": [],
  "found_functions": [
    "django/django/utils/text.py::slugify",
    "django/django/template/defaultfilters.py::slugify"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/text.py",
      "slugify"
    ]
  ],
  "predictions": [
    [
      "django/template/defaultfilters.py",
      "slugify"
    ],
    [
      "django/utils/text.py",
      "slugify"
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
      "django/utils/text.py",
      "slugify"
    ]
  ],
  "false_positive": [
    [
      "django/template/defaultfilters.py",
      "slugify"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 104.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/utils/text.py",
          "slugify"
        ]
      ],
      "seeds": [
        [
          "django/utils/text.py",
          "slugify"
        ]
      ],
      "causal_received": [
        [
          "django/utils/text.py",
          "slugify"
        ]
      ],
      "final": [
        [
          "django/utils/text.py",
          "slugify"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 5,
      "model_request": 5,
      "model_response": 5,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 8
    },
    "predicted_function_count": 2,
    "seconds": 103.96511556394398
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 7600,
    "output": 886
  }
}
```

## 47. django__django-13028

项目：`django/django`；base commit：`78ad4b4b0201003792bfdbf1a7781cbc9ee03539`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 9.09% | 100.00% | 16.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/query.py",
    "django/django/db/models/expressions.py",
    "django/django/db/models/query.py",
    "django/django/db/models/query_utils.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/query.py::Query",
    "django/django/db/models/expressions.py::BaseExpression",
    "django/django/db/models/query.py::QuerySet",
    "django/django/db/models/query_utils.py::Q",
    "django/django/db/models/expressions.py::Ref",
    "django/django/db/models/expressions.py::OuterRef"
  ],
  "found_functions": [
    "django/django/db/models/sql/query.py::Query.resolve_lookup_value",
    "django/django/db/models/expressions.py::BaseExpression.resolve_expression",
    "django/django/db/models/expressions.py::BaseExpression.copy",
    "django/django/db/models/sql/query.py::Query.resolve_expression",
    "django/django/db/models/query.py::QuerySet.resolve_expression",
    "django/django/db/models/query_utils.py::Q.resolve_expression",
    "django/django/db/models/expressions.py::Ref.resolve_expression",
    "django/django/db/models/expressions.py::OuterRef.resolve_expression",
    "django/django/db/models/sql/query.py::Query.check_filterable",
    "django/django/db/models/sql/query.py::Query.build_filter",
    "django/django/db/models/sql/query.py::Query._add_q"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query.check_filterable"
    ]
  ],
  "predictions": [
    [
      "django/db/models/expressions.py",
      "BaseExpression.copy"
    ],
    [
      "django/db/models/expressions.py",
      "BaseExpression.resolve_expression"
    ],
    [
      "django/db/models/expressions.py",
      "OuterRef.resolve_expression"
    ],
    [
      "django/db/models/expressions.py",
      "Ref.resolve_expression"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.resolve_expression"
    ],
    [
      "django/db/models/query_utils.py",
      "Q.resolve_expression"
    ],
    [
      "django/db/models/sql/query.py",
      "Query._add_q"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.build_filter"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.check_filterable"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.resolve_expression"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.resolve_lookup_value"
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
      "django/db/models/sql/query.py",
      "Query.check_filterable"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/expressions.py",
      "BaseExpression.copy"
    ],
    [
      "django/db/models/expressions.py",
      "BaseExpression.resolve_expression"
    ],
    [
      "django/db/models/expressions.py",
      "OuterRef.resolve_expression"
    ],
    [
      "django/db/models/expressions.py",
      "Ref.resolve_expression"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.resolve_expression"
    ],
    [
      "django/db/models/query_utils.py",
      "Q.resolve_expression"
    ],
    [
      "django/db/models/sql/query.py",
      "Query._add_q"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.build_filter"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.resolve_expression"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.resolve_lookup_value"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 235.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/sql/query.py",
          "Query.check_filterable"
        ]
      ],
      "seeds": [
        [
          "django/db/models/sql/query.py",
          "Query.check_filterable"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/query.py",
          "Query.check_filterable"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/query.py",
          "Query.check_filterable"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 19,
      "model_request": 19,
      "model_response": 19,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 14,
      "causal_parse": 14,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 0,
      "causal": 143
    },
    "predicted_function_count": 11,
    "seconds": 235.30546371545643
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 3
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 14
  },
  "tokens": {
    "input": 135598,
    "output": 21149
  }
}
```

## 48. django__django-13033

项目：`django/django`；base commit：`a59de6e89e8dc1f3e71c9a5a5bbceb373ea5247e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/compiler.py",
    "django/django/db/models/sql/query.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/compiler.py::SQLCompiler",
    "django/django/db/models/sql/query.py::Query"
  ],
  "found_functions": [
    "django/django/db/models/sql/compiler.py::SQLCompiler.find_ordering_name",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_order_by",
    "django/django/db/models/sql/query.py::Query.setup_joins"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.find_ordering_name"
    ]
  ],
  "predictions": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.find_ordering_name"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.setup_joins"
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
      "django/db/models/sql/compiler.py",
      "SQLCompiler.find_ordering_name"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.setup_joins"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 121.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.find_ordering_name"
        ]
      ],
      "seeds": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.find_ordering_name"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.find_ordering_name"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.find_ordering_name"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 28
    },
    "predicted_function_count": 3,
    "seconds": 121.01919655501842
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 51263,
    "output": 3094
  }
}
```

## 49. django__django-13158

项目：`django/django`；base commit：`7af8f4127397279d19ef7c7899e93018274e2f9b`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 50.00% | 25.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/related_descriptors.py",
    "django/django/db/models/query.py",
    "django/django/db/models/sql/query.py",
    "django/django/db/models/sql/where.py"
  ],
  "found_modules": [
    "django/django/db/models/query.py::QuerySet",
    "django/django/db/models/sql/query.py::Query",
    "django/django/db/models/sql/where.py::NothingNode"
  ],
  "found_functions": [
    "django/django/db/models/fields/related_descriptors.py::create_reverse_many_to_one_manager",
    "django/django/db/models/query.py::QuerySet.none",
    "django/django/db/models/sql/query.py::Query.set_empty",
    "django/django/db/models/sql/query.py::Query.is_empty",
    "django/django/db/models/query.py::QuerySet._chain",
    "django/django/db/models/sql/where.py::NothingNode.as_sql"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query.clone"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.set_empty"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/related_descriptors.py",
      "create_reverse_many_to_one_manager"
    ],
    [
      "django/db/models/query.py",
      "QuerySet._chain"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.none"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.is_empty"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.set_empty"
    ],
    [
      "django/db/models/sql/where.py",
      "NothingNode.as_sql"
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
      "django/db/models/sql/query.py",
      "Query.set_empty"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/fields/related_descriptors.py",
      "create_reverse_many_to_one_manager"
    ],
    [
      "django/db/models/query.py",
      "QuerySet._chain"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.none"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.is_empty"
    ],
    [
      "django/db/models/sql/where.py",
      "NothingNode.as_sql"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/sql/query.py",
      "Query.clone"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 200.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖部分目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/sql/query.py",
          "Query.set_empty"
        ]
      ],
      "seeds": [
        [
          "django/db/models/sql/query.py",
          "Query.set_empty"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/query.py",
          "Query.clone"
        ],
        [
          "django/db/models/sql/query.py",
          "Query.set_empty"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/query.py",
          "Query.set_empty"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 18,
      "model_request": 18,
      "model_response": 18,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 13,
      "causal_parse": 13,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 0,
      "causal": 191
    },
    "predicted_function_count": 6,
    "seconds": 200.19945679605007
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 13
  },
  "tokens": {
    "input": 103547,
    "output": 10028
  }
}
```

## 50. django__django-13220

项目：`django/django`；base commit：`16218c20606d8cd89c5393970c83da04598a3e04`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/exceptions.py"
  ],
  "found_modules": [
    "django/django/core/exceptions.py::ValidationError"
  ],
  "found_functions": [
    "django/django/core/exceptions.py::ValidationError.__init__",
    "django/django/core/exceptions.py::ValidationError.messages"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/exceptions.py",
      "ValidationError.__eq__"
    ],
    [
      "django/core/exceptions.py",
      "ValidationError.__hash__"
    ]
  ],
  "predictions": [
    [
      "django/core/exceptions.py",
      "ValidationError.__init__"
    ],
    [
      "django/core/exceptions.py",
      "ValidationError.messages"
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
      "django/core/exceptions.py",
      "ValidationError.__init__"
    ],
    [
      "django/core/exceptions.py",
      "ValidationError.messages"
    ]
  ],
  "missed_targets": [
    [
      "django/core/exceptions.py",
      "ValidationError.__eq__"
    ],
    [
      "django/core/exceptions.py",
      "ValidationError.__hash__"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 115.0 秒。

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
    "search_unprocessed_matches": 827,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "search_page_summary": 5,
      "source_receipt": 10,
      "relevance_attempt": 10,
      "relevance_decisions": 10,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 64,
      "causal": 59
    },
    "predicted_function_count": 2,
    "seconds": 114.95345044508576
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 10,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 88804,
    "output": 4772
  }
}
```

## 51. django__django-13230

项目：`django/django`；base commit：`184a6eebb0ef56d5f1b1315a8e666830e37f3f81`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/syndication/views.py",
    "django/django/utils/feedgenerator.py"
  ],
  "found_modules": [
    "django/django/contrib/syndication/views.py::Feed",
    "django/django/utils/feedgenerator.py::SyndicationFeed"
  ],
  "found_functions": [
    "django/django/contrib/syndication/views.py::Feed.item_extra_kwargs",
    "django/django/utils/feedgenerator.py::SyndicationFeed.add_item"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/syndication/views.py",
      "Feed.get_feed"
    ]
  ],
  "predictions": [
    [
      "django/contrib/syndication/views.py",
      "Feed.item_extra_kwargs"
    ],
    [
      "django/utils/feedgenerator.py",
      "SyndicationFeed.add_item"
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
      "django/contrib/syndication/views.py",
      "Feed.item_extra_kwargs"
    ],
    [
      "django/utils/feedgenerator.py",
      "SyndicationFeed.add_item"
    ]
  ],
  "missed_targets": [
    [
      "django/contrib/syndication/views.py",
      "Feed.get_feed"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 114.8 秒。

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
          "django/contrib/syndication/views.py",
          "Feed.get_feed"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 16
    },
    "predicted_function_count": 2,
    "seconds": 114.82804276794195
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 17498,
    "output": 2142
  }
}
```

## 52. django__django-13265

项目：`django/django`；base commit：`b2b0711b555fa292751763c2df4fe577c396f265`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/operations/models.py"
  ],
  "found_modules": [
    "django/django/db/migrations/operations/models.py::AlterOrderWithRespectTo",
    "django/django/db/migrations/operations/models.py::AddIndex"
  ],
  "found_functions": []
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._detect_changes"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_created_models"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._detect_changes"
    ],
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector.generate_created_models"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 100.6 秒。

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
    "search_unprocessed_matches": 336,
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
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 37,
      "causal": 15
    },
    "predicted_function_count": 0,
    "seconds": 100.64418791793287
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 30582,
    "output": 2351
  }
}
```

## 53. django__django-13315

项目：`django/django`；base commit：`36bc47069ce071e80c8129500de3b8664d2058a7`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/models.py",
    "django/django/db/models/fields/related.py"
  ],
  "found_modules": [
    "django/django/forms/models.py::ModelChoiceField",
    "django/django/db/models/fields/related.py::RelatedField",
    "django/django/forms/models.py::ModelChoiceIterator"
  ],
  "found_functions": [
    "django/django/forms/models.py::ModelChoiceField.__init__",
    "django/django/forms/models.py::ModelChoiceField._get_queryset",
    "django/django/forms/models.py::ModelChoiceField._get_choices",
    "django/django/db/models/fields/related.py::RelatedField.formfield",
    "django/django/forms/models.py::ModelChoiceField.get_limit_choices_to"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/models.py",
      "apply_limit_choices_to_to_formfield"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/related.py",
      "RelatedField.formfield"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField.__init__"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField._get_choices"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField._get_queryset"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField.get_limit_choices_to"
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
      "django/db/models/fields/related.py",
      "RelatedField.formfield"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField.__init__"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField._get_choices"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField._get_queryset"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceField.get_limit_choices_to"
    ]
  ],
  "missed_targets": [
    [
      "django/forms/models.py",
      "apply_limit_choices_to_to_formfield"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 156.9 秒。

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
          "django/forms/models.py",
          "apply_limit_choices_to_to_formfield"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 2,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 18,
      "model_request": 18,
      "model_response": 18,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 32,
      "causal": 30
    },
    "predicted_function_count": 5,
    "seconds": 156.90967030730098
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 35343,
    "output": 4385
  }
}
```

## 54. django__django-13321

项目：`django/django`；base commit：`35b03788b0607c1f8d2b64e4fa9e1669b0907ea4`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/sessions/backends/base.py"
  ],
  "found_modules": [
    "django/django/contrib/sessions/backends/base.py::SessionBase"
  ],
  "found_functions": [
    "django/django/contrib/sessions/backends/base.py::SessionBase._legacy_decode",
    "django/django/contrib/sessions/backends/base.py::SessionBase.decode"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/sessions/backends/base.py",
      "SessionBase.decode"
    ]
  ],
  "predictions": [
    [
      "django/contrib/sessions/backends/base.py",
      "SessionBase._legacy_decode"
    ],
    [
      "django/contrib/sessions/backends/base.py",
      "SessionBase.decode"
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
      "django/contrib/sessions/backends/base.py",
      "SessionBase.decode"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/sessions/backends/base.py",
      "SessionBase._legacy_decode"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 109.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/sessions/backends/base.py",
          "SessionBase.decode"
        ]
      ],
      "seeds": [
        [
          "django/contrib/sessions/backends/base.py",
          "SessionBase.decode"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/sessions/backends/base.py",
          "SessionBase.decode"
        ]
      ],
      "final": [
        [
          "django/contrib/sessions/backends/base.py",
          "SessionBase.decode"
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
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 16,
      "causal": 12
    },
    "predicted_function_count": 2,
    "seconds": 109.27543614245951
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "relevance_json": 3,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 30157,
    "output": 2266
  }
}
```

## 55. django__django-13401

项目：`django/django`；base commit：`453967477e3ddae704cd739eac2449c0e13d464c`。

状态：complete；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 33.33% | 28.57% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 100.00% | 100.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/__init__.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/__init__.py::Field"
  ],
  "found_functions": [
    "django/django/db/models/fields/__init__.py::Field.__eq__",
    "django/django/db/models/fields/__init__.py::Field.__hash__",
    "django/django/db/models/fields/__init__.py::Field.__lt__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field.__eq__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__hash__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__lt__"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/__init__.py",
      "Field.__eq__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__hash__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__lt__"
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
      "django/db/models/fields/__init__.py",
      "Field.__eq__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__hash__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "Field.__lt__"
    ]
  ],
  "false_positive": [],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 152.6 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/fields/__init__.py",
          "Field.__eq__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__lt__"
        ]
      ],
      "seeds": [
        [
          "django/db/models/fields/__init__.py",
          "Field.__eq__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__hash__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__lt__"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/__init__.py",
          "Field.__eq__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__hash__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__lt__"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/__init__.py",
          "Field.__eq__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__hash__"
        ],
        [
          "django/db/models/fields/__init__.py",
          "Field.__lt__"
        ]
      ]
    },
    "search_unprocessed_matches": 25,
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
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 32,
      "causal": 3
    },
    "predicted_function_count": 3,
    "seconds": 152.56306265108287
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 20801,
    "output": 2116
  }
}
```

## 56. django__django-13447

项目：`django/django`；base commit：`0456d3e42795481a186db05719300691fe2a1029`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/admin_views/customadmin.py",
    "django/django/contrib/admin/sites.py"
  ],
  "found_modules": [
    "django/tests/admin_views/customadmin.py::Admin2",
    "django/django/contrib/admin/sites.py::AdminSite"
  ],
  "found_functions": [
    "django/tests/admin_views/customadmin.py::Admin2.index",
    "django/django/contrib/admin/sites.py::AdminSite._build_app_dict",
    "django/django/contrib/admin/sites.py::AdminSite.app_index",
    "django/django/contrib/admin/sites.py::AdminSite.get_app_list"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/sites.py",
      "AdminSite._build_app_dict"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/sites.py",
      "AdminSite._build_app_dict"
    ],
    [
      "django/contrib/admin/sites.py",
      "AdminSite.app_index"
    ],
    [
      "django/contrib/admin/sites.py",
      "AdminSite.get_app_list"
    ],
    [
      "tests/admin_views/customadmin.py",
      "Admin2.index"
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
      "django/contrib/admin/sites.py",
      "AdminSite._build_app_dict"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/admin/sites.py",
      "AdminSite.app_index"
    ],
    [
      "django/contrib/admin/sites.py",
      "AdminSite.get_app_list"
    ],
    [
      "tests/admin_views/customadmin.py",
      "Admin2.index"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 117.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/admin/sites.py",
          "AdminSite._build_app_dict"
        ]
      ],
      "seeds": [
        [
          "django/contrib/admin/sites.py",
          "AdminSite._build_app_dict"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/admin/sites.py",
          "AdminSite._build_app_dict"
        ]
      ],
      "final": [
        [
          "django/contrib/admin/sites.py",
          "AdminSite._build_app_dict"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 7,
      "causal": 10
    },
    "predicted_function_count": 4,
    "seconds": 117.48206822574139
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 27365,
    "output": 3022
  }
}
```

## 57. django__django-13448

项目：`django/django`；base commit：`7b9596b974fb0ad1868b10c8c2174e10b72be403`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/backends/base/creation.py"
  ],
  "found_modules": [
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation"
  ],
  "found_functions": [
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.create_test_db",
    "django/django/db/backends/base/creation.py::BaseDatabaseCreation.serialize_db_to_string"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ]
  ],
  "predictions": [
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ],
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.serialize_db_to_string"
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
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.create_test_db"
    ]
  ],
  "false_positive": [
    [
      "django/db/backends/base/creation.py",
      "BaseDatabaseCreation.serialize_db_to_string"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 91.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.create_test_db"
        ]
      ],
      "seeds": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.create_test_db"
        ]
      ],
      "causal_received": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.create_test_db"
        ]
      ],
      "final": [
        [
          "django/db/backends/base/creation.py",
          "BaseDatabaseCreation.create_test_db"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 10,
      "model_request": 10,
      "model_response": 10,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 5,
      "causal": 7
    },
    "predicted_function_count": 2,
    "seconds": 91.66568428371102
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 34129,
    "output": 2096
  }
}
```

## 58. django__django-13551

项目：`django/django`；base commit：`7f9e4524d6b23424cf44fbe1bf1f4e70f6bb066e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 10.00% | 100.00% | 18.18% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 20.00% | 100.00% | 33.33% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/auth/tokens.py",
    "django/django/utils/crypto.py"
  ],
  "found_modules": [
    "django/django/contrib/auth/tokens.py::PasswordResetTokenGenerator"
  ],
  "found_functions": [
    "django/django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_hash_value",
    "django/django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_token_with_timestamp",
    "django/django/contrib/auth/tokens.py::PasswordResetTokenGenerator.check_token",
    "django/django/contrib/auth/tokens.py::PasswordResetTokenGenerator.make_token",
    "django/django/utils/crypto.py::salted_hmac"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator._make_hash_value"
    ]
  ],
  "predictions": [
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator._make_hash_value"
    ],
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator._make_token_with_timestamp"
    ],
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator.check_token"
    ],
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator.make_token"
    ],
    [
      "django/utils/crypto.py",
      "salted_hmac"
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
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator._make_hash_value"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator._make_token_with_timestamp"
    ],
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator.check_token"
    ],
    [
      "django/contrib/auth/tokens.py",
      "PasswordResetTokenGenerator.make_token"
    ],
    [
      "django/utils/crypto.py",
      "salted_hmac"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 126.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/auth/tokens.py",
          "PasswordResetTokenGenerator._make_hash_value"
        ]
      ],
      "seeds": [
        [
          "django/contrib/auth/tokens.py",
          "PasswordResetTokenGenerator._make_hash_value"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/auth/tokens.py",
          "PasswordResetTokenGenerator._make_hash_value"
        ]
      ],
      "final": [
        [
          "django/contrib/auth/tokens.py",
          "PasswordResetTokenGenerator._make_hash_value"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 4,
      "search_page_summary": 4,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 28
    },
    "predicted_function_count": 5,
    "seconds": 126.79969184752554
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 30438,
    "output": 4630
  }
}
```

## 59. django__django-13590

项目：`django/django`；base commit：`755dbf39fcdc491fe9b588358303e259c7750be4`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 100.00% | 100.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/query.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/query.py::Query"
  ],
  "found_functions": [
    "django/django/db/models/sql/query.py::Query.resolve_lookup_value"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query.resolve_lookup_value"
    ]
  ],
  "predictions": [
    [
      "django/db/models/sql/query.py",
      "Query.resolve_lookup_value"
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
      "django/db/models/sql/query.py",
      "Query.resolve_lookup_value"
    ]
  ],
  "false_positive": [],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 92.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/sql/query.py",
          "Query.resolve_lookup_value"
        ]
      ],
      "seeds": [
        [
          "django/db/models/sql/query.py",
          "Query.resolve_lookup_value"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/query.py",
          "Query.resolve_lookup_value"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/query.py",
          "Query.resolve_lookup_value"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 5,
      "model_request": 5,
      "model_response": 5,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 0,
      "causal": 7
    },
    "predicted_function_count": 1,
    "seconds": 92.34912494104356
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 11289,
    "output": 896
  }
}
```

## 60. django__django-13658

项目：`django/django`；base commit：`0773837e15bb632afffb6848a58c59a791008fa1`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/base.py",
    "django/django/core/management/__init__.py"
  ],
  "found_modules": [
    "django/django/core/management/base.py::CommandParser",
    "django/django/core/management/base.py::BaseCommand",
    "django/django/core/management/base.py::CommandError",
    "django/django/core/management/__init__.py::ManagementUtility"
  ],
  "found_functions": [
    "django/django/core/management/base.py::CommandParser.parse_args",
    "django/django/core/management/base.py::CommandParser.error",
    "django/django/core/management/base.py::BaseCommand.create_parser",
    "django/django/core/management/base.py::CommandParser.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/management/__init__.py",
      "ManagementUtility.execute"
    ]
  ],
  "predictions": [
    [
      "django/core/management/base.py",
      "BaseCommand.create_parser"
    ],
    [
      "django/core/management/base.py",
      "CommandParser.__init__"
    ],
    [
      "django/core/management/base.py",
      "CommandParser.error"
    ],
    [
      "django/core/management/base.py",
      "CommandParser.parse_args"
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
      "django/core/management/base.py",
      "BaseCommand.create_parser"
    ],
    [
      "django/core/management/base.py",
      "CommandParser.__init__"
    ],
    [
      "django/core/management/base.py",
      "CommandParser.error"
    ],
    [
      "django/core/management/base.py",
      "CommandParser.parse_args"
    ]
  ],
  "missed_targets": [
    [
      "django/core/management/__init__.py",
      "ManagementUtility.execute"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 141.0 秒。

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
          "django/core/management/__init__.py",
          "ManagementUtility.execute"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 810,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 18,
      "model_request": 18,
      "model_response": 18,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 7,
      "search_page_summary": 4,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_tool_error": 1,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 37,
      "causal": 20
    },
    "predicted_function_count": 4,
    "seconds": 140.98711240570992
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 46508,
    "output": 6687
  }
}
```

## 61. django__django-13660

项目：`django/django`；base commit：`50c3ac6fa9b7c8a94a6d1dc87edf775e3bc4d575`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 100.00% | 100.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/commands/shell.py"
  ],
  "found_modules": [
    "django/django/core/management/commands/shell.py::Command"
  ],
  "found_functions": [
    "django/django/core/management/commands/shell.py::Command.handle"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/management/commands/shell.py",
      "Command.handle"
    ]
  ],
  "predictions": [
    [
      "django/core/management/commands/shell.py",
      "Command.handle"
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
      "django/core/management/commands/shell.py",
      "Command.handle"
    ]
  ],
  "false_positive": [],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 93.9 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/management/commands/shell.py",
          "Command.handle"
        ]
      ],
      "seeds": [
        [
          "django/core/management/commands/shell.py",
          "Command.handle"
        ]
      ],
      "causal_received": [
        [
          "django/core/management/commands/shell.py",
          "Command.handle"
        ]
      ],
      "final": [
        [
          "django/core/management/commands/shell.py",
          "Command.handle"
        ]
      ]
    },
    "search_unprocessed_matches": 30,
    "event_counts": {
      "run_start": 1,
      "search_round": 3,
      "search_history_compaction": 3,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 2,
      "search_matches": 2,
      "search_result": 5,
      "search_page_summary": 2,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 32,
      "causal": 1
    },
    "predicted_function_count": 1,
    "seconds": 93.86127154994756
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 3,
    "relevance_json": 4,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 32224,
    "output": 2026
  }
}
```

## 62. django__django-13710

项目：`django/django`；base commit：`1bd6a7a0acc11e249fca11c017505ad39f15ebf6`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/admin_inlines/tests.py",
    "django/django/contrib/admin/options.py",
    "django/django/db/models/options.py"
  ],
  "found_modules": [
    "django/tests/admin_inlines/tests.py::TestVerboseNameInlineForms",
    "django/django/contrib/admin/options.py::InlineModelAdmin",
    "django/django/db/models/options.py::Options"
  ],
  "found_functions": [
    "django/tests/admin_inlines/tests.py::TestVerboseNameInlineForms.test_verbose_name_plural_inline",
    "django/django/contrib/admin/options.py::InlineModelAdmin.__init__",
    "django/django/db/models/options.py::Options.contribute_to_class",
    "django/tests/admin_inlines/tests.py::TestVerboseNameInlineForms.test_both_verbose_names_inline"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/options.py",
      "InlineModelAdmin.__init__"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/options.py",
      "InlineModelAdmin.__init__"
    ],
    [
      "django/db/models/options.py",
      "Options.contribute_to_class"
    ],
    [
      "tests/admin_inlines/tests.py",
      "TestVerboseNameInlineForms.test_both_verbose_names_inline"
    ],
    [
      "tests/admin_inlines/tests.py",
      "TestVerboseNameInlineForms.test_verbose_name_plural_inline"
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
      "django/contrib/admin/options.py",
      "InlineModelAdmin.__init__"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/options.py",
      "Options.contribute_to_class"
    ],
    [
      "tests/admin_inlines/tests.py",
      "TestVerboseNameInlineForms.test_both_verbose_names_inline"
    ],
    [
      "tests/admin_inlines/tests.py",
      "TestVerboseNameInlineForms.test_verbose_name_plural_inline"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 167.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/admin/options.py",
          "InlineModelAdmin.__init__"
        ]
      ],
      "seeds": [
        [
          "django/contrib/admin/options.py",
          "InlineModelAdmin.__init__"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/admin/options.py",
          "InlineModelAdmin.__init__"
        ]
      ],
      "final": [
        [
          "django/contrib/admin/options.py",
          "InlineModelAdmin.__init__"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 18,
      "model_request": 18,
      "model_response": 18,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 7,
      "search_page_summary": 4,
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 30,
      "causal": 29
    },
    "predicted_function_count": 4,
    "seconds": 167.15072677191347
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 53406,
    "output": 5471
  }
}
```

## 63. django__django-13757

项目：`django/django`；base commit：`3f140dde51c0fe6c350acb7727bbe489a99f0632`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/json.py",
    "django/django/db/models/expressions.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/json.py::KeyTransformIsNull",
    "django/django/db/models/fields/json.py::HasKey",
    "django/django/db/models/fields/json.py::KeyTransformExact",
    "django/django/db/models/expressions.py::Value",
    "django/django/db/models/expressions.py::Func"
  ],
  "found_functions": [
    "django/django/db/models/fields/json.py::KeyTransformIsNull.as_oracle",
    "django/django/db/models/fields/json.py::KeyTransformIsNull.as_sqlite",
    "django/django/db/models/expressions.py::Value.as_sql",
    "django/django/db/models/expressions.py::Func.as_sql"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/json.py",
      "KeyTransformIsNull.as_oracle"
    ],
    [
      "django/db/models/fields/json.py",
      "KeyTransformIsNull.as_sqlite"
    ]
  ],
  "predictions": [
    [
      "django/db/models/expressions.py",
      "Func.as_sql"
    ],
    [
      "django/db/models/expressions.py",
      "Value.as_sql"
    ],
    [
      "django/db/models/fields/json.py",
      "KeyTransformIsNull.as_oracle"
    ],
    [
      "django/db/models/fields/json.py",
      "KeyTransformIsNull.as_sqlite"
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
      "django/db/models/fields/json.py",
      "KeyTransformIsNull.as_oracle"
    ],
    [
      "django/db/models/fields/json.py",
      "KeyTransformIsNull.as_sqlite"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/expressions.py",
      "Func.as_sql"
    ],
    [
      "django/db/models/expressions.py",
      "Value.as_sql"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 155.1 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/db/models/fields/json.py",
          "KeyTransformIsNull.as_oracle"
        ],
        [
          "django/db/models/fields/json.py",
          "KeyTransformIsNull.as_sqlite"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/json.py",
          "KeyTransformIsNull.as_oracle"
        ],
        [
          "django/db/models/fields/json.py",
          "KeyTransformIsNull.as_sqlite"
        ]
      ]
    },
    "search_unprocessed_matches": 61,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 7,
      "relevance_attempt": 7,
      "relevance_decisions": 7,
      "search_action_error": 1,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 37,
      "causal": 56
    },
    "predicted_function_count": 4,
    "seconds": 155.0568081215024
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 7,
    "search_action_repair": 1,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 49050,
    "output": 5026
  }
}
```

## 64. django__django-13768

项目：`django/django`；base commit：`965d2d95c630939b53eb60d9c169f5dfc77ee0c6`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/dispatch/tests.py",
    "django/django/dispatch/dispatcher.py"
  ],
  "found_modules": [
    "django/tests/dispatch/tests.py::DispatcherTests",
    "django/django/dispatch/dispatcher.py::Signal"
  ],
  "found_functions": [
    "django/tests/dispatch/tests.py::DispatcherTests.test_send_robust_fail",
    "django/django/dispatch/dispatcher.py::Signal.send_robust",
    "django/tests/dispatch/tests.py::DispatcherTests.assertTestIsClean"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/dispatch/dispatcher.py",
      "Signal.send_robust"
    ]
  ],
  "predictions": [
    [
      "django/dispatch/dispatcher.py",
      "Signal.send_robust"
    ],
    [
      "tests/dispatch/tests.py",
      "DispatcherTests.assertTestIsClean"
    ],
    [
      "tests/dispatch/tests.py",
      "DispatcherTests.test_send_robust_fail"
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
      "django/dispatch/dispatcher.py",
      "Signal.send_robust"
    ]
  ],
  "false_positive": [
    [
      "tests/dispatch/tests.py",
      "DispatcherTests.assertTestIsClean"
    ],
    [
      "tests/dispatch/tests.py",
      "DispatcherTests.test_send_robust_fail"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 133.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/dispatch/dispatcher.py",
          "Signal.send_robust"
        ]
      ],
      "seeds": [
        [
          "django/dispatch/dispatcher.py",
          "Signal.send_robust"
        ]
      ],
      "causal_received": [
        [
          "django/dispatch/dispatcher.py",
          "Signal.send_robust"
        ]
      ],
      "final": [
        [
          "django/dispatch/dispatcher.py",
          "Signal.send_robust"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 3,
      "search_page_summary": 3,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 6,
      "causal": 25
    },
    "predicted_function_count": 3,
    "seconds": 133.48511277418584
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "relevance_json": 1,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 24946,
    "output": 6354
  }
}
```

## 65. django__django-13925

项目：`django/django`；base commit：`0c42cdf0d2422f4c080e93594d5d15381d6e955e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/base.py",
    "django/django/apps/config.py"
  ],
  "found_modules": [
    "django/django/db/models/base.py::Model",
    "django/django/apps/config.py::AppConfig"
  ],
  "found_functions": [
    "django/django/db/models/base.py::Model._check_default_pk",
    "django/django/apps/config.py::AppConfig._is_default_auto_field_overridden"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/base.py",
      "Model._check_default_pk"
    ]
  ],
  "predictions": [
    [
      "django/apps/config.py",
      "AppConfig._is_default_auto_field_overridden"
    ],
    [
      "django/db/models/base.py",
      "Model._check_default_pk"
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
      "django/db/models/base.py",
      "Model._check_default_pk"
    ]
  ],
  "false_positive": [
    [
      "django/apps/config.py",
      "AppConfig._is_default_auto_field_overridden"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 129.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/base.py",
          "Model._check_default_pk"
        ]
      ],
      "seeds": [
        [
          "django/db/models/base.py",
          "Model._check_default_pk"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/base.py",
          "Model._check_default_pk"
        ]
      ],
      "final": [
        [
          "django/db/models/base.py",
          "Model._check_default_pk"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 4
    },
    "predicted_function_count": 2,
    "seconds": 129.66163655556738
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 24550,
    "output": 1976
  }
}
```

## 66. django__django-13933

项目：`django/django`；base commit：`42e8cf47c7ee2db238bf91197ea398126c546741`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/models.py",
    "django/tests/model_forms/test_uuid.py",
    "django/tests/forms_tests/tests/test_error_messages.py"
  ],
  "found_modules": [
    "django/django/forms/models.py::ModelMultipleChoiceField",
    "django/tests/model_forms/test_uuid.py::ModelFormBaseTest",
    "django/tests/forms_tests/tests/test_error_messages.py::ModelChoiceFieldErrorMessagesTestCase",
    "django/django/forms/models.py::ModelChoiceField"
  ],
  "found_functions": [
    "django/django/forms/models.py::ModelMultipleChoiceField.to_python",
    "django/django/forms/models.py::ModelMultipleChoiceField._check_values",
    "django/tests/forms_tests/tests/test_error_messages.py::ModelChoiceFieldErrorMessagesTestCase.test_modelchoicefield",
    "django/django/forms/models.py::ModelChoiceField.to_python"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/models.py",
      "ModelChoiceField.to_python"
    ]
  ],
  "predictions": [
    [
      "django/forms/models.py",
      "ModelChoiceField.to_python"
    ],
    [
      "django/forms/models.py",
      "ModelMultipleChoiceField._check_values"
    ],
    [
      "django/forms/models.py",
      "ModelMultipleChoiceField.to_python"
    ],
    [
      "tests/forms_tests/tests/test_error_messages.py",
      "ModelChoiceFieldErrorMessagesTestCase.test_modelchoicefield"
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
      "django/forms/models.py",
      "ModelChoiceField.to_python"
    ]
  ],
  "false_positive": [
    [
      "django/forms/models.py",
      "ModelMultipleChoiceField._check_values"
    ],
    [
      "django/forms/models.py",
      "ModelMultipleChoiceField.to_python"
    ],
    [
      "tests/forms_tests/tests/test_error_messages.py",
      "ModelChoiceFieldErrorMessagesTestCase.test_modelchoicefield"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 143.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/forms/models.py",
          "ModelChoiceField.to_python"
        ]
      ],
      "seeds": [
        [
          "django/forms/models.py",
          "ModelChoiceField.to_python"
        ]
      ],
      "causal_received": [
        [
          "django/forms/models.py",
          "ModelChoiceField.to_python"
        ]
      ],
      "final": [
        [
          "django/forms/models.py",
          "ModelChoiceField.to_python"
        ]
      ]
    },
    "search_unprocessed_matches": 24,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 20,
      "model_request": 20,
      "model_response": 20,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 9,
      "search_page_summary": 5,
      "source_receipt": 7,
      "relevance_attempt": 7,
      "relevance_decisions": 7,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 50,
      "causal": 27
    },
    "predicted_function_count": 4,
    "seconds": 143.34809773694724
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 7,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 46395,
    "output": 4703
  }
}
```

## 67. django__django-13964

项目：`django/django`；base commit：`f39634ff229887bf7790c069d0c411b38494ca38`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/related_descriptors.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/related_descriptors.py::ForwardManyToOneDescriptor"
  ],
  "found_functions": [
    "django/django/db/models/fields/related_descriptors.py::ForwardManyToOneDescriptor.__set__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/base.py",
      "Model._prepare_related_fields_for_save"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/related_descriptors.py",
      "ForwardManyToOneDescriptor.__set__"
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
      "django/db/models/fields/related_descriptors.py",
      "ForwardManyToOneDescriptor.__set__"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/base.py",
      "Model._prepare_related_fields_for_save"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 114.4 秒。

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
      "search_result": 6,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 16,
      "causal": 10
    },
    "predicted_function_count": 1,
    "seconds": 114.35501453187317
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 31223,
    "output": 4314
  }
}
```

## 68. django__django-14016

项目：`django/django`；base commit：`1710cdbe79c90665046034fe1700933d038d90ad`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/query_utils.py"
  ],
  "found_modules": [
    "django/django/db/models/query_utils.py::Q"
  ],
  "found_functions": [
    "django/django/db/models/query_utils.py::Q._combine",
    "django/django/db/models/query_utils.py::Q.__or__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/query_utils.py",
      "Q._combine"
    ]
  ],
  "predictions": [
    [
      "django/db/models/query_utils.py",
      "Q.__or__"
    ],
    [
      "django/db/models/query_utils.py",
      "Q._combine"
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
      "django/db/models/query_utils.py",
      "Q._combine"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/query_utils.py",
      "Q.__or__"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 151.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ],
      "seeds": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ],
      "final": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ]
    },
    "search_unprocessed_matches": 2370,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 19,
      "model_request": 19,
      "model_response": 19,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "search_page_summary": 5,
      "source_receipt": 9,
      "relevance_attempt": 9,
      "relevance_decisions": 9,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 70,
      "causal": 32
    },
    "predicted_function_count": 2,
    "seconds": 151.46300073340535
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 9,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 58360,
    "output": 4351
  }
}
```

## 69. django__django-14017

项目：`django/django`；base commit：`466920f6d726eee90d5566e0a9948e92b33a122e`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/expressions.py",
    "django/django/db/models/query_utils.py"
  ],
  "found_modules": [
    "django/django/db/models/expressions.py::Combinable",
    "django/django/db/models/query_utils.py::Q"
  ],
  "found_functions": [
    "django/django/db/models/expressions.py::Combinable.__rand__",
    "django/django/db/models/query_utils.py::Q._combine",
    "django/django/db/models/query_utils.py::Q.__and__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/query_utils.py",
      "Q._combine"
    ]
  ],
  "predictions": [
    [
      "django/db/models/expressions.py",
      "Combinable.__rand__"
    ],
    [
      "django/db/models/query_utils.py",
      "Q.__and__"
    ],
    [
      "django/db/models/query_utils.py",
      "Q._combine"
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
      "django/db/models/query_utils.py",
      "Q._combine"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/expressions.py",
      "Combinable.__rand__"
    ],
    [
      "django/db/models/query_utils.py",
      "Q.__and__"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 128.9 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ],
      "seeds": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ],
      "final": [
        [
          "django/db/models/query_utils.py",
          "Q._combine"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 8,
      "relevance": 6,
      "causal": 34
    },
    "predicted_function_count": 3,
    "seconds": 128.90091820713133
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 35949,
    "output": 2594
  }
}
```

## 70. django__django-14155

项目：`django/django`；base commit：`2f13c476abe4ba787b6cb71131818341911f43cc`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/urls/resolvers.py"
  ],
  "found_modules": [
    "django/django/urls/resolvers.py::ResolverMatch"
  ],
  "found_functions": [
    "django/django/urls/resolvers.py::ResolverMatch.__init__",
    "django/django/urls/resolvers.py::ResolverMatch.__repr__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/urls/resolvers.py",
      "ResolverMatch.__repr__"
    ]
  ],
  "predictions": [
    [
      "django/urls/resolvers.py",
      "ResolverMatch.__init__"
    ],
    [
      "django/urls/resolvers.py",
      "ResolverMatch.__repr__"
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
      "django/urls/resolvers.py",
      "ResolverMatch.__repr__"
    ]
  ],
  "false_positive": [
    [
      "django/urls/resolvers.py",
      "ResolverMatch.__init__"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 126.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/urls/resolvers.py",
          "ResolverMatch.__repr__"
        ]
      ],
      "final": [
        [
          "django/urls/resolvers.py",
          "ResolverMatch.__repr__"
        ]
      ]
    },
    "search_unprocessed_matches": 887,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 26,
      "model_request": 26,
      "model_response": 26,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "source_receipt": 10,
      "relevance_attempt": 10,
      "relevance_decisions": 10,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 11,
      "causal_parse": 11,
      "run_end": 1
    },
    "duplicate_code_associations": 4,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 69,
      "causal": 5
    },
    "predicted_function_count": 2,
    "seconds": 126.04429820459336
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 10,
    "generate_causal_graph": 11
  },
  "tokens": {
    "input": 47914,
    "output": 6774
  }
}
```

## 71. django__django-14238

项目：`django/django`；base commit：`30e123ed351317b7527f632b3b7dc4e81e850449`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/__init__.py",
    "django/django/db/models/options.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/__init__.py::AutoFieldMeta",
    "django/django/db/models/options.py::Options"
  ],
  "found_functions": [
    "django/django/db/models/fields/__init__.py::AutoFieldMeta.__subclasscheck__",
    "django/django/db/models/options.py::Options._get_default_pk_class",
    "django/django/db/models/fields/__init__.py::AutoFieldMeta.__instancecheck__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "AutoFieldMeta.__subclasscheck__"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/__init__.py",
      "AutoFieldMeta.__instancecheck__"
    ],
    [
      "django/db/models/fields/__init__.py",
      "AutoFieldMeta.__subclasscheck__"
    ],
    [
      "django/db/models/options.py",
      "Options._get_default_pk_class"
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
      "django/db/models/fields/__init__.py",
      "AutoFieldMeta.__subclasscheck__"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/fields/__init__.py",
      "AutoFieldMeta.__instancecheck__"
    ],
    [
      "django/db/models/options.py",
      "Options._get_default_pk_class"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 127.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/fields/__init__.py",
          "AutoFieldMeta.__subclasscheck__"
        ]
      ],
      "seeds": [
        [
          "django/db/models/fields/__init__.py",
          "AutoFieldMeta.__subclasscheck__"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/__init__.py",
          "AutoFieldMeta.__subclasscheck__"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/__init__.py",
          "AutoFieldMeta.__subclasscheck__"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 0,
      "causal": 5
    },
    "predicted_function_count": 3,
    "seconds": 127.48578550480306
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 22042,
    "output": 2980
  }
}
```

## 72. django__django-14382

项目：`django/django`；base commit：`29345aecf6e8d53ccb3577a3762bb0c263f7558d`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/templates.py",
    "django/django/core/management/commands/startapp.py"
  ],
  "found_modules": [
    "django/django/core/management/templates.py::TemplateCommand",
    "django/django/core/management/commands/startapp.py::Command"
  ],
  "found_functions": [
    "django/django/core/management/templates.py::TemplateCommand.validate_name",
    "django/django/core/management/commands/startapp.py::Command.handle"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/management/templates.py",
      "TemplateCommand.handle"
    ]
  ],
  "predictions": [
    [
      "django/core/management/commands/startapp.py",
      "Command.handle"
    ],
    [
      "django/core/management/templates.py",
      "TemplateCommand.validate_name"
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
      "django/core/management/commands/startapp.py",
      "Command.handle"
    ],
    [
      "django/core/management/templates.py",
      "TemplateCommand.validate_name"
    ]
  ],
  "missed_targets": [
    [
      "django/core/management/templates.py",
      "TemplateCommand.handle"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 149.0 秒。

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
          "django/core/management/templates.py",
          "TemplateCommand.handle"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 60,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "search_page_summary": 5,
      "source_receipt": 8,
      "relevance_attempt": 8,
      "relevance_decisions": 8,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 32,
      "causal": 12
    },
    "predicted_function_count": 2,
    "seconds": 149.02658751793206
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 8,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 61968,
    "output": 4205
  }
}
```

## 73. django__django-14411

项目：`django/django`；base commit：`fa4e963ee7e6876581b5432363603571839ba00c`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/auth/forms.py",
    "django/django/contrib/admin/helpers.py",
    "django/django/contrib/auth/hashers.py"
  ],
  "found_modules": [
    "django/django/contrib/auth/forms.py::ReadOnlyPasswordHashWidget",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField",
    "django/django/contrib/auth/forms.py::ReadOnlyPasswordHashField"
  ],
  "found_functions": [
    "django/django/contrib/auth/forms.py::ReadOnlyPasswordHashWidget.get_context",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField.contents",
    "django/django/contrib/auth/hashers.py::identify_hasher",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField.label_tag",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/auth/forms.py",
      "ReadOnlyPasswordHashWidget.id_for_label"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.__init__"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.contents"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.label_tag"
    ],
    [
      "django/contrib/auth/forms.py",
      "ReadOnlyPasswordHashWidget.get_context"
    ],
    [
      "django/contrib/auth/hashers.py",
      "identify_hasher"
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
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.__init__"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.contents"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.label_tag"
    ],
    [
      "django/contrib/auth/forms.py",
      "ReadOnlyPasswordHashWidget.get_context"
    ],
    [
      "django/contrib/auth/hashers.py",
      "identify_hasher"
    ]
  ],
  "missed_targets": [
    [
      "django/contrib/auth/forms.py",
      "ReadOnlyPasswordHashWidget.id_for_label"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 187.4 秒。

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
      "request_preflight": 17,
      "model_request": 17,
      "model_response": 17,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 10,
      "causal_parse": 10,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 10,
      "causal": 37
    },
    "predicted_function_count": 5,
    "seconds": 187.42903675232083
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 10
  },
  "tokens": {
    "input": 40584,
    "output": 6758
  }
}
```

## 74. django__django-14534

项目：`django/django`；base commit：`910ecd1b8df7678f45c3d507dde6bcb1faafa243`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 9.09% | 100.00% | 16.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/boundfield.py",
    "django/django/forms/widgets.py"
  ],
  "found_modules": [
    "django/django/forms/boundfield.py::BoundWidget",
    "django/django/forms/widgets.py::ChoiceWidget",
    "django/django/forms/boundfield.py::BoundField",
    "django/django/forms/widgets.py::RadioSelect",
    "django/django/forms/widgets.py::Widget"
  ],
  "found_functions": [
    "django/django/forms/boundfield.py::BoundWidget.__init__",
    "django/django/forms/boundfield.py::BoundWidget.id_for_label",
    "django/django/forms/widgets.py::ChoiceWidget.id_for_label",
    "django/django/forms/boundfield.py::BoundField.subwidgets",
    "django/django/forms/boundfield.py::BoundField.value",
    "django/django/forms/widgets.py::ChoiceWidget.create_option",
    "django/django/forms/widgets.py::RadioSelect.id_for_label",
    "django/django/forms/widgets.py::Widget.build_attrs",
    "django/django/forms/widgets.py::ChoiceWidget.optgroups",
    "django/django/forms/boundfield.py::BoundField.auto_id",
    "django/django/forms/boundfield.py::BoundField.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/boundfield.py",
      "BoundWidget.id_for_label"
    ]
  ],
  "predictions": [
    [
      "django/forms/boundfield.py",
      "BoundField.__init__"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.auto_id"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.subwidgets"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.value"
    ],
    [
      "django/forms/boundfield.py",
      "BoundWidget.__init__"
    ],
    [
      "django/forms/boundfield.py",
      "BoundWidget.id_for_label"
    ],
    [
      "django/forms/widgets.py",
      "ChoiceWidget.create_option"
    ],
    [
      "django/forms/widgets.py",
      "ChoiceWidget.id_for_label"
    ],
    [
      "django/forms/widgets.py",
      "ChoiceWidget.optgroups"
    ],
    [
      "django/forms/widgets.py",
      "RadioSelect.id_for_label"
    ],
    [
      "django/forms/widgets.py",
      "Widget.build_attrs"
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
      "django/forms/boundfield.py",
      "BoundWidget.id_for_label"
    ]
  ],
  "false_positive": [
    [
      "django/forms/boundfield.py",
      "BoundField.__init__"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.auto_id"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.subwidgets"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.value"
    ],
    [
      "django/forms/boundfield.py",
      "BoundWidget.__init__"
    ],
    [
      "django/forms/widgets.py",
      "ChoiceWidget.create_option"
    ],
    [
      "django/forms/widgets.py",
      "ChoiceWidget.id_for_label"
    ],
    [
      "django/forms/widgets.py",
      "ChoiceWidget.optgroups"
    ],
    [
      "django/forms/widgets.py",
      "RadioSelect.id_for_label"
    ],
    [
      "django/forms/widgets.py",
      "Widget.build_attrs"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 166.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/forms/boundfield.py",
          "BoundWidget.id_for_label"
        ]
      ],
      "seeds": [
        [
          "django/forms/boundfield.py",
          "BoundWidget.id_for_label"
        ]
      ],
      "causal_received": [
        [
          "django/forms/boundfield.py",
          "BoundWidget.id_for_label"
        ]
      ],
      "final": [
        [
          "django/forms/boundfield.py",
          "BoundWidget.id_for_label"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 3,
      "search_history_compaction": 3,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 2,
      "search_matches": 2,
      "search_result": 3,
      "search_page_summary": 2,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 16,
      "causal_parse": 16,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 12,
      "causal": 27
    },
    "predicted_function_count": 11,
    "seconds": 166.75934310536832
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 3,
    "relevance_json": 2,
    "generate_causal_graph": 16
  },
  "tokens": {
    "input": 48846,
    "output": 14003
  }
}
```

## 75. django__django-14580

项目：`django/django`；base commit：`36fa071d6ebd18a61c4d7f1b5c9d17106134bd44`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/serializer.py",
    "django/django/db/migrations/writer.py"
  ],
  "found_modules": [
    "django/django/db/migrations/serializer.py::TypeSerializer",
    "django/django/db/migrations/writer.py::OperationWriter"
  ],
  "found_functions": [
    "django/django/db/migrations/serializer.py::TypeSerializer.serialize",
    "django/django/db/migrations/writer.py::OperationWriter.serialize"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/serializer.py",
      "TypeSerializer.serialize"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/serializer.py",
      "TypeSerializer.serialize"
    ],
    [
      "django/db/migrations/writer.py",
      "OperationWriter.serialize"
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
      "django/db/migrations/serializer.py",
      "TypeSerializer.serialize"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/writer.py",
      "OperationWriter.serialize"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 118.9 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/serializer.py",
          "TypeSerializer.serialize"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/serializer.py",
          "TypeSerializer.serialize"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/serializer.py",
          "TypeSerializer.serialize"
        ]
      ],
      "final": [
        [
          "django/db/migrations/serializer.py",
          "TypeSerializer.serialize"
        ]
      ]
    },
    "search_unprocessed_matches": 2,
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
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 7,
      "relevance": 32,
      "causal": 23
    },
    "predicted_function_count": 2,
    "seconds": 118.91554988734424
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 35621,
    "output": 2789
  }
}
```

## 76. django__django-14608

项目：`django/django`；base commit：`7f33c1e22dbc34a7afae7967783725b10f1f13b1`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/formsets.py",
    "django/django/forms/utils.py"
  ],
  "found_modules": [
    "django/django/forms/formsets.py::BaseFormSet",
    "django/django/forms/utils.py::ErrorList"
  ],
  "found_functions": [
    "django/django/forms/formsets.py::BaseFormSet.non_form_errors",
    "django/django/forms/formsets.py::BaseFormSet.full_clean"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.full_clean"
    ]
  ],
  "predictions": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.full_clean"
    ],
    [
      "django/forms/formsets.py",
      "BaseFormSet.non_form_errors"
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
      "django/forms/formsets.py",
      "BaseFormSet.full_clean"
    ]
  ],
  "false_positive": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.non_form_errors"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 370.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.full_clean"
        ]
      ],
      "seeds": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.full_clean"
        ]
      ],
      "causal_received": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.full_clean"
        ]
      ],
      "final": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.full_clean"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 7,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 22,
      "causal": 54
    },
    "predicted_function_count": 2,
    "seconds": 370.035926066339
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 47579,
    "output": 2400
  }
}
```

## 77. django__django-14667

项目：`django/django`；base commit：`6a970a8b4600eb91be25f38caed0a52269d6303d`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 100.00% | 28.57% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/query.py",
    "django/django/db/models/query.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/query.py::Query",
    "django/django/db/models/query.py::QuerySet"
  ],
  "found_functions": [
    "django/django/db/models/sql/query.py::Query.clear_deferred_loading",
    "django/django/db/models/query.py::QuerySet.defer",
    "django/django/db/models/query.py::QuerySet._chain",
    "django/django/db/models/sql/query.py::Query.add_deferred_loading",
    "django/django/db/models/sql/query.py::Query.add_immediate_loading",
    "django/django/db/models/query.py::QuerySet.only"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query.add_deferred_loading"
    ]
  ],
  "predictions": [
    [
      "django/db/models/query.py",
      "QuerySet._chain"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.defer"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.only"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_deferred_loading"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_immediate_loading"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.clear_deferred_loading"
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
      "django/db/models/sql/query.py",
      "Query.add_deferred_loading"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/query.py",
      "QuerySet._chain"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.defer"
    ],
    [
      "django/db/models/query.py",
      "QuerySet.only"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_immediate_loading"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.clear_deferred_loading"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 177.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/sql/query.py",
          "Query.add_deferred_loading"
        ]
      ],
      "seeds": [
        [
          "django/db/models/sql/query.py",
          "Query.add_deferred_loading"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/query.py",
          "Query.add_deferred_loading"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/query.py",
          "Query.add_deferred_loading"
        ]
      ]
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
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "output_truncated": 2,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 93
    },
    "predicted_function_count": 6,
    "seconds": 177.25785664841533
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 58445,
    "output": 12850
  }
}
```

## 78. django__django-14672

项目：`django/django`；base commit：`00ea883ef56fb5e092cbe4a6f7ff2e7470886ac4`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 6.25% | 100.00% | 11.76% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/base.py",
    "django/django/utils/hashable.py",
    "django/tests/utils_tests/test_hashable.py",
    "django/django/utils/itercompat.py",
    "django/django/utils/tree.py",
    "django/django/core/exceptions.py",
    "django/django/db/models/lookups.py",
    "django/django/db/models/fields/reverse_related.py",
    "django/django/db/models/expressions.py",
    "django/django/db/models/sql/compiler.py"
  ],
  "found_modules": [
    "django/django/db/models/base.py::Model",
    "django/tests/utils_tests/test_hashable.py::TestHashable",
    "django/django/utils/tree.py::Node",
    "django/django/core/exceptions.py::ValidationError",
    "django/django/db/models/lookups.py::Lookup",
    "django/django/db/models/fields/reverse_related.py::ManyToManyRel",
    "django/django/db/models/fields/reverse_related.py::ForeignObjectRel",
    "django/django/db/models/expressions.py::Expression",
    "django/django/db/models/sql/compiler.py::SQLCompiler"
  ],
  "found_functions": [
    "django/django/db/models/base.py::Model._get_FIELD_display",
    "django/django/utils/hashable.py::make_hashable",
    "django/tests/utils_tests/test_hashable.py::TestHashable.test_unhashable",
    "django/django/utils/itercompat.py::is_iterable",
    "django/django/utils/tree.py::Node.__hash__",
    "django/django/core/exceptions.py::ValidationError.__hash__",
    "django/django/db/models/lookups.py::Lookup.__hash__",
    "django/django/db/models/fields/reverse_related.py::ManyToManyRel.__init__",
    "django/django/db/models/fields/reverse_related.py::ManyToManyRel.get_related_field",
    "django/django/db/models/fields/reverse_related.py::ManyToManyRel.identity",
    "django/django/db/models/fields/reverse_related.py::ForeignObjectRel.identity",
    "django/tests/utils_tests/test_hashable.py::TestHashable.test_equal",
    "django/django/db/models/expressions.py::Expression.identity",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_group_by",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_order_by",
    "django/tests/utils_tests/test_hashable.py::TestHashable.test_count_equal"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.identity"
    ]
  ],
  "predictions": [
    [
      "django/core/exceptions.py",
      "ValidationError.__hash__"
    ],
    [
      "django/db/models/base.py",
      "Model._get_FIELD_display"
    ],
    [
      "django/db/models/expressions.py",
      "Expression.identity"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ForeignObjectRel.identity"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.__init__"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.get_related_field"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.identity"
    ],
    [
      "django/db/models/lookups.py",
      "Lookup.__hash__"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/utils/hashable.py",
      "make_hashable"
    ],
    [
      "django/utils/itercompat.py",
      "is_iterable"
    ],
    [
      "django/utils/tree.py",
      "Node.__hash__"
    ],
    [
      "tests/utils_tests/test_hashable.py",
      "TestHashable.test_count_equal"
    ],
    [
      "tests/utils_tests/test_hashable.py",
      "TestHashable.test_equal"
    ],
    [
      "tests/utils_tests/test_hashable.py",
      "TestHashable.test_unhashable"
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
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.identity"
    ]
  ],
  "false_positive": [
    [
      "django/core/exceptions.py",
      "ValidationError.__hash__"
    ],
    [
      "django/db/models/base.py",
      "Model._get_FIELD_display"
    ],
    [
      "django/db/models/expressions.py",
      "Expression.identity"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ForeignObjectRel.identity"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.__init__"
    ],
    [
      "django/db/models/fields/reverse_related.py",
      "ManyToManyRel.get_related_field"
    ],
    [
      "django/db/models/lookups.py",
      "Lookup.__hash__"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_group_by"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_order_by"
    ],
    [
      "django/utils/hashable.py",
      "make_hashable"
    ],
    [
      "django/utils/itercompat.py",
      "is_iterable"
    ],
    [
      "django/utils/tree.py",
      "Node.__hash__"
    ],
    [
      "tests/utils_tests/test_hashable.py",
      "TestHashable.test_count_equal"
    ],
    [
      "tests/utils_tests/test_hashable.py",
      "TestHashable.test_equal"
    ],
    [
      "tests/utils_tests/test_hashable.py",
      "TestHashable.test_unhashable"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 324.9 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/models/fields/reverse_related.py",
          "ManyToManyRel.identity"
        ]
      ],
      "seeds": [
        [
          "django/db/models/fields/reverse_related.py",
          "ManyToManyRel.identity"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/fields/reverse_related.py",
          "ManyToManyRel.identity"
        ]
      ],
      "final": [
        [
          "django/db/models/fields/reverse_related.py",
          "ManyToManyRel.identity"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 30,
      "model_request": 30,
      "model_response": 30,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 22,
      "causal_parse": 22,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 7,
      "causal": 77
    },
    "predicted_function_count": 16,
    "seconds": 324.9485391192138
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [
    [
      "django/utils/itercompat.py",
      "is_iterable"
    ]
  ],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 22
  },
  "tokens": {
    "input": 177580,
    "output": 16809
  }
}
```

## 79. django__django-14730

项目：`django/django`；base commit：`4fe3774c729f3fd5105b3001fe69a70bdca95ac3`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/fields/related.py"
  ],
  "found_modules": [
    "django/django/db/models/fields/related.py::ManyToManyField"
  ],
  "found_functions": [
    "django/django/db/models/fields/related.py::ManyToManyField.__init__",
    "django/django/db/models/fields/related.py::ManyToManyField.contribute_to_class"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/related.py",
      "ManyToManyField._check_ignored_options"
    ]
  ],
  "predictions": [
    [
      "django/db/models/fields/related.py",
      "ManyToManyField.__init__"
    ],
    [
      "django/db/models/fields/related.py",
      "ManyToManyField.contribute_to_class"
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
      "django/db/models/fields/related.py",
      "ManyToManyField.__init__"
    ],
    [
      "django/db/models/fields/related.py",
      "ManyToManyField.contribute_to_class"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/fields/related.py",
      "ManyToManyField._check_ignored_options"
    ]
  ]
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 110.5 秒。

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
          "django/db/models/fields/related.py",
          "ManyToManyField._check_ignored_options"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 825,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 13,
      "model_request": 13,
      "model_response": 13,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 6,
      "search_page_summary": 3,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 32,
      "causal": 38
    },
    "predicted_function_count": 2,
    "seconds": 110.50340203102678
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "relevance_json": 4,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 69770,
    "output": 2898
  }
}
```

## 80. django__django-14752

项目：`django/django`；base commit：`b64db05b9cedd96905d637a2d824cbbf428e40e7`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 50.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 50.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/admin/views/autocomplete.py"
  ],
  "found_modules": [
    "django/django/contrib/admin/views/autocomplete.py::AutocompleteJsonView"
  ],
  "found_functions": [
    "django/django/contrib/admin/views/autocomplete.py::AutocompleteJsonView.get"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/views/autocomplete.py",
      "AutocompleteJsonView.get"
    ],
    [
      "django/contrib/admin/views/autocomplete.py",
      "AutocompleteJsonView.serialize_result"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/views/autocomplete.py",
      "AutocompleteJsonView.get"
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
      "django/contrib/admin/views/autocomplete.py",
      "AutocompleteJsonView.get"
    ]
  ],
  "false_positive": [],
  "missed_targets": [
    [
      "django/contrib/admin/views/autocomplete.py",
      "AutocompleteJsonView.serialize_result"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 103.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖部分目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/admin/views/autocomplete.py",
          "AutocompleteJsonView.get"
        ]
      ],
      "seeds": [
        [
          "django/contrib/admin/views/autocomplete.py",
          "AutocompleteJsonView.get"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/admin/views/autocomplete.py",
          "AutocompleteJsonView.get"
        ]
      ],
      "final": [
        [
          "django/contrib/admin/views/autocomplete.py",
          "AutocompleteJsonView.get"
        ]
      ]
    },
    "search_unprocessed_matches": 9,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 15,
      "model_request": 15,
      "model_response": 15,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 37,
      "causal": 6
    },
    "predicted_function_count": 1,
    "seconds": 103.4628222770989
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 32202,
    "output": 2768
  }
}
```

## 81. django__django-14787

项目：`django/django`；base commit：`004b4620f6f4ad87261e149898940f2dcd5757ef`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/decorators.py"
  ],
  "found_modules": [],
  "found_functions": [
    "django/django/utils/decorators.py::_update_method_wrapper",
    "django/django/utils/decorators.py::_multi_decorate",
    "django/django/utils/decorators.py::method_decorator"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/decorators.py",
      "_multi_decorate._wrapper"
    ]
  ],
  "predictions": [
    [
      "django/utils/decorators.py",
      "_multi_decorate"
    ],
    [
      "django/utils/decorators.py",
      "_update_method_wrapper"
    ],
    [
      "django/utils/decorators.py",
      "method_decorator"
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
      "django/utils/decorators.py",
      "_multi_decorate"
    ],
    [
      "django/utils/decorators.py",
      "_update_method_wrapper"
    ],
    [
      "django/utils/decorators.py",
      "method_decorator"
    ]
  ],
  "missed_targets": [
    [
      "django/utils/decorators.py",
      "_multi_decorate._wrapper"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 162.3 秒。

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
      "request_preflight": 11,
      "model_request": 11,
      "model_response": 11,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 6,
      "search_page_summary": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 16,
      "causal": 13
    },
    "predicted_function_count": 3,
    "seconds": 162.26762718334794
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 24529,
    "output": 5598
  }
}
```

## 82. django__django-14855

项目：`django/django`；base commit：`475cffd1d64c690cdad16ede4d5e81985738ceb4`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 100.00% | 28.57% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/admin/utils.py",
    "django/django/core/exceptions.py",
    "django/django/contrib/admin/helpers.py"
  ],
  "found_modules": [
    "django/django/contrib/admin/utils.py::FieldIsAForeignKeyColumnName",
    "django/django/core/exceptions.py::FieldDoesNotExist",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField",
    "django/django/contrib/admin/helpers.py::Fieldline"
  ],
  "found_functions": [
    "django/django/contrib/admin/utils.py::_get_non_gfk_field",
    "django/django/contrib/admin/utils.py::lookup_field",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField.get_admin_url",
    "django/django/contrib/admin/helpers.py::Fieldline.__iter__",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField.__init__",
    "django/django/contrib/admin/helpers.py::AdminReadonlyField.contents"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.get_admin_url"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.__init__"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.contents"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.get_admin_url"
    ],
    [
      "django/contrib/admin/helpers.py",
      "Fieldline.__iter__"
    ],
    [
      "django/contrib/admin/utils.py",
      "_get_non_gfk_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_field"
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
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.get_admin_url"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.__init__"
    ],
    [
      "django/contrib/admin/helpers.py",
      "AdminReadonlyField.contents"
    ],
    [
      "django/contrib/admin/helpers.py",
      "Fieldline.__iter__"
    ],
    [
      "django/contrib/admin/utils.py",
      "_get_non_gfk_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_field"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 171.4 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/admin/helpers.py",
          "AdminReadonlyField.get_admin_url"
        ]
      ],
      "seeds": [
        [
          "django/contrib/admin/helpers.py",
          "AdminReadonlyField.get_admin_url"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/admin/helpers.py",
          "AdminReadonlyField.get_admin_url"
        ]
      ],
      "final": [
        [
          "django/contrib/admin/helpers.py",
          "AdminReadonlyField.get_admin_url"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 4,
      "search_history_compaction": 4,
      "request_preflight": 14,
      "model_request": 14,
      "model_response": 14,
      "search_query": 3,
      "search_matches": 3,
      "search_result": 3,
      "search_page_summary": 3,
      "seed_locations": 1,
      "causal_context": 10,
      "causal_parse": 10,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 0,
      "causal": 23
    },
    "predicted_function_count": 6,
    "seconds": 171.4303102325648
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 4,
    "generate_causal_graph": 10
  },
  "tokens": {
    "input": 37994,
    "output": 6053
  }
}
```

## 83. django__django-14915

项目：`django/django`；base commit：`903aaa35e5ceaa33bfc9b19b7f6da65ce5a91dd4`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/models.py"
  ],
  "found_modules": [
    "django/django/forms/models.py::ModelChoiceIteratorValue",
    "django/django/forms/models.py::ModelChoiceIterator"
  ],
  "found_functions": [
    "django/django/forms/models.py::ModelChoiceIteratorValue.__str__",
    "django/django/forms/models.py::ModelChoiceIteratorValue.__eq__",
    "django/django/forms/models.py::ModelChoiceIterator.choice",
    "django/django/forms/models.py::ModelChoiceIteratorValue.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__hash__"
    ]
  ],
  "predictions": [
    [
      "django/forms/models.py",
      "ModelChoiceIterator.choice"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__eq__"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__init__"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__str__"
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
      "django/forms/models.py",
      "ModelChoiceIterator.choice"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__eq__"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__init__"
    ],
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__str__"
    ]
  ],
  "missed_targets": [
    [
      "django/forms/models.py",
      "ModelChoiceIteratorValue.__hash__"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 132.4 秒。

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
      "request_preflight": 18,
      "model_request": 18,
      "model_response": 18,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 7,
      "search_page_summary": 5,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 30,
      "causal": 7
    },
    "predicted_function_count": 4,
    "seconds": 132.36877130996436
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 30023,
    "output": 8344
  }
}
```

## 84. django__django-14997

项目：`django/django`；base commit：`0d4e575c96d408e0efb4dfd0cbfc864219776950`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 3.33% | 100.00% | 6.45% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/backends/ddl_references.py",
    "django/django/db/backends/base/schema.py",
    "django/django/db/backends/sqlite3/schema.py",
    "django/tests/backends/test_ddl_references.py",
    "django/django/db/models/constraints.py"
  ],
  "found_modules": [
    "django/django/db/backends/ddl_references.py::Expressions",
    "django/django/db/backends/ddl_references.py::Table",
    "django/django/db/backends/ddl_references.py::ForeignKeyName",
    "django/django/db/backends/ddl_references.py::Statement",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor",
    "django/tests/backends/test_ddl_references.py::ExpressionsTests",
    "django/django/db/models/constraints.py::UniqueConstraint"
  ],
  "found_functions": [
    "django/django/db/backends/ddl_references.py::Expressions.rename_table_references",
    "django/django/db/backends/ddl_references.py::Table.references_table",
    "django/django/db/backends/ddl_references.py::ForeignKeyName.references_table",
    "django/django/db/backends/ddl_references.py::Statement.references_table",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.delete_model",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor.delete_model",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor.remove_field",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._alter_field",
    "django/django/db/backends/ddl_references.py::Expressions.rename_column_references",
    "django/django/db/backends/ddl_references.py::ForeignKeyName.rename_column_references",
    "django/django/db/backends/ddl_references.py::Statement.rename_column_references",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._unique_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._create_unique_sql",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor.alter_db_table",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.alter_db_table",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.execute",
    "django/tests/backends/test_ddl_references.py::ExpressionsTests.test_rename_table_references",
    "django/django/db/backends/ddl_references.py::Expressions.__init__",
    "django/django/db/backends/ddl_references.py::Expressions.__str__",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor._remake_table",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor._alter_field",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.create_model",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.table_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.__enter__",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.__exit__",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.remove_field",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.add_field",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor._alter_many_to_many",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor.add_field",
    "django/django/db/models/constraints.py::UniqueConstraint.create_sql"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/backends/ddl_references.py",
      "Expressions.rename_table_references"
    ]
  ],
  "predictions": [
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.__enter__"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.__exit__"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.add_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_db_table"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.create_model"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.delete_model"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.execute"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.remove_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.table_sql"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.__init__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.__str__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.rename_column_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.rename_table_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "ForeignKeyName.references_table"
    ],
    [
      "django/db/backends/ddl_references.py",
      "ForeignKeyName.rename_column_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Statement.references_table"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Statement.rename_column_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Table.references_table"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._alter_many_to_many"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._remake_table"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.add_field"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.alter_db_table"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.delete_model"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.remove_field"
    ],
    [
      "django/db/models/constraints.py",
      "UniqueConstraint.create_sql"
    ],
    [
      "tests/backends/test_ddl_references.py",
      "ExpressionsTests.test_rename_table_references"
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
      "django/db/backends/ddl_references.py",
      "Expressions.rename_table_references"
    ]
  ],
  "false_positive": [
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.__enter__"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.__exit__"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.add_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_db_table"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.create_model"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.delete_model"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.execute"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.remove_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.table_sql"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.__init__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.__str__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Expressions.rename_column_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "ForeignKeyName.references_table"
    ],
    [
      "django/db/backends/ddl_references.py",
      "ForeignKeyName.rename_column_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Statement.references_table"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Statement.rename_column_references"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Table.references_table"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._alter_many_to_many"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._remake_table"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.add_field"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.alter_db_table"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.delete_model"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor.remove_field"
    ],
    [
      "django/db/models/constraints.py",
      "UniqueConstraint.create_sql"
    ],
    [
      "tests/backends/test_ddl_references.py",
      "ExpressionsTests.test_rename_table_references"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`unresolved_action`；因果终止：`legacy_causal_stop`；耗时 256.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/db/backends/ddl_references.py",
          "Expressions.rename_table_references"
        ]
      ],
      "final": [
        [
          "django/db/backends/ddl_references.py",
          "Expressions.rename_table_references"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 31,
      "model_request": 31,
      "model_response": 31,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 5,
      "search_page_summary": 4,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "search_action_error": 2,
      "seed_locations": 1,
      "causal_context": 22,
      "causal_parse": 22,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 9,
      "relevance": 16,
      "causal": 122
    },
    "predicted_function_count": 30,
    "seconds": 256.8335155369714
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "search_action_repair": 1,
    "generate_causal_graph": 22
  },
  "tokens": {
    "input": 346433,
    "output": 22699
  }
}
```

## 85. django__django-14999

项目：`django/django`；base commit：`a754b82dac511475b6276039471ccd17cc64aeb8`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/operations/models.py",
    "django/django/db/migrations/operations/base.py"
  ],
  "found_modules": [
    "django/django/db/migrations/operations/models.py::RenameModel",
    "django/django/db/migrations/operations/base.py::Operation"
  ],
  "found_functions": [
    "django/django/db/migrations/operations/models.py::RenameModel.database_forwards",
    "django/django/db/migrations/operations/base.py::Operation.database_forwards"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/operations/models.py",
      "RenameModel.database_forwards"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/operations/base.py",
      "Operation.database_forwards"
    ],
    [
      "django/db/migrations/operations/models.py",
      "RenameModel.database_forwards"
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
      "django/db/migrations/operations/models.py",
      "RenameModel.database_forwards"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/operations/base.py",
      "Operation.database_forwards"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 137.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/operations/models.py",
          "RenameModel.database_forwards"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/operations/models.py",
          "RenameModel.database_forwards"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/operations/models.py",
          "RenameModel.database_forwards"
        ]
      ],
      "final": [
        [
          "django/db/migrations/operations/models.py",
          "RenameModel.database_forwards"
        ]
      ]
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
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 29,
      "causal": 86
    },
    "predicted_function_count": 2,
    "seconds": 137.70567854866385
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 71459,
    "output": 3814
  }
}
```

## 86. django__django-15061

项目：`django/django`；base commit：`2c01ebb4be5d53cbf6450f356c10e436025d6d07`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 14.29% | 100.00% | 25.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/postgres/forms/ranges.py",
    "django/tests/forms_tests/tests/test_media.py",
    "django/django/forms/widgets.py",
    "django/tests/forms_tests/tests/test_forms.py",
    "django/tests/forms_tests/widget_tests/test_multiwidget.py",
    "django/tests/forms_tests/field_tests/test_multivaluefield.py",
    "django/django/forms/boundfield.py",
    "django/django/utils/html.py"
  ],
  "found_modules": [
    "django/django/contrib/postgres/forms/ranges.py::RangeWidget",
    "django/tests/forms_tests/tests/test_media.py::MyMultiWidget",
    "django/django/forms/widgets.py::SplitDateTimeWidget",
    "django/tests/forms_tests/tests/test_forms.py::PhoneWidget",
    "django/tests/forms_tests/widget_tests/test_multiwidget.py::MyMultiWidget",
    "django/tests/forms_tests/widget_tests/test_multiwidget.py::DeepCopyWidget",
    "django/tests/forms_tests/widget_tests/test_multiwidget.py::ComplexMultiWidget",
    "django/tests/forms_tests/field_tests/test_multivaluefield.py::ComplexMultiWidget",
    "django/django/forms/widgets.py::MultiWidget",
    "django/django/forms/boundfield.py::BoundField",
    "django/django/forms/widgets.py::Widget"
  ],
  "found_functions": [
    "django/django/forms/widgets.py::MultiWidget.__init__",
    "django/django/forms/widgets.py::MultiWidget.get_context",
    "django/django/forms/widgets.py::MultiWidget.id_for_label",
    "django/django/forms/boundfield.py::BoundField.label_tag",
    "django/django/forms/widgets.py::Widget.id_for_label",
    "django/django/forms/boundfield.py::BoundField.id_for_label",
    "django/django/utils/html.py::format_html"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/widgets.py",
      "MultiWidget.id_for_label"
    ]
  ],
  "predictions": [
    [
      "django/forms/boundfield.py",
      "BoundField.id_for_label"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.label_tag"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget.__init__"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget.get_context"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget.id_for_label"
    ],
    [
      "django/forms/widgets.py",
      "Widget.id_for_label"
    ],
    [
      "django/utils/html.py",
      "format_html"
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
      "django/forms/widgets.py",
      "MultiWidget.id_for_label"
    ]
  ],
  "false_positive": [
    [
      "django/forms/boundfield.py",
      "BoundField.id_for_label"
    ],
    [
      "django/forms/boundfield.py",
      "BoundField.label_tag"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget.__init__"
    ],
    [
      "django/forms/widgets.py",
      "MultiWidget.get_context"
    ],
    [
      "django/forms/widgets.py",
      "Widget.id_for_label"
    ],
    [
      "django/utils/html.py",
      "format_html"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 382.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/forms/widgets.py",
          "MultiWidget.id_for_label"
        ]
      ],
      "seeds": [
        [
          "django/forms/widgets.py",
          "MultiWidget.id_for_label"
        ]
      ],
      "causal_received": [
        [
          "django/forms/widgets.py",
          "MultiWidget.id_for_label"
        ]
      ],
      "final": [
        [
          "django/forms/widgets.py",
          "MultiWidget.id_for_label"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 23,
      "model_request": 23,
      "model_response": 23,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 7,
      "relevance_attempt": 7,
      "relevance_decisions": 7,
      "seed_locations": 1,
      "causal_context": 11,
      "causal_parse": 11,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 6,
      "relevance": 22,
      "causal": 111
    },
    "predicted_function_count": 7,
    "seconds": 381.983965549618
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 7,
    "generate_causal_graph": 11
  },
  "tokens": {
    "input": 78541,
    "output": 7521
  }
}
```

## 87. django__django-15202

项目：`django/django`；base commit：`4fd3044ca0135da903a70dfb66992293f529ecf1`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/validators.py",
    "django/django/forms/fields.py",
    "django/django/core/exceptions.py"
  ],
  "found_modules": [
    "django/django/core/validators.py::URLValidator",
    "django/django/forms/fields.py::Field",
    "django/django/forms/fields.py::URLField",
    "django/django/core/exceptions.py::ValidationError"
  ],
  "found_functions": [
    "django/django/core/validators.py::URLValidator.__call__",
    "django/django/forms/fields.py::Field.clean",
    "django/django/forms/fields.py::URLField.to_python",
    "django/django/forms/fields.py::URLField.split_url"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/validators.py",
      "URLValidator.__call__"
    ]
  ],
  "predictions": [
    [
      "django/core/validators.py",
      "URLValidator.__call__"
    ],
    [
      "django/forms/fields.py",
      "<unresolved>:URLField.split_url"
    ],
    [
      "django/forms/fields.py",
      "Field.clean"
    ],
    [
      "django/forms/fields.py",
      "URLField.to_python"
    ]
  ],
  "unresolved": [
    {
      "file": "django/forms/fields.py",
      "name": "URLField.split_url",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/core/validators.py",
      "URLValidator.__call__"
    ]
  ],
  "false_positive": [
    [
      "django/forms/fields.py",
      "<unresolved>:URLField.split_url"
    ],
    [
      "django/forms/fields.py",
      "Field.clean"
    ],
    [
      "django/forms/fields.py",
      "URLField.to_python"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 201.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/validators.py",
          "URLValidator.__call__"
        ]
      ],
      "seeds": [
        [
          "django/core/validators.py",
          "URLValidator.__call__"
        ]
      ],
      "causal_received": [
        [
          "django/core/validators.py",
          "URLValidator.__call__"
        ]
      ],
      "final": [
        [
          "django/core/validators.py",
          "URLValidator.__call__"
        ]
      ]
    },
    "search_unprocessed_matches": 67,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 23,
      "model_request": 23,
      "model_response": 23,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 11,
      "source_receipt": 9,
      "relevance_attempt": 9,
      "relevance_decisions": 9,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 69,
      "causal": 64
    },
    "predicted_function_count": 4,
    "seconds": 201.50552506744862
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 9,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 70167,
    "output": 7769
  }
}
```

## 88. django__django-15213

项目：`django/django`；base commit：`03cadb912c78b769d6bf4a943a2a35fc1d952960`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/expressions.py"
  ],
  "found_modules": [
    "django/django/db/models/expressions.py::Func",
    "django/django/db/models/expressions.py::ExpressionWrapper"
  ],
  "found_functions": [
    "django/django/db/models/expressions.py::Func.as_sql"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field.select_format"
    ]
  ],
  "predictions": [
    [
      "django/db/models/expressions.py",
      "Func.as_sql"
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
      "django/db/models/expressions.py",
      "Func.as_sql"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/fields/__init__.py",
      "Field.select_format"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 228.9 秒。

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
    "search_unprocessed_matches": 248,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 23,
      "model_request": 23,
      "model_response": 23,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 14,
      "search_page_summary": 5,
      "source_receipt": 13,
      "relevance_attempt": 13,
      "relevance_decisions": 13,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 14,
      "relevance": 81,
      "causal": 69
    },
    "predicted_function_count": 1,
    "seconds": 228.939212648198
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 13,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 78411,
    "output": 5077
  }
}
```

## 89. django__django-15252

项目：`django/django`；base commit：`361bb8f786f112ee275be136795c0b1ecefff928`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 7.69% | 100.00% | 14.29% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/commands/showmigrations.py",
    "django/django/db/migrations/recorder.py",
    "django/django/db/migrations/executor.py",
    "django/django/core/management/commands/migrate.py",
    "django/django/db/migrations/loader.py"
  ],
  "found_modules": [
    "django/django/core/management/commands/showmigrations.py::Command",
    "django/django/db/migrations/recorder.py::MigrationRecorder",
    "django/django/db/migrations/executor.py::MigrationExecutor",
    "django/django/core/management/commands/migrate.py::Command",
    "django/django/db/migrations/loader.py::MigrationLoader"
  ],
  "found_functions": [
    "django/django/core/management/commands/showmigrations.py::Command.handle",
    "django/django/core/management/commands/showmigrations.py::Command.show_list",
    "django/django/core/management/commands/showmigrations.py::Command.show_plan",
    "django/django/db/migrations/recorder.py::MigrationRecorder.has_table",
    "django/django/db/migrations/recorder.py::MigrationRecorder.ensure_schema",
    "django/django/db/migrations/recorder.py::MigrationRecorder.record_applied",
    "django/django/db/migrations/recorder.py::MigrationRecorder.record_unapplied",
    "django/django/db/migrations/recorder.py::MigrationRecorder.applied_migrations",
    "django/django/db/migrations/executor.py::MigrationExecutor.migrate",
    "django/django/core/management/commands/migrate.py::Command.handle",
    "django/django/db/migrations/loader.py::MigrationLoader.build_graph",
    "django/django/db/migrations/loader.py::MigrationLoader.check_consistent_history",
    "django/django/db/migrations/executor.py::MigrationExecutor.check_replacements"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/executor.py",
      "MigrationExecutor.migrate"
    ]
  ],
  "predictions": [
    [
      "django/core/management/commands/migrate.py",
      "Command.handle"
    ],
    [
      "django/core/management/commands/showmigrations.py",
      "Command.handle"
    ],
    [
      "django/core/management/commands/showmigrations.py",
      "Command.show_list"
    ],
    [
      "django/core/management/commands/showmigrations.py",
      "Command.show_plan"
    ],
    [
      "django/db/migrations/executor.py",
      "MigrationExecutor.check_replacements"
    ],
    [
      "django/db/migrations/executor.py",
      "MigrationExecutor.migrate"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.build_graph"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.check_consistent_history"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.applied_migrations"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.ensure_schema"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.has_table"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.record_applied"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.record_unapplied"
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
      "django/db/migrations/executor.py",
      "MigrationExecutor.migrate"
    ]
  ],
  "false_positive": [
    [
      "django/core/management/commands/migrate.py",
      "Command.handle"
    ],
    [
      "django/core/management/commands/showmigrations.py",
      "Command.handle"
    ],
    [
      "django/core/management/commands/showmigrations.py",
      "Command.show_list"
    ],
    [
      "django/core/management/commands/showmigrations.py",
      "Command.show_plan"
    ],
    [
      "django/db/migrations/executor.py",
      "MigrationExecutor.check_replacements"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.build_graph"
    ],
    [
      "django/db/migrations/loader.py",
      "MigrationLoader.check_consistent_history"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.applied_migrations"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.ensure_schema"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.has_table"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.record_applied"
    ],
    [
      "django/db/migrations/recorder.py",
      "MigrationRecorder.record_unapplied"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 215.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [],
      "seeds": [],
      "causal_received": [
        [
          "django/db/migrations/executor.py",
          "MigrationExecutor.migrate"
        ]
      ],
      "final": [
        [
          "django/db/migrations/executor.py",
          "MigrationExecutor.migrate"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 20,
      "model_request": 20,
      "model_response": 20,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 15,
      "causal_parse": 15,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 0,
      "causal": 79
    },
    "predicted_function_count": 13,
    "seconds": 215.8265362503007
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "generate_causal_graph": 15
  },
  "tokens": {
    "input": 126084,
    "output": 11995
  }
}
```

## 90. django__django-15320

项目：`django/django`；base commit：`b55ebe32417e0884b6b8b3e1bc0379033aa221af`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/expressions.py"
  ],
  "found_modules": [
    "django/django/db/models/expressions.py::Subquery"
  ],
  "found_functions": []
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/expressions.py",
      "Subquery.__init__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/models/expressions.py",
      "Subquery.__init__"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 234.0 秒。

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
          "django/db/models/expressions.py",
          "Subquery.__init__"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 930,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 14,
      "search_page_summary": 5,
      "source_receipt": 13,
      "relevance_attempt": 13,
      "relevance_decisions": 13,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 101,
      "causal": 44
    },
    "predicted_function_count": 0,
    "seconds": 233.98966749291867
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 13,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 71255,
    "output": 3857
  }
}
```

## 91. django__django-15347

项目：`django/django`；base commit：`7c4f3965098baad2396e24501e09237425a7bd6f`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/messages/storage/base.py",
    "django/django/contrib/messages/storage/cookie.py"
  ],
  "found_modules": [
    "django/django/contrib/messages/storage/base.py::Message",
    "django/django/contrib/messages/storage/cookie.py::MessageEncoder",
    "django/django/contrib/messages/storage/cookie.py::MessageDecoder",
    "django/django/contrib/messages/storage/base.py::BaseStorage"
  ],
  "found_functions": [
    "django/django/contrib/messages/storage/base.py::Message._prepare",
    "django/django/contrib/messages/storage/base.py::Message.__init__",
    "django/django/contrib/messages/storage/base.py::BaseStorage.add"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/messages/storage/cookie.py",
      "MessageEncoder.default"
    ]
  ],
  "predictions": [
    [
      "django/contrib/messages/storage/base.py",
      "BaseStorage.add"
    ],
    [
      "django/contrib/messages/storage/base.py",
      "Message.__init__"
    ],
    [
      "django/contrib/messages/storage/base.py",
      "Message._prepare"
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
      "django/contrib/messages/storage/base.py",
      "BaseStorage.add"
    ],
    [
      "django/contrib/messages/storage/base.py",
      "Message.__init__"
    ],
    [
      "django/contrib/messages/storage/base.py",
      "Message._prepare"
    ]
  ],
  "missed_targets": [
    [
      "django/contrib/messages/storage/cookie.py",
      "MessageEncoder.default"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 137.9 秒。

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
          "django/contrib/messages/storage/cookie.py",
          "MessageEncoder.default"
        ]
      ],
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
      "search_result": 7,
      "search_page_summary": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 20,
      "causal": 16
    },
    "predicted_function_count": 3,
    "seconds": 137.85133654624224
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 25282,
    "output": 3825
  }
}
```

## 92. django__django-15388

项目：`django/django`；base commit：`c5cd8783825b5f6384417dac5f3889b4210b7d08`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/autoreload.py",
    "django/tests/admin_scripts/custom_templates/project_template/project_name/settings.py"
  ],
  "found_modules": [
    "django/django/utils/autoreload.py::StatReloader",
    "django/django/utils/autoreload.py::BaseReloader",
    "django/django/utils/autoreload.py::WatchmanReloader"
  ],
  "found_functions": [
    "django/django/utils/autoreload.py::StatReloader.snapshot_files",
    "django/django/utils/autoreload.py::StatReloader.tick",
    "django/django/utils/autoreload.py::BaseReloader.watched_files",
    "django/django/utils/autoreload.py::WatchmanReloader._update_watches"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/template/autoreload.py",
      "template_changed"
    ]
  ],
  "predictions": [
    [
      "django/utils/autoreload.py",
      "BaseReloader.watched_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.snapshot_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.tick"
    ],
    [
      "django/utils/autoreload.py",
      "WatchmanReloader._update_watches"
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
      "django/utils/autoreload.py",
      "BaseReloader.watched_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.snapshot_files"
    ],
    [
      "django/utils/autoreload.py",
      "StatReloader.tick"
    ],
    [
      "django/utils/autoreload.py",
      "WatchmanReloader._update_watches"
    ]
  ],
  "missed_targets": [
    [
      "django/template/autoreload.py",
      "template_changed"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 151.1 秒。

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
      "request_preflight": 17,
      "model_request": 17,
      "model_response": 17,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 5,
      "causal": 24
    },
    "predicted_function_count": 4,
    "seconds": 151.1200770298019
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 30451,
    "output": 9686
  }
}
```

## 93. django__django-15400

项目：`django/django`；base commit：`4c76ffc2d6c77c850b4bef8d9acc197d11c47937`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/functional.py"
  ],
  "found_modules": [
    "django/django/utils/functional.py::SimpleLazyObject",
    "django/django/utils/functional.py::__proxy__"
  ],
  "found_functions": [
    "django/django/utils/functional.py::new_method_proxy"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/functional.py",
      "lazy.__proxy__.__radd__"
    ]
  ],
  "predictions": [
    [
      "django/utils/functional.py",
      "new_method_proxy"
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
      "django/utils/functional.py",
      "new_method_proxy"
    ]
  ],
  "missed_targets": [
    [
      "django/utils/functional.py",
      "lazy.__proxy__.__radd__"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 154.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "因果收到目标实体但未保留",
    "coverage": {
      "search_received": [
        [
          "django/utils/functional.py",
          "lazy.__proxy__.__radd__"
        ]
      ],
      "seeds": [
        [
          "django/utils/functional.py",
          "lazy.__proxy__.__radd__"
        ]
      ],
      "causal_received": [
        [
          "django/utils/functional.py",
          "lazy.__proxy__.__radd__"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 7,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 8,
      "relevance": 23,
      "causal": 35
    },
    "predicted_function_count": 1,
    "seconds": 154.81576030422002
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 26995,
    "output": 2945
  }
}
```

## 94. django__django-15498

项目：`django/django`；base commit：`d90e34c61b27fba2527834806639eebbcfab9631`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/http.py",
    "django/django/utils/cache.py",
    "django/django/views/static.py"
  ],
  "found_modules": [],
  "found_functions": [
    "django/django/utils/http.py::parse_http_date",
    "django/django/utils/cache.py::get_conditional_response",
    "django/django/utils/http.py::parse_http_date_safe",
    "django/django/views/static.py::was_modified_since"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/views/static.py",
      "was_modified_since"
    ]
  ],
  "predictions": [
    [
      "django/utils/cache.py",
      "get_conditional_response"
    ],
    [
      "django/utils/http.py",
      "parse_http_date"
    ],
    [
      "django/utils/http.py",
      "parse_http_date_safe"
    ],
    [
      "django/views/static.py",
      "was_modified_since"
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
      "django/views/static.py",
      "was_modified_since"
    ]
  ],
  "false_positive": [
    [
      "django/utils/cache.py",
      "get_conditional_response"
    ],
    [
      "django/utils/http.py",
      "parse_http_date"
    ],
    [
      "django/utils/http.py",
      "parse_http_date_safe"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 182.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/views/static.py",
          "was_modified_since"
        ]
      ],
      "seeds": [
        [
          "django/views/static.py",
          "was_modified_since"
        ]
      ],
      "causal_received": [
        [
          "django/views/static.py",
          "was_modified_since"
        ]
      ],
      "final": [
        [
          "django/views/static.py",
          "was_modified_since"
        ]
      ]
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
      "search_result": 6,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 8,
      "causal_parse": 8,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 6,
      "relevance": 14,
      "causal": 20
    },
    "predicted_function_count": 4,
    "seconds": 182.71030382346362
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 8
  },
  "tokens": {
    "input": 41484,
    "output": 11241
  }
}
```

## 95. django__django-15695

项目：`django/django`；base commit：`647480166bfe7532e8c471fef0146e3a17e6c0c9`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/operations/models.py",
    "django/tests/migrations/test_operations.py"
  ],
  "found_modules": [
    "django/django/db/migrations/operations/models.py::RenameIndex",
    "django/tests/migrations/test_operations.py::OperationTests"
  ],
  "found_functions": [
    "django/django/db/migrations/operations/models.py::RenameIndex.database_backwards",
    "django/django/db/migrations/operations/models.py::RenameIndex.database_forwards",
    "django/tests/migrations/test_operations.py::OperationTests.test_rename_index"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/operations/models.py",
      "RenameIndex.database_forwards"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/operations/models.py",
      "RenameIndex.database_backwards"
    ],
    [
      "django/db/migrations/operations/models.py",
      "RenameIndex.database_forwards"
    ],
    [
      "tests/migrations/test_operations.py",
      "OperationTests.test_rename_index"
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
      "django/db/migrations/operations/models.py",
      "RenameIndex.database_forwards"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/operations/models.py",
      "RenameIndex.database_backwards"
    ],
    [
      "tests/migrations/test_operations.py",
      "OperationTests.test_rename_index"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 185.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/operations/models.py",
          "RenameIndex.database_forwards"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/operations/models.py",
          "RenameIndex.database_forwards"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/operations/models.py",
          "RenameIndex.database_forwards"
        ]
      ],
      "final": [
        [
          "django/db/migrations/operations/models.py",
          "RenameIndex.database_forwards"
        ]
      ]
    },
    "search_unprocessed_matches": 81,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 24,
      "model_request": 24,
      "model_response": 24,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 15,
      "source_receipt": 14,
      "relevance_attempt": 14,
      "relevance_decisions": 14,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 71,
      "causal": 164
    },
    "predicted_function_count": 3,
    "seconds": 185.72922395169735
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 14,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 200081,
    "output": 4775
  }
}
```

## 96. django__django-15738

项目：`django/django`；base commit：`6f73eb9d90cfec684529aab48d517e3d6449ba8c`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/backends/ddl_references.py",
    "django/django/db/backends/base/schema.py",
    "django/django/db/backends/utils.py",
    "django/django/db/backends/mysql/schema.py",
    "django/django/db/backends/postgresql/schema.py",
    "django/django/db/backends/sqlite3/schema.py"
  ],
  "found_modules": [
    "django/django/db/backends/ddl_references.py::TableColumns",
    "django/django/db/backends/ddl_references.py::IndexName",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor",
    "django/django/db/backends/ddl_references.py::Columns",
    "django/django/db/backends/ddl_references.py::Table",
    "django/django/db/backends/mysql/schema.py::DatabaseSchemaEditor",
    "django/django/db/backends/postgresql/schema.py::DatabaseSchemaEditor",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor"
  ],
  "found_functions": [
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.create_unique_name",
    "django/django/db/backends/ddl_references.py::Columns.__str__",
    "django/django/db/backends/ddl_references.py::Columns.col_str",
    "django/django/db/backends/ddl_references.py::Columns.__init__",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._unique_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._create_unique_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._index_columns",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.table_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._index_include_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.quote_name",
    "django/django/db/backends/ddl_references.py::IndexName.__init__",
    "django/django/db/backends/ddl_references.py::IndexName.__str__",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._create_index_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._create_index_name",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._unique_constraint_name",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._create_primary_key_sql",
    "django/django/db/backends/utils.py::split_identifier",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.alter_unique_together",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._delete_composed_index",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._delete_constraint_sql",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._alter_field",
    "django/django/db/backends/base/schema.py::BaseDatabaseSchemaEditor._constraint_names",
    "django/django/db/backends/mysql/schema.py::DatabaseSchemaEditor._delete_composed_index",
    "django/django/db/backends/postgresql/schema.py::DatabaseSchemaEditor._alter_field",
    "django/django/db/backends/sqlite3/schema.py::DatabaseSchemaEditor._alter_field"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._generate_added_field"
    ]
  ],
  "predictions": [
    [
      "django/db/backends/base/schema.py",
      "<unresolved>:BaseDatabaseSchemaEditor.create_unique_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._constraint_names"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_index_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_index_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_primary_key_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._delete_composed_index"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._delete_constraint_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._index_columns"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._index_include_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._unique_constraint_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_unique_together"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.quote_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.table_sql"
    ],
    [
      "django/db/backends/ddl_references.py",
      "<unresolved>:Columns.col_str"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Columns.__init__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Columns.__str__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "IndexName.__init__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "IndexName.__str__"
    ],
    [
      "django/db/backends/mysql/schema.py",
      "DatabaseSchemaEditor._delete_composed_index"
    ],
    [
      "django/db/backends/postgresql/schema.py",
      "DatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/utils.py",
      "split_identifier"
    ]
  ],
  "unresolved": [
    {
      "file": "django/db/backends/base/schema.py",
      "name": "BaseDatabaseSchemaEditor.create_unique_name",
      "reason": "absent"
    },
    {
      "file": "django/db/backends/ddl_references.py",
      "name": "Columns.col_str",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [
    [
      "django/db/backends/base/schema.py",
      "<unresolved>:BaseDatabaseSchemaEditor.create_unique_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._constraint_names"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_index_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_index_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_primary_key_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._create_unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._delete_composed_index"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._delete_constraint_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._index_columns"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._index_include_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._unique_constraint_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor._unique_sql"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.alter_unique_together"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.quote_name"
    ],
    [
      "django/db/backends/base/schema.py",
      "BaseDatabaseSchemaEditor.table_sql"
    ],
    [
      "django/db/backends/ddl_references.py",
      "<unresolved>:Columns.col_str"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Columns.__init__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "Columns.__str__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "IndexName.__init__"
    ],
    [
      "django/db/backends/ddl_references.py",
      "IndexName.__str__"
    ],
    [
      "django/db/backends/mysql/schema.py",
      "DatabaseSchemaEditor._delete_composed_index"
    ],
    [
      "django/db/backends/postgresql/schema.py",
      "DatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/sqlite3/schema.py",
      "DatabaseSchemaEditor._alter_field"
    ],
    [
      "django/db/backends/utils.py",
      "split_identifier"
    ]
  ],
  "missed_targets": [
    [
      "django/db/migrations/autodetector.py",
      "MigrationAutodetector._generate_added_field"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 265.8 秒。

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
      "request_preflight": 28,
      "model_request": 28,
      "model_response": 28,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 22,
      "causal_parse": 22,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 5,
      "relevance": 5,
      "causal": 93
    },
    "predicted_function_count": 25,
    "seconds": 265.83571877889335
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 22
  },
  "tokens": {
    "input": 267553,
    "output": 28163
  }
}
```

## 97. django__django-15781

项目：`django/django`；base commit：`8d160f154f0240a423e83ffe0690e472f837373c`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/base.py"
  ],
  "found_modules": [
    "django/django/core/management/base.py::DjangoHelpFormatter",
    "django/django/core/management/base.py::BaseCommand",
    "django/django/core/management/base.py::CommandParser"
  ],
  "found_functions": [
    "django/django/core/management/base.py::BaseCommand.create_parser",
    "django/django/core/management/base.py::BaseCommand.print_help",
    "django/django/core/management/base.py::BaseCommand.run_from_argv"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/management/base.py",
      "BaseCommand.create_parser"
    ]
  ],
  "predictions": [
    [
      "django/core/management/base.py",
      "BaseCommand.create_parser"
    ],
    [
      "django/core/management/base.py",
      "BaseCommand.print_help"
    ],
    [
      "django/core/management/base.py",
      "BaseCommand.run_from_argv"
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
      "django/core/management/base.py",
      "BaseCommand.create_parser"
    ]
  ],
  "false_positive": [
    [
      "django/core/management/base.py",
      "BaseCommand.print_help"
    ],
    [
      "django/core/management/base.py",
      "BaseCommand.run_from_argv"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 114.0 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/management/base.py",
          "BaseCommand.create_parser"
        ]
      ],
      "seeds": [
        [
          "django/core/management/base.py",
          "BaseCommand.create_parser"
        ]
      ],
      "causal_received": [
        [
          "django/core/management/base.py",
          "BaseCommand.create_parser"
        ]
      ],
      "final": [
        [
          "django/core/management/base.py",
          "BaseCommand.create_parser"
        ]
      ]
    },
    "search_unprocessed_matches": 4,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 16,
      "model_request": 16,
      "model_response": 16,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 0,
      "causal": 25
    },
    "predicted_function_count": 3,
    "seconds": 113.96132187917829
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 42884,
    "output": 4060
  }
}
```

## 98. django__django-15789

项目：`django/django`；base commit：`d4d5427571b4bf3a21c902276c2a00215c2a37cc`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/template/defaultfilters.py",
    "django/django/utils/html.py"
  ],
  "found_modules": [],
  "found_functions": [
    "django/django/template/defaultfilters.py::json_script",
    "django/django/utils/html.py::json_script"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/html.py",
      "json_script"
    ]
  ],
  "predictions": [
    [
      "django/template/defaultfilters.py",
      "json_script"
    ],
    [
      "django/utils/html.py",
      "json_script"
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
      "django/utils/html.py",
      "json_script"
    ]
  ],
  "false_positive": [
    [
      "django/template/defaultfilters.py",
      "json_script"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 106.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/utils/html.py",
          "json_script"
        ]
      ],
      "seeds": [
        [
          "django/utils/html.py",
          "json_script"
        ]
      ],
      "causal_received": [
        [
          "django/utils/html.py",
          "json_script"
        ]
      ],
      "final": [
        [
          "django/utils/html.py",
          "json_script"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 5,
      "model_request": 5,
      "model_response": 5,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 3,
      "causal_parse": 3,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 6
    },
    "predicted_function_count": 2,
    "seconds": 106.82309474237263
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 3
  },
  "tokens": {
    "input": 6471,
    "output": 471
  }
}
```

## 99. django__django-15790

项目：`django/django`；base commit：`c627226d05dd52aef59447dcfb29cec2c2b11b8a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 14.29% | 100.00% | 25.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/checks/templates.py",
    "django/django/template/backends/django.py"
  ],
  "found_modules": [],
  "found_functions": [
    "django/django/core/checks/templates.py::check_for_template_tags_with_the_same_name",
    "django/django/template/backends/django.py::get_template_tag_modules",
    "django/django/template/backends/django.py::get_package_libraries"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/checks/templates.py",
      "check_for_template_tags_with_the_same_name"
    ]
  ],
  "predictions": [
    [
      "django/core/checks/templates.py",
      "check_for_template_tags_with_the_same_name"
    ],
    [
      "django/template/backends/django.py",
      "get_package_libraries"
    ],
    [
      "django/template/backends/django.py",
      "get_template_tag_modules"
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
      "django/core/checks/templates.py",
      "check_for_template_tags_with_the_same_name"
    ]
  ],
  "false_positive": [
    [
      "django/template/backends/django.py",
      "get_package_libraries"
    ],
    [
      "django/template/backends/django.py",
      "get_template_tag_modules"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 125.8 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/checks/templates.py",
          "check_for_template_tags_with_the_same_name"
        ]
      ],
      "seeds": [
        [
          "django/core/checks/templates.py",
          "check_for_template_tags_with_the_same_name"
        ]
      ],
      "causal_received": [
        [
          "django/core/checks/templates.py",
          "check_for_template_tags_with_the_same_name"
        ]
      ],
      "final": [
        [
          "django/core/checks/templates.py",
          "check_for_template_tags_with_the_same_name"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 10,
      "model_request": 10,
      "model_response": 10,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 4,
      "search_page_summary": 4,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 8,
      "relevance": 6,
      "causal": 9
    },
    "predicted_function_count": 3,
    "seconds": 125.77140513435006
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 17382,
    "output": 1881
  }
}
```

## 100. django__django-15814

项目：`django/django`；base commit：`5eb6a2b33d70b9889e1cafa12594ad6f80773d3a`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/query.py"
  ],
  "found_modules": [
    "django/django/db/models/query.py::RelatedPopulator",
    "django/django/db/models/query.py::ModelIterable"
  ],
  "found_functions": [
    "django/django/db/models/query.py::RelatedPopulator.__init__",
    "django/django/db/models/query.py::ModelIterable.__iter__",
    "django/django/db/models/query.py::get_related_populators",
    "django/django/db/models/query.py::RelatedPopulator.populate"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query.deferred_to_data"
    ]
  ],
  "predictions": [
    [
      "django/db/models/query.py",
      "ModelIterable.__iter__"
    ],
    [
      "django/db/models/query.py",
      "RelatedPopulator.__init__"
    ],
    [
      "django/db/models/query.py",
      "RelatedPopulator.populate"
    ],
    [
      "django/db/models/query.py",
      "get_related_populators"
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
      "django/db/models/query.py",
      "ModelIterable.__iter__"
    ],
    [
      "django/db/models/query.py",
      "RelatedPopulator.__init__"
    ],
    [
      "django/db/models/query.py",
      "RelatedPopulator.populate"
    ],
    [
      "django/db/models/query.py",
      "get_related_populators"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/sql/query.py",
      "Query.deferred_to_data"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 123.8 秒。

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
    "search_unprocessed_matches": 850,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 17,
      "model_request": 17,
      "model_response": 17,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 37,
      "causal": 10
    },
    "predicted_function_count": 4,
    "seconds": 123.75530972704291
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 64333,
    "output": 4723
  }
}
```

## 101. django__django-15819

项目：`django/django`；base commit：`877c800f255ccaa7abde1fb944de45d1616f5cc9`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/management/commands/inspectdb.py"
  ],
  "found_modules": [
    "django/django/core/management/commands/inspectdb.py::Command"
  ],
  "found_functions": [
    "django/django/core/management/commands/inspectdb.py::Command.get_field_type"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/management/commands/inspectdb.py",
      "Command.handle_inspection"
    ]
  ],
  "predictions": [
    [
      "django/core/management/commands/inspectdb.py",
      "Command.get_field_type"
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
      "django/core/management/commands/inspectdb.py",
      "Command.get_field_type"
    ]
  ],
  "missed_targets": [
    [
      "django/core/management/commands/inspectdb.py",
      "Command.handle_inspection"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 122.5 秒。

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
          "django/core/management/commands/inspectdb.py",
          "Command.handle_inspection"
        ]
      ],
      "final": []
    },
    "search_unprocessed_matches": 33,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 16,
      "model_request": 16,
      "model_response": 16,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 7,
      "relevance_attempt": 7,
      "relevance_decisions": 7,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 13,
      "causal": 7
    },
    "predicted_function_count": 1,
    "seconds": 122.46646391227841
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 7,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 26760,
    "output": 4279
  }
}
```

## 102. django__django-15851

项目：`django/django`；base commit：`b4817d20b9e55df30be0b1b2ca8c8bb6d61aab07`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/backends/postgresql/client.py",
    "django/tests/dbshell/test_postgresql.py"
  ],
  "found_modules": [
    "django/django/db/backends/postgresql/client.py::DatabaseClient",
    "django/tests/dbshell/test_postgresql.py::PostgreSqlDbshellCommandTestCase"
  ],
  "found_functions": [
    "django/django/db/backends/postgresql/client.py::DatabaseClient.settings_to_cmd_args_env",
    "django/tests/dbshell/test_postgresql.py::PostgreSqlDbshellCommandTestCase.settings_to_cmd_args_env"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/backends/postgresql/client.py",
      "DatabaseClient.settings_to_cmd_args_env"
    ]
  ],
  "predictions": [
    [
      "django/db/backends/postgresql/client.py",
      "DatabaseClient.settings_to_cmd_args_env"
    ],
    [
      "tests/dbshell/test_postgresql.py",
      "PostgreSqlDbshellCommandTestCase.settings_to_cmd_args_env"
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
      "django/db/backends/postgresql/client.py",
      "DatabaseClient.settings_to_cmd_args_env"
    ]
  ],
  "false_positive": [
    [
      "tests/dbshell/test_postgresql.py",
      "PostgreSqlDbshellCommandTestCase.settings_to_cmd_args_env"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 164.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/backends/postgresql/client.py",
          "DatabaseClient.settings_to_cmd_args_env"
        ]
      ],
      "seeds": [
        [
          "django/db/backends/postgresql/client.py",
          "DatabaseClient.settings_to_cmd_args_env"
        ]
      ],
      "causal_received": [
        [
          "django/db/backends/postgresql/client.py",
          "DatabaseClient.settings_to_cmd_args_env"
        ]
      ],
      "final": [
        [
          "django/db/backends/postgresql/client.py",
          "DatabaseClient.settings_to_cmd_args_env"
        ]
      ]
    },
    "search_unprocessed_matches": 65,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 20,
      "model_request": 20,
      "model_response": 20,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 12,
      "search_page_summary": 5,
      "source_receipt": 10,
      "relevance_attempt": 10,
      "relevance_decisions": 10,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 41,
      "causal": 15
    },
    "predicted_function_count": 2,
    "seconds": 164.49391612783074
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 10,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 49340,
    "output": 3339
  }
}
```

## 103. django__django-15902

项目：`django/django`；base commit：`44c24bf02835323d5418512ebe8e76166739ebf8`。

状态：complete；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | NA |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/forms.py",
    "django/django/forms/formsets.py",
    "django/tests/forms_tests/field_tests/test_nullbooleanfield.py",
    "django/django/forms/utils.py",
    "django/django/utils/html.py"
  ],
  "found_modules": [
    "django/django/forms/forms.py::Form",
    "django/django/forms/formsets.py::ManagementForm",
    "django/tests/forms_tests/field_tests/test_nullbooleanfield.py::HiddenNullBooleanForm",
    "django/django/forms/formsets.py::BaseFormSet",
    "django/django/forms/utils.py::DEFAULT_TEMPLATE_DEPRECATION_MSG",
    "django/django/forms/forms.py::BaseForm",
    "django/django/forms/utils.py::RenderableMixin",
    "django/django/forms/utils.py::RenderableFormMixin",
    "django/django/forms/utils.py::RenderableErrorMixin"
  ],
  "found_functions": [
    "django/django/forms/formsets.py::BaseFormSet.management_form",
    "django/django/forms/utils.py::RenderableMixin.render",
    "django/django/forms/utils.py::RenderableMixin.get_context"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.management_form"
    ],
    [
      "django/forms/utils.py",
      "RenderableMixin.get_context"
    ],
    [
      "django/forms/utils.py",
      "RenderableMixin.render"
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
      "django/forms/formsets.py",
      "BaseFormSet.management_form"
    ],
    [
      "django/forms/utils.py",
      "RenderableMixin.get_context"
    ],
    [
      "django/forms/utils.py",
      "RenderableMixin.render"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 205.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "NA",
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
      "request_preflight": 24,
      "model_request": 24,
      "model_response": 24,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "search_page_summary": 5,
      "source_receipt": 3,
      "relevance_attempt": 3,
      "relevance_decisions": 3,
      "seed_locations": 1,
      "causal_context": 16,
      "causal_parse": 16,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 10,
      "causal": 64
    },
    "predicted_function_count": 3,
    "seconds": 205.72150118555874
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 3,
    "generate_causal_graph": 16
  },
  "tokens": {
    "input": 95340,
    "output": 11399
  }
}
```

## 104. django__django-15996

项目：`django/django`；base commit：`b30c0081d4d8a31ab7dc7f72a4c7099af606ef29`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 命中 |
| CoSIL/off | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 20.00% | 100.00% | 33.33% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/utils/functional.py",
    "django/django/db/migrations/serializer.py"
  ],
  "found_modules": [
    "django/django/utils/functional.py::__proxy__",
    "django/django/db/migrations/serializer.py::EnumSerializer",
    "django/django/db/migrations/serializer.py::ModelFieldSerializer",
    "django/django/db/migrations/serializer.py::RegexSerializer",
    "django/django/db/migrations/serializer.py::BaseSerializer"
  ],
  "found_functions": [
    "django/django/utils/functional.py::__proxy__.__reduce__",
    "django/django/db/migrations/serializer.py::EnumSerializer.serialize",
    "django/django/db/migrations/serializer.py::RegexSerializer.serialize",
    "django/django/db/migrations/serializer.py::serializer_factory",
    "django/django/db/migrations/serializer.py::BaseSerializer.serialize"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/serializer.py",
      "EnumSerializer.serialize"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/serializer.py",
      "BaseSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "EnumSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "RegexSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "serializer_factory"
    ],
    [
      "django/utils/functional.py",
      "<unresolved>:__proxy__.__reduce__"
    ]
  ],
  "unresolved": [
    {
      "file": "django/utils/functional.py",
      "name": "__proxy__.__reduce__",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/db/migrations/serializer.py",
      "EnumSerializer.serialize"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/serializer.py",
      "BaseSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "RegexSerializer.serialize"
    ],
    [
      "django/db/migrations/serializer.py",
      "serializer_factory"
    ],
    [
      "django/utils/functional.py",
      "<unresolved>:__proxy__.__reduce__"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 179.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ],
      "final": [
        [
          "django/db/migrations/serializer.py",
          "EnumSerializer.serialize"
        ]
      ]
    },
    "search_unprocessed_matches": 2,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "search_page_summary": 5,
      "source_receipt": 6,
      "relevance_attempt": 6,
      "relevance_decisions": 6,
      "seed_locations": 1,
      "causal_context": 10,
      "causal_parse": 10,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 6,
      "relevance": 32,
      "causal": 37
    },
    "predicted_function_count": 5,
    "seconds": 179.24050912912935
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 2
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 6,
    "generate_causal_graph": 10
  },
  "tokens": {
    "input": 45694,
    "output": 9282
  }
}
```

## 105. django__django-16041

项目：`django/django`；base commit：`6df9398cce063874ae4d59db126d4adacb0fa8d3`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/formsets.py",
    "django/tests/forms_tests/tests/test_formsets.py"
  ],
  "found_modules": [
    "django/django/forms/formsets.py::BaseFormSet",
    "django/tests/forms_tests/tests/test_formsets.py::FormsFormsetTestCase"
  ],
  "found_functions": [
    "django/django/forms/formsets.py::BaseFormSet.empty_form",
    "django/django/forms/formsets.py::BaseFormSet.get_form_kwargs",
    "django/tests/forms_tests/tests/test_formsets.py::FormsFormsetTestCase.test_form_kwargs_empty_form"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.empty_form"
    ]
  ],
  "predictions": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.empty_form"
    ],
    [
      "django/forms/formsets.py",
      "BaseFormSet.get_form_kwargs"
    ],
    [
      "tests/forms_tests/tests/test_formsets.py",
      "FormsFormsetTestCase.test_form_kwargs_empty_form"
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
      "django/forms/formsets.py",
      "BaseFormSet.empty_form"
    ]
  ],
  "false_positive": [
    [
      "django/forms/formsets.py",
      "BaseFormSet.get_form_kwargs"
    ],
    [
      "tests/forms_tests/tests/test_formsets.py",
      "FormsFormsetTestCase.test_form_kwargs_empty_form"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 126.6 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.empty_form"
        ]
      ],
      "seeds": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.empty_form"
        ]
      ],
      "causal_received": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.empty_form"
        ]
      ],
      "final": [
        [
          "django/forms/formsets.py",
          "BaseFormSet.empty_form"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 14,
      "model_request": 14,
      "model_response": 14,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 6,
      "search_page_summary": 4,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 6,
      "relevance": 27,
      "causal": 10
    },
    "predicted_function_count": 3,
    "seconds": 126.62106860242784
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 27913,
    "output": 2522
  }
}
```

## 106. django__django-16046

项目：`django/django`；base commit：`ec13e801b820614ff374cb0046092caab8d67249`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 100.00% | 100.00% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 12.50% | 100.00% | 22.22% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/humanize/templatetags/humanize.py",
    "django/django/utils/formats.py",
    "django/django/utils/numberformat.py",
    "django/tests/utils_tests/test_numberformat.py",
    "django/django/forms/widgets.py"
  ],
  "found_modules": [
    "django/tests/utils_tests/test_numberformat.py::TestNumberFormat",
    "django/tests/utils_tests/test_numberformat.py::EuroDecimal",
    "django/django/forms/widgets.py::DateTimeBaseInput"
  ],
  "found_functions": [
    "django/django/contrib/humanize/templatetags/humanize.py::intcomma",
    "django/django/utils/formats.py::number_format",
    "django/django/utils/formats.py::localize_input",
    "django/django/utils/formats.py::localize",
    "django/django/utils/numberformat.py::format",
    "django/tests/utils_tests/test_numberformat.py::TestNumberFormat.test_decimal_subclass",
    "django/tests/utils_tests/test_numberformat.py::EuroDecimal.__format__",
    "django/django/forms/widgets.py::DateTimeBaseInput.format_value"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/utils/numberformat.py",
      "format"
    ]
  ],
  "predictions": [
    [
      "django/contrib/humanize/templatetags/humanize.py",
      "intcomma"
    ],
    [
      "django/forms/widgets.py",
      "DateTimeBaseInput.format_value"
    ],
    [
      "django/utils/formats.py",
      "localize"
    ],
    [
      "django/utils/formats.py",
      "localize_input"
    ],
    [
      "django/utils/formats.py",
      "number_format"
    ],
    [
      "django/utils/numberformat.py",
      "format"
    ],
    [
      "tests/utils_tests/test_numberformat.py",
      "<unresolved>:EuroDecimal.__format__"
    ],
    [
      "tests/utils_tests/test_numberformat.py",
      "TestNumberFormat.test_decimal_subclass"
    ]
  ],
  "unresolved": [
    {
      "file": "tests/utils_tests/test_numberformat.py",
      "name": "EuroDecimal.__format__",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/utils/numberformat.py",
      "format"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/humanize/templatetags/humanize.py",
      "intcomma"
    ],
    [
      "django/forms/widgets.py",
      "DateTimeBaseInput.format_value"
    ],
    [
      "django/utils/formats.py",
      "localize"
    ],
    [
      "django/utils/formats.py",
      "localize_input"
    ],
    [
      "django/utils/formats.py",
      "number_format"
    ],
    [
      "tests/utils_tests/test_numberformat.py",
      "<unresolved>:EuroDecimal.__format__"
    ],
    [
      "tests/utils_tests/test_numberformat.py",
      "TestNumberFormat.test_decimal_subclass"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 221.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/utils/numberformat.py",
          "format"
        ]
      ],
      "seeds": [
        [
          "django/utils/numberformat.py",
          "format"
        ]
      ],
      "causal_received": [
        [
          "django/utils/numberformat.py",
          "format"
        ]
      ],
      "final": [
        [
          "django/utils/numberformat.py",
          "format"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 16,
      "model_request": 16,
      "model_response": 16,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 4,
      "search_page_summary": 4,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "seed_locations": 1,
      "causal_context": 9,
      "causal_parse": 9,
      "output_truncated": 2,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 8,
      "causal": 28
    },
    "predicted_function_count": 8,
    "seconds": 221.71292261499912
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 9
  },
  "tokens": {
    "input": 65863,
    "output": 12787
  }
}
```

## 107. django__django-16139

项目：`django/django`；base commit：`d559cb02da30f74debbb1fc3a46de0df134d2d80`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 100.00% | 100.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/auth/forms.py"
  ],
  "found_modules": [
    "django/django/contrib/auth/forms.py::UserChangeForm",
    "django/django/contrib/auth/forms.py::ReadOnlyPasswordHashField"
  ],
  "found_functions": [
    "django/django/contrib/auth/forms.py::UserChangeForm.__init__"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/auth/forms.py",
      "UserChangeForm.__init__"
    ]
  ],
  "predictions": [
    [
      "django/contrib/auth/forms.py",
      "UserChangeForm.__init__"
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
      "django/contrib/auth/forms.py",
      "UserChangeForm.__init__"
    ]
  ],
  "false_positive": [],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 135.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/auth/forms.py",
          "UserChangeForm.__init__"
        ]
      ],
      "seeds": [
        [
          "django/contrib/auth/forms.py",
          "UserChangeForm.__init__"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/auth/forms.py",
          "UserChangeForm.__init__"
        ]
      ],
      "final": [
        [
          "django/contrib/auth/forms.py",
          "UserChangeForm.__init__"
        ]
      ]
    },
    "search_unprocessed_matches": 859,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 15,
      "model_request": 15,
      "model_response": 15,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 7,
      "search_page_summary": 4,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "output_truncated": 1,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 1,
      "relevance": 37,
      "causal": 4
    },
    "predicted_function_count": 1,
    "seconds": 135.68324513919652
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 3
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 32331,
    "output": 8864
  }
}
```

## 108. django__django-16229

项目：`django/django`；base commit：`04b15022e8d1f49af69d8a1e6cd678f31f1280ff`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/forms/models.py"
  ],
  "found_modules": [
    "django/django/forms/models.py::BaseModelForm"
  ],
  "found_functions": []
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/forms/boundfield.py",
      "BoundField.as_widget"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/forms/boundfield.py",
      "BoundField.as_widget"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 114.4 秒。

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
      "request_preflight": 14,
      "model_request": 14,
      "model_response": 14,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 4,
      "relevance_attempt": 4,
      "relevance_decisions": 4,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 0,
      "relevance": 5,
      "causal": 8
    },
    "predicted_function_count": 0,
    "seconds": 114.42173305060714
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 4,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 19147,
    "output": 2793
  }
}
```

## 109. django__django-16255

项目：`django/django`；base commit：`444b6da7cc229a58a2c476a52e45233001dc7073`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 100.00% | 100.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/sitemaps/__init__.py"
  ],
  "found_modules": [
    "django/django/contrib/sitemaps/__init__.py::Sitemap"
  ],
  "found_functions": [
    "django/django/contrib/sitemaps/__init__.py::Sitemap.get_latest_lastmod"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/sitemaps/__init__.py",
      "Sitemap.get_latest_lastmod"
    ]
  ],
  "predictions": [
    [
      "django/contrib/sitemaps/__init__.py",
      "Sitemap.get_latest_lastmod"
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
      "django/contrib/sitemaps/__init__.py",
      "Sitemap.get_latest_lastmod"
    ]
  ],
  "false_positive": [],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 106.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/sitemaps/__init__.py",
          "Sitemap.get_latest_lastmod"
        ]
      ],
      "seeds": [
        [
          "django/contrib/sitemaps/__init__.py",
          "Sitemap.get_latest_lastmod"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/sitemaps/__init__.py",
          "Sitemap.get_latest_lastmod"
        ]
      ],
      "final": [
        [
          "django/contrib/sitemaps/__init__.py",
          "Sitemap.get_latest_lastmod"
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
      "main_search": 4,
      "relevance": 0,
      "causal": 15
    },
    "predicted_function_count": 1,
    "seconds": 106.70475367456675
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
    "input": 13364,
    "output": 1456
  }
}
```

## 110. django__django-16379

项目：`django/django`；base commit：`1d0fa848e084cad62d0bb6bde3b51e4862558e57`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 100.00% | 66.67% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/core/cache/backends/filebased.py"
  ],
  "found_modules": [
    "django/django/core/cache/backends/filebased.py::FileBasedCache"
  ],
  "found_functions": [
    "django/django/core/cache/backends/filebased.py::FileBasedCache.has_key",
    "django/django/core/cache/backends/filebased.py::FileBasedCache._is_expired"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/core/cache/backends/filebased.py",
      "FileBasedCache.has_key"
    ]
  ],
  "predictions": [
    [
      "django/core/cache/backends/filebased.py",
      "FileBasedCache._is_expired"
    ],
    [
      "django/core/cache/backends/filebased.py",
      "FileBasedCache.has_key"
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
      "django/core/cache/backends/filebased.py",
      "FileBasedCache.has_key"
    ]
  ],
  "false_positive": [
    [
      "django/core/cache/backends/filebased.py",
      "FileBasedCache._is_expired"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 115.6 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/core/cache/backends/filebased.py",
          "FileBasedCache.has_key"
        ]
      ],
      "seeds": [
        [
          "django/core/cache/backends/filebased.py",
          "FileBasedCache.has_key"
        ]
      ],
      "causal_received": [
        [
          "django/core/cache/backends/filebased.py",
          "FileBasedCache.has_key"
        ]
      ],
      "final": [
        [
          "django/core/cache/backends/filebased.py",
          "FileBasedCache.has_key"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 10,
      "model_request": 10,
      "model_response": 10,
      "search_query": 4,
      "search_matches": 4,
      "search_result": 4,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "search_page_summary": 4,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 8,
      "causal": 16
    },
    "predicted_function_count": 2,
    "seconds": 115.56792530417442
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 17851,
    "output": 2281
  }
}
```

## 111. django__django-16400

项目：`django/django`；base commit：`0bd2c0c9015b53c41394a1c0989afbfd94dc2830`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 33.33% | 100.00% | 50.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/auth/apps.py",
    "django/django/contrib/auth/management/__init__.py",
    "django/django/contrib/contenttypes/management/__init__.py"
  ],
  "found_modules": [
    "django/django/contrib/auth/apps.py::AuthConfig"
  ],
  "found_functions": [
    "django/django/contrib/auth/apps.py::AuthConfig.ready",
    "django/django/contrib/auth/management/__init__.py::create_permissions",
    "django/django/contrib/contenttypes/management/__init__.py::create_contenttypes"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/auth/management/__init__.py",
      "create_permissions"
    ]
  ],
  "predictions": [
    [
      "django/contrib/auth/apps.py",
      "AuthConfig.ready"
    ],
    [
      "django/contrib/auth/management/__init__.py",
      "create_permissions"
    ],
    [
      "django/contrib/contenttypes/management/__init__.py",
      "create_contenttypes"
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
      "django/contrib/auth/management/__init__.py",
      "create_permissions"
    ]
  ],
  "false_positive": [
    [
      "django/contrib/auth/apps.py",
      "AuthConfig.ready"
    ],
    [
      "django/contrib/contenttypes/management/__init__.py",
      "create_contenttypes"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 165.3 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/auth/management/__init__.py",
          "create_permissions"
        ]
      ],
      "seeds": [
        [
          "django/contrib/auth/management/__init__.py",
          "create_permissions"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/auth/management/__init__.py",
          "create_permissions"
        ]
      ],
      "final": [
        [
          "django/contrib/auth/management/__init__.py",
          "create_permissions"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 12,
      "model_request": 12,
      "model_response": 12,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 2,
      "relevance_attempt": 2,
      "relevance_decisions": 2,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 5,
      "causal_parse": 5,
      "run_end": 1
    },
    "duplicate_code_associations": 1,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 5,
      "causal": 6
    },
    "predicted_function_count": 3,
    "seconds": 165.30600293446332
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 2,
    "generate_causal_graph": 5
  },
  "tokens": {
    "input": 28982,
    "output": 3805
  }
}
```

## 112. django__django-16408

项目：`django/django`；base commit：`ef85b6bf0bc5a8b194f0724cf5bbedbcee402b96`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 12.50% | 50.00% | 20.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/models/sql/query.py",
    "django/tests/queries/test_query.py",
    "django/django/db/models/sql/compiler.py",
    "django/django/db/models/query_utils.py",
    "django/django/db/models/query.py",
    "django/django/db/models/fields/related.py"
  ],
  "found_modules": [
    "django/django/db/models/sql/query.py::Query",
    "django/tests/queries/test_query.py::TestQuery",
    "django/django/db/models/sql/compiler.py::SQLCompiler",
    "django/django/db/models/query_utils.py::FilteredRelation",
    "django/django/db/models/query.py::QuerySet"
  ],
  "found_functions": [
    "django/django/db/models/sql/query.py::Query.add_select_related",
    "django/django/db/models/sql/query.py::Query.clone",
    "django/tests/queries/test_query.py::TestQuery.test_clone_select_related",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_default_columns",
    "django/django/db/models/sql/compiler.py::SQLCompiler.get_related_selections",
    "django/django/db/models/query_utils.py::select_related_descend",
    "django/django/db/models/sql/compiler.py::SQLCompiler._get_field_choices",
    "django/django/db/models/query.py::QuerySet.select_related"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections.local_setter_noop"
    ]
  ],
  "predictions": [
    [
      "django/db/models/query.py",
      "QuerySet.select_related"
    ],
    [
      "django/db/models/query_utils.py",
      "select_related_descend"
    ],
    [
      "django/db/models/sql/compiler.py",
      "<unresolved>:SQLCompiler._get_field_choices"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_default_columns"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_select_related"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.clone"
    ],
    [
      "tests/queries/test_query.py",
      "TestQuery.test_clone_select_related"
    ]
  ],
  "unresolved": [
    {
      "file": "django/db/models/sql/compiler.py",
      "name": "SQLCompiler._get_field_choices",
      "reason": "absent"
    }
  ]
}
```

函数集合分析：

```json
{
  "correct": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections"
    ]
  ],
  "false_positive": [
    [
      "django/db/models/query.py",
      "QuerySet.select_related"
    ],
    [
      "django/db/models/query_utils.py",
      "select_related_descend"
    ],
    [
      "django/db/models/sql/compiler.py",
      "<unresolved>:SQLCompiler._get_field_choices"
    ],
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_default_columns"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.add_select_related"
    ],
    [
      "django/db/models/sql/query.py",
      "Query.clone"
    ],
    [
      "tests/queries/test_query.py",
      "TestQuery.test_clone_select_related"
    ]
  ],
  "missed_targets": [
    [
      "django/db/models/sql/compiler.py",
      "SQLCompiler.get_related_selections.local_setter_noop"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 247.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖部分目标",
    "coverage": {
      "search_received": [],
      "seeds": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.get_related_selections"
        ]
      ],
      "causal_received": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.get_related_selections"
        ]
      ],
      "final": [
        [
          "django/db/models/sql/compiler.py",
          "SQLCompiler.get_related_selections"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 18,
      "model_request": 18,
      "model_response": 18,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 5,
      "source_receipt": 1,
      "relevance_attempt": 1,
      "relevance_decisions": 1,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 12,
      "causal_parse": 12,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 0,
      "causal": 119
    },
    "predicted_function_count": 8,
    "seconds": 247.45960657298565
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 1,
    "generate_causal_graph": 12
  },
  "tokens": {
    "input": 137936,
    "output": 10842
  }
}
```

## 113. django__django-16527

项目：`django/django`；base commit：`bd366ca2aeffa869b7dbc0b0aa01caea75e6dc31`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/contrib/admin/templatetags/admin_modify.py",
    "django/tests/admin_views/tests.py"
  ],
  "found_modules": [
    "django/tests/admin_views/tests.py::SaveAsTests"
  ],
  "found_functions": [
    "django/django/contrib/admin/templatetags/admin_modify.py::submit_row",
    "django/tests/admin_views/tests.py::SaveAsTests.test_save_as_new_with_validation_errors",
    "django/tests/admin_views/tests.py::SaveAsTests.test_save_as_new_with_validation_errors_with_inlines",
    "django/tests/admin_views/tests.py::SaveAsTests.test_save_as_new_with_inlines_with_validation_errors"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/templatetags/admin_modify.py",
      "submit_row"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/templatetags/admin_modify.py",
      "submit_row"
    ],
    [
      "tests/admin_views/tests.py",
      "SaveAsTests.test_save_as_new_with_inlines_with_validation_errors"
    ],
    [
      "tests/admin_views/tests.py",
      "SaveAsTests.test_save_as_new_with_validation_errors"
    ],
    [
      "tests/admin_views/tests.py",
      "SaveAsTests.test_save_as_new_with_validation_errors_with_inlines"
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
      "django/contrib/admin/templatetags/admin_modify.py",
      "submit_row"
    ]
  ],
  "false_positive": [
    [
      "tests/admin_views/tests.py",
      "SaveAsTests.test_save_as_new_with_inlines_with_validation_errors"
    ],
    [
      "tests/admin_views/tests.py",
      "SaveAsTests.test_save_as_new_with_validation_errors"
    ],
    [
      "tests/admin_views/tests.py",
      "SaveAsTests.test_save_as_new_with_validation_errors_with_inlines"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 159.5 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/contrib/admin/templatetags/admin_modify.py",
          "submit_row"
        ]
      ],
      "seeds": [
        [
          "django/contrib/admin/templatetags/admin_modify.py",
          "submit_row"
        ]
      ],
      "causal_received": [
        [
          "django/contrib/admin/templatetags/admin_modify.py",
          "submit_row"
        ]
      ],
      "final": [
        [
          "django/contrib/admin/templatetags/admin_modify.py",
          "submit_row"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 3,
      "search_history_compaction": 3,
      "request_preflight": 9,
      "model_request": 9,
      "model_response": 9,
      "search_query": 2,
      "search_matches": 2,
      "search_result": 2,
      "search_page_summary": 2,
      "seed_locations": 1,
      "causal_context": 6,
      "causal_parse": 6,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 0,
      "causal": 19
    },
    "predicted_function_count": 4,
    "seconds": 159.53285809699446
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 3,
    "generate_causal_graph": 6
  },
  "tokens": {
    "input": 20425,
    "output": 2050
  }
}
```

## 114. django__django-16595

项目：`django/django`；base commit：`f9fe062de5fc0896d6bbbf3f260b5c44473b3c77`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 25.00% | 100.00% | 40.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/db/migrations/operations/fields.py"
  ],
  "found_modules": [
    "django/django/db/migrations/operations/fields.py::FieldOperation",
    "django/django/db/migrations/operations/fields.py::AddField",
    "django/django/db/migrations/operations/fields.py::AlterField"
  ],
  "found_functions": [
    "django/django/db/migrations/operations/fields.py::FieldOperation.is_same_model_operation",
    "django/django/db/migrations/operations/fields.py::FieldOperation.is_same_field_operation",
    "django/django/db/migrations/operations/fields.py::AddField.reduce",
    "django/django/db/migrations/operations/fields.py::AlterField.reduce"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/operations/fields.py",
      "AlterField.reduce"
    ]
  ],
  "predictions": [
    [
      "django/db/migrations/operations/fields.py",
      "AddField.reduce"
    ],
    [
      "django/db/migrations/operations/fields.py",
      "AlterField.reduce"
    ],
    [
      "django/db/migrations/operations/fields.py",
      "FieldOperation.is_same_field_operation"
    ],
    [
      "django/db/migrations/operations/fields.py",
      "FieldOperation.is_same_model_operation"
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
      "django/db/migrations/operations/fields.py",
      "AlterField.reduce"
    ]
  ],
  "false_positive": [
    [
      "django/db/migrations/operations/fields.py",
      "AddField.reduce"
    ],
    [
      "django/db/migrations/operations/fields.py",
      "FieldOperation.is_same_field_operation"
    ],
    [
      "django/db/migrations/operations/fields.py",
      "FieldOperation.is_same_model_operation"
    ]
  ],
  "missed_targets": []
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 115.2 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/db/migrations/operations/fields.py",
          "AlterField.reduce"
        ]
      ],
      "seeds": [
        [
          "django/db/migrations/operations/fields.py",
          "AlterField.reduce"
        ]
      ],
      "causal_received": [
        [
          "django/db/migrations/operations/fields.py",
          "AlterField.reduce"
        ]
      ],
      "final": [
        [
          "django/db/migrations/operations/fields.py",
          "AlterField.reduce"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 5,
      "search_history_compaction": 5,
      "request_preflight": 17,
      "model_request": 17,
      "model_response": 17,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 7,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 7,
      "causal_parse": 7,
      "run_end": 1
    },
    "duplicate_code_associations": 0,
    "source_function_counts_by_role": {
      "main_search": 2,
      "relevance": 11,
      "causal": 20
    },
    "predicted_function_count": 4,
    "seconds": 115.17480447981507
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 7
  },
  "tokens": {
    "input": 36197,
    "output": 3533
  }
}
```

## 115. django__django-16816

项目：`django/django`；base commit：`191f6a9a4586b5e5f79f4f42f190e7ad4bbacc84`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

原始定位：

```json
{
  "found_files": [
    "django/tests/gis_tests/geoadmin/models.py",
    "django/django/contrib/admin/checks.py",
    "django/tests/str/models.py",
    "django/django/contrib/admin/utils.py",
    "django/django/contrib/admin/templatetags/admin_list.py",
    "django/django/core/exceptions.py"
  ],
  "found_modules": [
    "django/django/core/exceptions.py::FieldDoesNotExist"
  ],
  "found_functions": [
    "django/django/contrib/admin/utils.py::label_for_field",
    "django/django/contrib/admin/templatetags/admin_list.py::items_for_result",
    "django/django/contrib/admin/utils.py::_get_non_gfk_field",
    "django/django/contrib/admin/templatetags/admin_list.py::result_headers",
    "django/django/contrib/admin/utils.py::lookup_field",
    "django/django/contrib/admin/utils.py::help_text_for_field",
    "django/django/contrib/admin/utils.py::lookup_spawns_duplicates"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/contrib/admin/checks.py",
      "ModelAdminChecks._check_list_display_item"
    ]
  ],
  "predictions": [
    [
      "django/contrib/admin/templatetags/admin_list.py",
      "items_for_result"
    ],
    [
      "django/contrib/admin/templatetags/admin_list.py",
      "result_headers"
    ],
    [
      "django/contrib/admin/utils.py",
      "_get_non_gfk_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "help_text_for_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "label_for_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_spawns_duplicates"
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
      "django/contrib/admin/templatetags/admin_list.py",
      "items_for_result"
    ],
    [
      "django/contrib/admin/templatetags/admin_list.py",
      "result_headers"
    ],
    [
      "django/contrib/admin/utils.py",
      "_get_non_gfk_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "help_text_for_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "label_for_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_field"
    ],
    [
      "django/contrib/admin/utils.py",
      "lookup_spawns_duplicates"
    ]
  ],
  "missed_targets": [
    [
      "django/contrib/admin/checks.py",
      "ModelAdminChecks._check_list_display_item"
    ]
  ]
}
```

搜索终止：`search_round_limit`；因果终止：`legacy_causal_stop`；耗时 255.1 秒。

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
      "request_preflight": 21,
      "model_request": 21,
      "model_response": 21,
      "search_query": 5,
      "search_matches": 5,
      "search_result": 8,
      "source_receipt": 5,
      "relevance_attempt": 5,
      "relevance_decisions": 5,
      "search_page_summary": 5,
      "seed_locations": 1,
      "causal_context": 11,
      "causal_parse": 11,
      "run_end": 1
    },
    "duplicate_code_associations": 3,
    "source_function_counts_by_role": {
      "main_search": 4,
      "relevance": 0,
      "causal": 51
    },
    "predicted_function_count": 7,
    "seconds": 255.11952367983758
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 0
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 5,
    "relevance_json": 5,
    "generate_causal_graph": 11
  },
  "tokens": {
    "input": 186735,
    "output": 6080
  }
}
```

## 116. django__django-16820

项目：`django/django`；base commit：`c61219a7ae051d2baab53f041e00592011fc550c`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/operations/models.py",
      "CreateModel.reduce"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/migrations/operations/models.py",
      "CreateModel.reduce"
    ]
  ]
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 117. django__django-16873

项目：`django/django`；base commit：`fce90950bef348803fa7cc3e6bc65f4bce429b82`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 100.00% | 100.00% | 100.00% | 命中 |

原始定位：

```json
{
  "found_files": [
    "django/django/template/defaultfilters.py"
  ],
  "found_modules": [],
  "found_functions": [
    "django/django/template/defaultfilters.py::join"
  ]
}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/template/defaultfilters.py",
      "join"
    ]
  ],
  "predictions": [
    [
      "django/template/defaultfilters.py",
      "join"
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
      "django/template/defaultfilters.py",
      "join"
    ]
  ],
  "false_positive": [],
  "missed_targets": []
}
```

搜索终止：`model_finish`；因果终止：`legacy_causal_stop`；耗时 140.7 秒。

阶段定位与源码审计：

```json
{
  "pipeline": {
    "reason": "最终覆盖全部目标",
    "coverage": {
      "search_received": [
        [
          "django/template/defaultfilters.py",
          "join"
        ]
      ],
      "seeds": [
        [
          "django/template/defaultfilters.py",
          "join"
        ]
      ],
      "causal_received": [
        [
          "django/template/defaultfilters.py",
          "join"
        ]
      ],
      "final": [
        [
          "django/template/defaultfilters.py",
          "join"
        ]
      ]
    },
    "search_unprocessed_matches": 0,
    "event_counts": {
      "run_start": 1,
      "search_round": 2,
      "search_history_compaction": 2,
      "request_preflight": 6,
      "model_request": 6,
      "model_response": 6,
      "search_query": 1,
      "search_matches": 1,
      "search_result": 1,
      "search_page_summary": 1,
      "seed_locations": 1,
      "causal_context": 4,
      "causal_parse": 4,
      "run_end": 1
    },
    "duplicate_code_associations": 2,
    "source_function_counts_by_role": {
      "main_search": 3,
      "relevance": 0,
      "causal": 29
    },
    "predicted_function_count": 1,
    "seconds": 140.70985811017454
  },
  "legacy_parser_binding_losses": {
    "responses_with_multiple_graph_headers": 1
  },
  "unknown_relevance": 0,
  "functions_without_source_receipt": [],
  "calls_by_role": {
    "search_action": 2,
    "generate_causal_graph": 4
  },
  "tokens": {
    "input": 37896,
    "output": 1850
  }
}
```

## 118. django__django-16910

项目：`django/django`；base commit：`4142739af1cda53581af4169dbe16d6cd5e26948`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/sql/query.py",
      "Query._get_only_select_mask"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/models/sql/query.py",
      "Query._get_only_select_mask"
    ]
  ]
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 119. django__django-17051

项目：`django/django`；base commit：`b7a17b0ea0a2061bae752a3a2292007d41825814`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/models/query.py",
      "QuerySet._batched_insert"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/models/query.py",
      "QuerySet._batched_insert"
    ]
  ]
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 120. django__django-17087

项目：`django/django`；base commit：`4a72da71001f154ea60906a2f74898d32b7322a7`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "django/db/migrations/serializer.py",
      "FunctionTypeSerializer.serialize"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "django/db/migrations/serializer.py",
      "FunctionTypeSerializer.serialize"
    ]
  ]
}
```

该题没有最终结果。预算不足中断，原始调用证据已保留。

## 121. matplotlib__matplotlib-18869

项目：`matplotlib/matplotlib`；base commit：`b7d05919865fc0c37a0164cf467d5d5513bd0ede`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/__init__.py",
      "__getattr__"
    ],
    [
      "lib/matplotlib/__init__.py",
      "_get_version"
    ],
    [
      "lib/matplotlib/__init__.py",
      "_parse_to_version_info"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/__init__.py",
      "__getattr__"
    ],
    [
      "lib/matplotlib/__init__.py",
      "_get_version"
    ],
    [
      "lib/matplotlib/__init__.py",
      "_parse_to_version_info"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 122. matplotlib__matplotlib-22711

项目：`matplotlib/matplotlib`；base commit：`f670fe78795b18eb1118707721852209cd77ad51`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 33.33% | 25.00% | 命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/widgets.py",
      "RangeSlider._update"
    ],
    [
      "lib/matplotlib/widgets.py",
      "RangeSlider._update_val_from_pos"
    ],
    [
      "lib/matplotlib/widgets.py",
      "RangeSlider.set_val"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/widgets.py",
      "RangeSlider._update"
    ],
    [
      "lib/matplotlib/widgets.py",
      "RangeSlider._update_val_from_pos"
    ],
    [
      "lib/matplotlib/widgets.py",
      "RangeSlider.set_val"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 123. matplotlib__matplotlib-22835

项目：`matplotlib/matplotlib`；base commit：`c33557d120eefe3148ebfcf2e758ff2357966000`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/artist.py",
      "Artist.format_cursor_data"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/artist.py",
      "Artist.format_cursor_data"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 124. matplotlib__matplotlib-23299

项目：`matplotlib/matplotlib`；base commit：`3eadeacc06c9f2ddcdac6ae39819faa9fbee9e39`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/__init__.py",
      "rc_context"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/__init__.py",
      "rc_context"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 125. matplotlib__matplotlib-23314

项目：`matplotlib/matplotlib`；base commit：`97fc1154992f64cfb2f86321155a7404efeb2d8a`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/mpl_toolkits/mplot3d/axes3d.py",
      "Axes3D.draw"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/mpl_toolkits/mplot3d/axes3d.py",
      "Axes3D.draw"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 126. matplotlib__matplotlib-23476

项目：`matplotlib/matplotlib`；base commit：`33a0599711d26dc2b79f851c6daed4947df7c167`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/figure.py",
      "Figure.__getstate__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/figure.py",
      "Figure.__getstate__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 127. matplotlib__matplotlib-23562

项目：`matplotlib/matplotlib`；base commit：`29a86636a9c45ab5ac4d80ac76eaee497f460dce`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/mpl_toolkits/mplot3d/art3d.py",
      "Poly3DCollection.get_edgecolor"
    ],
    [
      "lib/mpl_toolkits/mplot3d/art3d.py",
      "Poly3DCollection.get_facecolor"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/mpl_toolkits/mplot3d/art3d.py",
      "Poly3DCollection.get_edgecolor"
    ],
    [
      "lib/mpl_toolkits/mplot3d/art3d.py",
      "Poly3DCollection.get_facecolor"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 128. matplotlib__matplotlib-23563

项目：`matplotlib/matplotlib`；base commit：`149a0398b391cfc4eddb5e659f50b3c66f32ea65`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/mpl_toolkits/mplot3d/art3d.py",
      "Line3D.set_3d_properties"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/mpl_toolkits/mplot3d/art3d.py",
      "Line3D.set_3d_properties"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 129. matplotlib__matplotlib-23913

项目：`matplotlib/matplotlib`；base commit：`5c4595267ccd3daf78f5fd05693b7ecbcd575c1e`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/legend.py",
      "Legend.__init__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/legend.py",
      "Legend.__init__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 130. matplotlib__matplotlib-23964

项目：`matplotlib/matplotlib`；base commit：`269c0b94b4fcf8b1135011c1556eac29dc09de15`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/backends/backend_ps.py",
      "RendererPS.draw_text"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/backends/backend_ps.py",
      "RendererPS.draw_text"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 131. matplotlib__matplotlib-23987

项目：`matplotlib/matplotlib`；base commit：`e98d8d085e8f53ec0467422b326f7738a2dd695e`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/figure.py",
      "Figure.__init__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/figure.py",
      "Figure.__init__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 132. matplotlib__matplotlib-24149

项目：`matplotlib/matplotlib`；base commit：`af39f1edffcd828f05cfdd04f2e59506bb4a27bc`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/axes/_axes.py",
      "Axes._convert_dx"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/axes/_axes.py",
      "Axes._convert_dx"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 133. matplotlib__matplotlib-24265

项目：`matplotlib/matplotlib`；base commit：`e148998d9bed9d1b53a91587ad48f9bb43c7737f`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/style/core.py",
      "_StyleLibrary.__getitem__"
    ],
    [
      "lib/matplotlib/style/core.py",
      "reload_library"
    ],
    [
      "lib/matplotlib/style/core.py",
      "use.fix_style"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/style/core.py",
      "_StyleLibrary.__getitem__"
    ],
    [
      "lib/matplotlib/style/core.py",
      "reload_library"
    ],
    [
      "lib/matplotlib/style/core.py",
      "use.fix_style"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 134. matplotlib__matplotlib-24334

项目：`matplotlib/matplotlib`；base commit：`332937997d03e0c173be6d9fc1841e9186e857df`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/axis.py",
      "Axis.set_ticks"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/axis.py",
      "Axis.set_ticks"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 135. matplotlib__matplotlib-24970

项目：`matplotlib/matplotlib`；base commit：`a3011dfd1aaa2487cce8aa7369475533133ef777`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/colors.py",
      "Colormap.__call__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/colors.py",
      "Colormap.__call__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 136. matplotlib__matplotlib-25079

项目：`matplotlib/matplotlib`；base commit：`66f7956984cbfc3647e867c6e5fde889a89c64ef`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/colors.py",
      "Normalize.autoscale"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/colors.py",
      "Normalize.autoscale"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 137. matplotlib__matplotlib-25311

项目：`matplotlib/matplotlib`；base commit：`430fb1db88843300fb4baae3edc499bbfe073b0c`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.__init__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.__init__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 138. matplotlib__matplotlib-25332

项目：`matplotlib/matplotlib`；base commit：`66ba515e671638971bd11a34cff12c107a437e0b`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/cbook.py",
      "CallbackRegistry.__getstate__"
    ],
    [
      "lib/matplotlib/cbook.py",
      "CallbackRegistry.__setstate__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/cbook.py",
      "CallbackRegistry.__getstate__"
    ],
    [
      "lib/matplotlib/cbook.py",
      "CallbackRegistry.__setstate__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 139. matplotlib__matplotlib-25433

项目：`matplotlib/matplotlib`；base commit：`7eafdd8af3c523c1c77b027d378fb337dd489f18`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/figure.py",
      "FigureBase.delaxes"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/figure.py",
      "FigureBase.delaxes"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 140. matplotlib__matplotlib-25442

项目：`matplotlib/matplotlib`；base commit：`73394f2b11321e03a5df199ec0196f27a728b0b0`。

状态：missing；函数真值：4。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 40.00% | 50.00% | 44.44% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.__init__"
    ],
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.disconnect"
    ],
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.on_pick"
    ],
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.on_release"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.__init__"
    ],
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.disconnect"
    ],
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.on_pick"
    ],
    [
      "lib/matplotlib/offsetbox.py",
      "DraggableBase.on_release"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 141. matplotlib__matplotlib-25498

项目：`matplotlib/matplotlib`；base commit：`78bf53caacbb5ce0dc7aa73f07a74c99f1ed919b`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/colorbar.py",
      "Colorbar.__init__"
    ],
    [
      "lib/matplotlib/colorbar.py",
      "Colorbar._process_values"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/colorbar.py",
      "Colorbar.__init__"
    ],
    [
      "lib/matplotlib/colorbar.py",
      "Colorbar._process_values"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 142. matplotlib__matplotlib-26011

项目：`matplotlib/matplotlib`；base commit：`00afcc0c6d4d2e4390338127f05b8f4fdb4e7087`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/matplotlib/axis.py",
      "Axis._set_lim"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/matplotlib/axis.py",
      "Axis._set_lim"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 143. matplotlib__matplotlib-26020

项目：`matplotlib/matplotlib`；base commit：`f6a781f77f5ddf1204c60ca7c544809407d4a807`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "lib/mpl_toolkits/axes_grid1/axes_grid.py",
      "_tick_only"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "lib/mpl_toolkits/axes_grid1/axes_grid.py",
      "_tick_only"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 144. mwaskom__seaborn-2848

项目：`mwaskom/seaborn`；base commit：`94621cef29f80282436d73e8d2c0aa76dab81273`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "seaborn/_oldcore.py",
      "HueMapping._lookup_single"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "seaborn/_oldcore.py",
      "HueMapping._lookup_single"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 145. mwaskom__seaborn-3010

项目：`mwaskom/seaborn`；base commit：`0f5a013e2cf43562deec3b879458e59a73853813`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "seaborn/_stats/regression.py",
      "PolyFit.__call__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "seaborn/_stats/regression.py",
      "PolyFit.__call__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 146. mwaskom__seaborn-3190

项目：`mwaskom/seaborn`；base commit：`4a9e54962a29c12a8b103d75f838e0e795a6974d`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 20.00% | 100.00% | 33.33% | 命中 |

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

## 147. mwaskom__seaborn-3407

项目：`mwaskom/seaborn`；base commit：`515286e02be3e4c0ff2ef4addb34a53c4a676ee4`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "seaborn/axisgrid.py",
      "PairGrid.map_diag"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "seaborn/axisgrid.py",
      "PairGrid.map_diag"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 148. pallets__flask-4045

项目：`pallets/flask`；base commit：`d8c37f43724cd9fb0870f77877b7c4c7e38a19e0`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/flask/blueprints.py",
      "Blueprint.__init__"
    ],
    [
      "src/flask/blueprints.py",
      "Blueprint.add_url_rule"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/flask/blueprints.py",
      "Blueprint.__init__"
    ],
    [
      "src/flask/blueprints.py",
      "Blueprint.add_url_rule"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 149. pallets__flask-4992

项目：`pallets/flask`；base commit：`4c288bc97ea371817199908d0d9b12de9dae327e`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/flask/config.py",
      "Config.from_file"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/flask/config.py",
      "Config.from_file"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 150. pallets__flask-5063

项目：`pallets/flask`；base commit：`182ce3dd15dfa3537391c3efaf9c3ff407d134d4`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/flask/cli.py",
      "routes_command"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/flask/cli.py",
      "routes_command"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 151. psf__requests-1963

项目：`psf/requests`；base commit：`110048f9837f8441ea536804115e80b69f400277`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "requests/sessions.py",
      "SessionRedirectMixin.resolve_redirects"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "requests/sessions.py",
      "SessionRedirectMixin.resolve_redirects"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 152. psf__requests-2148

项目：`psf/requests`；base commit：`fe693c492242ae532211e0c173324f09ca8cf227`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "requests/models.py",
      "Response.iter_content.generate"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "requests/models.py",
      "Response.iter_content.generate"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 153. psf__requests-2317

项目：`psf/requests`；base commit：`091991be0da19de9108dbe5e3752917fea3d7fdc`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "requests/sessions.py",
      "Session.request"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "requests/sessions.py",
      "Session.request"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 154. psf__requests-2674

项目：`psf/requests`；base commit：`0be38a0c37c59c4b66ce908731da15b401655113`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "requests/adapters.py",
      "HTTPAdapter.send"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "requests/adapters.py",
      "HTTPAdapter.send"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 155. psf__requests-3362

项目：`psf/requests`；base commit：`36453b95b13079296776d11b09cab2567ea3e703`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "requests/utils.py",
      "stream_decode_response_unicode"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "requests/utils.py",
      "stream_decode_response_unicode"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 156. psf__requests-863

项目：`psf/requests`；base commit：`a0df2cbb10419037d11d04352b3175405ab52941`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "requests/models.py",
      "Request.register_hook"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "requests/models.py",
      "Request.register_hook"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 157. pydata__xarray-3364

项目：`pydata/xarray`；base commit：`863e49066ca4d61c9adfe62aca3bf21b90e1af8c`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 10.00% | 100.00% | 18.18% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "xarray/core/concat.py",
      "_dataset_concat"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "xarray/core/concat.py",
      "_dataset_concat"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 158. pydata__xarray-4094

项目：`pydata/xarray`；base commit：`a64cf2d5476e7bbda099b34c40b7be1880dbd39a`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "xarray/core/dataarray.py",
      "DataArray.to_unstacked_dataset"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "xarray/core/dataarray.py",
      "DataArray.to_unstacked_dataset"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 159. pydata__xarray-4248

项目：`pydata/xarray`；base commit：`98dc1f4ea18738492e074e9e51ddfed5cd30ab94`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "xarray/core/formatting.py",
      "inline_variable_array_repr"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "xarray/core/formatting.py",
      "inline_variable_array_repr"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 160. pydata__xarray-4493

项目：`pydata/xarray`；base commit：`a5f53e203c52a7605d5db799864046471115d04f`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "xarray/core/variable.py",
      "as_variable"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "xarray/core/variable.py",
      "as_variable"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 161. pydata__xarray-5131

项目：`pydata/xarray`；base commit：`e56905889c836c736152b11a7e6117a229715975`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "xarray/core/groupby.py",
      "GroupBy.__repr__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "xarray/core/groupby.py",
      "GroupBy.__repr__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 162. pylint-dev__pylint-5859

项目：`pylint-dev/pylint`；base commit：`182cc539b8154c0710fcea7e522267e42eba8899`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "pylint/checkers/misc.py",
      "EncodingChecker.open"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "pylint/checkers/misc.py",
      "EncodingChecker.open"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 163. pylint-dev__pylint-6506

项目：`pylint-dev/pylint`；base commit：`0a4204fd7555cfedd43f43017c94d24ef48244a5`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "pylint/config/config_initialization.py",
      "_config_initialization"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "pylint/config/config_initialization.py",
      "_config_initialization"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 164. pylint-dev__pylint-7080

项目：`pylint-dev/pylint`；base commit：`3c5eca2ded3dd2b59ebaf23eb289453b5d2930f0`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "pylint/lint/expand_modules.py",
      "_is_ignored_file"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "pylint/lint/expand_modules.py",
      "_is_ignored_file"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 165. pylint-dev__pylint-7114

项目：`pylint-dev/pylint`；base commit：`397c1703e8ae6349d33f7b99f45b2ccaf581e666`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "pylint/lint/expand_modules.py",
      "expand_modules"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "pylint/lint/expand_modules.py",
      "expand_modules"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 166. pylint-dev__pylint-7228

项目：`pylint-dev/pylint`；base commit：`d597f252915ddcaaa15ccdfcb35670152cb83587`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "pylint/config/argument.py",
      "_regex_transformer"
    ],
    [
      "pylint/config/argument.py",
      "_regexp_csv_transfomer"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "pylint/config/argument.py",
      "_regex_transformer"
    ],
    [
      "pylint/config/argument.py",
      "_regexp_csv_transfomer"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 167. pylint-dev__pylint-7993

项目：`pylint-dev/pylint`；base commit：`e90702074e68e20dc8e5df5013ee3ecf22139c3e`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "pylint/reporters/text.py",
      "TextReporter.on_set_current_module"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "pylint/reporters/text.py",
      "TextReporter.on_set_current_module"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 168. pytest-dev__pytest-11143

项目：`pytest-dev/pytest`；base commit：`6995257cf470d2143ad1683824962de4071c0eb7`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter.run"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter.run"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 169. pytest-dev__pytest-11148

项目：`pytest-dev/pytest`；base commit：`2f7415cfbc4b6ca62f9013f1abd27136f46b9653`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/pathlib.py",
      "import_path"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/pathlib.py",
      "import_path"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 170. pytest-dev__pytest-5103

项目：`pytest-dev/pytest`；base commit：`10ca84ffc56c2dd2d9dc4bd71b7b898e083500cd`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter._visit_all"
    ],
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter.visit_Call_35"
    ],
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter.visit_Call_legacy"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter._visit_all"
    ],
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter.visit_Call_35"
    ],
    [
      "src/_pytest/assertion/rewrite.py",
      "AssertionRewriter.visit_Call_legacy"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 171. pytest-dev__pytest-5221

项目：`pytest-dev/pytest`；base commit：`4a2fdce62b73944030cff9b3e52862868ca9584d`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/python.py",
      "_showfixtures_main"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/python.py",
      "_showfixtures_main"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 172. pytest-dev__pytest-5227

项目：`pytest-dev/pytest`；base commit：`2051e30b9b596e944524ccb787ed20f9f5be93e3`。

状态：missing；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": []
}
```

该题没有最终结果。未运行或尚未完成。

## 173. pytest-dev__pytest-5413

项目：`pytest-dev/pytest`；base commit：`450d2646233c670654744d3d24330b69895bb9d2`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/_code/code.py",
      "ExceptionInfo.__str__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/_code/code.py",
      "ExceptionInfo.__str__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 174. pytest-dev__pytest-5495

项目：`pytest-dev/pytest`；base commit：`1aefb24b37c30fba8fd79a744829ca16e252f340`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/assertion/util.py",
      "_compare_eq_sequence"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/assertion/util.py",
      "_compare_eq_sequence"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 175. pytest-dev__pytest-5692

项目：`pytest-dev/pytest`；base commit：`29e336bd9bf87eaef8e2683196ee1975f1ad4088`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/junitxml.py",
      "LogXML.pytest_sessionfinish"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/junitxml.py",
      "LogXML.pytest_sessionfinish"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 176. pytest-dev__pytest-6116

项目：`pytest-dev/pytest`；base commit：`e670ff76cbad80108bde9bab616b66771b8653cf`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/main.py",
      "pytest_addoption"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/main.py",
      "pytest_addoption"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 177. pytest-dev__pytest-7168

项目：`pytest-dev/pytest`；base commit：`4787fd64a4ca0dba5528b5651bddd254102fe9f3`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/_io/saferepr.py",
      "_format_repr_exception"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/_io/saferepr.py",
      "_format_repr_exception"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 178. pytest-dev__pytest-7220

项目：`pytest-dev/pytest`；base commit：`56bf819c2f4eaf8b36bd8c42c06bb59d5a3bfc0f`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/nodes.py",
      "Node._repr_failure_py"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/nodes.py",
      "Node._repr_failure_py"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 179. pytest-dev__pytest-7373

项目：`pytest-dev/pytest`；base commit：`7b77fc086aab8b3a8ebc890200371884555eea1e`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 40.00% | 66.67% | 50.00% | 命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 18.18% | 66.67% | 28.57% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/mark/evaluate.py",
      "MarkEvaluator._istrue"
    ],
    [
      "src/_pytest/mark/evaluate.py",
      "cached_eval"
    ],
    [
      "src/_pytest/mark/evaluate.py",
      "compiled_eval"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/mark/evaluate.py",
      "MarkEvaluator._istrue"
    ],
    [
      "src/_pytest/mark/evaluate.py",
      "cached_eval"
    ],
    [
      "src/_pytest/mark/evaluate.py",
      "compiled_eval"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 180. pytest-dev__pytest-7432

项目：`pytest-dev/pytest`；base commit：`e6e300e729dd33956e5448d8be9a0b1540b4e53a`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/skipping.py",
      "pytest_runtest_makereport"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/skipping.py",
      "pytest_runtest_makereport"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 181. pytest-dev__pytest-7490

项目：`pytest-dev/pytest`；base commit：`7f7a36478abe7dd1fa993b115d22606aa0e35e88`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/skipping.py",
      "pytest_runtest_call"
    ],
    [
      "src/_pytest/skipping.py",
      "pytest_runtest_setup"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/skipping.py",
      "pytest_runtest_call"
    ],
    [
      "src/_pytest/skipping.py",
      "pytest_runtest_setup"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 182. pytest-dev__pytest-8365

项目：`pytest-dev/pytest`；base commit：`4964b468c83c06971eb743fbc57cc404f760c573`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/tmpdir.py",
      "TempPathFactory.getbasetemp"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/tmpdir.py",
      "TempPathFactory.getbasetemp"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 183. pytest-dev__pytest-8906

项目：`pytest-dev/pytest`；base commit：`69356d20cfee9a81972dcbf93d8caf9eabe113e8`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/python.py",
      "Module._importtestmodule"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/python.py",
      "Module._importtestmodule"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 184. pytest-dev__pytest-9359

项目：`pytest-dev/pytest`；base commit：`e2ee3144ed6e241dea8d96215fcdca18b3892551`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "src/_pytest/_code/source.py",
      "get_statement_startend2"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "src/_pytest/_code/source.py",
      "get_statement_startend2"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 185. scikit-learn__scikit-learn-10297

项目：`scikit-learn/scikit-learn`；base commit：`b90661d6a46aa3619d3eec94d5281f5888add501`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/linear_model/ridge.py",
      "RidgeClassifierCV.__init__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/linear_model/ridge.py",
      "RidgeClassifierCV.__init__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 186. scikit-learn__scikit-learn-10508

项目：`scikit-learn/scikit-learn`；base commit：`c753b77ac49e72ebc0fe5e3c2369fe628f975017`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/preprocessing/label.py",
      "LabelEncoder.inverse_transform"
    ],
    [
      "sklearn/preprocessing/label.py",
      "LabelEncoder.transform"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/preprocessing/label.py",
      "LabelEncoder.inverse_transform"
    ],
    [
      "sklearn/preprocessing/label.py",
      "LabelEncoder.transform"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 187. scikit-learn__scikit-learn-10949

项目：`scikit-learn/scikit-learn`；base commit：`3b5abf76597ce6aff76192869f92647c1b5259e7`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/utils/validation.py",
      "check_array"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/utils/validation.py",
      "check_array"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 188. scikit-learn__scikit-learn-11040

项目：`scikit-learn/scikit-learn`；base commit：`96a02f3934952d486589dddd3f00b40d5a5ab5f2`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/neighbors/base.py",
      "KNeighborsMixin.kneighbors"
    ],
    [
      "sklearn/neighbors/base.py",
      "NeighborsBase._fit"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/neighbors/base.py",
      "KNeighborsMixin.kneighbors"
    ],
    [
      "sklearn/neighbors/base.py",
      "NeighborsBase._fit"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 189. scikit-learn__scikit-learn-11281

项目：`scikit-learn/scikit-learn`；base commit：`4143356c3c51831300789e4fdf795d83716dbab6`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/mixture/base.py",
      "BaseMixture.fit"
    ],
    [
      "sklearn/mixture/base.py",
      "BaseMixture.fit_predict"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/mixture/base.py",
      "BaseMixture.fit"
    ],
    [
      "sklearn/mixture/base.py",
      "BaseMixture.fit_predict"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 190. scikit-learn__scikit-learn-12471

项目：`scikit-learn/scikit-learn`；base commit：`02dc9ed680e7f53f1b0d410dcdd37341c7958eb1`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/preprocessing/_encoders.py",
      "_BaseEncoder._transform"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/preprocessing/_encoders.py",
      "_BaseEncoder._transform"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 191. scikit-learn__scikit-learn-13142

项目：`scikit-learn/scikit-learn`；base commit：`1c8668b0a021832386470ddf740d834e02c66f69`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/mixture/base.py",
      "BaseMixture.fit_predict"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/mixture/base.py",
      "BaseMixture.fit_predict"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 192. scikit-learn__scikit-learn-13241

项目：`scikit-learn/scikit-learn`；base commit：`f8b108d0c6f2f82b2dc4e32a6793f9d9ac9cf2f4`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/decomposition/kernel_pca.py",
      "KernelPCA._fit_transform"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/decomposition/kernel_pca.py",
      "KernelPCA._fit_transform"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 193. scikit-learn__scikit-learn-13439

项目：`scikit-learn/scikit-learn`；base commit：`a62775e99f2a5ea3d51db7160fad783f6cd8a4c5`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/pipeline.py",
      "Pipeline.__len__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/pipeline.py",
      "Pipeline.__len__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 194. scikit-learn__scikit-learn-13496

项目：`scikit-learn/scikit-learn`；base commit：`3aefc834dce72e850bff48689bea3c7dff5f3fad`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/ensemble/iforest.py",
      "IsolationForest.__init__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/ensemble/iforest.py",
      "IsolationForest.__init__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 195. scikit-learn__scikit-learn-13497

项目：`scikit-learn/scikit-learn`；base commit：`26f690961a52946dd2f53bf0fdd4264b2ae5be90`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/feature_selection/mutual_info_.py",
      "_estimate_mi"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/feature_selection/mutual_info_.py",
      "_estimate_mi"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 196. scikit-learn__scikit-learn-13584

项目：`scikit-learn/scikit-learn`；base commit：`0e3c1879b06d839171b7d0a607d71bbb19a966a9`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/utils/_pprint.py",
      "_changed_params"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/utils/_pprint.py",
      "_changed_params"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 197. scikit-learn__scikit-learn-13779

项目：`scikit-learn/scikit-learn`；base commit：`b34751b7ed02b2cfcc36037fb729d4360480a299`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/ensemble/voting.py",
      "_BaseVoting.fit"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/ensemble/voting.py",
      "_BaseVoting.fit"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 198. scikit-learn__scikit-learn-14087

项目：`scikit-learn/scikit-learn`；base commit：`a5743ed36fbd3fbc8e351bdab16561fbfca7dfa1`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/linear_model/logistic.py",
      "LogisticRegressionCV.fit"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/linear_model/logistic.py",
      "LogisticRegressionCV.fit"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 199. scikit-learn__scikit-learn-14092

项目：`scikit-learn/scikit-learn`；base commit：`df7dd8391148a873d157328a4f0328528a0c4ed9`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/neighbors/nca.py",
      "NeighborhoodComponentsAnalysis._validate_params"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/neighbors/nca.py",
      "NeighborhoodComponentsAnalysis._validate_params"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 200. scikit-learn__scikit-learn-14894

项目：`scikit-learn/scikit-learn`；base commit：`fdbaa58acbead5a254f2e6d597dc1ab3b947f4c6`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/svm/base.py",
      "BaseLibSVM._sparse_fit"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/svm/base.py",
      "BaseLibSVM._sparse_fit"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 201. scikit-learn__scikit-learn-14983

项目：`scikit-learn/scikit-learn`；base commit：`06632c0d185128a53c57ccc73b25b6408e90bb89`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/model_selection/_split.py",
      "_RepeatedSplits.__repr__"
    ],
    [
      "sklearn/model_selection/_split.py",
      "_build_repr"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/model_selection/_split.py",
      "_RepeatedSplits.__repr__"
    ],
    [
      "sklearn/model_selection/_split.py",
      "_build_repr"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 202. scikit-learn__scikit-learn-15512

项目：`scikit-learn/scikit-learn`；base commit：`b8a4da8baa1137f173e7035f104067c7d2ffde22`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/cluster/_affinity_propagation.py",
      "AffinityPropagation.predict"
    ],
    [
      "sklearn/cluster/_affinity_propagation.py",
      "affinity_propagation"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/cluster/_affinity_propagation.py",
      "AffinityPropagation.predict"
    ],
    [
      "sklearn/cluster/_affinity_propagation.py",
      "affinity_propagation"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 203. scikit-learn__scikit-learn-15535

项目：`scikit-learn/scikit-learn`；base commit：`70b0ddea992c01df1a41588fa9e2d130fb6b13f8`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/metrics/cluster/_supervised.py",
      "check_clusterings"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/metrics/cluster/_supervised.py",
      "check_clusterings"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 204. scikit-learn__scikit-learn-25500

项目：`scikit-learn/scikit-learn`；base commit：`4db04923a754b6a2defa1b172f55d492b85d165e`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/isotonic.py",
      "IsotonicRegression._transform"
    ],
    [
      "sklearn/isotonic.py",
      "IsotonicRegression.predict"
    ],
    [
      "sklearn/isotonic.py",
      "IsotonicRegression.transform"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/isotonic.py",
      "IsotonicRegression._transform"
    ],
    [
      "sklearn/isotonic.py",
      "IsotonicRegression.predict"
    ],
    [
      "sklearn/isotonic.py",
      "IsotonicRegression.transform"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 205. scikit-learn__scikit-learn-25570

项目：`scikit-learn/scikit-learn`；base commit：`cd25abee0ad0ac95225d4a9be8948eff69f49690`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 16.67% | 100.00% | 28.57% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/compose/_column_transformer.py",
      "ColumnTransformer._hstack"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/compose/_column_transformer.py",
      "ColumnTransformer._hstack"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 206. scikit-learn__scikit-learn-25638

项目：`scikit-learn/scikit-learn`；base commit：`6adb209acd63825affc884abcd85381f148fb1b0`。

状态：complete；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 50.00% | 50.00% | 50.00% | 命中 |

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

## 207. scikit-learn__scikit-learn-25747

项目：`scikit-learn/scikit-learn`；base commit：`2c867b8f822eb7a684f0d5c4359e4426e1c9cfe0`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sklearn/utils/_set_output.py",
      "_wrap_in_pandas_container"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sklearn/utils/_set_output.py",
      "_wrap_in_pandas_container"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 208. sphinx-doc__sphinx-10325

项目：`sphinx-doc/sphinx`；base commit：`7bdc11e87c7d86dcc2a087eccb7a7c129a473415`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "Documenter.filter_members.is_filtered_inherited_member"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "inherited_members_option"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "Documenter.filter_members.is_filtered_inherited_member"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "inherited_members_option"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 209. sphinx-doc__sphinx-10451

项目：`sphinx-doc/sphinx`；base commit：`195e911f1dab04b8ddeacbe04b7d214aaf81bb0b`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 100.00% | 50.00% | 66.67% | 命中 |
| CoSIL/off | 50.00% | 50.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autodoc/typehints.py",
      "augment_descriptions_with_types"
    ],
    [
      "sphinx/ext/autodoc/typehints.py",
      "modify_field_list"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autodoc/typehints.py",
      "augment_descriptions_with_types"
    ],
    [
      "sphinx/ext/autodoc/typehints.py",
      "modify_field_list"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 210. sphinx-doc__sphinx-11445

项目：`sphinx-doc/sphinx`；base commit：`71db08c05197545944949d5aa76cd340e7143627`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/util/rst.py",
      "prepend_prolog"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/util/rst.py",
      "prepend_prolog"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 211. sphinx-doc__sphinx-7686

项目：`sphinx-doc/sphinx`；base commit：`752d3285d250bbaf673cff25e83f03f247502021`。

状态：missing；函数真值：5。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 33.33% | 20.00% | 25.00% | 命中 |
| GraphLocator/Qwen | 33.33% | 20.00% | 25.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.__init__"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.get_object_type"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.is_skipped"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.scan"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "generate_autosummary_content"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.__init__"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.get_object_type"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.is_skipped"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "ModuleScanner.scan"
    ],
    [
      "sphinx/ext/autosummary/generate.py",
      "generate_autosummary_content"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 212. sphinx-doc__sphinx-7738

项目：`sphinx-doc/sphinx`；base commit：`c087d717f6ed183dd422359bf91210dc59689d63`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/napoleon/docstring.py",
      "GoogleDocstring._escape_args_and_kwargs"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/napoleon/docstring.py",
      "GoogleDocstring._escape_args_and_kwargs"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 213. sphinx-doc__sphinx-7975

项目：`sphinx-doc/sphinx`；base commit：`4ec6cbe341fd84468c448e20082c778043bbea4b`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/environment/adapters/indexentries.py",
      "IndexEntries.create_index"
    ],
    [
      "sphinx/environment/adapters/indexentries.py",
      "IndexEntries.create_index.keyfunc"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/environment/adapters/indexentries.py",
      "IndexEntries.create_index"
    ],
    [
      "sphinx/environment/adapters/indexentries.py",
      "IndexEntries.create_index.keyfunc"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 214. sphinx-doc__sphinx-8273

项目：`sphinx-doc/sphinx`；base commit：`88b81a06eb635a1596617f8971fa97a84c069e93`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/builders/manpage.py",
      "ManualPageBuilder.write"
    ],
    [
      "sphinx/builders/manpage.py",
      "setup"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/builders/manpage.py",
      "ManualPageBuilder.write"
    ],
    [
      "sphinx/builders/manpage.py",
      "setup"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 215. sphinx-doc__sphinx-8282

项目：`sphinx-doc/sphinx`；base commit：`2c2335bbb8af99fa132e1573bbf45dc91584d5a2`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "ClassDocumenter.format_signature"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "FunctionDocumenter.format_signature"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "MethodDocumenter.format_signature"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "ClassDocumenter.format_signature"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "FunctionDocumenter.format_signature"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "MethodDocumenter.format_signature"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 216. sphinx-doc__sphinx-8435

项目：`sphinx-doc/sphinx`；base commit：`5d8d6275a54f2c5fb72b82383b5712c22d337634`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "AttributeDocumenter.add_directive_header"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "DataDocumenter.add_directive_header"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "AttributeDocumenter.add_directive_header"
    ],
    [
      "sphinx/ext/autodoc/__init__.py",
      "DataDocumenter.add_directive_header"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 217. sphinx-doc__sphinx-8474

项目：`sphinx-doc/sphinx`；base commit：`3ea1ec84cc610f7a9f4f6b354e264565254923ff`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/domains/std.py",
      "StandardDomain._resolve_numref_xref"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/domains/std.py",
      "StandardDomain._resolve_numref_xref"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 218. sphinx-doc__sphinx-8506

项目：`sphinx-doc/sphinx`；base commit：`e4bd3bd3ddd42c6642ff779a4f7381f219655c2c`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/domains/std.py",
      "Cmdoption.handle_signature"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/domains/std.py",
      "Cmdoption.handle_signature"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 219. sphinx-doc__sphinx-8595

项目：`sphinx-doc/sphinx`；base commit：`b19bce971e82f2497d67fdacdeca8db08ae0ba56`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "ModuleDocumenter.get_object_members"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autodoc/__init__.py",
      "ModuleDocumenter.get_object_members"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 220. sphinx-doc__sphinx-8627

项目：`sphinx-doc/sphinx`；base commit：`332d80ba8433aea41c3709fa52737ede4405072b`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/util/typing.py",
      "restify"
    ],
    [
      "sphinx/util/typing.py",
      "stringify"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/util/typing.py",
      "restify"
    ],
    [
      "sphinx/util/typing.py",
      "stringify"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 221. sphinx-doc__sphinx-8713

项目：`sphinx-doc/sphinx`；base commit：`3ed7590ed411bd93b26098faab4f23619cdb2267`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/napoleon/docstring.py",
      "GoogleDocstring._parse_other_parameters_section"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/napoleon/docstring.py",
      "GoogleDocstring._parse_other_parameters_section"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 222. sphinx-doc__sphinx-8721

项目：`sphinx-doc/sphinx`；base commit：`82ef497a8c88f0f6e50d84520e7276bfbf65025d`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 50.00% | 100.00% | 66.67% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/viewcode.py",
      "collect_pages"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/viewcode.py",
      "collect_pages"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 223. sphinx-doc__sphinx-8801

项目：`sphinx-doc/sphinx`；base commit：`7ca279e33aebb60168d35e6be4ed059f4a68f2c1`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sphinx/ext/autodoc/importer.py",
      "get_class_members"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sphinx/ext/autodoc/importer.py",
      "get_class_members"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 224. sympy__sympy-11400

项目：`sympy/sympy`；base commit：`8dcb12a6cf500e8738d6729ab954a261758f49ca`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/ccode.py",
      "CCodePrinter._print_Relational"
    ],
    [
      "sympy/printing/ccode.py",
      "CCodePrinter._print_sinc"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/ccode.py",
      "CCodePrinter._print_Relational"
    ],
    [
      "sympy/printing/ccode.py",
      "CCodePrinter._print_sinc"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 225. sympy__sympy-11870

项目：`sympy/sympy`；base commit：`5c2e1f96a7ff562d4a778f4ca9ffc9c81557197e`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/functions/elementary/trigonometric.py",
      "sin._eval_rewrite_as_sinc"
    ],
    [
      "sympy/functions/elementary/trigonometric.py",
      "sinc._eval_rewrite_as_sin"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/functions/elementary/trigonometric.py",
      "sin._eval_rewrite_as_sinc"
    ],
    [
      "sympy/functions/elementary/trigonometric.py",
      "sinc._eval_rewrite_as_sin"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 226. sympy__sympy-11897

项目：`sympy/sympy`；base commit：`e2918c1205c47345eb73c9be68b14c0f15fdeb17`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._needs_mul_brackets"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._needs_mul_brackets"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 227. sympy__sympy-12171

项目：`sympy/sympy`；base commit：`ca6ef27272be31c9dc3753ede9232c39df9a75d8`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/mathematica.py",
      "MCodePrinter._print_Derivative"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/mathematica.py",
      "MCodePrinter._print_Derivative"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 228. sympy__sympy-12236

项目：`sympy/sympy`；base commit：`d60497958f6dea7f5e25bc41e9107a6a63694d01`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/polys/domains/polynomialring.py",
      "PolynomialRing.from_FractionField"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/polys/domains/polynomialring.py",
      "PolynomialRing.from_FractionField"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 229. sympy__sympy-12419

项目：`sympy/sympy`；base commit：`479939f8c65c8c2908bbedc959549a257a7c0b0b`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/expressions/matexpr.py",
      "Identity._entry"
    ],
    [
      "sympy/matrices/expressions/matexpr.py",
      "MatrixElement._eval_derivative"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/expressions/matexpr.py",
      "Identity._entry"
    ],
    [
      "sympy/matrices/expressions/matexpr.py",
      "MatrixElement._eval_derivative"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 230. sympy__sympy-12454

项目：`sympy/sympy`；base commit：`d3fcdb72bfcbb560eb45264ac1c03f359436edef`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/matrices.py",
      "MatrixProperties._eval_is_upper_hessenberg"
    ],
    [
      "sympy/matrices/matrices.py",
      "MatrixProperties.is_upper"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/matrices.py",
      "MatrixProperties._eval_is_upper_hessenberg"
    ],
    [
      "sympy/matrices/matrices.py",
      "MatrixProperties.is_upper"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 231. sympy__sympy-12481

项目：`sympy/sympy`；base commit：`c807dfe7569692cad24f02a08477b70c1679a4dd`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 16.67% | 100.00% | 28.57% | 命中 |

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

## 232. sympy__sympy-13031

项目：`sympy/sympy`；base commit：`2dfa7457f20ee187fbb09b5b6a1631da4458388c`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/sparse.py",
      "MutableSparseMatrix.col_join"
    ],
    [
      "sympy/matrices/sparse.py",
      "MutableSparseMatrix.row_join"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/sparse.py",
      "MutableSparseMatrix.col_join"
    ],
    [
      "sympy/matrices/sparse.py",
      "MutableSparseMatrix.row_join"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 233. sympy__sympy-13043

项目：`sympy/sympy`；base commit：`a3389a25ec84d36f5cf04a4f2562d820f131db64`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/integrals/intpoly.py",
      "decompose"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/integrals/intpoly.py",
      "decompose"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 234. sympy__sympy-13146

项目：`sympy/sympy`；base commit：`b678d8103e48fdb1af335dbf0080b3d5366f2d17`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/operations.py",
      "AssocOp._eval_evalf"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/operations.py",
      "AssocOp._eval_evalf"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 235. sympy__sympy-13177

项目：`sympy/sympy`；base commit：`662cfb818e865f580e18b59efbb3540c34232beb`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/mod.py",
      "Mod.eval.doit"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/mod.py",
      "Mod.eval.doit"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 236. sympy__sympy-13437

项目：`sympy/sympy`；base commit：`674afc619d7f5c519b6a5393a8b0532a131e57e0`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 14.29% | 100.00% | 25.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/functions/combinatorial/numbers.py",
      "bell.eval"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/functions/combinatorial/numbers.py",
      "bell.eval"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 237. sympy__sympy-13471

项目：`sympy/sympy`；base commit：`3546ac7ed78e1780c1a76929864bb33330055740`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/numbers.py",
      "Float.__new__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/numbers.py",
      "Float.__new__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 238. sympy__sympy-13480

项目：`sympy/sympy`；base commit：`f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/functions/elementary/hyperbolic.py",
      "coth.eval"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/functions/elementary/hyperbolic.py",
      "coth.eval"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 239. sympy__sympy-13647

项目：`sympy/sympy`；base commit：`67e3c956083d0128a621f65ee86a7dacd4f9f19f`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/common.py",
      "MatrixShaping._eval_col_insert.entry"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/common.py",
      "MatrixShaping._eval_col_insert.entry"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 240. sympy__sympy-13773

项目：`sympy/sympy`；base commit：`7121bdf1facdd90d05b6994b4c2e5b2865a4638a`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 50.00% | 50.00% | 50.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 50.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/common.py",
      "MatrixArithmetic.__matmul__"
    ],
    [
      "sympy/matrices/common.py",
      "MatrixArithmetic.__rmatmul__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/common.py",
      "MatrixArithmetic.__matmul__"
    ],
    [
      "sympy/matrices/common.py",
      "MatrixArithmetic.__rmatmul__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 241. sympy__sympy-13895

项目：`sympy/sympy`；base commit：`4da0b64558e9551a11a99bccc63557ba34f50c58`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/numbers.py",
      "Integer._eval_power"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/numbers.py",
      "Integer._eval_power"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 242. sympy__sympy-13915

项目：`sympy/sympy`；base commit：`5c1644ff85e15752f9f8721bc142bfbf975e7805`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/mul.py",
      "Mul.flatten"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/mul.py",
      "Mul.flatten"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 243. sympy__sympy-13971

项目：`sympy/sympy`；base commit：`84c125972ad535b2dfb245f8d311d347b45e5b8a`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_SeqFormula"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_SeqFormula"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 244. sympy__sympy-14024

项目：`sympy/sympy`；base commit：`b17abcb09cbcee80a90f6750e0f9b53f0247656c`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/numbers.py",
      "Integer._eval_power"
    ],
    [
      "sympy/core/numbers.py",
      "Rational._eval_power"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/numbers.py",
      "Integer._eval_power"
    ],
    [
      "sympy/core/numbers.py",
      "Rational._eval_power"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 245. sympy__sympy-14308

项目：`sympy/sympy`；base commit：`fb536869fb7aa28b2695ad7a3b70949926b291c4`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_BasisDependent"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_BasisDependent"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 246. sympy__sympy-14317

项目：`sympy/sympy`；base commit：`fb536869fb7aa28b2695ad7a3b70949926b291c4`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Poly"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Poly"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 247. sympy__sympy-14396

项目：`sympy/sympy`；base commit：`f35ad6411f86a15dd78db39c29d1e5291f66f9b5`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/polys/polyoptions.py",
      "Domain.preprocess"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/polys/polyoptions.py",
      "Domain.preprocess"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 248. sympy__sympy-14774

项目：`sympy/sympy`；base commit：`8fc63c2d71752389a44367b8ef4aba8a91af6a45`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Function"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Function"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 249. sympy__sympy-14817

项目：`sympy/sympy`；base commit：`0dbdc0ea83d339936da175f8c3a97d0d6bafb9f8`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_MatAdd"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_MatAdd"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 250. sympy__sympy-15011

项目：`sympy/sympy`；base commit：`b7c5ba2bf3ffd5cf453b25af7c8ddd9a639800cb`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/utilities/lambdify.py",
      "_EvaluatorPrinter._preprocess"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/utilities/lambdify.py",
      "_EvaluatorPrinter._preprocess"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 251. sympy__sympy-15308

项目：`sympy/sympy`；base commit：`fb59d703e6863ed803c98177b59197b5513332e9`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Basic"
    ],
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Trace"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Basic"
    ],
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_Trace"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 252. sympy__sympy-15345

项目：`sympy/sympy`；base commit：`9ef28fba5b4d6d0168237c9c005a550e6dc27d81`。

状态：missing；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": []
}
```

该题没有最终结果。未运行或尚未完成。

## 253. sympy__sympy-15346

项目：`sympy/sympy`；base commit：`9ef28fba5b4d6d0168237c9c005a550e6dc27d81`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/simplify/trigsimp.py",
      "_futrig"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/simplify/trigsimp.py",
      "_futrig"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 254. sympy__sympy-15609

项目：`sympy/sympy`；base commit：`15f56f3b0006d2ed2c29bde3c43e91618012c849`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_MatrixElement"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_MatrixElement"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 255. sympy__sympy-15678

项目：`sympy/sympy`；base commit：`31c68eef3ffef39e2e792b0ec92cd92b7010eb2a`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/geometry/util.py",
      "idiff"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/geometry/util.py",
      "idiff"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 256. sympy__sympy-16106

项目：`sympy/sympy`；base commit：`0e987498b00167fdd4a08a41c852a97cb70ce8f2`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/mathml.py",
      "MathMLPresentationPrinter._print_Indexed"
    ],
    [
      "sympy/printing/mathml.py",
      "MathMLPresentationPrinter._print_IndexedBase"
    ],
    [
      "sympy/printing/mathml.py",
      "MathMLPresentationPrinter._print_tuple"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/mathml.py",
      "MathMLPresentationPrinter._print_Indexed"
    ],
    [
      "sympy/printing/mathml.py",
      "MathMLPresentationPrinter._print_IndexedBase"
    ],
    [
      "sympy/printing/mathml.py",
      "MathMLPresentationPrinter._print_tuple"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 257. sympy__sympy-16281

项目：`sympy/sympy`；base commit：`41490b75f3621408e0468b0e7b6dc409601fc6ff`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Product"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Product"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 258. sympy__sympy-16503

项目：`sympy/sympy`；base commit：`a7e6f093c98a3c4783848a19fce646e32b6e0161`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Sum"
    ],
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Sum.asum"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Sum"
    ],
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Sum.asum"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 259. sympy__sympy-16792

项目：`sympy/sympy`；base commit：`09786a173e7a0a488f46dd6000177c23e5d24eed`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/utilities/codegen.py",
      "CodeGen.routine"
    ],
    [
      "sympy/utilities/codegen.py",
      "CodeGen.routine.dimensions"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/utilities/codegen.py",
      "CodeGen.routine"
    ],
    [
      "sympy/utilities/codegen.py",
      "CodeGen.routine.dimensions"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 260. sympy__sympy-16988

项目：`sympy/sympy`；base commit：`e727339af6dc22321b00f52d971cda39e4ce89fb`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/sets/sets.py",
      "Intersection.__new__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/sets/sets.py",
      "Intersection.__new__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 261. sympy__sympy-17022

项目：`sympy/sympy`；base commit：`f91de695585c1fbc7d4f49ee061f64fcb1c2c4d8`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pycode.py",
      "NumPyPrinter._print_Identity"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pycode.py",
      "NumPyPrinter._print_Identity"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 262. sympy__sympy-17139

项目：`sympy/sympy`；base commit：`1d3327b8e90a186df6972991963a5ae87053259d`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/simplify/fu.py",
      "_TR56._f"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/simplify/fu.py",
      "_TR56._f"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 263. sympy__sympy-17630

项目：`sympy/sympy`；base commit：`58e78209c8577b9890e957b624466e5beed7eb08`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/expressions/matexpr.py",
      "get_postprocessor._postprocessor"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/expressions/matexpr.py",
      "get_postprocessor._postprocessor"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 264. sympy__sympy-17655

项目：`sympy/sympy`；base commit：`f5e965947af2410ded92cfad987aaf45262ea434`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/geometry/point.py",
      "Point.__rmul__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/geometry/point.py",
      "Point.__rmul__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 265. sympy__sympy-18057

项目：`sympy/sympy`；base commit：`62000f37b8821573ba00280524ffb4ac4a380875`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/expr.py",
      "Expr.__eq__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/expr.py",
      "Expr.__eq__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 266. sympy__sympy-18087

项目：`sympy/sympy`；base commit：`9da013ad0ddc3cd96fe505f2e47c63e372040916`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/exprtools.py",
      "Factors.__init__"
    ],
    [
      "sympy/core/exprtools.py",
      "Factors.as_expr"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/exprtools.py",
      "Factors.__init__"
    ],
    [
      "sympy/core/exprtools.py",
      "Factors.as_expr"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 267. sympy__sympy-18189

项目：`sympy/sympy`；base commit：`1923822ddf8265199dbd9ef9ce09641d3fd042b9`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/solvers/diophantine.py",
      "diophantine"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/solvers/diophantine.py",
      "diophantine"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 268. sympy__sympy-18199

项目：`sympy/sympy`；base commit：`ba80d1e493f21431b4bf729b3e0452cd47eb9566`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/ntheory/residue_ntheory.py",
      "_nthroot_mod_composite"
    ],
    [
      "sympy/ntheory/residue_ntheory.py",
      "nthroot_mod"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/ntheory/residue_ntheory.py",
      "_nthroot_mod_composite"
    ],
    [
      "sympy/ntheory/residue_ntheory.py",
      "nthroot_mod"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 269. sympy__sympy-18532

项目：`sympy/sympy`；base commit：`74227f900b05009d4eed62e34a166228788a32ca`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/basic.py",
      "Basic.atoms"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/basic.py",
      "Basic.atoms"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 270. sympy__sympy-18621

项目：`sympy/sympy`；base commit：`b17ef6effe278d5b861d65896cc53442a6370d8f`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/expressions/blockmatrix.py",
      "BlockDiagMatrix.blocks"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/expressions/blockmatrix.py",
      "BlockDiagMatrix.blocks"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 271. sympy__sympy-18698

项目：`sympy/sympy`；base commit：`3dff1b98a78f28c953ae2140b69356b8391e399c`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/polys/polytools.py",
      "_symbolic_factor_list"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/polys/polytools.py",
      "_symbolic_factor_list"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 272. sympy__sympy-18835

项目：`sympy/sympy`；base commit：`516fa83e69caf1e68306cfc912a13f36c434d51c`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/utilities/iterables.py",
      "uniq"
    ],
    [
      "sympy/utilities/iterables.py",
      "uniq.check"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/utilities/iterables.py",
      "uniq"
    ],
    [
      "sympy/utilities/iterables.py",
      "uniq.check"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 273. sympy__sympy-19007

项目：`sympy/sympy`；base commit：`f9e030b57623bebdc2efa7f297c1b5ede08fcebf`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/matrices/expressions/blockmatrix.py",
      "BlockMatrix._entry"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/matrices/expressions/blockmatrix.py",
      "BlockMatrix._entry"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 274. sympy__sympy-19254

项目：`sympy/sympy`；base commit：`e0ef1da13e2ab2a77866c05246f73c871ca9388c`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 50.00% | 100.00% | 66.67% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/polys/factortools.py",
      "dup_zz_mignotte_bound"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/polys/factortools.py",
      "dup_zz_mignotte_bound"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 275. sympy__sympy-19487

项目：`sympy/sympy`；base commit：`25fbcce5b1a4c7e3956e6062930f4a44ce95a632`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/functions/elementary/complexes.py",
      "sign._eval_rewrite_as_Abs"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/functions/elementary/complexes.py",
      "sign._eval_rewrite_as_Abs"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 276. sympy__sympy-20049

项目：`sympy/sympy`；base commit：`d57aaf064041fe52c0fa357639b069100f8b28e1`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/physics/vector/point.py",
      "Point.vel"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/physics/vector/point.py",
      "Point.vel"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 277. sympy__sympy-20154

项目：`sympy/sympy`；base commit：`bdb49c4abfb35554a3c8ce761696ffff3bb837fe`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/utilities/iterables.py",
      "partitions"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/utilities/iterables.py",
      "partitions"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 278. sympy__sympy-20212

项目：`sympy/sympy`；base commit：`a106f4782a9dbe7f8fd16030f15401d977e03ae9`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/power.py",
      "Pow.__new__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/power.py",
      "Pow.__new__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 279. sympy__sympy-20322

项目：`sympy/sympy`；base commit：`ab864967e71c950a15771bb6c3723636026ba876`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/mul.py",
      "Mul._eval_is_integer"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/mul.py",
      "Mul._eval_is_integer"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 280. sympy__sympy-20442

项目：`sympy/sympy`；base commit：`1abbc0ac3e552cb184317194e5d5c5b9dd8fb640`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/physics/units/util.py",
      "_get_conversion_matrix_for_expr"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/physics/units/util.py",
      "_get_conversion_matrix_for_expr"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 281. sympy__sympy-20590

项目：`sympy/sympy`；base commit：`cffd4e0f86fefd4802349a9f9b19ed70934ea354`。

状态：missing；函数真值：NA。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | NA | NA | NA | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": []
}
```

该题没有最终结果。未运行或尚未完成。

## 282. sympy__sympy-20639

项目：`sympy/sympy`；base commit：`eb926a1d0c1158bf43f01eaf673dc84416b5ebb1`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Pow"
    ],
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_nth_root"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_Pow"
    ],
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_nth_root"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 283. sympy__sympy-21055

项目：`sympy/sympy`；base commit：`748ce73479ee2cd5c861431091001cc18943c735`。

状态：complete；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未命中 |

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

## 284. sympy__sympy-21171

项目：`sympy/sympy`；base commit：`aa22709cb7df2d7503803d4b2c0baa7aa21440b6`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_SingularityFunction"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/latex.py",
      "LatexPrinter._print_SingularityFunction"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 285. sympy__sympy-21379

项目：`sympy/sympy`；base commit：`624217179aaf8d094e6ff75b7493ad1ee47599b0`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/mod.py",
      "Mod.eval"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/mod.py",
      "Mod.eval"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 286. sympy__sympy-21612

项目：`sympy/sympy`；base commit：`b4777fdcef467b7132c055f8ac2c9a5059e6a145`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/str.py",
      "StrPrinter._print_Mul"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/str.py",
      "StrPrinter._print_Mul"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 287. sympy__sympy-21614

项目：`sympy/sympy`；base commit：`b4777fdcef467b7132c055f8ac2c9a5059e6a145`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/core/function.py",
      "Derivative.kind"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/core/function.py",
      "Derivative.kind"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 288. sympy__sympy-21627

项目：`sympy/sympy`；base commit：`126f80578140e752ad5135aac77b8ff887eede3e`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/functions/elementary/complexes.py",
      "Abs.eval"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/functions/elementary/complexes.py",
      "Abs.eval"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 289. sympy__sympy-21847

项目：`sympy/sympy`；base commit：`d9b18c518d64d0ebe8e35a98c2fb519938b9b151`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/polys/monomials.py",
      "itermonomials"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/polys/monomials.py",
      "itermonomials"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 290. sympy__sympy-22005

项目：`sympy/sympy`；base commit：`2c83657ff1c62fc2761b639469fdac7f7561a72a`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/solvers/polysys.py",
      "solve_generic._solve_reduced_system"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/solvers/polysys.py",
      "solve_generic._solve_reduced_system"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 291. sympy__sympy-22714

项目：`sympy/sympy`；base commit：`3ff4717b6aef6086e78f01cdfa06f64ae23aed7e`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/geometry/point.py",
      "Point.__new__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/geometry/point.py",
      "Point.__new__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 292. sympy__sympy-22840

项目：`sympy/sympy`；base commit：`d822fcba181155b85ff2b29fe525adbafb22b448`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/simplify/cse_main.py",
      "tree_cse"
    ],
    [
      "sympy/simplify/cse_main.py",
      "tree_cse._find_repeated"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/simplify/cse_main.py",
      "tree_cse"
    ],
    [
      "sympy/simplify/cse_main.py",
      "tree_cse._find_repeated"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 293. sympy__sympy-23117

项目：`sympy/sympy`；base commit：`c5cef2499d6eed024b0db5c792d6ec7c53baa470`。

状态：missing；函数真值：3。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/tensor/array/ndim_array.py",
      "NDimArray._check_index_for_getitem"
    ],
    [
      "sympy/tensor/array/ndim_array.py",
      "NDimArray._parse_index"
    ],
    [
      "sympy/tensor/array/ndim_array.py",
      "NDimArray._scan_iterable_shape.f"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/tensor/array/ndim_array.py",
      "NDimArray._check_index_for_getitem"
    ],
    [
      "sympy/tensor/array/ndim_array.py",
      "NDimArray._parse_index"
    ],
    [
      "sympy/tensor/array/ndim_array.py",
      "NDimArray._scan_iterable_shape.f"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 294. sympy__sympy-23191

项目：`sympy/sympy`；base commit：`fa9b4b140ec0eaf75a62c1111131626ef0f6f524`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_BasisDependent"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/printing/pretty/pretty.py",
      "PrettyPrinter._print_BasisDependent"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 295. sympy__sympy-23262

项目：`sympy/sympy`；base commit：`fdc707f73a65a429935c01532cd3970d3355eab6`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/utilities/lambdify.py",
      "_recursive_to_string"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/utilities/lambdify.py",
      "_recursive_to_string"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 296. sympy__sympy-24066

项目：`sympy/sympy`；base commit：`514579c655bf22e2af14f0743376ae1d7befe345`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/physics/units/unitsystem.py",
      "UnitSystem._collect_factor_and_dimension"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/physics/units/unitsystem.py",
      "UnitSystem._collect_factor_and_dimension"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 297. sympy__sympy-24102

项目：`sympy/sympy`；base commit：`58598660a3f6ab3d918781c4988c2e4b2bdd9297`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/parsing/mathematica.py",
      "MathematicaParser._from_mathematica_to_tokens"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/parsing/mathematica.py",
      "MathematicaParser._from_mathematica_to_tokens"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 298. sympy__sympy-24152

项目：`sympy/sympy`；base commit：`b9af885473ad7e34b5b0826cb424dd26d8934670`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/physics/quantum/tensorproduct.py",
      "TensorProduct._eval_expand_tensorproduct"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/physics/quantum/tensorproduct.py",
      "TensorProduct._eval_expand_tensorproduct"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 299. sympy__sympy-24213

项目：`sympy/sympy`；base commit：`e8c22f6eac7314be8d92590bfff92ced79ee03e2`。

状态：missing；函数真值：1。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/physics/units/unitsystem.py",
      "UnitSystem._collect_factor_and_dimension"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/physics/units/unitsystem.py",
      "UnitSystem._collect_factor_and_dimension"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

## 300. sympy__sympy-24909

项目：`sympy/sympy`；base commit：`d3b4158dea271485e3daa11bf82e69b8dab348ce`。

状态：missing；函数真值：2。

| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |
|---|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 命中 |
| CoSIL/off | 50.00% | 50.00% | 50.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 0.00% | 0.00% | 0.00% | 未提供 |

原始定位：

```json
{}
```

严格函数真值与预测：

```json
{
  "targets": [
    [
      "sympy/physics/units/prefixes.py",
      "Prefix.__mul__"
    ],
    [
      "sympy/physics/units/prefixes.py",
      "Prefix.__truediv__"
    ]
  ],
  "predictions": [],
  "unresolved": []
}
```

函数集合分析：

```json
{
  "correct": [],
  "false_positive": [],
  "missed_targets": [
    [
      "sympy/physics/units/prefixes.py",
      "Prefix.__mul__"
    ],
    [
      "sympy/physics/units/prefixes.py",
      "Prefix.__truediv__"
    ]
  ]
}
```

该题没有最终结果。未运行或尚未完成。

