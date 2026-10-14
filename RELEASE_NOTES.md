# AtlasDFE v2.5.0

- Nome AtlasDFE com logos próprios para os temas claro e escuro.
- Novos XMLs são processados para extrair dados, sem cópia permanente; os relatórios, itens, impostos, manifestações, cancelamentos e vínculos CT-e continuam disponíveis.
- Download de XML removido; Excel, CSV e registros de lote continuam disponíveis. Obtenha o XML original no Synchro.
- Respostas da SEFAZ ficam temporariamente preservadas até o processamento confirmar; falhas de gravação mantêm a resposta para nova tentativa.
- XMLs históricos não são apagados automaticamente, nem o banco é compactado nesta atualização.
- Janela noturna das 22h às 04h de Brasília, disparos às 22h e 01h e recuperação consNSU pausada para o teste, com pendências preservadas.
- Logs recolhidos, diagnóstico de erros e preservação do último NSU gravado com sucesso após 656.

## Atualização

Pare o aplicativo, faça backup do banco e preserve dados, secrets, logs e certificado. Atualize o código, execute INSTALAR.cmd se estiver usando o pacote e reinicie com INICIAR_WEB.cmd. As contas, senhas e caminhos configurados continuam válidos.

O teste noturno depende da confirmação da janela das 08h às 18h no Qive. Separar horários não garante aceitação de cursores independentes pela SEFAZ.
