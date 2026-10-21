# 独立外部验证：逐题逐臂分析

cohort=external；run=`20261021_external_nonthinking_v1`。同一instance_id横向对照，严格/部分/不可映射分列；未运行与失败不同。

## lincc-frameworks__nested-pandas-190

仓库：lincc-frameworks/nested-pandas；base：`77a816ddfef6489e599f8f463f0855c1e2f90882`；PR时间：2025-01-27 16:04:51；映射：fully_mappable。

gold文件：`src/nested_pandas/series/packer.py`。

可映射gold函数：`src/nested_pandas/series/packer.py::view_sorted_series_as_list_array`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 11.12 | 35359/472 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 26.98 | 84715/1112 | 10/10 | 10/3 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 26.93 | 1609/381 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 49.48 | 1609/381 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/nested_pandas/series/packer.py::view_sorted_series_as_list_array`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/lincc-frameworks__nested-pandas-190`。
- D-COSIL：`src/nested_pandas/series/packer.py::view_sorted_series_as_list_array`, `src/nested_pandas/series/packer.py::view_sorted_df_as_list_arrays`, `src/nested_pandas/series/ext_array.py::NestedExtensionArray.__arrow_array__`, `src/nested_pandas/series/ext_array.py::NestedExtensionArray.chunked_array`, `src/nested_pandas/series/packer.py::calculate_sorted_index_offsets`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/lincc-frameworks__nested-pandas-190`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/lincc-frameworks__nested-pandas-190`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/lincc-frameworks__nested-pandas-190`。

## tox-dev__tox-3846

仓库：tox-dev/tox；base：`ae05f2a33ccfe52ff22ac578ec6c8eb9f750ce4a`；PR时间：2026-03-03 15:34:23；映射：partially_mappable。

gold文件：`src/tox/tox_env/python/api.py`。

可映射gold函数：`src/tox/tox_env/python/api.py::Python.extract_base_python`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 11.08 | 35792/665 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 25.06 | 53883/1836 | 0/0 | 0/0 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 73.09 | 42692/959 | 3/10 | 3/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 73.12 | 46618/959 | 3/10 | 3/0 |

各臂预测与证据：

- D-SIMPLE：`src/tox/tox_env/python/api.py::Python.extract_base_python`, `src/tox/tox_env/python/api.py::Python._base_python_default`, `src/tox/tox_env/python/api.py::Python._validate_base_python`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/tox-dev__tox-3846`。
- D-COSIL：`src/tox/tox_env/python/api.py::Python.extract_base_python`, `src/tox/tox_env/python/api.py::Python._base_python_default`, `src/tox/config/loader/ini/factor.py::explode_factor`, `src/tox/config/loader/ini/factor.py::expand_factors`, `src/tox/tox_env/python/api.py::Python._validate_base_python`。解析失败10，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/tox-dev__tox-3846`。
- Q-COSIL：`None`, `None`, `src/tox/session/cmd/version_flag.py::get_version_info`, `None`, `None`。解析失败0，工具错误7，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/tox-dev__tox-3846`。
- Q-PRUNER：`None`, `None`, `src/tox/session/cmd/version_flag.py::get_version_info`, `None`, `None`。解析失败0，工具错误7，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/tox-dev__tox-3846`。

## yt-project__unyt-560

仓库：yt-project/unyt；base：`09fb30062e927744f8305b673a21322a21b91034`；PR时间：2025-02-06 18:24:16；映射：fully_mappable。

gold文件：`unyt/array.py`。

可映射gold函数：`unyt/array.py::unyt_array.from_hdf5`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 5.33 | 29027/162 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 21.95 | 63301/1623 | 7/7 | 7/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 86.14 | 78750/1152 | 5/10 | 5/3 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 87.60 | 78605/1132 | 5/10 | 5/3 |

各臂预测与证据：

- D-SIMPLE：`unyt/array.py::unyt_array.from_hdf5`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/yt-project__unyt-560`。
- D-COSIL：`unyt/array.py::unyt_array.from_hdf5`, `unyt/array.py::unyt_array.write_hdf5`, `unyt/array.py::unyt_quantity.__new__`, `unyt/array.py::unyt_array.__new__`, `unyt/array.py::unyt_quantity.reshape`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/yt-project__unyt-560`。
- Q-COSIL：`unyt/array.py::unyt_array.from_hdf5`, `None`, `None`, `unyt/_pint_conversions.py::convert_pint_units`。解析失败0，工具错误5，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/yt-project__unyt-560`。
- Q-PRUNER：`unyt/array.py::unyt_array.from_hdf5`, `None`, `None`, `unyt/_pint_conversions.py::convert_pint_units`。解析失败0，工具错误5，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/yt-project__unyt-560`。

## scverse__spatialdata-822

仓库：scverse/spatialdata；base：`54e7dd01648fdc149820a4506120efdc6197be6c`；PR时间：2025-01-08 23:22:10；映射：fully_mappable。

gold文件：`src/spatialdata/_core/query/relational_query.py`。

可映射gold函数：`src/spatialdata/_core/query/relational_query.py::_inner_join_spatialelement_table`, `src/spatialdata/_core/query/relational_query.py::_left_join_spatialelement_table`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.03 | 59742/698 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.00 | 93405/1495 | 0/0 | 0/0 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 35.19 | 3734/483 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 35.15 | 3734/483 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/spatialdata/_core/query/relational_query.py::_inner_join_spatialelement_table`, `src/spatialdata/_core/query/relational_query.py::_get_joined_table_indices`, `src/spatialdata/_core/query/relational_query.py::_match_rows`, `src/spatialdata/_core/query/relational_query.py::_left_join_spatialelement_table`, `src/spatialdata/_core/query/relational_query.py::_get_masked_element`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/scverse__spatialdata-822`。
- D-COSIL：`src/spatialdata/_core/query/relational_query.py::_inner_join_spatialelement_table`, `src/spatialdata/_core/query/relational_query.py::_get_joined_table_indices`, `src/spatialdata/_core/query/relational_query.py::_left_join_spatialelement_table`, `src/spatialdata/_core/query/relational_query.py::_right_join_spatialelement_table`, `src/spatialdata/_core/query/relational_query.py::_match_rows`。解析失败10，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/scverse__spatialdata-822`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/scverse__spatialdata-822`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/scverse__spatialdata-822`。

## openai__openai-agents-python-2144

仓库：openai/openai-agents-python；base：`509ddda77841ac1a6ce399e0d5fccde71a0a2f38`；PR时间：2025-12-03 19:21:23；映射：fully_mappable。

gold文件：`src/agents/extensions/models/litellm_model.py`。

可映射gold函数：`src/agents/extensions/models/litellm_model.py::LitellmModel._fetch_response`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.77 | 40763/721 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 19.12 | 63323/1832 | 0/0 | 0/0 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 22.60 | 2516/313 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 23.73 | 2516/313 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/agents/extensions/models/litellm_model.py::LitellmModel._fetch_response`, `src/agents/extensions/models/litellm_model.py::LitellmConverter.convert_message_to_openai`, `src/agents/models/chatcmpl_converter.py::Converter.message_to_output_items`, `src/agents/extensions/models/litellm_model.py::LitellmModel.get_response`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/openai__openai-agents-python-2144`。
- D-COSIL：`src/agents/extensions/models/litellm_model.py::LitellmModel._fetch_response`, `src/agents/models/chatcmpl_converter.py::Converter.maybe_reasoning_message`, `src/agents/extensions/models/litellm_model.py::LitellmModel.get_response`, `src/agents/models/chatcmpl_converter.py::Converter.message_to_output_items`, `src/agents/model_settings.py::ModelSettings.to_json_dict`。解析失败10，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/openai__openai-agents-python-2144`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/openai__openai-agents-python-2144`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/openai__openai-agents-python-2144`。

## omni-us__jsonargparse-707

仓库：omni-us/jsonargparse；base：`e90e8e088cfd006ca416dd4ad2df742f63d4fdd8`；PR时间：2025-04-16 05:25:35；映射：fully_mappable。

gold文件：`jsonargparse/_actions.py`。

可映射gold函数：`jsonargparse/_actions.py::ActionParser._move_parser_actions`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 6.75 | 18991/462 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | 0.00%/0.00% | 4.25 | 1080/810 | 0/0 | 0/0 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 18.81 | 1045/276 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 19.69 | 1045/276 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`jsonargparse/_core.py::ArgumentParser.instantiate_classes`, `None`, `None`, `jsonargparse/_link_arguments.py::ActionLink.apply_instantiation_links`, `jsonargparse/_cli.py::auto_cli`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/omni-us__jsonargparse-707`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/omni-us__jsonargparse-707`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/omni-us__jsonargparse-707`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/omni-us__jsonargparse-707`。

## scrapy__scrapy-6671

仓库：scrapy/scrapy；base：`00167edca0677fd9657a8c5995d30600dd37fe37`；PR时间：2025-02-13 13:41:48；映射：unmappable。

gold文件：`scrapy/spiders/sitemap.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 8.84 | 24687/807 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 27.35 | 49534/2269 | 8/8 | 8/6 |
| Q-COSIL | complete | 100.00% | NA/NA | 100.87 | 49260/1389 | 8/10 | 8/5 |
| Q-PRUNER | complete | 100.00% | NA/NA | 106.24 | 55633/1386 | 10/10 | 10/7 |

各臂预测与证据：

- D-SIMPLE：`scrapy/spiders/sitemap.py::SitemapSpider._parse_sitemap`, `scrapy/spiders/sitemap.py::SitemapSpider.start_requests`, `scrapy/spiders/sitemap.py::SitemapSpider.sitemap_filter`, `scrapy/spiders/crawl.py::CrawlSpider._parse`, `scrapy/spiders/crawl.py::CrawlSpider.parse_start_url`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/scrapy__scrapy-6671`。
- D-COSIL：`scrapy/spiders/sitemap.py::SitemapSpider._parse_sitemap`, `scrapy/spiders/crawl.py::CrawlSpider._parse_response`, `scrapy/spiders/crawl.py::CrawlSpider._requests_to_follow`, `scrapy/spiders/feed.py::XMLFeedSpider._parse`, `scrapy/spiders/crawl.py::CrawlSpider._parse`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/scrapy__scrapy-6671`。
- Q-COSIL：`scrapy/spiders/sitemap.py::SitemapSpider._parse_sitemap`, `scrapy/spiders/sitemap.py::SitemapSpider.sitemap_filter`, `scrapy/spiders/sitemap.py::SitemapSpider._get_sitemap_body`, `scrapy/spiders/sitemap.py::SitemapSpider.start_requests`, `scrapy/spiders/sitemap.py::SitemapSpider.from_crawler`。解析失败0，工具错误2，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/scrapy__scrapy-6671`。
- Q-PRUNER：`scrapy/spiders/sitemap.py::SitemapSpider._parse_sitemap`, `scrapy/spiders/sitemap.py::SitemapSpider._get_sitemap_body`, `scrapy/spiders/sitemap.py::SitemapSpider.sitemap_filter`, `None`, `None`。解析失败0，工具错误0，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/scrapy__scrapy-6671`。

## stefmolin__data-morph-265

仓库：stefmolin/data-morph；base：`9391f315ee8e19e51614c7b0702e44ac72cc1ff5`；PR时间：2025-02-12 03:09:03；映射：unmappable。

gold文件：`src/data_morph/shapes/factory.py`, `src/data_morph/shapes/points/__init__.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 7.65 | 8508/724 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 18.06 | 44745/992 | 6/6 | 6/1 |
| Q-COSIL | complete | 100.00% | NA/NA | 86.57 | 35002/1207 | 10/10 | 10/0 |
| Q-PRUNER | complete | 100.00% | NA/NA | 83.37 | 35356/1167 | 10/10 | 10/0 |

各臂预测与证据：

- D-SIMPLE：`src/data_morph/shapes/factory.py::ShapeFactory.generate_shape`, `src/data_morph/shapes/factory.py::ShapeFactory.plot_available_shapes`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/stefmolin__data-morph-265`。
- D-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败4，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/stefmolin__data-morph-265`。
- Q-COSIL：`src/data_morph/shapes/factory.py::ShapeFactory.generate_shape`, `src/data_morph/shapes/factory.py::ShapeFactory.plot_available_shapes`, `src/data_morph/morpher.py::DataMorpher.morph`, `src/data_morph/shapes/bases/shape.py::Shape.plot`, `src/data_morph/shapes/lines/diamond.py::Diamond.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/stefmolin__data-morph-265`。
- Q-PRUNER：`src/data_morph/shapes/factory.py::ShapeFactory.generate_shape`, `src/data_morph/shapes/factory.py::ShapeFactory.plot_available_shapes`, `src/data_morph/morpher.py::DataMorpher.morph`, `src/data_morph/shapes/bases/shape.py::Shape.plot`, `src/data_morph/shapes/lines/diamond.py::Diamond.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/stefmolin__data-morph-265`。

## django-guardian__django-guardian-904

仓库：django-guardian/django-guardian；base：`d9f15f2249ec75316723f34b3659ad0ff2822d91`；PR时间：2025-09-06 23:39:28；映射：fully_mappable。

gold文件：`guardian/core.py`。

可映射gold函数：`guardian/core.py::_get_pks_model_and_ctype`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.15 | 11271/201 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 17.90 | 42681/1333 | 2/3 | 2/2 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 102.78 | 42344/1468 | 6/10 | 6/2 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 102.84 | 46694/1411 | 8/10 | 8/4 |

各臂预测与证据：

- D-SIMPLE：`guardian/core.py::_get_pks_model_and_ctype`, `guardian/core.py::ObjectPermissionChecker.prefetch_perms`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/django-guardian__django-guardian-904`。
- D-COSIL：`guardian/core.py::_get_pks_model_and_ctype`, `guardian/core.py::ObjectPermissionChecker.prefetch_perms`, `guardian/core.py::ObjectPermissionChecker._prefetch_cache`, `guardian/core.py::ObjectPermissionChecker._init_obj_prefetch_cache`, `guardian/core.py::ObjectPermissionChecker.get_local_cache_key`。解析失败5，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/django-guardian__django-guardian-904`。
- Q-COSIL：`None`, `guardian/core.py::ObjectPermissionChecker.prefetch_perms`, `guardian/utils.py::get_group_obj_perms_model`, `guardian/utils.py::get_user_obj_perms_model`, `None`。解析失败0，工具错误4，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/django-guardian__django-guardian-904`。
- Q-PRUNER：`None`, `guardian/core.py::ObjectPermissionChecker.prefetch_perms`, `guardian/utils.py::get_obj_perm_model_by_conf`, `guardian/utils.py::get_group_obj_perms_model`, `guardian/utils.py::get_user_obj_perms_model`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/django-guardian__django-guardian-904`。

## vprusso__toqito-1538

仓库：vprusso/toqito；base：`396ba18ba1fa3e2b8d4eed682562a454d85f5c91`；PR时间：2026-04-22 15:23:30；映射：partially_mappable。

gold文件：`toqito/state_props/sandwiched_renyi_conditional_entropy.py`。

可映射gold函数：`toqito/state_props/sandwiched_renyi_conditional_entropy.py::sandwiched_renyi_conditional_entropy`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 10.39 | 29498/1011 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 18.61 | 63313/958 | 7/7 | 7/5 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 97.89 | 48384/1341 | 8/10 | 8/0 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 99.51 | 66278/1300 | 8/10 | 8/5 |

各臂预测与证据：

- D-SIMPLE：`toqito/state_props/sandwiched_renyi_conditional_entropy.py::sandwiched_renyi_conditional_entropy`, `toqito/state_props/sandwiched_renyi_conditional_entropy.py::_sandwiched_renyi_conditional_entropy_downarrow`, `toqito/state_props/petz_renyi_conditional_entropy.py::_petz_renyi_conditional_entropy_uparrow`, `toqito/state_props/petz_renyi_conditional_entropy.py::petz_renyi_conditional_entropy`, `toqito/state_props/_renyi_utils.py::psd_matrix_power`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/vprusso__toqito-1538`。
- D-COSIL：`toqito/state_props/sandwiched_renyi_conditional_entropy.py::sandwiched_renyi_conditional_entropy`, `toqito/state_props/sandwiched_renyi_conditional_entropy.py::_sandwiched_renyi_conditional_entropy_downarrow`, `None`, `toqito/state_props/_renyi_utils.py::validate_bipartite_dim`, `toqito/state_props/_renyi_utils.py::psd_matrix_power`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/vprusso__toqito-1538`。
- Q-COSIL：`toqito/state_props/sandwiched_renyi_conditional_entropy.py::sandwiched_renyi_conditional_entropy`, `None`, `toqito/matrix_ops/partial_trace.py::partial_trace`, `toqito/state_props/_renyi_utils.py::validate_bipartite_dim`, `toqito/state_props/_renyi_utils.py::psd_matrix_power`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/vprusso__toqito-1538`。
- Q-PRUNER：`toqito/state_props/sandwiched_renyi_conditional_entropy.py::sandwiched_renyi_conditional_entropy`, `toqito/state_props/sandwiched_renyi_conditional_entropy.py::_sandwiched_renyi_conditional_entropy_downarrow`, `toqito/matrix_ops/partial_trace.py::partial_trace`, `toqito/state_props/_renyi_utils.py::validate_bipartite_dim`, `toqito/state_props/_renyi_utils.py::psd_matrix_power`。解析失败0，工具错误2，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/vprusso__toqito-1538`。

## bluesky__ophyd-async-1164

仓库：bluesky/ophyd-async；base：`d381c3b434b8b1a38a1325920efda1f6666658ba`；PR时间：2025-12-16 11:08:19；映射：partially_mappable。

gold文件：`src/ophyd_async/epics/pmac/_pmac_trajectory.py`。

可映射gold函数：`src/ophyd_async/epics/pmac/_pmac_trajectory.py::PmacTrajectoryTriggerLogic._move_to_start`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.64 | 25860/554 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.34 | 52308/1401 | 10/10 | 10/3 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 72.21 | 46873/980 | 5/10 | 5/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 74.35 | 46613/955 | 5/10 | 5/0 |

各臂预测与证据：

- D-SIMPLE：`src/ophyd_async/epics/pmac/_pmac_trajectory.py::PmacTrajectoryTriggerLogic._move_to_start`, `src/ophyd_async/epics/pmac/_pmac_io.py::PmacCoordIO.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/bluesky__ophyd-async-1164`。
- D-COSIL：`src/ophyd_async/epics/pmac/_pmac_trajectory.py::PmacTrajectoryTriggerLogic._move_to_start`, `src/ophyd_async/epics/pmac/_pmac_trajectory.py::PmacTrajectoryTriggerLogic.prepare`, `None`, `None`, `src/ophyd_async/epics/pmac/_utils.py::calculate_ramp_position_and_duration`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/bluesky__ophyd-async-1164`。
- Q-COSIL：`src/ophyd_async/core/_device.py::Device.connect`, `None`, `None`, `None`, `None`。解析失败0，工具错误5，重复输入5，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/bluesky__ophyd-async-1164`。
- Q-PRUNER：`src/ophyd_async/core/_device.py::Device.connect`, `None`, `None`, `None`, `None`。解析失败0，工具错误5，重复输入5，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/bluesky__ophyd-async-1164`。

## getmoto__moto-9350

仓库：getmoto/moto；base：`5397d3a86f6f399d55b46a9835ff793ad426199b`；PR时间：2025-10-08 21:04:53；映射：partially_mappable。

gold文件：`moto/ec2/models/transit_gateway_attachments.py`, `moto/ec2/responses/transit_gateway_attachments.py`。

可映射gold函数：`moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachment.__init__`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.create_transit_gateway_peering_attachment`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.create_transit_gateway_vpc_attachment`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.create_transit_gateway_vpn_attachment`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayPeeringAttachment.__init__`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayVpcAttachment.__init__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 8.60 | 102638/885 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/16.67% | 43.37 | 91108/1518 | 6/6 | 6/6 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 155.70 | 76376/1795 | 7/10 | 7/3 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 170.77 | 74786/1740 | 7/10 | 7/2 |

各臂预测与证据：

- D-SIMPLE：`moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.describe_transit_gateway_attachments`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.describe_transit_gateway_attachments`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.set_attachment_association`, `moto/ec2/models/transit_gateway_route_tables.py::TransitGatewayRouteTableBackend.associate_transit_gateway_route_table`, `moto/ec2/models/transit_gateway_route_tables.py::TransitGatewayRouteTableBackend.set_route_table_association`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/getmoto__moto-9350`。
- D-COSIL：`moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.describe_transit_gateway_attachments`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.describe_transit_gateway_attachments`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachmentBackend.set_attachment_association`, `moto/ec2/models/transit_gateway_route_tables.py::TransitGatewayRouteTableBackend.associate_transit_gateway_route_table`, `moto/ec2/models/transit_gateway_attachments.py::TransitGatewayAttachment.__init__`。解析失败4，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/getmoto__moto-9350`。
- Q-COSIL：`moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.describe_transit_gateway_attachments`, `None`, `moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.associate_transit_gateway_route_table`, `None`, `moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.create_transit_gateway_peering_attachment`。解析失败0，工具错误3，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/getmoto__moto-9350`。
- Q-PRUNER：`moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.describe_transit_gateway_attachments`, `None`, `moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.associate_transit_gateway_route_table`, `moto/ec2/utils.py::random_transit_gateway_route_table_id`, `moto/ec2/responses/transit_gateway_attachments.py::TransitGatewayAttachment.disassociate_transit_gateway_route_table`。解析失败0，工具错误3，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/getmoto__moto-9350`。

## hkuds__openharness-217

仓库：HKUDS/OpenHarness；base：`1bcdc62a50db14c2f0bf5dbee05b2bdc369dffb3`；PR时间：2026-04-30 00:28:27；映射：partially_mappable。

