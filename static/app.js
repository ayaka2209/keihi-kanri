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
    if (btn.dataset.tab === "invoices") loadInvoices();
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
  // 取引先マスタ・発行元設定と既定値（発行日＝今日）を用意
  CLIENTS = await api("/api/clients");
  fillClientSelect();
  await loadSettings(); // 見積の印刷でも発行者情報を出せるように
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
        <button class="row-btn to-invoice">請求書に変換</button>
        <button class="row-btn edit">編集</button>
        <button class="row-btn del">削除</button>
      </td>`;
    tr.querySelector(".print").addEventListener("click", () => printQuote(r));
    tr.querySelector(".to-invoice").addEventListener("click", () => convertQuoteToInvoice(r));
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
// 見積書・請求書で共通の帳票HTMLを組み立てる（テラコッタ調デザイン）。
// kind: "quote" | "invoice"。見た目は共通で、ラベルと振込先の有無だけ切り替える。
function buildDocHtml(kind, doc) {
  const isInvoice = kind === "invoice";
  const s = SETTINGS || {};
  const taxLabel = TAX_MODE_LABELS[doc.tax_mode] || "";
  const no = isInvoice ? doc.invoice_no : doc.quote_no;
  const title = isInvoice ? "御 請 求 書" : "御 見 積 書";
  const noLabel = isInvoice ? "請求No." : "見積No.";
  const intro = isInvoice ? "下記の通りご請求申し上げます。" : "下記の通り御見積申し上げます。";
  const amountLabel = (isInvoice ? "御請求金額" : "御見積金額") + `（${taxLabel}）`;
  const sectionLabel = isInvoice ? "ご請求の内訳" : "お見積の内訳";
  const termLabel = isInvoice ? "お支払い期限" : "有効期限";
  const termValue = isInvoice ? doc.due_date : doc.valid_until;

  const itemsHtml = (doc.items || [])
    .map(
      (it, i) => `<tr>
        <td class="num">${i + 1}</td>
        <td>${esc(it.name)}</td>
        <td class="num">${yen(it.quantity)}</td>
        <td>${esc(it.unit)}</td>
        <td class="num">¥${yen(it.unit_price)}</td>
        <td class="num">¥${yen(it.amount)}</td>
      </tr>`
    )
    .join("");

  // 発行者ブロック（設定から流し込み）
  const issuerLines = [];
  if (s.tel) issuerLines.push(`TEL：${esc(s.tel)}`);
  if (s.email) issuerLines.push(`Mail：${esc(s.email)}`);
  const addr = [s.postal_code ? `〒${esc(s.postal_code)}` : "", esc(s.address || "")]
    .filter(Boolean)
    .join(" ");
  if (addr.trim()) issuerLines.push(addr);
  if (s.registration_no) issuerLines.push(`登録番号：${esc(s.registration_no)}`);
  const issuerHtml =
    s.business_name || issuerLines.length
      ? `<div class="doc-issuer">
          <div class="doc-issuer-label">［発行者］</div>
          ${s.business_name ? `<div class="doc-issuer-name">${esc(s.business_name)}</div>` : ""}
          ${issuerLines.map((l) => `<div>${l}</div>`).join("")}
        </div>`
      : "";

  // 税込は合計1行、税抜は小計＋消費税を出す
  const footerHtml =
    doc.tax_mode === "inclusive"
      ? `<tr class="subtotal-row"><td colspan="5" class="num">合計（税込）</td><td class="num">¥${yen(doc.total)}</td></tr>
         <tr><td colspan="5" class="num muted">（内 消費税 ${doc.tax_rate}%）</td><td class="num muted">¥${yen(doc.tax)}</td></tr>`
      : `<tr class="subtotal-row"><td colspan="5" class="num">小計（税抜）</td><td class="num">¥${yen(doc.subtotal)}</td></tr>
         <tr class="subtotal-row"><td colspan="5" class="num">消費税（${doc.tax_rate}%）</td><td class="num">¥${yen(doc.tax)}</td></tr>`;

  // 振込先（請求書のみ・設定のテキストを枠に流し込む）
  const bankHtml =
    isInvoice && s.bank_info
      ? `<div class="quote-doc-bank">
          <div class="quote-doc-bank-head">お振込先</div>
          <div class="quote-doc-bank-body">${esc(s.bank_info)}</div>
        </div>`
      : "";

  // 備考（改行があれば箇条書き）
  const noteLines = (doc.notes || "")
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean);
  const notesHtml = noteLines.length
    ? `<div class="quote-doc-notes-title">備考</div>
       <ul class="quote-doc-notes">${noteLines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>`
    : "";

  return `
    <div class="quote-doc">
      <h1 class="quote-doc-title">${title}</h1>
      ${doc.subject ? `<div class="quote-doc-subtitle">${esc(doc.subject)}</div>` : ""}
      <div class="quote-doc-head">
        <div class="quote-doc-to">
          <div class="to-name">${esc(doc.client_name)} <span>${esc(doc.honorific)}</span></div>
          <div class="to-intro">${intro}</div>
        </div>
        <div class="quote-doc-meta">
          <div class="meta-row"><span>${noLabel}</span><strong>${esc(no)}</strong></div>
          <div class="meta-row"><span>発行日</span><strong>${doc.issue_date}</strong></div>
          ${issuerHtml}
        </div>
      </div>
      <div class="quote-doc-banner">
        <span class="banner-label">${amountLabel}</span>
        <span class="banner-amount">¥${yen(doc.total)}</span>
      </div>
      ${
        termValue
          ? `<div class="quote-doc-term"><span class="term-label">${termLabel}</span><span class="term-value">${termValue}</span></div>`
          : `<div class="quote-doc-term-spacer"></div>`
      }
      <div class="quote-doc-section">${sectionLabel}</div>
      <table class="quote-doc-table">
        <thead>
          <tr><th class="num">No.</th><th>品名・項目</th><th class="num">数量</th><th>単位</th><th class="num">単価</th><th class="num">金額</th></tr>
        </thead>
        <tbody>${itemsHtml}</tbody>
        <tfoot>${footerHtml}</tfoot>
      </table>
      <div class="quote-doc-grandline">
        <span class="g-label">${amountLabel}</span>
        <span class="g-amount">¥${yen(doc.total)}</span>
      </div>
      ${bankHtml}
      ${notesHtml}
    </div>`;
}

function printQuote(q) {
  $("#print-area").innerHTML = buildDocHtml("quote", q);
  document.body.classList.add("printing");
  window.print();
}

// 印刷終了後は画面を元に戻す
window.addEventListener("afterprint", () => {
  document.body.classList.remove("printing");
  $("#print-area").innerHTML = "";
});

// ---- 請求書 ---------------------------------------------------------------
const INVOICE_STATUS_LABELS = { unpaid: "未入金", paid: "入金済み" };
let SETTINGS = null;

async function loadInvoices() {
  // 取引先マスタ・発行元設定・既定値（発行日＝今日）を用意
  CLIENTS = await api("/api/clients");
  fillInvClientSelect();
  await loadSettings();
  if (!$("#i-issue-date").value) $("#i-issue-date").value = META.today;
  if ($("#inv-item-table tbody").children.length === 0) addInvItemRow();
  recalcInvoice();

  const rows = await api("/api/invoices");
  const tbody = $("#invoice-table tbody");
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const paid = r.status === "paid";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(r.invoice_no)}</td>
      <td>${r.issue_date}</td>
      <td>${esc(r.client_name)} ${esc(r.honorific)}</td>
      <td>${esc(r.subject)}</td>
      <td class="num">${yen(r.total)}</td>
      <td><span class="badge ${paid ? "paid" : "unpaid"}">${INVOICE_STATUS_LABELS[r.status] || ""}</span></td>
      <td class="num">
        <button class="row-btn print">印刷</button>
        <button class="row-btn toggle-pay">${paid ? "未入金に戻す" : "入金済みに"}</button>
        <button class="row-btn edit">編集</button>
        <button class="row-btn del">削除</button>
      </td>`;
    tr.querySelector(".print").addEventListener("click", () => printInvoice(r));
    tr.querySelector(".toggle-pay").addEventListener("click", () => toggleInvoicePaid(r));
    tr.querySelector(".edit").addEventListener("click", () => startEditInvoice(r));
    tr.querySelector(".del").addEventListener("click", () => removeInvoice(r));
    tbody.appendChild(tr);
  });
  $("#invoice-empty").hidden = rows.length > 0;
}

