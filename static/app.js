"use strict";

const byId = (id) => document.getElementById(id);
const state = { scenarios: [], selected: null, result: null, number: "", showAll: false, request: 0 };
const format = (value, digits = 0) => Number(value).toLocaleString("ru-RU", { maximumFractionDigits: digits });
const dateLabel = (value) => new Date(value).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...options.headers } });
  let data;
  try { data = await response.json(); } catch { throw new Error("Сервер вернул некорректный ответ. Проверьте, что запущена новая версия проекта."); }
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((e) => e.msg.replace(/^Value error, /, "")).join(". ") : data.detail;
    throw new Error(detail || "Не удалось выполнить запрос. Попробуйте ещё раз.");
  }
  return data;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

let toastTimer;
function toast(message) {
  byId("toast").textContent = message;
  byId("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { byId("toast").hidden = true; }, 2800);
}

function busy(value) {
  byId("result-card").setAttribute("aria-busy", String(value));
  byId("number-submit").disabled = value;
}

function error(message) {
  byId("score-error").textContent = message;
  byId("score-error").hidden = !message;
}

function renderScenarios() {
  const icons = { mass: "↗", fanout: "⋈", personal: "○", hospital: "+", international: "◎", quiet: "∿", emergency: "+", spoof: "≠" };
  const list = byId("scenario-list");
  list.replaceChildren();
  byId("scenario-count").textContent = state.scenarios.length;
  for (const sample of state.scenarios) {
    const button = node("button", "scenario-button" + (state.selected?.id === sample.id ? " active" : ""));
    button.type = "button";
    button.setAttribute("aria-pressed", String(state.selected?.id === sample.id));
    button.dataset.scenario = sample.id;
    button.append(node("span", "scenario-icon", icons[sample.id]));
    const text = node("span", "scenario-text");
    text.append(node("strong", "", sample.title), node("small", "", sample.subtitle));
    button.append(text, node("span", "scenario-arrow", "→"));
    button.addEventListener("click", () => evaluateScenario(sample));
    list.append(button);
  }
}

async function evaluateScenario(sample) {
  const request = ++state.request;
  state.selected = sample;
  state.number = sample.call.caller;
  state.showAll = false;
  renderScenarios();
  error("");
  busy(true);
  try {
    const call = { ...sample.call, started_at: new Date().toISOString() };
    const result = await api("/v1/calls/score", { method: "POST", body: JSON.stringify(call) });
    // Поздний ответ предыдущего запроса не должен заменять выбранный сейчас сценарий.
    if (request !== state.request) return;
    state.result = result;
    renderResult(result, { ...sample, call });
  } catch (e) { if (request === state.request) error(e.message); }
  finally { if (request === state.request) busy(false); }
}

async function evaluateNumber(number) {
  const request = ++state.request;
  const at = new Date().toISOString();
  state.selected = null;
  state.number = number;
  state.showAll = false;
  renderScenarios();
  error("");
  busy(true);
  try {
    const result = await api("/v1/numbers/score", { method: "POST", body: JSON.stringify({ number, at }) });
    if (request !== state.request) return;
    state.number = result.number || number;
    state.result = result;
    renderResult(result, { title: "Оценка номера по истории", display_caller: state.number, display_callee: "", call: { started_at: at } });
  } catch (e) { if (request === state.request) error(e.message); }
  finally { if (request === state.request) busy(false); }
}

function renderResult(result, sample) {
  const score = result.risk_score;
  const threshold = 100 * (result.review_threshold ?? 0.6946663610181804);
  const protectedCall = result.status === "protected";
  const scored = result.status === "scored" && Number.isFinite(score);
  const high = scored && result.action === "review";
  const medium = scored && !high && score >= 35;
  const tone = protectedCall || (scored && !high && !medium) ? "low" : medium ? "medium" : scored ? "high" : "unknown";
  byId("result-card").className = `result-card ${tone}`;
  byId("call-title").textContent = sample.title;
  byId("caller-display").textContent = sample.display_caller;
  byId("callee-display").textContent = sample.display_callee;
  document.querySelector(".route-arrow").hidden = !sample.display_callee;
  const country = sample.call.source_country;
  const origin = country ? (country === "RU" ? "внутри страны" : "вход из-за рубежа") : "по доступной истории";
  byId("call-meta").textContent = `${dateLabel(sample.call.started_at)} · ${origin}${sample.display_callee ? " · до соединения" : ""}`;
  byId("risk-score").textContent = scored ? format(score, 1) : "—";
  byId("score-denominator").hidden = !scored;
  byId("risk-badge").textContent = protectedCall ? "Защищённый вызов" : high ? "Высокий риск" : medium ? "Есть сигналы риска" : scored ? "Низкий риск" : result.status === "degraded" ? "Сервис недоступен" : "Недостаточно данных";
  byId("score-scale").hidden = !scored;
  byId("risk-fill").style.width = `${scored ? score : 0}%`;
  byId("threshold-marker").style.left = `${Math.min(100, threshold)}%`;
  byId("threshold-label").textContent = `Порог проверки ${format(threshold, 1)}`;
  byId("decision-title").textContent = protectedCall ? "Пропустить вызов" : high ? "Рекомендуется проверка" : scored ? "Оснований для проверки недостаточно" : "Пропустить без оценки";
  byId("decision-description").textContent = protectedCall ? result.reason : high ? "Передайте на проверку оператору. Соединение продолжается." : result.reason || "Неизвестный номер не получает нулевой риск.";
  const features = result.features || {};
  byId("history-stats").hidden = !scored;
  byId("stat-calls").textContent = features.calls_1h == null ? "—" : format(features.calls_1h);
  byId("stat-regions").textContent = features.regions_1h == null ? "—" : format(features.regions_1h);
  byId("stat-short").textContent = features.short_ratio_24h == null ? "—" : `${format(features.short_ratio_24h * 100)}%`;
  byId("factors-section").hidden = !scored;
  byId("empty-state").hidden = scored;
  if (!scored) {
    const emergency = result.protection?.kind === "emergency_destination";
    byId("empty-title").textContent = emergency ? "Экстренная связь доступна" : protectedCall ? "Организация подтверждена" : result.status === "degraded" ? "Оценка временно недоступна" : "Для оценки нужна история";
    byId("empty-description").textContent = emergency ? "Вызов скорой помощи проходит независимо от риска источника. Для этого решения модель и база истории не нужны." : protectedCall ? `${result.protection.organization}. Номер, абонент, оператор и входящий транк совпадают с записью в реестре. Привилегия не означает нулевой риск номера.` : result.status === "degraded" ? "Модель или история недоступны. Вызов пропускается без выдуманного балла риска." : "Нужно не менее пяти завершённых вызовов этого номера. Выберите готовый пример справа или загрузите историю через API.";
    byId("empty-state").querySelector(".empty-icon").textContent = protectedCall ? "+" : "?";
  }
  byId("assessment-time").textContent = scored ? `${format(result.history_calls || 0)} вызовов в истории · окно 24 часа` : "Баллы риска не присваивались";
  renderFactors();
}

function valueLabel(factor) {
  const name = factor.feature, value = factor.value;
  if (name.includes("_ratio_")) return `${format(value * 100, 1)}% за последние сутки`;
  if (name === "mean_duration_24h") return `${format(value, 1)} сек. в среднем`;
  if (["foreign_ingress", "voip", "unverified_identity"].includes(name)) return value ? "Признак присутствует" : "Признак отсутствует";
  if (name.startsWith("hour_")) return `Временная компонента: ${format(value, 2)}`;
  if (name === "fanout_pattern") return `Сходство шаблона: ${format(value, 2)} из 1`;
  return `Значение: ${format(value)}`;
}

function renderFactors() {
  const result = state.result;
  if (!result) return;
  const factors = result.factors || [];
  const list = byId("factor-list");
  list.replaceChildren();
  const max = Math.max(0.001, ...factors.map((f) => Math.abs(f.log_odds_contribution)));
  for (const factor of state.showAll ? factors : factors.slice(0, 4)) {
    const weight = factor.log_odds_contribution;
    const row = node("div", "factor-row" + (weight < 0 ? " negative" : ""));
    const label = node("div", "factor-label");
    const name = node("div", "factor-name", factor.description);
    name.append(node("span", "factor-value", valueLabel(factor)));
    const amount = node("span", "factor-weight", `${weight > 0 ? "+" : ""}${format(weight, 2)}`);
    amount.title = "Вклад в логарифм отношения шансов, не баллы риска";
    label.append(name, amount);
    const track = node("div", "factor-track");
    const bar = node("div");
    bar.style.width = `${Math.abs(weight) / max * 100}%`;
    track.append(bar);
    row.append(label, track);
    list.append(row);
  }
  byId("toggle-factors").textContent = state.showAll ? "Свернуть" : `Все факторы · ${factors.length}`;
  byId("toggle-factors").setAttribute("aria-expanded", String(state.showAll));
  byId("model-equation").textContent = `Базовый уровень: ${format(result.baseline_log_odds || 0, 3)}. Сумма с учётом всех факторов: ${format(result.total_log_odds || 0, 3)}. Затем модель переводит сумму в шкалу от 0 до 100.`;
}

async function loadRegistry() {
  const rows = await api("/v1/privileges");
  const active = rows.filter((row) => row.status === "approved" && row.expires * 1000 > Date.now());
  byId("registry-count").textContent = active.length;
  const list = byId("registry-list");
  list.replaceChildren();
  if (!active.length) list.append(node("p", "registry-empty", "Пока нет активных привилегий. Добавьте первый номер."));
  for (const entry of active) {
    const row = node("div", "registry-entry");
    const info = node("div", "registry-entry-info");
    const sample = state.scenarios.find((s) => s.call.caller === entry.number);
    info.append(node("h3", "", entry.organization), node("code", "", entry.number));
    info.append(node("small", "", `${sample ? sample.display_caller + " · " : ""}До ${new Date(entry.expires * 1000).toLocaleDateString("ru-RU")}`));
    const button = node("button", "revoke-button", "Отозвать");
    button.type = "button";
    button.setAttribute("aria-label", `Отозвать привилегию: ${entry.organization}`);
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await api(`/v1/privileges/${encodeURIComponent(entry.id)}`, { method: "DELETE" });
        await loadRegistry();
        toast("Привилегия отозвана");
      } catch (e) { toast(e.message); button.disabled = false; }
    });
    row.append(info, button);
    list.append(row);
  }
}