gold文件：`src/openharness/auth/flows.py`。

可映射gold函数：`src/openharness/auth/flows.py::DeviceCodeFlow._try_open_browser`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.17 | 20827/271 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.06 | 74131/1142 | 6/6 | 6/5 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 103.43 | 54493/1404 | 3/4 | 3/2 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 104.50 | 54343/1395 | 3/4 | 3/2 |

各臂预测与证据：

- D-SIMPLE：`src/openharness/auth/flows.py::DeviceCodeFlow._try_open_browser`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/hkuds__openharness-217`。
- D-COSIL：`src/openharness/auth/flows.py::DeviceCodeFlow._try_open_browser`, `src/openharness/auth/flows.py::DeviceCodeFlow.run`, `src/openharness/api/copilot_auth.py::request_device_code`, `src/openharness/auth/flows.py::BrowserFlow.run`, `src/openharness/cli.py::_run_copilot_login`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/hkuds__openharness-217`。
- Q-COSIL：`src/openharness/auth/flows.py::DeviceCodeFlow._try_open_browser`, `None`, `src/openharness/auth/flows.py::BrowserFlow.run`, `None`, `None`。解析失败6，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/hkuds__openharness-217`。
- Q-PRUNER：`src/openharness/auth/flows.py::DeviceCodeFlow._try_open_browser`, `None`, `src/openharness/auth/flows.py::BrowserFlow.run`, `None`, `None`。解析失败6，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/hkuds__openharness-217`。

## collective__icalendar-921

仓库：collective/icalendar；base：`8e3d091c880a9465f5347204e3bc9a46774a277e`；PR时间：2025-10-19 06:59:58；映射：partially_mappable。

gold文件：`src/icalendar/prop/conference.py`。

可映射gold函数：`src/icalendar/prop/conference.py::Conference.to_uri`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.20 | 19843/235 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 18.46 | 46352/976 | 5/5 | 5/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 74.45 | 52630/1010 | 5/10 | 5/5 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 73.13 | 52075/980 | 5/10 | 5/5 |

各臂预测与证据：

- D-SIMPLE：`src/icalendar/prop/conference.py::Conference.to_uri`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/collective__icalendar-921`。
- D-COSIL：`src/icalendar/prop/conference.py::Conference.to_uri`, `src/icalendar/prop/conference.py::Conference.from_uri`, `None`, `src/icalendar/prop/__init__.py::vUri.__new__`, `src/icalendar/param.py::quoted_list_parameter`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/collective__icalendar-921`。
- Q-COSIL：`src/icalendar/prop/conference.py::Conference.to_uri`, `src/icalendar/attr.py::single_string_property`, `src/icalendar/attr.py::multi_text_property`, `None`, `None`。解析失败0，工具错误5，重复输入8，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/collective__icalendar-921`。
- Q-PRUNER：`src/icalendar/prop/conference.py::Conference.to_uri`, `src/icalendar/attr.py::single_string_property`, `src/icalendar/attr.py::multi_text_property`, `None`, `None`。解析失败0，工具错误5，重复输入8，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/collective__icalendar-921`。

## probabl-ai__skore-1335

仓库：probabl-ai/skore；base：`035e4f65d914d492ac75c387c7b227fb1ed9e1c2`；PR时间：2025-02-15 18:14:07；映射：fully_mappable。

gold文件：`skore/src/skore/sklearn/_plot/prediction_error.py`。

可映射gold函数：`skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay.plot`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.24 | 44175/637 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 21.07 | 82740/1779 | 8/8 | 8/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 156.18 | 57948/2211 | 8/10 | 8/0 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 154.33 | 57288/2166 | 8/10 | 8/0 |

各臂预测与证据：

- D-SIMPLE：`skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay.plot`, `skore/src/skore/sklearn/_plot/utils.py::_despine_matplotlib_axis`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/probabl-ai__skore-1335`。
- D-COSIL：`skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay.plot`, `skore/src/skore/sklearn/_plot/utils.py::_despine_matplotlib_axis`, `skore/src/skore/sklearn/_cross_validation/metrics_accessor.py::_MetricsAccessor.prediction_error`, `skore/src/skore/sklearn/_estimator/metrics_accessor.py::_MetricsAccessor.prediction_error`, `skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay._from_predictions`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/probabl-ai__skore-1335`。
- Q-COSIL：`skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay.plot`, `skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay._from_predictions`, `None`, `skore/src/skore/sklearn/_plot/utils.py::_ClassifierCurveDisplayMixin._validate_plot_params`, `skore/src/skore/sklearn/_base.py::_HelpMixin._get_help_legend`。解析失败0，工具错误2，重复输入3，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/probabl-ai__skore-1335`。
- Q-PRUNER：`skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay.plot`, `skore/src/skore/sklearn/_plot/prediction_error.py::PredictionErrorDisplay._from_predictions`, `None`, `skore/src/skore/sklearn/_plot/utils.py::_ClassifierCurveDisplayMixin._validate_plot_params`, `skore/src/skore/sklearn/_base.py::_HelpMixin._get_help_legend`。解析失败0，工具错误2，重复输入3，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/probabl-ai__skore-1335`。

## dag-hammarskjold-library__dlx-512

仓库：dag-hammarskjold-library/dlx；base：`117817f3321b71ef5061a84aaf99877f514ecb1c`；PR时间：2025-03-03 18:49:04；映射：fully_mappable。

gold文件：`dlx/marc/query.py`。

可映射gold函数：`dlx/marc/query.py::Query.from_string.parse`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 5.93 | 16625/257 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 27.45 | 90499/1911 | 6/6 | 6/3 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 15.87 | 432/230 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 15.38 | 432/230 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`dlx/marc/query.py::Query.from_string`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/dag-hammarskjold-library__dlx-512`。
- D-COSIL：`dlx/marc/query.py::Query.from_string`, `dlx/marc/query.py::TagOnly.compile`, `dlx/marc/query.py::Condition.compile`, `dlx/marc/query.py::WildcardRegex.__init__`, `dlx/marc/query.py::Text.compile`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/dag-hammarskjold-library__dlx-512`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/dag-hammarskjold-library__dlx-512`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/dag-hammarskjold-library__dlx-512`。

## schemathesis__schemathesis-3405

仓库：schemathesis/schemathesis；base：`736305e2a7a9c7596bed33f60635edff18671211`；PR时间：2025-12-10 12:36:40；映射：fully_mappable。

gold文件：`src/schemathesis/specs/openapi/examples.py`。

可映射gold函数：`src/schemathesis/specs/openapi/examples.py::extract_from_schema`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 9.59 | 91454/1023 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 23.45 | 67035/1771 | 8/8 | 7/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 25.08 | 1706/351 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 43.92 | 1706/351 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/schemathesis/specs/openapi/converter.py::_to_json_schema`, `src/schemathesis/specs/openapi/_hypothesis.py::make_positive_strategy`, `src/schemathesis/specs/openapi/_hypothesis.py::_get_body_strategy`, `src/schemathesis/specs/openapi/_hypothesis.py::openapi_cases`, `src/schemathesis/core/jsonschema/references.py::_sanitize_combinators`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/schemathesis__schemathesis-3405`。
- D-COSIL：`src/schemathesis/specs/openapi/converter.py::_to_json_schema`, `src/schemathesis/specs/openapi/converter.py::ensure_required_properties`, `src/schemathesis/specs/openapi/_hypothesis.py::make_positive_strategy`, `src/schemathesis/specs/openapi/converter.py::rewrite_properties`, `src/schemathesis/specs/openapi/_hypothesis.py::_get_body_strategy`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/schemathesis__schemathesis-3405`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/schemathesis__schemathesis-3405`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/schemathesis__schemathesis-3405`。

## tobymao__sqlglot-4563

仓库：tobymao/sqlglot；base：`795e7e0e857486417ce98246389849fc09ccb60a`；PR时间：2025-01-05 13:49:45；映射：unmappable。

gold文件：`sqlglot/dialects/tsql.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 7.05 | 75099/266 | 0/0 | 0/0 |
| D-COSIL | budget_exceeded | 0.00% | NA/NA | 28.32 | 368040/1417 | 5/6 | 5/3 |
| Q-COSIL | failed | 0.00% | NA/NA | 247.94 | 31618/2499 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | NA/NA | 257.18 | 31618/2499 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/tobymao__sqlglot-4563`。
- D-COSIL：空。解析失败2，工具错误1，重复输入0，agent未收到源码仍定位=False；400000 token cap。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/tobymao__sqlglot-4563`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/tobymao__sqlglot-4563`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/tobymao__sqlglot-4563`。

## koxudaxi__datamodel-code-generator-2998

仓库：koxudaxi/datamodel-code-generator；base：`2b659f001e744e1e95e464ab0d613fae0122bc01`；PR时间：2026-02-14 06:35:10；映射：fully_mappable。

gold文件：`src/datamodel_code_generator/parser/base.py`。

可映射gold函数：`src/datamodel_code_generator/parser/base.py::Parser.__change_from_import`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 9.20 | 91908/924 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 27.38 | 160866/1481 | 9/9 | 9/8 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 44.55 | 1928/432 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 33.97 | 1928/432 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/koxudaxi__datamodel-code-generator-2998`。
- D-COSIL：`src/datamodel_code_generator/parser/jsonschema.py::JsonSchemaParser._merge_all_of_object`, `src/datamodel_code_generator/parser/jsonschema.py::JsonSchemaParser.parse_all_of`, `src/datamodel_code_generator/parser/jsonschema.py::JsonSchemaParser._parse_all_of_item`, `src/datamodel_code_generator/parser/jsonschema.py::JsonSchemaParser._parse_object_common_part`, `src/datamodel_code_generator/reference.py::ModelResolver.add_ref`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/koxudaxi__datamodel-code-generator-2998`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/koxudaxi__datamodel-code-generator-2998`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/koxudaxi__datamodel-code-generator-2998`。

## pandas-dev__pandas-60691

仓库：pandas-dev/pandas；base：`0110487d4bccf3f7498c22a71e6a0dfdb3be3a16`；PR时间：2025-01-10 06:21:42；映射：fully_mappable。

gold文件：`pandas/core/array_algos/replace.py`。

可映射gold函数：`pandas/core/array_algos/replace.py::compare_or_regex_search`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.36 | 114093/659 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 45.60 | 182914/1917 | 6/6 | 6/6 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 132.00 | 101703/1469 | 1/3 | 1/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 154.22 | 101644/1464 | 1/3 | 1/0 |

各臂预测与证据：

- D-SIMPLE：`pandas/core/array_algos/replace.py::compare_or_regex_search`, `pandas/core/array_algos/replace.py::replace_regex`, `pandas/core/internals/blocks.py::Block.replace_list`, `pandas/core/internals/blocks.py::Block._replace_regex`, `pandas/core/internals/blocks.py::Block._replace_coerce`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/pandas-dev__pandas-60691`。
- D-COSIL：`pandas/core/array_algos/replace.py::compare_or_regex_search`, `pandas/core/array_algos/replace.py::replace_regex`, `pandas/core/internals/blocks.py::Block._replace_regex`, `pandas/core/internals/blocks.py::Block.replace`, `pandas/core/internals/managers.py::BaseBlockManager.replace_regex`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/pandas-dev__pandas-60691`。
- Q-COSIL：`None`, `pandas/core/arrays/string_.py::StringArray.astype`, `None`, `pandas/core/frame.py::DataFrame.__getitem__`, `None`。解析失败7，工具错误2，重复输入1，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/pandas-dev__pandas-60691`。
- Q-PRUNER：`None`, `pandas/core/arrays/string_.py::StringArray.astype`, `None`, `pandas/core/frame.py::DataFrame.__getitem__`, `None`。解析失败7，工具错误2，重复输入1，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/pandas-dev__pandas-60691`。

## serge-sans-paille__beniget-121

仓库：serge-sans-paille/beniget；base：`6a4605a48591a9d2b0e65493edfe3b690b1a1271`；PR时间：2025-01-28 18:17:00；映射：unmappable。

gold文件：`beniget/beniget.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 6.56 | 16914/258 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 26.03 | 89207/1345 | 10/10 | 10/4 |
| Q-COSIL | complete | 100.00% | NA/NA | 118.72 | 57010/1606 | 5/5 | 5/0 |
| Q-PRUNER | complete | 100.00% | NA/NA | 120.06 | 57566/1586 | 5/5 | 5/0 |

各臂预测与证据：

- D-SIMPLE：`beniget/beniget.py::DefUseChains.__init__`, `beniget/beniget.py::DefUseChains.visit_Module`, `beniget/beniget.py::DefUseChains.compute_defs`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/serge-sans-paille__beniget-121`。
- D-COSIL：`beniget/beniget.py::DefUseChains.__init__`, `beniget/beniget.py::DefUseChains.visit_Module`, `beniget/beniget.py::DefUseChains.compute_defs`, `beniget/beniget.py::DefUseChains.unbound_identifier`, `beniget/beniget.py::DefUseChains.visit_Name`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/serge-sans-paille__beniget-121`。
- Q-COSIL：`beniget/beniget.py::DefUseChains.unbound_identifier`, `beniget/beniget.py::DefUseChains.warn`, `beniget/beniget.py::DefUseChains.invalid_name_lookup`, `None`, `beniget/beniget.py::DefUseChains._support_stdlib`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/serge-sans-paille__beniget-121`。
- Q-PRUNER：`beniget/beniget.py::DefUseChains.unbound_identifier`, `beniget/beniget.py::DefUseChains.warn`, `beniget/beniget.py::DefUseChains.invalid_name_lookup`, `None`, `beniget/beniget.py::DefUseChains._support_stdlib`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/serge-sans-paille__beniget-121`。

## BerriAI__litellm-15753

仓库：BerriAI/litellm；base：`5ce2be732e9b69a94f08a2bfc654f3c355e58747`；PR时间：2025-10-21 00:28:04；映射：partially_mappable。

gold文件：`litellm/responses/litellm_completion_transformation/transformation.py`, `litellm/types/llms/openai.py`。

可映射gold函数：`litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig._extract_message_output_items`, `litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig._extract_reasoning_output_items`, `litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig.transform_chat_completion_response_to_responses_api_response`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.91 | 99704/1054 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/66.67% | 42.21 | 94797/1463 | 6/6 | 6/5 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 24.20 | 9608/251 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 38.73 | 9608/251 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig._extract_message_output_items`, `litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig._extract_reasoning_output_items`, `litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig.transform_chat_completion_response_to_responses_api_response`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/BerriAI__litellm-15753`。
- D-COSIL：`litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig._extract_message_output_items`, `litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig.transform_chat_completion_response_to_responses_api_response`, `litellm/responses/litellm_completion_transformation/transformation.py::LiteLLMCompletionResponsesConfig._transform_chat_completion_choices_to_responses_output`, `litellm/responses/litellm_completion_transformation/streaming_iterator.py::LiteLLMCompletionStreamingIterator._emit_response_completed_event`, `None`。解析失败4，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/BerriAI__litellm-15753`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/BerriAI__litellm-15753`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/BerriAI__litellm-15753`。

## pallets-eco__wtforms-892_interface

仓库：pallets-eco/wtforms；base：`22fb0dc9cc57327e5a7ce620f59d7f6da1788343`；PR时间：2026-05-03 13:17:49；映射：unmappable。

gold文件：`src/wtforms/__init__.py`, `src/wtforms/fields/__init__.py`, `src/wtforms/fields/simple.py`, `src/wtforms/widgets/__init__.py`, `src/wtforms/widgets/core.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 7.44 | 17398/445 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 23.13 | 61486/1201 | 9/9 | 9/1 |
| Q-COSIL | complete | 100.00% | NA/NA | 53.97 | 64043/719 | 0/10 | 0/0 |
| Q-PRUNER | complete | 100.00% | NA/NA | 54.74 | 64043/719 | 0/10 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/wtforms/widgets/core.py::SubmitInput.__call__`, `src/wtforms/widgets/core.py::Input.__call__`, `None`, `src/wtforms/widgets/core.py::html_params`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/pallets-eco__wtforms-892_interface`。
- D-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/pallets-eco__wtforms-892_interface`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误10，重复输入9，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/pallets-eco__wtforms-892_interface`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误10，重复输入9，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/pallets-eco__wtforms-892_interface`。

## quantumlib__ReCirq-410

仓库：quantumlib/ReCirq；base：`3e0ed4e40900841d244fe06ff0b846af4a3a3403`；PR时间：2025-08-01 18:03:54+00:00；映射：partially_mappable。

gold文件：`recirq/documentation_utils.py`。

可映射gold函数：`recirq/documentation_utils.py::fetch_guide_data_collection_data`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.75 | 33189/173 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 14.96 | 27108/990 | 5/5 | 5/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 86.74 | 59757/1141 | 10/10 | 10/1 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 82.43 | 59926/1093 | 10/10 | 10/1 |

各臂预测与证据：

- D-SIMPLE：`recirq/documentation_utils.py::fetch_guide_data_collection_data`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/quantumlib__ReCirq-410`。
- D-COSIL：`recirq/documentation_utils.py::fetch_guide_data_collection_data`, `None`, `recirq/documentation_utils.py::display_markdown_docstring`, `None`, `None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/quantumlib__ReCirq-410`。
- Q-COSIL：`recirq/documentation_utils.py::fetch_guide_data_collection_data`, `None`, `recirq/serialization_utils.py::load_records`, `None`, `recirq/hfvqe/util.py::generate_fswap_pairs`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/quantumlib__ReCirq-410`。
- Q-PRUNER：`recirq/documentation_utils.py::fetch_guide_data_collection_data`, `None`, `recirq/serialization_utils.py::load_records`, `None`, `recirq/hfvqe/util.py::generate_fswap_pairs`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/quantumlib__ReCirq-410`。

## hynek__svcs-140

仓库：hynek/svcs；base：`f8585ce9f8fe6df9da4cf405cec1e03f4708be26`；PR时间：2025-09-10 14:10:27；映射：partially_mappable。

gold文件：`src/svcs/_core.py`。

可映射gold函数：`src/svcs/_core.py::Container.get`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.67 | 16469/167 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 17.31 | 69882/1049 | 5/5 | 3/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 60.06 | 62036/793 | 7/10 | 3/1 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 31.65 | 8185/451 | 1/1 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/svcs/_core.py::Container.get`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/hynek__svcs-140`。
- D-COSIL：`src/svcs/_core.py::Container.get`, `src/svcs/_core.py::Container.aget`, `src/svcs/_core.py::Container._lookup`, `src/svcs/_core.py::Container.get_abstract`, `src/svcs/_core.py::Container.aget_abstract`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/hynek__svcs-140`。
- Q-COSIL：`src/svcs/_core.py::Container.get`, `None`, `src/svcs/_core.py::Container.register_local_factory`, `None`, `src/svcs/_core.py::Container.register_local_value`。解析失败0，工具错误3，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/hynek__svcs-140`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；Cannot bind exact source function。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/hynek__svcs-140`。

## Lightning-AI__litdata-461

仓库：Lightning-AI/litdata；base：`a147df6066923a88323ceb2cba977990d03f09d1`；PR时间：2025-02-04 06:08:14；映射：fully_mappable。

gold文件：`src/litdata/streaming/client.py`。

可映射gold函数：`src/litdata/streaming/client.py::S3Client._create_client`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.66 | 24389/798 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 21.13 | 55869/1618 | 6/6 | 6/6 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 110.20 | 71432/1515 | 9/10 | 9/5 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 110.52 | 73798/1471 | 10/10 | 10/9 |

各臂预测与证据：

- D-SIMPLE：`src/litdata/streaming/client.py::S3Client.client`, `src/litdata/streaming/client.py::S3Client._create_client`, `src/litdata/streaming/downloader.py::S3Downloader.download_file`, `src/litdata/streaming/downloader.py::Downloader.download_chunk_from_index`, `src/litdata/streaming/config.py::ChunksConfig.download_chunk_from_index`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/Lightning-AI__litdata-461`。
- D-COSIL：`src/litdata/streaming/client.py::S3Client._create_client`, `src/litdata/streaming/client.py::S3Client.client`, `src/litdata/streaming/client.py::S3Client.__init__`, `src/litdata/streaming/downloader.py::S3Downloader.download_file`, `src/litdata/streaming/downloader.py::Downloader.download_chunk_from_index`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/Lightning-AI__litdata-461`。
- Q-COSIL：`src/litdata/streaming/client.py::S3Client._create_client`, `src/litdata/streaming/downloader.py::Downloader.download_chunk_from_index`, `None`, `src/litdata/streaming/dataloader.py::StreamingDataLoader.__iter__`, `src/litdata/streaming/dataset.py::StreamingDataset.__getitem__`。解析失败0，工具错误1，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/Lightning-AI__litdata-461`。
- Q-PRUNER：`src/litdata/streaming/client.py::S3Client._create_client`, `src/litdata/streaming/downloader.py::Downloader.download_chunk_from_index`, `None`, `src/litdata/streaming/dataloader.py::StreamingDataLoader.__iter__`, `src/litdata/streaming/dataloader.py::_MultiProcessingDataLoaderIterPatch._next_data`。解析失败0，工具错误0，重复输入5，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/Lightning-AI__litdata-461`。

## pymc-devs__pymc-7858

仓库：pymc-devs/pymc；base：`f34eb2605afac335b75561a8c1e56642ef440958`；PR时间：2025-07-20 11:06:00+00:00；映射：partially_mappable。

gold文件：`pymc/pytensorf.py`。

