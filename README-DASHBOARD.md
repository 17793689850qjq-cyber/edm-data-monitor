# BLUETTI EDM Flow & Campaign Data

静态网页 + JSON 数据，覆盖 11 个 Klaviyo 站点：US、AU、CA、UK、FR、DE、IT、EU、ES、JP、CL。

**在线看板**：<https://17793689850qjq-cyber.github.io/bluetti-edm-flow-campaign-data/>

## 架构

```
Klaviyo REST API  →  scripts/sync_dashboard.py  →  dashboard/data/dashboard-{7,30,60,90}d.json
                                                          ↓
                                              dashboard/index.html (GitHub Pages)
```

- **每日同步**：`.github/workflows/sync-dashboard.yml` 依次生成 7/30/60/90 天四套 JSON（`dashboard.json` 与 `dashboard-30d.json` 内容相同，默认 30 天）
- **页面部署**：`.github/workflows/deploy-pages.yml`（`dashboard/` 目录变更时自动发布）
- **页头区间选择**：预设切换加载对应 JSON；自定义范围需先通过 Actions 同步

## 本地预览（无需 API Key）

```bash
cd scripts
python build_seed_dashboard.py --all-presets

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

API Key 需具备 **Reporting** 读取权限。未配置的站点会在同步时跳过，并在 JSON 的 `meta.errors` 中记录。

## 启用 GitHub Pages

1. 仓库 **Settings → Pages**
2. **Build and deployment** → Source 选 **GitHub Actions**
3. 首次 push `dashboard/` 后，`Deploy Dashboard to GitHub Pages` workflow 会自动运行

## 手动同步

Actions 页选择 **Sync Klaviyo Dashboard** → **Run workflow**：

- 默认：同步 7/30/60/90 天四套数据
- 可选 `days`：仅同步单个预设
- 可选 `start_date` + `end_date`：自定义区间，输出 `dashboard-custom-YYYY-MM-DD_YYYY-MM-DD.json`

本地：

```bash
cd scripts
python sync_dashboard.py --days 30
python sync_dashboard.py --start 2025-05-01 --end 2025-05-31
```

## 数据口径

- 统计周期：页头可选近 7/30/60/90 天或自定义（需预同步 JSON）
- 转化 Metric：Placed Order
- GMV：各站本位币，汇总按固定汇率折算 CNY
- Campaign：已发送邮件
- Flow：Live / Draft，周期内有发送量

## 看板视图

1. **全球总览** — KPI、GMV 饼图/柱状图、各站对比表
2. **分站诊断** — 按站点折叠，Campaign / Flow 最佳与待优化（含 Subject 解读）
3. **Flow 待关注** — Draft、Sunset 等待处理项
4. **Playbook** — 成功/失败模式清单

## 自定义区间限制（静态站点）

GitHub Pages 无法按需调用 Klaviyo API。自定义日期需先在 Actions 或本地运行 `sync_dashboard.py --start … --end …` 生成对应 JSON 后，看板才能加载该区间数据。
