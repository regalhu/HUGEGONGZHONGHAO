const state = {
  topics: [],
  article: null,
};

const APP_VERSION = "20260605-quality1";

const els = {
  form: document.querySelector("#generatorForm"),
  articleType: document.querySelector("#articleType"),
  topicSelect: document.querySelector("#topicSelect"),
  publishDate: document.querySelector("#publishDate"),
  issueNumber: document.querySelector("#issueNumber"),
  brandName: document.querySelector("#brandName"),
  authorName: document.querySelector("#authorName"),
  titleInput: document.querySelector("#titleInput"),
  digestInput: document.querySelector("#digestInput"),
  randomButton: document.querySelector("#randomButton"),
  copyTextButton: document.querySelector("#copyTextButton"),
  copyHtmlButton: document.querySelector("#copyHtmlButton"),
  downloadMdButton: document.querySelector("#downloadMdButton"),
  downloadHtmlButton: document.querySelector("#downloadHtmlButton"),
  statusText: document.querySelector("#statusText"),
  previewTitle: document.querySelector("#previewTitle"),
  metaDate: document.querySelector("#metaDate"),
  metaTopic: document.querySelector("#metaTopic"),
  metaCount: document.querySelector("#metaCount"),
  articlePreview: document.querySelector("#articlePreview"),
};

const articleTypeLabels = {
  ten_lessons: "餐饮10句劝",
  hot_interpretation: "餐饮热点解读",
  methodology: "餐饮方法论",
};

init();

async function init() {
  els.publishDate.value = new Date().toISOString().slice(0, 10);
  try {
    const response = await fetch(`./topic_library.json?v=${APP_VERSION}`, { cache: "no-store" });
    state.topics = await response.json();
    renderTopicOptions();
    hydrateFromStorage();
    generateCurrentArticle();
    bindEvents();
  } catch (error) {
    els.statusText.textContent = "内容库载入失败";
    els.previewTitle.textContent = String(error);
  }
}

function bindEvents() {
  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    generateCurrentArticle();
  });

  [
    els.articleType,
    els.topicSelect,
    els.publishDate,
    els.issueNumber,
    els.brandName,
    els.authorName,
  ].forEach((element) => {
    element.addEventListener("change", () => {
      persistControls();
      generateCurrentArticle();
    });
    element.addEventListener("input", persistControls);
  });

  els.titleInput.addEventListener("input", () => {
    if (!state.article) return;
    state.article.title = els.titleInput.value.trim() || state.article.title;
    renderArticle();
  });

  els.digestInput.addEventListener("input", () => {
    if (!state.article) return;
    state.article.digest = els.digestInput.value.trim();
    renderArticle();
  });

  els.randomButton.addEventListener("click", chooseRandomTopic);
  els.copyTextButton.addEventListener("click", () => copyToClipboard(articleToText()));
  els.copyHtmlButton.addEventListener("click", () => copyToClipboard(articleBodyHtml()));
  els.downloadMdButton.addEventListener("click", () => downloadFile(filename("md"), articleToMarkdown(), "text/markdown"));
  els.downloadHtmlButton.addEventListener("click", () => downloadFile(filename("html"), fullHtmlDocument(), "text/html"));
}

function renderTopicOptions() {
  els.topicSelect.innerHTML = state.topics
    .map((topic) => `<option value="${escapeAttr(topic.id)}">${escapeHtml(topic.name)} · ${escapeHtml(topic.title)}</option>`)
    .join("");
  if (state.topics.length && !els.topicSelect.value) {
    els.topicSelect.value = state.topics[0].id;
  }
}

function hydrateFromStorage() {
  const stored = JSON.parse(localStorage.getItem("hugeGithubTool") || "{}");
  if (stored.articleType) els.articleType.value = stored.articleType;
  if (stored.topicId && state.topics.some((topic) => topic.id === stored.topicId)) els.topicSelect.value = stored.topicId;
  if (!state.topics.some((topic) => topic.id === els.topicSelect.value) && state.topics[0]) {
    els.topicSelect.value = state.topics[0].id;
  }
  if (stored.issueNumber) els.issueNumber.value = stored.issueNumber;
  if (stored.brandName) els.brandName.value = stored.brandName;
  if (stored.authorName) els.authorName.value = stored.authorName;
}