可映射gold函数：`pymc/pytensorf.py::PointFunc.__getattr__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 100.00%/100.00% | 7.60 | 35298/474 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 23.15 | 62443/1144 | 10/10 | 10/1 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 129.91 | 57027/1775 | 9/10 | 9/1 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 130.17 | 56567/1719 | 8/10 | 8/0 |

各臂预测与证据：

- D-SIMPLE：`pymc/pytensorf.py::PointFunc.__getattr__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/pymc-devs__pymc-7858`。
- D-COSIL：`None`, `pymc/sampling/parallel.py::_Process._unpickle_step_method`, `pymc/step_methods/metropolis.py::CategoricalGibbsMetropolis.__init__`, `pymc/step_methods/arraystep.py::ArrayStepShared.__init__`, `pymc/sampling/mcmc.py::_mp_sample`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/pymc-devs__pymc-7858`。
- Q-COSIL：`pymc/step_methods/arraystep.py::ArrayStep.step`, `pymc/step_methods/compound.py::CompoundStep.step`, `pymc/step_methods/hmc/base_hmc.py::BaseHMC._hamiltonian_step`, `pymc/step_methods/hmc/nuts.py::NUTS._hamiltonian_step`, `pymc/sampling/parallel.py::_Process._unpickle_step_method`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/pymc-devs__pymc-7858`。
- Q-PRUNER：`None`, `pymc/step_methods/compound.py::CompoundStep.__init__`, `pymc/step_methods/hmc/base_hmc.py::BaseHMC.__init__`, `pymc/step_methods/hmc/nuts.py::NUTS.__init__`, `pymc/sampling/parallel.py::_Process._unpickle_step_method`。解析失败0，工具错误2，重复输入1，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/pymc-devs__pymc-7858`。

## hdmf-dev__hdmf-1374

仓库：hdmf-dev/hdmf；base：`a21f308c40f5fb35505120aeae12ef43a2b9672a`；PR时间：2026-01-09 23:03:31；映射：partially_mappable。

gold文件：`src/hdmf/spec/namespace.py`。

可映射gold函数：`src/hdmf/spec/namespace.py::NamespaceCatalog.__register_dependent_types`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__register_dependent_types.__register_dependent_types_helper`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__register_type`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/66.67% | 7.47 | 43480/709 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/66.67% | 24.78 | 92890/1921 | 5/5 | 5/3 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 69.43 | 64125/929 | 0/10 | 0/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 70.22 | 64125/929 | 0/10 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/hdmf/spec/namespace.py::NamespaceCatalog.__register_dependent_types`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__register_type`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__load_namespace`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__resolve_includes`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__load_spec_file`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/hdmf-dev__hdmf-1374`。
- D-COSIL：`src/hdmf/spec/namespace.py::NamespaceCatalog.__register_type`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__register_dependent_types`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__load_namespace`, `src/hdmf/spec/namespace.py::NamespaceCatalog.load_namespaces`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__resolve_includes`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/hdmf-dev__hdmf-1374`。
- Q-COSIL：`None`, `None`, `src/hdmf/spec/namespace.py::NamespaceCatalog.load_namespaces`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__resolve_includes`, `src/hdmf/common/__init__.py::load_namespaces`。解析失败0，工具错误10，重复输入9，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/hdmf-dev__hdmf-1374`。
- Q-PRUNER：`None`, `None`, `src/hdmf/spec/namespace.py::NamespaceCatalog.load_namespaces`, `src/hdmf/spec/namespace.py::NamespaceCatalog.__resolve_includes`, `src/hdmf/common/__init__.py::load_namespaces`。解析失败0，工具错误10，重复输入9，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/hdmf-dev__hdmf-1374`。

## jlowin__fastmcp-1011

仓库：jlowin/fastmcp；base：`a3f22e7aa0116011c37e28e0866276e5f91ada2d`；PR时间：2025-07-02 04:53:24+00:00；映射：partially_mappable。

gold文件：`src/fastmcp/cli/cli.py`, `src/fastmcp/cli/run.py`, `src/fastmcp/server/server.py`, `src/fastmcp/utilities/cli.py`。

可映射gold函数：`src/fastmcp/cli/cli.py::_build_uv_command`, `src/fastmcp/cli/cli.py::dev`, `src/fastmcp/cli/cli.py::run`, `src/fastmcp/cli/run.py::run_command`, `src/fastmcp/server/server.py::FastMCP.run`, `src/fastmcp/server/server.py::FastMCP.run_async`, `src/fastmcp/server/server.py::FastMCP.run_http_async`, `src/fastmcp/server/server.py::FastMCP.run_stdio_async`, `src/fastmcp/utilities/cli.py::print_server_banner`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/55.56% | 7.99 | 40966/806 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/55.56% | 27.18 | 67561/1938 | 9/9 | 9/6 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 25.44 | 1451/371 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 26.99 | 1451/371 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/fastmcp/server/server.py::FastMCP.run_stdio_async`, `src/fastmcp/server/server.py::FastMCP.run_async`, `src/fastmcp/server/server.py::FastMCP.run`, `src/fastmcp/cli/run.py::run_command`, `src/fastmcp/cli/cli.py::run`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/jlowin__fastmcp-1011`。
- D-COSIL：`src/fastmcp/server/server.py::FastMCP.run_stdio_async`, `src/fastmcp/server/server.py::FastMCP.run_async`, `src/fastmcp/server/server.py::FastMCP.run`, `src/fastmcp/cli/run.py::run_command`, `src/fastmcp/server/server.py::FastMCP.run_http_async`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/jlowin__fastmcp-1011`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/jlowin__fastmcp-1011`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/jlowin__fastmcp-1011`。

## deepset-ai__haystack-8879

仓库：deepset-ai/haystack；base：`de3d0a23e816d54717a7542a9a1a1f2eb7a7eaec`；PR时间：2025-02-19 15:22:04；映射：fully_mappable。

gold文件：`haystack/components/generators/chat/openai.py`。

可映射gold函数：`haystack/components/generators/chat/openai.py::OpenAIChatGenerator._convert_streaming_chunks_to_chat_message`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.49 | 73330/702 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 24.16 | 60876/1567 | 5/5 | 5/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 100.64 | 53465/1336 | 10/10 | 10/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 104.23 | 54664/1286 | 10/10 | 10/0 |

各臂预测与证据：

- D-SIMPLE：`haystack/components/generators/chat/openai.py::OpenAIChatGenerator._convert_streaming_chunks_to_chat_message`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator._handle_stream_response`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator._convert_chat_completion_chunk_to_streaming_chunk`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator.run`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator._prepare_api_call`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/deepset-ai__haystack-8879`。
- D-COSIL：`haystack/components/generators/chat/openai.py::OpenAIChatGenerator._convert_streaming_chunks_to_chat_message`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator._convert_chat_completion_chunk_to_streaming_chunk`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator._handle_stream_response`, `None`, `haystack/components/generators/chat/openai.py::OpenAIChatGenerator._prepare_api_call`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/deepset-ai__haystack-8879`。
- Q-COSIL：`haystack/core/pipeline/base.py::PipelineBase._consume_component_inputs`, `haystack/core/pipeline/base.py::PipelineBase._fill_queue`, `haystack/core/pipeline/base.py::PipelineBase._write_component_outputs`, `haystack/dataclasses/chat_message.py::ChatMessage.tool_call_results`, `haystack/core/pipeline/base.py::PipelineBase._validate_input`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/deepset-ai__haystack-8879`。
- Q-PRUNER：`haystack/core/pipeline/base.py::PipelineBase._consume_component_inputs`, `haystack/core/pipeline/base.py::PipelineBase._fill_queue`, `haystack/core/pipeline/base.py::PipelineBase._write_component_outputs`, `haystack/dataclasses/chat_message.py::ChatMessage.tool_call_results`, `haystack/core/pipeline/base.py::PipelineBase._validate_input`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/deepset-ai__haystack-8879`。

## scipp__plopp-422

仓库：scipp/plopp；base：`239103c412e27e47867033ade0c2aaf07574ef6e`；PR时间：2025-03-10 09:41:34；映射：partially_mappable。

gold文件：`src/plopp/core/limits.py`。

可映射gold函数：`src/plopp/core/limits.py::find_limits`, `src/plopp/core/limits.py::fix_empty_range`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.99 | 22754/562 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 19.15 | 47786/1843 | 5/5 | 5/5 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 3.68 | 1403/49 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 4.14 | 1403/49 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/plopp/core/limits.py::fix_empty_range`, `src/plopp/core/limits.py::find_limits`, `src/plopp/graphics/bbox.py::axis_bounds`, `src/plopp/backends/common.py::make_line_bbox`, `src/plopp/backends/matplotlib/line.py::Line.bbox`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/scipp__plopp-422`。
- D-COSIL：`src/plopp/core/limits.py::fix_empty_range`, `src/plopp/graphics/bbox.py::axis_bounds`, `src/plopp/core/limits.py::find_limits`, `src/plopp/backends/common.py::make_line_bbox`, `src/plopp/backends/matplotlib/line.py::Line.bbox`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/scipp__plopp-422`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/scipp__plopp-422`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/scipp__plopp-422`。

## cubed-dev__cubed-799

仓库：cubed-dev/cubed；base：`de56acf751e5bf41bf2159466bb2fdc1bb89b3f0`；PR时间：2025-09-09 15:30:19；映射：partially_mappable。

gold文件：`cubed/core/ops.py`, `cubed/core/plan.py`, `cubed/primitive/blockwise.py`, `cubed/storage/backend.py`。

可映射gold函数：`cubed/core/ops.py::_general_blockwise`, `cubed/core/ops.py::store`, `cubed/core/ops.py::to_zarr`, `cubed/core/plan.py::Plan.visualize`, `cubed/primitive/blockwise.py::general_blockwise`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/40.00% | 7.52 | 12725/945 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 23.31 | 39766/1562 | 9/9 | 9/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 19.93 | 787/296 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 26.77 | 787/296 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`cubed/core/ops.py::store`, `cubed/core/ops.py::to_zarr`, `cubed/icechunk.py::store_icechunk`, `cubed/storage/zarr.py::LazyZarrArray.create`, `cubed/storage/zarr.py::LazyZarrArray.open`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/cubed-dev__cubed-799`。
- D-COSIL：`cubed/storage/backend.py::open_backend_array`, `cubed/icechunk.py::store_icechunk`, `cubed/storage/backends/zarr_python.py::ZarrArrayGroup.set_basic_selection`, `cubed/storage/backends/zarr_python_v3.py::ZarrV3ArrayGroup.set_basic_selection`, `cubed/storage/backends/zarr_python.py::open_zarr_array`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/cubed-dev__cubed-799`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/cubed-dev__cubed-799`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/cubed-dev__cubed-799`。

## raullenchai__rapid-mlx-289

仓库：raullenchai/Rapid-MLX；base：`67c49b5bec9a049e361785090a20a17f6085886d`；PR时间：2026-05-07 19:33:12；映射：fully_mappable。

gold文件：`vllm_mlx/reasoning/gemma4_parser.py`。

可映射gold函数：`vllm_mlx/reasoning/gemma4_parser.py::Gemma4ReasoningParser.extract_reasoning_streaming`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.65 | 60597/960 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 26.98 | 155891/1310 | 8/8 | 8/4 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 24.64 | 6045/315 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 31.04 | 6045/315 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`vllm_mlx/reasoning/gemma4_parser.py::Gemma4ReasoningParser.extract_reasoning_streaming`, `vllm_mlx/reasoning/harmony_parser.py::HarmonyReasoningParser.extract_reasoning_streaming`, `vllm_mlx/reasoning/minimax_parser.py::MiniMaxReasoningParser.extract_reasoning_streaming`, `vllm_mlx/reasoning/deepseek_r1_parser.py::DeepSeekR1ReasoningParser.extract_reasoning_streaming`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/raullenchai__rapid-mlx-289`。
- D-COSIL：`vllm_mlx/reasoning/gemma4_parser.py::Gemma4ReasoningParser.extract_reasoning_streaming`, `vllm_mlx/reasoning/harmony_parser.py::HarmonyReasoningParser.extract_reasoning_streaming`, `vllm_mlx/reasoning/deepseek_r1_parser.py::DeepSeekR1ReasoningParser.extract_reasoning_streaming`, `vllm_mlx/reasoning/minimax_parser.py::MiniMaxReasoningParser.extract_reasoning_streaming`, `None`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/raullenchai__rapid-mlx-289`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/raullenchai__rapid-mlx-289`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/raullenchai__rapid-mlx-289`。

## oracle__macaron-1136

仓库：oracle/macaron；base：`5f8a6527f128519752aab4b156d1690face571ec`；PR时间：2025-08-01 05:31:57+00:00；映射：fully_mappable。

gold文件：`src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py`。

可映射gold函数：`src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer._load_defaults`, `src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer.analyze`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.22 | 98336/663 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/50.00% | 28.56 | 198914/2742 | 6/6 | 6/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 116.52 | 218198/1304 | 7/10 | 7/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 118.72 | 159822/1418 | 2/2 | 2/2 |

各臂预测与证据：

- D-SIMPLE：`src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer._load_defaults`, `src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer.__init__`, `src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer.analyze`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/oracle__macaron-1136`。
- D-COSIL：`src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer._load_defaults`, `None`, `None`, `None`, `src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer.__init__`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/oracle__macaron-1136`。
- Q-COSIL：`src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer._load_defaults`, `src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer.analyze`, `None`, `src/macaron/config/global_config.py::GlobalConfig.load`, `src/macaron/util.py::send_get_http`。解析失败0，工具错误3，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/oracle__macaron-1136`。
- Q-PRUNER：`src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer._load_defaults`, `src/macaron/malware_analyzer/pypi_heuristics/sourcecode/pypi_sourcecode_analyzer.py::PyPISourcecodeAnalyzer.analyze`, `None`, `src/macaron/config/global_config.py::GlobalConfig.load`, `src/macaron/util.py::send_get_http`。解析失败8，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/oracle__macaron-1136`。

## cal-itp__benefits-3330

仓库：cal-itp/benefits；base：`2949c7d90b91830543d0a69c1bcbff8ddfcddc86`；PR时间：2025-11-20 18:02:03；映射：partially_mappable。

gold文件：`benefits/enrollment_littlepay/enrollment.py`。

可映射gold函数：`benefits/enrollment_littlepay/enrollment.py::enroll`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.50 | 25154/592 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.65 | 56748/1735 | 8/8 | 8/4 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 161.15 | 56674/2147 | 8/10 | 8/1 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 153.40 | 57390/2103 | 7/10 | 7/2 |

各臂预测与证据：

- D-SIMPLE：`benefits/enrollment_littlepay/enrollment.py::enroll`, `benefits/enrollment/enrollment.py::handle_enrollment_results`, `benefits/enrollment_littlepay/views.py::IndexView.form_valid`, `benefits/enrollment_littlepay/enrollment.py::_get_group_funding_source`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/cal-itp__benefits-3330`。
- D-COSIL：`benefits/enrollment_littlepay/enrollment.py::_get_group_funding_source`, `benefits/enrollment_littlepay/enrollment.py::enroll`, `benefits/enrollment/enrollment.py::handle_enrollment_results`, `benefits/enrollment_littlepay/views.py::IndexView.form_valid`, `benefits/enrollment_littlepay/enrollment.py::request_card_tokenization_access`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/cal-itp__benefits-3330`。
- Q-COSIL：`benefits/enrollment_littlepay/views.py::IndexView.form_valid`, `None`, `benefits/core/mixins.py::AgencySessionRequiredMixin.dispatch`, `benefits/core/mixins.py::EligibleSessionRequiredMixin.dispatch`, `benefits/core/mixins.py::FlowSessionRequiredMixin.dispatch`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/cal-itp__benefits-3330`。
- Q-PRUNER：`benefits/enrollment_littlepay/views.py::IndexView.form_valid`, `None`, `benefits/core/mixins.py::AgencySessionRequiredMixin.dispatch`, `benefits/core/mixins.py::EligibleSessionRequiredMixin.dispatch`, `benefits/core/mixins.py::FlowSessionRequiredMixin.dispatch`。解析失败0，工具错误3，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/cal-itp__benefits-3330`。

## Blaizzy__mlx-vlm-179

仓库：Blaizzy/mlx-vlm；base：`1e4579ad0c99b41c71f7309a4cb59d0c4e49fca1`；PR时间：2025-01-11 21:48:06；映射：fully_mappable。

gold文件：`mlx_vlm/models/qwen2_vl/vision.py`, `mlx_vlm/trainer/trainer.py`。

可映射gold函数：`mlx_vlm/models/qwen2_vl/vision.py::VisionRotaryEmbedding.__call__`, `mlx_vlm/trainer/trainer.py::Dataset.__getitem__`, `mlx_vlm/trainer/trainer.py::Trainer.loss_fn`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/33.33% | 7.33 | 24593/638 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/33.33% | 19.30 | 52481/1723 | 2/2 | 2/2 |
| Q-COSIL | complete | 100.00% | 100.00%/33.33% | 61.43 | 80130/791 | 8/10 | 8/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/33.33% | 60.25 | 72394/758 | 4/10 | 4/4 |

各臂预测与证据：

- D-SIMPLE：`mlx_vlm/trainer/trainer.py::Dataset.__getitem__`, `mlx_vlm/utils.py::prepare_inputs`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/Blaizzy__mlx-vlm-179`。
- D-COSIL：`mlx_vlm/trainer/trainer.py::Dataset.__getitem__`, `mlx_vlm/lora.py::main`, `mlx_vlm/trainer/trainer.py::Dataset.__init__`, `mlx_vlm/models/mllama/mllama.py::Model.__call__`, `mlx_vlm/trainer/trainer.py::Trainer.train_step`。解析失败8，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/Blaizzy__mlx-vlm-179`。
- Q-COSIL：`mlx_vlm/trainer/trainer.py::Dataset.__getitem__`, `mlx_vlm/lora.py::main`, `mlx_vlm/utils.py::prepare_inputs`, `None`。解析失败0，工具错误2，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/Blaizzy__mlx-vlm-179`。
- Q-PRUNER：`mlx_vlm/trainer/trainer.py::Dataset.__getitem__`, `mlx_vlm/lora.py::main`, `mlx_vlm/utils.py::prepare_inputs`, `mlx_vlm/trainer/trainer.py::Trainer.train_step`, `mlx_vlm/trainer/trainer.py::Trainer.train_epoch`。解析失败0，工具错误6，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/Blaizzy__mlx-vlm-179`。

## macbre__sql-metadata-553

仓库：macbre/sql-metadata；base：`8df3ffceb18cea4b29a7195263f132cda4ca34a7`；PR时间：2025-05-04 15:45:49；映射：unmappable。

gold文件：`sql_metadata/keywords_lists.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 6.65 | 14976/319 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 23.02 | 53354/1470 | 8/8 | 8/3 |
| Q-COSIL | complete | 100.00% | NA/NA | 69.32 | 59371/920 | 10/10 | 10/3 |
| Q-PRUNER | complete | 100.00% | NA/NA | 70.66 | 53209/934 | 10/10 | 10/1 |

各臂预测与证据：

- D-SIMPLE：`sql_metadata/parser.py::Parser.tables`, `sql_metadata/parser.py::Parser._determine_last_relevant_keyword`, `sql_metadata/token.py::SQLToken.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/macbre__sql-metadata-553`。
- D-COSIL：`sql_metadata/token.py::SQLToken.is_potential_table_name`, `sql_metadata/parser.py::Parser.tables`, `sql_metadata/token.py::SQLToken.is_potential_column_name`, `None`, `sql_metadata/parser.py::Parser._not_parsed_tokens`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/macbre__sql-metadata-553`。
- Q-COSIL：`sql_metadata/parser.py::Parser.query_type`, `sql_metadata/parser.py::Parser.tables`, `sql_metadata/parser.py::Parser.columns`, `sql_metadata/parser.py::Parser._handle_column_save`, `sql_metadata/parser.py::Parser._resolve_column_alias`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/macbre__sql-metadata-553`。
- Q-PRUNER：`sql_metadata/parser.py::Parser.tables`, `sql_metadata/parser.py::Parser.columns`, `sql_metadata/parser.py::Parser._handle_column_save`, `sql_metadata/parser.py::Parser._resolve_column_alias`, `sql_metadata/parser.py::Parser.query_type`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/macbre__sql-metadata-553`。

## brightway-lca__brightway2-data-235

仓库：brightway-lca/brightway2-data；base：`f9f36639f2637e4cb9f033d44e2acd7cf59fe026`；PR时间：2025-01-28 10:42:58；映射：fully_mappable。

gold文件：`bw2data/search/indices.py`。

可映射gold函数：`bw2data/search/indices.py::IndexManager.__init__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.49 | 15883/414 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.45 | 45931/1016 | 7/7 | 7/5 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 62.26 | 53820/814 | 7/10 | 7/4 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 64.58 | 61680/828 | 9/10 | 9/8 |

各臂预测与证据：

- D-SIMPLE：`bw2data/search/indices.py::IndexManager.delete_database`, `bw2data/search/indices.py::IndexManager.__init__`, `bw2data/search/indices.py::IndexManager.create`, `bw2data/search/indices.py::IndexManager.update_dataset`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/brightway-lca__brightway2-data-235`。
- D-COSIL：`bw2data/search/indices.py::IndexManager.delete_database`, `bw2data/search/indices.py::IndexManager.__init__`, `bw2data/search/indices.py::IndexManager.create`, `bw2data/search/indices.py::IndexManager.update_dataset`, `bw2data/backends/proxies.py::Activity.save`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/brightway-lca__brightway2-data-235`。
- Q-COSIL：`bw2data/search/indices.py::IndexManager.delete_database`, `bw2data/search/indices.py::IndexManager.update_dataset`, `bw2data/backends/proxies.py::Activity.save`, `None`, `bw2data/utils.py::safe_filename`。解析失败0，工具错误3，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/brightway-lca__brightway2-data-235`。
- Q-PRUNER：`bw2data/search/indices.py::IndexManager.delete_database`, `bw2data/search/indices.py::IndexManager.update_dataset`, `bw2data/backends/proxies.py::Activity.save`, `bw2data/search/indices.py::IndexManager.create`, `bw2data/utils.py::safe_filename`。解析失败0，工具错误1，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/brightway-lca__brightway2-data-235`。

