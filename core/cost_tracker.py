# 文件用途：API 调用成本追踪模块，记录每次 API 调用的 token 消耗和预估费用

import json
from datetime import datetime, date
from pathlib import Path

# 本地记录文件路径
COST_LOG_PATH = Path(__file__).parent.parent / "data" / "cost_log.json"

# DeepSeek-chat 价格（元/百万token）
PRICE_INPUT_PER_M = 1.0   # 输入 1元/百万token
PRICE_OUTPUT_PER_M = 2.0  # 输出 2元/百万token

_PURPOSE_LABELS = {
    "exam": "检验",
    "study": "带学",
    "intel": "情报分析",
    "portfolio": "竞品监测",
    "history": "历史记录",
    "other": "其他",
}


def _load_log() -> list:
    """加载本地 cost_log.json，返回记录列表"""
    if not COST_LOG_PATH.exists():
        return []
    try:
        with open(COST_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_log(records: list) -> None:
    """保存记录列表到 cost_log.json"""
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(COST_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[cost_tracker] 保存失败：{e}")


def log_api_call(model: str, input_tokens: int, output_tokens: int, purpose: str = "other") -> None:
    """
    记录一次 API 调用。

    Args:
        model: 模型名称，如 deepseek-chat
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        purpose: 调用目的，如 exam/study/intel/portfolio
    """
    records = _load_log()
    records.append({
        "ts": datetime.now().isoformat(),
        "date": date.today().isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "purpose": purpose,
    })
    # 只保留最近5000条，防止文件过大
    if len(records) > 5000:
        records = records[-5000:]
    _save_log(records)


def get_cost_summary() -> dict:
    """
    返回累计 API 调用统计。

    Returns:
        {
            total_calls, total_input_tokens, total_output_tokens,
            total_cost_yuan, today_calls, today_input_tokens,
            today_output_tokens, today_cost_yuan,
            by_purpose: {purpose: {calls, input_tokens, output_tokens, cost_yuan}}
        }
    """
    records = _load_log()
    today_str = date.today().isoformat()

    total_calls = len(records)
    total_input = sum(r.get("input_tokens", 0) for r in records)
    total_output = sum(r.get("output_tokens", 0) for r in records)
    total_cost = (total_input * PRICE_INPUT_PER_M + total_output * PRICE_OUTPUT_PER_M) / 1_000_000

    today_records = [r for r in records if r.get("date") == today_str]
    today_calls = len(today_records)
    today_input = sum(r.get("input_tokens", 0) for r in today_records)
    today_output = sum(r.get("output_tokens", 0) for r in today_records)
    today_cost = (today_input * PRICE_INPUT_PER_M + today_output * PRICE_OUTPUT_PER_M) / 1_000_000

    by_purpose: dict = {}
    for r in records:
        p = r.get("purpose", "other")
        if p not in by_purpose:
            by_purpose[p] = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        by_purpose[p]["calls"] += 1
        by_purpose[p]["input_tokens"] += r.get("input_tokens", 0)
        by_purpose[p]["output_tokens"] += r.get("output_tokens", 0)

    for p, stats in by_purpose.items():
        stats["cost_yuan"] = round(
            (stats["input_tokens"] * PRICE_INPUT_PER_M + stats["output_tokens"] * PRICE_OUTPUT_PER_M) / 1_000_000, 4
        )
        stats["label"] = _PURPOSE_LABELS.get(p, p)

    return {
        "total_calls": total_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_yuan": round(total_cost, 4),
        "today_calls": today_calls,
        "today_input_tokens": today_input,
        "today_output_tokens": today_output,
        "today_cost_yuan": round(today_cost, 4),
        "by_purpose": by_purpose,
    }
