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


def percorso_csv_sessione(session_id):
    return os.path.join(CSV_DIR, f"consenso_{session_id}.csv")


def carica_storico(session_id):
    percorso_storico = percorso_csv_sessione(session_id)
    if os.path.exists(percorso_storico):
        return pd.read_csv(percorso_storico)
    return None


def esegui_periodo(lockdown_equilibrium, session_id=None, max_ticks=None):
    """
    Esegue un periodo (una run) della simulazione NetLogo con il valore di
    LOCKDOWN-EQUILIBRIUM indicato. Ogni chiamata avvia una simulazione da zero
    (nessun salvataggio/caricamento di stato tra periodi).
    """
    lockdown_equilibrium = _clip_lockdown(lockdown_equilibrium)
    max_ticks = max_ticks or PARAMETRI_COMUNI["max-ticks"]
    session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    netlogo = pynetlogo.NetLogoLink(
        netlogo_home=NETLOGO_HOME,
        jvm_path=JVM_PATH,
        gui=False,
    )
    try:
        netlogo.load_model(MODEL_PATH)
        nuova_simulazione(netlogo, lockdown_equilibrium)

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
    finally:
        netlogo.kill_workspace()

    return df_periodo, session_id


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

def negozia(messaggio_ministro, lockdown_equilibrium_corrente=0.5, session_id=None):

    nuovo_lockdown_equilibrium = estrai_parametri_conte(
        messaggio_ministro, lockdown_equilibrium_corrente
    )

    df_periodo, session_id = esegui_periodo(
        nuovo_lockdown_equilibrium, session_id=session_id
    )

    ultima_riga = df_periodo.iloc[-1]

    risposta_presidente = genera_risposta_presidente(messaggio_ministro, ultima_riga)

    return {
        "lockdown_equilibrium": nuovo_lockdown_equilibrium,
        "risposta_presidente": risposta_presidente,
        "session_id": session_id,
        "csv_storico": percorso_csv_sessione(session_id),
    }
