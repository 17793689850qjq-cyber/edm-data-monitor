"""Rank emails and build insight copy from Klaviyo report rows."""

from __future__ import annotations


def fmt_pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def fmt_gmv(gmv: float, ccy: str) -> str:
    if ccy in ("CLP", "JPY"):
        if gmv >= 1_000_000:
            return f"{gmv / 1_000_000:.1f}M {ccy}"
        return f"{gmv / 1000:.0f}K {ccy}"
    if gmv >= 1_000_000:
        return f"{gmv / 1_000_000:.2f}M {ccy}"
    if gmv >= 1_000:
        return f"{gmv / 1000:.0f}K {ccy}"
    return f"{gmv:.0f} {ccy}"


FLOW_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


def normalize_priority(priority: str | int | None) -> str:
    if priority is None:
        return ""
    raw = str(priority).strip().upper()
    if raw in FLOW_PRIORITY_RANK:
        return raw
    if raw.isdigit():
        return f"P{raw}"
    if raw.startswith("P") and raw[1:].isdigit():
        return f"P{raw[1:]}"
    return raw


def flow_alert_sort_key(alert: dict) -> tuple[int, str]:
    return (FLOW_PRIORITY_RANK.get(normalize_priority(alert.get("priority")), 99), alert.get("region", ""))


def is_sunset(name: str) -> bool:
    return "sunset" in name.lower()


def score_best(item: tuple) -> tuple:
    _, _rec, _open_r, _click, conv, gmv, _status = item
    return (gmv, gmv / max(_rec, 1), conv)


def score_worst(item: tuple, min_rec: int = 500) -> float | None:
    _name, rec, open_r, click, conv, gmv, _status = item
    if rec < min_rec:
        return None
    pain = (1 - open_r) * 0.4 + (1 - min(conv * 100, 1)) * 0.4 + (1 - min(click * 10, 1)) * 0.2
    if gmv == 0 and open_r < 0.25:
        pain += 0.3
    return pain


def rank_items(items: list[tuple], kind: str, min_rec: int = 500) -> tuple[list, list, list]:
    eligible = [i for i in items if i[1] >= (100 if kind == "flow" else min_rec)]
    if not eligible:
        eligible = [i for i in items if i[1] >= 50]
    best = sorted(eligible, key=score_best, reverse=True)[:3]
    best_names = {i[0] for i in best}
    candidates = [i for i in eligible if i[0] not in best_names]
    actionable = [i for i in candidates if not is_sunset(i[0])]
    sunset = [i for i in candidates if is_sunset(i[0])]
    worst_scored = []
    for item in actionable:
        s = score_worst(item, min_rec=200 if kind == "flow" else min_rec)
        if s is not None:
            worst_scored.append((s, item))
    worst = [x[1] for x in sorted(worst_scored, key=lambda t: t[0], reverse=True)[:3]]
    return best, worst, sunset


def explain_campaign(name: str, subject: str, audiences: list[str], open_r: float, click: float, conv: float, gmv: float, ccy: str, positive: bool) -> list[str]:
    reasons: list[str] = []
    aud = ", ".join(audiences[:3]) if audiences else "—"
    if subject and subject != name:
        reasons.append(f"Subject 点明主题：{subject[:80]}")
    if audiences:
        reasons.append(f"受众：{aud}")
    if any("ALL" in a.upper() for a in audiences):
        reasons.append(f"含 ALL 宽网，打开 {fmt_pct(open_r)}")
    elif any("Active" in a for a in audiences):
        reasons.append(f"Active 分层，打开 {fmt_pct(open_r)}")
    if positive:
        if gmv > 0:
            reasons.append(f"GMV {fmt_gmv(gmv, ccy)}")
        if click >= 0.02:
            reasons.append(f"点击 {fmt_pct(click)}")
    else:
        if open_r < 0.3:
            reasons.append(f"打开率偏低（{fmt_pct(open_r)}）")
        if click < 0.01:
            reasons.append(f"点击率低（{fmt_pct(click)}）")
        if conv < 0.0002 and gmv < 1000:
            reasons.append("转化与 GMV 均偏弱")
    return reasons[:4] or [name]


