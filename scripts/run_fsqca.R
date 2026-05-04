# ============================================================
# fsQCA Analysis — Publication-Standard Output
# ============================================================
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("Usage: Rscript scripts/run_fsqca.R <run_dir>")
run_dir <- normalizePath(args[[1]], mustWork = TRUE)

packages <- c("QCA", "jsonlite", "readr", "dplyr", "writexl")
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
  cal_data <- as.data.frame(data[, cal_cols, drop = FALSE])
  rows <- lapply(cond_cols, function(cond) {
    res <- tryCatch(
      pof(setms = cal_data[[cond]], outcome = cal_data[[outcome_col]],
          relation = "necessity", neg.out = neg_outcome),
      error = function(e) NULL
    )
    if (is.null(res) || is.null(res$incl.cov) || nrow(res$incl.cov) < 1) {
      c(NA_real_, NA_real_)
    } else {
      c(round(res$incl.cov[1, "inclN"], 4), round(res$incl.cov[1, "covN"], 4))
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
get_solution_pof <- function(sol) {
  if (is.null(sol) || inherits(sol, "error") || is.null(sol$IC)) return(NULL)
  if (!is.null(sol$IC$overall)) return(sol$IC$overall)
  sol$IC
}

extract_metrics <- function(sol, sol_name) {
  ic <- get_solution_pof(sol)
  if (is.null(ic)) {
    return(data.frame(
      path = character(0), solution_type = character(0),
      consistency = numeric(0), raw_coverage = numeric(0), unique_coverage = numeric(0),
      formula = character(0), stringsAsFactors = FALSE
    ))
  }
  icdf <- ic$incl.cov
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
  ic <- get_solution_pof(sol)
  if (is.null(ic)) {
    return(data.frame(
      solution_type = sol_name, solution_consistency = NA_real_,
      solution_coverage = NA_real_, n_paths = 0L,
      stringsAsFactors = FALSE
    ))
  }
  si <- ic$sol.incl.cov
  icdf <- ic$incl.cov
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

  sol_int_ic <- get_solution_pof(sol_int)
  sol_par_ic <- get_solution_pof(sol_par)
  icdf <- if (is.null(sol_int_ic)) NULL else sol_int_ic$incl.cov
  n_paths <- if (is.null(icdf)) 0L else nrow(icdf)

  if (n_paths > 0) {
    config_rows <- list()

    # Build formula strings from row names
    formulas_int <- rownames(icdf)

    # Parsimonious formula for core/peripheral comparison
    formulas_par <- if (!is.null(sol_par_ic) && !is.null(sol_par_ic$incl.cov)) {
      rownames(sol_par_ic$incl.cov)
    } else { character(0) }
    formula_tokens <- function(expr) {
      tokens <- unlist(strsplit(expr, "\\s*[+*]\\s*"))
      trimws(tokens[tokens != ""])
    }
    par_tokens <- unique(unlist(lapply(formulas_par, formula_tokens)))

    for (p in seq_len(n_paths)) {
      path_expr <- formulas_int[p]
      path_tokens <- formula_tokens(path_expr)

      for (j in seq_along(conditions)) {
        v <- conditions[j]
        v_label <- label_of(v)
        term <- paste0("f_", v)
        neg_term <- paste0("~", term)

        # Determine presence/absence in this path
        is_neg <- neg_term %in% path_tokens
        in_sol <- term %in% path_tokens

        # Core vs peripheral: does this condition also appear in parsimonious?
        is_neg_par <- neg_term %in% par_tokens
        in_par <- term %in% par_tokens

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
# 6. EXPORT Excel
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
