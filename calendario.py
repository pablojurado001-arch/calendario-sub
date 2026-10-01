import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


URL = (
    "https://astursala.es/"
    "tercera-division-futbol-sala-grupo-18-andalucia-oriental"
)

EQUIPO = "C.D. Boca F.S. Priego"
SALIDA = "boca-priego.ics"


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


def descargar():

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


def analizar_fecha(linea_fecha, linea_hora=None):

    texto = limpiar(linea_fecha)

    if linea_hora:
        texto += " " + limpiar(linea_hora)

    # Formato:
    # sábado, 3 octubre 2026 - 17:00 Horas
    patron = re.search(
        r"(\d{1,2})\s+"
        r"([a-záéíóú]+)\s+"
        r"(\d{4})"
        r"(?:\s*-\s*(\d{1,2}):(\d{2})\s*Horas)?",
        texto,
        re.IGNORECASE
    )

    if not patron:
        return None

    dia = int(patron.group(1))
    mes_nombre = patron.group(2).lower()
    anio = int(patron.group(3))

    mes = MESES.get(mes_nombre)

    if not mes:
        return None

    if patron.group(4):
        hora = int(patron.group(4))
        minuto = int(patron.group(5))
    else:
        hora = 0
        minuto = 0

    return datetime(
        anio,
        mes,
        dia,
        hora,
        minuto
    )


def obtener_partidos():

    soup = BeautifulSoup(
        descargar(),
        "html.parser"
    )

    lineas = []

    for texto in soup.get_text("\n").splitlines():

        texto = limpiar(texto)

        if texto:
            lineas.append(texto)

    partidos = []

    i = 0

    while i < len(lineas):

        linea = lineas[i]

        # -------------------------------------------------
        # FORMATO 1
        #
        # sábado, 3 octubre 2026
        # - 17:00 Horas
        # Pabellón Municipal Torre del Mar
        # C.D. Atletico Torre del Mar
        # Previa
        # C.D. Boca F.S. Priego
        # -------------------------------------------------

        if (
            "Boca" in linea
            and "Priego" in linea
        ):
            i += 1
            continue

        fecha = None
        fecha_index = None

        # Miramos unas líneas alrededor.
        for j in range(
            max(0, i - 8),
            min(len(lineas), i + 8)
        ):

            posible_fecha = analizar_fecha(
                lineas[j]
            )

            if posible_fecha:

                fecha = posible_fecha
                fecha_index = j
                break

            # Formato partido en dos líneas:
            # 3 octubre 2026
            # - 17:00 Horas

            if j + 1 < len(lineas):

                posible_fecha = analizar_fecha(
                    lineas[j],
                    lineas[j + 1]
                )

                if posible_fecha:

                    fecha = posible_fecha
                    fecha_index = j
                    break

        if fecha is None:
            i += 1
            continue

        # -------------------------------------------------
        # Buscamos la estructura del partido a partir
        # de la fecha.
        # -------------------------------------------------

        pabellon = None
        local = None
        visitante = None

        for j in range(
            fecha_index + 1,
            min(
                len(lineas),
                fecha_index + 10
            )
        ):

            texto = lineas[j]

            # Pabellón
            if (
                "Pabellón" in texto
                or "Pabellon" in texto
                or "Polideportivo" in texto
            ):

                if pabellon is None:
                    pabellon = texto

                continue

            # Buscamos la estructura:
            #
            # EQUIPO
            # Previa
            # EQUIPO

            if j + 2 < len(lineas):

                candidato_local = lineas[j]
                marcador = lineas[j + 1]
                candidato_visitante = lineas[j + 2]

                if marcador.lower() == "previa":

                    if (
                        EQUIPO in candidato_local
                        or EQUIPO in candidato_visitante
                    ):

                        local = candidato_local
                        visitante = candidato_visitante

                        break

        if (
            local is None
            or visitante is None
        ):
            i += 1
            continue

        if (
            EQUIPO not in local
            and EQUIPO not in visitante
        ):
            i += 1
            continue

        rival = (
            visitante
            if EQUIPO in local
            else local
        )

        # -------------------------------------------------
        # UID ESTABLE
        # -------------------------------------------------

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

        partidos.append(
            {
                "fecha": fecha,
                "local": local,
                "visitante": visitante,
                "rival": rival,
                "pabellon": pabellon or "",
                "uid": uid,
            }
        )

        i = fecha_index + 5

    # Eliminar duplicados

    unicos = {}

    for partido in partidos:

        unicos[partido["uid"]] = partido

    partidos = list(
        unicos.values()
    )

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


def generar_calendario(partidos):

    calendario = [
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

            calendario.append(
                "DTSTART;VALUE=DATE:"
                + fecha.strftime(
                    "%Y%m%d"
                )
            )

            calendario.append(
                "DTEND;VALUE=DATE:"
                + (
                    fecha
                    + timedelta(days=1)
                ).strftime(
                    "%Y%m%d"
                )
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
        SALIDA,
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
    print(
        "========================================"
    )
    print(
        "PARTIDOS ENCONTRADOS:",
        len(partidos)
    )
    print(
        "========================================"
    )

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

    print(
        "========================================"
    )

    generar_calendario(
        partidos
    )

    print(
        "CALENDARIO GENERADO:",
        SALIDA
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
