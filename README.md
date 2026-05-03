# 科研数据分析平台 MVP

这是一个基于 Python + Streamlit 的本地科研数据分析平台。第一版支持 fsQCA 分析，不使用数据库，所有项目、数据集和分析记录都保存在 `workspace/` 文件夹中。

## 目录结构

```text
research_analysis_app/
  app.py
  pages/
  utils/
  scripts/run_fsqca.R
  workspace/projects/
  sample_data/sample_fsqca_data.csv
  requirements.txt
```

## 安装 Python 依赖

```bash
cd research_analysis_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 安装 R 依赖

需要先安装 R，并确保命令行可以运行 `Rscript`。

```r
install.packages(c("QCA", "jsonlite", "readr", "dplyr", "writexl", "ggplot2"))
```

## 启动 Streamlit

```bash
cd research_analysis_app
streamlit run app.py
```

默认项目会自动创建：

```text
双师型护理教师数字素养研究
```

## 使用流程

1. 进入「数据集管理」页面，上传 Excel 或 CSV。
2. 系统保存原始文件到 `original/`，并转换为 `prepared/data.csv`。
3. 系统自动生成：
   - `dataset.json`
   - `metadata/columns.json`
   - `metadata/preview.json`
   - `metadata/missing_summary.json`
   - `metadata/descriptive_summary.json`
4. 进入「新建fsQCA分析」页面，选择 outcome、conditions 和校准锚点。
5. 点击运行后，系统创建独立 run 文件夹并调用：

```bash
Rscript scripts/run_fsqca.R <run_dir>
```

6. 进入「分析结果」页面查看表格、图片、报告、日志和配置。

说明：fsQCA 表格、Excel、解文本和 Markdown 报告由 `scripts/run_fsqca.R` 生成；`configuration_path.png` 和 `configuration_path.svg` 会由 Python runner 兜底生成，以避免不同系统上的 R 图形设备差异。

## fsQCA 输出

每次运行会生成：

```text
analyses/run_xxx/
  run.json
  config.json
  status.json
  input/selected_data.csv
  output/
    tables/
      calibration_thresholds.csv
      calibrated_data.csv
      necessity_high.csv
      necessity_low.csv
      truth_table_high.csv
      truth_table_low.csv
    figures/
      configuration_path.png
      configuration_path.svg
    files/
      qca_results.xlsx
      qca_solutions.txt
    report/
      report.md
    logs/
      stdout.log
      stderr.log
```

## 样例数据

可以先上传：

```text
sample_data/sample_fsqca_data.csv
```

用于测试 fsQCA 分析流程。
