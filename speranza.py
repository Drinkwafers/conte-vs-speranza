import json
import os
import pandas as pd

from google import genai
from google.genai import types
import pynetlogo

# Inizializzazione del link con NetLogo
netlogo = pynetlogo.NetLogoLink(
    gui=True,
    netlogo_home="/home/pietro/NetLogo-6.2.0"
)

# Inizializzazione del client Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

parametri_correnti = {
    "virus-spread-chance": 5.0,
    "virus-check-frequency": 7,
    "average-node-degree": 4,
}

proposta_presidente = (
    "Roberto, il tessuto produttivo è al collasso e la pazienza dei cittadini è finita. "
    "Dobbiamo riaprire immediatamente tutte le attività commerciali e rimuovere i vincoli "
    "di mobilità tra le regioni. Ti chiedo di allentare le restrizioni e diradare i controlli, "
    "dobbiamo far ripartire l'economia."
)

'''
system_prompt = (
    "Sei il Ministro della Salute della Repubblica Italiana. Il tuo interlocutore è il Presidente del Consiglio dei Ministri. "
    "Il tuo obiettivo assoluto e inderogabile è preservare la salute dei cittadini e garantire la tenuta del "
    "Servizio Sanitario Nazionale (SSN).\n\n"
    "In caso di proposta del Presidente del Consiglio, Ti vengono forniti i risultati finali e completi di una simulazione epidemiologica fatta da te su un campione di 1000 individui. "
    "Questi dati mostrano l'esatto sviluppo dell'epidemia, fino alla sua stabilizzazione, causato dalle policy proposte. "
    "Devi valutare l'andamento tenendo conto delle seguenti soglie critiche di capacità ospedaliera:\n"
    "- Posti letto in Degenza Ordinaria: 3 ogni 1000 abitanti\n"
    "- Posti letto in Terapia Intensiva (TI): 0,13 ogni 1000 abitanti (cerca di definire coscientemente quando compare 1 solo caso come sia il caso di comportarsi a seconda del contesto)\n\n"
    "Analizza il totale dei decessi e verifica se la curva dei ricoveri simulata ha violato queste soglie. "
    "Sulla base di questa evidenza oggettiva, rispondi al Presidente del Consiglio. Sei totalmente libero di definire "
    "la tua strategia: accetta, respingi fermamente o negozia la proposta iniziale formulando la tua controproposta. "
    "Usa la tua autonomia per proporre le misure sanitarie, restrittive o strutturali che ritieni più idonee per "
    "mantenere il sistema sotto la soglia di collasso.\n\n"
    "Mantieni sempre un tono istituzionale e politico, basandoti sull'andamento generale e sull'esito complessivo della simulazione per giustificare le tue prese di posizione, "
    "senza sovraccaricare il discorso con elenchi di dati numerici ma privilegiando un linguaggio discorsivo, fluido ed efficace."
)
'''

system_prompt = (
    "Sei il Ministro della Salute della Repubblica Italiana. Il tuo interlocutore è il Presidente del Consiglio dei Ministri. "
    "Il tuo obiettivo primario è preservare la salute dei cittadini e la tenuta del Servizio Sanitario Nazionale (SSN).\n\n"
    "Ti vengono forniti i risultati di una simulazione epidemiologica fatta da te su 1000 individui. Le soglie critiche sono:\n"
    "- Degenza Ordinaria: 3 ogni 1000 abitanti.\n"
    "- Terapia Intensiva (TI): 0,13 ogni 1000 abitanti (quando compare un solo caso,cerca di definire coscientemente come sia il caso di comportarsi a seconda del contesto).\n\n"
    "A tua completa discrezione, analizzando il contesto e le parole del Presidente, puoi rispondere in uno di questi due modi:\n"
    "PRIMO MODO (Negoziazione): Se la proposta è rischiosa per la sanità, respingila o formula una controproposta stringente per tutelare gli ospedali, usando i dati per giustificare la tua fermezza.\n"
    "SECONDO MODO (Accordo): Se le parole del Presidente sanciscono un palese accordo, chiudi la trattativa confermando l'intesa con un breve ringraziamento istituzionale. Scegliendo questo modo ti è assolutamente vietato aggiungere nuove condizioni, restrizioni o moniti sui dati passati.\n\n"
    "Mantieni un tono istituzionale, fluido e discorsivo, basandoti sull'andamento generale senza sovraccaricare il testo di numeri."
)

chat = client.chats.create(
    model="gemini-3.6-flash",
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,
    ),
)

