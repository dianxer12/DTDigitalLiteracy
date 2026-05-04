# ============================================================
# fsQCA Analysis — Publication-Standard Output
# ============================================================
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript scripts/run_fsqca.R <run_dir>")
run_dir <- normalizePath(args[[1]], mustWork = TRUE)

packages <- c("QCA", "jsonlite", "readr", "dplyr", "writexl", "ggplot2", "tidyr")
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
library(tidyr)

# ── Paths ──────────────────────────────────────────────────────────────────
input_dir <- file.path(run_dir, "input")
tables_dir <- file.path(run_dir, "output", "tables")
figures_dir <- file.path(run_dir, "output", "figures")
files_dir <- file.path(run_dir, "output", "files")
report_dir <- file.path(run_dir, "output", "report")
logs_dir <- file.path(run_dir, "output", "logs")
for (d in c(tables_dir, figures_dir, files_dir, report_dir, logs_dir)) {
  dir.create(d, recursive = TRUE, showWarnings = FALSE)
}

# ── Load config & data ─────────────────────────────────────────────────────
config <- fromJSON(file.path(run_dir, "config.json"), simplifyVector = FALSE)
dat <- read_csv(file.path(input_dir, "selected_data.csv"), show_col_types = FALSE)

outcome <- config$outcome
conditions <- unlist(config$conditions)
all_vars <- c(outcome, conditions)
dat <- dat %>% mutate(across(all_of(all_vars), as.numeric))

# Helper: Chinese label
var_labels <- config$variable_labels
if (is.null(var_labels)) var_labels <- list()
label_of <- function(var_name) {
  lbl <- var_labels[[var_name]]
  if (is.null(lbl) || lbl == "") var_name else lbl
}

# ── Calibration ────────────────────────────────────────────────────────────
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
  data.frame(
    variable = v, label = label_of(v),
    full_exclusion = th[1], crossover = th[2], full_inclusion = th[3],
    stringsAsFactors = FALSE
  )
})
thresholds_df <- bind_rows(threshold_rows)
write_csv(thresholds_df, file.path(tables_dir, "calibration_thresholds.csv"))

# Calibrate
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
run_robust <- isTRUE(config$robustness)

# ═══════════════════════════════════════════════════════════════════════════
# 1. NECESSITY ANALYSIS — structured tables
# ═══════════════════════════════════════════════════════════════════════════
run_necessity <- function(data, outcome_col, cond_cols, neg_outcome = FALSE) {
  # Use only calibrated columns (f_ prefix) to avoid pof validation error
  cal_cols <- c(outcome_col, cond_cols)
  cal_data <- data[, cal_cols, drop = FALSE]
  rows <- lapply(cond_cols, function(cond) {
    res <- tryCatch(
      pof(data = cal_data, outcome = outcome_col, relation = "necessity",
          conditions = cond, neg.out = neg_outcome),
      error = function(e) NULL
    )
    if (is.null(res)) {
      c(NA_real_, NA_real_)
    } else {
      c(round(res$incl.cov[1, 1], 4), round(res$incl.cov[1, 2], 4))
    }
  })
  data.frame(
    condition = cond_cols,
    label = sapply(cond_cols, function(x) label_of(gsub("^f_", "", x))),
    consistency = sapply(rows, `[`, 1),
    coverage = sapply(rows, `[`, 2),
    stringsAsFactors = FALSE
  )
}

nec_high_df <- run_necessity(qdat, out_f, cond_f, neg_outcome = FALSE)
write_csv(nec_high_df, file.path(tables_dir, "necessity_high.csv"))

if (run_low) {
  nec_low_df <- run_necessity(qdat, out_f, cond_f, neg_outcome = TRUE)
} else {
  nec_low_df <- data.frame(
    condition = cond_f, label = sapply(cond_f, function(x) label_of(gsub("^f_", "", x))),
    consistency = NA_real_, coverage = NA_real_,
    stringsAsFactors = FALSE
  )
}
write_csv(nec_low_df, file.path(tables_dir, "necessity_low.csv"))

# ═══════════════════════════════════════════════════════════════════════════
# 2. TRUTH TABLE
# ═══════════════════════════════════════════════════════════════════════════
tt_high <- tryCatch(
  truthTable(qdat, outcome = out_f, conditions = cond_f,
             n.cut = n_cut, incl.cut = incl_cut, pri.cut = pri_cut,
             complete = TRUE, show.cases = TRUE, sort.by = "incl"),
  error = function(e) e
)

