const DEFAULT_OWNER = "17793689850qjq-cyber";
const DEFAULT_REPO = "bluetti-edm-dashboard";
const WORKFLOW_FILE = "sync-dashboard.yml";
const DEFAULT_REF = "main";

function json(statusCode, body) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
    body: JSON.stringify(body),
  };
}

function parseDates(event) {
  const q = event.queryStringParameters || {};
  const start = q.start || q.start_date;
  const end = q.end || q.end_date;
  if (start && end) return { start, end };

  if (event.body) {
    try {
      const body = JSON.parse(event.body);
      if (body.start && body.end) return { start: body.start, end: body.end };
    } catch (_) {
      /* ignore */
    }
  }
  return { start: null, end: null };
}

function isValidDate(s) {
  return typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s);
}

exports.handler = async (event) => {
  if (event.httpMethod !== "GET" && event.httpMethod !== "POST") {
    return json(405, { error: "Method not allowed", triggered: false });
  }

  const { start, end } = parseDates(event);
  if (!isValidDate(start) || !isValidDate(end)) {
    return json(400, {
      error: "需要 start 与 end 参数，格式 YYYY-MM-DD",
      triggered: false,
    });
  }
  if (start > end) {
    return json(400, { error: "开始日期不能晚于结束日期", triggered: false });
  }

  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    return json(503, {
      error: "GITHUB_PAT 未配置。请在 Netlify 站点环境变量中添加 Personal Access Token（需 repo + workflow 权限）。",
      triggered: false,
    });
  }

  const owner = process.env.GITHUB_REPO_OWNER || DEFAULT_OWNER;
  const repo = process.env.GITHUB_REPO_NAME || DEFAULT_REPO;
  const ref = process.env.GITHUB_REF || DEFAULT_REF;
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${pat}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "bluetti-edm-dashboard-trigger-sync",
    },
    body: JSON.stringify({
      ref,
      inputs: { start_date: start, end_date: end },
    }),
  });

  if (!res.ok) {
    const detail = await res.text();
    return json(res.status, {
      error: `GitHub workflow_dispatch 失败 (${res.status})`,
      detail: detail.slice(0, 500),
      triggered: false,
    });
  }

  return json(200, { triggered: true, start, end, ref });
};
