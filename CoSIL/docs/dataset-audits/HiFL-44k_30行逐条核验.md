# HiFL-44k：30行逐条核验

行号为原始文件从0开始的row index；文件/函数/行各10条，选择规则在总览中披露。源仓、issue、PR与测试证据逐项区分，未核验不写成False。
targeted=明确针对问题的合并PR；related=仅关联，不能认证为原问题单一修复；unverified=候选错误/无修复源。所有repo当前可访问。

| 行号/层级 | 源仓及issue | PR候选 | 关联级别 | 测试相关修改 | Full所有split同仓 |
|---|---|---|---|---|---|
| 14439/file | [letta-ai/letta#197](https://github.com/letta-ai/letta/issues/197) | [#216](https://github.com/letta-ai/letta/pull/216) | targeted | 无 | 否 |
| 35264/file | [pyscript/pyscript#1780](https://github.com/pyscript/pyscript/issues/1780) | [#1781](https://github.com/pyscript/pyscript/pull/1781) | targeted | 无 | 否 |
| 7170/file | [pandas-dev/pandas#31355](https://github.com/pandas-dev/pandas/issues/31355) | [#36335](https://github.com/pandas-dev/pandas/pull/36335) | targeted | 有 | 是 |
| 5901/file | [keras-team/keras#19257](https://github.com/keras-team/keras/issues/19257) | [#19284](https://github.com/keras-team/keras/pull/19284) | targeted | 有 | 否 |
| 39024/file | [wagtail/wagtail#1852](https://github.com/wagtail/wagtail/issues/1852) | [#1879](https://github.com/wagtail/wagtail/pull/1879) | targeted | 有 | 是 |
| 23149/file | [ranger/ranger#2812](https://github.com/ranger/ranger/issues/2812) | [#2818](https://github.com/ranger/ranger/pull/2818) | targeted | 无 | 否 |
| 19347/file | [python/mypy#4794](https://github.com/python/mypy/issues/4794) | [#7693](https://github.com/python/mypy/pull/7693) | unverified | NA | 否 |
| 37928/file | [searxng/searxng#4020](https://github.com/searxng/searxng/issues/4020) | [#4021](https://github.com/searxng/searxng/pull/4021) | targeted | 无 | 否 |
| 24894/file | [python/mypy#11893](https://github.com/python/mypy/issues/11893) | [#12463](https://github.com/python/mypy/pull/12463) | targeted | 有 | 否 |
| 12691/file | [openai/openai-python#173](https://github.com/openai/openai-python/issues/173) | [#176](https://github.com/openai/openai-python/pull/176) | targeted | 无 | 否 |
| 12333/function | [localstack/localstack#1302](https://github.com/localstack/localstack/issues/1302) | [#1849](https://github.com/localstack/localstack/pull/1849) | targeted | 有 | 否 |
| 25704/function | [keras-team/keras#3703](https://github.com/keras-team/keras/issues/3703) | [#3708](https://github.com/keras-team/keras/pull/3708) | related | NA | 否 |
| 18726/function | [huggingface/transformers#3502](https://github.com/huggingface/transformers/issues/3502) | [#3517](https://github.com/huggingface/transformers/pull/3517) | targeted | 无 | 是 |
| 1291/function | [BerriAI/litellm#5022](https://github.com/BerriAI/litellm/issues/5022) | [#5025](https://github.com/BerriAI/litellm/pull/5025) | targeted | 有 | 否 |
| 12053/function | [dask/dask#2509](https://github.com/dask/dask/issues/2509) | [#2513](https://github.com/dask/dask/pull/2513) | targeted | 有 | 否 |
| 38149/function | [keras-team/keras#19120](https://github.com/keras-team/keras/issues/19120) | [#19133](https://github.com/keras-team/keras/pull/19133) | targeted | 无 | 否 |
| 37405/function | [holoviz/holoviews#987](https://github.com/holoviz/holoviews/issues/987) | [#1213](https://github.com/holoviz/holoviews/pull/1213) | targeted | 有 | 否 |
| 10376/function | [python/mypy#10357](https://github.com/python/mypy/issues/10357) | [#13602](https://github.com/python/mypy/pull/13602) | targeted | 有 | 否 |
| 26641/function | [localstack/localstack#5337](https://github.com/localstack/localstack/issues/5337) | [#5388](https://github.com/localstack/localstack/pull/5388) | targeted | 有 | 否 |
| 3736/function | [python/mypy#2911](https://github.com/python/mypy/issues/2911) | [#2912](https://github.com/python/mypy/pull/2912) | targeted | 有 | 否 |
| 5490/line | [Avaiga/taipy#1268](https://github.com/Avaiga/taipy/issues/1268) | [#1281](https://github.com/Avaiga/taipy/pull/1281) | targeted | 无 | 否 |
| 19923/line | [freqtrade/freqtrade#2789](https://github.com/freqtrade/freqtrade/issues/2789) | [#2790](https://github.com/freqtrade/freqtrade/pull/2790) | targeted | 无 | 否 |
| 3846/line | [pymc-devs/pymc#4273](https://github.com/pymc-devs/pymc/issues/4273) | [#4297](https://github.com/pymc-devs/pymc/pull/4297) | targeted | 有 | 否 |
| 13050/line | [apache/airflow#1357](https://github.com/apache/airflow/issues/1357) | [#1371](https://github.com/apache/airflow/pull/1371) | targeted | 无 | 是 |
| 9051/line | [huggingface/transformers#14301](https://github.com/huggingface/transformers/issues/14301) | [#14658](https://github.com/huggingface/transformers/pull/14658) | targeted | 有 | 是 |
| 2088/line | [python/mypy#6619](https://github.com/python/mypy/issues/6619) | [#8562](https://github.com/python/mypy/pull/8562) | targeted | 有 | 否 |
| 11259/line | [frappe/erpnext#3402](https://github.com/frappe/erpnext/issues/3402) | [#3572](https://github.com/frappe/erpnext/pull/3572) | targeted | 无 | 否 |
| 17982/line | [numpy/numpy#647](https://github.com/numpy/numpy/issues/647) | [#7119](https://github.com/numpy/numpy/pull/7119) | targeted | 无 | 是 |
| 18098/line | [dask/distributed#4872](https://github.com/dask/distributed/issues/4872) | [#4997](https://github.com/dask/distributed/pull/4997) | targeted | 无 | 否 |
| 36313/line | [keras-team/keras#4881](https://github.com/keras-team/keras/issues/4881) | [#4917](https://github.com/keras-team/keras/pull/4917) | targeted | 有 | 否 |

## 行14439：Don't crash on rate limit error

- 来源：[issue](https://github.com/letta-ai/letta/issues/197)；当前API可访问：True；正文精确匹配：True。
- [PR#216](https://github.com/letta-ai/letta/pull/216)，合并于2023-10-31T19:12:07Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`7ccfe5e951a0e8368c0aee7e8499e07fdb92b074`；head：`998d4da5818f58627b781df96fe784b18135f6da`；merge：`4e6af2f3e3085db6e81eb9e5113f20b3076fec7f`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_14439.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_14439.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_14439.json)。

## 行35264：Do not recycle lastElementChild in display

- 来源：[issue](https://github.com/pyscript/pyscript/issues/1780)；当前API可访问：False；正文精确匹配：None。
- [PR#1781](https://github.com/pyscript/pyscript/pull/1781)，合并于2023-10-02T13:39:35Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`50f7ab0f34958f37119f00a0a6ef13753a33fa66`；head：`11ae827d6e55dd21053cd0262eb667b4553aa649`；merge：`bc1cac9c417d3b3ba9ae4bb91b48929c9e43fbe2`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_35264.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_35264.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_35264.json)。

## 行7170：BUG: Calling cartesian_product with large combinatorial space overflows int64 gives misleading errors

- 来源：[issue](https://github.com/pandas-dev/pandas/issues/31355)；当前API可访问：True；正文精确匹配：True。
- [PR#36335](https://github.com/pandas-dev/pandas/pull/36335)，合并于2020-09-13T20:22:37Z，完整changed-files=2。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`068d1b5be234231e5a829399d58136f5028834eb`；head：`c965099fd3d4a83301ce7d5c9aec3d4361acdfdc`；merge：`aa6298fb757e0e26b95a9478888489d105e0e128`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`pandas/tests/reshape/test_util.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_7170.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_7170.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_7170.json)。

## 行5901：Keras 3 Attention layer value tensor dimension

- 来源：[issue](https://github.com/keras-team/keras/issues/19257)；当前API可访问：True；正文精确匹配：True。
- [PR#19284](https://github.com/keras-team/keras/pull/19284)，合并于2024-03-18T22:25:43Z，完整changed-files=3。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`4c356306273153d5dc26fc5772b106b4f750095f`；head：`54f5956c3df333e932ae2aea43e17652fd7ebf69`；merge：`b2ef949cceb01c53d231a4da9cbfbaa12cea981d`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`keras/layers/attention/attention_test.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_5901.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_5901.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_5901.json)。

## 行39024：Copy function regression with many to many fields

- 来源：[issue](https://github.com/wagtail/wagtail/issues/1852)；当前API可访问：True；正文精确匹配：True。
- [PR#1879](https://github.com/wagtail/wagtail/pull/1879)，合并于2015-11-02T10:50:35Z，完整changed-files=5。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`26857f525d21d14343dbced0f1443b5502896276`；head：`9db24387fe0f64810c871d2ad6a98abc3813b663`；merge：`d86cbae5e63c099911694762bcb15170baee67d5`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`wagtail/tests/testapp/migrations/0014_m2m_blog_page.py`、`wagtail/tests/testapp/migrations/0015_genericsnippetpage.py`、`wagtail/tests/testapp/models.py`、`wagtail/wagtailcore/tests/test_page_model.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_39024.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_39024.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_39024.json)。

## 行23149：`:flat 1` crashes ranger

- 来源：[issue](https://github.com/ranger/ranger/issues/2812)；当前API可访问：True；正文精确匹配：True。
- [PR#2818](https://github.com/ranger/ranger/pull/2818)，合并于2023-04-03T10:42:52Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`a953f8f3576b667b6f5d84cd9e41e8b079546f06`；head：`454c2d14ca1e7b46b1b1288f76b1021ae289828c`；merge：`b8340db5e615842aa40c5572db89d469b8fe1c60`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_23149.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_23149.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_23149.json)。

## 行19347：Multiple assignment of types is not recognized as a type alias

- 来源：[issue](https://github.com/python/mypy/issues/4794)；当前API可访问：True；正文精确匹配：True。
- [PR#7693](https://github.com/python/mypy/pull/7693)，合并于2019-10-12T05:16:22Z，完整changed-files=2。关联级别：`no_verified_fix_PR`。
- 核验理由：Reject PR7693: it fixes7279 rather than4794. Source issue closes by design, declining multiple-target type aliases; no verified fixing PR.
- PR base：`742d33a41271206d6eb7dd2e4b04659de4683597`；head：`7017681f35518ccd4a4a7818c8efe726e33c7c0a`；merge：`34fe00b4f9220fa9a939be1a80cf5acc3479da9a`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`test-data/unit/check-enum.test`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_19347.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_19347.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_19347.json)。

## 行37928：Problem with DDG and Hebrew search

- 来源：[issue](https://github.com/searxng/searxng/issues/4020)；当前API可访问：True；正文精确匹配：True。
- [PR#4021](https://github.com/searxng/searxng/pull/4021)，合并于2024-11-17T17:14:23Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`4b57bc3db19b373d28b55db00d728a0c610ba9af`；head：`19d8ba76f613aeeb36d631be737b84ae23ff0308`；merge：`10d3af84b833ab2f2d1095efa3a7ba240ffb32fc`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_37928.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_37928.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_37928.json)。

## 行24894：Stubgen applies Generator type to function with nested generator

- 来源：[issue](https://github.com/python/mypy/issues/11893)；当前API可访问：True；正文精确匹配：True。
- [PR#12463](https://github.com/python/mypy/pull/12463)，合并于2022-03-27T03:34:05Z，完整changed-files=2。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`c7559283995ea020afbb82d92cad538f0b174913`；head：`c550d124d32d1e545a40781f640bf8bb59354fbc`；merge：`1480344cfc99ed0396c2b9b9f36c14b253f440b4`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`test-data/unit/stubgen.test`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_24894.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_24894.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_24894.json)。

## 行12691：[0.26.0] openai/cli.py:440: RuntimeWarning: coroutine 'FineTune.stream_events' was never awaited

- 来源：[issue](https://github.com/openai/openai-python/issues/173)；当前API可访问：True；正文精确匹配：True。
- [PR#176](https://github.com/openai/openai-python/pull/176)，合并于2023-01-12T05:35:31Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`777c1c3de1a9cfc0a33e6376cc09b9badbb9cdf9`；head：`2f0b32d5b253176c943bbd82a1a2be7e9ec4a137`；merge：`71cee6a4ab54a1c26bc8f3570a435ef189c9aeff`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_12691.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_12691.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_12691.json)。

## 行12333：Handle "success_action_status" form field in S3 POST.

- 来源：[issue](https://github.com/localstack/localstack/issues/1302)；当前API可访问：True；正文精确匹配：True。
- [PR#1849](https://github.com/localstack/localstack/pull/1849)，合并于2019-12-11T20:31:31Z，完整changed-files=3。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`dd0a9742da83dd05e110d35f5159fa656c4871c4`；head：`7cf3bcbee9e711f10427684d4596e7d28537167b`；merge：`d052ee7cba725505d74e500bffe5d06b29e8537e`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`tests/unit/test_s3.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_12333.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_12333.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_12333.json)。

## 行25704：Lambda layer for computing sum over samples does not work

- 来源：[issue](https://github.com/keras-team/keras/issues/3703)；当前API可访问：True；正文精确匹配：True。
- [PR#3708](https://github.com/keras-team/keras/pull/3708)，合并于2016-09-06T22:04:26Z，完整changed-files=1。关联级别：`related_PR_secondary_error`。
- 核验理由：PR3708 mentions3703 and changes error formatting; source first closed after output_shape workaround before PR merge. Not a certified sole fix for original Lambda limitation.
- PR base：`4325843ef07b00eb3f234d5d3dd5c92205effe9f`；head：`d4fdb2ab82ba4de2ad050d4629ed52ef56aeb122`；merge：`f05cd95fadfd9a2084f27eb88ff62d1bdfe5d5e5`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_25704.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_25704.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_25704.json)。

## 行18726：Bert Batch Encode Plus adding an extra [SEP]

- 来源：[issue](https://github.com/huggingface/transformers/issues/3502)；当前API可访问：True；正文精确匹配：True。
- [PR#3517](https://github.com/huggingface/transformers/pull/3517)，合并于2020-04-07T20:26:31Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`5aa8a278a3f13b8f83a0deb9b6d743f159cea23c`；head：`3bde1625e1733cef402213006237340292f542b3`；merge：`b0ad06951708b782e45b02a4d092f6fcde68a9b9`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_18726.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_18726.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_18726.json)。

## 行1291：Handle bedrock tool calling in stream_chunk_builder

- 来源：[issue](https://github.com/BerriAI/litellm/issues/5022)；当前API可访问：True；正文精确匹配：True。
- [PR#5025](https://github.com/BerriAI/litellm/pull/5025)，合并于2024-08-04T03:31:05Z，完整changed-files=3。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`7f1d32a75b5cddb51c5a5006d7e436f3fe1cd03e`；head：`b7be609d6e3d197e0dec4083bf1ed5d9fa148a42`；merge：`c5fe467cdd559390a7742a7a05ab4ce421b48719`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`litellm/tests/stream_chunk_testdata.py`、`litellm/tests/test_stream_chunk_builder.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_1291.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_1291.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_1291.json)。

## 行12053：DataFrame.assign with lambda

- 来源：[issue](https://github.com/dask/dask/issues/2509)；当前API可访问：True；正文精确匹配：True。
- [PR#2513](https://github.com/dask/dask/pull/2513)，合并于2017-07-10T14:47:44Z，完整changed-files=2。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`657317cc09676348a0c1d725c2e6dfb3cf589809`；head：`6f7db606446de41d708692364ef9ddd1e4eb34ba`；merge：`f92f2d92cfda1218242cb8a81841ec6856189bbc`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`dask/dataframe/tests/test_dataframe.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_12053.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_12053.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_12053.json)。

## 行38149：[Performance regression] Since keras==3.0.3, using ArrayDataAdapter with PyTorch is much slower

- 来源：[issue](https://github.com/keras-team/keras/issues/19120)；当前API可访问：True；正文精确匹配：True。
- [PR#19133](https://github.com/keras-team/keras/pull/19133)，合并于2024-02-02T04:50:26Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`6c1ea8dd6b80198f4b555696c4f5545f5cc4293f`；head：`feec83a7252425ae4ffd8ed84b765950bf263842`；merge：`e5f92f350719861fbca7abcd69f3730bd00ac096`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_38149.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_38149.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_38149.json)。

## 行37405：Overlaying an AdjointLayout should either error or overlay the main layer

- 来源：[issue](https://github.com/holoviz/holoviews/issues/987)；当前API可访问：True；正文精确匹配：True。
- [PR#1213](https://github.com/holoviz/holoviews/pull/1213)，合并于2017-03-16T20:03:20Z，完整changed-files=4。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`3658cbd8c858e81847064d69866cfb5d5621e912`；head：`fc722328ba7f0da3d154e1fce6b262c666e72f66`；merge：`f1edbabf7e02cb84afcc978e941fb390d53ab2c2`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`tests/testlayouts.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_37405.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_37405.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_37405.json)。

## 行10376：Crash involving member type aliases

- 来源：[issue](https://github.com/python/mypy/issues/10357)；当前API可访问：True；正文精确匹配：True。
- [PR#13602](https://github.com/python/mypy/pull/13602)，合并于2022-09-05T15:42:27Z，完整changed-files=5。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`2e326b2394b0af44c8023c6b7d153bff1c1b5c54`；head：`1e0f6309114bf1e73caa5bf523c6e4f6da7a3e9c`；merge：`71e19e85e2adc68594e983d012f07bfe7af7256c`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`test-data/unit/check-dataclasses.test`、`test-data/unit/check-type-aliases.test`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_10376.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_10376.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_10376.json)。

## 行26641：bug: SNS to SQS subscription breaks on republished 0.13.3 version

- 来源：[issue](https://github.com/localstack/localstack/issues/5337)；当前API可访问：True；正文精确匹配：True。
- [PR#5388](https://github.com/localstack/localstack/pull/5388)，合并于2022-01-28T22:17:37Z，完整changed-files=4。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`e9bfab3b3deb192a3f73359cd5ca0a6f15d96184`；head：`2276c31f39a85e0f718003a612364513f8f18149`；merge：`1ce07121755a5e08ef43f7928ae2194d077fef70`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`tests/integration/test_sns.py`、`tests/integration/test_sqs.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_26641.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_26641.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_26641.json)。

## 行3736：Metaclass with Any type should be allowed

- 来源：[issue](https://github.com/python/mypy/issues/2911)；当前API可访问：True；正文精确匹配：True。
- [PR#2912](https://github.com/python/mypy/pull/2912)，合并于2017-02-27T13:58:48Z，完整changed-files=3。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`0bb2d1680e8b9522108b38d203cb73021a617e64`；head：`31d03ba5e4926deff15bd660d681ec9aaf92226f`；merge：`d2eaa08ffea36dd1f63a56dac0f345efa3ae62fd`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`test-data/unit/check-classes.test`、`test-data/unit/check-python2.test`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_3736.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_3736.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_3736.json)。

## 行5490：BUG-gui.reload creates a new ngrok tunnel which fails when 3 tunnels are already active

- 来源：[issue](https://github.com/Avaiga/taipy/issues/1268)；当前API可访问：True；正文精确匹配：True。
- [PR#1281](https://github.com/Avaiga/taipy/pull/1281)，合并于2024-05-14T07:30:43Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`ebf7f9d0d780bdf5b3bc7098cd23ebf03dc8c946`；head：`b2fce695f419ebcbf187025366d133058e1b3f9b`；merge：`24fc8fe0f39266dc1ff9589892e378143a28fde9`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_5490.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_5490.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_5490.json)。

## 行19923：UserWarning: Boolean Series key will be reindexed to match DataFrame index.

- 来源：[issue](https://github.com/freqtrade/freqtrade/issues/2789)；当前API可访问：True；正文精确匹配：True。
- [PR#2790](https://github.com/freqtrade/freqtrade/pull/2790)，合并于2020-01-22T09:29:21Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`66415d48d4d9d42aaeec6beb1b8fc58dd58cf022`；head：`7d2d0235a0407b564038f02b4834ab365cc72f8a`；merge：`055f3fd1fdb1e32a2b2f602234f4d7ee512152a0`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_19923.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_19923.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_19923.json)。

## 行3846：Recursion error pickling step functions

- 来源：[issue](https://github.com/pymc-devs/pymc/issues/4273)；当前API可访问：True；正文精确匹配：True。
- [PR#4297](https://github.com/pymc-devs/pymc/pull/4297)，合并于2020-12-05T11:35:37Z，完整changed-files=3。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`df3ae60bc3608c9743e01be26f079460162dfd39`；head：`d70728282ee7db8d4f9f79822693cd15c826df53`；merge：`3fa3d1fc223d6fd5a847f08c666169a39c7fff32`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`pymc3/tests/test_distributions_random.py`、`pymc3/tests/test_parallel_sampling.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_3846.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_3846.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_3846.json)。

## 行13050：S3FileTransformOperator has side effects on each instantiation, queries DB on each scheduler run

- 来源：[issue](https://github.com/apache/airflow/issues/1357)；当前API可访问：True；正文精确匹配：True。
- [PR#1371](https://github.com/apache/airflow/pull/1371)，合并于2016-04-14T07:00:53Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`96891596f9c392a9a477e5e564ea08a84095386b`；head：`19c0fac4db144ed4947af090b85089e4556889b3`；merge：`a8b533f12731648392c361af90a6d4f2b9309055`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_13050.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_13050.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_13050.json)。

## 行9051：Inference with a Dataset using pipeline in a tokenclassification job causes a ValueError("At least one input is required.")

- 来源：[issue](https://github.com/huggingface/transformers/issues/14301)；当前API可访问：True；正文精确匹配：True。
- [PR#14658](https://github.com/huggingface/transformers/pull/14658)，合并于2021-12-08T08:54:24Z，完整changed-files=5。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`b66c5ab20c8bb08d52cb840382498f936ea8da03`；head：`698946634c6f1765f26912bfe429e0a636121572`；merge：`2e12d90b9ed3005a3fa412566b899de2a229e033`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`tests/test_pipelines_common.py`、`tests/test_pipelines_table_question_answering.py`、`tests/test_pipelines_token_classification.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_9051.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_9051.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_9051.json)。

## 行2088：Can't infer TypeVar through lambda that returns None

- 来源：[issue](https://github.com/python/mypy/issues/6619)；当前API可访问：True；正文精确匹配：True。
- [PR#8562](https://github.com/python/mypy/pull/8562)，合并于2020-03-23T18:34:55Z，完整changed-files=2。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`11c6888ade536bad775c654a6d807bbaa141a789`；head：`4e028542a86b3c9ee6ed2f727c2661f13f5d3ceb`；merge：`60a7e0806df85071a7d3c7395a3834fe51aa35d8`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`test-data/unit/check-inference.test`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_2088.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_2088.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_2088.json)。

## 行11259：[V5] Failed with error on "Monthly Attendance Sheet"

- 来源：[issue](https://github.com/frappe/erpnext/issues/3402)；当前API可访问：True；正文精确匹配：True。
- [PR#3572](https://github.com/frappe/erpnext/pull/3572)，合并于2015-07-03T10:19:26Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`b7219dc698d2edf5f84e0879d6d64d453c6cc4fa`；head：`5a0fbff1a3088d0ab5b165e8958c43e0e211a8d2`；merge：`c24344e90ccd2165da277ae1573ff0020da5091f`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_11259.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_11259.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_11259.json)。

## 行17982：Gnu95FCompiler doesn't find libmingwex.a when using msvc + gfortran (Trac #2194)

- 来源：[issue](https://github.com/numpy/numpy/issues/647)；当前API可访问：True；正文精确匹配：True。
- [PR#7119](https://github.com/numpy/numpy/pull/7119)，合并于2016-01-31T20:51:29Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`471bab33bbfac24df42221b5c5739a190ca4018e`；head：`bce84bb6fbfc7d26b209fb38247b64f7faeb739f`；merge：`41ada49744b3d5542c412b8d8aa35a74f9e76dd6`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_17982.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_17982.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_17982.json)。

## 行18098：Worker memory chart is very jittery

- 来源：[issue](https://github.com/dask/distributed/issues/4872)；当前API可访问：True；正文精确匹配：True。
- [PR#4997](https://github.com/dask/distributed/pull/4997)，合并于2021-07-01T19:55:50Z，完整changed-files=1。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`b8b4ff81f4071b46453ecdee4bdc26b648139603`；head：`b6eb66dae7ce33275ee1be29d9deeac2541d6ffd`；merge：`8b79bd95d0c5a681f6d0543eb20d645dc1182ec1`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：未见；完整文件清单已核对。
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_18098.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_18098.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_18098.json)。

## 行36313：TypeError: BatchNormalization + Merge on GPU (ResNet)

- 来源：[issue](https://github.com/keras-team/keras/issues/4881)；当前API可访问：True；正文精确匹配：True。
- [PR#4917](https://github.com/keras-team/keras/pull/4917)，合并于2017-01-05T11:13:44Z，完整changed-files=2。关联级别：`targeted_merged_PR`。
- 核验理由：Merged PR explicitly targets source issue, or source discussion identifies the fix.
- PR base：`f6b804263a6e1d3ce6d2131cb9d758e1d7e57888`；head：`8852e90b5d7f86d8f1fa9e6740c178849a669fa9`；merge：`a6c9227372c607fc356b14e17c230cb9c1d5f589`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。
- 测试相关改动路径：`tests/keras/layers/test_normalization.py`
- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。
- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_36313.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_36313.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_36313.json)。
