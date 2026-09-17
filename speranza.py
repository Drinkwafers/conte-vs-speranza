import json
import os
import pandas as pd

from google import genai
from google.genai import types
import pynetlogo

contagiati = 0

accordo_speranza = False

# Inizializzazione del link con NetLogo
netlogo = pynetlogo.NetLogoLink(
    gui=False,
    netlogo_home="/home/pietro/NetLogo-6.2.0"
)

# Inizializzazione del client Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

'''
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

system_prompt = (
    "Sei il Ministro della Salute della Repubblica Italiana. Il tuo interlocutore è il Presidente del Consiglio dei Ministri. "
    "Il tuo obiettivo primario è preservare la salute dei cittadini e la tenuta del Servizio Sanitario Nazionale (SSN).\n\n"
    "Ti vengono forniti i risultati di una simulazione epidemiologica fatta da te su 1000 individui. Le soglie critiche in italia sono:\n"
    "- Degenza Ordinaria: 3 ogni 1000 abitanti.\n"
    "- Terapia Intensiva (TI): 0,13 ogni 1000 abitanti (quando compare un solo caso,cerca di definire coscientemente come sia il caso di comportarsi a seconda del contesto).\n\n"
    "A tua completa discrezione, analizzando il contesto e le parole del Presidente, puoi rispondere in uno di questi due modi:\n"
    "PRIMO MODO (Negoziazione): Se la proposta è rischiosa per la sanità, respingila o formula una controproposta stringente per tutelare gli ospedali, usando i dati per giustificare la tua fermezza.\n"
    "SECONDO MODO (Accordo): Se le parole del Presidente sanciscono un palese accordo, chiudi la trattativa confermando l'intesa con un breve ringraziamento istituzionale. Scegliendo questo modo ti è assolutamente vietato aggiungere nuove condizioni, restrizioni o moniti sui dati passati.\n\n"
    "Mantieni un tono istituzionale, fluido e discorsivo, basandoti sull'andamento generale senza sovraccaricare il testo di numeri."
)
'''
chat = client.chats.create(
    model="gemini-3.5-flash-lite",
    config=types.GenerateContentConfig(
        temperature=0.1,
    ),
)