def explain_flow(name: str, open_r: float, conv: float, gmv: float, ccy: str, status: str, positive: bool) -> list[str]:
    if is_sunset(name):
        return ["List Hygiene 序列，低打开为预期行为"]
    reasons: list[str] = []
    if positive:
        if conv >= 0.01:
            reasons.append(f"转化 {fmt_pct(conv, 2)}")
        if gmv > 0:
            reasons.append(f"GMV {fmt_gmv(gmv, ccy)}")
        reasons.append(f"打开 {fmt_pct(open_r)}")
    else:
        if status.lower() == "draft":
            reasons.append("Draft 状态但周期内有发送，需确认 Live/合并/下线")
        if open_r < 0.2:
            reasons.append(f"打开 {fmt_pct(open_r)} 偏低")
        if gmv == 0:
            reasons.append("近 30 天无 GMV")
    return reasons[:3] or [name]


def to_why_item(name: str, subject: str, audiences: list[str], item: tuple, ccy: str, positive: bool) -> dict:
    _name, rec, open_r, click, conv, gmv, status = item
    return {
        "name": name,
        "subject": subject or name,
        "audience": ", ".join(audiences[:4]) if audiences else "—",
        "metrics": {
            "recipients": int(rec),
            "openRate": open_r,
            "clickRate": click,
            "convRate": conv,
            "gmv": gmv,
        },
        "reasons": explain_campaign(name, subject or "", audiences, open_r, click, conv, gmv, ccy, positive),
    }


def to_flow_why_item(item: tuple, ccy: str, positive: bool) -> dict:
    name, rec, open_r, click, conv, gmv, status = item
    return {
        "name": name,
        "subject": "—",
        "audience": "—",
        "metrics": {
            "recipients": int(rec),
            "openRate": open_r,
            "clickRate": click,
            "convRate": conv,
            "gmv": gmv,
        },
        "reasons": explain_flow(name, open_r, conv, gmv, ccy, status, positive),
    }


def build_flow_alerts(flows: list[tuple], region: str, ccy: str) -> list[dict]:
    alerts: list[dict] = []
    for name, rec, open_r, click, conv, gmv, status in flows:
        base = f"近30天发送 {int(rec):,} · 打开 {fmt_pct(open_r)} · 点击 {fmt_pct(click, 2)} · GMV {fmt_gmv(gmv, ccy)}"
        if status.lower() == "draft" and rec >= 10:
            alerts.append({
                "priority": "P1",
                "region": region,
                "flow": name,
                "category": "Draft",
                "issue": f"Draft 状态仍有发送 · {base}",
                "action": "确认 Live / 合并 / 下线，避免与 Live 版本并存",
            })
        elif is_sunset(name) and rec >= 100:
            alerts.append({
                "priority": "P2",
                "region": region,
                "flow": name,
                "category": "Sunset",
                "issue": f"List Hygiene 序列 · {base}（低打开为预期）",
                "action": "仅监控 list 健康，不与 Welcome/Checkout 比打开率",
            })
        elif "welcome" in name.lower() and rec >= 1000 and open_r < 0.32:
            alerts.append({
                "priority": "P1",
                "region": region,
                "flow": name,
                "category": "Welcome",
                "issue": f"Welcome 打开 {fmt_pct(open_r)} 偏低 · {base}",
                "action": "A/B 首封 Subject 或调整序列发送顺序",
            })
        elif not is_sunset(name) and rec >= 500 and gmv == 0 and open_r < 0.15:
            alerts.append({
                "priority": "P2",
                "region": region,
                "flow": name,
                "category": "Other",
                "issue": f"大发送量但无 GMV · {base}",
                "action": "评估降频、合并或下线",
            })
        elif not is_sunset(name) and status.lower() == "live" and rec >= 200 and gmv > 0 and conv < 0.003 and "checkout" not in name.lower() and "cart" not in name.lower() and "abandon" not in name.lower():
            alerts.append({
                "priority": "P2",
                "region": region,
                "flow": name,
                "category": "Other",
                "issue": f"Live 但转化偏弱 · {base}",
                "action": "检查 offer / CTA，或与 Checkout 序列对比",
            })
    for alert in alerts:
        alert["priority"] = normalize_priority(alert.get("priority"))
    return alerts


