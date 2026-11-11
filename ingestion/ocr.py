"""Optional local PDF rendering and bounded Tesseract execution."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from core.exceptions import OcrError


class TesseractOcr:
    def __init__(self, language="chi_sim+eng", timeout=60, command="tesseract"):
        self.language,self.timeout,self.command=language,timeout,command

    def read_page(self, path, page_number):
        try:
            import pypdfium2 as pdfium
            with ExitStack() as stack:
                pdf=pdfium.PdfDocument(str(path));stack.callback(pdf.close)
                page=pdf[page_number-1];stack.callback(page.close)
                width,height=page.get_size()
                scale=200/72
                if width<=0 or height<=0 or width*height*scale*scale>20_000_000:
                    raise OcrError("PDF 页面过大，无法进行 OCR")
                bitmap=page.render(scale=scale);stack.callback(bitmap.close)
                image=bitmap.to_pil();stack.callback(image.close)
                with TemporaryDirectory(prefix="agent-ocr-") as folder:
                    source=Path(folder)/"page.png"
                    output=Path(folder)/"recognized"
                    image.save(source)
                    subprocess.run([self.command,str(source),str(output),"-l",self.language],
                        check=True,timeout=self.timeout,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                    with output.with_suffix(".txt").open("rb") as handle:
                        raw=handle.read(1_000_001)
                    if len(raw)>1_000_000: raise OcrError("OCR 输出过长")
                    return raw.decode("utf-8").strip()
        except OcrError: raise
        except ImportError as exc:
            raise OcrError("OCR 依赖未安装，请安装项目的 ocr 可选依赖") from exc
        except FileNotFoundError as exc:
            raise OcrError("OCR 程序或输出不可用，请检查 Tesseract 安装与配置") from exc
        except subprocess.TimeoutExpired as exc:
            raise OcrError("OCR 识别超时") from exc
        except Exception as exc:
            raise OcrError("OCR 失败，请检查 PDF、Tesseract 和语言包") from exc
