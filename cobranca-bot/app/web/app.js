"use strict";

const PAGE_SIZE = 50;
const CHUNK_ENVIO = 10; // titulos por requisicao no envio em lote

const state = {
  titulos: [],
  selecionados: new Set(),
  busca: "",
  pagina: 1,
  filtroCliente: "",
  filtroAtraso: "",
  visao: "titulos", // titulos | clientes (consolidado)
};

// ---------- Helpers ----------
function fmtMoeda(v) {
  if (v === null || v === undefined) return "-";
  return "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtData(iso) {
  if (!iso) return "-";
  const p = String(iso).split(" ")[0].split("-");
  if (p.length === 3) return `${p[2]}/${p[1]}/${p[0]}`;
  return iso;
}
function fmtDataHora(iso) {
  if (!iso) return "-";
  const partes = String(iso).split(" ");
  const data = fmtData(partes[0]);
  const hora = partes[1] ? " " + partes[1].slice(0, 5) : "";
  return data + hora;
}
function normalizar(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
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

// Confirmacao simples reutilizavel -> retorna Promise<boolean>
function confirmar({ title = "Confirmar", msg = "", extraHtml = "", okLabel = "Confirmar" }) {
  return new Promise((resolve) => {
    const modal = document.getElementById("confirm-modal");
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-msg").textContent = msg;
    document.getElementById("confirm-extra").innerHTML = extraHtml;
    const ok = document.getElementById("confirm-ok");
    const cancel = document.getElementById("confirm-cancel");
    ok.textContent = okLabel;
    modal.hidden = false;

    function cleanup(result) {
      modal.hidden = true;
      ok.removeEventListener("click", onOk);
      cancel.removeEventListener("click", onCancel);
      resolve(result);
    }
    function onOk() { cleanup(true); }
    function onCancel() { cleanup(false); }
    ok.addEventListener("click", onOk);
    cancel.addEventListener("click", onCancel);
  });
}

// ---------- Tabs ----------
function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
      if (tab.dataset.tab === "relatorio") carregarRelatorio();
      if (tab.dataset.tab === "agendamento") { carregarAgendamentos(); carregarRegua(); }
      if (tab.dataset.tab === "pendencias") carregarAbaPendencias();
    });
  });
}

