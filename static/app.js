"use strict";

// ---- 共通ヘルパ -----------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = "エラーが発生しました";
    try { msg = (await res.json()).error || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

const yen = (n) => Number(n || 0).toLocaleString("ja-JP");

// 事業分 = 金額 × 事業割合(%)（四捨五入）。バックエンドの business_share と揃える
const bizShare = (amount, ratio) =>
  Math.round((Number(amount || 0) * (ratio ?? 100)) / 100);

// 固定資産の償却区分の表示名
const METHOD_LABELS = {
  straight_line: "通常",
  lump_sum_3y: "一括償却",
  small_special: "少額特例",
};

let META = { payments: [], today: "" };
let CATEGORIES = [];

// ---- タブ切り替え ---------------------------------------------------------
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "list") loadList();
    if (btn.dataset.tab === "income") loadIncome();
    if (btn.dataset.tab === "summary") loadSummary();
    if (btn.dataset.tab === "assets") loadAssets();
    if (btn.dataset.tab === "quotes") loadQuotes();
  });
});

// ---- 初期化 ---------------------------------------------------------------
async function init() {
  META = await api("/api/meta");
  CATEGORIES = await api("/api/categories");

  // 支払方法
  $("#f-payment").innerHTML =
    '<option value=""></option>' +
    META.payments.map((p) => `<option>${p}</option>`).join("");

  // 勘定科目セレクト
  fillCategorySelects();

  // 収入科目セレクト
  $("#i-category").innerHTML = (META.income_categories || [])
    .map((c) => `<option>${c}</option>`)
    .join("");

  // 日付の初期値＝今日
  $("#f-date").value = META.today;
  $("#i-date").value = META.today;

  // 年セレクト
  await fillYearSelects();

  // 支払先サジェスト
  refreshPayeeList();
}

function fillCategorySelects() {
  const opts = CATEGORIES.map((c) => `<option>${c}</option>`).join("");
  $("#f-category").innerHTML = opts;
  $("#filter-category").innerHTML =
    '<option value="">科目：すべて</option>' +
    CATEGORIES.map((c) => `<option>${c}</option>`).join("");
}

async function fillYearSelects() {
  const years = await api("/api/years");
  const optHtml = years.map((y) => `<option>${y}</option>`).join("");
  $("#filter-year").innerHTML = optHtml;
  $("#summary-year").innerHTML = optHtml;
  $("#dep-year").innerHTML = optHtml;
  $("#income-filter-year").innerHTML = optHtml;
  // 月セレクト
  $("#filter-month").innerHTML =
    '<option value="">月：すべて</option>' +
    Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}">${i + 1}月</option>`).join("");
}

async function refreshPayeeList() {
  const rows = await api("/api/expenses");
  const payees = [...new Set(rows.map((r) => r.payee).filter(Boolean))];
  $("#payee-list").innerHTML = payees.map((p) => `<option value="${p}">`).join("");
}