def build_flow_insights(
    flows: list[tuple],
    region: str,
    ccy: str,
    site_why: dict,
    alerts: list[dict],
) -> list[dict]:
    best_map = {x["name"]: x for x in site_why.get("flowBest", [])}
    worst_map = {x["name"]: x for x in site_why.get("flowWorst", [])}
    alert_by_flow: dict[str, list[dict]] = {}
    for alert in alerts:
        alert_by_flow.setdefault(alert["flow"], []).append(alert)

    items: list[dict] = []
    for name, rec, open_r, click, conv, gmv, status in flows:
        if rec < 10 and gmv == 0:
            continue
        tags: list[str] = []
        if name in best_map:
            tags.append("best")
        if name in worst_map:
            tags.append("improve")
        if name in alert_by_flow:
            tags.append("alert")

        strengths = list(best_map.get(name, {}).get("reasons") or [])
        improvements = list(worst_map.get(name, {}).get("reasons") or [])
        flow_alerts = alert_by_flow.get(name, [])

        if not strengths and gmv > 0 and conv >= 0.005:
            strengths.append(f"转化 {fmt_pct(conv, 2)}，GMV {fmt_gmv(gmv, ccy)}")
        if not strengths and open_r >= 0.35:
            strengths.append(f"打开率 {fmt_pct(open_r)} 表现良好")
        if not improvements and tags == [] and rec >= 200:
            improvements.append("暂无显著问题，保持监控即可")

        if status.lower() == "draft":
            improvements.insert(0, "Draft 状态但周期内有发送，需确认 Live / 合并 / 下线")

        summary_parts: list[str] = []
        if "best" in tags:
            summary_parts.append("表现优秀")
        if "alert" in tags:
            summary_parts.append("有待关注项")
        if "improve" in tags:
            summary_parts.append("有优化空间")
        if not summary_parts:
            summary_parts.append("常规监控")

        items.append({
            "id": f"{region}::{name}",
            "region": region,
            "name": name,
            "status": status,
            "currency": ccy,
            "tags": tags,
            "summary": " · ".join(summary_parts),
            "metrics": {
                "recipients": int(rec),
                "openRate": open_r,
                "clickRate": click,
                "convRate": conv,
                "gmv": gmv,
                "gmvLabel": fmt_gmv(gmv, ccy),
            },
            "strengths": strengths[:5],
            "improvements": improvements[:5],
            "alerts": [
                {
                    "priority": a.get("priority"),
                    "category": a.get("category"),
                    "issue": a.get("issue"),
                    "action": a.get("action"),
                }
                for a in flow_alerts
            ],
        })

    items.sort(key=lambda x: (x["metrics"]["gmv"], x["metrics"]["recipients"]), reverse=True)
    return items


def _delta_label(val: float, avg: float, label: str, higher_is_better: bool = True) -> str | None:
    if avg <= 0:
        return None
    ratio = val / avg
    if higher_is_better:
        if ratio >= 1.25:
            return f"{label} 高于站点均值 {fmt_pct(ratio - 1)}"
        if ratio <= 0.75:
            return f"{label} 低于站点均值 {fmt_pct(1 - ratio)}"
    else:
        if ratio <= 0.75:
            return f"{label} 低于站点均值 {fmt_pct(1 - ratio)}"
        if ratio >= 1.25:
            return f"{label} 高于站点均值 {fmt_pct(ratio - 1)}"
    return None