// ---------- Cards / resumo ----------
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
    ${c.titulos_liberados != null ? `
    <div class="line"><span>Liberados p/ cobranca</span><strong>${c.titulos_liberados}</strong></div>
    <div class="line"><span>Bloqueados (ocultos)</span><strong>${c.titulos_bloqueados}</strong></div>` : ""}
  `;
}

function renderStatus(resumo) {
  const box = document.getElementById("status-panel");
  const graph = resumo.graph_configurado;
  const c = resumo.ultima_carga || {};
  box.innerHTML = `
    <div class="line"><span>Microsoft Graph</span><span class="${graph ? "ok" : "bad"}">${graph ? "Configurado" : "Nao configurado"}</span></div>
    <div class="line"><span>Remetente</span><span class="muted">${resumo.graph_sender || "-"}</span></div>
    <div class="line"><span>Coluna Email</span><span class="${c.email_disponivel ? "ok" : "bad"}">${c.email_disponivel ? "Presente" : "Ausente"}</span></div>
    <div class="line"><span>Coluna Link</span><span class="${c.link_disponivel ? "ok" : "bad"}">${c.link_disponivel ? "Presente" : "Ausente"}</span></div>
    <div class="line"><span>Aba INADIMPLENCIA</span><span class="${c.status_disponivel ? "ok" : "bad"}">${c.status_disponivel ? "Lida" : "Ausente"}</span></div>
    ${resumo.geral && resumo.geral.bloqueados != null ? `<div class="line"><span>Bloqueados por status</span><span class="muted">${resumo.geral.bloqueados}</span></div>` : ""}
    <button id="btn-graph-test" class="btn btn-secondary" style="margin-top:10px;width:100%;">Testar conexao Graph</button>
    <div id="graph-test-result" class="muted" style="margin-top:8px;"></div>
  `;
  const btn = document.getElementById("btn-graph-test");
  if (btn) btn.addEventListener("click", testarGraph);
}

async function testarGraph() {
  const out = document.getElementById("graph-test-result");
  out.textContent = "Testando...";
  try {
    const r = await api("/api/graph/test", { method: "POST" });
    out.textContent = r.mensagem;
    out.style.color = r.ok ? "var(--ok)" : "var(--danger)";
  } catch (e) {
    out.textContent = e.message;
    out.style.color = "var(--danger)";
  }
}

function renderPendencias(lista) {
  document.getElementById("pendencias-list").innerHTML = lista.map((p) => `
    <li>
      <div class="pend-head">
        <span class="dot ${p.ativa ? "on" : "off"}"></span>
        <span class="pend-title">${p.titulo}</span>
      </div>
      <div class="pend-desc">${p.descricao}</div>
    </li>
  `).join("");
}

function renderPlanilhaBar(resumo) {
  const bar = document.getElementById("planilha-bar");
  const path = resumo.excel_path;
  if (path) {
    bar.className = "planilha-bar ok";
    bar.innerHTML = `<span class="pb-label">Planilha:</span> <span class="pb-path">${path}</span>`;
  } else {
    bar.className = "planilha-bar empty";
    bar.innerHTML = `Nenhuma planilha selecionada. Clique em <strong>Selecionar planilha</strong> para comecar.`;
  }
}

// ---------- Tabela de cobrancas (filtros + paginacao + visoes) ----------
function _faixaAtrasoOk(dias) {
  const d = dias ?? 0;
  switch (state.filtroAtraso) {
    case "0-15": return d < 15;
    case "15-30": return d >= 15 && d < 30;
    case "30-60": return d >= 30 && d < 60;
    case "60+": return d >= 60;
    default: return true;
  }
}

function titulosFiltrados() {
  let lista = state.titulos;
  if (state.filtroCliente) {
    lista = lista.filter((t) => t.cliente === state.filtroCliente);
  }
  if (state.filtroAtraso) {
    lista = lista.filter((t) => _faixaAtrasoOk(t.dias_atraso));
  }
  if (state.busca) {
    const q = normalizar(state.busca);
    lista = lista.filter((t) =>
      normalizar(t.cliente).includes(q) ||
      normalizar(t.cd_cliente).includes(q) ||
      normalizar(t.titulo).includes(q) ||
      normalizar(t.email).includes(q)
    );
  }
  return lista;
}

function filtrosAtivos() {
  return !!(state.busca || state.filtroCliente || state.filtroAtraso ||
            document.getElementById("filter-status").value);
}

// Barra de consolidacao do conjunto filtrado
function renderResumoFiltro(filtrados) {
  const bar = document.getElementById("resumo-filtro");
  if (!filtrosAtivos() || filtrados.length === 0) {
    bar.hidden = true;
    return;
  }
  const clientes = new Set(filtrados.map((t) => t.cliente)).size;
  const total = filtrados.reduce((s, t) => s + (t.total_atualizado || 0), 0);
  const cobrados = filtrados.filter((t) => t.cobrado).length;
  const maiorAtraso = Math.max(...filtrados.map((t) => t.dias_atraso ?? 0));
  bar.hidden = false;
  bar.innerHTML = `
    <span><strong>${filtrados.length}</strong> titulo(s)</span>
    <span><strong>${clientes}</strong> cliente(s)</span>
    <span>Total: <strong>${fmtMoeda(total)}</strong></span>
    <span>Cobrados: <strong>${cobrados}</strong> &middot; Nao cobrados: <strong>${filtrados.length - cobrados}</strong></span>
    <span>Maior atraso: <strong>${maiorAtraso}d</strong></span>
  `;
}

// Agrupamento por cliente (visao consolidada)
function consolidarPorCliente(filtrados) {
  const mapa = new Map();
  for (const t of filtrados) {
    const chave = t.cliente || "-";
    if (!mapa.has(chave)) {
      mapa.set(chave, {
        cliente: chave, cd_cliente: t.cd_cliente, email: t.email,
        status_cliente: t.status_cliente, titulos: [],
      });
    }
    mapa.get(chave).titulos.push(t);
  }
  const grupos = [...mapa.values()];
  for (const g of grupos) {
    g.qtd = g.titulos.length;
    g.total = g.titulos.reduce((s, t) => s + (t.total_atualizado || 0), 0);
    g.maiorAtraso = Math.max(...g.titulos.map((t) => t.dias_atraso ?? 0));
    g.cobrados = g.titulos.filter((t) => t.cobrado).length;
    g.ids = g.titulos.map((t) => t.id);
  }
  grupos.sort((a, b) => b.maiorAtraso - a.maiorAtraso);
  return grupos;
}

function badgeAtraso(dias) {
  const d = dias ?? 0;
  let cls = "atraso-baixo";
  if (d >= 30) cls = "atraso-alto";
  else if (d >= 15) cls = "atraso-medio";
  return `<span class="badge-atraso ${cls}">${d}d</span>`;
}

function _renderThead() {
  const thead = document.getElementById("thead");
  if (state.visao === "clientes") {
    thead.innerHTML = `
      <tr>
        <th class="col-check"><input type="checkbox" id="check-all" title="Selecionar todos os resultados do filtro"></th>
        <th>Cliente</th>
        <th class="num">Titulos</th>
        <th class="num">Total Atualizado</th>
        <th class="num">Maior Atraso</th>
        <th>Cobranca</th>
        <th class="col-acao">Acao</th>
      </tr>`;
  } else {
    thead.innerHTML = `
      <tr>
        <th class="col-check"><input type="checkbox" id="check-all" title="Selecionar todos os resultados do filtro"></th>
        <th>Cliente</th>
        <th>Titulo</th>
        <th class="num">Total Atualizado</th>
        <th>Vencimento</th>
        <th class="num">Atraso</th>
        <th>Status</th>
        <th class="col-acao">Acao</th>
      </tr>`;
  }
  document.getElementById("check-all").addEventListener("change", (e) => {
    const filtrados = titulosFiltrados();
    if (e.target.checked) filtrados.forEach((t) => state.selecionados.add(t.id));
    else filtrados.forEach((t) => state.selecionados.delete(t.id));
    renderTabela();
  });
}

function renderTabela() {
  _renderThead();
  const tbody = document.getElementById("tbody");
  const filtrados = titulosFiltrados();
  renderResumoFiltro(filtrados);
  document.getElementById("btn-limpar-filtros").hidden = !filtrosAtivos();

  if (state.visao === "clientes") {
    renderTabelaClientes(filtrados);
    return;
  }

  const totalPag = Math.max(1, Math.ceil(filtrados.length / PAGE_SIZE));
  if (state.pagina > totalPag) state.pagina = totalPag;
  const inicio = (state.pagina - 1) * PAGE_SIZE;
  const visiveis = filtrados.slice(inicio, inicio + PAGE_SIZE);

  if (filtrados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty">${filtrosAtivos()
      ? "Nenhum titulo encontrado para os filtros."
      : "Nenhum titulo. Selecione/recarregue a planilha."}</td></tr>`;
    renderPaginacao(0, totalPag);
    updateSelUI(filtrados);
    return;
  }

  tbody.innerHTML = visiveis.map((t) => {
    const checked = state.selecionados.has(t.id) ? "checked" : "";
    const status = t.cobrado
      ? `<span class="badge cobrado">Cobrado ${fmtDataHora(t.ultimo_envio)}</span>`
      : `<span class="badge nao">Nao cobrado</span>`;
    const temEmail = !!t.email;
    const sub = temEmail
      ? `${t.cd_cliente ?? ""} &middot; ${t.email}`
      : `${t.cd_cliente ?? ""} &middot; <span class="no-email">sem e-mail</span>`;
    const stCli = t.status_cliente
      ? ` <span class="badge-st ${t.status_cliente === "NEGATIVADO" ? "st-neg" : "st-cob"}">${t.status_cliente}</span>`
      : "";
    const btnEnviar = temEmail
      ? `<button class="btn btn-mini btn-primary row-send" data-id="${t.id}">Enviar</button>`
      : `<button class="btn btn-mini" disabled title="Sem e-mail">Enviar</button>`;
    return `
      <tr>
        <td class="col-check"><input type="checkbox" class="row-check" data-id="${t.id}" ${checked}></td>
        <td class="cel-cliente">
          <div class="cliente-nome">${t.cliente ?? "-"}${stCli}</div>
          <div class="cliente-sub">${sub}</div>
        </td>
        <td class="cel-titulo">
          <div>${t.titulo ?? "-"}</div>
          <div class="cliente-sub">${t.doc_fiscal ?? ""}</div>
        </td>
        <td class="num valor-destaque">${fmtMoeda(t.total_atualizado)}</td>
        <td>${fmtData(t.vencimento)}</td>
        <td class="num">${badgeAtraso(t.dias_atraso)}</td>
        <td>${status}</td>
        <td class="col-acao">${btnEnviar}</td>
      </tr>`;
  }).join("");

  document.querySelectorAll(".row-check").forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = Number(cb.dataset.id);
      if (cb.checked) state.selecionados.add(id);
      else state.selecionados.delete(id);
      updateSelUI(filtrados);
    });
  });
  document.querySelectorAll(".row-send").forEach((btn) => {
    btn.addEventListener("click", () => enviarIndividual(Number(btn.dataset.id)));
  });

  renderPaginacao(filtrados.length, totalPag);
  updateSelUI(filtrados);
}

