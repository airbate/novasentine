# PDF导出优化系统使用指南

## 概述

全新的PDF导出系统现已集成到ReportEngine中，提供了智能布局优化功能，确保PDF文档美观且无溢出问题。

## 核心特性

### 1. 智能布局优化

系统会自动分析文档内容并优化布局参数：

- **KPI卡片优化**
  - 自动调整每行列数（1-3列）
  - 根据数值长度动态调整字号
  - 防止数值溢出

- **表格优化**
  - 根据列数自动缩小字号
  - 智能调整单元格内边距
  - 支持长内容自动换行

- **文本优化**
  - 检测长文本自动增加行高
  - 防止标题孤行
  - 优化段落间距

### 2. 配置持久化

所有优化决策都会保存到日志文件中：
- 位置：`logs/pdf_layouts/layout_YYYYMMDD_HHMMSS.json`
- 内容：文档统计信息、优化策略、最终配置

### 3. 前端集成

用户只需点击"下载PDF"按钮，系统将：
1. 自动分析报告内容
2. 应用最佳布局优化
3. 生成高质量PDF
4. 自动下载到本地

## 使用方法

### 方式一：通过Web界面（推荐）

1. 启动系统：`python app.py`
2. 生成报告：在Report Engine中生成最终报告
3. 点击"下载PDF"按钮
4. 系统自动优化并下载PDF

### 方式二：通过API

#### 根据任务ID导出

```bash
curl -X GET \
  "http://localhost:5000/api/report/export/pdf/YOUR_TASK_ID?optimize=true" \
  -o report.pdf
```

#### 从IR JSON直接导出

```bash
curl -X POST \
  "http://localhost:5000/api/report/export/pdf-from-ir" \
  -H "Content-Type: application/json" \
  -d '{
    "document_ir": {...},
    "optimize": true
  }' \
  -o report.pdf
```

### 方式三：通过Python脚本

```python
from pathlib import Path
import json
from ReportEngine.renderers import PDFRenderer

# 读取IR数据
with open('report_ir.json', 'r', encoding='utf-8') as f:
    document_ir = json.load(f)

# 创建渲染器并导出PDF
renderer = PDFRenderer()
renderer.render_to_pdf(
    document_ir,
    'output.pdf',
    optimize_layout=True  # 启用布局优化
)
```

## 配置选项

### 全局配置

```python
from ReportEngine.renderers import PDFLayoutOptimizer, PDFLayoutConfig

# 自定义配置
config = PDFLayoutConfig(
    page=PageLayout(
        font_size_base=14,
        line_height=1.6
    ),
    kpi_card=KPICardLayout(
        font_size_value=32,
        min_height=120
    ),
    # ... 更多配置
)

# 使用自定义配置
optimizer = PDFLayoutOptimizer(config)
renderer = PDFRenderer(layout_optimizer=optimizer)
```

### 优化策略

| 场景 | 触发条件 | 优化措施 |
|------|---------|---------|
| KPI数量多 | > 6个 | 调整为3列布局 |
| KPI数量少 | ≤ 2个 | 调整为1列布局 |
| KPI数值长 | > 10字符 | 字号从32px调整为28px |
| KPI数值很长 | > 15字符 | 字号从32px调整为24px |
| 表格列多 | > 6列 | 字号从13/12px调整为11/10px |
| 文本很长 | > 200字符 | 行高从1.6增加到1.8 |

## 测试

运行测试脚本验证所有功能：

```bash
# 设置环境变量
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# 运行测试
python test_pdf_optimized.py
```

测试将生成：
- `test_pdf_optimized.pdf` - 启用优化的PDF
- `test_pdf_default.pdf` - 默认设置的PDF（对比）
- `test_layout_config.json` - 布局配置
- `logs/pdf_layouts/` - 优化日志

## 优化日志格式

```json
{
  "timestamp": "2024-11-18T19:41:10.983000",
  "document_stats": {
    "kpi_count": 10,
    "table_count": 2,
    "chart_count": 2,
    "max_kpi_value_length": 14,
    "max_table_columns": 8
  },
  "optimizations": [
    "KPI数值过长(14字符)，字号从32调整为28",
    "KPI卡片较多(10个)，每行列数从2调整为3",
    "表格列数较多(8列)，缩小字号和内边距"
  ],
  "final_config": {
    "page": {...},
    "kpi_card": {...},
    "table": {...}
  }
}
```

## 故障排除

### 问题1：WeasyPrint库加载失败

**症状**：
```
OSError: cannot load library 'libpango-1.0-0'
```

**解决方案**：
```bash
# macOS
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# 或在脚本中设置
import os
os.environ['DYLD_LIBRARY_PATH'] = '/opt/homebrew/lib'
```

### 问题2：字体文件缺失

**症状**：
```
FileNotFoundError: 未找到字体文件
```

**解决方案**：
确保以下字体文件存在：
- `ReportEngine/renderers/assets/fonts/SourceHanSerifSC-Medium.otf`

### 问题3：PDF布局仍有问题

**解决方案**：
1. 检查优化日志：`logs/pdf_layouts/`
2. 查看应用了哪些优化策略
3. 如需自定义，修改配置参数
4. 禁用优化对比：`optimize_layout=False`

## 性能优化建议

1. **首次导出**：需要加载字体文件，可能需要几秒钟
2. **字体子集化**：对于大型报告，考虑使用字体子集以减小文件大小
3. **图表处理**：图表会自动转换为表格，提高PDF渲染速度
4. **批量导出**：复用同一个PDFRenderer实例可以提高效率

## 架构说明

```
┌─────────────────────────────────────────┐
│           Web UI / API                  │
│  (用户点击"下载PDF"按钮)                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Flask API Endpoint                 │
│  /api/report/export/pdf/:task_id        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      PDFLayoutOptimizer                 │
│  • 分析文档结构                          │
│  • 智能调整布局参数                      │
│  • 保存优化日志                          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      HTMLRenderer                       │
│  • 将IR转换为HTML                        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      PDFRenderer                        │
│  • 注入优化的CSS                         │
│  • 嵌入字体                             │
│  • 使用WeasyPrint生成PDF                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      优化的PDF文件                       │
│  • 无溢出                               │
│  • 布局美观                             │
│  • 自动分页                             │
└─────────────────────────────────────────┘
```

## 更新日志

### v1.0.0 (2024-11-18)

**新增功能**：
- ✅ PDF布局智能优化器
- ✅ 自动调整字号、行间距、网格列数
- ✅ 配置持久化系统
- ✅ Flask API集成
- ✅ 前端一键导出

**优化措施**：
- ✅ KPI卡片防溢出
- ✅ 表格自适应布局
- ✅ 长文本行高优化
- ✅ 标题防孤行
- ✅ 图表转表格渲染

**测试覆盖**：
- ✅ 多种KPI场景测试
- ✅ 复杂表格测试
- ✅ 图表渲染测试
- ✅ 长文本测试

## 未来计划

- [ ] 支持更多纸张尺寸（A3、Letter等）
- [ ] 添加PDF水印功能
- [ ] 支持页眉页脚自定义
- [ ] 提供更多布局模板
- [ ] 优化大型文档渲染性能

## 技术栈

- **PDF生成**：WeasyPrint
- **布局优化**：自研PDFLayoutOptimizer
- **字体**：思源宋体（SourceHanSerifSC）
- **后端框架**：Flask
- **前端**：原生JavaScript

## 贡献者

欢迎提交Issue和PR来改进PDF导出系统！

## 许可证

本项目遵循项目主仓库的许可证。
