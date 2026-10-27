"use strict";
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const API_DEFAULT = `${window.location.protocol}//${window.location.hostname}${["5500", "5501"].includes(window.location.port) ? ":8000" : ""}/api/v1`;
const savedPage = localStorage.getItem("antifraudCurrentPage");
const state = {
  page: savedPage || "dashboard",
  callsPage: 1,
  alertsPage: 1,
  callsPages: 0,
  alertsPages: 0,
  dashboardRefreshStatus: null,
};
const titles = {
  dashboard: [
    "Обзор антифрода",
    "Сводная картина вызовов и выявленных рисков.",
  ],
  calls: ["Журнал вызовов", "Поиск и просмотр записей CDR."],
  alerts: [
    "Подозрительные события",
    "События, которые требуют внимания аналитика.",
  ],
  subscriber: [
    "Профиль абонента",
    "История активности и связи выбранного номера.",
  ],
  analysis: [
    "Аналитические задачи",
    "Запуск обработки данных за выбранный период.",
  ],
  prediction: ["Прогноз звонка", "Оценка риска для одной записи CDR."],
  model: [
    "Модель и сервис",
    "Состояние API, базы данных и модели классификации.",
  ],
};
if (!Object.prototype.hasOwnProperty.call(titles, state.page)) {
  state.page = "dashboard";
}
const analysisStatusNames = {
  queued: "В очереди",
  running: "Запущено",
  completed: "Выполнено",
  failed: "Провалено",
  cancelled: "Отменено",
};
const riskNames = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
};
const scenarioNames = {
  S1: "S1 • Wangiri",
  S2: "S2 • Массовый обзвон (робот)",
  S3: "S3 • SIM-box",
  S4: "S4 • Клон SIM / смена IMSI",
  S5: "S5 • Цепочка переадресаций",
  S6: "S6 • Карусель",
  S7: "S7 • Вишинг со спуфингом",
};
const recommendationNames = {
  monitor: "Наблюдать",
  manual_review: "Ручная проверка",
  escalate: "Эскалация",
};
const typeNames = {
  "01": "Исходящий",
  "02": "Входящий",
  "03": "Переадресованный",
};
const operatorPrefixes = {
  842: "Городские (АВС)",
  499: "Городские (АВС)",
  892: "Городские (АВС)",
  "025": "Альфа",
  "026": "Альфа",
  "027": "Альфа",
  899: "Барбетта",
  810: "Барбетта",
  834: "Барбетта",
  210: "Bell-ka",
  214: "Bell-ka",
  200: "Bell-ka",
};
const esc = (s) =>
  String(s ?? "—").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (n) => Number(n || 0).toLocaleString("ru-RU");
const pct = (n) =>
  n == null
    ? "—"
    : (Number(n) * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 }) +
      "%";
