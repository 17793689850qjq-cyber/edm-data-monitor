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
    return alerts


def build_site_playbook(region: str, site_why: dict, seed_block: dict | None) -> dict:
    seed_block = seed_block or {}
    def bullets(items: list[dict], limit: int = 4) -> list[str]:
        out: list[str] = []
        for item in items[:limit]:
            reasons = item.get("reasons") or []
            hint = reasons[0] if reasons else item.get("name", "")
            subj = item.get("subject") or ""
            if subj and subj not in ("—", item.get("name", "")):
                out.append(f"{item['name']} · {subj[:60]} · {hint}")
            else:
                out.append(f"{item['name']} · {hint}")
        return out or ["暂无足够数据"]

    return {
        "region": region,
        "summary": seed_block.get("pattern") or seed_block.get("summary") or site_why.get("summary", ""),
        "successCampaign": bullets(site_why.get("campaignBest", [])),
        "avoidCampaign": bullets(site_why.get("campaignWorst", [])),
        "successFlow": bullets(site_why.get("flowBest", [])),
        "avoidFlow": bullets(site_why.get("flowWorst", [])),
    }
