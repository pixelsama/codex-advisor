const token = new URLSearchParams(window.location.search).get("token") || "";

const elements = {
  enabled: document.querySelector("#enabled"),
  enabledLabel: document.querySelector("#enabled-label"),
  mode: document.querySelector("#mode"),
  agentProtocol: document.querySelector("#agent-protocol"),
  reasoningEffort: document.querySelector("#reasoning-effort"),
  onExhausted: document.querySelector("#on-exhausted"),
  selectedModels: document.querySelector("#selected-models"),
  availableModels: document.querySelector("#available-models"),
  selectedCount: document.querySelector("#selected-count"),
  modelSource: document.querySelector("#model-source"),
  catalogSource: document.querySelector("#catalog-source"),
  catalogPath: document.querySelector("#catalog-path"),
  catalogPathField: document.querySelector("#catalog-path-field"),
  manualModel: document.querySelector("#manual-model"),
  manualModelId: document.querySelector("#manual-model-id"),
  manualEffort: document.querySelector("#manual-effort"),
  message: document.querySelector("#message"),
  save: document.querySelector("#save"),
  refresh: document.querySelector("#refresh"),
  shutdown: document.querySelector("#shutdown"),
  saveBanner: document.querySelector("#save-banner"),
  saveBannerIcon: document.querySelector("#save-banner-icon"),
  saveBannerTitle: document.querySelector("#save-banner-title"),
  saveBannerMessage: document.querySelector("#save-banner-message"),
  saveBannerClose: document.querySelector("#save-banner-close"),
};

let state = {
  config: null,
  models: [],
  modelDetails: {},
  reasoningEfforts: [],
};
const sourceLabels = {
  codex: "Codex 本机缓存",
  "cc-switch": "CC Switch 发布的目录",
  catalog: "自定义 Codex 模型目录",
  manual: "手动添加",
};
let catalogRequest = 0;
let bannerTimer = null;
let bannerHideTimer = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Advisor-Token": token,
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `请求失败：${response.status}`);
  }
  return payload;
}

function showMessage(text, kind = "") {
  elements.message.textContent = text;
  elements.message.className = kind;
}

function hideSaveBanner() {
  if (bannerTimer !== null) {
    window.clearTimeout(bannerTimer);
    bannerTimer = null;
  }
  if (bannerHideTimer !== null) {
    window.clearTimeout(bannerHideTimer);
    bannerHideTimer = null;
  }
  elements.saveBanner.classList.remove("visible");
  bannerHideTimer = window.setTimeout(() => {
    elements.saveBanner.hidden = true;
    bannerHideTimer = null;
  }, 180);
}

function showSaveBanner(kind, title, message) {
  if (bannerTimer !== null) {
    window.clearTimeout(bannerTimer);
    bannerTimer = null;
  }
  if (bannerHideTimer !== null) {
    window.clearTimeout(bannerHideTimer);
    bannerHideTimer = null;
  }
  elements.saveBanner.hidden = false;
  const isSuccess = kind === "success";
  elements.saveBanner.className = `save-banner ${kind}`;
  elements.saveBannerIcon.textContent = isSuccess ? "✓" : "!";
  elements.saveBannerTitle.textContent = title;
  elements.saveBannerMessage.textContent = message;
  elements.saveBanner.setAttribute("role", isSuccess ? "status" : "alert");
  window.requestAnimationFrame(() => {
    elements.saveBanner.classList.add("visible");
  });
  if (isSuccess) {
    bannerTimer = window.setTimeout(hideSaveBanner, 6000);
  }
}

function updateEnabledLabel() {
  elements.enabledLabel.textContent = elements.enabled.checked ? "开启" : "关闭";
}

function iconButton(label, title, className, handler, disabled = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `icon ${className || ""}`.trim();
  button.textContent = label;
  button.title = title;
  button.setAttribute("aria-label", title);
  button.disabled = disabled;
  button.addEventListener("click", handler);
  return button;
}