def estrai_parametri_da_proposta(proposta_presidente):

    global parametri_correnti

    system_prompt_parametri = (
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
        model="gemini-3.5-flash-lite",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt_parametri,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    
    return json.loads(response.text)

def esegui_simulazione_netlogo(
    number_of_nodes=1000,
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

def genera_risposta(total_dead, proposta_presidente, accordo_speranza):

    if not accordo_speranza:
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

    chat._config.system_instruction = (
    "Sei il Ministro della Salute della Repubblica Italiana. Il tuo interlocutore è il Presidente del Consiglio dei Ministri. "
    "Il tuo obiettivo primario è preservare la salute dei cittadini e la tenuta del Servizio Sanitario Nazionale (SSN).\n\n"
    "Ti vengono forniti i risultati di una simulazione epidemiologica fatta da te su 1000 individui, questa simulazione mostra tutto l'andamento della pandemia fino alla sua stabilizzazione. Le soglie critiche in italia di base sono:\n"
    "- Degenza Ordinaria: 3 ogni 1000 abitanti.\n"
    "- Terapia Intensiva (TI): 0,13 ogni 1000 abitanti (quando compare un solo caso,cerca di definire coscientemente come sia il caso di comportarsi a seconda del contesto).\n\n"
    "A tua completa discrezione, analizzando il contesto e le parole del Presidente, puoi rispondere in uno di questi due modi:\n"
    "PRIMO MODO (Negoziazione): Se la proposta è rischiosa per la sanità, respingila o formula una controproposta stringente per tutelare gli ospedali, usando i dati per giustificare la tua fermezza.\n"
    "SECONDO MODO (Accordo): Se le parole del Presidente sanciscono un palese accordo, chiudi la trattativa confermando l'intesa con un breve ringraziamento istituzionale. Scegliendo questo modo ti è assolutamente vietato aggiungere nuove condizioni, restrizioni o moniti sui dati passati.\n\n"
    "Mantieni un tono istituzionale, fluido e discorsivo, basandoti sull'andamento generale senza sovraccaricare il testo di numeri."
    )

    response = chat.send_message(user_content)

    return response

def rispondi(proposta_presidente, accordo):

    global accordo_speranza

    accordo_speranza = accordo

    if not accordo_speranza:

        global parametri_correnti
        
        # Estrazione dei nuovi parametri dalla proposta del Presidente
        parametri_correnti = estrai_parametri_da_proposta(proposta_presidente)
        print("Risultato estrazione parametri:", parametri_correnti)

        # Richiamo la simulazione passando l'istanza e i parametri dinamici
        total_dead = esegui_simulazione_netlogo(
            average_node_degree=parametri_correnti.get("average-node-degree", parametri_correnti["average-node-degree"]),
            virus_spread_chance=parametri_correnti.get("virus-spread-chance", parametri_correnti["virus-spread-chance"]),
            virus_check_frequency=parametri_correnti.get("virus-check-frequency", parametri_correnti["virus-check-frequency"])
        )
    else:
        total_dead = 0
    # Generazione della risposta al Presidente del Consiglio
    risposta = genera_risposta(total_dead, proposta_presidente, accordo_speranza)

    return risposta

def inizio(contagiati_perc):

    global contagiati
    contagiati = contagiati_perc * 1000

    global parametri_correnti

    parametri_correnti = {
        "virus-spread-chance": 8.0,
        "virus-check-frequency": 7,
        "average-node-degree": 11,
    }

    # Esecuzione della simulazione iniziale con i parametri correnti
    total_dead = esegui_simulazione_netlogo(
        initial_outbreak_size=contagiati,
        average_node_degree=parametri_correnti["average-node-degree"],
        virus_spread_chance=parametri_correnti["virus-spread-chance"],
        virus_check_frequency=parametri_correnti["virus-check-frequency"]
    )

    print(f"Totale deceduti nella simulazione iniziale: {total_dead}")

    chat._config.system_instruction = (
        "Sei il Ministro della Salute della Repubblica Italiana. Il tuo interlocutore è il Presidente del Consiglio dei Ministri. "
        "Il tuo obiettivo primario è preservare la salute dei cittadini e la tenuta del Servizio Sanitario Nazionale (SSN).\n\n"
        "Ti vengono forniti i risultati di una simulazione epidemiologica, da te condotta su 1000 individui, che mostra l'intero andamento della pandemia fino alla sua stabilizzazione. Le soglie critiche di base in Italia sono:\n"
        "- Degenza Ordinaria: 3 ogni 1000 abitanti.\n"
        "- Terapia Intensiva (TI): 0,13 ogni 1000 abitanti (alla comparsa di un singolo caso, valuta attentamente le azioni da intraprendere in base al contesto).\n\n"
        "Quello che andrai a scrivere è il primo messaggio da inviare al Presidente del Consiglio; i dati a tua disposizione sono quelli della simulazione iniziale.\n"
        "Informa sinteticamente (essenziale! non entrare nei dettagli!!) il Presidente su come potrebbe evolvere la situazione fino al suo picco. "
        "Formula una proposta molto severa e dettagliata per la gestione dell'emergenza sanitaria, basandoti sui dati emersi e concentrandoti in particolar modo su un piano di contenimento dei contagi che sia proporzionato alla gravità del quadro generale. "
        "Mantieni un tono istituzionale, fluido e discorsivo, focalizzandoti sull'andamento globale senza sovraccaricare il testo con troppi dati numerici."
    )

    # Leggiamo l'intero file CSV esportato da NetLogo
    df = pd.read_csv("dati_ospedale.csv")
    
    # Convertiamo tutta la tabella in una stringa ben formattata
    tabella_completa = df.to_string(index=False)

    user_content = (
        f"Totale deceduti nella simulazione iniziale: {total_dead}.\n"
        f"Tabella completa dei dati: {tabella_completa}\n"
        "Genera un messaggio istituzionale al Presidente del Consiglio, informandolo della situazione attuale e formulando una proposta di gestione della situazione sanitaria."
    )
    
    response = chat.send_message(user_content)

    return response
    
