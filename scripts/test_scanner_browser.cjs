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
import django, json
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
print(json.dumps({'ean': p.ean13, 'product': p.pk, 'second': q.pk}))
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
    await page.getByRole('button', { name: 'Salvar rascunho' }).click();
    await page.waitForURL(/\/consignacoes\/\d+\/$/);
    const draftUrl = page.url();
    await page.goto(`${draftUrl}editar/`);
    assert.equal(await toggle.isChecked(), false);
    assert.equal(await quantity().inputValue(), '3');
    await toggle.check();
    await rows.first().locator('.remove-item').click();
    await scan(fixture.ean);
    assert.equal(await rows.count(), 2);
    await page.getByRole('button', { name: 'Salvar rascunho' }).click();
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
    assert.deepEqual(errors, []);
    console.log('PASS: EAN/SKU scans, quantities, negotiated price, stock, errors, manual mode, persistence, deletion, draft save, mobile and label.');
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