function fillInvClientSelect() {
  $("#i-client").innerHTML =
    '<option value="">（直接入力）</option>' +
    CLIENTS.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
}

// 取引先マスタを選んだら宛名・敬称を流し込む
$("#i-client").addEventListener("change", () => {
  const c = CLIENTS.find((x) => String(x.id) === $("#i-client").value);
  if (c) {
    $("#i-client-name").value = c.name;
    $("#i-honorific").value = c.honorific || "御中";
  }
});

// ---- 発行元設定（振込先） -------------------------------------------------
async function loadSettings() {
  SETTINGS = await api("/api/settings");
  $("#s-business-name").value = SETTINGS.business_name || "";
  $("#s-postal-code").value = SETTINGS.postal_code || "";
  $("#s-address").value = SETTINGS.address || "";
  $("#s-tel").value = SETTINGS.tel || "";
  $("#s-email").value = SETTINGS.email || "";
  $("#s-registration-no").value = SETTINGS.registration_no || "";
  $("#s-bank-info").value = SETTINGS.bank_info || "";
}

$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {
    business_name: $("#s-business-name").value.trim(),
    postal_code: $("#s-postal-code").value.trim(),
    address: $("#s-address").value.trim(),
    tel: $("#s-tel").value.trim(),
    email: $("#s-email").value.trim(),
    registration_no: $("#s-registration-no").value.trim(),
    bank_info: $("#s-bank-info").value.trim(),
  };
  try {
    SETTINGS = await api("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    showMsg("#settings-msg", "設定を保存しました");
  } catch (err) {
    showMsg("#settings-msg", err.message, true);
  }
});