// Visao consolidada: uma linha por cliente
function renderTabelaClientes(filtrados) {
  const tbody = document.getElementById("tbody");
  const grupos = consolidarPorCliente(filtrados);
  const totalPag = Math.max(1, Math.ceil(grupos.length / PAGE_SIZE));
  if (state.pagina > totalPag) state.pagina = totalPag;
  const inicio = (state.pagina - 1) * PAGE_SIZE;
  const visiveis = grupos.slice(inicio, inicio + PAGE_SIZE);

  if (grupos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">${filtrosAtivos()
      ? "Nenhum cliente encontrado para os filtros."
      : "Nenhum titulo. Selecione/recarregue a planilha."}</td></tr>`;
    renderPaginacao(0, totalPag);
    updateSelUI(filtrados);
    return;
  }

  tbody.innerHTML = visiveis.map((g) => {
    const todosSel = g.ids.every((id) => state.selecionados.has(id));
    const stCli = g.status_cliente
      ? ` <span class="badge-st ${g.status_cliente === "NEGATIVADO" ? "st-neg" : "st-cob"}">${g.status_cliente}</span>`
      : "";
    const cobranca = g.cobrados === g.qtd
      ? `<span class="badge cobrado">${g.cobrados}/${g.qtd} cobrados</span>`
      : g.cobrados > 0
        ? `<span class="badge nao">${g.cobrados}/${g.qtd} cobrados</span>`
        : `<span class="badge nao">Nao cobrado</span>`;
    const temEmail = !!g.email;
    const btn = temEmail
      ? `<button class="btn btn-mini btn-primary grp-send" data-ids="${g.ids.join(",")}">Enviar ${g.qtd}</button>`
      : `<button class="btn btn-mini" disabled title="Sem e-mail">Enviar</button>`;
    return `
      <tr>
        <td class="col-check"><input type="checkbox" class="grp-check" data-ids="${g.ids.join(",")}" ${todosSel ? "checked" : ""}></td>
        <td class="cel-cliente">
          <div class="cliente-nome">${g.cliente}${stCli}</div>
          <div class="cliente-sub">${g.cd_cliente ?? ""}${temEmail ? " &middot; " + g.email : ' &middot; <span class="no-email">sem e-mail</span>'}</div>
        </td>
        <td class="num">${g.qtd}</td>
        <td class="num valor-destaque">${fmtMoeda(g.total)}</td>
        <td class="num">${badgeAtraso(g.maiorAtraso)}</td>
        <td>${cobranca}</td>
        <td class="col-acao">${btn}</td>
      </tr>`;
  }).join("");

  document.querySelectorAll(".grp-check").forEach((cb) => {
    cb.addEventListener("change", () => {
      const ids = cb.dataset.ids.split(",").map(Number);
      ids.forEach((id) => cb.checked ? state.selecionados.add(id) : state.selecionados.delete(id));
      updateSelUI(titulosFiltrados());
    });
  });
  document.querySelectorAll(".grp-send").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ids = btn.dataset.ids.split(",").map(Number);
      const g = tituloById(ids[0]);
      const ok = await confirmar({
        title: "Enviar cobrancas do cliente",
        msg: `Enviar ${ids.length} cobranca(s) de ${g?.cliente ?? "cliente"}? (um e-mail por titulo)`,
        okLabel: `Enviar ${ids.length}`,
      });
      if (ok) await dispararEnvio(ids);
    });
  });

  renderPaginacao(grupos.length, totalPag);
  updateSelUI(filtrados);
}

function renderPaginacao(total, totalPag) {
  const el = document.getElementById("paginacao");
  const rotulo = state.visao === "clientes" ? "cliente(s)" : "titulo(s)";
  if (total <= PAGE_SIZE) {
    el.innerHTML = total > 0 ? `<span class="pag-info">${total} ${rotulo}</span>` : "";
    return;
  }
  const p = state.pagina;
  el.innerHTML = `
    <span class="pag-info">${total} ${rotulo}</span>
    <div class="pag-controls">
      <button class="btn btn-mini btn-secondary" data-pag="1" ${p === 1 ? "disabled" : ""}>&laquo;</button>
      <button class="btn btn-mini btn-secondary" data-pag="${p - 1}" ${p === 1 ? "disabled" : ""}>&lsaquo;</button>
      <span class="pag-atual">Pagina ${p} de ${totalPag}</span>
      <button class="btn btn-mini btn-secondary" data-pag="${p + 1}" ${p === totalPag ? "disabled" : ""}>&rsaquo;</button>
      <button class="btn btn-mini btn-secondary" data-pag="${totalPag}" ${p === totalPag ? "disabled" : ""}>&raquo;</button>
    </div>
  `;
  el.querySelectorAll("[data-pag]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.pagina = Number(btn.dataset.pag);
      renderTabela();
    });
  });
}

function updateSelUI(filtrados) {
  const n = state.selecionados.size;
  document.getElementById("sel-count").textContent = n;
  document.getElementById("btn-lote").disabled = n === 0;
  document.getElementById("btn-agendar").disabled = n === 0;
  document.getElementById("sel-info").textContent = n > 0 ? `${n} selecionado(s)` : "";
  const all = document.getElementById("check-all");
  const lista = filtrados || titulosFiltrados();
  all.checked = lista.length > 0 && lista.every((t) => state.selecionados.has(t.id));
}

function tituloById(id) {
  return state.titulos.find((t) => t.id === id);
}

// ---------- Envio ----------
async function enviarIndividual(id) {
  const t = tituloById(id);
  const ok = await confirmar({
    title: "Enviar cobranca",
    msg: `Enviar e-mail de cobranca para ${t.cliente} (${t.titulo})?`,
    extraHtml: `<div class="confirm-detail">${t.email} &middot; ${fmtMoeda(t.total_atualizado)}</div>`,
    okLabel: "Enviar agora",
  });
  if (!ok) return;
  await dispararEnvio([id]);
}

async function enviarLote() {
  const ids = [...state.selecionados];
  if (ids.length === 0) return;
  const semEmail = ids.filter((id) => !tituloById(id)?.email).length;
  let extra = "";
  if (semEmail > 0) {
    extra = `<div class="confirm-warn">${semEmail} titulo(s) sem e-mail nao serao enviados.</div>`;
  }
  const ok = await confirmar({
    title: "Enviar lote",
    msg: `Enviar cobranca para ${ids.length} titulo(s) selecionado(s)?`,
    extraHtml: extra,
    okLabel: "Enviar lote",
  });
  if (!ok) return;
  await dispararEnvio(ids);
}

function setProgresso(feitos, total) {
  const pct = total > 0 ? Math.round((feitos / total) * 100) : 0;
  document.getElementById("progress-fill").style.width = pct + "%";
  document.getElementById("progress-label").textContent = `${feitos} de ${total} processado(s) (${pct}%)`;
}

async function dispararEnvio(ids) {
  const total = ids.length;
  const modal = document.getElementById("progress-modal");
  const agregado = { enviados: 0, falhas: 0, pendentes: 0 };

  if (total > CHUNK_ENVIO) {
    modal.hidden = false;
    setProgresso(0, total);
  } else {
    toast("Enviando...");
  }

  try {
    for (let i = 0; i < total; i += CHUNK_ENVIO) {
      const chunk = ids.slice(i, i + CHUNK_ENVIO);
      const res = await api("/api/lote/enviar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ titulo_ids: chunk }),
      });
      agregado.enviados += res.total_enviados;
      agregado.falhas += res.total_falhas;
      agregado.pendentes += res.total_pendentes;
      setProgresso(Math.min(i + CHUNK_ENVIO, total), total);
    }
    state.selecionados.clear();
    const kind = agregado.falhas > 0 ? "bad" : "ok";
    toast(`Enviados: ${agregado.enviados} | Falhas: ${agregado.falhas} | Pendentes: ${agregado.pendentes}`, kind);
    await recarregarTudo();
  } catch (e) {
    toast("Erro no envio: " + e.message, "bad");
  } finally {
    modal.hidden = true;
  }
}

// ---------- Agendamento manual (a partir da selecao) ----------
async function agendarSelecionados() {
  const ids = [...state.selecionados];
  if (ids.length === 0) return;
  // default: agora + 1h; min: agora (nao permitir agendar no passado)
  const pad = (n) => String(n).padStart(2, "0");
  const fmtLocal = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const def = fmtLocal(new Date(Date.now() + 3600 * 1000));
  const min = fmtLocal(new Date());
  const ok = await confirmar({
    title: "Agendar envio",
    msg: `Agendar ${ids.length} titulo(s) para envio automatico em:`,
    extraHtml: `<input type="datetime-local" id="agendar-dt" value="${def}" min="${min}" class="dt-input">`,
    okLabel: "Agendar",
  });
  if (!ok) return;
  const dt = document.getElementById("agendar-dt")?.value;
  if (!dt) { toast("Data/hora invalida", "bad"); return; }
  try {
    const r = await api("/api/agendamentos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo_ids: ids, data_agendada: dt }),
    });
    state.selecionados.clear();
    toast(`${r.criados} agendamento(s) criado(s) para ${fmtDataHora(r.data_agendada)}.`, "ok");
    await carregarTitulos();
  } catch (e) {
    toast("Erro ao agendar: " + e.message, "bad");
  }
}

// ---------- Relatorio ----------
async function carregarRelatorio() {
  const status = document.getElementById("rel-filter-status").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const data = await api(`/api/relatorio?${params.toString()}`);
  const r = data.resumo || {};
  document.getElementById("rel-cards").innerHTML = `
    <div class="card"><div class="label">Total de envios</div><div class="value">${r.total ?? 0}</div></div>
    <div class="card ok"><div class="label">Enviados</div><div class="value">${r.enviados ?? 0}</div></div>
    <div class="card warn"><div class="label">Erros</div><div class="value">${r.erros ?? 0}</div></div>
  `;
  const tbody = document.getElementById("rel-tbody");
  if (!data.envios.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty">Sem envios registrados.</td></tr>`;
    return;
  }
  tbody.innerHTML = data.envios.map((e) => {
    const st = e.status_envio === "enviado"
      ? `<span class="badge cobrado">Enviado</span>`
      : `<span class="badge erro">Erro</span>`;
    return `
      <tr>
        <td>${fmtDataHora(e.data_envio)}</td>
        <td>${st}</td>
        <td>${e.origem_label}${e.regra_dias != null ? " (" + e.regra_dias + "d)" : ""}</td>
        <td>${e.cliente ?? "-"}</td>
        <td>${e.titulo ?? "-"}</td>
        <td class="num">${fmtMoeda(e.total_atualizado)}</td>
        <td>${e.email ?? "-"}</td>
        <td class="erro-cell">${e.erro ?? ""}</td>
      </tr>`;
  }).join("");
}

