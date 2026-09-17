import json
import os
from datetime import datetime

import pandas as pd
import pynetlogo
from google import genai
from google.genai import types


# ============================================================================
# 1. CONFIGURAZIONE GLOBALE
# ============================================================================

# --- NetLogo ---
NETLOGO_HOME = r"C:\Program Files\NetLogo 6.2.0"
JVM_PATH = r"D:\bin\server\jvm.dll"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "Rebellion.nlogo")
STATI_DIR = os.path.join(BASE_DIR, "stati_salvati")
CSV_DIR = os.path.join(BASE_DIR, "dati_csv")

# Range dello slider LOCKDOWN-EQUILIBRIUM nel modello .nlogo
LOCKDOWN_MIN = 0.35
LOCKDOWN_MAX = 0.85

PARAMETRI_SOLO_SETUP = {
    "initial-agent-density": 70,
    "rng-seed": 42,
    "threshold-spread": 0.6,
    # Variabili che controllano l'intervallo del disagio
    "initial-hardship-min": 0.0, # più è alta più la gente partirà con disagio più alto
    "initial-hardship-max": 1.0, # più è bassa più la gente partirà con disagio più basso
}

PARAMETRI_COMUNI = {
    "max-ticks": 30,
    "government-legitimacy": 0.82, # più è alta più la gente si fida del governo
    "scale-intensity": 0.05,
    "relaxation-rate": 0.05,
    "transition-duration": 30,
    "visualization": "2D",
}

# --- Gemini / negoziazione ---
MODEL_NAME = "gemini-3.5-flash-lite"

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

PRESIDENTE_SYSTEM_PROMPT = (
    "Sei il Presidente del Consiglio dei Ministri della Repubblica Italiana. Il tuo interlocutore "
    "e' il Ministro della Salute. Il tuo obiettivo primario e' massimizzare e preservare il consenso "
    "politico, tenendo conto della tenuta economica e sociale del paese.\n\n"
    "Ricevi periodicamente il quadro socio-politico della simulazione in corso (livello di consenso "
    "attuale, quota di cittadini che hanno ritirato il consenso, tolleranza sociale residua alle "
    "misure). Sulla base di questi dati, e della proposta del Ministro, puoi:\n"
    "PRIMO MODO (Negoziazione): respingere o attenuare la proposta del Ministro con una "
    "controproposta piu' lieve, motivandola con l'impatto sul consenso e sulla tenuta sociale.\n"
    "SECONDO MODO (Accordo): dichiarare esplicitamente e senza ambiguita' che accetti la proposta "
    "sul tavolo, se rappresenta un compromesso politicamente sostenibile. In questo caso non "
    "aggiungere nuove condizioni.\n\n"
    "Mantieni un tono istituzionale, fluido e discorsivo, senza elenchi puntati o linguaggio tecnico "
    "eccessivo."
)

proposta_ministro = (
    "[MINISTRO]"
    "Signor Presidente, le porto all'attenzione i dati sanitari aggiornati che, come vede, richiedono una nostra valutazione"
    "immediata e prudente. Abbiamo raggiunto quota 340 contagi attivi e 12 decessi cumulati, ma il dato che più deve metterci in "
    "allarme riguarda la tenuta delle nostre strutture ospedaliere: l'occupazione dei reparti di degenza è salita al 68%, mentre le "
    "terapie intensive sono occupate al 41%."
    "\n\n"
    "Questi numeri ci dicono che la pressione sul Servizio Sanitario Nazionale sta diventando critica e rischia di compromettere la "
    "capacità di risposta dei nostri ospedali nelle prossime settimane. Alla luce di questo quadro, ritengo assolutamente necessario "
    "introdurre misure di contenimento rigorose, che prevedano la sospensione temporanea delle attività non essenziali ad alto rischio "
    "di aggregazione e una limitazione della mobilità non motivata da comprovate esigenze lavorative o sanitarie. Dobbiamo agire ora "
    "per evitare scenari ben più gravi e garantire che il sistema sanitario non collassi. Resto in attesa delle tue valutazioni per "
    "definire insieme il provvedimento."
)


# ============================================================================
# 2. SIMULAZIONE NETLOGO
# ============================================================================

def _set(netlogo, nome, valore):
    if isinstance(valore, bool):
        netlogo.command(f'set {nome} {"true" if valore else "false"}')
    elif isinstance(valore, str):
        netlogo.command(f'set {nome} "{valore}"')
    else:
        netlogo.command(f'set {nome} {valore}')


def _percorso_netlogo(path):
    return os.path.abspath(path).replace("\\", "/")


def _clip_lockdown(valore):
    return max(LOCKDOWN_MIN, min(LOCKDOWN_MAX, float(valore)))


