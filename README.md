# Melo Joias — consignação local

Protótipo funcional para controlar produtos, categorias, custos por unidade, revendedoras, referências e consignações. A interface segue a marca Melo Joias, com preto, branco e tons neutros.

## Escolha técnica

**Django 5.2 LTS + SQLite + páginas renderizadas no servidor + Waitress.** Django concentra formulários, validação, transações, proteção CSRF e migrações em uma aplicação pequena, sem exigir Node.js ou uma interface separada. SQLite mantém o banco em um arquivo local e dispensa servidor, usuário ou senha. Waitress executa a aplicação no Windows.

A escolha usa a linha com suporte prolongado descrita nas [notas oficiais do Django 5.2](https://docs.djangoproject.com/en/5.2/releases/5.2/). O armazenamento local em arquivo se encaixa nos [usos recomendados do SQLite](https://www.sqlite.org/whentouse.html), e o servidor adotado é compatível com Windows conforme a [documentação do Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/).

O navegador acessa `http://127.0.0.1:8791`. Aplicação e banco ficam no computador; não há hospedagem em nuvem, CDN, fontes externas ou chamadas de serviços durante o uso. A primeira instalação precisa de internet para baixar as dependências Python.

## Começar no Windows

### Ferramentas necessárias

| Ferramenta / requisito | Para que serve | Como preparar |
|---|---|---|
| **Windows** | Executar os atalhos `.bat` fornecidos. | Extraia o projeto em uma pasta local com permissão de leitura e gravação, como `D:\aplicativos\melo-joias`. |
| **Python 3.11** | Executar a aplicação e o instalador. É a versão validada neste protótipo. | Instale o Python com os componentes `pip` e `venv`. O comando `py` ou `python` deve estar disponível no terminal. |
| **Navegador** | Acessar a interface local. | Use Microsoft Edge, Google Chrome ou Firefox atualizado. O fluxo de leitura foi testado no Edge. |
| **Internet na instalação e nas atualizações** | Baixar as bibliotecas Python. | Mantenha a conexão enquanto `INSTALAR.bat` instala as dependências. O uso normal do sistema é local. |

O instalador procura primeiro o comando `py -3` e, se ele não existir, usa `python`. Antes de começar, abra o Prompt de Comando ou PowerShell e confira:

```powershell
py -3 --version
py -3 -m pip --version
```

Se o comando `py` não estiver disponível, use `python --version` e `python -m pip --version`. Se nenhum dos dois for reconhecido, conclua a instalação do Python e sua inclusão no `PATH`, depois abra um novo terminal. Em computadores com várias versões de Python, confira qual delas o comando `py -3` seleciona.

### Bibliotecas instaladas automaticamente

O arquivo `requirements.txt` controla as dependências. Você não precisa instalar cada biblioteca manualmente: `INSTALAR.bat` cria a pasta `.venv` e instala tudo nela.

| Biblioteca | Versão definida no projeto | Função |
|---|---|---|
| Django | `5.2.18` | Aplicação, formulários, validações e tabelas do banco. |
| Waitress | `3.0.2` | Servidor HTTP local. |
| python-dotenv | `>=1,<2` | Leitura das configurações em `.env`. |
| WhiteNoise | `>=6,<7` | Entrega dos arquivos CSS, JavaScript e imagens. |
| python-barcode | `0.16.1` | Geração das barras EAN-13 para impressão. |
| Pillow | `12.3.0` | Validação e preparação das fotos dos produtos. |
| pypdf | `7.0.0` | Validação dos romaneios anexados em PDF. |

**SQLite já acompanha o Python** e o instalador cria o arquivo do banco. Para a instalação padrão, não é necessário instalar PostgreSQL, MySQL, Node.js, Docker ou um servidor web separado.

### Equipamentos e ferramentas opcionais

| Opção | Quando é necessária |
|---|---|
| Leitor óptico USB ou Bluetooth | Para adicionar peças pela etiqueta. Deve ler EAN-13 e funcionar como teclado, com sufixo Enter ou Tab. A inclusão manual funciona sem leitor. |
| Impressora configurada no Windows | Para imprimir as etiquetas. O formato inicial é 60 × 65 mm; confira papel e configuração de impressão compatíveis. Também é possível salvar em PDF pelo navegador. |
| PostgreSQL e adaptador Python | Somente se escolher esse banco. Consulte a seção **PostgreSQL opcional** para instalação, configuração e backup. |
| Editor de código, como VS Code | Para modificar os arquivos da aplicação. |
| Git | Para controlar versões do código durante o desenvolvimento. |
| Node.js, Playwright e navegador de teste | Somente para executar `scripts/test_scanner_browser.cjs`. Os testes Python usam as dependências já instaladas. |

### Instalação passo a passo

1. Instale o Python e confira os comandos acima.
2. Extraia o ZIP completo em uma pasta local. Execute os atalhos a partir da pasta extraída.
3. Abra `INSTALAR.bat`. Ele cria o ambiente Python, instala as bibliotecas, cria `.env` quando necessário, prepara as tabelas e os arquivos da interface. Aguarde a mensagem de instalação concluída.
4. Abra `INICIAR.bat` para cadastrar seus dados. O navegador abre automaticamente em `http://127.0.0.1:8791`.
5. Deixe a janela do servidor aberta durante o uso; `Ctrl+C` encerra a aplicação.

A instalação normal começa **sem dados de exemplo**, usando `data\melo.sqlite3`. Para experimentar exemplos fictícios, abra **`DEMONSTRACAO.bat`**: ele usa outro banco, `data\demo.sqlite3`, e abre `http://127.0.0.1:8792`. Os dados da demonstração permanecem separados dos seus cadastros e são preservados ao abrir novamente.

O protótipo foi pensado para uma pessoa em um computador de confiança. Não possui tela de login e o servidor escuta apenas `127.0.0.1`.

### Comandos manuais

Execute na pasta do projeto. Na primeira instalação, crie o ambiente virtual; se `py` não estiver disponível, substitua a primeira linha por `python -m venv .venv`.

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\setup.py
.venv\Scripts\python.exe scripts\start.py
```

O arquivo `.env` é criado automaticamente a partir de `.env.example`. As configurações normais são `DB_ENGINE=sqlite`, `MELO_DEMO_MODE=0` e `MELO_DEBUG=0`. Se a porta estiver ocupada, altere `MELO_PORT=8791` para outra porta local, por exemplo `8793`. A chave interna da aplicação é gerada em `data/.secret_key`.

## Fluxo de uso

1. Cadastre categorias, tipos de custo e produtos; informe código, preço, estoque inicial e componentes de custo por unidade.
2. Cadastre a revendedora e as referências vinculadas a ela.
3. Crie uma consignação AGUARDANDO ENVIO com revendedora, datas de envio/acerto e referências da mesma revendedora. Adicione os produtos e quantidades.
4. Confirme o envio para mudar para **EM TRÂNSITO**. O sistema verifica saldo e retira do estoque as unidades enviadas em uma transação.
5. Registre vendas, devoluções e pagamentos. Devoluções recompõem o estoque. O saldo financeiro considera somente peças vendidas, menos pagamentos.
6. Finalize após resolver todas as peças e quitar o saldo, mudando para **FINALIZADO**. O histórico preserva nome, código, preço e custo do produto no envio.

O cadastro de custos representa componentes do **custo por unidade do produto**, como compra, banho, embalagem ou frete rateado. Não é um módulo de despesas gerais, contabilidade, emissão fiscal ou contas a pagar. Quantidades são inteiras e valores são registrados em reais com duas casas decimais.

O fluxo principal é **AGUARDANDO ENVIO → EM TRÂNSITO → FINALIZADO**. O cancelamento antes do envio permanece como situação excepcional. Um prazo vencido é indicado separadamente e não substitui a etapa da consignação.

## Estrutura e atualizações

### Fotos dos produtos

Cada produto pode ter uma foto opcional. Em **Produtos → Novo produto / Editar**, selecione uma imagem JPG, PNG ou WebP de até **5 MB e 20 megapixels**. Confira a prévia e clique em **Salvar cadastro**. A aplicação corrige a orientação, reduz para até 1600 px e grava uma cópia JPEG sem metadados da câmera. A listagem mostra uma miniatura; produtos sem foto continuam funcionando normalmente.

Para trocar, selecione outro arquivo e salve. Para remover a associação, marque **Remover foto atual ao salvar**. Os arquivos antigos são preservados no disco para evitar perda em backups e operações simultâneas; não são mais exibidos no cadastro. Após erro de validação em outro campo, selecione novamente a nova imagem antes de reenviar o formulário.

As fotos ficam em `data/media/products/`; a demonstração usa `data/demo-media/products/`. Elas não são enviadas à nuvem nem incluídas no pacote de código-fonte. Use o backup completo para transferi-las junto com o banco.

### Responsável, tipo de envio e rastreio no romaneio

Os campos opcionais **Responsável pelo envio**, **Tipo de envio** e **Código de rastreio** ficam no cadastro da consignação. Informe o nome de quem enviará as peças e a modalidade, por exemplo PAC, SEDEX, transportadora, motoboy ou retirada. O tipo de envio aceita texto livre. Os dados também podem ser preenchidos ou corrigidos em **Detalhes da consignação → Sobre o envio → Salvar dados de envio**, inclusive depois de confirmar o envio ou finalizar. Consignações canceladas permitem apenas consulta. A alteração não movimenta estoque nem modifica os itens enviados.

Os três campos aparecem juntos no **Romaneio → Imprimir / salvar PDF**. Campos vazios mantêm espaço para preenchimento à mão; o nome do responsável também aparece na linha de assinatura do envio. O rastreio apenas registra o código; não consulta automaticamente a entrega nos Correios. Alterar esses dados não modifica um PDF assinado já anexado: esse arquivo original permanece preservado. A migração `0009` adiciona os campos de responsável e tipo de envio sem alterar os rastreios existentes.

### Etiqueta de endereçamento da maleta

Abra **Consignação → Etiqueta da maleta**. A etiqueta utiliza o nome, telefone e endereço da revendedora vinculada ao romaneio. Preencha no cadastro os campos **CEP, logradouro, número, complemento, bairro, cidade e UF**; complemento e telefone são opcionais. O endereço anterior em texto livre continua preservado. Quando os campos separados estiverem completos, o romaneio também passa a exibir esse endereço.

Na mesma tela, cadastre o **remetente e endereço de origem** uma vez. Esses dados ficam no banco local e são reutilizados nas próximas etiquetas. O nome do responsável pelo envio não substitui o endereço do remetente. A impressão fica disponível somente com ambos os endereços completos. A validação do CEP confere o formato de oito dígitos, sem consulta automática à base dos Correios.

Use **Visualizar / imprimir etiqueta → Imprimir / salvar PDF**. O formato é **106,36 mm de largura × 138,11 mm de altura**, em folha **A4**, com escala **100%**, sem cabeçalhos ou rodapés. Recorte pela borda; a etiqueta deve ficar inteira numa face da embalagem. A impressão acompanha o modelo de endereçamento para postagem na agência descrito no [Guia dos Correios](https://www.correios.com.br/enviar/precisa-de-ajuda/guia-de-enderecamento/guia-de-enderecamento), com área exclusiva para o identificador postal, destinatário destacado, remetente e campos de recebimento. Use ao menos 240 dpi. Endereços extensos são ajustados até 9 pt; se ainda não couberem, a impressão é bloqueada para revisão dos campos, sem cortar informações.

Esta é uma **etiqueta de endereçamento**, sem contratação de frete, código de postagem gerado ou integração com a API dos Correios. O comprovante de postagem e os rótulos de frete são emitidos pelos Correios; para uma postagem contratual, utilize o rótulo do serviço contratado. A etiqueta não expõe CPF, valores ou produtos da consignação e não autoriza entrega a vizinhos. Os PDFs assinados já anexados permanecem intactos.

A migração `0010` adiciona os campos de endereço e a tabela do remetente sem converter automaticamente textos antigos. O backup do banco já inclui esses dados. Não é necessário instalar outra ferramenta além das dependências existentes.

### Romaneio assinado em PDF

Em **Detalhes da consignação → Romaneio assinado**, selecione o PDF recebido da revendedora e clique em **Anexar PDF assinado**. São aceitos PDFs válidos, com páginas, sem senha ou criptografia, de até **20 MB**. O envio é opcional e está disponível também em consignações finalizadas. Anexar o documento não altera situação, estoque ou valores.

Após salvar, use **Abrir PDF** ou **Baixar PDF**. Para corrigir um anexo, escolha outro PDF, marque a confirmação de substituição e clique em **Substituir PDF**. A tela apresenta um documento atual por consignação e a data do upload. Após erro de validação, selecione novamente o arquivo.

O conteúdo original é armazenado sem regravar o PDF; a aplicação não verifica a autenticidade das assinaturas. A validação estrutural usa [PdfReader do pypdf](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html). Os arquivos ficam em `data/media/signed-documents/` (demonstração: `data/demo-media/signed-documents/`). Arquivos substituídos permanecem no disco para preservar backups anteriores; não aparecem como histórico na interface.

O backup completo inclui os PDFs atualmente vinculados às consignações, mesmo quando não há fotos de produtos. Restaure o banco e toda a pasta de mídia do ZIP juntos. Para atualizar outra instalação, execute `INSTALAR.bat`, que instala `pypdf` e aplica a migração dos campos do documento sem apagar registros.

### Etiquetas e leitor óptico

Cada produto recebe automaticamente um EAN-13 interno único, com dígito verificador. A atualização também preenche os produtos existentes, preservando SKU, preços, estoque e histórico. O EAN permanece estável ao editar o cadastro e ajustar o estoque. O prefixo 20 é usado para circulação restrita: estes números não são GTINs comerciais registrados nem devem ser enviados como tais a marketplaces. [Referência GS1](https://www.gs1.org/docs/barcodes/SummaryOfGS1MOPrefixes20-29.pdf).

Em **Produtos**, abra o ícone de etiqueta na listagem ou **Visualizar / imprimir etiqueta** na edição do produto. A etiqueta contém marca, nome, SKU, preço, barras e EAN legível. O formato inicial é **60 × 65 mm**; use papel compatível, escala 100%, sem cabeçalhos ou rodapés. Confira uma impressão com seu leitor antes de produzir várias etiquetas.

Na criação ou edição de uma consignação AGUARDANDO ENVIO, marque **Ativar leitor** na seção de peças. Clique no campo de leitura e escaneie a etiqueta. São compatíveis leitores USB/Bluetooth que funcionam como teclado, com sufixo **Enter** ou **Tab**; também é possível digitar o código e clicar em **Adicionar leitura**. A aplicação não usa câmera e não exige internet.

Cada leitura adiciona uma unidade pelo EAN ou pelo SKU exato (inclusive zeros à esquerda). Uma peça já selecionada tem sua quantidade incrementada sem perder o preço negociado. Códigos desconhecidos, inativos ou ambíguos e quantidades acima do estoque exibido são recusados. O estoque é novamente validado no servidor ao confirmar o envio. A leitura apenas preenche o formulário: clique em **Salvar consignação** para persistir as peças.

Desmarque **Ativar leitor** para usar somente a seleção manual. A preferência é lembrada neste navegador; itens já incluídos permanecem na lista. A leitura é capturada apenas no campo específico para não interferir nas observações e demais cadastros. Ao editar outro campo, clique novamente no campo de leitura antes de escanear.

Para atualizar outra instalação, execute `INSTALAR.bat`: a nova dependência `python-barcode` e a migração `0002_product_ean13` são necessárias. Faça backup antes da atualização.

O mapa das **12 tabelas de negócio** e suas relações está em [docs/database.md](docs/database.md). As migrações Django em `core/migrations` são a fonte de criação e atualização do esquema; o SQL de referência está em `docs/schema.sql`. Também existem tabelas internas do Django para sessões, permissões e controle das migrações.

O SQLite trabalha com transações `IMMEDIATE` e espera de até 20 segundos para escritas concorrentes. Não coloque o arquivo do banco em uma pasta de rede nem use este protótipo como servidor para vários computadores. PostgreSQL permanece uma opção de configuração para experimentar depois.

Ao atualizar a aplicação, faça backup, instale as dependências e execute `scripts\setup.py`. O instalador aplica apenas migrações pendentes e preserva os registros existentes. Não apague migrações ou tabelas manualmente.

### Devolução por leitura

Abra uma consignação **EM TRÂNSITO** com peças pendentes e ative o **Leitor de devoluções**. Clique no campo de leitura e leia o EAN ou SKU das peças recebidas, terminando cada leitura com Enter ou Tab. Cada bip soma uma unidade à conferência. O SKU registrado no envio também é reconhecido, mesmo que o cadastro tenha sido alterado; produtos inativos podem ser devolvidos.

Confira as quantidades, ajuste ou remova peças se necessário e clique em **Confirmar devolução**. Somente essa confirmação registra a devolução e repõe o estoque. Códigos de outra consignação e quantidades acima do saldo pendente são recusados. O lote inteiro é validado antes de gravar; uma tentativa repetida ou um acerto alterado em outra página exige recarregar e conferir o saldo.

É possível desligar o leitor e continuar usando o acerto manual de cada produto. A preferência do leitor de devoluções é independente da leitura no envio. A conferência ainda não confirmada não é salva ao fechar a página. Se a conexão falhar na confirmação, recarregue para conferir o que foi registrado antes de tentar novamente. A validação automatizada simula o teclado; confira também o leitor físico e as etiquetas impressas.

## Backup e restauração

Use **Backup** na interface ou execute:

```powershell
.venv\Scripts\python.exe scripts\backup.py
```

O arquivo é gravado em `backups\melo_joias_DATA_HORA_ID.sqlite3`. A demonstração usa o prefixo `demo_`. O backup utiliza a API de cópia consistente do SQLite e verifica a integridade do arquivo gerado, permitindo sua execução com a aplicação aberta.

O backup contém todas as tabelas e registros. Configuração `.env` e chave `data/.secret_key` ficam fora do banco; mantenha uma cópia protegida desses arquivos junto com o projeto. Copie backups importantes para outra unidade ou mídia.

**Quando há fotos ou PDFs assinados**, o arquivo entregue passa a ser um **ZIP com o banco e os anexos**. Na instalação padrão ele contém `data/melo.sqlite3` e os anexos em `data/media/`; na demonstração, `data/demo.sqlite3` e os anexos em `data/demo-media/`. A cópia isolada do banco também fica na pasta de backups, mas não contém fotos nem PDFs. Se um anexo referenciado estiver ausente, o sistema informa a falha em vez de entregar um backup completo sem o arquivo.

Para restaurar seus cadastros:

1. Encerre a aplicação com `Ctrl+C` e feche outras instâncias do sistema.
2. Guarde uma cópia do arquivo atual `data\melo.sqlite3` em outro local.
3. Copie o backup escolhido para `data\melo.sqlite3`, substituindo esse arquivo somente após guardar a cópia anterior. Use `data\demo.sqlite3` apenas para restaurar uma demonstração.
4. Abra `INICIAR.bat` e confira os cadastros e saldos. Se o backup for de versão anterior do aplicativo, execute primeiro `scripts\setup.py`.

Os backups incluem dados pessoais dos cadastros. Mantenha-os em local protegido e teste a restauração antes de depender do sistema para dados definitivos.

Para restaurar um **ZIP com fotos ou PDFs**, feche o sistema, guarde uma cópia do banco e da pasta de imagens atuais e extraia o ZIP em uma pasta separada. Copie o banco restaurado para o caminho correspondente e copie também a pasta `media` (ou `demo-media`) para `data`, preservando seus nomes internos. Se utilizar `MELO_DATA_DIR`, use a pasta configurada em vez de `data`. Abra o sistema e confira os cadastros e as imagens. Um backup antigo que contém somente `.sqlite3` não recupera fotos nem PDFs.

No PostgreSQL, um ZIP com fotos contém `data/database.dump` e a pasta de imagens; restaure o `.dump` com `pg_restore` conforme a seção abaixo e copie a pasta de imagens separadamente.

## PostgreSQL opcional

SQLite é a configuração entregue. Para experimentar PostgreSQL no futuro, use a opção abaixo. **A mudança de configuração não transfere os dados automaticamente**; ela aponta para outro banco. Preserve o SQLite e seu backup se quiser voltar.

1. Prepare um banco PostgreSQL **14 ou superior**, dedicado e vazio, com seu usuário como proprietário. O aplicativo não cria nem altera outros bancos do servidor.
2. Instale o adaptador: `.venv\Scripts\python.exe -m pip install -r requirements-postgresql.txt`.
3. No `.env`, defina `DB_ENGINE=postgresql` e preencha `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD`. Há campos comentados em `.env.example`.
4. Execute `scripts\setup.py` para criar as tabelas no banco selecionado e abra `INICIAR.bat`.

Nesta máquina foi identificado PostgreSQL 17 na porta **5433**. A porta 5432 corresponde a outra instalação; confirme a versão antes de conectar. A integração opcional precisa ser validada com suas credenciais antes de usar dados reais.

No modo PostgreSQL, o backup usa `pg_dump` da mesma versão principal do servidor e gera `.dump`. Configure `MELO_PG_BIN` se a pasta `bin` não estiver no local padrão. A senha é passada somente pelo ambiente do processo, sem aparecer na linha de comando. Para restaurar, use `pg_restore --no-owner --no-privileges --exit-on-error` em **outro banco vazio**, confira o resultado e só então altere `DB_NAME`. Não restaure sobre um banco em uso.

## Verificação técnica

A preparação da página de callback Bagy está documentada em [docs/cloudflare-bagy.md](docs/cloudflare-bagy.md), com o código inicial em `scripts/cloudflare/worker.mjs`. Esta etapa cria uma página de apresentação pendente de configuração; a autorização e a sincronização com a Bagy ainda não estão implementadas.

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
```

Os testes SQLite usam um banco isolado e não alteram `data\melo.sqlite3` nem `data\demo.sqlite3`. Também é possível especificar `--settings=config.test_settings` para forçar SQLite em memória. Se configurar PostgreSQL, os testes padrão precisam de um usuário com permissão para criar seu banco temporário de testes.

O teste opcional `node scripts/test_scanner_browser.cjs` usa Playwright instalado no ambiente de desenvolvimento e cria um banco temporário separado. Ele verifica leitura EAN/SKU, repetição, preço negociado, limites de estoque, erros, modo manual, remoção, salvamento e layout. No Windows com Edge, use `PLAYWRIGHT_CHANNEL=msedge` como variável de ambiente. Playwright não é necessário para utilizar o sistema. O teste simula o teclado do leitor; a validação física depende do leitor e da impressão.

## Protótipo entregue

Esta entrega contém o código-fonte instalável, esquema e migrações do banco, cadastros, envio/acerto de consignações, controle de estoque, pagamentos, demonstração isolada e backup local. Os atalhos `.bat` usam Python para executar a aplicação; não são um executável independente.

O pacote de distribuição pode ser gerado com `.venv\Scripts\python.exe scripts\package.py`. Ele inclui apenas fontes, documentação e recursos da interface; exclui seu ambiente Python, bancos, backups, credenciais e arquivos temporários. Para instalar em outro computador, extraia o ZIP e execute `INSTALAR.bat`. A cópia de dados deve ser feita separadamente pelo procedimento de backup e restauração.