def _build_benchmark(
    m: dict,
    site_avg: dict,
    item_type: str,
    verdict: str,
    ccy: str,
) -> dict:
    rec = max(m.get("recipients") or 0, 1)
    gmv_per_rec = (m.get("gmv") or 0) / rec
    avg_gmv_per_rec = (site_avg.get("gmv") or 0) / max(site_avg.get("delivered") or site_avg.get("recipients") or 1, 1)
    comparisons: list[str] = []
    for key, label in (
        ("openRate", "打开率"),
        ("clickRate", "点击率"),
        ("convRate", "转化率"),
    ):
        note = _delta_label(m.get(key) or 0, site_avg.get(key) or 0, label)
        if note:
            comparisons.append(note)
    gmv_note = _delta_label(gmv_per_rec, avg_gmv_per_rec, "人均 GMV")
    if gmv_note:
        comparisons.append(gmv_note)
    prefix = "Campaign" if item_type == "campaign" else "Flow"
    summary = (
        f"对比站点 {prefix} 均值：打开 {fmt_pct(site_avg.get('openRate', 0))} · "
        f"点击 {fmt_pct(site_avg.get('clickRate', 0), 2)} · "
        f"转化 {fmt_pct(site_avg.get('convRate', 0), 2)} · "
        f"GMV {fmt_gmv(site_avg.get('gmv', 0), ccy)}"
    )
    if verdict == "copy" and not comparisons:
        comparisons.append(f"各指标均接近或优于站点 {prefix} 均值")
    elif verdict == "avoid" and not comparisons:
        comparisons.append(f"综合表现弱于站点 {prefix} 头部邮件")
    return {"summary": summary, "comparisons": comparisons[:4]}


def _campaign_logic_chain(
    why_item: dict,
    m: dict,
    site_avg: dict,
    verdict: str,
    ccy: str,
) -> list[str]:
    audience = why_item.get("audience") or "—"
    subject = why_item.get("subject") or ""
    rec = int(m.get("recipients") or 0)
    open_r = m.get("openRate") or 0
    click = m.get("clickRate") or 0
    conv = m.get("convRate") or 0
    gmv = m.get("gmv") or 0
    avg_open = site_avg.get("openRate") or 0

    chain: list[str] = []
    if audience != "—":
        chain.append(f"受众分层「{audience}」→ 触达 {rec:,} 人（Placed Order 统计口径）")
    else:
        chain.append(f"全量发送触达 {rec:,} 人（Placed Order 统计口径）")

    subj_hint = f"「{subject[:70]}」" if subject and subject not in ("—", why_item.get("name", "")) else "Subject"
    if open_r >= avg_open * 1.1:
        chain.append(f"{subj_hint} 吸引打开 → 打开率 {fmt_pct(open_r)}（高于站点 Campaign 均值 {fmt_pct(avg_open)}）")
    elif open_r < avg_open * 0.85:
        chain.append(f"{subj_hint} 打开吸引力不足 → 打开率 {fmt_pct(open_r)}（低于站点均值 {fmt_pct(avg_open)}）")
    else:
        chain.append(f"{subj_hint} → 打开率 {fmt_pct(open_r)}（接近站点均值 {fmt_pct(avg_open)}）")

    if click >= 0.02:
        chain.append(f"正文/CTA 有效 → 点击率 {fmt_pct(click, 2)}，引导用户进入落地页")
    elif click < 0.008:
        chain.append(f"点击意愿弱 → 点击率仅 {fmt_pct(click, 2)}，内容与 offer 匹配度待验证")
    else:
        chain.append(f"点击表现中等 → 点击率 {fmt_pct(click, 2)}")

    if conv > 0:
        chain.append(f"落地转化 → 转化率 {fmt_pct(conv, 2)}（Placed Order / 送达）")
    else:
        chain.append("漏斗末端断裂 → 近 30 天无 Placed Order 转化")

    if gmv > 0:
        chain.append(f"收入结果 → GMV {fmt_gmv(gmv, ccy)}（{'可复制此模式' if verdict == 'copy' else 'GMV 未达预期'}）")
    elif verdict == "avoid":
        chain.append("收入结果 → 近 30 天 GMV 为 0，投入产出比不佳")
    return chain[:5]


