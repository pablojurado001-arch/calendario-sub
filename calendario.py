import re
import hashlib
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


URL = "https://astursala.es/tercera-division-futbol-sala-grupo-18-andalucia-oriental"
EQUIPO = "C.D. Boca F.S. Priego"
ARCHIVO = "boca-priego.ics"


def descargar():
    req = Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urlopen(req, timeout=30) as respuesta:
        return respuesta.read()


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def extraer_partidos():

    soup = BeautifulSoup(descargar(), "html.parser")

    texto = soup.get_text("\n")

    lineas = [
        limpiar(x)
        for x in texto.splitlines()
        if limpiar(x)
    ]

    partidos = []

    meses = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
    }

    patron = re.compile(
        r"(\d{1,2})\s+"
        r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)"
        r"[a-z]*\s+"
        r"(\d{4})\s*-\s*"
        r"(\d{1,2}):(\d{2})\s*Horas",
        re.IGNORECASE
    )

    for i, linea in enumerate(lineas):

        if "3ª Dvs - Grupo 18" not in linea:
            continue

        fecha_match = None
        fecha_index = None

        for j in range(i + 1, min(i + 15, len(lineas))):

            m = patron.search(lineas[j])

            if m:
                fecha_match = m
                fecha_index = j
                break

        if not fecha_match:
            continue

        dia = int(fecha_match.group(1))
        mes = meses[fecha_match.group(2).lower()]
        anio = int(fecha_match.group(3))
        hora = int(fecha_match.group(4))
        minuto = int(fecha_match.group(5))

        fecha = datetime(
            anio,
            mes,
            dia,
            hora,
            minuto
        )

        bloque = lineas[
            fecha_index + 1:
            min(fecha_index + 10, len(lineas))
        ]

        if EQUIPO not in bloque:
            continue

        indice_boca = bloque.index(EQUIPO)

        equipos = []

        for texto_linea in bloque:

            if texto_linea == EQUIPO:
                continue

            if "Pabell" in texto_linea or "pabell" in texto_linea:
                continue

            if "Horas" in texto_linea:
                continue

            if re.match(r"^\d+\s*-\s*\d+$", texto_linea):
                continue

            if len(texto_linea) > 80:
                continue

            if texto_linea in [
                "Previa",
                "Resultado",
                "Ficha",
                "Clasificación"
            ]:
                continue

            equipos.append(texto_linea)

        if not equipos:
            continue

        rival = equipos[0]

        pabellon = ""

        for texto_linea in bloque:

            if (
                "Pabellón" in texto_linea
                or "Pabellon" in texto_linea
                or "Polideportivo" in texto_linea
            ):
                pabellon = texto_linea
                break

        # Determinar local/visitante según la posición.
        posiciones = [
            k for k, x in enumerate(bloque)
            if x == EQUIPO
        ]

        if posiciones and posiciones[0] < 4:
            local = EQUIPO
            visitante = rival
        else:
            local = rival
            visitante = EQUIPO

        # Identificador estable:
        # mismo partido aunque cambie hora o pabellón.
        uid_base = (
            fecha.strftime("%Y-%m-%d")
            + "|"
            + rival
        )

        uid = hashlib.md5(
            uid_base.encode("utf-8")
        ).hexdigest()

        partidos.append({
            "fecha": fecha,
            "rival": rival,
            "pabellon": pabellon,
            "local": local,
            "visitante": visitante,
            "uid": uid
        })

    # Eliminar duplicados.
    unicos = {}

    for partido in partidos:
        unicos[partido["uid"]] = partido

    partidos = list(unicos.values())

    partidos.sort(
        key=lambda x: x["fecha"]
    )

    return partidos