async function showPage(registry) {
  byId("score-page").hidden = registry;
  byId("registry-page").hidden = !registry;
  for (const [id, active] of [["nav-score", !registry], ["nav-registry", registry]]) {
    byId(id).classList.toggle("active", active);
    if (active) byId(id).setAttribute("aria-current", "page"); else byId(id).removeAttribute("aria-current");
  }
  if (registry) {
    try { await loadRegistry(); } catch (e) { toast(e.message); }
  } else if (state.selected) await evaluateScenario(state.selected);
}

byId("number-form").addEventListener("submit", (event) => { event.preventDefault(); evaluateNumber(byId("number-input").value.trim()); });
byId("toggle-factors").addEventListener("click", () => { state.showAll = !state.showAll; renderFactors(); });
byId("nav-score").addEventListener("click", () => showPage(false));
byId("nav-registry").addEventListener("click", () => showPage(true));
byId("use-selected").addEventListener("click", () => { byId("registry-number").value = state.number; byId("registry-number").focus(); });
byId("copy-number").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(state.number); toast("ID номера скопирован"); }
  catch { byId("number-input").value = state.number; byId("number-input").focus(); byId("number-input").select(); toast("Номер подставлен в поле поиска"); }
});
byId("registry-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.target.querySelector("[type=submit]");
  button.disabled = true;
  const message = byId("registry-message");
  message.textContent = "";
  message.className = "";
  try {
    await api("/v1/privileges", { method: "POST", body: JSON.stringify({ number: byId("registry-number").value.trim(), organization: byId("organization-input").value.trim() }) });
    message.textContent = "Номер добавлен. Привилегия действует 30 дней и может быть отозвана в любой момент.";
    await loadRegistry();
  } catch (e) { message.textContent = e.message; message.className = "error"; }
  finally { button.disabled = false; }
});

async function initialize() {
  const results = await Promise.allSettled([api("/v1/demo/scenarios"), api("/health"), api("/v1/demo/metrics")]);
  const health = results[1];
  const ready = health.status === "fulfilled" && health.value.model_loaded;
  byId("model-state").className = `model-state ${ready ? "ready" : "failed"}`;
  byId("model-state").querySelector("span").textContent = ready ? "Модель загружена" : "Модель недоступна";
  if (results[2].status === "fulfilled") {
    byId("test-count").textContent = format(results[2].value.test.n);
    byId("test-fpr").textContent = `${format(results[2].value.test.fpr * 100, 2)}%`;
  }
  if (results[0].status === "fulfilled" && results[0].value.length) {
    state.scenarios = results[0].value;
    await evaluateScenario(state.scenarios[0]);
  } else {
    busy(false);
    error("Не удалось загрузить примеры. Перезапустите сервер и обновите страницу.");
    byId("call-title").textContent = "Примеры недоступны";
    byId("risk-badge").textContent = "Ошибка загрузки";
  }
}
initialize();
