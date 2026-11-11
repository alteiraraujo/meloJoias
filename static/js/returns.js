/* Local return checking; stock changes only after a server-confirmed batch. */
(() => {
  'use strict';
  const form = document.getElementById('return-scan-form');
  if (!form) return;
  const $ = id => document.getElementById(id);
  const items = JSON.parse($('return-item-data').textContent);
  const cart = new Map();
  const input = $('return-code');
  const toggle = $('return-enabled');
  const confirm = $('return-confirm');
  const feedback = $('return-feedback');
  let busy = false;
  const notify = (text, error = false) => {
    feedback.textContent = text;
    feedback.classList.toggle('text-danger', error);
    input.setAttribute('aria-invalid', String(error));
  };
  const render = () => {
    const body = $('return-cart');
    body.replaceChildren();
    let total = 0;
    for (const { item, quantity } of cart.values()) {
      const row = document.createElement('tr');
      const name = row.insertCell();
      const title = document.createElement('strong');
      title.textContent = item.name; title.className = 'table-primary';
      const sku = document.createElement('span');
      sku.textContent = item.sku; sku.className = 'table-secondary';
      name.append(title, sku);
      row.insertCell().textContent = String(item.pending);
      const qty = document.createElement('input');
      Object.assign(qty, { type:'number', min:'1', max:String(item.pending), step:'1', value:String(quantity), disabled:busy });
      qty.setAttribute('aria-label', `Devolver ${item.name}`);
      qty.addEventListener('change', () => {
        const value = Number(qty.value);
        if (!Number.isSafeInteger(value) || value < 1 || value > item.pending) {
          qty.value = String(quantity);
          notify(`Informe de 1 a ${item.pending} unidades de ${item.name}.`, true);
          return;
        }
        cart.set(item.id, { item, quantity:value });
        render();
      });
      row.insertCell().append(qty);
      const remove = document.createElement('button');
      Object.assign(remove, { type:'button', textContent:'Remover', className:'button secondary small', disabled:busy });
      remove.setAttribute('aria-label', `Remover ${item.name} da conferência`);
      remove.addEventListener('click', () => { cart.delete(item.id); render(); notify('Peça removida da conferência.'); });
      row.insertCell().append(remove);
      body.append(row);
      total += quantity;
    }
    $('return-total').textContent = String(total);
    $('return-cart-wrap').hidden = !cart.size;
    confirm.disabled = busy || !cart.size;
    $('return-clear').disabled = busy || !cart.size;
  };
  const setMode = (focus = false) => {
    $('return-controls').hidden = !toggle.checked;
    input.disabled = busy || !toggle.checked;
    $('return-add').disabled = busy || !toggle.checked;
    input.value = '';
    $('return-mode').textContent = toggle.checked
      ? 'Ligado · Leia as etiquetas das peças recebidas.'
      : 'Desligado · Use o acerto manual abaixo ou ative o leitor.';
    try { localStorage.setItem('melo.returns.enabled', String(toggle.checked)); } catch {}
    if (focus && toggle.checked && !busy) input.focus();
  };
  const scan = () => {
    if (busy || !toggle.checked) return;
    const code = input.value.trim();
    if (!code) return;
    const reject = text => { notify(text, true); input.focus(); input.select(); };
    const matches = items.filter(item => item.codes.includes(code));
    if (!matches.length) return reject('Código não encontrado nesta consignação. Confira a etiqueta e a revendedora.');
    if (matches.length !== 1) return reject('Código ambíguo nesta consignação. Confira os cadastros ou use o acerto manual.');
    const item = matches[0];
    const quantity = (cart.get(item.id)?.quantity || 0) + 1;
    if (quantity > item.pending) return reject(`${item.name}: somente ${item.pending} unidade(s) pendente(s). Confira a quantidade já lida.`);
    cart.set(item.id, { item, quantity });
    render();
    notify(`${item.name}: +1 unidade · ${quantity} nesta conferência.`);
    input.value = ''; input.focus();
  };
  $('return-scanner').hidden = false;
  try { toggle.checked = localStorage.getItem('melo.returns.enabled') === 'true'; } catch {}
  toggle.addEventListener('change', () => setMode(true));
  $('return-add').addEventListener('click', scan);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' || (event.key === 'Tab' && !event.shiftKey && input.value.trim())) {
      event.preventDefault();
      if (!event.repeat && !event.isComposing) scan();
    }
  });
  form.addEventListener('keydown', event => {
    if (event.key === 'Enter' && event.target.tagName === 'INPUT') event.preventDefault();
  });
  $('return-clear').addEventListener('click', () => { cart.clear(); render(); notify('Conferência limpa. O estoque não foi alterado.'); });
  window.addEventListener('beforeunload', event => {
    if (cart.size) { event.preventDefault(); event.returnValue = ''; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !cart.size) return;
    const payload = new FormData(form);
    payload.set('entries', JSON.stringify([...cart.values()].map(({item, quantity}) => ({
      item_id:item.id, quantity, expected_sold:item.sold, expected_returned:item.returned,
    }))));
    busy = true; toggle.disabled = true; setMode(); render();
    confirm.textContent = 'Confirmando…';
    notify('Registrando a devolução. Aguarde a confirmação.');
    try {
      const response = await fetch(form.action, { method:'POST', body:payload, credentials:'same-origin', headers:{Accept:'application/json'} });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Não foi possível confirmar. Recarregue a página para conferir o saldo.');
      cart.clear();
      window.location.reload();
    } catch (error) {
      notify(error instanceof SyntaxError || error instanceof TypeError
        ? 'A confirmação não foi recebida. Recarregue a página para conferir se a devolução foi registrada antes de tentar novamente.' : error.message, true);
      busy = false; toggle.disabled = false; setMode(); render();
      confirm.textContent = 'Confirmar devolução';
    }
  });
  setMode(); render();
})();
