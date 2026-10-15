# GraphLocator + Qwen 适配v2：逐题分析

预测已冻结，以下为离线评分与日志审计。无函数真值为NA，失败和空预测分别显示。

## 1. astropy__astropy-12907

项目：astropy/astropy；本轮子集：开发集；状态：complete。

问题描述节选：

> Modeling's `separability_matrix` does not compute separability correctly for nested CompoundModels
> Consider the following model:
> 
> ```python
> from astropy.modeling import models as m
> from astropy.modeling.separable import separability_matrix
> 
> cm = m.Linear1D(10) & m.Linear1D(5)
> ```
> 
> It's separability matrix as you might expect is a diagonal:
> 
> ```python
> >>> separability_matrix(cm)
> array([[ True, False],
>        [False,  True]])
> ```
> 
> If I make the model more complex:
> ```python
> >>> separability_matrix(m.Pix2Sky_TAN() & m.Linear1D(10) & m.Linear1D(5))
> array([[ True,  True, False, False],
>        [ True,  True, False, False],
>        [False, False,  True, False],
>        [False, False, False,  True]])
> ```
> 
> The output matrix is again, as expected, the outputs and inputs to th

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["astropy/modeling/separable.py", "_cstack"]]`

新预测：`[["astropy/modeling/core.py", "<unresolved>:CompoundModel.n_outputs"], ["astropy/modeling/core.py", "Model.__call__"], ["astropy/modeling/core.py", "Model._calculate_separability_matrix"], ["astropy/modeling/core.py", "Model.n_outputs"], ["astropy/modeling/mappings.py", "Mapping.n_outputs"], ["astropy/modeling/mappings.py", "UnitsMapping.n_outputs"], ["astropy/modeling/separable.py", "_separable"], ["astropy/modeling/separable.py", "separability_matrix"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=210933/23230；耗时=2371.9秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["astropy/modeling/separable.py", "_cstack"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 32, "causal": 169}`。

无法唯一映射的函数：`[{"file": "astropy/modeling/core.py", "name": "CompoundModel.n_outputs", "reason": "absent"}]`

- A1：Incorrect computation；依据：；关联：`[["astropy/modeling/separable.py", "_operators"]]`
- A：Inaccurate recursive check；依据：；关联：`[["astropy/modeling/core.py", "Model.__call__"]]`
- A2：Wrong logic；依据：；关联：`[["astropy/timeseries/periodograms/bls/core.py", "core.py"]]`
- F：Nested CompoundModel handling failure；依据：；关联：`[["astropy/modeling/core.py", "Model._calculate_separability_matrix"], ["astropy/modeling/core.py", "CompoundModel"], ["astropy/modeling/separable.py", "separable.py"], ["astropy/modeling/separable.py", "_operators"], ["astropy/modeling/core.py", "Model"]]`
- E：_separable；依据：；关联：`[["astropy/modeling/separable.py", "_separable"]]`
- G：Default behavior not designed for nested models；依据：；关联：`[["astropy/modeling/core.py", "Model._calculate_separability_matrix"], ["astropy/modeling/separable.py", "separable.py"], ["astropy/modeling/separable.py", "_operators"], ["astropy/modeling/core.py", "Model"]]`
- H：Recursive check fails for nested models；依据：；关联：`[["astropy/modeling/separable.py", "_operators"], ["astropy/modeling/core.py", "Model._calculate_separability_matrix"], ["astropy/modeling/core.py", "CompoundModel"], ["astropy/modeling/separable.py", "separable.py"], ["astropy/modeling/separable.py", "_operators"], ["astropy/modeling/core.py", "Model"]]`
- D：n_outputs；依据：；关联：`[["astropy/modeling/core.py", "CompoundModel.n_outputs"], ["astropy/modeling/core.py", "Model.n_outputs"], ["astropy/modeling/mappings.py", "UnitsMapping.n_outputs"], ["astropy/modeling/mappings.py", "Mapping.n_outputs"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["astropy/modeling/separable.py", "separability_matrix"]]`
- C：Dependency on Product；依据：；关联：`[["astropy/modeling/separable.py", "separability_matrix"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/astropy__astropy-12907.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/astropy__astropy-12907.jsonl)

## 2. astropy__astropy-14182

项目：astropy/astropy；本轮子集：验证集；状态：complete。

问题描述节选：

> Please support header rows in RestructuredText output
> ### Description
> 
> It would be great if the following would work:
> 
> ```Python
> >>> from astropy.table import QTable
> >>> import astropy.units as u
> >>> import sys
> >>> tbl = QTable({'wave': [350,950]*u.nm, 'response': [0.7, 1.2]*u.count})
> >>> tbl.write(sys.stdout,  format="ascii.rst")
> ===== ========
>  wave response
> ===== ========
> 350.0      0.7
> 950.0      1.2
> ===== ========
> >>> tbl.write(sys.stdout,  format="ascii.fixed_width", header_rows=["name", "unit"])
> |  wave | response |
> |    nm |       ct |
> | 350.0 |      0.7 |
> | 950.0 |      1.2 |
> >>> tbl.write(sys.stdout,  format="ascii.rst", header_rows=["name", "unit"])
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "/usr/lib/python3/dist-pack

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["astropy/io/ascii/rst.py", "RST.__init__"], ["astropy/io/ascii/rst.py", "RST.read"], ["astropy/io/ascii/rst.py", "RST.write"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=15106/2520；耗时=206.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/astropy__astropy-14182.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/astropy__astropy-14182.jsonl)

## 3. astropy__astropy-14365

项目：astropy/astropy；本轮子集：验证集；状态：complete。

问题描述节选：

> ascii.qdp Table format assumes QDP commands are upper case
> ### Description
> 
> ascii.qdp assumes that commands in a QDP file are upper case, for example, for errors they must be "READ SERR 1 2" whereas QDP itself is not case sensitive and case use "read serr 1 2". 
> 
> As many QDP files are created by hand, the expectation that all commands be all-caps should be removed.
> 
> ### Expected behavior
> 
> The following qdp file should read into a `Table` with errors, rather than crashing.
> ```
> read serr 1 2 
> 1 0.5 1 0.5
> ```
> 
> ### How to Reproduce
> 
> Create a QDP file:
> ```
> > cat > test.qdp
> read serr 1 2 
> 1 0.5 1 0.5
> <EOF>
> 
>  > python
> Python 3.10.9 (main, Dec  7 2022, 02:03:23) [Clang 13.0.0 (clang-1300.0.29.30)] on darwin
> Type "help", "copyright", "credits" or "license" for more information.
> >>> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["astropy/io/ascii/qdp.py", "_get_tables_from_qdp_file"], ["astropy/io/ascii/qdp.py", "_line_type"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=6356/842；耗时=90.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/astropy__astropy-14365.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/astropy__astropy-14365.jsonl)

## 4. astropy__astropy-14995

项目：astropy/astropy；本轮子集：验证集；状态：complete。

问题描述节选：

> In v5.3, NDDataRef mask propagation fails when one of the operand does not have a mask
> ### Description
> 
> This applies to v5.3. 
> 
> It looks like when one of the operand does not have a mask, the mask propagation when doing arithmetic, in particular with `handle_mask=np.bitwise_or` fails.  This is not a problem in v5.2.
> 
> I don't know enough about how all that works, but it seems from the error that the operand without a mask is set as a mask of None's and then the bitwise_or tries to operate on an integer and a None and fails.
> 
> ### Expected behavior
> 
> When one of the operand does not have mask, the mask that exists should just be copied over to the output.  Or whatever was done in that situation in v5.2 where there's no problem.
> 
> ### How to Reproduce
> 
> This is with v5.3.   With v5.2, there a

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["astropy/nddata/mixins/ndarithmetic.py", "NDArithmeticMixin._arithmetic_mask"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=19962/4875；耗时=372.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/astropy__astropy-14995.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/astropy__astropy-14995.jsonl)

## 5. astropy__astropy-6938

项目：astropy/astropy；本轮子集：开发集；状态：complete。

问题描述节选：

> Possible bug in io.fits related to D exponents
> I came across the following code in ``fitsrec.py``:
> 
> ```python
>         # Replace exponent separator in floating point numbers
>         if 'D' in format:
>             output_field.replace(encode_ascii('E'), encode_ascii('D'))
> ```
> 
> I think this may be incorrect because as far as I can tell ``replace`` is not an in-place operation for ``chararray`` (it returns a copy). Commenting out this code doesn't cause any tests to fail so I think this code isn't being tested anyway.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["astropy/io/fits/fitsrec.py", "FITS_rec._scale_back_ascii"]]`

新预测：`[["astropy/table/bst.py", "Node.replace"], ["astropy/table/index.py", "SlicedIndex.replace"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=20723/7062；耗时=535.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 31}`。

- A1：Incorrect computation；依据：；关联：`[["astropy/table/index.py", "SlicedIndex"]]`
- A：Inaccurate recursive check；依据：；关联：`[["astropy/table/bst.py", "Node.replace"]]`
- A2：Wrong logic；依据：；关联：`[["", "self._frozen"]]`
- E：Non-in-place replacement of chararray；依据：；关联：`[["", "self.original"]]`
- F：Issue；依据：；关联：`[]`
- D：Potential in-place modification failure；依据：；关联：`[["astropy/table/index.py", "SlicedIndex"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["astropy/table/index.py", "SlicedIndex.replace"]]`
- C：Dependency on Product；依据：；关联：`[["astropy/table/index.py", "SlicedIndex.replace"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/astropy__astropy-6938.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/astropy__astropy-6938.jsonl)

## 6. astropy__astropy-7746

项目：astropy/astropy；本轮子集：开发集；状态：complete。

问题描述节选：

> Issue when passing empty lists/arrays to WCS transformations
> The following should not fail but instead should return empty lists/arrays:
> 
> ```
> In [1]: from astropy.wcs import WCS
> 
> In [2]: wcs = WCS('2MASS_h.fits')
> 
> In [3]: wcs.wcs_pix2world([], [], 0)
> ---------------------------------------------------------------------------
> InconsistentAxisTypesError                Traceback (most recent call last)
> <ipython-input-3-e2cc0e97941a> in <module>()
> ----> 1 wcs.wcs_pix2world([], [], 0)
> 
> ~/Dropbox/Code/Astropy/astropy/astropy/wcs/wcs.py in wcs_pix2world(self, *args, **kwargs)
>    1352         return self._array_converter(
>    1353             lambda xy, o: self.wcs.p2s(xy, o)['world'],
> -> 1354             'output', *args, **kwargs)
>    1355     wcs_pix2world.__doc__ = """
>    1356  

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |

共同严格目标：`[["astropy/wcs/wcs.py", "WCS._array_converter._return_list_of_arrays"], ["astropy/wcs/wcs.py", "WCS._array_converter._return_single_array"]]`

新预测：`[["astropy/wcs/wcs.py", "<unresolved>:WCS._return_list_of_arrays"], ["astropy/wcs/wcs.py", "<unresolved>:WCS._return_single_array"], ["astropy/wcs/wcs.py", "WCS._array_converter"], ["astropy/wcs/wcs.py", "WCS.all_world2pix"], ["astropy/wcs/wcs.py", "WCS.wcs_pix2world"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=47578/9823；耗时=740.5秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["astropy/wcs/wcs.py", "WCS._array_converter._return_list_of_arrays"], ["astropy/wcs/wcs.py", "WCS._array_converter._return_single_array"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 29}`。

无法唯一映射的函数：`[{"file": "astropy/wcs/wcs.py", "name": "WCS._return_list_of_arrays", "reason": "absent"}, {"file": "astropy/wcs/wcs.py", "name": "WCS._return_single_array", "reason": "absent"}]`

- D：self.naxis；依据：；关联：`[["", "self.naxis,"], ["", "self.naxis"]]`
- A：Inaccurate recursive check；依据：；关联：`[["astropy/wcs/wcs.py", "WCS._array_converter"]]`
- E：_return_list_of_arrays；依据：；关联：`[["astropy/wcs/wcs.py", "WCS._return_list_of_arrays"]]`
- F：_return_single_array；依据：；关联：`[["astropy/wcs/wcs.py", "WCS._return_single_array"]]`
- G：wcs_pix2world；依据：；关联：`[["astropy/wcs/wcs.py", "WCS.wcs_pix2world"]]`
- H：all_world2pix；依据：；关联：`[["astropy/wcs/wcs.py", "WCS.all_world2pix"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/astropy__astropy-7746.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/astropy__astropy-7746.jsonl)

## 7. django__django-10914

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Set default FILE_UPLOAD_PERMISSION to 0o644.
> Description
> 	
> Hello,
> As far as I can see, the ​File Uploads documentation page does not mention any permission issues.
> What I would like to see is a warning that in absence of explicitly configured FILE_UPLOAD_PERMISSIONS, the permissions for a file uploaded to FileSystemStorage might not be consistent depending on whether a MemoryUploadedFile or a TemporaryUploadedFile was used for temporary storage of the uploaded data (which, with the default FILE_UPLOAD_HANDLERS, in turn depends on the uploaded data size).
> The tempfile.NamedTemporaryFile + os.rename sequence causes the resulting file permissions to be 0o0600 on some systems (I experience it here on CentOS 7.4.1708 and Python 3.6.5). In all probability, the implementation of Python's built-in

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=6216/1029；耗时=119.2秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-10914.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-10914.jsonl)

## 8. django__django-10924

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Allow FilePathField path to accept a callable.
> Description
> 	
> I have a special case where I want to create a model containing the path to some local files on the server/dev machine. Seeing as the place where these files are stored is different on different machines I have the following:
> import os
> from django.conf import settings
> from django.db import models
> class LocalFiles(models.Model):
> 	name = models.CharField(max_length=255)
> 	file = models.FilePathField(path=os.path.join(settings.LOCAL_FILE_DIR, 'example_dir'))
> Now when running manage.py makemigrations it will resolve the path based on the machine it is being run on. Eg: /home/<username>/server_files/example_dir
> I had to manually change the migration to include the os.path.join() part to not break this when running the migration on prod

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "FilePathField.formfield"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12470/1930；耗时=186.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-10924.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-10924.jsonl)

## 9. django__django-11001

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Incorrect removal of order_by clause created as multiline RawSQL
> Description
> 	
> Hi.
> The SQLCompiler is ripping off one of my "order by" clause, because he "thinks" the clause was already "seen" (in SQLCompiler.get_order_by()). I'm using expressions written as multiline RawSQLs, which are similar but not the same. 
> The bug is located in SQLCompiler.get_order_by(), somewhere around line computing part of SQL query without ordering:
> without_ordering = self.ordering_parts.search(sql).group(1)
> The sql variable contains multiline sql. As a result, the self.ordering_parts regular expression is returning just a line containing ASC or DESC words. This line is added to seen set, and because my raw queries have identical last lines, only the first clasue is returing from SQLCompiler.get_order_by().
> As

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/compiler.py", "SQLCompiler.__init__"]]`

新预测：`[["django/db/models/sql/compiler.py", "SQLCompiler.get_order_by"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=27437/3791；耗时=389.0秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["django/db/models/sql/compiler.py", "SQLCompiler.__init__"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 19}`。

- A：Inaccurate recursive check；依据：；关联：`[["", "self.ordering_parts"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/models/sql/compiler.py", "SQLCompiler.get_order_by"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/models/sql/compiler.py", "SQLCompiler.get_order_by"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11001.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11001.jsonl)

## 10. django__django-11019

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Merging 3 or more media objects can throw unnecessary MediaOrderConflictWarnings
> Description
> 	
> Consider the following form definition, where text-editor-extras.js depends on text-editor.js but all other JS files are independent:
> from django import forms
> class ColorPicker(forms.Widget):
> 	class Media:
> 		js = ['color-picker.js']
> class SimpleTextWidget(forms.Widget):
> 	class Media:
> 		js = ['text-editor.js']
> class FancyTextWidget(forms.Widget):
> 	class Media:
> 		js = ['text-editor.js', 'text-editor-extras.js', 'color-picker.js']
> class MyForm(forms.Form):
> 	background_color = forms.CharField(widget=ColorPicker())
> 	intro = forms.CharField(widget=SimpleTextWidget())
> 	body = forms.CharField(widget=FancyTextWidget())
> Django should be able to resolve the JS files for the final form into the order text-ed

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 33.33% | 25.00% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/widgets.py", "Media._css"], ["django/forms/widgets.py", "Media._js"], ["django/forms/widgets.py", "Media.merge"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14694/2040；耗时=197.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11019.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11019.jsonl)

## 11. django__django-11039

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> sqlmigrate wraps it's outpout in BEGIN/COMMIT even if the database doesn't support transactional DDL
> Description
> 	 
> 		(last modified by Simon Charette)
> 	 
> The migration executor only adds the outer BEGIN/COMMIT ​if the migration is atomic and ​the schema editor can rollback DDL but the current sqlmigrate logic only takes migration.atomic into consideration.
> The issue can be addressed by
> Changing sqlmigrate ​assignment of self.output_transaction to consider connection.features.can_rollback_ddl as well.
> Adding a test in tests/migrations/test_commands.py based on ​an existing test for non-atomic migrations that mocks connection.features.can_rollback_ddl to False instead of overdidding MIGRATION_MODULES to point to a non-atomic migration.
> I marked the ticket as easy picking because I included 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/management/commands/sqlmigrate.py", "Command.handle"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4570/808；耗时=105.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11039.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11039.jsonl)

## 12. django__django-11049

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Correct expected format in invalid DurationField error message
> Description
> 	
> If you enter a duration "14:00" into a duration field, it translates to "00:14:00" which is 14 minutes.
> The current error message for invalid DurationField says that this should be the format of durations: "[DD] [HH:[MM:]]ss[.uuuuuu]". But according to the actual behaviour, it should be: "[DD] [[HH:]MM:]ss[.uuuuuu]", because seconds are mandatory, minutes are optional, and hours are optional if minutes are provided.
> This seems to be a mistake in all Django versions that support the DurationField.
> Also the duration fields could have a default help_text with the requested format, because the syntax is not self-explanatory.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12452/1805；耗时=176.7秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11049.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11049.jsonl)

## 13. django__django-11099

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> UsernameValidator allows trailing newline in usernames
> Description
> 	
> ASCIIUsernameValidator and UnicodeUsernameValidator use the regex 
> r'^[\w.@+-]+$'
> The intent is to only allow alphanumeric characters as well as ., @, +, and -. However, a little known quirk of Python regexes is that $ will also match a trailing newline. Therefore, the user name validators will accept usernames which end with a newline. You can avoid this behavior by instead using \A and \Z to terminate regexes. For example, the validator regex could be changed to
> r'\A[\w.@+-]+\Z'
> in order to reject usernames that end with a newline.
> I am not sure how to officially post a patch, but the required change is trivial - using the regex above in the two validators in contrib.auth.validators.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[["django/contrib/auth/management/commands/createsuperuser.py", "Command._validate_username"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=15347/2260；耗时=232.9秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/auth/management/commands/createsuperuser.py", "Command._validate_username"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11099.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11099.jsonl)

## 14. django__django-11133

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> HttpResponse doesn't handle memoryview objects
> Description
> 	
> I am trying to write a BinaryField retrieved from the database into a HttpResponse. When the database is Sqlite this works correctly, but Postgresql returns the contents of the field as a memoryview object and it seems like current Django doesn't like this combination:
> from django.http import HttpResponse																	 
> # String content
> response = HttpResponse("My Content")																			
> response.content																								 
> # Out: b'My Content'
> # This is correct
> # Bytes content
> response = HttpResponse(b"My Content")																		 
> response.content																								 
> # Out: b'My Content'
> # This is also correct
> # memoryview content
> response = HttpResponse(memoryview(b"My Content"))															 
> response.co

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/http/response.py", "HttpResponseBase.make_bytes"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12588/2585；耗时=225.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11133.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11133.jsonl)

## 15. django__django-11179

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> delete() on instances of models without any dependencies doesn't clear PKs.
> Description
> 	
> Deleting any model with no dependencies not updates the PK on the model. It should be set to None after .delete() call.
> See Django.db.models.deletion:276-281. Should update the model line 280.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/deletion.py", "Collector.delete"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11436/1739；耗时=164.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11179.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11179.jsonl)

## 16. django__django-11283

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Migration auth.0011_update_proxy_permissions fails for models recreated as a proxy.
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> I am trying to update my project to Django 2.2. When I launch python manage.py migrate, I get this error message when migration auth.0011_update_proxy_permissions is applying (full stacktrace is available ​here):
> django.db.utils.IntegrityError: duplicate key value violates unique constraint "idx_18141_auth_permission_content_type_id_01ab375a_uniq" DETAIL: Key (co.ntent_type_id, codename)=(12, add_agency) already exists.
> It looks like the migration is trying to re-create already existing entries in the auth_permission table. At first I though it cloud because we recently renamed a model. But after digging and deleting the entries associated with the ren

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/auth/migrations/0011_update_proxy_permissions.py", "update_proxy_model_permissions"]]`

新预测：`[["django/contrib/contenttypes/management/__init__.py", "RenameContentType._rename"], ["django/contrib/contenttypes/management/__init__.py", "RenameContentType.rename_backward"], ["django/contrib/contenttypes/management/__init__.py", "RenameContentType.rename_forward"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=40489/9734；耗时=759.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 64, "causal": 6}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/contenttypes/management/__init__.py", "RenameContentType.rename_backward"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/contenttypes/management/__init__.py", "RenameContentType._rename"]]`
- A2：Wrong logic；依据：；关联：`[["django/contrib/contenttypes/management/__init__.py", "RenameContentType"]]`
- F1：Duplicate `ContentType` entry；依据：；关联：`[["", "self.new_model,"]]`
- F2：Incorrect `ContentType` retrieval；依据：；关联：`[["", "self.old_model"]]`
- F3：Stale `ContentType` causing conflict；依据：；关联：`[["", "self.new_model,"]]`
- D：Incorrect use of `rename_backward`；依据：；关联：`[["django/contrib/contenttypes/management/__init__.py", "RenameContentType.rename_backward"]]`
- E：Incorrect use of `rename_forward`；依据：；关联：`[["django/contrib/contenttypes/management/__init__.py", "RenameContentType.rename_forward"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11283.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11283.jsonl)

## 17. django__django-11422

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Autoreloader with StatReloader doesn't track changes in manage.py.
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> This is a bit convoluted, but here we go.
> Environment (OSX 10.11):
> $ python -V
> Python 3.6.2
> $ pip -V
> pip 19.1.1
> $ pip install Django==2.2.1
> Steps to reproduce:
> Run a server python manage.py runserver
> Edit the manage.py file, e.g. add print(): 
> def main():
> 	print('sth')
> 	os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket_30479.settings')
> 	...
> Under 2.1.8 (and prior), this will trigger the auto-reloading mechanism. Under 2.2.1, it won't. As far as I can tell from the django.utils.autoreload log lines, it never sees the manage.py itself.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/utils/autoreload.py", "iter_modules_and_files"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=4191/821；耗时=121.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[["tests/i18n/sampleproject/manage.py", "manage.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11422.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11422.jsonl)

## 18. django__django-11564

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Add support for SCRIPT_NAME in STATIC_URL and MEDIA_URL
> Description
> 	 
> 		(last modified by Rostyslav Bryzgunov)
> 	 
> By default, {% static '...' %} tag just appends STATIC_URL in the path. When running on sub-path, using SCRIPT_NAME WSGI param, it results in incorrect static URL - it doesn't prepend SCRIPT_NAME prefix.
> This problem can be solved with prepending SCRIPT_NAME to STATIC_URL in settings.py but that doesn't work when SCRIPT_NAME is a dynamic value.
> This can be easily added into default Django static tag and django.contrib.staticfiles tag as following:
> def render(self, context):
> 	url = self.url(context)
> 	# Updating url here with request.META['SCRIPT_NAME'] 
> 	if self.varname is None:
> 		return url
> 	context[self.varname] = url
> 		return ''
> On more research I found that FileSystemStorag

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/conf/__init__.py", "LazySettings.MEDIA_URL"], ["django/conf/__init__.py", "LazySettings.STATIC_URL"], ["django/conf/__init__.py", "LazySettings._add_script_prefix"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11915/1890；耗时=180.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11564.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11564.jsonl)

## 19. django__django-11583

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Auto-reloading with StatReloader very intermittently throws "ValueError: embedded null byte".
> Description
> 	
> Raising this mainly so that it's tracked, as I have no idea how to reproduce it, nor why it's happening. It ultimately looks like a problem with Pathlib, which wasn't used prior to 2.2.
> Stacktrace:
> Traceback (most recent call last):
>  File "manage.py" ...
> 	execute_from_command_line(sys.argv)
>  File "/Userz/kez/path/to/venv/lib/python3.6/site-packages/django/core/management/__init__.py", line 381, in execute_from_command_line
> 	utility.execute()
>  File "/Userz/kez/path/to/venv/lib/python3.6/site-packages/django/core/management/__init__.py", line 375, in execute
> 	self.fetch_command(subcommand).run_from_argv(self.argv)
>  File "/Userz/kez/path/to/venv/lib/python3.6/site-packages/django/core/m

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/utils/autoreload.py", "iter_modules_and_files"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=16774/2519；耗时=223.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Null byte in path；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11583.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11583.jsonl)

## 20. django__django-11620

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> When DEBUG is True, raising Http404 in a path converter's to_python method does not result in a technical response
> Description
> 	
> This is the response I get (plain text): 
> A server error occurred. Please contact the administrator.
> I understand a ValueError should be raised which tells the URL resolver "this path does not match, try next one" but Http404 is what came to my mind intuitively and the error message was not very helpful.
> One could also make a point that raising a Http404 should be valid way to tell the resolver "this is indeed the right path but the current parameter value does not match anything so stop what you are doing and let the handler return the 404 page (including a helpful error message when DEBUG is True instead of the default 'Django tried these URL patterns')".
> This 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/views/debug.py", "technical_404_response"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12937/2233；耗时=205.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11620.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11620.jsonl)

## 21. django__django-11630

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Django throws error when different apps with different models have the same name table name.
> Description
> 	
> Error message:
> table_name: (models.E028) db_table 'table_name' is used by multiple models: base.ModelName, app2.ModelName.
> We have a Base app that points to a central database and that has its own tables. We then have multiple Apps that talk to their own databases. Some share the same table names.
> We have used this setup for a while, but after upgrading to Django 2.2 we're getting an error saying we're not allowed 2 apps, with 2 different models to have the same table names. 
> Is this correct behavior? We've had to roll back to Django 2.0 for now.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/checks/model_checks.py", "check_all_models"]]`

新预测：`[["django/contrib/gis/db/backends/postgis/schema.py", "PostGISSchemaEditor._create_index_sql"], ["django/db/backends/base/schema.py", "BaseDatabaseSchemaEditor._alter_field"], ["django/db/backends/postgresql/schema.py", "DatabaseSchemaEditor._alter_field"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=79815/9247；耗时=815.1秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["django/core/checks/model_checks.py", "check_all_models"]], "seeds": [["django/core/checks/model_checks.py", "check_all_models"]], "causal_received": [["django/core/checks/model_checks.py", "check_all_models"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 32, "causal": 35}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/gis/db/backends/postgis/schema.py", "PostGISSchemaEditor"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/gis/db/backends/postgis/schema.py", "PostGISSchemaEditor._create_index_sql"]]`
- A2：Wrong logic；依据：；关联：`[["", "self.rast_index_wrapper"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/backends/base/schema.py", "BaseDatabaseSchemaEditor._alter_field"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/backends/base/schema.py", "BaseDatabaseSchemaEditor._alter_field"]]`
- D：Same table name conflict；依据：；关联：`[["django/db/backends/postgresql/schema.py", "DatabaseSchemaEditor._alter_field"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11630.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11630.jsonl)

## 22. django__django-11742

项目：django/django；本轮子集：验证集；状态：failed。

问题描述节选：

> Add check to ensure max_length fits longest choice.
> Description
> 	
> There is currently no check to ensure that Field.max_length is large enough to fit the longest value in Field.choices.
> This would be very helpful as often this mistake is not noticed until an attempt is made to save a record with those values that are too long.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "Field._check_choices"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=19027/3797；耗时=413.2秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 24}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/django__django-11742.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11742.jsonl)

## 23. django__django-11797

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Filtering on query result overrides GROUP BY of internal query
> Description
> 	
> from django.contrib.auth import models
> a = models.User.objects.filter(email__isnull=True).values('email').annotate(m=Max('id')).values('m')
> print(a.query) # good
> # SELECT MAX("auth_user"."id") AS "m" FROM "auth_user" WHERE "auth_user"."email" IS NULL GROUP BY "auth_user"."email"
> print(a[:1].query) # good
> # SELECT MAX("auth_user"."id") AS "m" FROM "auth_user" WHERE "auth_user"."email" IS NULL GROUP BY "auth_user"."email" LIMIT 1
> b = models.User.objects.filter(id=a[:1])
> print(b.query) # GROUP BY U0."id" should be GROUP BY U0."email"
> # SELECT ... FROM "auth_user" WHERE "auth_user"."id" = (SELECT U0."id" FROM "auth_user" U0 WHERE U0."email" IS NULL GROUP BY U0."id" LIMIT 1)

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/lookups.py", "Exact.process_rhs"]]`

新预测：`[["django/db/models/query.py", "QuerySet.filter"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=21017/2461；耗时=268.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 12, "causal": 19}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/query.py", "QuerySet.filter"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11797.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11797.jsonl)

## 24. django__django-11815

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Migrations uses value of enum object instead of its name.
> Description
> 	 
> 		(last modified by oasl)
> 	 
> When using Enum object as a default value for a CharField, the generated migration file uses the value of the Enum object instead of the its name. This causes a problem when using Django translation on the value of the Enum object. 
> The problem is that, when the Enum object value get translated to the users language, the old migration files raise an error stating that the Enum does not have the corresponding value. (because the Enum value is translated to another language)
> Example:
> Let say we have this code in models.py:
> from enum import Enum
> from django.utils.translation import gettext_lazy as _
> from django.db import models
> class Status(Enum):
> 	GOOD = _('Good') # 'Good' will be translated

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/serializer.py", "EnumSerializer.serialize"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14489/2243；耗时=201.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11815.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11815.jsonl)

## 25. django__django-11848

项目：django/django；本轮子集：开发集；状态：complete。

问题描述节选：

> django.utils.http.parse_http_date two digit year check is incorrect
> Description
> 	 
> 		(last modified by Ad Timmering)
> 	 
> RFC 850 does not mention this, but in RFC 7231 (and there's something similar in RFC 2822), there's the following quote:
> Recipients of a timestamp value in rfc850-date format, which uses a
> two-digit year, MUST interpret a timestamp that appears to be more
> than 50 years in the future as representing the most recent year in
> the past that had the same last two digits.
> Current logic is hard coded to consider 0-69 to be in 2000-2069, and 70-99 to be 1970-1999, instead of comparing versus the current year.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |

共同严格目标：`[["django/utils/http.py", "parse_http_date"]]`

新预测：`[["django/utils/http.py", "parse_http_date"], ["tests/utils_tests/test_http.py", "HttpDateProcessingTests.test_parsing_rfc850"], ["tests/utils_tests/test_http.py", "HttpDateProcessingTests.test_parsing_year_less_than_70"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=16300/5742；耗时=507.5秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/utils/http.py", "parse_http_date"]], "seeds": [["django/utils/http.py", "parse_http_date"]], "causal_received": [["django/utils/http.py", "parse_http_date"]], "final": [["django/utils/http.py", "parse_http_date"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 7}`。

- A2：Wrong logic；依据：；关联：`[["django/utils/http.py", "RFC850_DATE"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/utils/http.py", "parse_http_date"]]`
- A1：Incorrect computation；依据：；关联：`[["tests/utils_tests/test_http.py", "HttpDateProcessingTests.test_parsing_year_less_than_70"]]`
- E：test_parsing_year_less_than_70；依据：；关联：`[["tests/utils_tests/test_http.py", "HttpDateProcessingTests.test_parsing_year_less_than_70"]]`
- D：Issue；依据：；关联：`[]`
- F：test_parsing_rfc850；依据：；关联：`[["tests/utils_tests/test_http.py", "HttpDateProcessingTests.test_parsing_rfc850"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11848.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11848.jsonl)

## 26. django__django-11905

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Prevent using __isnull lookup with non-boolean value.
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> __isnull should not allow for non-boolean values. Using truthy/falsey doesn't promote INNER JOIN to an OUTER JOIN but works fine for a simple queries. Using non-boolean values is ​undocumented and untested. IMO we should raise an error for non-boolean values to avoid confusion and for consistency.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/lookups.py", "IsNull.as_sql"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=3965/796；耗时=102.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11905.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11905.jsonl)

## 27. django__django-11910

项目：django/django；本轮子集：开发集；状态：complete。

问题描述节选：

> ForeignKey's to_field parameter gets the old field's name when renaming a PrimaryKey.
> Description
> 	
> Having these two models 
> class ModelA(models.Model):
> 	field_wrong = models.CharField('field1', max_length=50, primary_key=True) # I'm a Primary key.
> class ModelB(models.Model):
> 	field_fk = models.ForeignKey(ModelA, blank=True, null=True, on_delete=models.CASCADE) 
> ... migrations applyed ...
> the ModelA.field_wrong field has been renamed ... and Django recognizes the "renaming"
> # Primary key renamed
> class ModelA(models.Model):
> 	field_fixed = models.CharField('field1', max_length=50, primary_key=True) # I'm a Primary key.
> Attempts to to_field parameter. 
> The to_field points to the old_name (field_typo) and not to the new one ("field_fixed")
> class Migration(migrations.Migration):
> 	dependencies =

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/autodetector.py", "MigrationAutodetector.generate_altered_fields"]]`

新预测：`[["django/contrib/admin/views/main.py", "ChangeList.__init__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=39371/9625；耗时=944.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 19}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/admin/views/main.py", "ChangeList.__init__"]]`
- A：Inaccurate recursive check；依据：；关联：`[["", "self.to_field"]]`
- A2：Wrong logic；依据：；关联：`[["django/forms/models.py", "InlineForeignKeyField"]]`
- D：Migration operation not updating to_field]；依据：；关联：`[["django/contrib/admin/views/main.py", "ChangeList"]]`
- C：Dependency on Product；依据：；关联：`[]`
- E：Incorrect handling of ForeignKey to_field；依据：；关联：`[]`
- F：Product dependency causing incorrect to_field handling；依据：；关联：`[]`
- G：Product dependency causing incorrect to_field handling；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11910.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11910.jsonl)

## 28. django__django-11964

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> The value of a TextChoices/IntegerChoices field has a differing type
> Description
> 	
> If we create an instance of a model having a CharField or IntegerField with the keyword choices pointing to IntegerChoices or TextChoices, the value returned by the getter of the field will be of the same type as the one created by enum.Enum (enum value).
> For example, this model:
> from django.db import models
> from django.utils.translation import gettext_lazy as _
> class MyChoice(models.TextChoices):
> 	FIRST_CHOICE = "first", _("The first choice, it is")
> 	SECOND_CHOICE = "second", _("The second choice, it is")
> class MyObject(models.Model):
> 	my_str_value = models.CharField(max_length=10, choices=MyChoice.choices)
> Then this test:
> from django.test import TestCase
> from testing.pkg.models import MyObject, MyChoice
> cl

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/enums.py", "Choices.__str__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=10459/1488；耗时=167.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11964.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11964.jsonl)

## 29. django__django-11999

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Cannot override get_FOO_display() in Django 2.2+.
> Description
> 	
> I cannot override the get_FIELD_display function on models since version 2.2. It works in version 2.1.
> Example:
> class FooBar(models.Model):
> 	foo_bar = models.CharField(_("foo"), choices=[(1, 'foo'), (2, 'bar')])
> 	def __str__(self):
> 		return self.get_foo_bar_display() # This returns 'foo' or 'bar' in 2.2, but 'something' in 2.1
> 	def get_foo_bar_display(self):
> 		return "something"
> What I expect is that I should be able to override this function.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "Field.contribute_to_class"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4322/1237；耗时=130.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-11999.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-11999.jsonl)

## 30. django__django-12113

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> admin_views.test_multidb fails with persistent test SQLite database.
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> I've tried using persistent SQLite databases for the tests (to make use of
> --keepdb), but at least some test fails with:
> sqlite3.OperationalError: database is locked
> This is not an issue when only using TEST["NAME"] with "default" (which is good enough in terms of performance).
> diff --git i/tests/test_sqlite.py w/tests/test_sqlite.py
> index f1b65f7d01..9ce4e32e14 100644
> --- i/tests/test_sqlite.py
> +++ w/tests/test_sqlite.py
> @@ -15,9 +15,15 @@
>  DATABASES = {
> 	 'default': {
> 		 'ENGINE': 'django.db.backends.sqlite3',
> +		'TEST': {
> +			'NAME': 'test_default.sqlite3'
> +		},
> 	 },
> 	 'other': {
> 		 'ENGINE': 'django.db.backends.sqlite3',
> +		'TEST': {
> +			'NAME': 'test_other.sqlit

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/backends/sqlite3/creation.py", "DatabaseCreation.test_db_signature"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=27213/2814；耗时=260.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12113.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12113.jsonl)

## 31. django__django-12125

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> makemigrations produces incorrect path for inner classes
> Description
> 	
> When you define a subclass from django.db.models.Field as an inner class of some other class, and use this field inside a django.db.models.Model class, then when you run manage.py makemigrations, a migrations file is created which refers to the inner class as if it were a top-level class of the module it is in.
> To reproduce, create the following as your model:
> class Outer(object):
> 	class Inner(models.CharField):
> 		pass
> class A(models.Model):
> 	field = Outer.Inner(max_length=20)
> After running manage.py makemigrations, the generated migrations file contains the following:
> migrations.CreateModel(
> 	name='A',
> 	fields=[
> 		('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
> 		('fie

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/serializer.py", "TypeSerializer.serialize"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14515/1968；耗时=181.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12125.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12125.jsonl)

## 32. django__django-12184

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Optional URL params crash some view functions.
> Description
> 	
> My use case, running fine with Django until 2.2:
> URLConf:
> urlpatterns += [
> 	...
> 	re_path(r'^module/(?P<format>(html|json|xml))?/?$', views.modules, name='modules'),
> ]
> View:
> def modules(request, format='html'):
> 	...
> 	return render(...)
> With Django 3.0, this is now producing an error:
> Traceback (most recent call last):
>  File "/l10n/venv/lib/python3.6/site-packages/django/core/handlers/exception.py", line 34, in inner
> 	response = get_response(request)
>  File "/l10n/venv/lib/python3.6/site-packages/django/core/handlers/base.py", line 115, in _get_response
> 	response = self.process_exception_by_middleware(e, request)
>  File "/l10n/venv/lib/python3.6/site-packages/django/core/handlers/base.py", line 113, in _get_response
> 	response = wrapp

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/urls/resolvers.py", "RegexPattern.match"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=7803/1703；耗时=171.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A1：Incorrect handling of optional parameters；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12184.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12184.jsonl)

## 33. django__django-12284

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Model.get_FOO_display() does not work correctly with inherited choices.
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> Given a base model with choices A containing 3 tuples
> Child Model inherits the base model overrides the choices A and adds 2 more tuples
> get_foo_display does not work correctly for the new tuples added
> Example:
> class A(models.Model):
>  foo_choice = [("A","output1"),("B","output2")]
>  field_foo = models.CharField(max_length=254,choices=foo_choice)
>  class Meta:
> 	 abstract = True
> class B(A):
>  foo_choice = [("A","output1"),("B","output2"),("C","output3")]
>  field_foo = models.CharField(max_length=254,choices=foo_choice)
> Upon invoking get_field_foo_display() on instance of B , 
> For value "A" and "B" the output works correctly i.e. returns "output1" / "output2"
> but for val

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "Field.contribute_to_class"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4885/1142；耗时=123.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12284.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12284.jsonl)

## 34. django__django-12286

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> translation.E004 shouldn't be raised on sublanguages when a base language is available.
> Description
> 	
> According to Django documentation:
> If a base language is available but the sublanguage specified is not, Django uses the base language. For example, if a user specifies de-at (Austrian German) but Django only has de available, Django uses de.
> However, when using Django 3.0.2, if my settings.py has
> LANGUAGE_CODE = "de-at"
> I get this error message:
> SystemCheckError: System check identified some issues:
> ERRORS:
> ?: (translation.E004) You have provided a value for the LANGUAGE_CODE setting that is not in the LANGUAGES setting.
> If using
> LANGUAGE_CODE = "es-ar"
> Django works fine (es-ar is one of the translations provided out of the box).

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/checks/translation.py", "check_language_settings_consistent"]]`

新预测：`[]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=8318/1922；耗时=228.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 1}`。

- A：Inaccurate recursive check；依据：；关联：`[["tests/admin_scripts/custom_templates/project_template/project_name/settings.py", "settings.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12286.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12286.jsonl)

## 35. django__django-12308

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> JSONField are not properly displayed in admin when they are readonly.
> Description
> 	
> JSONField values are displayed as dict when readonly in the admin.
> For example, {"foo": "bar"} would be displayed as {'foo': 'bar'}, which is not valid JSON.
> I believe the fix would be to add a special case in django.contrib.admin.utils.display_for_field to call the prepare_value of the JSONField (not calling json.dumps directly to take care of the InvalidJSONInput case).

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |

共同严格目标：`[["django/contrib/admin/utils.py", "display_for_field"]]`

新预测：`[["django/contrib/admin/utils.py", "display_for_field"], ["django/utils/formats.py", "number_format"], ["tests/admin_utils/tests.py", "UtilsTests.test_null_display_for_field"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=20115/4072；耗时=380.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/admin/utils.py", "display_for_field"]], "seeds": [["django/contrib/admin/utils.py", "display_for_field"]], "causal_received": [["django/contrib/admin/utils.py", "display_for_field"]], "final": [["django/contrib/admin/utils.py", "display_for_field"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 20}`。

- A1：Incorrect handling of JSONField values in display_for_field；依据：；关联：`[["tests/admin_utils/tests.py", "UtilsTests.test_null_display_for_field"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/utils.py", "display_for_field"]]`
- A2：Lack of explicit conversion to JSON string in display_for_value；依据：；关联：`[["django/utils/formats.py", "number_format"]]`
- D：Missing call to prepare_value for JSONField；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12308.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12308.jsonl)

## 36. django__django-12453

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> `TransactionTestCase.serialized_rollback` fails to restore objects due to ordering constraints
> Description
> 	
> I hit this problem in a fairly complex projet and haven't had the time to write a minimal reproduction case. I think it can be understood just by inspecting the code so I'm going to describe it while I have it in mind.
> Setting serialized_rollback = True on a TransactionTestCase triggers ​rollback emulation. In practice, for each database:
> BaseDatabaseCreation.create_test_db calls connection._test_serialized_contents = connection.creation.serialize_db_to_string()
> TransactionTestCase._fixture_setup calls connection.creation.deserialize_db_from_string(connection._test_serialized_contents)
> (The actual code isn't written that way; it's equivalent but the symmetry is less visible.)
> serial

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]]`

新预测：`[["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=14383/2315；耗时=228.0秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]], "seeds": [["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]], "causal_received": [["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]], "final": [["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 19}`。

- D：deserialize_db_from_string；依据：；关联：`[["django/db/backends/base/creation.py", "BaseDatabaseCreation"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/backends/base/creation.py", "BaseDatabaseCreation.deserialize_db_from_string"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12453.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12453.jsonl)

## 37. django__django-12470

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Inherited model doesn't correctly order by "-pk" when specified on Parent.Meta.ordering
> Description
> 	
> Given the following model definition:
> from django.db import models
> class Parent(models.Model):
> 	class Meta:
> 		ordering = ["-pk"]
> class Child(Parent):
> 	pass
> Querying the Child class results in the following:
> >>> print(Child.objects.all().query)
> SELECT "myapp_parent"."id", "myapp_child"."parent_ptr_id" FROM "myapp_child" INNER JOIN "myapp_parent" ON ("myapp_child"."parent_ptr_id" = "myapp_parent"."id") ORDER BY "myapp_parent"."id" ASC
> The query is ordered ASC but I expect the order to be DESC.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/compiler.py", "SQLCompiler.find_ordering_name"]]`

新预测：`[]`

搜索种子 14；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=18387/6984；耗时=609.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[["tests/admin_changelist/models.py", "Parent"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/invalid_models_tests/test_models.py", "Parent"]]`
- C：Dependency on Product；依据：；关联：`[["tests/invalid_models_tests/test_models.py", "Parent"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12470.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12470.jsonl)

## 38. django__django-12497

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Wrong hint about recursive relationship.
> Description
> 	 
> 		(last modified by Matheus Cunha Motta)
> 	 
> When there's more than 2 ForeignKeys in an intermediary model of a m2m field and no through_fields have been set, Django will show an error with the following hint:
> hint=(
> 	'If you want to create a recursive relationship, '
> 	'use ForeignKey("%s", symmetrical=False, through="%s").'
> But 'symmetrical' and 'through' are m2m keyword arguments, not ForeignKey.
> This was probably a small mistake where the developer thought ManyToManyField but typed ForeignKey instead. And the symmetrical=False is an outdated requirement to recursive relationships with intermediary model to self, not required since 3.0. I'll provide a PR with a proposed correction shortly after.
> Edit: fixed description.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/related.py", "ManyToManyField._check_relationship_model"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12194/1812；耗时=176.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12497.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12497.jsonl)

## 39. django__django-12589

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Django 3.0: "GROUP BY" clauses error with tricky field annotation
> Description
> 	
> Let's pretend that we have next model structure with next model's relations:
> class A(models.Model):
> 	bs = models.ManyToManyField('B',
> 								related_name="a",
> 								through="AB")
> class B(models.Model):
> 	pass
> class AB(models.Model):
> 	a = models.ForeignKey(A, on_delete=models.CASCADE, related_name="ab_a")
> 	b = models.ForeignKey(B, on_delete=models.CASCADE, related_name="ab_b")
> 	status = models.IntegerField()
> class C(models.Model):
> 	a = models.ForeignKey(
> 		A,
> 		null=True,
> 		blank=True,
> 		on_delete=models.SET_NULL,
> 		related_name="c",
> 		verbose_name=_("a")
> 	)
> 	status = models.IntegerField()
> Let's try to evaluate next query
> ab_query = AB.objects.filter(a=OuterRef("pk"), b=1)
> filter_conditions = Q(pk=1) | Q(ab_a_

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query.set_group_by"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=17876/2859；耗时=249.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12589.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12589.jsonl)

## 40. django__django-12700

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Settings are cleaned insufficiently.
> Description
> 	
> Posting publicly after checking with the rest of the security team.
> I just ran into a case where django.views.debug.SafeExceptionReporterFilter.get_safe_settings() would return several un-cleansed values. Looking at cleanse_setting() I realized that we ​only take care of `dict`s but don't take other types of iterables into account but ​return them as-is.
> Example:
> In my settings.py I have this:
> MY_SETTING = {
> 	"foo": "value",
> 	"secret": "value",
> 	"token": "value",
> 	"something": [
> 		{"foo": "value"},
> 		{"secret": "value"},
> 		{"token": "value"},
> 	],
> 	"else": [
> 		[
> 			{"foo": "value"},
> 			{"secret": "value"},
> 			{"token": "value"},
> 		],
> 		[
> 			{"foo": "value"},
> 			{"secret": "value"},
> 			{"token": "value"},
> 		],
> 	]
> }
> On Django 3.0 and below:
> >

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"]]`

新预测：`[["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"], ["tests/view_tests/tests/test_debug.py", "ExceptionReporterFilterTests.test_cleanse_setting_recurses_in_dictionary"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=24989/4728；耗时=436.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"]], "seeds": [["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"]], "causal_received": [["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"]], "final": [["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 34}`。

- A1：Incorrect computation；依据：；关联：`[["tests/view_tests/tests/test_debug.py", "ExceptionReporterFilterTests.test_cleanse_setting_recurses_in_dictionary"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/views/debug.py", "SafeExceptionReporterFilter.cleanse_setting"]]`
- A2：Wrong logic；依据：；关联：`[["django/views/debug.py", "SafeExceptionReporterFilter"]]`
- D1：Cleanse setting method；依据：；关联：`[["django/views/debug.py", "debug.py"]]`
- E：Issue；依据：；关联：`[]`
- D2：Get safe settings method；依据：；关联：`[["tests/view_tests/tests/test_debug.py", "ExceptionReporterFilterTests"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12700.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12700.jsonl)

## 41. django__django-12708

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Migration crashes deleting an index_together if there is a unique_together on the same fields
> Description
> 	
> Happens with Django 1.11.10
> Steps to reproduce:
> 1) Create models with 2 fields, add 2 same fields to unique_together and to index_together
> 2) Delete index_together -> Fail
> It will fail at django/db/backends/base/schema.py, line 378, in _delete_composed_index(), ValueError: Found wrong number (2) of constraints for as this one will find two constraints, the _uniq and the _idx one. No way to get out of this...
> The worst in my case is that happened as I wanted to refactor my code to use the "new" (Dj 1.11) Options.indexes feature. I am actually not deleting the index, just the way it is declared in my code.
> I think there are 2 different points here:
> 1) The deletion of index_together sho

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/backends/base/schema.py", "BaseDatabaseSchemaEditor.alter_index_together"]]`

新预测：`[["django/db/backends/mysql/schema.py", "DatabaseSchemaEditor._delete_composed_index"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=71293/20994；耗时=1770.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 54}`。

- A1：Incorrect computation；依据：；关联：`[["django/db/backends/ddl_references.py", "ddl_references.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/backends/base/schema.py", "schema.py"]]`
- A2：Wrong logic；依据：；关联：`[["django/contrib/gis/db/backends/oracle/base.py", "base.py"]]`
- I2：Table columns handling；依据：；关联：`[["django/db/backends/ddl_references.py", "TableColumns"]]`
- D1：Constraints handling in PostgreSQL；依据：；关联：`[["django/db/backends/postgresql/schema.py", "schema.py"]]`
- D2：Schema changes in PostgreSQL；依据：；关联：`[["django/db/backends/postgresql/schema.py", "schema.py"]]`
- E1：IndexColumns class；依据：；关联：`[["django/db/backends/ddl_references.py", "IndexColumns"]]`
- E2：IndexName class；依据：；关联：`[["django/db/backends/ddl_references.py", "IndexName"]]`
- F1：Statement class；依据：；关联：`[["django/db/backends/ddl_references.py", "Statement"]]`
- F2：Table class；依据：；关联：`[["django/db/backends/ddl_references.py", "Table"]]`
- G1：Columns class；依据：；关联：`[["django/db/backends/ddl_references.py", "Columns"]]`
- H1：DDL references in SQLite3；依据：；关联：`[["django/db/backends/sqlite3/schema.py", "schema.py"]]`
- H2：Test DDL references；依据：；关联：`[["tests/backends/test_ddl_references.py", "test_ddl_references.py"]]`
- I1：Foreign key name handling；依据：；关联：`[["django/db/backends/ddl_references.py", "ForeignKeyName"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/backends/mysql/schema.py", "DatabaseSchemaEditor._delete_composed_index"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/backends/mysql/schema.py", "DatabaseSchemaEditor._delete_composed_index"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12708.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12708.jsonl)

## 42. django__django-12747

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> QuerySet.Delete - inconsistent result when zero objects deleted
> Description
> 	
> The result format of the QuerySet.Delete method is a tuple: (X, Y) 
> X - is the total amount of deleted objects (including foreign key deleted objects)
> Y - is a dictionary specifying counters of deleted objects for each specific model (the key is the _meta.label of the model and the value is counter of deleted objects of this model).
> Example: <class 'tuple'>: (2, {'my_app.FileAccess': 1, 'my_app.File': 1})
> When there are zero objects to delete in total - the result is inconsistent:
> For models with foreign keys - the result will be: <class 'tuple'>: (0, {})
> For "simple" models without foreign key - the result will be: <class 'tuple'>: (0, {'my_app.BlockLibrary': 0})
> I would expect there will be no difference betwee

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/db/models/deletion.py", "Collector.delete"]]`

新预测：`[["django/db/models/deletion.py", "Collector.delete"], ["django/views/generic/edit.py", "DeletionMixin.delete"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=36243/9677；耗时=766.2秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/models/deletion.py", "Collector.delete"]], "seeds": [["django/db/models/deletion.py", "Collector.delete"]], "causal_received": [["django/db/models/deletion.py", "Collector.delete"]], "final": [["django/db/models/deletion.py", "Collector.delete"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 30, "causal": 14}`。

- J：Fast delete optimization；依据：；关联：`[]`
- K：Can fast delete check；依据：；关联：`[]`
- L：Instances with model；依据：；关联：`[]`
- M：Mark for rollback on error；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/deletion.py", "Collector.delete"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/views/generic/edit.py", "DeletionMixin.delete"]]`
- C：Dependency on Product；依据：；关联：`[["django/views/generic/edit.py", "DeletionMixin.delete"]]`
- D：Collector behavior based on foreign key relationships；依据：；关联：`[]`
- E：Fast delete optimization；依据：；关联：`[]`
- F：Can fast delete check；依据：；关联：`[]`
- G：Instances with model；依据：；关联：`[]`
- H：Mark for rollback on error；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12747.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12747.jsonl)

## 43. django__django-12856

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Add check for fields of UniqueConstraints.
> Description
> 	 
> 		(last modified by Marnanel Thurman)
> 	 
> When a model gains a UniqueConstraint, makemigrations doesn't check that the fields named therein actually exist.
> This is in contrast to the older unique_together syntax, which raises models.E012 if the fields don't exist.
> In the attached demonstration, you'll need to uncomment "with_unique_together" in settings.py in order to show that unique_together raises E012.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/base.py", "Model._check_constraints"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11544/1852；耗时=179.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12856.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12856.jsonl)

## 44. django__django-12908

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Union queryset should raise on distinct().
> Description
> 	 
> 		(last modified by Sielc Technologies)
> 	 
> After using
> .annotate() on 2 different querysets
> and then .union()
> .distinct() will not affect the queryset
> 	def setUp(self) -> None:
> 		user = self.get_or_create_admin_user()
> 		Sample.h.create(user, name="Sam1")
> 		Sample.h.create(user, name="Sam2 acid")
> 		Sample.h.create(user, name="Sam3")
> 		Sample.h.create(user, name="Sam4 acid")
> 		Sample.h.create(user, name="Dub")
> 		Sample.h.create(user, name="Dub")
> 		Sample.h.create(user, name="Dub")
> 		self.user = user
> 	def test_union_annotated_diff_distinct(self):
> 		qs = Sample.objects.filter(user=self.user)
> 		qs1 = qs.filter(name='Dub').annotate(rank=Value(0, IntegerField()))
> 		qs2 = qs.filter(name='Sam1').annotate(rank=Value(1, IntegerField()))
> 		qs =

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |

共同严格目标：`[["django/db/models/query.py", "QuerySet.distinct"]]`

新预测：`[["django/db/models/query.py", "QuerySet._chain"], ["django/db/models/query.py", "QuerySet.dates"], ["django/db/models/query.py", "QuerySet.datetimes"], ["django/db/models/query.py", "QuerySet.delete"], ["django/db/models/query.py", "QuerySet.distinct"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=66045/11584；耗时=1029.0秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/models/query.py", "QuerySet.distinct"]], "seeds": [["django/db/models/query.py", "QuerySet.distinct"]], "causal_received": [["django/db/models/query.py", "QuerySet.distinct"]], "final": [["django/db/models/query.py", "QuerySet.distinct"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 88}`。

- A1：Incorrect computation；依据：；关联：`[["django/db/models/query.py", "QuerySet.dates"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/query.py", "QuerySet.distinct"]]`
- A2：Wrong logic；依据：；关联：`[["django/db/models/query.py", "QuerySet"]]`
- E1：Inconsistent State After Chaining；依据：；关联：`[["django/db/models/query.py", "QuerySet.delete"]]`
- E2：Misapplication of Distinct；依据：；关联：`[["django/db/models/query.py", "QuerySet.delete"]]`
- D1：Annotation with date field；依据：；关联：`[["django/db/models/query.py", "QuerySet.dates"]]`
- D2：Annotation with datetime field；依据：；关联：`[["django/db/models/query.py", "QuerySet.datetimes"]]`
- E：_chain method；依据：；关联：`[["django/db/models/query.py", "QuerySet._chain"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12908.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12908.jsonl)

## 45. django__django-12915

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Add get_response_async for ASGIStaticFilesHandler
> Description
> 	
> It looks like the StaticFilesHandlerMixin is missing the the async response function.
> Without this, when trying to use the ASGIStaticFilesHandler, this is the traceback:
> Exception inside application: 'NoneType' object is not callable
> Traceback (most recent call last):
>  File ".../lib/python3.7/site-packages/daphne/cli.py", line 30, in asgi
> 	await self.app(scope, receive, send)
>  File ".../src/django/django/contrib/staticfiles/handlers.py", line 86, in __call__
> 	return await super().__call__(scope, receive, send)
>  File ".../src/django/django/core/handlers/asgi.py", line 161, in __call__
> 	response = await self.get_response_async(request)
>  File ".../src/django/django/core/handlers/base.py", line 148, in get_response_async
> 	response

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/staticfiles/handlers.py", "StaticFilesHandlerMixin.get_response_async"]]`

新预测：`[["django/core/handlers/base.py", "BaseHandler.get_response_async"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=5595/1124；耗时=152.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 2}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/core/handlers/base.py", "BaseHandler.get_response_async"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12915.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12915.jsonl)

## 46. django__django-12983

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Make django.utils.text.slugify() strip dashes and underscores
> Description
> 	 
> 		(last modified by Elinaldo do Nascimento Monteiro)
> 	 
> Bug generation slug
> Example:
> from django.utils import text
> text.slugify("___This is a test ---")
> output: ___this-is-a-test-
> Improvement after correction
> from django.utils import text
> text.slugify("___This is a test ---")
> output: this-is-a-test
> ​PR

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/utils/text.py", "slugify"]]`

新预测：`[["django/template/defaultfilters.py", "slugify"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=5802/1113；耗时=171.2秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["django/utils/text.py", "slugify"]], "seeds": [["django/utils/text.py", "slugify"]], "causal_received": [["django/utils/text.py", "slugify"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 6}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/template/defaultfilters.py", "slugify"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-12983.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-12983.jsonl)

## 47. django__django-13028

项目：django/django；本轮子集：验证集；状态：failed。

问题描述节选：

> Queryset raises NotSupportedError when RHS has filterable=False attribute.
> Description
> 	 
> 		(last modified by Nicolas Baccelli)
> 	 
> I'm migrating my app to django 3.0.7 and I hit a strange behavior using a model class with a field labeled filterable
> class ProductMetaDataType(models.Model):
> 	label = models.CharField(max_length=255, unique=True, blank=False, null=False)
> 	filterable = models.BooleanField(default=False, verbose_name=_("filterable"))
> 	class Meta:
> 		app_label = "adminpricing"
> 		verbose_name = _("product meta data type")
> 		verbose_name_plural = _("product meta data types")
> 	def __str__(self):
> 		return self.label
> class ProductMetaData(models.Model):
> 	id = models.BigAutoField(primary_key=True)
> 	product = models.ForeignKey(
> 		Produit, null=False, blank=False, on_delete=models.CASCADE

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query.check_filterable"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=188196/22848；耗时=2217.6秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["django/db/models/sql/query.py", "Query.check_filterable"]], "seeds": [], "causal_received": [["django/db/models/sql/query.py", "Query.check_filterable"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 224}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/django__django-13028.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13028.jsonl)

## 48. django__django-13033

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Self referencing foreign key doesn't correctly order by a relation "_id" field.
> Description
> 	
> Initially discovered on 2.2.10 but verified still happens on 3.0.6. Given the following models:
> class OneModel(models.Model):
> 	class Meta:
> 		ordering = ("-id",)
> 	id = models.BigAutoField(primary_key=True)
> 	root = models.ForeignKey("OneModel", on_delete=models.CASCADE, null=True)
> 	oneval = models.BigIntegerField(null=True)
> class TwoModel(models.Model):
> 	id = models.BigAutoField(primary_key=True)
> 	record = models.ForeignKey(OneModel, on_delete=models.CASCADE)
> 	twoval = models.BigIntegerField(null=True)
> The following queryset gives unexpected results and appears to be an incorrect SQL query:
> qs = TwoModel.objects.filter(record__oneval__in=[1,2,3])
> qs = qs.order_by("record__root_id")
> print(qs.query)
> S

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/compiler.py", "SQLCompiler.find_ordering_name"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=20780/2025；耗时=194.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13033.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13033.jsonl)

## 49. django__django-13158

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> QuerySet.none() on combined queries returns all results.
> Description
> 	
> I came across this issue on Stack Overflow. I'm not 100% sure it's a bug, but it does seem strange. With this code (excuse the bizarre example filtering):
> class Publication(models.Model):
> 	pass
> class Article(models.Model):
> 	publications = models.ManyToManyField(to=Publication, blank=True, null=True)
> class ArticleForm(forms.ModelForm):
> 	publications = forms.ModelMultipleChoiceField(
> 		Publication.objects.filter(id__lt=2) | Publication.objects.filter(id__gt=5),
> 		required=False,
> 	)
> 	class Meta:
> 		model = Article
> 		fields = ["publications"]
> class ArticleAdmin(admin.ModelAdmin):
> 	form = ArticleForm
> This works well. However, changing the ModelMultipleChoiceField queryset to use union() breaks things.
> publications = forms.Mod

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query.clone"], ["django/db/models/sql/query.py", "Query.set_empty"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=15637/5011；耗时=383.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Issue；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13158.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13158.jsonl)

## 50. django__django-13220

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Allow ValidationErrors to equal each other when created identically
> Description
> 	 
> 		(last modified by kamni)
> 	 
> Currently ValidationErrors (django.core.exceptions.ValidationError) that have identical messages don't equal each other, which is counter-intuitive, and can make certain kinds of testing more complicated. Please add an __eq__ method that allows two ValidationErrors to be compared. 
> Ideally, this would be more than just a simple self.messages == other.messages. It would be most helpful if the comparison were independent of the order in which errors were raised in a field or in non_field_errors.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/exceptions.py", "ValidationError.__eq__"], ["django/core/exceptions.py", "ValidationError.__hash__"]]`

新预测：`[["django/contrib/gis/geos/geometry.py", "GEOSGeometryBase.__eq__"], ["django/core/validators.py", "RegexValidator.__eq__"]]`

搜索种子 8；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=12826/2983；耗时=307.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 8, "relevance": 32, "causal": 10}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/gis/geos/geometry.py", "GEOSGeometryBase.__eq__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/core/validators.py", "RegexValidator.__eq__"]]`
- C：Dependency on Product；依据：；关联：`[["django/core/validators.py", "RegexValidator.__eq__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13220.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13220.jsonl)

## 51. django__django-13230

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Add support for item_comments to syndication framework
> Description
> 	
> Add comments argument to feed.add_item() in syndication.views so that item_comments can be defined directly without having to take the detour via item_extra_kwargs .
> Additionally, comments is already explicitly mentioned in the feedparser, but not implemented in the view.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/syndication/views.py", "Feed.get_feed"]]`

新预测：`[["django/utils/feedgenerator.py", "SyndicationFeed.add_item"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=5761/1319；耗时=210.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/utils/feedgenerator.py", "SyndicationFeed.add_item"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13230.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13230.jsonl)

## 52. django__django-13265

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> AlterOrderWithRespectTo() with ForeignKey crash when _order is included in Index().
> Description
> 	
> 	class Meta:
> 		db_table = 'look_image'
> 		order_with_respect_to = 'look'
> 		indexes = [
> 			models.Index(fields=['look', '_order']),
> 			models.Index(fields=['created_at']),
> 			models.Index(fields=['updated_at']),
> 		]
> migrations.CreateModel(
> 			name='LookImage',
> 			fields=[
> 				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
> 				('look', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='posts.Look', verbose_name='LOOK')),
> 				('image_url', models.URLField(blank=True, max_length=10000, null=True)),
> 				('image', models.ImageField(max_length=2000, upload_to='')),
> 				('deleted', models.DateTimeField(editable=F

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/autodetector.py", "MigrationAutodetector._detect_changes"], ["django/db/migrations/autodetector.py", "MigrationAutodetector.generate_created_models"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=13305/5296；耗时=406.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- E：Ensure correct migration order；依据：；关联：`[]`
- F：Adjust migration order；依据：；关联：`[]`
- G：Correct migration order；依据：；关联：`[]`
- D：Migration order issue；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13265.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13265.jsonl)

## 53. django__django-13315

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> limit_choices_to on a ForeignKey can render duplicate options in formfield
> Description
> 	
> If you pass a Q object as limit_choices_to on a ForeignKey field involving a join, you may end up with duplicate options in your form.
> See regressiontest in patch for a clear view on the problem.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/models.py", "apply_limit_choices_to_to_formfield"]]`

新预测：`[["django/contrib/admin/filters.py", "AllValuesFieldListFilter.__init__"], ["django/contrib/admin/filters.py", "AllValuesFieldListFilter.choices"], ["django/contrib/admin/filters.py", "FieldListFilter.__init__"], ["django/contrib/admin/utils.py", "reverse_field_path"], ["tests/admin_changelist/admin.py", "ChildAdmin.get_queryset"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=37602/8247；耗时=958.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 64, "causal": 19}`。

- A1：Incorrect computation；依据：；关联：`[["", "self.lookup_val"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/filters.py", "AllValuesFieldListFilter.__init__"]]`
- A2：Wrong logic；依据：；关联：`[["", "self.lookup_kwarg_isnull"]]`
- F1：Flawed choice generation logic；依据：；关联：`[["django/contrib/admin/filters.py", "AllValuesFieldListFilter.choices"]]`
- D：Flawed queryset generation；依据：；关联：`[["django/contrib/admin/utils.py", "reverse_field_path"], ["", "self.lookup_choices"], ["", "self.lookup_kwarg"], ["", "self.lookup_val_isnull"]]`
- E：Incomplete initialization；依据：；关联：`[["django/contrib/admin/filters.py", "FieldListFilter.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/admin_changelist/admin.py", "ChildAdmin.get_queryset"]]`
- C：Dependency on Product；依据：；关联：`[["tests/admin_changelist/admin.py", "ChildAdmin.get_queryset"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13315.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13315.jsonl)

## 54. django__django-13321

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Decoding an invalid session data crashes.
> Description
> 	 
> 		(last modified by Matt Hegarty)
> 	 
> Hi
> I recently upgraded my staging server to 3.1. I think that there was an old session which was still active.
> On browsing to any URL, I get the crash below. It looks similar to ​this issue.
> I cannot login at all with Chrome - each attempt to access the site results in a crash. Login with Firefox works fine.
> This is only happening on my Staging site, which is running Gunicorn behind nginx proxy.
> Internal Server Error: /overview/
> Traceback (most recent call last):
> File "/usr/local/lib/python3.8/site-packages/django/contrib/sessions/backends/base.py", line 215, in _get_session
> return self._session_cache
> AttributeError: 'SessionStore' object has no attribute '_session_cache'
> During handling of the ab

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/sessions/backends/base.py", "SessionBase.decode"]]`

新预测：`[["django/contrib/messages/storage/cookie.py", "CookieStorage._decode"], ["django/contrib/messages/storage/cookie.py", "CookieStorage._legacy_decode"], ["django/contrib/sessions/backends/base.py", "SessionBase._legacy_decode"], ["django/core/signing.py", "loads"], ["django/utils/crypto.py", "constant_time_compare"], ["tests/messages_tests/test_cookie.py", "stored_cookie_messages_count"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=56018/12466；耗时=1212.9秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["django/contrib/sessions/backends/base.py", "SessionBase.decode"]], "seeds": [["django/contrib/sessions/backends/base.py", "SessionBase.decode"]], "causal_received": [["django/contrib/sessions/backends/base.py", "SessionBase.decode"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 12, "causal": 47}`。

- A5：Base64 Decoding Failure；依据：；关联：`[["tests/messages_tests/test_cookie.py", "stored_cookie_messages_count"], ["django/core/signing.py", "loads"]]`
- A1：Incorrect computation；依据：；关联：`[["django/contrib/messages/storage/cookie.py", "CookieStorage"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/messages/storage/cookie.py", "CookieStorage._legacy_decode"]]`
- A2：Wrong logic；依据：；关联：`[["django/utils/crypto.py", "constant_time_compare"]]`
- A3：Incompatible Browser；依据：；关联：`[["tests/messages_tests/test_cookie.py", "stored_cookie_messages_count"]]`
- A4：Misconfigured Sessions；依据：；关联：`[["", "self.signer"]]`
- D：_decode；依据：；关联：`[["django/contrib/messages/storage/cookie.py", "CookieStorage._decode"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/contrib/sessions/backends/base.py", "SessionBase._legacy_decode"]]`
- C：Dependency on Product；依据：；关联：`[["django/contrib/sessions/backends/base.py", "SessionBase._legacy_decode"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13321.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13321.jsonl)

## 55. django__django-13401

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Abstract model field should not be equal across models
> Description
> 	
> Consider the following models:
> class A(models.Model):
> 	class Meta:
> 		abstract = True
> 	myfield = IntegerField()
> class B(A):
> 	pass
> class C(A):
> 	pass
> If I pull the fields of B and C into a shared set, one will be de-duplicated away, because they compare as equal. I found this surprising, though in practice using a list was sufficient for my need. The root of the issue is that they compare equal, as fields only consider self.creation_counter when comparing for equality.
> len({B._meta.get_field('myfield'), C._meta.get_field('myfield')}) == 1
> B._meta.get_field('myfield') == C._meta.get_field('myfield')
> We should adjust __eq__ so that if the field.model is different, they will compare unequal. Similarly, it is probably wise to ad

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 33.33% | 28.57% | 0.00% | 命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "Field.__eq__"], ["django/db/models/fields/__init__.py", "Field.__hash__"], ["django/db/models/fields/__init__.py", "Field.__lt__"]]`

新预测：`[["django/db/models/base.py", "Model.__eq__"], ["django/db/models/base.py", "Model._check_field_name_clashes"], ["django/db/models/base.py", "Model.check"], ["django/db/models/fields/__init__.py", "Field.__lt__"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=164446/16758；耗时=1507.8秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["django/db/models/fields/__init__.py", "Field.__hash__"], ["django/db/models/fields/__init__.py", "Field.__lt__"]], "seeds": [["django/db/models/fields/__init__.py", "Field.__hash__"], ["django/db/models/fields/__init__.py", "Field.__lt__"]], "causal_received": [["django/db/models/fields/__init__.py", "Field.__eq__"], ["django/db/models/fields/__init__.py", "Field.__hash__"], ["django/db/models/fields/__init__.py", "Field.__lt__"]], "final": [["django/db/models/fields/__init__.py", "Field.__lt__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 55, "causal": 121}`。

- Field：Field Class；依据：；关联：`[["django/db/models/fields/__init__.py", "Field"]]`
- F1：Field Clashing Check；依据：；关联：`[["django/db/models/base.py", "Model._check_field_name_clashes"]]`
- A1：Incorrect computation；依据：；关联：`[["django/db/models/base.py", "Model"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/base.py", "Model.__eq__"]]`
- A2：Wrong logic；依据：；关联：`[]`
- F2：Model Validation Check；依据：；关联：`[["django/db/models/base.py", "Model.check"]]`
- F3：Recursive Check Adjustment；依据：；关联：`[["django/db/models/base.py", "Model._check_field_name_clashes"]]`
- F4：Clash Detection Mechanism；依据：；关联：`[["django/db/models/base.py", "Model._check_field_name_clashes"]]`
- D：Model Definition；依据：；关联：`[["django/db/models/base.py", "Model"]]`
- E：Metaclass Usage；依据：；关联：`[["django/db/models/base.py", "Model"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/models/fields/__init__.py", "Field.__lt__"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/models/fields/__init__.py", "Field.__lt__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13401.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13401.jsonl)

## 56. django__django-13447

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Added model class to app_list context
> Description
> 	 
> 		(last modified by Raffaele Salmaso)
> 	 
> I need to manipulate the app_list in my custom admin view, and the easiest way to get the result is to have access to the model class (currently the dictionary is a serialized model).
> In addition I would make the _build_app_dict method public, as it is used by the two views index and app_index.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]]`

新预测：`[["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=6775/1214；耗时=157.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]], "seeds": [["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]], "causal_received": [["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]], "final": [["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/sites.py", "AdminSite._build_app_dict"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13447.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13447.jsonl)

## 57. django__django-13448

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Test runner setup_databases crashes with "TEST": {"MIGRATE": False}.
> Description
> 	
> I'm trying to upgrade a project from Django 3.0 to Django 3.1 and wanted to try out the new "TEST": {"MIGRATE": False} database setting.
> Sadly I'm running into an issue immediately when running ./manage.py test.
> Removing the "TEST": {"MIGRATE": False} line allows the tests to run. So this is not blocking the upgrade for us, but it would be nice if we were able to use the new feature to skip migrations during testing.
> For reference, this project was recently upgraded from Django 1.4 all the way to 3.0 so there might be some legacy cruft somewhere that triggers this.
> Here's the trackeback. I'll try to debug this some more.
> Traceback (most recent call last):
>  File "/usr/local/lib/python3.6/site-packages/django/

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/backends/base/creation.py", "BaseDatabaseCreation.create_test_db"]]`

新预测：`[["django/test/runner.py", "DiscoverRunner.setup_databases"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=16775/1820；耗时=230.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 10}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/test/runner.py", "DiscoverRunner.setup_databases"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13448.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13448.jsonl)

## 58. django__django-13551

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Changing user's email could invalidate password reset tokens
> Description
> 	
> Sequence:
> Have account with email address foo@…
> Password reset request for that email (unused)
> foo@… account changes their email address
> Password reset email is used
> The password reset email's token should be rejected at that point, but in fact it is allowed.
> The fix is to add the user's email address into ​PasswordResetTokenGenerator._make_hash_value()
> Nothing forces a user to even have an email as per AbstractBaseUser. Perhaps the token generation method could be factored out onto the model, ala get_session_auth_hash().

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 10.00% | 100.00% | 18.18% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]]`

新预测：`[["django/contrib/auth/base_user.py", "AbstractBaseUser.get_email_field_name"], ["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=21187/6801；耗时=614.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]], "seeds": [["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]], "causal_received": [["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]], "final": [["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 18}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/auth/base_user.py", "AbstractBaseUser.get_email_field_name"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/auth/base_user.py", "AbstractBaseUser"]]`
- A2：Wrong logic；依据：；关联：`[["tests/auth_tests/test_checks.py", "CustomUserBadRequiredFields"]]`
- EmailNotConsideredInHash：Email not considered in hash；依据：；关联：`[["django/contrib/auth/base_user.py", "AbstractBaseUser.get_email_field_name"], ["tests/auth_tests/test_checks.py", "CustomUserBadRequiredFields"], ["tests/auth_tests/models/with_custom_email_field.py", "CustomEmailField"], ["tests/test_client_regress/models.py", "CustomUser"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]]`
- C：Dependency on Product；依据：；关联：`[["django/contrib/auth/tokens.py", "PasswordResetTokenGenerator._make_hash_value"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13551.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13551.jsonl)

## 59. django__django-13590

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Upgrading 2.2>3.0 causes named tuples used as arguments to __range to error.
> Description
> 	
> I noticed this while upgrading a project from 2.2 to 3.0.
> This project passes named 2-tuples as arguments to range queryset filters. This works fine on 2.2. On 3.0 it causes the following error: TypeError: __new__() missing 1 required positional argument: 'far'.
> This happens because django.db.models.sql.query.Query.resolve_lookup_value goes into the tuple elements to resolve lookups and then attempts to reconstitute the tuple with the resolved elements.
> When it attempts to construct the new tuple it preserves the type (the named tuple) but it passes a iterator to it's constructor.
> NamedTuples don't have the code path for copying an iterator, and so it errors on insufficient arguments.
> The fix is to *

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query.resolve_lookup_value"]]`

新预测：`[["django/db/models/sql/query.py", "Query.resolve_lookup_value"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=10246/3758；耗时=355.0秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/models/sql/query.py", "Query.resolve_lookup_value"]], "seeds": [["django/db/models/sql/query.py", "Query.resolve_lookup_value"]], "causal_received": [["django/db/models/sql/query.py", "Query.resolve_lookup_value"]], "final": [["django/db/models/sql/query.py", "Query.resolve_lookup_value"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 7}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/sql/query.py", "Query.resolve_lookup_value"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13590.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13590.jsonl)

## 60. django__django-13658

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> ManagementUtility instantiates CommandParser without passing already-computed prog argument
> Description
> 	
> ManagementUtility ​goes to the trouble to parse the program name from the argv it's passed rather than from sys.argv: 
> 	def __init__(self, argv=None):
> 		self.argv = argv or sys.argv[:]
> 		self.prog_name = os.path.basename(self.argv[0])
> 		if self.prog_name == '__main__.py':
> 			self.prog_name = 'python -m django'
> But then when it needs to parse --pythonpath and --settings, it ​uses the program name from sys.argv: 
> 		parser = CommandParser(usage='%(prog)s subcommand [options] [args]', add_help=False, allow_abbrev=False)
> Above "%(prog)s" ​refers to sys.argv[0]. Instead, it should refer to self.prog_name. This can fixed as follows:
> 		parser = CommandParser(
> 			prog=self.prog_name,
> 			usage='

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/core/management/__init__.py", "ManagementUtility.execute"]]`

新预测：`[["django/core/management/__init__.py", "ManagementUtility.execute"], ["django/core/management/__init__.py", "execute_from_command_line"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=45698/7157；耗时=626.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["django/core/management/__init__.py", "ManagementUtility.execute"]], "final": [["django/core/management/__init__.py", "ManagementUtility.execute"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 14}`。

- A1：Incorrect computation；依据：；关联：`[["django/core/management/__init__.py", "__init__.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/core/management/__init__.py", "ManagementUtility"]]`
- A2：Wrong logic；依据：；关联：`[["django/core/management/__init__.py", "ManagementUtility.execute"]]`
- D：Instantiation of CommandParser without passing prog argument；依据：；关联：`[["tests/flatpages_tests/settings.py", "settings.py"]]`
- E：Issue；依据：；关联：`[]`
- F：Usage of %(prog)s in CommandParser；依据：；关联：`[["tests/apps/explicit_default_config_mismatch_app/apps.py", "apps.py"]]`
- G：Modification of sys.argv[0]；依据：；关联：`[["tests/apps/two_default_configs_app/apps.py", "apps.py"]]`
- H：Issue；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[["django/core/management/__init__.py", "execute_from_command_line"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/core/management/__init__.py", "execute_from_command_line"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13658.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13658.jsonl)

## 61. django__django-13660

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> shell command crashes when passing (with -c) the python code with functions.
> Description
> 	
> The examples below use Python 3.7 and Django 2.2.16, but I checked that the code is the same on master and works the same in Python 3.8.
> Here's how ​python -c works:
> $ python -c <<EOF " 
> import django
> def f():
> 		print(django.__version__)
> f()"
> EOF
> 2.2.16
> Here's how ​python -m django shell -c works (paths shortened for clarify):
> $ python -m django shell -c <<EOF "
> import django
> def f():
> 		print(django.__version__)
> f()"
> EOF
> Traceback (most recent call last):
>  File "{sys.base_prefix}/lib/python3.7/runpy.py", line 193, in _run_module_as_main
> 	"__main__", mod_spec)
>  File "{sys.base_prefix}/lib/python3.7/runpy.py", line 85, in _run_code
> 	exec(code, run_globals)
>  File "{sys.prefix}/lib/python3.7/site-package

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/core/management/commands/shell.py", "Command.handle"]]`

新预测：`[["django/core/management/commands/shell.py", "Command.handle"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=34290/4218；耗时=379.9秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/core/management/commands/shell.py", "Command.handle"]], "seeds": [["django/core/management/commands/shell.py", "Command.handle"]], "causal_received": [["django/core/management/commands/shell.py", "Command.handle"]], "final": [["django/core/management/commands/shell.py", "Command.handle"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 1}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/core/management/commands/shell.py", "Command.handle"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Lack of global context in exec；依据：；关联：`[]`
- E：Class definition missing necessary imports；依据：；关联：`[]`
- F：Field self.shells not properly initialized；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13660.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13660.jsonl)

## 62. django__django-13710

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Use Admin Inline verbose_name as default for Inline verbose_name_plural
> Description
> 	
> Django allows specification of a verbose_name and a verbose_name_plural for Inline classes in admin views. However, verbose_name_plural for an Inline is not currently based on a specified verbose_name. Instead, it continues to be based on the model name, or an a verbose_name specified in the model's Meta class. This was confusing to me initially (I didn't understand why I had to specify both name forms for an Inline if I wanted to overrule the default name), and seems inconsistent with the approach for a model's Meta class (which does automatically base the plural form on a specified verbose_name). I propose that verbose_name_plural for an Inline class should by default be based on the verbose_name for an

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]]`

新预测：`[["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=100103/14309；耗时=1169.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]], "seeds": [["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]], "causal_received": [["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]], "final": [["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 64, "causal": 68}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/admin/options.py", "InlineModelAdmin"]]`
- A：Inaccurate recursive check；依据：；关联：`[["", "self.verbose_name_plural"]]`
- A2：Wrong logic；依据：；关联：`[["django/db/models/options.py", "Options"]]`
- D1：Verbose name not set in InlineModelAdmin；依据：；关联：`[["django/contrib/admin/options.py", "InlineModelAdmin"]]`
- D2：Verbose name plural not set in InlineModelAdmin；依据：；关联：`[["django/contrib/admin/options.py", "InlineModelAdmin"]]`
- E1：Verbose name defined in Options；依据：；关联：`[["django/db/models/options.py", "Options"]]`
- E2：Verbose name plural defined in Options；依据：；关联：`[["django/db/models/options.py", "Options"]]`
- F1：Verbose name defined in Options；依据：；关联：`[["django/core/cache/backends/db.py", "Options"]]`
- F2：Verbose name plural defined in Options；依据：；关联：`[["django/core/cache/backends/db.py", "Options"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]]`
- C：Dependency on Product；依据：；关联：`[["django/contrib/admin/options.py", "InlineModelAdmin.__init__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13710.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13710.jsonl)

## 63. django__django-13757

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Using __isnull=True on a KeyTransform should not match JSON null on SQLite and Oracle
> Description
> 	
> The KeyTransformIsNull lookup borrows the logic from HasKey for isnull=False, which is correct. If isnull=True, the query should only match objects that do not have the key. The query is correct for MariaDB, MySQL, and PostgreSQL. However, on SQLite and Oracle, the query also matches objects that have the key with the value null, which is incorrect.
> To confirm, edit tests.model_fields.test_jsonfield.TestQuerying.test_isnull_key. For the first assertion, change
> 		self.assertSequenceEqual(
> 			NullableJSONModel.objects.filter(value__a__isnull=True),
> 			self.objs[:3] + self.objs[5:],
> 		)
> to
> 		self.assertSequenceEqual(
> 			NullableJSONModel.objects.filter(value__j__isnull=True),
> 			self.objs[:4] +

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/json.py", "KeyTransformIsNull.as_oracle"], ["django/db/models/fields/json.py", "KeyTransformIsNull.as_sqlite"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=9390/1366；耗时=207.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 9, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/core/management/commands/test.py", "test.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13757.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13757.jsonl)

## 64. django__django-13768

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Log exceptions handled in Signal.send_robust()
> Description
> 	
> As pointed out by ​Haki Benita on Twitter, by default Signal.send_robust() doesn't have any log messages for exceptions raised in receivers. Since Django logs exceptions in other similar situations, such as missing template variables, I think it would be worth adding a logger.exception() call in the except clause of send_robust() . Users would then see such exceptions in their error handling tools, e.g. Sentry, and be able to figure out what action to take from there. Ultimately any *expected* exception should be caught with a try in the receiver function.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/dispatch/dispatcher.py", "Signal.send_robust"]]`

新预测：`[["django/dispatch/dispatcher.py", "Signal.send_robust"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=7140/1275；耗时=166.7秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/dispatch/dispatcher.py", "Signal.send_robust"]], "seeds": [["django/dispatch/dispatcher.py", "Signal.send_robust"]], "causal_received": [["django/dispatch/dispatcher.py", "Signal.send_robust"]], "final": [["django/dispatch/dispatcher.py", "Signal.send_robust"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/dispatch/dispatcher.py", "Signal.send_robust"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13768.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13768.jsonl)

## 65. django__django-13925

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> models.W042 is raised on inherited manually specified primary key.
> Description
> 	
> I have models which inherit from other models, and they should inherit the primary key. This works fine with Django 3.1. However, if I install Django 3.2 alpha, when I run make_migrations I get the following error messages:
> System check identified some issues:
> WARNINGS:
> accounts.ReservedUsername: (models.W042) Auto-created primary key used when not defining a primary key type, by default 'django.db.models.AutoField'.
> 		HINT: Configure the DEFAULT_AUTO_FIELD setting or the SpeedyCoreAccountsConfig.default_auto_field attribute to point to a subclass of AutoField, e.g. 'django.db.models.BigAutoField'.
> accounts.User: (models.W042) Auto-created primary key used when not defining a primary key type, by default 'djan

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/db/models/base.py", "Model._check_default_pk"]]`

新预测：`[["django/db/models/base.py", "Model._check_default_pk"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=19723/1931；耗时=242.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/models/base.py", "Model._check_default_pk"]], "seeds": [["django/db/models/base.py", "Model._check_default_pk"]], "causal_received": [["django/db/models/base.py", "Model._check_default_pk"]], "final": [["django/db/models/base.py", "Model._check_default_pk"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/base.py", "Model._check_default_pk"]]`
- D：Check function for default primary key；依据：；关联：`[]`
- E：Class definition for Model；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13925.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13925.jsonl)

## 66. django__django-13933

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> ModelChoiceField does not provide value of invalid choice when raising ValidationError
> Description
> 	 
> 		(last modified by Aaron Wiegel)
> 	 
> Compared with ChoiceField and others, ModelChoiceField does not show the value of the invalid choice when raising a validation error. Passing in parameters with the invalid value and modifying the default error message for the code invalid_choice should fix this.
> From source code:
> class ModelMultipleChoiceField(ModelChoiceField):
> 	"""A MultipleChoiceField whose choices are a model QuerySet."""
> 	widget = SelectMultiple
> 	hidden_widget = MultipleHiddenInput
> 	default_error_messages = {
> 		'invalid_list': _('Enter a list of values.'),
> 		'invalid_choice': _('Select a valid choice. %(value)s is not one of the'
> 							' available choices.'),
> 		'invalid_pk_value'

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/models.py", "ModelChoiceField.to_python"]]`

新预测：`[["django/db/models/fields/__init__.py", "Field.validate"], ["django/forms/fields.py", "ChoiceField.valid_value"], ["django/forms/fields.py", "MultipleChoiceField.validate"], ["django/forms/fields.py", "TypedMultipleChoiceField.validate"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=18017/3742；耗时=444.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 21, "causal": 11}`。

- E：Incorrect validate method implementation；依据：；关联：`[["django/forms/fields.py", "TypedMultipleChoiceField.validate"]]`
- F：Incorrect valid_value method implementation；依据：；关联：`[["django/forms/fields.py", "ChoiceField.valid_value"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/fields/__init__.py", "Field.validate"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/forms/fields.py", "MultipleChoiceField.validate"]]`
- C：Dependency on Product；依据：；关联：`[["django/forms/fields.py", "MultipleChoiceField.validate"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13933.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13933.jsonl)

## 67. django__django-13964

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Saving parent object after setting on child leads to data loss for parents with non-numeric primary key.
> Description
> 	 
> 		(last modified by Charlie DeTar)
> 	 
> Given a model with a foreign key relation to another model that has a non-auto CharField as its primary key:
> class Product(models.Model):
> 	sku = models.CharField(primary_key=True, max_length=50)
> class Order(models.Model):
> 	product = models.ForeignKey(Product, on_delete=models.CASCADE)
> If the relation is initialized on the parent with an empty instance that does not yet specify its primary key, and the primary key is subsequently defined, the parent does not "see" the primary key's change:
> with transaction.atomic():
> 	order = Order()
> 	order.product = Product()
> 	order.product.sku = "foo"
> 	order.product.save()
> 	order.save()
> 	assert Order.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/base.py", "Model._prepare_related_fields_for_save"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=19146/5381；耗时=434.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Transaction deferral of foreign key constraints；依据：；关联：`[]`
- E：Parent object not seeing primary key change；依据：；关联：`[]`
- F：Order not correctly updating product_id during assignment；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-13964.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-13964.jsonl)

## 68. django__django-14016

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> "TypeError: cannot pickle" when applying | operator to a Q object
> Description
> 	 
> 		(last modified by Daniel Izquierdo)
> 	 
> Using a reference to a non-pickleable type of object such as dict_keys in a Q object makes the | operator fail:
> >>> from django.db.models import Q
> >>> Q(x__in={}.keys())
> <Q: (AND: ('x__in', dict_keys([])))>
> >>> Q() | Q(x__in={}.keys())
> Traceback (most recent call last):
> ...
> TypeError: cannot pickle 'dict_keys' object
> Even though this particular example could be solved by doing Q() | Q(x__in={}) it still feels like using .keys() should work.
> I can work on a patch if there's agreement that this should not crash.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/query_utils.py", "Q._combine"]]`

新预测：`[["django/db/models/expressions.py", "Combinable.__or__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=28320/8831；耗时=792.0秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["django/db/models/query_utils.py", "Q._combine"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 6, "causal": 32}`。

- A1：Incorrect computation；依据：；关联：`[["django/db/models/expressions.py", "Combinable"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/expressions.py", "Combinable.__or__"]]`
- A2：Wrong logic；依据：；关联：`[["django/db/models/query_utils.py", "Q"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- D：Non-pickleable type used in Q object；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14016.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14016.jsonl)

## 69. django__django-14017

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Q(...) & Exists(...) raises a TypeError
> Description
> 	
> Exists(...) & Q(...) works, but Q(...) & Exists(...) raise a TypeError
> Here's a minimal example:
> In [3]: Exists(Product.objects.all()) & Q()
> Out[3]: <Q: (AND: <django.db.models.expressions.Exists object at 0x7fc18dd0ed90>, (AND: ))>
> In [4]: Q() & Exists(Product.objects.all())
> ---------------------------------------------------------------------------
> TypeError								 Traceback (most recent call last)
> <ipython-input-4-21d3dea0fcb9> in <module>
> ----> 1 Q() & Exists(Product.objects.all())
> ~/Code/venv/ecom/lib/python3.8/site-packages/django/db/models/query_utils.py in __and__(self, other)
> 	 90 
> 	 91	 def __and__(self, other):
> ---> 92		 return self._combine(other, self.AND)
> 	 93 
> 	 94	 def __invert__(self):
> ~/Code/venv/ecom/lib/python3.8/si

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/query_utils.py", "Q._combine"]]`

新预测：`[["django/contrib/postgres/search.py", "SearchQueryCombinable.__rand__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=5754/1736；耗时=226.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/postgres/search.py", "SearchQueryCombinable.__rand__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14017.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14017.jsonl)

## 70. django__django-14155

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> ResolverMatch.__repr__() doesn't handle functools.partial() nicely.
> Description
> 	 
> 		(last modified by Nick Pope)
> 	 
> When a partial function is passed as the view, the __repr__ shows the func argument as functools.partial which isn't very helpful, especially as it doesn't reveal the underlying function or arguments provided.
> Because a partial function also has arguments provided up front, we need to handle those specially so that they are accessible in __repr__.
> ISTM that we can simply unwrap functools.partial objects in ResolverMatch.__init__().

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/urls/resolvers.py", "ResolverMatch.__repr__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=8314/2034；耗时=205.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14155.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14155.jsonl)

## 71. django__django-14238

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> DEFAULT_AUTO_FIELD subclass check fails for subclasses of BigAutoField and SmallAutoField.
> Description
> 	
> Set DEFAULT_AUTO_FIELD = "example.core.models.MyBigAutoField" , with contents of example.core.models:
> from django.db import models
> class MyBigAutoField(models.BigAutoField):
> 	pass
> class MyModel(models.Model):
> 	pass
> Django then crashes with:
> Traceback (most recent call last):
>  File "/..././manage.py", line 21, in <module>
> 	main()
>  File "/..././manage.py", line 17, in main
> 	execute_from_command_line(sys.argv)
>  File "/.../venv/lib/python3.9/site-packages/django/core/management/__init__.py", line 419, in execute_from_command_line
> 	utility.execute()
>  File "/.../venv/lib/python3.9/site-packages/django/core/management/__init__.py", line 395, in execute
> 	django.setup()
>  File "/.../venv/lib/pyth

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]]`

新预测：`[["django/db/models/fields/__init__.py", "AutoFieldMeta.__instancecheck__"], ["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=16788/4741；耗时=417.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]], "seeds": [["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]], "causal_received": [["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]], "final": [["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 3}`。

- A1：Incorrect computation；依据：；关联：`[["django/db/models/fields/__init__.py", "AutoFieldMeta"]]`
- A：Inaccurate recursive check；依据：；关联：`[["", "self._subclasses"]]`
- A2：Wrong logic；依据：；关联：`[["django/db/models/fields/__init__.py", "AutoFieldMeta.__instancecheck__"]]`
- D：Subclass check failure；依据：；关联：`[["django/db/models/fields/__init__.py", "AutoFieldMeta.__subclasscheck__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- E：Custom field does not subclass AutoField；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14238.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14238.jsonl)

## 72. django__django-14382

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> django-admin startapp with trailing slash in directory name results in error
> Description
> 	
> Bash tab-completion appends trailing slashes to directory names. django-admin startapp name directory/ results in the error:
> CommandError: '' is not a valid app directory. Please make sure the directory is a valid identifier.
> The error is caused by ​line 77 of django/core/management/templates.py by calling basename() on the path with no consideration for a trailing slash:
> self.validate_name(os.path.basename(target), 'directory')
> Removing potential trailing slashes would solve the problem:
> self.validate_name(os.path.basename(target.rstrip(os.sep)), 'directory')

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/management/templates.py", "TemplateCommand.handle"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=6967/1249；耗时=145.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14382.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14382.jsonl)

## 73. django__django-14411

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Label for ReadOnlyPasswordHashWidget points to non-labelable element.
> Description
> 	 
> 		(last modified by David Sanders)
> 	 
> In the admin, the label element for the ReadOnlyPasswordHashWidget widget has a 'for' attribute which points to a non-labelable element, since the widget just renders text, not an input. There's no labelable element for the widget, so the label shouldn't have a 'for' attribute.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/auth/forms.py", "ReadOnlyPasswordHashWidget.id_for_label"]]`

新预测：`[["django/contrib/admin/helpers.py", "AdminReadonlyField.__init__"], ["django/contrib/admin/templatetags/admin_list.py", "result_headers"], ["django/contrib/admin/utils.py", "label_for_field"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=25172/3539；耗时=372.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 5, "causal": 25}`。

- D1：result_headers；依据：；关联：`[["django/contrib/admin/templatetags/admin_list.py", "result_headers"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/utils.py", "label_for_field"]]`
- D2：__init__；依据：；关联：`[["django/contrib/admin/helpers.py", "AdminReadonlyField.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14411.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14411.jsonl)

## 74. django__django-14534

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> BoundWidget.id_for_label ignores id set by ChoiceWidget.options
> Description
> 	
> If you look at the implementation of BoundField.subwidgets
> class BoundField:
> 	...
> 	def subwidgets(self):
> 		id_ = self.field.widget.attrs.get('id') or self.auto_id
> 		attrs = {'id': id_} if id_ else {}
> 		attrs = self.build_widget_attrs(attrs)
> 		return [
> 			BoundWidget(self.field.widget, widget, self.form.renderer)
> 			for widget in self.field.widget.subwidgets(self.html_name, self.value(), attrs=attrs)
> 		]
> one sees that self.field.widget.subwidgets(self.html_name, self.value(), attrs=attrs) returns a dict and assigns it to widget. Now widget['attrs']['id'] contains the "id" we would like to use when rendering the label of our CheckboxSelectMultiple.
> However BoundWidget.id_for_label() is implemented as
> class BoundWid

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |

共同严格目标：`[["django/forms/boundfield.py", "BoundWidget.id_for_label"]]`

新预测：`[["django/forms/boundfield.py", "BoundField.id_for_label"], ["django/forms/boundfield.py", "BoundField.label_tag"], ["django/forms/boundfield.py", "BoundWidget.id_for_label"]]`

搜索种子 8；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=27964/8631；耗时=689.7秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/forms/boundfield.py", "BoundWidget.id_for_label"]], "seeds": [["django/forms/boundfield.py", "BoundWidget.id_for_label"]], "causal_received": [["django/forms/boundfield.py", "BoundWidget.id_for_label"]], "final": [["django/forms/boundfield.py", "BoundWidget.id_for_label"]]}`。

各角色实际收到显式函数体数：`{"main_search": 7, "relevance": 12, "causal": 31}`。

- D1：Class BoundField；依据：；关联：`[["django/forms/boundfield.py", "BoundField"]]`
- E：Issue；依据：；关联：`[]`
- D2：Function label_tag；依据：；关联：`[["django/forms/boundfield.py", "BoundField.label_tag"]]`
- D3：Function id_for_label；依据：；关联：`[["django/forms/boundfield.py", "BoundWidget.id_for_label"]]`
- F：Issue；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["", "self.auto_id"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/forms/boundfield.py", "BoundField.id_for_label"]]`
- C：Dependency on Product；依据：；关联：`[["django/forms/boundfield.py", "BoundField.id_for_label"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14534.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14534.jsonl)

## 75. django__django-14580

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Missing import statement in generated migration (NameError: name 'models' is not defined)
> Description
> 	
> I found a bug in Django's latest release: 3.2.4. 
> Given the following contents of models.py:
> from django.db import models
> class MyField(models.TextField):
> 	pass
> class MyBaseModel(models.Model):
> 	class Meta:
> 		abstract = True
> class MyMixin:
> 	pass
> class MyModel(MyMixin, MyBaseModel):
> 	name = MyField(primary_key=True)
> The makemigrations command will generate the following migration file:
> # Generated by Django 3.2.4 on 2021-06-30 19:13
> import app.models
> from django.db import migrations
> class Migration(migrations.Migration):
> 	initial = True
> 	dependencies = [
> 	]
> 	operations = [
> 		migrations.CreateModel(
> 			name='MyModel',
> 			fields=[
> 				('name', app.models.MyField(primary_key=True, serialize=

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/serializer.py", "TypeSerializer.serialize"]]`

新预测：`[]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=29269/7855；耗时=700.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/core/management/commands/makemigrations.py", "makemigrations.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/core/management/commands/squashmigrations.py", "squashmigrations.py"]]`
- C：Dependency on Product；依据：；关联：`[["django/core/management/commands/squashmigrations.py", "squashmigrations.py"]]`
- G：migrations.py；依据：；关联：`[]`
- D：writer.py；依据：；关联：`[["django/db/migrations/writer.py", "writer.py"]]`
- H：module_loading.py；依据：；关联：`[]`
- F：apps.py；依据：；关联：`[]`
- E：loader.py；依据：；关联：`[["django/db/migrations/loader.py", "loader.py"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14580.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14580.jsonl)

## 76. django__django-14608

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Add `nonform` CSS class for non form errors in FormSets
> Description
> 	 
> 		(last modified by Ties Jan Hefting)
> 	 
> Forms add the nonfield CSS class for non field errors in ErrorList instances. This is documented in a section on ​rendering form error messages. Similarly, in FormSets I'd expect to see the nonform CSS class added for non form errors. This would allow a custom ErrorList to make a distinction in form field errors, non field errors (forms) and non form errors (FormSets) when rendering error messages. Therefore I'd suggest to add this nonform CSS class and document it for developers to use.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/formsets.py", "BaseFormSet.full_clean"]]`

新预测：`[]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=10169/1450；耗时=188.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 1}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/forms/forms.py", "forms.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14608.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14608.jsonl)

## 77. django__django-14667

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> QuerySet.defer() doesn't clear deferred field when chaining with only().
> Description
> 	
> Considering a simple Company model with four fields: id, name, trade_number and country. If we evaluate a queryset containing a .defer() following a .only(), the generated sql query selects unexpected fields. For example: 
> Company.objects.only("name").defer("name")
> loads all the fields with the following query:
> SELECT "company"."id", "company"."name", "company"."trade_number", "company"."country" FROM "company"
> and 
> Company.objects.only("name").defer("name").defer("country")
> also loads all the fields with the same query:
> SELECT "company"."id", "company"."name", "company"."trade_number", "company"."country" FROM "company"
> In those two cases, i would expect the sql query to be:
> SELECT "company"."id" FROM "

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query.add_deferred_loading"]]`

新预测：`[["django/db/models/query.py", "QuerySet._chain"], ["django/db/models/query.py", "QuerySet.defer"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=22827/2961；耗时=304.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 29}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/query.py", "QuerySet.defer"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/models/query.py", "QuerySet._chain"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/models/query.py", "QuerySet._chain"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14667.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14667.jsonl)

## 78. django__django-14672

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Missing call `make_hashable` on `through_fields` in `ManyToManyRel`
> Description
> 	
> In 3.2 identity property has been added to all ForeignObjectRel to make it possible to compare them. A hash is derived from said identity and it's possible because identity is a tuple. To make limit_choices_to hashable (one of this tuple elements), ​there's a call to make_hashable.
> It happens that through_fields can be a list. In such case, this make_hashable call is missing in ​ManyToManyRel.
> For some reason it only fails on checking proxy model. I think proxy models have 29 checks and normal ones 24, hence the issue, but that's just a guess.
> Minimal repro:
> class Parent(models.Model):
> 	name = models.CharField(max_length=256)
> class ProxyParent(Parent):
> 	class Meta:
> 		proxy = True
> class Child(models.Model):
> 	p

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/reverse_related.py", "ManyToManyRel.identity"]]`

新预测：`[["django/db/models/fields/reverse_related.py", "ForeignObjectRel.__hash__"], ["django/utils/tree.py", "Node.__hash__"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=29519/2813；耗时=289.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 22, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/fields/reverse_related.py", "ForeignObjectRel.__hash__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/utils/tree.py", "Node.__hash__"]]`
- C：Dependency on Product；依据：；关联：`[["django/utils/tree.py", "Node.__hash__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14672.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14672.jsonl)

## 79. django__django-14730

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Prevent developers from defining a related_name on symmetrical ManyToManyFields
> Description
> 	
> In ManyToManyField, if the symmetrical argument is passed, or if it's a self-referential ManyToMany relationship, the related field on the target model is not created. However, if a developer passes in the related_name not understanding this fact, they may be confused until they find the information about symmetrical relationship. Thus, it is proposed to raise an error when the user defines a ManyToManyField in this condition.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/related.py", "ManyToManyField._check_ignored_options"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=13753/2006；耗时=200.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14730.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14730.jsonl)

## 80. django__django-14752

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Refactor AutocompleteJsonView to support extra fields in autocomplete response
> Description
> 	 
> 		(last modified by mrts)
> 	 
> Adding data attributes to items in ordinary non-autocomplete foreign key fields that use forms.widgets.Select-based widgets is relatively easy. This enables powerful and dynamic admin site customizations where fields from related models are updated immediately when users change the selected item.
> However, adding new attributes to autocomplete field results currently requires extending contrib.admin.views.autocomplete.AutocompleteJsonView and fully overriding the AutocompleteJsonView.get() method. Here's an example:
> class MyModelAdmin(admin.ModelAdmin):
> 	def get_urls(self):
> 		return [
> 			path('autocomplete/', CustomAutocompleteJsonView.as_view(admin_site=self.admin_site

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 50.00% | 33.33% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 0.00% | 命中 |

共同严格目标：`[["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"], ["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.serialize_result"]]`

新预测：`[["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=23961/4652；耗时=416.1秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"]], "seeds": [["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"]], "causal_received": [["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"]], "final": [["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 37, "causal": 5}`。

- D：Maintenance Overhead；依据：；关联：`[]`
- E：Complexity Increase；依据：；关联：`[]`
- F：Lack of Extension Point；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/views/autocomplete.py", "AutocompleteJsonView.get"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14752.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14752.jsonl)

## 81. django__django-14787

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> method_decorator() should preserve wrapper assignments
> Description
> 	
> the function that is passed to the decorator is a partial object and does not have any of the attributes expected from a function i.e. __name__, __module__ etc...
> consider the following case
> def logger(func):
> 	@wraps(func)
> 	def inner(*args, **kwargs):
> 		try:
> 			result = func(*args, **kwargs)
> 		except Exception as e:
> 			result = str(e)
> 		finally:
> 			logger.debug(f"{func.__name__} called with args: {args} and kwargs: {kwargs} resulting: {result}")
> 	return inner
> class Test:
> 	@method_decorator(logger)
> 	def hello_world(self):
> 		return "hello"
> Test().test_method()
> This results in the following exception
> AttributeError: 'functools.partial' object has no attribute '__name__'

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/utils/decorators.py", "_multi_decorate._wrapper"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4634/1382；耗时=152.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14787.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14787.jsonl)

## 82. django__django-14855

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Wrong URL generated by get_admin_url for readonly field in custom Admin Site
> Description
> 	
> When a model containing a ForeignKey field is viewed (or edited) in a custom Admin Site, and that ForeignKey field is listed in readonly_fields, the url generated for the link is /admin/... instead of /custom-admin/....
> This appears to be caused by the following line in django.contrib.admin.helpers get_admin_url:
> url = reverse(url_name, args=[quote(remote_obj.pk)])
> Other parts of the admin use the current_app keyword parameter to identify the correct current name of the Admin Site. (See django.contrib.admin.options.ModelAdmin response_add as just one example)
> I have been able to correct this specific issue by replacing the above line with:
> url = reverse(
> 	url_name,
> 	args=[quote(remote_obj.pk)],
> 	curr

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"]]`

新预测：`[["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"], ["django/contrib/gis/geos/mutable_list.py", "ListMixin.reverse"]]`

搜索种子 7；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=10776/1984；耗时=322.4秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"]], "seeds": [["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"]], "causal_received": [["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"]], "final": [["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"]]}`。

各角色实际收到显式函数体数：`{"main_search": 7, "relevance": 0, "causal": 10}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/helpers.py", "AdminReadonlyField.get_admin_url"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/contrib/gis/geos/mutable_list.py", "ListMixin.reverse"]]`
- C：Dependency on Product；依据：；关联：`[["django/contrib/gis/geos/mutable_list.py", "ListMixin.reverse"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14855.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14855.jsonl)

## 83. django__django-14915

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> ModelChoiceIteratorValue is not hashable.
> Description
> 	
> Recently I migrated from Django 3.0 to Django 3.1. In my code, I add custom data-* attributes to the select widget options. After the upgrade some of those options broke. Error is {TypeError}unhashable type: 'ModelChoiceIteratorValue'.
> Example (this one breaks):
> 	def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
> 		context = super().create_option(name, value, label, selected, index, subindex, attrs)
> 		if not value:
> 			return context
> 		if value in self.show_fields: # This is a dict {1: ['first_name', 'last_name']}
> 			context['attrs']['data-fields'] = json.dumps(self.show_fields[value])
> However, working with arrays is not an issue:
> 	def create_option(self, name, value, label, selected, index, subind

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/models.py", "ModelChoiceIteratorValue.__hash__"]]`

新预测：`[["django/forms/widgets.py", "ChoiceWidget.create_option"], ["django/forms/widgets.py", "Widget.build_attrs"], ["tests/model_forms/test_modelchoicefield.py", "<unresolved>:CustomCheckboxSelectMultiple.create_option"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=14460/3703；耗时=349.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 9}`。

无法唯一映射的函数：`[{"file": "tests/model_forms/test_modelchoicefield.py", "name": "CustomCheckboxSelectMultiple.create_option", "reason": "absent"}]`

- A1：Incorrect computation；依据：；关联：`[["", "self.checked_attribute"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/forms/widgets.py", "ChoiceWidget.create_option"]]`
- A2：Wrong logic；依据：；关联：`[["django/forms/widgets.py", "Widget.build_attrs"]]`
- C1：Dependency on non-hashable values in self.checked_attribute；依据：；关联：`[["", "self.checked_attribute"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/model_forms/test_modelchoicefield.py", "CustomCheckboxSelectMultiple.create_option"]]`
- C：Dependency on Product；依据：；关联：`[["tests/model_forms/test_modelchoicefield.py", "CustomCheckboxSelectMultiple.create_option"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14915.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14915.jsonl)

## 84. django__django-14997

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Remaking table with unique constraint crashes on SQLite.
> Description
> 	
> In Django 4.0a1, this model:
> class Tag(models.Model):
> 	name = models.SlugField(help_text="The tag key.")
> 	value = models.CharField(max_length=150, help_text="The tag value.")
> 	class Meta:
> 		ordering = ["name", "value"]
> 		constraints = [
> 			models.UniqueConstraint(
> 				"name",
> 				"value",
> 				name="unique_name_value",
> 			)
> 		]
> 	def __str__(self):
> 		return f"{self.name}={self.value}"
> with these migrations, using sqlite:
> class Migration(migrations.Migration):
> 	initial = True
> 	dependencies = [
> 	]
> 	operations = [
> 		migrations.CreateModel(
> 			name='Tag',
> 			fields=[
> 				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
> 				('name', models.SlugField(help_text='The tag key.')

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/backends/ddl_references.py", "Expressions.rename_table_references"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=29155/3532；耗时=305.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Unique Constraint Handling；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14997.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14997.jsonl)

## 85. django__django-14999

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> RenameModel with db_table should be a noop.
> Description
> 	
> A RenameModel operation that already has db_table defined must be a noop.
> In Postgres, it drops and recreates foreign key constraints. In sqlite it recreates the table (as expected for a table renaming).

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/operations/models.py", "RenameModel.database_forwards"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=3608/682；耗时=110.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-14999.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-14999.jsonl)

## 86. django__django-15061

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Remove "for = ..." from MultiWidget's <label>.
> Description
> 	
> The instance from Raw MultiWidget class generate id_for_label like f'{id_}0'
> It has not sense.
> For example ChoiceWidget has self.add_id_index and I can decide it myself, how I will see label_id - with or without index.
> I think, it is better to remove completely id_for_label method from MultiWidget Class.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/forms/widgets.py", "MultiWidget.id_for_label"]]`

新预测：`[["django/contrib/postgres/forms/array.py", "SplitArrayWidget.id_for_label"], ["django/forms/widgets.py", "MultiWidget.id_for_label"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=12040/3763；耗时=356.4秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/forms/widgets.py", "MultiWidget.id_for_label"]], "seeds": [["django/forms/widgets.py", "MultiWidget.id_for_label"]], "causal_received": [["django/forms/widgets.py", "MultiWidget.id_for_label"]], "final": [["django/forms/widgets.py", "MultiWidget.id_for_label"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 12, "causal": 11}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/postgres/forms/array.py", "SplitArrayWidget"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/postgres/forms/array.py", "SplitArrayWidget.id_for_label"]]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/forms/widgets.py", "MultiWidget.id_for_label"]]`
- C：Dependency on Product；依据：；关联：`[["django/forms/widgets.py", "MultiWidget.id_for_label"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15061.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15061.jsonl)

## 87. django__django-15202

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> URLField throws ValueError instead of ValidationError on clean
> Description
> 	
> forms.URLField( ).clean('////]@N.AN')
> results in:
> 	ValueError: Invalid IPv6 URL
> 	Traceback (most recent call last):
> 	 File "basic_fuzzer.py", line 22, in TestOneInput
> 	 File "fuzzers.py", line 350, in test_forms_URLField
> 	 File "django/forms/fields.py", line 151, in clean
> 	 File "django/forms/fields.py", line 136, in run_validators
> 	 File "django/core/validators.py", line 130, in __call__
> 	 File "urllib/parse.py", line 440, in urlsplit

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |

共同严格目标：`[["django/core/validators.py", "URLValidator.__call__"]]`

新预测：`[["django/contrib/postgres/fields/array.py", "ArrayField.run_validators"], ["django/core/validators.py", "URLValidator.__call__"], ["django/forms/fields.py", "Field.clean"], ["django/forms/fields.py", "Field.run_validators"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=39768/5543；耗时=547.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/core/validators.py", "URLValidator.__call__"]], "seeds": [["django/core/validators.py", "URLValidator.__call__"]], "causal_received": [["django/core/validators.py", "URLValidator.__call__"]], "final": [["django/core/validators.py", "URLValidator.__call__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 37, "causal": 22}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/postgres/fields/array.py", "ArrayField.run_validators"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/forms/fields.py", "Field.run_validators"]]`
- A2：Wrong logic；依据：；关联：`[["django/forms/fields.py", "Field"]]`
- A3：Catching ValueError and raising ValidationError；依据：；关联：`[["django/forms/fields.py", "Field.clean"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/core/validators.py", "URLValidator.__call__"]]`
- C：Dependency on Product；依据：；关联：`[["django/core/validators.py", "URLValidator.__call__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15202.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15202.jsonl)

## 88. django__django-15213

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> ExpressionWrapper for ~Q(pk__in=[]) crashes.
> Description
> 	 
> 		(last modified by Stefan Brand)
> 	 
> Problem Description
> I'm reducing some Q objects (similar to what is described in ticket:32554. Everything is fine for the case where the result is ExpressionWrapper(Q(pk__in=[])). However, when I reduce to ExpressionWrapper(~Q(pk__in=[])) the query breaks.
> Symptoms
> Working for ExpressionWrapper(Q(pk__in=[]))
> print(queryset.annotate(foo=ExpressionWrapper(Q(pk__in=[]), output_field=BooleanField())).values("foo").query)
> SELECT 0 AS "foo" FROM "table"
> Not working for ExpressionWrapper(~Q(pk__in=[]))
> print(queryset.annotate(foo=ExpressionWrapper(~Q(pk__in=[]), output_field=BooleanField())).values("foo").query)
> SELECT AS "foo" FROM "table"

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/fields/__init__.py", "Field.select_format"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12490/1791；耗时=203.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15213.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15213.jsonl)

## 89. django__django-15252

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> MigrationRecorder does not obey db_router allow_migrate rules
> Description
> 	
> Hi,
> We have a multi-db setup. We have one connection that is for the django project, and several connections that talk to other dbs for information (ie models with managed = False). Django should only create tables in the first connection, never in any of the other connections. We have a simple router that does the following: 
> class Router(object):
> 	def allow_migrate(self, db, model):
> 		if db == 'default':
> 			return True
> 		return False
> Current Behaviour
> We run our functional tests and the migrate command is called against each connection when the test databases are created (see django/test/runner.py, setup_databases, line 300-ish, which calls django/db/backends/creation.py, create_test_db, line 377-ish)
> When this m

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |

共同严格目标：`[["django/db/migrations/executor.py", "MigrationExecutor.migrate"]]`

新预测：`[["django/db/migrations/executor.py", "MigrationExecutor.migrate"], ["django/db/migrations/recorder.py", "MigrationRecorder.ensure_schema"], ["django/db/migrations/recorder.py", "MigrationRecorder.has_table"], ["django/db/migrations/recorder.py", "MigrationRecorder.record_applied"], ["tests/migrations/test_loader.py", "LoaderTests.test_loading_squashed_complex"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=56246/6640；耗时=597.4秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["django/db/migrations/executor.py", "MigrationExecutor.migrate"]], "final": [["django/db/migrations/executor.py", "MigrationExecutor.migrate"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 52}`。

- A1：Incorrect computation；依据：；关联：`[["django/db/migrations/recorder.py", "MigrationRecorder.ensure_schema"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/migrations/recorder.py", "MigrationRecorder"]]`
- A2：Wrong logic；依据：；关联：`[["tests/migrations/test_loader.py", "LoaderTests.test_loading_squashed_complex"]]`
- D：Migrate function calling ensure_schema；依据：；关联：`[["django/db/migrations/executor.py", "MigrationExecutor.migrate"]]`
- E：Has_table checking for django_migrations table；依据：；关联：`[["django/db/migrations/recorder.py", "MigrationRecorder.has_table"]]`
- F：self.Migration field reference；依据：；关联：`[["", "self.Migration"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/migrations/recorder.py", "MigrationRecorder.record_applied"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/migrations/recorder.py", "MigrationRecorder.record_applied"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15252.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15252.jsonl)

## 90. django__django-15320

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Subquery.as_sql() generates invalid SQL.
> Description
> 	 
> 		(last modified by M1ha Shvn)
> 	 
> Since ​this commit Subquery.as_sql(...) method returns incorrect SQL removing first and last symbols instead of absent breakets. Adding Subquery().query.subquery = True attribute fixes the problem. From my point of view, it should be set in Subquery constructor.
> from django.db import connection
> from apps.models import App
> q = Subquery(App.objects.all())
> print(str(q.query))
> # Output SQL is valid:
> # 'SELECT "apps_app"."id", "apps_app"."name" FROM "apps_app"'
> print(q.as_sql(q.query.get_compiler('default'), connection))
> # Outptut SQL is invalid (no S letter at the beggining and " symbol at the end):
> # ('(ELECT "apps_app"."id", "apps_app"."name" FROM "apps_app)', ())
> q.query.subquery = True
> print(q.as_sql(

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/expressions.py", "Subquery.__init__"]]`

新预测：`[["django/contrib/postgres/fields/hstore.py", "KeyTransform.__init__"], ["django/contrib/postgres/fields/hstore.py", "KeyTransform.as_sql"], ["django/db/models/fields/json.py", "HasKeyLookup.as_oracle"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=36228/10329；耗时=833.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 64, "causal": 12}`。

- A1：Incorrect computation；依据：；关联：`[["", "self.key_name,"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/postgres/fields/hstore.py", "KeyTransform.as_sql"]]`
- A2：Wrong logic；依据：；关联：`[["django/db/models/fields/json.py", "HasKeyLookup.as_oracle"]]`
- K：KeyTransform class；依据：；关联：`[["django/contrib/postgres/fields/hstore.py", "KeyTransform.__init__"]]`
- R：Setting subquery attribute；依据：；关联：`[["django/db/models/fields/json.py", "KeyTransformFactory"]]`
- F：KeyTransformFactory；依据：；关联：`[["django/contrib/postgres/fields/hstore.py", "KeyTransformFactory"]]`
- D1：Use of self.key_name,；依据：；关联：`[["", "self.key_name,"]]`
- E：Issue；依据：；关联：`[]`
- D2：Use of self.key_name；依据：；关联：`[["", "self.key_name"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15320.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15320.jsonl)

## 91. django__django-15347

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Messages framework incorrectly serializes/deserializes extra_tags when it's an empty string
> Description
> 	
> When a message is serialised and then deserialised with any of the built in storage backends, then extra_tags=="" is converted to extra_tags==None. This is because MessageEncoder checks for the truthyness of extra_tags rather than checking it is not None.
> To replicate this bug
> >>> from django.conf import settings
> >>> settings.configure() # Just to allow the following import
> >>> from django.contrib.messages.storage.base import Message
> >>> from django.contrib.messages.storage.cookie import MessageEncoder, MessageDecoder
> >>> original_message = Message(10, "Here is a message", extra_tags="")
> >>> encoded_message = MessageEncoder().encode(original_message)
> >>> decoded_message = MessageDecode

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/messages/storage/cookie.py", "MessageEncoder.default"]]`

新预测：`[]`

搜索种子 2；搜索停止=search_round_limit；因果停止=legacy_causal_stop；输入/输出token=34103/6001；耗时=533.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 42, "causal": 9}`。

- A1：Incorrect computation；依据：；关联：`[["", "self.level_tag"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/messages/storage/base.py", "Message"]]`
- A2：Wrong logic；依据：；关联：`[["django/contrib/messages/storage/base.py", "base.py"]]`
- D：MessageEncoder checks for truthiness of extra_tags；依据：；关联：`[]`
- H：MessageDecoder converts None to ""；依据：；关联：`[["django/contrib/messages/storage/cookie.py", "MessageDecoder"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15347.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15347.jsonl)

## 92. django__django-15388

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Dev Server fails to restart after adding BASE_DIR to TEMPLATES[0]['DIRS'] in settings
> Description
> 	
> Repro steps:
> $ pip install -U django
> $ django-admin startproject <name>
> Open settings.py, copy the BASE_DIR variable from line 16 and paste it into the empty DIRS list on line 57
> $ ./manage.py runserver
> Back in your IDE, save a file and watch the dev server *NOT* restart.
> Back in settings.py, remove BASE_DIR from the templates DIRS list. Manually CTRL-C your dev server (as it won't restart on its own when you save), restart the dev server. Now return to your settings.py file, re-save it, and notice the development server once again detects changes and restarts.
> This bug prevents the dev server from restarting no matter where you make changes - it is not just scoped to edits to settings.py.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/template/autoreload.py", "template_changed"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=23702/9830；耗时=803.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A1：Inaccurate recursive check；依据：；关联：`[["tests/staticfiles_tests/test_management.py", "test_management.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["tests/admin_scripts/custom_templates/project_template/project_name/settings.py", "settings.py"]]`
- A2：Wrong logic；依据：；关联：`[["tests/staticfiles_tests/test_checks.py", "test_checks.py"]]`
- C2：Test finder configuration error；依据：；关联：`[["tests/staticfiles_tests/test_finders.py", "test_finders.py"]]`
- D：Project specific configuration error；依据：；关联：`[["tests/admin_scripts/custom_templates/project_template/project_name", "project_name"]]`
- C：Dependency on Product；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- E1：Modification of project structure；依据：；关联：`[["tests/admin_scripts/custom_templates/project_template", "project_template"]]`
- E2：Change in package recognition；依据：；关联：`[["tests/admin_scripts/custom_templates/project_template/project_name/__init__.py", "__init__.py"]]`
- F1：Hidden directory interference；依据：；关联：`[]`
- F2：Additional directory misconfiguration；依据：；关联：`[]`
- F3：Custom template directory misconfiguration；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15388.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15388.jsonl)

## 93. django__django-15400

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> SimpleLazyObject doesn't implement __radd__
> Description
> 	
> Technically, there's a whole bunch of magic methods it doesn't implement, compared to a complete proxy implementation, like that of wrapt.ObjectProxy, but __radd__ being missing is the one that's biting me at the moment.
> As far as I can tell, the implementation can't just be
> __radd__ = new_method_proxy(operator.radd)
> because that doesn't exist, which is rubbish.
> __radd__ = new_method_proxy(operator.attrgetter("__radd__"))
> also won't work because types may not have that attr, and attrgetter doesn't supress the exception (correctly)
> The minimal implementation I've found that works for me is:
> 	def __radd__(self, other):
> 		if self._wrapped is empty:
> 			self._setup()
> 		return other + self._wrapped

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |

共同严格目标：`[["django/utils/functional.py", "lazy.__proxy__.__radd__"]]`

新预测：`[["django/contrib/gis/geos/mutable_list.py", "ListMixin.__radd__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__add__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__bytes_cast"], ["django/utils/functional.py", "<unresolved>:__proxy__.__cast"], ["django/utils/functional.py", "<unresolved>:__proxy__.__eq__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__hash__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__lt__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__mod__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__radd__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__reduce__"], ["django/utils/functional.py", "<unresolved>:__proxy__.__str__"], ["django/utils/functional.py", "LazyObject.__reduce__"], ["django/utils/functional.py", "SimpleLazyObject.__deepcopy__"], ["django/utils/functional.py", "lazy"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=82968/20493；耗时=1614.9秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["django/utils/functional.py", "lazy.__proxy__.__radd__"]], "seeds": [["django/utils/functional.py", "lazy.__proxy__.__radd__"]], "causal_received": [["django/utils/functional.py", "lazy.__proxy__.__radd__"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 117}`。

无法唯一映射的函数：`[{"file": "django/utils/functional.py", "name": "__proxy__.__add__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__radd__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__cast", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__eq__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__hash__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__lt__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__mod__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__reduce__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__str__", "reason": "absent"}, {"file": "django/utils/functional.py", "name": "__proxy__.__bytes_cast", "reason": "absent"}]`

- G：__add__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__add__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/utils/functional.py", "__proxy__.__radd__"]]`
- A1：Incorrect computation；依据：；关联：`[["django/contrib/gis/geos/mutable_list.py", "ListMixin"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/gis/geos/mutable_list.py", "ListMixin.__radd__"]]`
- A2：Wrong logic；依据：；关联：`[]`
- H：__cast；依据：；关联：`[["django/utils/functional.py", "__proxy__.__cast"]]`
- J：__eq__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__eq__"]]`
- K：__hash__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__hash__"]]`
- L：__lt__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__lt__"]]`
- M：__mod__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__mod__"]]`
- N：__reduce__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__reduce__"], ["django/utils/functional.py", "LazyObject.__reduce__"]]`
- O：__str__；依据：；关联：`[["django/utils/functional.py", "__proxy__.__str__"]]`
- P：__text_cast；依据：；关联：`[["django/utils/functional.py", "SimpleLazyObject.__deepcopy__"]]`
- Q：__bytes_cast；依据：；关联：`[["django/utils/functional.py", "__proxy__.__bytes_cast"]]`
- R：__bytes_cast_encoded；依据：；关联：`[["django/utils/functional.py", "__proxy__.__bytes_cast"]]`
- E：__proxy__；依据：；关联：`[["django/utils/functional.py", "__proxy__"]]`
- D：ListMixin；依据：；关联：`[["django/contrib/gis/geos/mutable_list.py", "ListMixin"]]`
- C：Dependency on Product；依据：；关联：`[["django/utils/functional.py", "__proxy__.__radd__"]]`
- F：Missing __radd__ method in SimpleLazyObject；依据：；关联：`[["django/utils/functional.py", "lazy"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15400.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15400.jsonl)

## 94. django__django-15498

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Fix handling empty string for If-Modified-Since header
> Description
> 	
> Empty string used to be ignored for If-Modified-Since header, but now raises exception since d6aff369ad3.
> Fix handling empty string for If-Modified-Since header
> Description
> 	
> Empty string used to be ignored for If-Modified-Since header, but now raises exception since d6aff369ad3.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/views/static.py", "was_modified_since"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14162/1968；耗时=252.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15498.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15498.jsonl)

## 95. django__django-15695

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> RenameIndex() crashes when unnamed index is moving backward and forward.
> Description
> 	
> RenameIndex() should restore the old auto-generated name when an unnamed index for unique_together is moving backward. Now re-applying RenameIndex() crashes. For example:
> tests/migrations/test_operations.py
> diff --git a/tests/migrations/test_operations.py b/tests/migrations/test_operations.py
> index cfd28b1b39..c0a55023bb 100644
> 					
> 					 a
> 				 
> 					
> 					 b
> 				 
>  class OperationTests(OperationTestBase): 
> 29882988        with connection.schema_editor() as editor, self.assertNumQueries(0):
> 29892989            operation.database_backwards(app_label, editor, new_state, project_state)
> 29902990        self.assertIndexNameExists(table_name, "new_pony_test_idx")
>  2991        # Re-apply renaming.
>  2992      

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/operations/models.py", "RenameIndex.database_forwards"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=5779/786；耗时=108.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15695.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15695.jsonl)

## 96. django__django-15738

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Models migration with change field foreign to many and deleting unique together.
> Description
> 	 
> 		(last modified by Simon Charette)
> 	 
> I have models like
> class Authors(models.Model):
> 	project_data_set = models.ForeignKey(
> 		ProjectDataSet,
> 		on_delete=models.PROTECT
> 	)
> 	state = models.IntegerField()
> 	start_date = models.DateField()
> 	class Meta:
> 		 unique_together = (('project_data_set', 'state', 'start_date'),)
> and
> class DataSet(models.Model):
> 	name = models.TextField(max_length=50)
> class Project(models.Model):
> 	data_sets = models.ManyToManyField(
> 		DataSet,
> 		through='ProjectDataSet',
> 	)
> 	name = models.TextField(max_length=50)
> class ProjectDataSet(models.Model):
> 	"""
> 	Cross table of data set and project
> 	"""
> 	data_set = models.ForeignKey(DataSet, on_delete=models.PROTECT)
> 	project = model

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/autodetector.py", "MigrationAutodetector._generate_added_field"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=18396/3317；耗时=321.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Removing unique_together constraint；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15738.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15738.jsonl)

## 97. django__django-15781

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Customizable management command formatters.
> Description
> 	
> With code like:
> class Command(BaseCommand):
> 	help = '''
> 	Import a contract from tzkt.
> 	Example usage:
> 		./manage.py tzkt_import 'Tezos Mainnet' KT1HTDtMBRCKoNHjfWEEvXneGQpCfPAt6BRe
> 	'''
> Help output is:
> $ ./manage.py help tzkt_import
> usage: manage.py tzkt_import [-h] [--api API] [--version] [-v {0,1,2,3}] [--settings SETTINGS]
> 							 [--pythonpath PYTHONPATH] [--traceback] [--no-color] [--force-color]
> 							 [--skip-checks]
> 							 blockchain target
> Import a contract from tzkt Example usage: ./manage.py tzkt_import 'Tezos Mainnet'
> KT1HTDtMBRCKoNHjfWEEvXneGQpCfPAt6BRe
> positional arguments:
>  blockchain			Name of the blockchain to import into
>  target				Id of the contract to import
> When that was expected:
> $ ./manage.py help tzkt_impor

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/management/base.py", "BaseCommand.create_parser"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14457/2434；耗时=218.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15781.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15781.jsonl)

## 98. django__django-15789

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Add an encoder parameter to django.utils.html.json_script().
> Description
> 	
> I have a use case where I want to customize the JSON encoding of some values to output to the template layer. It looks like django.utils.html.json_script is a good utility for that, however the JSON encoder is hardcoded to DjangoJSONEncoder. I think it would be nice to be able to pass a custom encoder class.
> By the way, django.utils.html.json_script is not documented (only its template filter counterpart is), would it be a good thing to add to the docs?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/utils/html.py", "json_script"]]`

新预测：`[["django/template/defaultfilters.py", "json_script"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=32323/6498；耗时=680.2秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["django/utils/html.py", "json_script"]], "seeds": [["django/utils/html.py", "json_script"]], "causal_received": [["django/utils/html.py", "json_script"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 60}`。

- A1：Incorrect computation；依据：；关联：`[["django/template/defaultfilters.py", "defaultfilters.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/template/defaultfilters.py", "json_script"]]`
- A2：Wrong logic；依据：；关联：`[]`
- D：Customizable JSON encoder；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15789.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15789.jsonl)

## 99. django__django-15790

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> check_for_template_tags_with_the_same_name with libraries in TEMPLATES
> Description
> 	
> I didn't explore this thoroughly, but I think there might be an issue with the check_for_template_tags_with_the_same_name when you add a template tag library into TEMPLATES['OPTIONS']['librairies'].
> I'm getting an error like: 
> (templates.E003) 'my_tags' is used for multiple template tag modules: 'someapp.templatetags.my_tags', 'someapp.templatetags.my_tags'

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 14.29% | 100.00% | 25.00% | 100.00% | 命中 |

共同严格目标：`[["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"]]`

新预测：`[["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"], ["django/template/backends/django.py", "get_template_tag_modules"], ["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.get_settings"], ["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_different_library_name"], ["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_different_name"], ["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_same_library_name"], ["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_same_name"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=29105/11139；耗时=845.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"]], "seeds": [["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"]], "causal_received": [["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"]], "final": [["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"]]}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 6, "causal": 10}`。

- A1：Incorrect computation；依据：；关联：`[["", "self.error_same_tags"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/core/checks/templates.py", "check_for_template_tags_with_the_same_name"]]`
- A2：Wrong logic；依据：；关联：`[["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.get_settings"]]`
- D：E003；依据：；关联：`[["django/core/checks/templates.py", "E003"]]`
- E：get_template_tag_modules；依据：；关联：`[["django/template/backends/django.py", "get_template_tag_modules"]]`
- F：test_template_tags_with_same_library_name_and_module_name；依据：；关联：`[["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_same_name"]]`
- G：test_template_tags_with_different_name；依据：；关联：`[["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_different_name"]]`
- H：test_template_tags_with_different_library_name；依据：；关联：`[["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_different_library_name"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_same_library_name"]]`
- C：Dependency on Product；依据：；关联：`[["tests/check_framework/test_templates.py", "CheckTemplateTagLibrariesWithSameName.test_template_tags_with_same_library_name"]]`
- C1：CheckTemplateTagLibrariesWithSameName；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15790.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15790.jsonl)

## 100. django__django-15814

项目：django/django；本轮子集：开发集；状态：complete。

问题描述节选：

> QuerySet.only() after select_related() crash on proxy models.
> Description
> 	
> When I optimize a query using select_related() and only() methods from the proxy model I encounter an error:
> Windows 10; Python 3.10; Django 4.0.5
> Traceback (most recent call last):
>  File "D:\study\django_college\manage.py", line 22, in <module>
> 	main()
>  File "D:\study\django_college\manage.py", line 18, in main
> 	execute_from_command_line(sys.argv)
>  File "D:\Anaconda3\envs\django\lib\site-packages\django\core\management\__init__.py", line 446, in execute_from_command_line
> 	utility.execute()
>  File "D:\Anaconda3\envs\django\lib\site-packages\django\core\management\__init__.py", line 440, in execute
> 	self.fetch_command(subcommand).run_from_argv(self.argv)
>  File "D:\Anaconda3\envs\django\lib\site-packages\django\core\m

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query.deferred_to_data"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=22418/4594；耗时=416.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Incorrect metadata reference for proxy models；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15814.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15814.jsonl)

## 101. django__django-15819

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> inspectdb should generate related_name on same relation links.
> Description
> 	
> Hi!
> After models generation with inspectdb command we have issue with relations to same enities
> module.Model.field1: (fields.E304) Reverse accessor for 'module.Model.field1' clashes with reverse accessor for 'module.Model.field2'.
> HINT: Add or change a related_name argument to the definition for 'module.Model.field1' or 'module.Model.field2'.
> *
> Maybe we can autogenerate
> related_name='attribute_name'
> to all fields in model if related Model was used for this table

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/core/management/commands/inspectdb.py", "Command.handle_inspection"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11949/1846；耗时=246.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15819.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15819.jsonl)

## 102. django__django-15851

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> dbshell additional parameters should be passed before dbname on PostgreSQL.
> Description
> 	
> psql expects all options to proceed the database name, if provided. So, if doing something like `./manage.py dbshell -- -c "select * from some_table;" one will get this:
> $ ./manage.py dbshell -- -c "select * from some_table;"
> psql: warning: extra command-line argument "-c" ignored
> psql: warning: extra command-line argument "select * from some_table;" ignored
> psql (10.21)
> Type "help" for help.
> some_database=>
> It appears the args list just need to be constructed in the proper order, leaving the database name for the end of the args list.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/backends/postgresql/client.py", "DatabaseClient.settings_to_cmd_args_env"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=10919/1810；耗时=208.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15851.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15851.jsonl)

## 103. django__django-15902

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> "default.html" deprecation warning raised for ManagementForm's
> Description
> 	
> I have a project where I never render forms with the {{ form }} expression. However, I'm still getting the new template deprecation warning because of the formset management form production, during which the template used is insignificant (only hidden inputs are produced).
> Is it worth special-casing this and avoid producing the warning for the management forms?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11569/1731；耗时=180.7秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15902.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15902.jsonl)

## 104. django__django-15996

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Support for serialization of combination of Enum flags.
> Description
> 	 
> 		(last modified by Willem Van Onsem)
> 	 
> If we work with a field:
> regex_flags = models.IntegerField(default=re.UNICODE | re.IGNORECASE)
> This is turned into a migration with:
> default=re.RegexFlag[None]
> This is due to the fact that the EnumSerializer aims to work with the .name of the item, but if there is no single item for the given value, then there is no such name.
> In that case, we can use enum._decompose to obtain a list of names, and create an expression to create the enum value by "ORing" the items together.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| CoSIL/off | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/serializer.py", "EnumSerializer.serialize"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4250/723；耗时=133.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-15996.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-15996.jsonl)

## 105. django__django-16041

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Rendering empty_form crashes when empty_permitted is passed to form_kwargs
> Description
> 	
> Issue
> When explicitly setting form_kwargs = {'empty_permitted':True} or form_kwargs = {'empty_permitted':False} , a KeyError occurs when rendering a template that uses a formset's empty_form.
> Expected Behavior
> empty_permitted is ignored for formset.empty_form since empty_permitted is irrelevant for empty_form, as empty_form is not meant to be used to pass data and therefore does not need to be validated.
> Steps to Reproduce
> # views.py
> from django.shortcuts import render
> from .models import MyModel
> def test_view(request):
> 	context = {}
> 	ff = modelformset_factory(MyModel, fields = ['a_field'])
> 	context['formset'] = ff(
> 		queryset = MyModel.objects.none(),
> 		form_kwargs = {'empty_permitted':True} # or form

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/formsets.py", "BaseFormSet.empty_form"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=27849/3318；耗时=296.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 64, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16041.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16041.jsonl)

## 106. django__django-16046

项目：django/django；本轮子集：开发集；状态：complete。

问题描述节选：

> Fix numberformat.py "string index out of range" when null
> Description
> 	
> When:
> if str_number[0] == "-"
> encounters a number field that's null when formatting for the admin list_display this causes an 
> IndexError: string index out of range
> I can attach the proposed fix here, or open a pull request on GitHub if you like?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/utils/numberformat.py", "format"]]`

新预测：`[["django/utils/numberformat.py", "format"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=44225/11032；耗时=971.7秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["django/utils/numberformat.py", "format"]], "final": [["django/utils/numberformat.py", "format"]]}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 8}`。

- D：format function；依据：；关联：`[["django/utils/numberformat.py", "format"]]`
- E：test_numberformat.py；依据：；关联：`[["tests/utils_tests/test_numberformat.py", "test_numberformat.py"]]`
- F：tests.py；依据：；关联：`[["tests/i18n/tests.py", "tests.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/utils/numberformat.py", "numberformat.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16046.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16046.jsonl)

## 107. django__django-16139

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Accessing UserAdmin via to_field leads to link to PasswordResetForm being broken (404)
> Description
> 	 
> 		(last modified by Simon Kern)
> 	 
> Accessing the UserAdmin via another model's Admin that has a reference to User (with to_field set, e.g., to_field="uuid") leads to the UserAdmin being accessed via an url that looks similar to this one:
> .../user/22222222-3333-4444-5555-666677778888/change/?_to_field=uuid
> However the underlying form looks like this: 
> Code highlighting:
> class UserChangeForm(forms.ModelForm):
> 	password = ReadOnlyPasswordHashField(
> 		label=_("Password"),
> 		help_text=_(
> 			"Raw passwords are not stored, so there is no way to see this "
> 			"user’s password, but you can change the password using "
> 			'<a href="{}">this form</a>.'
> 		),
> 	)
> 	...
> 	...
> 	def __init__(self, *args, **kw

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/auth/forms.py", "UserChangeForm.__init__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=17142/3109；耗时=270.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16139.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16139.jsonl)

## 108. django__django-16229

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> ModelForm fields with callable defaults don't correctly propagate default values
> Description
> 	
> When creating an object via the admin, if an inline contains an ArrayField in error, the validation will be bypassed (and the inline dismissed) if we submit the form a second time (without modification).
> go to /admin/my_app/thing/add/
> type anything in plop
> submit -> it shows an error on the inline
> submit again -> no errors, plop become unfilled
> # models.py
> class Thing(models.Model):
> 	pass
> class RelatedModel(models.Model):
> 	thing = models.ForeignKey(Thing, on_delete=models.CASCADE)
> 	plop = ArrayField(
> 		models.CharField(max_length=42),
> 		default=list,
> 	)
> # admin.py
> class RelatedModelForm(forms.ModelForm):
> 	def clean(self):
> 		raise ValidationError("whatever")
> class RelatedModelInline(admin.TabularI

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/forms/boundfield.py", "BoundField.as_widget"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=18334/5093；耗时=424.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- C1：Callable default for ArrayField；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- D：Form handling of hidden inputs；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D1：Setting show_hidden_initial=False；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16229.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16229.jsonl)

## 109. django__django-16255

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Sitemaps without items raise ValueError on callable lastmod.
> Description
> 	
> When sitemap contains not items, but supports returning lastmod for an item, it fails with a ValueError:
> Traceback (most recent call last):
>  File "/usr/local/lib/python3.10/site-packages/django/core/handlers/exception.py", line 55, in inner
> 	response = get_response(request)
>  File "/usr/local/lib/python3.10/site-packages/django/core/handlers/base.py", line 197, in _get_response
> 	response = wrapped_callback(request, *callback_args, **callback_kwargs)
>  File "/usr/local/lib/python3.10/site-packages/django/utils/decorators.py", line 133, in _wrapped_view
> 	response = view_func(request, *args, **kwargs)
>  File "/usr/local/lib/python3.10/site-packages/django/contrib/sitemaps/views.py", line 34, in inner
> 	response = func(requ

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |

共同严格目标：`[["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"]]`

新预测：`[["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"], ["django/contrib/sitemaps/__init__.py", "Sitemap.items"], ["tests/sitemaps_tests/urls/http.py", "GetLatestLastmodNoneSiteMap.get_latest_lastmod"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=23059/12141；耗时=957.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"]], "seeds": [["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"]], "causal_received": [["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"]], "final": [["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"]]}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 15}`。

- A1：Incorrect computation；依据：；关联：`[["django/contrib/sitemaps/__init__.py", "Sitemap"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/sitemaps/__init__.py", "Sitemap.get_latest_lastmod"]]`
- A2：Wrong logic；依据：；关联：`[["", "self.lastmod"]]`
- D：Empty items list；依据：；关联：`[["django/contrib/sitemaps/__init__.py", "Sitemap.items"]]`
- E：Callable lastmod；依据：；关联：`[["", "self.lastmod"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/sitemaps_tests/urls/http.py", "GetLatestLastmodNoneSiteMap.get_latest_lastmod"]]`
- C：Dependency on Product；依据：；关联：`[["tests/sitemaps_tests/urls/http.py", "GetLatestLastmodNoneSiteMap.get_latest_lastmod"]]`
- H：GetLatestLastmodNoneSiteMap class；依据：；关联：`[]`
- G：_items function；依据：；关联：`[]`
- F：New i18n handling；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16255.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16255.jsonl)

## 110. django__django-16379

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> FileBasedCache has_key is susceptible to race conditions
> Description
> 	 
> 		(last modified by Marti Raudsepp)
> 	 
> I received the exception from Django's cache framework:
> FileNotFoundError: [Errno 2] No such file or directory: '/app/var/cache/d729e4cf4ba88cba5a0f48e0396ec48a.djcache'
> [...]
>  File "django/core/cache/backends/base.py", line 229, in get_or_set
> 	self.add(key, default, timeout=timeout, version=version)
>  File "django/core/cache/backends/filebased.py", line 26, in add
> 	if self.has_key(key, version):
>  File "django/core/cache/backends/filebased.py", line 94, in has_key
> 	with open(fname, "rb") as f:
> The code is:
> 	def has_key(self, key, version=None):
> 		fname = self._key_to_file(key, version)
> 		if os.path.exists(fname):
> 			with open(fname, "rb") as f:
> 				return not self._is_expired(f)
> 		

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]]`

新预测：`[["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=9717/1328；耗时=175.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]], "seeds": [["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]], "causal_received": [["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]], "final": [["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 8, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/core/cache/backends/filebased.py", "FileBasedCache.has_key"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16379.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16379.jsonl)

## 111. django__django-16400

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> migrate management command does not respect database parameter when adding Permissions.
> Description
> 	 
> 		(last modified by Vasanth)
> 	 
> When invoking migrate with a database parameter, the migration runs successfully. However, there seems to be a DB read request that runs after the migration. This call does not respect the db param and invokes the db router .
> When naming the db as a parameter, all DB calls in the context of the migrate command are expected to use the database specified.
> I came across this as I am currently using a thread-local variable to get the active DB with a custom DB router for a multi-tenant service .
> Minimal example 
> Setup the custom middleware and custom DB Router as show below. Then run any DB migration. We see that "read {}" is being printed before the exception 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/auth/management/__init__.py", "create_permissions"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=23487/7241；耗时=560.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- H：DB Read Request During Migration；依据：；关联：`[]`
- J：Thread-Local Variable Usage；依据：；关联：`[]`
- D：TenantSubdomainMiddleware；依据：；关联：`[]`
- E：Issue；依据：；关联：`[]`
- F：TenantDatabaseRouter；依据：；关联：`[]`
- G：Issue；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16400.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16400.jsonl)

## 112. django__django-16408

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Multi-level FilteredRelation with select_related() may set wrong related object.
> Description
> 	
> test case:
> # add to known_related_objects.tests.ExistingRelatedInstancesTests
> 	def test_wrong_select_related(self):
> 		with self.assertNumQueries(3):
> 			p = list(PoolStyle.objects.annotate(
> 				tournament_pool=FilteredRelation('pool__tournament__pool'),
> 				).select_related('tournament_pool'))
> 			self.assertEqual(p[0].pool.tournament, p[0].tournament_pool.tournament)
> result:
> ======================================================================
> FAIL: test_wrong_select_related (known_related_objects.tests.ExistingRelatedInstancesTests.test_wrong_select_related)
> ----------------------------------------------------------------------
> Traceback (most recent call last):
>  File "D:\Work\django\tests\known

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/compiler.py", "SQLCompiler.get_related_selections"], ["django/db/models/sql/compiler.py", "SQLCompiler.get_related_selections.local_setter_noop"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=18263/2220；耗时=214.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16408.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16408.jsonl)

## 113. django__django-16527

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> "show_save_as_new" in admin can add without this permission
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> At "django/contrib/admin/templatetags/admin_modify.py" file, line 102, I think you must put one more verification for this tag: "and has_add_permission", because "save_as_new" is a add modification.
> I rewrite this for my project:
> 			"show_save_as_new": not is_popup
> 			and has_add_permission # This line that I put!!!
> 			and has_change_permission
> 			and change
> 			and save_as,

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/admin/templatetags/admin_modify.py", "submit_row"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4208/819；耗时=122.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16527.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16527.jsonl)

## 114. django__django-16595

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Migration optimizer does not reduce multiple AlterField
> Description
> 	
> Let's consider the following operations: 
> operations = [
> 	migrations.AddField(
> 		model_name="book",
> 		name="title",
> 		field=models.CharField(max_length=256, null=True),
> 	),
> 	migrations.AlterField(
> 		model_name="book",
> 		name="title",
> 		field=models.CharField(max_length=128, null=True),
> 	),
> 	migrations.AlterField(
> 		model_name="book",
> 		name="title",
> 		field=models.CharField(max_length=128, null=True, help_text="help"),
> 	),
> 	migrations.AlterField(
> 		model_name="book",
> 		name="title",
> 		field=models.CharField(max_length=128, null=True, help_text="help", default=None),
> 	),
> ]
> If I run the optimizer, I get only the AddField, as we could expect. However, if the AddField model is separated from the AlterField (e.g. because of a

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |

共同严格目标：`[["django/db/migrations/operations/fields.py", "AlterField.reduce"]]`

新预测：`[["django/db/migrations/operations/base.py", "Operation.reduce"], ["django/db/migrations/operations/fields.py", "AddField.reduce"], ["django/db/migrations/operations/fields.py", "AlterField.reduce"], ["django/db/migrations/operations/models.py", "ModelOperation.reduce"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=22532/7340；耗时=660.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/db/migrations/operations/fields.py", "AlterField.reduce"]], "seeds": [["django/db/migrations/operations/fields.py", "AlterField.reduce"]], "causal_received": [["django/db/migrations/operations/fields.py", "AlterField.reduce"]], "final": [["django/db/migrations/operations/fields.py", "AlterField.reduce"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 11, "causal": 12}`。

- A1：Inaccurate recursive check；依据：；关联：`[["", "self.elidable"]]`
- A：Inaccurate recursive check；依据：；关联：`[["django/db/migrations/operations/base.py", "Operation.reduce"]]`
- A2：Wrong logic；依据：；关联：`[["django/db/migrations/operations/models.py", "ModelOperation.reduce"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/migrations/operations/fields.py", "AddField.reduce"]]`
- C：Dependency on Product；依据：；关联：`[["django/db/migrations/operations/fields.py", "AlterField.reduce"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16595.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16595.jsonl)

## 115. django__django-16816

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Error E108 does not cover some cases
> Description
> 	 
> 		(last modified by Baha Sdtbekov)
> 	 
> I have two models, Question and Choice. And if I write list_display = ["choice"] in QuestionAdmin, I get no errors.
> But when I visit /admin/polls/question/, the following trace is returned:
> Internal Server Error: /admin/polls/question/
> Traceback (most recent call last):
>  File "/some/path/django/contrib/admin/utils.py", line 334, in label_for_field
> 	field = _get_non_gfk_field(model._meta, name)
>  File "/some/path/django/contrib/admin/utils.py", line 310, in _get_non_gfk_field
> 	raise FieldDoesNotExist()
> django.core.exceptions.FieldDoesNotExist
> During handling of the above exception, another exception occurred:
> Traceback (most recent call last):
>  File "/some/path/django/core/handlers/exception.py", line 5

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/contrib/admin/checks.py", "ModelAdminChecks._check_list_display_item"]]`

新预测：`[["django/contrib/admin/utils.py", "label_for_field"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=29151/4919；耗时=435.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 12}`。

- A1：Inaccurate recursive check；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["django/contrib/admin/utils.py", "label_for_field"]]`
- D1：Missing foreign key definition for 'choice'；依据：；关联：`[]`
- B1：Incorrect handling of commutative factors；依据：；关联：`[]`
- C1：Dependency on Product；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16816.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16816.jsonl)

## 116. django__django-16820

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Squashing migrations with Meta.index_together -> indexes transition should remove deprecation warnings.
> Description
> 	
> Squashing migrations with Meta.index_together -> Meta.indexes transition should remove deprecation warnings. As far as I'm aware, it's a 4.2 release blocker because you cannot get rid of the index_together deprecation warnings without rewriting migrations, see comment.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/operations/models.py", "CreateModel.reduce"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=48154/2267；耗时=291.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 1}`。

- A：Inaccurate recursive check；依据：；关联：`[["django/db/migrations/operations/models.py", "models.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16820.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16820.jsonl)

## 117. django__django-16873

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Template filter `join` should not escape the joining string if `autoescape` is `off`
> Description
> 	
> Consider the following template code snippet:
> {% autoescape off %}
> {{ some_list|join:some_var }}
> {% endautoescape %}
> in this case, the items inside some_list will not be escaped (matching the expected behavior) but some_var will forcibly be escaped. From the docs for autoescape or join I don't think this is expected behavior.
> The following testcase illustrates what I think is a bug in the join filter (run inside the template_tests/filter_tests folder):
> from django.template.defaultfilters import escape
> from django.test import SimpleTestCase
> from ..utils import setup
> class RegressionTests(SimpleTestCase):
> 	@setup({"join01": '{{ some_list|join:some_var }}'})
> 	def test_join01(self):
> 		some_list =

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["django/template/defaultfilters.py", "join"]]`

新预测：`[["django/db/models/functions/comparison.py", "<unresolved>:ArgJoiner.join"], ["django/template/defaultfilters.py", "join"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=31452/1695；耗时=255.4秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["django/template/defaultfilters.py", "join"]], "seeds": [["django/template/defaultfilters.py", "join"]], "causal_received": [["django/template/defaultfilters.py", "join"]], "final": [["django/template/defaultfilters.py", "join"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 30}`。

无法唯一映射的函数：`[{"file": "django/db/models/functions/comparison.py", "name": "ArgJoiner.join", "reason": "absent"}]`

- A：Inaccurate recursive check；依据：；关联：`[["django/db/models/functions/comparison.py", "ArgJoiner.join"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/template/defaultfilters.py", "join"]]`
- C：Dependency on Product；依据：；关联：`[["django/template/defaultfilters.py", "join"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16873.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16873.jsonl)

## 118. django__django-16910

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> QuerySet.only() doesn't work with select_related() on a reverse OneToOneField relation.
> Description
> 	
> On Django 4.2 calling only() with select_related() on a query using the reverse lookup for a OneToOne relation does not generate the correct query.
> All the fields from the related model are still included in the generated SQL.
> Sample models:
> class Main(models.Model):
> 	main_field_1 = models.CharField(blank=True, max_length=45)
> 	main_field_2 = models.CharField(blank=True, max_length=45)
> 	main_field_3 = models.CharField(blank=True, max_length=45)
> class Secondary(models.Model):
> 	main = models.OneToOneField(Main, primary_key=True, related_name='secondary', on_delete=models.CASCADE)
> 	secondary_field_1 = models.CharField(blank=True, max_length=45)
> 	secondary_field_2 = models.CharField(blank=True,

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/sql/query.py", "Query._get_only_select_mask"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14793/2037；耗时=211.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-16910.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-16910.jsonl)

## 119. django__django-17051

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Allow returning IDs in QuerySet.bulk_create() when updating conflicts.
> Description
> 	
> Currently, when using bulk_create with a conflict handling flag turned on (e.g. ignore_conflicts or update_conflicts), the primary keys are not set in the returned queryset, as documented in bulk_create.
> While I understand using ignore_conflicts can lead to PostgreSQL not returning the IDs when a row is ignored (see ​this SO thread), I don't understand why we don't return the IDs in the case of update_conflicts.
> For instance:
> MyModel.objects.bulk_create([MyModel(...)], update_conflicts=True, update_fields=[...], unique_fields=[...])
> generates a query without a RETURNING my_model.id part:
> INSERT INTO "my_model" (...)
> VALUES (...)
> 	ON CONFLICT(...) DO UPDATE ...
> If I append the RETURNING my_model.id clause, 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/models/query.py", "QuerySet._batched_insert"]]`

新预测：`[["django/db/models/query.py", "QuerySet.bulk_create"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=50621/7240；耗时=626.2秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["django/db/models/query.py", "QuerySet._batched_insert"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 13}`。

- A1：Incorrect computation；依据：；关联：`[["django/db/models/sql/compiler.py", "SQLInsertCompiler"]]`
- A：Inaccurate recursive check；依据：；关联：`[["", "self.returning_fields"]]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["django/db/models/query.py", "QuerySet.bulk_create"]]`
- D：SQLInsertCompiler；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[["django/db/models/query.py", "QuerySet.bulk_create"]]`
- E：Conditionally removing RETURNING clause；依据：；关联：`[]`
- F：Handling update_conflicts；依据：；关联：`[]`
- G：Setting primary keys on PostgreSQL；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-17051.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-17051.jsonl)

## 120. django__django-17087

项目：django/django；本轮子集：验证集；状态：complete。

问题描述节选：

> Class methods from nested classes cannot be used as Field.default.
> Description
> 	 
> 		(last modified by Mariusz Felisiak)
> 	 
> Given the following model:
>  
> class Profile(models.Model):
> 	class Capability(models.TextChoices):
> 		BASIC = ("BASIC", "Basic")
> 		PROFESSIONAL = ("PROFESSIONAL", "Professional")
> 		
> 		@classmethod
> 		def default(cls) -> list[str]:
> 			return [cls.BASIC]
> 	capabilities = ArrayField(
> 		models.CharField(choices=Capability.choices, max_length=30, blank=True),
> 		null=True,
> 		default=Capability.default
> 	)
> The resulting migration contained the following:
>  # ...
> 	 migrations.AddField(
> 		 model_name='profile',
> 		 name='capabilities',
> 		 field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, choices=[('BASIC', 'Basic'), ('PROFESSIONAL', 'Professional')

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["django/db/migrations/serializer.py", "FunctionTypeSerializer.serialize"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=7108/1096；耗时=137.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 10, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/django__django-17087.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/django__django-17087.jsonl)

## 121. matplotlib__matplotlib-18869

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> Add easily comparable version info to toplevel
> <!--
> Welcome! Thanks for thinking of a way to improve Matplotlib.
> 
> 
> Before creating a new feature request please search the issues for relevant feature requests.
> -->
> 
> ### Problem
> 
> Currently matplotlib only exposes `__version__`.  For quick version checks, exposing either a `version_info` tuple (which can be compared with other tuples) or a `LooseVersion` instance (which can be properly compared with other strings) would be a small usability improvement.
> 
> (In practice I guess boring string comparisons will work just fine until we hit mpl 3.10 or 4.10 which is unlikely to happen soon, but that feels quite dirty :))
> <!--
> Provide a clear and concise description of the problem this feature will solve. 
> 
> For example:
> * I'm always fru

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/__init__.py", "__getattr__"], ["lib/matplotlib/__init__.py", "_get_version"], ["lib/matplotlib/__init__.py", "_parse_to_version_info"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=26268/3662；耗时=345.0秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["lib/matplotlib/__init__.py", "__getattr__"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 35}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/__init__.py", "__init__.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-18869.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-18869.jsonl)

## 122. matplotlib__matplotlib-22711

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: cannot give init value for RangeSlider widget
> ### Bug summary
> 
> I think `xy[4] = .25, val[0]` should be commented in /matplotlib/widgets. py", line 915, in set_val
> as it prevents to initialized value for RangeSlider
> 
> ### Code for reproduction
> 
> ```python
> import numpy as np
> import matplotlib.pyplot as plt
> from matplotlib.widgets import RangeSlider
> 
> # generate a fake image
> np.random.seed(19680801)
> N = 128
> img = np.random.randn(N, N)
> 
> fig, axs = plt.subplots(1, 2, figsize=(10, 5))
> fig.subplots_adjust(bottom=0.25)
> 
> im = axs[0].imshow(img)
> axs[1].hist(img.flatten(), bins='auto')
> axs[1].set_title('Histogram of pixel intensities')
> 
> # Create the RangeSlider
> slider_ax = fig.add_axes([0.20, 0.1, 0.60, 0.03])
> slider = RangeSlider(slider_ax, "Threshold", img.min(), img.m

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 33.33% | 25.00% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/widgets.py", "RangeSlider._update"], ["lib/matplotlib/widgets.py", "RangeSlider._update_val_from_pos"], ["lib/matplotlib/widgets.py", "RangeSlider.set_val"]]`

新预测：`[]`

搜索种子 6；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=39238/4095；耗时=357.5秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["lib/matplotlib/widgets.py", "RangeSlider.set_val"]], "seeds": [["lib/matplotlib/widgets.py", "RangeSlider.set_val"]], "causal_received": [["lib/matplotlib/widgets.py", "RangeSlider.set_val"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 36, "causal": 9}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/testing/widgets.py", "widgets.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["lib/matplotlib/widgets.py", "widgets.py"]]`
- C：Dependency on Product；依据：；关联：`[["lib/matplotlib/widgets.py", "widgets.py"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-22711.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-22711.jsonl)

## 123. matplotlib__matplotlib-22835

项目：matplotlib/matplotlib；本轮子集：开发集；状态：complete。

问题描述节选：

> [Bug]: scalar mappable format_cursor_data crashes on BoundarNorm
> ### Bug summary
> 
> In 3.5.0 if you do:
> 
> ```python
> import matplotlib.pyplot as plt
> import numpy as np
> import matplotlib as mpl
> 
> fig, ax = plt.subplots()
> norm = mpl.colors.BoundaryNorm(np.linspace(-4, 4, 5), 256)
> X = np.random.randn(10, 10)
> pc = ax.imshow(X, cmap='RdBu_r', norm=norm)
> ```
> 
> and mouse over the image, it crashes with
> 
> ```
> File "/Users/jklymak/matplotlib/lib/matplotlib/artist.py", line 1282, in format_cursor_data
>     neighbors = self.norm.inverse(
>   File "/Users/jklymak/matplotlib/lib/matplotlib/colors.py", line 1829, in inverse
>     raise ValueError("BoundaryNorm is not invertible")
> ValueError: BoundaryNorm is not invertible
> ```
> 
> and interaction stops.  
> 
> Not sure if we should have a special

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["lib/matplotlib/artist.py", "Artist.format_cursor_data"]]`

新预测：`[["lib/matplotlib/artist.py", "Artist.format_cursor_data"], ["lib/matplotlib/colors.py", "BoundaryNorm.inverse"]]`

搜索种子 4；搜索停止=search_round_limit；因果停止=legacy_causal_stop；输入/输出token=23975/4338；耗时=535.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["lib/matplotlib/artist.py", "Artist.format_cursor_data"]], "seeds": [["lib/matplotlib/artist.py", "Artist.format_cursor_data"]], "causal_received": [["lib/matplotlib/artist.py", "Artist.format_cursor_data"]], "final": [["lib/matplotlib/artist.py", "Artist.format_cursor_data"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 18, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.format_cursor_data"]]`
- D：Uninvertible BoundaryNorm；依据：；关联：`[["", "self.norm"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["lib/matplotlib/colors.py", "BoundaryNorm.inverse"]]`
- C：Dependency on Product；依据：；关联：`[["lib/matplotlib/colors.py", "BoundaryNorm.inverse"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-22835.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-22835.jsonl)

## 124. matplotlib__matplotlib-23299

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: get_backend() clears figures from Gcf.figs if they were created under rc_context
> ### Bug summary
> 
> calling `matplotlib.get_backend()` removes all figures from `Gcf` if the *first* figure in `Gcf.figs` was created in an `rc_context`.
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> from matplotlib import get_backend, rc_context
> 
> # fig1 = plt.figure()  # <- UNCOMMENT THIS LINE AND IT WILL WORK
> # plt.ion()            # <- ALTERNATIVELY, UNCOMMENT THIS LINE AND IT WILL ALSO WORK
> with rc_context():
>     fig2 = plt.figure()
> before = f'{id(plt._pylab_helpers.Gcf)} {plt._pylab_helpers.Gcf.figs!r}'
> get_backend()
> after = f'{id(plt._pylab_helpers.Gcf)} {plt._pylab_helpers.Gcf.figs!r}'
> 
> assert before == after, '\n' + before + '\n' + after
> ```
> 
> 
> ### Actua

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/__init__.py", "rc_context"]]`

新预测：`[["lib/matplotlib/__init__.py", "get_backend"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=7813/1093；耗时=120.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 2}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/__init__.py", "get_backend"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23299.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23299.jsonl)

## 125. matplotlib__matplotlib-23314

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: set_visible() not working for 3d projection 
> ### Bug summary
> 
> in the subplot projection="3d" the set_visible function doesn't work even if the value is set to False
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> from matplotlib.gridspec import GridSpec
> 
> fig, (ax1, ax2) = plt.subplots(1, 2, subplot_kw={'projection': '3d'})
> ax1.scatter(1,1,1)
> ax2.scatter(1,1,1, c='r')
> ax1.set_visible(False)
> 
> plt.show()
> # Thanks Tim for your help! 
> ```
> 
> 
> ### Actual outcome
> 
> the subplot remains visible which should not happen if the value is set to False
> 
> ### Expected outcome
> 
> the subplot is not visible if the value is set to False
> 
> ### Additional information
> 
> _No response_
> 
> ### Operating system
> 
> _No response_
> 
> ### Matplotlib Version
> 
> 3.4.2
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/mpl_toolkits/mplot3d/axes3d.py", "Axes3D.draw"]]`

新预测：`[["lib/matplotlib/artist.py", "<unresolved>:Artist.axes"], ["lib/matplotlib/artist.py", "<unresolved>:Artist.matchfunc"], ["lib/matplotlib/artist.py", "<unresolved>:Artist.stale"], ["lib/matplotlib/artist.py", "Artist.__getstate__"], ["lib/matplotlib/artist.py", "Artist.__init__"], ["lib/matplotlib/artist.py", "Artist.__init_subclass__"], ["lib/matplotlib/artist.py", "Artist._cm_set"], ["lib/matplotlib/artist.py", "Artist._default_contains"], ["lib/matplotlib/artist.py", "Artist._fully_clipped_to_axes"], ["lib/matplotlib/artist.py", "Artist._internal_update"], ["lib/matplotlib/artist.py", "Artist._set_alpha_for_array"], ["lib/matplotlib/artist.py", "Artist._set_gc_clip"], ["lib/matplotlib/artist.py", "Artist._update_props"], ["lib/matplotlib/artist.py", "Artist._update_set_signature_and_docstring"], ["lib/matplotlib/artist.py", "Artist.add_callback"], ["lib/matplotlib/artist.py", "Artist.contains"], ["lib/matplotlib/artist.py", "Artist.convert_xunits"], ["lib/matplotlib/artist.py", "Artist.convert_yunits"], ["lib/matplotlib/artist.py", "Artist.draw"], ["lib/matplotlib/artist.py", "Artist.findobj"], ["lib/matplotlib/artist.py", "Artist.format_cursor_data"], ["lib/matplotlib/artist.py", "Artist.get_agg_filter"], ["lib/matplotlib/artist.py", "Artist.get_alpha"], ["lib/matplotlib/artist.py", "Artist.get_animated"], ["lib/matplotlib/artist.py", "Artist.get_children"], ["lib/matplotlib/artist.py", "Artist.get_clip_box"], ["lib/matplotlib/artist.py", "Artist.get_clip_on"], ["lib/matplotlib/artist.py", "Artist.get_clip_path"], ["lib/matplotlib/artist.py", "Artist.get_cursor_data"], ["lib/matplotlib/artist.py", "Artist.get_figure"], ["lib/matplotlib/artist.py", "Artist.get_gid"], ["lib/matplotlib/artist.py", "Artist.get_in_layout"], ["lib/matplotlib/artist.py", "Artist.get_label"], ["lib/matplotlib/artist.py", "Artist.get_mouseover"], ["lib/matplotlib/artist.py", "Artist.get_path_effects"], ["lib/matplotlib/artist.py", "Artist.get_picker"], ["lib/matplotlib/artist.py", "Artist.get_rasterized"], ["lib/matplotlib/artist.py", "Artist.get_sketch_params"], ["lib/matplotlib/artist.py", "Artist.get_snap"], ["lib/matplotlib/artist.py", "Artist.get_tightbbox"], ["lib/matplotlib/artist.py", "Artist.get_transform"], ["lib/matplotlib/artist.py", "Artist.get_transformed_clip_path_and_affine"], ["lib/matplotlib/artist.py", "Artist.get_url"], ["lib/matplotlib/artist.py", "Artist.get_visible"], ["lib/matplotlib/artist.py", "Artist.get_window_extent"], ["lib/matplotlib/artist.py", "Artist.get_zorder"], ["lib/matplotlib/artist.py", "Artist.have_units"], ["lib/matplotlib/artist.py", "Artist.is_transform_set"], ["lib/matplotlib/artist.py", "Artist.pchanged"], ["lib/matplotlib/artist.py", "Artist.pick"], ["lib/matplotlib/artist.py", "Artist.pickable"], ["lib/matplotlib/artist.py", "Artist.properties"], ["lib/matplotlib/artist.py", "Artist.remove"], ["lib/matplotlib/artist.py", "Artist.remove_callback"], ["lib/matplotlib/artist.py", "Artist.set"], ["lib/matplotlib/artist.py", "Artist.set_agg_filter"], ["lib/matplotlib/artist.py", "Artist.set_alpha"], ["lib/matplotlib/artist.py", "Artist.set_animated"], ["lib/matplotlib/artist.py", "Artist.set_clip_box"], ["lib/matplotlib/artist.py", "Artist.set_clip_on"], ["lib/matplotlib/artist.py", "Artist.set_clip_path"], ["lib/matplotlib/artist.py", "Artist.set_figure"], ["lib/matplotlib/artist.py", "Artist.set_gid"], ["lib/matplotlib/artist.py", "Artist.set_in_layout"], ["lib/matplotlib/artist.py", "Artist.set_label"], ["lib/matplotlib/artist.py", "Artist.set_mouseover"], ["lib/matplotlib/artist.py", "Artist.set_path_effects"], ["lib/matplotlib/artist.py", "Artist.set_picker"], ["lib/matplotlib/artist.py", "Artist.set_rasterized"], ["lib/matplotlib/artist.py", "Artist.set_sketch_params"], ["lib/matplotlib/artist.py", "Artist.set_snap"], ["lib/matplotlib/artist.py", "Artist.set_url"], ["lib/matplotlib/artist.py", "Artist.set_visible"], ["lib/matplotlib/artist.py", "Artist.set_zorder"], ["lib/matplotlib/artist.py", "Artist.sticky_edges"], ["lib/matplotlib/artist.py", "Artist.update_from"], ["lib/matplotlib/artist.py", "setp"], ["lib/matplotlib/figure.py", "FigureBase.autofmt_xdate"], ["lib/mpl_toolkits/axes_grid1/axes_rgb.py", "make_rgb_axes"], ["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.set_visible"], ["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.toggle"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=376213/60053；耗时=5890.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 125}`。

无法唯一映射的函数：`[{"file": "lib/matplotlib/artist.py", "name": "Artist.axes", "reason": "absent"}, {"file": "lib/matplotlib/artist.py", "name": "Artist.stale", "reason": "absent"}, {"file": "lib/matplotlib/artist.py", "name": "Artist.matchfunc", "reason": "absent"}]`

- A1：Incorrect computation；依据：；关联：`[["lib/matplotlib/artist.py", "Artist"]]`
- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_visible"]]`
- A2：Wrong logic；依据：；关联：`[["lib/matplotlib/figure.py", "FigureBase.autofmt_xdate"]]`
- F145：Self Visibility Control；依据：；关联：`[["", "self._visible"]]`
- E：Visibility settings not respected；依据：；关联：`[["lib/matplotlib/artist.py", "Artist"], ["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.set_visible"]]`
- D：Toggle method overriding visibility；依据：；关联：`[["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.set_visible"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- F1：set_transform；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._update_props"]]`
- F2：self._visible；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_picker"]]`
- F3：update；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.draw"]]`
- F4：self._gid；依据：；关联：`[["lib/matplotlib/transforms.py", "TransformedPatchPath"]]`
- F5：self._rasterized；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_snap"]]`
- F6：self._url；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_window_extent"]]`
- F7：set_picker；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.convert_xunits"]]`
- F8：draw；依据：；关联：`[["", "self._path_effects"]]`
- F9：TransformedPatchPath；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.pickable"]]`
- F10：set_snap；依据：；关联：`[["", "self._stale"]]`
- F11：get_window_extent；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.findobj"]]`
- F12：convert_xunits；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.__init__"]]`
- F13：set_path_effects；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.axes"]]`
- F14：get_sketch_params；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.update_from"]]`
- F15：set_sketch_params；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_children"]]`
- F16：set_url；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_animated"]]`
- F17：set_figure；依据：；关联：`[["lib/matplotlib/legend.py", "Legend"]]`
- F18：add_callback；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set"]]`
- F19：get_alpha；依据：；关联：`[["", "self._alpha"]]`
- F20：get_rasterized；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_rasterized"]]`
- F21：get_clip_on；依据：；关联：`[["lib/matplotlib/artist.py", "artist.py"]]`
- F22：get_label；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_clip_on"]]`
- F23：get_stale；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_label"]]`
- F24：get_clip_box；依据：；关联：`[["", "self.stale"]]`
- F25：get_clip_path；依据：；关联：`[["", "self.norm"]]`
- F26：get_path_effects；依据：；关联：`[["lib/matplotlib/artist.py", "ArtistInspector"]]`
- F27：_fully_clipped_to_axes；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._update_set_signature_and_docstring"]]`
- F28：get_snap；依据：；关联：`[["", "self._label"]]`
- F29：get_transformed_clip_path_and_affine；依据：；关联：`[["", "self.figure"]]`
- F30：get_transform；依据：；关联：`[["lib/matplotlib/transforms.py", "TransformedPath"]]`
- F31：properties；依据：；关联：`[["", "self.stale_callback"]]`
- F32：get_in_layout；依据：；关联：`[["", "self.__dict__"]]`
- F33：stale；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_zorder"]]`
- F34：get_remove_method；依据：；关联：`[["", "self._picker"]]`
- F35：get_sticky_edges；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.sticky_edges"]]`
- F36：format_cursor_data；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._default_contains"]]`
- F37：get_sketch_params；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.__init_subclass__"]]`
- F38：set_sketch_params；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_in_layout"]]`
- F39：pchanged；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_picker"]]`
- F40：have_units；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.have_units"]]`
- F41：set_agg_filter；依据：；关联：`[["", "self._snap"]]`
- F42：get_agg_filter；依据：；关联：`[["", "self._agg_filter"]]`
- F43：remove；依据：；关联：`[["", "self.draw,"]]`
- F44：get_visible；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_sketch_params"]]`
- F45：set_animated；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.pchanged"]]`
- F46：get_animated；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_figure"]]`
- F47：set_path_effects；依据：；关联：`[["", "self._clippath"]]`
- F48：get_path_effects；依据：；关联：`[["", "self._transform"]]`
- F49：_set_alpha_for_array；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_agg_filter"]]`
- F50：set_clip_box；依据：；关联：`[["lib/matplotlib/lines.py", "Line2D"]]`
- F51：get_clip_box；依据：；关联：`[["", "self._transform,"]]`
- F52：set_clip_path；依据：；关联：`[["", "self._sketch"]]`
- F53：get_clip_path；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.remove_callback"]]`
- F54：set_clip_on；依据：；关联：`[["", "self.sticky_edges"]]`
- F55：get_clip_on；依据：；关联：`[["", "self._in_layout"]]`
- F56：set_mouseover；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.is_transform_set"]]`
- F57：get_mouseover；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_mouseover"]]`
- F58：set_label；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_label"]]`
- F59：get_label；依据：；关联：`[["lib/matplotlib/artist.py", "_XYPair"]]`
- F60：set_picker；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._cm_set"]]`
- F61：get_picker；依据：；关联：`[["", "self._sticky_edges"]]`
- F62：set_rasterized；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_alpha"]]`
- F63：get_rasterized；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_url"]]`
- F64：set_tight_bbox；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_tightbbox"]]`
- F65：set_clip_box；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_clip_box"]]`
- F66：get_clip_box；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.__getstate__"]]`
- F67：set_clip_path；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_clip_path"]]`
- F68：get_clip_path；依据：；关联：`[["", "self.cmap"]]`
- F69：set_clip_on；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_figure"]]`
- F70：get_clip_on；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.add_callback"]]`
- F71：set_mouseover；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.contains"]]`
- F72：get_mouseover；依据：；关联：`[["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist"]]`
- F73：set_label；依据：；关联：`[["", "self.zorder"]]`
- F74：get_label；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.pick"]]`
- F75：set_picker；依据：；关联：`[["", "self.clipbox"]]`
- F76：get_picker；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_zorder"]]`
- F77：set_rasterized；依据：；关联：`[["", "self._axes"]]`
- F78：get_rasterized；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._set_alpha_for_array"]]`
- F79：set_path_effects；依据：；关联：`[["", "self._animated"]]`
- F80：get_path_effects；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_animated"]]`
- F81：_fully_clipped_to_axes；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_path_effects"]]`
- F82：get_snap；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_sketch_params"]]`
- F83：get_transformed_clip_path_and_affine；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_url"]]`
- F84：get_transform；依据：；关联：`[["", "self._clipon"]]`
- F85：properties；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.format_cursor_data"]]`
- F86：get_in_layout；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.convert_yunits"]]`
- F87：stale；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_clip_path"]]`
- F88：get_remove_method；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._set_gc_clip"]]`
- F89：get_sticky_edges；依据：；关联：`[["lib/matplotlib/artist.py", "setp"]]`
- F90：format_cursor_data；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_clip_box"]]`
- F91：get_sketch_params；依据：；关联：`[["lib/matplotlib/table.py", "Table"]]`
- F92：set_sketch_params；依据：；关联：`[["", "self.__class__"]]`
- F93：pchanged；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.stale"]]`
- F94：have_units；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.remove"]]`
- F95：set_agg_filter；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_visible"]]`
- F96：get_agg_filter；依据：；关联：`[["lib/matplotlib/figure.py", "FigureBase"]]`
- F97：remove；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.matchfunc"]]`
- F98：get_visible；依据：；关联：`[["lib/matplotlib/transforms.py", "TransformedBbox"]]`
- F99：set_animated；依据：；关联：`[["", "self._mouseover"]]`
- F100：get_animated；依据：；关联：`[["lib/matplotlib/text.py", "Text"]]`
- F101：set_path_effects；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.axes"]]`
- F102：get_path_effects；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_rasterized"]]`
- F103：_set_alpha_for_array；依据：；关联：`[["lib/matplotlib/transforms.py", "Bbox"]]`
- F104：set_clip_box；依据：；关联：`[["", "self._remove_method"]]`
- F105：get_clip_box；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_agg_filter"]]`
- F106：set_clip_path；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_gid"]]`
- F107：get_clip_path；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_gid"]]`
- F108：set_clip_on；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._internal_update"]]`
- F109：get_clip_on；依据：；关联：`[["lib/matplotlib/transforms.py", "IdentityTransform"]]`
- F110：set_mouseover；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_clip_on"]]`
- F111：get_mouseover；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_cursor_data"]]`
- F112：set_label；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_path_effects"]]`
- F113：get_label；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._fully_clipped_to_axes"]]`
- F114：set_picker；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_snap"]]`
- F115：get_picker；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_transformed_clip_path_and_affine"]]`
- F116：set_rasterized；依据：；关联：`[["", "self.axes"]]`
- F117：get_rasterized；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.matchfunc"]]`
- F118：set_tight_bbox；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.set_alpha"]]`
- F119：set_clip_box；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_transform"]]`
- F120：get_clip_box；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.properties"]]`
- F121：set_clip_path；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_in_layout"]]`
- F122：get_clip_path；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.stale"]]`
- F123：set_clip_on；依据：；关联：`[["", "self._transformSet"]]`
- F124：get_clip_on；依据：；关联：`[["", "self._callbacks"]]`
- F125：set_mouseover；依据：；关联：`[["lib/matplotlib/artist.py", "Artist.get_mouseover"]]`
- F126：get_mouseover；依据：；关联：`[["examples/misc/demo_agg_filter.py", "FilteredArtistList"]]`
- F127：set_label；依据：；关联：`[["lib/mpl_toolkits/axes_grid1/axes_rgb.py", "make_rgb_axes"]]`
- F128：get_label；依据：；关联：`[["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.toggle"]]`
- F129：set_picker；依据：；关联：`[]`
- F130：get_picker；依据：；关联：`[]`
- F131：set_rasterized；依据：；关联：`[]`
- F132：get_rasterized；依据：；关联：`[]`
- F133：set_tight_bbox；依据：；关联：`[]`
- F134：set_clip_box；依据：；关联：`[]`
- F135：get_clip_box；依据：；关联：`[]`
- F136：set_clip_path；依据：；关联：`[]`
- F137：get_clip_path；依据：；关联：`[]`
- F138：set_clip_on；依据：；关联：`[]`
- F139：get_clip_on；依据：；关联：`[]`
- F140：set_mouseover；依据：；关联：`[]`
- F141：get_mouseover；依据：；关联：`[]`
- F142：set_label；依据：；关联：`[]`
- F143：get_label；依据：；关联：`[]`
- F144：set_picker；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23314.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23314.jsonl)

## 126. matplotlib__matplotlib-23476

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: DPI of a figure is doubled after unpickling on M1 Mac
> ### Bug summary
> 
> When a figure is unpickled, it's dpi is doubled. This behaviour happens every time and if done in a loop it can cause an `OverflowError`.
> 
> ### Code for reproduction
> 
> ```python
> import numpy as np
> import matplotlib
> import matplotlib.pyplot as plt
> import pickle
> import platform
> 
> print(matplotlib.get_backend())
> print('Matplotlib ver:', matplotlib.__version__)
> print('Platform:', platform.platform())
> print('System:', platform.system())
> print('Release:', platform.release())
> print('Python ver:', platform.python_version())
> 
> 
> def dump_load_get_dpi(fig):
>     with open('sinus.pickle','wb') as file:
>         pickle.dump(fig, file)
> 
>     with open('sinus.pickle', 'rb') as blob:
>         fig2 = pickle.load

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/figure.py", "Figure.__getstate__"]]`

新预测：`[["lib/matplotlib/backend_bases.py", "FigureCanvasBase.new_manager"], ["lib/matplotlib/figure.py", "Figure.__setstate__"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=34848/5587；耗时=451.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 8, "causal": 6}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/backend_bases.py", "FigureCanvasBase.new_manager"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["lib/matplotlib/figure.py", "Figure.__setstate__"]]`
- C：Dependency on Product；依据：；关联：`[["lib/matplotlib/figure.py", "Figure.__setstate__"]]`
- D：FigureCanvasBase Class；依据：；关联：`[]`
- E：draw_if_interactive Function；依据：；关联：`[]`
- F：get_fignums Function；依据：；关联：`[]`
- G：Figure Class；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23476.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23476.jsonl)

## 127. matplotlib__matplotlib-23562

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> 'Poly3DCollection' object has no attribute '_facecolors2d'
> The following minimal example demonstrates the issue:
> 
> ```
> import numpy as np
> import matplotlib.tri as mtri
> import matplotlib.pyplot as plt
> from mpl_toolkits.mplot3d import Axes3D
> 
> y,x = np.ogrid[1:10:100j, 1:10:100j]
> z2 = np.cos(x)**3 - np.sin(y)**2
> fig = plt.figure()
> ax = fig.add_subplot(111, projection='3d')
> r = ax.plot_surface(x,y,z2, cmap='hot')
> r.get_facecolors()
> ```
> 
> It fails on the last line with the following traceback:
> 
> ```
> AttributeError                            Traceback (most recent call last)
> <ipython-input-13-de0f41d662cd> in <module>()
> ----> 1 r.get_facecolors()
> 
> /home/oliver/.virtualenvs/mpl/local/lib/python2.7/site-packages/mpl_toolkits/mplot3d/art3d.pyc in get_facecolors(self)
>     634
>     635     def get_faceco

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/mpl_toolkits/mplot3d/art3d.py", "Poly3DCollection.get_edgecolor"], ["lib/mpl_toolkits/mplot3d/art3d.py", "Poly3DCollection.get_facecolor"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=5924/2098；耗时=179.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23562.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23562.jsonl)

## 128. matplotlib__matplotlib-23563

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: 'Line3D' object has no attribute '_verts3d'
> ### Bug summary
> 
> I use matplotlib 3D to visualize some lines in 3D. When I first run the following code, the code can run right. But, if I give `x_s_0[n]` a numpy array, it will report the error 'input operand has more dimensions than allowed by the axis remapping'. The point is when next I give  `x_s_0[n]` and other variables an int number, the AttributeError: 'Line3D' object has no attribute '_verts3d' will appear and can not be fixed whatever I change the variables or delete them. The error can be only fixed when I restart the kernel of ipython console. I don't know why it happens, so I come here for help.
> 
> ### Code for reproduction
> 
> ```python
> x_s_0 = np.array(['my int number list'])
> x_e_0 = np.array(['my int number list'])
> y_s_0 = np

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/mpl_toolkits/mplot3d/art3d.py", "Line3D.set_3d_properties"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=13034/1954；耗时=165.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 4, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23563.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23563.jsonl)

## 129. matplotlib__matplotlib-23913

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> legend draggable as keyword
> <!--To help us understand and resolve your issue, please fill out the form to the best of your ability.-->
> <!--You can feel free to delete the sections that do not apply.-->
> 
> ### Feature request
> 
> **There is not keyword to make legend draggable at creation**
> 
> <!--A short 1-2 sentences that succinctly describes the bug-->
> 
> Is there a code reason why one can not add a "draggable=True" keyword to the __init__ function for Legend?  This would be more handy than having to call it after legend creation.  And, naively, it would seem simple to do.  But maybe there is a reason why it would not work?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/legend.py", "Legend.__init__"]]`

新预测：`[["examples/event_handling/cursor_demo.py", "Cursor.__init__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=13160/3346；耗时=300.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 7}`。

- A：Inaccurate recursive check；依据：；关联：`[["examples/event_handling/cursor_demo.py", "Cursor.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23913.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23913.jsonl)

## 130. matplotlib__matplotlib-23964

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: Text label with empty line causes a "TypeError: cannot unpack non-iterable NoneType object" in PostScript backend
> ### Bug summary
> 
> When saving a figure with the PostScript backend, a
> > TypeError: cannot unpack non-iterable NoneType object
> 
> happens if the figure contains a multi-line text label with an empty line (see example).
> 
> ### Code for reproduction
> 
> ```python
> from matplotlib.figure import Figure
> 
> figure = Figure()
> ax = figure.add_subplot(111)
> # ax.set_title('\nLower title')  # this would cause an error as well
> ax.annotate(text='\nLower label', xy=(0, 0))
> figure.savefig('figure.eps')
> ```
> 
> 
> ### Actual outcome
> 
> $ ./venv/Scripts/python save_ps.py
> Traceback (most recent call last):
>   File "C:\temp\matplotlib_save_ps\save_ps.py", line 7, in <module>
>     figure.savefig('fi

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/backends/backend_ps.py", "RendererPS.draw_text"]]`

新预测：`[["lib/matplotlib/backends/backend_ps.py", "FigureCanvasPS._print_figure"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=54041/4720；耗时=434.8秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["lib/matplotlib/backends/backend_ps.py", "RendererPS.draw_text"]], "seeds": [["lib/matplotlib/backends/backend_ps.py", "RendererPS.draw_text"]], "causal_received": [["lib/matplotlib/backends/backend_ps.py", "RendererPS.draw_text"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 15, "causal": 20}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/backends/backend_ps.py", "backend_ps.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["lib/matplotlib/backends/backend_ps.py", "FigureCanvasPS._print_figure"]]`
- C：Dependency on Product；依据：；关联：`[["lib/matplotlib/backends/backend_ps.py", "FigureCanvasPS._print_figure"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23964.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23964.jsonl)

## 131. matplotlib__matplotlib-23987

项目：matplotlib/matplotlib；本轮子集：开发集；状态：complete。

问题描述节选：

> [Bug]: Constrained layout UserWarning even when False
> ### Bug summary
> 
> When using layout settings such as `plt.subplots_adjust` or `bbox_inches='tight`, a UserWarning is produced due to incompatibility with constrained_layout, even if constrained_layout = False. This was not the case in previous versions.
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> import numpy as np
> a = np.linspace(0,2*np.pi,100)
> b = np.sin(a)
> c = np.cos(a)
> fig,ax = plt.subplots(1,2,figsize=(8,2),constrained_layout=False)
> ax[0].plot(a,b)
> ax[1].plot(a,c)
> plt.subplots_adjust(wspace=0)
> ```
> 
> 
> ### Actual outcome
> 
> The plot works fine but the warning is generated
> 
> `/var/folders/ss/pfgdfm2x7_s4cyw2v0b_t7q80000gn/T/ipykernel_76923/4170965423.py:7: UserWarning: This figure was using 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/figure.py", "Figure.__init__"]]`

新预测：`[["examples/event_handling/cursor_demo.py", "Cursor.__init__"], ["lib/matplotlib/backends/backend_wx.py", "_FigureCanvasWxBase.__init__"], ["lib/matplotlib/pyplot.py", "subplots_adjust"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=25744/5616；耗时=499.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 32, "causal": 15}`。

- D：Incompatible backend setup；依据：；关联：`[["lib/matplotlib/backends/backend_wx.py", "_FigureCanvasWxBase.__init__"]]`
- A：Inaccurate recursive check；依据：；关联：`[["examples/event_handling/cursor_demo.py", "Cursor.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["lib/matplotlib/pyplot.py", "subplots_adjust"]]`
- C：Dependency on Product；依据：；关联：`[["lib/matplotlib/pyplot.py", "subplots_adjust"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-23987.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-23987.jsonl)

## 132. matplotlib__matplotlib-24149

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: ax.bar raises for all-nan data on matplotlib 3.6.1 
> ### Bug summary
> 
> `ax.bar` raises an exception in 3.6.1 when passed only nan data. This irrevocably breaks seaborn's histogram function (which draws and then removes a "phantom" bar to trip the color cycle).
> 
> ### Code for reproduction
> 
> ```python
> import numpy as np
> import matplotlib.pyplot as plt
> f, ax = plt.subplots()
> ax.bar([np.nan], [np.nan])
> ```
> 
> 
> ### Actual outcome
> 
> ```python-traceback
> ---------------------------------------------------------------------------
> StopIteration                             Traceback (most recent call last)
> Cell In [1], line 4
>       2 import matplotlib.pyplot as plt
>       3 f, ax = plt.subplots()
> ----> 4 ax.bar([np.nan], [np.nan])[0].get_x()
> 
> File ~/miniconda/envs/py310/lib/python3.10/site-

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/axes/_axes.py", "Axes._convert_dx"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11849/1758；耗时=179.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 11, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-24149.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-24149.jsonl)

## 133. matplotlib__matplotlib-24265

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: Setting matplotlib.pyplot.style.library['seaborn-colorblind'] result in key error on matplotlib v3.6.1
> ### Bug summary
> 
> I have code that executes:
> ```
> import matplotlib.pyplot as plt
> the_rc = plt.style.library["seaborn-colorblind"]
> ```
> 
> Using version 3.4.3 of matplotlib, this works fine. I recently installed my code on a machine with matplotlib version 3.6.1 and upon importing my code, this generated a key error for line `the_rc = plt.style.library["seaborn-colorblind"]` saying "seaborn-colorblind" was a bad key.
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> the_rc = plt.style.library["seaborn-colorblind"]
> ```
> 
> 
> ### Actual outcome
> 
> Traceback (most recent call last):
> KeyError: 'seaborn-colorblind'
> 
> ### Expected outcome
> 
> seaborn-colorblind should be set

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/style/core.py", "_StyleLibrary.__getitem__"], ["lib/matplotlib/style/core.py", "reload_library"], ["lib/matplotlib/style/core.py", "use.fix_style"]]`

新预测：`[["lib/matplotlib/__init__.py", "RcParams.__getitem__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=12294/2436；耗时=206.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 20, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/__init__.py", "RcParams.__getitem__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-24265.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-24265.jsonl)

## 134. matplotlib__matplotlib-24334

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [ENH]: Axes.set_xticks/Axis.set_ticks only validates kwargs if ticklabels are set, but they should
> ### Problem
> 
> Per the doc of `Axis.set_ticks`:
> ```
>         **kwargs
>             `.Text` properties for the labels. These take effect only if you
>             pass *labels*. In other cases, please use `~.Axes.tick_params`.
> ```
> This means that in e.g. `ax.set_xticks([0, 1], xticklabels=["a", "b"])`, the incorrect `xticklabels` silently do nothing; they are not even validated (because `labels` has not been passed).
> 
> ### Proposed solution
> 
> We should at least check that `kwargs` are valid Text properties in all cases; we could even consider making any kwargs an error if `labels` is not set.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/axis.py", "Axis.set_ticks"]]`

新预测：`[["lib/matplotlib/artist.py", "Artist._internal_update"], ["lib/matplotlib/lines.py", "Line2D.__init__"], ["lib/matplotlib/pyplot.py", "xticks"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=57101/8009；耗时=725.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 122}`。

- A1：Incorrect computation；依据：；关联：`[["lib/matplotlib/lines.py", "Line2D.__init__"]]`
- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/pyplot.py", "xticks"]]`
- A2：Wrong logic；依据：；关联：`[["lib/matplotlib/artist.py", "Artist"]]`
- D：_internal_update；依据：；关联：`[["lib/matplotlib/artist.py", "Artist._internal_update"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-24334.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-24334.jsonl)

## 135. matplotlib__matplotlib-24970

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: NumPy 1.24 deprecation warnings
> ### Bug summary
> 
> Starting NumPy 1.24 I observe several deprecation warnings.
> 
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> import numpy as np
> 
> plt.get_cmap()(np.empty((0, ), dtype=np.uint8))
> ```
> 
> 
> ### Actual outcome
> 
> ```
> /usr/lib/python3.10/site-packages/matplotlib/colors.py:730: DeprecationWarning: NumPy will stop allowing conversion of out-of-bound Python integers to integer arrays.  The conversion of 257 to uint8 will fail in the future.
> For the old behavior, usually:
>     np.array(value).astype(dtype)`
> will give the desired result (the cast overflows).
>   xa[xa > self.N - 1] = self._i_over
> /usr/lib/python3.10/site-packages/matplotlib/colors.py:731: DeprecationWarning: NumPy will stop allowing conversio

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/colors.py", "Colormap.__call__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11439/2020；耗时=183.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 20, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-24970.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-24970.jsonl)

## 136. matplotlib__matplotlib-25079

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: Setting norm with existing colorbar fails with 3.6.3
> ### Bug summary
> 
> Setting the norm to a `LogNorm` after the colorbar has been created (e.g. in interactive code) fails with an `Invalid vmin` value in matplotlib 3.6.3.
> 
> The same code worked in previous matplotlib versions.
> 
> Not that vmin and vmax are explicitly set to values valid for `LogNorm` and no negative values (or values == 0) exist in the input data.
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> from matplotlib.colors import LogNorm
> import numpy as np
> 
> # create some random data to fill a 2d plot
> rng = np.random.default_rng(0)
> img = rng.uniform(1, 5, (25, 25))
> 
> # plot it
> fig, ax = plt.subplots(layout="constrained")
> plot = ax.pcolormesh(img)
> cbar = fig.colorbar(plot, ax=ax)
> 
> vm

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/colors.py", "Normalize.autoscale"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=27931/4796；耗时=475.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Interaction between colorbar and norm；依据：；关联：`[]`
- E：Colorbar creation before norm update；依据：；关联：`[]`
- F：Norm update without proper validation；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-25079.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-25079.jsonl)

## 137. matplotlib__matplotlib-25311

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: Unable to pickle figure with draggable legend
> ### Bug summary
> 
> I am unable to pickle figure with draggable legend. Same error comes for draggable annotations.
> 
> 
> 
> 
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> import pickle
> 
> fig = plt.figure()
> ax = fig.add_subplot(111)
> 
> time=[0,1,2,3,4]
> speed=[40,43,45,47,48]
> 
> ax.plot(time,speed,label="speed")
> 
> leg=ax.legend()
> leg.set_draggable(True) #pickling works after removing this line 
> 
> pickle.dumps(fig)
> plt.show()
> ```
> 
> 
> ### Actual outcome
> 
> `TypeError: cannot pickle 'FigureCanvasQTAgg' object`
> 
> ### Expected outcome
> 
> Pickling successful
> 
> ### Additional information
> 
> _No response_
> 
> ### Operating system
> 
> Windows 10
> 
> ### Matplotlib Version
> 
> 3.7.0
> 
> ### Matplotlib Backend
> 
> _No

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/offsetbox.py", "DraggableBase.__init__"]]`

新预测：`[["lib/matplotlib/cbook.py", "CallbackRegistry.__getstate__"], ["lib/matplotlib/figure.py", "Figure.__getstate__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=12686/3449；耗时=367.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 16, "causal": 6}`。

- D：__getstate__ function in cbook.py；依据：；关联：`[["lib/matplotlib/cbook.py", "CallbackRegistry.__getstate__"]]`
- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/figure.py", "Figure.__getstate__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-25311.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-25311.jsonl)

## 138. matplotlib__matplotlib-25332

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: Unable to pickle figure with aligned labels
> ### Bug summary
> 
>  Unable to pickle figure after calling `align_labels()`
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as plt
> import pickle
> 
> fig = plt.figure()
> ax1 = fig.add_subplot(211)
> ax2 = fig.add_subplot(212)
> time=[0,1,2,3,4]
> speed=[40000,4300,4500,4700,4800]
> acc=[10,11,12,13,14]
> ax1.plot(time,speed)
> ax1.set_ylabel('speed')
> ax2.plot(time,acc)
> ax2.set_ylabel('acc')
> 
> fig.align_labels() ##pickling works after removing this line 
> 
> pickle.dumps(fig)
> plt.show()
> ```
> 
> 
> ### Actual outcome
> ```
> align.py", line 16
> pickle.dumps(fig)
> TypeError: cannot pickle 'weakref.ReferenceType' object
> ```
> ### Expected outcome
> 
> Pickling successful
> 
> ### Additional information
> 
> _No response_
> 
> ### Operating

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/cbook.py", "CallbackRegistry.__getstate__"], ["lib/matplotlib/cbook.py", "CallbackRegistry.__setstate__"]]`

新预测：`[["lib/matplotlib/figure.py", "FigureBase.align_labels"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=8257/2115；耗时=195.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/figure.py", "FigureBase.align_labels"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-25332.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-25332.jsonl)

## 139. matplotlib__matplotlib-25433

项目：matplotlib/matplotlib；本轮子集：验证集；状态：failed。

问题描述节选：

> [Bug]: using clf and pyplot.draw in range slider on_changed callback blocks input to widgets
> ### Bug summary
> 
> When using clear figure, adding new widgets and then redrawing the current figure in the on_changed callback of a range slider the inputs to all the widgets in the figure are blocked. When doing the same in the button callback on_clicked, everything works fine.
> 
> ### Code for reproduction
> 
> ```python
> import matplotlib.pyplot as pyplot
> import matplotlib.widgets as widgets
> 
> def onchanged(values):
>     print("on changed")
>     print(values)
>     pyplot.clf()
>     addElements()
>     pyplot.draw()
> 
> def onclick(e):
>     print("on click")
>     pyplot.clf()
>     addElements()
>     pyplot.draw()
> 
> def addElements():
>     ax = pyplot.axes([0.1, 0.45, 0.8, 0.1])
>     global slider
>     sl

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/figure.py", "FigureBase.delaxes"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=33290/4043；耗时=402.3秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 9, "relevance": 65, "causal": 18}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/matplotlib__matplotlib-25433.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-25433.jsonl)

## 140. matplotlib__matplotlib-25442

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> [Bug]: Attribute Error combining matplotlib 3.7.1 and mplcursor on data selection
> ### Bug summary
> 
> If you combine mplcursor and matplotlib 3.7.1, you'll get an `AttributeError: 'NoneType' object has no attribute 'canvas'` after clicking a few data points. Henceforth, selecting a new data point will trigger the same traceback. Otherwise, it works fine. 
> 
> ### Code for reproduction
> 
> ```python
> import numpy as np
> import matplotlib.pyplot as plt
> import mplcursors as mpl
> 
> x = np.arange(1, 11)    
> y1 = x
> 
> plt.scatter(x,y1)
> 
> mpl.cursor()
> plt.show()
> ```
> 
> 
> ### Actual outcome
> 
> ```
> Traceback (most recent call last):
>   File "C:\Users\MrAni\Python\miniconda3\lib\site-packages\matplotlib\cbook\__init__.py", line 304, in process
>     func(*args, **kwargs)
>   File "C:\Users\MrAni\Py

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 40.00% | 50.00% | 44.44% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/offsetbox.py", "DraggableBase.__init__"], ["lib/matplotlib/offsetbox.py", "DraggableBase.disconnect"], ["lib/matplotlib/offsetbox.py", "DraggableBase.on_pick"], ["lib/matplotlib/offsetbox.py", "DraggableBase.on_release"]]`

新预测：`[["galleries/examples/event_handling/cursor_demo.py", "BlittedCursor.__init__"], ["lib/matplotlib/_blocking_input.py", "blocking_input_loop"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=19968/4575；耗时=392.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 36, "causal": 5}`。

- A：Inaccurate recursive check；依据：；关联：`[["galleries/examples/event_handling/cursor_demo.py", "BlittedCursor.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["lib/matplotlib/_blocking_input.py", "blocking_input_loop"]]`
- C：Dependency on Product；依据：；关联：`[["lib/matplotlib/_blocking_input.py", "blocking_input_loop"]]`

源码送达缺口：`[["lib/matplotlib/_blocking_input.py", "blocking_input_loop"]]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-25442.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-25442.jsonl)

## 141. matplotlib__matplotlib-25498

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> Update colorbar after changing mappable.norm
> How can I update a colorbar, after I changed the norm instance of the colorbar?
> 
> `colorbar.update_normal(mappable)` has now effect and `colorbar.update_bruteforce(mappable)` throws a `ZeroDivsionError`-Exception.
> 
> Consider this example:
> 
> ``` python
> import matplotlib.pyplot as plt
> from matplotlib.colors import LogNorm
> import numpy as np
> 
> img = 10**np.random.normal(1, 1, size=(50, 50))
> 
> fig, ax = plt.subplots(1, 1)
> plot = ax.imshow(img, cmap='gray')
> cb = fig.colorbar(plot, ax=ax)
> plot.norm = LogNorm()
> cb.update_normal(plot)  # no effect
> cb.update_bruteforce(plot)  # throws ZeroDivisionError
> plt.show()
> ```
> 
> Output for `cb.update_bruteforce(plot)`:
> 
> ```
> Traceback (most recent call last):
>   File "test_norm.py", line 12, in <module>
>     cb.update_brut

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/colorbar.py", "Colorbar.__init__"], ["lib/matplotlib/colorbar.py", "Colorbar._process_values"]]`

新预测：`[["lib/matplotlib/colorbar.py", "Colorbar.update_normal"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=11751/2849；耗时=274.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 7}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/colorbar.py", "Colorbar.update_normal"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-25498.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-25498.jsonl)

## 142. matplotlib__matplotlib-26011

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> xlim_changed not emitted on shared axis
> <!--To help us understand and resolve your issue, please fill out the form to the best of your ability.-->
> <!--You can feel free to delete the sections that do not apply.-->
> 
> ### Bug report
> 
> **Bug summary**
> 
> When an axis is shared with another its registered "xlim_changed" callbacks does not get called when the change is induced by a shared axis (via sharex=). 
> 
> In _base.py the set_xlim for sibling axis are called with emit=False:
> 
> ```
> matplotlib/lib/matplotlib/axes/_base.py:
> 
> /.../
> def set_xlim(...)
> /.../
>         if emit:
>             self.callbacks.process('xlim_changed', self)
>             # Call all of the other x-axes that are shared with this one
>             for other in self._shared_x_axes.get_siblings(self):
>                

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["lib/matplotlib/axis.py", "Axis._set_lim"]]`

新预测：`[["lib/matplotlib/axes/_base.py", "_AxesBase.drag_pan"], ["lib/matplotlib/axes/_base.py", "_AxesBase.set_xbound"], ["lib/matplotlib/axes/_base.py", "_AxesBase.set_xlim"], ["lib/matplotlib/axes/_base.py", "_AxesBase.sharex"], ["lib/matplotlib/pyplot.py", "xlim"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=234995/12873；耗时=1624.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 10, "causal": 177}`。

- A1：Incorrect computation；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase.drag_pan"]]`
- A：Inaccurate recursive check；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase.set_xlim"]]`
- A2：Wrong logic；依据：；关联：`[["lib/matplotlib/pyplot.py", "xlim"]]`
- D：Use of emit=False in set_xlim for sibling axes；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase.sharex"]]`
- E：Recursion issue with emit=True；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase.set_xbound"]]`
- F：Move callback call outside of if-emit statement；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase.sharex"]]`
- G：Class _AxesBase；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase"]]`
- H：Function get_xbound；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase"]]`
- J：Function apply_aspect；依据：；关联：`[["lib/matplotlib/axes/_base.py", "_AxesBase"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-26011.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-26011.jsonl)

## 143. matplotlib__matplotlib-26020

项目：matplotlib/matplotlib；本轮子集：验证集；状态：complete。

问题描述节选：

> Error creating AxisGrid with non-default axis class
> <!--To help us understand and resolve your issue, please fill out the form to the best of your ability.-->
> <!--You can feel free to delete the sections that do not apply.-->
> 
> ### Bug report
> 
> **Bug summary**
> 
> Creating `AxesGrid` using cartopy `GeoAxes` as `axis_class` raises `TypeError: 'method' object is not subscriptable`. Seems to be due to different behaviour of `axis` attr. for `mpl_toolkits.axes_grid1.mpl_axes.Axes` and other axes instances (like `GeoAxes`) where `axis` is only a callable. The error is raised in method `mpl_toolkits.axes_grid1.axes_grid._tick_only` when trying to access keys from `axis` attr.
> 
> **Code for reproduction**
> 
> <!--A minimum code snippet required to reproduce the bug.
> Please make sure to minimize

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"]]`

新预测：`[["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"], ["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.toggle"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=54407/2902；耗时=278.0秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"]], "seeds": [["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"]], "causal_received": [["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"]], "final": [["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 8}`。

- A：Inaccurate recursive check；依据：；关联：`[["lib/mpl_toolkits/axes_grid1/axes_grid.py", "_tick_only"]]`
- D：Incorrect use of callable as dictionary；依据：；关联：`[["lib/mpl_toolkits/axes_grid1/mpl_axes.py", "SimpleAxisArtist.toggle"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/matplotlib__matplotlib-26020.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/matplotlib__matplotlib-26020.jsonl)

## 144. mwaskom__seaborn-2848

项目：mwaskom/seaborn；本轮子集：验证集；状态：complete。

问题描述节选：

> pairplot fails with hue_order not containing all hue values in seaborn 0.11.1
> In seaborn < 0.11, one could plot only a subset of the values in the hue column, by passing a hue_order list containing only the desired values. Points with hue values not in the list were simply not plotted.
> ```python
> iris = sns.load_dataset("iris")`
> # The hue column contains three different species; here we want to plot two
> sns.pairplot(iris, hue="species", hue_order=["setosa", "versicolor"])
> ```
> 
> This no longer works in 0.11.1. Passing a hue_order list that does not contain some of the values in the hue column raises a long, ugly error traceback. The first exception arises in seaborn/_core.py:
> ```
> TypeError: ufunc 'isnan' not supported for the input types, and the inputs could not be safely coerced to any supp

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["seaborn/_oldcore.py", "HueMapping._lookup_single"]]`

新预测：`[["seaborn/_compat.py", "<unresolved>:ScaledNorm.__call__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=17933/5175；耗时=353.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 28, "causal": 3}`。

无法唯一映射的函数：`[{"file": "seaborn/_compat.py", "name": "ScaledNorm.__call__", "reason": "absent"}]`

- D1：Transformation of input values；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- D2：Subtraction of transformed minimum；依据：；关联：`[]`
- D3：Division by difference of transformed max and min；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["seaborn/_compat.py", "ScaledNorm.__call__"]]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/mwaskom__seaborn-2848.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/mwaskom__seaborn-2848.jsonl)

## 145. mwaskom__seaborn-3010

项目：mwaskom/seaborn；本轮子集：验证集；状态：complete。

问题描述节选：

> PolyFit is not robust to missing data
> ```python
> so.Plot([1, 2, 3, None, 4], [1, 2, 3, 4, 5]).add(so.Line(), so.PolyFit())
> ```
> 
> <details><summary>Traceback</summary>
> 
> ```python-traceback
> ---------------------------------------------------------------------------
> LinAlgError                               Traceback (most recent call last)
> File ~/miniconda3/envs/seaborn-py39-latest/lib/python3.9/site-packages/IPython/core/formatters.py:343, in BaseFormatter.__call__(self, obj)
>     341     method = get_real_method(obj, self.print_method)
>     342     if method is not None:
> --> 343         return method()
>     344     return None
>     345 else:
> 
> File ~/code/seaborn/seaborn/_core/plot.py:265, in Plot._repr_png_(self)
>     263 def _repr_png_(self) -> tuple[bytes, dict[str, float]]:
> -

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["seaborn/_stats/regression.py", "PolyFit.__call__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=16062/2599；耗时=174.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A1：Missing data in x；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Missing data in y；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/mwaskom__seaborn-3010.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/mwaskom__seaborn-3010.jsonl)

## 146. mwaskom__seaborn-3190

项目：mwaskom/seaborn；本轮子集：开发集；状态：complete。

问题描述节选：

> Color mapping fails with boolean data
> ```python
> so.Plot(["a", "b"], [1, 2], color=[True, False]).add(so.Bar())
> ```
> ```python-traceback
> ---------------------------------------------------------------------------
> TypeError                                 Traceback (most recent call last)
> ...
> File ~/code/seaborn/seaborn/_core/plot.py:841, in Plot._plot(self, pyplot)
>     838 plotter._compute_stats(self, layers)
>     840 # Process scale spec for semantic variables and coordinates computed by stat
> --> 841 plotter._setup_scales(self, common, layers)
>     843 # TODO Remove these after updating other methods
>     844 # ---- Maybe have debug= param that attaches these when True?
>     845 plotter._data = common
> 
> File ~/code/seaborn/seaborn/_core/plot.py:1252, in Plotter._setup_scales(self,

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["seaborn/_core/scales.py", "ContinuousBase._setup"]]`

新预测：`[["seaborn/_core/properties.py", "PointSize._forward"]]`

搜索种子 7；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=51756/11456；耗时=877.3秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["seaborn/_core/scales.py", "ContinuousBase._setup"]], "seeds": [["seaborn/_core/scales.py", "ContinuousBase._setup"]], "causal_received": [["seaborn/_core/scales.py", "ContinuousBase._setup"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 6, "relevance": 5, "causal": 25}`。

- A1：Incorrect computation；依据：；关联：`[["tests/_core/test_properties.py", "test_properties.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["seaborn/_core/properties.py", "properties.py"]]`
- A2：Wrong logic；依据：；关联：`[["seaborn/_core/properties.py", "PointSize"]]`
- D：Boolean Subtraction in _forward Method；依据：；关联：`[["seaborn/_core/rules.py", "rules.py"], ["seaborn/_core/scales.py", "scales.py"], ["seaborn/_compat.py", "_compat.py"], ["tests/_core/test_scales.py", "test_scales.py"], ["seaborn/_core/plot.py", "plot.py"]]`
- E：Use of Bitwise XOR or Logical XOR；依据：；关联：`[["seaborn/_core/rules.py", "rules.py"], ["seaborn/_core/scales.py", "scales.py"], ["seaborn/_compat.py", "_compat.py"], ["tests/_core/test_scales.py", "test_scales.py"], ["seaborn/_core/plot.py", "plot.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["seaborn/_core/properties.py", "PointSize._forward"]]`
- C：Dependency on Product；依据：；关联：`[["seaborn/_core/properties.py", "PointSize._forward"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/mwaskom__seaborn-3190.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/mwaskom__seaborn-3190.jsonl)

## 147. mwaskom__seaborn-3407

项目：mwaskom/seaborn；本轮子集：开发集；状态：complete。

问题描述节选：

> pairplot raises KeyError with MultiIndex DataFrame
> When trying to pairplot a MultiIndex DataFrame, `pairplot` raises a `KeyError`:
> 
> MRE:
> 
> ```python
> import numpy as np
> import pandas as pd
> import seaborn as sns
> 
> 
> data = {
>     ("A", "1"): np.random.rand(100),
>     ("A", "2"): np.random.rand(100),
>     ("B", "1"): np.random.rand(100),
>     ("B", "2"): np.random.rand(100),
> }
> df = pd.DataFrame(data)
> sns.pairplot(df)
> ```
> 
> Output:
> 
> ```
> [c:\Users\KLuu\anaconda3\lib\site-packages\seaborn\axisgrid.py](file:///C:/Users/KLuu/anaconda3/lib/site-packages/seaborn/axisgrid.py) in pairplot(data, hue, hue_order, palette, vars, x_vars, y_vars, kind, diag_kind, markers, height, aspect, corner, dropna, plot_kws, diag_kws, grid_kws, size)
>    2142     diag_kws.setdefault("legend", False)
>    

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["seaborn/axisgrid.py", "PairGrid.map_diag"]]`

新预测：`[["seaborn/axisgrid.py", "PairGrid.map_diag"], ["tests/test_axisgrid.py", "TestPairGrid.test_map_diag_matplotlib"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=34651/4475；耗时=355.9秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["seaborn/axisgrid.py", "PairGrid.map_diag"]], "seeds": [["seaborn/axisgrid.py", "PairGrid.map_diag"]], "causal_received": [["seaborn/axisgrid.py", "PairGrid.map_diag"]], "final": [["seaborn/axisgrid.py", "PairGrid.map_diag"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 21}`。

- A1：Incorrect computation；依据：；关联：`[["", "self.x_vars"]]`
- A：Inaccurate recursive check；依据：；关联：`[["seaborn/axisgrid.py", "PairGrid.map_diag"]]`
- A2：Wrong logic；依据：；关联：`[["tests/test_axisgrid.py", "TestPairGrid.test_map_diag_matplotlib"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/mwaskom__seaborn-3407.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/mwaskom__seaborn-3407.jsonl)

## 148. pallets__flask-4045

项目：pallets/flask；本轮子集：开发集；状态：complete。

问题描述节选：

> Raise error when blueprint name contains a dot
> This is required since every dot is now significant since blueprints can be nested. An error was already added for endpoint names in 1.0, but should have been added for this as well.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 0.00% | 命中 |

共同严格目标：`[["src/flask/blueprints.py", "Blueprint.__init__"], ["src/flask/blueprints.py", "Blueprint.add_url_rule"]]`

新预测：`[["src/flask/blueprints.py", "Blueprint.__init__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=18213/2400；耗时=171.5秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["src/flask/blueprints.py", "Blueprint.__init__"]], "seeds": [["src/flask/blueprints.py", "Blueprint.__init__"]], "causal_received": [["src/flask/blueprints.py", "Blueprint.__init__"]], "final": [["src/flask/blueprints.py", "Blueprint.__init__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 37, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["src/flask/blueprints.py", "Blueprint.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pallets__flask-4045.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pallets__flask-4045.jsonl)

## 149. pallets__flask-4992

项目：pallets/flask；本轮子集：验证集；状态：complete。

问题描述节选：

> Add a file mode parameter to flask.Config.from_file()
> Python 3.11 introduced native TOML support with the `tomllib` package. This could work nicely with the `flask.Config.from_file()` method as an easy way to load TOML config files:
> 
> ```python
> app.config.from_file("config.toml", tomllib.load)
> ```
> 
> However, `tomllib.load()` takes an object readable in binary mode, while `flask.Config.from_file()` opens a file in text mode, resulting in this error:
> 
> ```
> TypeError: File must be opened in binary mode, e.g. use `open('foo.toml', 'rb')`
> ```
> 
> We can get around this with a more verbose expression, like loading from a file opened with the built-in `open()` function and passing the `dict` to `app.Config.from_mapping()`:
> 
> ```python
> # We have to repeat the path joining that from_file() 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["src/flask/config.py", "Config.from_file"]]`

新预测：`[["src/flask/config.py", "Config.from_file"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=6660/1491；耗时=115.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["src/flask/config.py", "Config.from_file"]], "seeds": [["src/flask/config.py", "Config.from_file"]], "causal_received": [["src/flask/config.py", "Config.from_file"]], "final": [["src/flask/config.py", "Config.from_file"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 2}`。

- A：Inaccurate recursive check；依据：；关联：`[["src/flask/config.py", "Config.from_file"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pallets__flask-4992.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pallets__flask-4992.jsonl)

## 150. pallets__flask-5063

项目：pallets/flask；本轮子集：开发集；状态：complete。

问题描述节选：

> Flask routes to return domain/sub-domains information
> Currently when checking **flask routes** it provides all routes but **it is no way to see which routes are assigned to which subdomain**.
> 
> **Default server name:**
> SERVER_NAME: 'test.local'
> 
> **Domains (sub-domains):**
> test.test.local
> admin.test.local
> test.local
> 
> **Adding blueprints:**
> app.register_blueprint(admin_blueprint,url_prefix='',subdomain='admin')
> app.register_blueprint(test_subdomain_blueprint,url_prefix='',subdomain='test')
> 
> 
> ```
> $ flask routes
>  * Tip: There are .env or .flaskenv files present. Do "pip install python-dotenv" to use them.
> Endpoint                                                 Methods    Rule
> -------------------------------------------------------  ---------  --------------------------------

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/flask/cli.py", "routes_command"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4682/1549；耗时=109.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pallets__flask-5063.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pallets__flask-5063.jsonl)

## 151. psf__requests-1963

项目：psf/requests；本轮子集：验证集；状态：complete。

问题描述节选：

> `Session.resolve_redirects` copies the original request for all subsequent requests, can cause incorrect method selection
> Consider the following redirection chain:
> 
> ```
> POST /do_something HTTP/1.1
> Host: server.example.com
> ...
> 
> HTTP/1.1 303 See Other
> Location: /new_thing_1513
> 
> GET /new_thing_1513
> Host: server.example.com
> ...
> 
> HTTP/1.1 307 Temporary Redirect
> Location: //failover.example.com/new_thing_1513
> ```
> 
> The intermediate 303 See Other has caused the POST to be converted to
> a GET.  The subsequent 307 should preserve the GET.  However, because
> `Session.resolve_redirects` starts each iteration by copying the _original_
> request object, Requests will issue a POST!
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |

共同严格目标：`[["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"]]`

新预测：`[["requests/adapters.py", "HTTPAdapter.build_response"], ["requests/cookies.py", "extract_cookies_to_jar"], ["requests/sessions.py", "Session.send"], ["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"], ["requests/utils.py", "to_native_string"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=35889/9417；耗时=703.0秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"]], "seeds": [["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"]], "causal_received": [["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"]], "final": [["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 22}`。

- A1：Incorrect computation；依据：；关联：`[["requests/cookies.py", "extract_cookies_to_jar"]]`
- A：Inaccurate recursive check；依据：；关联：`[["requests/sessions.py", "SessionRedirectMixin.resolve_redirects"]]`
- A2：Wrong logic；依据：；关联：`[["requests/utils.py", "to_native_string"]]`
- D：Method change due to 303 See Other；依据：；关联：`[["requests/sessions.py", "Session.send"]]`
- E：Copying original request；依据：；关联：`[["requests/adapters.py", "HTTPAdapter.build_response"], ["requests/sessions.py", "Session.send"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/psf__requests-1963.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/psf__requests-1963.jsonl)

## 152. psf__requests-2148

项目：psf/requests；本轮子集：验证集；状态：complete。

问题描述节选：

> socket.error exception not caught/wrapped in a requests exception (ConnectionError perhaps?)
> I just noticed a case where I had a socket reset on me, and was raised to me as a raw socket error as opposed to something like a requests.exceptions.ConnectionError:
> 
> ```
>   File "/home/rtdean/***/***/***/***/***/***.py", line 67, in dir_parse
>     root = ElementTree.fromstring(response.text)
>   File "/home/rtdean/.pyenv/versions/2.7.6/lib/python2.7/site-packages/requests-2.3.0-py2.7.egg/requests/models.py", line 721, in text
>     if not self.content:
>   File "/home/rtdean/.pyenv/versions/2.7.6/lib/python2.7/site-packages/requests-2.3.0-py2.7.egg/requests/models.py", line 694, in content
>     self._content = bytes().join(self.iter_content(CONTENT_CHUNK_SIZE)) or bytes()
>   File "/home/rtdean/.pyenv/versi

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["requests/models.py", "Response.iter_content.generate"]]`

新预测：`[]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=26109/6329；耗时=465.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- D1：ProxyError；依据：；关联：`[["requests/exceptions.py", "ProxyError"]]`
- A：Inaccurate recursive check；依据：；关联：`[["requests/exceptions.py", "ConnectionError"]]`
- D2：SSLError；依据：；关联：`[["requests/exceptions.py", "SSLError"]]`
- E：exceptions.py；依据：；关联：`[["requests/exceptions.py", "exceptions.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/psf__requests-2148.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/psf__requests-2148.jsonl)

## 153. psf__requests-2317

项目：psf/requests；本轮子集：验证集；状态：complete。

问题描述节选：

> method = builtin_str(method) problem
> In requests/sessions.py is a command:
> 
> method = builtin_str(method)
> Converts method from
> b’GET’
> to
> "b'GET’"
> 
> Which is the literal string, no longer a binary string.  When requests tries to use the method "b'GET’”, it gets a 404 Not Found response.
> 
> I am using python3.4 and python-neutronclient (2.3.9) with requests (2.4.3).  neutronclient is broken because it uses this "args = utils.safe_encode_list(args)" command which converts all the values to binary string, including method.
> 
> I'm not sure if this is a bug with neutronclient or a bug with requests, but I'm starting here.  Seems if requests handled the method value being a binary string, we wouldn't have any problem.
> 
> Also, I tried in python2.6 and this bug doesn't exist there. Some difference between

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["requests/sessions.py", "Session.request"]]`

新预测：`[["requests/utils.py", "to_native_string"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=22505/4393；耗时=314.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 10, "causal": 35}`。

- A1：Incorrect computation；依据：；关联：`[["requests/utils.py", "utils.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["requests/utils.py", "to_native_string"]]`
- A2：Wrong logic；依据：；关联：`[["requests/compat.py", "is_py2"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/psf__requests-2317.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/psf__requests-2317.jsonl)

## 154. psf__requests-2674

项目：psf/requests；本轮子集：开发集；状态：complete。

问题描述节选：

> urllib3 exceptions passing through requests API
> I don't know if it's a design goal of requests to hide urllib3's exceptions and wrap them around requests.exceptions types.
> 
> (If it's not IMHO it should be, but that's another discussion)
> 
> If it is, I have at least two of them passing through that I have to catch in addition to requests' exceptions. They are requests.packages.urllib3.exceptions.DecodeError and requests.packages.urllib3.exceptions.TimeoutError (this one I get when a proxy timeouts)
> 
> Thanks!
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["requests/adapters.py", "HTTPAdapter.send"]]`

新预测：`[["requests/packages/urllib3/response.py", "HTTPResponse._decode"], ["requests/packages/urllib3/response.py", "HTTPResponse._handle_chunk"], ["requests/packages/urllib3/response.py", "HTTPResponse.flush"], ["requests/packages/urllib3/response.py", "HTTPResponse.read_chunked"], ["requests/packages/urllib3/response.py", "HTTPResponse.stream"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=88053/24137；耗时=1733.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 9, "causal": 21}`。

- A1：Incorrect computation；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse._handle_chunk"]]`
- A：Inaccurate recursive check；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse._decode"]]`
- A2：Wrong logic；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse.stream"]]`
- D1：_decode；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse.read_chunked"], ["", "self._decoder"]]`
- L：_update_chunk_length；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- E1：DecodeError；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse.read_chunked"]]`
- F1：TimeoutError；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse.read_chunked"]]`
- E2：ResponseNotChunked；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"]]`
- F2：_init_decoder；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- G：self.chunk_left；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- H：self.chunked；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- J：close；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- K：self._fp；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- M：self._original_response；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- N：release_conn；依据：；关联：`[["requests/packages/urllib3/exceptions.py", "ResponseNotChunked"], ["", "self.chunk_left"], ["", "self.chunked"], ["", "self._fp"]]`
- D2：HTTPResponse；依据：；关联：`[["requests/packages/urllib3/response.py", "HTTPResponse.flush"], ["requests/packages/urllib3/response.py", "HTTPResponse"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/psf__requests-2674.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/psf__requests-2674.jsonl)

## 155. psf__requests-3362

项目：psf/requests；本轮子集：验证集；状态：complete。

问题描述节选：

> Uncertain about content/text vs iter_content(decode_unicode=True/False)
> When requesting an application/json document, I'm seeing `next(r.iter_content(16*1024, decode_unicode=True))` returning bytes, whereas `r.text` returns unicode. My understanding was that both should return a unicode object. In essence, I thought "iter_content" was equivalent to "iter_text" when decode_unicode was True. Have I misunderstood something? I can provide an example if needed.
> 
> For reference, I'm using python 3.5.1 and requests 2.10.0.
> 
> Thanks!
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["requests/utils.py", "stream_decode_response_unicode"]]`

新预测：`[["requests/models.py", "Response.iter_content"], ["requests/utils.py", "iter_slices"], ["tests/test_requests.py", "TestRequests.test_response_chunk_size_int"], ["tests/test_requests.py", "TestRequests.test_response_decode_unicode"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=22018/4450；耗时=319.8秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["requests/utils.py", "stream_decode_response_unicode"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 5, "causal": 12}`。

- A1：Incorrect computation；依据：；关联：`[["tests/test_requests.py", "TestRequests.test_response_chunk_size_int"]]`
- A：Inaccurate recursive check；依据：；关联：`[["requests/models.py", "Response.iter_content"]]`
- A2：Wrong logic；依据：；关联：`[["requests/utils.py", "iter_slices"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/test_requests.py", "TestRequests.test_response_decode_unicode"]]`
- D：TestRequests；依据：；关联：`[]`
- E：Response；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[["tests/test_requests.py", "TestRequests.test_response_decode_unicode"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/psf__requests-3362.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/psf__requests-3362.jsonl)

## 156. psf__requests-863

项目：psf/requests；本轮子集：开发集；状态：complete。

问题描述节选：

> Allow lists in the dict values of the hooks argument
> Currently the Request class has a .register_hook() method but it parses the dictionary it expects from it's hooks argument weirdly: the argument can only specify one hook function per hook.  If you pass in a list of hook functions per hook the code in Request.**init**() will wrap the list in a list which then fails when the hooks are consumed (since a list is not callable).  This is especially annoying since you can not use multiple hooks from a session.  The only way to get multiple hooks now is to create the request object without sending it, then call .register_hook() multiple times and then finally call .send().
> 
> This would all be much easier if Request.**init**() parsed the hooks parameter in a way that it accepts lists as it's valu

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["requests/models.py", "Request.register_hook"]]`

新预测：`[["requests/models.py", "Request.__init__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=20274/3865；耗时=281.6秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["requests/models.py", "Request.register_hook"]], "seeds": [["requests/models.py", "Request.register_hook"]], "causal_received": [["requests/models.py", "Request.register_hook"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 32, "causal": 5}`。

- D：Incorrect processing of hooks argument；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["requests/models.py", "Request.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/psf__requests-863.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/psf__requests-863.jsonl)

## 157. pydata__xarray-3364

项目：pydata/xarray；本轮子集：验证集；状态：complete。

问题描述节选：

> Ignore missing variables when concatenating datasets?
> Several users (@raj-kesavan, @richardotis, now myself) have wondered about how to concatenate xray Datasets with different variables.
> 
> With the current `xray.concat`, you need to awkwardly create dummy variables filled with `NaN` in datasets that don't have them (or drop mismatched variables entirely). Neither of these are great options -- `concat` should have an option (the default?) to take care of this for the user.
> 
> This would also be more consistent with `pd.concat`, which takes a more relaxed approach to matching dataframes with different variables (it does an outer join).
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 10.00% | 100.00% | 18.18% | 100.00% | 命中 |

共同严格目标：`[["xarray/core/concat.py", "_dataset_concat"]]`

新预测：`[["xarray/core/combine.py", "_auto_concat"], ["xarray/core/combine.py", "_combine_1d"], ["xarray/core/concat.py", "_dataarray_concat"], ["xarray/core/concat.py", "_dataset_concat"], ["xarray/core/concat.py", "concat"], ["xarray/core/dataarray.py", "<unresolved>:DataArray.compat"], ["xarray/core/groupby.py", "DataArrayGroupBy._combine"], ["xarray/core/groupby.py", "DataArrayGroupBy._concat_shortcut"], ["xarray/core/groupby.py", "DatasetGroupBy._combine"], ["xarray/core/variable.py", "IndexVariable.concat"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=120903/12542；耗时=1151.9秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["xarray/core/concat.py", "_dataset_concat"]], "final": [["xarray/core/concat.py", "_dataset_concat"]]}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 5, "causal": 89}`。

无法唯一映射的函数：`[{"file": "xarray/core/dataarray.py", "name": "DataArray.compat", "reason": "absent"}]`

- A1：Incorrect computation；依据：；关联：`[["xarray/core/groupby.py", "DataArrayGroupBy._concat_shortcut"]]`
- A：Inaccurate recursive check；依据：；关联：`[["xarray/core/concat.py", "concat"]]`
- A2：Wrong logic；依据：；关联：`[["xarray/core/dataarray.py", "DataArray.compat"]]`
- D：_concat_shortcut；依据：；关联：`[["xarray/core/groupby.py", "DataArrayGroupBy._combine"]]`
- E：_auto_concat；依据：；关联：`[["xarray/core/combine.py", "_auto_concat"], ["xarray/core/groupby.py", "DatasetGroupBy._combine"]]`
- F：_dataset_concat；依据：；关联：`[["xarray/core/concat.py", "_dataset_concat"], ["xarray/core/combine.py", "_combine_1d"]]`
- G：_combine；依据：；关联：`[["xarray/core/concat.py", "_dataarray_concat"], ["xarray/core/groupby.py", "DataArrayGroupBy._combine"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["xarray/core/variable.py", "IndexVariable.concat"]]`
- C：Dependency on Product；依据：；关联：`[["xarray/core/variable.py", "IndexVariable.concat"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pydata__xarray-3364.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pydata__xarray-3364.jsonl)

## 158. pydata__xarray-4094

项目：pydata/xarray；本轮子集：验证集；状态：failed。

问题描述节选：

> to_unstacked_dataset broken for single-dim variables
> <!-- A short summary of the issue, if appropriate -->
> 
> 
> #### MCVE Code Sample
> 
> ```python
> arr = xr.DataArray(
>      np.arange(3),
>      coords=[("x", [0, 1, 2])],
>  )
> data = xr.Dataset({"a": arr, "b": arr})
> stacked = data.to_stacked_array('y', sample_dims=['x'])
> unstacked = stacked.to_unstacked_dataset('y')
> # MergeError: conflicting values for variable 'y' on objects to be combined. You can skip this check by specifying compat='override'.
> ```
> 
> #### Expected Output
> A working roundtrip.
> 
> #### Problem Description
> I need to stack a bunch of variables and later unstack them again, however this doesn't work if the variables only have a single dimension.
> 
> #### Versions
> 
> <details><summary>Output of <tt>xr.show_versions()</tt>

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["xarray/core/dataarray.py", "DataArray.to_unstacked_dataset"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=15171/5104；耗时=433.9秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["xarray/core/dataarray.py", "DataArray.to_unstacked_dataset"]], "seeds": [], "causal_received": [["xarray/core/dataarray.py", "DataArray.to_unstacked_dataset"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 11}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/pydata__xarray-4094.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pydata__xarray-4094.jsonl)

## 159. pydata__xarray-4248

项目：pydata/xarray；本轮子集：验证集；状态：complete。

问题描述节选：

> Feature request: show units in dataset overview
> Here's a hypothetical dataset:
> 
> ```
> <xarray.Dataset>
> Dimensions:  (time: 3, x: 988, y: 822)
> Coordinates:
>   * x         (x) float64 ...
>   * y         (y) float64 ...
>   * time      (time) datetime64[ns] ...
> Data variables:
>     rainfall  (time, y, x) float32 ...
>     max_temp  (time, y, x) float32 ...
> ```
> 
> It would be really nice if the units of the coordinates and of the data variables were shown in the `Dataset` repr, for example as:
> 
> ```
> <xarray.Dataset>
> Dimensions:  (time: 3, x: 988, y: 822)
> Coordinates:
>   * x, in metres         (x)            float64 ...
>   * y, in metres         (y)            float64 ...
>   * time                 (time)         datetime64[ns] ...
> Data variables:
>     rainfall, in mm      (time, y, x)  

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["xarray/core/formatting.py", "inline_variable_array_repr"]]`

新预测：`[["xarray/core/common.py", "AbstractArray.__repr__"], ["xarray/core/utils.py", "ReprObject.__repr__"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=14178/2977；耗时=252.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 36, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["xarray/core/common.py", "AbstractArray.__repr__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["xarray/core/utils.py", "ReprObject.__repr__"]]`
- C：Dependency on Product；依据：；关联：`[["xarray/core/utils.py", "ReprObject.__repr__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pydata__xarray-4248.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pydata__xarray-4248.jsonl)

## 160. pydata__xarray-4493

项目：pydata/xarray；本轮子集：开发集；状态：complete。

问题描述节选：

> DataSet.update causes chunked dask DataArray to evalute its values eagerly 
> **What happened**:
> Used `DataSet.update` to update a chunked dask DataArray, but the DataArray is no longer chunked after the update.
> 
> **What you expected to happen**:
> The chunked DataArray should still be chunked after the update
> 
> **Minimal Complete Verifiable Example**:
> 
> ```python
> foo = xr.DataArray(np.random.randn(3, 3), dims=("x", "y")).chunk()  # foo is chunked
> ds = xr.Dataset({"foo": foo, "bar": ("x", [1, 2, 3])})  # foo is still chunked here
> ds  # you can verify that foo is chunked
> ```
> ```python
> update_dict = {"foo": (("x", "y"), ds.foo[1:, :]), "bar": ("x", ds.bar[1:])}
> update_dict["foo"][1]  # foo is still chunked
> ```
> ```python
> ds.update(update_dict)
> ds  # now foo is no longer chunked
> `

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["xarray/core/variable.py", "as_variable"]]`

新预测：`[["xarray/backends/pydap_.py", "_fix_attributes"], ["xarray/core/alignment.py", "_broadcast_helper"], ["xarray/core/computation.py", "dot"], ["xarray/core/coordinates.py", "Coordinates.update"], ["xarray/core/dataset.py", "split_indexes"], ["xarray/core/merge.py", "determine_coords"], ["xarray/core/missing.py", "_get_interpolator"], ["xarray/core/missing.py", "decompose_interp"], ["xarray/core/utils.py", "OrderedSet.update"], ["xarray/core/variable.py", "Variable._broadcast_indexes_vectorized"], ["xarray/core/variable.py", "assert_unique_multiindex_level_names"], ["xarray/plot/dataset_plot.py", "_dsplot"], ["xarray/plot/dataset_plot.py", "scatter"], ["xarray/plot/plot.py", "_plot2d"], ["xarray/plot/plot.py", "line"], ["xarray/plot/utils.py", "_process_cmap_cbar_kwargs"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=325809/44893；耗时=3860.5秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["xarray/core/variable.py", "as_variable"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 32, "causal": 115}`。

- A1：Dependency on _fast_dataset；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["xarray/core/coordinates.py", "Coordinates.update"]]`
- A2：Dependency on calculate_dimensions；依据：；关联：`[]`
- A3：Dependency on deep_align；依据：；关联：`[]`
- A4：Dependency on collect_variables_and_indexes；依据：；关联：`[]`
- A5：Dependency on merge_collected；依据：；关联：`[]`
- A6：Dependency on assert_unique_multiindex_level_names；依据：；关联：`[]`
- A7：Dependency on merge_attrs；依据：；关联：`[]`
- A8：Dependency on expand_variable_dicts；依据：；关联：`[]`
- A9：Dependency on determine_coords；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["xarray/core/utils.py", "OrderedSet.update"]]`
- C：Dependency on Product；依据：；关联：`[["xarray/core/utils.py", "OrderedSet.update"]]`
- D：Dependency on _process_cmap_cbar_kwargs；依据：；关联：`[["xarray/plot/utils.py", "_process_cmap_cbar_kwargs"]]`
- E：Dependency on _get_interpolator；依据：；关联：`[["xarray/core/missing.py", "_get_interpolator"]]`
- F：Dependency on decompose_interp；依据：；关联：`[["xarray/core/missing.py", "decompose_interp"]]`
- G：Dependency on _broadcast_indexes_vectorized；依据：；关联：`[["xarray/core/merge.py", "determine_coords"]]`
- H：Dependency on scatter；依据：；关联：`[["xarray/core/alignment.py", "_broadcast_helper"]]`
- I1：Dependency on _fix_attributes；依据：；关联：`[["xarray/plot/dataset_plot.py", "scatter"]]`
- J：Dependency on _plot2d；依据：；关联：`[["xarray/backends/pydap_.py", "_fix_attributes"]]`
- K：Dependency on apply_variable_ufunc；依据：；关联：`[["xarray/plot/plot.py", "_plot2d"]]`
- L：Dependency on merge_core；依据：；关联：`[["xarray/core/variable.py", "assert_unique_multiindex_level_names"]]`
- M：Dependency on open_dataset；依据：；关联：`[["xarray/core/variable.py", "Variable._broadcast_indexes_vectorized"]]`
- N：Dependency on to_dict；依据：；关联：`[["xarray/plot/plot.py", "line"]]`
- O：Dependency on interp；依据：；关联：`[["xarray/plot/dataset_plot.py", "_dsplot"]]`
- P：Dependency on dot；依据：；关联：`[["xarray/core/dataset.py", "split_indexes"]]`
- Q：Dependency on imshow；依据：；关联：`[["xarray/core/computation.py", "dot"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pydata__xarray-4493.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pydata__xarray-4493.jsonl)

## 161. pydata__xarray-5131

项目：pydata/xarray；本轮子集：开发集；状态：complete。

问题描述节选：

> Trailing whitespace in DatasetGroupBy text representation
> When displaying a DatasetGroupBy in an interactive Python session, the first line of output contains a trailing whitespace. The first example in the documentation demonstrate this:
> 
> ```pycon
> >>> import xarray as xr, numpy as np
> >>> ds = xr.Dataset(
> ...     {"foo": (("x", "y"), np.random.rand(4, 3))},
> ...     coords={"x": [10, 20, 30, 40], "letters": ("x", list("abba"))},
> ... )
> >>> ds.groupby("letters")
> DatasetGroupBy, grouped over 'letters' 
> 2 groups with labels 'a', 'b'.
> ```
> 
> There is a trailing whitespace in the first line of output which is "DatasetGroupBy, grouped over 'letters' ". This can be seen more clearly by converting the object to a string (note the whitespace before `\n`):
> 
> ```pycon
> >>> str(ds.groupby("l

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["xarray/core/groupby.py", "GroupBy.__repr__"]]`

新预测：`[["xarray/coding/cftime_offsets.py", "BaseCFTimeOffset.__str__"], ["xarray/coding/cftime_offsets.py", "YearOffset.__str__"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=9200/1378；耗时=118.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 4}`。

- A：Inaccurate recursive check；依据：；关联：`[["xarray/coding/cftime_offsets.py", "BaseCFTimeOffset.__str__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["xarray/coding/cftime_offsets.py", "YearOffset.__str__"]]`
- C：Dependency on Product；依据：；关联：`[["xarray/coding/cftime_offsets.py", "YearOffset.__str__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pydata__xarray-5131.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pydata__xarray-5131.jsonl)

## 162. pylint-dev__pylint-5859

项目：pylint-dev/pylint；本轮子集：验证集；状态：complete。

问题描述节选：

> "--notes" option ignores note tags that are entirely punctuation
> ### Bug description
> 
> If a note tag specified with the `--notes` option is entirely punctuation, pylint won't report a fixme warning (W0511).
> 
> ```python
> # YES: yes
> # ???: no
> ```
> 
> `pylint test.py --notes="YES,???"` will return a fixme warning (W0511) for the first line, but not the second.
> 
> ### Configuration
> 
> ```ini
> Default
> ```
> 
> 
> ### Command used
> 
> ```shell
> pylint test.py --notes="YES,???"
> ```
> 
> 
> ### Pylint output
> 
> ```shell
> ************* Module test
> test.py:1:1: W0511: YES: yes (fixme)
> ```
> 
> 
> ### Expected behavior
> 
> ```
> ************* Module test
> test.py:1:1: W0511: YES: yes (fixme)
> test.py:2:1: W0511: ???: no (fixme)
> ```
> 
> ### Pylint version
> 
> ```shell
> pylint 2.12.2
> astroid 2.9.0
> Python 3.10.2 (main, Feb  2 2022, 05:51:

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["pylint/checkers/misc.py", "EncodingChecker.open"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=14190/2283；耗时=178.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 36, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pylint-dev__pylint-5859.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pylint-dev__pylint-5859.jsonl)

## 163. pylint-dev__pylint-6506

项目：pylint-dev/pylint；本轮子集：验证集；状态：complete。

问题描述节选：

> Traceback printed for unrecognized option
> ### Bug description
> 
> A traceback is printed when an unrecognized option is passed to pylint.
> 
> ### Configuration
> 
> _No response_
> 
> ### Command used
> 
> ```shell
> pylint -Q
> ```
> 
> 
> ### Pylint output
> 
> ```shell
> ************* Module Command line
> Command line:1:0: E0015: Unrecognized option found: Q (unrecognized-option)
> Traceback (most recent call last):
>   File "/Users/markbyrne/venv310/bin/pylint", line 33, in <module>
>     sys.exit(load_entry_point('pylint', 'console_scripts', 'pylint')())
>   File "/Users/markbyrne/programming/pylint/pylint/__init__.py", line 24, in run_pylint
>     PylintRun(argv or sys.argv[1:])
>   File "/Users/markbyrne/programming/pylint/pylint/lint/run.py", line 135, in __init__
>     args = _config_initialization(
>   File "/Users/markb

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["pylint/config/config_initialization.py", "_config_initialization"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=8926/1033；耗时=85.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 2, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pylint-dev__pylint-6506.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pylint-dev__pylint-6506.jsonl)

## 164. pylint-dev__pylint-7080

项目：pylint-dev/pylint；本轮子集：验证集；状态：complete。

问题描述节选：

> `--recursive=y` ignores `ignore-paths`
> ### Bug description
> 
> When running recursively, it seems `ignore-paths` in my settings in pyproject.toml is completely ignored
> 
> ### Configuration
> 
> ```ini
> [tool.pylint.MASTER]
> ignore-paths = [
>   # Auto generated
>   "^src/gen/.*$",
> ]
> ```
> 
> 
> ### Command used
> 
> ```shell
> pylint --recursive=y src/
> ```
> 
> 
> ### Pylint output
> 
> ```shell
> ************* Module region_selection
> src\region_selection.py:170:0: R0914: Too many local variables (17/15) (too-many-locals)
> ************* Module about
> src\gen\about.py:2:0: R2044: Line with empty comment (empty-comment)
> src\gen\about.py:4:0: R2044: Line with empty comment (empty-comment)
> src\gen\about.py:57:0: C0301: Line too long (504/120) (line-too-long)
> src\gen\about.py:12:0: C0103: Class name "Ui_

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["pylint/lint/expand_modules.py", "_is_ignored_file"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=99983/1908；耗时=173.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pylint-dev__pylint-7080.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pylint-dev__pylint-7080.jsonl)

## 165. pylint-dev__pylint-7114

项目：pylint-dev/pylint；本轮子集：验证集；状态：complete。

问题描述节选：

> Linting fails if module contains module of the same name
> ### Steps to reproduce
> 
> Given multiple files:
> ```
> .
> `-- a/
>     |-- a.py
>     `-- b.py
> ```
> Which are all empty, running `pylint a` fails:
> 
> ```
> $ pylint a
> ************* Module a
> a/__init__.py:1:0: F0010: error while code parsing: Unable to load file a/__init__.py:
> [Errno 2] No such file or directory: 'a/__init__.py' (parse-error)
> $
> ```
> 
> However, if I rename `a.py`, `pylint a` succeeds:
> 
> ```
> $ mv a/a.py a/c.py
> $ pylint a
> $
> ```
> Alternatively, I can also `touch a/__init__.py`, but that shouldn't be necessary anymore.
> 
> ### Current behavior
> 
> Running `pylint a` if `a/a.py` is present fails while searching for an `__init__.py` file.
> 
> ### Expected behavior
> 
> Running `pylint a` if `a/a.py` is present should succe

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["pylint/lint/expand_modules.py", "expand_modules"]]`

新预测：`[]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=10675/2476；耗时=212.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 1}`。

- D：Conflicting Module Names；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["tests/input/func_noerror_cycle/a.py", "a.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/regrtest_data/beyond_top_three/a.py", "a.py"]]`
- C：Dependency on Product；依据：；关联：`[["tests/regrtest_data/beyond_top_three/a.py", "a.py"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pylint-dev__pylint-7114.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pylint-dev__pylint-7114.jsonl)

## 166. pylint-dev__pylint-7228

项目：pylint-dev/pylint；本轮子集：开发集；状态：complete。

问题描述节选：

> rxg include '\p{Han}' will throw error
> ### Bug description
> 
> config rxg in pylintrc with \p{Han} will throw err
> 
> ### Configuration
> .pylintrc:
> 
> ```ini
> function-rgx=[\p{Han}a-z_][\p{Han}a-z0-9_]{2,30}$
> ```
> 
> ### Command used
> 
> ```shell
> pylint
> ```
> 
> 
> ### Pylint output
> 
> ```shell
> (venvtest) tsung-hande-MacBook-Pro:robot_is_comming tsung-han$ pylint
> Traceback (most recent call last):
>   File "/Users/tsung-han/PycharmProjects/robot_is_comming/venvtest/bin/pylint", line 8, in <module>
>     sys.exit(run_pylint())
>   File "/Users/tsung-han/PycharmProjects/robot_is_comming/venvtest/lib/python3.9/site-packages/pylint/__init__.py", line 25, in run_pylint
>     PylintRun(argv or sys.argv[1:])
>   File "/Users/tsung-han/PycharmProjects/robot_is_comming/venvtest/lib/python3.9/site-packages

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["pylint/config/argument.py", "_regex_transformer"], ["pylint/config/argument.py", "_regexp_csv_transfomer"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12837/1679；耗时=240.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pylint-dev__pylint-7228.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pylint-dev__pylint-7228.jsonl)

## 167. pylint-dev__pylint-7993

项目：pylint-dev/pylint；本轮子集：开发集；状态：complete。

问题描述节选：

> Using custom braces in message template does not work
> ### Bug description
> 
> Have any list of errors:
> 
> On pylint 1.7 w/ python3.6 - I am able to use this as my message template
> ```
> $ pylint test.py --msg-template='{{ "Category": "{category}" }}'
> No config file found, using default configuration
> ************* Module [redacted].test
> { "Category": "convention" }
> { "Category": "error" }
> { "Category": "error" }
> { "Category": "convention" }
> { "Category": "convention" }
> { "Category": "convention" }
> { "Category": "error" }
> ```
> 
> However, on Python3.9 with Pylint 2.12.2, I get the following:
> ```
> $ pylint test.py --msg-template='{{ "Category": "{category}" }}'
> [redacted]/site-packages/pylint/reporters/text.py:206: UserWarning: Don't recognize the argument '{ "Category"' in the --msg-

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["pylint/reporters/text.py", "TextReporter.on_set_current_module"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=15848/2517；耗时=196.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pylint-dev__pylint-7993.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pylint-dev__pylint-7993.jsonl)

## 168. pytest-dev__pytest-11143

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Rewrite fails when first expression of file is a number and mistaken as docstring 
> <!--
> Thanks for submitting an issue!
> 
> Quick check-list while reporting bugs:
> -->
> 
> - [x] a detailed description of the bug or problem you are having
> - [x] output of `pip list` from the virtual environment you are using
> - [x] pytest and operating system versions
> - [x] minimal example if possible
> ```
> Installing collected packages: zipp, six, PyYAML, python-dateutil, MarkupSafe, importlib-metadata, watchdog, tomli, soupsieve, pyyaml-env-tag, pycparser, pluggy, packaging, mergedeep, Markdown, jinja2, iniconfig, ghp-import, exceptiongroup, click, websockets, urllib3, tqdm, smmap, pytest, pyee, mkdocs, lxml, importlib-resources, idna, cssselect, charset-normalizer, cffi, certifi, beautifulsoup4, attrs, a

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/assertion/rewrite.py", "AssertionRewriter.run"]]`

新预测：`[["testing/test_assertion.py", "callequal"], ["testing/test_assertion.py", "callop"], ["testing/test_assertion.py", "mock_config"], ["testing/test_assertion.py", "test_AssertionError_message"], ["testing/test_assertion.py", "test_assert_indirect_tuple_no_warning"], ["testing/test_assertion.py", "test_assert_tuple_warning"], ["testing/test_assertion.py", "test_assert_with_unicode"], ["testing/test_assertion.py", "test_assertion_location_with_coverage"], ["testing/test_assertion.py", "test_assertion_options"], ["testing/test_assertion.py", "test_assertrepr_loaded_per_dir"], ["testing/test_assertion.py", "test_diff_newline_at_end"], ["testing/test_assertion.py", "test_exception_handling_no_traceback"], ["testing/test_assertion.py", "test_exit_from_assertrepr_compare"], ["testing/test_assertion.py", "test_issue_1944"], ["testing/test_assertion.py", "test_pytest_assertrepr_compare_integration"], ["testing/test_assertion.py", "test_python25_compile_issue257"], ["testing/test_assertion.py", "test_raise_assertion_error_raising_repr"], ["testing/test_assertion.py", "test_raise_unprintable_assertion_error"], ["testing/test_assertion.py", "test_recursion_source_decode"], ["testing/test_assertion.py", "test_reprcompare_notin"], ["testing/test_assertion.py", "test_reprcompare_verbose_long"], ["testing/test_assertion.py", "test_reprcompare_whitespaces"], ["testing/test_assertion.py", "test_rewritten"], ["testing/test_assertion.py", "test_sequence_comparison_uses_repr"], ["testing/test_assertion.py", "test_traceback_failure"], ["testing/test_assertion.py", "test_triple_quoted_string_issue113"], ["testing/test_assertion.py", "test_warn_missing"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=111180/4709；耗时=540.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 179}`。

- A1：Incorrect computation；依据：；关联：`[["testing/test_assertion.py", "SimpleDataObjectOne"]]`
- A：Inaccurate recursive check；依据：；关联：`[["testing/test_assertion.py", "test_assertion.py"]]`
- A2：Docstring misinterpretation；依据：；关联：`[["testing/test_assertion.py", "SimpleDataObjectOne"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "test_assert_indirect_tuple_no_warning"], ["testing/test_assertion.py", "test_reprcompare_verbose_long"], ["testing/test_assertion.py", "callequal"], ["testing/test_assertion.py", "TestImportHookInstallation"], ["testing/test_assertion.py", "test_exception_handling_no_traceback"], ["testing/test_assertion.py", "test_exit_from_assertrepr_compare"], ["testing", "testing"], ["testing/test_assertion.py", "callop"], ["testing/test_assertion.py", "test_traceback_failure"], ["testing/test_assertion.py", "test_assertion_location_with_coverage"], ["testing/test_assertion.py", "test_recursion_source_decode"], ["testing/test_assertion.py", "test_pytest_assertrepr_compare_integration"], ["testing/test_assertion.py", "TestTruncateExplanation"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "test_raise_assertion_error_raising_repr"], ["testing/test_assertion.py", "test_AssertionError_message"], ["testing/test_assertion.py", "test_sequence_comparison_uses_repr"], ["testing/test_assertion.py", "test_triple_quoted_string_issue113"], ["testing/test_assertion.py", "OtherDataObject"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "A"], ["src/_pytest/outcomes.py", "outcomes.py"], ["testing/test_assertion.py", "test_rewritten"], ["testing/test_assertion.py", "test_diff_newline_at_end"], ["testing/test_assertion.py", "test_assertion_options"], ["testing/test_assertion.py", "test_assertrepr_loaded_per_dir"], ["testing/test_assertion.py", "TestAssert_reprcompare_dataclass"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "OtherDataObject"], ["src/_pytest/monkeypatch.py", "monkeypatch.py"], ["testing/test_assertion.py", "Config"], ["testing/test_assertion.py", "TestAssert_reprcompare_namedtuple"], ["testing/test_assertion.py", "TestBinReprIntegration"], ["testing/test_assertion.py", "SimpleDataObjectTwo"], ["testing/test_assertion.py", "TestSequence"], ["src/_pytest/assertion/truncate.py", "truncate.py"], ["testing/test_assertion.py", "test_reprcompare_notin"], ["testing/test_assertion.py", "test_reprcompare_whitespaces"], ["src/_pytest/assertion/util.py", "util.py"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "A"], ["src/_pytest/pytester.py", "pytester.py"], ["testing/test_assertion.py", "test_python25_compile_issue257"], ["testing/test_assertion.py", "mock_config"], ["testing/test_assertion.py", "A"], ["testing/test_assertion.py", "test_issue_1944"], ["testing/test_assertion.py", "TestAssert_reprcompare"], ["testing/test_assertion.py", "TestAssert_reprcompare_attrsclass"], ["testing/test_assertion.py", "SimpleDataObject"], ["testing/test_assertion.py", "test_assert_with_unicode"], ["testing/test_assertion.py", "test_assert_tuple_warning"], ["testing/test_assertion.py", "test_warn_missing"], ["testing/test_assertion.py", "TestFormatExplanation"], ["testing/test_assertion.py", "test_raise_unprintable_assertion_error"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-11143.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-11143.jsonl)

## 169. pytest-dev__pytest-11148

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Module imported twice under import-mode=importlib
> In pmxbot/pmxbot@7f189ad, I'm attempting to switch pmxbot off of pkg_resources style namespace packaging to PEP 420 namespace packages. To do so, I've needed to switch to `importlib` for the `import-mode` and re-organize the tests to avoid import errors on the tests.
> 
> Yet even after working around these issues, the tests are failing when the effect of `core.initialize()` doesn't seem to have had any effect.
> 
> Investigating deeper, I see that initializer is executed and performs its actions (setting a class variable `pmxbot.logging.Logger.store`), but when that happens, there are two different versions of `pmxbot.logging` present, one in `sys.modules` and another found in `tests.unit.test_commands.logging`:
> 
> ```
> =======================

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/pathlib.py", "import_path"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=11671/2207；耗时=168.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 6}`。

- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/logging.py", "logging.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-11148.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-11148.jsonl)

## 170. pytest-dev__pytest-5103

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Unroll the iterable for all/any calls to get better reports
> Sometime I need to assert some predicate on all of an iterable, and for that the builtin functions `all`/`any` are great - but the failure messages aren't useful at all!
> For example - the same test written in three ways:
> 
> - A generator expression
> ```sh                                                                                                                                                                                                                         
>     def test_all_even():
>         even_stevens = list(range(1,100,2))
> >       assert all(is_even(number) for number in even_stevens)
> E       assert False
> E        +  where False = all(<generator object test_all_even.<locals>.<genexpr> at 0x101f82ed0>)
> ```
> - A 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/assertion/rewrite.py", "AssertionRewriter._visit_all"], ["src/_pytest/assertion/rewrite.py", "AssertionRewriter.visit_Call_35"], ["src/_pytest/assertion/rewrite.py", "AssertionRewriter.visit_Call_legacy"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=7540/880；耗时=66.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-5103.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-5103.jsonl)

## 171. pytest-dev__pytest-5221

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Display fixture scope with `pytest --fixtures`
> It would be useful to show fixture scopes with `pytest --fixtures`; currently the only way to learn the scope of a fixture is look at the docs (when that is documented) or at the source code.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/python.py", "_showfixtures_main"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=9448/2058；耗时=153.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-5221.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-5221.jsonl)

## 172. pytest-dev__pytest-5227

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Improve default logging format
> Currently it is:
> 
> > DEFAULT_LOG_FORMAT = "%(filename)-25s %(lineno)4d %(levelname)-8s %(message)s"
> 
> I think `name` (module name) would be very useful here, instead of just the base filename.
> 
> (It might also be good to have the relative path there (maybe at the end), but it is usually still very long (but e.g. `$VIRTUAL_ENV` could be substituted therein))
> 
> Currently it would look like this:
> ```
> utils.py                   114 DEBUG    (0.000) SELECT "app_url"."id", "app_url"."created", "app_url"."url" FROM "app_url" WHERE "app_url"."id" = 2; args=(2,)
> multipart.py               604 DEBUG    Calling on_field_start with no data
> ```
> 
> 
> Using `DEFAULT_LOG_FORMAT = "%(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s"` instead:
> 
> ```
> DEBUG  

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=10129/2185；耗时=154.7秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Improper log format configuration；依据：；关联：`[]`
- B：Lack of module name inclusion in log format；依据：；关联：`[]`
- C：Use of absolute file paths in log format；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-5227.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-5227.jsonl)

## 173. pytest-dev__pytest-5413

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> str() on the pytest.raises context variable doesn't behave same as normal exception catch
> Pytest 4.6.2, macOS 10.14.5
> 
> ```Python
> try:
>     raise LookupError(
>         f"A\n"
>         f"B\n"
>         f"C"
>     )
> except LookupError as e:
>     print(str(e))
> ```
> prints
> 
> > A
> > B
> > C
> 
> But
> 
> ```Python
> with pytest.raises(LookupError) as e:
>     raise LookupError(
>         f"A\n"
>         f"B\n"
>         f"C"
>     )
> 
> print(str(e))
> ```
> 
> prints
> 
> > <console>:3: LookupError: A
> 
> In order to get the full error message, one must do `str(e.value)`, which is documented, but this is a different interaction. Any chance the behavior could be changed to eliminate this gotcha?
> 
> -----
> 
> Pip list gives
> 
> ```
> Package            Version  Location
> ------------------ -------- -------------

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |

共同严格目标：`[["src/_pytest/_code/code.py", "ExceptionInfo.__str__"]]`

新预测：`[["src/_pytest/_code/code.py", "ExceptionInfo.__str__"], ["src/_pytest/_code/code.py", "ExceptionInfo.exconly"], ["src/_pytest/_code/code.py", "ExceptionInfo.from_current"], ["src/_pytest/_code/code.py", "ExceptionInfo.getrepr"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=85759/32510；耗时=3000.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["src/_pytest/_code/code.py", "ExceptionInfo.__str__"]], "seeds": [["src/_pytest/_code/code.py", "ExceptionInfo.__str__"]], "causal_received": [["src/_pytest/_code/code.py", "ExceptionInfo.__str__"]], "final": [["src/_pytest/_code/code.py", "ExceptionInfo.__str__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 7, "causal": 32}`。

- A1：Inaccurate recursive check；依据：；关联：`[["", "self._excinfo"]]`
- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.__str__"]]`
- A2：Wrong logic；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo"]]`
- G：ReprTracebackNative class；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.getrepr"]]`
- H：self.tb field；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.from_current"]]`
- J：from_current function；依据：；关联：`[["", "self.type"]]`
- K：traceback function；依据：；关联：`[["src/_pytest/_code/code.py", "code.py"]]`
- L：self.type field；依据：；关联：`[["", "self.value"]]`
- M：self.value field；依据：；关联：`[["", "self.value,"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["src/_pytest/fixtures.py", "FixtureLookupErrorRepr"]]`
- C：Dependency on Product；依据：；关联：`[["src/_pytest/fixtures.py", "FixtureLookupErrorRepr"]]`
- D：self._excinfo；依据：；关联：`[["", "self._excinfo"]]`
- E：self.traceback；依据：；关联：`[["", "self.traceback"]]`
- F：exconly method；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.exconly"]]`
- N：exconly method called with tryshort=True；依据：；关联：`[]`
- O：str(pytest.raises) prints simplified traceback；依据：；关联：`[]`
- P：exconly method removes 'AssertionError:' prefix；依据：；关联：`[]`
- Q：exconly method truncates traceback after first 'def' line；依据：；关联：`[]`
- R：exconly method formats exception as a string；依据：；关联：`[]`
- S：exconly method is called in str(pytest.raises)；依据：；关联：`[]`
- T：exconly method is called in str(ExceptionInfo)；依据：；关联：`[]`
- U：exconly method is experimental；依据：；关联：`[]`
- V：exconly method is used to determine if exception should be stripped；依据：；关联：`[]`
- W：exconly method is used to format exception representation；依据：；关联：`[]`
- X：exconly method is used to handle traceback information；依据：；关联：`[]`
- Y：exconly method is used to handle exception details；依据：；关联：`[]`
- Z：exconly method is used to handle exception formatting；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-5413.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-5413.jsonl)

## 174. pytest-dev__pytest-5495

项目：pytest-dev/pytest；本轮子集：开发集；状态：complete。

问题描述节选：

> Confusing assertion rewriting message with byte strings
> The comparison with assertion rewriting for byte strings is confusing: 
> ```
>     def test_b():
> >       assert b"" == b"42"
> E       AssertionError: assert b'' == b'42'
> E         Right contains more items, first extra item: 52
> E         Full diff:
> E         - b''
> E         + b'42'
> E         ?   ++
> ```
> 
> 52 is the ASCII ordinal of "4" here.
> 
> It became clear to me when using another example:
> 
> ```
>     def test_b():
> >       assert b"" == b"1"
> E       AssertionError: assert b'' == b'1'
> E         Right contains more items, first extra item: 49
> E         Full diff:
> E         - b''
> E         + b'1'
> E         ?   +
> ```
> 
> Not sure what should/could be done here.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/assertion/util.py", "_compare_eq_sequence"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4748/1019；耗时=105.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-5495.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-5495.jsonl)

## 175. pytest-dev__pytest-5692

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Hostname and timestamp properties in generated JUnit XML reports
> Pytest enables generating JUnit XML reports of the tests.
> 
> However, there are some properties missing, specifically `hostname` and `timestamp` from the `testsuite` XML element. Is there an option to include them?
> 
> Example of a pytest XML report:
> ```xml
> <?xml version="1.0" encoding="utf-8"?>
> <testsuite errors="0" failures="2" name="check" skipped="0" tests="4" time="0.049">
> 	<testcase classname="test_sample.TestClass" file="test_sample.py" line="3" name="test_addOne_normal" time="0.001"></testcase>
> 	<testcase classname="test_sample.TestClass" file="test_sample.py" line="6" name="test_addOne_edge" time="0.001"></testcase>
> </testsuite>
> ```
> 
> Example of a junit XML report:
> ```xml
> <?xml version="1.0" encoding="UTF-8"

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/junitxml.py", "LogXML.pytest_sessionfinish"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11610/2165；耗时=160.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-5692.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-5692.jsonl)

## 176. pytest-dev__pytest-6116

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> pytest --collect-only needs a one char shortcut command
> I find myself needing to run `--collect-only` very often and that cli argument is a very long to type one. 
> 
> I do think that it would be great to allocate a character for it, not sure which one yet. Please use up/down thumbs to vote if you would find it useful or not and eventually proposing which char should be used. 
> 
> Clearly this is a change very easy to implement but first I want to see if others would find it useful or not.
> pytest --collect-only needs a one char shortcut command
> I find myself needing to run `--collect-only` very often and that cli argument is a very long to type one. 
> 
> I do think that it would be great to allocate a character for it, not sure which one yet. Please use up/down thumbs to vote if you would fin

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/main.py", "pytest_addoption"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=2404/313；耗时=27.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-6116.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-6116.jsonl)

## 177. pytest-dev__pytest-7168

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> INTERNALERROR when exception in __repr__
> Minimal code to reproduce the issue: 
> ```python
> class SomeClass:
>     def __getattribute__(self, attr):
>         raise
>     def __repr__(self):
>         raise
> def test():
>     SomeClass().attr
> ```
> Session traceback:
> ```
> ============================= test session starts ==============================
> platform darwin -- Python 3.8.1, pytest-5.4.1, py-1.8.1, pluggy-0.13.1 -- /usr/local/opt/python@3.8/bin/python3.8
> cachedir: .pytest_cache
> rootdir: ******
> plugins: asyncio-0.10.0, mock-3.0.0, cov-2.8.1
> collecting ... collected 1 item
> 
> test_pytest.py::test 
> INTERNALERROR> Traceback (most recent call last):
> INTERNALERROR>   File "/usr/local/lib/python3.8/site-packages/_pytest/main.py", line 191, in wrap_session
> INTERNALERROR>     session.ex

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/_io/saferepr.py", "_format_repr_exception"]]`

新预测：`[["doc/en/example/assertion/failure_demo.py", "<unresolved>:JSON.__repr__"], ["src/_pytest/python_api.py", "ApproxMapping.__repr__"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=37933/3063；耗时=233.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 32, "causal": 6}`。

无法唯一映射的函数：`[{"file": "doc/en/example/assertion/failure_demo.py", "name": "JSON.__repr__", "reason": "absent"}]`

- A：Inaccurate recursive check；依据：；关联：`[["doc/en/example/assertion/failure_demo.py", "JSON.__repr__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["src/_pytest/python_api.py", "ApproxMapping.__repr__"]]`
- C：Dependency on Product；依据：；关联：`[["src/_pytest/python_api.py", "ApproxMapping.__repr__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-7168.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-7168.jsonl)

## 178. pytest-dev__pytest-7220

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Wrong path to test file when directory changed in fixture
> Files are shown as relative to new directory when working directory is changed in a fixture. This makes it impossible to jump to the error as the editor is unaware of the directory change. The displayed directory should stay relative to the original directory.
> 
> test_path_error.py:
> ```python
> import os
> import errno
> import shutil
> 
> import pytest
> 
> 
> @pytest.fixture
> def private_dir():  # or (monkeypatch)
>     out_dir = 'ddd'
> 
>     try:
>         shutil.rmtree(out_dir)
>     except OSError as ex:
>         if ex.errno != errno.ENOENT:
>             raise
>     os.mkdir(out_dir)
> 
>     old_dir = os.getcwd()
>     os.chdir(out_dir)
>     yield out_dir
>     os.chdir(old_dir)
> 
>     # Same issue if using:
>     # monkeypatch.chdir(out_dir)

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/nodes.py", "Node._repr_failure_py"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=21088/3102；耗时=236.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-7220.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-7220.jsonl)

## 179. pytest-dev__pytest-7373

项目：pytest-dev/pytest；本轮子集：开发集；状态：complete。

问题描述节选：

> Incorrect caching of skipif/xfail string condition evaluation
> Version: pytest 5.4.3, current master
> 
> pytest caches the evaluation of the string in e.g. `@pytest.mark.skipif("sys.platform == 'win32'")`. The caching key is only the string itself (see `cached_eval` in `_pytest/mark/evaluate.py`). However, the evaluation also depends on the item's globals, so the caching can lead to incorrect results. Example:
> 
> ```py
> # test_module_1.py
> import pytest
> 
> skip = True
> 
> @pytest.mark.skipif("skip")
> def test_should_skip():
>     assert False
> ```
> 
> ```py
> # test_module_2.py
> import pytest
> 
> skip = False
> 
> @pytest.mark.skipif("skip")
> def test_should_not_skip():
>     assert False
> ```
> 
> Running `pytest test_module_1.py test_module_2.py`.
> 
> Expected: `test_should_skip` is skipped, `test_sh

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 40.00% | 66.67% | 50.00% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 18.18% | 66.67% | 28.57% | 0.00% | 命中 |

共同严格目标：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator._istrue"], ["src/_pytest/mark/evaluate.py", "cached_eval"], ["src/_pytest/mark/evaluate.py", "compiled_eval"]]`

新预测：`[["src/_pytest/_code/code.py", "Frame.eval"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator.__bool__"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator.__init__"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator._get_marks"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator._getglobals"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator._istrue"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator.get"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator.getexplanation"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator.istrue"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator.wasvalid"], ["src/_pytest/mark/evaluate.py", "cached_eval"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=74067/24323；耗时=1770.6秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["src/_pytest/mark/evaluate.py", "cached_eval"]], "seeds": [["src/_pytest/mark/evaluate.py", "cached_eval"]], "causal_received": [["src/_pytest/mark/evaluate.py", "MarkEvaluator._istrue"], ["src/_pytest/mark/evaluate.py", "cached_eval"]], "final": [["src/_pytest/mark/evaluate.py", "MarkEvaluator._istrue"], ["src/_pytest/mark/evaluate.py", "cached_eval"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 5, "causal": 25}`。

- A1：Incorrect computation；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator._istrue"]]`
- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/_code/code.py", "Frame.eval"]]`
- A2：Wrong logic；依据：；关联：`[["src/_pytest/mark/evaluate.py", "evaluate.py"]]`
- Y：BrokenObj class；依据：；关联：`[["testing/io/test_saferepr.py", "BrokenObj"]]`
- E：Global state dependency in caching；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator._getglobals"], ["src/_pytest/mark/evaluate.py", "MarkEvaluator"]]`
- M：_get_marks function；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator._get_marks"]]`
- D：Caching of skipif/xfail string condition evaluation；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["src/_pytest/mark/evaluate.py", "cached_eval"]]`
- C：Dependency on Product；依据：；关联：`[["src/_pytest/mark/evaluate.py", "cached_eval"]]`
- F：TestEvaluator class；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator.__init__"]]`
- G：self.result field；依据：；关联：`[["", "self.result"]]`
- H：self.item field；依据：；关联：`[["", "self.item,"]]`
- J：istrue function；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator.istrue"]]`
- K：wasvalid function；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator.wasvalid"]]`
- L：__bool__ function；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator.__bool__"]]`
- N：getexplanation function；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator.getexplanation"]]`
- O：get function；依据：；关联：`[["src/_pytest/mark/evaluate.py", "MarkEvaluator.get"]]`
- P：self.expr field；依据：；关联：`[["", "self.expr,"]]`
- Q：self._mark_name field；依据：；关联：`[["", "self._mark_name"]]`
- R：self.exc field；依据：；关联：`[["", "self.exc"]]`
- S：self._marks field；依据：；关联：`[["", "self._marks"]]`
- T：self._mark field；依据：；关联：`[["", "self._mark"]]`
- U：self.reason field；依据：；关联：`[["", "self.reason"]]`
- V：self.expr field；依据：；关联：`[["", "self.expr"]]`
- W：self.item field；依据：；关联：`[["", "self.item"]]`
- X：self._mark_name field；依据：；关联：`[["", "self._mark_name,"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-7373.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-7373.jsonl)

## 180. pytest-dev__pytest-7432

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> skipping: --runxfail breaks pytest.mark.skip location reporting
> pytest versions: 5.4.x, current master
> 
> When `@pytest.mark.skip`/`skipif` marks are used to skip a test, for example
> 
> ```py
> import pytest
> @pytest.mark.skip
> def test_skip_location() -> None:
>     assert 0
> ```
> 
> the expected skip location reported should point to the item itself, and this is indeed what happens when running with `pytest -rs`:
> 
> ```
> SKIPPED [1] test_it.py:3: unconditional skip
> ```
> 
> However, adding `pytest -rs --runxfail` breaks this:
> 
> ```
> SKIPPED [1] src/_pytest/skipping.py:238: unconditional skip
> ```
> 
> The `--runxfail` is only about xfail and should not affect this at all.
> 
> ---
> 
> Hint: the bug is in `src/_pytest/skipping.py`, the `pytest_runtest_makereport` hook.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/skipping.py", "pytest_runtest_makereport"]]`

新预测：`[["src/_pytest/hookspec.py", "pytest_cmdline_parse"], ["src/_pytest/hookspec.py", "pytest_configure"], ["src/_pytest/hookspec.py", "pytest_enter_pdb"], ["src/_pytest/hookspec.py", "pytest_fixture_setup"], ["src/_pytest/hookspec.py", "pytest_generate_tests"], ["src/_pytest/hookspec.py", "pytest_internalerror"], ["src/_pytest/hookspec.py", "pytest_leave_pdb"], ["src/_pytest/hookspec.py", "pytest_pycollect_makeitem"], ["src/_pytest/hookspec.py", "pytest_pyfunc_call"], ["src/_pytest/hookspec.py", "pytest_runtest_call"], ["src/_pytest/hookspec.py", "pytest_runtest_logfinish"], ["src/_pytest/hookspec.py", "pytest_runtest_makereport"], ["src/_pytest/hookspec.py", "pytest_runtestloop"], ["src/_pytest/hookspec.py", "pytest_unconfigure"], ["src/_pytest/hookspec.py", "pytest_warning_captured"], ["src/_pytest/hookspec.py", "pytest_warning_recorded"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=58021/12471；耗时=1032.0秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["src/_pytest/skipping.py", "pytest_runtest_makereport"]], "seeds": [["src/_pytest/skipping.py", "pytest_runtest_makereport"]], "causal_received": [["src/_pytest/skipping.py", "pytest_runtest_makereport"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 70}`。

- A1：Hook specification modification；依据：；关联：`[["src/_pytest/hookspec.py", "pytest_internalerror"]]`
- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/hookspec.py", "pytest_runtest_makereport"]]`
- F：Hook implementation error；依据：；关联：`[["src/_pytest/hookspec.py", "pytest_configure"], ["src/_pytest/hookspec.py", "pytest_runtestloop"], ["src/_pytest/hookspec.py", "pytest_runtest_call"], ["src/_pytest/hookspec.py", "pytest_unconfigure"], ["src/_pytest/hookspec.py", "pytest_generate_tests"], ["src/_pytest/hookspec.py", "pytest_fixture_setup"], ["src/_pytest/hookspec.py", "pytest_runtest_logfinish"], ["src/_pytest/hookspec.py", "pytest_leave_pdb"], ["src/_pytest/hookspec.py", "pytest_pyfunc_call"], ["src/_pytest/hookspec.py", "pytest_warning_recorded"], ["src/_pytest/hookspec.py", "pytest_warning_captured"], ["src/_pytest", "_pytest"], ["src/_pytest/reports.py", "reports.py"], ["src/_pytest/hookspec.py", "pytest_enter_pdb"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["src/_pytest/skipping.py", "skipping.py"]]`
- D2：Command-line flag processing error；依据：；关联：`[["src/_pytest/hookspec.py", "pytest_cmdline_parse"]]`
- E：Warning handling error；依据：；关联：`[["src/_pytest/hookspec.py", "pytest_warning_recorded"], ["src/_pytest/hookspec.py", "pytest_pycollect_makeitem"]]`
- D1：Hook specification modification；依据：；关联：`[["src/_pytest/hookspec.py", "hookspec.py"]]`
- C：Dependency on Product；依据：；关联：`[["src/_pytest/skipping.py", "skipping.py"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-7432.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-7432.jsonl)

## 181. pytest-dev__pytest-7490

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Pytest 6: Dynamically adding xfail marker in test no longer ignores failure
> <!--
> Thanks for submitting an issue!
> 
> Here's a quick checklist for what to provide:
> -->
> 
> ## Description
> 
> With pytest 5.x, we can dynamically add an xfail to a test `request` object using `request.node.add_marker(mark)` (see example below). In 5.x this treated the failing test like a a test marked statically with an `xfail`. With 6.0.0rc0 it raises. 
> 
> ## Versions
> 
> <details>
> 
> ```
> $ pip list
> Package                       Version                         Location                                                      
> ----------------------------- ------------------------------- --------------------------------------------------------------
> a                             1.0                             

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/skipping.py", "pytest_runtest_call"], ["src/_pytest/skipping.py", "pytest_runtest_setup"]]`

新预测：`[["src/_pytest/nodes.py", "<unresolved>:Node.get_closest_marker"], ["src/_pytest/nodes.py", "Node.__hash__"], ["src/_pytest/nodes.py", "Node.__init__"], ["src/_pytest/nodes.py", "Node._repr_failure_py"], ["src/_pytest/nodes.py", "Node.add_marker"], ["src/_pytest/nodes.py", "Node.addfinalizer"], ["src/_pytest/nodes.py", "Node.iter_markers"], ["src/_pytest/nodes.py", "Node.repr_failure"], ["src/_pytest/nodes.py", "Node.setup"], ["testing/test_mark.py", "test_addmarker_order"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=153579/15964；耗时=1336.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 56}`。

无法唯一映射的函数：`[{"file": "src/_pytest/nodes.py", "name": "Node.get_closest_marker", "reason": "absent"}]`

- A1：Inaccurate recursive check；依据：；关联：`[["src/_pytest/nodes.py", "Node"]]`
- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/nodes.py", "Node.add_marker"]]`
- A2：Dependency on Product；依据：；关联：`[["testing/test_mark.py", "test_addmarker_order"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D1：Changes in `get_closest_marker` implementation；依据：；关联：`[["src/_pytest/nodes.py", "Node.get_closest_marker"], ["src/_pytest/nodes.py", "Node.repr_failure"], ["src/_pytest/nodes.py", "Node.setup"], ["src/_pytest/nodes.py", "Node.iter_markers"], ["src/_pytest/nodes.py", "Node.get_closest_marker"], ["src/_pytest/nodes.py", "Node.get_closest_marker"], ["src/_pytest/nodes.py", "Node.__hash__"]]`
- D2：Changes in `add_marker` implementation；依据：；关联：`[["src/_pytest/nodes.py", "Node.get_closest_marker"], ["src/_pytest/store.py", "Store"], ["src/_pytest/nodes.py", "Node.setup"], ["src/_pytest/nodes.py", "Node.__init__"], ["src/_pytest/_code/code.py", "ExceptionInfo"], ["", "self.own_markers"], ["", "self.parent"], ["src/_pytest/nodes.py", "Node.addfinalizer"], ["", "self.config"]]`
- E1：Changes in `repr_failure` implementation；依据：；关联：`[["src/_pytest/nodes.py", "Node.get_closest_marker"], ["src/_pytest/nodes.py", "Node.repr_failure"], ["src/_pytest/nodes.py", "Node.setup"], ["src/_pytest/nodes.py", "Node._repr_failure_py"], ["src/_pytest/_code/code.py", "ExceptionInfo"], ["", "self.own_markers"], ["", "self.parent"], ["src/_pytest/nodes.py", "Node.addfinalizer"], ["", "self.config"]]`
- E2：Changes in `iter_markers` implementation；依据：；关联：`[["src/_pytest/nodes.py", "Node.get_closest_marker"], ["src/_pytest/store.py", "Store"], ["src/_pytest/nodes.py", "Node.setup"], ["src/_pytest/nodes.py", "Node.__init__"], ["src/_pytest/_code/code.py", "ExceptionInfo"], ["", "self.own_markers"], ["", "self.parent"], ["src/_pytest/nodes.py", "Node.addfinalizer"], ["", "self.config"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-7490.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-7490.jsonl)

## 182. pytest-dev__pytest-8365

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> tmpdir creation fails when the username contains illegal characters for directory names
> `tmpdir`, `tmpdir_factory` and `tmp_path_factory` rely on `getpass.getuser()` for determining the `basetemp` directory. I found that the user name returned by `getpass.getuser()` may return characters that are not allowed for directory names. This may lead to errors while creating the temporary directory.
> 
> The situation in which I reproduced this issue was while being logged in through an ssh connection into my Windows 10 x64 Enterprise version (1909) using an OpenSSH_for_Windows_7.7p1 server. In this configuration the command `python -c "import getpass; print(getpass.getuser())"` returns my domain username e.g. `contoso\john_doe` instead of `john_doe` as when logged in regularly using a local session

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/tmpdir.py", "TempPathFactory.getbasetemp"]]`

新预测：`[["src/_pytest/pytester.py", "Pytester.mkdir"], ["src/_pytest/pytester.py", "Testdir.mkdir"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=94207/5638；耗时=507.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 32, "causal": 48}`。

- A：Illegal characters in username；依据：；关联：`[["src/_pytest/pytester.py", "Pytester.mkdir"]]`
- B：Incorrect handling of domain prefix；依据：；关联：`[["src/_pytest/pytester.py", "Pytester.mkdir"]]`
- C：Dependency on `getpass.getuser()`；依据：；关联：`[["src/_pytest/pytester.py", "Pytester.mkdir"]]`
- D：Use of `WindowsPath`；依据：；关联：`[["src/_pytest/pytester.py", "Testdir.mkdir"]]`
- E：Error during directory creation；依据：；关联：`[["src/_pytest/pytester.py", "Testdir.mkdir"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-8365.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-8365.jsonl)

## 183. pytest-dev__pytest-8906

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Improve handling of skip for module level
> This is potentially about updating docs, updating error messages or introducing a new API.
> 
> Consider the following scenario:
> 
> `pos_only.py` is using Python 3,8 syntax:
> ```python
> def foo(a, /, b):
>     return a + b
> ```
> 
> It should not be tested under Python 3.6 and 3.7.
> This is a proper way to skip the test in Python older than 3.8:
> ```python
> from pytest import raises, skip
> import sys
> if sys.version_info < (3, 8):
>     skip(msg="Requires Python >= 3.8", allow_module_level=True)
> 
> # import must be after the module level skip:
> from pos_only import *
> 
> def test_foo():
>     assert foo(10, 20) == 30
>     assert foo(10, b=20) == 30
>     with raises(TypeError):
>         assert foo(a=10, b=20)
> ```
> 
> My actual test involves parameterize and

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/python.py", "Module._importtestmodule"]]`

新预测：`[["src/_pytest/outcomes.py", "skip"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=14203/5620；耗时=474.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 14}`。

- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/outcomes.py", "skip"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-8906.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-8906.jsonl)

## 184. pytest-dev__pytest-9359

项目：pytest-dev/pytest；本轮子集：验证集；状态：complete。

问题描述节选：

> Error message prints extra code line when using assert in python3.9
> <!--
> Thanks for submitting an issue!
> 
> Quick check-list while reporting bugs:
> -->
> 
> - [x] a detailed description of the bug or problem you are having
> - [x] output of `pip list` from the virtual environment you are using
> - [x] pytest and operating system versions
> - [ ] minimal example if possible
> ### Description
> I have a test like this:
> ```
> from pytest import fixture
> 
> 
> def t(foo):
>     return foo
> 
> 
> @fixture
> def foo():
>     return 1
> 
> 
> def test_right_statement(foo):
>     assert foo == (3 + 2) * (6 + 9)
> 
>     @t
>     def inner():
>         return 2
> 
>     assert 2 == inner
> 
> 
> @t
> def outer():
>     return 2
> ```
> The test "test_right_statement" fails at the first assertion,but print extra code (the "t" de

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["src/_pytest/_code/source.py", "get_statement_startend2"]]`

新预测：`[["src/_pytest/_code/code.py", "ExceptionInfo._getreprcrash"], ["src/_pytest/_code/code.py", "ExceptionInfo.exconly"], ["src/_pytest/_code/code.py", "ExceptionInfo.from_exc_info"], ["testing/code/test_excinfo.py", "test_excinfo_exconly"], ["testing/test_runner.py", "test_exception_printing_skip"], ["testing/test_runner.py", "test_pytest_fail"]]`

搜索种子 6；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=65470/12523；耗时=962.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 6, "relevance": 37, "causal": 30}`。

- D：_getreprcrash function；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo._getreprcrash"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.exconly"]]`
- E：ExceptionInfo class；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo"]]`
- F：self._striptext field；依据：；关联：`[["", "self._striptext"]]`
- G：self.type field；依据：；关联：`[["", "self.type,"]]`
- H：test_exception_printing_skip function；依据：；关联：`[["testing/test_runner.py", "test_exception_printing_skip"]]`
- J：test_excinfo_exconly function；依据：；关联：`[["testing/code/test_excinfo.py", "test_excinfo_exconly"]]`
- K：test_pytest_fail function；依据：；关联：`[["testing/test_runner.py", "test_pytest_fail"]]`
- A：Inaccurate recursive check；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.from_exc_info"]]`
- C：Dependency on Product；依据：；关联：`[["src/_pytest/_code/code.py", "ExceptionInfo.exconly"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/pytest-dev__pytest-9359.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/pytest-dev__pytest-9359.jsonl)

## 185. scikit-learn__scikit-learn-10297

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> linear_model.RidgeClassifierCV's Parameter store_cv_values issue
> #### Description
> Parameter store_cv_values error on sklearn.linear_model.RidgeClassifierCV
> 
> #### Steps/Code to Reproduce
> import numpy as np
> from sklearn import linear_model as lm
> 
> #test database
> n = 100
> x = np.random.randn(n, 30)
> y = np.random.normal(size = n)
> 
> rr = lm.RidgeClassifierCV(alphas = np.arange(0.1, 1000, 0.1), normalize = True, 
>                                          store_cv_values = True).fit(x, y)
> 
> #### Expected Results
> Expected to get the usual ridge regression model output, keeping the cross validation predictions as attribute.
> 
> #### Actual Results
> TypeError: __init__() got an unexpected keyword argument 'store_cv_values'
> 
> lm.RidgeClassifierCV actually has no parameter store_cv_values, 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/linear_model/ridge.py", "RidgeClassifierCV.__init__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=16933/2510；耗时=225.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 36, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-10297.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-10297.jsonl)

## 186. scikit-learn__scikit-learn-10508

项目：scikit-learn/scikit-learn；本轮子集：开发集；状态：complete。

问题描述节选：

> LabelEncoder transform fails for empty lists (for certain inputs)
> Python 3.6.3, scikit_learn 0.19.1
> 
> Depending on which datatypes were used to fit the LabelEncoder, transforming empty lists works or not. Expected behavior would be that empty arrays are returned in both cases.
> 
> ```python
> >>> from sklearn.preprocessing import LabelEncoder
> >>> le = LabelEncoder()
> >>> le.fit([1,2])
> LabelEncoder()
> >>> le.transform([])
> array([], dtype=int64)
> >>> le.fit(["a","b"])
> LabelEncoder()
> >>> le.transform([])
> Traceback (most recent call last):
>   File "[...]\Python36\lib\site-packages\numpy\core\fromnumeric.py", line 57, in _wrapfunc
>     return getattr(obj, method)(*args, **kwds)
> TypeError: Cannot cast array data from dtype('float64') to dtype('<U32') according to the rule 'safe'
> 
> During 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/preprocessing/label.py", "LabelEncoder.inverse_transform"], ["sklearn/preprocessing/label.py", "LabelEncoder.transform"]]`

新预测：`[["sklearn/feature_extraction/hashing.py", "FeatureHasher.transform"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=19434/2790；耗时=256.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/feature_extraction/hashing.py", "FeatureHasher.transform"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-10508.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-10508.jsonl)

## 187. scikit-learn__scikit-learn-10949

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：failed。

问题描述节选：

> warn_on_dtype with DataFrame
> #### Description
> 
> ``warn_on_dtype`` has no effect when input is a pandas ``DataFrame``
> 
> #### Steps/Code to Reproduce
> ```python
> from sklearn.utils.validation import check_array
> import pandas as pd
> df = pd.DataFrame([[1, 2, 3], [2, 3, 4]], dtype=object)
> checked = check_array(df, warn_on_dtype=True)
> ```
> 
> #### Expected result: 
> 
> ```python-traceback
> DataConversionWarning: Data with input dtype object was converted to float64.
> ```
> 
> #### Actual Results
> No warning is thrown
> 
> #### Versions
> Linux-4.4.0-116-generic-x86_64-with-debian-stretch-sid
> Python 3.6.3 |Anaconda, Inc.| (default, Nov  3 2017, 19:19:16) 
> [GCC 7.2.0]
> NumPy 1.13.1
> SciPy 0.19.1
> Scikit-Learn 0.20.dev0
> Pandas 0.21.0
> 
> warn_on_dtype with DataFrame
> #### Description
> 
> ``warn_on_dt

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/utils/validation.py", "check_array"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=7829/187；耗时=46.1秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["sklearn/utils/validation.py", "check_array"]], "seeds": [], "causal_received": [["sklearn/utils/validation.py", "check_array"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 1}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/scikit-learn__scikit-learn-10949.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-10949.jsonl)

## 188. scikit-learn__scikit-learn-11040

项目：scikit-learn/scikit-learn；本轮子集：开发集；状态：complete。

问题描述节选：

> Missing parameter validation in Neighbors estimator for float n_neighbors
> ```python
> from sklearn.neighbors import NearestNeighbors
> from sklearn.datasets import make_blobs
> X, y = make_blobs()
> neighbors = NearestNeighbors(n_neighbors=3.)
> neighbors.fit(X)
> neighbors.kneighbors(X)
> ```
> ```
> ~/checkout/scikit-learn/sklearn/neighbors/binary_tree.pxi in sklearn.neighbors.kd_tree.NeighborsHeap.__init__()
> 
> TypeError: 'float' object cannot be interpreted as an integer
> ```
> This should be caught earlier and a more helpful error message should be raised (or we could be lenient and cast to integer, but I think a better error might be better).
> 
> We need to make sure that 
> ```python
> neighbors.kneighbors(X, n_neighbors=3.)
> ```
> also works.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/neighbors/base.py", "KNeighborsMixin.kneighbors"], ["sklearn/neighbors/base.py", "NeighborsBase._fit"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11977/2550；耗时=204.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 31, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-11040.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-11040.jsonl)

## 189. scikit-learn__scikit-learn-11281

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> Should mixture models have a clusterer-compatible interface
> Mixture models are currently a bit different. They are basically clusterers, except they are probabilistic, and are applied to inductive problems unlike many clusterers. But they are unlike clusterers in API:
> * they have an `n_components` parameter, with identical purpose to `n_clusters`
> * they do not store the `labels_` of the training data
> * they do not have a `fit_predict` method
> 
> And they are almost entirely documented separately.
> 
> Should we make the MMs more like clusterers?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/mixture/base.py", "BaseMixture.fit"], ["sklearn/mixture/base.py", "BaseMixture.fit_predict"]]`

新预测：`[["sklearn/base.py", "ClusterMixin.fit_predict"], ["sklearn/mixture/gmm.py", "_GMMBase.fit_predict"]]`

搜索种子 12；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=23617/3062；耗时=339.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 12, "relevance": 21, "causal": 16}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/mixture/gmm.py", "_GMMBase.fit_predict"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sklearn/base.py", "ClusterMixin.fit_predict"]]`
- C：Dependency on Product；依据：；关联：`[["sklearn/base.py", "ClusterMixin.fit_predict"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-11281.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-11281.jsonl)

## 190. scikit-learn__scikit-learn-12471

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> OneHotEncoder ignore unknown error when categories are strings 
> #### Description
> 
> This bug is very specific, but it happens when you set OneHotEncoder to ignore unknown entries.
> and your labels are strings. The memory of the arrays is not handled safely and it can lead to a ValueError
> 
> Basically, when you call the transform method it will sets all the unknown strings on your array to OneHotEncoder.categories_[i][0] which is the first category alphabetically sorted given for fit
> If this OneHotEncoder.categories_[i][0] is a long string, and the array that you want to transform has small strings, then it is impossible to fit the whole  OneHotEncoder.categories_[i][0] into the entries of the array we want to transform. So  OneHotEncoder.categories_[i][0]  is truncated and this raise the 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/preprocessing/_encoders.py", "_BaseEncoder._transform"]]`

新预测：`[["sklearn/preprocessing/_encoders.py", "OneHotEncoder.fit_transform"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=56953/6207；耗时=496.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 98, "causal": 12}`。

- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["sklearn/preprocessing/_encoders.py", "OneHotEncoder.fit_transform"]]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-12471.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-12471.jsonl)

## 191. scikit-learn__scikit-learn-13142

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> GaussianMixture predict and fit_predict disagree when n_init>1
> #### Description
> When `n_init` is specified in GaussianMixture, the results of fit_predict(X) and predict(X) are often different.  The `test_gaussian_mixture_fit_predict` unit test doesn't catch this because it does not set `n_init`.
> 
> #### Steps/Code to Reproduce
> ```
> python
> from sklearn.mixture import GaussianMixture
> from sklearn.utils.testing import assert_array_equal
> import numpy
> X = numpy.random.randn(1000,5)
> print 'no n_init'
> gm = GaussianMixture(n_components=5)
> c1 = gm.fit_predict(X)
> c2 = gm.predict(X)
> assert_array_equal(c1,c2)
> print 'n_init=5'
> gm = GaussianMixture(n_components=5, n_init=5)
> c1 = gm.fit_predict(X)
> c2 = gm.predict(X)
> assert_array_equal(c1,c2)
> ```
> 
> #### Expected Results
> ```
> no n_init

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/mixture/base.py", "BaseMixture.fit_predict"]]`

新预测：`[["sklearn/base.py", "ClusterMixin.fit_predict"], ["sklearn/tests/test_pipeline.py", "FitParamT.fit_predict"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=39466/6335；耗时=490.4秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["sklearn/mixture/base.py", "BaseMixture.fit_predict"]], "seeds": [["sklearn/mixture/base.py", "BaseMixture.fit_predict"]], "causal_received": [["sklearn/mixture/base.py", "BaseMixture.fit_predict"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 41, "causal": 12}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/base.py", "ClusterMixin.fit_predict"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sklearn/tests/test_pipeline.py", "FitParamT.fit_predict"]]`
- C：Dependency on Product；依据：；关联：`[["sklearn/tests/test_pipeline.py", "FitParamT.fit_predict"]]`
- D：Test fit_predict on pipeline；依据：；关联：`[]`
- E：Test k-means fit_predict；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-13142.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13142.jsonl)

## 192. scikit-learn__scikit-learn-13241

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> Differences among the results of KernelPCA with rbf kernel
> Hi there,
> I met with a problem:
> 
> #### Description
> When I run KernelPCA for dimension reduction for the same datasets, the results are different in signs.
> 
> #### Steps/Code to Reproduce
> Just to reduce the dimension to 7 with rbf kernel:
> pca = KernelPCA(n_components=7, kernel='rbf', copy_X=False, n_jobs=-1)
> pca.fit_transform(X)
> 
> #### Expected Results
> The same result.
> 
> #### Actual Results
> The results are the same except for their signs:(
> [[-0.44457617 -0.18155886 -0.10873474  0.13548386 -0.1437174  -0.057469	0.18124364]] 
> 
> [[ 0.44457617  0.18155886  0.10873474 -0.13548386 -0.1437174  -0.057469 -0.18124364]] 
> 
> [[-0.44457617 -0.18155886  0.10873474  0.13548386  0.1437174   0.057469  0.18124364]] 
> 
> #### Versions
> 0.1

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/decomposition/kernel_pca.py", "KernelPCA._fit_transform"]]`

新预测：`[["sklearn/decomposition/kernel_pca.py", "KernelPCA.fit_transform"], ["sklearn/externals/joblib/parallel.py", "Parallel.__call__"]]`

搜索种子 7；搜索停止=search_round_limit；因果停止=legacy_causal_stop；输入/输出token=75739/12201；耗时=889.6秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sklearn/decomposition/kernel_pca.py", "KernelPCA._fit_transform"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 7, "relevance": 100, "causal": 22}`。

- A1：Incorrect computation；依据：；关联：`[["", "self._aborting"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sklearn/decomposition/kernel_pca.py", "KernelPCA.fit_transform"]]`
- A2：Wrong logic；依据：；关联：`[["", "self._original_iterator"]]`
- D：Sign inversion during computation；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sklearn/externals/joblib/parallel.py", "Parallel.__call__"]]`
- C：Dependency on Product；依据：；关联：`[["sklearn/externals/joblib/parallel.py", "Parallel.__call__"]]`
- E：Parallel processing；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-13241.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13241.jsonl)

## 193. scikit-learn__scikit-learn-13439

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> Pipeline should implement __len__
> #### Description
> 
> With the new indexing support `pipe[:len(pipe)]` raises an error.
> 
> #### Steps/Code to Reproduce
> 
> ```python
> from sklearn import svm
> from sklearn.datasets import samples_generator
> from sklearn.feature_selection import SelectKBest
> from sklearn.feature_selection import f_regression
> from sklearn.pipeline import Pipeline
> 
> # generate some data to play with
> X, y = samples_generator.make_classification(
>     n_informative=5, n_redundant=0, random_state=42)
> 
> anova_filter = SelectKBest(f_regression, k=5)
> clf = svm.SVC(kernel='linear')
> pipe = Pipeline([('anova', anova_filter), ('svc', clf)])
> 
> len(pipe)
> ```
> 
> #### Versions
> 
> ```
> System:
>     python: 3.6.7 | packaged by conda-forge | (default, Feb 19 2019, 18:37:23)  [GCC 4.2.1 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/pipeline.py", "Pipeline.__len__"]]`

新预测：`[["sklearn/utils/tests/test_validation.py", "<unresolved>:TestNonNumericShape.__len__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=7655/1617；耗时=147.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 9, "causal": 2}`。

无法唯一映射的函数：`[{"file": "sklearn/utils/tests/test_validation.py", "name": "TestNonNumericShape.__len__", "reason": "absent"}]`

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/utils/tests/test_validation.py", "TestNonNumericShape.__len__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-13439.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13439.jsonl)

## 194. scikit-learn__scikit-learn-13496

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> Expose warm_start in Isolation forest
> It seems to me that `sklearn.ensemble.IsolationForest` supports incremental addition of new trees with the `warm_start` parameter of its parent class, `sklearn.ensemble.BaseBagging`.
> 
> Even though this parameter is not exposed in `__init__()` , it gets inherited from `BaseBagging` and one can use it by changing it to `True` after initialization. To make it work, you have to also increment `n_estimators` on every iteration. 
> 
> It took me a while to notice that it actually works, and I had to inspect the source code of both `IsolationForest` and `BaseBagging`. Also, it looks to me that the behavior is in-line with `sklearn.ensemble.BaseForest` that is behind e.g. `sklearn.ensemble.RandomForestClassifier`.
> 
> To make it more easier to use, I'd suggest t

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/ensemble/iforest.py", "IsolationForest.__init__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=17627/3854；耗时=287.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 31, "causal": 0}`。

- A1：Exposing `warm_start` in `IsolationForest.__init__()`；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Documenting `warm_start` in `IsolationForest`；依据：；关联：`[]`
- A3：Adding a test for `warm_start`；依据：；关联：`[]`
- A4：Mentioning `warm_start` in the "IsolationForest example" documentation entry；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-13496.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13496.jsonl)

## 195. scikit-learn__scikit-learn-13497

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：failed。

问题描述节选：

> Comparing string to array in _estimate_mi
> In ``_estimate_mi`` there is ``discrete_features == 'auto'`` but discrete features can be an array of indices or a boolean mask.
> This will error in future versions of numpy.
> Also this means we never test this function with discrete features != 'auto', it seems?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/feature_selection/mutual_info_.py", "_estimate_mi"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=10408/1151；耗时=123.5秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["sklearn/feature_selection/mutual_info_.py", "_estimate_mi"]], "seeds": [], "causal_received": [["sklearn/feature_selection/mutual_info_.py", "_estimate_mi"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 8}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/scikit-learn__scikit-learn-13497.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13497.jsonl)

## 196. scikit-learn__scikit-learn-13584

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> bug in print_changed_only in new repr: vector values
> ```python
> import sklearn
> import numpy as np
> from sklearn.linear_model import LogisticRegressionCV
> sklearn.set_config(print_changed_only=True)
> print(LogisticRegressionCV(Cs=np.array([0.1, 1])))
> ```
> > ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()
> 
> ping @NicolasHug 
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/utils/_pprint.py", "_changed_params"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=6993/1629；耗时=130.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 10, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-13584.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13584.jsonl)

## 197. scikit-learn__scikit-learn-13779

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> Voting estimator will fail at fit if weights are passed and an estimator is None
> Because we don't check for an estimator to be `None` in `sample_weight` support, `fit` is failing`.
> 
> ```python
>     X, y = load_iris(return_X_y=True)
>     voter = VotingClassifier(
>         estimators=[('lr', LogisticRegression()),
>                     ('rf', RandomForestClassifier())]
>     )
>     voter.fit(X, y, sample_weight=np.ones(y.shape))
>     voter.set_params(lr=None)
>     voter.fit(X, y, sample_weight=np.ones(y.shape))
> ```
> 
> ```
> AttributeError: 'NoneType' object has no attribute 'fit'
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/ensemble/voting.py", "_BaseVoting.fit"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11570/2295；耗时=180.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 31, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-13779.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-13779.jsonl)

## 198. scikit-learn__scikit-learn-14087

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> IndexError thrown with LogisticRegressionCV and refit=False
> #### Description
> The following error is thrown when trying to estimate a regularization parameter via cross-validation, *without* refitting.
> 
> #### Steps/Code to Reproduce
> ```python
> import sys
> import sklearn
> from sklearn.linear_model import LogisticRegressionCV
> import numpy as np
> 
> np.random.seed(29)
> X = np.random.normal(size=(1000, 3))
> beta = np.random.normal(size=3)
> intercept = np.random.normal(size=None)
> y = np.sign(intercept + X @ beta)
> 
> LogisticRegressionCV(
> cv=5,
> solver='saga', # same error with 'liblinear'
> tol=1e-2,
> refit=False).fit(X, y)
> ```
> 
> 
> #### Expected Results
> No error is thrown. 
> 
> #### Actual Results
> ```
> ---------------------------------------------------------------------------
> IndexError

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/linear_model/logistic.py", "LogisticRegressionCV.fit"]]`

新预测：`[["sklearn/calibration.py", "CalibratedClassifierCV.fit"], ["sklearn/calibration.py", "_SigmoidCalibration.fit"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=68492/10635；耗时=869.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 63, "causal": 20}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/calibration.py", "CalibratedClassifierCV.fit"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sklearn/calibration.py", "_SigmoidCalibration.fit"]]`
- C：Dependency on Product；依据：；关联：`[["sklearn/calibration.py", "_SigmoidCalibration.fit"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-14087.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-14087.jsonl)

## 199. scikit-learn__scikit-learn-14092

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> NCA fails in GridSearch due to too strict parameter checks
> NCA checks its parameters to have a specific type, which can easily fail in a GridSearch due to how param grid is made.
> 
> Here is an example:
> ```python
> import numpy as np
> 
> from sklearn.pipeline import Pipeline
> from sklearn.model_selection import GridSearchCV
> from sklearn.neighbors import NeighborhoodComponentsAnalysis
> from sklearn.neighbors import KNeighborsClassifier
> 
> X = np.random.random_sample((100, 10))
> y = np.random.randint(2, size=100)
> 
> nca = NeighborhoodComponentsAnalysis()
> knn = KNeighborsClassifier()
> 
> pipe = Pipeline([('nca', nca),
>                  ('knn', knn)])
>                 
> params = {'nca__tol': [0.1, 0.5, 1],
>           'nca__n_components': np.arange(1, 10)}
>           
> gs = GridSearchCV(estimato

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/neighbors/nca.py", "NeighborhoodComponentsAnalysis._validate_params"]]`

新预测：`[["benchmarks/bench_plot_nmf.py", "_PGNMF.__init__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=18526/3460；耗时=268.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 31, "causal": 2}`。

- A：Inaccurate recursive check；依据：；关联：`[["benchmarks/bench_plot_nmf.py", "_PGNMF.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-14092.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-14092.jsonl)

## 200. scikit-learn__scikit-learn-14894

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> ZeroDivisionError in _sparse_fit for SVM with empty support_vectors_
> #### Description
> When using sparse data, in the case where the support_vectors_ attribute is be empty, _fit_sparse gives a ZeroDivisionError
> 
> #### Steps/Code to Reproduce
> ```
> import numpy as np
> import scipy
> import sklearn
> from sklearn.svm import SVR
> x_train = np.array([[0, 1, 0, 0],
> [0, 0, 0, 1],
> [0, 0, 1, 0],
> [0, 0, 0, 1]])
> y_train = np.array([0.04, 0.04, 0.10, 0.16])
> model = SVR(C=316.227766017, cache_size=200, coef0=0.0, degree=3, epsilon=0.1,
>   	    gamma=1.0, kernel='linear', max_iter=15000,
>   	    shrinking=True, tol=0.001, verbose=False)
> # dense x_train has no error
> model.fit(x_train, y_train)
> 
> # convert to sparse
> xtrain= scipy.sparse.csr_matrix(x_train)
> model.fit(xtrain, y_train)
> 
> ```
> ####

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]]`

新预测：`[["sklearn/impute/_base.py", "SimpleImputer._sparse_fit"], ["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=19591/4895；耗时=436.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]], "seeds": [["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]], "causal_received": [["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]], "final": [["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 8}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/impute/_base.py", "SimpleImputer._sparse_fit"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]]`
- C：Dependency on Product；依据：；关联：`[["sklearn/svm/base.py", "BaseLibSVM._sparse_fit"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-14894.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-14894.jsonl)

## 201. scikit-learn__scikit-learn-14983

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> RepeatedKFold and RepeatedStratifiedKFold do not show correct __repr__ string
> #### Description
> 
> `RepeatedKFold` and `RepeatedStratifiedKFold` do not show correct \_\_repr\_\_ string.
> 
> #### Steps/Code to Reproduce
> 
> ```python
> >>> from sklearn.model_selection import RepeatedKFold, RepeatedStratifiedKFold
> >>> repr(RepeatedKFold())
> >>> repr(RepeatedStratifiedKFold())
> ```
> 
> #### Expected Results
> 
> ```python
> >>> repr(RepeatedKFold())
> RepeatedKFold(n_splits=5, n_repeats=10, random_state=None)
> >>> repr(RepeatedStratifiedKFold())
> RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=None)
> ```
> 
> #### Actual Results
> 
> ```python
> >>> repr(RepeatedKFold())
> '<sklearn.model_selection._split.RepeatedKFold object at 0x0000016421AA4288>'
> >>> repr(RepeatedStratifiedKFold())
> '<sk

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/model_selection/_split.py", "_RepeatedSplits.__repr__"], ["sklearn/model_selection/_split.py", "_build_repr"]]`

新预测：`[["sklearn/base.py", "BaseEstimator.__repr__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=44113/5841；耗时=460.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 25, "causal": 23}`。

- D：BaseEstimator；依据：；关联：`[["sklearn/base.py", "BaseEstimator"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sklearn/base.py", "BaseEstimator.__repr__"]]`
- E：_EstimatorPrettyPrinter；依据：；关联：`[["sklearn/utils/_pprint.py", "_EstimatorPrettyPrinter"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-14983.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-14983.jsonl)

## 202. scikit-learn__scikit-learn-15512

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> Return values of non converged affinity propagation clustering
> The affinity propagation Documentation states: 
> "When the algorithm does not converge, it returns an empty array as cluster_center_indices and -1 as label for each training sample."
> 
> Example:
> ```python
> from sklearn.cluster import AffinityPropagation
> import pandas as pd
> 
> data = pd.DataFrame([[1,0,0,0,0,0],[0,1,1,1,0,0],[0,0,1,0,0,1]])
> af = AffinityPropagation(affinity='euclidean', verbose=True, copy=False, max_iter=2).fit(data)
> 
> print(af.cluster_centers_indices_)
> print(af.labels_)
> 
> ```
> I would expect that the clustering here (which does not converge) prints first an empty List and then [-1,-1,-1], however, I get [2] as cluster center and [0,0,0] as cluster labels. 
> The only way I currently know if the clustering 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/cluster/_affinity_propagation.py", "AffinityPropagation.predict"], ["sklearn/cluster/_affinity_propagation.py", "affinity_propagation"]]`

新预测：`[["sklearn/cluster/_affinity_propagation.py", "AffinityPropagation.fit"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=49866/6884；耗时=529.3秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sklearn/cluster/_affinity_propagation.py", "affinity_propagation"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 68, "causal": 8}`。

- A1：Incorrect computation；依据：；关联：`[["", "self.affinity_matrix_,"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sklearn/cluster/_affinity_propagation.py", "AffinityPropagation.fit"]]`
- A2：Wrong logic；依据：；关联：`[["", "self.labels_,"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-15512.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-15512.jsonl)

## 203. scikit-learn__scikit-learn-15535

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> regression in input validation of clustering metrics
> ```python
> from sklearn.metrics.cluster import mutual_info_score
> import numpy as np
> 
> x = np.random.choice(['a', 'b'], size=20).astype(object)
> mutual_info_score(x, x)
> ```
> ValueError: could not convert string to float: 'b'
> 
> while
> ```python
> x = np.random.choice(['a', 'b'], size=20)
> mutual_info_score(x, x)
> ```
> works with a warning?
> 
> this worked in 0.21.1 without a warning (as I think it should)
> 
> 
> Edit by @ogrisel: I removed the `.astype(object)` in the second code snippet.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/metrics/cluster/_supervised.py", "check_clusterings"]]`

新预测：`[["sklearn/metrics/cluster/_supervised.py", "mutual_info_score"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=17343/2049；耗时=200.4秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sklearn/metrics/cluster/_supervised.py", "check_clusterings"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 10}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/metrics/cluster/_supervised.py", "mutual_info_score"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-15535.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-15535.jsonl)

## 204. scikit-learn__scikit-learn-25500

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：failed。

问题描述节选：

> CalibratedClassifierCV doesn't work with `set_config(transform_output="pandas")`
> ### Describe the bug
> 
> CalibratedClassifierCV with isotonic regression doesn't work when we previously set `set_config(transform_output="pandas")`.
> The IsotonicRegression seems to return a dataframe, which is a problem for `_CalibratedClassifier`  in `predict_proba` where it tries to put the dataframe in a numpy array row `proba[:, class_idx] = calibrator.predict(this_pred)`.
> 
> ### Steps/Code to Reproduce
> 
> ```python
> import numpy as np
> from sklearn import set_config
> from sklearn.calibration import CalibratedClassifierCV
> from sklearn.linear_model import SGDClassifier
> 
> set_config(transform_output="pandas")
> model = CalibratedClassifierCV(SGDClassifier(), method='isotonic')
> model.fit(np.arange(90).resh

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 33.33% | 25.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/isotonic.py", "IsotonicRegression._transform"], ["sklearn/isotonic.py", "IsotonicRegression.predict"], ["sklearn/isotonic.py", "IsotonicRegression.transform"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=68408/15350；耗时=1266.7秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 32, "causal": 37}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/scikit-learn__scikit-learn-25500.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-25500.jsonl)

## 205. scikit-learn__scikit-learn-25570

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> ColumnTransformer with pandas output can't handle transformers with no features
> ### Describe the bug
> 
> Hi,
> 
> ColumnTransformer doesn't deal well with transformers that apply to 0 features (categorical_features in the example below) when using "pandas" as output. It seems steps with 0 features are not fitted, hence don't appear in `self._iter(fitted=True)` (_column_transformer.py l.856) and hence break the input to the `_add_prefix_for_feature_names_out` function (l.859).
> 
> 
> ### Steps/Code to Reproduce
> 
> Here is some code to reproduce the error. If you remove .set_output(transform="pandas") on the line before last, all works fine. If you remove the ("categorical", ...) step, it works fine too.
> 
> ```python
> import numpy as np
> import pandas as pd
> from lightgbm import LGBMClassifier
> f

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 16.67% | 100.00% | 28.57% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/compose/_column_transformer.py", "ColumnTransformer._hstack"]]`

新预测：`[["sklearn/compose/_column_transformer.py", "ColumnTransformer._iter"], ["sklearn/pipeline.py", "FeatureUnion._iter"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=26717/7793；耗时=607.8秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sklearn/compose/_column_transformer.py", "ColumnTransformer._hstack"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 18}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/compose/_column_transformer.py", "ColumnTransformer._iter"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sklearn/pipeline.py", "FeatureUnion._iter"]]`
- C：Dependency on Product；依据：；关联：`[["sklearn/pipeline.py", "FeatureUnion._iter"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-25570.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-25570.jsonl)

## 206. scikit-learn__scikit-learn-25638

项目：scikit-learn/scikit-learn；本轮子集：开发集；状态：failed。

问题描述节选：

> Support nullable pandas dtypes in `unique_labels`
> ### Describe the workflow you want to enable
> 
> I would like to be able to pass the nullable pandas dtypes ("Int64", "Float64", "boolean") into sklearn's `unique_labels` function. Because the dtypes become `object` dtype when converted to numpy arrays we get `ValueError: Mix type of y not allowed, got types {'binary', 'unknown'}`:
> 
> Repro with sklearn 1.2.1
> ```py 
>     import pandas as pd
>     import pytest
>     from sklearn.utils.multiclass import unique_labels
>     
>     for dtype in ["Int64", "Float64", "boolean"]:
>         y_true = pd.Series([1, 0, 0, 1, 0, 1, 1, 0, 1], dtype=dtype)
>         y_predicted = pd.Series([0, 0, 1, 1, 0, 1, 1, 1, 1], dtype="int64")
> 
>         with pytest.raises(ValueError, match="Mix type of y not allowed, got

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/utils/multiclass.py", "is_multilabel"], ["sklearn/utils/multiclass.py", "type_of_target"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=75817/11627；耗时=1077.8秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sklearn/utils/multiclass.py", "is_multilabel"], ["sklearn/utils/multiclass.py", "type_of_target"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 28}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/scikit-learn__scikit-learn-25638.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-25638.jsonl)

## 207. scikit-learn__scikit-learn-25747

项目：scikit-learn/scikit-learn；本轮子集：验证集；状态：complete。

问题描述节选：

> FeatureUnion not working when aggregating data and pandas transform output selected
> ### Describe the bug
> 
> I would like to use `pandas` transform output and use a custom transformer in a feature union which aggregates data. When I'm using this combination I got an error. When I use default `numpy` output it works fine.
> 
> ### Steps/Code to Reproduce
> 
> ```python
> import pandas as pd
> from sklearn.base import BaseEstimator, TransformerMixin
> from sklearn import set_config
> from sklearn.pipeline import make_union
> 
> index = pd.date_range(start="2020-01-01", end="2020-01-05", inclusive="left", freq="H")
> data = pd.DataFrame(index=index, data=[10] * len(index), columns=["value"])
> data["date"] = index.date
> 
> 
> class MyTransformer(BaseEstimator, TransformerMixin):
>     def fit(self, X: pd.DataFrame

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sklearn/utils/_set_output.py", "_wrap_in_pandas_container"]]`

新预测：`[["sklearn/compose/_column_transformer.py", "ColumnTransformer.fit_transform"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=84379/8246；耗时=696.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 72, "causal": 12}`。

- A：Inaccurate recursive check；依据：；关联：`[["sklearn/compose/_column_transformer.py", "ColumnTransformer.fit_transform"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- E：_validate_remainder；依据：；关联：`[]`
- D：Issue；依据：；关联：`[]`
- F：_record_output_indices；依据：；关联：`[]`
- G：_fit_transform；依据：；关联：`[]`
- H：_validate_output；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/scikit-learn__scikit-learn-25747.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/scikit-learn__scikit-learn-25747.jsonl)

## 208. sphinx-doc__sphinx-10325

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> inherited-members should support more than one class
> **Is your feature request related to a problem? Please describe.**
> I have two situations:
> - A class inherits from multiple other classes. I want to document members from some of the base classes but ignore some of the base classes
> - A module contains several class definitions that inherit from different classes that should all be ignored (e.g., classes that inherit from list or set or tuple). I want to ignore members from list, set, and tuple while documenting all other inherited members in classes in the module.
> 
> **Describe the solution you'd like**
> The :inherited-members: option to automodule should accept a list of classes. If any of these classes are encountered as base classes when instantiating autoclass documentation, they s

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 0.00% | 命中 |

共同严格目标：`[["sphinx/ext/autodoc/__init__.py", "Documenter.filter_members.is_filtered_inherited_member"], ["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]]`

新预测：`[["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=15323/2008；耗时=170.2秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]], "seeds": [["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]], "causal_received": [["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]], "final": [["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 17}`。

- D：Current implementation of inherited_members_option does not support lists of classes；依据：；关联：`[["sphinx/ext/autodoc/__init__.py", "__init__.py"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sphinx/ext/autodoc/__init__.py", "inherited_members_option"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-10325.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-10325.jsonl)

## 209. sphinx-doc__sphinx-10451

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> Fix duplicated *args and **kwargs with autodoc_typehints
> Fix duplicated *args and **kwargs with autodoc_typehints
> 
> ### Bugfix
> - Bugfix
> 
> ### Detail
> Consider this
> ```python
> class _ClassWithDocumentedInitAndStarArgs:
>     """Class docstring."""
> 
>     def __init__(self, x: int, *args: int, **kwargs: int) -> None:
>         """Init docstring.
> 
>         :param x: Some integer
>         :param *args: Some integer
>         :param **kwargs: Some integer
>         """
> ```
> when using the autodoc extension and the setting `autodoc_typehints = "description"`.
> 
> WIth sphinx 4.2.0, the current output is
> ```
> Class docstring.
> 
>    Parameters:
>       * **x** (*int*) --
> 
>       * **args** (*int*) --
> 
>       * **kwargs** (*int*) --
> 
>    Return type:
>       None
> 
>    __init__(x, *args, **kwarg

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 100.00% | 50.00% | 66.67% | 0.00% | 命中 |
| CoSIL/off | 50.00% | 50.00% | 50.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/autodoc/typehints.py", "augment_descriptions_with_types"], ["sphinx/ext/autodoc/typehints.py", "modify_field_list"]]`

新预测：`[["sphinx/addnodes.py", "_desc_classes_injector.__init__"]]`

搜索种子 9；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=29983/4481；耗时=389.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 8, "relevance": 48, "causal": 9}`。

- A：Inaccurate recursive check；依据：；关联：`[["sphinx/addnodes.py", "_desc_classes_injector.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sphinx/domains/c.py", "T"]]`
- C：Dependency on Product；依据：；关联：`[["sphinx/domains/c.py", "T"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-10451.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-10451.jsonl)

## 210. sphinx-doc__sphinx-11445

项目：sphinx-doc/sphinx；本轮子集：开发集；状态：complete。

问题描述节选：

> Using rst_prolog removes top level headings containing a domain directive
> ### Describe the bug
> 
> If `rst_prolog` is set, then any documents that contain a domain directive as the first heading (eg `:mod:`) do not render the heading correctly or include the heading in the toctree.
> 
> In the example below, if the heading of `docs/mypackage.rst` were `mypackage2` instead of `:mod:mypackage2` then the heading displays correctly.
> Similarly, if you do not set `rst_prolog` then the heading will display correctly.
> 
> This appears to have been broken for some time because I can reproduce it in v4.0.0 of Sphinx
> 
> ### How to Reproduce
> 
> ```bash
> $ sphinx-quickstart --no-sep --project mypackage --author me -v 0.1.0 --release 0.1.0 --language en docs
> $ echo -e 'Welcome\n=======\n\n.. toctree::\n\n

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/util/rst.py", "prepend_prolog"]]`

新预测：`[]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=18946/4116；耗时=381.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["doc/conf.py", "conf.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/roots/test-copyright-multiline/conf.py", "conf.py"]]`
- C：Dependency on Product；依据：；关联：`[["tests/roots/test-copyright-multiline/conf.py", "conf.py"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-11445.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-11445.jsonl)

## 211. sphinx-doc__sphinx-7686

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> autosummary: The members variable for module template contains imported members
> **Describe the bug**
> autosummary: The members variable for module template contains imported members even if autosummary_imported_members is False.
> 
> **To Reproduce**
> 
> ```
> # _templates/autosummary/module.rst
> {{ fullname | escape | underline }}
> 
> .. automodule:: {{ fullname }}
> 
>    .. autosummary::
>    {% for item in members %}
>       {{ item }}
>    {%- endfor %}
> 
> ```
> ```
> # example.py
> import os
> ```
> ```
> # index.rst
> .. autosummary::
>    :toctree: generated
> 
>    example
> ```
> ```
> # conf.py
> autosummary_generate = True
> autosummary_imported_members = False
> ```
> 
> As a result, I got following output:
> ```
> # generated/example.rst
> example
> =======
> 
> .. automodule:: example
> 
>    .. autosummary::

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 33.33% | 20.00% | 25.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 33.33% | 20.00% | 25.00% | 0.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/autosummary/generate.py", "ModuleScanner.__init__"], ["sphinx/ext/autosummary/generate.py", "ModuleScanner.get_object_type"], ["sphinx/ext/autosummary/generate.py", "ModuleScanner.is_skipped"], ["sphinx/ext/autosummary/generate.py", "ModuleScanner.scan"], ["sphinx/ext/autosummary/generate.py", "generate_autosummary_content"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=13232/1927；耗时=149.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-7686.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-7686.jsonl)

## 212. sphinx-doc__sphinx-7738

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> overescaped trailing underscore on attribute with napoleon
> **Describe the bug**
> Attribute name `hello_` shows up as `hello\_` in the html (visible backslash) with napoleon.
> 
> **To Reproduce**
> Steps to reproduce the behavior:
> 
> empty `__init__.py`
> `a.py` contains
> ```python
> class A:
>     """
>     Attributes
>     ----------
>     hello_: int
>         hi
>     """
>     pass
> ```
> run `sphinx-quickstart`
> add `'sphinx.ext.autodoc', 'sphinx.ext.napoleon'` to extensions in conf.py.
> add `.. autoclass:: a.A` to index.rst
> PYTHONPATH=. make clean html
> open _build/html/index.html in web browser and see the ugly backslash.
> 
> **Expected behavior**
> No backslash, a similar output to what I get for
> ```rst
>     .. attribute:: hello_
>         :type: int
> 
>         hi
> ```
> (the type shows up diffe

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._escape_args_and_kwargs"]]`

新预测：`[["sphinx/builders/gettext.py", "GettextRenderer.__init__"], ["sphinx/util/template.py", "SphinxRenderer.__init__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=20831/5653；耗时=410.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 10}`。

- A1：Incorrect computation；依据：；关联：`[["sphinx/builders/gettext.py", "GettextRenderer"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sphinx/builders/gettext.py", "GettextRenderer.__init__"]]`
- A2：Wrong logic；依据：；关联：`[["sphinx/util/template.py", "SphinxRenderer.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-7738.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-7738.jsonl)

## 213. sphinx-doc__sphinx-7975

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> Two sections called Symbols in index
> When using index entries with the following leading characters: _@_, _£_, and _←_ I get two sections called _Symbols_ in the HTML output, the first containing all _@_ entries before ”normal” words and the second containing _£_ and _←_ entries after the ”normal” words.  Both have the same anchor in HTML so the links at the top of the index page contain two _Symbols_ links, one before the letters and one after, but both lead to the first section.
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/environment/adapters/indexentries.py", "IndexEntries.create_index"], ["sphinx/environment/adapters/indexentries.py", "IndexEntries.create_index.keyfunc"]]`

新预测：`[]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=9132/1483；耗时=124.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 1}`。

- A：Inaccurate recursive check；依据：；关联：`[["sphinx/domains/index.py", "index.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-7975.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-7975.jsonl)

## 214. sphinx-doc__sphinx-8273

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> Generate man page section directories
> **Current man page generation does not conform to `MANPATH` search functionality**
> Currently, all generated man pages are placed in to a single-level directory: `<build-dir>/man`. Unfortunately, this cannot be used in combination with the unix `MANPATH` environment variable. The `man` program explicitly looks for man pages in section directories (such as `man/man1`, etc.). 
> 
> **Describe the solution you'd like**
> It would be great if sphinx would automatically create the section directories (e.g., `man/man1/`, `man/man3/`, etc.) and place each generated man page within appropriate section.
> 
> **Describe alternatives you've considered**
> This problem can be over come within our project’s build system, ensuring the built man pages are installed in a co

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/builders/manpage.py", "ManualPageBuilder.write"], ["sphinx/builders/manpage.py", "setup"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=3885/1387；耗时=106.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8273.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8273.jsonl)

## 215. sphinx-doc__sphinx-8282

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> autodoc_typehints does not effect to overloaded callables
> **Describe the bug**
> autodoc_typehints does not effect to overloaded callables.
> 
> **To Reproduce**
> 
> ```
> # in conf.py
> autodoc_typehints = 'none'
> ```
> ```
> # in index.rst
> .. automodule:: example
>    :members:
>    :undoc-members:
> ```
> ```
> # in example.py
> from typing import overload
> 
> 
> @overload
> def foo(x: int) -> int:
>     ...
> 
> 
> @overload
> def foo(x: float) -> float:
>     ...
> 
> 
> def foo(x):
>     return x
> ```
> 
> **Expected behavior**
> All typehints for overloaded callables are obeyed `autodoc_typehints` setting.
> 
> **Your project**
> No
> 
> **Screenshots**
> No
> 
> **Environment info**
> - OS: Mac
> - Python version: 3.8.2
> - Sphinx version: 3.1.0dev
> - Sphinx extensions: sphinx.ext.autodoc
> - Extra tools: No
> 
> **Addition

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/autodoc/__init__.py", "ClassDocumenter.format_signature"], ["sphinx/ext/autodoc/__init__.py", "FunctionDocumenter.format_signature"], ["sphinx/ext/autodoc/__init__.py", "MethodDocumenter.format_signature"]]`

新预测：`[["tests/roots/test-ext-autodoc/target/decorator.py", "foo"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=5159/1057；耗时=87.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 4, "causal": 1}`。

- A：Inaccurate recursive check；依据：；关联：`[["tests/roots/test-ext-autodoc/target/decorator.py", "foo"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8282.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8282.jsonl)

## 216. sphinx-doc__sphinx-8435

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> autodoc_type_aliases does not effect to variables and attributes
> **Describe the bug**
> autodoc_type_aliases does not effect to variables and attributes
> 
> **To Reproduce**
> 
> ```
> # example.py
> from __future__ import annotations
> 
> 
> #: blah blah blah
> var: String
> 
> 
> class MyString:
>     "mystring"
> 
>     #: blah blah blah
>     var: String
> ```
> ```
> # index.rst
> .. automodule:: example
>    :members:
>    :undoc-members:
> ```
> ```
> # conf.py
> autodoc_type_aliases = {
>     'String': 'example.MyString'
> }
> ```
> 
> **Expected behavior**
> `autodoc_type_aliases` should be applied to `example.var` and `example.MyString.var`.
> 
> **Your project**
> N/A
> 
> **Screenshots**
> N/A
> 
> **Environment info**
> - OS: Mac
> - Python version: 3.9.0
> - Sphinx version: HEAD of 3.x branch
> - Sphinx extensions: sphi

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/autodoc/__init__.py", "AttributeDocumenter.add_directive_header"], ["sphinx/ext/autodoc/__init__.py", "DataDocumenter.add_directive_header"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12209/2087；耗时=150.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8435.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8435.jsonl)

## 217. sphinx-doc__sphinx-8474

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> v3.3 upgrade started generating "WARNING: no number is assigned for table" warnings
> We've updated to Sphinx 3.3 in our documentation, and suddenly the following warning started popping up in our builds when we build either `singlehtml` or `latex`.:
> 
> `WARNING: no number is assigned for table:`
> 
> I looked through the changelog but it didn't seem like there was anything related to `numref` that was changed, but perhaps I missed something? Could anyone point me to a change in the numref logic so I can figure out where these warnings are coming from?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]]`

新预测：`[["sphinx/directives/__init__.py", "ObjectDescription.handle_signature"], ["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]]`

搜索种子 7；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=41510/3930；耗时=305.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]], "seeds": [["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]], "causal_received": [["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]], "final": [["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]]}`。

各角色实际收到显式函数体数：`{"main_search": 7, "relevance": 37, "causal": 11}`。

- A：Inaccurate recursive check；依据：；关联：`[["sphinx/directives/__init__.py", "ObjectDescription.handle_signature"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]]`
- C：Dependency on Product；依据：；关联：`[["sphinx/domains/std.py", "StandardDomain._resolve_numref_xref"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8474.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8474.jsonl)

## 218. sphinx-doc__sphinx-8506

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> Sphinx 3.2 complains about option:: syntax that earlier versions accepted
> Sphinx 3.2 complains about use of the option:: directive that earlier versions accepted without complaint.
> 
> The QEMU documentation includes this:
> ```
> .. option:: [enable=]PATTERN
> 
>    Immediately enable events matching *PATTERN*
> ```
> 
> as part of the documentation of the command line options of one of its programs. Earlier versions of Sphinx were fine with this, but Sphinx 3.2 complains:
> 
> ```
> Warning, treated as error:
> ../../docs/qemu-option-trace.rst.inc:4:Malformed option description '[enable=]PATTERN', should look like "opt", "-opt args", "--opt args", "/opt args" or "+opt args"
> ```
> 
> Sphinx ideally shouldn't change in ways that break the building of documentation that worked in older versions, because

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/domains/std.py", "Cmdoption.handle_signature"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=4855/1355；耗时=98.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8506.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8506.jsonl)

## 219. sphinx-doc__sphinx-8595

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> autodoc: empty __all__ attribute is ignored
> **Describe the bug**
> autodoc: empty `__all__` attribute is ignored
> 
> **To Reproduce**
> ```
> # example.py
> __all__ = []
> 
> 
> def foo():
>     "docstring"
> 
> 
> def bar():
>     "docstring"
> 
> 
> def baz():
>     "docstring"
> ```
> ```
> # index.rst
> .. automodule:: example
>    :members:
> ```
> 
> All foo, bar, and baz are shown.
> 
> **Expected behavior**
> No entries should be shown because `__all__` is empty.
> 
> **Your project**
> No
> 
> **Screenshots**
> No
> 
> **Environment info**
> - OS: Mac
> - Python version: 3.9.1
> - Sphinx version: HEAD of 3.x
> - Sphinx extensions: sphinx.ext.autodoc
> - Extra tools: No
> 
> **Additional context**
> No

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/autodoc/__init__.py", "ModuleDocumenter.get_object_members"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11791/1846；耗时=145.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8595.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8595.jsonl)

## 220. sphinx-doc__sphinx-8627

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> autodoc isn't able to resolve struct.Struct type annotations
> **Describe the bug**
> If `struct.Struct` is declared in any type annotations, I get `class reference target not found: Struct`
> 
> **To Reproduce**
> Simple `index.rst`
> ```
> Hello World
> ===========
> 
> code docs
> =========
> 
> .. automodule:: helloworld.helloworld
> ```
> 
> Simple `helloworld.py`
> ```
> import struct
> import pathlib
> 
> def consume_struct(_: struct.Struct) -> None:
>     pass
> 
> def make_struct() -> struct.Struct:
>     mystruct = struct.Struct('HH')
>     return mystruct
> 
> def make_path() -> pathlib.Path:
>     return pathlib.Path()
> ```
> 
> Command line:
> ```
> python3 -m sphinx -b html docs/ doc-out -nvWT
> ```
> 
> **Expected behavior**
> If you comment out the 2 functions that have `Struct` type annotations, you'll see tha

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/util/typing.py", "restify"], ["sphinx/util/typing.py", "stringify"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=11301/1979；耗时=153.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 16, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8627.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8627.jsonl)

## 221. sphinx-doc__sphinx-8713

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> napoleon_use_param should also affect "other parameters" section
> Subject: napoleon_use_param should also affect "other parameters" section
> 
> ### Problem
> Currently, napoleon always renders the Other parameters section as if napoleon_use_param was False, see source
> ```
>     def _parse_other_parameters_section(self, section):
>         # type: (unicode) -> List[unicode]
>         return self._format_fields(_('Other Parameters'), self._consume_fields())
> 
>     def _parse_parameters_section(self, section):
>         # type: (unicode) -> List[unicode]
>         fields = self._consume_fields()
>         if self._config.napoleon_use_param:
>             return self._format_docutils_params(fields)
>         else:
>             return self._format_fields(_('Parameters'), fields)
> ```
> whereas it would ma

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |

共同严格目标：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]]`

新预测：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._consume_fields"], ["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._format_fields"], ["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse"], ["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_notes_section"], ["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=47377/11729；耗时=857.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]], "seeds": [["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]], "causal_received": [["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]], "final": [["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 72}`。

- A1：Incorrect computation；依据：；关联：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_other_parameters_section"]]`
- A2：Wrong logic；依据：；关联：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._consume_fields"]]`
- D：Missing condition in _parse_other_parameters_section；依据：；关联：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse_notes_section"]]`
- E：Incorrect call to _format_fields in _parse_other_parameters_section；依据：；关联：`[["tests/test_ext_napoleon_docstring.py", "GoogleDocstringTest"]]`
- F：Incorrect call to _consume_fields in _parse_other_parameters_section；依据：；关联：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._parse"]]`
- A3：Dependency on Product；依据：；关联：`[["sphinx/ext/napoleon/docstring.py", "GoogleDocstring._format_fields"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8713.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8713.jsonl)

## 222. sphinx-doc__sphinx-8721

项目：sphinx-doc/sphinx；本轮子集：验证集；状态：complete。

问题描述节选：

> viewcode creates pages for epub even if `viewcode_enable_epub=False` on `make html epub`
> **Describe the bug**
> viewcode creates pages for epub even if `viewcode_enable_epub=False` on `make html epub`
> 
> **To Reproduce**
> ```
> $ make html epub
> ```
> 
> **Expected behavior**
> module pages should not be created for epub by default.
> 
> **Your project**
> No
> 
> **Screenshots**
> No
> 
> **Environment info**
> - OS: Mac
> - Python version: 3.9.1
> - Sphinx version: HEAD of 3.x
> - Sphinx extensions:  sphinx.ext.viewcode
> - Extra tools: No
> 
> **Additional context**
> No
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/viewcode.py", "collect_pages"]]`

新预测：`[]`

搜索种子 18；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=30762/8427；耗时=674.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 2}`。

- D1：epub_pre_files；依据：；关联：`[["doc/conf.py", "epub_pre_files"]]`
- A：Inaccurate recursive check；依据：；关联：`[["doc/conf.py", "conf.py"]]`
- D2：epub_exclude_files；依据：；关联：`[["doc/conf.py", "epub_exclude_files"]]`
- E：extensions；依据：；关联：`[["doc/conf.py", "extensions"]]`
- A1：Incorrect computation；依据：；关联：`[["doc/conf.py", "locale_dirs"]]`
- A2：Wrong logic；依据：；关联：`[["doc/conf.py", "copyright"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/roots/test-add_enumerable_node/conf.py", "conf.py"]]`
- C：Dependency on Product；依据：；关联：`[["tests/roots/test-add_enumerable_node/conf.py", "conf.py"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8721.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8721.jsonl)

## 223. sphinx-doc__sphinx-8801

项目：sphinx-doc/sphinx；本轮子集：开发集；状态：complete。

问题描述节选：

> autodoc: The annotation only member in superclass is treated as "undocumented"
> **Describe the bug**
> autodoc: The annotation only member in superclass is treated as "undocumented".
> 
> **To Reproduce**
> 
> ```
> # example.py
> class Foo:
>     """docstring"""
>     attr1: int  #: docstring
> 
> 
> class Bar(Foo):
>     """docstring"""
>     attr2: str  #: docstring
> ```
> ```
> # index.rst
> .. autoclass:: example.Bar
>    :members:
>    :inherited-members:
> ```
> 
> `Bar.attr1` is not documented. It will be shown if I give `:undoc-members:` option to the autoclass directive call. It seems the attribute is treated as undocumented.
> 
> **Expected behavior**
> It should be shown.
> 
> **Your project**
> No
> 
> **Screenshots**
> No
> 
> **Environment info**
> - OS: Mac
> - Python version: 3.9.1
> - Sphinx version: HEAD of

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sphinx/ext/autodoc/importer.py", "get_class_members"]]`

新预测：`[]`

搜索种子 9；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=32699/12053；耗时=1097.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 7}`。

- D1：Class Bar in name_mangling.py；依据：；关联：`[["tests/roots/test-ext-autodoc/target/name_mangling.py", "Bar"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["tests/roots/test-ext-autosummary-recursive/package2/module.py", "Foo"]]`
- D2：Class Bar in test_util_inspect.py；依据：；关联：`[["tests/test_util_inspect.py", "Bar"]]`
- D3：Class Bar in test.py；依据：；关联：`[["tests/roots/test-ext-inheritance_diagram/test.py", "Bar"], ["tests/roots/test-ext-inheritance_diagram/test.py", "Qux"]]`
- D4：Class Bar in instance_variable.py；依据：；关联：`[["tests/roots/test-ext-autodoc/target/instance_variable.py", "Bar"]]`
- A：Inaccurate recursive check；依据：；关联：`[["tests/roots/test-directive-code/target.py", "Foo"]]`
- C：Dependency on Product；依据：；关联：`[["tests/roots/test-ext-autosummary-recursive/package2/module.py", "Foo"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sphinx-doc__sphinx-8801.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sphinx-doc__sphinx-8801.jsonl)

## 224. sympy__sympy-11400

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> ccode(sinc(x)) doesn't work
> ```
> In [30]: ccode(sinc(x))
> Out[30]: '// Not supported in C:\n// sinc\nsinc(x)'
> ```
> 
> I don't think `math.h` has `sinc`, but it could print
> 
> ```
> In [38]: ccode(Piecewise((sin(theta)/theta, Ne(theta, 0)), (1, True)))
> Out[38]: '((Ne(theta, 0)) ? (\n   sin(theta)/theta\n)\n: (\n   1\n))'
> ```
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/ccode.py", "CCodePrinter._print_Relational"], ["sympy/printing/ccode.py", "CCodePrinter._print_sinc"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=5610/2180；耗时=175.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-11400.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-11400.jsonl)

## 225. sympy__sympy-11870

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> simplifying exponential -> trig identities
> ```
> f = 1 / 2 * (-I*exp(I*k) + I*exp(-I*k))
> trigsimp(f)
> ```
> 
> Ideally, this would yield `sin(k)`. Is there a way to do this?
> 
> As a corollary, it would be awesome if 
> 
> ```
> f = 1 / 2 / k* (-I*exp(I*k) + I*exp(-I*k))
> trigsimp(f)
> ```
> 
> could yield `sinc(k)`. Thank you for your consideration!

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/functions/elementary/trigonometric.py", "sin._eval_rewrite_as_sinc"], ["sympy/functions/elementary/trigonometric.py", "sinc._eval_rewrite_as_sin"]]`

新预测：`[["sympy/core/expr.py", "Expr.trigsimp"], ["sympy/vector/basisdependent.py", "BasisDependent.__neg__"], ["sympy/vector/basisdependent.py", "BasisDependent.__rsub__"], ["sympy/vector/basisdependent.py", "BasisDependent._eval_trigsimp"], ["sympy/vector/basisdependent.py", "BasisDependent.trigsimp"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=23878/7734；耗时=849.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 29}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent.__neg__"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.trigsimp"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent.__rsub__"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent.trigsimp"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent.trigsimp"]]`
- D：_eval_trigsimp；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent._eval_trigsimp"]]`
- E：BasisDependent；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent"]]`
- F：self.components；依据：；关联：`[["", "self.components"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-11870.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-11870.jsonl)

## 226. sympy__sympy-11897

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> LaTeX printer inconsistent with pretty printer
> The LaTeX printer should always give the same output as the pretty printer, unless better output is possible from LaTeX. In some cases it is inconsistent. For instance:
> 
> ``` py
> In [9]: var('x', positive=True)
> Out[9]: x
> 
> In [10]: latex(exp(-x)*log(x))
> Out[10]: '\\frac{1}{e^{x}} \\log{\\left (x \\right )}'
> 
> In [11]: pprint(exp(-x)*log(x))
>  -x
> ℯ  ⋅log(x)
> ```
> 
> (I also don't think the assumptions should affect printing). 
> 
> ``` py
> In [14]: var('x y')
> Out[14]: (x, y)
> 
> In [15]: latex(1/(x + y)/2)
> Out[15]: '\\frac{1}{2 x + 2 y}'
> 
> In [16]: pprint(1/(x + y)/2)
>     1
> ─────────
> 2⋅(x + y)
> ```
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._needs_mul_brackets"]]`

新预测：`[["sympy/printing/latex.py", "latex"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=56914/4774；耗时=610.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 116}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/printing/latex.py", "latex"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-11897.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-11897.jsonl)

## 227. sympy__sympy-12171

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> matematica code printer does not handle floats and derivatives correctly
> In its current state the mathematica code printer does not handle Derivative(func(vars), deriver) 
> e.g. Derivative(f(t), t) yields Derivative(f(t), t) instead of D[f[t],t]
> 
> Also floats with exponents are not handled correctly e.g. 1.0e-4 is not converted to 1.0*^-4
> 
> This has an easy fix by adding the following lines to MCodePrinter:
> 
> 
> def _print_Derivative(self, expr):
>         return "D[%s]" % (self.stringify(expr.args, ", "))
> 
> def _print_Float(self, expr):
>         res =str(expr)
>         return res.replace('e','*^') 
> 
> 
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/mathematica.py", "MCodePrinter._print_Derivative"]]`

新预测：`[["sympy/physics/vector/printing.py", "VectorStrPrinter._print_Derivative"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=31673/4607；耗时=397.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 8, "causal": 121}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/physics/vector/printing.py", "VectorStrPrinter"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/physics/vector/printing.py", "VectorStrPrinter._print_Derivative"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/printing/str.py", "StrPrinter"]]`
- D1：Correct derivative printing logic；依据：；关联：`[]`
- D2：Correct float exponent handling logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-12171.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-12171.jsonl)

## 228. sympy__sympy-12236

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Wrong result with apart
> ```
> Python 3.6.0 |Continuum Analytics, Inc.| (default, Dec 23 2016, 12:22:00) 
> Type "copyright", "credits" or "license" for more information.
> 
> IPython 5.1.0 -- An enhanced Interactive Python.
> ?         -> Introduction and overview of IPython's features.
> %quickref -> Quick reference.
> help      -> Python's own help system.
> object?   -> Details about 'object', use 'object??' for extra details.
> 
> In [1]: from sympy import symbols
> 
> In [2]: a = symbols('a', real=True)
> 
> In [3]: t = symbols('t', real=True, negative=False)
> 
> In [4]: bug = a * (-t + (-t + 1) * (2 * t - 1)) / (2 * t - 1)
> 
> In [5]: bug.subs(a, 1)
> Out[5]: (-t + (-t + 1)*(2*t - 1))/(2*t - 1)
> 
> In [6]: bug.subs(a, 1).apart()
> Out[6]: -t + 1/2 - 1/(2*(2*t - 1))
> 
> In [7]: bug.subs(a, 1).apart(t)
> O

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/polys/domains/polynomialring.py", "PolynomialRing.from_FractionField"]]`

新预测：`[["sympy/core/expr.py", "Expr.apart"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=11218/4735；耗时=396.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.apart"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-12236.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-12236.jsonl)

## 229. sympy__sympy-12419

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Sum of the elements of an identity matrix is zero
> I think this is a bug.
> 
> I created a matrix by M.T * M under an assumption that M is orthogonal.  SymPy successfully recognized that the result is an identity matrix.  I tested its identity-ness by element-wise, queries, and sum of the diagonal elements and received expected results.
> 
> However, when I attempt to evaluate the total sum of the elements the result was 0 while 'n' is expected.
> 
> ```
> from sympy import *
> from sympy import Q as Query
> 
> n = Symbol('n', integer=True, positive=True)
> i, j = symbols('i j', integer=True)
> M = MatrixSymbol('M', n, n)
> 
> e = None
> with assuming(Query.orthogonal(M)):
>     e = refine((M.T * M).doit())
> 
> # Correct: M.T * M is an identity matrix.
> print(e, e[0, 0], e[0, 1], e[1, 0], e[1, 1])
> 
> # Corr

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/expressions/matexpr.py", "Identity._entry"], ["sympy/matrices/expressions/matexpr.py", "MatrixElement._eval_derivative"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=12888/3390；耗时=266.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-12419.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-12419.jsonl)

## 230. sympy__sympy-12454

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> is_upper() raises IndexError for tall matrices
> The function Matrix.is_upper raises an IndexError for a 4x2 matrix of zeros.
> ```
> >>> sympy.zeros(4,2).is_upper
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "sympy/matrices/matrices.py", line 1112, in is_upper
>     for i in range(1, self.rows)
>   File "sympy/matrices/matrices.py", line 1113, in <genexpr>
>     for j in range(i))
>   File "sympy/matrices/dense.py", line 119, in __getitem__
>     return self.extract(i, j)
>   File "sympy/matrices/matrices.py", line 352, in extract
>     colsList = [a2idx(k, self.cols) for k in colsList]
>   File "sympy/matrices/matrices.py", line 5261, in a2idx
>     raise IndexError("Index out of range: a[%s]" % (j,))
> IndexError: Index out of range: a[2]
> ```
> The code for is_up

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/matrices.py", "MatrixProperties._eval_is_upper_hessenberg"], ["sympy/matrices/matrices.py", "MatrixProperties.is_upper"]]`

新预测：`[["sympy/matrices/dense.py", "DenseMatrix.__getitem__"], ["sympy/matrices/matrices.py", "MatrixBase.key2ij"], ["sympy/matrices/matrices.py", "MatrixShaping.extract"], ["sympy/matrices/matrices.py", "a2idx"]]`

搜索种子 6；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=60009/8419；耗时=682.4秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["sympy/matrices/matrices.py", "MatrixProperties.is_upper"]], "seeds": [["sympy/matrices/matrices.py", "MatrixProperties.is_upper"]], "causal_received": [["sympy/matrices/matrices.py", "MatrixProperties.is_upper"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 6, "relevance": 32, "causal": 33}`。

- A1：Incorrect computation；依据：；关联：`[["", "self._mat"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/dense.py", "DenseMatrix.__getitem__"]]`
- A2：Wrong logic；依据：；关联：`[["", "self.rows"]]`
- D：Accessing out-of-range index；依据：；关联：`[["", "self._mat"], ["", "self.rows"], ["sympy/matrices/matrices.py", "a2idx"], ["sympy/matrices/expressions/matexpr.py", "MatrixElement"], ["sympy/matrices/matrices.py", "MatrixBase.key2ij"], ["", "self.cols"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/matrices/matrices.py", "MatrixShaping.extract"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/matrices/matrices.py", "MatrixShaping.extract"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-12454.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-12454.jsonl)

## 231. sympy__sympy-12481

项目：sympy/sympy；本轮子集：开发集；状态：complete。

问题描述节选：

> `Permutation` constructor fails with non-disjoint cycles
> Calling `Permutation([[0,1],[0,1]])` raises a `ValueError` instead of constructing the identity permutation.  If the cycles passed in are non-disjoint, they should be applied in left-to-right order and the resulting permutation should be returned.
> 
> This should be easy to compute.  I don't see a reason why non-disjoint cycles should be forbidden.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/combinatorics/permutations.py", "Permutation.__new__"]]`

新预测：`[["sympy/categories/diagram_drawing.py", "DiagramGrid.__init__"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=74364/9947；耗时=1002.4秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sympy/combinatorics/permutations.py", "Permutation.__new__"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 32, "causal": 78}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/categories/diagram_drawing.py", "DiagramGrid.__init__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-12481.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-12481.jsonl)

## 232. sympy__sympy-13031

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Behavior of Matrix hstack and vstack changed in sympy 1.1
> In sympy 1.0:
> ```
> import sympy as sy
> M1 = sy.Matrix.zeros(0, 0)
> M2 = sy.Matrix.zeros(0, 1)
> M3 = sy.Matrix.zeros(0, 2)
> M4 = sy.Matrix.zeros(0, 3)
> sy.Matrix.hstack(M1, M2, M3, M4).shape
> ```
> returns 
> `(0, 6)`
> 
> Now, same in sympy 1.1:
> ```
> import sympy as sy
> M1 = sy.Matrix.zeros(0, 0)
> M2 = sy.Matrix.zeros(0, 1)
> M3 = sy.Matrix.zeros(0, 2)
> M4 = sy.Matrix.zeros(0, 3)
> sy.Matrix.hstack(M1, M2, M3, M4).shape
> ```
> returns
> `(0, 3)
> `
> whereas:
> ```
> import sympy as sy
> M1 = sy.Matrix.zeros(1, 0)
> M2 = sy.Matrix.zeros(1, 1)
> M3 = sy.Matrix.zeros(1, 2)
> M4 = sy.Matrix.zeros(1, 3)
> sy.Matrix.hstack(M1, M2, M3, M4).shape
> ```
> returns
> `(1, 6)
> `

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/sparse.py", "MutableSparseMatrix.col_join"], ["sympy/matrices/sparse.py", "MutableSparseMatrix.row_join"]]`

新预测：`[["sympy/matrices/common.py", "MatrixRequired._new"], ["sympy/matrices/common.py", "MatrixShaping.hstack"], ["sympy/matrices/tests/test_commonmatrix.py", "test_hstack"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=30042/8064；耗时=792.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 57}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/matrices/common.py", "MatrixShaping"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/common.py", "MatrixShaping.hstack"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/matrices/common.py", "MatrixRequired._new"]]`
- D：Test case for hstack with zero rows；依据：；关联：`[["sympy/matrices/tests/test_commonmatrix.py", "test_hstack"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- E：Changes in hstack implementation；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13031.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13031.jsonl)

## 233. sympy__sympy-13043

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> decompose() function in intpoly returns a list of arbitrary order
> The decompose() function, with separate=True, returns `list(poly_dict.values())`, which is ordered arbitrarily.  
> 
> What is this used for? It should be sorted somehow, or returning a set (in which case, why not just use the returned dictionary and have the caller take the values). This is causing test failures for me after some changes to the core. 
> 
> CC @ArifAhmed1995 @certik 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["sympy/integrals/intpoly.py", "decompose"]]`

新预测：`[["sympy/integrals/intpoly.py", "decompose"], ["sympy/sets/sets.py", "FiniteSet._sorted_args"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=19697/3169；耗时=317.9秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/integrals/intpoly.py", "decompose"]], "seeds": [["sympy/integrals/intpoly.py", "decompose"]], "causal_received": [["sympy/integrals/intpoly.py", "decompose"]], "final": [["sympy/integrals/intpoly.py", "decompose"]]}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 14, "causal": 14}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/integrals/intpoly.py", "decompose"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/sets/sets.py", "FiniteSet._sorted_args"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/sets/sets.py", "FiniteSet._sorted_args"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13043.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13043.jsonl)

## 234. sympy__sympy-13146

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Exponent doesn't fully simplify
> Say I have code like this:
> 
> ```
> import sympy
> from sympy import *
> x=Symbol('x')
> expr1 = S(1)/2*x**2.5
> expr2 = S(1)*x**(S(5)/2)/2
> res = expr1-expr2
> res= simplify(res.evalf(5))
> print res
> ```
> 
> The output is
> `-0.5*x**2.5 + 0.5*x**2.5`
> How do I simplify it to 0?
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/operations.py", "AssocOp._eval_evalf"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=26008/1286；耗时=190.1秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 27, "causal": 4}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-13146.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13146.jsonl)

## 235. sympy__sympy-13177

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Mod(x**2, x) is not (always) 0
> When the base is not an integer, `x**2 % x` is not 0. The base is not tested to be an integer in Mod's eval logic:
> 
> ```
> if (p == q or p == -q or
>         p.is_Pow and p.exp.is_Integer and p.base == q or
>         p.is_integer and q == 1):
>     return S.Zero
> ```
> 
> so
> 
> ```
> >>> Mod(x**2, x)
> 0
> ```
> but
> ```
> >>> x = S(1.5)
> >>> Mod(x**2, x)
> 0.75
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |

共同严格目标：`[["sympy/core/mod.py", "Mod.eval.doit"]]`

新预测：`[["sympy/core/mod.py", "<unresolved>:Mod.doit"], ["sympy/core/mod.py", "Mod.eval"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=56227/4088；耗时=370.4秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sympy/core/mod.py", "Mod.eval.doit"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 30, "causal": 66}`。

无法唯一映射的函数：`[{"file": "sympy/core/mod.py", "name": "Mod.doit", "reason": "absent"}]`

- A1：Incorrect computation；依据：；关联：`[["sympy/core/add.py", "Add"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/mod.py", "Mod.eval"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/core/mod.py", "Mod.doit"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13177.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13177.jsonl)

## 236. sympy__sympy-13437

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> bell(n).limit(n, oo) should be oo rather than bell(oo)
> `bell(n).limit(n,oo)` should take the value infinity, but the current output is `bell(oo)`. As the Bell numbers represent the number of partitions of a set, it seems natural that `bell(oo)` should be able to be evaluated rather than be returned unevaluated. This issue is also in line with the recent fixes to the corresponding limit for the Fibonacci numbers and Lucas numbers.
> 
> ```
> from sympy import *
> n = symbols('n')
> bell(n).limit(n,oo)
> 
> Output:
> bell(oo)
> ```
> 
> I'm new to Sympy, so I'd appreciate the opportunity to fix this bug myself if that's alright.
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 14.29% | 100.00% | 25.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/functions/combinatorial/numbers.py", "bell.eval"]]`

新预测：`[["sympy/core/expr.py", "Expr.limit"], ["sympy/core/numbers.py", "One.factors"], ["sympy/matrices/matrices.py", "MatrixCalculus.limit"], ["sympy/ntheory/factor_.py", "factorint"], ["sympy/ntheory/factor_.py", "factorrat"], ["sympy/ntheory/factor_.py", "perfect_power"], ["sympy/ntheory/factor_.py", "primefactors"], ["sympy/ntheory/tests/test_factor_.py", "test_factorint"], ["sympy/series/order.py", "Order._eval_subs"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=171060/13782；耗时=1662.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 110}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/ntheory/factor_.py", "factorint"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.limit"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/ntheory/factor_.py", "primefactors"]]`
- F2：Inadequate recursion in limit calculation；依据：；关联：`[["sympy/core/numbers.py", "One.factors"]]`
- F1：Incorrect handling of infinite limits；依据：；关联：`[["sympy/ntheory/tests/test_factor_.py", "test_factorint"], ["sympy/ntheory/factor_.py", "perfect_power"]]`
- D1：_eval_subs；依据：；关联：`[["sympy/series/order.py", "Order._eval_subs"]]`
- D2：doit；依据：；关联：`[["sympy/ntheory/factor_.py", "factorrat"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/matrices/matrices.py", "MatrixCalculus.limit"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/matrices/matrices.py", "MatrixCalculus.limit"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13437.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13437.jsonl)

## 237. sympy__sympy-13471

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Python 2->3 pickle fails with float-containing expressions
> Dumping a pickled sympy expression containing a float in Python 2, then loading it in Python 3 generates an error.
> 
> Here is a minimum working example, verified with sympy git commit 3546ac7 (master at time of writing), Python 2.7 and Python 3.6:
> 
> ```python
> python2 -c 'import pickle; import sympy; x = sympy.symbols("x"); print pickle.dumps(x + 1.0, 2)' | python3 -c 'import pickle; import sys; print(pickle.loads(sys.stdin.buffer.read()))'
> ```
> 
> and the result:
> 
> ```
> Traceback (most recent call last):
>   File "<string>", line 1, in <module>
>   File "/Users/alex/git/VU/sympy/sympy/core/numbers.py", line 1045, in __new__
>     num[1] = long(num[1], 16)
> ValueError: invalid literal for int() with base 16: '1L'
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/numbers.py", "Float.__new__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=23106/4061；耗时=337.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 37, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Float handling in SymPy expressions；依据：；关联：`[]`
- E：Version mismatch between Python 2 and Python 3；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13471.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13471.jsonl)

## 238. sympy__sympy-13480

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> .subs on coth(log(tan(x))) errors for certain integral values
>     >>> from sympy import *
>     >>> x = Symbol('x')
>     >>> e = coth(log(tan(x)))
>     >>> print(e.subs(x, 2))
>     ...
>     File "C:\Users\E\Desktop\sympy-master\sympy\functions\elementary\hyperbolic.py", line 590, in eval
>         if cotm is S.ComplexInfinity:
>     NameError: name 'cotm' is not defined
> 
> Fails for 2, 3, 5, 6, 8, 9, 11, 12, 13, 15, 18, ... etc.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/functions/elementary/hyperbolic.py", "coth.eval"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=20691/4447；耗时=340.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Odd integer input；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13480.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13480.jsonl)

## 239. sympy__sympy-13647

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Matrix.col_insert() no longer seems to work correctly.
> Example:
> 
> ```
> In [28]: import sympy as sm
> 
> In [29]: M = sm.eye(6)
> 
> In [30]: M
> Out[30]: 
> ⎡1  0  0  0  0  0⎤
> ⎢                ⎥
> ⎢0  1  0  0  0  0⎥
> ⎢                ⎥
> ⎢0  0  1  0  0  0⎥
> ⎢                ⎥
> ⎢0  0  0  1  0  0⎥
> ⎢                ⎥
> ⎢0  0  0  0  1  0⎥
> ⎢                ⎥
> ⎣0  0  0  0  0  1⎦
> 
> In [31]: V = 2 * sm.ones(6, 2)
> 
> In [32]: V
> Out[32]: 
> ⎡2  2⎤
> ⎢    ⎥
> ⎢2  2⎥
> ⎢    ⎥
> ⎢2  2⎥
> ⎢    ⎥
> ⎢2  2⎥
> ⎢    ⎥
> ⎢2  2⎥
> ⎢    ⎥
> ⎣2  2⎦
> 
> In [33]: M.col_insert(3, V)
> Out[33]: 
> ⎡1  0  0  2  2  1  0  0⎤
> ⎢                      ⎥
> ⎢0  1  0  2  2  0  1  0⎥
> ⎢                      ⎥
> ⎢0  0  1  2  2  0  0  1⎥
> ⎢                      ⎥
> ⎢0  0  0  2  2  0  0  0⎥
> ⎢                      ⎥
> ⎢0  0  0  2  2  0  0  0⎥
> ⎢    

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/common.py", "MatrixShaping._eval_col_insert.entry"]]`

新预测：`[["sympy/matrices/common.py", "MatrixShaping.col_insert"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=8099/2005；耗时=231.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/common.py", "MatrixShaping.col_insert"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13647.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13647.jsonl)

## 240. sympy__sympy-13773

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> @ (__matmul__) should fail if one argument is not a matrix
> ```
> >>> A = Matrix([[1, 2], [3, 4]])
> >>> B = Matrix([[2, 3], [1, 2]])
> >>> A@B
> Matrix([
> [ 4,  7],
> [10, 17]])
> >>> 2@B
> Matrix([
> [4, 6],
> [2, 4]])
> ```
> 
> Right now `@` (`__matmul__`) just copies `__mul__`, but it should actually only work if the multiplication is actually a matrix multiplication. 
> 
> This is also how NumPy works
> 
> ```
> >>> import numpy as np
> >>> a = np.array([[1, 2], [3, 4]])
> >>> 2*a
> array([[2, 4],
>        [6, 8]])
> >>> 2@a
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
> ValueError: Scalar operands are not allowed, use '*' instead
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 50.00% | 50.00% | 50.00% | 0.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 50.00% | 50.00% | 0.00% | 命中 |

共同严格目标：`[["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"], ["sympy/matrices/common.py", "MatrixArithmetic.__rmatmul__"]]`

新预测：`[["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"], ["sympy/matrices/common.py", "MatrixArithmetic.__mul__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=25743/7509；耗时=600.4秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"]], "seeds": [["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"]], "causal_received": [["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"], ["sympy/matrices/common.py", "MatrixArithmetic.__rmatmul__"]], "final": [["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 26}`。

- D1：Scalar multiplication allowed in __mul__；依据：；关联：`[["sympy/matrices/common.py", "MatrixArithmetic.__mul__"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/common.py", "MatrixArithmetic.__matmul__"]]`
- D2：Matrix multiplication handled correctly in MatrixArithmetic；依据：；关联：`[["sympy/matrices/common.py", "MatrixArithmetic"]]`
- A1：Incorrect computation；依据：；关联：`[["sympy/matrices/common.py", "MatrixArithmetic.__mul__"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/matrices/common.py", "MatrixArithmetic"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13773.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13773.jsonl)

## 241. sympy__sympy-13895

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> (-x/4 - S(1)/12)**x - 1 simplifies to an inequivalent expression
>     >>> from sympy import *
>     >>> x = Symbol('x')
>     >>> e = (-x/4 - S(1)/12)**x - 1
>     >>> e
>     (-x/4 - 1/12)**x - 1
>     >>> f = simplify(e)
>     >>> f
>     12**(-x)*(-12**x + (-3*x - 1)**x)
>     >>> a = S(9)/5
>     >>> simplify(e.subs(x,a))
>     -1 - 32*15**(1/5)*2**(2/5)/225
>     >>> simplify(f.subs(x,a))
>     -1 - 32*(-1)**(4/5)*60**(1/5)/225
>     >>> N(e.subs(x,a))
>     -1.32255049319339
>     >>> N(f.subs(x,a))
>     -0.739051169462523 - 0.189590423018741*I
> 
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/numbers.py", "Integer._eval_power"]]`

新预测：`[["sympy/core/expr.py", "Expr.simplify"], ["sympy/solvers/ode.py", "ode_1st_homogeneous_coeff_subs_indep_div_dep"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=131034/6738；耗时=849.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 10, "causal": 165}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/core/expr.py", "Expr"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.simplify"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/solvers/ode.py", "ode_1st_homogeneous_coeff_subs_indep_div_dep"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13895.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13895.jsonl)

## 242. sympy__sympy-13915

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Issue with a substitution that leads to an undefined expression
> ```
> Python 3.6.4 |Anaconda custom (64-bit)| (default, Dec 21 2017, 15:39:08) 
> Type 'copyright', 'credits' or 'license' for more information
> IPython 6.2.1 -- An enhanced Interactive Python. Type '?' for help.
> 
> In [1]: from sympy import *
> 
> In [2]: a,b = symbols('a,b')
> 
> In [3]: r = (1/(a+b) + 1/(a-b))/(1/(a+b) - 1/(a-b))
> 
> In [4]: r.subs(b,a)
> Out[4]: 1
> 
> In [6]: import sympy
> 
> In [7]: sympy.__version__
> Out[7]: '1.1.1'
> ```
> 
> If b is substituted by a, r is undefined. It is possible to calculate the limit
> `r.limit(b,a) # -1`
> 
> But whenever a subexpression of r is undefined, r itself is undefined.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/mul.py", "Mul.flatten"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=12740/550；耗时=152.4秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 8, "causal": 5}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-13915.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13915.jsonl)

## 243. sympy__sympy-13971

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Display of SeqFormula()
> ```
> import sympy as sp
> k, m, n = sp.symbols('k m n', integer=True)
> sp.init_printing()
> 
> sp.SeqFormula(n**2, (n,0,sp.oo))
> ```
> 
> The Jupyter rendering of this command backslash-escapes the brackets producing:
> 
> `\left\[0, 1, 4, 9, \ldots\right\]`
> 
> Copying this output to a markdown cell this does not render properly.  Whereas:
> 
> `[0, 1, 4, 9, \ldots ]`
> 
> does render just fine.  
> 
> So - sequence output should not backslash-escape square brackets, or, `\]` should instead render?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._print_SeqFormula"]]`

新预测：`[["sympy/categories/diagram_drawing.py", "ArrowStringDescription.__str__"], ["sympy/holonomic/recurrence.py", "RecurrenceOperator.__str__"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=16150/3864；耗时=547.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 32, "causal": 5}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/categories/diagram_drawing.py", "ArrowStringDescription.__str__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/holonomic/recurrence.py", "RecurrenceOperator.__str__"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/holonomic/recurrence.py", "RecurrenceOperator.__str__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-13971.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-13971.jsonl)

## 244. sympy__sympy-14024

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Inconsistency when simplifying (-a)**x * a**(-x), a a positive integer
> Compare:
> 
> ```
> >>> a = Symbol('a', integer=True, positive=True)
> >>> e = (-a)**x * a**(-x)
> >>> f = simplify(e)
> >>> print(e)
> a**(-x)*(-a)**x
> >>> print(f)
> (-1)**x
> >>> t = -S(10)/3
> >>> n1 = e.subs(x,t)
> >>> n2 = f.subs(x,t)
> >>> print(N(n1))
> -0.5 + 0.866025403784439*I
> >>> print(N(n2))
> -0.5 + 0.866025403784439*I
> ```
> 
> vs
> 
> ```
> >>> a = S(2)
> >>> e = (-a)**x * a**(-x)
> >>> f = simplify(e)
> >>> print(e)
> (-2)**x*2**(-x)
> >>> print(f)
> (-1)**x
> >>> t = -S(10)/3
> >>> n1 = e.subs(x,t)
> >>> n2 = f.subs(x,t)
> >>> print(N(n1))
> 0.5 - 0.866025403784439*I
> >>> print(N(n2))
> -0.5 + 0.866025403784439*I
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/numbers.py", "Integer._eval_power"], ["sympy/core/numbers.py", "Rational._eval_power"]]`

新预测：`[["sympy/core/expr.py", "Expr.simplify"], ["sympy/vector/basisdependent.py", "BasisDependent._eval_simplify"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=78001/4252；耗时=583.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 15, "causal": 36}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/vector/basisdependent.py", "BasisDependent._eval_simplify"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.simplify"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-14024.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-14024.jsonl)

## 245. sympy__sympy-14308

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> vectors break pretty printing
> ```py
> In [1]: from sympy.vector import *
> 
> In [2]: e = CoordSysCartesian('e')
> 
> In [3]: (x/y)**t*e.j
> Out[3]:
> ⎛   t⎞ e_j
> ⎜⎛x⎞ e_j ⎟
> ⎜⎜─⎟ ⎟
> ⎝⎝y⎠ ⎠
> ```
> 
> Also, when it does print correctly, the baseline is wrong (it should be centered). 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_BasisDependent"]]`

新预测：`[["sympy/physics/vector/tests/test_printing.py", "test_vector_pretty_print"], ["sympy/printing/pretty/pretty.py", "pretty_print"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=21623/3802；耗时=359.4秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 6, "causal": 13}`。

- A1：Inaccurate recursive check；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/physics/vector/tests/test_printing.py", "test_vector_pretty_print"]]`
- A2：Incorrect handling of commutative factors；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/printing/pretty/pretty.py", "pretty_print"]]`
- A3：Dependency on Product；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[["sympy/printing/pretty/pretty.py", "pretty_print"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-14308.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-14308.jsonl)

## 246. sympy__sympy-14317

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> LaTeX printer does not use the same order of monomials as pretty and str 
> When printing a Poly, the str and pretty printers use the logical order of monomials, from highest to lowest degrees. But latex printer does not. 
> ```
> >>> var('a b c x')
> >>> p = Poly([a, 1, b, 2, c, 3], x)
> >>> p
> Poly(a*x**5 + x**4 + b*x**3 + 2*x**2 + c*x + 3, x, domain='ZZ[a,b,c]')
> >>> pretty(p)
> "Poly(a*x**5 + x**4 + b*x**3 + 2*x**2 + c*x + 3, x, domain='ZZ[a,b,c]')"
> >>> latex(p)
> '\\operatorname{Poly}{\\left( a x^{5} + b x^{3} + c x + x^{4} + 2 x^{2} + 3, x, domain=\\mathbb{Z}\\left[a, b, c\\right] \\right)}'
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._print_Poly"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=7500/1803；耗时=158.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-14317.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-14317.jsonl)

## 247. sympy__sympy-14396

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Poly(domain='RR[y,z]') doesn't work
> ``` py
> In [14]: Poly(1.2*x*y*z, x)
> Out[14]: Poly(1.2*y*z*x, x, domain='RR[y,z]')
> 
> In [15]: Poly(1.2*x*y*z, x, domain='RR[y,z]')
> ---------------------------------------------------------------------------
> OptionError                               Traceback (most recent call last)
> <ipython-input-15-d83389519ae1> in <module>()
> ----> 1 Poly(1.2*x*y*z, x, domain='RR[y,z]')
> 
> /Users/aaronmeurer/Documents/Python/sympy/sympy-scratch/sympy/polys/polytools.py in __new__(cls, rep, *gens, **args)
>      69     def __new__(cls, rep, *gens, **args):
>      70         """Create a new polynomial instance out of something useful. """
> ---> 71         opt = options.build_options(gens, args)
>      72
>      73         if 'order' in opt:
> 
> /Users/aaronmeurer/Documents/Python/sympy/sy

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/polys/polyoptions.py", "Domain.preprocess"]]`

新预测：`[["sympy/concrete/summations.py", "Sum.__new__"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=34098/2938；耗时=290.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 19}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/concrete/summations.py", "Sum.__new__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-14396.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-14396.jsonl)

## 248. sympy__sympy-14774

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Latex printer does not support full inverse trig function names for acsc and asec
> For example
> `latex(asin(x), inv_trig_style="full")` works as expected returning `'\\arcsin{\\left (x \\right )}'`
> But `latex(acsc(x), inv_trig_style="full")` gives `'\\operatorname{acsc}{\\left (x \\right )}'` instead of `'\\operatorname{arccsc}{\\left (x \\right )}'`
> 
> A fix seems to be to change line 743 of sympy/printing/latex.py from
> `inv_trig_table = ["asin", "acos", "atan", "acot"]` to
> `inv_trig_table = ["asin", "acos", "atan", "acsc", "asec", "acot"]`

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._print_Function"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=11075/1184；耗时=153.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 0, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/printing/latex.py", "latex.py"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-14774.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-14774.jsonl)

## 249. sympy__sympy-14817

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Error pretty printing MatAdd
> ```py
> >>> pprint(MatrixSymbol('x', n, n) + MatrixSymbol('y*', n, n))
> Traceback (most recent call last):
>   File "./sympy/core/sympify.py", line 368, in sympify
>     expr = parse_expr(a, local_dict=locals, transformations=transformations, evaluate=evaluate)
>   File "./sympy/parsing/sympy_parser.py", line 950, in parse_expr
>     return eval_expr(code, local_dict, global_dict)
>   File "./sympy/parsing/sympy_parser.py", line 863, in eval_expr
>     code, global_dict, local_dict)  # take local objects in preference
>   File "<string>", line 1
>     Symbol ('y' )*
>                  ^
> SyntaxError: unexpected EOF while parsing
> 
> During handling of the above exception, another exception occurred:
> 
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <modu

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"]]`

新预测：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"], ["sympy/printing/pretty/stringpict.py", "stringPict.next"], ["sympy/printing/str.py", "StrPrinter._print_MatAdd"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=217792/25733；耗时=2442.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"]], "seeds": [["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"]], "causal_received": [["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"]], "final": [["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 127}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "stringPict.next"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_MatAdd"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "prettyForm"]]`
- D：Use of sympify for string arguments；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "stringPict.next"]]`
- E：Assumption about argument forms；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "prettyForm"]]`
- F：Handling of negative signs；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "stringPict.next"]]`
- G：next function usage；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "stringPict.next"]]`
- H：prettyForm class usage；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "stringPict.next"]]`
- J：PrettyPrinter class usage；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "prettyForm"]]`
- K：_print function usage；依据：；关联：`[["sympy/printing/pretty/stringpict.py", "prettyForm"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/printing/str.py", "StrPrinter._print_MatAdd"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/printing/str.py", "StrPrinter._print_MatAdd"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-14817.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-14817.jsonl)

## 250. sympy__sympy-15011

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> lambdify does not work with certain MatrixSymbol names even with dummify=True
> `lambdify` is happy with curly braces in a symbol name and with `MatrixSymbol`s, but not with both at the same time, even if `dummify` is `True`.
> 
> Here is some basic code that gives the error.
> ```
> import sympy as sy
> curlyx = sy.symbols("{x}")
> v = sy.MatrixSymbol("v", 2, 1)
> curlyv = sy.MatrixSymbol("{v}", 2, 1)
> ```
> 
> The following two lines of code work:
> ```
> curlyScalarId = sy.lambdify(curlyx, curlyx)
> vectorId = sy.lambdify(v,v)
> ```
> 
> The following two lines of code give a `SyntaxError`:
> ```
> curlyVectorId = sy.lambdify(curlyv, curlyv)
> curlyVectorIdDummified = sy.lambdify(curlyv, curlyv, dummify=True)
> ```
> 
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/utilities/lambdify.py", "_EvaluatorPrinter._preprocess"]]`

新预测：`[["sympy/utilities/lambdify.py", "lambdify"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=135251/9417；耗时=1175.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 15, "causal": 102}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/utilities/lambdify.py", "lambdify"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/utilities/lambdify.py", "lambdify"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/utilities/lambdify.py", "lambdify"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-15011.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-15011.jsonl)

## 251. sympy__sympy-15308

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> LaTeX printing for Matrix Expression
> ```py
> >>> A = MatrixSymbol("A", n, n)
> >>> latex(trace(A**2))
> 'Trace(A**2)'
> ```
> 
> The bad part is not only is Trace not recognized, but whatever printer is being used doesn't fallback to the LaTeX printer for the inner expression (it should be `A^2`). 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._print_Basic"], ["sympy/printing/latex.py", "LatexPrinter._print_Trace"]]`

新预测：`[["sympy/core/basic.py", "Basic.doit"], ["sympy/core/trace.py", "Tr.doit"], ["sympy/physics/quantum/density.py", "Density._eval_trace"]]`

搜索种子 7；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=49510/6132；耗时=601.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 7, "relevance": 37, "causal": 46}`。

- D3：Tr class；依据：；关联：`[["sympy/core/trace.py", "Tr"]]`
- D1：_eval_trace；依据：；关联：`[["sympy/physics/quantum/density.py", "Density._eval_trace"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/basic.py", "Basic.doit"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/core/trace.py", "Tr.doit"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/core/trace.py", "Tr.doit"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-15308.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-15308.jsonl)

## 252. sympy__sympy-15345

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> mathematica_code gives wrong output with Max
> If I run the code
> 
> ```
> x = symbols('x')
> mathematica_code(Max(x,2))
> ```
> 
> then I would expect the output `'Max[x,2]'` which is valid Mathematica code but instead I get `'Max(2, x)'` which is not valid Mathematica code.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[["sympy/functions/elementary/tests/test_miscellaneous.py", "test_Max"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=53317/9147；耗时=761.5秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 5, "causal": 14}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/functions/elementary/tests/test_miscellaneous.py", "test_Max"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/functions/elementary/tests/test_miscellaneous.py", "test_Max"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/functions/elementary/tests/test_miscellaneous.py", "test_Max"]]`
- D：Handling of complex numbers；依据：；关联：`[["sympy/core/numbers.py", "ComplexInfinity"]]`
- E：Ordering of arguments in Max function；依据：；关联：`[]`
- F：Special value handling in Max function；依据：；关联：`[]`
- G：Imaginary unit I in Max function；依据：；关联：`[]`
- H：Complex number processing in Max function；依据：；关联：`[]`
- I1：Incorrect argument ordering in Max function；依据：；关联：`[]`
- I2：Failure to handle complex numbers correctly；依据：；关联：`[]`
- I3：Incorrect evaluation of special values in Max function；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-15345.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-15345.jsonl)

## 253. sympy__sympy-15346

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> can't simplify sin/cos with Rational?
> latest cloned sympy, python 3 on windows
> firstly, cos, sin with symbols can be simplified; rational number can be simplified
> ```python
> from sympy import *
> 
> x, y = symbols('x, y', real=True)
> r = sin(x)*sin(y) + cos(x)*cos(y)
> print(r)
> print(r.simplify())
> print()
> 
> r = Rational(1, 50) - Rational(1, 25)
> print(r)
> print(r.simplify())
> print()
> ```
> says
> ```cmd
> sin(x)*sin(y) + cos(x)*cos(y)
> cos(x - y)
> 
> -1/50
> -1/50
> ```
> 
> but
> ```python
> t1 = Matrix([sin(Rational(1, 50)), cos(Rational(1, 50)), 0])
> t2 = Matrix([sin(Rational(1, 25)), cos(Rational(1, 25)), 0])
> r = t1.dot(t2)
> print(r)
> print(r.simplify())
> print()
> 
> r = sin(Rational(1, 50))*sin(Rational(1, 25)) + cos(Rational(1, 50))*cos(Rational(1, 25))
> print(r)
> print(r.simplify())
> print

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/simplify/trigsimp.py", "_futrig"]]`

新预测：`[["sympy/matrices/common.py", "MatrixOperations.simplify"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=17480/2998；耗时=304.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 10, "causal": 9}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/common.py", "MatrixOperations.simplify"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-15346.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-15346.jsonl)

## 254. sympy__sympy-15609

项目：sympy/sympy；本轮子集：开发集；状态：complete。

问题描述节选：

> Indexed matrix-expression LaTeX printer is not compilable
> ```python
> i, j, k = symbols("i j k")
> M = MatrixSymbol("M", k, k)
> N = MatrixSymbol("N", k, k)
> latex((M*N)[i, j])
> ```
> 
> The LaTeX string produced by the last command is:
> ```
> \sum_{i_{1}=0}^{k - 1} M_{i, _i_1} N_{_i_1, j}
> ```
> LaTeX complains about a double subscript `_`. This expression won't render in MathJax either.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._print_MatrixElement"]]`

新预测：`[["sympy/matrices/common.py", "_MinimalMatrix.__getitem__"], ["sympy/matrices/expressions/matexpr.py", "MatrixExpr.__getitem__"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=32748/3524；耗时=540.1秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 32, "causal": 19}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix.__getitem__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/matrices/expressions/matexpr.py", "MatrixExpr.__getitem__"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/matrices/expressions/matexpr.py", "MatrixExpr.__getitem__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-15609.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-15609.jsonl)

## 255. sympy__sympy-15678

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Some issues with idiff
> idiff doesn't support Eq, and it also doesn't support f(x) instead of y. Both should be easy to correct.
> 
> ```
> >>> idiff(Eq(y*exp(y), x*exp(x)), y, x)
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "./sympy/geometry/util.py", line 582, in idiff
>     yp = solve(eq.diff(x), dydx)[0].subs(derivs)
> IndexError: list index out of range
> >>> idiff(f(x)*exp(f(x)) - x*exp(x), f(x), x)
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "./sympy/geometry/util.py", line 574, in idiff
>     raise ValueError("expecting x-dependent symbol(s) but got: %s" % y)
> ValueError: expecting x-dependent symbol(s) but got: f(x)
> >>> idiff(y*exp(y)- x*exp(x), y, x)
> (x + 1)*exp(x - y)/(y + 1)
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["sympy/geometry/util.py", "idiff"]]`

新预测：`[["sympy/geometry/util.py", "idiff"], ["sympy/matrices/sparse.py", "SparseMatrix.solve"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=35935/6678；耗时=707.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/geometry/util.py", "idiff"]], "seeds": [["sympy/geometry/util.py", "idiff"]], "causal_received": [["sympy/geometry/util.py", "idiff"]], "final": [["sympy/geometry/util.py", "idiff"]]}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 15}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/geometry/util.py", "idiff"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/matrices/sparse.py", "SparseMatrix.solve"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/matrices/sparse.py", "SparseMatrix.solve"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-15678.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-15678.jsonl)

## 256. sympy__sympy-16106

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> mathml printer for IndexedBase required
> Writing an `Indexed` object to MathML fails with a `TypeError` exception: `TypeError: 'Indexed' object is not iterable`:
> 
> ```
> In [340]: sympy.__version__
> Out[340]: '1.0.1.dev'
> 
> In [341]: from sympy.abc import (a, b)
> 
> In [342]: sympy.printing.mathml(sympy.IndexedBase(a)[b])
> ---------------------------------------------------------------------------
> TypeError                                 Traceback (most recent call last)
> <ipython-input-342-b32e493b70d3> in <module>()
> ----> 1 sympy.printing.mathml(sympy.IndexedBase(a)[b])
> 
> /dev/shm/gerrit/venv/stable-3.5/lib/python3.5/site-packages/sympy/printing/mathml.py in mathml(expr, **settings)
>     442 def mathml(expr, **settings):
>     443     """Returns the MathML representation of expr"""
> -->

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/mathml.py", "MathMLPresentationPrinter._print_Indexed"], ["sympy/printing/mathml.py", "MathMLPresentationPrinter._print_IndexedBase"], ["sympy/printing/mathml.py", "MathMLPresentationPrinter._print_tuple"]]`

新预测：`[["sympy/printing/mathml.py", "MathMLContentPrinter._print_Basic"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=13920/2190；耗时=323.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 15, "causal": 3}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/printing/mathml.py", "MathMLContentPrinter._print_Basic"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-16106.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-16106.jsonl)

## 257. sympy__sympy-16281

项目：sympy/sympy；本轮子集：开发集；状态：complete。

问题描述节选：

> Product pretty print could be improved
> This is what the pretty printing for `Product` looks like:
> 
> ```
> >>> pprint(Product(1, (n, 1, oo)))
>   ∞
> ┬───┬
> │   │ 1
> │   │
> n = 1
> >>> pprint(Product(1/n, (n, 1, oo)))
>    ∞
> ┬──────┬
> │      │ 1
> │      │ ─
> │      │ n
> │      │
>  n = 1
> >>> pprint(Product(1/n**2, (n, 1, oo)))
>     ∞
> ┬────────┬
> │        │ 1
> │        │ ──
> │        │  2
> │        │ n
> │        │
>   n = 1
> >>> pprint(Product(1, (n, 1, oo)), use_unicode=False)
>   oo
> _____
> |   | 1
> |   |
> n = 1
> >>> pprint(Product(1/n, (n, 1, oo)), use_unicode=False)
>    oo
> ________
> |      | 1
> |      | -
> |      | n
> |      |
>  n = 1
> >>> pprint(Product(1/n**2, (n, 1, oo)), use_unicode=False)
>     oo
> __________
> |        | 1
> |        | --
> |        |  2
> |        | n
> |        |
>   n = 1

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_Product"]]`

新预测：`[]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=20269/3097；耗时=405.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 13}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/concrete/products.py", "Product"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-16281.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-16281.jsonl)

## 258. sympy__sympy-16503

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Bad centering for Sum pretty print
> ```
> >>> pprint(Sum(x, (x, 1, oo)) + 3)
>   ∞
>  ___
>  ╲
>   ╲   x
>   ╱     + 3
>  ╱
>  ‾‾‾
> x = 1
> ```
> 
> The `x` and the `+ 3` should be aligned. I'm not sure if the `x` should be lower of if the `+ 3` should be higher. 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_Sum"], ["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_Sum.asum"]]`

新预测：`[["sympy/printing/tree.py", "pprint_nodes"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=7999/1372；耗时=161.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 5, "causal": 2}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/printing/tree.py", "pprint_nodes"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-16503.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-16503.jsonl)

## 259. sympy__sympy-16792

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> autowrap with cython backend fails when array arguments do not appear in wrapped expr
> When using the cython backend for autowrap, it appears that the code is not correctly generated when the function in question has array arguments that do not appear in the final expression. A minimal counterexample is:
> 
> ```python
> from sympy.utilities.autowrap import autowrap
> from sympy import MatrixSymbol
> import numpy as np
> 
> x = MatrixSymbol('x', 2, 1)
> expr = 1.0
> f = autowrap(expr, args=(x,), backend='cython')
> 
> f(np.array([[1.0, 2.0]]))
> ```
> 
> This should of course return `1.0` but instead fails with:
> ```python
> TypeError: only size-1 arrays can be converted to Python scalars
> ```
> 
> A little inspection reveals that this is because the corresponding C function is generated with an incorrect s

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/utilities/codegen.py", "CodeGen.routine"], ["sympy/utilities/codegen.py", "CodeGen.routine.dimensions"]]`

新预测：`[["bin/coverage_doctest.py", "_get_arg_list"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=28629/5478；耗时=589.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 37, "causal": 2}`。

- A：Inaccurate recursive check；依据：；关联：`[["bin/coverage_doctest.py", "_get_arg_list"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`
- D：Missing array argument dependency；依据：；关联：`[]`
- E：_get_arg_list function；依据：；关联：`[]`
- F：Expression does not depend on all arguments；依据：；关联：`[]`
- G：Incorrect C function signature；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-16792.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-16792.jsonl)

## 260. sympy__sympy-16988

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Intersection should remove duplicates
> ```python
> >>> Intersection({1},{1},{x})
> EmptySet()
> >>> Intersection({1},{x})
> {1}
> ```
> The answer should be `Piecewise(({1}, Eq(x, 1)), (S.EmptySet, True))` or remain unevaluated.
> 
> The routine should give the same answer if duplicates are present; my initial guess is that duplicates should just be removed at the outset of instantiation. Ordering them will produce canonical processing.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/sets/sets.py", "Intersection.__new__"]]`

新预测：`[["sympy/core/containers.py", "OrderedSet.intersection"], ["sympy/geometry/ellipse.py", "Circle.intersection"], ["sympy/geometry/entity.py", "intersection_sets"], ["sympy/geometry/polygon.py", "Polygon.intersection"], ["sympy/sets/fancysets.py", "ComplexRegion.args"], ["sympy/sets/fancysets.py", "ComplexRegion.b_interval"], ["sympy/sets/fancysets.py", "ComplexRegion.psets"], ["sympy/sets/handlers/intersection.py", "<unresolved>:intersection_sets"], ["sympy/sets/handlers/intersection.py", "_intlike_interval"], ["sympy/sets/sets.py", "Set.is_subset"], ["sympy/sets/sets.py", "simplify_intersection"]]`

搜索种子 8；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=261268/44818；耗时=3944.9秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sympy/sets/sets.py", "Intersection.__new__"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 5, "causal": 152}`。

无法唯一映射的函数：`[{"file": "sympy/sets/handlers/intersection.py", "name": "intersection_sets", "reason": "ambiguous"}]`

- A1：Incorrect computation；依据：；关联：`[["sympy/geometry/ellipse.py", "Circle.intersection"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/geometry/entity.py", "intersection_sets"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/geometry/polygon.py", "Polygon.intersection"]]`
- C1：Duplicate handling in containers.py；依据：；关联：`[["sympy/core/containers.py", "OrderedSet.intersection"]]`
- D11：Using psets incorrectly；依据：；关联：`[["sympy/sets/fancysets.py", "ComplexRegion.psets"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/sets/handlers/intersection.py", "intersection_sets"]]`
- D6：Using b_interval incorrectly；依据：；关联：`[["sympy/sets/fancysets.py", "ComplexRegion.b_interval"]]`
- D1：Renaming intersection_sets to intersection_sets(b, a)；依据：；关联：`[["sympy/sets/handlers/intersection.py", "intersection_sets"], ["sympy/sets/handlers/intersection.py", "intersection_sets"]]`
- D2：Calling intersection_sets with Interval(1, S.Infinity)；依据：；关联：`[["sympy/sets/handlers/intersection.py", "intersection_sets"]]`
- D3：Using Lambda incorrectly；依据：；关联：`[["sympy/core/function.py", "Lambda"]]`
- D4：Using Reals incorrectly；依据：；关联：`[["sympy/sets/fancysets.py", "Reals"]]`
- D5：Using Pi incorrectly；依据：；关联：`[["sympy/core/numbers.py", "Pi"]]`
- D8：Using _intlike_interval incorrectly；依据：；关联：`[["sympy/sets/fancysets.py", "ComplexRegion.args"]]`
- D7：Using intersection.py incorrectly；依据：；关联：`[["sympy/sets/handlers/intersection.py", "intersection.py"]]`
- D9：Using Zero incorrectly；依据：；关联：`[["sympy/core/numbers.py", "Zero"]]`
- D10：Using is_subset incorrectly；依据：；关联：`[["sympy/sets/sets.py", "Set.is_subset"]]`
- D12：Using simplify_intersection incorrectly；依据：；关联：`[["sympy/sets/handlers/intersection.py", "_intlike_interval"]]`
- D14：Using ImageSet incorrectly；依据：；关联：`[["sympy/sets/fancysets.py", "ImageSet"]]`
- D13：Using intersection_sets incorrectly；依据：；关联：`[["sympy/sets/sets.py", "simplify_intersection"], ["sympy/sets/handlers/intersection.py", "intersection_sets"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/sets/handlers/intersection.py", "intersection_sets"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-16988.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-16988.jsonl)

## 261. sympy__sympy-17022

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Lambdify misinterprets some matrix expressions
> Using lambdify on an expression containing an identity matrix gives us an unexpected result:
> 
> ```python
> >>> import numpy as np
> >>> n = symbols('n', integer=True)
> >>> A = MatrixSymbol("A", n, n)
> >>> a = np.array([[1, 2], [3, 4]])
> >>> f = lambdify(A, A + Identity(n))
> >>> f(a)
> array([[1.+1.j, 2.+1.j],
>        [3.+1.j, 4.+1.j]])
> ```
> 
> Instead, the output should be  `array([[2, 2], [3, 5]])`, since we're adding an identity matrix to the array. Inspecting the globals and source code of `f` shows us why we get the result:
> 
> ```python
> >>> import inspect
> >>> print(inspect.getsource(f))
> def _lambdifygenerated(A):
>     return (I + A)
> >>> f.__globals__['I']
> 1j
> ```
> 
> The code printer prints `I`, which is currently being interpreted as a 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/pycode.py", "NumPyPrinter._print_Identity"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=13121/4257；耗时=344.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-17022.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-17022.jsonl)

## 262. sympy__sympy-17139

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> simplify(cos(x)**I): Invalid comparison of complex I (fu.py)
> ```
> >>> from sympy import *
> >>> x = Symbol('x')
> >>> print(simplify(cos(x)**I))
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "/home/e/se/sympy/simplify/simplify.py", line 587, in simplify
>     expr = trigsimp(expr, deep=True)
>   File "/home/e/se/sympy/simplify/trigsimp.py", line 508, in trigsimp
>     return trigsimpfunc(expr)
>   File "/home/e/se/sympy/simplify/trigsimp.py", line 501, in <lambda>
>     'matching': (lambda x: futrig(x)),
>   File "/home/e/se/sympy/simplify/trigsimp.py", line 1101, in futrig
>     e = bottom_up(e, lambda x: _futrig(x, **kwargs))
>   File "/home/e/se/sympy/simplify/simplify.py", line 1081, in bottom_up
>     rv = F(rv)
>   File "/home/e/se/sympy/simplify/trigsimp.py"

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/simplify/fu.py", "_TR56._f"]]`

新预测：`[["sympy/core/expr.py", "Expr.__lt__"], ["sympy/core/expr.py", "_n2"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=34427/5618；耗时=593.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 17}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/core/expr.py", "_n2"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.__lt__"]]`
- A2：Wrong logic；依据：；关联：`[["", "self.is_extended_positive"]]`
- D：Incorrect handling of complex numbers；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-17139.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-17139.jsonl)

## 263. sympy__sympy-17630

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Exception when multiplying BlockMatrix containing ZeroMatrix blocks
> When a block matrix with zero blocks is defined
> 
> ```
> >>> from sympy import *
> >>> a = MatrixSymbol("a", 2, 2)
> >>> z = ZeroMatrix(2, 2)
> >>> b = BlockMatrix([[a, z], [z, z]])
> ```
> 
> then block-multiplying it once seems to work fine:
> 
> ```
> >>> block_collapse(b * b)
> Matrix([
> [a**2, 0],
> [0, 0]])
> >>> b._blockmul(b)
> Matrix([
> [a**2, 0],
> [0, 0]])
> ```
> 
> but block-multiplying twice throws an exception:
> 
> ```
> >>> block_collapse(b * b * b)
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "/home/jan/.pyenv/versions/3.7.4/lib/python3.7/site-packages/sympy/matrices/expressions/blockmatrix.py", line 297, in block_collapse
>     result = rule(expr)
>   File "/home/jan/.pyenv/versions/3.7.4/

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/expressions/matexpr.py", "get_postprocessor._postprocessor"]]`

新预测：`[["sympy/core/numbers.py", "Zero.__neg__"], ["sympy/core/numbers.py", "Zero.__nonzero__"], ["sympy/core/numbers.py", "Zero._eval_order"], ["sympy/core/numbers.py", "Zero._eval_power"], ["sympy/matrices/expressions/blockmatrix.py", "BlockDiagMatrix._blockmul"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=53664/19222；耗时=1679.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 17}`。

- N：Factor: Incorrect zero handling in block matrix operations；依据：；关联：`[]`
- A1：Inaccurate recursive check；依据：；关联：`[["sympy/diffgeom/diffgeom.py", "Differential"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/numbers.py", "Zero"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/core/numbers.py", "Zero.__neg__"]]`
- D：Handling of Zero objects in block matrix operations；依据：；关联：`[["sympy/core/numbers.py", "Zero._eval_order"], ["sympy/core/numbers.py", "Zero._eval_power"], ["sympy/core/numbers.py", "Zero.__nonzero__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/matrices/expressions/blockmatrix.py", "BlockDiagMatrix._blockmul"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/matrices/expressions/blockmatrix.py", "BlockDiagMatrix._blockmul"]]`
- E：as_coeff_Mul method；依据：；关联：`[]`
- F：_denest_pow method；依据：；关联：`[]`
- G：Zero class definition；依据：；关联：`[]`
- H：Non-commutative gcd handling；依据：；关联：`[]`
- J：block_collapse method；依据：；关联：`[]`
- K：b._blockmul method；依据：；关联：`[]`
- L：colblocksizes method；依据：；关联：`[]`
- M：New observation: Zeros in intermediate results are instances of Zero；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-17630.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-17630.jsonl)

## 264. sympy__sympy-17655

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Unexpected exception when multiplying geometry.Point and number
> ```python
> from sympy import geometry as ge
> import sympy
> 
> point1 = ge.Point(0,0)
> point2 = ge.Point(1,1)
> ```
> 
> This line works fine
> ```python
> point1 + point2 * sympy.sympify(2.0)
> ```
> 
> But when I write the same this way it raises an exception
> ```python
> point1 + sympy.sympify(2.0) * point2
> ```
> 
> ```
> ---------------------------------------------------------------------------
> TypeError                                 Traceback (most recent call last)
> ~/.virtualenvs/test/lib/python3.6/site-packages/sympy/geometry/point.py in __add__(self, other)
>     219         try:
> --> 220             s, o = Point._normalize_dimension(self, Point(other, evaluate=False))
>     221         except TypeError:
> 
> ~/.virtualenvs/test/l

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/geometry/point.py", "Point.__rmul__"]]`

新预测：`[["sympy/core/expr.py", "Expr.__mul__"], ["sympy/core/numbers.py", "Float.__mul__"], ["sympy/core/tests/test_arit.py", "test_issue_3531b"], ["sympy/physics/units/prefixes.py", "Prefix.__mul__"]]`

搜索种子 8；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=44267/6865；耗时=711.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 8, "relevance": 32, "causal": 24}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/core/tests/test_arit.py", "test_issue_3531b"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.__mul__"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/physics/units/prefixes.py", "Prefix.__mul__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/core/numbers.py", "Float.__mul__"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/core/numbers.py", "Float.__mul__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-17655.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-17655.jsonl)

## 265. sympy__sympy-18057

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Sympy incorrectly attempts to eval reprs in its __eq__ method
> Passing strings produced by unknown objects into eval is **very bad**. It is especially surprising for an equality check to trigger that kind of behavior. This should be fixed ASAP.
> 
> Repro code:
> 
> ```
> import sympy
> class C:
>     def __repr__(self):
>         return 'x.y'
> _ = sympy.Symbol('x') == C()
> ```
> 
> Results in:
> 
> ```
> E   AttributeError: 'Symbol' object has no attribute 'y'
> ```
> 
> On the line:
> 
> ```
>     expr = eval(
>         code, global_dict, local_dict)  # take local objects in preference
> ```
> 
> Where code is:
> 
> ```
> Symbol ('x' ).y
> ```
> 
> Full trace:
> 
> ```
> FAILED                   [100%]
>         class C:
>             def __repr__(self):
>                 return 'x.y'
>     
> >       _ = sympy.Symbol('x') =

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/core/expr.py", "Expr.__eq__"]]`

新预测：`[["sympy/core/expr.py", "Expr.__eq__"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=24839/6278；耗时=547.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/core/expr.py", "Expr.__eq__"]], "seeds": [["sympy/core/expr.py", "Expr.__eq__"]], "causal_received": [["sympy/core/expr.py", "Expr.__eq__"]], "final": [["sympy/core/expr.py", "Expr.__eq__"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 36, "causal": 7}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.__eq__"]]`
- D：Use of eval in sympify；依据：；关联：`[]`
- E：Improper handling of _hashable_content；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-18057.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18057.jsonl)

## 266. sympy__sympy-18087

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Simplify of simple trig expression fails
> trigsimp in various versions, including 1.5, incorrectly simplifies cos(x)+sqrt(sin(x)**2) as though it were cos(x)+sin(x) for general complex x. (Oddly it gets this right if x is real.)
> 
> Embarrassingly I found this by accident while writing sympy-based teaching material...
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/exprtools.py", "Factors.__init__"], ["sympy/core/exprtools.py", "Factors.as_expr"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=52579/4953；耗时=722.7秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 4, "causal": 33}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-18087.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18087.jsonl)

## 267. sympy__sympy-18189

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> diophantine: incomplete results depending on syms order with permute=True
> ```
> In [10]: diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(m,n), permute=True)
> Out[10]: {(-3, -2), (-3, 2), (-2, -3), (-2, 3), (2, -3), (2, 3), (3, -2), (3, 2)}
> 
> In [11]: diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(n,m), permute=True)
> Out[11]: {(3, 2)}
> ```
> 
> diophantine: incomplete results depending on syms order with permute=True
> ```
> In [10]: diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(m,n), permute=True)
> Out[10]: {(-3, -2), (-3, 2), (-2, -3), (-2, 3), (2, -3), (2, 3), (3, -2), (3, 2)}
> 
> In [11]: diophantine(n**4 + m**4 - 2**4 - 3**4, syms=(n,m), permute=True)
> Out[11]: {(3, 2)}
> ```
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/solvers/diophantine.py", "diophantine"]]`

新预测：`[["sympy/solvers/diophantine.py", "diophantine"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=48537/2649；耗时=362.9秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/solvers/diophantine.py", "diophantine"]], "seeds": [["sympy/solvers/diophantine.py", "diophantine"]], "causal_received": [["sympy/solvers/diophantine.py", "diophantine"]], "final": [["sympy/solvers/diophantine.py", "diophantine"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 66}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/solvers/diophantine.py", "diophantine"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-18189.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18189.jsonl)

## 268. sympy__sympy-18199

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> nthroot_mod function misses one root of x = 0 mod p.
> When in the equation x**n = a mod p , when a % p == 0. Then x = 0 mod p is also a root of this equation. But right now `nthroot_mod` does not check for this condition. `nthroot_mod(17*17, 5 , 17)` has a root `0 mod 17`. But it does not return it.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 50.00% | 66.67% | 0.00% | 命中 |

共同严格目标：`[["sympy/ntheory/residue_ntheory.py", "_nthroot_mod_composite"], ["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]]`

新预测：`[["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=20294/2375；耗时=273.3秒。

阶段诊断：最终覆盖部分目标；各阶段实际覆盖目标：`{"search_received": [["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]], "seeds": [["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]], "causal_received": [["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]], "final": [["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 10}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/ntheory/residue_ntheory.py", "nthroot_mod"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-18199.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18199.jsonl)

## 269. sympy__sympy-18532

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> expr.atoms() should return objects with no args instead of subclasses of Atom
> `expr.atoms()` with no arguments returns subclasses of `Atom` in `expr`. But the correct definition of a leaf node should be that it has no `.args`. 
> 
> This should be easy to fix, but one needs to check that this doesn't affect the performance. 
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/basic.py", "Basic.atoms"]]`

新预测：`[["sympy/combinatorics/permutations.py", "Permutation.__xor__"], ["sympy/combinatorics/permutations.py", "Permutation.atoms"], ["sympy/combinatorics/permutations.py", "Permutation.get_precedence_distance"]]`

搜索种子 6；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=92811/8056；耗时=919.6秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [["sympy/core/basic.py", "Basic.atoms"]], "seeds": [["sympy/core/basic.py", "Basic.atoms"]], "causal_received": [["sympy/core/basic.py", "Basic.atoms"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 77}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation.get_precedence_distance"]]`
- A：Inaccurate recursive check；依据：；关联：`[["", "self.args"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation.__xor__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation.atoms"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation.atoms"]]`
- D：Class definition of Permutation；依据：；关联：`[["sympy/combinatorics/permutations.py", "Permutation"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-18532.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18532.jsonl)

## 270. sympy__sympy-18621

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> BlockDiagMatrix with one element cannot be converted to regular Matrix
> Creating a BlockDiagMatrix with one Matrix element will raise if trying to convert it back to a regular Matrix:
> 
> ```python
> M = sympy.Matrix([[1, 2], [3, 4]])
> D = sympy.BlockDiagMatrix(M)
> B = sympy.Matrix(D)
> ```
> 
> ```
> Traceback (most recent call last):
> 
>   File "<ipython-input-37-5b65c1f8f23e>", line 3, in <module>
>     B = sympy.Matrix(D)
> 
>   File "/home/rikard/.local/lib/python3.7/site-packages/sympy/matrices/dense.py", line 430, in __new__
>     return cls._new(*args, **kwargs)
> 
>   File "/home/rikard/.local/lib/python3.7/site-packages/sympy/matrices/dense.py", line 442, in _new
>     rows, cols, flat_list = cls._handle_creation_inputs(*args, **kwargs)
> 
>   File "/home/rikard/.local/lib/python3.7/site-packages

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/expressions/blockmatrix.py", "BlockDiagMatrix.blocks"]]`

新预测：`[["sympy/matrices/common.py", "<unresolved>:_MinimalMatrix._coord_to_index"], ["sympy/matrices/common.py", "<unresolved>:_MinimalMatrix._normalize_slices"], ["sympy/matrices/common.py", "_MinimalMatrix.__getitem__"], ["sympy/matrices/common.py", "_MinimalMatrix._new"], ["sympy/matrices/expressions/matexpr.py", "MatrixExpr._entry"]]`

搜索种子 5；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=70003/14141；耗时=1261.2秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 57, "causal": 41}`。

无法唯一映射的函数：`[{"file": "sympy/matrices/common.py", "name": "_MinimalMatrix._coord_to_index", "reason": "absent"}, {"file": "sympy/matrices/common.py", "name": "_MinimalMatrix._normalize_slices", "reason": "absent"}]`

- D1：_coord_to_index；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix._coord_to_index"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix.__getitem__"]]`
- D2：_MinimalMatrix；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix"]]`
- D3：_normalize_slices；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix._normalize_slices"]]`
- D4：_new；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix._new"]]`
- A1：Incorrect computation；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix._coord_to_index"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/matrices/common.py", "_MinimalMatrix"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/matrices/expressions/matexpr.py", "MatrixExpr._entry"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/matrices/expressions/matexpr.py", "MatrixExpr._entry"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-18621.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18621.jsonl)

## 271. sympy__sympy-18698

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> sqf and sqf_list output is not consistant
> The example below is wrong in the sense that we should have (x*_2 - 5_x + 6, 3) and not 2 factors of multiplicity 3.
> 
> ```
> >  sqf_list(  (x**2 + 1)  * (x - 1)**2 * (x - 2)**3 * (x - 3)**3  )
> 
> >  (1, [(x**2 + 1, 1), (x - 1, 2), (x - 3, 3), (x - 2, 3)])
> ```
> 
> whereas below is correct --- one factor of multiplicity 2
> 
> ```
> >  sqf_list( x**5 - 2*x**4 - 2*x**3 + 4*x**2 + x - 2 )
> 
> >  (1, [(x - 2, 1), (x**2 - 1, 2)])
> ```
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/polys/polytools.py", "_symbolic_factor_list"]]`

新预测：`[["sympy/polys/compatibility.py", "IPolys.dmp_sqf_list"], ["sympy/polys/polytools.py", "Poly.sqf_list"]]`

搜索种子 6；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=19155/4617；耗时=582.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 6, "relevance": 4, "causal": 15}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/polys/compatibility.py", "IPolys.dmp_sqf_list"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/polys/polytools.py", "Poly.sqf_list"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/polys/polytools.py", "Poly.sqf_list"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-18698.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18698.jsonl)

## 272. sympy__sympy-18835

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> uniq modifies list argument
> When you iterate over a dictionary or set and try to modify it while doing so you get an error from Python:
> ```python
> >>> multiset('THISTLE')
> {'T': 2, 'H': 1, 'I': 1, 'S': 1, 'L': 1, 'E': 1}
> >>> for i in _:
> ...   _.pop(i)
> ...
> 2
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
> RuntimeError: dictionary changed size during iteration
> ```
> It would be good to do the same thing from within `uniq` because the output will silently be wrong if you modify a passed list:
> ```python
> >>> f=list('THISTLE')
> >>> for i in uniq(f):
> ...   f.remove(i)
> ...   i
> ...
> 'T'
> 'I'
> 'L'
> ```
> I think this would entail recording the size at the start and then checking the size and raising a similar RuntimeError if the size changes.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/utilities/iterables.py", "uniq"], ["sympy/utilities/iterables.py", "uniq.check"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=36169/2208；耗时=525.5秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["sympy/utilities/iterables.py", "uniq"]], "seeds": [], "causal_received": [["sympy/utilities/iterables.py", "uniq"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 26}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-18835.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-18835.jsonl)

## 273. sympy__sympy-19007

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Wrong matrix element fetched from BlockMatrix
> Given this code:
> ```
> from sympy import *
> n, i = symbols('n, i', integer=True)
> A = MatrixSymbol('A', 1, 1)
> B = MatrixSymbol('B', n, 1)
> C = BlockMatrix([[A], [B]])
> print('C is')
> pprint(C)
> print('C[i, 0] is')
> pprint(C[i, 0])
> ```
> I get this output:
> ```
> C is
> ⎡A⎤
> ⎢ ⎥
> ⎣B⎦
> C[i, 0] is
> (A)[i, 0]
> ```
> `(A)[i, 0]` is the wrong here. `C[i, 0]` should not be simplified as that element may come from either `A` or `B`.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/matrices/expressions/blockmatrix.py", "BlockMatrix._entry"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=114481/19494；耗时=1615.4秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 32, "causal": 38}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-19007.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-19007.jsonl)

## 274. sympy__sympy-19254

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> sympy.polys.factortools.dmp_zz_mignotte_bound improvement
> The method `dup_zz_mignotte_bound(f, K)` can be significantly improved by using the **Knuth-Cohen bound** instead. After our research with Prof. Ag.Akritas we have implemented the Knuth-Cohen bound among others, and compare them among dozens of polynomials with different degree, density and coefficients range. Considering the results and the feedback from Mr.Kalevi Suominen, our proposal is that the mignotte_bound should be replaced by the knuth-cohen bound.
> Also, `dmp_zz_mignotte_bound(f, u, K)` for mutli-variants polynomials should be replaced appropriately.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]]`

新预测：`[["sympy/polys/compatibility.py", "IPolys.dup_zz_mignotte_bound"], ["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=8434/2152；耗时=251.8秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]], "seeds": [["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]], "causal_received": [["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]], "final": [["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]]}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 0, "causal": 7}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/polys/compatibility.py", "IPolys.dup_zz_mignotte_bound"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/polys/factortools.py", "dup_zz_mignotte_bound"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-19254.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-19254.jsonl)

## 275. sympy__sympy-19487

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Rewrite sign as abs
> In sympy the `sign` function is defined as
> ```
>     sign(z)  :=  z / Abs(z)
> ```
> for all complex non-zero `z`. There should be a way to rewrite the sign in terms of `Abs` e.g.:
> ```
> >>> sign(x).rewrite(Abs)                                                                                                                   
>  x 
> ───
> │x│
> ```
> I'm not sure how the possibility of `x` being zero should be handled currently we have
> ```
> >>> sign(0)                                                                                                                               
> 0
> >>> 0 / Abs(0)                                                                                                                            
> nan
> ```
> Maybe `sign(0)` should be `nan` as well. Otherwi

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/functions/elementary/complexes.py", "sign._eval_rewrite_as_Abs"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=67299/9900；耗时=1126.7秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 5, "relevance": 3, "causal": 193}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-19487.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-19487.jsonl)

## 276. sympy__sympy-20049

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Point.vel() should calculate the velocity if possible
> If you specify the orientation of two reference frames and then ask for the angular velocity between the two reference frames the angular velocity will be calculated. But if you try to do the same thing with velocities, this doesn't work. See below:
> 
> ```
> In [1]: import sympy as sm                                                                               
> 
> In [2]: import sympy.physics.mechanics as me                                                             
> 
> In [3]: A = me.ReferenceFrame('A')                                                                       
> 
> In [5]: q = me.dynamicsymbols('q')                                                                       
> 
> In [6]: B = A.orientnew('B', 'Axis', (q, A.x))      

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/physics/vector/point.py", "Point.vel"]]`

新预测：`[["sympy/physics/vector/frame.py", "_check_frame"], ["sympy/physics/vector/point.py", "Point.a1pt_theory"], ["sympy/physics/vector/point.py", "Point.partial_velocity"], ["sympy/physics/vector/point.py", "Point.vel"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=55132/15622；耗时=1248.1秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/physics/vector/point.py", "Point.vel"]], "seeds": [["sympy/physics/vector/point.py", "Point.vel"]], "causal_received": [["sympy/physics/vector/point.py", "Point.vel"]], "final": [["sympy/physics/vector/point.py", "Point.vel"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 33}`。

- A1：Incorrect computation；依据：；关联：`[["", "self._vel_dict"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/physics/vector/point.py", "Point.vel"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/physics/vector/point.py", "Point"]]`
- C1：Empty velocity dictionary；依据：；关联：`[["", "self._vel_dict"]]`
- D1：Partial velocity calculations；依据：；关联：`[["sympy/physics/vector/point.py", "Point.partial_velocity"]]`
- D2：Acceleration calculations；依据：；关联：`[["sympy/physics/vector/point.py", "Point.a1pt_theory"]]`
- E1：Type checking failure；依据：；关联：`[["sympy/physics/vector/frame.py", "_check_frame"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-20049.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20049.jsonl)

## 277. sympy__sympy-20154

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> partitions() reusing the output dictionaries
> The partitions() iterator in sympy.utilities.iterables reuses the output dictionaries. There is a caveat about it in the docstring. 
> 
> I'm wondering if it's really that important for it to do this. It shouldn't be that much of a performance loss to copy the dictionary before yielding it. This behavior is very confusing. It means that something as simple as list(partitions()) will give an apparently wrong result. And it can lead to much more subtle bugs if the partitions are used in a nontrivial way. 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/utilities/iterables.py", "partitions"]]`

新预测：`[["sympy/utilities/iterables.py", "partitions"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=87751/6547；耗时=646.4秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/utilities/iterables.py", "partitions"]], "seeds": [["sympy/utilities/iterables.py", "partitions"]], "causal_received": [["sympy/utilities/iterables.py", "partitions"]], "final": [["sympy/utilities/iterables.py", "partitions"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 15}`。

- A：Reusing output dictionaries；依据：；关联：`[["sympy/utilities/iterables.py", "partitions"]]`
- B：Confusion due to shared state；依据：；关联：`[["sympy/utilities/iterables.py", "partitions"]]`
- C：Subtle bugs in complex usage；依据：；关联：`[["sympy/utilities/iterables.py", "partitions"]]`
- D：Performance gain by avoiding copying；依据：；关联：`[["sympy/utilities/iterables.py", "partitions"]]`
- E：Documentation does not clearly state the behavior；依据：；关联：`[["sympy/utilities/iterables.py", "partitions"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-20154.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20154.jsonl)

## 278. sympy__sympy-20212

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> 0**-oo produces 0, the documentation says it should produce zoo
> Using SymPy 1.5.1, evaluate `0**-oo` produces `0`.
> 
> The documentation for the Pow class states that it should return `ComplexInfinity`, aka `zoo`
> 
> | expr | value | reason |
> | :-- | :-- | :--|
> | `0**-oo` | `zoo` | This is not strictly true, as 0**oo may be oscillating between positive and negative values or rotating in the complex plane. It is convenient, however, when the base is positive.|
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/power.py", "Pow.__new__"]]`

新预测：`[["sympy/core/expr.py", "Expr.__pow__"], ["sympy/core/expr.py", "Expr._pow"], ["sympy/core/numbers.py", "mod_inverse"], ["sympy/polys/fields.py", "FracElement.__pow__"], ["sympy/polys/polytools.py", "Poly.pow"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=61144/5243；耗时=670.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 32, "causal": 56}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/core/numbers.py", "mod_inverse"], ["sympy/core/expr.py", "Expr._pow"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.__pow__"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/polys/polytools.py", "Poly.pow"], ["sympy/core/expr.py", "Expr._pow"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/polys/fields.py", "FracElement.__pow__"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/polys/fields.py", "FracElement.__pow__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-20212.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20212.jsonl)

## 279. sympy__sympy-20322

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Inconsistent behavior for sympify/simplify with ceiling
> In sympy v1.5.1:
> ```python
> In [16]: sympy.sympify('4*ceiling(x/4 - 3/4)', evaluate=False).simplify()
> Out[16]: 4*ceiling(x/4 - 3/4)
> 
> In [17]: sympy.sympify('4*ceiling(x/4 - 3/4)', evaluate=True).simplify()
> Out[17]: 4*ceiling(x/4 - 3/4)
> ```
> 
> In sympy v.1.6.2:
> ```python
> In [16]: sympy.sympify('4*ceiling(x/4 - 3/4)', evaluate=False).simplify()
> Out[16]: 4*ceiling(x/4) - 3
> 
> In [17]: sympy.sympify('4*ceiling(x/4 - 3/4)', evaluate=True).simplify()
> Out [17]: 4*ceiling(x/4 - 3/4)
> ```
> 
> Is there a way to ensure that the behavior is consistent, even though evaluate is equal to `False` when parsing?

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/mul.py", "Mul._eval_is_integer"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=25429/950；耗时=231.1秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 13, "causal": 4}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-20322.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20322.jsonl)

## 280. sympy__sympy-20442

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> convert_to seems to combine orthogonal units
> Tested in sympy 1.4, not presently in a position to install 1.5+.
> Simple example. Consider `J = kg*m**2/s**2 => J*s = kg*m**2/s`. The convert_to behavior is odd:
> ```
> >>>convert_to(joule*second,joule)
>     joule**(7/9)
> ```
> I would expect the unchanged original expression back, an expression in terms of base units, or an error. It appears that convert_to can only readily handle conversions where the full unit expression is valid.
> 
> Note that the following three related examples give sensible results:
> ```
> >>>convert_to(joule*second,joule*second)
>     joule*second
> ```
> ```
> >>>convert_to(J*s, kg*m**2/s)
>     kg*m**2/s
> ```
> ```
> >>>convert_to(J*s,mins)
>     J*mins/60
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/physics/units/util.py", "_get_conversion_matrix_for_expr"]]`

新预测：`[["sympy/physics/units/quantities.py", "Quantity.convert_to"], ["sympy/physics/units/tests/test_quantities.py", "test_add_sub"], ["sympy/physics/units/tests/test_quantities.py", "test_conversion_with_2_nonstandard_dimensions"], ["sympy/physics/units/tests/test_quantities.py", "test_convert_to"], ["sympy/physics/units/tests/test_quantities.py", "test_deprecated_quantity_methods"], ["sympy/physics/units/tests/test_quantities.py", "test_issue_quart"], ["sympy/physics/units/tests/test_quantities.py", "test_mul_div"], ["sympy/physics/units/tests/test_quantities.py", "test_units"], ["sympy/physics/units/util.py", "convert_to"], ["sympy/polys/domainmatrix.py", "DomainMatrix.convert_to"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=44293/12480；耗时=1033.4秒。

阶段诊断：因果收到目标实体但未保留；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [["sympy/physics/units/util.py", "_get_conversion_matrix_for_expr"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 24}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/physics/units/tests/test_quantities.py", "test_units"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/physics/units/quantities.py", "Quantity.convert_to"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/physics/units/tests/test_quantities.py", "test_mul_div"]]`
- D：Unit compatibility check failure；依据：；关联：`[["sympy/physics/units/tests/test_quantities.py", "test_units"], ["sympy/physics/units/tests/test_quantities.py", "test_mul_div"], ["sympy/physics/units/tests/test_quantities.py", "test_convert_to"], ["sympy/physics/units/tests/test_quantities.py", "test_deprecated_quantity_methods"], ["sympy/physics/units/tests/test_quantities.py", "test_issue_quart"], ["sympy/physics/units/tests/test_quantities.py", "test_conversion_with_2_nonstandard_dimensions"], ["sympy/physics/units/util.py", "convert_to"], ["sympy/physics/units/tests/test_quantities.py", "test_add_sub"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/polys/domainmatrix.py", "DomainMatrix.convert_to"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/polys/domainmatrix.py", "DomainMatrix.convert_to"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-20442.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20442.jsonl)

## 281. sympy__sympy-20590

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Symbol instances have __dict__ since 1.7?
> In version 1.6.2 Symbol instances had no `__dict__` attribute
> ```python
> >>> sympy.Symbol('s').__dict__
> ---------------------------------------------------------------------------
> AttributeError                            Traceback (most recent call last)
> <ipython-input-3-e2060d5eec73> in <module>
> ----> 1 sympy.Symbol('s').__dict__
> 
> AttributeError: 'Symbol' object has no attribute '__dict__'
> >>> sympy.Symbol('s').__slots__
> ('name',)
> ```
> 
> This changes in 1.7 where `sympy.Symbol('s').__dict__` now exists (and returns an empty dict)
> I may misinterpret this, but given the purpose of `__slots__`, I assume this is a bug, introduced because some parent class accidentally stopped defining `__slots__`.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | NA | NA | NA | NA | NA |
| CoSIL/off | NA | NA | NA | NA | NA |
| GraphLocator/Qwen | NA | NA | NA | NA | NA |
| GraphLocator/Qwen-适配v2 | NA | NA | NA | NA | NA |

共同严格目标：`[]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=5194/969；耗时=115.0秒。

阶段诊断：NA；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 5, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-20590.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20590.jsonl)

## 282. sympy__sympy-20639

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> inaccurate rendering of pi**(1/E)
> This claims to be version 1.5.dev; I just merged from the project master, so I hope this is current.  I didn't notice this bug among others in printing.pretty.
> 
> ```
> In [52]: pi**(1/E)                                                               
> Out[52]: 
> -1___
> ╲╱ π 
> 
> ```
> LaTeX and str not fooled:
> ```
> In [53]: print(latex(pi**(1/E)))                                                 
> \pi^{e^{-1}}
> 
> In [54]: str(pi**(1/E))                                                          
> Out[54]: 'pi**exp(-1)'
> ```
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_Pow"], ["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_nth_root"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=22008/1475；耗时=293.5秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 5, "causal": 22}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-20639.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-20639.jsonl)

## 283. sympy__sympy-21055

项目：sympy/sympy；本轮子集：开发集；状态：failed。

问题描述节选：

> `refine()` does not understand how to simplify complex arguments
> Just learned about the refine-function, which would come in handy frequently for me.  But
> `refine()` does not recognize that argument functions simplify for real numbers.
> 
> ```
> >>> from sympy import *                                                     
> >>> var('a,x')                                                              
> >>> J = Integral(sin(x)*exp(-a*x),(x,0,oo))                                     
> >>> J.doit()
> 	Piecewise((1/(a**2 + 1), 2*Abs(arg(a)) < pi), (Integral(exp(-a*x)*sin(x), (x, 0, oo)), True))
> >>> refine(J.doit(),Q.positive(a))                                                 
>         Piecewise((1/(a**2 + 1), 2*Abs(arg(a)) < pi), (Integral(exp(-a*x)*sin(x), (x, 0, oo)), True))
> >>> refine(abs(a),Q

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/assumptions/refine.py", "refine_arg"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=7574/1244；耗时=219.5秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 5, "causal": 10}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-21055.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21055.jsonl)

## 284. sympy__sympy-21171

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> _print_SingularityFunction() got an unexpected keyword argument 'exp'
> On a Jupyter Notebook cell, type the following:
> 
> ```python
> from sympy import *
> from sympy.physics.continuum_mechanics import Beam
> # Young's modulus
> E = symbols("E")
> # length of the beam
> L = symbols("L")
> # concentrated load at the end tip of the beam
> F = symbols("F")
> # square cross section
> B, H = symbols("B, H")
> I = B * H**3 / 12
> # numerical values (material: steel)
> d = {B: 1e-02, H: 1e-02, E: 210e09, L: 0.2, F: 100}
> 
> b2 = Beam(L, E, I)
> b2.apply_load(-F, L / 2, -1)
> b2.apply_support(0, "fixed")
> R0, M0 = symbols("R_0, M_0")
> b2.solve_for_reaction_loads(R0, M0)
> ```
> 
> Then:
> 
> ```
> b2.shear_force()
> ```
> 
> The following error appears:
> ```
> ----------------------------------------------------------------

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/latex.py", "LatexPrinter._print_SingularityFunction"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=21732/1307；耗时=288.4秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["sympy/printing/latex.py", "LatexPrinter._print_SingularityFunction"]], "seeds": [], "causal_received": [["sympy/printing/latex.py", "LatexPrinter._print_SingularityFunction"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 6}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-21171.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21171.jsonl)

## 285. sympy__sympy-21379

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> Unexpected `PolynomialError` when using simple `subs()` for particular expressions
> I am seeing weird behavior with `subs` for particular expressions with hyperbolic sinusoids with piecewise arguments. When applying `subs`, I obtain an unexpected `PolynomialError`. For context, I was umbrella-applying a casting from int to float of all int atoms for a bunch of random expressions before using a tensorflow lambdify to avoid potential tensorflow type errors. You can pretend the expression below has a `+ 1` at the end, but below is the MWE that I could produce.
> 
> See the expression below, and the conditions in which the exception arises.
> 
> Sympy version: 1.8.dev
> 
> ```python
> from sympy import *
> from sympy.core.cache import clear_cache
> 
> x, y, z = symbols('x y z')
> 
> clear_cache()
> expr = e

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/mod.py", "Mod.eval"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=16137/611；耗时=167.5秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 9, "causal": 2}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-21379.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21379.jsonl)

## 286. sympy__sympy-21612

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Latex parsing of fractions yields wrong expression due to missing brackets
> Problematic latex expression: `"\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}"`
> 
> is parsed to: `((a**3 + b)/c)/1/(c**2)`.
> 
> Expected is: `((a**3 + b)/c)/(1/(c**2))`. 
> 
> The missing brackets in the denominator result in a wrong expression.
> 
> ## Tested on
> 
> - 1.8
> - 1.6.2
> 
> ## Reproduce:
> 
> ```
> root@d31ef1c26093:/# python3
> Python 3.6.9 (default, Jan 26 2021, 15:33:00)
> [GCC 8.4.0] on linux
> Type "help", "copyright", "credits" or "license" for more information.
> >>> from sympy.parsing.latex import parse_latex
> >>> parse_latex("\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}")
> ((a**3 + b)/c)/1/(c**2)
> 
> 

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/str.py", "StrPrinter._print_Mul"]]`

新预测：`[["sympy/parsing/latex/__init__.py", "parse_latex"], ["sympy/parsing/latex/_parse_latex_antlr.py", "parse_latex"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=14053/2369；耗时=274.8秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 5}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/parsing/latex/__init__.py", "parse_latex"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/parsing/latex/_parse_latex_antlr.py", "parse_latex"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/parsing/latex/_parse_latex_antlr.py", "parse_latex"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-21612.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21612.jsonl)

## 287. sympy__sympy-21614

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Wrong Derivative kind attribute
> I'm playing around with the `kind` attribute.
> 
> The following is correct:
> 
> ```
> from sympy import Integral, Derivative
> from sympy import MatrixSymbol
> from sympy.abc import x
> A = MatrixSymbol('A', 2, 2)
> i = Integral(A, x)
> i.kind
> # MatrixKind(NumberKind)
> ```
> 
> This one is wrong:
> ```
> d = Derivative(A, x)
> d.kind
> # UndefinedKind
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/core/function.py", "Derivative.kind"]]`

新预测：`[["sympy/core/function.py", "<unresolved>:Derivative.eval"], ["sympy/core/function.py", "Derivative._diff_wrt"]]`

搜索种子 2；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=43417/10087；耗时=968.0秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 7, "causal": 51}`。

无法唯一映射的函数：`[{"file": "sympy/core/function.py", "name": "Derivative.eval", "reason": "absent"}]`

- A1：Incorrect computation；依据：；关联：`[["sympy/core/function.py", "Derivative._diff_wrt"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/function.py", "Derivative"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/core/function.py", "Derivative.eval"]]`
- D：Incorrect _diff_wrt implementation；依据：；关联：`[["sympy/core/function.py", "Derivative._diff_wrt"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-21614.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21614.jsonl)

## 288. sympy__sympy-21627

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Bug: maximum recusion depth error when checking is_zero of cosh expression
> The following code causes a `RecursionError: maximum recursion depth exceeded while calling a Python object` error when checked if it is zero:
> ```
> expr =sympify("cosh(acos(-i + acosh(-g + i)))")
> expr.is_zero
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/functions/elementary/complexes.py", "Abs.eval"]]`

新预测：`[["sympy/functions/combinatorial/factorials.py", "factorial2.eval"], ["sympy/utilities/tests/test_wester.py", "test_X15"]]`

搜索种子 4；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=27939/4540；耗时=469.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 4, "relevance": 32, "causal": 12}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/functions/combinatorial/factorials.py", "factorial2.eval"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/utilities/tests/test_wester.py", "test_X15"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/utilities/tests/test_wester.py", "test_X15"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-21627.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21627.jsonl)

## 289. sympy__sympy-21847

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> itermonomials returns incorrect monomials when using min_degrees argument
> `itermonomials` returns incorrect monomials when using optional `min_degrees` argument
> 
> For example, the following code introduces three symbolic variables and generates monomials with max and min degree of 3:
> 
> 
> ```
> import sympy as sp
> from sympy.polys.orderings import monomial_key
> 
> x1, x2, x3 = sp.symbols('x1, x2, x3')
> states = [x1, x2, x3]
> max_degrees = 3
> min_degrees = 3
> monomials = sorted(sp.itermonomials(states, max_degrees, min_degrees=min_degrees), 
>                    key=monomial_key('grlex', states))
> print(monomials)
> ```
> The code returns `[x3**3, x2**3, x1**3]`, when it _should_ also return monomials such as `x1*x2**2, x2*x3**2, etc...` that also have total degree of 3. This behaviour is incon

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/polys/monomials.py", "itermonomials"]]`

新预测：`[["sympy/polys/monomials.py", "itermonomials"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=22037/1705；耗时=213.1秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/polys/monomials.py", "itermonomials"]], "seeds": [["sympy/polys/monomials.py", "itermonomials"]], "causal_received": [["sympy/polys/monomials.py", "itermonomials"]], "final": [["sympy/polys/monomials.py", "itermonomials"]]}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 6}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/polys/monomials.py", "itermonomials"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-21847.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-21847.jsonl)

## 290. sympy__sympy-22005

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> detection of infinite solution request
> ```python
> >>> solve_poly_system((x - 1,), x, y)
> Traceback (most recent call last):
> ...
> NotImplementedError:
> only zero-dimensional systems supported (finite number of solutions)
> >>> solve_poly_system((y - 1,), x, y)  <--- this is not handled correctly
> [(1,)]
> ```
> ```diff
> diff --git a/sympy/solvers/polysys.py b/sympy/solvers/polysys.py
> index b9809fd4e9..674322d4eb 100644
> --- a/sympy/solvers/polysys.py
> +++ b/sympy/solvers/polysys.py
> @@ -240,7 +240,7 @@ def _solve_reduced_system(system, gens, entry=False):
>  
>          univariate = list(filter(_is_univariate, basis))
>  
> -        if len(univariate) == 1:
> +        if len(univariate) == 1 and len(gens) == 1:
>              f = univariate.pop()
>          else:
>              raise NotImplementedE

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/solvers/polysys.py", "solve_generic._solve_reduced_system"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=33382/3939；耗时=438.7秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 32, "causal": 15}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-22005.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-22005.jsonl)

## 291. sympy__sympy-22714

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> simpify gives `Imaginary coordinates are not permitted.` with evaluate(False)
> ## Issue
> `with evaluate(False)` crashes unexpectedly with `Point2D`
> 
> ## Code
> ```python
> import sympy as sp
> with sp.evaluate(False):
>   sp.S('Point2D(Integer(1),Integer(2))')
> ```
> 
> ## Error
> ```
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "/home/avinash/.local/lib/python3.8/site-packages/sympy/core/sympify.py", line 472, in sympify
>     expr = parse_expr(a, local_dict=locals, transformations=transformations, evaluate=evaluate)
>   File "/home/avinash/.local/lib/python3.8/site-packages/sympy/parsing/sympy_parser.py", line 1026, in parse_expr
>     raise e from ValueError(f"Error from parse_expr with transformed code: {code!r}")
>   File "/home/avinash/.local/lib/python3.8/

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |
| CoSIL/off | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/geometry/point.py", "Point.__new__"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=26129/4416；耗时=373.6秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 35, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-22714.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-22714.jsonl)

## 292. sympy__sympy-22840

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> cse() has strange behaviour for MatrixSymbol indexing
> Example: 
> ```python
> import sympy as sp
> from pprint import pprint
> 
> 
> def sub_in_matrixsymbols(exp, matrices):
>     for matrix in matrices:
>         for i in range(matrix.shape[0]):
>             for j in range(matrix.shape[1]):
>                 name = "%s_%d_%d" % (matrix.name, i, j)
>                 sym = sp.symbols(name)
>                 exp = exp.subs(sym, matrix[i, j])
>     return exp
> 
> 
> def t44(name):
>     return sp.Matrix(4, 4, lambda i, j: sp.symbols('%s_%d_%d' % (name, i, j)))
> 
> 
> # Construct matrices of symbols that work with our
> # expressions. (MatrixSymbols does not.)
> a = t44("a")
> b = t44("b")
> 
> # Set up expression. This is a just a simple example.
> e = a * b
> 
> # Put in matrixsymbols. (Gives array-input in codegen.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/simplify/cse_main.py", "tree_cse"], ["sympy/simplify/cse_main.py", "tree_cse._find_repeated"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=102372/9644；耗时=1074.8秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 2, "causal": 74}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-22840.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-22840.jsonl)

## 293. sympy__sympy-23117

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> sympy.Array([]) fails, while sympy.Matrix([]) works
> SymPy 1.4 does not allow to construct empty Array (see code below). Is this the intended behavior?
> 
> ```
> >>> import sympy
> KeyboardInterrupt
> >>> import sympy
> >>> from sympy import Array
> >>> sympy.__version__
> '1.4'
> >>> a = Array([])
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "/Users/hcui7/miniconda3/envs/a/lib/python3.7/site-packages/sympy/tensor/array/dense_ndim_array.py", line 130, in __new__
>     return cls._new(iterable, shape, **kwargs)
>   File "/Users/hcui7/miniconda3/envs/a/lib/python3.7/site-packages/sympy/tensor/array/dense_ndim_array.py", line 136, in _new
>     shape, flat_list = cls._handle_ndarray_creation_inputs(iterable, shape, **kwargs)
>   File "/Users/hcui7/miniconda3/envs/a/li

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/tensor/array/ndim_array.py", "NDimArray._check_index_for_getitem"], ["sympy/tensor/array/ndim_array.py", "NDimArray._parse_index"], ["sympy/tensor/array/ndim_array.py", "NDimArray._scan_iterable_shape.f"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=24545/2169；耗时=211.9秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 34, "causal": 0}`。

- A：Inaccurate recursive check；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-23117.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-23117.jsonl)

## 294. sympy__sympy-23191

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> display bug while using pretty_print with sympy.vector object in the terminal
> The following code jumbles some of the outputs in the terminal, essentially by inserting the unit vector in the middle -
> ```python
> from sympy import *
> from sympy.vector import CoordSys3D, Del
> 
> init_printing()
> 
> delop = Del()
> CC_ = CoordSys3D("C")
> x,    y,    z    = CC_.x, CC_.y, CC_.z
> xhat, yhat, zhat = CC_.i, CC_.j, CC_.k
> 
> t = symbols("t")
> ten = symbols("10", positive=True)
> eps, mu = 4*pi*ten**(-11), ten**(-5)
> 
> Bx = 2 * ten**(-4) * cos(ten**5 * t) * sin(ten**(-3) * y)
> vecB = Bx * xhat
> vecE = (1/eps) * Integral(delop.cross(vecB/mu).doit(), t)
> 
> pprint(vecB)
> print()
> pprint(vecE)
> print()
> pprint(vecE.doit())
> ```
> 
> Output:
> ```python
> ⎛     ⎛y_C⎞    ⎛  5  ⎞⎞    
> ⎜2⋅sin⎜───⎟ i_C⋅cos⎝10 ⋅t⎠⎟
> ⎜

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/printing/pretty/pretty.py", "PrettyPrinter._print_BasisDependent"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=21553/5147；耗时=499.8秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 0, "causal": 13}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-23191.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-23191.jsonl)

## 295. sympy__sympy-23262

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Python code printer not respecting tuple with one element
> Hi,
> 
> Thanks for the recent updates in SymPy! I'm trying to update my code to use SymPy 1.10 but ran into an issue with the Python code printer. MWE:
> 
> 
> ```python
> import inspect
> from sympy import lambdify
> 
> inspect.getsource(lambdify([], tuple([1])))
> ```
> SymPy 1.9 and under outputs:
> ```
> 'def _lambdifygenerated():\n    return (1,)\n'
> ```
> 
> But SymPy 1.10 gives
> 
> ```
> 'def _lambdifygenerated():\n    return (1)\n'
> ```
> Note the missing comma after `1` that causes an integer to be returned instead of a tuple. 
> 
> For tuples with two or more elements, the generated code is correct:
> ```python
> inspect.getsource(lambdify([], tuple([1, 2])))
> ```
> In SymPy  1.10 and under, outputs:
> 
> ```
> 'def _lambdifygenerated():\n    retu

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/utilities/lambdify.py", "_recursive_to_string"]]`

新预测：`[]`

搜索种子 0；搜索停止=empty_seeds:model_finish；因果停止=legacy_causal_stop；输入/输出token=13412/4193；耗时=334.5秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 0, "relevance": 32, "causal": 0}`。

- A1：Incorrect computation；依据：；关联：`[]`
- A：Inaccurate recursive check；依据：；关联：`[]`
- A2：Wrong logic；依据：；关联：`[]`
- B：Incorrect handling of commutative factors；依据：；关联：`[]`
- C：Dependency on Product；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-23262.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-23262.jsonl)

## 296. sympy__sympy-24066

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> SI._collect_factor_and_dimension() cannot properly detect that exponent is dimensionless
> How to reproduce:
> 
> ```python
> from sympy import exp
> from sympy.physics import units
> from sympy.physics.units.systems.si import SI
> 
> expr = units.second / (units.ohm * units.farad)
> dim = SI._collect_factor_and_dimension(expr)[1]
> 
> assert SI.get_dimension_system().is_dimensionless(dim)
> 
> buggy_expr = 100 + exp(expr)
> SI._collect_factor_and_dimension(buggy_expr)
> 
> # results in ValueError: Dimension of "exp(second/(farad*ohm))" is Dimension(time/(capacitance*impedance)), but it should be Dimension(1)
> ```

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen | 100.00% | 100.00% | 100.00% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 25.00% | 100.00% | 40.00% | 100.00% | 命中 |

共同严格目标：`[["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]]`

新预测：`[["sympy/physics/units/quantities.py", "Quantity._collect_factor_and_dimension"], ["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"], ["sympy/physics/units/unitsystem.py", "UnitSystem.get_dimension_system"], ["sympy/physics/units/unitsystem.py", "UnitSystem.get_dimensional_expr"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=48327/12935；耗时=1102.6秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]], "seeds": [["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]], "causal_received": [["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]], "final": [["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 52}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/physics/units/unitsystem.py", "UnitSystem.get_dimensional_expr"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/physics/units/quantities.py", "Quantity._collect_factor_and_dimension"]]`
- A2：Wrong logic；依据：；关联：`[["", "self._derived_units"]]`
- G：Exponential of Dimensional Expression；依据：；关联：`[]`
- H：Dimension Handling in Simplification；依据：；关联：`[]`
- E：exp function；依据：；关联：`[]`
- F：Issue；依据：；关联：`[]`
- D1：UnitSystem；依据：；关联：`[["sympy/physics/units/unitsystem.py", "UnitSystem"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]]`
- D2：Dimension；依据：；关联：`[["sympy/physics/units/dimensions.py", "Dimension"]]`
- D3：get_dimension_system；依据：；关联：`[["sympy/physics/units/unitsystem.py", "UnitSystem.get_dimension_system"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-24066.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-24066.jsonl)

## 297. sympy__sympy-24102

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Cannot parse Greek characters (and possibly others) in parse_mathematica
> The old Mathematica parser `mathematica` in the package `sympy.parsing.mathematica` was able to parse e.g. Greek characters. Hence the following example works fine:
> ```
> from sympy.parsing.mathematica import mathematica
> mathematica('λ')
> Out[]: 
> λ
> ```
> 
> As of SymPy v. 1.11, the `mathematica` function is deprecated, and is replaced by `parse_mathematica`. This function, however, seems unable to handle the simple example above:
> ```
> from sympy.parsing.mathematica import parse_mathematica
> parse_mathematica('λ')
> Traceback (most recent call last):
> ...
> File "<string>", line unknown
> SyntaxError: unable to create a single AST for the expression
> ```
> 
> This appears to be due to a bug in `parse_mathematica`, which i

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| CoSIL/off | 33.33% | 100.00% | 50.00% | 100.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/parsing/mathematica.py", "MathematicaParser._from_mathematica_to_tokens"]]`

新预测：`[["sympy/parsing/mathematica.py", "parse_mathematica"]]`

搜索种子 1；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=34484/10749；耗时=826.3秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 1, "relevance": 2, "causal": 3}`。

- A1：Deprecation of old Mathematica parser；依据：；关联：`[]`
- A2：Lack of support for Greek characters in new parser；依据：；关联：`[]`
- A3：Change in implementation logic between parsers；依据：；关联：`[]`
- A：Deprecation of old Mathematica parser；依据：；关联：`[["sympy/parsing/mathematica.py", "parse_mathematica"]]`
- B：Lack of support for Greek characters in new parser；依据：；关联：`[["sympy/parsing/mathematica.py", "parse_mathematica"]]`
- C：Change in implementation logic between parsers；依据：；关联：`[["sympy/parsing/mathematica.py", "parse_mathematica"]]`
- D：MathematicaParser class；依据：；关联：`[]`
- E：parse method；依据：；关联：`[]`
- F：test_mathematica function；依据：；关联：`[]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-24102.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-24102.jsonl)

## 298. sympy__sympy-24152

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Bug in expand of TensorProduct + Workaround + Fix
> ### Error description
> The expansion of a TensorProduct object stops incomplete if summands in the tensor product factors have (scalar) factors, e.g.
> ```
> from sympy import *
> from sympy.physics.quantum import *
> U = Operator('U')
> V = Operator('V')
> P = TensorProduct(2*U - V, U + V)
> print(P) 
> # (2*U - V)x(U + V)
> print(P.expand(tensorproduct=True)) 
> #result: 2*Ux(U + V) - Vx(U + V) #expansion has missed 2nd tensor factor and is incomplete
> ```
> This is clearly not the expected behaviour. It also effects other functions that rely on .expand(tensorproduct=True), as e.g. qapply() .
> 
> ### Work around
> Repeat .expand(tensorproduct=True) as may times as there are tensor factors, resp. until the expanded term does no longer change. This is h

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 50.00% | 100.00% | 66.67% | 100.00% | 命中 |

共同严格目标：`[["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]]`

新预测：`[["sympy/core/expr.py", "Expr.args_cnc"], ["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]]`

搜索种子 3；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=31671/2656；耗时=409.3秒。

阶段诊断：最终覆盖全部目标；各阶段实际覆盖目标：`{"search_received": [["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]], "seeds": [["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]], "causal_received": [["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]], "final": [["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]]}`。

各角色实际收到显式函数体数：`{"main_search": 3, "relevance": 0, "causal": 18}`。

- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/expr.py", "Expr.args_cnc"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/physics/quantum/tensorproduct.py", "TensorProduct._eval_expand_tensorproduct"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-24152.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-24152.jsonl)

## 299. sympy__sympy-24213

项目：sympy/sympy；本轮子集：验证集；状态：failed。

问题描述节选：

> collect_factor_and_dimension does not detect equivalent dimensions in addition
> Code to reproduce:
> ```python
> from sympy.physics import units
> from sympy.physics.units.systems.si import SI
> 
> v1 = units.Quantity('v1')
> SI.set_quantity_dimension(v1, units.velocity)
> SI.set_quantity_scale_factor(v1, 2 * units.meter / units.second)
> 
> a1 = units.Quantity('a1')
> SI.set_quantity_dimension(a1, units.acceleration)
> SI.set_quantity_scale_factor(a1, -9.8 * units.meter / units.second**2)
> 
> t1 = units.Quantity('t1')
> SI.set_quantity_dimension(t1, units.time)
> SI.set_quantity_scale_factor(t1, 5 * units.second)
> 
> expr1 = a1*t1 + v1
> SI._collect_factor_and_dimension(expr1)
> ```
> Results in:
> ```
> Traceback (most recent call last):
>   File "<stdin>", line 1, in <module>
>   File "C:\Python\Python310\lib

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| CoSIL/off | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen | 20.00% | 100.00% | 33.33% | 100.00% | 命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]]`

新预测：`[]`

搜索种子 0；搜索停止=未完成；因果停止=未完成；输入/输出token=30250/9409；耗时=865.7秒。

阶段诊断：运行失败；各阶段实际覆盖目标：`{"search_received": [["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]], "seeds": [], "causal_received": [["sympy/physics/units/unitsystem.py", "UnitSystem._collect_factor_and_dimension"]], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 2, "relevance": 0, "causal": 18}`。

故障：ContextBudgetExceeded；Local Qwen context budget exceeded


源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/failures/sympy__sympy-24213.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-24213.jsonl)

## 300. sympy__sympy-24909

项目：sympy/sympy；本轮子集：验证集；状态：complete。

问题描述节选：

> Bug with milli prefix
> What happened:
> ```
> In [1]: from sympy.physics.units import milli, W
> In [2]: milli*W == 1
> Out[2]: True
> In [3]: W*milli
> Out[3]: watt*Prefix(milli, m, -3, 10)
> ```
> What I expected to happen: milli*W should evaluate to milli watts / mW
> 
> `milli*W` or more generally `milli` times some unit evaluates to the number 1. I have tried this with Watts and Volts, I'm not sure what other cases this happens. I'm using sympy version 1.11.1-1 on Arch Linux with Python 3.10.9. If you cannot reproduce I would be happy to be of any assitance.

| 条件 | 严格P | 严格R | 严格F1 | SL | Top-5 |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 20.00% | 50.00% | 28.57% | 0.00% | 命中 |
| CoSIL/off | 50.00% | 50.00% | 50.00% | 0.00% | 命中 |
| GraphLocator/Qwen | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |
| GraphLocator/Qwen-适配v2 | 0.00% | 0.00% | 0.00% | 0.00% | 未命中 |

共同严格目标：`[["sympy/physics/units/prefixes.py", "Prefix.__mul__"], ["sympy/physics/units/prefixes.py", "Prefix.__truediv__"]]`

新预测：`[["sympy/core/exprtools.py", "Factors.__mul__"], ["sympy/core/exprtools.py", "Factors.mul"], ["sympy/core/numbers.py", "Float.__mul__"], ["sympy/core/numbers.py", "Integer.__mul__"], ["sympy/core/numbers.py", "Number.__mul__"], ["sympy/core/numbers.py", "Rational.__mul__"]]`

搜索种子 10；搜索停止=model_finish；因果停止=legacy_causal_stop；输入/输出token=88825/15367；耗时=1423.7秒。

阶段诊断：目标函数实体未送达模型；各阶段实际覆盖目标：`{"search_received": [], "seeds": [], "causal_received": [], "final": []}`。

各角色实际收到显式函数体数：`{"main_search": 9, "relevance": 32, "causal": 65}`。

- A1：Incorrect computation；依据：；关联：`[["sympy/core/exprtools.py", "Factors.mul"]]`
- A：Inaccurate recursive check；依据：；关联：`[["sympy/core/exprtools.py", "Factors.__mul__"]]`
- A2：Wrong logic；依据：；关联：`[["sympy/core/mul.py", "mul"]]`
- C1：Dependency on Product；依据：；关联：`[["sympy/core/numbers.py", "Rational.__mul__"], ["sympy/core/numbers.py", "Float.__mul__"], ["sympy/core/numbers.py", "Integer.__mul__"]]`
- E1：mul function in exprtools.py；依据：；关联：`[["sympy/core/exprtools.py", "Factors.mul"]]`
- D：Issue；依据：；关联：`[]`
- E2：Factors class in exprtools.py；依据：；关联：`[["sympy/core/exprtools.py", "Factors"]]`
- C：Dependency on Product；依据：；关联：`[["sympy/core/numbers.py", "Number.__mul__"]]`
- B：Incorrect handling of commutative factors；依据：；关联：`[["sympy/core/numbers.py", "Number.__mul__"]]`

源码送达缺口：`[]`；相关性未知项=0；因果校验错误项=0。

[原始结果](../../results/qwen_adapt_v2/full/B2/cases/sympy__sympy-24909.json) · [事件日志](../../results/qwen_adapt_v2/full/B2/events/sympy__sympy-24909.jsonl)

