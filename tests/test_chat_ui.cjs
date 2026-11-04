// Async client protocol tests with a minimal DOM test double, not a browser or LLM evaluation.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../src/emporio_ai/web/chat.js'), 'utf8');
class Element {
  constructor(tag = 'div', text = '') { this.tagName = tag; this.children = []; this.text = text; this.events = {}; this.hidden = false; this.disabled = false; this.value = ''; this.dataset = {}; this.attributes = {}; this.style = {}; this.classList = {toggle() {}}; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  set textContent(value) { this.text = String(value); this.children = []; }
  append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
  replaceChildren(...children) { this.children = []; this.text = ''; this.append(...children); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(name, callback) { (this.events[name] ||= []).push(callback); }
  click() { if (!this.disabled) for (const f of this.events.click || []) f({}); }
  fire(name, args = {}) { for (const f of this.events[name] || []) f({preventDefault() {}, ...args}); }
  focus() { this.focused = true; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); }
  get scrollHeight() { return this.children.length; }
}
const token = n => String(n).repeat(43);
const answer = {answer: 'Preço: R$ 10,00. <img src=x onerror=alert(1)>', status: 'completed', sources: [{id: 'policy:3.1', kind: 'policy', section: '3.1', title: 'Pagamento', text: '<script>unsafe</script>', pages: [3]}], tool_trace: [{tool: 'search_policies', ok: true}], model: 'test-double', request_id: 'fixture'};
function fixture({chat, initial, storageThrows = false, deleting, healthy = true} = {}) {
  const nodes = new Map(), calls = [], stored = new Map(); let sessions = 0;
  if (initial) stored.set('emporio_chat_v1', JSON.stringify(initial));
  const get = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  for (const id of ['rs', 'cf', 'notice', 'technical']) get(id).hidden = true;
  const chips = [new Element('button', 'Horário no sábado')];
  const storage = {
    getItem(k) { if (storageThrows) throw Error('blocked'); return stored.get(k) || null; },
    setItem(k, v) { if (storageThrows) throw Error('blocked'); stored.set(k, v); },
    removeItem(k) { if (storageThrows) throw Error('blocked'); stored.delete(k); }
  };
  async function fetch(url, options) {
    calls.push({url, ...options}); let status = 200, data;
    if (url === '/chat/health') { status = healthy ? 200 : 503; data = {status: 'ready'}; }
    else if (url === '/sessions') data = {session_id: token(++sessions)};
    else if (url === '/sessions/current') { status = deleting || 204; data = {detail: 'delete failed'}; }
    else if (url === '/chat') {
      const result = chat ? await chat(calls.filter(c => c.url === '/chat').length) : {data: answer};
      status = result.status || 200; data = result.data || {detail: result.detail || 'busy'};
    } else throw Error('Unexpected request: ' + url);
    return {status, ok: status >= 200 && status < 300, json: async () => data};
  }
  const document = {getElementById: get, createElement: tag => new Element(tag), createTextNode: text => new Element('#text', text), querySelectorAll: () => chips};
  vm.runInNewContext(code, {document, fetch, sessionStorage: storage, navigator: {clipboard: {writeText: async () => {}}}, AbortController, setTimeout, clearTimeout, setInterval() {}, console});
  const send = text => { get('t').value = text; get('f').fire('submit'); };
  return {get, calls, stored, send};
}
async function until(condition) {
  for (let i = 0; i < 100; i++) { if (condition()) return; await new Promise(resolve => setImmediate(resolve)); }
  assert.ok(condition(), 'async UI did not reach the expected state');
}
async function boot(f) { await until(() => !f.get('s').disabled); }
function saved(f) { return JSON.parse(f.stored.get('emporio_chat_v1')); }

test('creates session automatically; real evidence is rendered as text, never HTML', async () => {
  const f = fixture(); await boot(f); f.send('Preço e pagamento?');
  await until(() => f.get('msgs').textContent.includes(answer.answer) && !f.get('s').disabled);
  assert.equal(f.calls.filter(c => c.url === '/sessions').length, 1);
  assert.equal(f.calls.find(c => c.url === '/chat').headers.Authorization, 'Bearer ' + token(1));
  assert.match(f.get('msgs').textContent, /<script>unsafe<\/script>/);
  assert.match(f.get('tl').textContent, /search_policies/);
  assert.equal(saved(f).items.length, 2);
});
test('suppresses duplicate submissions while a request is pending', async () => {
  let release; const f = fixture({chat: () => new Promise(resolve => { release = resolve; })}); await boot(f);
  f.send('first'); f.send('second');
  await until(() => release);
  assert.equal(f.calls.filter(c => c.url === '/chat').length, 1);
  assert.equal(f.get('nc').disabled, true);
  release({data: answer}); await until(() => !f.get('s').disabled);
});
test('restores token, displayed messages and last trace without creating another session', async () => {
  const f = fixture({initial: {token: token(7), items: [{role: 'me', text: 'prior'}, {role: 'bot', text: answer.answer, result: answer}]}}); await boot(f);
  assert.equal(f.calls.filter(c => c.url === '/sessions').length, 0);
  assert.match(f.get('rn').textContent, /2 mensagens/);
  assert.match(f.get('msgs').textContent, /prior/);
  assert.match(f.get('tl').textContent, /search_policies/);
});
test('expired session creates a new session but never silently replays the message', async () => {
  const f = fixture({chat: n => n === 1 ? {status: 401} : {data: answer}}); await boot(f); f.send('last question');
  await until(() => f.get('notice-text').textContent.includes('expirou'));
  assert.equal(f.calls.filter(c => c.url === '/sessions').length, 2);
  assert.equal(f.calls.filter(c => c.url === '/chat').length, 1);
  assert.equal(saved(f).items.length, 0);
  f.get('notice-action').click(); await until(() => f.get('msgs').textContent.includes(answer.answer));
  assert.equal(f.calls.filter(c => c.url === '/chat').length, 2);
  assert.equal(saved(f).items.filter(i => i.role === 'me').length, 1);
});
test('busy response offers explicit retry without duplicating the customer bubble', async () => {
  const f = fixture({chat: n => n === 1 ? {status: 409} : {data: answer}}); await boot(f); f.send('retry me');
  await until(() => f.get('notice-text').textContent.includes('ocupado'));
  f.get('notice-action').click(); await until(() => f.get('msgs').textContent.includes(answer.answer));
  assert.equal(saved(f).items.filter(i => i.role === 'me').length, 1);
});
test('session limit offers New conversation rather than another failing send', async () => {
  const f = fixture({chat: () => ({status: 429, detail: 'Limite de turnos atingido.'})}); await boot(f); f.send('limit');
  await until(() => f.get('notice-text').textContent.includes('limite'));
  assert.equal(f.get('notice-action').textContent, 'Nova conversa');
  f.get('notice-action').click(); assert.equal(f.get('cf').hidden, false);
});
test('new conversation cancels locally or deletes the old session before creating another', async () => {
  const f = fixture(); await boot(f); f.send('old question'); await until(() => f.get('msgs').textContent.includes(answer.answer));
  f.get('nc').click(); f.get('cn').click(); assert.equal(f.calls.filter(c => c.method === 'DELETE').length, 0);
  f.get('nc').click(); f.get('cy').click(); await until(() => f.calls.filter(c => c.url === '/sessions').length === 2 && !f.get('s').disabled);
  const urls = f.calls.map(c => c.url);
  assert.ok(urls.lastIndexOf('/sessions/current') < urls.lastIndexOf('/sessions'));
  assert.equal(saved(f).items.length, 0);
  assert.equal(f.get('msgs').textContent.includes('old question'), false);
});
test('failed deletion preserves current conversation and does not report success', async () => {
  const f = fixture({deleting: 503}); await boot(f); f.send('keep me'); await until(() => f.get('msgs').textContent.includes(answer.answer));
  f.get('nc').click(); f.get('cy').click(); await until(() => f.get('notice-text').textContent.includes('exclusão'));
  assert.equal(saved(f).items.length, 2);
  assert.equal(f.calls.filter(c => c.url === '/sessions').length, 1);
});
test('blocked sessionStorage leaves the current in-memory conversation usable', async () => {
  const f = fixture({storageThrows: true}); await boot(f); f.send('works'); await until(() => f.get('msgs').textContent.includes(answer.answer));
  assert.equal(f.calls.filter(c => c.url === '/chat').length, 1);
});
test('offline model prevents sending and exposes a reconnect action', async () => {
  const f = fixture({healthy: false}); await until(() => f.get('notice-text').textContent.includes('indisponível'));
  assert.equal(f.get('s').disabled, true);
  assert.equal(f.calls.filter(c => c.url === '/chat').length, 0);
  assert.equal(f.get('notice-action').textContent, 'Verificar novamente');
});
