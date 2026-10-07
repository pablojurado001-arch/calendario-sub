import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


URL = "https://astursala.es/tercera-division-futbol-sala-grupo-18-andalucia-oriental"
# SUGERENCIA: Si la web solo muestra una jornada aquí, busca el enlace al calendario completo 
# (suele ser algo como /calendario) y ponlo en esta variable.

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
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urlopen(request, timeout=30) as respuesta:
        return respuesta.read()


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


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

    return datetime(anio, mes, dia, hora, minuto)


def es_fecha(texto):
    return convertir_fecha(texto) is not None


def es_hora(texto):
    return re.match(
        r"^-\s*\d{1,2}:\d{2}\s*Horas$",
        texto,
        re.IGNORECASE
    ) is not None


def obtener_lineas():
    soup = BeautifulSoup(descargar_pagina(), "html.parser")
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
        if es_fecha(lineas[i]):
            fecha = convertir_fecha(lineas[i])
            siguiente = i + 1

            if siguiente < len(lineas) and es_hora(lineas[siguiente]):
                fecha = convertir_fecha(lineas[i], lineas[siguiente])
                posicion = i + 2
            else:
                posicion = i + 1

            if fecha is None:
                i += 1
                continue

            if posicion + 3 >= len(lineas):
                i += 1
                continue

            pabellon = lineas[posicion]
            local = lineas[posicion + 1]
            marcador = lineas[posicion + 2]
            visitante = lineas[posicion + 3]

            # Comprobamos si el equipo participa en el partido.
            # Se ha eliminado la restricción de que el marcador sea "Previa"
            # para capturar toda la temporada (resultados pasados o fechas por confirmar).
            if EQUIPO not in local and EQUIPO not in visitante:
                i += 1
                continue

            rival = visitante if EQUIPO in local else local

            # UID estable basado EXCLUSIVAMENTE en los equipos.
            # En liga regular, se enfrentan local vs visitante una sola vez.
            # Si el webmaster cambia la hora o el pabellón, la clave y el UID seguirán siendo idénticos,
            # lo que forzará al calendario a actualizar el evento existente en lugar de duplicarlo.
            clave = f"{local}|{visitante}"
            
            uid = hashlib.sha256(clave.encode("utf-8")).hexdigest()[:32]

            partidos.append({
                "fecha": fecha,
                "local": local,
                "visitante": visitante,
                "rival": rival,
                "pabellon": pabellon,
                "marcador": marcador, # Guardado por si quisieras añadirlo a la descripción
                "uid": uid
            })

            i = posicion + 4
            continue

        i += 1

    # Eliminar duplicados
    unicos = {partido["uid"]: partido for partido in partidos}
    partidos = list(unicos.values())
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
        hora_pendiente = (fecha.hour == 0 and fecha.minute == 0)

        titulo = f"{partido['local']} - {partido['visitante']}"
        descripcion = (
            "Boca Priego FS Senior\\n"
            "3ª División Fútbol Sala - Grupo 18\\n"
            f"Local: {partido['local']}\\n"
            f"Visitante: {partido['visitante']}"
        )
        
        # Añadir el resultado del partido en la descripción si ya se ha jugado
        if re.search(r"\d+", partido["marcador"]): 
            descripcion += f"\\nResultado: {partido['marcador']}"

        calendario.append("BEGIN:VEVENT")
        calendario.append(f"UID:{partido['uid']}@bocapriego")
        calendario.append("DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

        if hora_pendiente:
            # Solo fecha
            calendario.append("DTSTART;VALUE=DATE:" + fecha.strftime("%Y%m%d"))
            calendario.append("DTEND;VALUE=DATE:" + (fecha + timedelta(days=1)).strftime("%Y%m%d"))
            titulo += " - HORA PENDIENTE"
        else:
            # Fecha con hora
            fin = fecha + timedelta(hours=2)
            calendario.append("DTSTART;TZID=Europe/Madrid:" + fecha.strftime("%Y%m%dT%H%M%S"))
            calendario.append("DTEND;TZID=Europe/Madrid:" + fin.strftime("%Y%m%dT%H%M%S"))

        calendario.append("SUMMARY:" + escapar(titulo))
        calendario.append("LOCATION:" + escapar(partido["pabellon"]))
        calendario.append("DESCRIPTION:" + escapar(descripcion))
        calendario.append("END:VEVENT")

    calendario.append("END:VCALENDAR")

    with open(ARCHIVO, "w", encoding="utf-8") as archivo:
        archivo.write("\r\n".join(calendario) + "\r\n")


def main():
    partidos = obtener_partidos()

    print("\n========================================")
    print("PARTIDOS ENCONTRADOS:", len(partidos))
    print("========================================")

    for partido in partidos:
        fecha = partido["fecha"]
        hora = "HORA PENDIENTE" if (fecha.hour == 0 and fecha.minute == 0) else fecha.strftime("%H:%M")

        print(
            fecha.strftime("%d/%m/%Y"),
            "|", hora, "|",
            partido["local"], "vs", partido["visitante"],
            "|", partido["pabellon"]
        )

    print("========================================")
    generar_ics(partidos)
    print("CALENDARIO GENERADO:", ARCHIVO)
    print("========================================")

if __name__ == "__main__":
    main()
