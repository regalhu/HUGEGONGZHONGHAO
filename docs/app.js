const state = {
  topics: [],
  articles: [],
};

const APP_VERSION = "20260605-role1";

const els = {
  form: document.querySelector("#generatorForm"),
  articleType: document.querySelector("#articleType"),
  keywordInput: document.querySelector("#keywordInput"),
  roleSelect: document.querySelector("#roleSelect"),
  topicSelect: document.querySelector("#topicSelect"),
  publishDate: document.querySelector("#publishDate"),
  issueNumber: document.querySelector("#issueNumber"),
  articleCount: document.querySelector("#articleCount"),
  brandName: document.querySelector("#brandName"),
  authorName: document.querySelector("#authorName"),
  titleInput: document.querySelector("#titleInput"),
  digestInput: document.querySelector("#digestInput"),
  referenceEnabled: document.querySelector("#referenceEnabled"),
  referenceInput: document.querySelector("#referenceInput"),
  randomButton: document.querySelector("#randomButton"),
  copyTextButton: document.querySelector("#copyTextButton"),
  copyHtmlButton: document.querySelector("#copyHtmlButton"),
  downloadMdButton: document.querySelector("#downloadMdButton"),
  downloadHtmlButton: document.querySelector("#downloadHtmlButton"),
  statusText: document.querySelector("#statusText"),
  previewTitle: document.querySelector("#previewTitle"),
  metaDate: document.querySelector("#metaDate"),
  metaTopic: document.querySelector("#metaTopic"),
  metaRole: document.querySelector("#metaRole"),
  metaCount: document.querySelector("#metaCount"),
  articlePreview: document.querySelector("#articlePreview"),
};

const articleTypeLabels = {
  ten_lessons: "餐饮10句劝",
  hot_interpretation: "餐饮热点解读",
  methodology: "餐饮方法论",
};

const roleProfiles = {
  owner: {
    label: "餐饮老板视角",
    focus: ["赚钱", "亏损", "现金流", "毛利", "复购", "风险"],
    reader: "小店老板",
    title: "别只看热闹，先把利润账算清楚",
    background: "主要看它会不会改变门店利润、现金流、客流结构和复购质量。",
    angles: ["利润有没有留下来", "现金流会不会被拖紧", "低价客能不能变成复购", "履约成本会不会吃掉毛利", "老板今天该先算哪三笔账"],
  },
  manager: {
    label: "门店店长视角",
    focus: ["执行", "排班", "出餐", "服务", "卫生", "差评", "员工管理"],
    reader: "门店店长",
    title: "订单来了，现场不能先乱",
    background: "主要看门店如何扛住高峰、减少差评、稳住出餐和服务动作。",
    angles: ["高峰出餐怎么排", "员工岗位怎么拆", "差评风险怎么提前拦", "卫生和打包怎么守住", "店长班前会该交代什么"],
  },
  operations: {
    label: "营运总监视角",
    focus: ["标准化", "加盟管控", "区域管理", "数据复盘", "督导体系"],
    reader: "营运负责人",
    title: "单店动作要变成全区域标准",
    background: "主要看总部如何统一标准、控制加盟店动作，并用数据复盘纠偏。",
    angles: ["总部哪些动作必须统一", "加盟店不能各自发挥什么", "区域督导要查哪几项", "数据复盘看什么信号", "标准化怎么不压死灵活性"],
  },
  marketing: {
    label: "品牌营销视角",
    focus: ["流量", "爆品", "内容传播", "会员", "私域", "团购", "抖音", "小红书"],
    reader: "品牌和营销负责人",
    title: "热点能蹭，但要把流量接成复购",
    background: "主要看品牌如何借热点做内容、团购、会员转化和私域沉淀。",
    angles: ["短内容怎么借势", "团购券怎么设计不伤毛利", "爆品怎么承接搜索流量", "会员怎么接住一次到店", "小红书和抖音话题怎么分工"],
  },
  supply: {
    label: "供应链视角",
    focus: ["采购", "损耗", "成本波动", "食材稳定", "仓配", "议价"],
    reader: "采购和供应链负责人",
    title: "低价竞争背后，先守住食材和损耗",
    background: "主要看低价竞争下食材成本、损耗、供应稳定和议价空间。",
    angles: ["核心食材会不会被拉涨", "低价套餐如何控制出成率", "仓配节奏怎么跟高峰", "替代原料能不能用", "供应商议价要看哪张表"],
  },
  customer: {
    label: "顾客视角",
    focus: ["价格", "体验", "口味", "服务", "环境", "复购理由"],
    reader: "顾客体验负责人",
    title: "顾客会被低价吸引，但不一定会复购",
    background: "主要看顾客为什么被吸引、哪里会失望、什么体验会让他愿意再来。",
    angles: ["顾客第一眼为什么点进来", "低价之后最怕什么落差", "口味和服务哪个更影响复购", "环境细节如何改变评价", "顾客愿意再来的理由是什么"],
  },
  investor: {
    label: "投资人视角",
    focus: ["模型是否成立", "坪效", "人效", "回本周期", "扩张风险"],
    reader: "投资人和合伙人",
    title: "热闹背后，先看这个模型能不能长期成立",
    background: "主要看商业模型是否可持续，重点盯坪效、人效、回本周期和扩张风险。",
    angles: ["补贴拉动的收入能不能持续", "坪效有没有真实改善", "人效是不是被高峰拖低", "回本周期会不会变长", "扩张前必须验证哪几个指标"],
  },
};