## CS-SI__eodag-1717

仓库：CS-SI/eodag；base：`036b86bbefeed905c9962a7a4bf7bca8258246fb`；PR时间：2025-07-01 16:44:39+00:00；映射：partially_mappable。

gold文件：`eodag/plugins/download/base.py`。

可映射gold函数：`eodag/plugins/download/base.py::Download._prepare_download`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.16 | 89843/731 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 27.70 | 160909/1300 | 10/10 | 10/6 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 22.51 | 5169/296 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 23.03 | 5169/296 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`eodag/plugins/download/base.py::Download._prepare_download`, `eodag/plugins/download/http.py::HTTPDownload.download`, `eodag/plugins/download/base.py::Download.download_all`, `eodag/api/product/_product.py::EOProduct.download`, `eodag/api/core.py::EODataAccessGateway.download_all`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/CS-SI__eodag-1717`。
- D-COSIL：`eodag/plugins/download/base.py::Download._prepare_download`, `eodag/plugins/download/base.py::Download.generate_record_hash`, `eodag/plugins/download/http.py::HTTPDownload.download`, `eodag/plugins/download/http.py::HTTPDownload._check_product_filename`, `eodag/api/product/_product.py::EOProduct.download`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/CS-SI__eodag-1717`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/CS-SI__eodag-1717`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/CS-SI__eodag-1717`。

## allenneuraldynamics__aind-data-schema-1677

仓库：AllenNeuralDynamics/aind-data-schema；base：`c1d1457d99927bdf79dbbdc6194e6449561c57e9`；PR时间：2026-01-05 22:24:41；映射：unmappable。

gold文件：`src/aind_data_schema/components/devices.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 6.46 | 21026/596 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 20.11 | 53941/1786 | 6/6 | 6/3 |
| Q-COSIL | complete | 0.00% | NA/NA | 121.58 | 45385/1694 | 7/10 | 7/0 |
| Q-PRUNER | complete | 0.00% | NA/NA | 118.79 | 46551/1652 | 7/10 | 7/0 |

各臂预测与证据：

- D-SIMPLE：`None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/allenneuraldynamics__aind-data-schema-1677`。
- D-COSIL：`None`, `src/aind_data_schema/base.py::DataModel.unit_validator`, `None`, `None`, `src/aind_data_schema/base.py::DataModel.__init_subclass__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/allenneuraldynamics__aind-data-schema-1677`。
- Q-COSIL：`None`, `src/aind_data_schema/core/acquisition.py::Acquisition.__add__`, `src/aind_data_schema/utils/compatibility_check.py::InstrumentAcquisitionCompatibility.run_compatibility_check`, `src/aind_data_schema/core/acquisition.py::DataStream.check_modality_config_requirements`, `src/aind_data_schema/utils/validators.py::validate_creation_time_after_midnight`。解析失败0，工具错误3，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/allenneuraldynamics__aind-data-schema-1677`。
- Q-PRUNER：`None`, `src/aind_data_schema/core/acquisition.py::Acquisition.__add__`, `src/aind_data_schema/utils/compatibility_check.py::InstrumentAcquisitionCompatibility.run_compatibility_check`, `src/aind_data_schema/core/acquisition.py::DataStream.check_modality_config_requirements`, `src/aind_data_schema/utils/validators.py::validate_creation_time_after_midnight`。解析失败0，工具错误3，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/allenneuraldynamics__aind-data-schema-1677`。

## reata__sqllineage-743

仓库：reata/sqllineage；base：`e8f4ec4bf9a77c056fe8933f934bd710b6eae573`；PR时间：2025-12-17 11:36:49；映射：fully_mappable。

gold文件：`sqllineage/core/parser/sqlfluff/extractors/create_insert.py`。

可映射gold函数：`sqllineage/core/parser/sqlfluff/extractors/create_insert.py::CreateInsertExtractor.extract`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.56 | 25863/809 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.21 | 67639/1651 | 4/4 | 4/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 162.78 | 84157/2273 | 10/10 | 10/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 169.75 | 90064/2273 | 10/10 | 10/2 |

各臂预测与证据：

- D-SIMPLE：`sqllineage/core/parser/__init__.py::SourceHandlerMixin.end_of_query_cleanup`, `sqllineage/core/parser/sqlfluff/extractors/create_insert.py::CreateInsertExtractor.extract`, `sqllineage/core/holders.py::SubQueryLineageHolder.add_write_column`, `sqllineage/core/holders.py::SubQueryLineageHolder.write_columns`, `sqllineage/core/parser/sqlfluff/extractors/base.py::BaseExtractor._init_holder`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/reata__sqllineage-743`。
- D-COSIL：`sqllineage/core/parser/sqlfluff/extractors/create_insert.py::CreateInsertExtractor.extract`, `sqllineage/core/holders.py::SubQueryLineageHolder.add_write_column`, `sqllineage/core/holders.py::SubQueryLineageHolder.get_source_columns`, `sqllineage/core/holders.py::SubQueryLineageHolder.add_column_lineage`, `sqllineage/core/parser/sqlfluff/models.py::SqlFluffColumn.of`。解析失败6，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/reata__sqllineage-743`。
- Q-COSIL：`sqllineage/core/parser/sqlfluff/extractors/create_insert.py::CreateInsertExtractor.extract`, `sqllineage/core/metadata_provider.py::MetaDataProvider.get_table_columns`, `sqllineage/core/models.py::Column.to_source_columns`, `sqllineage/core/analyzer.py::LineageAnalyzer.analyze`。解析失败0，工具错误0，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/reata__sqllineage-743`。
- Q-PRUNER：`sqllineage/core/parser/sqlfluff/extractors/create_insert.py::CreateInsertExtractor.extract`, `sqllineage/core/metadata_provider.py::MetaDataProvider.get_table_columns`, `sqllineage/core/models.py::Column.to_source_columns`, `sqllineage/core/analyzer.py::LineageAnalyzer.analyze`。解析失败0，工具错误0，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/reata__sqllineage-743`。

## cpp-linter__cpp-linter-hooks-142

仓库：cpp-linter/cpp-linter-hooks；base：`96fbc91db4870834da0332b8a933490a8ce92664`；PR时间：2025-11-04 17:20:52；映射：partially_mappable。

gold文件：`cpp_linter_hooks/util.py`。

可映射gold函数：`cpp_linter_hooks/util.py::_install_tool`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 5.69 | 4543/163 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.51 | 29936/1246 | 7/7 | 7/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 86.60 | 37977/1181 | 6/10 | 6/2 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 85.38 | 40990/1145 | 6/10 | 6/3 |

各臂预测与证据：

- D-SIMPLE：`cpp_linter_hooks/util.py::_install_tool`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/cpp-linter__cpp-linter-hooks-142`。
- D-COSIL：`cpp_linter_hooks/util.py::_install_tool`, `cpp_linter_hooks/util.py::resolve_install`, `cpp_linter_hooks/util.py::_resolve_version`, `cpp_linter_hooks/util.py::get_version_from_dependency`, `cpp_linter_hooks/clang_format.py::run_clang_format`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/cpp-linter__cpp-linter-hooks-142`。
- Q-COSIL：`cpp_linter_hooks/util.py::_install_tool`, `cpp_linter_hooks/util.py::get_version_from_dependency`, `cpp_linter_hooks/util.py::_resolve_version`, `cpp_linter_hooks/clang_format.py::run_clang_format`, `cpp_linter_hooks/clang_tidy.py::run_clang_tidy`。解析失败0，工具错误4，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/cpp-linter__cpp-linter-hooks-142`。
- Q-PRUNER：`cpp_linter_hooks/util.py::_install_tool`, `cpp_linter_hooks/util.py::resolve_install`, `cpp_linter_hooks/clang_format.py::run_clang_format`, `cpp_linter_hooks/clang_tidy.py::run_clang_tidy`, `scripts/update_versions.py::fetch_versions_from_pypi`。解析失败0，工具错误4，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/cpp-linter__cpp-linter-hooks-142`。

## google__adk-python-3088

仓库：google/adk-python；base：`b17c8f19e5fc67180d1bdc621f84cd43e357571c`；PR时间：2025-10-03 21:08:25；映射：partially_mappable。

gold文件：`src/google/adk/tools/_function_parameter_parse_util.py`。

可映射gold函数：`src/google/adk/tools/_function_parameter_parse_util.py::_parse_schema_from_parameter`, `src/google/adk/tools/_function_parameter_parse_util.py::_raise_if_schema_unsupported`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/50.00% | 8.87 | 65155/972 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 26.01 | 53463/1127 | 7/7 | 7/7 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 20.74 | 4672/270 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 23.85 | 4672/270 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/google/adk/tools/_function_parameter_parse_util.py::_parse_schema_from_parameter`, `src/google/adk/tools/_automatic_function_calling_util.py::from_function_with_options`, `src/google/adk/tools/function_tool.py::FunctionTool._preprocess_args`, `src/google/adk/tools/_automatic_function_calling_util.py::_get_fields_dict`, `src/google/adk/tools/_automatic_function_calling_util.py::_get_pydantic_schema`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/google__adk-python-3088`。
- D-COSIL：`src/google/adk/tools/_automatic_function_calling_util.py::_map_pydantic_type_to_property_schema`, `src/google/adk/tools/_automatic_function_calling_util.py::_remove_any_of`, `src/google/adk/tools/_automatic_function_calling_util.py::_get_pydantic_schema`, `src/google/adk/tools/_automatic_function_calling_util.py::_process_pydantic_schema`, `src/google/adk/tools/_automatic_function_calling_util.py::_map_pydantic_type_to_schema_type`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/google__adk-python-3088`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/google__adk-python-3088`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/google__adk-python-3088`。

## dstl__Stone-Soup-1167

仓库：dstl/Stone-Soup；base：`6231f58db37ba76d93024600a26aca4dccbc16e8`；PR时间：2025-05-15 16:59:34；映射：fully_mappable。

gold文件：`stonesoup/functions/__init__.py`。

可映射gold函数：`stonesoup/functions/__init__.py::mod_elevation`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 6.90 | 31986/352 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 27.52 | 70646/1784 | 8/10 | 8/0 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 74.79 | 69924/974 | 9/10 | 9/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 81.66 | 76623/934 | 10/10 | 10/2 |

各臂预测与证据：

- D-SIMPLE：`None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/dstl__Stone-Soup-1167`。
- D-COSIL：`None`, `None`, `stonesoup/types/angle.py::Angle.mod_angle`, `stonesoup/types/angle.py::Angle.__init__`, `stonesoup/functions/__init__.py::mod_bearing`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/dstl__Stone-Soup-1167`。
- Q-COSIL：`None`, `None`, `None`, `stonesoup/functions/__init__.py::grid_creation`, `stonesoup/functions/__init__.py::mod_bearing`。解析失败0，工具错误1，重复输入3，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/dstl__Stone-Soup-1167`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/dstl__Stone-Soup-1167`。

## icloud-photos-downloader__icloud_photos_downloader-1060

仓库：icloud-photos-downloader/icloud_photos_downloader；base：`337ea77aefb5c1189681a2971c037caeeec43f51`；PR时间：2025-01-18 05:00:10；映射：fully_mappable。

gold文件：`src/icloudpd/xmp_sidecar.py`。

可映射gold函数：`src/icloudpd/xmp_sidecar.py::build_metadata`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 5.93 | 48226/338 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.56 | 90766/1240 | 8/8 | 8/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 25.88 | 1636/370 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 29.43 | 1636/370 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/icloudpd/xmp_sidecar.py::build_metadata`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/icloud-photos-downloader__icloud_photos_downloader-1060`。
- D-COSIL：`src/icloudpd/xmp_sidecar.py::build_metadata`, `src/icloudpd/xmp_sidecar.py::generate_xmp_file`, `src/icloudpd/xmp_sidecar.py::generate_xml`, `None`, `src/icloudpd/base.py::core`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/icloud-photos-downloader__icloud_photos_downloader-1060`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/icloud-photos-downloader__icloud_photos_downloader-1060`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/icloud-photos-downloader__icloud_photos_downloader-1060`。

## apache__iceberg-python-3295

仓库：apache/iceberg-python；base：`b67b7241690e05413f3cfea69287f897b0b2410e`；PR时间：2026-04-28 22:03:47；映射：unmappable。

gold文件：`pyiceberg/expressions/__init__.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 5.73 | 24754/320 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 24.00 | 128581/1596 | 6/6 | 6/6 |
| Q-COSIL | complete | 100.00% | NA/NA | 98.26 | 153903/1141 | 1/10 | 1/1 |
| Q-PRUNER | complete | 100.00% | NA/NA | 96.31 | 153863/1136 | 1/10 | 1/1 |

各臂预测与证据：

- D-SIMPLE：`pyiceberg/expressions/__init__.py::And.__new__`, `pyiceberg/expressions/__init__.py::Or.__new__`, `pyiceberg/expressions/__init__.py::Not.__new__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/apache__iceberg-python-3295`。
- D-COSIL：`pyiceberg/expressions/__init__.py::And.__new__`, `pyiceberg/expressions/__init__.py::Or.__new__`, `pyiceberg/expressions/__init__.py::Not.__new__`, `pyiceberg/expressions/__init__.py::And.__getnewargs__`, `pyiceberg/expressions/__init__.py::Or.__getnewargs__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/apache__iceberg-python-3295`。
- Q-COSIL：`pyiceberg/expressions/__init__.py::And.__new__`, `pyiceberg/expressions/__init__.py::Or.__new__`, `pyiceberg/expressions/__init__.py::Not.__new__`, `None`, `None`。解析失败0，工具错误9，重复输入8，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/apache__iceberg-python-3295`。
- Q-PRUNER：`pyiceberg/expressions/__init__.py::And.__new__`, `pyiceberg/expressions/__init__.py::Or.__new__`, `pyiceberg/expressions/__init__.py::Not.__new__`, `None`, `None`。解析失败0，工具错误9，重复输入8，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/apache__iceberg-python-3295`。

## streamlink__streamlink-6420

仓库：streamlink/streamlink；base：`638ea0dffad99cb2c28a64888bb2f528a3e4f31c`；PR时间：2025-02-02 23:10:13；映射：partially_mappable。

gold文件：`src/streamlink/plugins/nos.py`。

可映射gold函数：`src/streamlink/plugins/nos.py::NOS._get_streams`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.61 | 27307/224 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 24.99 | 67550/972 | 8/8 | 8/1 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 19.02 | 2764/266 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 21.69 | 2764/266 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/streamlink/plugins/nos.py::NOS._get_streams`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/streamlink__streamlink-6420`。
- D-COSIL：`src/streamlink/plugins/nos.py::NOS._get_streams`, `None`, `None`, `None`, `src/streamlink/validate/_validators.py::validator_parse_json`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/streamlink__streamlink-6420`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/streamlink__streamlink-6420`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/streamlink__streamlink-6420`。

## asottile__dead-204

仓库：asottile/dead；base：`d2d94828cfe205d294b5e551dfe187d77a1fe026`；PR时间：2025-02-08 19:41:24；映射：partially_mappable。

gold文件：`dead.py`。

可映射gold函数：`dead.py::Visitor.visit_ClassDef`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.35 | 4668/279 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 17.52 | 25255/1099 | 6/6 | 6/6 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 76.74 | 34349/985 | 9/10 | 9/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 68.29 | 35202/955 | 9/10 | 9/0 |

各臂预测与证据：

- D-SIMPLE：`dead.py::Visitor.visit_ClassDef`, `dead.py::Visitor.visit_Attribute`, `dead.py::Visitor.read`, `dead.py::Visitor.define`, `dead.py::Visitor.visit_FunctionDef`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/asottile__dead-204`。
- D-COSIL：`dead.py::Visitor.visit_ClassDef`, `dead.py::Visitor.read`, `dead.py::Visitor.scope`, `dead.py::Visitor.visit_FunctionDef`, `dead.py::Visitor.define`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/asottile__dead-204`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/asottile__dead-204`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/asottile__dead-204`。

## SciTools__iris-6719

仓库：SciTools/iris；base：`8ed25703a20a57f1ed72fc910c499c93df5e9857`；PR时间：2025-09-22 15:29:05；映射：fully_mappable。

gold文件：`lib/iris/coords.py`。

可映射gold函数：`lib/iris/coords.py::Coord.collapsed`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 11.04 | 165219/672 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 25.92 | 124324/1855 | 3/3 | 3/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 23.22 | 1957/319 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 30.36 | 1957/319 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`lib/iris/cube.py::Cube.aggregated_by`, `lib/iris/cube.py::Cube.collapsed`, `lib/iris/coords.py::Coord.collapsed`, `lib/iris/coords.py::Coord.copy`, `lib/iris/coords.py::_DimensionalMetadata.copy`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/SciTools__iris-6719`。
- D-COSIL：`lib/iris/analysis/__init__.py::_Groupby._compute_shared_coords`, `lib/iris/coords.py::Coord.collapsed`, `lib/iris/cube.py::Cube.aggregated_by`, `lib/iris/cube.py::Cube.collapsed`, `lib/iris/coords.py::_DimensionalMetadata._sanitise_array`。解析失败7，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/SciTools__iris-6719`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/SciTools__iris-6719`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/SciTools__iris-6719`。

## agronholm__sqlacodegen-375

仓库：agronholm/sqlacodegen；base：`70e1a5c079a9d1568f57b0a242e155d43df9510c`；PR时间：2025-02-25 20:54:06；映射：partially_mappable。

gold文件：`src/sqlacodegen/generators.py`。

可映射gold函数：`src/sqlacodegen/generators.py::TablesGenerator.get_adapted_type`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.34 | 17737/256 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 17.64 | 66996/1195 | 4/5 | 4/3 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 2.79 | 837/38 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 3.04 | 837/38 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/sqlacodegen/generators.py::TablesGenerator.get_adapted_type`, `src/sqlacodegen/generators.py::TablesGenerator.fix_column_types`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/agronholm__sqlacodegen-375`。
- D-COSIL：`src/sqlacodegen/generators.py::TablesGenerator.get_adapted_type`, `src/sqlacodegen/generators.py::TablesGenerator.fix_column_types`, `src/sqlacodegen/generators.py::TablesGenerator.generate`, `src/sqlacodegen/generators.py::TablesGenerator.collect_imports_for_column`, `src/sqlacodegen/generators.py::TablesGenerator.render_column`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/agronholm__sqlacodegen-375`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/agronholm__sqlacodegen-375`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/agronholm__sqlacodegen-375`。

## scott-huberty__eyelinkio-22

仓库：scott-huberty/eyelinkio；base：`1d57c07e5e186b8219be6586d09b16ac6397c43c`；PR时间：2025-02-05 21:17:46；映射：partially_mappable。

gold文件：`src/eyelinkio/edf/read.py`。

可映射gold函数：`src/eyelinkio/edf/read.py::_handle_end`, `src/eyelinkio/edf/read.py::_read_raw_edf`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.07 | 18463/409 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 24.89 | 61341/1474 | 10/10 | 10/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 89.00 | 47623/1261 | 10/10 | 10/1 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 91.32 | 55099/1257 | 10/10 | 10/3 |

各臂预测与证据：

- D-SIMPLE：`src/eyelinkio/edf/read.py::_handle_end`, `src/eyelinkio/edf/read.py::_read_raw_edf`, `src/eyelinkio/edf/read.py::_handle_recording_info`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/scott-huberty__eyelinkio-22`。
- D-COSIL：`src/eyelinkio/edf/read.py::_handle_end`, `src/eyelinkio/edf/read.py::_read_raw_edf`, `src/eyelinkio/edf/read.py::_handle_recording_info`, `src/eyelinkio/edf/read.py::EDF.__init__`, `src/eyelinkio/edf/read.py::_handle_message`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/scott-huberty__eyelinkio-22`。
- Q-COSIL：`src/eyelinkio/edf/read.py::_handle_end`, `src/eyelinkio/edf/read.py::read_edf`, `src/eyelinkio/edf/read.py::_read_raw_edf`, `src/eyelinkio/edf/read.py::_parse_preamble`, `None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/scott-huberty__eyelinkio-22`。
- Q-PRUNER：`src/eyelinkio/edf/read.py::_handle_end`, `src/eyelinkio/edf/read.py::read_edf`, `src/eyelinkio/edf/read.py::_read_raw_edf`, `src/eyelinkio/edf/read.py::_parse_preamble`, `src/eyelinkio/edf/read.py::_to_list`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/scott-huberty__eyelinkio-22`。

## ethereum__eth-account-317

仓库：ethereum/eth-account；base：`22c9d54b07f948f191d0f9075441fac462c39984`；PR时间：2025-03-21 21:25:08；映射：fully_mappable。

gold文件：`eth_account/_utils/encode_typed_data/encoding_and_hashing.py`, `eth_account/messages.py`。

可映射gold函数：`eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_field`, `eth_account/messages.py::encode_typed_data`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/50.00% | 6.95 | 12439/275 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.45 | 55780/1132 | 4/4 | 4/2 |
| Q-COSIL | complete | 100.00% | 100.00%/50.00% | 191.80 | 116407/2618 | 10/10 | 10/10 |
| Q-PRUNER | complete | 100.00% | 100.00%/50.00% | 200.26 | 122087/2598 | 10/10 | 10/10 |

各臂预测与证据：

- D-SIMPLE：`eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_field`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/ethereum__eth-account-317`。
- D-COSIL：`eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_field`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_data`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_struct`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_eip712_message`, `eth_account/messages.py::encode_typed_data`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/ethereum__eth-account-317`。
- Q-COSIL：`eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_field`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_data`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_struct`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_eip712_message`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_domain`。解析失败0，工具错误0，重复输入9，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/ethereum__eth-account-317`。
- Q-PRUNER：`eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_field`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::encode_data`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_struct`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_eip712_message`, `eth_account/_utils/encode_typed_data/encoding_and_hashing.py::hash_domain`。解析失败0，工具错误0，重复输入9，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/ethereum__eth-account-317`。