function setOptions(select, options, selected) {
  select.replaceChildren(...options.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
  select.value = selected;
}

function effortOptions(id, selected) {
  const details = Object.hasOwn(state.modelDetails, id) ? state.modelDetails[id] : null;
  const supported = details?.efforts?.length ? details.efforts : state.reasoningEfforts;
  const options = [
    ["inherit", "跟随 Advisor 默认"],
    ["auto", "由 Codex 决定"],
    ...supported.map((effort) => [effort, effort]),
  ];
  if (!options.some(([value]) => value === selected)) {
    options.push([selected, `${selected}（目录未列出）`]);
  }
  return options;
}

function renderSelectedModels() {
  const selected = state.config.models;
  elements.selectedModels.replaceChildren();
  elements.selectedCount.textContent = String(selected.length);

  if (!selected.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "还没有 Advisor 模型。请从目录加入或手动添加。";
    elements.selectedModels.append(empty);
    return;
  }

  selected.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "model-row selected-model";

    const name = document.createElement("div");
    name.className = "model-name";
    name.textContent = `${index + 1}. ${item.id}`;
    if (!state.models.includes(item.id)) {
      const warning = document.createElement("span");
      warning.className = "unavailable";
      warning.textContent = "未在当前目录验证";
      name.append(warning);
    }

    const effort = document.createElement("label");
    effort.className = "field model-effort";
    effort.textContent = "推理强度";
    const effortInput = document.createElement("select");
    effortInput.setAttribute("aria-label", `${item.id} 的推理强度`);
    const selectedEffort = item.reasoning_effort === null ? "auto" : (item.reasoning_effort ?? "inherit");
    setOptions(effortInput, effortOptions(item.id, selectedEffort), selectedEffort);
    effortInput.addEventListener("change", () => {
      if (effortInput.value === "inherit") {
        delete item.reasoning_effort;
      } else {
        item.reasoning_effort = effortInput.value === "auto" ? null : effortInput.value;
      }
    });
    effort.append(effortInput);

    const retry = document.createElement("label");
    retry.className = "retry";
    retry.textContent = "额外重试";
    const retryInput = document.createElement("input");
    retryInput.type = "number";
    retryInput.min = "0";
    retryInput.max = "5";
    retryInput.value = String(item.retries);
    const updateRetries = () => {
      const parsed = Number.parseInt(retryInput.value, 10);
      item.retries = Number.isFinite(parsed)
        ? Math.max(0, Math.min(5, parsed))
        : 0;
    };
    retryInput.addEventListener("input", updateRetries);
    retryInput.addEventListener("change", () => {
      updateRetries();
      retryInput.value = String(item.retries);
    });
    retry.append(retryInput);

    row.append(
      name,
      effort,
      retry,
      iconButton(
        "↑",
        "提高优先级",
        "",
        () => moveSelected(index, -1),
        index === 0,
      ),
      iconButton(
        "↓",
        "降低优先级",
        "",
        () => moveSelected(index, 1),
        index === selected.length - 1,
      ),
      iconButton("×", "移除", "remove", () => removeSelected(index)),
    );
    elements.selectedModels.append(row);
  });
}

function renderAvailableModels() {
  const selectedIds = new Set(state.config.models.map((item) => item.id));
  const available = state.models.filter((model) => !selectedIds.has(model));
  elements.availableModels.replaceChildren();

  if (!available.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = state.models.length
      ? "所有可用模型都已加入 Advisor。"
      : "当前目录没有可显示的模型。可在下方手动添加。";
    elements.availableModels.append(empty);
    return;
  }

  available.forEach((model) => {
    const row = document.createElement("div");
    row.className = "model-row";
    const name = document.createElement("div");
    name.className = "model-name";
    name.textContent = model;
    const add = document.createElement("button");
    add.type = "button";
    add.className = "ghost";
    add.textContent = "加入";
    add.addEventListener("click", () => {
      state.config.models.push({ id: model, retries: 1, reasoning_effort: null });
      renderModelLists();
    });
    row.append(name, add);
    elements.availableModels.append(row);
  });
}

function renderModelLists() {
  renderSelectedModels();
  renderAvailableModels();
}

function moveSelected(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= state.config.models.length) return;
  [state.config.models[index], state.config.models[target]] = [
    state.config.models[target],
    state.config.models[index],
  ];
  renderModelLists();
}

function removeSelected(index) {
  state.config.models.splice(index, 1);
  renderModelLists();
}

function render() {
  const config = state.config;
  elements.enabled.checked = config.enabled;
  elements.mode.value = config.mode;
  elements.agentProtocol.value = config.agent_protocol;
  elements.reasoningEffort.value = config.reasoning_effort;
  elements.onExhausted.value = config.on_exhausted;
  elements.catalogSource.value = config.model_source;
  elements.catalogPath.value = config.catalog_path;
  updateCatalogPathVisibility();
  updateEnabledLabel();
  renderModelLists();
}

