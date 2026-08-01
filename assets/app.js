const token = new URLSearchParams(window.location.search).get("token") || "";

const elements = {
  enabled: document.querySelector("#enabled"),
  enabledLabel: document.querySelector("#enabled-label"),
  mode: document.querySelector("#mode"),
  reasoningEffort: document.querySelector("#reasoning-effort"),
  onExhausted: document.querySelector("#on-exhausted"),
  selectedModels: document.querySelector("#selected-models"),
  availableModels: document.querySelector("#available-models"),
  selectedCount: document.querySelector("#selected-count"),
  modelSource: document.querySelector("#model-source"),
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
  modelSource: "",
  modelSourcePath: null,
};
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

function renderSelectedModels() {
  const selected = state.config.models;
  elements.selectedModels.replaceChildren();
  elements.selectedCount.textContent = String(selected.length);

  if (!selected.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "还没有 Advisor 模型，请从右侧添加。";
    elements.selectedModels.append(empty);
    return;
  }

  selected.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "model-row";

    const name = document.createElement("div");
    name.className = "model-name";
    name.textContent = `${index + 1}. ${item.id}`;
    if (!state.models.includes(item.id)) {
      const warning = document.createElement("span");
      warning.className = "unavailable";
      warning.textContent = "当前 subagent 列表中不可用";
      name.append(warning);
    }

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
      : "没有读取到 subagent 模型。";
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
      state.config.models.push({ id: model, retries: 1 });
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
  elements.reasoningEffort.value = config.reasoning_effort;
  elements.onExhausted.value = config.on_exhausted;
  updateEnabledLabel();
  elements.modelSource.textContent = state.modelSourcePath
    ? `来源：${state.modelSource} · ${state.modelSourcePath}`
    : `来源：${state.modelSource}`;
  renderModelLists();
}

function collectConfig() {
  return {
    version: 1,
    enabled: elements.enabled.checked,
    mode: elements.mode.value,
    reasoning_effort: elements.reasoningEffort.value,
    on_exhausted: elements.onExhausted.value,
    models: state.config.models.map((item) => ({
      id: item.id,
      retries: item.retries,
    })),
  };
}

async function bootstrap(message = "") {
  showMessage("正在读取配置…");
  try {
    const payload = await api("/api/bootstrap");
    state = {
      config: payload.config,
      models: payload.models,
      modelSource: payload.modelSource,
      modelSourcePath: payload.modelSourcePath,
    };
    render();
    showMessage(message || "已读取当前配置。", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

elements.enabled.addEventListener("change", updateEnabledLabel);
elements.saveBannerClose.addEventListener("click", hideSaveBanner);
elements.refresh.addEventListener("click", () => bootstrap("已重新读取模型列表。"));
elements.save.addEventListener("click", async () => {
  elements.save.disabled = true;
  showMessage("正在保存…");
  try {
    const payload = await api("/api/config", {
      method: "PUT",
      body: JSON.stringify(collectConfig()),
    });
    state.config = payload.config;
    render();
    showMessage("配置已保存，新任务从下一次用户消息开始生效。", "success");
    showSaveBanner(
      "success",
      "配置已保存",
      "新任务会从下一次用户消息开始使用这份配置。",
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