tt_high_df <- if (inherits(tt_high, "error")) {
  data.frame(error = tt_high$message)
} else {
  tt <- as.data.frame(tt_high$tt)
  tt$cases <- sapply(tt_high$tt$cases, function(x) paste(x, collapse = "; "))
  tt
}
write_csv(tt_high_df, file.path(tables_dir, "truth_table_high.csv"))

# ═══════════════════════════════════════════════════════════════════════════
# 3. SUFFICIENCY ANALYSIS — 3 solutions (complex, parsimonious, intermediate)
# ═══════════════════════════════════════════════════════════════════════════

run_solutions <- function(tt) {
  if (inherits(tt, "error")) return(NULL)

  # Complex (no remainders)
  sol_complex <- tryCatch(
    minimize(tt, details = TRUE, show.cases = TRUE),
    error = function(e) NULL
  )

  # Parsimonious (all remainders)
  sol_pars <- tryCatch(
    minimize(tt, details = TRUE, show.cases = TRUE, include = "?"),
    error = function(e) NULL
  )

  # Intermediate (directional expectations: all conditions expected positive)
  dir_exp <- rep(1, length(conditions))
  sol_inter <- tryCatch(
    minimize(tt, details = TRUE, show.cases = TRUE, include = "?", dir.exp = dir_exp),
    error = function(e) NULL
  )

  list(complex = sol_complex, parsimonious = sol_pars, intermediate = sol_inter)
}

sol_high <- run_solutions(tt_high)

# ── Extract solution metrics as structured table ───────────────────────────
# New QCA package (≥3.0): sol$IC is a QCA_pof list with $overall$incl.cov
extract_metrics <- function(sol, sol_name) {
  if (is.null(sol) || inherits(sol, "error") || is.null(sol$IC$overall)) {
    return(data.frame(
      path = character(0), solution_type = character(0),
      consistency = numeric(0), raw_coverage = numeric(0), unique_coverage = numeric(0),
      formula = character(0), stringsAsFactors = FALSE
    ))
  }
  icdf <- sol$IC$overall$incl.cov
  if (is.null(icdf) || nrow(icdf) == 0) {
    return(data.frame(
      path = character(0), solution_type = character(0),
      consistency = numeric(0), raw_coverage = numeric(0), unique_coverage = numeric(0),
      formula = character(0), stringsAsFactors = FALSE
    ))
  }
  formulas <- rownames(icdf)
  data.frame(
    path = paste0("H", seq_len(nrow(icdf))),
    solution_type = sol_name,
    consistency = round(as.numeric(icdf$inclS), 4),
    raw_coverage = round(as.numeric(icdf$covS), 4),
    unique_coverage = round(as.numeric(icdf$covU), 4),
    formula = formulas,
    stringsAsFactors = FALSE
  )
}

extract_overall <- function(sol, sol_name) {
  if (is.null(sol) || inherits(sol, "error") || is.null(sol$IC$overall)) {
    return(data.frame(
      solution_type = sol_name, solution_consistency = NA_real_,
      solution_coverage = NA_real_, n_paths = 0L,
      stringsAsFactors = FALSE
    ))
  }
  si <- sol$IC$overall$sol.incl.cov
  icdf <- sol$IC$overall$incl.cov
  n_paths <- if (is.null(icdf)) 0L else nrow(icdf)
  data.frame(
    solution_type = sol_name,
    solution_consistency = if (!is.null(si)) round(as.numeric(si$inclS), 4) else NA_real_,
    solution_coverage = if (!is.null(si)) round(as.numeric(si$covS), 4) else NA_real_,
    n_paths = n_paths,
    stringsAsFactors = FALSE
  )
}