// ---- 入力フォーム ---------------------------------------------------------
$("#expense-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("#edit-id").value;
  const data = {
    date: $("#f-date").value,
    category: $("#f-category").value,
    amount: $("#f-amount").value,
    business_ratio: Number($("#f-ratio").value || 100),
    payee: $("#f-payee").value.trim(),
    payment: $("#f-payment").value,
    memo: $("#f-memo").value.trim(),
    receipt: $("#f-receipt").checked,
  };
  if (!data.date || !data.category || data.amount === "") return;

  try {
    if (id) {
      await api(`/api/expenses/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#form-msg", "更新しました");
      resetForm();
    } else {
      await api("/api/expenses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#form-msg", `登録しました（${yen(data.amount)}円）`);
      // 連続入力しやすいよう日付・科目は残し金額等のみクリア
      $("#f-amount").value = "";
      $("#f-payee").value = "";
      $("#f-memo").value = "";
      $("#f-receipt").checked = false;
      $("#f-amount").focus();
    }
    await fillYearSelects();
    refreshPayeeList();
  } catch (err) {
    showMsg("#form-msg", err.message, true);
  }
});

$("#cancel-edit").addEventListener("click", resetForm);

function resetForm() {
  $("#edit-id").value = "";
  $("#expense-form").reset();
  $("#f-date").value = META.today;
  $("#form-title").textContent = "経費を入力";
  $("#submit-btn").textContent = "登録する";
  $("#cancel-edit").hidden = true;
}

function startEdit(row) {
  $("#edit-id").value = row.id;
  $("#f-date").value = row.date;
  $("#f-category").value = row.category;
  $("#f-amount").value = row.amount;
  $("#f-ratio").value = row.business_ratio ?? 100;
  $("#f-payee").value = row.payee || "";
  $("#f-payment").value = row.payment || "";
  $("#f-memo").value = row.memo || "";
  $("#f-receipt").checked = !!row.receipt;
  $("#form-title").textContent = `経費を編集（#${row.id}）`;
  $("#submit-btn").textContent = "更新する";
  $("#cancel-edit").hidden = false;
  // 入力タブへ
  $('.tab[data-tab="input"]').click();
  $('.tab[data-tab="input"]').classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showMsg(sel, text, isError) {
  const el = $(sel);
  el.textContent = text;
  el.style.color = isError ? "var(--danger)" : "var(--green)";
  if (!isError) setTimeout(() => (el.textContent = ""), 3000);
}

// ---- 一覧 -----------------------------------------------------------------
async function loadList() {
  const params = new URLSearchParams();
  const y = $("#filter-year").value;
  const m = $("#filter-month").value;
  const c = $("#filter-category").value;
  const k = $("#filter-keyword").value.trim();
  if (y) params.set("year", y);
  if (m) params.set("month", m);
  if (c) params.set("category", c);
  if (k) params.set("keyword", k);

  const rows = await api("/api/expenses?" + params.toString());
  const tbody = $("#expense-table tbody");
  tbody.innerHTML = "";
  let total = 0;

  rows.forEach((r) => {
    total += r.amount;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.date}</td>
      <td>${r.category}</td>
      <td class="num">${yen(r.amount)}</td>
      <td class="num">${r.business_ratio ?? 100}%</td>
      <td class="num">${yen(bizShare(r.amount, r.business_ratio))}</td>
      <td>${esc(r.payee)}</td>
      <td>${esc(r.payment)}</td>
      <td>${esc(r.memo)}</td>
      <td>${r.receipt ? "✓" : ""}</td>
      <td class="num">
        <button class="row-btn edit">編集</button>
        <button class="row-btn del">削除</button>
      </td>`;
    tr.querySelector(".edit").addEventListener("click", () => startEdit(r));
    tr.querySelector(".del").addEventListener("click", () => removeExpense(r));
    tbody.appendChild(tr);
  });

  $("#list-total-amount").textContent = yen(total);
  $("#list-count").textContent = rows.length;
  $("#list-empty").hidden = rows.length > 0;
}

async function removeExpense(row) {
  if (!confirm(`この経費を削除しますか？\n${row.date} ${row.category} ${yen(row.amount)}円`)) return;
  await api(`/api/expenses/${row.id}`, { method: "DELETE" });
  loadList();
  refreshPayeeList();
}

function esc(s) {
  return (s || "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

["filter-year", "filter-month", "filter-category"].forEach((id) =>
  $("#" + id).addEventListener("change", loadList)
);
$("#filter-keyword").addEventListener("input", debounce(loadList, 250));

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---- 集計 -----------------------------------------------------------------
async function loadSummary() {
  const year = $("#summary-year").value;
  const s = await api("/api/summary?year=" + year);

  $("#sum-total").textContent = yen(s.total);
  $("#sum-count").textContent = s.count;
  $("#sum-income").textContent = yen(s.income_total);
  $("#sum-profit").textContent = yen(s.profit);
  $("#sum-withholding").textContent = yen(s.withholding_total);
  $("#export-btn").href = "/api/export.csv?year=" + year;

  // 減価償却費の注記（科目別・年間合計には含むが、月別推移には含めない）
  const note = $("#dep-note");
  if (s.depreciation_total) {
    note.textContent =
      `※ 年間合計と科目別集計には固定資産の減価償却費 ${yen(s.depreciation_total)}円（事業分）を` +
      `含んでいます。月別推移は実際の支出のみのため、合計とは一致しません。`;
    note.hidden = false;
  } else {
    note.hidden = true;
  }

  // 科目別
  const tbody = $("#cat-table tbody");
  tbody.innerHTML = "";
  s.by_category.forEach((c) => {
    const pct = s.total ? ((c.total / s.total) * 100).toFixed(1) : "0.0";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${c.category}</td><td class="num">${yen(c.total)}</td><td class="num">${c.count}</td><td class="num">${pct}%</td>`;
    tbody.appendChild(tr);
  });
  if (s.by_category.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">この年のデータはありません</td></tr>';
  }

  // 月別チャート
  const max = Math.max(...s.by_month.map((m) => m.total), 1);
  $("#month-chart").innerHTML = s.by_month
    .map((m) => {
      const h = (m.total / max) * 100;
      return `<div class="bar-col">
        <div class="bar-val">${m.total ? yen(m.total) : ""}</div>
        <div class="bar" style="height:${h}%" title="${m.month}月: ${yen(m.total)}円"></div>
        <div class="bar-label">${m.month}</div>
      </div>`;
    })
    .join("");
}

$("#summary-year").addEventListener("change", loadSummary);

// ---- 勘定科目の追加 -------------------------------------------------------
$("#cat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#new-cat").value.trim();
  if (!name) return;
  await api("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  $("#new-cat").value = "";
  CATEGORIES = await api("/api/categories");
  fillCategorySelects();
  showMsg("#cat-msg", `「${name}」を追加しました`);
});

// ---- 固定資産 -------------------------------------------------------------
async function loadAssets() {
  const rows = await api("/api/assets");
  const tbody = $("#asset-table tbody");
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(r.name)}</td>
      <td>${METHOD_LABELS[r.depreciation_method] || r.depreciation_method}</td>
      <td>${r.acquisition_date}</td>
      <td class="num">${yen(r.acquisition_cost)}</td>
      <td class="num">${r.useful_life_years}年</td>
      <td class="num">${r.business_ratio}%</td>
      <td>${r.disposal_date || ""}</td>
      <td class="num">
        <button class="row-btn edit">編集</button>
        <button class="row-btn del">削除</button>
      </td>`;
    tr.querySelector(".edit").addEventListener("click", () => startEditAsset(r));
    tr.querySelector(".del").addEventListener("click", () => removeAsset(r));
    tbody.appendChild(tr);
  });
  $("#asset-empty").hidden = rows.length > 0;

  // 減価償却の明細も更新
  await loadDepreciation();
}

$("#asset-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("#asset-edit-id").value;
  const data = {
    name: $("#a-name").value.trim(),
    acquisition_cost: Number($("#a-cost").value),
    acquisition_date: $("#a-acq-date").value,
    depreciation_method: $("#a-method").value,
    useful_life_years: Number($("#a-life").value),
    business_ratio: Number($("#a-ratio").value || 100),
    disposal_date: $("#a-disposal").value || null,
    memo: $("#a-memo").value.trim(),
  };
  if (!data.name || !data.acquisition_date || !data.acquisition_cost || !data.useful_life_years) {
    return;
  }

  try {
    if (id) {
      await api(`/api/assets/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#asset-msg", "更新しました");
    } else {
      await api("/api/assets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#asset-msg", `登録しました（${esc(data.name)}）`);
    }
    resetAssetForm();
    await fillYearSelects();
    await loadAssets();
  } catch (err) {
    showMsg("#asset-msg", err.message, true);
  }
});