function collectConfig() {
  return {
    version: 1,
    enabled: elements.enabled.checked,
    mode: elements.mode.value,
    agent_protocol: elements.agentProtocol.value,
    model_source: elements.catalogSource.value,
    catalog_path: elements.catalogSource.value === "catalog" ? elements.catalogPath.value.trim() : "",
    reasoning_effort: elements.reasoningEffort.value,
    on_exhausted: elements.onExhausted.value,
    models: state.config.models,
  };
}

function updateCatalogPathVisibility() {
  elements.catalogPathField.hidden = elements.catalogSource.value !== "catalog";
}

function showCatalog(payload) {
  state.models = payload.models;
  state.modelDetails = payload.modelDetails;
  const lines = [sourceLabels[payload.modelSource] || payload.modelSource];
  if (payload.modelSourcePath) lines.push(payload.modelSourcePath);
  if (payload.modelSourceUpdatedAt) {
    lines.push(`文件更新于 ${new Date(payload.modelSourceUpdatedAt).toLocaleString()}`);
  }
  if (payload.modelSourceError) lines.push(payload.modelSourceError);
  elements.modelSource.textContent = lines.join(" · ");
  renderModelLists();
}

async function refreshCatalog() {
  if (!state.config) return;
  const request = ++catalogRequest;
  const source = elements.catalogSource.value;
  const path = source === "catalog" ? elements.catalogPath.value.trim() : "";
  updateCatalogPathVisibility();
  showCatalog({ models: [], modelDetails: {}, modelSource: source });
  if (source === "catalog" && !path) {
    elements.modelSource.textContent = "填写目录文件路径后，点击重新读取。";
    return;
  }
  elements.modelSource.textContent = "正在读取模型目录…";
  try {
    const query = new URLSearchParams({ source, path });
    const payload = await api(`/api/models?${query}`);
    if (request === catalogRequest) showCatalog(payload);
  } catch (error) {
    if (request === catalogRequest) elements.modelSource.textContent = error.message;
  }
}

async function bootstrap() {
  showMessage("正在读取配置…");
  try {
    const payload = await api("/api/bootstrap");
    state.config = payload.config;
    state.reasoningEfforts = payload.reasoningEfforts;
    const efforts = state.reasoningEfforts.map((effort) => [effort, effort]);
    setOptions(elements.reasoningEffort, efforts, state.config.reasoning_effort);
    setOptions(elements.manualEffort, [["auto", "由 Codex 决定"], ...efforts], "auto");
    render();
    showCatalog(payload);
    elements.save.disabled = false;
    showMessage("已读取当前配置。", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

elements.enabled.addEventListener("change", updateEnabledLabel);
elements.saveBannerClose.addEventListener("click", hideSaveBanner);
elements.refresh.addEventListener("click", refreshCatalog);
elements.catalogSource.addEventListener("change", refreshCatalog);
elements.catalogPath.addEventListener("change", refreshCatalog);
elements.manualModel.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state.config) return;
  const id = elements.manualModelId.value.trim();
  if (!id || /[\s`\x00-\x1f\x7f]/u.test(id)) {
    showMessage("请填写 Codex 显示的完整模型 ID，去掉空白和反引号。", "error");
    return;
  }
  if (state.config.models.some((item) => item.id === id)) {
    showMessage("这个模型已在 Advisor 优先级列表中。", "error");
    return;
  }
  const effort = elements.manualEffort.value;
  state.config.models.push({ id, retries: 1, reasoning_effort: effort === "auto" ? null : effort });
  elements.manualModelId.value = "";
  renderModelLists();
  showMessage("模型已添加。点击保存配置后生效。", "success");
});
elements.save.addEventListener("click", async () => {
  if (!state.config) return;
  elements.save.disabled = true;
  showMessage("正在保存…");
  try {
    const payload = await api("/api/config", {
      method: "PUT",
      body: JSON.stringify(collectConfig()),
    });
    state.config = payload.config;
    render();
    showMessage("配置已保存。", "success");
    showSaveBanner(
      "success",
      "配置已保存",
      "下次发消息或手动咨询时读取新配置。",
    );
  } catch (error) {
    showMessage(error.message, "error");
    showSaveBanner("error", "保存失败", error.message);
  } finally {
    elements.save.disabled = false;
  }
});
elements.shutdown.addEventListener("click", async () => {
  try {
    await api("/api/shutdown", { method: "POST", body: "{}" });
    showMessage("配置服务已关闭，可以关闭此页面。", "success");
    elements.save.disabled = true;
    elements.refresh.disabled = true;
    elements.shutdown.disabled = true;
  } catch (error) {
    showMessage(error.message, "error");
  }
});

bootstrap();