## aiidateam__aiida-quantumespresso-1142

仓库：aiidateam/aiida-quantumespresso；base：`9f490185f525482d1851b8d91d7d5ce468d546f9`；PR时间：2025-09-18 01:24:49；映射：fully_mappable。

gold文件：`src/aiida_quantumespresso/calculations/neb.py`。

可映射gold函数：`src/aiida_quantumespresso/calculations/neb.py::NebCalculation.validate_inputs`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.74 | 57258/502 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | 0.00%/0.00% | 3.59 | 1435/830 | 0/0 | 0/0 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 32.84 | 1468/477 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 34.52 | 1468/477 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/aiida_quantumespresso/calculations/neb.py::NebCalculation.validate_inputs`, `src/aiida_quantumespresso/calculations/pw.py::PwCalculation.validate_inputs`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/aiidateam__aiida-quantumespresso-1142`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/aiidateam__aiida-quantumespresso-1142`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/aiidateam__aiida-quantumespresso-1142`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/aiidateam__aiida-quantumespresso-1142`。

## reagento__dishka-512

仓库：reagento/dishka；base：`e11de4e1e2f18621943df2084e683459d9445c18`；PR时间：2025-08-02 10:34:01+00:00；映射：fully_mappable。

gold文件：`src/dishka/dependency_source/decorator.py`。

可映射gold函数：`src/dishka/dependency_source/decorator.py::Decorator._replace_dep`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.32 | 19948/795 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.25 | 66478/1527 | 7/7 | 7/5 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 123.52 | 60275/1645 | 9/10 | 9/8 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 134.52 | 63227/1615 | 9/10 | 9/8 |

各臂预测与证据：

- D-SIMPLE：`src/dishka/dependency_source/decorator.py::Decorator._replace_dep`, `src/dishka/dependency_source/decorator.py::Decorator.as_factory`, `src/dishka/dependency_source/type_match.py::_TypeMatcher._is_broader_or_same_generic`, `src/dishka/dependency_source/type_match.py::get_typevar_replacement`, `src/dishka/registry_builder.py::RegistryBuilder._process_generic_decorator`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/reagento__dishka-512`。
- D-COSIL：`src/dishka/dependency_source/decorator.py::Decorator._replace_dep`, `src/dishka/dependency_source/decorator.py::Decorator.as_factory`, `src/dishka/registry_builder.py::RegistryBuilder._decorate_factory`, `src/dishka/registry_builder.py::RegistryBuilder._process_generic_decorator`, `src/dishka/dependency_source/decorator.py::Decorator.is_generic`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/reagento__dishka-512`。
- Q-COSIL：`src/dishka/dependency_source/decorator.py::Decorator._replace_dep`, `src/dishka/dependency_source/decorator.py::Decorator.as_factory`, `src/dishka/registry_builder.py::RegistryBuilder._process_generic_decorator`, `src/dishka/registry_builder.py::RegistryBuilder._decorate_factory`, `None`。解析失败0，工具错误1，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/reagento__dishka-512`。
- Q-PRUNER：`src/dishka/dependency_source/decorator.py::Decorator._replace_dep`, `src/dishka/dependency_source/decorator.py::Decorator.as_factory`, `src/dishka/registry_builder.py::RegistryBuilder._process_generic_decorator`, `src/dishka/registry_builder.py::RegistryBuilder._decorate_factory`, `None`。解析失败0，工具错误1，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/reagento__dishka-512`。

## ej2__python-quickbooks-381

仓库：ej2/python-quickbooks；base：`5efc53561e31a71870d0ed5417d07847d25502c0`；PR时间：2025-03-16 20:12:53；映射：fully_mappable。

gold文件：`quickbooks/client.py`。

可映射gold函数：`quickbooks/client.py::QuickBooks.__new__`, `quickbooks/client.py::QuickBooks.get`, `quickbooks/client.py::QuickBooks.get_single_object`, `quickbooks/client.py::QuickBooks.make_request`, `quickbooks/client.py::QuickBooks.post`, `quickbooks/client.py::QuickBooks.update_object`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/33.33% | 5.16 | 9205/184 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/50.00% | 12.04 | 32365/983 | 3/3 | 3/3 |
| Q-COSIL | complete | 100.00% | 100.00%/33.33% | 70.86 | 70826/951 | 10/10 | 10/6 |
| Q-PRUNER | complete | 100.00% | 100.00%/33.33% | 79.93 | 72338/916 | 10/10 | 10/6 |

各臂预测与证据：

- D-SIMPLE：`quickbooks/client.py::QuickBooks.make_request`, `quickbooks/client.py::QuickBooks.__new__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/ej2__python-quickbooks-381`。
- D-COSIL：`None`, `quickbooks/client.py::QuickBooks.__new__`, `quickbooks/client.py::QuickBooks.make_request`, `quickbooks/client.py::QuickBooks.process_request`, `quickbooks/client.py::QuickBooks.get`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/ej2__python-quickbooks-381`。
- Q-COSIL：`quickbooks/client.py::QuickBooks.make_request`, `quickbooks/client.py::QuickBooks.__new__`, `quickbooks/client.py::QuickBooks.api_url`, `quickbooks/client.py::QuickBooks.validate_webhook_signature`, `quickbooks/client.py::QuickBooks.get_current_user`。解析失败0，工具错误0，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/ej2__python-quickbooks-381`。
- Q-PRUNER：`quickbooks/client.py::QuickBooks.make_request`, `quickbooks/client.py::QuickBooks.__new__`, `quickbooks/client.py::QuickBooks.api_url`, `quickbooks/client.py::QuickBooks.validate_webhook_signature`, `quickbooks/client.py::QuickBooks.get_current_user`。解析失败0，工具错误0，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/ej2__python-quickbooks-381`。

## huggingface__transformers-43721_interface

仓库：huggingface/transformers；base：`8ead2903d5ea3799cc3bb43670fddccac1d80f23`；PR时间：2026-02-03 20:01:08；映射：unmappable。

gold文件：`src/transformers/integrations/bitnet.py`, `src/transformers/quantizers/quantizer_bitnet.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 11.42 | 108824/1038 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 223.32 | 157667/1979 | 6/6 | 6/6 |
| Q-COSIL | complete | 100.00% | NA/NA | 209.41 | 120170/1419 | 8/10 | 8/0 |
| Q-PRUNER | complete | 100.00% | NA/NA | 232.20 | 117859/1349 | 5/10 | 5/1 |

各臂预测与证据：

- D-SIMPLE：`src/transformers/integrations/bitnet.py::AutoBitLinear.load_hook`, `src/transformers/quantizers/quantizer_bitnet.py::BitNetHfQuantizer._process_model_before_weight_loading`, `src/transformers/integrations/bitnet.py::replace_with_bitnet_linear`, `src/transformers/integrations/bitnet.py::unpack_weights`, `src/transformers/core_model_loading.py::convert_and_load_state_dict_in_model`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/huggingface__transformers-43721_interface`。
- D-COSIL：`None`, `None`, `src/transformers/integrations/bitnet.py::AutoBitLinear.load_hook`, `src/transformers/integrations/bitnet.py::AutoBitLinear.__init__`, `src/transformers/quantizers/base.py::HfQuantizer.get_weight_conversions`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/huggingface__transformers-43721_interface`。
- Q-COSIL：`None`, `src/transformers/integrations/accelerate.py::check_and_set_device_map`, `src/transformers/core_model_loading.py::ConversionOps.convert`, `src/transformers/models/bitnet/modeling_bitnet.py::BitNetForCausalLM.forward`。解析失败0，工具错误2，重复输入4，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/huggingface__transformers-43721_interface`。
- Q-PRUNER：`None`, `src/transformers/integrations/accelerate.py::check_and_set_device_map`, `src/transformers/core_model_loading.py::ConversionOps.convert`, `src/transformers/models/bitnet/modeling_bitnet.py::BitNetForCausalLM.forward`, `None`。解析失败0，工具错误5，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/huggingface__transformers-43721_interface`。

## nilearn__nilearn-5741

仓库：nilearn/nilearn；base：`5083999d5b005050dd69f228823a4c1f6bd43dd3`；PR时间：2025-10-08 10:38:40；映射：fully_mappable。

gold文件：`nilearn/glm/first_level/first_level.py`。

可映射gold函数：`nilearn/glm/first_level/first_level.py::_check_args_first_level_from_bids`, `nilearn/glm/first_level/first_level.py::_check_length_match`, `nilearn/glm/first_level/first_level.py::_check_repetition_time`, `nilearn/glm/first_level/first_level.py::_check_run_tables`, `nilearn/glm/first_level/first_level.py::_check_slice_time_ref`, `nilearn/glm/first_level/first_level.py::_check_trial_type`, `nilearn/glm/first_level/first_level.py::_list_valid_subjects`, `nilearn/glm/first_level/first_level.py::_make_bids_files_filter`, `nilearn/glm/first_level/first_level.py::first_level_from_bids`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/33.33% | 7.71 | 77651/517 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/33.33% | 20.75 | 84706/1232 | 5/5 | 5/5 |
| Q-COSIL | complete | 100.00% | 100.00%/22.22% | 98.65 | 68108/1208 | 10/10 | 10/4 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 100.97 | 85990/1141 | 8/10 | 8/8 |

各臂预测与证据：

- D-SIMPLE：`nilearn/glm/first_level/first_level.py::first_level_from_bids`, `nilearn/glm/first_level/first_level.py::_list_valid_subjects`, `nilearn/glm/first_level/first_level.py::_check_bids_image_list`, `nilearn/glm/first_level/first_level.py::_get_processed_imgs`, `nilearn/glm/first_level/first_level.py::_check_args_first_level_from_bids`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/nilearn__nilearn-5741`。
- D-COSIL：`nilearn/glm/first_level/first_level.py::first_level_from_bids`, `nilearn/glm/first_level/first_level.py::_list_valid_subjects`, `nilearn/glm/first_level/first_level.py::_check_args_first_level_from_bids`, `nilearn/glm/first_level/first_level.py::_check_bids_image_list`, `nilearn/glm/first_level/first_level.py::_get_processed_imgs`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/nilearn__nilearn-5741`。
- Q-COSIL：`nilearn/glm/first_level/first_level.py::first_level_from_bids`, `nilearn/glm/first_level/first_level.py::_list_valid_subjects`, `nilearn/glm/first_level/first_level.py::_report_found_files`, `nilearn/glm/first_level/first_level.py::_check_bids_image_list`, `nilearn/glm/first_level/first_level.py::_check_bids_events_list`。解析失败0，工具错误0，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/nilearn__nilearn-5741`。
- Q-PRUNER：`nilearn/glm/first_level/first_level.py::FirstLevelModel._fit_single_run`, `nilearn/glm/first_level/first_level.py::FirstLevelModel.fit`, `nilearn/glm/first_level/first_level.py::FirstLevelModel.compute_contrast`, `nilearn/glm/first_level/first_level.py::FirstLevelModel._make_stat_maps`, `nilearn/glm/first_level/first_level.py::FirstLevelModel._check_fit_inputs`。解析失败0，工具错误2，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/nilearn__nilearn-5741`。

## jsonpickle__jsonpickle-587

仓库：jsonpickle/jsonpickle；base：`f0a02c4dd46c5919669767ad84462937f3fbebf7`；PR时间：2026-01-11 19:48:21；映射：fully_mappable。

gold文件：`jsonpickle/pickler.py`。

可映射gold函数：`jsonpickle/pickler.py::Pickler._flatten_newstyle_with_slots`, `jsonpickle/pickler.py::Pickler._flatten_obj_attrs`, `jsonpickle/pickler.py::Pickler._flatten_obj_instance`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.38 | 22430/360 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.53 | 65656/2099 | 5/5 | 5/4 |
| Q-COSIL | complete | 100.00% | 100.00%/66.67% | 172.49 | 105084/2326 | 10/10 | 10/8 |
| Q-PRUNER | complete | 100.00% | 100.00%/66.67% | 216.49 | 108326/2290 | 10/10 | 10/8 |

各臂预测与证据：

- D-SIMPLE：`jsonpickle/pickler.py::Pickler._flatten_newstyle_with_slots`, `jsonpickle/pickler.py::Pickler._flatten_obj_instance`, `jsonpickle/pickler.py::Pickler._flatten_obj_attrs`, `jsonpickle/pickler.py::Pickler._flatten_dict_obj`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/jsonpickle__jsonpickle-587`。
- D-COSIL：`jsonpickle/pickler.py::Pickler._flatten_obj_instance`, `jsonpickle/pickler.py::Pickler._flatten_newstyle_with_slots`, `jsonpickle/pickler.py::Pickler._flatten_obj_attrs`, `jsonpickle/pickler.py::Pickler._flatten_key_value_pair`, `jsonpickle/pickler.py::Pickler._flatten_properties`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/jsonpickle__jsonpickle-587`。
- Q-COSIL：`jsonpickle/pickler.py::Pickler._flatten_newstyle_with_slots`, `jsonpickle/pickler.py::Pickler._flatten_obj_attrs`, `jsonpickle/util.py::in_slots`, `jsonpickle/util.py::_is_type`, `None`。解析失败0，工具错误0，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/jsonpickle__jsonpickle-587`。
- Q-PRUNER：`jsonpickle/pickler.py::Pickler._flatten_newstyle_with_slots`, `jsonpickle/pickler.py::Pickler._flatten_obj_attrs`, `jsonpickle/util.py::in_slots`, `jsonpickle/util.py::_is_type`, `None`。解析失败0，工具错误0，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/jsonpickle__jsonpickle-587`。

## home-assistant__core-134506

仓库：home-assistant/core；base：`629d108078c05d8b032452fc678955ad6029ac31`；PR时间：2025-01-03 02:20:50；映射：unmappable。

gold文件：`homeassistant/components/backup/manager.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | NA/NA | 8.99 | 71924/394 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 519.01 | 141202/1456 | 9/10 | 9/5 |
| Q-COSIL | complete | 100.00% | NA/NA | 243.96 | 130550/1381 | 10/10 | 10/3 |
| Q-PRUNER | complete | 100.00% | NA/NA | 221.09 | 131409/1305 | 5/5 | 5/2 |

各臂预测与证据：

- D-SIMPLE：`None`, `homeassistant/components/backup/http.py::UploadBackupView.post`, `None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/home-assistant__core-134506`。
- D-COSIL：`homeassistant/components/backup/util.py::receive_file`, `homeassistant/components/backup/backup.py::CoreLocalBackupAgent.get_backup_path`, `homeassistant/components/backup/backup.py::CoreLocalBackupAgent.__init__`, `homeassistant/components/backup/util.py::make_backup_dir`, `homeassistant/components/backup/http.py::UploadBackupView.post`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/home-assistant__core-134506`。
- Q-COSIL：`homeassistant/components/backup/util.py::make_backup_dir`, `None`, `None`, `None`, `None`。解析失败0，工具错误0，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/home-assistant__core-134506`。
- Q-PRUNER：`homeassistant/components/backup/backup.py::CoreLocalBackupAgent.__init__`, `homeassistant/components/backup/backup.py::CoreLocalBackupAgent.get_backup_path`, `homeassistant/components/backup/store.py::BackupStore.save`, `homeassistant/components/backup/backup.py::CoreLocalBackupAgent.async_upload_backup`, `homeassistant/components/backup/backup.py::CoreLocalBackupAgent.async_get_backup`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/home-assistant__core-134506`。

## iris-hep__func_adl-199

仓库：iris-hep/func_adl；base：`2606c3c795b345932319b84da9d1d073cd34b77e`；PR时间：2025-07-05 16:44:19+00:00；映射：partially_mappable。

gold文件：`func_adl/ast/syntatic_sugar.py`。

可映射gold函数：`func_adl/ast/syntatic_sugar.py::resolve_syntatic_sugar`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 6.66 | 33460/542 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 25.38 | 115551/2459 | 6/6 | 6/1 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 73.06 | 91693/904 | 5/10 | 5/1 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 71.45 | 90604/884 | 5/10 | 5/1 |

各臂预测与证据：

- D-SIMPLE：`None`, `None`, `None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/iris-hep__func_adl-199`。
- D-COSIL：`func_adl/type_based_replacement.py::remap_by_types`, `None`, `None`, `func_adl/util_types.py::resolve_type_vars`, `func_adl/ast/syntatic_sugar.py::resolve_syntatic_sugar`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/iris-hep__func_adl-199`。
- Q-COSIL：`None`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Name`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Attribute`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Lambda`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Call`。解析失败0，工具错误5，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/iris-hep__func_adl-199`。
- Q-PRUNER：`None`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Name`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Attribute`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Lambda`, `func_adl/util_ast.py::_rewrite_captured_vars.visit_Call`。解析失败0，工具错误5，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/iris-hep__func_adl-199`。

## pypsa__pypsa-1653

仓库：PyPSA/PyPSA；base：`50bcbb8c1ba6319167a8bf0059cf18114b2f2eac`；PR时间：2026-04-13 08:33:16；映射：fully_mappable。

gold文件：`pypsa/statistics/expressions.py`, `pypsa/statistics/grouping.py`。

可映射gold函数：`pypsa/statistics/expressions.py::StatisticsAccessor._aggregate_components_groupby`, `pypsa/statistics/grouping.py::Groupers.name`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.25 | 70286/662 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | 0.00%/0.00% | 4.28 | 919/857 | 0/0 | 0/0 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 104.64 | 53927/1460 | 5/10 | 3/2 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 83.75 | 27417/1122 | 3/6 | 2/1 |

各臂预测与证据：

- D-SIMPLE：`pypsa/statistics/expressions.py::StatisticsAccessor._aggregate_components_groupby`, `pypsa/statistics/grouping.py::Groupers.name`, `pypsa/statistics/abstract.py::AbstractStatisticsAccessor._aggregate_components`, `pypsa/statistics/abstract.py::AbstractStatisticsAccessor._get_grouping`, `pypsa/statistics/grouping.py::Groupers._multi_grouper`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/pypsa__pypsa-1653`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/pypsa__pypsa-1653`。
- Q-COSIL：`None`, `pypsa/statistics/grouping.py::Groupers._map_with_multiindex`, `pypsa/networks.py::Network.name`, `pypsa/statistics/grouping.py::Groupers._get_generic_grouper`, `pypsa/plot/statistics/plotter.py::StatisticPlotter.__call__`。解析失败0，工具错误5，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/pypsa__pypsa-1653`。
- Q-PRUNER：空。解析失败0，工具错误3，重复输入1，agent未收到源码仍定位=False；Cannot bind exact source function。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/pypsa__pypsa-1653`。

## isledecomp__reccmp-142

仓库：isledecomp/reccmp；base：`e425c3a30c9da25269b0e453529c28280c40f650`；PR时间：2025-06-18 03:42:45；映射：unmappable。

gold文件：`reccmp/isledecomp/parser/error.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 6.32 | 13911/354 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 19.45 | 49247/1466 | 6/6 | 6/5 |
| Q-COSIL | complete | 100.00% | NA/NA | 102.55 | 49853/1410 | 6/8 | 6/1 |
| Q-PRUNER | complete | 100.00% | NA/NA | 102.31 | 54294/1357 | 6/8 | 6/6 |

各臂预测与证据：

- D-SIMPLE：`reccmp/tools/decomplint.py::display_errors`, `None`, `reccmp/isledecomp/parser/parser.py::DecompParser._handle_marker`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/isledecomp__reccmp-142`。
- D-COSIL：`None`, `reccmp/tools/decomplint.py::display_errors`, `reccmp/isledecomp/parser/parser.py::DecompParser._handle_marker`, `reccmp/isledecomp/parser/error.py::ParserAlert.is_error`, `reccmp/isledecomp/parser/error.py::ParserAlert.is_warning`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/isledecomp__reccmp-142`。
- Q-COSIL：`None`, `None`, `None`, `None`, `reccmp/tools/decomplint.py::display_errors`。解析失败2，工具错误2，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/isledecomp__reccmp-142`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `reccmp/tools/decomplint.py::display_errors`。解析失败2，工具错误2，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/isledecomp__reccmp-142`。

## tlsfuzzer__python-ecdsa-358

仓库：tlsfuzzer/python-ecdsa；base：`aa81ba3b7339f30362098580c754576bc15edba1`；PR时间：2025-03-13 10:20:39；映射：partially_mappable。

gold文件：`src/ecdsa/util.py`。

可映射gold函数：`src/ecdsa/util.py::sigencode_der_canonize`, `src/ecdsa/util.py::sigencode_string_canonize`, `src/ecdsa/util.py::sigencode_strings_canonize`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.17 | 13606/243 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 17.97 | 55526/1028 | 5/5 | 5/3 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 64.92 | 78790/842 | 7/10 | 7/3 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 71.92 | 88497/871 | 10/10 | 10/10 |

各臂预测与证据：

- D-SIMPLE：`src/ecdsa/util.py::sigencode_strings_canonize`, `src/ecdsa/util.py::sigencode_string_canonize`, `src/ecdsa/util.py::sigencode_der_canonize`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/tlsfuzzer__python-ecdsa-358`。
- D-COSIL：`src/ecdsa/util.py::sigencode_strings_canonize`, `src/ecdsa/util.py::sigencode_string_canonize`, `src/ecdsa/util.py::sigencode_der_canonize`, `src/ecdsa/util.py::sigencode_strings`, `src/ecdsa/util.py::sigencode_der`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/tlsfuzzer__python-ecdsa-358`。
- Q-COSIL：`src/ecdsa/util.py::sigencode_strings_canonize`, `src/ecdsa/util.py::sigencode_string_canonize`, `src/ecdsa/util.py::sigencode_der_canonize`, `None`, `None`。解析失败0，工具错误3，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/tlsfuzzer__python-ecdsa-358`。
- Q-PRUNER：`src/ecdsa/util.py::sigencode_strings_canonize`, `src/ecdsa/util.py::sigencode_string_canonize`, `src/ecdsa/util.py::sigencode_der_canonize`, `src/ecdsa/util.py::number_to_string`, `src/ecdsa/util.py::orderlen`。解析失败0，工具错误0，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/tlsfuzzer__python-ecdsa-358`。