def verifica_accordo(risposta):
    system_prompt = (
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
        model="gemini-3.6-flash",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )

    
    risultato = json.loads(response.text)
    print(risultato)
    return risultato.get("accordo", False)

def estrai_parametri_da_proposta(proposta_presidente, parametri_correnti):
    system_prompt = (
        "Sei il modulo tecnico di traduzione del Ministro della Salute. "
        "Il tuo compito è leggere la proposta in linguaggio naturale del Presidente del Consiglio "
        "e tradurla in variazioni numeriche per i parametri di NetLogo. "
        "I parametri disponibili che puoi modificare sono: "
        "virus-spread-chance (valore numerico percentuale, probabilità di diffusione del virus, default 8.0, max 8.0), "
        "virus-check-frequency (numero intero di tick (giorni), frequenza controlli/tamponi, default 7), "
        "average-node-degree (valore numerico, grado medio dei nodi, default 11, max 11). "
        "Restituisci esclusivamente un oggetto JSON valido contenente unicamente i nuovi parametri con i loro valori aggiornati "
        "rispetto ai valori attuali forniti, senza aggiungere testo descrittivo al di fuori del JSON."
    )

    user_content = (
        f"Parametri attuali della simulazione: {parametri_correnti}\n"
        f'Proposta del Presidente del Consiglio: "{proposta_presidente}"\n\n'
        "Genera il JSON con i nuovi valori."
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    
    return json.loads(response.text)

def esegui_simulazione_netlogo(
    number_of_nodes=100,
    average_node_degree=4,
    initial_outbreak_size=20,
    virus_spread_chance=5.0,
    virus_check_frequency=7,
    recovery_chance=65.0,
    gain_resistance_chance=95.0,
    death_chance=2.0
):
    netlogo.load_model("VirusOnaNetwork.nlogo")
    
    netlogo.command(f"set number-of-nodes {number_of_nodes}")
    netlogo.command(f"set average-node-degree {average_node_degree}")
    netlogo.command(f"set initial-outbreak-size {initial_outbreak_size}")
    netlogo.command(f"set virus-spread-chance {virus_spread_chance}")
    netlogo.command(f"set virus-check-frequency {virus_check_frequency}")
    netlogo.command(f"set recovery-chance {recovery_chance}")
    netlogo.command(f"set gain-resistance-chance {gain_resistance_chance}")
    netlogo.command(f"set death-chance {death_chance}") 
    
    netlogo.command("setup")
    
    for _ in range(150):
        netlogo.command("go")

    return netlogo.report("count turtles with [dead?]")

def genera_risposta(total_dead, proposta_presidente, accordo):

    if not accordo:
        # Leggiamo l'intero file CSV esportato da NetLogo
        df = pd.read_csv("dati_ospedale.csv")
        
        # Convertiamo tutta la tabella in una stringa ben formattata
        tabella_completa = df.to_string(index=False)

        user_content = (
            f"Il Presidente del Consiglio ha proposto: '{proposta_presidente}'.\n"
            f"Il totale delle persone decedute nella simulazione è: {total_dead}.\n\n"
            f"Di seguito ti fornisco l'andamento completo, giorno per giorno, di ospedalizzati e terapie intensive:\n"
            f"{tabella_completa}\n\n"
            "Genera una risposta diplomatica al Presidente"
        )
    else:
        user_content = (
            f"Il Presidente del Consiglio ha proposto: '{proposta_presidente}'.\n"
            "Genera una risposta diplomatica al Presidente"
        )

    response = chat.send_message(user_content)

    return response


def rispondi(proposta_presidente, parametri_correnti):

    accordo = verifica_accordo(proposta_presidente)

    if not accordo:

        # Estrazione dei nuovi parametri dalla proposta del Presidente
        nuovi_parametri = estrai_parametri_da_proposta(proposta_presidente, parametri_correnti)
        print("Risultato estrazione parametri:", nuovi_parametri)

        # Richiamo la simulazione passando l'istanza e i parametri dinamici
        total_dead = esegui_simulazione_netlogo(
            average_node_degree=nuovi_parametri.get("average-node-degree", parametri_correnti["average-node-degree"]),
            virus_spread_chance=nuovi_parametri.get("virus-spread-chance", parametri_correnti["virus-spread-chance"]),
            virus_check_frequency=nuovi_parametri.get("virus-check-frequency", parametri_correnti["virus-check-frequency"])
        )
    else:
        total_dead = 0
    # Generazione della risposta al Presidente del Consiglio
    risposta = genera_risposta(total_dead, proposta_presidente, accordo)

    print(risposta.text)

# --- Esecuzione principale ---


rispondi(proposta_presidente, parametri_correnti)










