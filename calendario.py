from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

URL = "https://astursala.es/tercera-division-futbol-sala-grupo-18-andalucia-oriental"

EQUIPO = "Boca"


def main():

    request = Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urlopen(request, timeout=30) as respuesta:
        html = respuesta.read()

    print("Tamaño de la página:", len(html))

    soup = BeautifulSoup(html, "html.parser")

    texto = soup.get_text("\n")

    lineas = [
        x.strip()
        for x in texto.splitlines()
        if x.strip()
    ]

    print()
    print("========== INFORMACIÓN BOCA ==========")

    encontradas = 0

    for i, linea in enumerate(lineas):

        if "Boca" in linea or "Priego" in linea:

            encontradas += 1

            print()
            print("----- BLOQUE", encontradas, "-----")

            inicio = max(0, i - 5)
            fin = min(len(lineas), i + 10)

            for j in range(inicio, fin):
                print(j, repr(lineas[j]))

            if encontradas >= 10:
                break

    print()
    print("Bloques encontrados:", encontradas)


if __name__ == "__main__":
    main()
