# BLUETTI EDM Flow & Campaign Data

静态网页 + JSON 数据，覆盖 11 个 Klaviyo 站点：US、AU、CA、UK、FR、DE、IT、EU、ES、JP、CL。

**在线看板**：<https://17793689850qjq-cyber.github.io/bluetti-edm-flow-campaign-data/>

## 架构

```
Klaviyo REST API  →  scripts/sync_dashboard.py  →  dashboard/data/dashboard.json
                                                          ↓
                                              dashboard/index.html (GitHub Pages)
```

- **每日同步**：`.github/workflows/sync-dashboard.yml`（UTC 06:00，约北京时间 14:00）
- **页面部署**：`.github/workflows/deploy-pages.yml`（`dashboard/` 目录变更时自动发布）

## 本地预览（无需 API Key）

```bash
cd scripts
python build_seed_dashboard.py

cd ../dashboard
python -m http.server 8080
# 打开 http://localhost:8080
```

## 配置 GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions** 添加各站 Private API Key：

| Secret 名称 | 站点 |
|-------------|------|
| `KLAVIYO_API_KEY_US` | 美国 |
| `KLAVIYO_API_KEY_AU` | 澳大利亚 |
| `KLAVIYO_API_KEY_CA` | 加拿大 |
| `KLAVIYO_API_KEY_UK` | 英国 |
| `KLAVIYO_API_KEY_FR` | 法国 |
| `KLAVIYO_API_KEY_DE` | 德国 |
| `KLAVIYO_API_KEY_IT` | 意大利 |
| `KLAVIYO_API_KEY_EU` | 泛欧账号 |
| `KLAVIYO_API_KEY_ES` | 西班牙 |
| `KLAVIYO_API_KEY_JP` | 日本 |
| `KLAVIYO_API_KEY_CL` | 智利 |

API Key 需具备 **Reporting** 读取权限。未配置的站点会在同步时跳过，并在 `dashboard.json` 的 `meta.errors` 中记录。

## 启用 GitHub Pages

1. 仓库 **Settings → Pages**
2. **Build and deployment** → Source 选 **GitHub Actions**
3. 首次 push `dashboard/` 后，`Deploy Dashboard to GitHub Pages` workflow 会自动运行

## 手动同步

Actions 页选择 **Sync Klaviyo Dashboard** → **Run workflow**。

## 数据口径

- 统计周期：近 30 天（`last_30_days`）
- 转化 Metric：Placed Order
- GMV：各站本位币，汇总按固定汇率折算 CNY
- Campaign：已发送邮件
- Flow：Live / Draft，周期内有发送量

## 看板视图

1. **全球总览** — KPI、GMV 饼图/柱状图、各站对比表
2. **分站诊断** — 按站点折叠，Campaign / Flow 最佳与待优化（含 Subject 解读）
3. **Flow 待关注** — Draft、Sunset 等待处理项
4. **Playbook** — 成功/失败模式清单
