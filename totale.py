import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conte
import speranza


def avvia_conversazione():
    """Esegue una conversazione iniziale tra Ministro e Presidente."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("Manca la variabile GEMINI_API_KEY. Non posso avviare la chat.")
        return None

    speranzessaggio = speranza.inizio(0.1).text
    print("\n=== MINISTRO ===")
    print(speranzessaggio)


    while (True):
        contessaggio = conte.negozia(speranzessaggio)

        print("\n=== PRESIDENTE ===\n")
        print(contessaggio["risposta_presidente"])


        speranzessaggio = speranza.rispondi(contessaggio["risposta_presidente"])

        print("\n=== MINISTRO ===\n")
        print(speranzessaggio)





if __name__ == "__main__":
    avvia_conversazione()
