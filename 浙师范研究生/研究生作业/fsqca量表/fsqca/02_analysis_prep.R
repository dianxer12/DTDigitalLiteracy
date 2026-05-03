# =========================
# 1. 安装并加载包
# =========================
packages <- c("readxl", "dplyr", "psych", "writexl")
installed <- rownames(installed.packages())

for (p in packages) {
  if (!(p %in% installed)) install.packages(p)
}

library(readxl)
library(dplyr)
library(psych)
library(writexl)

# =========================
# 2. 读取上一步处理后的完整数据
# =========================
dat <- read_excel("processed_full_data.xlsx")

cat("读取完成：", dim(dat)[1], "行,", dim(dat)[2], "列\n")
# =========================
# 3. 定义各量表题项
# =========================

# 组织支持（用反向处理后的 scored 题项）
os_work_support_items   <- paste0("os", 1:11, "_scored")
os_value_identity_items <- paste0("os", 12:18, "_scored")
os_benefit_care_items   <- paste0("os", 19:23, "_scored")
os_all_items            <- paste0("os", 1:23, "_scored")

# 工作投入
we_vigor_items      <- paste0("we", c(1, 4, 8, 12, 15, 17))
we_dedication_items <- paste0("we", c(2, 5, 7, 10, 13))
we_absorption_items <- paste0("we", c(3, 6, 9, 11, 14, 16))
we_all_items        <- paste0("we", 1:17)

# 数字胜任力
dc_professional_engagement <- paste0("dc", 1:4)
dc_digital_resources       <- paste0("dc", 5:7)
dc_teaching_learning       <- paste0("dc", 8:11)
dc_assessment_feedback     <- paste0("dc", 12:14)
dc_empowering_learners     <- paste0("dc", 15:17)
dc_facilitating_digital    <- paste0("dc", 18:22)
dc_all_items               <- paste0("dc", 1:22)

# 数字素养
dl_concept_awareness <- paste0("dl", 1:6)
dl_knowledge_skills  <- paste0("dl", 7:13)
dl_application_eval  <- paste0("dl", 14:24)
dl_security_respons  <- paste0("dl", 25:28)
dl_professional_dev  <- paste0("dl", 29:33)
dl_all_items         <- paste0("dl", 1:33)
# =========================
# 4. 定义信度分析函数
# =========================
get_alpha_result <- function(data, items, scale_name) {
  subdat <- data[, items, drop = FALSE] %>% as.data.frame()
  
  a <- psych::alpha(subdat, check.keys = TRUE)
  
  # 更稳妥地提取平均题间相关
  mean_r <- NA_real_
  
  if ("average_r" %in% names(a)) {
    tmp <- a[["average_r"]]
    if (length(tmp) > 0 && is.numeric(tmp)) {
      mean_r <- tmp[1]
    }
  }
  
  if (is.na(mean_r) && "total" %in% names(a)) {
    total_names <- names(a$total)
    if (!is.null(total_names) && "average_r" %in% total_names) {
      tmp <- a$total[["average_r"]]
      if (length(tmp) > 0 && is.numeric(tmp)) {
        mean_r <- tmp[1]
      }
    }
  }
  
  data.frame(
    scale = scale_name,
    n_items = length(items),
    alpha = round(as.numeric(a$total$raw_alpha)[1], 3),
    std_alpha = round(as.numeric(a$total$std.alpha)[1], 3),
    mean_interitem_r = ifelse(is.na(mean_r), NA, round(mean_r, 3)),
    stringsAsFactors = FALSE
  )
}
# =========================
# 5. 各量表信度分析
# =========================
alpha_results <- bind_rows(
  get_alpha_result(dat, os_work_support_items, "组织支持-工作支持"),
  get_alpha_result(dat, os_value_identity_items, "组织支持-价值认同"),
  get_alpha_result(dat, os_benefit_care_items, "组织支持-利益关心"),
  get_alpha_result(dat, os_all_items, "组织支持-总量表"),
  
  get_alpha_result(dat, we_vigor_items, "工作投入-活力"),
  get_alpha_result(dat, we_dedication_items, "工作投入-奉献"),
  get_alpha_result(dat, we_absorption_items, "工作投入-专注"),
  get_alpha_result(dat, we_all_items, "工作投入-总量表"),
  
  get_alpha_result(dat, dc_professional_engagement, "数字胜任力-专业参与"),
  get_alpha_result(dat, dc_digital_resources, "数字胜任力-数字资源"),
  get_alpha_result(dat, dc_teaching_learning, "数字胜任力-教学与学习"),
  get_alpha_result(dat, dc_assessment_feedback, "数字胜任力-评价与反馈"),
  get_alpha_result(dat, dc_empowering_learners, "数字胜任力-促进学习者发展"),
  get_alpha_result(dat, dc_facilitating_digital, "数字胜任力-促进学习者数字能力"),
  get_alpha_result(dat, dc_all_items, "数字胜任力-总量表"),
  
  get_alpha_result(dat, dl_concept_awareness, "数字素养-数字化观念与意识"),
  get_alpha_result(dat, dl_knowledge_skills, "数字素养-数字技术知识与技能"),
  get_alpha_result(dat, dl_application_eval, "数字素养-数字化应用与评价"),
  get_alpha_result(dat, dl_security_respons, "数字素养-数字安全与责任"),
  get_alpha_result(dat, dl_professional_dev, "数字素养-数字化专业发展"),
  get_alpha_result(dat, dl_all_items, "数字素养-总量表")
)