def escapar(texto):

    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generar_ics(partidos):

    calendario = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boca Priego FS//Calendario Senior//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Boca Priego FS Senior",
        "X-WR-TIMEZONE:Europe/Madrid"
    ]

    for partido in partidos:

        inicio = partido["fecha"]
        fin = inicio + timedelta(hours=2)

        titulo = (
            f"{partido['local']} - "
            f"{partido['visitante']}"
        )

        descripcion = (
            "Boca Priego FS Senior\\n"
            "3ª División Fútbol Sala - Grupo 18"
        )

        calendario.extend([
            "BEGIN:VEVENT",

            f"UID:{partido['uid']}@bocapriego",

            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",

            f"DTSTART;TZID=Europe/Madrid:"
            f"{inicio.strftime('%Y%m%dT%H%M%S')}",

            f"DTEND;TZID=Europe/Madrid:"
            f"{fin.strftime('%Y%m%dT%H%M%S')}",

            f"SUMMARY:{escapar(titulo)}",

            f"LOCATION:{escapar(partido['pabellon'])}",

            f"DESCRIPTION:{escapar(descripcion)}",

            "END:VEVENT"
        ])

    calendario.append("END:VCALENDAR")

    with open(
        ARCHIVO,
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            "\r\n".join(calendario)
            + "\r\n"
        )


def main():

    partidos = extraer_partidos()

    print()
    print("=" * 60)
    print("PARTIDOS ENCONTRADOS:", len(partidos))
    print("=" * 60)

    for partido in partidos:

        print(
            partido["fecha"].strftime(
                "%d/%m/%Y %H:%M"
            ),
            "|",
            partido["local"],
            "vs",
            partido["visitante"],
            "|",
            partido["pabellon"]
        )

    print("=" * 60)

    generar_ics(partidos)

    print("Calendario generado:", ARCHIVO)
    print("=" * 60)


if __name__ == "__main__":
    main()    lineas = [
        limpiar(x)
        for x in soup.get_text("\n").splitlines()
        if limpiar(x)
    ]

    partidos = []

    patron_fecha = re.compile(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo),?\s*"
        r"(\d{1,2})\s+"
        r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)"
        r"(?:[a-z]+)?\s+"
        r"(\d{4})\s*-\s*"
        r"(\d{1,2}):(\d{2})\s*Horas",
        re.IGNORECASE
    )

    meses = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
    }

    for i, linea in enumerate(lineas):

        if "3ª Dvs - Grupo 18" not in linea:
            continue

        # Buscamos la fecha inmediatamente después.
        fecha = None
        indice_fecha = None

        for j in range(i + 1, min(i + 12, len(lineas))):
            coincidencia = patron_fecha.search(lineas[j])

            if coincidencia:
                fecha = coincidencia
                indice_fecha = j
                break

        if not fecha:
            continue

        dia = int(fecha.group(1))
        mes = meses.get(fecha.group(2).lower())
        anio = int(fecha.group(3))
        hora = int(fecha.group(4))
        minuto = int(fecha.group(5))

        if not mes:
            continue

        fecha_partido = datetime(
            anio,
            mes,
            dia,
            hora,
            minuto
        )

        # Después de la fecha normalmente aparecen:
        # pabellón
        # equipo local
        # Previa/resultado
        # equipo visitante

        bloque = lineas[
            indice_fecha + 1:
            min(indice_fecha + 8, len(lineas))
        ]

        pabellon = ""
        local = ""
        visitante = ""

        indice_boca = None

        for k, texto in enumerate(bloque):

            if "Pabell" in texto or "pabell" in texto:
                if not pabellon:
                    pabellon = texto

            if EQUIPO.lower() in texto.lower():
                indice_boca = k

        if indice_boca is None:
            continue

        # El rival está normalmente justo antes o justo después
        # del nombre de Boca.
        candidatos = []

        for k, texto in enumerate(bloque):
            if k == indice_boca:
                continue

            if any(
                x in texto.lower()
                for x in [
                    "previa",
                    "horas",
                    "3ª dvs",
                    "pabell",
                ]
            ):
                continue

            if re.match(r"^\d+\s*-\s*\d+$", texto):
                continue

            if len(texto) > 100:
                continue

            candidatos.append((k, texto))

        # El rival es el equipo que acompaña a Boca en el bloque.
        for k, texto in candidatos:
            if texto != EQUIPO and texto not in [
                local,
                visitante
            ]:
                if k < indice_boca:
                    local = texto
                elif not visitante:
                    visitante = texto

        # Determinamos quién es local.
        # Si Boca aparece antes que el rival, Boca es local.
        if indice_boca < len(bloque) // 2:
            local = EQUIPO
        else:
            visitante = EQUIPO

        rival = (
            visitante
            if local == EQUIPO
            else local
        )

        if not rival or rival == EQUIPO:
            continue

        # Evitar duplicados.
        clave = (
            fecha_partido.strftime("%Y%m%d"),
            hora,
            minuto,
            rival,
            pabellon,
        )

        if any(p["clave"] == clave for p in partidos):
            continue

        partidos.append(
            {
                "fecha": fecha_partido,
                "rival": rival,
                "pabellon": pabellon,
                "local": local,
                "visitante": visitante,
                "clave": clave,
            }
        )

    partidos.sort(key=lambda p: p["fecha"])

    return partidos


