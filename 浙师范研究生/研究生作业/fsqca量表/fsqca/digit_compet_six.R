# 加载必要的包
library(readxl)
library(dplyr)
library(QCA)
library(writexl)

# 1. 读取数据
dat <- read_excel("processed_full_data.xlsx")

# 2. 提取变量并转换为标准数据框
# 改为 3 个数字胜任力维度 + 结果变量
dc_qca <- dat %>%
  select(
    id,
    dc_teaching_learning,
    dc_assessment_feedback,
    dc_facilitating_digital,
    dl_total
  ) %>%
  as.data.frame()

summary(dc_qca)

# 3. 计算分位数锚点
get_quantiles <- function(x, var_name) {
  data.frame(
    variable = var_name,
    p25 = round(as.numeric(quantile(x, 0.25, na.rm = TRUE)), 3),
    p50 = round(as.numeric(quantile(x, 0.50, na.rm = TRUE)), 3),
    p75 = round(as.numeric(quantile(x, 0.75, na.rm = TRUE)), 3)
  )
}

dc_quantiles <- bind_rows(
  get_quantiles(dc_qca$dc_teaching_learning, "dc_teaching_learning"),
  get_quantiles(dc_qca$dc_assessment_feedback, "dc_assessment_feedback"),
  get_quantiles(dc_qca$dc_facilitating_digital, "dc_facilitating_digital"),
  get_quantiles(dc_qca$dl_total, "dl_total")
)

print(dc_quantiles)

# 4. 模糊集校准
# 数字胜任力维度仍用理论锚点 c(2, 3, 4)
# 结果变量用你前面跑出来的 dl_total 锚点
dc_qca$f_dctl <- calibrate(
  dc_qca$dc_teaching_learning,
  type = "fuzzy",
  thresholds = c(2, 3, 4)
)

dc_qca$f_dcaf <- calibrate(
  dc_qca$dc_assessment_feedback,
  type = "fuzzy",
  thresholds = c(2, 3, 4)
)

dc_qca$f_dcfd <- calibrate(
  dc_qca$dc_facilitating_digital,
  type = "fuzzy",
  thresholds = c(2, 3, 4)
)

dc_qca$f_dl <- calibrate(
  dc_qca$dl_total,
  type = "fuzzy",
  thresholds = c(4.000, 4.485, 4.970)
)

qca_vars <- c("f_dctl", "f_dcaf", "f_dcfd", "f_dl")
summary(dc_qca[, qca_vars])

# 5. 清理缺失值
dc_qca_clean <- dc_qca[complete.cases(dc_qca[, qca_vars]), ]

# 如果你想避免 0.5 警告，可以把恰好等于 0.5 的值轻微扰动
# 注意：这是技术性处理，只改 very tiny amount
eps <- 0.001
for (v in c("f_dctl", "f_dcaf", "f_dcfd")) {
  dc_qca_clean[[v]][dc_qca_clean[[v]] == 0.5] <- 0.5 + eps
}

write_xlsx(dc_qca_clean, "qca_dc3_calibrated.xlsx")

# 6. 必要条件分析
nec_dc_high <- superSubset(
  data = dc_qca_clean,
  outcome = "f_dl",
  conditions = c("f_dctl", "f_dcaf", "f_dcfd"),
  relation = "nec",
  incl.cut = 0.90
)
print("------ 高水平必要条件分析 ------")
print(nec_dc_high)

nec_dc_low <- superSubset(
  data = dc_qca_clean,
  outcome = "f_dl",
  neg.out = TRUE,
  conditions = c("f_dctl", "f_dcaf", "f_dcfd"),
  relation = "nec",
  incl.cut = 0.90
)
print("------ 低水平（非）必要条件分析 ------")
print(nec_dc_low)

# 7. 真值表构建
tt_dc_high <- truthTable(
  data = dc_qca_clean,
  outcome = "f_dl",
  conditions = c("f_dctl", "f_dcaf", "f_dcfd"),
  n.cut = 2,
  incl.cut = 0.80,
  complete = TRUE,
  show.cases = TRUE
)
print("------ 高水平真值表 ------")
print(tt_dc_high)

tt_dc_low <- truthTable(
  data = dc_qca_clean,
  outcome = "f_dl",
  neg.out = TRUE,
  conditions = c("f_dctl", "f_dcaf", "f_dcfd"),
  n.cut = 2,
  incl.cut = 0.80,
  complete = TRUE,
  show.cases = TRUE
)
print("------ 低水平（非）真值表 ------")
print(tt_dc_low)

# 8. 布尔最小化分析
sol_dc_high <- minimize(tt_dc_high, details = TRUE, show.cases = TRUE)
print("------ 高水平组态求解结果 ------")
print(sol_dc_high)

sol_dc_low <- minimize(tt_dc_low, details = TRUE, show.cases = TRUE)
print("------ 低水平（非）组态求解结果 ------")
print(sol_dc_low)

# 9. 导出结果
tt_dc_high_df <- as.data.frame(tt_dc_high$tt)
tt_dc_low_df  <- as.data.frame(tt_dc_low$tt)

write_xlsx(
  list(
    dc3_quantiles = dc_quantiles,
    dc3_calibrated_data = dc_qca_clean,
    dc3_truth_table_high = tt_dc_high_df,
    dc3_truth_table_low = tt_dc_low_df
  ),
  "qca_dc3_results.xlsx"
)

print("3维度QCA分析已完成，并成功导出结果！")