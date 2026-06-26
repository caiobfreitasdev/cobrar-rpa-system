"use strict";

const state = {
  titulos: [],
  selecionados: new Set(),
};

// ---------- Helpers ----------
function fmtMoeda(v) {
  if (v === null || v === undefined) return "-";
  return "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtData(iso) {
  if (!iso) return "-";
  const p = String(iso).split("-");
  if (p.length === 3) return `${p[2]}/${p[1]}/${p[0]}`;
  return iso;
}
function fmtDataHora(iso) {
  if (!iso) return "-";
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d)) return fmtData(iso);
  return d.toLocaleDateString("pt-BR");
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

function toast(msg, kind) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast" + (kind ? " " + kind : "");
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 4500);
}

// ---------- Render ----------
function renderCards(resumo) {
  const g = resumo.geral || {};
  document.getElementById("cards").innerHTML = `
    <div class="card"><div class="label">Titulos abertos</div><div class="value">${g.total_ativos ?? 0}</div></div>
    <div class="card warn"><div class="label">Nao cobrados</div><div class="value">${g.nao_cobrados ?? 0}</div></div>
    <div class="card ok"><div class="label">Cobrados</div><div class="value">${g.cobrados ?? 0}</div></div>
  `;
}

function renderCarga(resumo) {
  const c = resumo.ultima_carga || {};
  const box = document.getElementById("carga-resumo");
  if (!c || Object.keys(c).length === 0) {
    box.innerHTML = `<p class="muted">Recarregue a planilha para sincronizar.</p>`;
    return;
  }
  box.innerHTML = `
    <div class="line"><span>Novos</span><strong>${c.novos ?? 0}</strong></div>
    <div class="line"><span>Alterados</span><strong>${c.alterados ?? 0}</strong></div>
    <div class="line"><span>Baixados (provavel pgto)</span><strong>${c.baixados ?? 0}</strong></div>
    <div class="line"><span>Total na carga</span><strong>${c.total_carga ?? 0}</strong></div>
  `;
}

function renderStatus(resumo) {
  const box = document.getElementById("status-panel");
  const smtp = resumo.smtp_configurado;
  const c = resumo.ultima_carga || {};
  box.innerHTML = `
    <div class="line"><span>SMTP</span><span class="${smtp ? "ok" : "bad"}">${smtp ? "Configurado" : "Nao configurado"}</span></div>
    <div class="line"><span>Coluna Email</span><span class="${c.email_disponivel ? "ok" : "bad"}">${c.email_disponivel ? "Presente" : "Ausente"}</span></div>
    <div class="line"><span>Coluna Link</span><span class="${c.link_disponivel ? "ok" : "bad"}">${c.link_disponivel ? "Presente" : "Ausente"}</span></div>
  `;
}

function renderPendencias(lista) {
  document.getElementById("pendencias-list").innerHTML = lista.map(p => `
    <li>
      <div class="pend-head">
        <span class="dot ${p.ativa ? "on" : "off"}"></span>
        <span class="pend-title">${p.titulo}</span>
      </div>
      <div class="pend-desc">${p.descricao}</div>
    </li>
  `).join("");
}

function renderTabela() {
  const tbody = document.getElementById("tbody");
  if (state.titulos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty">Nenhum titulo encontrado.</td></tr>`;
    updateSelUI();
    return;
  }
  tbody.innerHTML = state.titulos.map(t => {
    const checked = state.selecionados.has(t.id) ? "checked" : "";
    const status = t.cobrado
      ? `<span class="badge cobrado">Cobrado em ${fmtDataHora(t.ultimo_envio)}</span>`
      : `<span class="badge nao">Nao cobrado</span>`;
    const email = t.email
      ? t.email
      : `<span class="no-email">sem e-mail</span>`;
    const atrasoCls = (t.dias_atraso ?? 0) >= 30 ? "atraso-alto" : "";
    return `
      <tr>
        <td class="col-check"><input type="checkbox" class="row-check" data-id="${t.id}" ${checked}></td>
        <td>${t.cliente ?? "-"}</td>
        <td>${t.titulo ?? "-"}</td>
        <td class="num">${fmtMoeda(t.total_atualizado)}</td>
        <td>${fmtData(t.vencimento)}</td>
        <td class="num ${atrasoCls}">${t.dias_atraso ?? "-"}</td>
        <td>${email}</td>
        <td>${status}</td>
      </tr>`;
  }).join("");

  document.querySelectorAll(".row-check").forEach(cb => {
    cb.addEventListener("change", () => {
      const id = Number(cb.dataset.id);
      if (cb.checked) state.selecionados.add(id);
      else state.selecionados.delete(id);
      updateSelUI();
    });
  });
  updateSelUI();
}

