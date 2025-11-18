"""
图表到SVG转换器 - 将Chart.js数据转换为矢量SVG图形

支持的图表类型:
- line: 折线图
- bar: 柱状图
- pie: 饼图
- doughnut: 圆环图
- radar: 雷达图
- polarArea: 极地区域图
- scatter: 散点图
"""

from __future__ import annotations

import base64
import io
import re
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非GUI后端
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.patches import Wedge
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib未安装，PDF图表矢量渲染功能将不可用")


class ChartToSVGConverter:
    """
    将Chart.js图表数据转换为SVG矢量图形
    """

    # 默认颜色调色板（与Chart.js默认颜色接近）
    DEFAULT_COLORS = [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
    ]

    def __init__(self, font_path: Optional[str] = None):
        """
        初始化转换器

        参数:
            font_path: 中文字体路径（可选）
        """
        if not MATPLOTLIB_AVAILABLE:
            raise RuntimeError("Matplotlib未安装，请运行: pip install matplotlib")

        self.font_path = font_path
        self._setup_chinese_font()

    def _setup_chinese_font(self):
        """配置中文字体"""
        if self.font_path:
            try:
                # 添加自定义字体
                fm.fontManager.addfont(self.font_path)
                # 设置默认字体
                font_prop = fm.FontProperties(fname=self.font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
                logger.info(f"已加载中文字体: {self.font_path}")
            except Exception as e:
                logger.warning(f"加载中文字体失败: {e}，将使用系统默认字体")
        else:
            # 尝试使用系统中文字体
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
            except Exception as e:
                logger.warning(f"配置中文字体失败: {e}")

    def convert_widget_to_svg(
        self,
        widget_data: Dict[str, Any],
        width: int = 800,
        height: int = 500,
        dpi: int = 100
    ) -> Optional[str]:
        """
        将widget数据转换为SVG字符串

        参数:
            widget_data: widget块数据（包含widgetType、data、props）
            width: 图表宽度（像素）
            height: 图表高度（像素）
            dpi: DPI设置

        返回:
            str: SVG字符串，失败返回None
        """
        try:
            # 提取图表类型
            widget_type = widget_data.get('widgetType', '')
            if not widget_type or not widget_type.startswith('chart.js'):
                logger.warning(f"不支持的widget类型: {widget_type}")
                return None

            # 从widgetType中提取图表类型，例如 "chart.js/line" -> "line"
            chart_type = widget_type.split('/')[-1] if '/' in widget_type else 'bar'

            # 也检查props中的type
            props = widget_data.get('props', {})
            if props.get('type'):
                chart_type = props['type']

            # 提取数据
            data = widget_data.get('data', {})
            if not data:
                logger.warning("图表数据为空")
                return None

            # 根据图表类型调用相应的渲染方法
            render_method = getattr(self, f'_render_{chart_type}', None)
            if not render_method:
                logger.warning(f"不支持的图表类型: {chart_type}")
                return None

            # 创建图表并转换为SVG
            return render_method(data, props, width, height, dpi)

        except Exception as e:
            logger.error(f"转换图表为SVG失败: {e}", exc_info=True)
            return None

    def _create_figure(
        self,
        width: int,
        height: int,
        dpi: int,
        title: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """
        创建matplotlib图表

        返回:
            tuple: (fig, ax)
        """
        fig, ax = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)

        if title:
            ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        return fig, ax

    def _parse_color(self, color: Any) -> str:
        """
        解析颜色值，将CSS格式转换为matplotlib支持的格式

        参数:
            color: 颜色值（可能是CSS格式如rgba()或十六进制）

        返回:
            str: matplotlib支持的颜色格式
        """
        if not isinstance(color, str):
            return str(color)

        color = color.strip()

        # 处理rgba(r, g, b, a)格式
        rgba_pattern = r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)'
        match = re.match(rgba_pattern, color)
        if match:
            r, g, b, a = match.groups()
            # 转换为matplotlib格式 (r/255, g/255, b/255, a)
            return (int(r)/255, int(g)/255, int(b)/255, float(a))

        # 处理rgb(r, g, b)格式
        rgb_pattern = r'rgb\((\d+),\s*(\d+),\s*(\d+)\)'
        match = re.match(rgb_pattern, color)
        if match:
            r, g, b = match.groups()
            # 转换为matplotlib格式 (r/255, g/255, b/255)
            return (int(r)/255, int(g)/255, int(b)/255)

        # 其他格式（十六进制、颜色名等）直接返回
        return color

    def _get_colors(self, datasets: List[Dict[str, Any]]) -> List[str]:
        """
        获取图表颜色

        优先使用dataset中定义的颜色，否则使用默认调色板
        """
        colors = []
        for i, dataset in enumerate(datasets):
            # 尝试获取各种可能的颜色字段
            color = (
                dataset.get('backgroundColor') or
                dataset.get('borderColor') or
                dataset.get('color') or
                self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
            )

            # 如果是颜色数组，取第一个
            if isinstance(color, list):
                color = color[0] if color else self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]

            # 解析颜色格式
            color = self._parse_color(color)

            colors.append(color)

        return colors

    def _figure_to_svg(self, fig: Any) -> str:
        """
        将matplotlib图表转换为SVG字符串
        """
        svg_buffer = io.BytesIO()
        fig.savefig(svg_buffer, format='svg', bbox_inches='tight', transparent=False, facecolor='white')
        plt.close(fig)

        svg_buffer.seek(0)
        svg_string = svg_buffer.getvalue().decode('utf-8')

        return svg_string

    def _render_line(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染折线图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                # 绘制折线
                ax.plot(
                    range(len(labels)),
                    dataset_data,
                    marker='o',
                    label=label,
                    color=color,
                    linewidth=2,
                    markersize=6
                )

            # 设置x轴标签
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # 网格
            ax.grid(True, alpha=0.3, linestyle='--')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染折线图失败: {e}")
            return None

    def _render_bar(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染柱状图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # 计算柱子位置
            x = np.arange(len(labels))
            width_bar = 0.8 / len(datasets) if len(datasets) > 1 else 0.6

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                offset = (i - len(datasets)/2 + 0.5) * width_bar
                ax.bar(
                    x + offset,
                    dataset_data,
                    width_bar,
                    label=label,
                    color=color,
                    alpha=0.8,
                    edgecolor='white',
                    linewidth=0.5
                )

            # 设置x轴标签
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # 网格
            ax.grid(True, alpha=0.3, linestyle='--', axis='y')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染柱状图失败: {e}")
            return None

    def _render_pie(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染饼图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # 饼图只使用第一个数据集
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            # 获取颜色
            colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(colors, list):
                colors = self.DEFAULT_COLORS[:len(labels)]

            # 绘制饼图
            wedges, texts, autotexts = ax.pie(
                dataset_data,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 10}
            )

            # 设置百分比文字为白色
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.axis('equal')  # 保持圆形

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染饼图失败: {e}")
            return None

    def _render_doughnut(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染圆环图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # 圆环图只使用第一个数据集
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            # 获取颜色
            colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(colors, list):
                colors = self.DEFAULT_COLORS[:len(labels)]

            # 绘制圆环图（通过设置wedgeprops实现中空效果）
            wedges, texts, autotexts = ax.pie(
                dataset_data,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                wedgeprops=dict(width=0.5, edgecolor='white'),
                textprops={'fontsize': 10}
            )

            # 设置百分比文字
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.axis('equal')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染圆环图失败: {e}")
            return None

    def _render_radar(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染雷达图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)

            # 创建极坐标子图
            ax = fig.add_subplot(111, projection='polar')

            if title:
                ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            colors = self._get_colors(datasets)

            # 计算角度
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
            angles += angles[:1]  # 闭合图形

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                # 闭合数据
                values = dataset_data + dataset_data[:1]

                # 绘制雷达图
                ax.plot(angles, values, 'o-', linewidth=2, label=label, color=color)
                ax.fill(angles, values, alpha=0.25, color=color)

            # 设置标签
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels)

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染雷达图失败: {e}")
            return None

    def _render_scatter(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染散点图"""
        try:
            datasets = data.get('datasets', [])

            if not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # 绘制每个数据系列
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'系列{i+1}')
                color = colors[i]

                # 提取x和y坐标
                if dataset_data and isinstance(dataset_data[0], dict):
                    x_values = [point.get('x', 0) for point in dataset_data]
                    y_values = [point.get('y', 0) for point in dataset_data]
                else:
                    # 如果不是{x,y}格式，使用索引作为x
                    x_values = range(len(dataset_data))
                    y_values = dataset_data

                ax.scatter(
                    x_values,
                    y_values,
                    label=label,
                    color=color,
                    s=50,
                    alpha=0.6,
                    edgecolors='white',
                    linewidth=0.5
                )

            # 显示图例
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # 网格
            ax.grid(True, alpha=0.3, linestyle='--')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染散点图失败: {e}")
            return None

    def _render_polarArea(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """渲染极地区域图"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # 只使用第一个数据集
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            title = props.get('title')
            fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
            ax = fig.add_subplot(111, projection='polar')

            if title:
                ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            # 获取颜色
            colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(colors, list):
                colors = self.DEFAULT_COLORS[:len(labels)]

            # 计算角度
            theta = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
            width_bar = 2 * np.pi / len(labels)

            # 绘制极地区域图
            bars = ax.bar(
                theta,
                dataset_data,
                width=width_bar,
                bottom=0.0,
                color=colors,
                alpha=0.7,
                edgecolor='white',
                linewidth=1
            )

            # 设置标签
            ax.set_xticks(theta)
            ax.set_xticklabels(labels)

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"渲染极地区域图失败: {e}")
            return None


def create_chart_converter(font_path: Optional[str] = None) -> ChartToSVGConverter:
    """
    创建图表转换器实例

    参数:
        font_path: 中文字体路径（可选）

    返回:
        ChartToSVGConverter: 转换器实例
    """
    return ChartToSVGConverter(font_path=font_path)


__all__ = ["ChartToSVGConverter", "create_chart_converter"]
