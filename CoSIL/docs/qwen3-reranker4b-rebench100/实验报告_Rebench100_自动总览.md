# SWE-rebench100：Qwen3基线与4B剪枝对照

状态：FAILED；已配对执行68/100、完整成功68/100。文件分母100，完整非空既有函数分母92；未运行不冒充模型失败，最终按固定名单计分。

| 条件 | 文件Hit@1 | 文件Hit@3 | 文件Hit@5 | 函数Hit@1 | 函数Hit@3 | 函数Hit@5 | 函数Recall@5 | 全目标覆盖@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 33/100 | 39/100 | 46/100 | 26/92 | 33/92 | 35/92 | 34.24% | 30.43% |
| hybrid_safe | 33/100 | 39/100 | 46/100 | 26/92 | 34/92 | 35/92 | 33.70% | 29.35% |

主模型token与时间按同题补计共享文件阶段；4B自身计算、初始化与CPU缓存准备另外披露。基线固定先跑，缓存／共享GPU负载影响时间，token少不等于整体成本更低。

冻结265池已被历史实验观察过；本轮不按历史表现选题，不调阈值；每仓最多一道，不能代表全部SWE-rebench或视为完全未见测试集。正式test保持封存。

```json
{
  "state": "FAILED",
  "allocated": 100,
  "attempted_pairs": 68,
  "complete_pairs": 68,
  "file_denominator": 100,
  "function_denominator": 92,
  "metrics": {
    "baseline": {
      "file": {
        "n": 100,
        "hit1_numerator": 33,
        "hit1": 0.33,
        "hit1_ci95": [
          0.24563122734128034,
          0.4269465620490947
        ],
        "hit3_numerator": 39,
        "hit3": 0.39,
        "hit3_ci95": [
          0.3001687400639441,
          0.4879698295415926
        ],
        "hit5_numerator": 46,
        "hit5": 0.46,
        "hit5_ci95": [
          0.36560808309024106,
          0.5573513967663177
        ],
        "precision5": 0.092,
        "precision5_ci95": [
          0.07200000000000004,
          0.11199999999999992
        ],
        "recall5": 0.46,
        "recall5_ci95": [
          0.36,
          0.56
        ],
        "f15": 0.15333333333333335,
        "f15_ci95": [
          0.12000000000000004,
          0.18666666666666668
        ],
        "all_coverage5": 0.46,
        "all_coverage5_ci95": [
          0.36,
          0.56
        ],
        "mrr10": 0.37166666666666665,
        "mrr10_ci95": [
          0.2856666666666666,
          0.4643333333333334
        ]
      },
      "function": {
        "n": 92,
        "hit1_numerator": 26,
        "hit1": 0.2826086956521739,
        "hit1_ci95": [
          0.2007567930217749,
          0.3818872892763214
        ],
        "hit3_numerator": 33,
        "hit3": 0.358695652173913,
        "hit3_ci95": [
          0.2681713717356563,
          0.4605472817581062
        ],
        "hit5_numerator": 35,
        "hit5": 0.3804347826086957,
        "hit5_ci95": [
          0.28791157059835987,
          0.48254267466559314
        ],
        "precision5": 0.08478260869565218,
        "precision5_ci95": [
          0.06086956521739134,
          0.10869565217391304
        ],
        "recall5": 0.3423913043478261,
        "recall5_ci95": [
          0.2554347826086957,
          0.43478260869565216
        ],
        "f15": 0.13354037267080748,
        "f15_ci95": [
          0.09834368530020701,
          0.17132505175983442
        ],
        "all_coverage5": 0.30434782608695654,
        "all_coverage5_ci95": [
          0.21739130434782608,
          0.40217391304347827
        ],
        "mrr10": 0.3213768115942029,
        "mrr10_ci95": [
          0.23405797101449277,
          0.4141304347826087
        ]
      }
    },
    "hybrid_safe": {
      "file": {
        "n": 100,
        "hit1_numerator": 33,
        "hit1": 0.33,
        "hit1_ci95": [
          0.24563122734128034,
          0.4269465620490947
        ],
        "hit3_numerator": 39,
        "hit3": 0.39,
        "hit3_ci95": [
          0.3001687400639441,
          0.4879698295415926
        ],
        "hit5_numerator": 46,
        "hit5": 0.46,
        "hit5_ci95": [
          0.36560808309024106,
          0.5573513967663177
        ],
        "precision5": 0.092,
        "precision5_ci95": [
          0.07200000000000004,
          0.11199999999999992
        ],
        "recall5": 0.46,
        "recall5_ci95": [
          0.36,
          0.56
        ],
        "f15": 0.15333333333333335,
        "f15_ci95": [
          0.12000000000000004,
          0.18666666666666668
        ],
        "all_coverage5": 0.46,
        "all_coverage5_ci95": [
          0.36,
          0.56
        ],
        "mrr10": 0.37166666666666665,
        "mrr10_ci95": [
          0.2856666666666666,
          0.4643333333333334
        ]
      },
      "function": {
        "n": 92,
        "hit1_numerator": 26,
        "hit1": 0.2826086956521739,
        "hit1_ci95": [
          0.2007567930217749,
          0.3818872892763214
        ],
        "hit3_numerator": 34,
        "hit3": 0.3695652173913043,
        "hit3_ci95": [
          0.2780163401233967,
          0.47157010925546106
        ],
        "hit5_numerator": 35,
        "hit5": 0.3804347826086957,
        "hit5_ci95": [
          0.28791157059835987,
          0.48254267466559314
        ],
        "precision5": 0.08260869565217392,
        "precision5_ci95": [
          0.06086956521739133,
          0.10652173913043476
        ],
        "recall5": 0.33695652173913043,
        "recall5_ci95": [
          0.24456521739130435,
          0.42934782608695654
        ],
        "f15": 0.13043478260869568,
        "f15_ci95": [
          0.09575569358178053,
          0.16718426501035205
        ],
        "all_coverage5": 0.29347826086956524,
        "all_coverage5_ci95": [
          0.20652173913043478,
          0.391304347826087
        ],
        "mrr10": 0.3233695652173913,
        "mrr10_ci95": [
          0.23641304347826086,
          0.41485507246376807
        ]
      }
    }
  },
  "resources": {
    "baseline": {
      "statuses": {
        "complete": 68,
        "failed": 1,
        "NOT_RUN": 31
      },
      "actual_main_tokens": 5861631,
      "main_prompt_tokens": 5812753,
      "main_completion_tokens": 48878,
      "main_pruner_tokens": 658109,
      "local_input_tokens": 0,
      "local_decisions": 0,
      "routes": {},
      "local_gold_reject_events": 0,
      "comparable_tokens": 5861631,
      "comparable_mean_tokens": 86200.45588235294,
      "comparable_mean_seconds": 35.03552272939123,
      "comparable_median_seconds": 33.95985150942579
    },
    "hybrid_safe": {
      "statuses": {
        "complete": 68,
        "NOT_RUN": 32
      },
      "actual_main_tokens": 5226227,
      "main_prompt_tokens": 5187413,
      "main_completion_tokens": 38814,
      "main_pruner_tokens": 458268,
      "local_input_tokens": 530700,
      "local_decisions": 438,
      "routes": {
        "qwen": 223,
        "reject": 57,
        "retain": 158
      },
      "local_gold_reject_events": 0,
      "comparable_tokens": 5672716,
      "comparable_mean_tokens": 83422.29411764706,
      "comparable_mean_seconds": 40.05024370412781,
      "comparable_median_seconds": 38.792010333854705
    }
  },
  "api_calls": 0,
  "gpu_limit": 2,
  "final": true,
  "paired_function_hit5": {
    "n": 63,
    "baseline_hits": 35,
    "hybrid_hits": 35,
    "only_baseline": 1,
    "only_hybrid": 1,
    "delta": 0.0,
    "mcnemar_exact_p": 1.0,
    "noninferiority_certified": false
  }
}
```