$("#asset-cancel-edit").addEventListener("click", resetAssetForm);

function resetAssetForm() {
  $("#asset-edit-id").value = "";
  $("#asset-form").reset();
  $("#a-ratio").value = "100";
  $("#asset-form-title").textContent = "固定資産を登録";
  $("#asset-submit-btn").textContent = "登録する";
  $("#asset-cancel-edit").hidden = true;
}

function startEditAsset(row) {
  $("#asset-edit-id").value = row.id;
  $("#a-name").value = row.name;
  $("#a-cost").value = row.acquisition_cost;
  $("#a-acq-date").value = row.acquisition_date;
  $("#a-method").value = row.depreciation_method || "straight_line";
  $("#a-life").value = row.useful_life_years;
  $("#a-ratio").value = row.business_ratio;
  $("#a-disposal").value = row.disposal_date || "";
  $("#a-memo").value = row.memo || "";
  $("#asset-form-title").textContent = `固定資産を編集（#${row.id}）`;
  $("#asset-submit-btn").textContent = "更新する";
  $("#asset-cancel-edit").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function removeAsset(row) {
  if (!confirm(`この固定資産を削除しますか？\n${row.name}（${yen(row.acquisition_cost)}円）`)) return;
  await api(`/api/assets/${row.id}`, { method: "DELETE" });
  await fillYearSelects();
  loadAssets();
}

// ---- 減価償却の明細 -------------------------------------------------------
async function loadDepreciation() {
  const year = $("#dep-year").value;
  const d = await api("/api/depreciation?year=" + year);

  $("#dep-total").textContent = yen(d.total_business_amount);
  $("#dep-export-btn").href = "/api/assets_export.csv?year=" + year;

  const tbody = $("#dep-table tbody");
  tbody.innerHTML = "";
  d.details.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(r.name)}</td>
      <td>${METHOD_LABELS[r.method] || r.method}</td>
      <td class="num">${yen(r.acquisition_cost)}</td>
      <td class="num">${r.useful_life_years}年</td>
      <td class="num">${r.rate.toFixed(3)}</td>
      <td class="num">${r.business_ratio}%</td>
      <td class="num">${r.months}か月</td>
      <td class="num">${yen(r.opening_book_value)}</td>
      <td class="num">${yen(r.depreciation_amount)}</td>
      <td class="num">${yen(r.business_amount)}</td>
      <td class="num">${yen(r.closing_book_value)}</td>`;
    tbody.appendChild(tr);
  });
  if (d.details.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty">この年に償却する固定資産はありません</td></tr>';
  }
}

$("#dep-year").addEventListener("change", loadDepreciation);

// ---- 収入 -----------------------------------------------------------------
async function loadIncome() {
  const params = new URLSearchParams();
  const y = $("#income-filter-year").value;
  const k = $("#income-filter-keyword").value.trim();
  if (y) params.set("year", y);
  if (k) params.set("keyword", k);
  $("#income-export-btn").href = "/api/incomes_export.csv?year=" + (y || "");

  const rows = await api("/api/incomes?" + params.toString());
  const tbody = $("#income-table tbody");
  tbody.innerHTML = "";
  let total = 0;
  rows.forEach((r) => {
    total += r.amount;
    const tr = document.createElement("tr");
    const wh = r.withholding || 0;
    tr.innerHTML = `
      <td>${r.date}</td>
      <td>${r.category}</td>
      <td class="num">${yen(r.amount)}</td>
      <td class="num">${wh ? yen(wh) : "—"}</td>
      <td class="num">${yen(r.amount - wh)}</td>
      <td>${esc(r.payer)}</td>
      <td>${esc(r.memo)}</td>
      <td class="num">
        <button class="row-btn edit">編集</button>
        <button class="row-btn del">削除</button>
      </td>`;
    tr.querySelector(".edit").addEventListener("click", () => startEditIncome(r));
    tr.querySelector(".del").addEventListener("click", () => removeIncome(r));
    tbody.appendChild(tr);
  });
  $("#income-total-amount").textContent = yen(total);
  $("#income-count").textContent = rows.length;
  $("#income-empty").hidden = rows.length > 0;

  // 取引先サジェスト
  const payers = [...new Set(rows.map((r) => r.payer).filter(Boolean))];
  $("#payer-list").innerHTML = payers.map((p) => `<option value="${p}">`).join("");
}

$("#income-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("#income-edit-id").value;
  const data = {
    date: $("#i-date").value,
    category: $("#i-category").value,
    amount: $("#i-amount").value,
    withholding: $("#i-withholding").value || 0,
    payer: $("#i-payer").value.trim(),
    memo: $("#i-memo").value.trim(),
  };
  if (!data.date || !data.category || data.amount === "") return;

  try {
    if (id) {
      await api(`/api/incomes/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#income-msg", "更新しました");
      resetIncomeForm();
    } else {
      await api("/api/incomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#income-msg", `登録しました（${yen(data.amount)}円）`);
      // 連続入力しやすいよう日付・科目は残し金額等のみクリア
      $("#i-amount").value = "";
      $("#i-withholding").value = "";
      $("#i-payer").value = "";
      $("#i-memo").value = "";
      $("#i-amount").focus();
    }
    await fillYearSelects();
    loadIncome();
  } catch (err) {
    showMsg("#income-msg", err.message, true);
  }
});

