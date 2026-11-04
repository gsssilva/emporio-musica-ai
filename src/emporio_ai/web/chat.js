/* Local conversation client. DOM rendering never interprets model/source HTML. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const KEY = 'emporio_chat_v1';
  const greeting = 'Olá! Sou o assistente da Empório da Música. Posso ajudar com instrumentos, preços e políticas da loja. Como posso ajudar?';
  let state = {token: null, items: []};
  let busy = false, healthy = false, storageAvailable = true, retryMessage = '';
  let noticeAction = null;
  const chips = [...document.querySelectorAll('.chips button')];
  class ApiError extends Error {
    constructor(status, detail) { super(detail || 'Falha na solicitação.'); this.status = status; }
  }
  async function request(path, {method = 'GET', body, token, timeout = 12000} = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const headers = {};
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      if (token) headers.Authorization = `Bearer ${token}`;
      const r = await fetch(path, {method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal, cache: 'no-store', credentials: 'same-origin'});
      const data = r.status === 204 ? null : await r.json().catch(() => null);
      if (!r.ok) throw new ApiError(r.status, typeof data?.detail === 'string' ? data.detail : 'Solicitação não concluída.');
      return data;
    } finally { clearTimeout(timer); }
  }
  function element(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function save() {
    try { sessionStorage.setItem(KEY, JSON.stringify(state)); }
    catch (_) { storageAvailable = false; }
  }
  function restore() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(KEY));
      if (saved && typeof saved.token === 'string' && /^[A-Za-z0-9_-]{43}$/.test(saved.token) && Array.isArray(saved.items)) {
        state.token = saved.token;
        state.items = saved.items.slice(-40).filter(item => ['me', 'bot'].includes(item?.role) && typeof item.text === 'string' && item.text.length <= 6000);
      }
    } catch (_) { storageAvailable = false; }
  }
  function controls() {
    const disabled = busy || !healthy || !state.token;
    $('t').disabled = disabled;
    $('s').disabled = disabled;
    chips.forEach(b => b.disabled = disabled);
    $('rb').disabled = busy || !state.token;
    $('cy').disabled = busy;
    $('cn').disabled = busy;
    $('notice-action').disabled = busy;
    $('msgs').setAttribute('aria-busy', String(busy));
  }
  function notice(text, label, action) {
    $('notice-text').textContent = text;
    $('notice').hidden = !text;
    $('notice-action').hidden = !label;
    $('notice-action').textContent = label || '';
    noticeAction = action || null;
  }
  $('notice-action').addEventListener('click', () => { if (!busy && noticeAction) noticeAction(); });
  function scrollBottom() { $('msgs').scrollTop = $('msgs').scrollHeight; }
  function formatted(parent, text) {
    // Only bold markers and BRL amounts are recognized; all other input is literal text.
    const chunks = text.split(/(\*\*[^*]+\*\*|R\$\s*\d[\d.]*(?:,\d{2})?)/g);
    chunks.forEach(chunk => {
      if (chunk.startsWith('**') && chunk.endsWith('**')) parent.append(element('strong', '', chunk.slice(2, -2)));
      else if (/^R\$/.test(chunk)) parent.append(element('strong', '', chunk));
      else parent.append(document.createTextNode(chunk));
    });
  }
  function sourceLabel(s) {
    if (s.kind === 'policy') return `Política ${s.section || s.id?.replace('policy:', '') || ''}`;
    if (s.kind === 'catalog') return 'Catálogo';
    if (s.kind === 'order') return 'Pedido';
    if (s.kind === 'catalog_lookup') return 'Consulta ao catálogo';
    return String(s.kind || 'Fonte');
  }
  function sourcesView(bubble, sources) {
    if (!Array.isArray(sources) || !sources.length) return;
    const details = element('details', 'sources');
    details.append(element('summary', '', `Fontes consultadas (${sources.length})`));
    for (const s of sources) {
      const entry = element('div', 'source');
      entry.append(element('b', '', sourceLabel(s)), element('span', '', String(s.title || s.id || '')));
      if (Array.isArray(s.pages)) entry.append(element('div', '', `Páginas: ${s.pages.join(', ')}`));
      if (typeof s.text === 'string') entry.append(element('p', '', s.text));
      if (s.imported_at) entry.append(element('div', '', `Snapshot importado: ${s.imported_at}`));
      if (s.id) entry.append(element('div', '', `ID: ${s.id}`));
      details.append(entry);
    }
    bubble.append(details);
  }
  function productView(bubble, products) {
    if (!Array.isArray(products) || !products.length) return;
    for (const p of products) {
      const card = element('div', 'prod');
      const label = element('span');
      const money = cents => (cents / 100).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
      const price = p.promotion_bps > 0 && Number.isSafeInteger(p.table_price_cents)
        ? `De ${money(p.table_price_cents)} por ${money(p.current_price_cents)} (${(p.promotion_bps / 100).toLocaleString('pt-BR')}% de desconto)`
        : money(p.current_price_cents);
      label.append(element('span', 'product-name', p.name), element('small', '', price));
      const status = p.available ? `${p.stock_quantity} em estoque` : p.status === 'discontinued' ? 'Descontinuado' : p.status === 'coming_soon' ? 'Em lançamento' : 'Sem estoque';
      card.append(label, element('span', p.available ? 'ok' : 'ok unavailable', status));
      bubble.append(card);
    }
    bubble.append(element('div', 'product-caption', 'Consulta auxiliar ao catálogo local · preço antes das condições de pagamento.'));
  }
  function renderItem(item) {
    const bubble = element('div', `m ${item.role}`);
    const text = element('div', 'message-text');
    formatted(text, item.text); bubble.append(text);
    if (item.role === 'bot' && item.result) {
      productView(bubble, item.result.products);
      sourcesView(bubble, item.result.sources);
      const copy = element('button', 'copy', 'Copiar resposta'); copy.type = 'button';
      copy.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(item.text); copy.textContent = 'Resposta copiada'; }
        catch (_) { copy.textContent = 'Selecione o texto para copiar'; }
      });
      bubble.append(copy);
    }
    $('msgs').append(bubble); scrollBottom(); return bubble;
  }
  function add(item) { state.items.push(item); renderItem(item); save(); }
  function trace(result) {
    $('tl').replaceChildren();
    const tools = Array.isArray(result?.tool_trace) ? result.tool_trace : [];
    if (!result) $('tl').append(element('div', '', 'Nenhuma resposta recebida nesta conversa.'));
    else if (!tools.length) $('tl').append(element('div', '', 'Nenhuma ferramenta registrada nesta resposta.'));
    tools.forEach(tool => $('tl').append(element('div', '', `${tool.tool} · ${tool.ok ? 'concluído' : 'não concluído'}${tool.trigger ? ` · origem: ${tool.trigger}` : ''}`)));
    $('technical').hidden = !result;
    if (result) {
      const metadata = {};
      for (const key of ['request_id', 'model', 'provider', 'prompt_version', 'generation_mode', 'kind', 'usage', 'status']) if (result[key] !== undefined) metadata[key] = result[key];
      $('metadata').textContent = JSON.stringify(metadata, null, 2);
    } else $('metadata').textContent = '';
  }
  function renderConversation() {
    $('msgs').replaceChildren(element('div', 'day', 'Hoje'));
    renderItem({role: 'bot', text: greeting});
    state.items.forEach(renderItem);
    trace([...state.items].reverse().find(i => i.role === 'bot' && i.result)?.result);
  }
  async function health() {
    try {
      const data = await request('/chat/health');
      healthy = data?.status === 'ready';
    } catch (_) { healthy = false; }
    $('health').textContent = healthy ? 'Serviço local disponível' : 'Serviço local indisponível';
    $('dot').classList.toggle('off', !healthy); controls();
    return healthy;
  }
  async function createSession() {
    const session = await request('/sessions', {method: 'POST', body: {}});
    if (typeof session?.session_id !== 'string') throw new Error('Sessão inválida.');
    state.token = session.session_id; save();
  }
  async function reconnect() {
    busy = true; controls();
    try {
      const ready = await health();
      if (!state.token) await createSession();
      if (!ready) throw new Error('Serviço local indisponível.');
      notice(storageAvailable ? '' : 'O armazenamento desta aba está indisponível. A conversa funciona enquanto a página permanecer aberta.');
    } catch (_) { notice('Serviço local indisponível. Verifique se a API e o Ollama estão em execução.', 'Verificar novamente', reconnect); }
    finally { busy = false; controls(); }
  }
  async function enrichProducts(result) {
    const tools = result.tool_trace || [];
    if (result.status !== 'completed' || tools.some(t => t.tool === 'quote_payment') || !tools.some(t => ['search_products', 'get_product'].includes(t.tool) && t.ok)) return [];
    const ids = [...new Set((result.sources || []).filter(s => s.kind === 'catalog' && Number.isSafeInteger(s.product_id) && s.product_id > 0).map(s => s.product_id))].slice(0, 5);
    const settled = await Promise.allSettled(ids.map(id => request(`/api/products/${id}`)));
    return settled.flatMap(r => {
      const p = r.status === 'fulfilled' && r.value?.product;
      return p && Number.isSafeInteger(p.current_price_cents) && Number.isSafeInteger(p.stock_quantity) ? [p] : [];
    });
  }
  async function send(message = $('t').value, retry = false) {
    const text = String(message).trim();
    if (busy || !text || text.length > 2000) return;
    if (!state.token || !healthy) { await reconnect(); if (!state.token || !healthy) return; }
    busy = true; retryMessage = text; controls(); notice(''); $('cf').hidden = true;
    if (!retry) add({role: 'me', text});
    $('t').value = ''; $('t').style.height = '44px'; $('t').style.overflowY = 'hidden';
    const waiting = element('div', 'm bot waiting'); waiting.setAttribute('role', 'status'); waiting.setAttribute('aria-live', 'polite');
    waiting.append(element('span', 'dots', '•••'), element('span', '', 'Aguardando o modelo local. A primeira resposta pode levar um pouco mais enquanto o modelo é carregado.'));
    $('msgs').append(waiting); scrollBottom();
    try {
      const result = await request('/chat', {method: 'POST', token: state.token, body: {message: text}, timeout: 250000});
      if (typeof result?.answer !== 'string') throw new Error('Resposta inválida.');
      waiting.remove();
      result.products = await enrichProducts(result);
      add({role: 'bot', text: result.answer, result}); trace(result);
      if (result.status !== 'completed') notice('O agente não concluiu a consulta. Veja a orientação na resposta e tente reformular a pergunta.');
    } catch (error) {
      waiting.remove();
      if (error.status === 401 || error.status === 403) {
        // Never replay a message automatically after changing server-side history.
        state = {token: null, items: []}; save(); renderConversation(); $('rn').textContent = 'Conversa atual';
        try {
          await createSession();
          notice('A sessão expirou ou não é mais válida. Criei uma nova conversa; o histórico anterior não está disponível nesta sessão.', 'Reenviar última mensagem', () => send(retryMessage));
        } catch (_) { notice('A sessão expirou e não foi possível criar outra. Verifique o serviço local.', 'Verificar novamente', reconnect); }
      } else if (error.status === 409 || error.status === 429) {
        if (error.status === 429 && /limite/i.test(error.message)) notice('O limite desta sessão foi atingido. Use Nova conversa para continuar.', 'Nova conversa', () => $('rb').click());
        else notice('O atendimento está ocupado. Aguarde alguns instantes antes de tentar novamente.', 'Reenviar última mensagem', () => send(retryMessage, true));
      } else {
        if (!error.status) { healthy = false; $('health').textContent = 'Conexão interrompida'; $('dot').classList.add('off'); }
        notice('Não foi possível concluir a resposta. Verifique o serviço local antes de reenviar; não foi feita repetição automática.', 'Verificar e reenviar', async () => { await reconnect(); if (healthy && state.token) await send(retryMessage, true); });
      }
    } finally { waiting.remove(); busy = false; controls(); if (!$('t').disabled) $('t').focus(); }
  }
  async function resetConversation() {
    if (busy) return;
    busy = true; controls(); notice('');
    try {
      if (state.token) {
        try { await request('/sessions/current', {method: 'DELETE', token: state.token}); }
        catch (error) { if (![401, 403].includes(error.status)) throw error; }
      }
      state = {token: null, items: []}; retryMessage = '';
      try { sessionStorage.removeItem(KEY); } catch (_) { storageAvailable = false; }
      renderConversation(); $('cf').hidden = true; $('rn').textContent = 'Conversa atual';
      await createSession(); await health();
      notice(healthy ? 'Nova conversa iniciada.' : 'Histórico excluído. Inicie o modelo local para conversar.', healthy ? null : 'Verificar novamente', healthy ? null : reconnect);
    } catch (_) { notice('Não foi possível concluir a exclusão ou criar uma nova sessão. Verifique o serviço e tente novamente.', 'Verificar novamente', reconnect); }
    finally { busy = false; controls(); $('rb').focus(); }
  }
  $('f').addEventListener('submit', e => { e.preventDefault(); send(); });
  $('t').addEventListener('input', () => { $('t').style.height = '44px'; $('t').style.height = Math.min(100, Math.max(44, $('t').scrollHeight)) + 'px'; $('t').style.overflowY = $('t').scrollHeight > 100 ? 'auto' : 'hidden'; });
  $('t').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
  chips.forEach(b => b.addEventListener('click', () => send(b.dataset.question || b.textContent)));
  $('rb').addEventListener('click', () => { if (!busy) { $('cf').hidden = false; $('cy').focus(); } });
  $('cn').addEventListener('click', () => { $('cf').hidden = true; $('rb').focus(); });
  $('cy').addEventListener('click', resetConversation);
  restore(); renderConversation();
  document.fonts?.ready.then(scrollBottom);
  if (state.items.length) { $('rs').hidden = false; $('rn').textContent = `Conversa retomada neste navegador · ${state.items.length} mensagens`; }
  reconnect();
  setInterval(() => { if (!busy) health(); }, 30000);
})();