function exportarRelatorio() {
  const status = document.getElementById("rel-filter-status").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  window.location.href = `/api/relatorio/export?${params.toString()}`;
}

// ---------- Agendamentos (lista + regua) ----------
async function carregarAgendamentos() {
  const lista = await api("/api/agendamentos");
  const tbody = document.getElementById("agend-tbody");
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">Nenhum agendamento.</td></tr>`;
    return;
  }
  const stBadge = (s) => {
    const map = { pendente: "nao", executado: "cobrado", cancelado: "muted-badge", erro: "erro" };
    return `<span class="badge ${map[s] || "nao"}">${s}</span>`;
  };
  tbody.innerHTML = lista.map((a) => `
    <tr>
      <td>${fmtDataHora(a.data_agendada)}</td>
      <td>${a.cliente ?? "-"}</td>
      <td>${a.titulo ?? "-"}</td>
      <td class="num">${fmtMoeda(a.total_atualizado)}</td>
      <td>${stBadge(a.status)}${a.erro ? ' <span class="erro-cell">' + a.erro + "</span>" : ""}</td>
      <td class="col-acao">${a.status === "pendente"
        ? `<button class="btn btn-mini btn-secondary agend-cancel" data-id="${a.id}">Cancelar</button>`
        : "-"}</td>
    </tr>
  `).join("");
  document.querySelectorAll(".agend-cancel").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/agendamentos/${btn.dataset.id}/cancelar`, { method: "POST" });
      toast("Agendamento cancelado.", "ok");
      carregarAgendamentos();
    });
  });
}

async function carregarRegua() {
  const cfg = await api("/api/regua");
  document.getElementById("regua-ativa").checked = cfg.ativa;
  document.getElementById("regua-dias-input").value = (cfg.dias || []).join(", ");
}

async function salvarRegua() {
  const ativa = document.getElementById("regua-ativa").checked;
  const raw = document.getElementById("regua-dias-input").value;
  const dias = raw.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n) && n > 0);
  try {
    const cfg = await api("/api/regua", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ativa, dias }),
    });
    document.getElementById("regua-dias-input").value = (cfg.dias || []).join(", ");
    const st = document.getElementById("regua-status");
    st.textContent = cfg.ativa ? "Regua ativa." : "Regua desativada.";
    st.style.color = cfg.ativa ? "var(--ok)" : "var(--muted)";
    toast("Regua salva.", "ok");
  } catch (e) {
    toast("Erro ao salvar regua: " + e.message, "bad");
  }
}

// ---------- Aba Pendencias ----------
async function carregarAbaPendencias() {
  const [titulosAll, resumo, tecnicas] = await Promise.all([
    api("/api/titulos"),
    api("/api/resumo"),
    api("/api/pendencias"),
  ]);

  const semEmail = titulosAll.filter((t) => !t.email);
  const bloqueados = resumo.geral?.bloqueados ?? 0;
  const abaStatus = resumo.ultima_carga?.status_disponivel;

  document.getElementById("pend-cards").innerHTML = `
    <div class="card warn"><div class="label">Liberados sem e-mail</div><div class="value">${semEmail.length}</div></div>
    <div class="card"><div class="label">Bloqueados por status (ocultos)</div><div class="value">${bloqueados}</div></div>
    <div class="card ${abaStatus ? "ok" : "warn"}"><div class="label">Aba INADIMPLENCIA</div><div class="value" style="font-size:18px;">${abaStatus == null ? "-" : abaStatus ? "Lida" : "Ausente"}</div></div>
  `;

  const tbody = document.getElementById("pend-tbody");
  if (semEmail.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Nenhuma pendencia de e-mail — todos os titulos liberados tem destinatario.</td></tr>`;
  } else {
    tbody.innerHTML = semEmail.map((t) => `
      <tr>
        <td class="cel-cliente">
          <div class="cliente-nome">${t.cliente ?? "-"}</div>
          <div class="cliente-sub">${t.cd_cliente ?? ""}</div>
        </td>
        <td>${t.titulo ?? "-"}</td>
        <td class="num valor-destaque">${fmtMoeda(t.total_atualizado)}</td>
        <td>${fmtData(t.vencimento)}</td>
        <td class="num">${badgeAtraso(t.dias_atraso)}</td>
      </tr>`).join("");
  }

  renderPendencias(tecnicas);
}