print(alpha_results)
# =========================
# 6. 描述统计变量
# =========================
summary_vars <- c(
  "os_work_support", "os_value_identity", "os_benefit_care", "os_total",
  "we_vigor", "we_dedication", "we_absorption", "we_total",
  "dc_professional_engagement", "dc_digital_resources", "dc_teaching_learning",
  "dc_assessment_feedback", "dc_empowering_learners", "dc_facilitating_digital", "dc_total",
  "dl_concept_awareness", "dl_knowledge_skills", "dl_application_eval",
  "dl_security_respons", "dl_professional_dev", "dl_total"
)
# =========================
# 7. 描述统计函数
# =========================
get_desc <- function(x, var_name) {
  data.frame(
    variable = var_name,
    n = sum(!is.na(x)),
    mean = round(mean(x, na.rm = TRUE), 3),
    sd = round(sd(x, na.rm = TRUE), 3),
    min = round(min(x, na.rm = TRUE), 3),
    q1 = round(quantile(x, 0.25, na.rm = TRUE), 3),
    median = round(median(x, na.rm = TRUE), 3),
    q3 = round(quantile(x, 0.75, na.rm = TRUE), 3),
    max = round(max(x, na.rm = TRUE), 3),
    stringsAsFactors = FALSE
  )
}
# =========================
# 8. 批量描述统计
# =========================
desc_results <- bind_rows(
  lapply(summary_vars, function(v) get_desc(dat[[v]], v))
)

print(desc_results)
# =========================
# 9. fsQCA校准前分位数检查
# =========================
qca_core_vars <- c("os_total", "we_total", "dc_total", "dl_total")

quantile_results <- bind_rows(
  lapply(qca_core_vars, function(v) {
    x <- dat[[v]]
    data.frame(
      variable = v,
      p25 = round(quantile(x, 0.25, na.rm = TRUE), 3),
      p50 = round(quantile(x, 0.50, na.rm = TRUE), 3),
      p75 = round(quantile(x, 0.75, na.rm = TRUE), 3),
      stringsAsFactors = FALSE
    )
  })
)

print(quantile_results)
# =========================
# 10. 所有维度分位数
# =========================
quantile_results_all <- bind_rows(
  lapply(summary_vars, function(v) {
    x <- dat[[v]]
    data.frame(
      variable = v,
      p25 = round(quantile(x, 0.25, na.rm = TRUE), 3),
      p50 = round(quantile(x, 0.50, na.rm = TRUE), 3),
      p75 = round(quantile(x, 0.75, na.rm = TRUE), 3),
      stringsAsFactors = FALSE
    )
  })
)

print(quantile_results_all)
# =========================
# 11. 导出信度、描述统计、分位数
# =========================
write_xlsx(
  list(
    alpha_results = alpha_results,
    descriptive_statistics = desc_results,
    qca_core_quantiles = quantile_results,
    qca_all_quantiles = quantile_results_all
  ),
  "analysis_summary_results.xlsx"
)

cat("已导出 analysis_summary_results.xlsx\n")