const date = (v) =>
  v
    ? new Date(v).toLocaleString("ru-RU", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "—";
const val = (v) => (v == null || v === "" ? "—" : v);
const scenarioName = (scenario) => scenarioNames[scenario] || scenario || "—";
const recommendationName = (recommendation) =>
  recommendationNames[recommendation] || recommendation || "—";
function phoneMarkup(msisdn) {
  const value = String(msisdn ?? "—");
  const prefix = value.replace(/\D/g, "").slice(0, 3);
  const operator = operatorPrefixes[prefix];
  return `${esc(value)}${operator ? ` <span class="operator-label">· ${esc(operator)}</span>` : ""}`;
}
function base() {
  return (localStorage.getItem("antifraudApiBase") || API_DEFAULT).replace(
    /\/+$/,
    "",
  );
}
async function api(path, opts = {}, clearNoticeOnSuccess = true) {
  let r;
  try {
    r = await fetch(base() + path, {
      ...opts,
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    });
  } catch {
    throw new Error(
      "Не удалось подключиться к Backend. Проверьте адрес API и запущен ли сервер: " +
        base(),
    );
  }
  let d;
  try {
    d = await r.json();
  } catch {
    throw new Error("Backend вернул ответ, который не удалось прочитать.");
  }
  if (!r.ok)
    throw new Error(d.message || d.detail || `Ошибка API (${r.status})`);
  if (clearNoticeOnSuccess) notice("");
  return d;
}
function data(d) {
  return d && Object.prototype.hasOwnProperty.call(d, "data") ? d.data : d;
}
function toast(s) {
  $("#toast").textContent = s;
  $("#toast").hidden = false;
  setTimeout(() => ($("#toast").hidden = true), 3200);
}
function notice(s) {
  $("#notice").textContent = s;
  $("#notice").hidden = !s;
}
async function withLoading(button, task) {
  if (!button || button.disabled) return;
  const old = button.innerHTML;
  button.disabled = true;
  button.classList.add("is-loading");
  button.setAttribute("aria-busy", "true");
  try {
    return await task();
  } finally {
    if (
      !["calls-prev", "calls-next", "alerts-prev", "alerts-next"].includes(
        button.id,
      )
    )
      button.disabled = false;
    button.classList.remove("is-loading");
    button.removeAttribute("aria-busy");
    button.innerHTML = old;
  }
}
function setPage(p) {
  if (!Object.prototype.hasOwnProperty.call(titles, p)) return;
  state.page = p;
  localStorage.setItem("antifraudCurrentPage", p);
  $$(".page").forEach((x) => (x.hidden = x.id !== "page-" + p));
  $$(".nav-link").forEach((x) =>
    x.classList.toggle("active", x.dataset.page === p),
  );
  $("#page-title").textContent = titles[p][0];
  $("#page-desc").textContent = titles[p][1];
  notice("");
  loadPage().catch((e) => notice(e.message));
}
$$(".nav-link").forEach((b) =>
  b.addEventListener("click", () => setPage(b.dataset.page)),
);
$("#refresh").addEventListener("click", () =>
  withLoading($("#refresh"), async () => {
    try {
      await loadPage();
      toast("Данные обновлены");
    } catch (e) {
      notice(e.message);
    }
  }),
);
$("#docs-link").href = base().replace(/\/api\/v1$/, "") + "/docs";
async function health() {
  try {
    const h = data(await api("/health", {}, false));
    const ok = h.status === "ok";
    $("#health-dot").parentElement.className =
      "connection " + (ok ? "ok" : "failed");
    $("#health-label").textContent = ok ? "Backend доступен" : "Есть проблемы";
    $("#health-details").innerHTML =
      `<div class="health-item"><span>Общий статус</span><strong class="${ok ? "status-ok" : "status-bad"}">${esc(h.status)}</strong></div><div class="health-item"><span>База данных</span><strong class="${h.database?.status === "ok" ? "status-ok" : "status-bad"}">${esc(h.database?.status)}</strong></div><div class="health-item"><span>Модель</span><strong class="${h.model?.status === "ok" ? "status-ok" : "status-bad"}">${esc(h.model?.status)}</strong></div>`;
    return h;
  } catch (e) {
    $("#health-dot").parentElement.className = "connection failed";
    $("#health-label").textContent = "Backend недоступен";
    $("#health-details").innerHTML = `<p class="notice">${esc(e.message)}</p>`;
    throw e;
  }
}
async function dashboard() {
  const d = data(await api("/dashboard/summary"));
  $("#total-calls").textContent = num(d.total_calls);
  $("#analyzed-calls").textContent = num(d.analyzed_calls);
  $("#suspicious-calls").textContent = num(d.suspicious_calls);
  $("#suspicious-subs").textContent = num(d.suspicious_subscribers);
  const rd = d.risk_distribution || {},
    max = Math.max(1, ...Object.values(rd).map(Number));
  const colors = {
    low: "#27876d",
    medium: "#c28a2c",
    high: "#d85b61",
    critical: "#a92736",
  };
  $("#risk-bars").innerHTML = Object.entries({
    low: "Низкий",
    medium: "Средний",
    high: "Высокий",
    critical: "Критический",
  })
    .map(
      ([k, n]) =>
        `<div class="risk-row"><span>${n}</span><div class="track"><span style="width:${Math.max(0, (Number(rd[k] || 0) / max) * 100)}%;background:${colors[k]}"></span></div><strong>${num(rd[k])}</strong></div>`,
    )
    .join("");
  const t = d.timeline || [],
    tm = $("#timeline");
  if (!t.length) {
    tm.innerHTML =
      '<div class="empty">Нет данных для отображения динамики.</div>';
    return;
  }
  const maxT = Math.max(1, ...t.map((x) => Number(x.total_calls || 0)));
  tm.innerHTML =
    `<div class="timeline-plot">${t
      .map(
        (x) =>
          `<div class="timeline-col" title="${esc(date(x.timestamp))}: ${num(x.total_calls)} вызовов"><div class="timeline-bars"><i style="height:${Math.max(2, (Number(x.total_calls || 0) / maxT) * 100)}%"></i><i style="height:${Math.max(2, (Number(x.suspicious_calls || 0) / maxT) * 100)}%"></i></div><small>${esc(new Date(x.timestamp).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }))}</small></div>`,
      )
      .join("")}</div>` +
    `<div class="legend"><span><i style="background:#f28fa0"></i>Все звонки</span><span><i style="background:#d95c73"></i>Подозрительные</span></div>`;
}
async function refreshDashboardStatus() {
  const response = data(await api("/dashboard/refresh-status", {}, false));
  const status = response?.status || "idle";
  const previous = state.dashboardRefreshStatus;
  state.dashboardRefreshStatus = status;
  const banner = $("#dashboard-refresh-banner");
  banner.hidden = status === "idle";
  banner.textContent =
    status === "refreshing"
      ? "Анализ завершён. Обновляем статистику дашборда…"
      : status === "failed"
        ? "Анализ завершён, но обновить статистику дашборда не удалось. Данные могут быть устаревшими."
        : "";
  if (previous === "refreshing" && status === "idle" && state.page === "dashboard") {
    await dashboard();
  }
}
function query(form) {
  const p = new URLSearchParams(new FormData(form));
  for (const [k, v] of [...p]) if (!v.trim()) p.delete(k);
  return p.toString();
}
async function calls() {
  const f = $("#calls-filter"),
    q = query(f);
  const d = data(
    await api(
      "/calls?" +
        q +
        (q ? "&" : "") +
        "page=" +
        state.callsPage +
        "&page_size=20",
    ),
  );
  state.callsPages = d.pages;
  notice("");
  $("#calls-count").textContent = `Записей: ${num(d.total)}`;
  $("#calls-page").textContent = `${d.page} / ${Math.max(1, d.pages)}`;
  $("#calls-prev").disabled = d.page <= 1;
  $("#calls-next").disabled = d.page >= d.pages;
  $("#calls-body").innerHTML = d.items.length
    ? d.items
        .map(
          (x) =>
            `<tr><td>${esc(date(x.call_time))}</td><td>${phoneMarkup(x.msisdn_a)}</td><td>${phoneMarkup(x.msisdn_b)}</td><td>${esc(typeNames[x.call_type] || x.call_type || "—")}</td><td>${num(x.duration_seconds)} с</td><td>${pct(x.risk_score)}</td><td>${risk(x.risk_level)}</td><td><button class="link-button" data-call="${x.id}">Подробнее</button></td></tr>`,
        )
        .join("")
    : '<tr><td colspan="8" class="empty">Записи не найдены.</td></tr>';
  $$("[data-call]").forEach((b) =>
    b.addEventListener("click", () => callDetail(b.dataset.call)),
  );
}
function risk(level) {
  return level
    ? `<span class="risk-pill ${esc(level)}">${esc(riskNames[level] || level)}</span>`
    : "—";
}
async function callDetail(id) {
  const d = data(await api("/calls/" + id));
  $("#dialog-content").innerHTML = `<div class="detail-grid">${[
    ["ID", d.id],
    ["Тип", typeNames[d.call_type] || d.call_type],
    ["Дата", date(d.call_time)],
    ["Длительность", num(d.duration_seconds) + " сек."],
    ["Номер A", d.msisdn_a],
    ["Номер B", d.msisdn_b],
    ["IMSI A", d.imsi_a],
    ["Номер C", d.msisdn_c],
    ["Риск", pct(d.risk_score)],
    ["Уровень", riskNames[d.risk_level] || d.risk_level],
    ["Сценарий", scenarioName(d.fraud_scenario)],
    ["Рекомендация", recommendationName(d.recommendation)],
  ]
    .map(
      ([k, v]) =>
        `<div class="detail-cell"><small>${esc(k)}</small><strong>${k.startsWith("Номер") ? phoneMarkup(v) : esc(val(v))}</strong></div>`,
    )
    .join(
      "",
    )}</div><div class="subsection"><h3>Причины оценки</h3>${d.reasons?.length ? `<ul class="reasons">${d.reasons.map((x) => `<li>${esc(x.description || x.reason || JSON.stringify(x))}</li>`).join("")}</ul>` : "<p>Причины не указаны.</p>"}</div>`;
  $("#call-dialog").showModal();
}
$("#dialog-close").onclick = () => $("#call-dialog").close();
$("#calls-filter").addEventListener("submit", (e) => {
  e.preventDefault();
  state.callsPage = 1;
  calls().catch((err) => notice(err.message));
});
$("#calls-prev").onclick = () => {
  if (state.callsPage > 1)
    withLoading($("#calls-prev"), async () => {
      state.callsPage--;
      try {
        await calls();
      } catch (e) {
        notice(e.message);
      }
    });
};
$("#calls-next").onclick = () => {
  if (state.callsPage < state.callsPages)
    withLoading($("#calls-next"), async () => {
      state.callsPage++;
      try {
        await calls();
      } catch (e) {
        notice(e.message);
      }
    });
};
async function alerts() {
  const f = $("#alerts-filter"),
    q = query(f);
  const d = data(
    await api(
      "/fraud-alerts?" +
        q +
        (q ? "&" : "") +
        "page=" +
        state.alertsPage +
        "&page_size=20",
    ),
  );
  state.alertsPages = d.pages;
  notice("");
  $("#alerts-count").textContent = `Событий: ${num(d.total)}`;
  $("#alerts-page").textContent = `${d.page} / ${Math.max(1, d.pages)}`;
  $("#alerts-prev").disabled = d.page <= 1;
  $("#alerts-next").disabled = d.page >= d.pages;
  $("#alerts-body").innerHTML = d.items.length
    ? d.items
        .map(
          (x) =>
            `<tr><td>${x.call_id}</td><td>${esc(date(x.call_time))}</td><td>${phoneMarkup(x.msisdn_a)}</td><td>${phoneMarkup(x.msisdn_b)}</td><td>${esc(scenarioName(x.fraud_scenario))}</td><td>${risk(x.risk_level)} ${pct(x.risk_score)}</td><td>${esc(recommendationName(x.recommendation))}${x.auto_blocked ? " · заблокирован" : ""}</td></tr>`,
        )
        .join("")
    : '<tr><td colspan="7" class="empty">Подозрительных событий не найдено.</td></tr>';
}
$("#alerts-filter").addEventListener("submit", (e) => {
  e.preventDefault();
  state.alertsPage = 1;
  alerts().catch((err) => notice(err.message));
});
$("#alerts-prev").onclick = () => {
  if (state.alertsPage > 1)
    withLoading($("#alerts-prev"), async () => {
      state.alertsPage--;
      try {
        await alerts();
      } catch (e) {
        notice(e.message);
      }
    });
};
$("#alerts-next").onclick = () => {
  if (state.alertsPage < state.alertsPages)
    withLoading($("#alerts-next"), async () => {
      state.alertsPage++;
      try {
        await alerts();
      } catch (e) {
        notice(e.message);
      }
    });
};
function profileMarkup(p) {
  const s = p.statistics || {};
  return `<div class="profile-grid">${[
    ["Всего вызовов", s.total_calls],
    ["Входящие", s.incoming_calls],
    ["Исходящие", s.outgoing_calls],
    ["Переадресованные", s.forwarded_calls],
    ["Уникальные контакты", s.unique_contacts],
    ["Короткие вызовы", s.short_calls],
    ["Без ответа", s.unanswered_calls],
    ["Доля коротких", pct(s.short_calls_ratio)],
    ["Доля без ответа", pct(s.unanswered_calls_ratio)],
  ]
    .map(
      ([k, v]) =>
        `<div class="mini-stat"><span>${k}</span><strong>${esc(val(v))}</strong></div>`,
    )
    .join(
      "",
    )}</div><div class="subsection"><h3>Профиль ${phoneMarkup(p.msisdn)}</h3><p class="muted">Первое появление: ${esc(date(p.first_seen_at))} · Последняя активность: ${esc(date(p.last_seen_at))}</p><p style="margin-top:10px">Уровень риска: ${risk(p.risk_level)} ${pct(p.risk_score)}</p></div><div class="subsection"><h3>Частые контакты</h3>${p.contacts?.length ? `<div class="table-wrap"><table><thead><tr><th>Номер</th><th>Вызовов</th><th>Риск</th><th>Уровень</th></tr></thead><tbody>${p.contacts.map((c) => `<tr><td>${phoneMarkup(c.msisdn)}</td><td>${num(c.calls_count)}</td><td>${pct(c.risk_score)}</td><td>${risk(c.risk_level)}</td></tr>`).join("")}</tbody></table></div>` : "<p class='muted'>Контакты отсутствуют.</p>"}</div><div class="subsection"><h3>Связанные подозрительные номера</h3><div class="chips">${(p.related_suspicious_numbers || []).map((n) => `<span class="chip">${phoneMarkup(n)}</span>`).join("") || "Нет связанных номеров."}</div></div>`;
}
async function loadProfile(number) {
  if (!/^\d{10}$/.test(number)) {
    throw new Error("Введите номер из 10 цифр.");
  }
  const p = data(await api("/subscribers/" + encodeURIComponent(number)));
  $("#profile-number").value = number;
  $("#subscriber-number").value = number;
  $("#profile-result").innerHTML = profileMarkup(p);
}
$("#profile-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await loadProfile($("#profile-number").value);
    notice("");
  } catch (err) {
    notice(err.message);
  }
});
$("#subscriber-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setPage("subscriber");
  try {
    await loadProfile($("#subscriber-number").value);
    notice("");
  } catch (err) {
    notice(err.message);
  }
});
async function model() {
  const m = data(await api("/model/info"));
  $("#model-details").innerHTML =
    `<strong>${esc(m.name)}</strong><p>Версия: ${esc(m.version)} · Алгоритм: ${esc(m.algorithm)}</p><p>Обучена: ${esc(date(m.trained_at))}</p><p>Состояние: <span class="${m.is_loaded ? "status-ok" : "status-bad"}">${m.is_loaded ? "Загружена" : "Не загружена"}</span></p><div class="subsection"><h3>Метрики модели</h3><div class="metric-grid">${Object.entries(
      {
        Precision: m.metrics?.precision,
        Recall: m.metrics?.recall,
        "F1-score": m.metrics?.f1_score,
        "PR AUC": m.metrics?.pr_auc,
        "False positive rate": m.metrics?.false_positive_rate,
      },
    )
      .map(
        ([k, v]) =>
          `<div class="metric"><span>${k}</span><strong>${pct(v)}</strong></div>`,
      )
      .join(
        "",
      )}</div></div><div class="subsection"><h3>Признаки модели (${m.feature_names?.length || 0})</h3><div class="chips">${(m.feature_names || []).map((x) => `<span class="chip">${esc(x)}</span>`).join("") || "Не указаны"}</div></div>`;
}
async function loadCurrentAnalyses() {
  const response = data(await api("/analysis/current", {}, false));
  const current = response && typeof response === "object" ? response : {};
  const queue = Array.isArray(current.queued_jobs) ? current.queued_jobs : [];
  const jobs = [
    ["Активная задача", current.active_job],
    ...queue.map((job, i) => [
      `В очереди${queue.length > 1 ? ` · ${i + 1}` : ""}`,
      job,
    ]),
    ["Последняя ошибка", current.last_failed_job],
    ["Последняя успешная задача", current.last_successful_job],
  ].filter(([, job]) => job && typeof job === "object");
  const show = (value) => (value == null || value === "" ? "—" : esc(value));
  const renderMetrics = (value) => {
    if (!value || typeof value !== "object") return "";
    const entries = [
      ["Всего", value.total_calls],
      ["Обработано", value.processed_calls],
      ["Мошеннических", value.fraud_calls],
      ["Низкий риск", value.low_risk_calls],
      ["Средний риск", value.medium_risk_calls],
      ["Высокий риск", value.high_risk_calls],
      ["Критический риск", value.critical_risk_calls],
    ];
    return `<div class="current-job-metrics">${entries
      .map(([label, n]) => `<span>${label}: ${n == null ? "—" : num(n)}</span>`)
      .join("")}</div>`;
  };
  $("#analysis-current-list").innerHTML = jobs.length
    ? jobs
        .map(
          ([label, job]) =>
            `<div class="current-job"><div class="current-job-heading"><strong>${label}</strong><span>${show(analysisStatusNames[job.status] || job.status)}</span></div><p>Задача: <code>${show(job.job_id)}</code></p><p>Период: ${job.date_from == null ? "—" : esc(date(job.date_from))} — ${job.date_to == null ? "—" : esc(date(job.date_to))}</p><p>Прогресс: ${job.progress_percent == null ? "—" : `${Number(job.progress_percent).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`}</p><p>Создана: ${job.created_at == null ? "—" : esc(date(job.created_at))} · Начата: ${job.started_at == null ? "—" : esc(date(job.started_at))} · Завершена: ${job.finished_at == null ? "—" : esc(date(job.finished_at))}</p>${renderMetrics(job.metrics)}${job.error == null || job.error === "" ? "" : `<p class="current-job-error">${show(job.error)}</p>`}</div>`,
        )
        .join("")
    : '<p class="muted">Текущих и недавних задач нет.</p>';
}
async function runAnalysis(e) {
  e.preventDefault();
  const f = new FormData(e.currentTarget),
    body = {
      date_from: new Date(f.get("date_from")).toISOString().slice(0, 19),
      date_to: new Date(f.get("date_to")).toISOString().slice(0, 19),
      force_recalculate: f.has("force_recalculate"),
    };
  if (body.date_from >= body.date_to) {
    notice("Дата начала должна быть раньше даты окончания.");
    return;
  }
  try {
    await api("/analysis/run", {
      method: "POST",
      body: JSON.stringify(body),
    });
    notice("");
    await loadCurrentAnalyses();
  } catch (err) {
    notice(err.message);
  }
}
$("#analysis-form").addEventListener("submit", runAnalysis);
const predictionType = $("#prediction-form [name=call_type]");
predictionType.addEventListener("change", () => {
  const forwarded = predictionType.value === "03";
  const input = $("#prediction-form [name=msisdn_c]");
  $("#prediction-msisdn-c-wrap").hidden = !forwarded;
  input.required = forwarded;
  if (!forwarded) input.value = "";
});
$("#prediction-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const fields = new FormData(form);
  const call = {
    call_type: fields.get("call_type"),
    msisdn_a: fields.get("msisdn_a"),
    msisdn_b: fields.get("msisdn_b"),
    call_time: fields.get("call_time").replace("T", " ") + ":00",
    duration_seconds: Number(fields.get("duration_seconds")),
  };
  if (fields.get("imsi_a").trim()) call.imsi_a = fields.get("imsi_a").trim();
  if (call.call_type === "03") call.msisdn_c = fields.get("msisdn_c");
  const button = form.querySelector("button[type=submit], button:not([type])");
  await withLoading(button, async () => {
    try {
      const result = data(
        await api("/predict", {
          method: "POST",
          body: JSON.stringify({ call }),
        }),
      );
      const reasons = result.reasons?.length
        ? `<ul class="reasons">${result.reasons.map((item) => `<li>${esc(item.description || item.feature)}${item.impact ? ` · ${esc(item.impact)}` : ""}</li>`).join("")}</ul>`
        : '<p class="muted">Причины оценки не указаны.</p>';
      $("#prediction-result").innerHTML =
        `<div class="subsection"><h3>Результат прогноза</h3><div class="profile-grid"><div class="mini-stat"><span>Уровень риска</span><strong>${esc(riskNames[result.risk_level] || result.risk_level || "—")}</strong></div><div class="mini-stat"><span>Оценка риска</span><strong>${pct(result.risk_score)}</strong></div><div class="mini-stat"><span>Мошенничество</span><strong>${result.is_fraud ? "Обнаружено" : "Не обнаружено"}</strong></div></div><p>${esc(result.operator_message || "")}</p><p>Сценарий: ${esc(scenarioName(result.fraud_scenario))} · Рекомендация: ${esc(recommendationName(result.recommendation))}${result.auto_blocked ? " · Автоматически заблокирован" : ""}</p><h3>Причины оценки</h3>${reasons}</div>`;
      notice("");
    } catch (err) {
      notice(err.message);
    }
  });
});
$("#refresh-analysis-current").onclick = () =>
  withLoading($("#refresh-analysis-current"), async () => {
    try {
      await loadCurrentAnalyses();
      notice("");
    } catch (err) {
      notice(err.message);
    }
  });
