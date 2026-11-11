# 可选本地 OCR

扫描 PDF 可使用 Tesseract 识别。默认关闭，仅对没有可提取文字的页面执行 OCR；已有文字层保持原样。识别结果进入原有分块、向量缓存、检索和引用流程，保留 PDF 物理页码。引用新增 extraction_method，OCR 片段为 ocr。

## 安装与配置

在项目环境中安装可选 Python 依赖：

    python -m pip install -e ".[ocr]"

另行安装 Tesseract 和所需语言包，默认 chi_sim+eng。将程序加入 PATH，或在 AGENT_OCR_COMMAND 配置完整可执行文件路径（不要添加命令行参数）。

    AGENT_OCR_ENABLED=true
    AGENT_OCR_LANGUAGE=chi_sim+eng
    AGENT_OCR_TIMEOUT=60
    AGENT_OCR_COMMAND=tesseract
    AGENT_OCR_MAX_PAGES=30

配置变更后重启服务。语言或 OCR 开关等解析配置变化会使旧缓存失效，下次使用时重新构建。升级引擎或语言数据后应主动重建缓存。上传、启动恢复、评估和文档详情读取共用解析配置。

## 限制与错误

默认每份 PDF 最多识别 30 个无文字页（真正的空白页也计入），每页渲染约 200 DPI、最多 2000 万像素。Tesseract 子进程每页默认 60 秒超时，到时会结束进程；渲染阶段不具备强制超时，总入库耗时也不等于单页期限。临时图片与输出在处理后清理。

缺少依赖、程序或语言包、识别超时等返回明确 OCR 错误，API 为 503 / ocr_unavailable；超过待识别页数限制为 400。上传失败不发布新文档。全部没有识别出文字时仍视为无可用内容。

仅对完全无文字页回退，不处理已有少量文字但主体是扫描图的页面；未实现表格结构、手写、版面还原或识别置信度。OCR 可能识错字，引用检查只能证明回答引用与提取文本一致，不能证明提取文本与扫描原图完全一致。

当前测试覆盖混合页、页码、缓存配置、进程调用、超时和清理，使用模拟 OCR / 渲染器。本机尚未配置真实引擎和可选依赖，真实中英文扫描件识别效果待验证。

官方参考：[PDFium Python API](https://pypdfium2.readthedocs.io/en/stable/python_api.html)、[Tesseract 用法](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage)。
