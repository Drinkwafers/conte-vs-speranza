import os
import sys
import json

from google import genai
from google.genai import types

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.rule import Rule

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conte
import speranza

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
console = Console()

# Stile grafico per i due interlocutori
STILE_PRESIDENTE = "bold white on blue"
STILE_MINISTRO = "bold white on dark_green"
STILE_INFO = "dim italic"


def stampa_messaggio(titolo, testo, stile_titolo):
    """Mostra il messaggio di un interlocutore in un pannello colorato."""
    console.print()
    console.print(Panel(
        testo.strip(),
        title=f"[{stile_titolo}] {titolo} [/{stile_titolo}]",
        title_align="left",
        border_style=stile_titolo.split(" on ")[-1] if " on " in stile_titolo else stile_titolo,
        padding=(1, 2),
    ))


def stampa_esito_accordo(chi, accordo):
    """Mostra in modo compatto se un interlocutore ha dichiarato l'accordo."""
    simbolo = "✅ ACCORDO RAGGIUNTO" if accordo else "🔄 trattativa ancora aperta"
    colore = "green" if accordo else "yellow"
    console.print(f"  [{colore}]{simbolo}[/{colore}] — {chi}", style=STILE_INFO)


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

    with Status("[dim]Valutazione dell'esito in corso...[/dim]", console=console, spinner="dots"):
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
    return risultato.get("accordo", False)



def avvia_conversazione(contagiati, minimo, massimo, on_message=None, on_status=None):
    """
    Esegue una conversazione iniziale tra Ministro e Presidente.

    on_message(speaker, testo, accordo=None): chiamato ad ogni messaggio prodotto
        (speaker è "ministro" o "presidente"; accordo è True/False/None quando
        non ancora valutato). Se non fornito, l'output resta solo su console.
    on_status(testo): chiamato per aggiornamenti di stato brevi ("in corso...").
    """
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]Manca la variabile GEMINI_API_KEY. Non posso avviare la chat.[/bold red]")
        return None

    def notifica_stato(testo):
        if on_status:
            on_status(testo)

    def notifica_messaggio(speaker, titolo, testo, stile, accordo=None):
        stampa_messaggio(titolo, testo, stile)
        if on_message:
            on_message(speaker, testo, accordo)

    console.print(Rule("[bold]Negoziazione Governo — Ministero della Salute[/bold]", style="cyan"))

    notifica_stato("Il Ministro prepara il quadro iniziale...")
    with Status("[dim]Il Ministro prepara il quadro iniziale...[/dim]", console=console, spinner="dots"):
        speranzessaggio = speranza.inizio(contagiati)

    notifica_messaggio("ministro", "MINISTRO DELLA SALUTE", speranzessaggio.text, STILE_MINISTRO)

    contaccordo = False
    speranzaccordo = False
    numero_round = 0

    while (not contaccordo) or (not speranzaccordo):
        numero_round += 1
        console.print(Rule(f"[dim]Round {numero_round}[/dim]", style="grey50"))
        notifica_stato(f"Round {numero_round} — il Presidente valuta la proposta...")

        with Status("[dim]Il Presidente valuta la proposta...[/dim]", console=console, spinner="dots"):
            contessaggio = conte.negozia(speranzessaggio.text, minimo, massimo)

        contaccordo = verifica_accordo(contessaggio["risposta_presidente"])
        notifica_messaggio(
            "presidente", "PRESIDENTE DEL CONSIGLIO",
            contessaggio["risposta_presidente"], STILE_PRESIDENTE, contaccordo,
        )
        stampa_esito_accordo("Presidente", contaccordo)

        notifica_stato("Il Ministro prepara la risposta...")
        with Status("[dim]Il Ministro prepara la risposta...[/dim]", console=console, spinner="dots"):
            speranzessaggio = speranza.rispondi(contessaggio["risposta_presidente"], contaccordo)

        speranzaccordo = verifica_accordo(speranzessaggio.text)
        notifica_messaggio(
            "ministro", "MINISTRO DELLA SALUTE",
            speranzessaggio.text, STILE_MINISTRO, speranzaccordo,
        )
        stampa_esito_accordo("Ministro", speranzaccordo)

    console.print()
    console.print(Rule("[bold green]CONVERSAZIONE TERMINATA — Accordo raggiunto[/bold green]", style="green"))
    console.print(f"[dim]Round totali: {numero_round}[/dim]")
    notifica_stato(f"Conversazione terminata — accordo raggiunto dopo {numero_round} round.")


if __name__ == "__main__":
    avvia_conversazione(contagiati=0.1, minimo=0, massimo=1)