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
    if (btn.dataset.tab === "summary") loadSummary();
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

  // 日付の初期値＝今日
  $("#f-date").value = META.today;

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
  $("#export-btn").href = "/api/export.csv?year=" + year;

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

// ---- 起動 -----------------------------------------------------------------
init();