function persistControls() {
  localStorage.setItem(
    "hugeGithubTool",
    JSON.stringify({
      articleType: els.articleType.value,
      topicId: els.topicSelect.value,
      issueNumber: els.issueNumber.value,
      brandName: els.brandName.value,
      authorName: els.authorName.value,
    }),
  );
}

function chooseRandomTopic() {
  if (!state.topics.length) return;
  const current = els.topicSelect.value;
  const pool = state.topics.filter((topic) => topic.id !== current);
  const topic = pool[Math.floor(Math.random() * pool.length)] || state.topics[0];
  els.topicSelect.value = topic.id;
  persistControls();
  generateCurrentArticle();
}

function generateCurrentArticle() {
  const topic = state.topics.find((item) => item.id === els.topicSelect.value) || state.topics[0];
  if (!topic) return;

  const articleType = els.articleType.value;
  const issueNumber = Number.parseInt(els.issueNumber.value || "229", 10);
  const publishDate = els.publishDate.value || new Date().toISOString().slice(0, 10);
  const brandName = els.brandName.value.trim() || "胡哥说餐饮";
  const authorName = els.authorName.value.trim() || "胡哥";
  const title = titleFor(topic, articleType, issueNumber);
  const advices = advicesFor(topic, articleType);

  state.article = {
    title,
    digest: digestFor(topic, articleType),
    intro: introFor(topic, articleType),
    advices,
    conclusion: conclusionFor(authorName, brandName, articleType),
    topicName: topic.name,
    publishDate,
    issueNumber,
    articleType,
    brandName,
    authorName,
  };

  els.titleInput.value = state.article.title;
  els.digestInput.value = state.article.digest;
  persistControls();
  renderArticle();
}

function titleFor(topic, articleType, issueNumber) {
  if (articleType === "ten_lessons") return `${topic.short_title || "餐饮要赚钱 听我10句劝"}｜第${issueNumber}期`;
  if (articleType === "methodology") return `${topic.name.replace("·", "")}越做越乱？先用这3步把利润拉回来`;
  return topic.title;
}

function digestFor(topic, articleType) {
  if (articleType === "methodology") return `围绕${topic.name}，给餐饮老板一套能落地的检查动作。`;
  if (articleType === "hot_interpretation") return `${topic.digest}重点看客流、客单、毛利、复购和风险。`;
  return topic.digest;
}

function introFor(topic, articleType) {
  if (articleType === "methodology") return `${topic.intro}这次不讲大口号，只拆成3组动作，方便老板明天就拿去查店。`;
  if (articleType === "hot_interpretation") return `${topic.intro}热闹归热闹，餐饮老板更要看它会不会影响店里的钱。`;
  return topic.intro;
}

function advicesFor(topic, articleType) {
  const advices = topic.advices.map((item, index) => ({
    index: index + 1,
    title: item[0],
    body: item[1],
  }));

  if (articleType !== "methodology") return advices;

  return [
    {
      index: 1,
      title: "先把问题拆小",
      body: `${topic.name}不要一上来就全店大整改。先选一个最影响利润的环节，盯3天数据，再决定改哪里。`,
    },
    {
      index: 2,
      title: "再把动作固定",
      body: advices.slice(0, 4).map((item) => item.title).join("、") + "，这些动作要写成检查表，员工照着做，老板照着查。",
    },
    {
      index: 3,
      title: "最后看结果复盘",
      body: "每天只看一个核心变化：出餐速度、损耗、客单、复购或差评。连续7天有改善，再把动作变成门店标准。",
    },
  ];
}