if (!is.null(sol_high)) {
  # Metrics
  metrics_high <- bind_rows(
    extract_metrics(sol_high$intermediate, "intermediate"),
    extract_metrics(sol_high$parsimonious, "parsimonious"),
    extract_metrics(sol_high$complex, "complex")
  )
  write_csv(metrics_high, file.path(tables_dir, "solution_metrics_high.csv"))

  overall_high <- bind_rows(
    extract_overall(sol_high$intermediate, "intermediate"),
    extract_overall(sol_high$parsimonious, "parsimonious"),
    extract_overall(sol_high$complex, "complex")
  )
  write_csv(overall_high, file.path(tables_dir, "solution_overall_high.csv"))

  # Configuration table (core/peripheral) — intermediate solution
  sol_int <- sol_high$intermediate
  sol_par <- sol_high$parsimonious

  # New QCA: IC is a list with $overall$incl.cov (data.frame, one row per path)
  icdf <- sol_int$IC$overall$incl.cov
  n_paths <- if (is.null(icdf)) 0L else nrow(icdf)

  if (n_paths > 0) {
    config_rows <- list()

    # Build formula strings from row names
    formulas_int <- rownames(icdf)

    # Parsimonious formula for core/peripheral comparison
    formulas_par <- if (!is.null(sol_par) && !is.null(sol_par$IC$overall$incl.cov)) {
      rownames(sol_par$IC$overall$incl.cov)
    } else { character(0) }
    par_text <- paste(formulas_par, collapse = " ")

    for (p in seq_len(n_paths)) {
      path_expr <- formulas_int[p]

      for (j in seq_along(conditions)) {
        v <- conditions[j]
        v_label <- label_of(v)

        # Determine presence/absence in this path
        is_neg <- grepl(paste0("~", v), path_expr, fixed = TRUE)
        in_sol <- grepl(v, path_expr, fixed = TRUE)

        # Core vs peripheral: does this condition also appear in parsimonious?
        is_neg_par <- grepl(paste0("~", v), par_text, fixed = TRUE)
        in_par <- grepl(v, par_text, fixed = TRUE)

        status <- if (is_neg) {
          if (is_neg_par) "core_absent" else "peripheral_absent"
        } else if (in_sol) {
          if (in_par) "core_present" else "peripheral_present"
        } else {
          "irrelevant"
        }

        config_rows[[length(config_rows) + 1]] <- data.frame(
          path = paste0("H", p),
          condition = v,
          label = v_label,
          status = status,
          consistency = round(as.numeric(icdf$inclS[p]), 4),
          raw_coverage = round(as.numeric(icdf$covS[p]), 4),
          formula = path_expr,
          stringsAsFactors = FALSE
        )
      }
    }
    config_table_high <- bind_rows(config_rows)
  } else {
    config_table_high <- data.frame(
      path = character(0), condition = character(0), label = character(0),
      status = character(0), consistency = numeric(0),
      raw_coverage = numeric(0), formula = character(0),
      stringsAsFactors = FALSE
    )
  }
  write_csv(config_table_high, file.path(tables_dir, "config_table_high.csv"))

  # Save full solution text
  solution_txt <- c(
    "═══════════════════════ fsQCA 充分条件分析结果 ═══════════════════════",
    "",
    "结果变量：", paste0("  ", outcome, " = ", label_of(outcome)),
    "条件变量：",
    unlist(lapply(conditions, function(v) paste0("  ", v, " = ", label_of(v)))),
    "",
    "参数设置：",
    paste0("  一致性阈值: ", incl_cut),
    paste0("  PRI阈值: ", pri_cut),
    paste0("  频数阈值: ", n_cut),
    "",
    "───────────────── 复杂解 (Complex) ─────────────────",
    if (!is.null(sol_high$complex) && !inherits(sol_high$complex, "error"))
      capture.output(print(sol_high$complex)) else "  无解。",
    "",
    "───────────────── 精简解 (Parsimonious) ─────────────────",
    if (!is.null(sol_high$parsimonious) && !inherits(sol_high$parsimonious, "error"))
      capture.output(print(sol_high$parsimonious)) else "  无解。",
    "",
    "───────────────── 中间解 (Intermediate) ─────────────────",
    if (!is.null(sol_high$intermediate) && !inherits(sol_high$intermediate, "error"))
      capture.output(print(sol_high$intermediate)) else "  无解。"
  )
  writeLines(solution_txt, file.path(files_dir, "qca_solutions.txt"), useBytes = TRUE)
}

