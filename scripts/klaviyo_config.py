"""Klaviyo dashboard region configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RegionConfig:
    code: str
    currency: str
    fx_to_cny: float
    metric_id: str | None = None  # Placed Order; auto-resolved if None

    @property
    def api_key_env(self) -> str:
        return f"KLAVIYO_API_KEY_{self.code}"


REGIONS: list[RegionConfig] = [
    RegionConfig("US", "USD", 6.88, "W4SECN"),
    RegionConfig("AU", "AUD", 4.89, "Y8AaSW"),
    RegionConfig("CA", "CAD", 5.03, "YmMFzF"),
    RegionConfig("UK", "GBP", 9.31, "WXjPEV"),
    RegionConfig("FR", "EUR", 8.12, "SbKHJs"),
    RegionConfig("DE", "EUR", 8.12, "Y2sa8i"),
    RegionConfig("IT", "EUR", 8.12, "Th8NgK"),
    RegionConfig("EU", "EUR", 8.12, "UagBZw"),
    RegionConfig("ES", "EUR", 8.12, "X6FQfb"),
    RegionConfig("JP", "JPY", 0.044, "YhSbiC"),
    RegionConfig("CL", "CLP", 0.0079, "TZ3CAc"),
]

SITE_ORDER = [r.code for r in REGIONS]

TIMEFRAME = "last_30_days"
API_REVISION = "2024-10-15"

SUCCESS_PLAYBOOK = {
    "title": "成功模式 · 下次可复制",
    "campaign": [
        "受众：优先 Active 30D/60D，避免 ALL 宽网",
        "主题行：促销名 + 时限（Member Day / Prime Day / EOFY / Last Call）",
        "Preview：写清具体利益（折扣、赠品、price guarantee）",
        "排除：近期已购、bounce>1、已参与专项 list",
        "节点：绑定本地购物季（飓风季、EOFY、Cyber Day 等）",
    ],
    "flow": [
        "Checkout/Cart：保持行为触发 + 短序列 + 清晰 CTA",
        "Welcome：3–5 封序列，主要 offer 放在第 2–3 封",
        "Sunset：单独看 list hygiene，不与 Welcome/Checkout 比打开率",
        "Draft：有发送数据则尽快确认 Live / 合并 / 下线",
    ],
}

FAILURE_PLAYBOOK = {
    "title": "失败模式 · 下次避免",
    "campaign": [
        "ALL 宽网 + 纯内容主题 → 打开低、GMV 低",
        "同一活动克隆到冷订阅池",
        "平效期硬广大促",
        "主题行无 offer、无 urgency",
    ],
    "flow": [
        "用 Sunset 打开率评判 Welcome/Checkout 质量",
        "Welcome 序列内首封长期不迭代",
        "Draft Flow 长期挂起但有发送",
        "低 GMV 辅助 Flow 占用过多维护精力",
    ],
}


def api_key_for(region: RegionConfig) -> str | None:
    return os.environ.get(region.api_key_env) or os.environ.get("KLAVIYO_API_KEY")