## psd-tools__psd-tools-593

仓库：psd-tools/psd-tools；base：`b185d66beb9055b567106e0b90d6d786c62e27b4`；PR时间：2026-03-17 11:04:07；映射：partially_mappable。

gold文件：`src/psd_tools/composite/composite.py`。

可映射gold函数：`src/psd_tools/composite/composite.py::composite_pil`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.61 | 39462/980 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | 0.00%/0.00% | 5.85 | 892/2048 | 0/0 | 0/0 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 95.75 | 102760/1245 | 9/10 | 9/9 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 100.89 | 115819/1245 | 9/10 | 9/9 |

各臂预测与证据：

- D-SIMPLE：`src/psd_tools/api/psd_image.py::PSDImage.composite`, `src/psd_tools/composite/composite.py::composite_pil`, `src/psd_tools/api/pil_io.py::convert_image_data_to_pil`, `src/psd_tools/api/utils.py::has_transparency`, `src/psd_tools/api/numpy_io.py::get_image_data`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/psd-tools__psd-tools-593`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/psd-tools__psd-tools-593`。
- Q-COSIL：`src/psd_tools/api/pil_io.py::convert_image_data_to_pil`, `src/psd_tools/composite/composite.py::composite`, `None`, `src/psd_tools/api/layers.py::Layer.composite`, `None`。解析失败0，工具错误1，重复输入8，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/psd-tools__psd-tools-593`。
- Q-PRUNER：`src/psd_tools/api/pil_io.py::convert_image_data_to_pil`, `src/psd_tools/composite/composite.py::composite`, `None`, `src/psd_tools/api/layers.py::Layer.composite`, `None`。解析失败0，工具错误1，重复输入8，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/psd-tools__psd-tools-593`。

## facelessuser__pymdown-extensions-2651

仓库：facelessuser/pymdown-extensions；base：`f655468301b9372c1619a40c2f4b08e4d936b5d7`；PR时间：2025-04-27 19:44:03；映射：fully_mappable。

gold文件：`pymdownx/blocks/__init__.py`。

可映射gold函数：`pymdownx/blocks/__init__.py::BlocksProcessor.get_parent`, `pymdownx/blocks/__init__.py::BlocksProcessor.parse_blocks`, `pymdownx/blocks/__init__.py::BlocksProcessor.run`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.37 | 32011/703 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/66.67% | 28.54 | 71444/2644 | 7/7 | 7/7 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 100.10 | 66153/1319 | 9/10 | 9/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 96.51 | 70066/1301 | 5/10 | 5/2 |

各臂预测与证据：

- D-SIMPLE：`pymdownx/blocks/__init__.py::BlocksProcessor.parse_blocks`, `pymdownx/blocks/__init__.py::BlocksProcessor.get_parent`, `pymdownx/blocks/__init__.py::BlocksProcessor.run`, `pymdownx/blocks/tab.py::Tab.on_add`, `pymdownx/blocks/tab.py::Tab.on_create`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/facelessuser__pymdown-extensions-2651`。
- D-COSIL：`pymdownx/blocks/__init__.py::BlocksProcessor.parse_blocks`, `pymdownx/blocks/__init__.py::BlocksProcessor.detab_by_length`, `pymdownx/blocks/__init__.py::BlocksProcessor.get_parent`, `pymdownx/blocks/tab.py::Tab.on_add`, `pymdownx/blocks/__init__.py::BlocksProcessor.split_end`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/facelessuser__pymdown-extensions-2651`。
- Q-COSIL：`pymdownx/blocks/tab.py::TabbedTreeprocessor.run`, `pymdownx/blocks/html.py::HTML.on_markdown`, `pymdownx/highlight.py::BlockHtmlFormatter.wrap`, `pymdownx/util.py::PatternSequenceProcessor.handleMatch`, `pymdownx/blocks/tab.py::TabExtension.extendMarkdownBlocks`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/facelessuser__pymdown-extensions-2651`。
- Q-PRUNER：`pymdownx/blocks/tab.py::TabbedTreeprocessor.run`, `pymdownx/blocks/html.py::HTML.on_markdown`, `pymdownx/blocks/html.py::HTML.on_create`, `pymdownx/blocks/tab.py::TabbedTreeprocessor.get_parent_header_slug`, `None`。解析失败0，工具错误5，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/facelessuser__pymdown-extensions-2651`。

## Delgan__loguru-1306

仓库：Delgan/loguru；base：`3cfd03fb6fd2176b90ad14223408f3c4ec803cb6`；PR时间：2025-02-20 00:59:01；映射：fully_mappable。

gold文件：`loguru/_colorama.py`。

可映射gold函数：`loguru/_colorama.py::should_colorize`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 100.00%/100.00% | 6.71 | 46860/416 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 27.34 | 122037/1917 | 9/9 | 9/3 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 70.50 | 48154/934 | 6/10 | 6/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 70.88 | 50407/926 | 6/10 | 6/1 |

各臂预测与证据：

- D-SIMPLE：`loguru/_colorama.py::should_colorize`, `loguru/_logger.py::Logger.add`, `loguru/_defaults.py::env`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/Delgan__loguru-1306`。
- D-COSIL：`loguru/_colorama.py::should_colorize`, `loguru/_defaults.py::env`, `loguru/_logger.py::Logger.add`, `loguru/_colorama.py::should_wrap`, `loguru/_handler.py::Handler.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/Delgan__loguru-1306`。
- Q-COSIL：`None`, `loguru/_colorizer.py::ColoredFormat.colorize`, `loguru/_colorizer.py::AnsiParser.colorize`, `loguru/_colorama.py::should_colorize`, `loguru/_logger.py::Logger.log`。解析失败0，工具错误4，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/Delgan__loguru-1306`。
- Q-PRUNER：`loguru/_colorizer.py::AnsiParser.colorize`, `loguru/_colorizer.py::ColoredFormat.colorize`, `None`, `loguru/_colorizer.py::Colorizer.ansify`, `loguru/_logger.py::Logger.log`。解析失败0，工具错误4，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/Delgan__loguru-1306`。

## VRSEN__agency-swarm-468

仓库：VRSEN/agency-swarm；base：`0b16848ce4f973415ba7019c0bb05886e46c840d`；PR时间：2025-12-01 11:27:15；映射：fully_mappable。

gold文件：`src/agency_swarm/agent/file_manager.py`。

可映射gold函数：`src/agency_swarm/agent/file_manager.py::AgentFileManager.add_file_search_tool`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.49 | 35883/517 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.51 | 51945/1423 | 5/5 | 5/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 82.75 | 988/1199 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 89.92 | 988/1199 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/agency_swarm/agent/file_manager.py::AgentFileManager.add_file_search_tool`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/VRSEN__agency-swarm-468`。
- D-COSIL：`src/agency_swarm/agent/file_manager.py::AgentFileManager.add_file_search_tool`, `src/agency_swarm/agent/core.py::Agent.__init__`, `src/agency_swarm/agent/initialization.py::setup_file_manager`, `src/agency_swarm/agent/core.py::Agent.add_tool`, `src/agency_swarm/agent/file_manager.py::AgentFileManager.add_files_to_vector_store`。解析失败4，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/VRSEN__agency-swarm-468`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/VRSEN__agency-swarm-468`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/VRSEN__agency-swarm-468`。

## ASPP__pelita-863

仓库：ASPP/pelita；base：`ab9217f298fa4897b06e5e9e9e7fad7e29ba7114`；PR时间：2025-03-13 17:07:06；映射：unmappable。

gold文件：`pelita/team.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 7.01 | 96743/267 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 15.51 | 47548/1072 | 2/2 | 2/1 |
| Q-COSIL | complete | 100.00% | NA/NA | 69.94 | 51050/963 | 1/10 | 1/1 |
| Q-PRUNER | complete | 100.00% | NA/NA | 74.02 | 50992/958 | 1/10 | 1/1 |

各臂预测与证据：

- D-SIMPLE：`pelita/team.py::Bot.__str__`, `pelita/team.py::Bot.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/ASPP__pelita-863`。
- D-COSIL：`None`, `pelita/team.py::Bot.__str__`, `pelita/team.py::Bot._repr_html_`, `pelita/team.py::Bot.__init__`, `None`。解析失败4，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/ASPP__pelita-863`。
- Q-COSIL：`None`, `pelita/team.py::Bot.__str__`, `None`, `None`, `None`。解析失败0，工具错误9，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/ASPP__pelita-863`。
- Q-PRUNER：`None`, `pelita/team.py::Bot.__str__`, `None`, `None`, `None`。解析失败0，工具错误9，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/ASPP__pelita-863`。

## huggingface__huggingface_hub-4056

仓库：huggingface/huggingface_hub；base：`6983a4d3d2bdcbd09c6ea08acae64cdf83ccb2e4`；PR时间：2026-04-06 15:39:13；映射：partially_mappable。

gold文件：`src/huggingface_hub/_snapshot_download.py`, `src/huggingface_hub/utils/tqdm.py`。

可映射gold函数：`src/huggingface_hub/_snapshot_download.py::snapshot_download`, `src/huggingface_hub/utils/tqdm.py::_get_progress_bar_context`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/50.00% | 6.68 | 26920/319 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/50.00% | 24.92 | 60769/1249 | 7/7 | 6/3 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 4.33 | 2054/51 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 7.51 | 2054/51 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/huggingface_hub/utils/tqdm.py::_get_progress_bar_context`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/huggingface__huggingface_hub-4056`。
- D-COSIL：`src/huggingface_hub/utils/tqdm.py::_get_progress_bar_context`, `src/huggingface_hub/utils/tqdm.py::is_tqdm_disabled`, `src/huggingface_hub/utils/tqdm.py::tqdm.__init__`, `src/huggingface_hub/utils/tqdm.py::tqdm_stream_file`, `src/huggingface_hub/file_download.py::hf_hub_download`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/huggingface__huggingface_hub-4056`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/huggingface__huggingface_hub-4056`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/huggingface__huggingface_hub-4056`。

## biopython__biopython-5005

仓库：biopython/biopython；base：`11728693973fafcce459cf65c0450d579fd81b18`；PR时间：2025-06-06 15:06:38；映射：fully_mappable。

gold文件：`Bio/PDB/qcprot.py`。

可映射gold函数：`Bio/PDB/qcprot.py::qcp`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.24 | 91044/166 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.05 | 48095/991 | 3/3 | 3/2 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 89.29 | 110803/968 | 9/10 | 9/3 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 105.70 | 113603/930 | 9/10 | 9/5 |

各臂预测与证据：

- D-SIMPLE：`Bio/PDB/qcprot.py::qcp`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/biopython__biopython-5005`。
- D-COSIL：`Bio/PDB/qcprot.py::qcp`, `Bio/PDB/qcprot.py::QCPSuperimposer.run`, `Bio/PDB/qcprot.py::QCPSuperimposer.get_rms`, `Bio/PDB/qcprot.py::QCPSuperimposer.get_transformed`, `Bio/PDB/qcprot.py::QCPSuperimposer.get_rotran`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/biopython__biopython-5005`。
- Q-COSIL：`None`, `Bio/PDB/qcprot.py::QCPSuperimposer.run`, `Bio/PDB/qcprot.py::QCPSuperimposer.get_transformed`, `Bio/SVDSuperimposer/__init__.py::SVDSuperimposer.run`, `Bio/SVDSuperimposer/__init__.py::SVDSuperimposer.get_transformed`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/biopython__biopython-5005`。
- Q-PRUNER：`None`, `Bio/PDB/qcprot.py::QCPSuperimposer.run`, `Bio/PDB/qcprot.py::QCPSuperimposer.get_transformed`, `Bio/SVDSuperimposer/__init__.py::SVDSuperimposer.run`, `Bio/SVDSuperimposer/__init__.py::SVDSuperimposer.get_transformed`。解析失败0，工具错误1，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/biopython__biopython-5005`。

## sktime__sktime-8937

仓库：sktime/sktime；base：`ef97df5dd1732630546af1d83a48c91ef3b9eba3`；PR时间：2025-10-08 17:19:52；映射：fully_mappable。

gold文件：`sktime/benchmarking/benchmarks.py`。

可映射gold函数：`sktime/benchmarking/benchmarks.py::BaseBenchmark._run`, `sktime/benchmarking/benchmarks.py::BaseBenchmark.run`, `sktime/benchmarking/benchmarks.py::_BenchmarkingResults.__post_init__`, `sktime/benchmarking/benchmarks.py::_BenchmarkingResults.save`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.58 | 79387/674 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 30.63 | 53163/1534 | 7/7 | 7/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 113.98 | 70457/1392 | 7/10 | 7/7 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 121.95 | 72438/1382 | 9/10 | 9/0 |

各臂预测与证据：

- D-SIMPLE：`sktime/benchmarking/benchmarks.py::BaseBenchmark._run`, `sktime/benchmarking/benchmarks.py::BaseBenchmark.run`, `sktime/benchmarking/benchmarks.py::_BenchmarkingResults.__post_init__`, `sktime/benchmarking/benchmarks.py::_BenchmarkingResults.save`, `sktime/benchmarking/_storage_handlers.py::get_storage_backend`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/sktime__sktime-8937`。
- D-COSIL：`sktime/benchmarking/benchmarks.py::_BenchmarkingResults.__post_init__`, `sktime/benchmarking/benchmarks.py::_BenchmarkingResults.save`, `sktime/benchmarking/_storage_handlers.py::get_storage_backend`, `sktime/benchmarking/benchmarks.py::BaseBenchmark._run`, `sktime/benchmarking/benchmarks.py::BaseBenchmark.run`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/sktime__sktime-8937`。
- Q-COSIL：`sktime/benchmarking/_storage_handlers.py::CSVStorageHandler.save`, `sktime/benchmarking/_storage_handlers.py::JSONStorageHandler.save`, `sktime/benchmarking/_storage_handlers.py::ParquetStorageHandler.save`, `sktime/forecasting/base/_base.py::BaseForecaster.fit_predict`, `None`。解析失败0，工具错误3，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/sktime__sktime-8937`。
- Q-PRUNER：`sktime/benchmarking/_storage_handlers.py::BaseStorageHandler.save`, `sktime/forecasting/base/_base.py::BaseForecaster.predict`, `sktime/forecasting/compose/_pipeline.py::ForecastingPipeline._fit`, `sktime/forecasting/compose/_pipeline.py::ForecastingPipeline._predict`, `None`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/sktime__sktime-8937`。

## mitmproxy__pdoc-806

仓库：mitmproxy/pdoc；base：`ea2b69a4162226b07f68cd25d92d4d92dbbafaf8`；PR时间：2025-05-04 12:13:14；映射：unmappable。

gold文件：`pdoc/render_helpers.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 7.07 | 60700/420 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | NA/NA | 1.39 | 531/102 | 0/0 | 0/0 |
| Q-COSIL | complete | 0.00% | NA/NA | 97.61 | 68209/1327 | 6/10 | 6/0 |
| Q-PRUNER | complete | 0.00% | NA/NA | 125.48 | 68253/1302 | 6/10 | 6/0 |

各臂预测与证据：

- D-SIMPLE：`pdoc/render_helpers.py::to_html`, `pdoc/markdown2/__init__.py::Markdown._h_tag_sub`, `pdoc/markdown2/__init__.py::Markdown._hash_html_block_sub`, `pdoc/markdown2/__init__.py::Markdown.convert`, `pdoc/markdown2/__init__.py::Markdown.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/mitmproxy__pdoc-806`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/mitmproxy__pdoc-806`。
- Q-COSIL：`None`, `None`, `None`, `pdoc/docstrings.py::convert`, `None`。解析失败0，工具错误4，重复输入4，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/mitmproxy__pdoc-806`。
- Q-PRUNER：`None`, `None`, `None`, `pdoc/docstrings.py::convert`, `None`。解析失败0，工具错误4，重复输入4，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/mitmproxy__pdoc-806`。

## deltares__hydrolib-core-1049_interface

仓库：Deltares/HYDROLIB-core；base：`d46486ed3c6bedb6ef63e803da6e2e4851d1d48b`；PR时间：2026-04-13 09:42:06；映射：unmappable。

gold文件：`hydrolib/core/dflowfm/mdu/models.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 8.66 | 90325/472 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 35.64 | 180988/2237 | 10/10 | 10/2 |
| Q-COSIL | failed | 0.00% | NA/NA | 55.34 | 1130/763 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | NA/NA | 53.28 | 1130/763 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`hydrolib/core/dflowfm/mdu/models.py::Output.split_string_to_list`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/deltares__hydrolib-core-1049_interface`。
- D-COSIL：`None`, `hydrolib/core/base/models.py::FileModel._change_to_path`, `hydrolib/core/dflowfm/mdu/models.py::Output.split_string_to_list`, `None`, `hydrolib/core/base/models.py::BaseModel.__init__`。解析失败0，工具错误0，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/deltares__hydrolib-core-1049_interface`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/deltares__hydrolib-core-1049_interface`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/deltares__hydrolib-core-1049_interface`。

## dask__fastparquet-961

仓库：dask/fastparquet；base：`68da54f81836e3a05ed9d0468450207b24db40ca`；PR时间：2025-08-22 08:43:03+00:00；映射：fully_mappable。

gold文件：`fastparquet/writer.py`。

可映射gold函数：`fastparquet/writer.py::convert`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 5.31 | 40207/153 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 15.00 | 42171/1143 | 4/4 | 4/3 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 73.25 | 84342/921 | 8/10 | 8/8 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 72.08 | 85058/905 | 8/10 | 8/8 |

各臂预测与证据：

- D-SIMPLE：`fastparquet/writer.py::convert`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/dask__fastparquet-961`。
- D-COSIL：`fastparquet/writer.py::convert`, `fastparquet/writer.py::time_shift`, `fastparquet/writer.py::encode_plain`, `fastparquet/writer.py::write_column`, `fastparquet/writer.py::make_part_file`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/dask__fastparquet-961`。
- Q-COSIL：`fastparquet/writer.py::convert`, `fastparquet/writer.py::time_shift`, `fastparquet/converted_types.py::convert`, `None`, `None`。解析失败0，工具错误2，重复输入5，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/dask__fastparquet-961`。
- Q-PRUNER：`fastparquet/writer.py::convert`, `fastparquet/writer.py::time_shift`, `fastparquet/converted_types.py::convert`, `None`, `None`。解析失败0，工具错误2，重复输入5，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/dask__fastparquet-961`。

## aws-cloudformation__cfn-python-lint-4368

仓库：aws-cloudformation/cfn-python-lint；base：`e52850cf757a93a58d0535e775810a9e3f752792`；PR时间：2026-02-10 20:18:02；映射：partially_mappable。

gold文件：`src/cfnlint/jsonschema/_utils.py`。

