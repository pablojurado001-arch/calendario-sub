import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


URL = "https://astursala.es/tercera-division-futbol-sala-grupo-18-andalucia-oriental"

EQUIPO = "C.D. Boca F.S. Priego"

ARCHIVO = "boca-priego.ics"


MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def descargar_pagina():

    request = Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urlopen(request, timeout=30) as respuesta:
        return respuesta.read()


def limpiar(texto):

    return re.sub(
        r"\s+",
        " ",
        texto
    ).strip()


def convertir_fecha(fecha_texto, hora_texto=None):

    fecha_texto = limpiar(fecha_texto)

    if hora_texto:
        fecha_texto += " " + limpiar(hora_texto)

    patron = re.compile(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo),?\s*"
        r"(\d{1,2})\s+"
        r"([a-záéíóú]+)\s+"
        r"(\d{4})"
        r"(?:\s*-\s*(\d{1,2}):(\d{2})\s*Horas)?",
        re.IGNORECASE
    )

    resultado = patron.search(fecha_texto)

    if not resultado:
        return None

    dia = int(resultado.group(1))

    nombre_mes = resultado.group(2).lower()

    anio = int(resultado.group(3))

    mes = MESES.get(nombre_mes)

    if mes is None:
        return None

    if resultado.group(4) is None:

        hora = 0
        minuto = 0

    else:

        hora = int(resultado.group(4))
        minuto = int(resultado.group(5))

    return datetime(
        anio,
        mes,
        dia,
        hora,
        minuto
    )


def es_fecha(texto):

    return convertir_fecha(texto) is not None


def es_hora(texto):

    return re.match(
        r"^-\s*\d{1,2}:\d{2}\s*Horas$",
        texto,
        re.IGNORECASE
    ) is not None


def obtener_lineas():

    soup = BeautifulSoup(
        descargar_pagina(),
        "html.parser"
    )

    lineas = []

    for texto in soup.get_text("\n").splitlines():

        texto = limpiar(texto)

        if texto:
            lineas.append(texto)

    return lineas


def obtener_partidos():

    lineas = obtener_lineas()

    partidos = []

    i = 0

    while i < len(lineas):

        # ------------------------------------------------
        # FORMATO A:
        #
        # sábado, 3 octubre 2026
        # - 17:00 Horas
        # Pabellón Municipal Torre del Mar
        # C.D. Atletico Torre del Mar
        # Previa
        # C.D. Boca F.S. Priego
        # ------------------------------------------------

        if es_fecha(lineas[i]):

            fecha = convertir_fecha(lineas[i])

            siguiente = i + 1

            # Si la hora viene en la siguiente línea.
            if (
                siguiente < len(lineas)
                and es_hora(lineas[siguiente])
            ):

                fecha = convertir_fecha(
                    lineas[i],
                    lineas[siguiente]
                )

                posicion = i + 2

            else:

                posicion = i + 1

            if fecha is None:
                i += 1
                continue

            # Necesitamos:
            #
            # pabellón
            # local
            # Previa
            # visitante

            if posicion + 3 >= len(lineas):
                i += 1
                continue

            pabellon = lineas[posicion]
            local = lineas[posicion + 1]
            marcador = lineas[posicion + 2]
            visitante = lineas[posicion + 3]

            # Comprobamos que realmente sea un partido.
            if marcador.lower() != "previa":
                i += 1
                continue

            if (
                EQUIPO not in local
                and EQUIPO not in visitante
            ):
                i += 1
                continue

            # Hemos encontrado un partido válido.
            rival = (
                visitante
                if EQUIPO in local
                else local
            )

            # UID estable.
            # Si cambia la hora o el pabellón,
            # seguirá siendo el mismo evento.
            clave = (
                fecha.strftime("%Y-%m-%d")
                + "|"
                + local
                + "|"
                + visitante
            )

            uid = hashlib.sha256(
                clave.encode("utf-8")
            ).hexdigest()[:32]

            partidos.append({
                "fecha": fecha,
                "local": local,
                "visitante": visitante,
                "rival": rival,
                "pabellon": pabellon,
                "uid": uid
            })

            # Saltamos el bloque que acabamos de leer.
            i = posicion + 4
            continue

        i += 1

    # Eliminar duplicados.
    unicos = {}

    for partido in partidos:
        unicos[partido["uid"]] = partido

    partidos = list(unicos.values())

    partidos.sort(
        key=lambda partido: partido["fecha"]
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
        "X-WR-CALDESC:Partidos Boca Priego FS Senior",
        "X-WR-TIMEZONE:Europe/Madrid"
    ]

    for partido in partidos:

        fecha = partido["fecha"]

        hora_pendiente = (
            fecha.hour == 0
            and fecha.minute == 0
        )

        titulo = (
            partido["local"]
            + " - "
            + partido["visitante"]
        )

        descripcion = (
            "Boca Priego FS Senior\\n"
            "3ª División Fútbol Sala - Grupo 18\\n"
            "Local: "
            + partido["local"]
            + "\\n"
            "Visitante: "
            + partido["visitante"]
        )

        calendario.append(
            "BEGIN:VEVENT"
        )

        calendario.append(
            "UID:"
            + partido["uid"]
            + "@bocapriego"
        )

        calendario.append(
            "DTSTAMP:"
            + datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%dT%H%M%SZ"
            )
        )

        if hora_pendiente:

            # Solo fecha porque la hora aún no
            # está publicada.
            calendario.append(
                "DTSTART;VALUE=DATE:"
                + fecha.strftime("%Y%m%d")
            )

            calendario.append(
                "DTEND;VALUE=DATE:"
                + (
                    fecha
                    + timedelta(days=1)
                ).strftime("%Y%m%d")
            )

            titulo += " - HORA PENDIENTE"

        else:

            fin = fecha + timedelta(
                hours=2
            )

            calendario.append(
                "DTSTART;TZID=Europe/Madrid:"
                + fecha.strftime(
                    "%Y%m%dT%H%M%S"
                )
            )

            calendario.append(
                "DTEND;TZID=Europe/Madrid:"
                + fin.strftime(
                    "%Y%m%dT%H%M%S"
                )
            )

        calendario.append(
            "SUMMARY:"
            + escapar(titulo)
        )

        calendario.append(
            "LOCATION:"
            + escapar(
                partido["pabellon"]
            )
        )

        calendario.append(
            "DESCRIPTION:"
            + escapar(descripcion)
        )

        calendario.append(
            "END:VEVENT"
        )

    calendario.append(
        "END:VCALENDAR"
    )

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

    partidos = obtener_partidos()

    print()
    print("========================================")
    print(
        "PARTIDOS ENCONTRADOS:",
        len(partidos)
    )
    print("========================================")

    for partido in partidos:

        fecha = partido["fecha"]

        if (
            fecha.hour == 0
            and fecha.minute == 0
        ):

            hora = "HORA PENDIENTE"

        else:

            hora = fecha.strftime(
                "%H:%M"
            )

        print(
            fecha.strftime("%d/%m/%Y"),
            "|",
            hora,
            "|",
            partido["local"],
            "vs",
            partido["visitante"],
            "|",
            partido["pabellon"]
        )

    print("========================================")

    generar_ics(partidos)

    print(
        "CALENDARIO GENERADO:",
        ARCHIVO
    )

    print("========================================")


if __name__ == "__main__":
    main()