// ---------- Data loading ----------
async function carregarTitulos() {
  const status = document.getElementById("filter-status").value;
  const ordenar = document.getElementById("filter-ordenar").checked;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("ordenar_atraso", ordenar);
  state.titulos = await api(`/api/titulos?${params.toString()}`);
  const visiveis = new Set(state.titulos.map((t) => t.id));
  state.selecionados.forEach((id) => { if (!visiveis.has(id)) state.selecionados.delete(id); });
  popularFiltroClientes();
  renderTabela();
}

function popularFiltroClientes() {
  const sel = document.getElementById("filter-cliente");
  const atual = state.filtroCliente;
  const nomes = [...new Set(state.titulos.map((t) => t.cliente).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "pt-BR"));
  sel.innerHTML = `<option value="">Todos</option>` +
    nomes.map((n) => `<option value="${n.replace(/"/g, "&quot;")}"${n === atual ? " selected" : ""}>${n}</option>`).join("");
  if (atual && !nomes.includes(atual)) {
    state.filtroCliente = "";
  }
}

async function carregarResumo() {
  const resumo = await api("/api/resumo");
  renderCards(resumo);
  renderCarga(resumo);
  renderStatus(resumo);
  renderPlanilhaBar(resumo);
}

async function carregarPendencias() {
  const p = await api("/api/pendencias");
  renderPendencias(p);
}