# ═══════════════════════════════════════════════════════════════════════════
# 4. LOW OUTCOME ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
if (run_low) {
  tt_low <- tryCatch(
    truthTable(qdat, outcome = out_f, neg.out = TRUE, conditions = cond_f,
               n.cut = n_cut, incl.cut = incl_cut, pri.cut = pri_cut,
               complete = TRUE, show.cases = TRUE, sort.by = "incl"),
    error = function(e) e
  )

  tt_low_df <- if (inherits(tt_low, "error")) {
    data.frame(error = tt_low$message)
  } else {
    tt <- as.data.frame(tt_low$tt)
    tt$cases <- sapply(tt_low$tt$cases, function(x) paste(x, collapse = "; "))
    tt
  }
  write_csv(tt_low_df, file.path(tables_dir, "truth_table_low.csv"))

  sol_low <- run_solutions(tt_low)

  if (!is.null(sol_low)) {
    metrics_low <- bind_rows(
      extract_metrics(sol_low$intermediate, "intermediate"),
      extract_metrics(sol_low$parsimonious, "parsimonious"),
      extract_metrics(sol_low$complex, "complex")
    )
    write_csv(metrics_low, file.path(tables_dir, "solution_metrics_low.csv"))

    overall_low <- bind_rows(
      extract_overall(sol_low$intermediate, "intermediate"),
      extract_overall(sol_low$parsimonious, "parsimonious"),
      extract_overall(sol_low$complex, "complex")
    )
    write_csv(overall_low, file.path(tables_dir, "solution_overall_low.csv"))
  }
}

# ═══════════════════════════════════════════════════════════════════════════
# 5. ROBUSTNESS CHECK (if enabled)
# ═══════════════════════════════════════════════════════════════════════════
if (run_robust) {
  # 20/50/80 calibration
  qdat_r <- dat
  for (v in all_vars) {
    th_r <- as.numeric(quantile(qdat_r[[v]], probs = c(0.20, 0.50, 0.80), na.rm = TRUE))
    qdat_r[[paste0("f_", v)]] <- calibrate(qdat_r[[v]], type = "fuzzy", thresholds = th_r)
    qdat_r[[paste0("f_", v)]][qdat_r[[paste0("f_", v)]] == 0.5] <- 0.501
  }
  qdat_r <- as.data.frame(qdat_r)

  tt_ro <- tryCatch(
    truthTable(qdat_r, outcome = out_f, conditions = cond_f,
               n.cut = n_cut, incl.cut = incl_cut + 0.05, pri.cut = pri_cut,
               complete = TRUE, show.cases = TRUE, sort.by = "incl"),
    error = function(e) NULL
  )

  if (!is.null(tt_ro) && !inherits(tt_ro, "error")) {
    sol_ro <- tryCatch(
      minimize(tt_ro, details = TRUE, show.cases = TRUE, include = "?"),
      error = function(e) NULL
    )
    if (!is.null(sol_ro)) {
      capture.output(
        cat("══════════════ 稳健性检验 (20/50/80 校准, incl_cut 提高 0.05) ══════════════\n"),
        print(sol_ro),
        file = file.path(files_dir, "robustness_check.txt")
      )
    }
  }
}

# ═══════════════════════════════════════════════════════════════════════════
# 6. FIGURES — real solution path diagram + consistency/coverage bar chart
# ═══════════════════════════════════════════════════════════════════════════

# --- Figure 1: Solution consistency & coverage bar chart ---
generate_bar_chart <- function(metrics_df, overall_df, outcome_label, file_png) {
  if (is.null(metrics_df) || nrow(metrics_df) == 0) return(FALSE)
  inter <- metrics_df %>% filter(solution_type == "intermediate")
  if (nrow(inter) == 0) return(FALSE)

  inter$path_label <- paste0(inter$path, "\n", inter$formula)
  plot_df <- inter %>%
    select(path_label, consistency, raw_coverage) %>%
    pivot_longer(-path_label, names_to = "metric", values_to = "value")

  p <- ggplot(plot_df, aes(x = path_label, y = value, fill = metric)) +
    geom_col(position = "dodge", width = 0.6) +
    geom_text(aes(label = sprintf("%.3f", value)),
              position = position_dodge(0.6), vjust = -0.3, size = 3.5) +
    scale_fill_manual(
      values = c(consistency = "#2563EB", raw_coverage = "#F59E0B"),
      labels = c(consistency = "一致性", raw_coverage = "原始覆盖率")
    ) +
    scale_y_continuous(limits = c(0, 1.1), expand = c(0, 0)) +
    labs(
      title = paste0("高结果（", outcome_label, "）组态路径指标"),
      x = "", y = "", fill = ""
    ) +
    theme_minimal(base_family = "") +
    theme(
      plot.title = element_text(hjust = 0.5, size = 14, face = "bold"),
      legend.position = "bottom",
      panel.grid.major.x = element_blank(),
      axis.text.x = element_text(size = 10)
    )

  ggsave(file_png, p, width = 8, height = 5, dpi = 150)
  return(TRUE)
}

