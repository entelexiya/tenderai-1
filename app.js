"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const config = window.TENDERAI_CONFIG;
  const state = {
    tab: "file",
    file: null,
    reports: [],
    active: null,
    controller: null,
    busy: false,
    example: false,
  };
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = String(text);
    return n;
  };
  const append = (parent, ...children) => {
    parent.append(...children);
    return parent;
  };
  const date = (value) =>
    new Date(value).toLocaleString("ru-RU", {
      dateStyle: "short",
      timeStyle: "short",
    });
  const scoreText = (r) =>
    r.score === null ? "Не рассчитан" : `${r.score} / 100`;
  function demoReport() {
    const createdAt = new Date().toISOString();
    const findings = [
      {
        category: "brand",
        title: "Упоминание бренда",
        page: 2,
        quote:
          "Ноутбук Dell Latitude 5440 или устройство с эквивалентными характеристиками не допускается.",
        action:
          "Уточните, допускается ли эквивалент и чем обосновано указание бренда.",
      },
      {
        category: "technical_specification",
        title: "Детальные технические параметры",
        page: 2,
        quote:
          "Процессор Intel Core i7-1355U, оперативная память 16 ГБ, экран 14 дюймов, разрешение 1920×1080.",
        action:
          "Проверьте, действительно ли все точные параметры необходимы и допускается ли эквивалент с сопоставимыми характеристиками.",
      },
      {
        category: "restriction",
        title: "Ограничение аналогов",
        page: 2,
        quote: "Аналоги и товары с иными характеристиками не принимаются.",
        action:
          "Запросите обоснование ограничения и возможность предложить эквивалент.",
      },
      {
        category: "dealer",
        title: "Требование дилерства",
        page: 3,
        quote:
          "Поставщик должен иметь статус авторизованного дилера производителя.",
        action:
          "Уточните необходимость статуса дилера и допустимые подтверждающие документы.",
      },
      {
        category: "deadline",
        title: "Короткий срок поставки",
        page: 3,
        quote:
          "Поставка должна быть выполнена в течение 2 рабочих дней с даты подписания договора.",
        action:
          "Проверьте точку отсчёта срока и возможность поставки в указанные дни.",
      },
      {
        category: "experience",
        title: "Требование опыта",
        page: 3,
        quote:
          "Опыт работы в сфере поставки компьютерной техники — не менее 7 лет.",
        action: "Уточните обоснование требуемого опыта для предмета закупки.",
      },
    ];
    const components = [
      ["brand", "Упоминание бренда", 15],
      ["technical_specification", "Детальные технические параметры", 15],
      ["restriction", "Ограничение аналогов", 30],
      ["dealer", "Требование дилерства", 20],
      ["deadline", "Короткий срок поставки", 20],
      ["experience", "Требование опыта", 15],
    ].map(([key, label, points]) => ({
      key,
      label,
      points,
      maximum: points,
      count: 1,
    }));
    return {
      schema_version: 2,
      analysis_version: "2.1.0-demo",
      created_at: createdAt,
      document: {
        name: "Учебный тендер — демонстрационный отчёт",
        pages: 4,
        characters: 12480,
        sha256: "demo-report-not-a-user-document",
      },
      mode: "presentation_demo",
      score: 100,
      priority: "high",
      summary: "Демонстрационный пример: есть условия, которые стоит уточнить",
      score_explanation:
        "Подготовленный учебный отчёт для презентации. Он не получен из загруженного файла и не является результатом анализа реального тендера.",
      components,
      findings,
      requirements: [
        { label: "Предмет закупки", value: "Ноутбуки для учебных классов" },
        { label: "Количество", value: "15 шт." },
        { label: "Цена / стоимость", value: "850 000 тенге" },
        { label: "Срок поставки", value: "2 рабочих дня" },
      ],
      warnings: [
        "ДЕМО-РЕЖИМ: это заранее подготовленный пример для презентации, а не анализ вашего документа.",
      ],
      limitations: [
        "Демо-режим не анализирует загруженные файлы.",
        "Для реального документа используйте кнопку «Проверить условия».",
        "Проверка по правилам не устанавливает нарушение закона и не заменяет экспертизу.",
      ],
      supplier_history: { status: "unavailable" },
      ml: {
        status: "not_used_in_demo",
        included_in_score: false,
        note: "В демо-режиме модель не используется.",
      },
      example: true,
    };
  }
  function error(message) {
    $("error").textContent = message;
    $("error").hidden = false;
  }
  function setTab(tab) {
    state.tab = tab;
    for (const name of ["file", "text"]) {
      $(`tab-${name}`).setAttribute("aria-selected", String(name === tab));
      $(`tab-${name}`).tabIndex = name === tab ? 0 : -1;
      $(`panel-${name}`).hidden = name !== tab;
    }
    $("example-note").hidden = !(state.example && tab === "text");
    $("error").hidden = true;
  }
  for (const name of ["file", "text"]) {
    $(`tab-${name}`).addEventListener("click", () => setTab(name));
    $(`tab-${name}`).addEventListener("keydown", (e) => {
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
        e.preventDefault();
        const next =
          e.key === "Home"
            ? "file"
            : e.key === "End"
              ? "text"
              : name === "file"
                ? "text"
                : "file";
        setTab(next);
        $(`tab-${next}`).focus();
      }
    });
  }
  function selectFile(file) {
    if (state.busy) return;
    $("error").hidden = true;
    if (
      file &&
      (!/\.(pdf|txt)$/i.test(file.name) ||
        file.size === 0 ||
        file.size > 10 * 1024 * 1024)
    ) {
      state.file = null;
      $("document-file").value = "";
      updateFile();
      error("Выберите непустой PDF или TXT размером до 10 МБ.");
      return;
    }
    state.file = file;
    updateFile();
  }
  function updateFile() {
    $("file-label").textContent = state.file
      ? state.file.name
      : "Выберите документ";
    $("file-hint").textContent = state.file
      ? `${(state.file.size / 1024).toFixed(1)} КБ · нажмите, чтобы заменить`
      : "или перетащите его сюда";
    $("clear-file").hidden = !state.file;
  }
  $("document-file").addEventListener("change", (e) =>
    selectFile(e.target.files[0] || null),
  );
  $("clear-file").addEventListener("click", () => {
    selectFile(null);
    $("document-file").value = "";
  });
  const zone = $("drop-zone");
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (!state.busy) zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length !== 1) {
      error("Загрузите один документ за раз.");
      return;
    }
    selectFile(e.dataTransfer.files[0]);
  });
  $("example-button").addEventListener("click", () => {
    state.example = true;
    const report = demoReport();
    state.reports.push(report);
    state.active = report;
    render(report);
    renderReports();
    $("example-note").hidden = false;
  });
  $("document-text").addEventListener("input", () => {
    state.example = false;
    $("example-note").hidden = true;
  });
  function busy(value) {
    state.busy = value;
    for (const id of [
      "submit-button",
      "example-button",
      "document-file",
      "document-text",
      "clear-file",
      "tab-file",
      "tab-text",
      "clear-reports",
      "compare-button",
    ])
      $(id).disabled = value;
    document.querySelectorAll("#report-list button").forEach((button) => {
      button.disabled = value;
    });
    $("progress").hidden = !value;
  }
  async function responseJSON(response) {
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(
        "Сервер вернул непонятный ответ. Анализ не выполнен. Попробуйте позже.",
      );
    }
    if (!response.ok)
      throw new Error(
        typeof data?.detail === "string"
          ? data.detail
          : "Сервис не смог выполнить проверку. Попробуйте позже.",
      );
    return data;
  }
  function validateReport(data) {
    const arrays = [
      "findings",
      "components",
      "requirements",
      "warnings",
      "limitations",
    ];
    if (
      !data ||
      data.schema_version !== 2 ||
      !data.document ||
      !arrays.every((k) => Array.isArray(data[k])) ||
      !["none", "review", "high", "incomplete"].includes(data.priority) ||
      !(
        data.score === null ||
        (Number.isFinite(data.score) && data.score >= 0 && data.score <= 100)
      ) ||
      typeof data.summary !== "string" ||
      typeof data.analysis_version !== "string" ||
      !data.ml
    )
      throw new Error(
        "Версия API несовместима с сайтом. Требуется обновление сервера; результат не показан.",
      );
    if (
      !data.components.every(
        (c) =>
          c &&
          Number.isFinite(c.points) &&
          Number.isFinite(c.maximum) &&
          c.maximum > 0 &&
          c.points >= 0 &&
          c.points <= c.maximum,
      )
    )
      throw new Error(
        "Некорректные компоненты результата. Проверка не завершена.",
      );
    const strings = (object, keys) =>
      object && keys.every((key) => typeof object[key] === "string");
    if (
      !strings(data.document, ["name", "sha256"]) ||
      !Number.isInteger(data.document.pages) ||
      data.document.pages < 1 ||
      !Number.isInteger(data.document.characters) ||
      data.document.characters < 1 ||
      !Number.isFinite(Date.parse(data.created_at)) ||
      !data.warnings.every((x) => typeof x === "string") ||
      !data.limitations.every((x) => typeof x === "string") ||
      !data.requirements.every((x) => strings(x, ["label", "value"])) ||
      !data.findings.every(
        (x) =>
          strings(x, ["title", "quote", "action"]) &&
          Number.isInteger(x.page) &&
          x.page > 0,
      ) ||
      !data.components.every(
        (x) => strings(x, ["key", "label"]) && Number.isInteger(x.count),
      ) ||
      !strings(data, ["mode", "score_explanation"])
    ) {
      throw new Error("Некорректный формат отчёта. Результат не показан.");
    }
    return data;
  }
  $("analysis-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.busy) return;
    $("error").hidden = true;
    if (location.protocol === "file:") {
      error(
        "Откройте сайт через локальный сервер, а не как файл. Команда запуска указана в README.",
      );
      return;
    }
    if (state.tab === "file" && !state.file) {
      error("Сначала выберите документ.");
      $("document-file").focus();
      return;
    }
    const text = $("document-text").value.trim();
    if (state.tab === "text" && (text.match(/\p{L}/gu) || []).length < 30) {
      error("Добавьте содержимое документа: не менее 30 букв.");
      $("document-text").focus();
      return;
    }
    const controller = new AbortController();
    state.controller = controller;
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, config.timeoutMs);
    busy(true);
    $("result").hidden = true;
    try {
      const isText = state.tab === "text";
      const body = isText
        ? JSON.stringify({
            text,
            filename: state.example ? "Учебный пример" : "Вставленный текст",
          })
        : new FormData();
      if (!isText) body.append("file", state.file);
      const response = await fetch(
        `${config.apiBase}/api/analyze-${isText ? "text" : "file"}`,
        {
          method: "POST",
          body,
          headers: isText ? { "Content-Type": "application/json" } : {},
          signal: controller.signal,
        },
      );
      const report = validateReport(await responseJSON(response));
      report.example = Boolean(isText && state.example);
      state.reports.push(report);
      state.active = report;
      render(report);
      renderReports();
    } catch (exc) {
      $("result").hidden = true;
      error(
        exc.name === "AbortError"
          ? timedOut
            ? "Сервис не ответил вовремя. Результат не получен. Попробуйте позже; Space может запускаться после простоя."
            : "Ожидание отменено. Результат не получен; сервер мог продолжить обработку."
          : exc instanceof TypeError
            ? "Не удалось связаться с сервером. Проверьте соединение и попробуйте позже."
            : exc.message,
      );
    } finally {
      clearTimeout(timeout);
      state.controller = null;
      busy(false);
    }
  });
  $("cancel-button").addEventListener("click", () => state.controller?.abort());
  async function health() {
    try {
      const response = await fetch(`${config.apiBase}/api/health`, {
        signal: AbortSignal.timeout(12000),
      });
      const data = await responseJSON(response);
      if (data.schema_version !== 2 || data.status !== "ready")
        throw new Error("unavailable");
      $("service-status").textContent =
        data.mode === "rules"
          ? "Доступен · проверка правилами"
          : "Доступен · правила + экспериментальный ML";
      $("service-status").className = "service-status available";
    } catch {
      $("service-status").textContent =
        "Сервис пока недоступен · можно повторить проверку";
      $("service-status").className = "service-status unavailable";
    }
  }
  health();
  function render(r) {
    state.active = r;
    const root = $("result-content");
    root.replaceChildren();
    const summary = el("div", "result-summary");
    const info = el("div");
    append(
      info,
      el("p", "report-name", r.document.name),
      el("h3", `priority-${r.priority}`, r.summary),
      el(
        "p",
        "report-meta",
        `${r.document.pages} стр. · ${r.document.characters.toLocaleString("ru-RU")} символов · ${date(r.created_at)} · версия ${r.analysis_version}`,
      ),
    );
    const score = el("div", "score-box");
    const value = el(
      "div",
      `score-value priority-${r.priority}`,
      r.score === null ? "—" : r.score,
    );
    if (r.score !== null) value.append(el("small", "", " / 100"));
    append(
      score,
      value,
      el(
        "p",
        "",
        r.score === null ? "Индекс не рассчитан" : "Приоритет проверки",
      ),
    );
    append(
      root,
      append(summary, info, score),
      el("p", "score-explanation", r.score_explanation),
    );
    if (r.example)
      root.append(
        el(
          "p",
          "notice",
          "Учебный пример. Этот отчёт не относится к реальной закупке.",
        ),
      );
    for (const warning of r.warnings) root.append(el("p", "warning", warning));
    const grid = el("div", "result-grid");
    const findings = el("div", "finding-list");
    findings.append(
      el("h3", "", `Фрагменты для проверки · ${r.findings.length}`),
    );
    if (!r.findings.length)
      findings.append(
        el(
          "p",
          "empty-state",
          "Настроенные признаки не найдены. Это не подтверждает отсутствие других рисков.",
        ),
      );
    for (const item of r.findings) {
      const card = el("article", "finding");
      append(
        card,
        append(
          el("div", "finding-heading"),
          el("h4", "", item.title),
          el("span", "page-tag", `Стр. ${item.page}`),
        ),
        el("blockquote", "", item.quote),
        el("p", "", item.action),
      );
      findings.append(card);
    }
    const side = el("aside", "result-side");
    side.append(el("h3", "", "Из чего складывается индекс"));
    for (const c of r.components) {
      const component = el("div", "component");
      const fill = el("div", "component-fill");
      fill.style.width = `${(c.points / c.maximum) * 100}%`;
      append(
        component,
        append(
          el("div"),
          el("span", "", c.label),
          el("span", "", `${c.points} / ${c.maximum}`),
        ),
        append(el("div", "component-track"), fill),
      );
      side.append(component);
    }
    side.append(el("h3", "", "Извлечённые условия"));
    if (!r.requirements.length)
      side.append(
        el(
          "p",
          "muted",
          "Не удалось выделить структурированные поля. Проверьте исходный документ.",
        ),
      );
    for (const req of r.requirements)
      side.append(
        append(
          el("dl", "requirement"),
          el("dt", "", req.label),
          el("dd", "", req.value),
        ),
      );
    side.append(
      el("h3", "", "История поставщика"),
      el(
        "p",
        "muted",
        "Не подключена. Истории побед и выводы о сговоре не формируются.",
      ),
    );
    side.append(el("h3", "", "Как выполнена проверка"));
    side.append(
      el(
        "p",
        "muted",
        r.mode === "presentation_demo"
          ? "Подготовленный учебный отчёт: анализ файла не выполнялся."
          : r.ml.note || "Проверка выполнена серверными правилами по тексту документа.",
      ),
    );
    append(root, append(grid, findings, side));
    const limits = el("div", "limitations");
    for (const line of r.limitations) limits.append(el("p", "", line));
    root.append(limits);
    $("result").hidden = false;
    $("result").focus({ preventScroll: true });
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function renderReports() {
    $("report-count").textContent = state.reports.length;
    $("clear-reports").hidden = !state.reports.length;
    $("report-list").replaceChildren();
    if (!state.reports.length)
      $("report-list").append(
        el("p", "empty-state", "Здесь появятся проверенные документы."),
      );
    state.reports.forEach((r, i) => {
      const row = el("div", "report-row");
      const info = append(
        el("div"),
        el("strong", "", `${i + 1}. ${r.document.name}`),
        el(
          "p",
          "",
          `${date(r.created_at)} · индекс ${scoreText(r)}${r.example ? " · учебный пример" : ""}`,
        ),
      );
      const button = el("button", "text-link", "Открыть ↗");
      button.type = "button";
      button.addEventListener("click", () => render(r));
      append(row, info, button);
      $("report-list").append(row);
    });
    $("compare-controls").hidden = state.reports.length < 2;
    for (const key of ["a", "b"]) {
      const select = $(`compare-${key}`);
      select.replaceChildren();
      state.reports.forEach((r, i) => {
        const option = el("option", "", `${i + 1}. ${r.document.name}`);
        option.value = i;
        select.append(option);
      });
    }
    if (state.reports.length > 1) {
      $("compare-a").value = state.reports.length - 2;
      $("compare-b").value = state.reports.length - 1;
    }
    $("comparison").replaceChildren();
  }
  $("clear-reports").addEventListener("click", () => {
    state.reports = [];
    state.active = null;
    $("result").hidden = true;
    $("result-content").replaceChildren();
    renderReports();
  });
  $("new-analysis").addEventListener("click", () => {
    $("result").hidden = true;
    $("workspace").scrollIntoView();
    if (state.tab === "file") {
      selectFile(null);
      $("document-file").value = "";
      $("document-file").focus({ preventScroll: true });
    } else $("document-text").focus({ preventScroll: true });
  });
  $("compare-button").addEventListener("click", () => {
    const container = $("comparison");
    container.replaceChildren();
    if ($("compare-a").value === $("compare-b").value) {
      container.append(el("p", "warning", "Выберите два разных отчёта."));
      return;
    }
    const a = state.reports[Number($("compare-a").value)],
      b = state.reports[Number($("compare-b").value)];
    const compatible =
      a.analysis_version === b.analysis_version &&
      a.score !== null &&
      b.score !== null;
    const note = !compatible
      ? "Общий индекс нельзя сравнить: документ прочитан не полностью или версии методики различаются."
      : a.score === b.score
        ? "Индексы одинаковы. Изучите конкретные условия: одинаковый индекс не означает одинаковые риски."
        : `Индекс документа ${a.score < b.score ? "A" : "B"} ниже на ${Math.abs(a.score - b.score)}. Это разница в признаках для проверки, а не доказательство большей безопасности.`;
    container.append(el("p", "comparison-note", note));
    const table = el("table", "comparison-table");
    const head = el("thead");
    append(
      head,
      append(
        el("tr"),
        el("th", "", "Условие"),
        el("th", "", `A · ${a.document.name}`),
        el("th", "", `B · ${b.document.name}`),
      ),
    );
    table.append(head);
    const body = el("tbody");
    append(
      body,
      append(
        el("tr"),
        el("th", "", "Индекс"),
        el("td", "", scoreText(a)),
        el("td", "", scoreText(b)),
      ),
    );
    for (const c of a.components) {
      const other = b.components.find((x) => x.key === c.key);
      append(
        body,
        append(
          el("tr"),
          el("th", "", c.label),
          el("td", "", `${c.count} фрагм.`),
          el("td", "", other ? `${other.count} фрагм.` : "Нет данных"),
        ),
      );
    }
    for (const label of new Set(
      [...a.requirements, ...b.requirements].map((x) => x.label),
    ))
      append(
        body,
        append(
          el("tr"),
          el("th", "", label),
          el(
            "td",
            "",
            a.requirements.find((x) => x.label === label)?.value ||
              "Не извлечено",
          ),
          el(
            "td",
            "",
            b.requirements.find((x) => x.label === label)?.value ||
              "Не извлечено",
          ),
        ),
      );
    table.append(body);
    container.append(table);
  });
  function reportText(r) {
    return [
      "TenderAI — предварительная проверка",
      r.document.name,
      `Дата: ${date(r.created_at)}; версия: ${r.analysis_version}; режим: ${r.mode}`,
      `SHA-256 текста: ${r.document.sha256}`,
      r.example ? "УЧЕБНЫЙ ПРИМЕР" : "",
      r.summary,
      `Индекс: ${scoreText(r)}`,
      r.score_explanation,
      ...r.warnings,
      "",
      "ФРАГМЕНТЫ",
      ...r.findings.map(
        (f) => `${f.title} (стр. ${f.page})\n${f.quote}\n${f.action}\n`,
      ),
      "УСЛОВИЯ",
      ...r.requirements.map((x) => `${x.label}: ${x.value}`),
      "",
      "КОМПОНЕНТЫ",
      ...r.components.map(
        (c) => `${c.label}: ${c.points}/${c.maximum}; фрагментов ${c.count}`,
      ),
      "",
      "ML",
      JSON.stringify(r.ml),
      "",
      ...r.limitations,
    ].join("\n");
  }
  function download(kind) {
    if (!state.active) return;
    const json = kind === "json";
    const blob = new Blob(
      [json ? JSON.stringify(state.active, null, 2) : reportText(state.active)],
      {
        type: json
          ? "application/json;charset=utf-8"
          : "text/plain;charset=utf-8",
      },
    );
    const url = URL.createObjectURL(blob);
    const link = el("a");
    link.href = url;
    link.download = `tenderai-${state.active.document.sha256.slice(0, 12)}.${kind}`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $("export-text").addEventListener("click", () => download("txt"));
  $("export-json").addEventListener("click", () => download("json"));
  $("print-report").addEventListener("click", () => window.print());
})();
