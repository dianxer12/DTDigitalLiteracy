args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript scripts/run_fsqca.R <run_dir>")
run_dir <- normalizePath(args[[1]], mustWork = TRUE)

packages <- c("QCA", "jsonlite", "readr", "dplyr", "writexl", "ggplot2")
installed <- rownames(installed.packages())
missing <- setdiff(packages, installed)
if (length(missing) > 0) {
  stop(paste("Missing R packages:", paste(missing, collapse = ", "), "\nInstall them first."))
}

library(QCA)
library(jsonlite)
library(readr)
library(dplyr)
library(writexl)
library(ggplot2)

input_dir <- file.path(run_dir, "input")
tables_dir <- file.path(run_dir, "output", "tables")
figures_dir <- file.path(run_dir, "output", "figures")
files_dir <- file.path(run_dir, "output", "files")
report_dir <- file.path(run_dir, "output", "report")
logs_dir <- file.path(run_dir, "output", "logs")
dir.create(tables_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(files_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(report_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(logs_dir, recursive = TRUE, showWarnings = FALSE)

config <- fromJSON(file.path(run_dir, "config.json"), simplifyVector = FALSE)
dat <- read_csv(file.path(input_dir, "selected_data.csv"), show_col_types = FALSE)

outcome <- config$outcome
conditions <- unlist(config$conditions)
all_vars <- c(outcome, conditions)
dat <- dat %>% mutate(across(all_of(all_vars), as.numeric))

# Helper: translate variable name to Chinese label
var_labels <- config$variable_labels
if (is.null(var_labels)) var_labels <- list()
label_of <- function(var_name) {
  lbl <- var_labels[[var_name]]
  if (is.null(lbl) || lbl == "") var_name else lbl
}

get_thresholds <- function(var) {
  th <- unlist(config$calibration[[var]]$thresholds)
  if (length(th) != 3 || any(is.na(th))) {
    th <- as.numeric(quantile(dat[[var]], probs = c(0.25, 0.50, 0.75), na.rm = TRUE))
  }
  if (length(unique(round(th, 8))) < 3) {
    rng <- range(dat[[var]], na.rm = TRUE)
    step <- ifelse(diff(rng) == 0, 1, diff(rng) / 4)
    th <- c(rng[1] + step, rng[1] + 2 * step, rng[1] + 3 * step)
  }
  as.numeric(th)
}

threshold_rows <- lapply(all_vars, function(v) {
  th <- get_thresholds(v)
  data.frame(variable = v, t_exclusion = th[1], t_crossover = th[2], t_inclusion = th[3])
})
thresholds_df <- bind_rows(threshold_rows)
write_csv(thresholds_df, file.path(tables_dir, "calibration_thresholds.csv"))

qdat <- dat
for (v in all_vars) {
  th <- get_thresholds(v)
  qdat[[paste0("f_", v)]] <- calibrate(qdat[[v]], type = "fuzzy", thresholds = th)
}

qcols <- paste0("f_", all_vars)
qdat <- qdat[complete.cases(qdat[, qcols]), ]
for (v in qcols) {
  qdat[[v]][qdat[[v]] == 0.5] <- 0.501
}
qdat <- as.data.frame(qdat)
write_csv(qdat, file.path(tables_dir, "calibrated_data.csv"))

out_f <- paste0("f_", outcome)
cond_f <- paste0("f_", conditions)
incl_cut <- as.numeric(config$incl_cut)
pri_cut <- as.numeric(config$pri_cut)
n_cut <- as.numeric(config$n_cut)
run_low <- isTRUE(config$run_low)

capture_to_file <- function(expr, path) {
  txt <- capture.output(expr)
  writeLines(txt, path, useBytes = TRUE)
  txt
}

necessity_high_txt <- capture.output(
  nec_high <- tryCatch(
    superSubset(qdat, outcome = out_f, conditions = cond_f, relation = "nec", incl.cut = 0.90),
    error = function(e) e
  )
)
write_csv(data.frame(output = necessity_high_txt), file.path(tables_dir, "necessity_high.csv"))

if (run_low) {
  necessity_low_txt <- capture.output(
    nec_low <- tryCatch(
      superSubset(qdat, outcome = out_f, neg.out = TRUE, conditions = cond_f, relation = "nec", incl.cut = 0.90),
      error = function(e) e
    )
  )
  write_csv(data.frame(output = necessity_low_txt), file.path(tables_dir, "necessity_low.csv"))
} else {
  necessity_low_txt <- "未运行低结果分析。"
  write_csv(data.frame(output = necessity_low_txt), file.path(tables_dir, "necessity_low.csv"))
}

tt_high <- tryCatch(
  truthTable(
    qdat,
    outcome = out_f,
    conditions = cond_f,
    n.cut = n_cut,
    incl.cut = incl_cut,
    pri.cut = pri_cut,
    complete = TRUE,
    show.cases = TRUE
  ),
  error = function(e) e
)
tt_high_df <- if (inherits(tt_high, "error")) data.frame(error = tt_high$message) else as.data.frame(tt_high$tt)
write_csv(tt_high_df, file.path(tables_dir, "truth_table_high.csv"))

sol_high <- if (inherits(tt_high, "error")) tt_high else tryCatch(
  minimize(tt_high, details = TRUE, show.cases = TRUE, include = "?"),
  error = function(e) e
)

if (run_low) {
  tt_low <- tryCatch(
    truthTable(
      qdat,
      outcome = out_f,
      neg.out = TRUE,
      conditions = cond_f,
      n.cut = n_cut,
      incl.cut = incl_cut,
      pri.cut = pri_cut,
      complete = TRUE,
      show.cases = TRUE
    ),
    error = function(e) e
  )
  tt_low_df <- if (inherits(tt_low, "error")) data.frame(error = tt_low$message) else as.data.frame(tt_low$tt)
  write_csv(tt_low_df, file.path(tables_dir, "truth_table_low.csv"))
  sol_low <- if (inherits(tt_low, "error")) tt_low else tryCatch(
    minimize(tt_low, details = TRUE, show.cases = TRUE, include = "?"),
    error = function(e) e
  )
} else {
  tt_low_df <- data.frame(message = "未运行低结果分析。")
  write_csv(tt_low_df, file.path(tables_dir, "truth_table_low.csv"))
  sol_low <- "未运行低结果分析。"
}

solution_txt <- c(
  "fsQCA 解",
  "",
  "变量名对照：",
  paste0("  ", outcome, " = ", label_of(outcome), "（结果变量）"),
  unlist(lapply(conditions, function(v) paste0("  ", v, " = ", label_of(v)))),
  "",
  "高结果解：",
  capture.output(print(sol_high)),
  "",
  "低结果解：",
  capture.output(print(sol_low))
)
writeLines(solution_txt, file.path(files_dir, "qca_solutions.txt"), useBytes = TRUE)

write_xlsx(
  list(
    calibration_thresholds = thresholds_df,
    calibrated_data = qdat,
    necessity_high = data.frame(output = necessity_high_txt),
    necessity_low = data.frame(output = necessity_low_txt),
    truth_table_high = tt_high_df,
    truth_table_low = tt_low_df
  ),
  file.path(files_dir, "qca_results.xlsx")
)

fig_df <- data.frame(
  x = c(1, 1, 2.8, 2.8, 4.4),
  y = c(3, 2, 3, 2, 2.5),
  label = c(label_of(conditions[1]), ifelse(length(conditions) >= 2, label_of(conditions[2]), ""), "组态A", "组态B", label_of(outcome)),
  type = c("condition", "condition", "config", "config", "outcome")
)
fig_df <- fig_df[fig_df$label != "", ]
p <- ggplot(fig_df, aes(x, y)) +
  geom_label(aes(label = label, fill = type), color = "#1b1b1b", label.size = 0.4, size = 4) +
  annotate("segment", x = 1.35, y = 3, xend = 2.45, yend = 3, arrow = arrow(length = unit(0.15, "inches")), color = "#2E7D32", linewidth = 0.8) +
  annotate("segment", x = 1.35, y = 2, xend = 2.45, yend = 2, arrow = arrow(length = unit(0.15, "inches")), color = "#2E7D32", linewidth = 0.8) +
  annotate("segment", x = 3.15, y = 3, xend = 4.05, yend = 2.55, arrow = arrow(length = unit(0.15, "inches")), color = "#2E7D32", linewidth = 0.8) +
  annotate("segment", x = 3.15, y = 2, xend = 4.05, yend = 2.45, arrow = arrow(length = unit(0.15, "inches")), color = "#2E7D32", linewidth = 0.8) +
  scale_fill_manual(values = c(condition = "#E8F3EA", config = "#F2FAF2", outcome = "#D9EFD9")) +
  xlim(0.4, 5) +
  ylim(1.4, 3.6) +
  theme_void() +
  theme(legend.position = "none", plot.background = element_rect(fill = "white", color = NA))
ggsave(file.path(figures_dir, "configuration_path.png"), p, width = 10, height = 5, dpi = 180)
svg_lines <- c(
  '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="500" viewBox="0 0 1000 500">',
  '<style>text { font-family: "PingFang SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS", "Heiti SC", sans-serif; }</style>',
  '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#2E7D32"/></marker></defs>',
  '<rect width="100%" height="100%" fill="white"/>',
  '<rect x="70" y="160" width="220" height="70" fill="#E8F3EA" stroke="#2E7D32" stroke-width="3"/>',
  paste0('<text x="180" y="202" text-anchor="middle" font-size="18">', label_of(conditions[1]), '</text>'),
  '<rect x="70" y="270" width="220" height="70" fill="#E8F3EA" stroke="#2E7D32" stroke-width="3"/>',
  paste0('<text x="180" y="312" text-anchor="middle" font-size="18">', ifelse(length(conditions) >= 2, label_of(conditions[2]), ""), '</text>'),
  '<rect x="410" y="160" width="220" height="70" fill="#F2FAF2" stroke="#2E7D32" stroke-width="3"/>',
  '<text x="520" y="202" text-anchor="middle" font-size="18">组态A</text>',
  '<rect x="410" y="270" width="220" height="70" fill="#F2FAF2" stroke="#2E7D32" stroke-width="3"/>',
  '<text x="520" y="312" text-anchor="middle" font-size="18">组态B</text>',
  '<rect x="760" y="215" width="180" height="80" fill="#D9EFD9" stroke="#2E7D32" stroke-width="3"/>',
  paste0('<text x="850" y="262" text-anchor="middle" font-size="18">', label_of(outcome), '</text>'),
  '<line x1="290" y1="195" x2="410" y2="195" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>',
  '<line x1="290" y1="305" x2="410" y2="305" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>',
  '<line x1="630" y1="195" x2="760" y2="250" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>',
  '<line x1="630" y1="305" x2="760" y2="260" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>',
  '</svg>'
)
writeLines(svg_lines, file.path(figures_dir, "configuration_path.svg"), useBytes = TRUE)

# Build markdown thresholds table with Chinese labels
thresholds_md <- c(
  "| 变量名 | 中文标签 | 完全不隶属 | 交叉点 | 完全隶属 |",
  "|--------|----------|------------|--------|----------|",
  paste(sapply(all_vars, function(v) {
    th <- get_thresholds(v)
    sprintf("| %s | %s | %.3f | %.3f | %.3f |", v, label_of(v), th[1], th[2], th[3])
  }), collapse = "\n")
)

report <- c(
  "# fsQCA 分析报告",
  "",
  paste0("- 数据集：", config$dataset_name),
  paste0("- 结果变量：", label_of(outcome), "（", outcome, "）"),
  paste0("- 条件变量：", paste(mapply(function(v) paste0(label_of(v), "（", v, "）"), conditions), collapse = ", ")),
  paste0("- 一致性阈值 (incl_cut)：", incl_cut),
  paste0("- PRI阈值 (pri_cut)：", pri_cut),
  paste0("- 案例数阈值 (n_cut)：", n_cut),
  "",
  "## 变量名对照",
  "",
  paste0("| 变量名 | 中文标签 |"),
  paste0("|--------|----------|"),
  paste0("| ", outcome, " | ", label_of(outcome), "（结果变量） |"),
  paste(sapply(conditions, function(v) paste0("| ", v, " | ", label_of(v), " |")), collapse = "\n"),
  "",
  "## 校准锚点",
  "",
  thresholds_md,
  "",
  "## 高结果解",
  "",
  "```",
  capture.output(print(sol_high)),
  "```",
  "",
  "## 低结果解",
  "",
  "```",
  capture.output(print(sol_low)),
  "```"
)
writeLines(report, file.path(report_dir, "report.md"), useBytes = TRUE)