可映射gold函数：`src/cfnlint/jsonschema/_utils.py::find_additional_properties`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 8.16 | 83827/549 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 27.23 | 110121/1957 | 3/3 | 3/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 73.22 | 27228/637 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 86.58 | 27228/637 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/cfnlint/rules/resources/CfnInit.py::CfnInit.validate`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/aws-cloudformation__cfn-python-lint-4368`。
- D-COSIL：`src/cfnlint/jsonschema/_keywords_cfn.py::additionalProperties`, `src/cfnlint/rules/resources/CfnInit.py::CfnInit.validate`, `src/cfnlint/jsonschema/_keywords.py::additionalProperties`, `None`, `src/cfnlint/rules/functions/_BaseFn.py::BaseFn.validate`。解析失败7，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/aws-cloudformation__cfn-python-lint-4368`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/aws-cloudformation__cfn-python-lint-4368`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/aws-cloudformation__cfn-python-lint-4368`。

## bodo-ai__PyDough-368

仓库：bodo-ai/PyDough；base：`bce6fc846fe739fd8a9d913574aa4998b6cb5b73`；PR时间：2025-06-15 02:15:37；映射：partially_mappable。

gold文件：`pydough/qdag/collections/collection_qdag.py`, `pydough/unqualified/qualification.py`。

可映射gold函数：`pydough/unqualified/qualification.py::Qualifier.qualify_best`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 9.59 | 72393/858 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 24.21 | 45528/1658 | 8/8 | 8/3 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 25.81 | 1410/358 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 27.73 | 1410/358 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`None`, `pydough/qdag/collections/singular.py::Singular.is_singular`, `pydough/qdag/collections/partition_by.py::PartitionBy.is_singular`, `pydough/conversion/hybrid_tree.py::HybridTree.is_singular`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/bodo-ai__PyDough-368`。
- D-COSIL：`pydough/qdag/collections/singular.py::Singular.is_singular`, `pydough/qdag/collections/partition_child.py::PartitionChild.is_singular`, `pydough/qdag/collections/partition_by.py::PartitionBy.is_singular`, `None`, `pydough/qdag/collections/singular.py::Singular.__init__`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/bodo-ai__PyDough-368`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/bodo-ai__PyDough-368`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/bodo-ai__PyDough-368`。

## sunpy__sunpy-8316

仓库：sunpy/sunpy；base：`480bdff57260a4f0e76aa62ae5a57006bedef8cb`；PR时间：2025-08-08 10:03:43+00:00；映射：fully_mappable。

gold文件：`sunpy/net/scraper.py`。

可映射gold函数：`sunpy/net/scraper.py::Scraper._localfilelist`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.55 | 38299/634 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.93 | 62416/1474 | 4/4 | 4/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 78.86 | 61846/1025 | 10/10 | 10/5 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 91.57 | 56872/955 | 5/10 | 5/5 |

各臂预测与证据：

- D-SIMPLE：`sunpy/net/scraper.py::Scraper._localfilelist`, `sunpy/net/scraper.py::Scraper._ftpfilelist`, `sunpy/net/scraper.py::Scraper._httpfilelist`, `sunpy/net/scraper.py::Scraper.filelist`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/sunpy__sunpy-8316`。
- D-COSIL：`sunpy/net/scraper.py::Scraper._localfilelist`, `sunpy/net/scraper.py::Scraper._httpfilelist`, `sunpy/net/scraper.py::Scraper._ftpfilelist`, `sunpy/net/scraper.py::Scraper.range`, `sunpy/net/scraper.py::Scraper.filelist`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/sunpy__sunpy-8316`。
- Q-COSIL：`sunpy/net/scraper.py::Scraper._localfilelist`, `sunpy/net/scraper.py::Scraper._ftpfilelist`, `sunpy/net/scraper.py::Scraper._httpfilelist`, `sunpy/net/scraper.py::Scraper.filelist`, `sunpy/net/scraper.py::Scraper.matches`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/sunpy__sunpy-8316`。
- Q-PRUNER：`sunpy/net/scraper.py::Scraper._localfilelist`, `None`, `None`, `sunpy/net/scraper.py::Scraper.range`, `sunpy/net/scraper_utils.py::extract_timestep`。解析失败0，工具错误5，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/sunpy__sunpy-8316`。

## beeware__briefcase-2241

仓库：beeware/briefcase；base：`9cb34242c89a20c67f9eae438d7c0a018346d6fb`；PR时间：2025-04-17 00:52:56；映射：fully_mappable。

gold文件：`automation/src/automation/bootstraps/pyside6.py`, `src/briefcase/bootstraps/pyside6.py`。

可映射gold函数：`automation/src/automation/bootstraps/pyside6.py::PySide6AutomationBootstrap.pyproject_table_macOS`, `src/briefcase/bootstraps/pyside6.py::PySide6GuiBootstrap.pyproject_table_briefcase_app_extra_content`, `src/briefcase/bootstraps/pyside6.py::PySide6GuiBootstrap.pyproject_table_macOS`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 9.10 | 63528/969 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 24.56 | 75492/1799 | 5/5 | 5/1 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 26.74 | 1013/386 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 37.31 | 1013/386 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/briefcase/platforms/macOS/__init__.py::macOSCreateMixin._install_app_requirements`, `src/briefcase/commands/create.py::CreateCommand._pip_install`, `src/briefcase/commands/create.py::CreateCommand._install_app_requirements`, `src/briefcase/commands/create.py::CreateCommand.install_app_requirements`, `src/briefcase/platforms/iOS/xcode.py::iOSXcodeCreateCommand._install_app_requirements`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/beeware__briefcase-2241`。
- D-COSIL：`src/briefcase/platforms/macOS/__init__.py::macOSCreateMixin._install_app_requirements`, `None`, `src/briefcase/platforms/macOS/app.py::macOSAppCreateCommand.install_app_support_package`, `src/briefcase/integrations/subprocess.py::Subprocess.run`, `src/briefcase/platforms/iOS/__init__.py::iOSMixin.verify_tools`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/beeware__briefcase-2241`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/beeware__briefcase-2241`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/beeware__briefcase-2241`。

## plone__cookieplone-templates-308

仓库：plone/cookieplone-templates；base：`f1a7c13dd20b219da12d5ed60704c528a6ce81db`；PR时间：2025-11-15 01:35:13；映射：unmappable。

gold文件：。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | NA | NA/NA | 6.66 | 34366/337 | 0/0 | 0/0 |
| D-COSIL | complete | NA | NA/NA | 25.70 | 35624/1334 | 10/10 | 10/0 |
| Q-COSIL | complete | NA | NA/NA | 100.80 | 32732/1192 | 10/10 | 10/0 |
| Q-PRUNER | complete | NA | NA/NA | 83.66 | 42441/1134 | 8/10 | 8/3 |

各臂预测与证据：

- D-SIMPLE：`templates/add-ons/backend/hooks/post_gen_project.py::main`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/plone__cookieplone-templates-308`。
- D-COSIL：`templates/sub/cache/hooks/post_gen_project.py::main`, `templates/sub/cache/hooks/post_gen_project.py::set_configurations`, `templates/sub/cache/hooks/post_gen_project.py::update_file`, `templates/add-ons/backend/hooks/post_gen_project.py::handle_git_initialization`, `templates/add-ons/backend/hooks/post_gen_project.py::main`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/plone__cookieplone-templates-308`。
- Q-COSIL：`templates/add-ons/backend/hooks/post_gen_project.py::handle_git_initialization`, `templates/add-ons/backend/hooks/post_gen_project.py::main`, `hooks/pre_prompt.py::main`, `templates/add-ons/backend/hooks/post_gen_project.py::generate_docs_starter`, `templates/add-ons/backend/hooks/post_gen_project.py::handle_format`。解析失败0，工具错误0，重复输入1，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/plone__cookieplone-templates-308`。
- Q-PRUNER：`templates/add-ons/backend/hooks/post_gen_project.py::handle_git_initialization`, `hooks/pre_prompt.py::main`, `None`, `None`, `None`。解析失败0，工具错误2，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/plone__cookieplone-templates-308`。

## ardupilot__methodicconfigurator-1201

仓库：ArduPilot/MethodicConfigurator；base：`3b385c0df0d2fde99f44ecae7f76374a50f6ba48`；PR时间：2026-01-22 20:37:40；映射：partially_mappable。

gold文件：`ardupilot_methodic_configurator/backend_flightcontroller_connection.py`。

可映射gold函数：`ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection._register_and_try_connect`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection.connect`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.10 | 101731/624 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 27.18 | 75241/1449 | 8/8 | 8/6 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 20.86 | 1369/272 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 22.11 | 1369/272 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection.connect`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection.create_connection_with_retry`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection._register_and_try_connect`, `ardupilot_methodic_configurator/backend_flightcontroller_factory_mavlink.py::SystemMavlinkConnectionFactory.create`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection._detect_vehicles_from_heartbeats`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/ardupilot__methodicconfigurator-1201`。
- D-COSIL：`ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection.connect`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection.create_connection_with_retry`, `ardupilot_methodic_configurator/backend_flightcontroller_factory_mavlink.py::SystemMavlinkConnectionFactory.create`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection._register_and_try_connect`, `ardupilot_methodic_configurator/backend_flightcontroller_connection.py::FlightControllerConnection._create_mavlink_connection`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/ardupilot__methodicconfigurator-1201`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/ardupilot__methodicconfigurator-1201`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/ardupilot__methodicconfigurator-1201`。

## pymc-devs__pytensor-1701

仓库：pymc-devs/pytensor；base：`60ba7c714a714dfbc1ec66cb5c8531dcd3ba1cf1`；PR时间：2025-10-28 10:15:24；映射：partially_mappable。

gold文件：`pytensor/scalar/basic.py`, `pytensor/tensor/variable.py`, `pytensor/xtensor/type.py`。

可映射gold函数：`pytensor/tensor/variable.py::_tensor_py_operators.__div__`, `pytensor/tensor/variable.py::_tensor_py_operators.__rdiv__`, `pytensor/xtensor/type.py::XTensorVariable.__div__`, `pytensor/xtensor/type.py::XTensorVariable.__rdiv__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 7.19 | 72136/257 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 29.15 | 171577/1831 | 4/5 | 4/4 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 128.07 | 191734/1411 | 3/10 | 3/2 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 135.01 | 190752/1360 | 7/10 | 7/1 |

各臂预测与证据：

- D-SIMPLE：`pytensor/scalar/basic.py::_scalar_py_operators.__truediv__`, `None`, `pytensor/scalar/basic.py::ScalarOp.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/pymc-devs__pytensor-1701`。
- D-COSIL：`pytensor/scalar/basic.py::_scalar_py_operators.__truediv__`, `None`, `pytensor/scalar/basic.py::LogicalComparison.__init__`, `pytensor/scalar/basic.py::ScalarOp.__init__`, `pytensor/graph/rewriting/unify.py::OpPattern.match_parameters`。解析失败3，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/pymc-devs__pytensor-1701`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误7，重复输入5，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/pymc-devs__pytensor-1701`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误3，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/pymc-devs__pytensor-1701`。

## psf__black-4676

仓库：psf/black；base：`24e4cb20ab03c20af390fec7303207af2a4a09e8`；PR时间：2025-06-01 00:52:41；映射：fully_mappable。

gold文件：`src/blib2to3/pgen2/tokenize.py`。

可映射gold函数：`src/blib2to3/pgen2/tokenize.py::tokenize`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.33 | 26741/396 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.36 | 51273/1443 | 7/7 | 7/1 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 24.64 | 1039/367 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 30.66 | 1039/367 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`src/blib2to3/pgen2/tokenize.py::tokenize`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/psf__black-4676`。
- D-COSIL：`src/blib2to3/pgen2/tokenize.py::tokenize`, `src/blib2to3/pgen2/driver.py::Driver.parse_tokens`, `src/blib2to3/pgen2/driver.py::TokenProxy.__next__`, `src/blib2to3/pgen2/parse.py::Parser.addtoken`, `src/black/parsing.py::lib2to3_parse`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/psf__black-4676`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/psf__black-4676`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/psf__black-4676`。

## XKNX__xknx-1663

仓库：XKNX/xknx；base：`12ad7c9c7e081d68a91005c8ea2e7f5aac6a7bde`；PR时间：2025-02-18 20:35:56；映射：fully_mappable。

gold文件：`xknx/devices/datetime.py`。

可映射gold函数：`xknx/devices/datetime.py::DateDevice.broadcast_localtime`, `xknx/devices/datetime.py::DateTimeDevice.broadcast_localtime`, `xknx/devices/datetime.py::TimeDevice.broadcast_localtime`, `xknx/devices/datetime.py::_DateTimeBase.__init__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.72 | 19163/484 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 24.19 | 49819/1169 | 8/8 | 8/6 |
| Q-COSIL | complete | 100.00% | 100.00%/25.00% | 71.84 | 37943/978 | 4/10 | 4/1 |
| Q-PRUNER | complete | 100.00% | 100.00%/25.00% | 74.42 | 38199/968 | 4/10 | 4/1 |

各臂预测与证据：

- D-SIMPLE：`xknx/devices/datetime.py::DateTimeDevice.broadcast_localtime`, `xknx/devices/datetime.py::_DateTimeBase.__init__`, `xknx/devices/datetime.py::TimeDevice.broadcast_localtime`, `xknx/devices/datetime.py::DateDevice.broadcast_localtime`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/XKNX__xknx-1663`。
- D-COSIL：`xknx/devices/datetime.py::_DateTimeBase.__init__`, `xknx/devices/datetime.py::DateTimeDevice.broadcast_localtime`, `xknx/devices/datetime.py::TimeDevice.broadcast_localtime`, `xknx/devices/datetime.py::DateDevice.broadcast_localtime`, `xknx/devices/datetime.py::_DateTimeBase.async_start_tasks`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/XKNX__xknx-1663`。
- Q-COSIL：`xknx/devices/datetime.py::DateTimeDevice.broadcast_localtime`, `None`, `None`, `None`。解析失败0，工具错误6，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/XKNX__xknx-1663`。
- Q-PRUNER：`xknx/devices/datetime.py::DateTimeDevice.broadcast_localtime`, `None`, `None`, `None`。解析失败0，工具错误6，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/XKNX__xknx-1663`。

## All-Hands-AI__OpenHands-10628

仓库：All-Hands-AI/OpenHands；base：`55d204ae1b5581b0e55ebbd6465c7e2211b26765`；PR时间：2025-08-26 13:03:10+00:00；映射：partially_mappable。

gold文件：`openhands/cli/utils.py`, `openhands/llm/model_features.py`, `openhands/utils/llm.py`。

可映射gold函数：`openhands/utils/llm.py::get_supported_llm_models`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.53 | 83164/776 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 27.43 | 56582/1051 | 8/8 | 8/4 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 41.72 | 3583/590 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 47.46 | 3583/590 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`openhands/llm/model_features.py::get_features`, `openhands/utils/llm.py::get_supported_llm_models`, `openhands/llm/llm.py::LLM.init_model_info`, `openhands/llm/llm.py::LLM.__init__`, `openhands/core/config/llm_config.py::LLMConfig.model_post_init`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/All-Hands-AI__OpenHands-10628`。
- D-COSIL：`openhands/utils/llm.py::get_supported_llm_models`, `openhands/llm/model_features.py::get_features`, `openhands/llm/model_features.py::model_matches`, `None`, `openhands/llm/model_features.py::normalize_model_name`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/All-Hands-AI__OpenHands-10628`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/All-Hands-AI__OpenHands-10628`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/All-Hands-AI__OpenHands-10628`。

## vitalik__django-ninja-1427

仓库：vitalik/django-ninja；base：`5610903485b4da008b27169688154ebf8d2637b3`；PR时间：2025-03-21 10:19:09；映射：fully_mappable。

gold文件：`ninja/operation.py`, `ninja/router.py`。

可映射gold函数：`ninja/operation.py::Operation._set_auth`, `ninja/operation.py::Operation.set_api_instance`, `ninja/router.py::Router.set_api_instance`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.51 | 21233/395 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 28.83 | 62505/2282 | 7/7 | 7/7 |
| Q-COSIL | complete | 100.00% | 100.00%/33.33% | 135.25 | 50121/1721 | 8/10 | 8/3 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 120.22 | 47711/1693 | 9/10 | 9/2 |

各臂预测与证据：

- D-SIMPLE：`ninja/operation.py::Operation.set_api_instance`, `ninja/router.py::Router.set_api_instance`, `ninja/main.py::NinjaAPI.add_router`, `ninja/operation.py::Operation._set_auth`, `ninja/router.py::Router.add_router`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/vitalik__django-ninja-1427`。
- D-COSIL：`ninja/operation.py::Operation.set_api_instance`, `ninja/operation.py::Operation._set_auth`, `ninja/router.py::Router.set_api_instance`, `ninja/router.py::Router.__init__`, `ninja/main.py::NinjaAPI.add_router`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/vitalik__django-ninja-1427`。
- Q-COSIL：`ninja/security/base.py::AuthBase.__call__`, `None`, `ninja/operation.py::Operation._set_auth`, `ninja/router.py::Router.add_router`, `ninja/router.py::Router.api_operation`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/vitalik__django-ninja-1427`。
- Q-PRUNER：`ninja/security/base.py::AuthBase.__call__`, `None`, `ninja/security/apikey.py::APIKeyBase.authenticate`, `ninja/security/http.py::HttpBearer.authenticate`, `ninja/security/http.py::HttpBasicAuth.authenticate`。解析失败0，工具错误1，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/vitalik__django-ninja-1427`。

## duo-labs__py_webauthn-241

仓库：duo-labs/py_webauthn；base：`aa365d75e58bb5c506226449a9b859897f024811`；PR时间：2025-01-16 22:04:58；映射：partially_mappable。

gold文件：`webauthn/authentication/verify_authentication_response.py`, `webauthn/registration/formats/android_safetynet.py`。

可映射gold函数：`webauthn/authentication/verify_authentication_response.py::verify_authentication_response`, `webauthn/registration/formats/android_safetynet.py::verify_android_safetynet`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/50.00% | 6.36 | 20524/355 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/50.00% | 20.51 | 66529/1393 | 4/4 | 4/3 |
| Q-COSIL | complete | 100.00% | 100.00%/50.00% | 100.78 | 69802/1404 | 4/10 | 4/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/50.00% | 104.03 | 71302/1384 | 4/10 | 4/4 |

各臂预测与证据：

- D-SIMPLE：`webauthn/registration/formats/android_safetynet.py::verify_android_safetynet`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/duo-labs__py_webauthn-241`。
- D-COSIL：`webauthn/registration/formats/android_safetynet.py::verify_android_safetynet`, `webauthn/registration/verify_registration_response.py::verify_registration_response`, `None`, `webauthn/helpers/verify_safetynet_timestamp.py::verify_safetynet_timestamp`, `webauthn/helpers/parse_attestation_statement.py::parse_attestation_statement`。解析失败5，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/duo-labs__py_webauthn-241`。
- Q-COSIL：`webauthn/registration/formats/android_safetynet.py::verify_android_safetynet`, `None`, `None`, `webauthn/helpers/parse_attestation_object.py::parse_attestation_object`, `webauthn/helpers/verify_signature.py::verify_signature`。解析失败0，工具错误6，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/duo-labs__py_webauthn-241`。
- Q-PRUNER：`webauthn/registration/formats/android_safetynet.py::verify_android_safetynet`, `None`, `None`, `webauthn/helpers/parse_attestation_object.py::parse_attestation_object`, `webauthn/helpers/verify_signature.py::verify_signature`。解析失败0，工具错误6，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/duo-labs__py_webauthn-241`。

## zwicker-group__py-pde-712

仓库：zwicker-group/py-pde；base：`619aa23acf4b07d5fbe2cf8757ca74c574a621fd`；PR时间：2025-09-05 14:32:41；映射：partially_mappable。

gold文件：`pde/storage/base.py`, `pde/trackers/base.py`, `pde/trackers/trackers.py`。

可映射gold函数：`pde/storage/base.py::StorageTracker.__init__`, `pde/storage/base.py::StorageTracker._transform`, `pde/trackers/trackers.py::LivePlotTracker.__init__`, `pde/trackers/trackers.py::PlotTracker.__init__`, `pde/trackers/trackers.py::PlotTracker.handle`, `pde/trackers/trackers.py::PlotTracker.initialize`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/83.33% | 7.46 | 28070/578 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/83.33% | 23.00 | 72664/1246 | 6/6 | 6/5 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 80.10 | 43651/1089 | 9/10 | 9/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 80.05 | 44178/1059 | 9/10 | 9/0 |

各臂预测与证据：

- D-SIMPLE：`pde/trackers/trackers.py::PlotTracker.__init__`, `pde/trackers/trackers.py::PlotTracker.initialize`, `pde/trackers/trackers.py::PlotTracker.handle`, `pde/storage/base.py::StorageTracker._transform`, `pde/storage/base.py::StorageTracker.__init__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/zwicker-group__py-pde-712`。
- D-COSIL：`pde/trackers/trackers.py::PlotTracker.__init__`, `pde/trackers/trackers.py::PlotTracker.handle`, `pde/trackers/trackers.py::PlotTracker.initialize`, `pde/storage/base.py::StorageTracker._transform`, `pde/storage/base.py::StorageTracker.__init__`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/zwicker-group__py-pde-712`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入4，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/zwicker-group__py-pde-712`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入4，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/zwicker-group__py-pde-712`。

## google__flax-4681

仓库：google/flax；base：`e16cfc44f85a9c4b26f3ebb28249ba49ce3e1527`；PR时间：2025-04-04 00:52:21；映射：partially_mappable。

gold文件：`flax/nnx/nn/lora.py`。

可映射gold函数：`flax/nnx/nn/lora.py::LoRA.__call__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 5.94 | 37547/313 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.89 | 45277/1869 | 0/0 | 0/0 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 130.93 | 69760/1741 | 9/10 | 9/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 137.14 | 69615/1696 | 9/10 | 9/4 |

各臂预测与证据：

- D-SIMPLE：`flax/nnx/nn/lora.py::LoRA.__call__`, `flax/nnx/nn/lora.py::LoRA.__init__`, `flax/nnx/nn/lora.py::LoRALinear.__call__`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/google__flax-4681`。
- D-COSIL：`flax/nnx/nn/lora.py::LoRA.__call__`, `flax/nnx/nn/lora.py::LoRALinear.__call__`, `flax/nnx/nn/lora.py::LoRA.__init__`, `flax/nnx/nn/lora.py::LoRALinear.__init__`, `flax/nnx/nn/dtypes.py::promote_dtype`。解析失败10，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/google__flax-4681`。
- Q-COSIL：`flax/nnx/nn/lora.py::LoRA.__call__`, `flax/nnx/nn/lora.py::LoRA.__init__`, `flax/nnx/bridge/module.py::Module.apply`, `flax/nnx/bridge/module.py::Module._get_variables`, `flax/nnx/bridge/module.py::Module.__getattribute__`。解析失败0，工具错误1，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/google__flax-4681`。
- Q-PRUNER：`flax/nnx/nn/lora.py::LoRA.__call__`, `flax/nnx/nn/lora.py::LoRA.__init__`, `flax/nnx/bridge/module.py::Module.apply`, `flax/nnx/bridge/module.py::Module._get_variables`, `flax/nnx/bridge/module.py::Module.__getattribute__`。解析失败0，工具错误1，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/google__flax-4681`。

## dask__dask-12096

仓库：dask/dask；base：`fabab2aa71fe443a4baa344bd3cf1b5245f36a92`；PR时间：2025-10-09 07:24:22；映射：fully_mappable。

gold文件：`dask/dataframe/dask_expr/_concat.py`。

可映射gold函数：`dask/dataframe/dask_expr/_concat.py::Concat._meta`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.80 | 84278/622 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 24.13 | 153104/1249 | 6/6 | 6/6 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 72.82 | 64952/903 | 6/10 | 6/5 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 86.68 | 66617/894 | 6/10 | 6/4 |

各臂预测与证据：