function conclusionFor(authorName, brandName, articleType) {
  if (articleType === "methodology") return `我是${authorName}。${brandName}今天这套方法，不求一步到位，先让店里少乱一点、少漏一点、利润多留一点。`;
  if (articleType === "hot_interpretation") return `我是${authorName}。热点每天都变，餐饮老板别被热闹带跑，最后还是要回到顾客、成本、效率和复购。`;
  return `我是${authorName}。餐饮赚钱没有神招，真正有用的，往往是老板每天愿意盯住的小动作。`;
}

function renderArticle() {
  if (!state.article) return;
  els.statusText.textContent = `${articleTypeLabels[state.article.articleType]} · ${state.article.topicName} · ${APP_VERSION}`;
  els.previewTitle.textContent = state.article.title;
  els.metaDate.textContent = state.article.publishDate;
  els.metaTopic.textContent = state.article.topicName;
  els.metaCount.textContent = `${state.article.advices.length}段正文`;
  els.articlePreview.innerHTML = `
    <h3>${escapeHtml(state.article.title)}</h3>
    <p class="digest">${escapeHtml(state.article.digest)}</p>
    ${articleBodyHtml()}
  `;
}

function articleBodyHtml() {
  if (!state.article) return "";
  const adviceHtml = state.article.advices
    .map((advice) => `
      <section class="advice">
        <p class="advice-title">${state.article.articleType === "ten_lessons" ? String(advice.index).padStart(2, "0") + " " : ""}${escapeHtml(advice.title)}</p>
        <p>${escapeHtml(advice.body)}</p>
      </section>
    `)
    .join("");

  return `
    <section class="wechat-body">
      <p>${escapeHtml(state.article.intro)}</p>
      <p class="image-slot">【图片插入位：请在这里插入本期配图】</p>
      ${adviceHtml}
      <section class="conclusion"><p>${escapeHtml(state.article.conclusion)}</p></section>
      <p class="footer-line">栏目：${escapeHtml(state.article.brandName)} · ${escapeHtml(state.article.publishDate)}</p>
    </section>
  `;
}

function articleToText() {
  if (!state.article) return "";
  return [
    state.article.title,
    "",
    state.article.digest,
    "",
    state.article.intro,
    "",
    "【图片插入位：请在这里插入本期配图】",
    "",
    ...state.article.advices.flatMap((advice) => [
      `${state.article.articleType === "ten_lessons" ? String(advice.index).padStart(2, "0") + " " : ""}${advice.title}`,
      advice.body,
      "",
    ]),
    state.article.conclusion,
    "",
    `栏目：${state.article.brandName} · ${state.article.publishDate}`,
  ].join("\n");
}

function articleToMarkdown() {
  if (!state.article) return "";
  return [
    `# ${state.article.title}`,
    "",
    `> ${state.article.digest}`,
    "",
    state.article.intro,
    "",
    "【图片插入位：请在这里插入本期配图】",
    "",
    ...state.article.advices.flatMap((advice) => [
      `## ${state.article.articleType === "ten_lessons" ? String(advice.index).padStart(2, "0") + " " : ""}${advice.title}`,
      "",
      advice.body,
      "",
    ]),
    state.article.conclusion,
    "",
    `栏目：${state.article.brandName} · ${state.article.publishDate}`,
  ].join("\n");
}

function fullHtmlDocument() {
  if (!state.article) return "";
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(state.article.title)}</title></head><body>${articleBodyHtml()}</body></html>`;
}

async function copyToClipboard(value) {
  await navigator.clipboard.writeText(value);
  els.statusText.textContent = "已复制";
  window.setTimeout(() => {
    if (state.article) els.statusText.textContent = `${articleTypeLabels[state.article.articleType]} · 可复制`;
  }, 1400);
}

function downloadFile(name, content, type) {
  const blob = new Blob([content], { type: `${type};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function filename(extension) {
  const date = state.article?.publishDate || new Date().toISOString().slice(0, 10);
  return `huge-catering-${date}.${extension}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}
