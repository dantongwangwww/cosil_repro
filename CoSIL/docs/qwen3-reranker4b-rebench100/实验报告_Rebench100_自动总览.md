# SWE-rebench100：Qwen3基线与4B剪枝对照

状态：COMPLETE；已配对执行100/100、完整成功99/100。文件分母100，完整非空既有函数分母92；未运行不冒充模型失败，最终按固定名单计分。

| 条件 | 文件Hit@1 | 文件Hit@3 | 文件Hit@5 | 函数Hit@1 | 函数Hit@3 | 函数Hit@5 | 函数Recall@5 | 全目标覆盖@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 48/100 | 59/100 | 68/100 | 36/92 | 47/92 | 49/92 | 48.10% | 43.48% |
| hybrid_safe | 48/100 | 59/100 | 68/100 | 37/92 | 48/92 | 49/92 | 47.55% | 42.39% |

主模型token与时间按同题补计共享文件阶段；4B自身计算、初始化与CPU缓存准备另外披露。基线固定先跑，缓存／共享GPU负载影响时间，token少不等于整体成本更低。

冻结265池已被历史实验观察过；本轮不按历史表现选题，不调阈值；每仓最多一道，不能代表全部SWE-rebench或视为完全未见测试集。正式test保持封存。

```json
{
  "state": "COMPLETE",
  "allocated": 100,
  "attempted_pairs": 100,
  "complete_pairs": 99,
  "file_denominator": 100,
  "function_denominator": 92,
  "metrics": {
    "baseline": {
      "file": {
        "n": 100,
        "hit1_numerator": 48,
        "hit1": 0.48,
        "hit1_ci95": [
          0.384645517580519,
          0.5768342223477603
        ],
        "hit3_numerator": 59,
        "hit3": 0.59,
        "hit3_ci95": [
          0.4920143005341078,
          0.6813268697886348
        ],
        "hit5_numerator": 68,
        "hit5": 0.68,
        "hit5_ci95": [
          0.5833738138954762,
          0.7633085267500092
        ],
        "precision5": 0.136,
        "precision5_ci95": [
          0.1179999999999999,
          0.15399999999999978
        ],
        "recall5": 0.68,
        "recall5_ci95": [
          0.59,
          0.77
        ],
        "f15": 0.22666666666666668,
        "f15_ci95": [
          0.19666666666666666,
          0.25666666666666643
        ],
        "all_coverage5": 0.68,
        "all_coverage5_ci95": [
          0.59,
          0.77
        ],
        "mrr10": 0.5483333333333333,
        "mrr10_ci95": [
          0.45916666666666667,
          0.638
        ]
      },
      "function": {
        "n": 92,
        "hit1_numerator": 36,
        "hit1": 0.391304347826087,
        "hit1_ci95": [
          0.29785623268996947,
          0.49346580845907867
        ],
        "hit3_numerator": 47,
        "hit3": 0.5108695652173914,
        "hit3_ci95": [
          0.4103549210616722,
          0.6105128748234231
        ],
        "hit5_numerator": 49,
        "hit5": 0.532608695652174,
        "hit5_ci95": [
          0.4314045669897713,
          0.6311988206655142
        ],
        "precision5": 0.11739130434782609,
        "precision5_ci95": [
          0.09347826086956523,
          0.14347826086956508
        ],
        "recall5": 0.48097826086956524,
        "recall5_ci95": [
          0.3858695652173913,
          0.5788043478260869
        ],
        "f15": 0.18512767425810905,
        "f15_ci95": [
          0.14803312629399593,
          0.2236024844720497
        ],
        "all_coverage5": 0.43478260869565216,
        "all_coverage5_ci95": [
          0.33695652173913043,
          0.532608695652174
        ],
        "mrr10": 0.45181159420289857,
        "mrr10_ci95": [
          0.35833333333333334,
          0.5481884057971016
        ]
      }
    },
    "hybrid_safe": {
      "file": {
        "n": 100,
        "hit1_numerator": 48,
        "hit1": 0.48,
        "hit1_ci95": [
          0.384645517580519,
          0.5768342223477603
        ],
        "hit3_numerator": 59,
        "hit3": 0.59,
        "hit3_ci95": [
          0.4920143005341078,
          0.6813268697886348
        ],
        "hit5_numerator": 68,
        "hit5": 0.68,
        "hit5_ci95": [
          0.5833738138954762,
          0.7633085267500092
        ],
        "precision5": 0.136,
        "precision5_ci95": [
          0.1179999999999999,
          0.15399999999999978
        ],
        "recall5": 0.68,
        "recall5_ci95": [
          0.59,
          0.77
        ],
        "f15": 0.22666666666666668,
        "f15_ci95": [
          0.19666666666666666,
          0.25666666666666643
        ],
        "all_coverage5": 0.68,
        "all_coverage5_ci95": [
          0.59,
          0.77
        ],
        "mrr10": 0.5483333333333333,
        "mrr10_ci95": [
          0.45916666666666667,
          0.638
        ]
      },
      "function": {
        "n": 92,
        "hit1_numerator": 37,
        "hit1": 0.40217391304347827,
        "hit1_ci95": [
          0.3078495879261849,
          0.5043402491079584
        ],
        "hit3_numerator": 48,
        "hit3": 0.5217391304347826,
        "hit3_ci95": [
          0.4208569740212842,
          0.6208786177489061
        ],
        "hit5_numerator": 49,
        "hit5": 0.532608695652174,
        "hit5_ci95": [
          0.4314045669897713,
          0.6311988206655142
        ],
        "precision5": 0.11521739130434783,
        "precision5_ci95": [
          0.091304347826087,
          0.13913043478260864
        ],
        "recall5": 0.47554347826086957,
        "recall5_ci95": [
          0.38315217391304346,
          0.5760869565217391
        ],
        "f15": 0.18202208419599727,
        "f15_ci95": [
          0.14682539682539691,
          0.21997929606625258
        ],
        "all_coverage5": 0.42391304347826086,
        "all_coverage5_ci95": [
          0.32608695652173914,
          0.532608695652174
        ],
        "mrr10": 0.4592391304347826,
        "mrr10_ci95": [
          0.3659420289855072,
          0.5570652173913043
        ]
      }
    }
  },
  "resources": {
    "baseline": {
      "statuses": {
        "complete": 99,
        "failed": 1
      },
      "actual_main_tokens": 8313354,
      "main_prompt_tokens": 8242280,
      "main_completion_tokens": 71074,
      "main_pruner_tokens": 964727,
      "local_input_tokens": 0,
      "local_decisions": 0,
      "routes": {},
      "local_gold_reject_events": 0,
      "comparable_tokens": 8313354,
      "comparable_mean_tokens": 83133.54,
      "comparable_mean_seconds": 34.727700186604636,
      "comparable_median_seconds": 33.62470524199307
    },
    "hybrid_safe": {
      "statuses": {
        "complete": 99,
        "BLOCKED_SHARED_FILE_STAGE": 1
      },
      "actual_main_tokens": 7309907,
      "main_prompt_tokens": 7252143,
      "main_completion_tokens": 57764,
      "main_pruner_tokens": 597941,
      "local_input_tokens": 764211,
      "local_decisions": 652,
      "routes": {
        "qwen": 329,
        "reject": 104,
        "retain": 219
      },
      "local_gold_reject_events": 0,
      "comparable_tokens": 7927200,
      "comparable_mean_tokens": 79272,
      "comparable_mean_seconds": 39.77586982633918,
      "comparable_median_seconds": 38.792010333854705
    }
  },
  "api_calls": 0,
  "gpu_limit": 2,
  "final": true,
  "paired_function_hit5": {
    "n": 92,
    "baseline_hits": 49,
    "hybrid_hits": 49,
    "only_baseline": 1,
    "only_hybrid": 1,
    "delta": 0.0,
    "mcnemar_exact_p": 1.0,
    "noninferiority_certified": false
  }
}
```
