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
from .chart_to_svg import create_chart_converter


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

        # 初始化图表转换器
        try:
            font_path = self._get_font_path()
            self.chart_converter = create_chart_converter(font_path=str(font_path))
            logger.info("图表SVG转换器初始化成功")
        except Exception as e:
            logger.warning(f"图表SVG转换器初始化失败: {e}，将使用表格降级")

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

    def _convert_charts_to_svg(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        将document_ir中的所有图表转换为SVG

        参数:
            document_ir: Document IR数据

        返回:
            Dict[str, str]: widgetId到SVG字符串的映射
        """
        svg_map = {}

        if not hasattr(self, 'chart_converter') or not self.chart_converter:
            logger.warning("图表转换器未初始化，跳过图表转换")
            return svg_map

        # 遍历所有章节
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_and_convert_widgets(blocks, svg_map)

        logger.info(f"成功转换 {len(svg_map)} 个图表为SVG")
        return svg_map

    def _extract_and_convert_widgets(
        self,
        blocks: list,
        svg_map: Dict[str, str]
    ) -> None:
        """
        递归遍历blocks，找到所有widget并转换为SVG

        参数:
            blocks: block列表
            svg_map: 用于存储转换结果的字典
        """
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')

            # 处理widget类型
            if block_type == 'widget':
                widget_id = block.get('widgetId')
                widget_type = block.get('widgetType', '')

                # 只处理chart.js类型的widget
                if widget_id and widget_type.startswith('chart.js'):
                    try:
                        svg_content = self.chart_converter.convert_widget_to_svg(
                            block,
                            width=800,
                            height=500,
                            dpi=100
                        )
                        if svg_content:
                            svg_map[widget_id] = svg_content
                            logger.debug(f"图表 {widget_id} 转换为SVG成功")
                        else:
                            logger.warning(f"图表 {widget_id} 转换为SVG失败")
                    except Exception as e:
                        logger.error(f"转换图表 {widget_id} 时出错: {e}")

            # 递归处理嵌套的blocks
            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_and_convert_widgets(nested_blocks, svg_map)

            # 处理列表项
            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_and_convert_widgets(item, svg_map)

            # 处理表格单元格
            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_and_convert_widgets(cell_blocks, svg_map)

    def _inject_svg_into_html(self, html: str, svg_map: Dict[str, str]) -> str:
        """
        将SVG内容直接注入到HTML中（不使用JavaScript）

        参数:
            html: 原始HTML内容
            svg_map: widgetId到SVG内容的映射

        返回:
            str: 注入SVG后的HTML
        """
        if not svg_map:
            return html

        import re

        # 为每个widgetId查找对应的canvas并替换为SVG
        for widget_id, svg_content in svg_map.items():
            # 清理SVG内容（移除XML声明，因为SVG将嵌入HTML）
            svg_content = re.sub(r'<\?xml[^>]+\?>', '', svg_content)
            svg_content = re.sub(r'<!DOCTYPE[^>]+>', '', svg_content)
            svg_content = svg_content.strip()

            # 创建SVG容器HTML
            svg_html = f'<div class="chart-svg-container">{svg_content}</div>'

            # 查找包含此widgetId的配置脚本
            # 格式: <script type="application/json" id="chart-config-N">{"widgetId":"widget_id",...}</script>
            config_pattern = rf'<script[^>]+id="([^"]+)"[^>]*>\s*\{{[^}}]*"widgetId"\s*:\s*"{re.escape(widget_id)}"[^}}]*\}}'
            match = re.search(config_pattern, html, re.DOTALL)

            if match:
                config_id = match.group(1)

                # 查找对应的canvas元素
                # 格式: <canvas id="chart-N" data-config-id="chart-config-N"></canvas>
                canvas_pattern = rf'<canvas[^>]+data-config-id="{re.escape(config_id)}"[^>]*></canvas>'

                # 替换canvas为SVG
                html = re.sub(canvas_pattern, svg_html, html)
                logger.debug(f"已替换图表 {widget_id} 的canvas为SVG")
            else:
                logger.warning(f"未找到图表 {widget_id} 对应的配置脚本")

        return html

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
        - 将图表转换为SVG矢量图形

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

        # 转换图表为SVG
        logger.info("开始转换图表为SVG矢量图形...")
        svg_map = self._convert_charts_to_svg(document_ir)

        # 使用HTML渲染器生成基础HTML
        html = self.html_renderer.render(document_ir)

        # 注入SVG
        if svg_map:
            html = self._inject_svg_into_html(html, svg_map)
            logger.info(f"已注入 {len(svg_map)} 个SVG图表")

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

/* SVG图表容器样式 */
.chart-svg-container {{
    width: 100%;
    height: auto;
    display: flex;
    justify-content: center;
    align-items: center;
}}

.chart-svg-container svg {{
    max-width: 100%;
    height: auto;
}}

/* 隐藏fallback表格（因为现在使用SVG） */
.chart-fallback {{
    display: none !important;
}}

/* 确保chart-container显示（用于放置SVG） */
.chart-container {{
    display: block !important;
    min-height: 400px;
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
