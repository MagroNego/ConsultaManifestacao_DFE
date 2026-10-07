"""Eventos de vínculo CT-e/NF-e recebidos pela distribuição, sem chamadas extras."""
from __future__ import annotations

from dataclasses import dataclass

from nfe_consulta.modelos import EventoCTe, NfeErroResposta

CODES = {'610600': 'CT-e Autorizado', '610601': 'CT-e Cancelado'}


def text(root, name):
    if root is None:
        return ''
    return next(((el.text or '').strip() for el in root.iter() if el.tag.rsplit('}', 1)[-1] == name), '')


def parse_event(root, nsu='', schema=''):
    if root.tag.rsplit('}', 1)[-1] not in {'resEvento', 'procEventoNFe'}:
        return None
    request = next((el for el in root.iter() if el.tag.rsplit('}', 1)[-1] == 'evento'), root)
    response = next((el for el in root.iter() if el.tag.rsplit('}', 1)[-1] == 'retEvento'), None)
    code = text(request, 'tpEvento')
    if code not in CODES:
        return None
    if response is not None and text(response, 'cStat') not in {'135', '136', '155'}:
        return None
    nfe = text(request, 'chNFe')
    key = text(request, 'chCTe')
    if len(nfe) != 44 or not nfe.isdigit() or nfe[20:22] != '55':
        raise NfeErroResposta('Evento de CT-e sem chave NF-e válida')
    if key and (len(key) != 44 or not key.isdigit() or key[20:22] != '57'):
        raise NfeErroResposta('Evento com chave CT-e inválida')
    carrier = next((el for el in request.iter() if el.tag.rsplit('}', 1)[-1] == 'emit'), None)
    # nProt dentro de CTe é do conhecimento; o protocolo do evento vem no retorno.
    protocol = text(response, 'nProt') if response is not None else (text(root, 'nProt') if root.tag.rsplit('}', 1)[-1] == 'resEvento' else '')
    return EventoCTe(nfe, key, code, text(request, 'dhEvento') or text(root, 'dhRecbto'),
        protocol, text(request, 'nSeqEvento'), text(carrier, 'xNome'), text(carrier, 'CNPJ'), nsu, schema)


SCHEMA = '''CREATE TABLE IF NOT EXISTS eventos_cte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT NOT NULL, chave_nfe TEXT NOT NULL, chave_cte TEXT NOT NULL,
    codigo TEXT NOT NULL, data_evento TEXT NOT NULL, protocolo TEXT NOT NULL,
    sequencia TEXT NOT NULL, transportadora TEXT NOT NULL, cnpj_transportadora TEXT NOT NULL,
    nsu TEXT NOT NULL, schema_xml TEXT NOT NULL,
    UNIQUE(cnpj, chave_nfe, codigo, protocolo, nsu, sequencia)
);
CREATE INDEX IF NOT EXISTS idx_eventos_cte_nfe ON eventos_cte(cnpj, chave_nfe);'''


def save_events(connection, cnpj, events):
    for event in events:
        connection.execute('''INSERT INTO eventos_cte
            (cnpj,chave_nfe,chave_cte,codigo,data_evento,protocolo,sequencia,transportadora,cnpj_transportadora,nsu,schema_xml)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(cnpj,chave_nfe,codigo,protocolo,nsu,sequencia) DO UPDATE SET
            chave_cte=CASE WHEN excluded.chave_cte!='' THEN excluded.chave_cte ELSE eventos_cte.chave_cte END,
            transportadora=CASE WHEN excluded.transportadora!='' THEN excluded.transportadora ELSE eventos_cte.transportadora END,
            cnpj_transportadora=CASE WHEN excluded.cnpj_transportadora!='' THEN excluded.cnpj_transportadora ELSE eventos_cte.cnpj_transportadora END''',
            (cnpj,event.chave_nfe,event.chave_cte,event.codigo,event.data,event.protocolo,event.sequencia,
             event.transportadora,event.cnpj_transportadora,event.nsu,event.schema))


@dataclass(frozen=True)
class VinculoCTe:
    chave: str
    status: str
    transportadora: str = ''
    cnpj_transportadora: str = ''
    data: str = ''

    @property
    def numero(self):
        return str(int(self.chave[25:34])) if self.chave else ''

    @property
    def label(self):
        return f'CT-e {self.numero} · {self.status}' if self.chave else f'{self.status} · chave não informada'


def linked_ctes(connection, cnpj, keys):
    keys = list(set(keys))
    result = {key: [] for key in keys}
    if not keys or not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='eventos_cte'").fetchone():
        return result
    # Bancos antigos permanecem consultáveis. Consulta em lotes evita limite de variáveis SQLite.
    for offset in range(0, len(keys), 400):
        batch = keys[offset:offset + 400]
        rows = connection.execute(f'''SELECT chave_nfe,chave_cte,codigo,transportadora,cnpj_transportadora,data_evento,protocolo,sequencia
            FROM eventos_cte WHERE cnpj=? AND chave_nfe IN ({','.join('?' for _ in batch)}) ORDER BY id''', [cnpj, *batch]).fetchall()
        groups = {}
        resolved_protocols = {(r[0], r[2], r[6]): r[1] for r in rows if r[1] and r[6]}
        resolved_sequences = {(r[0], r[2], r[7]): r[1] for r in rows if r[1] and r[7]}
        for nfe, key, code, carrier, carrier_id, date, protocol, sequence in rows:
            # Resumo e evento completo de mesmo tipo/sequência representam a mesma ocorrência.
            resolved = key or resolved_protocols.get((nfe, code, protocol), '') or resolved_sequences.get((nfe, code, sequence), '')
            identifier = (nfe, key or resolved or f'{code}:{sequence or protocol or date}')
            previous = groups.get(identifier)
            cancelled = code == '610601' or (previous and previous.status == 'Cancelado')
            groups[identifier] = VinculoCTe(key or resolved,
                'Cancelado' if cancelled else ('Autorizado' if key or resolved else 'Vínculo identificado'),
                carrier or (previous.transportadora if previous else ''),
                carrier_id or (previous.cnpj_transportadora if previous else ''),
                date if code == '610601' or not previous else previous.data)
        for (nfe, _), item in groups.items():
            result[nfe].append(item)
    return {key: tuple(items) for key, items in result.items()}


def export_label(items):
    return ' | '.join(f'{item.label}' + (f' · {item.chave}' if item.chave else '') for item in items) or 'Não localizado'
