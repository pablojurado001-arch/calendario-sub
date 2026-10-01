import re
import hashlib
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


URL = (
    "https://astursala.es/"
    "tercera-division-futbol-sala-grupo-18-andalucia-oriental"
)

EQUIPO = "C.D. Boca F.S. Priego"
SALIDA = "boca-priego.ics"


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


def obtener_lineas():

    soup = BeautifulSoup(
        descargar(),
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

    meses = {
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
        "diciembre": 12
    }

    patron_fecha = re.compile(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo),?\s*"
        r"(\d{1,2})\s+"
        r"([a-záéíóú]+)\s+"
        r"(\d{4})\s*-\s*"
        r"(\d{1,2}):(\d{2})\s*Horas",
        re.IGNORECASE
    )

    for i in range(len(lineas)):

        coincidencia = patron_fecha.search(
            lineas[i]
        )

        if not coincidencia:
            continue

        # Necesitamos:
        #
        # fecha/hora
        # pabellón
        # local
        # Previa
        # visitante

        if i + 4 >= len(lineas):
            continue

        pabellon = lineas[i + 1]
        local = lineas[i + 2]
        marcador = lineas[i + 3]
        visitante = lineas[i + 4]

        if marcador.lower() != "previa":
            continue

        if (
            EQUIPO not in local
            and EQUIPO not in visitante
        ):
            continue

        dia = int(
            coincidencia.group(1)
        )

        nombre_mes = (
            coincidencia.group(2)
            .lower()
        )

        anio = int(
            coincidencia.group(3)
        )

        hora = int(
            coincidencia.group(4)
        )

        minuto = int(
            coincidencia.group(5)
        )

        mes = meses.get(
            nombre_mes
        )

        if not mes:
            continue

        fecha = datetime(
            anio,
            mes,
            dia,
            hora,
            minuto
        )

        rival = (
            visitante
            if local == EQUIPO
            else local
        )

        # Identificador estable.
        # Si cambia la hora o el pabellón,
        # seguirá siendo el mismo partido.
        identificador = (
            f"{anio}-{mes:02d}-{dia:02d}|"
            f"{local}|"
            f"{visitante}"
        )

        uid = hashlib.sha256(
            identificador.encode(
                "utf-8"
            )
        ).hexdigest()[:32]

        partidos.append(
            {
                "fecha": fecha,
                "local": local,
                "visitante": visitante,
                "rival": rival,
                "pabellon": pabellon,
                "uid": uid
            }
        )

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
        "X-WR-TIMEZONE:Europe/Madrid"
    ]

    for partido in partidos:

        fecha = partido["fecha"]

        # Si la web pone 00:00,
        # consideramos que la hora todavía
        # no está confirmada.
        hora_no_confirmada = (
            fecha.hour == 0
            and fecha.minute == 0
        )

        titulo = (
            f"{partido['local']} - "
            f"{partido['visitante']}"
        )

        descripcion = (
            "Boca Priego FS Senior\\n"
            "3ª División Fútbol Sala - Grupo 18\\n"
            f"Local: {partido['local']}\\n"
            f"Visitante: {partido['visitante']}"
        )

        calendario.append(
            "BEGIN:VEVENT"
        )

        calendario.append(
            f"UID:{partido['uid']}@bocapriego"
        )

        calendario.append(
            "DTSTAMP:"
            + datetime.utcnow().strftime(
                "%Y%m%dT%H%M%SZ"
            )
        )

        if hora_no_confirmada:

            calendario.append(
                "DTSTART;VALUE=DATE:"
                + fecha.strftime(
                    "%Y%m%d"
                )
            )

            calendario.append(
                "DTEND;VALUE=DATE:"
                + (
                    fecha + timedelta(days=1)
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
        SALIDA,
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            "\r\n".join(
                calendario
            )
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