def escapar(texto):
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generar_calendario(partidos):

    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boca Priego FS//Calendario Senior//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Boca Priego FS Senior",
        "X-WR-CALDESC:Partidos Boca Priego FS Senior",
        "X-WR-TIMEZONE:Europe/Madrid",
    ]

    for partido in partidos:

        inicio = partido["fecha"]

        # Dos horas de duración.
        fin = inicio + timedelta(hours=2)

        # El UID se basa en la jornada + rival.
        # Si cambia hora o pabellón, seguirá siendo
        # el mismo evento.
        uid_base = (
            f'{inicio.strftime("%Y-%m-%d")}|'
            f'{partido["rival"]}'
        )

        uid = hashlib.sha256(
            uid_base.encode("utf-8")
        ).hexdigest()[:32]

        uid = f"{uid}@bocapriego"

        titulo = (
            f"Boca Priego FS - {partido['rival']}"
        )

        descripcion = (
            "Boca Priego FS Senior\\n"
            "3ª División Fútbol Sala - Grupo 18\\n"
            f"Local: {partido['local']}\\n"
            f"Visitante: {partido['visitante']}"
        )

        lineas.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;TZID=Europe/Madrid:{inicio.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Europe/Madrid:{fin.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{escapar(titulo)}",
                f"LOCATION:{escapar(partido['pabellon'])}",
                f"DESCRIPTION:{escapar(descripcion)}",
                "END:VEVENT",
            ]
        )

    lineas.append("END:VCALENDAR")

    with open(
        ARCHIVO_SALIDA,
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            "\r\n".join(lineas) + "\r\n"
        )


