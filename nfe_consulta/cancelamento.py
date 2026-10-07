"""Situação de cancelamento compartilhada pelo leitor e pelas consultas."""
from __future__ import annotations

import re
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS informacoes_nfe (
    cnpj TEXT NOT NULL, chave TEXT NOT NULL, emitente TEXT NOT NULL DEFAULT '',
    cancelada INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(cnpj,chave)
);
CREATE TABLE IF NOT EXISTS cancelamentos_manuais (
    cnpj TEXT NOT NULL, chave TEXT NOT NULL, usuario TEXT NOT NULL,
    motivo TEXT NOT NULL, alterado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(cnpj,chave)
);
CREATE TABLE IF NOT EXISTS historico_cancelamentos_manuais (
    id INTEGER PRIMARY KEY, cnpj TEXT NOT NULL, chave TEXT NOT NULL,
    usuario TEXT NOT NULL, motivo TEXT NOT NULL, acao TEXT NOT NULL,
    alterado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS xml_cancelamentos (
    cnpj TEXT NOT NULL, chave TEXT NOT NULL, protocolo TEXT NOT NULL,
    data_evento TEXT NOT NULL, codigo_status TEXT NOT NULL, xml BLOB NOT NULL,
    importado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(cnpj,chave,protocolo)
);
"""


def child(parent, tag):
    return next((el for el in parent if el.tag.rsplit('}', 1)[-1] == tag), None) if parent is not None else None


def text(parent, tag):
    el = child(parent, tag)
    return (el.text or '').strip() if el is not None else ''


def read_cancellation(root, cnpj):
    """Aceita retorno homologado; uma solicitação ou rejeição não cancela a nota."""
    kind = root.tag.rsplit('}', 1)[-1]
    if kind in {'nfeProc', 'retConsSitNFe'}:
        inf = child(child(root, 'NFe'), 'infNFe')
        expected_key = inf.attrib.get('Id', '').removeprefix('NFe') if kind == 'nfeProc' and inf is not None else text(root, 'chNFe')
        for candidate in root:
            if candidate.tag.rsplit('}', 1)[-1] == 'procEventoNFe' and text(child(child(candidate, 'evento'), 'infEvento'), 'tpEvento') == '110111':
                try:
                    item = read_cancellation(candidate, cnpj)
                except ValueError:
                    continue
                if item['chave'] != expected_key:
                    raise ValueError('Nota e evento de cancelamento divergentes.')
                return item
    if kind == 'procEventoNFe':
        event = child(child(root, 'evento'), 'infEvento')
        response = child(child(root, 'retEvento'), 'infEvento')
        if event is None or response is None:
            raise ValueError('Cancelamento sem retorno da SEFAZ.')
        if text(event, 'tpEvento') != '110111' or text(response, 'tpEvento') != '110111':
            raise ValueError('Evento não é cancelamento de NF-e.')
        if text(response, 'cStat') not in {'135', '155'}:
            raise ValueError('Cancelamento não homologado.')
        key = text(response, 'chNFe')
        if text(event, 'chNFe') != key or text(event, 'CNPJ') != cnpj:
            raise ValueError('Evento e retorno divergentes.')
        for field in ('nSeqEvento', 'tpAmb'):
            if not text(event, field) or text(event, field) != text(response, field):
                raise ValueError('Evento e retorno divergentes.')
        if text(event, 'tpAmb') not in {'1', '2'} or not re.fullmatch(r'[1-9]\d?', text(event, 'nSeqEvento')):
            raise ValueError('Ambiente ou sequência inválidos.')
        date = text(response, 'dhRegEvento')
    elif kind == 'procCancNFe':
        response = child(child(root, 'retCancNFe'), 'infCanc')
        if text(response, 'cStat') not in {'101', '151'}:
            raise ValueError('Cancelamento não homologado.')
        key = text(response, 'chNFe')
        request = child(child(root, 'cancNFe'), 'infCanc')
        if request is not None and text(request, 'chNFe') != key:
            raise ValueError('Cancelamento e retorno divergentes.')
        date = text(response, 'dhRecbto')
    elif kind in {'nfeProc', 'retConsSitNFe'}:
        response = child(child(root, 'protNFe'), 'infProt')
        status = text(root, 'cStat') if kind == 'retConsSitNFe' else text(response, 'cStat')
        if status not in {'101', '151'}:
            return None
        if kind == 'retConsSitNFe' and text(response, 'cStat') not in {'101', '151'}:
            raise ValueError('Consulta sem protocolo de cancelamento.')
        key = text(response, 'chNFe')
        if kind == 'nfeProc':
            inf = child(child(root, 'NFe'), 'infNFe')
            if inf is None or inf.attrib.get('Id', '').removeprefix('NFe') != key:
                raise ValueError('Nota e protocolo divergentes.')
        elif text(root, 'chNFe') != key:
            raise ValueError('Consulta e protocolo divergentes.')
        date = text(response, 'dhRecbto')
    else:
        return None
    if not re.fullmatch(r'\d{44}', key) or key[20:22] != '55' or key[6:20] != cnpj:
        raise ValueError('Cancelamento de outra empresa ou modelo.')
    protocol = text(response, 'nProt')
    if text(response, 'tpAmb') != '1':
        raise ValueError('O app utiliza documentos do ambiente de produção.')
    if not re.fullmatch(r'\d{15}', protocol):
        raise ValueError('Protocolo de cancelamento inválido.')
    instant = datetime.fromisoformat(date.replace('Z', '+00:00'))
    if instant.tzinfo is None:
        raise ValueError('Data de cancelamento sem fuso horário.')
    return dict(chave=key, protocolo=protocol, data_evento=date, codigo_status=text(response, 'cStat'))


def save_cancellation(conn, cnpj, item, data):
    cursor = conn.execute('INSERT OR IGNORE INTO xml_cancelamentos(cnpj,chave,protocolo,data_evento,codigo_status,xml) VALUES (?,?,?,?,?,?)',
        (cnpj, item['chave'], item['protocolo'], item['data_evento'], item['codigo_status'], data))
    conn.execute('''INSERT INTO informacoes_nfe(cnpj,chave,cancelada) VALUES (?,?,1)
        ON CONFLICT(cnpj,chave) DO UPDATE SET cancelada=1''', (cnpj, item['chave']))
    return cursor.rowcount > 0


def _has_table(conn, name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def cancellation_condition(conn, alias):
    if alias not in {'d', 'manifestacoes'}:
        raise ValueError('Alias inválido.')
    parts = []
    for table in ('informacoes_nfe', 'cancelamentos_manuais'):
        if _has_table(conn, table):
            status = ' AND i.cancelada=1' if table == 'informacoes_nfe' else ''
            parts.append(f'EXISTS (SELECT 1 FROM {table} i WHERE i.cnpj={alias}.cnpj AND i.chave={alias}.chave{status})')
    return '(' + ' OR '.join(parts) + ')' if parts else '0=1'


def cancelled_keys(conn, cnpj, keys):
    keys = list(set(keys))
    found = set()
    for table in ('informacoes_nfe', 'cancelamentos_manuais'):
        if not _has_table(conn, table):
            continue
        for index in range(0, len(keys), 500):
            batch = keys[index:index + 500]
            marks = ','.join('?' for _ in batch)
            scope = 'cnpj=? AND ' if cnpj else ''
            params = (cnpj, *batch) if cnpj else tuple(batch)
            status = 'cancelada=1 AND ' if table == 'informacoes_nfe' else ''
            found.update(row[0] for row in conn.execute(f'SELECT chave FROM {table} WHERE {scope}{status}chave IN ({marks})', params))
    return found


def change_manual_status(database_path, cnpj, identifiers, *, user, reason, action='cancelar', password=None):
    """Correção interna auditada; não cria nem remove um evento da SEFAZ."""
    from nfe_consulta.seguranca_banco import abrir_banco
    from pathlib import Path
    if action not in {'cancelar', 'remover'}:
        raise ValueError('Ação inválida.')
    if len(identifiers) > 16384 or len(reason) > 500:
        raise ValueError('Limite de texto excedido.')
    tokens = list(dict.fromkeys(re.split(r'[\s,;]+', identifiers.strip())))
    if not tokens or not tokens[0] or len(tokens) > 100:
        raise ValueError('Informe entre 1 e 100 notas.')
    if any(not re.fullmatch(r'[0-9]{1,9}|[0-9]{44}', token) for token in tokens):
        raise ValueError('Informe somente números de nota ou chaves de 44 dígitos.')
    reason = reason.strip()
    if not reason:
        raise ValueError('Informe o motivo da alteração.')
    if not Path(database_path).is_file():
        raise ValueError('Banco local não encontrado.')
    conn = abrir_banco(database_path, password)
    try:
        # Resolver antes de criar tabelas evita alterar bancos em pedidos inválidos.
        tables = [t for t in ('xml_documentos', 'informacoes_nfe', 'manifestacoes') if _has_table(conn, t)]
        keys = set()
        for token in tokens:
            matches = set()
            for table in tables:
                clause = 'chave=?' if len(token) == 44 else 'CAST(SUBSTR(chave,26,9) AS INTEGER)=?'
                value = token if len(token) == 44 else int(token)
                matches.update(row[0] for row in conn.execute(f'SELECT DISTINCT chave FROM {table} WHERE cnpj=? AND {clause}', (cnpj, value)))
            matches = {key for key in matches if re.fullmatch(r'[0-9]{44}', key) and key[20:22] == '55'}
            if not matches:
                raise ValueError(f'Nota {token} não encontrada no banco desta empresa.')
            if len(matches) > 1:
                raise ValueError(f'Número {token} corresponde a mais de uma nota. Informe a chave de acesso.')
            keys.update(matches)
        # Schema migration is separate; all status changes share one transaction.
        conn.executescript(SCHEMA)
        with conn:
            for key in sorted(keys):
                if action == 'cancelar':
                    conn.execute("INSERT INTO cancelamentos_manuais(cnpj,chave,usuario,motivo) VALUES (?,?,?,?) ON CONFLICT(cnpj,chave) DO UPDATE SET usuario=excluded.usuario,motivo=excluded.motivo,alterado_em=CURRENT_TIMESTAMP", (cnpj, key, user, reason))
                else:
                    conn.execute('DELETE FROM cancelamentos_manuais WHERE cnpj=? AND chave=?', (cnpj, key))
                conn.execute('INSERT INTO historico_cancelamentos_manuais(cnpj,chave,usuario,motivo,acao) VALUES (?,?,?,?,?)', (cnpj, key, user, reason, action))
        return len(keys)
    finally:
        conn.close()


def status_label(cancelled):
    """Rótulo binário da interface, conforme a situação conhecida no banco local."""
    return 'Cancelada' if cancelled else 'Autorizada'


def lookup_cancelled(conn, cnpj, *, key=None, number=None, series=None):
    if not key and number is None:
        return ()
    sources = []
    for table in ('informacoes_nfe', 'cancelamentos_manuais'):
        if _has_table(conn, table):
            sources.append(f"SELECT cnpj,chave FROM {table}" + (' WHERE cancelada=1' if table == 'informacoes_nfe' else ''))
    if not sources:
        return ()
    clauses = ['cnpj=?']
    params = [cnpj]
    if key:
        clauses.append('chave=?')
        params.append(key)
    if number is not None:
        clauses.append('CAST(SUBSTR(chave,26,9) AS INTEGER)=?')
        params.append(number)
    if series is not None:
        clauses.append('CAST(SUBSTR(chave,23,3) AS INTEGER)=?')
        params.append(series)
    return tuple(dict(chave=row[0], numero=int(row[0][25:34]), serie=str(int(row[0][22:25])))
                 for row in conn.execute('SELECT DISTINCT chave FROM (' + ' UNION '.join(sources) + ') WHERE ' + ' AND '.join(clauses) + ' ORDER BY chave LIMIT 20', params))