if (!is.null(sol_high)) {
  ov_high <- read_csv(file.path(tables_dir, "solution_overall_high.csv"), show_col_types = FALSE)
  generate_bar_chart(
    read_csv(file.path(tables_dir, "solution_metrics_high.csv"), show_col_types = FALSE),
    ov_high,
    label_of(outcome),
    file.path(figures_dir, "solution_bars.png")
  )
}

if (run_low && !is.null(sol_low)) {
  ov_low_file <- file.path(tables_dir, "solution_overall_low.csv")
  met_low_file <- file.path(tables_dir, "solution_metrics_low.csv")
  if (file.exists(ov_low_file) && file.exists(met_low_file)) {
    generate_bar_chart(
      read_csv(met_low_file, show_col_types = FALSE),
      read_csv(ov_low_file, show_col_types = FALSE),
      paste0("非", label_of(outcome)),
      file.path(figures_dir, "solution_bars_low.png")
    )
  }
}

# --- Figure 2: Configuration table as SVG (core/peripheral) ---
svg_config_table <- function(config_df, file_svg, title) {
  if (is.null(config_df) || nrow(config_df) == 0) return(FALSE)

  paths <- unique(config_df$path)
  conds <- unique(config_df$condition)
  n_c <- length(conds)
  n_p <- length(paths)

  cell_w <- 140; cell_h <- 36
  label_w <- 140; header_h <- 50
  total_w <- label_w + n_p * cell_w + 40
  total_h <- header_h + n_c * cell_h + 60

  status_symbol <- function(s) {
    switch(s,
      core_present = "●",
      peripheral_present = "●",
      core_absent = "⊗",
      peripheral_absent = "⊙",
      ""
    )
  }
  status_color <- function(s) {
    switch(s,
      core_present = "#1E40AF",
      peripheral_present = "#60A5FA",
      core_absent = "#DC2626",
      peripheral_absent = "#FCA5A5",
      "#CBD5E1"
    )
  }
  status_size <- function(s) {
    if (grepl("core", s)) "20" else "16"
  }

  svg_lines <- c(
    sprintf('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">',
            total_w, total_h, total_w, total_h),
    '<style>',
    'text { font-family: "PingFang SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS", "Heiti SC", sans-serif; }',
    '.header { fill: #FEF3C7; stroke: #D97706; stroke-width: 1.5; }',
    '.cell { fill: #FFFFFF; stroke: #E2E8F0; stroke-width: 0.5; }',
    '.label-cell { fill: #FFFBEB; stroke: #E2E8F0; stroke-width: 0.5; }',
    '</style>',
    '<rect width="100%" height="100%" fill="white"/>',
    # Title
    sprintf('<text x="%d" y="30" text-anchor="middle" font-size="16" font-weight="bold" fill="#92400E">%s</text>',
            total_w / 2, title),
    # Path headers
    sprintf('<rect x="%d" y="35" width="%d" height="%d" class="header"/>',
            label_w, total_w - label_w - 20, header_h - 10),
    sprintf('<text x="%d" y="65" text-anchor="middle" font-size="13" font-weight="600" fill="#92400E">%s</text>',
            label_w + (total_w - label_w - 20) / 2, "组态路径")
  )

  # Column headers
  for (pi in seq_along(paths)) {
    x <- label_w + (pi - 1) * cell_w + cell_w / 2
    svg_lines <- c(svg_lines, sprintf(
      '<text x="%d" y="65" text-anchor="middle" font-size="12" font-weight="600" fill="#1E40AF">%s</text>',
      x, paths[pi]
    ))
  }

  # Rows
  for (ci in seq_along(conds)) {
    y <- header_h + (ci - 1) * cell_h + cell_h / 2
    # Label
    svg_lines <- c(svg_lines,
      sprintf('<rect x="5" y="%d" width="%d" height="%d" class="label-cell"/>',
              header_h + (ci - 1) * cell_h, label_w - 10, cell_h),
      sprintf('<text x="%d" y="%d" text-anchor="end" font-size="11" fill="#0F172A">%s</text>',
              label_w - 15, header_h + (ci - 1) * cell_h + cell_h - 12, config_df$label[config_df$condition == conds[ci] & config_df$path == paths[1]])
    )
    # Cells
    for (pi in seq_along(paths)) {
      row <- config_df[config_df$path == paths[pi] & config_df$condition == conds[ci], ]
      if (nrow(row) == 0) next
      sx <- label_w + (pi - 1) * cell_w
      sy <- header_h + (ci - 1) * cell_h
      sym <- status_symbol(row$status)
      clr <- status_color(row$status)
      fsize <- status_size(row$status)

      svg_lines <- c(svg_lines,
        sprintf('<rect x="%d" y="%d" width="%d" height="%d" class="cell"/>',
                sx, sy, cell_w, cell_h),
        sprintf('<text x="%d" y="%d" text-anchor="middle" font-size="%s" fill="%s">%s</text>',
                sx + cell_w / 2, sy + cell_h - 11, fsize, clr, sym)
      )
    }
  }

  # Legend
  ly <- total_h - 15
  legend_items <- c(
    list(c("● 核心条件存在", "#1E40AF")),
    list(c("● 边缘条件存在", "#60A5FA")),
    list(c("⊗ 核心条件缺失", "#DC2626")),
    list(c("⊙ 边缘条件缺失", "#FCA5A5"))
  )
  for (li in seq_along(legend_items)) {
    lx <- label_w + (li - 1) * 150
    svg_lines <- c(svg_lines, sprintf(
      '<text x="%d" y="%d" font-size="10" fill="%s">%s</text>',
      lx, ly, legend_items[[li]][2], legend_items[[li]][1]
    ))
  }

  svg_lines <- c(svg_lines, '</svg>')
  writeLines(svg_lines, file_svg, useBytes = TRUE)
  return(TRUE)
}

