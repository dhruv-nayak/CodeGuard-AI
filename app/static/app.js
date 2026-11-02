const API_BASE = "/api/v1";
let currentUser = null;

function authHeaders() {
  const token = sessionStorage.getItem("codeguard_access_token");
  return token ? { "Authorization": `Bearer ${token}` } : {};
}
function showAuthMessage(message) {
  document.getElementById("authMessage").textContent = message;
}
function setAuthenticated(data) {
  sessionStorage.setItem("codeguard_access_token", data.access_token);
  currentUser = data.user;
  document.getElementById("authState").textContent = `${data.user.full_name || data.user.email} · ${data.user.role}`;
  document.getElementById("loginBtn").hidden = true;
  document.getElementById("registerBtn").hidden = true;
  document.getElementById("logoutBtn").hidden = false;
  document.getElementById("historyBtn").hidden = false;
  showAuthMessage("Signed in. Reviews will be saved to your account.");
  loadHistory();
  loadAnalytics();
  loadSecurityIntelligence();
  loadRepositories();
  loadAdminWorkspace();
}
async function authRequest(path, payload) {
  const response = await fetch(`${API_BASE}/auth/${path}`, {
    method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Authentication failed.");
  return data;
}
async function login() {
  try {
    const data = await authRequest("login", {
      email: document.getElementById("authEmail").value.trim(),
      password: document.getElementById("authPassword").value
    });
    setAuthenticated(data);
  } catch (error) { showAuthMessage(error.message); }
}
async function register() {
  try {
    const data = await authRequest("register", {
      email: document.getElementById("authEmail").value.trim(),
      full_name: document.getElementById("authName").value.trim(),
      password: document.getElementById("authPassword").value
    });
    setAuthenticated(data);
  } catch (error) { showAuthMessage(error.message); }
}
async function logout() {
  const token = sessionStorage.getItem("codeguard_access_token");
  if (token) {
    try { await fetch(`${API_BASE}/auth/logout`, {method: "POST", headers: authHeaders()}); }
    catch (_) { /* Local sign-out must still work if the API is offline. */ }
  }
  sessionStorage.removeItem("codeguard_access_token");
  currentUser = null;
  document.getElementById("authState").textContent = "Sign in to save review history";
  document.getElementById("loginBtn").hidden = false;
  document.getElementById("registerBtn").hidden = false;
  document.getElementById("logoutBtn").hidden = true;
  document.getElementById("historyBtn").hidden = true;
  document.getElementById("historyList").replaceChildren();
  document.getElementById("adminPanel").hidden = true;
  document.getElementById("ghPublishPanel").hidden = true;
  window.lastGitHubReviewId = null;
  showAuthMessage("You have signed out.");
}
async function loadHistory() {
  if (!sessionStorage.getItem("codeguard_access_token")) return;
  const response = await fetch(`${API_BASE}/reviews/history`, {headers: authHeaders()});
  if (response.status === 401) { logout(); showAuthMessage("Session expired. Please sign in again."); return; }
  const rows = await response.json();
  const list = document.getElementById("historyList");
  list.replaceChildren();
  if (!rows.length) { list.textContent = "No reviews saved yet."; return; }
  rows.forEach(row => {
    const item = document.createElement("div"); item.className = "history-item";
    const detail = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = row.repository ? `${row.repository} · ${row.filename}` : row.filename;
    const summary = document.createElement("p"); summary.textContent = `${row.review_type} · ${row.score == null ? "Score n/a" : `Score ${row.score}/100`} · ${new Date(row.created_at).toLocaleString()}`;
    detail.append(title, summary);
    const view = document.createElement("button"); view.className = "secondary-btn"; view.textContent = "View review";
    view.onclick = () => viewHistoryItem(row.review_id);
    item.append(detail, view);
    if (row.review_type === "code") {
      const tests = document.createElement("button"); tests.className = "secondary-btn";
      tests.textContent = "Download tests"; tests.onclick = () => downloadTests(row.review_id);
      item.append(tests);
    }
    list.append(item);
  });
}

async function addRepository() {
  const payload = {
    owner: document.getElementById("repoOwner").value.trim(),
    name: document.getElementById("repoName").value.trim(),
    default_branch: document.getElementById("repoBranch").value.trim() || "main"
  };
  if (!payload.owner || !payload.name) { showAuthMessage("Enter a GitHub owner and repository name."); return; }
  const response = await fetch(`${API_BASE}/repositories`, {
    method: "POST",
    headers: {"Content-Type":"application/json", ...authHeaders()},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) { showAuthMessage(data.detail || "Could not add repository."); return; }
  document.getElementById("repoOwner").value = "";
  document.getElementById("repoName").value = "";
  showAuthMessage("Repository added to your personal list. No access token is stored.");
  loadRepositories();
}
async function loadRepositories() {
  if (!sessionStorage.getItem("codeguard_access_token")) return;
  const response = await fetch(`${API_BASE}/repositories`, {headers: authHeaders()});
  if (!response.ok) return;
  const rows = await response.json();
  const list = document.getElementById("repositoryList"); list.replaceChildren();
  if (!rows.length) { list.textContent = "No repositories registered."; }
  rows.forEach(repo => {
    const item = document.createElement("div"); item.className = "history-item";
    const detail = document.createElement("div");
    const link = document.createElement("a"); link.href = repo.url; link.target = "_blank"; link.rel = "noopener noreferrer";
    link.textContent = `${repo.owner}/${repo.name}`;
    const branch = document.createElement("p"); branch.textContent = `ID: ${repo.id} · Default branch: ${repo.default_branch}`;
    detail.append(link, branch);
    const remove = document.createElement("button"); remove.className = "secondary-btn"; remove.textContent = "Remove";
    remove.onclick = async () => {
      const deleted = await fetch(`${API_BASE}/repositories/${repo.id}`, {method:"DELETE", headers:authHeaders()});
      if (deleted.ok) loadRepositories();
    };
    item.append(detail, remove); list.append(item);
  });
  const sharedResponse = await fetch(`${API_BASE}/repositories/shared`, {headers:authHeaders()});
  const sharedList = document.getElementById("sharedRepositoryList"); sharedList.replaceChildren();
  if (sharedResponse.ok) {
    const shared = await sharedResponse.json();
    if (!shared.length) sharedList.textContent = "No team repositories shared with you.";
    shared.forEach(repo => {
      const item = document.createElement("div"); item.className = "history-item";
      const link = document.createElement("a"); link.href = repo.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = `${repo.owner}/${repo.name} · ${repo.default_branch}`;
      item.append(link); sharedList.append(item);
    });
  }
}
async function downloadTests(reviewId) {
  const response = await fetch(`${API_BASE}/reviews/history/${encodeURIComponent(reviewId)}/tests`, {headers:authHeaders()});
  if (!response.ok) { showAuthMessage("No generated test file is available for this review."); return; }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url;
  anchor.download = `codeguard_${reviewId.slice(0,8)}_tests.py`;
  document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
}

async function viewHistoryItem(reviewId) {
  const response = await fetch(`${API_BASE}/reviews/history/${encodeURIComponent(reviewId)}`, {headers: authHeaders()});
  const data = await response.json();
  if (!response.ok) { showAuthMessage(data.detail || "Could not load review."); return; }
  const summary = data.summary || data.ai_summary || "Review details loaded.";
  showAuthMessage(`${summary} · Review ID: ${reviewId}`);
  if (data.findings) {
    document.getElementById("empty").hidden = true;
    document.getElementById("results").hidden = false;
    document.getElementById("summary").textContent = summary;
    document.getElementById("score").innerHTML = `${data.score ?? "—"}<small>/100</small>`;
    document.getElementById("findingCount").textContent = data.findings.length;
    const findings = document.getElementById("findings"); findings.replaceChildren();
    data.findings.forEach(f => {
      const card = document.createElement("div"); card.className = "finding";
      const title = document.createElement("div"); title.className = "finding-title";
      const sev = document.createElement("span"); sev.className = `severity ${f.severity}`; sev.textContent = f.severity;
      title.append(sev, document.createTextNode(f.title));
      const msg = document.createElement("p"); msg.textContent = `${f.message}${f.line ? ` (line ${f.line})` : ""}`;
      const rec = document.createElement("p"); rec.textContent = `Recommendation: ${f.recommendation}`;
      card.append(title, msg, rec); findings.append(card);
    });
  }
}

async function runReview() {
  if (!sessionStorage.getItem("codeguard_access_token")) { showAuthMessage("Please sign in before starting a review."); return; }
  const button = document.getElementById("reviewBtn");
  const code = document.getElementById("code").value;
  const filename = document.getElementById("filename").value || "submitted.py";
  const status = document.getElementById("status");
  button.disabled = true;
  button.textContent = "Reviewing…";
  status.textContent = "Analysing";
  try {
    const response = await fetch("/api/v1/reviews", {
      method: "POST",
      headers: {"Content-Type": "application/json", ...authHeaders()},
      body: JSON.stringify({filename, language: document.getElementById("language").value, code, ai_provider: document.getElementById("provider").value})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Review failed");
    document.getElementById("empty").hidden = true;
    document.getElementById("results").hidden = false;
    document.getElementById("score").innerHTML = `${data.score}<small>/100</small>`;
    document.getElementById("aiState").textContent = data.ai_reviewed ? `AI: ${data.ai_provider}` : "Static analysis only";
    const aiDetails = document.getElementById("aiDetails");
    aiDetails.hidden = !data.ai_review;
    if (data.ai_review) {
      const aiFindings = document.getElementById("aiFindings");
      aiFindings.replaceChildren();
      (data.ai_review.findings || []).forEach(item => {
        const card = document.createElement("div"); card.className = "finding";
        const title = document.createElement("div"); title.className = "finding-title";
        const sev = document.createElement("span"); sev.className = `severity ${item.severity}`; sev.textContent = item.severity;
        title.append(sev, document.createTextNode(item.title));
        const explanation = document.createElement("p"); explanation.textContent = item.explanation;
        const recommendation = document.createElement("p"); recommendation.textContent = `Recommendation: ${item.recommendation}`;
        card.append(title, explanation, recommendation); aiFindings.append(card);
      });
      document.getElementById("improvedCode").textContent = data.ai_review.improved_code || "No code rewrite suggested.";
      document.getElementById("generatedTests").textContent = data.ai_review.generated_tests || "No complete test module generated.";
    }
    document.getElementById("summary").textContent = data.summary;
    document.getElementById("findingCount").textContent = data.findings.length;
    const findings = document.getElementById("findings");
    findings.replaceChildren();
    data.findings.forEach(item => {
      const card = document.createElement("div");
      card.className = "finding";
      const title = document.createElement("div");
      title.className = "finding-title";
      const sev = document.createElement("span");
      sev.className = `severity ${item.severity}`;
      sev.textContent = item.severity;
      title.append(sev, document.createTextNode(item.title));
      const message = document.createElement("p");
      message.textContent = `${item.message}${item.line ? ` (line ${item.line})` : ""}`;
      const recommendation = document.createElement("p");
      recommendation.textContent = `Recommendation: ${item.recommendation}`;
      card.append(title, message, recommendation);
      findings.append(card);
    });
    if (!data.findings.length) {
      const p = document.createElement("p"); p.className = "summary"; p.textContent = "No configured static-analysis findings were detected.";
      findings.append(p);
    }
    fillList("tests", data.suggested_tests);
    fillList("limits", data.limitations);
    status.textContent = "Review complete";
    loadHistory();
  } catch (error) {
    status.textContent = "Review failed";
    alert(error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Review code <span>→</span>';
  }
}
function fillList(id, items) {
  const list = document.getElementById(id); list.replaceChildren();
  items.forEach(value => { const li = document.createElement("li"); li.textContent = value; list.append(li); });
}


async function reviewPullRequest() {
  if (!sessionStorage.getItem("codeguard_access_token")) { showAuthMessage("Please sign in before reviewing a pull request."); return; }
  const button = document.getElementById("ghReviewBtn");
  const status = document.getElementById("ghStatus");
  const results = document.getElementById("ghResults");
  const payload = {
    owner: document.getElementById("ghOwner").value.trim(),
    repo: document.getElementById("ghRepo").value.trim(),
    pull_number: Number(document.getElementById("ghPr").value),
    github_token: document.getElementById("ghToken").value || null,
    installation_id: Number(document.getElementById("ghInstallation").value) || null,
    ai_provider: document.getElementById("ghProvider").value
  };
  if (!payload.owner || !payload.repo || !payload.pull_number || (!payload.github_token && !payload.installation_id)) {
    status.textContent = "Enter repository owner, repository, pull request number, and either a token or installation ID.";
    return;
  }
  button.disabled = true;
  status.textContent = "Fetching pull request and reviewing Python files…";
  results.hidden = true;
  results.replaceChildren();
  try {
    const response = await fetch("/api/v1/github/pull-requests/review", {
      method: "POST",
      headers: {"Content-Type": "application/json", ...authHeaders()},
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "GitHub review failed");
    status.textContent = `Reviewed ${data.files_reviewed} Python file(s); skipped ${data.files_skipped}.`;
    window.lastGitHubReviewId = data.review_id;
    document.getElementById("ghPublishPanel").hidden = !data.review_id;
    document.getElementById("ghCommentDraft").replaceChildren();
    document.getElementById("ghPublishConfirm").value = "";
    loadHistory();
    const heading = document.createElement("h3");
    heading.textContent = `${data.repository} · PR #${data.pull_number}: ${data.pull_title}`;
    results.append(heading);
    const link = document.createElement("a");
    link.href = data.pull_url; link.target = "_blank"; link.rel = "noopener noreferrer";
    link.textContent = "Open pull request ↗"; results.append(link);
    const meta = document.createElement("p");
    meta.className = "summary";
    meta.textContent = `${data.findings_count} static finding(s) · Head ${data.head_sha.slice(0, 8)} · AI: ${data.ai_provider || "not available"}`;
    results.append(meta);
    if (data.ai_summary) {
      const ai = document.createElement("p"); ai.className = "summary"; ai.textContent = data.ai_summary; results.append(ai);
    }
    data.file_results.forEach(file => {
      const section = document.createElement("section"); section.className = "finding";
      const title = document.createElement("div"); title.className = "finding-title";
      title.textContent = `${file.filename} · +${file.additions} / -${file.deletions}`;
      section.append(title);
      if (!file.findings.length) {
        const p = document.createElement("p"); p.textContent = "No configured static findings on changed lines."; section.append(p);
      }
      file.findings.forEach(f => {
        const p = document.createElement("p");
        p.textContent = `${f.severity.toUpperCase()} · ${f.title}${f.line ? ` (line ${f.line})` : ""}: ${f.recommendation}`;
        section.append(p);
      });
      results.append(section);
    });
    const limits = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = "Review limitations";
    const list = document.createElement("ul");
    data.limitations.forEach(item => { const li = document.createElement("li"); li.textContent = item; list.append(li); });
    limits.append(summary, list); results.append(limits);
    results.hidden = false;
    // Clear token from the password input after the request completes.
    document.getElementById("ghToken").value = "";
    document.getElementById("ghInstallation").value = "";
  } catch (error) {
    status.textContent = error.message;
    document.getElementById("ghToken").value = "";
    document.getElementById("ghInstallation").value = "";
  } finally {
    button.disabled = false;
  }
}


async function previewGitHubComments() {
  const reviewId = window.lastGitHubReviewId;
  if (!reviewId) return;
  const response = await fetch(`/api/v1/github/reviews/${encodeURIComponent(reviewId)}/comment-draft`, {headers:authHeaders()});
  const data = await response.json();
  if (!response.ok) { document.getElementById("ghStatus").textContent = data.detail || "Could not build comment drafts."; return; }
  const container = document.getElementById("ghCommentDraft"); container.replaceChildren();
  if (!data.comments.length) { container.textContent = "No line-specific comments can be drafted for this review."; return; }
  data.comments.forEach((comment, index) => {
    const card = document.createElement("div"); card.className = "comment-draft";
    const title = document.createElement("strong"); title.textContent = `${index+1}. ${comment.path} · line ${comment.line}`;
    const body = document.createElement("p"); body.textContent = comment.body;
    card.append(title, body); container.append(card);
  });
  document.getElementById("ghStatus").textContent = `${data.comment_count} comment draft(s). Check them before publishing.`;
}
async function publishGitHubComments() {
  const reviewId = window.lastGitHubReviewId;
  const confirmation = document.getElementById("ghPublishConfirm").value;
  if (!reviewId) return;
  if (confirmation !== "PUBLISH_COMMENTS") {
    document.getElementById("ghStatus").textContent = "Type PUBLISH_COMMENTS exactly to confirm.";
    return;
  }
  const githubToken = document.getElementById("ghToken").value || null;
  const installationId = Number(document.getElementById("ghInstallation").value) || null;
  if (!githubToken && !installationId) {
    document.getElementById("ghStatus").textContent = "Enter a GitHub token or installation ID before publishing.";
    return;
  }
  const button = document.getElementById("ghPublishBtn"); button.disabled = true;
  try {
    const response = await fetch(`/api/v1/github/reviews/${encodeURIComponent(reviewId)}/publish-comments`, {
      method:"POST", headers:{"Content-Type":"application/json", ...authHeaders()},
      body:JSON.stringify({github_token:githubToken, installation_id:installationId, confirmation})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Comment publishing failed.");
    document.getElementById("ghStatus").textContent = `${data.comment_count} GitHub comment(s) published as COMMENT. ${data.message}`;
    document.getElementById("ghPublishPanel").hidden = true;
    document.getElementById("ghToken").value = "";
    document.getElementById("ghInstallation").value = "";
    document.getElementById("ghPublishConfirm").value = "";
  } catch (error) {
    document.getElementById("ghStatus").textContent = error.message;
  } finally { button.disabled = false; }
}
async function loadAdminWorkspace() {
  if (!currentUser || currentUser.role !== "admin") return;
  const panel = document.getElementById("adminPanel"); panel.hidden = false;
  const [usersResponse, teamsResponse, auditResponse] = await Promise.all([
    fetch(`${API_BASE}/admin/users`, {headers:authHeaders()}),
    fetch(`${API_BASE}/admin/teams`, {headers:authHeaders()}),
    fetch(`${API_BASE}/admin/audit-logs?limit=25`, {headers:authHeaders()})
  ]);
  if (usersResponse.ok) {
    const users = await usersResponse.json(); const target = document.getElementById("adminUsers"); target.replaceChildren();
    const heading = document.createElement("h3"); heading.textContent = `Users (${users.length})`; target.append(heading);
    users.forEach(user => {
      const row = document.createElement("div"); row.className = "admin-row";
      const info = document.createElement("span"); info.textContent = `${user.full_name || user.email} · ${user.email} · ${user.role}`;
      const action = document.createElement("button"); action.className = "secondary-btn";
      action.textContent = user.role === "admin" ? "Make developer" : "Make admin";
      action.onclick = () => updateUserRole(user.id, user.role === "admin" ? "developer" : "admin");
      row.append(info, action); target.append(row);
    });
  }
  if (teamsResponse.ok) {
    const teams = await teamsResponse.json(); const target = document.getElementById("adminTeams"); target.replaceChildren();
    const heading = document.createElement("h3"); heading.textContent = `Your teams (${teams.length})`; target.append(heading);
    teams.forEach(team => {
      const row = document.createElement("div"); row.className = "admin-row";
      row.textContent = `#${team.id} ${team.name} · ${team.members.length} member(s) · ${team.repositories.length} shared repo(s)`;
      target.append(row);
    });
  }
  if (auditResponse.ok) {
    const logs = await auditResponse.json(); const target = document.getElementById("adminAudit"); target.replaceChildren();
    const heading = document.createElement("h3"); heading.textContent = "Recent audit activity"; target.append(heading);
    logs.forEach(log => {
      const row = document.createElement("div"); row.className = "admin-row";
      row.textContent = `${new Date(log.created_at).toLocaleString()} · user ${log.user_id ?? "system"} · ${log.action}`;
      target.append(row);
    });
  }
}
async function createTeam() {
  const payload = {name:document.getElementById("newTeamName").value.trim(), description:document.getElementById("newTeamDescription").value.trim()};
  const response = await fetch(`${API_BASE}/admin/teams`, {method:"POST", headers:{"Content-Type":"application/json", ...authHeaders()}, body:JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) { showAuthMessage(data.detail || "Could not create team."); return; }
  document.getElementById("newTeamName").value = "";
  document.getElementById("newTeamDescription").value = "";
  showAuthMessage(`Team ${data.name} created with ID ${data.id}.`);
  loadAdminWorkspace();
}
async function addTeamMember() {
  const teamId = Number(document.getElementById("teamIdInput").value);
  const email = document.getElementById("teamMemberEmail").value.trim();
  const response = await fetch(`${API_BASE}/admin/teams/${teamId}/members`, {method:"POST", headers:{"Content-Type":"application/json", ...authHeaders()}, body:JSON.stringify({email})});
  const data = await response.json();
  if (!response.ok) { showAuthMessage(data.detail || "Could not add member."); return; }
  showAuthMessage(`${email} added to ${data.name}.`);
  document.getElementById("teamMemberEmail").value = "";
  loadAdminWorkspace();
}
async function shareRepository() {
  const teamId = Number(document.getElementById("shareTeamId").value);
  const repositoryId = Number(document.getElementById("shareRepositoryId").value);
  const response = await fetch(`${API_BASE}/admin/teams/${teamId}/repositories`, {
    method:"POST", headers:{"Content-Type":"application/json", ...authHeaders()},
    body:JSON.stringify({repository_id:repositoryId})
  });
  const data = await response.json();
  if (!response.ok) { showAuthMessage(data.detail || "Could not share repository."); return; }
  showAuthMessage(`Repository ${repositoryId} shared with team ${teamId}.`);
  loadAdminWorkspace(); loadRepositories();
}
async function updateUserRole(userId, role) {
  const response = await fetch(`${API_BASE}/admin/users/${userId}/role?role=${encodeURIComponent(role)}`, {method:"PATCH", headers:authHeaders()});
  const data = await response.json();
  if (!response.ok) { showAuthMessage(data.detail || "Could not update role."); return; }
  showAuthMessage(`Updated ${data.email} to ${data.role}.`);
  loadAdminWorkspace();
}

document.addEventListener("DOMContentLoaded", async () => {
  const token = sessionStorage.getItem("codeguard_access_token");
  if (!token) return;
  try {
    const response = await fetch(`${API_BASE}/auth/me`, {headers: authHeaders()});
    if (!response.ok) { logout(); return; }
    const user = await response.json();
    currentUser = user;
    document.getElementById("authState").textContent = `${user.full_name || user.email} · ${user.role}`;
    document.getElementById("loginBtn").hidden = true;
    document.getElementById("registerBtn").hidden = true;
    document.getElementById("logoutBtn").hidden = false;
    document.getElementById("historyBtn").hidden = false;
    loadHistory();
    loadRepositories();
    loadAdminWorkspace();
  } catch (_) {
    showAuthMessage("Could not restore the previous session.");
  }
});


function updateFilenameHint() {
  const language = document.getElementById("language").value;
  const ext = {python:"py", javascript:"js", typescript:"ts", java:"java", php:"php", sql:"sql", html:"html"}[language];
  const field = document.getElementById("filename");
  if (!field.value || /\.(py|js|ts|java|php|sql|html)$/i.test(field.value)) field.value = `submitted.${ext}`;
}

async function loadAnalytics() {
  if (!sessionStorage.getItem("codeguard_access_token")) return;
  const summary = document.getElementById("analyticsSummary");
  const details = document.getElementById("analyticsDetails");
  try {
    const response = await fetch(`${API_BASE}/analytics/overview`, {headers: authHeaders()});
    if (!response.ok) return;
    const data = await response.json();
    summary.textContent = `${data.total_reviews} saved review(s) · Average score: ${data.average_score ?? "—"}/100`;
    details.replaceChildren();
    const cards = [
      ["Languages", Object.entries(data.language_distribution).map(([k,v])=>`${k}: ${v}`).join(" · ") || "No data"],
      ["Findings", Object.entries(data.severity_distribution).map(([k,v])=>`${k}: ${v}`).join(" · ")],
      ["Most frequent rules", (data.top_rules || []).slice(0,5).map(x=>`${x.rule_id} (${x.count})`).join(" · ") || "No findings yet"]
    ];
    cards.forEach(([heading, value]) => { const card=document.createElement("div"); card.className="analytics-card"; const h=document.createElement("strong"); h.textContent=heading; const p=document.createElement("p"); p.textContent=value; card.append(h,p); details.append(card); });
  } catch (_) { summary.textContent = "Analytics are temporarily unavailable."; }
}

async function scanRepository() {
  if (!sessionStorage.getItem("codeguard_access_token")) {
    showAuthMessage("Please sign in before scanning a repository."); return;
  }
  const owner = document.getElementById("scanOwner").value.trim();
  const repo = document.getElementById("scanRepo").value.trim();
  const github_token = document.getElementById("scanToken").value || null;
  const installationValue = document.getElementById("scanInstallation").value;
  const installation_id = installationValue ? Number(installationValue) : null;
  const status = document.getElementById("repoScanStatus");
  const results = document.getElementById("repoScanResults");
  if (!owner || !repo || (!github_token && !installation_id)) {
    status.textContent = "Enter an owner, repository, and GitHub token or App installation ID."; return;
  }
  const button = document.getElementById("scanRepoBtn"); button.disabled = true;
  status.textContent = "Fetching repository tree, source files and dependency manifests…";
  results.hidden = true; results.replaceChildren();
  try {
    const response = await fetch(`${API_BASE}/github/repositories/scan`, {
      method: "POST", headers: {"Content-Type":"application/json", ...authHeaders()},
      body: JSON.stringify({owner, repo, github_token, installation_id})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Repository scan failed.");
    status.textContent = `${data.repository}: scanned ${data.files_reviewed} source files; ${data.findings_count} code signals; ${data.dependency_count} pinned dependencies; ${data.vulnerable_dependency_count} OSV advisory match(es).`;
    const heading = document.createElement("h3"); heading.textContent = "Repository risk summary"; results.append(heading);
    const summary = document.createElement("p"); summary.className = "github-note";
    summary.textContent = data.summary || "Scan completed."; results.append(summary);
    const sbom = document.createElement("button"); sbom.className = "secondary-btn"; sbom.textContent = "Download CycloneDX SBOM";
    sbom.onclick = () => downloadSbom(data.review_id); results.append(sbom);
    const depHeading = document.createElement("h3"); depHeading.textContent = `Dependency advisories (${data.vulnerable_dependency_count})`; results.append(depHeading);
    if (data.dependency_vulnerabilities.length) {
      data.dependency_vulnerabilities.forEach(v => {
        const item = document.createElement("div"); item.className = "comment-draft";
        const title = document.createElement("strong"); title.textContent = `${v.id} · ${v.dependency}@${v.version}`;
        const detail = document.createElement("p"); detail.textContent = v.summary || "OSV advisory match";
        item.append(title, detail);
        (v.references || []).forEach(url => { const link = document.createElement("a"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "Advisory reference"; item.append(link); });
        results.append(item);
      });
    } else { const none = document.createElement("p"); none.textContent = data.osv_status; results.append(none); }
    const codeHeading = document.createElement("h3"); codeHeading.textContent = `Static code signals (${data.findings_count})`; results.append(codeHeading);
    (data.findings || []).slice(0, 30).forEach(f => {
      const item = document.createElement("div"); item.className = "comment-draft";
      const title = document.createElement("strong"); title.textContent = `${f.severity.toUpperCase()} · ${f.title}`;
      const detail = document.createElement("p"); detail.textContent = `${f.file}${f.line ? `:${f.line}` : ""} · ${f.message} Recommendation: ${f.recommendation}`;
      item.append(title, detail); results.append(item);
    });
    const limits = document.createElement("details"); const summaryEl = document.createElement("summary"); summaryEl.textContent = "Scan limitations";
    const list = document.createElement("ul"); (data.limitations || []).forEach(t => { const li=document.createElement("li"); li.textContent=t; list.append(li); });
    limits.append(summaryEl, list); results.append(limits); results.hidden = false;
    document.getElementById("scanToken").value = "";
    loadHistory();
  } catch (error) { status.textContent = error.message; }
  finally { button.disabled = false; }
}

async function downloadSbom(reviewId) {
  const response = await fetch(`${API_BASE}/reviews/history/${encodeURIComponent(reviewId)}/sbom`, {headers:authHeaders()});
  if (!response.ok) { showAuthMessage("Could not download this repository SBOM."); return; }
  const blob = await response.blob(); const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = "codeguard-sbom.cdx.json";
  document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
}


async function loadSecurityIntelligence() {
  if (!sessionStorage.getItem("codeguard_access_token")) return;
  const [dashboard, remediations, alerts, schedules] = await Promise.all([
    fetch(`${API_BASE}/security/dashboard`, {headers:authHeaders()}),
    fetch(`${API_BASE}/security/remediations`, {headers:authHeaders()}),
    fetch(`${API_BASE}/security/alerts`, {headers:authHeaders()}),
    fetch(`${API_BASE}/security/schedules`, {headers:authHeaders()})
  ]);
  if (!dashboard.ok) return;
  const data = await dashboard.json();
  document.getElementById("securitySummary").textContent = `${data.scans} repository scans across ${data.repositories} repositories · Risk score ${data.risk_score}/100 · ${data.scope}`;
  const metrics = document.getElementById("securityMetrics"); metrics.replaceChildren();
  [["Risk score",data.risk_score], ["Scans",data.scans], ["Repositories",data.repositories], ["Average quality",data.average_quality_score ?? "—"]].forEach(([label,value]) => {
    const card=document.createElement("div"); card.className="analytics-card";
    const strong=document.createElement("strong"); strong.textContent=value;
    const small=document.createElement("span"); small.textContent=label; card.append(strong,small); metrics.append(card);
  });
  const remList=document.getElementById("remediationList"); remList.replaceChildren();
  if (remediations.ok) {
    const items=await remediations.json();
    if (!items.length) remList.textContent="No repository findings are available yet.";
    items.slice(0,40).forEach(item=>{
      const card=document.createElement("div"); card.className="history-item";
      const info=document.createElement("div");
      const title=document.createElement("strong"); title.textContent=`${item.finding.severity || "info"} · ${item.finding.title || item.finding.rule_id || "Finding"}`;
      const detail=document.createElement("p"); detail.textContent=`${item.repository} · ${item.finding.file || ""} · ${item.finding.rule_id || ""}`;
      info.append(title,detail);
      const select=document.createElement("select");
      ["open","in_progress","resolved","accepted_risk","false_positive"].forEach(status=>{const option=document.createElement("option");option.value=status;option.textContent=status.replaceAll("_"," ");option.selected=item.status===status;select.append(option);});
      select.onchange=async()=>{await fetch(`${API_BASE}/security/remediations/${encodeURIComponent(item.review_id)}/${item.fingerprint}`,{method:"PATCH",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify({status:select.value,note:item.note || ""})});};
      card.append(info,select); remList.append(card);
    });
  }
  const alertList=document.getElementById("securityAlerts"); alertList.replaceChildren();
  if (alerts.ok) { const a=await alerts.json(); if(!a.alerts.length) alertList.textContent="No critical/high findings in recent saved scans."; a.alerts.slice(0,20).forEach(item=>{const row=document.createElement("div");row.className="history-item";row.textContent=`${item.severity.toUpperCase()} · ${item.repository} · ${item.title} · ${item.file || ""}`;alertList.append(row);}); }
  const scheduleList=document.getElementById("securitySchedules"); scheduleList.replaceChildren();
  if (schedules.ok) { const values=await schedules.json(); if(!values.length) scheduleList.textContent="No scan schedules configured."; values.forEach(item=>{const row=document.createElement("div");row.className="history-item";row.textContent=`Schedule #${item.id} · repository ID ${item.repository_id} · ${item.cadence} · external runner required`;scheduleList.append(row);}); }
}

async function downloadSecurityReport(format) {
  const response=await fetch(`${API_BASE}/security/reports/export?format=${encodeURIComponent(format)}`,{headers:authHeaders()});
  if(!response.ok){showAuthMessage("Could not export the security report.");return;}
  const blob=await response.blob(); const url=URL.createObjectURL(blob); const a=document.createElement("a");a.href=url;a.download=`codeguard-security-report.${format}`;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
}

async function createSecuritySchedule() {
  const repository_id=Number(document.getElementById("scheduleRepositoryId").value);
  const cadence=document.getElementById("scheduleCadence").value;
  const response=await fetch(`${API_BASE}/security/schedules`,{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify({repository_id,cadence})});
  const data=await response.json(); if(!response.ok){showAuthMessage(data.detail || "Could not save schedule.");return;}
  showAuthMessage(data.execution); loadSecurityIntelligence();
}


async function loadTeamSecurityDashboard() {
  const teamId=Number(document.getElementById("securityTeamId").value);
  if(!teamId){showAuthMessage("Enter a team ID.");return;}
  const response=await fetch(`${API_BASE}/security/teams/${teamId}/dashboard`,{headers:authHeaders()});
  const data=await response.json(); const target=document.getElementById("teamSecuritySummary"); target.replaceChildren();
  if(!response.ok){target.textContent=data.detail || "Could not load team dashboard.";return;}
  target.textContent=`Team ${teamId}: ${data.scans} scans · ${data.repositories} repositories · risk score ${data.risk_score}/100 · ${data.scope}`;
}