$("#income-cancel-edit").addEventListener("click", resetIncomeForm);

function resetIncomeForm() {
  $("#income-edit-id").value = "";
  $("#income-form").reset();
  $("#i-date").value = META.today;
  $("#income-form-title").textContent = "収入を入力";
  $("#income-submit-btn").textContent = "登録する";
  $("#income-cancel-edit").hidden = true;
}

function startEditIncome(row) {
  $("#income-edit-id").value = row.id;
  $("#i-date").value = row.date;
  $("#i-category").value = row.category;
  $("#i-amount").value = row.amount;
  $("#i-withholding").value = row.withholding || "";
  $("#i-payer").value = row.payer || "";
  $("#i-memo").value = row.memo || "";
  $("#income-form-title").textContent = `収入を編集（#${row.id}）`;
  $("#income-submit-btn").textContent = "更新する";
  $("#income-cancel-edit").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function removeIncome(row) {
  if (!confirm(`この収入を削除しますか？\n${row.date} ${row.category} ${yen(row.amount)}円`)) return;
  await api(`/api/incomes/${row.id}`, { method: "DELETE" });
  await fillYearSelects();
  loadIncome();
}

["income-filter-year"].forEach((id) =>
  $("#" + id).addEventListener("change", loadIncome)
);
$("#income-filter-keyword").addEventListener("input", debounce(loadIncome, 250));

// ---- 見積書 ---------------------------------------------------------------
let CLIENTS = [];
const TAX_MODE_LABELS = { exclusive: "税抜", inclusive: "税込" };

// バックエンドの quotes.compute_totals と必ず揃える（円未満切り捨て）
function quoteTotals(lineAmounts, taxMode, taxRate) {
  const gross = lineAmounts.reduce((a, b) => a + b, 0);
  if (taxMode === "inclusive") {
    const subtotal = Math.floor((gross * 100) / (100 + taxRate));
    return { subtotal, tax: gross - subtotal, total: gross };
  }
  const tax = Math.floor((gross * taxRate) / 100);
  return { subtotal: gross, tax, total: gross + tax };
}

async function loadQuotes() {
  // 取引先マスタと既定値（発行日＝今日）を用意
  CLIENTS = await api("/api/clients");
  fillClientSelect();
  if (!$("#q-issue-date").value) $("#q-issue-date").value = META.today;
  if ($("#quote-item-table tbody").children.length === 0) addItemRow();
  recalcQuote();

  const rows = await api("/api/quotes");
  const tbody = $("#quote-table tbody");
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(r.quote_no)}</td>
      <td>${r.issue_date}</td>
      <td>${esc(r.client_name)} ${esc(r.honorific)}</td>
      <td>${esc(r.subject)}</td>
      <td class="num">${yen(r.total)}</td>
      <td class="num">
        <button class="row-btn print">印刷</button>
        <button class="row-btn edit">編集</button>
        <button class="row-btn del">削除</button>
      </td>`;
    tr.querySelector(".print").addEventListener("click", () => printQuote(r));
    tr.querySelector(".edit").addEventListener("click", () => startEditQuote(r));
    tr.querySelector(".del").addEventListener("click", () => removeQuote(r));
    tbody.appendChild(tr);
  });
  $("#quote-empty").hidden = rows.length > 0;
}

function fillClientSelect() {
  $("#q-client").innerHTML =
    '<option value="">（直接入力）</option>' +
    CLIENTS.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
}

// 取引先マスタを選んだら宛名・敬称を流し込む
$("#q-client").addEventListener("change", () => {
  const c = CLIENTS.find((x) => String(x.id) === $("#q-client").value);
  if (c) {
    $("#q-client-name").value = c.name;
    $("#q-honorific").value = c.honorific || "御中";
  }
});

// ---- 明細の行 -------------------------------------------------------------
function addItemRow(item) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="qi-name" placeholder="例: トップページ制作" /></td>
    <td class="num"><input type="number" class="qi-qty num" min="0" step="1" value="1" /></td>
    <td><input type="text" class="qi-unit" placeholder="式" /></td>
    <td class="num"><input type="number" class="qi-price num" min="0" step="1" value="0" /></td>
    <td class="num qi-amount">0</td>
    <td class="num"><button type="button" class="row-btn del">削除</button></td>`;
  if (item) {
    tr.querySelector(".qi-name").value = item.name || "";
    tr.querySelector(".qi-qty").value = item.quantity ?? 1;
    tr.querySelector(".qi-unit").value = item.unit || "";
    tr.querySelector(".qi-price").value = item.unit_price ?? 0;
  }
  tr.querySelectorAll("input").forEach((inp) =>
    inp.addEventListener("input", recalcQuote)
  );
  tr.querySelector(".del").addEventListener("click", () => {
    tr.remove();
    if ($("#quote-item-table tbody").children.length === 0) addItemRow();
    recalcQuote();
  });
  $("#quote-item-table tbody").appendChild(tr);
}