init();

async function init() {
  els.publishDate.value = new Date().toISOString().slice(0, 10);
  try {
    const response = await fetch(`./topic_library.json?v=${APP_VERSION}`, { cache: "no-store" });
    state.topics = await response.json();
    renderTopicOptions();
    hydrateFromStorage();
    generateArticles();
    bindEvents();
  } catch (error) {
    els.statusText.textContent = "内容库载入失败";
    els.previewTitle.textContent = String(error);
  }
}

function bindEvents() {
  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    generateArticles();
  });

  [
    els.articleType,
    els.keywordInput,
    els.roleSelect,
    els.topicSelect,
    els.publishDate,
    els.issueNumber,
    els.articleCount,
    els.brandName,
    els.authorName,
    els.referenceEnabled,
    els.referenceInput,
  ].forEach((element) => {
    element.addEventListener("change", () => {
      persistControls();
      generateArticles();
    });
    element.addEventListener("input", persistControls);
  });

  els.titleInput.addEventListener("input", () => {
    if (!state.articles[0]) return;
    state.articles[0].title = els.titleInput.value.trim() || state.articles[0].title;
    renderArticles();
  });

  els.digestInput.addEventListener("input", () => {
    if (!state.articles[0]) return;
    state.articles[0].digest = els.digestInput.value.trim();
    renderArticles();
  });

  els.randomButton.addEventListener("click", chooseRandomTopic);
  els.copyTextButton.addEventListener("click", () => copyToClipboard(articlesToText()));
  els.copyHtmlButton.addEventListener("click", () => copyToClipboard(articlesBodyHtml()));
  els.downloadMdButton.addEventListener("click", () => downloadFile(filename("md"), articlesToMarkdown(), "text/markdown"));
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
  if (stored.keyword) els.keywordInput.value = stored.keyword;
  if (stored.role) els.roleSelect.value = stored.role;
  if (stored.topicId && state.topics.some((topic) => topic.id === stored.topicId)) els.topicSelect.value = stored.topicId;
  if (!state.topics.some((topic) => topic.id === els.topicSelect.value) && state.topics[0]) {
    els.topicSelect.value = state.topics[0].id;
  }
  if (stored.issueNumber) els.issueNumber.value = stored.issueNumber;
  if (stored.articleCount) els.articleCount.value = stored.articleCount;
  if (stored.brandName) els.brandName.value = stored.brandName;
  if (stored.authorName) els.authorName.value = stored.authorName;
  if (typeof stored.referenceEnabled === "boolean") els.referenceEnabled.checked = stored.referenceEnabled;
  if (stored.referenceText) els.referenceInput.value = stored.referenceText;
}

