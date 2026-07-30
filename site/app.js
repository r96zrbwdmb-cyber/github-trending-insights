const state = {
  view: location.hash === "#producthunt" ? "producthunt" : "github",
  date: ""
};
const $ = (id) => document.getElementById(id);
const esc = (value = "") => String(value).replace(/[&<>"']/g, c => (
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]
));
const list = (items) => (items || []).map(esc).join("、") || "未公开";

function githubData(snapshot) {
  const analysis = snapshot.industry_analysis || {};
  const insightMap = Object.fromEntries((analysis.repositories || []).map(x => [x.full_name, x]));
  return {
    date: snapshot.date || "",
    title: "开发者正在关注什么？",
    intro: "从开源项目热度中理解研究方向、产品机会与行业影响。",
    judgmentsTitle: "今天最重要的 5 个判断",
    judgments: analysis.key_judgments || [],
    patternsTitle: "今天的热门有什么特点",
    patterns: analysis.hot_characteristics || [],
    cardsTitle: "重点方向与项目",
    cardsEyebrow: "逐项理解",
    status: analysis.error || "",
    source: "https://github.com/trending",
    limits: "GitHub Trending 代表开发者关注度，不等于市场采用、收入、融资或研究突破。",
    cards: (snapshot.repositories || []).map(repo => {
      const item = insightMap[repo.full_name] || {};
      return {
        rank: repo.rank, name: repo.full_name, url: repo.url,
        kicker: item.industry_direction || "待分析",
        lead: item.one_line_summary || repo.description || "待分析",
        rows: [
          ["为谁服务", list(item.target_users)],
          ["解决什么", item.problem_solved || "待分析"],
          ["通俗场景", item.plain_language_explanation || "待分析"],
          ["实际好处", list(item.practical_benefits)],
          ["行业意义", item.industry_implications || "待分析"],
        ],
        signal: `日榜第 ${repo.rank} · 当日新增 ${Number(repo.stars_today || 0).toLocaleString()} Star`,
        confidence: item.confidence || "低"
      };
    })
  };
}

function productData(snapshot) {
  const analysis = snapshot.analysis || {};
  const insightMap = Object.fromEntries((analysis.products || []).map(x => [x.slug, x]));
  const trend7 = snapshot.trend_7d || {};
  const trend30 = snapshot.trend_30d || {};
  return {
    date: snapshot.date || "",
    title: "今天的新产品，究竟在卖什么？",
    intro: "看懂产品卖给谁、解决什么、怎样收费，以及它为什么现在值得关注。",
    judgmentsTitle: "今日最重要的产品与商业判断",
    judgments: analysis.key_judgments || [],
    patternsTitle: "今天大家在买什么能力",
    patterns: [
      ...(analysis.buying_capabilities || []),
      ...(analysis.business_model_patterns || [])
    ],
    cardsTitle: "Product Hunt Top 15",
    cardsEyebrow: `历史观察：7 天 ${trend7.observed_days || 0} 天 · 30 天 ${trend30.observed_days || 0} 天`,
    status: analysis.error || "",
    source: "https://www.producthunt.com/",
    limits: "Product Hunt 排名代表社区关注。价格和功能事实来自 Product Hunt 或产品官网；定位、获客与竞争判断均是分析推断。",
    cards: (snapshot.products || []).map(product => {
      const item = insightMap[product.slug] || {};
      const facts = (item.fact_claims || []).filter(x => x.source_url);
      return {
        rank: product.rank, name: product.name, url: product.product_hunt_url,
        image: product.thumbnail, kicker: item.category || list(product.topics),
        lead: item.what_it_sells || product.tagline || "未公开",
        rows: [
          ["卖给谁", list(item.target_customers)],
          ["解决什么", item.problem_solved || "未公开"],
          ["通俗场景", item.plain_scenario || "未公开"],
          ["有什么好处", list(item.benefits)],
          ["怎么收费", item.pricing_model || "未公开"],
          ["怎么成交", item.conversion_path || "未公开"],
          ["AI 的作用", item.ai_role || "未公开"],
        ],
        facts,
        judgments: item.strategy_judgments || [],
        signal: `官方日榜第 ${product.rank} · ${product.votes_count || 0} 票 · ${product.comments_count || 0} 条评论`,
        confidence: item.confidence || "低"
      };
    })
  };
}