$("#q-add-item").addEventListener("click", () => addItemRow());
$("#q-tax-mode").addEventListener("change", recalcQuote);
$("#q-tax-rate").addEventListener("input", recalcQuote);

function collectItems() {
  return [...$$("#quote-item-table tbody tr")]
    .map((tr) => ({
      name: tr.querySelector(".qi-name").value.trim(),
      quantity: Number(tr.querySelector(".qi-qty").value || 0),
      unit: tr.querySelector(".qi-unit").value.trim(),
      unit_price: Number(tr.querySelector(".qi-price").value || 0),
    }))
    .filter((it) => it.name !== "");
}

function recalcQuote() {
  const rows = [...$$("#quote-item-table tbody tr")];
  const lineAmounts = [];
  rows.forEach((tr) => {
    const qty = Number(tr.querySelector(".qi-qty").value || 0);
    const price = Number(tr.querySelector(".qi-price").value || 0);
    const amount = qty * price;
    tr.querySelector(".qi-amount").textContent = yen(amount);
    if (tr.querySelector(".qi-name").value.trim() !== "") lineAmounts.push(amount);
  });
  const t = quoteTotals(lineAmounts, $("#q-tax-mode").value, Number($("#q-tax-rate").value || 0));
  $("#q-subtotal").textContent = yen(t.subtotal);
  $("#q-tax").textContent = yen(t.tax);
  $("#q-total").textContent = yen(t.total);
}

