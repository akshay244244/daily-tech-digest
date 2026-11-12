/* Daily Tech Digest — static front-end. Reads JSON from ./data, no server needed. */
(function () {
  "use strict";

  // ---------- tiny helpers ----------
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const app = $("#app");
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
    raw(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    rawSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  const istToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
  const parseD = (d) => { const [y, m, dd] = d.split("-").map(Number); return new Date(Date.UTC(y, m - 1, dd, 12)); };
  const fmtLong = (d) => parseD(d).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
  const fmtShort = (d) => parseD(d).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const addDays = (d, n) => { const x = parseD(d); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };
  const relDay = (d) => { const t = istToday(); if (d === t) return "Today"; if (d === addDays(t, -1)) return "Yesterday"; return parseD(d).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" }); };
  const pad = (n) => String(n).padStart(2, "0");
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const bust = () => "?t=" + Math.floor(Date.now() / 60000);

  async function getJSON(path, fresh) {
    try {
      const r = await fetch("data/" + path + (fresh ? bust() : ""), { cache: fresh ? "no-store" : "default" });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  // ---------- data ----------
  const S = { idx: null, digests: {}, sections: [], secBy: {}, allLoaded: false };

  async function loadCore(fresh) {
    S.idx = await getJSON("index.json", true);
    if (!S.idx) { S.idx = { dates: [], sections: [], latest: null }; }
    S.sections = S.idx.sections || [];
    S.secBy = Object.fromEntries(S.sections.map((s) => [s.slug, s]));
    const want = S.idx.dates.slice(0, 7).map((r) => r.date);
    await loadDates(want, fresh);
  }
  async function loadDates(dates, fresh) {
    await Promise.all(dates.filter((d) => fresh || !S.digests[d]).map(async (d) => {
      const dg = await getJSON("digests/" + d + ".json", fresh);
      if (dg) S.digests[d] = dg;
    }));
  }
  async function loadAll() {
    if (S.allLoaded) return;
    await loadDates(S.idx.dates.map((r) => r.date));
    S.allLoaded = true;
  }
  const withDate = (dg) => (dg ? dg.stories.map((s) => Object.assign({ date: dg.date }, s)) : []);
  function windowDates() { const t = istToday(); return Array.from({ length: 7 }, (_, i) => addDays(t, -i)); }
  function last7Stories() { return windowDates().flatMap((d) => withDate(S.digests[d])); }
  const color = (cat) => (S.secBy[cat] || {}).color || "#888";

  // ---------- bookmarks (saved in this browser) ----------
  const BM = "dtd-bookmarks";
  const bookmarks = () => store.get(BM, []);
  const isSaved = (url) => bookmarks().some((b) => b.url === url);
  function toggleSave(story) {
    let b = bookmarks();
    if (b.some((x) => x.url === story.url)) { b = b.filter((x) => x.url !== story.url); toast("Removed from Saved"); }
    else {
      b.unshift({ url: story.url, id: story.id, summary: story.summary, source: story.source, category: story.category, image: story.image || null, date: story.date, created_at: new Date().toISOString() });
      toast("Saved ☆");
    }
    store.set(BM, b);
    $$(`[data-save="${CSS.escape(story.url)}"]`).forEach((el) => { const on = isSaved(story.url); el.classList.toggle("on", on); el.textContent = on ? "★" : "☆"; el.setAttribute("aria-pressed", on); });
  }

  // ---------- pieces ----------
  const REG = new Map(); // story key -> story object (for click handlers)
  function reg(s) { const k = s.id + "|" + (s.date || ""); REG.set(k, s); return k; }
  function media(s, cls = "") {
    const c = color(s.category);
    const ph = `<div class="ph ${cls}" style="--c:${c}"></div>`;
    if (!s.image) return ph;
    return `<img class="${cls}" src="${esc(s.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='${ph.replace(/"/g, "&quot;")}'">`;
  }
  function actions(s, k) {
    const on = isSaved(s.url);
    return `<div class="card-actions">
      <a class="act" href="${esc(s.url)}" target="_blank" rel="noopener" title="Open original" aria-label="Open original article">↗</a>
      <button class="act ${on ? "on" : ""}" type="button" data-save="${esc(s.url)}" data-k="${esc(k)}" aria-pressed="${on}" title="Bookmark" aria-label="Bookmark">${on ? "★" : "☆"}</button>
    </div>`;
  }
  function chip(cat) { const s = S.secBy[cat]; return s ? `<span class="chip" style="--c:${s.color}"><i></i>${esc(s.name)}</span>` : ""; }
  function storyCard(s, n, i = 0) {
    const k = reg(s);
    return `<article class="story surface tint rise" style="--c:${color(s.category)};animation-delay:${Math.min(i, 10) * 45}ms">
      <div class="thumb" data-open="${esc(k)}">${media(s)}</div>
      <div class="body">
        <div class="hd"><span class="num">${pad(n)}</span><h3 data-open="${esc(k)}">${esc(s.summary)}</h3></div>
        <div class="foot"><span class="src-label">${esc(s.source)}</span>${actions(s, k)}</div>
      </div></article>`;
  }
  function empty(title, text) { return `<div class="empty surface"><h3>${esc(title)}</h3><p>${text}</p></div>`; }
  function setActive(name) { $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === name)); }

  // ---------- pages ----------
  function pageHome() {
    setActive("home");
    const t = istToday();
    const latest = S.idx.latest;
    const dg = S.digests[t] || (latest && S.digests[latest]);
    if (!dg) {
      app.innerHTML = `<section class="hero"><div class="kicker">Latest edition</div><h1>${esc(fmtLong(t))}</h1></section>` +
        empty("No edition yet", "The first digest hasn't been generated. Run the <b>Daily Tech Digest</b> workflow (task: backfill) on GitHub, then reload.") + stylePicker();
      return;
    }
    const isToday = dg.date === t;
    const stories = withDate(dg);
    const byUrl = Object.fromEntries(stories.map((s) => [s.url, s]));
    let top = (dg.highlights || []).map((u) => byUrl[u]).filter(Boolean).slice(0, 5);
    if (top.length < 5) top = top.concat(stories.filter((s) => !top.includes(s) && s.rank === 1)).slice(0, 5);
    const week = last7Stories();
    const secCards = S.sections.map((sec, i) => {
      const inSec = week.filter((s) => s.category === sec.slug);
      const latestS = inSec.find((s) => s.image) || inSec[0];
      return `<a class="sec-card surface tint rise" href="#/c/${sec.slug}" style="--c:${sec.color};animation-delay:${i * 60}ms">
        <div class="thumb">${latestS ? media(latestS) : `<div class="ph" style="--c:${sec.color}"></div>`}</div>
        <div class="body"><h3><i></i>${esc(sec.name)}</h3><p class="blurb">${esc(sec.blurb)}</p>
          ${latestS ? `<p class="latest">${esc(latestS.summary)}</p>` : ""}
          <div class="meta"><span>${inSec.length} in the last 7 days</span><span class="open">Open section <span>→</span></span></div></div></a>`;
    }).join("");
    app.innerHTML = `
      <section class="hero rise">
        <div class="kicker">${isToday ? "Today's edition" : "Latest edition"} · ${stories.length} stories</div>
        <h1>${esc(fmtLong(dg.date))}</h1>
        <p class="intro">The day's most important tech stories, picked and summarised by AI across <b>5&nbsp;sections</b>. Fresh every morning at 06:30&nbsp;IST · no&nbsp;sign-up · no&nbsp;ads.</p>
      </section>
      <div class="section-head"><h2>Today's top 5</h2><a class="link-out" href="#/digest/${dg.date}">Full digest →</a></div>
      <div class="top-grid">${top.map((s, i) => { const k = reg(s); return `
        <article class="hl rise" style="--c:${color(s.category)};animation-delay:${i * 70}ms" data-open="${esc(k)}">
          <div class="media">${media(s)}</div>${actions(s, k)}
          <div class="hl-content"><span class="rank">${pad(i + 1)}</span>${chip(s.category)}
            <h3>${esc(s.summary)}</h3><div class="src">${esc(s.source)}</div></div>
        </article>`; }).join("")}</div>
      <div class="section-head"><h2>Sections</h2></div>
      <div class="sec-grid">${secCards}</div>
      ${stylePicker()}`;
  }

  function pageSection(slug) {
    setActive("");
    const sec = S.secBy[slug];
    if (!sec) { location.hash = "#/"; return; }
    const pills = `<div class="pills">${S.sections.map((s) => `<a class="pill ${s.slug === slug ? "active" : ""}" style="--c:${s.color}" href="#/c/${s.slug}"><i></i>${esc(s.name)}</a>`).join("")}</div>`;
    const groups = windowDates().map((d) => {
      const items = withDate(S.digests[d]).filter((s) => s.category === slug).sort((a, b) => a.rank - b.rank);
      if (!items.length) return "";
      return `<div class="date-group"><h2>${esc(relDay(d))} <small>${esc(fmtShort(d))} · ${items.length} stories</small></h2>
        <div class="story-grid">${items.map((s, i) => storyCard(s, i + 1, i)).join("")}</div></div>`;
    }).join("");
    app.innerHTML = `<div class="kicker">Section · last 7 days</div>
      <h1 class="page-title" style="--c:${sec.color}">${esc(sec.name)}</h1><p class="lede">${esc(sec.blurb)}</p>
      ${pills}${groups || empty("Nothing here yet", "No stories in this section in the last 7 days.")}`;
  }

  async function pageDigest(date) {
    setActive("");
    if (!S.digests[date]) await loadDates([date]);
    const dg = S.digests[date];
    if (!dg) { app.innerHTML = empty("No digest for that date", `There's no edition for ${esc(date)}. <a href="#/">Go to today</a>.`); return; }
    const stories = withDate(dg);
    const blocks = S.sections.map((sec) => {
      const items = stories.filter((s) => s.category === sec.slug).sort((a, b) => a.rank - b.rank);
      if (!items.length) return "";
      return `<section class="sec-block" style="--c:${sec.color}"><h2><i></i>${esc(sec.name)}</h2>
        <div class="story-grid">${items.map((s, i) => storyCard(s, i + 1, i)).join("")}</div></section>`;
    }).join("");
    const i = S.idx.dates.findIndex((r) => r.date === date);
    const prev = S.idx.dates[i + 1], next = S.idx.dates[i - 1];
    app.innerHTML = `<div class="kicker">Digest · ${stories.length} stories${dg.generated_by === "fallback" ? " · unranked (AI off)" : ""}</div>
      <h1 class="page-title">${esc(fmtLong(date))}</h1>
      <div class="pills">${prev ? `<a class="pill" href="#/digest/${prev.date}">← ${esc(fmtShort(prev.date))}</a>` : ""}${next && i > 0 ? `<a class="pill" href="#/digest/${next.date}">${esc(fmtShort(next.date))} →</a>` : ""}</div>
      ${blocks}`;
  }

  // ---------- search (keyword, over every past digest) ----------
  const STOP = new Set("a an the and or but if of to in on at by for with from as is are was were be been this that these those it its into what which who whom whose when where why how did does do done ship shipped any some about tell me show give latest news week today this there their they has have had new more most than".split(" "));
  const tokens = (s) => (String(s).toLowerCase().match(/[a-z0-9$₹%.+#-]+/g) || []).map((w) => w.replace(/^[.-]+|[.-]+$/g, "")).filter((w) => w && !STOP.has(w));
  const stem = (w) => w.replace(/(ing|ed|es|s)$/, "");
  async function pageSearch() {
    setActive("search");
    app.innerHTML = `<div class="kicker">Search</div><h1 class="page-title">Ask anything about the news</h1>
      <p class="lede">Answers come only from stories that appeared in past digests.</p>
      <form class="ask-box" id="search-form"><input class="input" id="q" type="search" placeholder="e.g. What did Anthropic ship this week?" autocomplete="off" aria-label="Your question">
      <button class="btn btn-primary" type="submit">Ask</button></form><div id="results"></div>`;
    const q0 = new URLSearchParams(location.hash.split("?")[1] || "").get("q");
    $("#search-form").addEventListener("submit", (e) => { e.preventDefault(); runSearch($("#q").value); });
    if (q0) { $("#q").value = q0; runSearch(q0); } else $("#q").focus();
  }
  async function runSearch(q) {
    q = q.trim(); if (!q) return;
    history.replaceState(null, "", "#/search?q=" + encodeURIComponent(q));
    $("#results").innerHTML = `<div class="skeleton" style="height:120px;margin-top:22px"></div>`;
    await loadAll();
    const all = Object.values(S.digests).flatMap(withDate);
    const ql = q.toLowerCase();
    let pool = all;
    const t = istToday();
    if (/\btoday\b/.test(ql)) pool = all.filter((s) => s.date === t);
    else if (/\byesterday\b/.test(ql)) pool = all.filter((s) => s.date === addDays(t, -1));
    else if (/\b(this|past|last) week\b/.test(ql)) pool = all.filter((s) => s.date >= addDays(t, -6));
    const qt = tokens(q).map(stem);
    const secHit = S.sections.filter((s) => qt.some((w) => s.name.toLowerCase().includes(w) && w.length > 3)).map((s) => s.slug);
    const scored = pool.map((s) => {
      const hay = tokens(s.summary + " " + s.source).map(stem);
      let sc = 0;
      qt.forEach((w) => { if (hay.includes(w)) sc += w.length > 3 ? 3 : 1.5; else if (hay.some((h) => h.length > 4 && w.length > 4 && (h.startsWith(w) || w.startsWith(h)))) sc += 1; });
      if (secHit.includes(s.category)) sc += 1;
      return { s, sc: sc ? sc + (6 - s.rank) * 0.05 + (s.date >= addDays(t, -6) ? 0.3 : 0) : 0 };
    }).filter((x) => x.sc > 0).sort((a, b) => b.sc - a.sc || (a.s.date < b.s.date ? 1 : -1));
    const seen = new Set(); const hits = [];
    scored.forEach(({ s }) => { if (!seen.has(s.url)) { seen.add(s.url); hits.push(s); } });
    const top = hits.slice(0, 12);
    const answer = top.length
      ? `<div class="answer surface"><div class="kicker">Answer · from your digests</div>
          <ul>${top.slice(0, 5).map((s) => `<li><b>${esc(s.summary)}</b> <span class="note">— ${esc(s.source)}, ${esc(fmtShort(s.date))}</span></li>`).join("")}</ul>
          <p class="note" style="margin:10px 0 0">Keyword match over past headlines (no AI on this free site).</p></div>`
      : `<div class="answer surface"><div class="kicker">No match</div>Nothing in past digests matched that. Try a company or product name.</div>`;
    $("#results").innerHTML = answer + `<div class="section-head" style="margin-top:10px"><h2>Matching stories</h2><span class="kicker">Searched ${all.length} stories</span></div>
      <div class="story-grid">${top.map((s, i) => storyCard(s, i + 1, i)).join("")}</div>`;
  }

  function pageSaved() {
    setActive("saved");
    const b = bookmarks();
    const blocks = S.sections.map((sec) => {
      const items = b.filter((x) => x.category === sec.slug);
      if (!items.length) return "";
      return `<section class="sec-block" style="--c:${sec.color}"><h2><i></i>${esc(sec.name)} <span class="kicker">${items.length}</span></h2>
        <div class="story-grid">${items.map((s, i) => storyCard(s, i + 1, i).replace('<div class="foot">', `<div class="foot"><button class="pill" type="button" data-remove="${esc(s.url)}">Remove</button>`)).join("")}</div></section>`;
    }).join("");
    app.innerHTML = `<div class="kicker">Saved · ${b.length} stories</div><h1 class="page-title">Saved stories</h1>
      <p class="lede">Bookmarks are kept in this browser.</p>${blocks || empty("Nothing saved yet", "Tap ☆ on any story to keep it here.")}`;
  }

  async function pageRecap() {
    setActive("recap");
    app.innerHTML = `<div class="skeleton"></div>`;
    const r = await getJSON("recap.json", true);
    if (!r || !r.items || !r.items.length) {
      app.innerHTML = `<div class="kicker">Weekly recap</div><h1 class="page-title">This week</h1>` +
        empty("No recap yet", "The recap is built every Sunday at 18:30 IST. You can also run the workflow with task <b>recap</b> on GitHub.");
      return;
    }
    const blocks = S.sections.map((sec) => {
      const items = r.items.filter((i) => i.category === sec.slug).sort((a, b) => a.rank - b.rank);
      if (!items.length) return "";
      return `<section class="sec-block" style="--c:${sec.color}"><h2><i></i>${esc(sec.name)}</h2><div class="recap-list">
        ${items.map((it, i) => { const k = reg(it); return `<article class="recap-item surface tint rise" style="--c:${sec.color};animation-delay:${i * 50}ms">
          <div class="num">${pad(it.rank)}</div><div><h3 data-open="${esc(k)}">${esc(it.summary)}</h3><p class="why">${esc(it.why)}</p>
          <div class="foot" style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="src-label">${esc(it.source)} · ${esc(fmtShort(it.date))}</span>
          <a class="link-out" href="${esc(it.url)}" target="_blank" rel="noopener">Read ↗</a></div></div></article>`; }).join("")}</div></section>`;
    }).join("");
    app.innerHTML = `<div class="kicker">Weekly recap · ${esc(fmtShort(r.week_start))} – ${esc(fmtShort(r.week_end))}</div>
      <h1 class="page-title">The week in tech</h1><p class="lede">Top 5 stories per section, and why each one matters.</p>${blocks}`;
  }

  // ---------- quiz ----------
  const LEVELS = { easy: ["Easy", "Who launched what"], medium: ["Medium", "Names, numbers, details"], hard: ["Hard", "Specifics & connections"] };
  const NOT_NAMES = new Set("The A An And Or For To In On At Of With From How Why What Who When New AI It Its This That These Says Said After Before Over Into Up By As Is Are Be Can Will Why Top Best First Next More Than Your Our We I Day Week Year US UK EU CEO CFO IPO API App Apps Pro Max Plus Mini Ultra".split(" "));
  const AMOUNT_RE = /(?:[$₹€£]\s?\d[\d,.]*\s?(?:[KMBT]|bn|mn|billion|million|crore|lakh|trillion)?|\b\d[\d,.]*\s?(?:%|percent|crore|lakh|billion|million|bn|mn|[KMB]\b|x\b|GB|TB|MP|nm|M\b|B\b))/gi;
  function nameTokens(h) {
    // proper nouns, joining runs like "Ola Electric" or "Swiggy Instamart" into one answer
    const words = h.split(/\s+/);
    const out = []; let run = [];
    const flush = () => { if (run.length) out.push(run.join(" ")); run = []; };
    words.forEach((raw) => {
      const w = raw.replace(/^[“"'(]+|[”"'),:;!?]+$/g, "").replace(/'s$/, "");
      const isName = (/^[A-Z][A-Za-z0-9&'.+-]*[A-Za-z0-9]$/.test(w) || /^[a-z]+[A-Z][A-Za-z0-9]+$/.test(w)) && !NOT_NAMES.has(w);
      if (isName) { run.push(w); if (/[,:;]$/.test(raw)) flush(); } else flush();
    });
    flush();
    return out.filter((w) => w.length > 1);
  }
  function fallbackQuiz(stories, level) {
    const names = new Set(), amounts = new Set();
    stories.forEach((s) => { nameTokens(s.summary).forEach((n) => names.add(n)); (s.summary.match(AMOUNT_RE) || []).forEach((a) => amounts.add(a.trim())); });
    const qs = [];
    shuffle(stories).forEach((s) => {
      if (qs.length >= 10) return;
      let target = null, pool = null, kind = "name";
      const am = s.summary.match(AMOUNT_RE);
      const nm = nameTokens(s.summary);
      if (level === "hard" && am) { target = am[0].trim(); pool = [...amounts]; kind = "amount"; }
      else if (nm.length) { target = level === "easy" ? nm[0] : nm[Math.floor(Math.random() * nm.length)]; pool = [...names]; }
      else if (am) { target = am[0].trim(); pool = [...amounts]; kind = "amount"; }
      if (!target) return;
      let distract = shuffle(pool.filter((p) => p.toLowerCase() !== target.toLowerCase() && !s.summary.includes(p))).slice(0, 3);
      if (kind === "amount") while (distract.length < 3) {
        const v = target.replace(/\d[\d,.]*/, (n) => { const x = parseFloat(n.replace(/,/g, "")); const f = [0.5, 2, 3, 1.5, 0.25][distract.length + Math.floor(Math.random() * 2)]; const y = Math.round(x * f * 10) / 10; return String(y === x ? x + 1 : y); });
        if (v !== target && !distract.includes(v)) distract.push(v); else break;
      }
      if (distract.length < 3) return;
      const opts = shuffle([target, ...distract]);
      qs.push({
        question: `Fill in the blank: “${s.summary.replace(target, "_____")}”`,
        options: opts, answer_index: opts.indexOf(target),
        explanation: `The headline: “${s.summary}”.`, category: s.category, source: s.source, url: s.url, story_date: s.date,
      });
    });
    return qs;
  }
  let QZ = null; // running quiz state
  function pageQuiz() {
    setActive("quiz");
    stopTimer();
    const lv = store.raw("dtd-quiz-level") || "medium";
    const chosen = new Set(store.get("dtd-quiz-secs", []));
    app.innerHTML = `<div class="kicker">Quiz · last 7 days</div><h1 class="page-title">Rapid-fire news quiz</h1>
      <p class="lede">10 questions · 20 seconds each · press 1–4 to answer.</p>
      <div class="quiz-card surface">
        <div class="kicker">Difficulty</div>
        <div class="opt-row levels">${Object.entries(LEVELS).map(([k, [n, d]]) => `<button type="button" class="choice ${k === lv ? "sel" : ""}" data-level="${k}"><span><b>${n}</b><small>${d}</small></span></button>`).join("")}</div>
        <div class="kicker" style="margin-top:22px">Sections <span style="text-transform:none;letter-spacing:0">(optional — none means all)</span></div>
        <div class="pills" style="flex-wrap:wrap;margin-top:8px">${S.sections.map((s) => `<button type="button" class="pill ${chosen.has(s.slug) ? "active" : ""}" style="--c:${s.color}" data-sec="${s.slug}"><i></i>${esc(s.name)}</button>`).join("")}</div>
        <label style="display:flex;gap:8px;align-items:center;margin:8px 0 20px;font-size:14px"><input type="checkbox" id="newset"> Give me a new set of questions</label>
        <button class="btn btn-primary" id="start" type="button">Start quiz →</button>
      </div>`;
    $$("[data-level]").forEach((b) => b.addEventListener("click", () => { $$("[data-level]").forEach((x) => x.classList.remove("sel")); b.classList.add("sel"); store.rawSet("dtd-quiz-level", b.dataset.level); }));
    $$("[data-sec]").forEach((b) => b.addEventListener("click", () => { b.classList.toggle("active"); store.set("dtd-quiz-secs", $$("[data-sec].active").map((x) => x.dataset.sec)); }));
    $("#start").addEventListener("click", startQuiz);
  }
  async function startQuiz() {
    const level = ($("[data-level].sel") || {}).dataset?.level || "medium";
    const secs = $$("[data-sec].active").map((x) => x.dataset.sec);
    const fresh = $("#newset").checked;
    const stories = last7Stories().filter((s) => !secs.length || secs.includes(s.category));
    if (stories.length < 5) { toast("Need at least 5 stories for a quiz. Pick more sections."); return; }
    const key = `dtd-quiz:${istToday()}:${level}:${secs.slice().sort().join(",") || "all"}`;
    let qs = !fresh && store.get(key, null);
    if (!qs || !qs.length) {
      const ai = await getJSON("quiz.json", true);
      let aiQs = [];
      if (ai && ai.date >= addDays(istToday(), -1) && Array.isArray(ai[level])) aiQs = ai[level].filter((q) => !secs.length || secs.includes(q.category));
      qs = shuffle(aiQs).slice(0, 10);
      if (qs.length < 10) qs = qs.concat(fallbackQuiz(stories, level).filter((f) => !qs.some((q) => q.url === f.url))).slice(0, 10);
      if (qs.length < 3) { toast("Not enough material for a quiz yet."); return; }
      store.set(key, qs);
    }
    QZ = { qs, i: 0, score: 0, answered: false, level };
    showQ();
  }
  let TMR = null;
  function stopTimer() { if (TMR) { clearInterval(TMR); TMR = null; } }
  function showQ() {
    stopTimer();
    const q = QZ.qs[QZ.i];
    const C = 2 * Math.PI * 25;
    app.innerHTML = `<div class="quiz-card surface rise">
      <div class="qprog"><span style="width:${(QZ.i / QZ.qs.length) * 100}%"></span></div>
      <div class="q-top"><div><div class="kicker">Question ${QZ.i + 1} of ${QZ.qs.length} · ${LEVELS[QZ.level][0]}</div><h2 style="margin-top:8px">${esc(q.question)}</h2></div>
        <div class="timer" id="timer"><svg viewBox="0 0 58 58"><circle class="track" cx="29" cy="29" r="25"/><circle class="bar" cx="29" cy="29" r="25" stroke-dasharray="${C}" stroke-dashoffset="0"/></svg><span>20</span></div></div>
      <div class="opt-row">${q.options.map((o, i) => `<button type="button" class="choice" data-opt="${i}"><span class="k">${i + 1}</span><span>${esc(o)}</span></button>`).join("")}</div>
      <div id="fb"></div></div>`;
    $$("[data-opt]").forEach((b) => b.addEventListener("click", () => answer(+b.dataset.opt)));
    let left = 20;
    const bar = $("#timer .bar"), lbl = $("#timer span");
    TMR = setInterval(() => {
      left--; lbl.textContent = left; bar.style.strokeDashoffset = C * (1 - left / 20);
      $("#timer").classList.toggle("low", left <= 5);
      if (left <= 0) answer(-1);
    }, 1000);
    QZ.answered = false;
  }
  function answer(i) {
    if (!QZ || QZ.answered) return;
    QZ.answered = true; stopTimer();
    const q = QZ.qs[QZ.i];
    const ok = i === q.answer_index;
    if (ok) QZ.score++;
    $$("[data-opt]").forEach((b, j) => { b.disabled = true; if (j === q.answer_index) b.classList.add("correct"); else if (j === i) b.classList.add("wrong"); });
    const head = i === -1 ? "Time's up" : ok ? "Correct" : "Not quite";
    const last = QZ.i === QZ.qs.length - 1;
    $("#fb").innerHTML = `<div class="feedback rise"><b>${head}</b>${esc(q.explanation || "")}
      <div style="margin-top:8px"><a class="link-out" href="${esc(q.url)}" target="_blank" rel="noopener">${esc(q.source)} · ${esc(fmtShort(q.story_date))} ↗</a></div></div>
      <button class="btn btn-primary" id="next" type="button" style="margin-top:16px">${last ? "See results" : "Next question"} →</button>`;
    $("#next").addEventListener("click", nextQ); $("#next").focus();
  }
  function nextQ() {
    if (!QZ) return;
    if (QZ.i < QZ.qs.length - 1) { QZ.i++; showQ(); return; }
    const pct = QZ.score / QZ.qs.length;
    const verdict = pct === 1 ? "Perfect. You read everything." : pct >= 0.8 ? "Sharp — you're on top of the news." : pct >= 0.5 ? "Solid. A few stories slipped past." : pct >= 0.3 ? "Time for a catch-up read." : "Fresh start — open today's digest.";
    app.innerHTML = `<div class="quiz-card surface rise"><div class="kicker">Results · ${LEVELS[QZ.level][0]}</div>
      <div class="score-big">${QZ.score}/${QZ.qs.length}</div><h2>${verdict}</h2>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:22px"><a class="btn btn-primary" href="#/quiz">Play again</a><a class="btn" href="#/">Read today's digest</a></div></div>`;
    QZ = null;
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePanel();
    if (!QZ || e.target.matches("input,textarea")) return;
    if (!QZ.answered && /^[1-4]$/.test(e.key)) answer(+e.key - 1);
    else if (QZ.answered && e.key === "Enter" && document.activeElement?.id !== "next") nextQ();
  });

  // ---------- detail panel ----------
  const panel = $("#panel"), pbody = $("#panel-body");
  let lastFocus = null;
  async function openStory(s) {
    lastFocus = document.activeElement;
    const k = reg(s);
    pbody.innerHTML = `<div class="panel-top"><span class="kicker">${chip(s.category)}</span><button class="icon-btn" data-close aria-label="Close">✕</button></div>
      <div class="hero-img">${media(s)}</div><h2>${esc(s.summary)}</h2>
      <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap"><span class="src-label">${esc(s.source)}${s.date ? " · " + esc(fmtShort(s.date)) : ""}</span>
      <a class="link-out" href="${esc(s.url)}" target="_blank" rel="noopener">Read the original ↗</a>
      <button class="act ${isSaved(s.url) ? "on" : ""}" style="background:var(--muted);color:var(--fg)" data-save="${esc(s.url)}" data-k="${esc(k)}">${isSaved(s.url) ? "★" : "☆"}</button></div>
      <div id="pd"><div class="skeleton" style="height:140px;margin-top:22px"></div></div>`;
    panel.classList.add("open"); panel.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    $("[data-close]", pbody).focus();
    const d = (s.id && (await getJSON("stories/" + s.id + ".json"))) || { detailed: [], sentences: [] };
    const sents = d.sentences || [];
    const sum = (d.detailed || []).length
      ? `<h4>${d.detail_kind === "ai" ? "Detailed summary" : "Extractive summary · key sentences from the article"}</h4><ul class="sum">${d.detailed.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`
      : `<h4>Summary</h4><p class="note">The article text couldn't be fetched (it may be paywalled). Open the original to read it.</p>`;
    $("#pd").innerHTML = sum + `<h4>Ask about this story</h4>
      <div class="chips">${["What are the key numbers here?", "Who does this compete with?", "What does this mean for product teams?"].map((c) => `<button type="button" data-ask="${esc(c)}">${esc(c)}</button>`).join("")}</div>
      <div class="chat" id="chat"></div>
      <form class="ask-box" id="ask-form"><input class="input" id="ask-q" placeholder="Ask a question about this article" autocomplete="off" aria-label="Question"><button class="btn btn-primary" type="submit">Ask</button></form>
      <p class="note">Answers quote the most relevant sentences from the article.</p>`;
    const ask = (q) => {
      q = q.trim(); if (!q) return;
      const chat = $("#chat");
      chat.insertAdjacentHTML("beforeend", `<div class="msg me">${esc(q)}</div>`);
      const ans = answerFromSentences(q, sents, s);
      chat.insertAdjacentHTML("beforeend", `<div class="msg bot rise">${ans}</div>`);
      chat.lastElementChild.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    $$("[data-ask]", pbody).forEach((b) => b.addEventListener("click", () => ask(b.dataset.ask)));
    $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); ask($("#ask-q").value); $("#ask-q").value = ""; });
  }
  function answerFromSentences(q, sents, s) {
    if (!sents.length) return "I couldn't read this article's text, so I can't answer from it. Try the original link.";
    const ql = q.toLowerCase();
    let scoreFn;
    if (/number|figure|stat|how much|how many|price|cost|valuation|revenue/.test(ql)) scoreFn = (x) => (x.match(/\d/g) || []).length + (/[$₹€%]|million|billion|crore|lakh/i.test(x) ? 4 : 0);
    else if (/compet|rival|versus|vs\b|alternative/.test(ql)) scoreFn = (x) => (/compet|rival|versus|\bvs\b|against|market|alternative|lead|share/i.test(x) ? 4 : 0) + nameTokens(x).length * 0.4;
    else if (/product team|mean for|implication|why .*matter|pm\b/.test(ql)) scoreFn = (x) => (/product|user|customer|feature|launch|pricing|developer|team|build|adopt|platform|roll/i.test(x) ? 4 : 0) + (/will|plan|expect|could/i.test(x) ? 1 : 0);
    else { const qt = tokens(q).map(stem); scoreFn = (x) => { const h = tokens(x).map(stem); return qt.reduce((a, w) => a + (h.includes(w) ? (w.length > 3 ? 2 : 1) : 0), 0); }; }
    const ranked = sents.map((x, i) => ({ x, i, sc: scoreFn(x) })).filter((r) => r.sc > 0).sort((a, b) => b.sc - a.sc).slice(0, 3).sort((a, b) => a.i - b.i);
    if (!ranked.length) return "The article doesn't seem to say anything about that.";
    return `From the article:<ul>${ranked.map((r) => `<li>${esc(r.x)}</li>`).join("")}</ul>`;
  }
  function closePanel() {
    if (!panel.classList.contains("open")) return;
    panel.classList.remove("open"); panel.setAttribute("aria-hidden", "true"); document.body.style.overflow = "";
    if (lastFocus) lastFocus.focus?.();
  }
  panel.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closePanel(); });

  // ---------- global clicks ----------
  document.addEventListener("click", (e) => {
    const sv = e.target.closest("[data-save]");
    if (sv) { e.preventDefault(); e.stopPropagation(); const s = REG.get(sv.dataset.k) || bookmarks().find((b) => b.url === sv.dataset.save); if (s) toggleSave(s); return; }
    const rm = e.target.closest("[data-remove]");
    if (rm) { store.set(BM, bookmarks().filter((b) => b.url !== rm.dataset.remove)); toast("Removed from Saved"); pageSaved(); return; }
    if (e.target.closest(".act")) return; // ↗ link
    const op = e.target.closest("[data-open]");
    if (op) { const s = REG.get(op.dataset.open); if (s) openStory(s); }
    const st = e.target.closest("[data-style-pick]");
    if (st) setStyle(st.dataset.stylePick);
  });

  // ---------- styles & theme ----------
  const STYLES = { classic: "Classic", glass: "Soft Glass", pop: "Vibrant Pop", brutal: "Bold Brutalist" };
  function stylePicker() {
    const cur = document.documentElement.dataset.style;
    return `<div class="style-picker"><span class="kicker">Site style</span>${Object.entries(STYLES).map(([k, n]) => `<button type="button" class="${k === cur ? "on" : ""}" data-style-pick="${k}">${n}</button>`).join("")}</div>`;
  }
  function applyTheme() {
    const st = document.documentElement.dataset.style;
    const t = store.raw("dtd-theme");
    const dark = st === "classic" && (t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }
  function setStyle(s) {
    if (!STYLES[s]) return;
    store.rawSet("dtd-style", s);
    document.documentElement.dataset.style = s;
    const fl = $("#font-link"); if (fl && window.__DTD_FONTS) fl.href = "https://fonts.googleapis.com/css2?family=" + window.__DTD_FONTS[s] + "&display=swap";
    applyTheme();
    $$(".style-picker button").forEach((b) => b.classList.toggle("on", b.dataset.stylePick === s));
  }
  $("#theme-btn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark";
    store.rawSet("dtd-theme", dark ? "light" : "dark"); applyTheme();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", applyTheme);

  // ---------- toast & refresh ----------
  let toastT = null;
  function toast(msg, ms = 2600) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), ms); }
  const rb = $("#refresh-btn");
  rb.addEventListener("click", async () => {
    const last = +(store.raw("dtd-refresh-at") || 0);
    const wait = 60 - Math.floor((Date.now() - last) / 1000);
    if (wait > 0) { toast(`Please wait ${wait}s before refreshing again.`); return; }
    store.rawSet("dtd-refresh-at", String(Date.now()));
    const before = S.idx && S.idx.generated_at;
    if (S.idx && S.idx.refresh_url) {
      window.open(S.idx.refresh_url, "_blank", "noopener");
      toast("On GitHub, click “Run workflow”. This page updates itself when the new edition is live (≈3–5 min).", 6500);
    }
    $("#progress").hidden = false; rb.classList.add("running"); rb.disabled = true;
    setTimeout(() => { rb.disabled = false; }, 60000);
    const started = Date.now();
    const poll = async () => {
      const idx = await getJSON("index.json", true);
      if (idx && idx.generated_at !== before) {
        $("#progress").hidden = true; rb.classList.remove("running");
        S.digests = {}; S.allLoaded = false; await loadCore(true); route();
        toast("Fresh edition loaded ✓"); return;
      }
      if (Date.now() - started > 10 * 60000) { $("#progress").hidden = true; rb.classList.remove("running"); toast("No new edition yet. Check the workflow on GitHub."); return; }
      setTimeout(poll, 20000);
    };
    if (S.idx && S.idx.refresh_url) setTimeout(poll, 20000);
    else { await loadCore(true); $("#progress").hidden = true; rb.classList.remove("running"); route(); toast("Reloaded the latest data"); }
  });

  // ---------- router ----------
  function route() {
    closePanel(); stopTimer(); if (QZ && !location.hash.startsWith("#/quiz")) QZ = null;
    const h = location.hash.replace(/^#/, "") || "/";
    const [path] = h.split("?");
    const parts = path.split("/").filter(Boolean);
    window.scrollTo(0, 0);
    if (!parts.length) pageHome();
    else if (parts[0] === "c") pageSection(parts[1]);
    else if (parts[0] === "digest") pageDigest(parts[1]);
    else if (parts[0] === "search") pageSearch();
    else if (parts[0] === "saved") pageSaved();
    else if (parts[0] === "recap") pageRecap();
    else if (parts[0] === "quiz") pageQuiz();
    else pageHome();
  }
  window.addEventListener("hashchange", () => { if (location.hash.startsWith("#/search?")) return; route(); });

  (async function init() {
    app.innerHTML = `<div class="skeleton" style="height:90px;margin-bottom:24px;max-width:520px"></div><div class="skeleton"></div>`;
    await loadCore(false);
    route();
  })();
})();
