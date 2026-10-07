"""Situação de cancelamento compartilhada pelo leitor e pelas consultas."""
from __future__ import annotations

import re
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS informacoes_nfe (
    cnpj TEXT NOT NULL, chave TEXT NOT NULL, emitente TEXT NOT NULL DEFAULT '',
    cancelada INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(cnpj,chave)
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


def cancelled_keys(conn, cnpj, keys):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='informacoes_nfe'").fetchone():
        return set()
    keys = list(set(keys))
    found = set()
    for index in range(0, len(keys), 500):
        batch = keys[index:index + 500]
        marks = ','.join('?' for _ in batch)
        scope = 'cnpj=? AND ' if cnpj else ''
        params = (cnpj, *batch) if cnpj else tuple(batch)
        found.update(row[0] for row in conn.execute(f'SELECT chave FROM informacoes_nfe WHERE {scope}cancelada=1 AND chave IN ({marks})', params))
    return found


def status_label(cancelled):
    """Rótulo binário da interface, conforme a situação conhecida no banco local."""
    return 'Cancelada' if cancelled else 'Autorizada'


def lookup_cancelled(conn, cnpj, *, key=None, number=None, series=None):
    if not key and number is None:
        return ()
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='informacoes_nfe'").fetchone():
        return ()
    clauses = ['cnpj=?', 'cancelada=1']
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
                 for row in conn.execute('SELECT chave FROM informacoes_nfe WHERE ' + ' AND '.join(clauses) + ' ORDER BY chave LIMIT 20', params))
