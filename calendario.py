import re
import hashlib
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

URL = "https://astursala.es/tercera-division-futbol-sala-grupo-18-andalucia-oriental"

EQUIPO = "C.D. Boca F.S. Priego"
ARCHIVO_SALIDA = "boca-priego.ics"


def descargar_web():
    request = Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urlopen(request, timeout=30) as respuesta:
        return respuesta.read()


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def obtener_partidos():
    html = descargar_web()
    soup = BeautifulSoup(html, "html.parser")

    texto = soup.get_text("\n")
    lineas = [limpiar(x) for x in texto.splitlines()]
    lineas = [x for x in lineas if x]

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
