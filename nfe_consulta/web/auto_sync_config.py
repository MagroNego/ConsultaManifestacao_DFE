"""Configuração persistente da agenda, sem alterar a janela externa da SEFAZ."""
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import tempfile

DEFAULT_TIMES = ('22:00', '23:00', '00:00', '01:00', '02:00', '03:00')


def validate_schedule(enabled, times, weekdays):
    if type(enabled) is not bool:
        raise ValueError('Estado do agendamento inválido.')
    if not isinstance(times, (list, tuple)) or not 1 <= len(times) <= 6:
        raise ValueError('Informe de um a seis horários.')
    minutes = []
    for value in times:
        if not isinstance(value, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
            raise ValueError('Use horários no formato HH:MM, separados por vírgula.')
        hour, minute = map(int, value.split(':'))
        if not (hour >= 22 or hour < 4):
            raise ValueError('Os disparos devem ocorrer entre 22:00 e antes de 04:00, Brasília.')
        minutes.append(hour*60 + minute + (1440 if hour < 4 else 0))
    minutes.sort()
    if any(b-a < 60 for a, b in zip(minutes, minutes[1:])):
        raise ValueError('Mantenha pelo menos 60 minutos entre os horários, sem duplicatas.')
    if not isinstance(weekdays, (tuple, list)) or not weekdays or any(type(day) is not int or day not in range(7) for day in weekdays):
        raise ValueError('Selecione pelo menos um dia válido da semana.')
    ordered = tuple(f'{(minute//60)%24:02d}:{minute%60:02d}' for minute in minutes)
    return dict(auto_sync_enabled=enabled, auto_sync_times=ordered, auto_sync_weekdays=tuple(sorted(set(weekdays))))


def config_path(settings):
    return settings.auto_sync_config_path or settings.database_path.parent / 'auto-sync.json'


def load_schedule(settings):
    path = config_path(settings)
    if not path.is_file():
        return settings
    try:
        data = json.loads(path.read_text('utf-8'))
        values = validate_schedule(data['enabled'], data['times'], data['weekdays'])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('Configuração de agendamento inválida em auto-sync.json.') from exc
    return replace(settings, **values)


def save_schedule(settings, *, enabled, times, weekdays):
    values = validate_schedule(enabled, times, weekdays)
    updated = replace(settings, **values)
    path = Path(config_path(settings))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.auto-sync-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(dict(enabled=enabled, times=values['auto_sync_times'], weekdays=values['auto_sync_weekdays']), stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return updated
