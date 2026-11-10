# Página inicial do aplicativo Bagy na Cloudflare

Worker criado pelo usuário: `https://melo-bagy.alteir-araujo.workers.dev/`.

URL planejada para o campo **URL de callback**:

```text
https://melo-bagy.alteir-araujo.workers.dev/bagy/callback/
```

## Publicar a página inicial

1. No painel Cloudflare, abra **Workers & Pages → melo-bagy → Edit code**.
2. Abra `scripts/cloudflare/worker.mjs` deste projeto e copie todo o conteúdo.
3. No arquivo de entrada do Worker (normalmente `worker.js` ou `index.js`), substitua o código de exemplo pelo conteúdo copiado. Preserve eventuais configurações do projeto. Se houver integração Git, mantenha também o código no repositório para que uma implantação posterior não reverta a edição.
4. Clique em **Deploy** para publicar; salvar uma versão sem implantá-la não atualiza o endereço público.
5. Abra a URL completa do callback em uma nova aba. Ela deve exibir **MELO JOIAS**, **Conexão com a Bagy** e **Aguardando configuração da integração**.
6. Use esse endereço para identificar a página do aplicativo na solicitação à Bagy, deixando claro que o fluxo de autorização está em desenvolvimento. A aprovação/homologação depende dos requisitos da Bagy; esta página inicial não garante aprovação.

Não é necessário instalar programas, criar banco online ou configurar chaves para publicar esta página inicial.

## O que esta etapa entrega

A página pública apresenta a aplicação e deixa explícito que a conexão está pendente. Ela aceita acesso por GET/HEAD, inclusive com os parâmetros iniciais da instalação, sem refletir os valores recebidos no HTML. Uma tentativa de retorno de autorização recebe HTTP 503, sem registrar sucesso fictício. O código não registra parâmetros em logs nem os armazena; a plataforma de hospedagem pode ter seus próprios logs de requisição.

**Ainda não implementado:** botão ativo de instalação, OAuth, validação da loja e da sessão de autorização, troca do código por tokens, armazenamento/renovação de tokens e entrega segura da conexão ao aplicativo local. O SQLite e os cadastros continuam locais. Nenhuma rota Bagy foi adicionada ao Django nesta etapa.

Após a emissão das chaves, será necessário implementar e testar esse fluxo antes de conectar uma loja. O `Consumer Secret` deve ficar em configuração secreta no servidor, nunca em HTML ou JavaScript entregue ao navegador. A página pública e o retorno da autorização são etapas diferentes, conforme o fluxo da Bagy.

## Referências

- [Bagy: cadastro do aplicativo e fluxo de autorização](https://developers.bagy.com.br/)
- [Cloudflare: gerenciamento de versões e implantações](https://developers.cloudflare.com/workers/versions-and-deployments/deployment-management/)

O arquivo local foi preparado para publicação manual. A criação deste arquivo não publica nem altera automaticamente o Worker da conta Cloudflare.