function persistControls() {
  localStorage.setItem(
    "hugeGithubTool",
    JSON.stringify({
      articleType: els.articleType.value,
      keyword: els.keywordInput.value,
      role: els.roleSelect.value,
      topicId: els.topicSelect.value,
      issueNumber: els.issueNumber.value,
      articleCount: els.articleCount.value,
      brandName: els.brandName.value,
      authorName: els.authorName.value,
      referenceEnabled: els.referenceEnabled.checked,
      referenceText: els.referenceInput.value,
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
  generateArticles();
}

function generateArticles() {
  const topic = state.topics.find((item) => item.id === els.topicSelect.value) || state.topics[0];
  if (!topic) return;

  const articleType = els.articleType.value;
  const issueNumber = Number.parseInt(els.issueNumber.value || "229", 10);
  const count = clamp(Number.parseInt(els.articleCount.value || "1", 10), 1, 5);
  els.articleCount.value = String(count);
  const publishDate = els.publishDate.value || new Date().toISOString().slice(0, 10);
  const brandName = els.brandName.value.trim() || "胡哥说餐饮";
  const authorName = els.authorName.value.trim() || "胡哥";
  const keyword = els.keywordInput.value.trim() || keywordFromTopic(topic);
  const role = roleProfiles[els.roleSelect.value] || roleProfiles.owner;
  const references = els.referenceEnabled.checked ? parseReferences(els.referenceInput.value) : [];
  const referenceIdeas = referenceIdeasFrom(references, keyword);

  state.articles = Array.from({ length: count }, (_, index) => {
    const angle = buildAngle({ topic, role, keyword, referenceIdeas, index });
    const article = buildArticle({
      topic,
      role,
      keyword,
      angle,
      articleType,
      issueNumber: issueNumber + index,
      publishDate,
      brandName,
      authorName,
      references,
      referenceIdeas,
      index,
    });
    return article;
  });

  els.titleInput.value = state.articles[0]?.title || "";
  els.digestInput.value = state.articles[0]?.digest || "";
  persistControls();
  renderArticles();
}

function buildAngle({ topic, role, keyword, referenceIdeas, index }) {
  const base = role.angles[index % role.angles.length];
  const referenceHint = referenceIdeas[index % Math.max(referenceIdeas.length, 1)] || "";
  return {
    title: base,
    topicLine: referenceHint ? `${keyword}：${base}，同时参考公开讨论里的“${referenceHint}”。` : `${keyword}：${base}。`,
    sourcePoint: referenceHint || role.focus[index % role.focus.length],
    topicName: topic.name,
  };
}

function buildArticle({
  topic,
  role,
  keyword,
  angle,
  articleType,
  issueNumber,
  publishDate,
  brandName,
  authorName,
  references,
  referenceIdeas,
  index,
}) {
  const title = titleFor({ topic, role, keyword, angle, articleType, issueNumber });
  const sections = sectionsFor({ topic, role, keyword, angle, articleType, referenceIdeas, index });
  return {
    title,
    digest: digestFor({ topic, role, keyword, angle, articleType }),
    intro: introFor({ topic, role, keyword, angle, articleType, references }),
    background: backgroundFor({ keyword, role, references, referenceIdeas }),
    sections,
    conclusion: conclusionFor({ authorName, brandName, role, keyword, articleType }),
    topicName: topic.name,
    publishDate,
    issueNumber,
    articleType,
    brandName,
    authorName,
    keyword,
    role,
    angle,
    references,
  };
}

function titleFor({ topic, role, keyword, angle, articleType, issueNumber }) {
  if (articleType === "ten_lessons") {
    return `${keyword}又火了，${role.reader}先听这10句劝｜第${issueNumber}期`;
  }
  if (articleType === "methodology") {
    return `${keyword}别只看热闹，${role.reader}先用这3步查${angle.title}`;
  }
  if (keyword && keyword !== keywordFromTopic(topic)) {
    return `${keyword}又来了，${role.reader}${role.title}`;
  }
  return `${topic.title}：${role.reader}要看${angle.title}`;
}

function digestFor({ role, keyword, angle, articleType }) {
  if (articleType === "methodology") {
    return `围绕${keyword}，从${role.label}拆一套能落地的检查方法，重点看${angle.title}。`;
  }
  if (articleType === "hot_interpretation") {
    return `同一个热点换一个角色，结论就会不同。本篇从${role.label}看${keyword}，重点拆${angle.title}。`;
  }
  return `本期从${role.label}聊${keyword}，不空喊口号，只讲${role.focus.slice(0, 4).join("、")}这些实账。`;
}

function introFor({ role, keyword, angle, references }) {
  const sourceLine = references.length
    ? "我先把公开资料里的观点过了一遍，只提炼方向，不照搬原文。"
    : "如果你手上有参考链接或摘要，可以粘到参考资料区，文章会自动带上信源。";
  return `老板，同一个${keyword}，站在不同位置看，完全是不同问题。${role.label}最该盯的不是热闹，而是${angle.title}。${sourceLine}`;
}

function backgroundFor({ keyword, role, references, referenceIdeas }) {
  if (!references.length) {
    return `目前未启用有效信源。本文只按“${keyword}”这个话题做经营推演，不把任何未核实数据写成事实。`;
  }
  const ideaText = referenceIdeas.length ? `公开资料中较常见的讨论方向包括：${referenceIdeas.slice(0, 4).join("、")}。` : "公开资料主要用于确认话题背景和讨论方向。";
  return `围绕${keyword}，已整理${references.length}条手动参考资料。${ideaText}${role.background}`;
}

function sectionsFor({ topic, role, keyword, angle, articleType, referenceIdeas, index }) {
  if (articleType === "ten_lessons") {
    return tenLessonsSections({ topic, role, keyword, angle, referenceIdeas });
  }
  if (articleType === "methodology") {
    return methodologySections({ role, keyword, angle, referenceIdeas });
  }
  return hotInterpretationSections({ role, keyword, angle, referenceIdeas, index });
}

function tenLessonsSections({ topic, role, keyword, angle, referenceIdeas }) {
  const base = topic.advices.map((item, index) => ({
    index: index + 1,
    title: item[0],
    body: item[1],
  }));
  return role.focus.slice(0, 10).map((focus, index) => {
    const advice = base[index % base.length];
    const idea = referenceIdeas[index % Math.max(referenceIdeas.length, 1)];
    return {
      title: `${focus}这笔账要单独看`,
      body: `${keyword}看起来是外部热闹，落到${role.label}，其实要查${focus}。${advice.body}${idea ? ` 参考资料里提到的“${idea}”，只能当方向，不能直接当结论。` : ""}`,
    };
  });
}

function methodologySections({ role, keyword, angle, referenceIdeas }) {
  const idea = referenceIdeas[0] || angle.title;
  return [
    {
      title: `第一步：把${keyword}拆回门店动作`,
      body: `不要先问要不要跟风，先问${role.reader}今天能改哪个动作。围绕${angle.title}，把人、货、钱、客四件事各列一个检查点。`,
    },
    {
      title: "第二步：把参考资料只当线索",
      body: `公开内容可以提醒你大家在聊什么，比如“${idea}”。但它不能替你下结论，门店还是要看自己的毛利、差评、复购和履约成本。`,
    },
    {
      title: `第三步：按${role.focus.slice(0, 3).join("、")}复盘`,
      body: `连续7天只盯这几个指标，别一天一个想法。指标变好，再扩大动作；指标没变，就说明这波热点只带来了热闹，没有带来经营结果。`,
    },
    {
      title: "今天能做的3个动作",
      body: `一是列出受${keyword}影响最大的3个菜或套餐；二是写清楚员工现场话术；三是闭店复盘一次${angle.title}，只改最卡的那个点。`,
    },
  ];
}

function hotInterpretationSections({ role, keyword, angle, referenceIdeas, index }) {
  const idea = referenceIdeas[index % Math.max(referenceIdeas.length, 1)] || "多个平台均出现相关讨论";
  return [
    {
      title: `一、${keyword}热闹，但${role.reader}不能只看声量`,
      body: `公开内容里常见的方向是“${idea}”。这个信息可以说明话题有人讨论，但不能直接说明门店一定赚钱。${role.label}要先把它翻译成${role.focus.slice(0, 3).join("、")}这些经营问题。`,
    },
    {
      title: `二、真正要拆的是${angle.title}`,
      body: `同一个热点，老板、店长、营运、营销看到的都不一样。站在${role.label}，这件事的关键不是跟不跟，而是跟了以后现场有没有能力接住。`,
    },
    {
      title: "三、低价和流量不能替代基本功",
      body: `如果产品不稳、出餐不稳、服务不稳，热点只会放大问题。顾客第一次可能被吸引，第二次是否回来，还是看体验和价值感。`,
    },
    {
      title: "四、今天先做这3个小动作",
      body: `先列一张影响清单，再定一个现场动作，最后只看一个复盘指标。不要把热点当战略，先把它当一次门店体检。`,
    },
  ];
}

function conclusionFor({ authorName, brandName, role, keyword }) {
  return `我是${authorName}。${brandName}今天这篇只想提醒一句：${keyword}可以借势，但账不能乱。站在${role.label}，先把能落地的动作做出来，再谈流量和声量。`;
}

function parseReferences(text) {
  const clean = text.trim();
  if (!clean) return [];
  const blocks = clean.split(/\n\s*\n+/).map((block) => block.trim()).filter(Boolean);
  const rawBlocks = blocks.length > 1 ? blocks : splitLooseReferences(clean);
  return rawBlocks.map(parseReferenceBlock).filter((item) => item.title || item.url || item.summary).slice(0, 6);
}

function splitLooseReferences(text) {
  const lines = text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  const blocks = [];
  let current = [];
  lines.forEach((line) => {
    if (/^(标题|来源|链接|摘要|观点|参考点|数据)[:：]/.test(line) && current.some((item) => /^标题[:：]/.test(item))) {
      blocks.push(current.join("\n"));
      current = [line];
    } else {
      current.push(line);
    }
  });
  if (current.length) blocks.push(current.join("\n"));
  return blocks;
}

function parseReferenceBlock(block) {
  const url = (block.match(/https?:\/\/[^\s，。)）]+/i) || [""])[0];
  const title = pickField(block, ["标题", "题目"]) || firstUsefulLine(block, url);
  const source = pickField(block, ["来源", "平台", "媒体"]) || sourceFromUrl(url) || "未标明来源";
  const publishedAt = pickField(block, ["发布时间", "日期", "时间"]) || "";
  const summary = pickField(block, ["摘要", "观点", "参考点", "内容", "数据"]) || summarizeBlock(block, title, url);
  const keywords = extractKeywords(`${title} ${summary}`);
  return {
    title: limitText(title || "未标明标题", 80),
    source: limitText(source, 40),
    publishedAt: limitText(publishedAt, 30),
    url,
    summary: limitText(summary, 140),
    keywords,
    referencePoint: limitText(summary || title || "用于参考话题方向", 70),
    incomplete: !(title && source && url),
  };
}

function pickField(text, names) {
  for (const name of names) {
    const match = text.match(new RegExp(`${name}[:：]\\s*([^\\n]+)`, "i"));
    if (match) return match[1].trim();
  }
  return "";
}

function firstUsefulLine(block, url) {
  return block
    .split(/\n+/)
    .map((line) => line.trim())
    .find((line) => line && line !== url && !/^https?:\/\//i.test(line) && !/^(来源|链接)[:：]/.test(line)) || "";
}

function summarizeBlock(block, title, url) {
  return block
    .replace(url, "")
    .split(/\n+/)
    .map((line) => line.replace(/^(标题|来源|链接|摘要|观点|参考点|内容|数据|发布时间|日期|时间)[:：]\s*/i, "").trim())
    .filter((line) => line && line !== title)
    .join("；");
}

function sourceFromUrl(url) {
  if (!url) return "";
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host.includes("weixin")) return "微信公众号公开内容";
    if (host.includes("xiaohongshu")) return "小红书";
    if (host.includes("douyin")) return "抖音";
    if (host.includes("dianping")) return "大众点评";
    if (host.includes("baidu")) return "百度搜索结果";
    return host;
  } catch {
    return "";
  }
}

function referenceIdeasFrom(references, keyword) {
  const ideas = [];
  references.forEach((reference) => {
    reference.keywords.forEach((item) => {
      if (item !== keyword && !ideas.includes(item)) ideas.push(item);
    });
    if (reference.referencePoint && ideas.length < 5) ideas.push(reference.referencePoint);
  });
  return ideas.slice(0, 8);
}

function extractKeywords(text) {
  const candidates = [
    "低价", "补贴", "团购", "复购", "现金流", "毛利", "差评", "爆单", "出餐", "会员",
    "私域", "供应链", "采购", "损耗", "坪效", "人效", "回本", "标准化", "加盟", "抖音",
    "小红书", "外卖", "套餐", "价格", "体验", "服务", "口味", "流量", "风险",
  ];
  return candidates.filter((keyword) => text.includes(keyword)).slice(0, 6);
}

function renderArticles() {
  if (!state.articles.length) return;
  const first = state.articles[0];
  els.statusText.textContent = `${articleTypeLabels[first.articleType]} · ${first.role.label} · ${APP_VERSION}`;
  els.previewTitle.textContent = first.title;
  els.metaDate.textContent = first.publishDate;
  els.metaTopic.textContent = first.keyword || first.topicName;
  els.metaRole.textContent = first.role.label;
  els.metaCount.textContent = `${state.articles.length}篇`;
  els.articlePreview.innerHTML = state.articles.map(articleCardHtml).join("");
}

function articleCardHtml(article) {
  return `
    <section class="draft-card">
      <h3>${escapeHtml(article.title)}</h3>
      <p class="digest">${escapeHtml(article.digest)}</p>
      ${articleBodyHtml(article)}
    </section>
  `;
}

function articleBodyHtml(article) {
  if (!article) return "";
  const sectionHtml = article.sections
    .map((section, index) => `
      <section class="advice">
        <p class="advice-title">${article.articleType === "ten_lessons" ? String(index + 1).padStart(2, "0") + " " : ""}${escapeHtml(section.title)}</p>
        <p>${escapeHtml(section.body)}</p>
      </section>
    `)
    .join("");

  return `
    <section class="wechat-body">
      <p class="image-slot">【图片插入位：请在这里插入本期配图】</p>
      <section class="role-line"><strong>角色视角：</strong>${escapeHtml(article.role.label)}</section>
      <section class="background"><strong>热点背景：</strong>${escapeHtml(article.background)}</section>
      <p>${escapeHtml(article.intro)}</p>
      ${sectionHtml}
      <section class="conclusion"><p>${escapeHtml(article.conclusion)}</p></section>
      ${sourcesHtml(article.references)}
      <p class="footer-line">栏目：${escapeHtml(article.brandName)} · ${escapeHtml(article.publishDate)}</p>
    </section>
  `;
}

function sourcesHtml(references) {
  if (!references.length) {
    return `
      <section class="sources">
        <strong>参考信源：</strong>
        <p>本篇未使用外部信源，仅按用户输入话题和内置餐饮经营框架原创生成；不作为数据依据。</p>
      </section>
    `;
  }
  return `
    <section class="sources">
      <strong>参考信源：</strong>
      <ol>
        ${references.map((reference) => `
          <li>
            <div>来源：${escapeHtml(reference.source)}</div>
            <div>标题：${escapeHtml(reference.title)}</div>
            <div>链接：${reference.url ? `<a href="${escapeAttr(reference.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(reference.url)}</a>` : "未提供"}</div>
            <div>参考点：${escapeHtml(reference.referencePoint || "用于参考热点背景/用户讨论/行业观点")}</div>
            ${reference.publishedAt ? `<div>发布时间：${escapeHtml(reference.publishedAt)}</div>` : ""}
            ${reference.incomplete ? `<div>该来源仅用于话题参考，不作为数据依据。</div>` : ""}
          </li>
        `).join("")}
      </ol>
    </section>
  `;
}

function articlesToText() {
  return state.articles.map(articleToText).join("\n\n---\n\n");
}

function articleToText(article) {
  return [
    `标题：${article.title}`,
    "",
    "【图片插入位：请在这里插入本期配图】",
    "",
    `角色视角：${article.role.label}`,
    "",
    `热点背景：${article.background}`,
    "",
    "正文：",
    article.intro,
    "",
    ...article.sections.flatMap((section, index) => [
      `${article.articleType === "ten_lessons" ? String(index + 1).padStart(2, "0") + " " : ""}${section.title}`,
      section.body,
      "",
    ]),
    `胡哥总结：${article.conclusion}`,
    "",
    sourcesText(article.references),
  ].join("\n");
}

function articlesToMarkdown() {
  return state.articles.map(articleToMarkdown).join("\n\n---\n\n");
}

function articleToMarkdown(article) {
  return [
    `# ${article.title}`,
    "",
    "【图片插入位：请在这里插入本期配图】",
    "",
    `**角色视角：** ${article.role.label}`,
    "",
    `**热点背景：** ${article.background}`,
    "",
    article.intro,
    "",
    ...article.sections.flatMap((section, index) => [
      `## ${article.articleType === "ten_lessons" ? String(index + 1).padStart(2, "0") + " " : ""}${section.title}`,
      "",
      section.body,
      "",
    ]),
    `## 胡哥总结`,
    "",
    article.conclusion,
    "",
    sourcesMarkdown(article.references),
  ].join("\n");
}

function sourcesText(references) {
  if (!references.length) {
    return "参考信源：\n1. 本篇未使用外部信源，仅按用户输入话题和内置餐饮经营框架原创生成；不作为数据依据。";
  }
  return [
    "参考信源：",
    ...references.map((reference, index) => [
      `${index + 1}. 来源：${reference.source}`,
      `   标题：${reference.title}`,
      `   链接：${reference.url || "未提供"}`,
      `   参考点：${reference.referencePoint || "用于参考热点背景/用户讨论/行业观点"}`,
      reference.incomplete ? "   该来源仅用于话题参考，不作为数据依据。" : "",
    ].filter(Boolean).join("\n")),
  ].join("\n");
}

function sourcesMarkdown(references) {
  if (!references.length) {
    return "## 参考信源\n\n1. 本篇未使用外部信源，仅按用户输入话题和内置餐饮经营框架原创生成；不作为数据依据。";
  }
  return [
    "## 参考信源",
    "",
    ...references.map((reference, index) => [
      `${index + 1}. 来源：${reference.source}`,
      `   标题：${reference.title}`,
      `   链接：${reference.url || "未提供"}`,
      `   参考点：${reference.referencePoint || "用于参考热点背景/用户讨论/行业观点"}`,
      reference.incomplete ? "   该来源仅用于话题参考，不作为数据依据。" : "",
      "",
    ].filter(Boolean).join("\n")),
  ].join("\n");
}

function articlesBodyHtml() {
  return state.articles.map(articleBodyHtml).join("\n<hr>\n");
}

function fullHtmlDocument() {
  const title = state.articles[0]?.title || "胡哥说餐饮公众号文章";
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title></head><body>${articlesBodyHtml()}</body></html>`;
}

async function copyToClipboard(value) {
  await navigator.clipboard.writeText(value);
  els.statusText.textContent = "已复制";
  window.setTimeout(() => {
    if (state.articles[0]) els.statusText.textContent = `${articleTypeLabels[state.articles[0].articleType]} · ${state.articles[0].role.label} · ${APP_VERSION}`;
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
  const date = state.articles[0]?.publishDate || new Date().toISOString().slice(0, 10);
  return `huge-catering-${date}.${extension}`;
}

function keywordFromTopic(topic) {
  return String(topic.name || topic.title || "餐饮热点").split("·")[0];
}

function limitText(value, max) {
  const text = String(value || "").trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function clamp(value, min, max) {
  if (Number.isNaN(value)) return min;
  return Math.max(min, Math.min(max, value));
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