if __name__ == "__main__":

    partidos = extraer_partidos()

    print("=" * 60)
    print(f"PARTIDOS ENCONTRADOS: {len(partidos)}")
    print("=" * 60)

    for partido in partidos:

        print(
            partido["fecha"].strftime(
                "%d/%m/%Y %H:%M"
            ),
            "|",
            partido["local"],
            "vs",
            partido["visitante"],
            "|",
            partido["pabellon"],
        )

    generar_calendario(partidos)

    print("=" * 60)
    print("CALENDARIO GENERADO:", ARCHIVO_SALIDA)
    print("=" * 60)    partidos = []

    meses = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
    }

    patron_fecha = re.compile(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo),?\s*"
        r"(\d{1,2})\s+"
        r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)"
        r"(?:rero|rero|zo|il|o|io|lio|osto|iembre|ubre|iembre|iembre|iembre)?"
        r"\s+(\d{4})"
        r"(?:\s*-\s*(\d{1,2}):(\d{2}))?",
        re.IGNORECASE,
    )

    # Buscamos bloques de texto donde aparece Boca Priego.
    for i, linea in enumerate(lineas):
        if EQUIPO.lower() not in linea.lower():
            continue

        inicio = max(0, i - 12)
        fin = min(len(lineas), i + 12)
        bloque = " ".join(lineas[inicio:fin])

        fecha_match = patron_fecha.search(bloque)

        if not fecha_match:
            continue

        dia = int(fecha_match.group(1))
        mes_texto = fecha_match.group(2).lower()
        anio = int(fecha_match.group(3))
        hora = fecha_match.group(4)
        minuto = fecha_match.group(5)

        mes = meses.get(mes_texto)

        if not mes:
            continue

        if hora:
            hora_int = int(hora)
            minuto_int = int(minuto)
        else:
            hora_int = 12
            minuto_int = 0

        fecha = datetime(
            anio,
            mes,
            dia,
            hora_int,
            minuto_int
        )

        # Intentamos encontrar el pabellón.
        pabellon = ""

        for j in range(max(0, i - 8), min(len(lineas), i + 8)):
            texto_linea = lineas[j]

            if any(
                palabra in texto_linea.lower()
                for palabra in [
                    "pabellón",
                    "pabellon",
                    "polideportivo",
                    "pab.",
                    "centro deportivo",
                ]
            ):
                pabellon = texto_linea
                break

        # Intentamos encontrar al rival.
        rival = ""

        for j in range(max(0, i - 5), min(len(lineas), i + 6)):
            candidato = lineas[j]

            if (
                candidato
                and EQUIPO.lower() not in candidato.lower()
                and not patron_fecha.search(candidato)
                and len(candidato) < 100
            ):
                if not any(
                    palabra in candidato.lower()
                    for palabra in [
                        "previa",
                        "histórico",
                        "últimos",
                        "próximos",
                        "jornada",
                        "clasificación",
                    ]
                ):
                    rival = candidato
                    break

        # Evitamos duplicados.
        clave = (
            fecha.strftime("%Y-%m-%d"),
            rival,
            pabellon
        )

        if not any(
            (
                p["fecha"].strftime("%Y-%m-%d"),
                p["rival"],
                p["pabellon"]
            ) == clave
            for p in partidos
        ):
            partidos.append(
                {
                    "fecha": fecha,
                    "rival": rival,
                    "pabellon": pabellon,
                    "texto": bloque,
                }
            )

    partidos.sort(key=lambda p: p["fecha"])

    return partidos


def escapar(texto):
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generar_ics(partidos):
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boca Priego FS//Calendario Senior//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Boca Priego FS Senior",
        "X-WR-CALDESC:Partidos del Boca Priego FS Senior",
        "X-WR-TIMEZONE:Europe/Madrid",
    ]

    for partido in partidos:
        inicio = partido["fecha"]
        fin = inicio + timedelta(hours=2)

        uid_base = (
            f'{inicio.isoformat()}|'
            f'{partido["rival"]}|'
            f'{partido["pabellon"]}'
        )

        uid = hashlib.md5(
            uid_base.encode("utf-8")
        ).hexdigest() + "@bocapriego"

        if partido["fecha"].hour == 12 and partido["fecha"].minute == 0:
            titulo = f"Boca Priego FS - {partido['rival']}"
        else:
            titulo = f"Boca Priego FS - {partido['rival']}"

        descripcion = (
            "Partido Boca Priego FS Senior\\n"
            "Competición: 3ª División Fútbol Sala - Grupo 18"
        )

        lineas.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;TZID=Europe/Madrid:{inicio.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Europe/Madrid:{fin.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{escapar(titulo)}",
                f"LOCATION:{escapar(partido['pabellon'])}",
                f"DESCRIPTION:{escapar(descripcion)}",
                "END:VEVENT",
            ]
        )

    lineas.append("END:VCALENDAR")

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as archivo:
        archivo.write("\r\n".join(lineas) + "\r\n")


if __name__ == "__main__":
    partidos = obtener_partidos()

    print(f"Partidos encontrados: {len(partidos)}")

    for partido in partidos:
        print(
            partido["fecha"].strftime("%d/%m/%Y %H:%M"),
            "-",
            partido["rival"],
            "-",
            partido["pabellon"],
        )

    generar_ics(partidos)

    print(f"Calendario generado: {ARCHIVO_SALIDA}")
