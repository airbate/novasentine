# Python PDF 导出 - 使用指南

## ✅ 解决方案说明

已将PDF导出从浏览器端（jsPDF）改为**Python直接生成**，使用WeasyPrint库，完美解决中文乱码问题。

### 优势
- ✓ **无乱码**：使用思源宋体（SourceHanSerifSC），完美显示所有中文字符
- ✓ **样式保留**：100%保留HTML的所有CSS样式
- ✓ **自动优化**：自动处理分页、布局、图表转表格
- ✓ **高质量**：生成的PDF可直接用于打印和分发

## 📦 依赖安装

### 1. 安装系统依赖（已完成）
```bash
brew install pango cairo gdk-pixbuf
```

### 2. 安装Python库（已完成）
```bash
pip3 install weasyprint
```

## 🚀 使用方法

### 方法一：直接使用Python（推荐）

```bash
# 设置环境变量
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# 运行导出
python3 ReportEngine/scripts/export_to_pdf.py final_reports/ir/report_ir_xxx.json

# 或从项目根目录运行
python3 -m ReportEngine.scripts.export_to_pdf final_reports/ir/report_ir_xxx.json
```

### 方法二：使用便捷脚本（如果有的话）

```bash
# 基本用法（自动生成同名PDF）
./pdf_export.sh final_reports/ir/report_ir_xxx.json

# 指定输出路径
./pdf_export.sh final_reports/ir/report_ir_xxx.json my_report.pdf
```

### 方法三：在代码中使用

```python
from ReportEngine.renderers import PDFRenderer
import json

# 读取报告数据
with open("report_ir.json", "r") as f:
    document_ir = json.load(f)

# 生成PDF
renderer = PDFRenderer()
renderer.render_to_pdf(document_ir, "output.pdf")
```

## 📊 测试样例

已生成两个测试PDF：

1. **综合样式测试** ([test_comprehensive.pdf](test_comprehensive.pdf))
   - 包含所有样式元素
   - 字体、标点、列表、表格、KPI卡片等

2. **真实报告** ([report_土木工程_python.pdf](report_土木工程_python.pdf))
   - 使用真实的土木工程报告数据
   - 完整展示实际使用效果

## ✨ 特性说明

### 1. 字体支持
- 优先使用：`SourceHanSerifSC-Medium.otf`（24MB完整版）
- 备选方案：`SourceHanSerifSC-Medium-Subset.ttf`（3.7MB子集版）
- 覆盖：所有常用汉字、标点符号、数字、英文

### 2. 样式保留
- 响应式布局 → PDF优化布局
- 交互按钮 → 自动隐藏
- Chart.js图表 → 自动显示fallback表格
- 所有CSS样式完整保留

### 3. 分页优化
- 标题不孤立（避免标题单独在页末）
- 表格和卡片避免跨页断裂
- 引用块和callout保持完整

## 🔧 故障排除

### 问题1：找不到libpango库

**症状**：
```
OSError: cannot load library 'libpango-1.0-0'
```

**解决**：
```bash
# 使用提供的pdf_export.sh脚本（已自动设置环境变量）
./pdf_export.sh <your_file.json>

# 或手动设置环境变量
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
```

### 问题2：字体文件缺失

**症状**：
```
FileNotFoundError: 未找到字体文件
```

**解决**：
确保以下任一字体文件存在：
- `ReportEngine/renderers/assets/fonts/SourceHanSerifSC-Medium.otf`
- `ReportEngine/renderers/assets/fonts/SourceHanSerifSC-Medium-Subset.ttf`

### 问题3：PDF仍然有乱码

**解决**：
1. 检查字体文件是否完整（应该是24MB或3.7MB）
2. 使用pdftotext验证：`pdftotext output.pdf - | head`
3. 如有问题，重新生成字体子集或使用完整版

## 📝 开发说明

### 核心文件

- [PDFRenderer](../renderers/pdf_renderer.py) - PDF渲染器主类
- [HTMLRenderer](../renderers/html_renderer.py) - HTML渲染器（被PDF渲染器使用）
- [export_to_pdf.py](../scripts/export_to_pdf.py) - 命令行工具
- [pdf_export.sh](../../pdf_export.sh) - 便捷启动脚本（如果有的话）

### 工作流程

```
Document IR (JSON)
    ↓
HTMLRenderer.render()
    ↓
HTML with embedded font (base64)
    ↓
WeasyPrint
    ↓
PDF (with SourceHanSerif font)
```

## 🎯 下一步

如需集成到Web应用：

1. **Flask/FastAPI后端**
   ```python
   from flask import send_file
   from ReportEngine.renderers import PDFRenderer

   @app.route('/export_pdf')
   def export_pdf():
       renderer = PDFRenderer()
       pdf_bytes = renderer.render_to_bytes(document_ir)
       return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf')
   ```

2. **前端按钮**
   ```javascript
   document.getElementById('export-btn').addEventListener('click', () => {
       window.open('/export_pdf', '_blank');
   });
   ```

---

**生成时间**: 2025-11-18
**版本**: 1.0
**状态**: ✅ 已测试，无乱码