async function recarregarTudo() {
  await Promise.all([carregarTitulos(), carregarResumo(), carregarPendencias()]);
}

// ---------- Acoes da planilha ----------
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

async function selecionarPlanilha() {
  if (!(window.pywebview && window.pywebview.api && window.pywebview.api.escolher_planilha)) {
    toast("Selecao de arquivo disponivel apenas no aplicativo (.exe).", "bad");
    return;
  }
  try {
    const r = await window.pywebview.api.escolher_planilha();
    if (!r.selecionado) return;
    toast("Planilha selecionada. Sincronizando...", "ok");
    await recarregarPlanilha();
  } catch (e) {
    toast("Erro ao selecionar planilha: " + e.message, "bad");
  }
}

function setVisao(v) {
  state.visao = v;
  state.pagina = 1;
  document.getElementById("visao-titulos").classList.toggle("active", v === "titulos");
  document.getElementById("visao-clientes").classList.toggle("active", v === "clientes");
  renderTabela();
}

// ---------- Eventos ----------
function initEvents() {
  document.getElementById("btn-select").addEventListener("click", selecionarPlanilha);
  document.getElementById("btn-reload").addEventListener("click", recarregarPlanilha);
  document.getElementById("btn-lote").addEventListener("click", enviarLote);
  document.getElementById("btn-agendar").addEventListener("click", agendarSelecionados);
  document.getElementById("filter-status").addEventListener("change", () => { state.pagina = 1; carregarTitulos(); });
  document.getElementById("filter-ordenar").addEventListener("change", () => { state.pagina = 1; carregarTitulos(); });
  document.getElementById("busca").addEventListener("input", (e) => {
    state.busca = e.target.value;
    state.pagina = 1;
    renderTabela();
  });
  document.getElementById("filter-cliente").addEventListener("change", (e) => {
    state.filtroCliente = e.target.value;
    state.pagina = 1;
    renderTabela();
  });
  document.getElementById("filter-atraso").addEventListener("change", (e) => {
    state.filtroAtraso = e.target.value;
    state.pagina = 1;
    renderTabela();
  });
  document.getElementById("btn-limpar-filtros").addEventListener("click", () => {
    state.busca = ""; state.filtroCliente = ""; state.filtroAtraso = ""; state.pagina = 1;
    document.getElementById("busca").value = "";
    document.getElementById("filter-cliente").value = "";
    document.getElementById("filter-atraso").value = "";
    const st = document.getElementById("filter-status");
    if (st.value) { st.value = ""; carregarTitulos(); } else { renderTabela(); }
  });
  document.getElementById("visao-titulos").addEventListener("click", () => setVisao("titulos"));
  document.getElementById("visao-clientes").addEventListener("click", () => setVisao("clientes"));
  document.getElementById("rel-filter-status").addEventListener("change", carregarRelatorio);
  document.getElementById("btn-export").addEventListener("click", exportarRelatorio);
  document.getElementById("btn-salvar-regua").addEventListener("click", salvarRegua);
}

initTabs();
initEvents();
recarregarTudo().catch((e) => toast("Erro ao carregar: " + e.message, "bad"));