function updateSelUI() {
  const n = state.selecionados.size;
  document.getElementById("sel-count").textContent = n;
  document.getElementById("btn-lote").disabled = n === 0;
  document.getElementById("sel-info").textContent = n > 0 ? `${n} selecionado(s)` : "";
  const all = document.getElementById("check-all");
  all.checked = n > 0 && n === state.titulos.length;
}

// ---------- Data loading ----------
async function carregarTitulos() {
  const status = document.getElementById("filter-status").value;
  const ordenar = document.getElementById("filter-ordenar").checked;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("ordenar_atraso", ordenar);
  state.titulos = await api(`/api/titulos?${params.toString()}`);
  // Limpa selecionados que sumiram do filtro
  const visiveis = new Set(state.titulos.map(t => t.id));
  state.selecionados.forEach(id => { if (!visiveis.has(id)) state.selecionados.delete(id); });
  renderTabela();
}

async function carregarResumo() {
  const resumo = await api("/api/resumo");
  renderCards(resumo);
  renderCarga(resumo);
  renderStatus(resumo);
}

async function carregarPendencias() {
  const p = await api("/api/pendencias");
  renderPendencias(p);
}

async function recarregarTudo() {
  await Promise.all([carregarTitulos(), carregarResumo(), carregarPendencias()]);
}

// ---------- Modal de lote ----------
async function abrirModalLote() {
  const ids = [...state.selecionados];
  if (ids.length === 0) return;
  let preview;
  try {
    preview = await api("/api/lote/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo_ids: ids }),
    });
  } catch (e) {
    toast("Erro ao gerar preview: " + e.message, "bad");
    return;
  }

  document.getElementById("modal-summary").innerHTML = `
    <div class="pill"><div class="n">${preview.total}</div><div class="l">Selecionados</div></div>
    <div class="pill"><div class="n">${preview.com_email}</div><div class="l">Com e-mail</div></div>
    <div class="pill"><div class="n">${preview.sem_email}</div><div class="l">Sem e-mail</div></div>
  `;
  document.getElementById("modal-tbody").innerHTML = preview.itens.map(i => `
    <tr>
      <td>${i.cliente ?? "-"}</td>
      <td>${i.titulo ?? "-"}</td>
      <td>${i.email ? i.email : '<span class="no-email">sem e-mail</span>'}</td>
    </tr>
  `).join("");
  document.getElementById("modal-warn").textContent = preview.sem_email > 0
    ? `${preview.sem_email} titulo(s) sem e-mail nao serao enviados (ficam pendentes).`
    : "";
  document.getElementById("modal").hidden = false;
}

function fecharModal() {
  document.getElementById("modal").hidden = true;
}

async function confirmarEnvio() {
  const ids = [...state.selecionados];
  const btn = document.getElementById("modal-confirm");
  btn.disabled = true;
  btn.textContent = "Enviando...";
  try {
    const res = await api("/api/lote/enviar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo_ids: ids }),
    });
    fecharModal();
    state.selecionados.clear();
    const kind = res.total_falhas > 0 ? "bad" : "ok";
    toast(`Enviados: ${res.total_enviados} | Falhas: ${res.total_falhas} | Pendentes: ${res.total_pendentes}`, kind);
    await recarregarTudo();
  } catch (e) {
    toast("Erro no envio: " + e.message, "bad");
  } finally {
    btn.disabled = false;
    btn.textContent = "Confirmar e enviar";
  }
}

// ---------- Sync planilha ----------
async function recarregarPlanilha() {
  const btn = document.getElementById("btn-reload");
  btn.disabled = true;
  btn.textContent = "Sincronizando...";
  try {
    const r = await api("/api/sync", { method: "POST" });
    toast(`Carga: ${r.novos} novos, ${r.alterados} alterados, ${r.baixados} baixados.`, "ok");
    await recarregarTudo();
  } catch (e) {
    toast("Erro ao sincronizar: " + e.message, "bad");
  } finally {
    btn.disabled = false;
    btn.textContent = "Recarregar planilha";
  }
}

// ---------- Eventos ----------
function initEvents() {
  document.getElementById("btn-reload").addEventListener("click", recarregarPlanilha);
  document.getElementById("btn-lote").addEventListener("click", abrirModalLote);
  document.getElementById("modal-cancel").addEventListener("click", fecharModal);
  document.getElementById("modal-confirm").addEventListener("click", confirmarEnvio);
  document.getElementById("filter-status").addEventListener("change", carregarTitulos);
  document.getElementById("filter-ordenar").addEventListener("change", carregarTitulos);
  document.getElementById("check-all").addEventListener("change", (e) => {
    if (e.target.checked) state.titulos.forEach(t => state.selecionados.add(t.id));
    else state.selecionados.clear();
    renderTabela();
  });
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") fecharModal();
  });
}

initEvents();
recarregarTudo().catch(e => toast("Erro ao carregar: " + e.message, "bad"));