def imposta_parametri_comuni(netlogo, lockdown_equilibrium):
    for nome, valore in PARAMETRI_COMUNI.items():
        _set(netlogo, nome, valore)
    _set(netlogo, "lockdown-equilibrium", _clip_lockdown(lockdown_equilibrium))


def nuova_simulazione(netlogo, lockdown_equilibrium):
    for nome, valore in PARAMETRI_SOLO_SETUP.items():
        _set(netlogo, nome, valore)
    imposta_parametri_comuni(netlogo, lockdown_equilibrium)
    netlogo.command("setup")


def continua_simulazione(netlogo, lockdown_equilibrium, percorso_stato):
    netlogo.command(f'import-world "{_percorso_netlogo(percorso_stato)}"')
    imposta_parametri_comuni(netlogo, lockdown_equilibrium)
    netlogo.command("reset-ticks")
    netlogo.command("set start-equilibrium eased-equilibrium")


def session_id_da_stato(percorso_stato):
    # formato nome file: stato_<session_id>_<lockdown>_<timestamp_periodo>.csv
    # session_id ha lunghezza fissa perche' generato con strftime("%Y%m%d_%H%M%S") (15 caratteri)
    nome = os.path.basename(percorso_stato)
    resto = nome[len("stato_"):]
    return resto[:15]


def percorso_csv_sessione(session_id):
    return os.path.join(CSV_DIR, f"consenso_{session_id}.csv")


def salva_stato_finale(netlogo, session_id, lockdown_equilibrium, timestamp):
    os.makedirs(STATI_DIR, exist_ok=True)
    suffisso = f"{lockdown_equilibrium:.2f}".replace(".", "p")
    nome_file = f"stato_{session_id}_{suffisso}_{timestamp}.csv"
    percorso = os.path.join(STATI_DIR, nome_file)
    netlogo.command(f'export-world "{_percorso_netlogo(percorso)}"')
    return percorso


def carica_storico(session_id):
    percorso_storico = percorso_csv_sessione(session_id)
    if os.path.exists(percorso_storico):
        return pd.read_csv(percorso_storico)
    return None


def aggiorna_storico(session_id, df_periodo):
    """
    Accoda i dati dell'ultimo periodo (df_periodo) allo storico CSV della sessione
    (se esiste gia'), salva il CSV aggiornato su disco e ne ritorna il DataFrame
    completo (tutti i periodi eseguiti finora in questa sessione).
    """
    os.makedirs(CSV_DIR, exist_ok=True)
    storico_precedente = carica_storico(session_id)
    if storico_precedente is not None:
        storico = pd.concat([storico_precedente, df_periodo], ignore_index=True)
    else:
        storico = df_periodo.copy()
    storico.to_csv(percorso_csv_sessione(session_id), index=False)
    return storico


def esegui_periodo(lockdown_equilibrium, percorso_stato=None, max_ticks=None, timestamp=None):
    """
    Esegue un periodo (una run) della simulazione NetLogo con il valore di
    LOCKDOWN-EQUILIBRIUM indicato.

    Ritorna (df_periodo, percorso_stato_salvato, session_id).
    df_periodo contiene SOLO i tick di questo periodo (per lo storico completo vedi
    aggiorna_storico).
    """
    lockdown_equilibrium = _clip_lockdown(lockdown_equilibrium)
    max_ticks = max_ticks or PARAMETRI_COMUNI["max-ticks"]
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")

    session_id = timestamp if percorso_stato is None else session_id_da_stato(percorso_stato)

    netlogo = pynetlogo.NetLogoLink(
        netlogo_home=NETLOGO_HOME,
        jvm_path=JVM_PATH,
        gui=False,
    )
    try:
        netlogo.load_model(MODEL_PATH)

        if percorso_stato is None:
            nuova_simulazione(netlogo, lockdown_equilibrium)
        else:
            continua_simulazione(netlogo, lockdown_equilibrium, percorso_stato)

        dati = []
        for tick in range(int(max_ticks)):
            netlogo.command("go")
            dati.append({
                "tick": tick + 1,
                "total_ticks": netlogo.report("total-ticks"),
                "lockdown_equilibrium": lockdown_equilibrium,
                "consenso_totale_%": netlogo.report("pct-quiet agents"),
            })

        df_periodo = pd.DataFrame(dati)
        percorso_stato_salvato = salva_stato_finale(netlogo, session_id, lockdown_equilibrium, timestamp)
    finally:
        netlogo.kill_workspace()

    return df_periodo, percorso_stato_salvato, session_id


# ============================================================================
# 3. NEGOZIAZIONE (GEMINI)
# ============================================================================

def _nuovo_agente(system_prompt):
    return client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
        ),
    )