$("#check-health").onclick = () =>
  withLoading($("#check-health"), async () => {
    try {
      await health();
      notice("");
    } catch (e) {
      notice(e.message);
    }
  });
async function loadPage() {
  switch (state.page) {
    case "dashboard":
      await dashboard();
      break;
    case "calls":
      await calls();
      break;
    case "alerts":
      await alerts();
      break;
    case "model":
      await health().catch(() => {});
      await model();
      break;
    case "subscriber":
      if ($("#profile-number").value) {
        await loadProfile($("#profile-number").value);
      }
      break;
    case "analysis":
      await loadCurrentAnalyses();
      break;
  }
  notice("");
}
async function init() {
  const now = new Date(),
    prior = new Date(now.getTime() - 86400000);
  const local = (d) =>
    new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  $("#analysis-form [name=date_from]").value = local(prior);
  $("#analysis-form [name=date_to]").value = local(now);
  $("#prediction-form [name=call_time]").value = local(now);
  $("#docs-link").href = base().replace(/\/api\/v1$/, "") + "/docs";
  $$(".page").forEach((x) => (x.hidden = x.id !== "page-" + state.page));
  $$(".nav-link").forEach((x) =>
    x.classList.toggle("active", x.dataset.page === state.page),
  );
  $("#page-title").textContent = titles[state.page][0];
  $("#page-desc").textContent = titles[state.page][1];
  try {
    await health();
    await refreshDashboardStatus();
    await loadPage();
  } catch (e) {
    notice(e.message);
  }
  setInterval(() => {
    health().catch(() => {});
    refreshDashboardStatus().catch(() => {});
    if (state.page === "analysis") loadCurrentAnalyses().catch(() => {});
  }, 3000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) health().catch(() => {});
  });
}
init();