def _flow_logic_chain(
    why_item: dict,
    m: dict,
    site_avg: dict,
    verdict: str,
    ccy: str,
) -> list[str]:
    name = why_item.get("name") or ""
    rec = int(m.get("recipients") or 0)
    open_r = m.get("openRate") or 0
    click = m.get("clickRate") or 0
    conv = m.get("convRate") or 0
    gmv = m.get("gmv") or 0
    avg_open = site_avg.get("openRate") or 0
    avg_conv = site_avg.get("convRate") or 0

    chain: list[str] = []
    if is_sunset(name):
        chain.append(f"List Hygiene 序列 → 触达 {rec:,} 未互动用户（低打开为预期行为）")
        chain.append(f"打开率 {fmt_pct(open_r)} · 点击 {fmt_pct(click, 2)} — 不与 Welcome/Checkout 对比")
        chain.append("目标为清理名单而非 GMV，避免误判为待优化 Flow")
        return chain[:5]

    trigger = "Welcome" if "welcome" in name.lower() else (
        "Checkout/Cart 弃单" if any(k in name.lower() for k in ("checkout", "cart", "abandon")) else "生命周期触发"
    )
    chain.append(f"{trigger} 触发 → 序列内发送 {rec:,} 封（近 30 天）")

    if open_r >= avg_open * 1.1:
        chain.append(f"首封/序列打开表现佳 → 打开率 {fmt_pct(open_r)}（高于站点 Flow 均值 {fmt_pct(avg_open)}）")
    elif open_r < avg_open * 0.8:
        chain.append(f"打开率偏低 {fmt_pct(open_r)}（站点 Flow 均值 {fmt_pct(avg_open)}）→ 优先检查 Subject 或发送时机")
    else:
        chain.append(f"打开率 {fmt_pct(open_r)}，与站点 Flow 均值 {fmt_pct(avg_open)} 相当")

    if click >= 0.05:
        chain.append(f"序列内 CTA 有效 → 点击率 {fmt_pct(click, 2)}，用户持续参与漏斗")
    else:
        chain.append(f"点击 {fmt_pct(click, 2)} → {'offer/商品推荐待加强' if verdict == 'avoid' else '点击处于正常区间'}")

    if conv >= avg_conv * 1.2 and conv > 0:
        chain.append(f"强转化闭环 → 转化率 {fmt_pct(conv, 2)}（显著高于站点 Flow 均值 {fmt_pct(avg_conv, 2)}）")
    elif conv > 0:
        chain.append(f"转化 {fmt_pct(conv, 2)} → Placed Order 归因至本序列")
    else:
        chain.append("转化断裂 → 近 30 天无 Placed Order，需检查 offer 或序列长度")

    if gmv > 0:
        chain.append(f"GMV 结果 {fmt_gmv(gmv, ccy)}（{'建议跨站复制序列结构' if verdict == 'copy' else 'GMV 贡献不足'}）")
    elif verdict == "avoid":
        chain.append("GMV 为 0 → 评估降频、合并步骤或下线")
    return chain[:5]


def _campaign_action(why_item: dict, verdict: str) -> str:
    reasons = why_item.get("reasons") or []
    audience = why_item.get("audience") or ""
    if verdict == "copy":
        if any("ALL" in a.upper() for a in audience.split(", ")):
            return "复制宽网 + 促销钩子组合；下一波活动沿用相似 Subject 结构与 ALL/Active 分层"
        if reasons:
            return f"复制成功要素：{reasons[0]}；下一场 Campaign 对齐受众与 Subject 模式"
        return "将此 Campaign 的 Subject、受众分层与 offer 结构作为下一波模板"
    if any("打开" in r for r in reasons):
        return "避免同类 Subject/宽网组合；先 A/B Subject 或收窄至 Active 分层再发送"
    if any("点击" in r for r in reasons):
        return "避免纯内容向主题无促销钩子；测试更强 CTA 或限时 offer"
    return "暂停类似主题 Campaign；用已验证的高 GMV 模板替换"