function render(snapshot) {
  const data = state.view === "github" ? githubData(snapshot) : productData(snapshot);
  $("eyebrow").textContent = state.view === "github" ? "每日 AI 行业信号" : "每日产品与商业信号";
  $("page-title").textContent = data.title;
  $("page-intro").textContent = data.intro;
  $("date-label").textContent = data.date ? `数据日期 · ${data.date}` : "暂无有效数据";
  $("judgments-title").textContent = data.judgmentsTitle;
  $("patterns-title").textContent = data.patternsTitle;
  $("cards-title").textContent = data.cardsTitle;
  $("cards-eyebrow").textContent = data.cardsEyebrow;
  $("limits-copy").textContent = data.limits;
  $("source-link").href = data.source;
  $("judgments").innerHTML = data.judgments.length
    ? data.judgments.map(x => `<li>${esc(x)}</li>`).join("")
    : "<li>分析尚未生成，已保留原始数据。</li>";
  $("patterns").innerHTML = data.patterns.length
    ? data.patterns.map(x => `<article>${esc(x)}</article>`).join("")
    : "<article>历史数据积累后再形成可靠判断。</article>";
  const status = $("status");
  status.hidden = !data.status;
  status.textContent = data.status ? `分析说明：${data.status}` : "";
  $("cards").innerHTML = data.cards.map(card => `
    <article class="card">
      <div class="card-top">
        <span class="rank">${card.rank}</span>
        ${card.image ? `<img src="${esc(card.image)}" alt="" loading="lazy">` : ""}
        <div><p class="kicker">${esc(card.kicker)}</p>
        <h3><a href="${esc(card.url)}" target="_blank" rel="noopener">${esc(card.name)} ↗</a></h3></div>
      </div>
      <p class="lead">${esc(card.lead)}</p>
      <dl>${card.rows.map(([k,v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>
      ${(card.facts || []).length ? `<div class="evidence"><strong>事实依据</strong>${card.facts.slice(0,3).map(x =>
        `<a href="${esc(x.source_url)}" target="_blank" rel="noopener">${esc(x.claim)} ↗</a>`).join("")}</div>` : ""}
      ${(card.judgments || []).length ? `<div class="strategy"><strong>分析判断</strong>${card.judgments.map(esc).join("；")}</div>` : ""}
      <div class="card-foot"><span>${esc(card.signal)}</span><span>置信度 ${esc(card.confidence)}</span></div>
    </article>`).join("") || `<div class="empty">尚无 ${state.view === "github" ? "GitHub" : "Product Hunt"} 有效数据。</div>`;
}

function formatDate(value) {
  if (!value) return "选择日期";
  const [year, month, day] = value.split("-").map(Number);
  return `${year}年${month}月${day}日`;
}

function availableDates() {
  return (window.SITE_DATA.dates || {})[state.view] || [];
}

function updateDateNavigation() {
  const dates = availableDates();
  const selected = state.date || dates[dates.length - 1] || "";
  const index = dates.indexOf(selected);
  $("date-select").value = selected;
  $("date-prev").disabled = index <= 0;
  $("date-next").disabled = index < 0 || index >= dates.length - 1;
  document.querySelector(".date-nav").hidden = !dates.length;
}

async function loadDate(value) {
  const dates = availableDates();
  state.date = value || dates[dates.length - 1] || "";
  updateDateNavigation();
  const latest = dates[dates.length - 1] || "";
  if (!state.date || state.date === latest) {
    return render(window.SITE_DATA[state.view] || {});
  }
  try {
    const response = await fetch(`data/${state.view}/${state.date}.json`);
    if (!response.ok) throw new Error();
    render(await response.json());
  } catch (_) {
    $("status").hidden = false;
    $("status").textContent = "该日期的数据暂时无法读取，已显示最新有效结果。";
    render(window.SITE_DATA[state.view] || {});
  }
}

function switchView(view) {
  state.view = view;
  state.date = "";
  location.hash = view;
  document.querySelectorAll(".nav-tab").forEach(x => x.classList.toggle("active", x.dataset.view === view));
  const dates = availableDates();
  $("date-select").innerHTML = [...dates].reverse()
    .map((x, index) => `<option value="${x}">${formatDate(x)}${index === 0 ? "（最新）" : ""}</option>`)
    .join("");
  loadDate("");
}

document.querySelectorAll(".nav-tab").forEach(x => x.addEventListener("click", () => switchView(x.dataset.view)));
$("date-select").addEventListener("change", e => loadDate(e.target.value));
$("date-prev").addEventListener("click", () => {
  const dates = availableDates();
  const index = dates.indexOf(state.date);
  if (index > 0) loadDate(dates[index - 1]);
});
$("date-next").addEventListener("click", () => {
  const dates = availableDates();
  const index = dates.indexOf(state.date);
  if (index >= 0 && index < dates.length - 1) loadDate(dates[index + 1]);
});
window.addEventListener("hashchange", () => switchView(location.hash === "#producthunt" ? "producthunt" : "github"));
switchView(state.view);