// ---- 保存・編集・削除 -----------------------------------------------------
$("#quote-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("#quote-edit-id").value;
  const items = collectItems();
  if (items.length === 0) {
    showMsg("#quote-msg", "明細を1行以上入力してください", true);
    return;
  }
  const data = {
    client_id: $("#q-client").value ? Number($("#q-client").value) : null,
    client_name: $("#q-client-name").value.trim(),
    honorific: $("#q-honorific").value,
    subject: $("#q-subject").value.trim(),
    issue_date: $("#q-issue-date").value,
    valid_until: $("#q-valid-until").value || null,
    tax_mode: $("#q-tax-mode").value,
    tax_rate: Number($("#q-tax-rate").value || 0),
    notes: $("#q-notes").value.trim(),
    items,
  };
  if (!data.client_name || !data.issue_date) return;

  try {
    if (id) {
      await api(`/api/quotes/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#quote-msg", "更新しました");
    } else {
      const created = await api("/api/quotes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#quote-msg", `保存しました（${created.quote_no}）`);
    }
    resetQuoteForm();
    loadQuotes();
  } catch (err) {
    showMsg("#quote-msg", err.message, true);
  }
});

$("#quote-cancel-edit").addEventListener("click", resetQuoteForm);

function resetQuoteForm() {
  $("#quote-edit-id").value = "";
  $("#quote-form").reset();
  $("#q-issue-date").value = META.today;
  $("#q-tax-rate").value = "10";
  $("#quote-item-table tbody").innerHTML = "";
  addItemRow();
  recalcQuote();
  $("#quote-form-title").textContent = "見積書を作成";
  $("#quote-submit-btn").textContent = "この内容で保存する";
  $("#quote-cancel-edit").hidden = true;
}

function startEditQuote(row) {
  $("#quote-edit-id").value = row.id;
  $("#q-client").value = row.client_id ? String(row.client_id) : "";
  $("#q-client-name").value = row.client_name || "";
  $("#q-honorific").value = row.honorific || "御中";
  $("#q-subject").value = row.subject || "";
  $("#q-issue-date").value = row.issue_date;
  $("#q-valid-until").value = row.valid_until || "";
  $("#q-tax-mode").value = row.tax_mode || "exclusive";
  $("#q-tax-rate").value = row.tax_rate ?? 10;
  $("#q-notes").value = row.notes || "";
  $("#quote-item-table tbody").innerHTML = "";
  (row.items || []).forEach((it) => addItemRow(it));
  if ((row.items || []).length === 0) addItemRow();
  recalcQuote();
  $("#quote-form-title").textContent = `見積書を編集（${row.quote_no}）`;
  $("#quote-submit-btn").textContent = "更新する";
  $("#quote-cancel-edit").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function removeQuote(row) {
  if (!confirm(`この見積書を削除しますか？\n${row.quote_no} ${row.client_name}様 ${yen(row.total)}円`))
    return;
  await api(`/api/quotes/${row.id}`, { method: "DELETE" });
  loadQuotes();
}

// この宛先を取引先マスタに保存（次回から選んで使える）
$("#q-save-client").addEventListener("click", async () => {
  const name = $("#q-client-name").value.trim();
  if (!name) {
    showMsg("#quote-msg", "宛名を入力してから保存してください", true);
    return;
  }
  try {
    await api("/api/clients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, honorific: $("#q-honorific").value }),
    });
    CLIENTS = await api("/api/clients");
    fillClientSelect();
    const saved = CLIENTS.find((c) => c.name === name);
    if (saved) $("#q-client").value = String(saved.id);
    showMsg("#quote-msg", `「${name}」を取引先に保存しました`);
  } catch (err) {
    showMsg("#quote-msg", err.message, true);
  }
});

// ---- 印刷（ブラウザのPDF保存を使う） --------------------------------------
function printQuote(q) {
  const itemsHtml = (q.items || [])
    .map(
      (it) => `<tr>
        <td>${esc(it.name)}</td>
        <td class="num">${yen(it.quantity)}</td>
        <td>${esc(it.unit)}</td>
        <td class="num">${yen(it.unit_price)}</td>
        <td class="num">${yen(it.amount)}</td>
      </tr>`
    )
    .join("");
  const taxLabel = TAX_MODE_LABELS[q.tax_mode] || "";
  $("#print-area").innerHTML = `
    <div class="quote-doc">
      <h1 class="quote-doc-title">御 見 積 書</h1>
      <div class="quote-doc-head">
        <div class="quote-doc-to">
          <div class="to-name">${esc(q.client_name)} <span>${esc(q.honorific)}</span></div>
          ${q.subject ? `<div class="to-subject">件名：${esc(q.subject)}</div>` : ""}
        </div>
        <div class="quote-doc-meta">
          <div>見積番号：${esc(q.quote_no)}</div>
          <div>発行日：${q.issue_date}</div>
          ${q.valid_until ? `<div>有効期限：${q.valid_until}</div>` : ""}
        </div>
      </div>
      <div class="quote-doc-grandtotal">お見積金額　<strong>¥${yen(q.total)}</strong>（${taxLabel}）</div>
      <table class="quote-doc-table">
        <thead>
          <tr><th>品名・項目</th><th class="num">数量</th><th>単位</th><th class="num">単価</th><th class="num">金額</th></tr>
        </thead>
        <tbody>${itemsHtml}</tbody>
        <tfoot>
          <tr><td colspan="4" class="num">小計（税抜）</td><td class="num">${yen(q.subtotal)}</td></tr>
          <tr><td colspan="4" class="num">消費税（${q.tax_rate}%）</td><td class="num">${yen(q.tax)}</td></tr>
          <tr class="grand"><td colspan="4" class="num">合計</td><td class="num">¥${yen(q.total)}</td></tr>
        </tfoot>
      </table>
      ${q.notes ? `<div class="quote-doc-notes">備考：${esc(q.notes)}</div>` : ""}
    </div>`;
  document.body.classList.add("printing");
  window.print();
}

// 印刷終了後は画面を元に戻す
window.addEventListener("afterprint", () => {
  document.body.classList.remove("printing");
  $("#print-area").innerHTML = "";
});

// ---- 起動 -----------------------------------------------------------------
init();