// ---- 明細の行（請求書用） -------------------------------------------------
function addInvItemRow(item) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="ii-name" placeholder="例: Lサイズ画像" /></td>
    <td class="num"><input type="number" class="ii-qty num" min="0" step="1" value="1" /></td>
    <td><input type="text" class="ii-unit" placeholder="点" /></td>
    <td class="num"><input type="number" class="ii-price num" min="0" step="1" value="0" /></td>
    <td class="num ii-amount">0</td>
    <td class="num"><button type="button" class="row-btn del">削除</button></td>`;
  if (item) {
    tr.querySelector(".ii-name").value = item.name || "";
    tr.querySelector(".ii-qty").value = item.quantity ?? 1;
    tr.querySelector(".ii-unit").value = item.unit || "";
    tr.querySelector(".ii-price").value = item.unit_price ?? 0;
  }
  tr.querySelectorAll("input").forEach((inp) =>
    inp.addEventListener("input", recalcInvoice)
  );
  tr.querySelector(".del").addEventListener("click", () => {
    tr.remove();
    if ($("#inv-item-table tbody").children.length === 0) addInvItemRow();
    recalcInvoice();
  });
  $("#inv-item-table tbody").appendChild(tr);
}

$("#i-add-item").addEventListener("click", () => addInvItemRow());
$("#i-tax-mode").addEventListener("change", recalcInvoice);
$("#i-tax-rate").addEventListener("input", recalcInvoice);
// 入金日を入れたら自動で「入金済み」に寄せる（バックエンドの検証と揃える）
$("#i-paid-date").addEventListener("change", () => {
  if ($("#i-paid-date").value) $("#i-status").value = "paid";
});

function collectInvItems() {
  return [...$$("#inv-item-table tbody tr")]
    .map((tr) => ({
      name: tr.querySelector(".ii-name").value.trim(),
      quantity: Number(tr.querySelector(".ii-qty").value || 0),
      unit: tr.querySelector(".ii-unit").value.trim(),
      unit_price: Number(tr.querySelector(".ii-price").value || 0),
    }))
    .filter((it) => it.name !== "");
}

function recalcInvoice() {
  const rows = [...$$("#inv-item-table tbody tr")];
  const lineAmounts = [];
  rows.forEach((tr) => {
    const qty = Number(tr.querySelector(".ii-qty").value || 0);
    const price = Number(tr.querySelector(".ii-price").value || 0);
    const amount = qty * price;
    tr.querySelector(".ii-amount").textContent = yen(amount);
    if (tr.querySelector(".ii-name").value.trim() !== "") lineAmounts.push(amount);
  });
  // 見積と同じ quoteTotals（＝バックエンド compute_totals）を共用する
  const t = quoteTotals(lineAmounts, $("#i-tax-mode").value, Number($("#i-tax-rate").value || 0));
  $("#i-subtotal").textContent = yen(t.subtotal);
  $("#i-tax").textContent = yen(t.tax);
  $("#i-total").textContent = yen(t.total);
}

// ---- 保存・編集・削除 -----------------------------------------------------
function invoiceFormData() {
  return {
    quote_id: $("#invoice-quote-id").value ? Number($("#invoice-quote-id").value) : null,
    client_id: $("#i-client").value ? Number($("#i-client").value) : null,
    client_name: $("#i-client-name").value.trim(),
    honorific: $("#i-honorific").value,
    subject: $("#i-subject").value.trim(),
    issue_date: $("#i-issue-date").value,
    due_date: $("#i-due-date").value || null,
    tax_mode: $("#i-tax-mode").value,
    tax_rate: Number($("#i-tax-rate").value || 0),
    notes: $("#i-notes").value.trim(),
    status: $("#i-status").value,
    paid_date: $("#i-paid-date").value || null,
    items: collectInvItems(),
  };
}

$("#invoice-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("#invoice-edit-id").value;
  const data = invoiceFormData();
  if (data.items.length === 0) {
    showMsg("#invoice-msg", "明細を1行以上入力してください", true);
    return;
  }
  if (!data.client_name || !data.issue_date) return;
  try {
    if (id) {
      await api(`/api/invoices/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#invoice-msg", "更新しました");
    } else {
      const created = await api("/api/invoices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showMsg("#invoice-msg", `保存しました（${created.invoice_no}）`);
    }
    resetInvoiceForm();
    loadInvoices();
  } catch (err) {
    showMsg("#invoice-msg", err.message, true);
  }
});

