# Dossiê técnico e de segurança — versão 0.9.4

## Escopo e fluxo

Aplicativo Python de consulta **somente leitura** de eventos de manifestação das NF-e emitidas. `nfe-consulta --gui` e `ABRIR_CONSULTA.cmd` abrem uma interface Tkinter local. A interface executa o CLI em processo separado com argumentos separados, sem `shell=True`; permite escolher caminhos e exibe prévia do XLSX. `ABRIR_CONSULTA_TEXTO.cmd` mantém o assistente em console. A operação remota usa `distNSU` no serviço `NFeDistribuicaoDFe` do Ambiente Nacional; a operação local cruza chaves de TXT com SQLite e gera XLSX ou CSV. Nenhum evento é transmitido em nome do destinatário.

A opção `3` (`--status`) abre o SQLite em modo de leitura e mostra a hora da última resposta armazenada para o CNPJ. Não atualiza o cursor, cria banco ou acessa rede. A igualdade `ultNSU = maxNSU` é histórica e não garante estado atual da SEFAZ.

## Acessos e dados

| Recurso | Uso |
| --- | --- |
| `https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx` | HTTPS de saída, somente quando escolhida atualização. |
| `Cert:\CurrentUser\My` | Lê metadados e usa a chave privada pelo Windows para autenticação de cliente. Não exporta PFX, chave privada ou senha. |
| `entrada/CHAVES.txt` ou TXT escolhido | Chaves que serão confrontadas com eventos. |
| `dados/nfe_manifestacoes_seguro.db` ou banco escolhido | SQLCipher com NSU e eventos; bancos legados `.db` sem criptografia também podem ser abertos para migração. |
| `saidas/Consulta_Manifestacao_YAB.xlsx` ou caminho escolhido | Resultado, **sem criptografia própria**. |
| PyPI / repositório interno | Acesso apenas no momento da instalação, para `openpyxl`, `defusedxml` e `sqlcipher3`, conforme política da TI. |

Não há porta de escuta, telemetria, credencial fixa ou execução elevada prevista. O endpoint de produção é constante no código. A validação do certificado do servidor não é desativada. O certificado do cliente é selecionado pelo CNPJ; uma seleção manual com CNPJ incompatível é recusada. As chamadas têm timeout de 60 segundos.

## Controles implementados

- `defusedxml` para XML recebido; resposta SOAP limitada a 32 MiB, `docZip` compactado a 2 MiB e XML expandido a 8 MiB por documento. TXT limitado a 2 MiB e 10.000 chaves. Excesso ou XML inválido interrompe a sincronização sem avançar o NSU do lote.
- Dados de consultas e eventos gravados em SQLite com parâmetros; lote e cursor são persistidos na mesma transação.
- `656` bloqueia novas consultas por uma hora no banco local; `137`/fim da fila evita repetição imediata. O cursor retoma após interrupção.
- Os textos externos na planilha são forçados a células de texto, para impedir execução de fórmula. O CSV recebe apóstrofo inicial para valores com prefixo de fórmula. Chave e protocolo são texto no XLSX.
- Corpo HTML de erro HTTP não é exibido; mensagens de erro do processo são truncadas.
- Em futuras rejeições `656`, `xMotivo` do XML validado é mostrado no terminal e registrado no SQLite junto da pausa. Texto remoto é limitado a 400 caracteres e caracteres de controle são removidos; o XML inteiro não é salvo. O cursor NSU não avança na rejeição.
- `INSTALAR.cmd` e `ABRIR_CONSULTA.cmd` são texto inspecionável. Não desabilitam antivírus, política de execução nem verificação de TLS.
- A GUI inicia pelo modo local e não realiza consulta à SEFAZ ao abrir. Exige ação e confirmação específicas para sincronização remota. Mostra o status local em modo de leitura; não cria um banco por engano no modo local e pede confirmação quando o modo remoto criará um banco novo. Tkinter não adiciona servidor web ou dependência externa.

## Limites a avaliar

- TXT, planilhas, bancos legados e cópias de backup podem conter dados fiscais e **não são criptografados automaticamente**. O banco SQLCipher exige senha.
- A instalação editável lê o código da pasta extraída; o usuário deve protegê-la contra alteração por terceiros.
- O programa usa o repositório de certificados da conta logada e depende da política de acesso à chave privada e da cadeia TLS do Windows/proxy corporativo.
- Outros sistemas podem consultar o mesmo CNPJ e causar limites compartilhados ou rejeição `656`. Coordenar com os sistemas fiscais existentes.
- O resultado “sem evento localizado” depende do período e da cobertura da distribuição. O software não atesta ausência definitiva de manifestação e não verifica autorização/cancelamento da NF-e.
- O código e os testes locais não substituem revisão, teste no Windows corporativo e aprovação da TI. A versão 0.9.4 não inclui testes de penetração, assinatura digital do instalador ou auditoria independente. A interface visual não foi validada em um desktop Windows corporativo.

## Verificação sugerida

1. Inspecionar o código-fonte, o histórico de commits e a lista de arquivos rastreados; comparar releases distribuídos com o manifesto incluído nos respectivos ZIPs.
2. Validar dependências `openpyxl`, `defusedxml`, `sqlcipher3`, Python e origem dos pacotes no repositório aprovado.
3. Rodar `py -m pip install -e ".[dev]"` e `py -m pytest -q` em ambiente isolado.
4. Testar a opção `2` com banco de teste antes de liberar acesso ao certificado e ao endpoint.
5. Confirmar ACLs do banco e do resultado, acesso HTTPS/proxy e coexistência com sistemas que usam NSU do mesmo CNPJ.

Referências: [MOC NF-e 7.0](https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-visao-geral.pdf), [documentação de segurança de XML do Python](https://docs.python.org/3/library/xml.html), [placeholders do SQLite](https://docs.python.org/3/library/sqlite3.html) e [HttpClientHandler da Microsoft](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.httpclienthandler).

## Banco criptografado

A versão 0.9.4 oferece migração explícita para SQLCipher 4, conferindo contagens e integridade e preservando o original. A senha não é passada pela linha de comando. O app continua aceitando bancos antigos sem criptografia para permitir migração; TXT, XLSX, CSV, banco original e backups não são cifrados automaticamente. Validar wheel SQLCipher para o Python corporativo e configurar backup/gestão de senhas antes de adotar.
