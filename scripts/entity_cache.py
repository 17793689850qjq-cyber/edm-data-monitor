"""Resolve Klaviyo campaign/flow/list names from IDs (report rows only include groupings)."""

from __future__ import annotations

import time
import urllib.request


class EntityCache:
    def __init__(self, client: "KlaviyoClient"):
        self.client = client
        self.campaigns: dict[str, dict] = {}
        self.flows: dict[str, dict] = {}
        self.audiences: dict[str, str] = {}

    def campaign_info(self, campaign_id: str) -> dict:
        if campaign_id in self.campaigns:
            return self.campaigns[campaign_id]
        info = {"name": campaign_id, "subject": "", "status": "Sent", "audiences": []}
        try:
            payload = self.client._request("GET", f"/campaigns/{campaign_id}")
            attrs = payload.get("data", {}).get("attributes") or {}
            info["name"] = attrs.get("name") or campaign_id
            info["status"] = attrs.get("status") or "Sent"
            aud = attrs.get("audiences") or {}
            included = aud.get("included") or []
            info["audiences"] = [self.audience_name(aid) for aid in included[:4]]
            time.sleep(0.15)
            msgs = self.client._request("GET", f"/campaigns/{campaign_id}/campaign-messages/")
            for msg in msgs.get("data") or []:
                content = (msg.get("attributes") or {}).get("content") or {}
                if content.get("subject"):
                    info["subject"] = content["subject"]
                    break
        except RuntimeError:
            pass
        self.campaigns[campaign_id] = info
        return info

    def flow_info(self, flow_id: str) -> dict:
        if flow_id in self.flows:
            return self.flows[flow_id]
        info = {"name": flow_id, "status": "live"}
        try:
            payload = self.client._request("GET", f"/flows/{flow_id}")
            attrs = payload.get("data", {}).get("attributes") or {}
            info["name"] = attrs.get("name") or flow_id
            info["status"] = attrs.get("status") or "live"
        except RuntimeError:
            pass
        self.flows[flow_id] = info
        return info

    def audience_name(self, audience_id: str) -> str:
        if audience_id in self.audiences:
            return self.audiences[audience_id]
        for path in (f"/lists/{audience_id}", f"/segments/{audience_id}"):
            try:
                payload = self.client._request("GET", path)
                name = (payload.get("data", {}).get("attributes") or {}).get("name")
                if name:
                    self.audiences[audience_id] = name
                    return name
            except RuntimeError:
                continue
        self.audiences[audience_id] = audience_id
        return audience_id
