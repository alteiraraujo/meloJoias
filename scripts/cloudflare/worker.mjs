/**
 * Melo Joias / Bagy — página inicial para cadastro do aplicativo.
 * Cole este arquivo no editor do Worker melo-bagy e publique com Deploy.
 * Esta etapa NÃO implementa OAuth, troca de tokens ou sincronização.
 * Não adicione Consumer Secret ou tokens ao HTML desta página.
 */
const PAGE = `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Melo Joias · Integração Bagy</title>
  <style>
    *{box-sizing:border-box}body{margin:0;padding:32px 20px;background:#f5f6f2;color:#222b25;font:16px/1.6 system-ui,sans-serif}
    main{max-width:640px;margin:5vh auto;background:#fff;border:1px solid #e3e6df;border-radius:16px;overflow:hidden}
    header{background:#171c19;color:#fff;padding:26px 32px;letter-spacing:3px;font-size:22px}
    section{padding:30px 32px}h1{font:30px/1.2 Georgia,serif;margin:0 0 20px}p{margin:0 0 18px}
    .status{display:inline-block;background:#fff3d8;color:#705418;border:1px solid #eadbb8;border-radius:6px;padding:8px 12px;font-size:14px}
    button{display:block;width:100%;padding:13px;margin-top:22px;border:0;border-radius:7px;background:#e8ebe4;color:#586151;font:inherit;cursor:not-allowed}
    footer{border-top:1px solid #e3e6df;padding:18px 32px;color:#646d63;font-size:14px}
    @media(max-width:480px){body{padding:16px}main{margin:16px auto}header,section,footer{padding:24px}h1{font-size:26px}}
  </style>
</head>
<body><main>
  <header>MELO JOIAS</header>
  <section>
    <h1>Conexão com a Bagy</h1>
    <p>O Melo Joias organiza produtos, clientes, estoque e consignações em uma aplicação local.</p>
    <p>Esta página será utilizada para conectar a loja Bagy ao sistema, após a configuração e autorização da integração.</p>
    <p class="status">Aguardando configuração da integração</p>
    <p>A autorização estará disponível após o recebimento das chaves do aplicativo e a implementação do fluxo de conexão.</p>
    <button type="button" disabled>Autorizar integração — em preparação</button>
  </section>
  <footer>Nenhuma loja foi conectada por esta página. Seus cadastros continuam no sistema local.</footer>
</main></body></html>`;

function respond(request, body, status = 200, extraHeaders = {}) {
  return new Response(request.method === 'HEAD' ? null : body, {
    status,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'Referrer-Policy': 'no-referrer',
      'X-Content-Type-Options': 'nosniff',
      'X-Robots-Tag': 'noindex, nofollow',
      // No frame restriction here: Bagy opens the public installation page in an iframe.
      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
      ...extraHeaders,
    },
  });
}

export default {
  async fetch(request) {
    if (!['GET', 'HEAD'].includes(request.method)) {
      return respond(request, '<p>Método não permitido.</p>', 405, { Allow: 'GET, HEAD' });
    }
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';
    // Do not echo, log, store, or forward query parameters (they may contain codes).
    if (path === '/bagy/callback/auth' || url.searchParams.has('code') || url.searchParams.has('error')) {
      return respond(request, '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Integração em preparação</title><p>A integração ainda não está configurada. Nenhuma autorização foi concluída. Retorne ao sistema após a configuração do aplicativo.</p></html>', 503);
    }
    if (path === '/' || path === '/bagy/callback') return respond(request, PAGE);
    return respond(request, '<p>Página não encontrada.</p>', 404);
  },
};
