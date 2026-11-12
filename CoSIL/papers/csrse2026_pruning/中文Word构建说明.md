# 中文 Word 构建说明

`scripts/build_chinese_docx.py` 使用 Python 标准库直接生成 Office Open XML 文档，无需 `python-docx`、联网服务或模型调用。

## 构建

```bash
python papers/csrse2026_pruning/scripts/build_chinese_docx.py
```

默认输入是 `chinese_manuscript.json`，默认输出是同目录的 `论文_中文版_17篇参考文献.docx`。也可显式指定 `--input` 和 `--output`。

JSON 顶层字段为 `title`、`title_en`、`author`、`affiliation`、`abstract`、`keywords`、`blocks`、`references`。正文块支持标题、段落、公式、图片和表格。参考文献引用写成 `{cite:key1,key2}`，构建时根据 `references` 中固定编号生成 `[n, m]`，未知引用或未被正文引用的条目会导致明确报错。正式文档要求 17 条唯一文献，编号连续。

## 可编辑性与排版

- 中文正文、标题、表格和参考文献均为可编辑 Word 元素。
- 四组数学公式为原生 OMML 数学对象，包括分式、上下标、分段函数和界限，不是公式截图。
- 四张图嵌入文档，可单独另存；标题与图片设置同页关联，表格重复表头并防止单行被拆开。
- A4 单栏、四边 2.2 cm，中文使用 Noto Serif CJK SC，西文使用 Times New Roman；正文 11 pt、1.15 倍行距。这是中文阅读版排版，不冒充会议官方 Word 模板。
- 页眉保留短标题，页脚为 Word PAGE 域。Word 打开后可正常更新页码。

## 检查方法

构建程序检查引用完整性、图片存在和 PNG 尺寸、表格列数、XML 可解析性、ZIP 完整性，以及实际嵌入图片和公式数量。输出回执列出文献、图片、表格、公式组数与文件大小。

可使用独立 LibreOffice 用户配置导出 PDF 目视核对，避免干扰已有桌面会话：

```bash
GSETTINGS_BACKEND=memory SAL_USE_VCLPLUGIN=svp \
libreoffice -env:UserInstallation=file:///tmp/csrse-word-preview \
  --headless --convert-to pdf:writer_pdf_Export \
  --outdir /tmp/csrse-word-preview-output \
  papers/csrse2026_pruning/论文_中文版_17篇参考文献.docx
```

构建器已通过独立临时样稿的 LibreOffice 打开/导出检查；正式文档还应使用最终内容再做一次完整分页与图表检查。临时样稿保存在 `/tmp`，未覆盖正式论文或历史实验文件。