- D-SIMPLE：`dask/dataframe/dask_expr/_concat.py::Concat._meta`, `dask/dataframe/dask_expr/_concat.py::Concat._lower`, `dask/dataframe/dask_expr/_concat.py::StackPartition._layer`, `dask/dataframe/dask_expr/_collection.py::concat`, `dask/dataframe/dask_expr/_concat.py::Concat._simplify_up`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/dask__dask-12096`。
- D-COSIL：`dask/dataframe/dask_expr/_concat.py::Concat._meta`, `dask/dataframe/dask_expr/_concat.py::Concat._lower`, `dask/dataframe/dask_expr/_concat.py::StackPartition._layer`, `dask/dataframe/dask_expr/_concat.py::ConcatUnindexed.operation`, `dask/dataframe/dask_expr/_collection.py::concat`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/dask__dask-12096`。
- Q-COSIL：`dask/dataframe/dask_expr/_concat.py::Concat._lower`, `dask/dataframe/core.py::_concat`, `None`, `dask/dataframe/utils.py::check_matching_columns`, `None`。解析失败0，工具错误4，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/dask__dask-12096`。
- Q-PRUNER：`dask/dataframe/dask_expr/_concat.py::Concat._lower`, `dask/dataframe/dask_expr/_concat.py::Concat.interleave_partitions`, `dask/dataframe/core.py::_concat`, `dask/dataframe/utils.py::check_matching_columns`, `None`。解析失败0，工具错误4，重复输入2，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/dask__dask-12096`。

## scikit-rf__scikit-rf-1256

仓库：scikit-rf/scikit-rf；base：`7eeb700a91771ad7f604491bcf056c9b6013640e`；PR时间：2025-02-22 22:22:44；映射：fully_mappable。

gold文件：`skrf/network.py`。

可映射gold函数：`skrf/network.py::Network.plot_attribute`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.21 | 111217/181 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 18.50 | 76292/1349 | 3/3 | 2/1 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 128.00 | 98808/1718 | 10/10 | 5/1 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 96.60 | 21645/1203 | 2/2 | 1/1 |

各臂预测与证据：

- D-SIMPLE：`skrf/network.py::Network.plot_attribute`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/scikit-rf__scikit-rf-1256`。
- D-COSIL：`skrf/network.py::Network.plot_attribute`, `skrf/plotting.py::plot_rectangular`, `skrf/plotting.py::plot_complex_rectangular`, `skrf/plotting.py::plot_complex_polar`, `skrf/plotting.py::_get_label_str`。解析失败4，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/scikit-rf__scikit-rf-1256`。
- Q-COSIL：`skrf/network.py::Network.plot_attribute`, `skrf/network.py::Network.s`, `skrf/network.py::Network.y`, `skrf/network.py::Network.z`, `skrf/network.py::Network.t`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/scikit-rf__scikit-rf-1256`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；Cannot bind exact source function。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/scikit-rf__scikit-rf-1256`。

## libp2p__py-libp2p-533

仓库：libp2p/py-libp2p；base：`f6279c23ac5f124f64d530631d3027d05c9c4d28`；PR时间：2025-03-06 20:29:47；映射：unmappable。

gold文件：`libp2p/abc.py`, `libp2p/host/basic_host.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NA/NA | 8.41 | 28793/939 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NA/NA | 26.72 | 49501/1745 | 9/9 | 9/8 |
| Q-COSIL | complete | 0.00% | NA/NA | 86.09 | 39009/1180 | 9/10 | 9/0 |
| Q-PRUNER | complete | 0.00% | NA/NA | 93.30 | 39348/1150 | 9/10 | 9/0 |

各臂预测与证据：

- D-SIMPLE：`libp2p/network/swarm.py::Swarm.remove_conn`, `libp2p/network/connection/swarm_connection.py::SwarmConn._cleanup`, `libp2p/network/swarm.py::Swarm.close_peer`, `libp2p/host/basic_host.py::BasicHost.disconnect`, `libp2p/host/basic_host.py::BasicHost.get_connected_peers`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/libp2p__py-libp2p-533`。
- D-COSIL：`libp2p/network/swarm.py::Swarm.remove_conn`, `libp2p/network/connection/swarm_connection.py::SwarmConn._cleanup`, `libp2p/network/swarm.py::Swarm.notify_disconnected`, `libp2p/network/swarm.py::Swarm.close_peer`, `None`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/libp2p__py-libp2p-533`。
- Q-COSIL：`libp2p/peer/peerstore.py::PeerStore.add_addr`, `libp2p/peer/peerstore.py::PeerStore.clear_addrs`, `libp2p/peer/peerstore.py::PeerStore.peer_info`, `libp2p/host/routed_host.py::RoutedHost.connect`, `libp2p/security/noise/messages.py::NoiseHandshakePayload.serialize`。解析失败0，工具错误1，重复输入1，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/libp2p__py-libp2p-533`。
- Q-PRUNER：`libp2p/peer/peerstore.py::PeerStore.add_addr`, `libp2p/peer/peerstore.py::PeerStore.clear_addrs`, `libp2p/peer/peerstore.py::PeerStore.peer_info`, `libp2p/host/routed_host.py::RoutedHost.connect`, `libp2p/security/noise/messages.py::NoiseHandshakePayload.serialize`。解析失败0，工具错误1，重复输入1，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/libp2p__py-libp2p-533`。

## microsoft__fabric-cicd-465

仓库：microsoft/fabric-cicd；base：`74f59b95e0203e0c7dda5418d461a1f2723a8b4b`；PR时间：2025-08-06 18:42:36+00:00；映射：partially_mappable。

gold文件：`src/fabric_cicd/_common/_validate_input.py`, `src/fabric_cicd/fabric_workspace.py`, `src/fabric_cicd/publish.py`。

可映射gold函数：`src/fabric_cicd/_common/_validate_input.py::validate_item_type_in_scope`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace.__init__`, `src/fabric_cicd/publish.py::publish_all_items`, `src/fabric_cicd/publish.py::unpublish_all_orphan_items`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.98 | 22930/601 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 26.62 | 90532/2311 | 7/7 | 7/7 |
| Q-COSIL | complete | 100.00% | 100.00%/50.00% | 120.97 | 83988/1621 | 10/10 | 10/6 |
| Q-PRUNER | complete | 100.00% | 100.00%/75.00% | 121.04 | 82991/1573 | 10/10 | 10/5 |

各臂预测与证据：

- D-SIMPLE：`src/fabric_cicd/_common/_validate_input.py::validate_item_type_in_scope`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace.__init__`, `src/fabric_cicd/publish.py::publish_all_items`, `src/fabric_cicd/publish.py::unpublish_all_orphan_items`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/microsoft__fabric-cicd-465`。
- D-COSIL：`src/fabric_cicd/_common/_validate_input.py::validate_item_type_in_scope`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace.__init__`, `src/fabric_cicd/publish.py::publish_all_items`, `src/fabric_cicd/publish.py::unpublish_all_orphan_items`, `None`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/microsoft__fabric-cicd-465`。
- Q-COSIL：`src/fabric_cicd/publish.py::publish_all_items`, `src/fabric_cicd/publish.py::unpublish_all_orphan_items`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace._refresh_repository_items`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace._publish_item`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace._unpublish_item`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/microsoft__fabric-cicd-465`。
- Q-PRUNER：`src/fabric_cicd/publish.py::publish_all_items`, `src/fabric_cicd/publish.py::unpublish_all_orphan_items`, `None`, `src/fabric_cicd/fabric_workspace.py::FabricWorkspace._refresh_repository_items`, `src/fabric_cicd/_common/_validate_input.py::validate_item_type_in_scope`。解析失败0，工具错误0，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/microsoft__fabric-cicd-465`。

## UXARRAY__uxarray-1369

仓库：UXARRAY/uxarray；base：`d7431d7f23fef7770746535635ede1c7e482d167`；PR时间：2025-09-15 15:57:47；映射：fully_mappable。

gold文件：`uxarray/core/utils.py`。

可映射gold函数：`uxarray/core/utils.py::_validate_indexers`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 6.98 | 53446/327 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 21.64 | 78315/1432 | 6/6 | 6/4 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 114.96 | 115645/1472 | 10/10 | 10/7 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 121.17 | 131825/1472 | 10/10 | 10/7 |

各臂预测与证据：

- D-SIMPLE：`uxarray/core/dataarray.py::UxDataArray.isel`, `uxarray/grid/slice.py::_slice_face_indices`, `uxarray/grid/grid.py::Grid.isel`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/UXARRAY__uxarray-1369`。
- D-COSIL：`uxarray/grid/slice.py::_slice_face_indices`, `uxarray/grid/grid.py::Grid.isel`, `uxarray/core/dataarray.py::UxDataArray.isel`, `uxarray/core/dataset.py::UxDataset.isel`, `uxarray/grid/slice.py::_slice_edge_indices`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/UXARRAY__uxarray-1369`。
- Q-COSIL：`uxarray/core/dataarray.py::UxDataArray.isel`, `uxarray/grid/grid.py::Grid.isel`, `uxarray/grid/slice.py::_slice_face_indices`, `uxarray/io/_ugrid.py::_read_ugrid`, `uxarray/remap/accessor.py::RemapAccessor.__call__`。解析失败0，工具错误0，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/UXARRAY__uxarray-1369`。
- Q-PRUNER：`uxarray/core/dataarray.py::UxDataArray.isel`, `uxarray/grid/grid.py::Grid.isel`, `uxarray/grid/slice.py::_slice_face_indices`, `uxarray/io/_ugrid.py::_read_ugrid`, `uxarray/remap/accessor.py::RemapAccessor.__call__`。解析失败0，工具错误0，重复输入6，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/UXARRAY__uxarray-1369`。

## neurostuff__NiMARE-939

仓库：neurostuff/NiMARE；base：`7098b16657723159fd0b074f4fc22853774bfd8c`；PR时间：2025-08-05 20:19:37+00:00；映射：fully_mappable。

gold文件：`nimare/io.py`。

可映射gold函数：`nimare/io.py::convert_nimads_to_dataset._analysis_to_dict`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 8.63 | 69448/854 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | 0.00%/0.00% | 21.61 | 67451/1655 | 5/5 | 5/3 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 86.34 | 52384/1172 | 8/10 | 8/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 83.93 | 52032/1137 | 8/10 | 8/0 |

各臂预测与证据：

- D-SIMPLE：`nimare/meta/cbma/base.py::CBMAEstimator._preprocess_input`, `nimare/meta/kernel.py::KernelTransformer.transform`, `nimare/meta/kernel.py::ALEKernel._transform`, `nimare/meta/cbma/mkda.py::MKDADensity._compute_weights`, `nimare/meta/cbma/ale.py::ALE._generate_description`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/neurostuff__NiMARE-939`。
- D-COSIL：`nimare/meta/cbma/base.py::CBMAEstimator._preprocess_input`, `nimare/nimads.py::Studyset.to_dataset`, `nimare/dataset.py::Dataset._generic_column_getter`, `nimare/nimads.py::Analysis.get_metadata`, `nimare/dataset.py::Dataset.get_metadata`。解析失败5，工具错误0，重复输入1，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/neurostuff__NiMARE-939`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/neurostuff__NiMARE-939`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误2，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/neurostuff__NiMARE-939`。

## pybamm-team__PyBaMM-5061

仓库：pybamm-team/PyBaMM；base：`314490709f14c1c3c5df06beffa2aaa39dd14ad5`；PR时间：2025-06-16 13:35:56；映射：fully_mappable。

gold文件：`src/pybamm/expression_tree/interpolant.py`。

可映射gold函数：`src/pybamm/expression_tree/interpolant.py::Interpolant.__init__`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.99 | 68063/967 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.19 | 57076/1700 | 0/0 | 0/0 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 145.33 | 97756/1858 | 10/10 | 7/4 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 114.55 | 47977/1479 | 6/6 | 5/2 |

各臂预测与证据：

- D-SIMPLE：`src/pybamm/expression_tree/interpolant.py::Interpolant.__init__`, `src/pybamm/expression_tree/operations/convert_to_casadi.py::CasadiConverter._convert`, `src/pybamm/expression_tree/interpolant.py::Interpolant._function_evaluate`, `src/pybamm/parameters/parameter_values.py::ParameterValues._get_interpolant_events`, `src/pybamm/expression_tree/interpolant.py::Interpolant._function_diff`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/pybamm-team__PyBaMM-5061`。
- D-COSIL：`src/pybamm/expression_tree/interpolant.py::Interpolant.__init__`, `src/pybamm/expression_tree/interpolant.py::Interpolant._function_evaluate`, `src/pybamm/expression_tree/interpolant.py::Interpolant._function_diff`, `src/pybamm/expression_tree/operations/convert_to_casadi.py::CasadiConverter._convert`, `src/pybamm/expression_tree/operations/evaluate_python.py::to_python`。解析失败10，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/pybamm-team__PyBaMM-5061`。
- Q-COSIL：`src/pybamm/expression_tree/interpolant.py::Interpolant.__init__`, `src/pybamm/simulation.py::Simulation.solve`, `src/pybamm/simulation.py::Simulation.plot`, `src/pybamm/expression_tree/interpolant.py::Interpolant.to_json`。解析失败0，工具错误0，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/pybamm-team__PyBaMM-5061`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；Cannot bind exact source function。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/pybamm-team__PyBaMM-5061`。

## databricks__dbt-databricks-1428

仓库：databricks/dbt-databricks；base：`80e486c6dce6d10b13ef1705a8e9255bbc4a521b`；PR时间：2026-04-27 19:20:43；映射：partially_mappable。

gold文件：`dbt/adapters/databricks/impl.py`。

可映射gold函数：`dbt/adapters/databricks/impl.py::DatabricksAdapter._get_schema_for_catalog`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.21 | 32497/668 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.66 | 51817/1834 | 6/6 | 6/4 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 36.62 | 1333/497 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 39.24 | 1333/497 | 0/0 | 0/0 |

各臂预测与证据：

- D-SIMPLE：`dbt/adapters/databricks/impl.py::DatabricksAdapter._get_schema_for_catalog`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/databricks__dbt-databricks-1428`。
- D-COSIL：`dbt/adapters/databricks/impl.py::DatabricksAdapter._get_schema_for_catalog`, `dbt/adapters/databricks/impl.py::DatabricksAdapter._get_catalog_for_relation_map`, `dbt/adapters/databricks/impl.py::DatabricksAdapter.get_catalog`, `dbt/adapters/databricks/impl.py::DatabricksAdapter.get_catalog_by_relations`, `dbt/adapters/databricks/impl.py::DatabricksAdapter._get_columns_for_catalog`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/databricks__dbt-databricks-1428`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/databricks__dbt-databricks-1428`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/databricks__dbt-databricks-1428`。

## PennLINC__CuBIDS-438

仓库：PennLINC/CuBIDS；base：`df31e94bdd3d76a7d096e4f91439ebbe7e668594`；PR时间：2025-02-19 21:13:35；映射：fully_mappable。

gold文件：`cubids/utils.py`。

可映射gold函数：`cubids/utils.py::assign_variants`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.06 | 47734/407 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 28.08 | 62567/3326 | 5/5 | 5/3 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 79.98 | 57784/1099 | 9/10 | 9/1 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 93.93 | 63610/1069 | 9/10 | 9/1 |

各臂预测与证据：

- D-SIMPLE：`cubids/utils.py::assign_variants`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/PennLINC__CuBIDS-438`。
- D-COSIL：`cubids/utils.py::assign_variants`, `cubids/utils.py::format_params`, `cubids/cubids.py::CuBIDS.get_param_groups_dataframes`, `cubids/cubids.py::CuBIDS.get_param_groups_from_entity_set`, `cubids/utils.py::round_params`。解析失败3，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/PennLINC__CuBIDS-438`。
- Q-COSIL：`None`, `cubids/utils.py::format_params`, `None`, `cubids/metadata_merge.py::get_acq_dictionary`, `cubids/metadata_merge.py::merge_json_into_json`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/PennLINC__CuBIDS-438`。
- Q-PRUNER：`None`, `cubids/utils.py::format_params`, `None`, `cubids/metadata_merge.py::get_acq_dictionary`, `cubids/metadata_merge.py::merge_json_into_json`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/PennLINC__CuBIDS-438`。

## piskvorky__smart_open-892

仓库：piskvorky/smart_open；base：`8add46d09b1e4c29b0dbe33dce1602f41a504313`；PR时间：2025-10-11 19:46:17；映射：fully_mappable。

gold文件：`smart_open/s3.py`。

可映射gold函数：`smart_open/s3.py::Reader.seek`, `smart_open/s3.py::open`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 8.11 | 27212/589 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 24.47 | 64550/1022 | 9/9 | 9/5 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 127.86 | 61207/1782 | 7/10 | 7/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 132.07 | 64843/1782 | 7/10 | 7/0 |

各臂预测与证据：

- D-SIMPLE：`smart_open/s3.py::MultipartWriter.write`, `smart_open/s3.py::MultipartWriter._upload_next_part`, `smart_open/s3.py::Reader.read`, `smart_open/s3.py::Reader._fill_buffer`, `smart_open/s3.py::_SeekableRawReader.read`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/piskvorky__smart_open-892`。
- D-COSIL：`smart_open/s3.py::MultipartWriter.write`, `smart_open/s3.py::MultipartWriter._upload_next_part`, `smart_open/s3.py::Reader._fill_buffer`, `smart_open/s3.py::Reader.read`, `smart_open/s3.py::Reader._read_from_buffer`。解析失败1，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/piskvorky__smart_open-892`。
- Q-COSIL：`smart_open/s3.py::Reader._read_from_buffer`, `smart_open/s3.py::Reader._fill_buffer`, `None`, `smart_open/s3.py::_SeekableRawReader.read`, `smart_open/compression.py::get_supported_compression_types`。解析失败0，工具错误3，重复输入6，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/piskvorky__smart_open-892`。
- Q-PRUNER：`smart_open/s3.py::Reader._read_from_buffer`, `smart_open/s3.py::Reader._fill_buffer`, `None`, `smart_open/s3.py::_SeekableRawReader.read`, `smart_open/compression.py::get_supported_compression_types`。解析失败0，工具错误3，重复输入6，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/piskvorky__smart_open-892`。

## Ultraplot__UltraPlot-346

仓库：Ultraplot/UltraPlot；base：`4affafd75d9e446ada59ea4e9c8474b1ca2b7318`；PR时间：2025-09-15 07:17:00；映射：partially_mappable。

gold文件：`ultraplot/axes/cartesian.py`。

可映射gold函数：`ultraplot/axes/cartesian.py::CartesianAxes.format`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.46 | 111530/459 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 29.08 | 159048/1520 | 9/10 | 9/3 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 112.02 | 165314/1347 | 5/10 | 5/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 106.80 | 157798/1348 | 6/10 | 6/3 |

各臂预测与证据：

- D-SIMPLE：`ultraplot/axes/cartesian.py::CartesianAxes.format`, `ultraplot/axes/cartesian.py::CartesianAxes._update_labels`, `ultraplot/internals/rcsetup.py::_validate_units`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/Ultraplot__UltraPlot-346`。
- D-COSIL：`ultraplot/axes/cartesian.py::CartesianAxes.format`, `ultraplot/axes/base.py::Axes.format`, `ultraplot/internals/rcsetup.py::_validate_units`, `ultraplot/axes/cartesian.py::CartesianAxes._update_labels`, `ultraplot/internals/labels.py::_update_label`。解析失败0，工具错误1，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/Ultraplot__UltraPlot-346`。
- Q-COSIL：`ultraplot/axes/cartesian.py::CartesianAxes.format`, `ultraplot/axes/base.py::Axes.format`, `ultraplot/figure.py::Figure.format`, `None`, `ultraplot/gridspec.py::SubplotGrid.format`。解析失败0，工具错误5，重复输入4，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/Ultraplot__UltraPlot-346`。
- Q-PRUNER：`ultraplot/axes/cartesian.py::CartesianAxes.format`, `ultraplot/axes/base.py::Axes.format`, `ultraplot/figure.py::Figure.format`, `ultraplot/gridspec.py::GridSpec._auto_layout_tight`, `ultraplot/gridspec.py::SubplotGrid.format`。解析失败0，工具错误4，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/Ultraplot__UltraPlot-346`。

## googleapis__python-pubsub-1318

仓库：googleapis/python-pubsub；base：`f79d35a21a0e005613f1f80f8ad285da5af09abb`；PR时间：2025-01-06 01:18:56；映射：partially_mappable。

gold文件：`google/cloud/pubsub_v1/publisher/_batch/thread.py`。

可映射gold函数：`google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit`。

| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.68 | 37293/565 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 26.18 | 103007/1523 | 7/7 | 7/5 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 97.02 | 88762/1254 | 4/10 | 4/1 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 94.91 | 95137/1250 | 4/10 | 4/1 |

各臂预测与证据：

- D-SIMPLE：`google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit`, `google/cloud/pubsub_v1/publisher/client.py::Client._gapic_publish`, `google/pubsub_v1/services/publisher/client.py::PublisherClient._validate_universe_domain`。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-SIMPLE/googleapis__python-pubsub-1318`。
- D-COSIL：`google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit`, `google/cloud/pubsub_v1/publisher/client.py::Client._gapic_publish`, `google/pubsub_v1/services/publisher/client.py::PublisherClient._validate_universe_domain`, `google/pubsub_v1/services/publisher/client.py::PublisherClient._compare_universes`, `google/pubsub_v1/services/publisher/client.py::PublisherClient.publish`。解析失败2，工具错误0，重复输入0，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/googleapis__python-pubsub-1318`。
- Q-COSIL：`google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit`, `google/cloud/pubsub_v1/publisher/client.py::Client._gapic_publish`, `None`, `None`, `None`。解析失败0，工具错误6，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/googleapis__python-pubsub-1318`。
- Q-PRUNER：`google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit`, `google/cloud/pubsub_v1/publisher/client.py::Client._gapic_publish`, `None`, `None`, `None`。解析失败0，工具错误6，重复输入3，agent未收到源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/googleapis__python-pubsub-1318`。

