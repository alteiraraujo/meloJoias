/* Melo Joias — interface local, sem dependências externas. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const menuButton = $('[data-open-menu]');
  const setMenu = (open) => {
    document.body.classList.toggle('sidebar-open', open);
    menuButton?.setAttribute('aria-expanded', String(open));
    if (open) $('#sidebar a')?.focus();
    else menuButton?.focus();
  };
  menuButton?.addEventListener('click', () => setMenu(!document.body.classList.contains('sidebar-open')));
  $('[data-close-menu]')?.addEventListener('click', () => setMenu(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('sidebar-open')) setMenu(false);
  });
  $$('[data-dismiss]').forEach((button) => button.addEventListener('click', () => button.closest('.alert')?.remove()));
  $$('[data-print]').forEach((button) => button.addEventListener('click', () => window.print()));
  $$('[data-confirm]').forEach((button) => button.addEventListener('click', (event) => {
    if (!window.confirm(button.dataset.confirm)) event.preventDefault();
  }));

  const photoInput = $('#id_photo');
  if (photoInput) {
    const preview = $('#product-photo-preview');
    const empty = $('#product-photo-empty');
    const status = $('#product-photo-status');
    const clear = $('#photo-clear_id');
    let objectUrl;
    const renderPhoto = () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
      const file = photoInput.files[0];
      photoInput.setCustomValidity('');
      status.classList.remove('text-danger');
      let source = clear?.checked ? '' : preview.dataset.originalSrc || '';
      if (file && !clear?.checked) {
        if (file.size > 5 * 1024 * 1024) {
          photoInput.setCustomValidity('A foto deve ter no máximo 5 MB.');
          status.textContent = 'A foto deve ter no máximo 5 MB. Escolha um arquivo menor.';
          status.classList.add('text-danger');
        } else {
          objectUrl = URL.createObjectURL(file);
          source = objectUrl;
          status.textContent = 'Nova foto selecionada. Clique em Salvar cadastro para confirmar.';
        }
      } else status.textContent = clear?.checked ? 'A foto será removida ao salvar o cadastro.' : '';
      preview.hidden = !source;
      empty.hidden = Boolean(source);
      if (source) preview.src = source;
      else preview.removeAttribute('src');
    };
    photoInput.addEventListener('change', () => { if (clear) clear.checked = false; renderPhoto(); });
    clear?.addEventListener('change', () => { if (clear.checked) photoInput.value = ''; renderPhoto(); });
    preview.addEventListener('error', () => {
      preview.hidden = true; empty.hidden = false;
      status.textContent = 'Não foi possível exibir a foto. Escolha uma imagem JPG, PNG ou WebP válida.';
      status.classList.add('text-danger');
    });
  }

  const form = $('#consignment-form');
  if (!form) return;
  const readJSON = (id) => {
    try { return JSON.parse(document.getElementById(id)?.textContent || '[]'); }
    catch { return []; }
  };
  const products = new Map(readJSON('product-data').map((product) => [String(product.id), product]));
  const contacts = new Map(readJSON('contact-data').map((contact) => [String(contact.id), contact]));
  const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const decimal = (value) => {
    let normalized = String(value || '').replace(/R\$|\s/g, '');
    if (normalized.includes(',')) normalized = normalized.replace(/\./g, '').replace(',', '.');
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const rows = $('#item-rows');
  const totalForms = $(`#id_${form.dataset.prefix}-TOTAL_FORMS`);
  const addButton = $('#add-item');
  const emptyTemplate = $('#empty-item-form');
  const activeRows = () => $$('.item-form-row', rows).filter((row) => !row.hidden);

  const recalculate = () => {
    let valueCents = 0;
    let pieces = 0;
    activeRows().forEach((row) => {
      const productId = $('[name$="-product"]', row)?.value;
      const quantity = Math.max(0, Math.floor(decimal($('[name$="-quantity"]', row)?.value)));
      const priceCents = Math.round(decimal($('[name$="-unit_price"]', row)?.value) * 100);
      const subtotalCents = productId ? quantity * priceCents : 0;
      $('.row-total', row).textContent = currency.format(subtotalCents / 100);
      valueCents += subtotalCents;
      if (productId) pieces += quantity;
    });
    $('#pieces-count').textContent = String(pieces);
    $('#consignment-total').textContent = currency.format(valueCents / 100);
    addButton.disabled = activeRows().length >= 100;
    addButton.title = addButton.disabled ? 'Limite de 100 produtos por consignação.' : '';
  };

  const updateStockHint = (row) => {
    const product = products.get($('[name$="-product"]', row)?.value);
    const hint = $('.stock-hint', row);
    if (!hint) return;
    hint.textContent = product ? `${product.stock} ${Number(product.stock) === 1 ? 'peça disponível' : 'peças disponíveis'} em estoque` : 'Selecione um produto do seu acervo.';
    const quantity = decimal($('[name$="-quantity"]', row)?.value);
    hint.classList.toggle('text-amber', Boolean(product && quantity > Number(product.stock)));
    if (product && quantity > Number(product.stock)) hint.textContent += ' · Quantidade maior que o estoque atual.';
  };

  const hideRow = (row) => {
    const deleteInput = $('[name$="-DELETE"]', row);
    if (!deleteInput) return;
    deleteInput.checked = true;
    row.hidden = true;
    $$('input, select, textarea', row).forEach((field) => {
      if (field !== deleteInput && field.type !== 'hidden') { field.required = false; field.disabled = true; }
    });
  };

  const wireRow = (row) => {
    const productSelect = $('[name$="-product"]', row);
    const priceInput = $('[name$="-unit_price"]', row);
    const quantityInput = $('[name$="-quantity"]', row);
    // Os nomes visíveis das colunas são compartilhados; cada controle também recebe um rótulo próprio.
    productSelect?.setAttribute('aria-label', 'Produto da consignação');
    priceInput?.setAttribute('aria-label', 'Preço unitário em reais');
    quantityInput?.setAttribute('aria-label', 'Quantidade de peças');
    productSelect?.addEventListener('change', () => {
      const product = products.get(productSelect.value);
      if (product && priceInput) priceInput.value = Number(product.price).toFixed(2).replace('.', ',');
      updateStockHint(row);
      recalculate();
    });
    quantityInput?.addEventListener('input', () => { updateStockHint(row); recalculate(); });
    priceInput?.addEventListener('input', recalculate);
    $('.remove-item', row)?.addEventListener('click', () => {
      hideRow(row);
      recalculate();
      addButton.focus();
    });
    if ($('[name$="-DELETE"]', row)?.checked) hideRow(row);
    updateStockHint(row);
  };

  $$('.item-form-row', rows).forEach(wireRow);
  const appendRow = () => {
    if (activeRows().length >= 100 || !emptyTemplate || !totalForms) return null;
    const index = Number(totalForms.value);
    const wrapper = document.createElement('template');
    wrapper.innerHTML = emptyTemplate.innerHTML.replace(/__prefix__/g, String(index));
    const row = wrapper.content.querySelector('.item-form-row');
    rows.appendChild(wrapper.content);
    totalForms.value = String(index + 1);
    wireRow(row);
    recalculate();
    return row;
  };
  addButton?.addEventListener('click', () => {
    const row = appendRow();
    if (!row) return;
    $('[name$="-product"]', row)?.focus();
  });

  const scannerPanel = $('#scanner-panel');
  const scannerToggle = $('#scanner-enabled');
  const scannerControls = $('#scanner-controls');
  const scannerInput = $('#scanner-code');
  const scannerButton = $('#scan-add');
  const scannerFeedback = $('#scanner-feedback');
  const feedback = (message, error = false) => {
    scannerFeedback.textContent = message;
    scannerFeedback.classList.toggle('text-danger', error);
    scannerInput.setAttribute('aria-invalid', String(error));
  };
  const scan = () => {
    if (!scannerToggle.checked) return;
    const code = scannerInput.value.trim();
    // Empty suffixes (including CR/LF) must never submit the surrounding form.
    if (!code) return;
    const matches = [...products.values()].filter((p) => p.sku === code || p.ean13 === code);
    const reject = (message) => { feedback(message, true); scannerInput.focus(); scannerInput.select(); };
    if (!matches.length) {
      reject(`Código ${code} não encontrado entre os produtos ativos. Confira o cadastro e a etiqueta.`);
      return;
    }
    if (matches.length !== 1) {
      reject('Este código identifica mais de um produto. Confira os SKUs ou selecione a peça manualmente.');
      return;
    }
    const product = matches[0];
    const matchingRows = activeRows().filter((r) => $('[name$="-product"]', r).value === String(product.id));
    if (matchingRows.length > 1) {
      reject('A peça está repetida na lista. Remova a linha duplicada antes de continuar a leitura.');
      return;
    }
    let row = matchingRows[0];
    const currentQuantity = row ? Number($('[name$="-quantity"]', row).value) : 0;
    if (row && (!Number.isSafeInteger(currentQuantity) || currentQuantity < 1)) {
      reject('Corrija a quantidade desta peça na lista antes de ler outra unidade.');
      return;
    }
    if (currentQuantity + 1 > Number(product.stock)) {
      reject(`Estoque insuficiente de ${product.name}: ${product.stock} disponível(is), ${currentQuantity} já selecionada(s).`);
      return;
    }
    if (!row) {
      row = activeRows().find((r) => !$('[name$="-product"]', r).value) || appendRow();
      if (!row) { reject('Limite de 100 produtos por consignação.'); return; }
      $('[name$="-product"]', row).value = String(product.id);
      $('[name$="-unit_price"]', row).value = Number(product.price).toFixed(2).replace('.', ',');
    }
    // Preserve any manually negotiated price when incrementing an existing item.
    $('[name$="-quantity"]', row).value = String(currentQuantity + 1);
    updateStockHint(row);
    recalculate();
    feedback(`${product.name}: +1 unidade · ${currentQuantity + 1} na consignação.`);
    scannerInput.value = '';
    scannerInput.focus();
  };
  if (scannerPanel) {
    scannerPanel.hidden = false;
    const setScannerMode = (focus = false) => {
      const enabled = scannerToggle.checked;
      scannerControls.hidden = !enabled;
      scannerInput.disabled = !enabled;
      scannerButton.disabled = !enabled;
      scannerInput.value = '';
      $('#scanner-mode-description').textContent = enabled
        ? 'Ligado · Cada leitura adiciona uma unidade. Você também pode editar a lista manualmente.'
        : 'Desligado · Adicione as peças manualmente.';
      feedback('Aguardando leitura.');
      try { localStorage.setItem('melo.scanner.enabled', String(enabled)); } catch { /* Storage may be unavailable. */ }
      if (enabled && focus) scannerInput.focus();
    };
    try { scannerToggle.checked = localStorage.getItem('melo.scanner.enabled') === 'true'; } catch { /* Default: off. */ }
    scannerToggle.addEventListener('change', () => setScannerMode(true));
    scannerButton.addEventListener('click', scan);
    scannerInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || (event.key === 'Tab' && !event.shiftKey && scannerInput.value.trim())) {
        event.preventDefault();
        if (!event.repeat && !event.isComposing) scan();
      }
    });
    setScannerMode();
  }

  const clientSelect = $('#id_client');
  const contactsField = $('#id_contacts');
  const contactsEmpty = document.createElement('p');
  contactsEmpty.className = 'contacts-empty';
  contactsEmpty.setAttribute('aria-live', 'polite');
  if (contactsField) contactsField.insertAdjacentElement('afterend', contactsEmpty);
  const filterContacts = () => {
    const clientId = clientSelect?.value;
    let count = 0;
    if (contactsField?.tagName === 'SELECT') {
      $$('option', contactsField).forEach((option) => {
        const matches = String(contacts.get(option.value)?.client_id) === clientId;
        option.hidden = !matches;
        option.disabled = !matches;
        if (!matches) option.selected = false;
        if (matches) count += 1;
      });
    } else if (contactsField) {
      $$('input[type=checkbox]', contactsField).forEach((checkbox) => {
        const matches = String(contacts.get(checkbox.value)?.client_id) === clientId;
        const container = checkbox.closest('label')?.parentElement;
        if (container) container.hidden = !matches;
        checkbox.disabled = !matches;
        if (!matches) checkbox.checked = false;
        if (matches) count += 1;
      });
    }
    if (contactsField) contactsField.hidden = count === 0;
    contactsEmpty.hidden = count > 0;
    contactsEmpty.textContent = clientId ? 'Esta revendedora ainda não possui referências cadastradas.' : 'Selecione uma revendedora para ver suas referências.';
  };
  clientSelect?.addEventListener('change', filterContacts);
  filterContacts();
  recalculate();
})();