if (exists("config_table_high") && nrow(config_table_high) > 0) {
  svg_config_table(
    config_table_high,
    file.path(figures_dir, "config_table.svg"),
    paste0("高", label_of(outcome), "的组态路径（中间解）")
  )
}

# ═══════════════════════════════════════════════════════════════════════════
# 7. EXPORT Excel
# ═══════════════════════════════════════════════════════════════════════════
excel_sheets <- list(
  calibration_thresholds = thresholds_df,
  necessity_high = nec_high_df,
  truth_table_high = tt_high_df
)
if (exists("config_table_high")) excel_sheets$config_table_high <- config_table_high
if (exists("metrics_high")) excel_sheets$solution_metrics_high <- metrics_high
if (exists("overall_high")) excel_sheets$solution_overall_high <- overall_high
if (run_low && exists("config_table_low"))
  excel_sheets$config_table_low <- tryCatch(read_csv(file.path(tables_dir, "config_table_low.csv"), show_col_types = FALSE), error = function(e) NULL)
if (run_low && exists("nec_low_df")) excel_sheets$necessity_low <- nec_low_df

write_xlsx(excel_sheets, file.path(files_dir, "qca_results.xlsx"))

# ═══════════════════════════════════════════════════════════════════════════
# 8. REPORT — markdown with interpretation
# ═══════════════════════════════════════════════════════════════════════════
build_report <- function() {
  lines <- c(
    "# fsQCA 分析报告",
    "",
    "## 1. 分析概况",
    "",
    paste0("- 数据集：", config$dataset_name),
    paste0("- 结果变量：", label_of(outcome), "（", outcome, "）"),
    paste0("- 条件变量："),
    paste(sapply(conditions, function(v) paste0("  - ", label_of(v), "（", v, "）")), collapse = "\n"),
    paste0("- 一致性阈值：", incl_cut),
    paste0("- PRI阈值：", pri_cut),
    paste0("- 频数阈值：", n_cut),
    "",
    "## 2. 校准锚点",
    "",
    "| 变量 | 中文标签 | 完全不隶属 | 交叉点 | 完全隶属 |",
    "|------|----------|------------|--------|----------|",
    paste(sapply(all_vars, function(v) {
      th <- get_thresholds(v)
      sprintf("| %s | %s | %.3f | %.3f | %.3f |", v, label_of(v), th[1], th[2], th[3])
    }), collapse = "\n"),
    "",
    "## 3. 必要条件分析",
    "",
    "| 条件 | 中文标签 | 一致性 | 覆盖率 |",
    "|------|----------|--------|--------|",
    paste(sapply(seq_len(nrow(nec_high_df)), function(i) {
      sprintf("| %s | %s | %.4f | %.4f |",
              gsub("^f_", "", nec_high_df$condition[i]),
              nec_high_df$label[i],
              nec_high_df$consistency[i],
              nec_high_df$coverage[i])
    }), collapse = "\n"),
    ""
  )

  # Necessity interpretation
  nec_sig <- nec_high_df[!is.na(nec_high_df$consistency) & nec_high_df$consistency >= 0.90, ]
  if (nrow(nec_sig) > 0) {
    lines <- c(lines,
      paste0("**解读：** ", paste(sapply(seq_len(nrow(nec_sig)), function(i)
        paste0(nec_sig$label[i], "（一致性=", sprintf("%.4f", nec_sig$consistency[i]), "）")
      ), collapse = "、"), "的一致性达到0.90的判断标准，可能构成", label_of(outcome), "的必要条件。但必要条件不等于充分条件，需结合组态分析进一步解释。"),
      ""
    )
  } else {
    lines <- c(lines,
      "**解读：** 各单项条件的一致性均未达到0.90的判断标准，说明单一条件并不构成结果产生的必要条件。这表明结果的形成更可能依赖多个条件之间的组合效应，适合进一步开展组态分析。",
      ""
    )
  }

  # Solution results
  lines <- c(lines,
    "## 4. 充分条件组态分析（高结果）",
    ""
  )

  if (exists("overall_high") && nrow(overall_high) > 0) {
    ov <- overall_high[overall_high$solution_type == "intermediate", ]
    if (nrow(ov) > 0 && ov$n_paths > 0) {
      lines <- c(lines,
        paste0("中间解共识别出 **", ov$n_paths, "条** 通向高", label_of(outcome), "的组态路径。"),
        paste0("总体解一致性：", sprintf("%.4f", ov$solution_consistency),
               "，总体解覆盖度：", sprintf("%.4f", ov$solution_coverage)),
        ""
      )
      if (exists("metrics_high") && nrow(metrics_high) > 0) {
        met <- metrics_high[metrics_high$solution_type == "intermediate", ]
        lines <- c(lines,
          "| 路径 | 一致性 | 原始覆盖率 | 唯一覆盖率 |",
          "|------|--------|------------|------------|",
          paste(sapply(seq_len(nrow(met)), function(i)
            sprintf("| %s | %.4f | %.4f | %.4f |",
                    met$path[i], met$consistency[i],
                    met$raw_coverage[i], met$unique_coverage[i])
          ), collapse = "\n"),
          ""
        )
      }
    }
  } else {
    lines <- c(lines, "未获得充分条件解。", "")
  }

  # Low outcome
  if (run_low) {
    lines <- c(lines, "## 5. 充分条件组态分析（低结果）", "")
    low_file <- file.path(tables_dir, "solution_overall_low.csv")
    if (file.exists(low_file)) {
      ov_low <- read_csv(low_file, show_col_types = FALSE)
      if (nrow(ov_low) > 0) {
        ovl <- ov_low[ov_low$solution_type == "intermediate", ]
        if (nrow(ovl) > 0 && ovl$n_paths > 0) {
          lines <- c(lines,
            paste0("中间解共识别出 **", ovl$n_paths, "条** 通向低", label_of(outcome), "的组态路径。"),
            paste0("总体解一致性：", sprintf("%.4f", ovl$solution_consistency),
                   "，总体解覆盖度：", sprintf("%.4f", ovl$solution_coverage)),
            ""
          )
        }
      }
    }
  }

  lines <- c(lines,
    "## 6. 因果非对称性",
    "",
    "**解读：** fsQCA的核心优势之一是揭示因果非对称性。高结果和低结果的组态路径通常不是简单的镜像反转，而是由不同的条件组合驱动。这意味着促进高水平结果的条件组合，与导致低水平结果的条件组合可能具有不同的逻辑。",
    "",
    "---",
    "*本报告由 fsQCA 科研分析平台自动生成。核心条件：●（既见于精简解又见于中间解）；边缘条件：•（仅见于中间解）。*"
  )

  lines
}

report_lines <- build_report()
writeLines(report_lines, file.path(report_dir, "report.md"), useBytes = TRUE)