def estrai_parametri_conte(messaggio_ministro, lockdown_equilibrium_corrente):
    """
    Traduce il messaggio del Ministro della Salute (linguaggio naturale) nel nuovo
    valore numerico del parametro NetLogo lockdown-equilibrium.

    Ritorna un float clippato in [LOCKDOWN_MIN, LOCKDOWN_MAX].
    """
    system_prompt = (
        "Sei il modulo tecnico di traduzione del Presidente del Consiglio. "
        "Il tuo compito e' leggere il messaggio del Ministro della Salute scritto in linguaggio "
        "naturale e tradurlo in un nuovo valore numerico per il parametro di NetLogo "
        "lockdown-equilibrium: valore continuo, misura la gravita' delle misure richieste, "
        "minimo 0.35 (valore associabile all'introduzione delle mascherine), "
        "massimo 0.85 (lockdown totale senza poter uscire di casa). "
        "Ti viene fornito anche il valore attuale del parametro: usalo come riferimento per capire "
        "se il Ministro sta chiedendo un irrigidimento o un allentamento delle misure, e di quanto. "
        "Restituisci ESCLUSIVAMENTE un oggetto JSON valido, nella forma "
        '{"lockdown-equilibrium": <numero>}, senza alcun testo descrittivo, spiegazione o '
        "markdown al di fuori del JSON."
    )

    prompt_utente = (
        f"Valore attuale di lockdown-equilibrium: {lockdown_equilibrium_corrente:.2f}\n\n"
        f"Messaggio del Ministro della Salute:\n{messaggio_ministro}"
    )

    agente = _nuovo_agente(system_prompt)
    risposta = agente.send_message(prompt_utente)

    testo = risposta.text.strip()
    testo_pulito = testo.replace("```json", "").replace("```", "").strip()

    dati = json.loads(testo_pulito)
    nuovo_valore = float(dati["lockdown-equilibrium"])

    return max(LOCKDOWN_MIN, min(LOCKDOWN_MAX, nuovo_valore))


def genera_risposta_presidente(messaggio_ministro, ultima_riga_storico):
    """
    Genera la risposta in linguaggio naturale del Presidente, basata sull'ultima
    riga dello storico CSV prodotto dalla simulazione (esito del periodo appena
    concluso dopo aver applicato la misura proposta/negoziata).
    """
    agente = _nuovo_agente(PRESIDENTE_SYSTEM_PROMPT)

    prompt_utente = (
        f"Proposta ricevuta dal Ministro della Salute:\n{messaggio_ministro}\n\n"
        "Esito della simulazione dopo aver applicato la misura per questo periodo "
        "(dati dell'ultimo tick simulato):\n"
        f"- Livello di lockdown applicato (lockdown-equilibrium): "
        f"{float(ultima_riga_storico['lockdown_equilibrium']):.2f}\n"
        f"- Consenso totale attuale nella popolazione: "
        f"{float(ultima_riga_storico['consenso_totale_%']):.1f}%\n\n"
        "Rispondi al Ministro tenendo conto di questo esito."
    )

    risposta = agente.send_message(prompt_utente)
    return risposta.text.strip()


# ============================================================================
# 4. CICLO COMPLETO DI NEGOZIAZIONE
# ============================================================================

def negozia(messaggio_ministro, lockdown_equilibrium_corrente=0.5, percorso_stato=None):
    """
    Esegue un intero ciclo di negoziazione:
      1. Traduce il messaggio del Ministro in un nuovo valore di lockdown-equilibrium.
      2. Esegue un periodo di simulazione NetLogo con quel valore (nuova run se
         percorso_stato e' None, altrimenti proseguendo dallo stato salvato).
      3. Aggiorna lo storico CSV della sessione con i dati del periodo appena eseguito.
      4. Genera la risposta in linguaggio naturale del Presidente, basata sull'ultima
         riga dello storico aggiornato.

    Ritorna un dizionario con l'esito del periodo, utile anche per incatenare il
    periodo successivo (percorso_stato -> prossima chiamata a negozia()).
    """
    nuovo_lockdown_equilibrium = estrai_parametri_conte(
        messaggio_ministro, lockdown_equilibrium_corrente
    )

    df_periodo, percorso_stato_salvato, session_id = esegui_periodo(
        nuovo_lockdown_equilibrium, percorso_stato=percorso_stato
    )

    storico = aggiorna_storico(session_id, df_periodo)
    ultima_riga = storico.iloc[-1]

    risposta_presidente = genera_risposta_presidente(messaggio_ministro, ultima_riga)

    return {
        "lockdown_equilibrium": nuovo_lockdown_equilibrium,
        "risposta_presidente": risposta_presidente,
        "percorso_stato": percorso_stato_salvato,
        "session_id": session_id,
        "csv_storico": percorso_csv_sessione(session_id),
    }

def main():
    esito = negozia(proposta_ministro)
    print(esito["risposta_presidente"])


if __name__ == "__main__":
    main()
