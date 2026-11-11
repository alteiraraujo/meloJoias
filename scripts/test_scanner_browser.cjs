/* Optional browser regression test. Requires Playwright in the development environment.
 * Uses a temporary SQLite database; never opens the user's databases. */
const { chromium } = require('playwright');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname, '..');
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'melo-scanner-'));
  const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const env = { ...process.env, DB_ENGINE: 'sqlite', MELO_DATA_DIR: temporary,
    MELO_DEMO_MODE: '0', MELO_DEBUG: '1', DJANGO_SETTINGS_MODULE: 'config.settings', PYTHONIOENCODING: 'utf-8' };
  let server, browser;
  try {
    const setup = spawnSync(python, ['-c', `
import django, json, base64
django.setup()
from django.core.management import call_command
call_command('migrate', verbosity=0)
from core.models import Category, Product, Client
c = Category.objects.create(name='Categoria de teste')
p = Product.objects.create(sku='000123', name='Anel de teste', category=c, sale_price='39.90', stock_quantity=3)
q = Product.objects.create(sku='BR-02', name='Brinco de teste', category=c, sale_price='10.00', stock_quantity=10)
Product.objects.create(sku='ZERO', name='Sem estoque', category=c, sale_price=1, stock_quantity=0)
Product.objects.create(sku='INACTIVE', name='Inativo', category=c, sale_price=1, stock_quantity=5, active=False)
Client.objects.create(name='Cliente do teste de leitura')
from core.test_documents import pdf_bytes
print(json.dumps({'ean': p.ean13, 'product': p.pk, 'second': q.pk, 'pdf': base64.b64encode(pdf_bytes()).decode()}))
`], { cwd: root, env, encoding: 'utf8' });
    assert.equal(setup.status, 0, setup.stderr);
    const fixture = JSON.parse(setup.stdout.trim());
    // Port 0 asks the OS for a free loopback port.
    server = spawn(python, ['-u', '-c', `
from wsgiref.simple_server import make_server
from django.core.wsgi import get_wsgi_application
server = make_server('127.0.0.1', 0, get_wsgi_application())
print(server.server_port, flush=True)
server.serve_forever()
`], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
    const port = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Server startup timed out')), 15000);
      server.once('error', reject);
      server.stdout.once('data', data => { clearTimeout(timer); resolve(Number(String(data).trim())); });
    });
    const base = `http://127.0.0.1:${port}`;
    browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}) });
    const page = await browser.newPage({ viewport: { width: 1366, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/cadastros/products/${fixture.product}/editar/`);
    assert.equal(await page.locator('.sidebar').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(8, 8, 8)');
    assert.equal(await page.locator('.page-subtitle').evaluate(el => getComputedStyle(el).color), 'rgb(77, 77, 77)');
    // Reuse the local logo only as an upload fixture; no real product is modified.
    const photo = path.join(root, 'static/img/logo.png');
    await page.locator('#id_photo').setInputFiles(photo);
    await page.locator('#product-photo-preview').evaluate(image => image.decode());
    await page.getByRole('button', { name: 'Salvar cadastro' }).click();
    await page.waitForURL(`${base}/cadastros/products/`);
    await page.locator('.product-thumbnail').first().evaluate(image => image.decode());
    await page.goto(`${base}/cadastros/products/${fixture.product}/editar/`);
    await page.locator('#product-photo-preview').evaluate(image => image.decode());
    await page.locator('#photo-clear_id').check();
    assert.equal(await page.locator('#product-photo-preview').isVisible(), false);
    await page.getByRole('button', { name: 'Salvar cadastro' }).click();
    await page.waitForURL(`${base}/cadastros/products/`);
    assert.equal(await page.locator('.product-thumbnail').count(), 0);
    await page.goto(`${base}/cadastros/products/${fixture.product}/editar/`);
    await page.locator('#id_photo').setInputFiles(photo);
    await page.getByRole('button', { name: 'Salvar cadastro' }).click();
    await page.waitForURL(`${base}/cadastros/products/`);
    await page.goto(`${base}/backups/`);
    const downloading = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Gerar e baixar backup' }).click();
    const download = await downloading;
    assert.ok(download.suggestedFilename().endsWith('.zip'));
    await download.saveAs(path.join(temporary, 'photo-backup.zip'));
    await page.goto(`${base}/consignacoes/nova/`);
    const input = page.locator('#scanner-code');
    const toggle = page.locator('#scanner-enabled');
    const rows = page.locator('.item-form-row:visible');
    const quantity = () => rows.first().locator('[name$="-quantity"]');
    const scan = async (value, suffix = 'Enter') => { await input.fill(value); await input.press(suffix); };
    assert.equal(await toggle.isChecked(), false);
    assert.equal(await input.isVisible(), false);
    await toggle.check();
    await scan(fixture.ean);
    assert.equal(await rows.count(), 1);
    assert.equal(await quantity().inputValue(), '1');
    assert.equal(await input.inputValue(), '');
    assert.equal(await input.evaluate(el => el === document.activeElement), true);
    await rows.first().locator('[name$="-unit_price"]').fill('35,00');
    await scan('000123', 'Tab');
    assert.equal(await quantity().inputValue(), '2');
    assert.equal(await rows.first().locator('[name$="-unit_price"]').inputValue(), '35,00');
    await scan('000123');
    assert.equal(await quantity().inputValue(), '3');
    await scan('000123');
    assert.match(await page.locator('#scanner-feedback').textContent(), /Estoque insuficiente/);
    assert.equal(await quantity().inputValue(), '3');
    for (const code of ['MISSING', '123', 'INACTIVE']) {
      await scan(code);
      assert.match(await page.locator('#scanner-feedback').textContent(), /não encontrado/);
      assert.equal(await rows.count(), 1);
    }
    await scan('ZERO');
    assert.match(await page.locator('#scanner-feedback').textContent(), /Estoque insuficiente/);
    await scan('BR-02');
    assert.equal(await rows.count(), 2);
    await input.press('Enter');
    assert.equal(page.url(), `${base}/consignacoes/nova/`);
    await toggle.uncheck();
    assert.equal(await input.isDisabled(), true);
    assert.equal(await rows.count(), 2);
    await rows.nth(1).locator('[name$="-quantity"]').fill('2');
    await page.selectOption('#id_client', { label: 'Cliente do teste de leitura' });
    await page.locator('#id_shipping_responsible').fill('Ana Melo');
    await page.locator('#id_shipping_method').fill('PAC');
    await page.locator('#id_tracking_code').fill('AA123456789BR');
    await page.getByRole('button', { name: 'Salvar consignação' }).click();
    await page.waitForURL(/\/consignacoes\/\d+\/$/);
    const draftUrl = page.url();
    assert.equal(await page.locator('#id_tracking_code').inputValue(), 'AA123456789BR');
    assert.equal(await page.locator('#id_shipping_responsible').inputValue(), 'Ana Melo');
    assert.equal(await page.locator('#id_shipping_method').inputValue(), 'PAC');
    await page.locator('#id_shipping_responsible').fill('Maria Melo');
    await page.locator('#id_shipping_method').fill('SEDEX');
    await page.locator('#id_tracking_code').fill('BB987654321BR');
    await page.getByRole('button', { name: 'Salvar dados de envio' }).click();
    await page.waitForURL(draftUrl);
    await page.goto(`${draftUrl}imprimir/`);
    assert.equal(await page.locator('.print-tracking').textContent().then(s => s.includes('BB987654321BR')), true);
    assert.match(await page.locator('.print-shipping').textContent(), /Maria Melo/);
    assert.match(await page.locator('.print-shipping').textContent(), /SEDEX/);
    assert.match(await page.locator('.signature-grid').textContent(), /Maria Melo/);
    await page.emulateMedia({ media:'print' });
    await page.screenshot({path:path.join(root, 'docs/preview-romaneio-rastreio.png'), fullPage:true});
    await page.emulateMedia({ media:'screen' });
    await page.goto(`${draftUrl}editar/`);
    assert.equal(await toggle.isChecked(), false);
    assert.equal(await quantity().inputValue(), '3');
    await toggle.check();
    await rows.first().locator('.remove-item').click();
    await scan(fixture.ean);
    assert.equal(await rows.count(), 2);
    await page.getByRole('button', { name: 'Salvar consignação' }).click();
    await page.waitForURL(draftUrl);
    await page.goto(`${draftUrl}editar/`);
    assert.equal(await toggle.isChecked(), true);
    assert.equal(await rows.count(), 2);
    // Fast sequential readings are not deduplicated or lost.
    await scan('BR-02');
    await scan('BR-02');
    const brRow = rows.filter({ has: page.locator('select option:checked', { hasText: 'BR-02' }) });
    assert.equal(await brRow.locator('[name$="-quantity"]').inputValue(), '4');
    await page.locator('#scanner-panel').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(root, 'docs/preview-leitor.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.goto(`${base}/produtos/${fixture.product}/etiqueta/`);
    await page.locator('.label-barcode').evaluate(image => image.decode());
    await page.emulateMedia({ media: 'print' });
    const dimensions = await page.locator('.product-label').boundingBox();
    console.log('Printed label dimensions (px):', dimensions);
    assert.ok(dimensions.height <= 65 * 96 / 25.4 + 1, 'Label must fit 65mm paper');
    await page.emulateMedia({ media: 'screen' });
    await page.screenshot({ path: path.join(root, 'docs/preview-etiqueta.png'), fullPage: true });
    await page.setViewportSize({ width: 1366, height: 1000 });
    await page.goto(draftUrl);
    page.once('dialog', dialog => dialog.accept());
    await Promise.all([
      page.waitForNavigation(),
      page.getByRole('button', { name: 'Confirmar envio', exact: true }).click(),
    ]);
    const returnToggle = page.locator('#return-enabled');
    const returnInput = page.locator('#return-code');
    const returnRows = page.locator('#return-cart tr');
    const scanReturn = async (code, suffix = 'Enter') => { await returnInput.fill(code); await returnInput.press(suffix); };
    assert.equal(await returnToggle.isChecked(), false);
    await returnToggle.check();
    await scanReturn(fixture.ean);
    assert.equal(await returnRows.count(), 1);
    assert.equal(await returnRows.first().locator('input').inputValue(), '1');
    assert.equal(await returnInput.evaluate(el => el === document.activeElement), true);
    await scanReturn('000123');
    assert.match(await page.locator('#return-feedback').textContent(), /somente 1 unidade/);
    for (const code of ['MISSING', '123', 'ZERO']) {
      await scanReturn(code);
      assert.match(await page.locator('#return-feedback').textContent(), /não encontrado nesta consignação/);
    }
    await scanReturn('BR-02', 'Tab');
    await scanReturn('BR-02');
    assert.equal(await returnRows.nth(1).locator('input').inputValue(), '2');
    await returnRows.nth(1).locator('input').fill('1');
    await returnRows.nth(1).locator('input').press('Tab');
    assert.equal(await page.locator('#return-total').textContent(), '2');
    await returnRows.nth(1).getByRole('button').click();
    await scanReturn('BR-02');
    await returnToggle.uncheck();
    assert.equal(await returnInput.isDisabled(), true);
    assert.equal(await returnRows.count(), 2);
    await returnToggle.check();
    await page.locator('#return-scanner').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(root, 'docs/preview-devolucao-leitor.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const readReturnData = () => page.locator('#return-item-data').textContent().then(JSON.parse);
    assert.ok((await readReturnData()).every(item => item.returned === 0));
    await Promise.all([page.waitForNavigation(), page.locator('#return-confirm').click()]);
    assert.equal(await returnToggle.isChecked(), true);
    const returned = await readReturnData();
    assert.ok(returned.every(item => item.returned === 1));
    assert.equal(returned.reduce((sum, item) => sum + item.pending, 0), 1);
    await scanReturn('BR-02');
    await Promise.all([page.waitForNavigation(), page.locator('#return-confirm').click()]);
    assert.equal(await page.locator('#return-scanner').count(), 0);
    const documentPanel = page.locator('#signed-document');
    const pdfPayload = { name: 'romaneio-assinado.pdf', mimeType: 'application/pdf', buffer: Buffer.from(fixture.pdf, 'base64') };
    await page.locator('#id_signed_document').setInputFiles({ name:'falso.pdf', mimeType:'application/pdf', buffer:Buffer.from('not a PDF') });
    await Promise.all([page.waitForNavigation(), documentPanel.getByRole('button', { name:'Anexar PDF assinado' }).click()]);
    assert.match(await documentPanel.textContent(), /não é um PDF válido/);
    await page.locator('#id_signed_document').setInputFiles(pdfPayload);
    await Promise.all([page.waitForNavigation(), documentPanel.getByRole('button', { name:'Anexar PDF assinado' }).click()]);
    assert.equal(await documentPanel.getByRole('link', { name:'Abrir PDF' }).count(), 1);
    const pdfResponse = await page.request.get(await documentPanel.getByRole('link', { name:'Abrir PDF' }).getAttribute('href').then(href => base + href));
    assert.equal(pdfResponse.status(), 200);
    assert.deepEqual(await pdfResponse.body(), pdfPayload.buffer);
    const pdfDownloadEvent = page.waitForEvent('download');
    await documentPanel.getByRole('link', { name:'Baixar PDF' }).click();
    const pdfDownload = await pdfDownloadEvent;
    const downloadedPdf = path.join(temporary, 'downloaded.pdf');
    await pdfDownload.saveAs(downloadedPdf);
    assert.deepEqual(fs.readFileSync(downloadedPdf), pdfPayload.buffer);
    await page.locator('#id_signed_document').setInputFiles(pdfPayload);
    await Promise.all([page.waitForNavigation(), documentPanel.getByRole('button', { name:'Substituir PDF' }).click()]);
    assert.match(await documentPanel.textContent(), /Confirme a substituição/);
    await page.locator('#id_signed_document').setInputFiles(pdfPayload);
    await page.locator('#id_replace_document').check();
    await Promise.all([page.waitForNavigation(), documentPanel.getByRole('button', { name:'Substituir PDF' }).click()]);
    assert.match(await page.locator('body').textContent(), /Romaneio assinado anexado/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.setViewportSize({ width:1366, height:1000 });
    await documentPanel.scrollIntoViewIfNeeded();
    await page.screenshot({ path:path.join(root, 'docs/preview-romaneio-assinado.png') });
    await page.goto(draftUrl);
    await page.getByRole('link', { name:'Etiqueta da maleta', exact:true }).click();
    const shippingSetupUrl = page.url();
    assert.equal(await page.locator('#shipping-label-preview').count(), 0);
    await page.getByRole('link', { name:'Editar endereço da revendedora' }).click();
    const destinationAddress = {postal_code:'01001-000',street:'Praça da Sé',number:'100',complement:'Sala 2',neighborhood:'Sé',city:'São Paulo',state:'SP'};
    for (const [field,value] of Object.entries(destinationAddress)) {
      if (field === 'state') await page.selectOption('#id_state', value);
      else await page.locator(`#id_${field}`).fill(value);
    }
    await page.getByRole('button', { name:'Salvar cadastro' }).click();
    await page.waitForURL(shippingSetupUrl);
    await page.locator('#id_name').fill('Melo Joias - teste');
    const originAddress = {postal_code:'20040-002',street:'Rua da Assembleia',number:'10',complement:'Sala 1',neighborhood:'Centro',city:'Rio de Janeiro',state:'RJ'};
    for (const [field,value] of Object.entries(originAddress)) {
      if (field === 'state') await page.selectOption('#id_state', value);
      else await page.locator(`#id_${field}`).fill(value);
    }
    await page.getByRole('button', { name:'Salvar remetente' }).click();
    await page.waitForURL(shippingSetupUrl);
    const postalUrl = base + await page.locator('#shipping-label-preview').getAttribute('href');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.goto(postalUrl);
    await page.waitForFunction(() => !document.getElementById('postal-print').disabled);
    assert.match(await page.locator('.postal-destination').textContent(), /01001-000/);
    assert.match(await page.locator('.postal-sender').textContent(), /20040-002/);
    await page.setViewportSize({width:794,height:1123});
    await page.emulateMedia({media:'print'});
    const postalBox = await page.locator('.postal-label').boundingBox();
    assert.ok(Math.abs(postalBox.width - 106.36*96/25.4) < 1);
    assert.ok(Math.abs(postalBox.height - 138.11*96/25.4) < 1);
    await page.locator('.postal-label').screenshot({path:path.join(root,'docs/preview-etiqueta-maleta.png')});
    const postalPdf = path.join(temporary,'etiqueta-maleta.pdf');
    await page.pdf({path:postalPdf,preferCSSPageSize:true,printBackground:true});
    const pdfCheck = spawnSync(python, ['-c', 'import sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); assert len(r.pages)==1; t=r.pages[0].extract_text(); assert "01001-000" in t and "20040-002" in t; assert abs(float(r.pages[0].mediabox.width)-595.28)<2', postalPdf], {cwd:root,env,encoding:'utf8'});
    assert.equal(pdfCheck.status,0,pdfCheck.stderr);
    await page.evaluate(() => {document.querySelector('.postal-destination .postal-address').textContent='Endereço muito extenso '.repeat(300); window.dispatchEvent(new Event('beforeprint'));});
    assert.equal(await page.locator('#postal-print').isDisabled(),true);
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    assert.equal(await page.locator('#postal-print').isDisabled(),true);
    await page.emulateMedia({media:'screen'});
    assert.deepEqual(errors, []);
    console.log('PASS: shipping label setup, recipient address, sender persistence, mobile, physical dimensions, A4 PDF and overflow guard.');
    console.log('PASS: signed PDF upload, invalid file rejection, open/download bytes, replacement confirmation and mobile.');
    console.log('PASS: return scans, pending limits, foreign codes, quantity correction, removal, toggle, confirmation, stock workflow and mobile.');
    console.log('PASS: contrast, photo upload/preview/removal, photo backup, tracking/packing slip, EAN/SKU scans, quantities, negotiated price, stock, errors, manual mode, persistence, deletion, draft save, mobile and label.');
  } finally {
    await browser?.close();
    if (server && server.exitCode === null) {
      const exited = new Promise(resolve => server.once('exit', resolve));
      server.kill();
      await exited;
    }
    // Only the exact directory created by mkdtemp above may be removed.
    if (path.dirname(temporary) === path.resolve(os.tmpdir()) && path.basename(temporary).startsWith('melo-scanner-')) {
      fs.rmSync(temporary, { recursive: true, force: true });
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