def _flow_action(why_item: dict, verdict: str) -> str:
    name = why_item.get("name") or ""
    reasons = why_item.get("reasons") or []
    if is_sunset(name):
        return "保持 Sunset 序列运行；仅监控 list 健康，不与交易型 Flow 比打开率"
    if verdict == "copy":
        if "checkout" in name.lower() or "cart" in name.lower() or "abandon" in name.lower():
            return "将此 Checkout/Cart 序列结构复制至其他站点；校准本地币种 offer 与 send time"
        if "welcome" in name.lower():
            return "复制 Welcome 首封 Subject 与步骤间隔；其他站点对齐序列长度"
        return f"复制序列逻辑：{reasons[0] if reasons else '保持当前 Live 配置'}"
    if any("Draft" in r for r in reasons):
        return "确认 Draft 版本：合并至 Live、或彻底下线，避免双版本并行发送"
    if any("无 GMV" in r for r in reasons):
        return "评估降频或合并步骤；若 60 天仍无 GMV 考虑下线"
    if "welcome" in name.lower():
        return "A/B 首封 Subject 或调整发送顺序；对比同站 Checkout Flow 转化"
    return "检查 offer/CTA 与同类型优秀 Flow 逐步对比，优先修复转化最弱步骤"


def build_playbook_item(
    why_item: dict,
    item_type: str,
    verdict: str,
    ccy: str,
    site_avg: dict,
) -> dict:
    m = why_item.get("metrics") or {}
    logic_fn = _campaign_logic_chain if item_type == "campaign" else _flow_logic_chain
    action_fn = _campaign_action if item_type == "campaign" else _flow_action
    return {
        "name": why_item.get("name", ""),
        "type": item_type,
        "verdict": verdict,
        "subject": why_item.get("subject"),
        "audience": why_item.get("audience"),
        "dataSource": "Klaviyo 近30天 Placed Order",
        "metrics": {
            "recipients": int(m.get("recipients") or 0),
            "openRate": m.get("openRate") or 0,
            "clickRate": m.get("clickRate") or 0,
            "convRate": m.get("convRate") or 0,
            "gmv": m.get("gmv") or 0,
            "gmvLabel": fmt_gmv(m.get("gmv") or 0, ccy),
        },
        "logicChain": logic_fn(why_item, m, site_avg, verdict, ccy),
        "action": action_fn(why_item, verdict),
        "benchmark": _build_benchmark(m, site_avg, item_type, verdict, ccy),
    }


def build_site_playbook(
    region: str,
    site_why: dict,
    seed_block: dict | None,
    *,
    ccy: str = "USD",
    camp_avg: dict | None = None,
    flow_avg: dict | None = None,
) -> dict:
    seed_block = seed_block or {}
    camp_avg = camp_avg or {}
    flow_avg = flow_avg or {}

    def items(why_items: list[dict], item_type: str, verdict: str, site_avg: dict, limit: int = 4) -> list[dict]:
        if not why_items:
            return []
        return [
            build_playbook_item(item, item_type, verdict, ccy, site_avg)
            for item in why_items[:limit]
        ]

    return {
        "region": region,
        "summary": seed_block.get("pattern") or seed_block.get("summary") or site_why.get("summary", ""),
        "successCampaign": items(site_why.get("campaignBest", []), "campaign", "copy", camp_avg),
        "avoidCampaign": items(site_why.get("campaignWorst", []), "campaign", "avoid", camp_avg),
        "successFlow": items(site_why.get("flowBest", []), "flow", "copy", flow_avg),
        "avoidFlow": items(site_why.get("flowWorst", []), "flow", "avoid", flow_avg),
    }
