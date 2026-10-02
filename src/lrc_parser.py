"""
Parser robusto de formato LRC y cálculo determinista de la línea activa.
Soporta centésimas, milésimas, etiquetas múltiples, metadatos y desorden temporal.
"""

import re
from typing import List, Optional
from .lyrics_models import LyricLine, ActiveLineResult

# Regex para extraer marcas de tiempo [mm:ss.xx] o [mm:ss.xxx]
TIMESTAMP_REGEX = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
# Regex para detectar metadatos estándar de LRC como [ar:Artist], [ti:Title], [offset:100]
METADATA_REGEX = re.compile(r"^\[([a-zA-Z]+):(.*)\]$")


def parse_timestamp_ms(min_str: str, sec_str: str, frac_str: Optional[str]) -> int:
    """Convierte minutos, segundos y fracción a milisegundos enteros."""
    minutes = int(min_str)
    seconds = int(sec_str)

    ms = 0
    if frac_str:
        # Si tiene 2 dígitos (centésimas), multiplicar por 10 (ej: .45 -> 450 ms)
        # Si tiene 1 dígito (décimas), multiplicar por 100 (ej: .4 -> 400 ms)
        # Si tiene 3 dígitos (milésimas), tomarlo tal cual (ej: .450 -> 450 ms)
        if len(frac_str) == 1:
            ms = int(frac_str) * 100
        elif len(frac_str) == 2:
            ms = int(frac_str) * 10
        else:
            ms = int(frac_str[:3])

    return (minutes * 60 * 1000) + (seconds * 1000) + ms


def parse_lrc(lrc_content: str) -> List[LyricLine]:
    """
    Parsea una cadena en formato LRC y devuelve una lista ordenada de LyricLine.
    
    Características:
    - Soporta múltiples timestamps por línea (ej: [00:10.00][00:25.00]Coro).
    - Aplica tag [offset:+/-ms] global si existe.
    - Filtra cabeceras de metadatos no musicales ([ti:], [ar:], etc.).
    - Ordena cronológicamente la salida final.
    """
    if not lrc_content or not lrc_content.strip():
        return []

    lines = lrc_content.splitlines()
    parsed_items: List[LyricLine] = []
    global_offset_ms = 0

    # 1. Primera pasada para capturar [offset:xxx] si existe
    for line in lines:
        line_clean = line.strip()
        if line_clean.lower().startswith("[offset:"):
            match = re.match(r"\[offset:\s*([+-]?\d+)\s*\]", line_clean, re.IGNORECASE)
            if match:
                try:
                    global_offset_ms = int(match.group(1))
                except ValueError:
                    pass

    # 2. Segunda pasada para parsear versos
    for raw_line in lines:
        line_str = raw_line.strip()
        if not line_str:
            continue

        # Si es una línea de metadatos pura sin timestamp numérico, ignorar
        if METADATA_REGEX.match(line_str) and not TIMESTAMP_REGEX.search(line_str):
            continue

        # Encontrar todos los timestamps en la línea
        matches = list(TIMESTAMP_REGEX.finditer(line_str))
        if not matches:
            continue

        # El texto lírico es todo lo que queda después del último timestamp
        last_match = matches[-1]
        text_content = line_str[last_match.end():].strip()

        # Para cada timestamp hallado en la línea, crear una entrada
        for m in matches:
            t_ms = parse_timestamp_ms(m.group(1), m.group(2), m.group(3))
            final_ms = max(0, t_ms + global_offset_ms)
            parsed_items.append(LyricLine(timestamp_ms=final_ms, text=text_content))

    # 3. Ordenar cronológicamente por timestamp_ms
    parsed_items.sort(key=lambda item: item.timestamp_ms)

    return parsed_items


def get_active_line(position_ms: int, lyrics: List[LyricLine]) -> ActiveLineResult:
    """
    Determina de manera determinista la línea activa para una posición en milisegundos.
    
    Reglas:
    - Si no hay letras: index = -1, line = None.
    - Si position_ms < primer timestamp: index = -1, is_intro = True, next_line = lyrics[0].
    - Si position_ms == timestamp: devuelve exactamente esa línea.
    - Si position_ms está entre dos timestamps: devuelve la línea del timestamp anterior.
    - Si position_ms >= último timestamp: devuelve la última línea, is_outro = True.
    """
    if not lyrics:
        return ActiveLineResult(index=-1, line=None, is_intro=True)

    # Caso A: Antes del primer verso (Intro instrumental)
    if position_ms < lyrics[0].timestamp_ms:
        return ActiveLineResult(
            index=-1,
            line=None,
            next_line=lyrics[0],
            is_intro=True,
            is_outro=False,
        )

    # Búsqueda binaria o búsqueda lineal del índice activo
    # lyrics[i].timestamp_ms <= position_ms < lyrics[i+1].timestamp_ms
    low = 0
    high = len(lyrics) - 1
    best_idx = 0

    while low <= high:
        mid = (low + high) // 2
        if lyrics[mid].timestamp_ms <= position_ms:
            best_idx = mid
            low = mid + 1
        else:
            high = mid - 1

    active_line = lyrics[best_idx]
    next_line = lyrics[best_idx + 1] if best_idx + 1 < len(lyrics) else None
    is_outro = (best_idx == len(lyrics) - 1)

    return ActiveLineResult(
        index=best_idx,
        line=active_line,
        next_line=next_line,
        is_intro=False,
        is_outro=is_outro,
    )