$("#invoice-cancel-edit").addEventListener("click", resetInvoiceForm);

function resetInvoiceForm() {
  $("#invoice-edit-id").value = "";
  $("#invoice-quote-id").value = "";
  $("#invoice-form").reset();
  $("#i-issue-date").value = META.today;
  $("#i-tax-rate").value = "10";
  $("#i-status").value = "unpaid";
  $("#inv-item-table tbody").innerHTML = "";
  addInvItemRow();
  recalcInvoice();
  $("#invoice-form-title").textContent = "請求書を作成";
  $("#invoice-submit-btn").textContent = "この内容で保存する";
  $("#invoice-cancel-edit").hidden = true;
}

function startEditInvoice(row) {
  $("#invoice-edit-id").value = row.id;
  $("#invoice-quote-id").value = row.quote_id ? String(row.quote_id) : "";
  $("#i-client").value = row.client_id ? String(row.client_id) : "";
  $("#i-client-name").value = row.client_name || "";
  $("#i-honorific").value = row.honorific || "御中";
  $("#i-subject").value = row.subject || "";
  $("#i-issue-date").value = row.issue_date;
  $("#i-due-date").value = row.due_date || "";
  $("#i-tax-mode").value = row.tax_mode || "exclusive";
  $("#i-tax-rate").value = row.tax_rate ?? 10;
  $("#i-status").value = row.status || "unpaid";
  $("#i-paid-date").value = row.paid_date || "";
  $("#i-notes").value = row.notes || "";
  $("#inv-item-table tbody").innerHTML = "";
  (row.items || []).forEach((it) => addInvItemRow(it));
  if ((row.items || []).length === 0) addInvItemRow();
  recalcInvoice();
  $("#invoice-form-title").textContent = `請求書を編集（${row.invoice_no}）`;
  $("#invoice-submit-btn").textContent = "更新する";
  $("#invoice-cancel-edit").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function removeInvoice(row) {
  if (
    !confirm(`この請求書を削除しますか？\n${row.invoice_no} ${row.client_name} ${yen(row.total)}円`)
  )
    return;
  await api(`/api/invoices/${row.id}`, { method: "DELETE" });
  loadInvoices();
}

// 一覧から入金状況を切り替える（PUTで丸ごと送り直す）
async function toggleInvoicePaid(row) {
  const paid = row.status === "paid";
  const data = {
    quote_id: row.quote_id ?? null,
    client_id: row.client_id ?? null,
    client_name: row.client_name,
    honorific: row.honorific,
    subject: row.subject,
    issue_date: row.issue_date,
    due_date: row.due_date || null,
    tax_mode: row.tax_mode,
    tax_rate: row.tax_rate,
    notes: row.notes || "",
    status: paid ? "unpaid" : "paid",
    paid_date: paid ? null : META.today,
    items: (row.items || []).map((it) => ({
      name: it.name,
      quantity: it.quantity,
      unit: it.unit,
      unit_price: it.unit_price,
    })),
  };
  try {
    await api(`/api/invoices/${row.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    loadInvoices();
  } catch (err) {
    showMsg("#invoice-msg", err.message, true);
  }
}

// この宛先を取引先マスタに保存
$("#i-save-client").addEventListener("click", async () => {
  const name = $("#i-client-name").value.trim();
  if (!name) {
    showMsg("#invoice-msg", "宛名を入力してから保存してください", true);
    return;
  }
  try {
    await api("/api/clients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, honorific: $("#i-honorific").value }),
    });
    CLIENTS = await api("/api/clients");
    fillInvClientSelect();
    const saved = CLIENTS.find((c) => c.name === name);
    if (saved) $("#i-client").value = String(saved.id);
    showMsg("#invoice-msg", `「${name}」を取引先に保存しました`);
  } catch (err) {
    showMsg("#invoice-msg", err.message, true);
  }
});

// ---- 見積 → 請求書 への変換 -----------------------------------------------
async function convertQuoteToInvoice(quote) {
  if (
    !confirm(
      `見積「${quote.quote_no}」を請求書に変換します。\n` +
        `内容を引き継いだ請求書を新規作成し、編集画面を開きます。よろしいですか？`
    )
  )
    return;
  try {
    const created = await api(`/api/quotes/${quote.id}/invoice`, { method: "POST" });
    // 請求書タブへ切り替えて、作成された請求書を編集画面に読み込む
    $('.tab[data-tab="invoices"]').click();
    await loadInvoices();
    startEditInvoice(created);
    showMsg("#invoice-msg", `見積 ${quote.quote_no} を請求書 ${created.invoice_no} に変換しました`);
  } catch (err) {
    alert(err.message);
  }
}

// ---- 印刷（ブラウザのPDF保存を使う） --------------------------------------
function printInvoice(inv) {
  $("#print-area").innerHTML = buildDocHtml("invoice", inv);
  document.body.classList.add("printing");
  window.print();
}

// ---- 起動 -----------------------------------------------------------------
init();
