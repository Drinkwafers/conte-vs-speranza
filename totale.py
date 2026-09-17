import os
import sys
import json

from google import genai
from google.genai import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conte
import speranza

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def verifica_accordo(risposta):
    system_prompt_verifica = (
        "Sei un valutatore imparziale di una trattazione politica tra il Presidente del Consiglio e il Ministro della Salute. "
        "Analizza l'ultima risposta fornita."
        "Devi determinare se le parti hanno raggiunto un accordo definitivo o se la trattazione è ancora aperta/rifiutata. "
        "Restituisci esclusivamente un oggetto JSON con una chiave booleana 'accordo' (true se c'è accordo, false altrimenti) "
    )
    
    user_content = (
        f"Risposta del Ministro della Salute: \"{risposta}\"\n\n"
        "C'è stato un accordo?"
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt_verifica,
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )

    
    risultato = json.loads(response.text)
    print(risultato)
    return risultato.get("accordo", False)


def avvia_conversazione(contagiati):
    """Esegue una conversazione iniziale tra Ministro e Presidente."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("Manca la variabile GEMINI_API_KEY. Non posso avviare la chat.")
        return None

    speranzessaggio = speranza.inizio(contagiati)

    print("\n=== MINISTRO ===")
    print(speranzessaggio.text)

    contaccordo = False
    speranzaccordo = False

    while ((not contaccordo) or (not speranzaccordo)):
        contessaggio = conte.negozia(speranzessaggio.text, minimo=0, massimo=1)

        print("\n=== PRESIDENTE ===\n")
        print(contessaggio["risposta_presidente"])

        contaccordo = verifica_accordo(contessaggio["risposta_presidente"])
        print(f"Accordo iniziale: {contaccordo}")

        speranzessaggio = speranza.rispondi(contessaggio["risposta_presidente"], contaccordo)

        print("\n=== MINISTRO ===\n")
        print(speranzessaggio.text)

        speranzaccordo = verifica_accordo(speranzessaggio.text)
        print(f"Accordo Ministro: {speranzaccordo}")

    print("\n\n\n=== CONVERSAZIONE TERMINATA ===")

if __name__ == "__main__":
    avvia_conversazione(0.1)
