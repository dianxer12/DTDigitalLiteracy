# =========================
# 1. 安装并加载包
# =========================
packages <- c("readxl", "dplyr", "QCA", "writexl")
installed <- rownames(installed.packages())

for (p in packages) {
  if (!(p %in% installed)) install.packages(p)
}

library(readxl)
library(dplyr)
library(QCA)
library(writexl)

# =========================
# 2. 读取数据
# =========================
dat <- read_excel("processed_full_data.xlsx")

cat("读取完成：", dim(dat)[1], "行,", dim(dat)[2], "列\n")
# =========================
# 3. 检查变量
# =========================
vars_needed <- c("id", "os_total", "we_total", "dc_total", "dl_total")

missing_vars <- setdiff(vars_needed, colnames(dat))
if (length(missing_vars) > 0) {
  stop(paste("缺少以下变量：", paste(missing_vars, collapse = ", ")))
}

summary(dat[, vars_needed])
# =========================
# 4. 提取总模型数据
# =========================
qca_dat <- dat %>%
  select(id, os_total, we_total, dc_total, dl_total)

head(qca_dat)
# =========================
# 5. 计算分位数锚点
# =========================
get_quantiles <- function(x, var_name) {
  data.frame(
    variable = var_name,
    p25 = round(as.numeric(quantile(x, 0.25, na.rm = TRUE)), 3),
    p50 = round(as.numeric(quantile(x, 0.50, na.rm = TRUE)), 3),
    p75 = round(as.numeric(quantile(x, 0.75, na.rm = TRUE)), 3)
  )
}

quantiles_total <- bind_rows(
  get_quantiles(qca_dat$os_total, "os_total"),
  get_quantiles(qca_dat$we_total, "we_total"),
  get_quantiles(qca_dat$dc_total, "dc_total"),
  get_quantiles(qca_dat$dl_total, "dl_total")
)

print(quantiles_total)
# =========================
# 6. 定义读取锚点函数
# =========================
get_thres <- function(qtab, varname) {
  row <- qtab[qtab$variable == varname, c("p25", "p50", "p75"), drop = FALSE]
  
  if (nrow(row) != 1) {
    stop(paste("锚点提取失败，变量名检查：", varname))
  }
  
  as.numeric(unlist(row[1, ]))
}

# =========================
# 7. fuzzy calibration
# =========================
qca_dat$f_os <- calibrate(
  qca_dat$os_total,
  type = "fuzzy",
  thresholds = get_thres(quantiles_total, "os_total")
)

qca_dat$f_we <- calibrate(
  qca_dat$we_total,
  type = "fuzzy",
  thresholds = get_thres(quantiles_total, "we_total")
)

qca_dat$f_dc <- calibrate(
  qca_dat$dc_total,
  type = "fuzzy",
  thresholds = get_thres(quantiles_total, "dc_total")
)

qca_dat$f_dl <- calibrate(
  qca_dat$dl_total,
  type = "fuzzy",
  thresholds = get_thres(quantiles_total, "dl_total")
)

summary(qca_dat[, c("f_os", "f_we", "f_dc", "f_dl")])
# =========================
# 8. 转换为标准数据框并导出
# =========================
# 【关键修复】：将 tibble 转换为标准 data.frame
qca_dat <- as.data.frame(qca_dat)

write_xlsx(qca_dat, "qca_total_calibrated_data.xlsx")
cat("已导出 qca_total_calibrated_data.xlsx\n")

# =========================
# 9. 必要条件分析：高数字素养
# =========================
# 注意：新版 QCA 将 exo.facs 更改为 conditions
nec_high <- superSubset(
  data = qca_dat,
  outcome = "f_dl",
  conditions = c("f_os", "f_we", "f_dc"), 
  relation = "nec",
  incl.cut = 0.90
)

print(nec_high)
# =========================
# 10. 必要条件分析：非高数字素养
# =========================
nec_low <- superSubset(
  data = qca_dat,
  outcome = "f_dl",
  neg.out = TRUE,
  conditions = c("f_os", "f_we", "f_dc"),
  relation = "nec",
  incl.cut = 0.90
)

print(nec_low)
# =========================
# 11. 真值表：高数字素养
# =========================
# 注意：新版 QCA 将 incl.cut1 更改为 incl.cut
tt_high <- truthTable(
  data = qca_dat,
  outcome = "f_dl",
  conditions = c("f_os", "f_we", "f_dc"),
  n.cut = 2,
  incl.cut = 0.80,  
  complete = TRUE,
  show.cases = TRUE
)

print(tt_high)
# =========================
# 12. 真值表：非高数字素养
# =========================
tt_low <- truthTable(
  data = qca_dat,
  outcome = "f_dl",
  neg.out = TRUE,
  conditions = c("f_os", "f_we", "f_dc"),
  n.cut = 2,
  incl.cut = 0.80,
  complete = TRUE,
  show.cases = TRUE
)

print(tt_low)
# =========================
# 13. 充分条件组态：高数字素养
# =========================
sol_high <- minimize(
  tt_high,
  details = TRUE,
  show.cases = TRUE,
  include = "?"
)

print(sol_high)
# =========================
# 14. 充分条件组态：非高数字素养
# =========================
sol_low <- minimize(
  tt_low,
  details = TRUE,
  show.cases = TRUE,
  include = "?"
)

print(sol_low)
# =========================
# 15. 导出真值表
# =========================
tt_high_df <- as.data.frame(tt_high$tt)
tt_low_df  <- as.data.frame(tt_low$tt)

write_xlsx(
  list(
    quantiles_total = quantiles_total,
    qca_calibrated_data = qca_dat,
    truth_table_high = tt_high_df,
    truth_table_low = tt_low_df
  ),
  "qca_total_results.xlsx"
)

cat("已导出 qca_total_results.xlsx\n")

sol_high <- minimize(tt_high, details = TRUE, show.cases = TRUE)
print(sol_high)

sol_low <- minimize(tt_low, details = TRUE, show.cases = TRUE)
print(sol_low)