"""
PDF渲染器 - 使用WeasyPrint从HTML生成PDF
支持完整的CSS样式和中文字体
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
from loguru import logger

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint未安装，PDF导出功能将不可用")

from .html_renderer import HTMLRenderer
from .pdf_layout_optimizer import PDFLayoutOptimizer, PDFLayoutConfig


class PDFRenderer:
    """
    基于WeasyPrint的PDF渲染器

    - 直接从HTML生成PDF，保留所有CSS样式
    - 完美支持中文字体
    - 自动处理分页和布局
    """

    def __init__(
        self,
        config: Dict[str, Any] | None = None,
        layout_optimizer: PDFLayoutOptimizer | None = None
    ):
        """
        初始化PDF渲染器

        参数:
            config: 渲染器配置
            layout_optimizer: PDF布局优化器（可选）
        """
        self.config = config or {}
        self.html_renderer = HTMLRenderer(config)
        self.layout_optimizer = layout_optimizer or PDFLayoutOptimizer()

        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError("WeasyPrint未安装，请运行: pip install weasyprint")

    @staticmethod
    def _get_font_path() -> Path:
        """获取字体文件路径"""
        # 优先使用完整字体以确保字符覆盖
        fonts_dir = Path(__file__).parent / "assets" / "fonts"

        # 检查完整字体
        full_font = fonts_dir / "SourceHanSerifSC-Medium.otf"
        if full_font.exists():
            logger.info(f"使用完整字体: {full_font}")
            return full_font

        # 检查TTF子集字体
        subset_ttf = fonts_dir / "SourceHanSerifSC-Medium-Subset.ttf"
        if subset_ttf.exists():
            logger.info(f"使用TTF子集字体: {subset_ttf}")
            return subset_ttf

        # 检查OTF子集字体
        subset_otf = fonts_dir / "SourceHanSerifSC-Medium-Subset.otf"
        if subset_otf.exists():
            logger.info(f"使用OTF子集字体: {subset_otf}")
            return subset_otf

        raise FileNotFoundError(f"未找到字体文件，请检查 {fonts_dir} 目录")

    def _get_pdf_html(
        self,
        document_ir: Dict[str, Any],
        optimize_layout: bool = True
    ) -> str:
        """
        生成适用于PDF的HTML内容

        - 移除交互式元素（按钮、导航等）
        - 添加PDF专用样式
        - 嵌入字体文件
        - 应用布局优化

        参数:
            document_ir: Document IR数据
            optimize_layout: 是否启用布局优化

        返回:
            str: 优化后的HTML内容
        """
        # 如果启用布局优化，先分析文档并生成优化配置
        if optimize_layout:
            logger.info("启用PDF布局优化...")
            layout_config = self.layout_optimizer.optimize_for_document(document_ir)

            # 保存优化日志
            log_dir = Path('logs/pdf_layouts')
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            # 保存配置和优化日志
            optimization_log = self.layout_optimizer._log_optimization(
                self.layout_optimizer._analyze_document(document_ir),
                layout_config
            )
            self.layout_optimizer.config = layout_config
            self.layout_optimizer.save_config(log_file, optimization_log)
        else:
            layout_config = self.layout_optimizer.config

        # 使用HTML渲染器生成基础HTML
        html = self.html_renderer.render(document_ir)

        # 获取字体路径并转换为base64（用于嵌入）
        font_path = self._get_font_path()
        font_data = font_path.read_bytes()
        font_base64 = base64.b64encode(font_data).decode('ascii')

        # 判断字体格式
        font_format = 'opentype' if font_path.suffix == '.otf' else 'truetype'

        # 生成优化后的CSS
        optimized_css = self.layout_optimizer.generate_pdf_css()

        # 添加PDF专用CSS
        pdf_css = f"""
<style>
/* PDF专用字体嵌入 */
@font-face {{
    font-family: 'SourceHanSerif';
    src: url(data:font/{font_format};base64,{font_base64}) format('{font_format}');
    font-weight: normal;
    font-style: normal;
}}

/* 强制所有文本使用思源宋体 */
body, h1, h2, h3, h4, h5, h6, p, li, td, th, div, span {{
    font-family: 'SourceHanSerif', serif !important;
}}

/* PDF专用样式调整 */
.report-header {{
    display: none !important;
}}

.no-print {{
    display: none !important;
}}

body {{
    background: white !important;
}}

/* 隐藏图表canvas，显示fallback表格 */
.chart-container {{
    display: none !important;
}}

.chart-fallback {{
    display: block !important;
}}

{optimized_css}
</style>
"""

        # 在</head>前插入PDF专用CSS
        html = html.replace('</head>', f'{pdf_css}\n</head>')

        return html

    def render_to_pdf(
        self,
        document_ir: Dict[str, Any],
        output_path: str | Path,
        optimize_layout: bool = True
    ) -> Path:
        """
        将Document IR渲染为PDF文件

        参数:
            document_ir: Document IR数据
            output_path: PDF输出路径
            optimize_layout: 是否启用布局优化（默认True）

        返回:
            Path: 生成的PDF文件路径
        """
        output_path = Path(output_path)

        logger.info(f"开始生成PDF: {output_path}")

        # 生成HTML内容
        html_content = self._get_pdf_html(document_ir, optimize_layout)

        # 配置字体
        font_config = FontConfiguration()

        # 从HTML字符串创建WeasyPrint HTML对象
        html_doc = HTML(string=html_content, base_url=str(Path.cwd()))

        # 生成PDF
        try:
            html_doc.write_pdf(
                output_path,
                font_config=font_config,
                presentational_hints=True  # 保留HTML的呈现提示
            )
            logger.info(f"✓ PDF生成成功: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF生成失败: {e}")
            raise

    def render_to_bytes(
        self,
        document_ir: Dict[str, Any],
        optimize_layout: bool = True
    ) -> bytes:
        """
        将Document IR渲染为PDF字节流

        参数:
            document_ir: Document IR数据
            optimize_layout: 是否启用布局优化（默认True）

        返回:
            bytes: PDF文件的字节内容
        """
        html_content = self._get_pdf_html(document_ir, optimize_layout)
        font_config = FontConfiguration()
        html_doc = HTML(string=html_content, base_url=str(Path.cwd()))

        return html_doc.write_pdf(
            font_config=font_config,
            presentational_hints=True
        )


__all__ = ["PDFRenderer"]
