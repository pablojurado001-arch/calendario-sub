import re
import hashlib
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

URL = "https://astursala.es/tercera-division-futbol-sala-grupo-18-andalucia-oriental"
EQUIPO = "C.D. Boca F.S. Priego"
SALIDA = "boca-priego.ics"


def descargar():
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        return r.read()


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def obtener_partidos():
    soup = BeautifulSoup(descargar(), "html.parser")
    lineas = [limpiar(x) for x in soup.get_text("\n").splitlines()]
    lineas = [x for x in lineas if x]

    meses = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4,
        "may": 5, "jun": 6, "jul": 7, "ago": 8,
        "sep": 9, "oct": 10, "nov": 11, "dic": 12
    }

    patron = re.compile(
        r"(\d{1,2})\s+"
        r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)"
        r"[a-z]*\s+(\d{4})\s*-\s*"
        r"(\d{1,2}):(\d{2})\s*Horas",
        re.IGNORECASE
    )

    partidos = []

    for i, linea in enumerate(lineas):

        if EQUIPO not in linea:
            continue

        inicio = max(0, i - 8)
        fin = min(len(lineas), i + 12)
        bloque = lineas[inicio:fin]

        fecha = None

        for texto in bloque:
            m = patron.search(texto)
            if m:
                fecha = m
                break

        if not fecha:
            continue

        dia = int(fecha.group(1))
        mes = meses[fecha.group(2).lower()]
        anio = int(fecha.group(3))
        hora = int(fecha.group(4))
        minuto = int(fecha.group(5))

        fecha_partido = datetime(
            anio,
            mes,
            dia,
            hora,
            minuto
        )

        rival = ""

        for texto in bloque:
            if texto == EQUIPO:
                continue

            if "Pabell" in texto or "pabell" in texto:
                continue

            if "Horas" in texto:
                continue

            if re.match(r"^\d+\s*-\s*\d+$", texto):
                continue

            if len(texto) > 80:
                continue

            if texto in [
                "Previa",
                "Resultado",
                "Ficha",
                "Clasificación"
            ]:
                continue

            rival = texto
            break

        if not rival:
            continue

        pabellon = ""

        for texto in bloque:
            if (
                "Pabellón" in texto
                or "Pabellon" in texto
                or "Polideportivo" in texto
            ):
                pabellon = texto
                break

        uid = hashlib.md5(
            (
                fecha_partido.strftime("%Y-%m-%d")
                + "|"
                + rival
            ).encode("utf-8")
        ).hexdigest()

        partidos.append({
            "fecha": fecha_partido,
            "rival": rival,
            "pabellon": pabellon,
            "uid": uid
        })

    resultado = {}

    for partido in partidos:
        resultado[partido["uid"]] = partido

    return sorted(
        resultado.values(),
        key=lambda x: x["fecha"]
    )


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
        "PRODID:-//Boca Priego FS//Calendario//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Boca Priego FS Senior",
        "X-WR-TIMEZONE:Europe/Madrid"
    ]

    for partido in partidos:

        inicio = partido["fecha"]
        fin = inicio + timedelta(hours=2)

        titulo = (
            "Boca Priego FS - "
            + partido["rival"]
        )

        lineas.extend([
            "BEGIN:VEVENT",
            "UID:" + partido["uid"] + "@bocapriego",
            "DTSTAMP:" + datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART;TZID=Europe/Madrid:"
            + inicio.strftime("%Y%m%dT%H%M%S"),
            "DTEND;TZID=Europe/Madrid:"
            + fin.strftime("%Y%m%dT%H%M%S"),
            "SUMMARY:" + escapar(titulo),
            "LOCATION:" + escapar(partido["pabellon"]),
            "DESCRIPTION:Boca Priego FS Senior - 3ª Division Futbol Sala",
            "END:VEVENT"
        ])

    lineas.append("END:VCALENDAR")

    with open(SALIDA, "w", encoding="utf-8") as archivo:
        archivo.write("\r\n".join(lineas) + "\r\n")


def main():

    partidos = obtener_partidos()

    print("========================================")
    print("PARTIDOS ENCONTRADOS:", len(partidos))
    print("========================================")

    for partido in partidos:
        print(
            partido["fecha"].strftime("%d/%m/%Y %H:%M"),
            "|",
            partido["rival"],
            "|",
            partido["pabellon"]
        )

    generar_calendario(partidos)

    print("========================================")
    print("CALENDARIO GENERADO:", SALIDA)
    print("========================================")


if __name__ == "__main__":
    main()
