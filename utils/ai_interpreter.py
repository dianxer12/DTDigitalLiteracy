from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .file_store import ensure_dir, now_iso, read_json, write_json
from .fsqca_runner import _formula_to_label, _friendly_metric_table, _variable_label


@dataclass(frozen=True)
class AIProvider:
    name: str
    base_url: str
    model: str
    note: str


AI_PROVIDERS = {
    "DeepSeek": AIProvider(
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        note="OpenAI-compatible；DeepSeek 官方兼容入口。",
    ),
    "OpenAI": AIProvider(
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        note="OpenAI Chat Completions。",
    ),
    "Kimi": AIProvider(
        name="Kimi",
        base_url="https://api.moonshot.ai/v1",
        model="kimi-k2-0711-preview",
        note="Moonshot/Kimi OpenAI-compatible。",
    ),
    "Qwen": AIProvider(
        name="Qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        note="阿里云百炼/通义千问 OpenAI 兼容模式，北京区域。",
    ),
    "Zhipu": AIProvider(
        name="Zhipu",
        base_url="https://api.z.ai/api/paas/v4",
        model="glm-4.5-flash",
        note="智谱 GLM OpenAI-compatible；若账号使用旧域名，可改自定义地址。",
    ),
    "Custom": AIProvider(
        name="Custom",
        base_url="",
        model="",
        note="任意 OpenAI-compatible 服务。",
    ),
}


def endpoint_from_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 900,
    timeout: int = 60,
) -> str:
    if not api_key.strip():
        raise ValueError("请先填写 API Token。")
    if not base_url.strip():
        raise ValueError("请先填写 API Base URL。")
    if not model.strip():
        raise ValueError("请先填写模型名称。")

    payload = {
        "model": model.strip(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint_from_base_url(base_url),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 请求失败：HTTP {exc.code}\n{detail[:1200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API 请求失败：{exc.reason}") from exc

    data = json.loads(raw)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"无法解析 API 返回：{raw[:1200]}") from exc
    return str(content).strip()


def _records(df: pd.DataFrame, max_rows: int = 80) -> list[dict[str, Any]]:
    clean = df.head(max_rows).astype(object).where(pd.notna(df.head(max_rows)), None)
    return clean.to_dict(orient="records")


def _solution_type_label(value: str) -> str:
    return {
        "intermediate": "中间解",
        "parsimonious": "精简解",
        "complex": "复杂解",
    }.get(str(value), str(value))


def _table_payload(path: Path, var_labels: dict[str, str]) -> dict[str, Any]:
    df = pd.read_csv(path)
    if path.name.startswith("solution_metrics"):
        friendly = _friendly_metric_table(df, var_labels)
        if "解类型" in friendly.columns:
            friendly["解类型"] = friendly["解类型"].map(_solution_type_label)
    else:
        friendly = df.copy()
        if "formula" in friendly.columns:
            friendly["组态路径"] = friendly["formula"].map(lambda x: _formula_to_label(x, var_labels))
            friendly = friendly.drop(columns=["formula"])
        if "condition" in friendly.columns:
            friendly["condition"] = friendly["condition"].map(lambda x: _variable_label(str(x), var_labels, include_code=True))
        if "variable" in friendly.columns:
            friendly["variable"] = friendly["variable"].map(lambda x: _variable_label(str(x), var_labels, include_code=True))
        if "solution_type" in friendly.columns:
            friendly["solution_type"] = friendly["solution_type"].map(_solution_type_label)
    return {
        "table_name": path.name,
        "row_count": int(len(df)),
        "columns": list(friendly.columns),
        "data": _records(friendly),
    }


def build_interpretation_payload(run_dir: Path, target_type: str, target_id: str) -> dict[str, Any]:
    config = read_json(run_dir / "config.json", {})
    var_labels = config.get("variable_labels", {})
    tables_dir = run_dir / "output" / "tables"
    outcome = config.get("outcome", "")
    conditions = config.get("conditions", [])

    base = {
        "analysis": "fsQCA",
        "dataset": config.get("dataset_name"),
        "outcome": {
            "label": _variable_label(outcome, var_labels),
            "code": outcome,
        },
        "conditions": [
            {"label": _variable_label(v, var_labels), "code": v}
            for v in conditions
        ],
        "parameters": {
            "incl_cut": config.get("incl_cut"),
            "pri_cut": config.get("pri_cut"),
            "n_cut": config.get("n_cut"),
        },
    }

    if target_type == "figure":
        files = {
            "solution_bars_high": ["solution_metrics_high.csv", "solution_overall_high.csv"],
            "solution_bars_low": ["solution_metrics_low.csv", "solution_overall_low.csv"],
            "config_table_high": ["config_table_high.csv", "solution_metrics_high.csv"],
        }.get(target_id, [])
        base["target"] = {"type": "figure", "id": target_id}
        base["tables"] = [
            _table_payload(tables_dir / name, var_labels)
            for name in files
            if (tables_dir / name).exists()
        ]
        return base

    if target_type == "table":
        path = tables_dir / target_id
        if not path.exists():
            raise FileNotFoundError(f"结果表不存在：{target_id}")
        base["target"] = {"type": "table", "id": target_id}
        base["tables"] = [_table_payload(path, var_labels)]
        return base

    raise ValueError(f"未知解读目标：{target_type}")


def build_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是一名熟悉 fsQCA 的中文科研方法顾问。"
        "请基于用户提供的结构化数据写解释，不要声称看到了图片。"
        "优先解释结果含义、关键路径、必要条件/充分条件区别、覆盖率和一致性。"
        "语言要适合论文结果部分，谨慎、客观，不要编造数据中没有的信息。"
    )
    user = (
        "请针对下面这个 fsQCA 图表或数据表写一段中文解读。要求：\n"
        "1. 先用 1-2 句话概括核心发现。\n"
        "2. 再解释关键数值和组态路径的含义。\n"
        "3. 最后给出论文写作中可直接使用的表述建议。\n"
        "4. 不要输出变量编码，除非需要在中文变量名后括号补充。\n\n"
        f"结构化数据：\n{json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def interpretation_store_path(run_dir: Path) -> Path:
    return run_dir / "output" / "ai_interpretations" / "interpretations.json"


def load_interpretations(run_dir: Path) -> dict[str, Any]:
    return read_json(interpretation_store_path(run_dir), {})


def save_interpretation(run_dir: Path, key: str, data: dict[str, Any]) -> None:
    path = interpretation_store_path(run_dir)
    ensure_dir(path.parent)
    current = read_json(path, {})
    current[key] = data
    write_json(path, current)


def interpretation_key(target_type: str, target_id: str) -> str:
    return f"{target_type}:{target_id}"


def generate_interpretation(
    *,
    run_dir: Path,
    target_type: str,
    target_id: str,
    api_key: str,
    base_url: str,
    model: str,
    provider: str,
) -> str:
    payload = build_interpretation_payload(run_dir, target_type, target_id)
    content = call_openai_compatible(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=build_messages(payload),
    )
    save_interpretation(
        run_dir,
        interpretation_key(target_type, target_id),
        {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "target_type": target_type,
            "target_id": target_id,
            "content": content,
            "created_at": now_iso(),
        },
    )
    return content
