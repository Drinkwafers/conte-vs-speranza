import glob
import os
import sys
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import pynetlogo

NETLOGO_HOME = r"C:\Program Files\NetLogo 6.2.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "Covid19_Consensi.nlogo")
STATI_DIR = os.path.join(BASE_DIR, "stati_salvati")
GRAFICI_DIR = os.path.join(BASE_DIR, "grafici")
CSV_DIR = os.path.join(BASE_DIR, "dati_csv")

RESTRIZIONI = {
    "1": "Nessuna restrizione",
    "2": "Lockdown parziale",
    "3": "Lockdown totale",
}

PARAMETRI_SOLO_SETUP = {
    "initial-agent-density": 70,
    "vision": 7,
    "rng-seed": 42,
    "threshold-spread": 0.6,
}

PARAMETRI_COMUNI = {
    "max-ticks": 30,
    "government-legitimacy": 0.82,
    "movement?": True,
    "scale-intensity": 0.05,
    "relaxation-rate": 0.05,
    "transition-duration": 30,
    "visualization": "2D",
}

def _set(netlogo, nome, valore):
    if isinstance(valore, bool):
        netlogo.command(f'set {nome} {"true" if valore else "false"}')
    elif isinstance(valore, str):
        netlogo.command(f'set {nome} "{valore}"')
    else:
        netlogo.command(f'set {nome} {valore}')


def _percorso_netlogo(path):
    return os.path.abspath(path).replace("\\", "/")


def scegli_modalita():
    print("\nCome vuoi avviare la simulazione?")
    print("  1) Nuova simulazione da zero (SETUP)")
    print("  2) Continua da uno stato salvato in precedenza (IMPORT-WORLD)")
    while True:
        scelta = input("Inserisci il numero (1-2): ").strip()
        if scelta in ("1", "2"):
            return scelta
        print("Scelta non valida, riprova.")


def scegli_restrizione():
    print("\nScegli la restrizione COVID-19 da simulare in questo periodo:")
    for key, val in RESTRIZIONI.items():
        print(f"  {key}) {val}")
    while True:
        scelta = input("Inserisci il numero (1-3): ").strip()
        if scelta in RESTRIZIONI:
            return RESTRIZIONI[scelta]
        print("Scelta non valida, riprova.")


def scegli_stato_da_caricare():
    os.makedirs(STATI_DIR, exist_ok=True)
    candidati = sorted(glob.glob(os.path.join(STATI_DIR, "*.csv")))
    if not candidati:
        sys.exit(
            f"Nessuno stato salvato trovato in:\n  {STATI_DIR}\n"
            "Esegui prima una simulazione da zero (opzione 1) per crearne uno."
        )
    print("\nStati salvati disponibili:")
    for i, path in enumerate(candidati, start=1):
        print(f"  {i}) {os.path.basename(path)}")
    while True:
        scelta = input(f"Inserisci il numero (1-{len(candidati)}): ").strip()
        if scelta.isdigit() and 1 <= int(scelta) <= len(candidati):
            return candidati[int(scelta) - 1]
        print("Scelta non valida, riprova.")


def imposta_parametri_comuni(netlogo, lockdown_config):
    for nome, valore in PARAMETRI_COMUNI.items():
        _set(netlogo, nome, valore)
    _set(netlogo, "lockdown-config", lockdown_config)


def nuova_simulazione(netlogo, lockdown_config):
    for nome, valore in PARAMETRI_SOLO_SETUP.items():
        _set(netlogo, nome, valore)
    imposta_parametri_comuni(netlogo, lockdown_config)
    netlogo.command("setup")


def continua_simulazione(netlogo, lockdown_config, percorso_stato):
    netlogo.command(f'import-world "{_percorso_netlogo(percorso_stato)}"')
    imposta_parametri_comuni(netlogo, lockdown_config)
    netlogo.command("reset-ticks")
    netlogo.command("set start-equilibrium eased-equilibrium")
    netlogo.command("set-transition-scale")


def session_id_da_stato(percorso_stato):
    # formato nome file: stato_<session_id>_<config>_<timestamp_periodo>.csv
    # session_id ha lunghezza fissa perche' generato con strftime("%Y%m%d_%H%M%S") (15 caratteri)
    nome = os.path.basename(percorso_stato)
    resto = nome[len("stato_"):]
    return resto[:15]


def percorso_csv_sessione(session_id):
    return os.path.join(CSV_DIR, f"consenso_{session_id}.csv")


def percorso_grafico_sessione(session_id):
    return os.path.join(GRAFICI_DIR, f"consenso_{session_id}.png")


def salva_stato_finale(netlogo, session_id, lockdown_config, timestamp):
    os.makedirs(STATI_DIR, exist_ok=True)
    suffisso = lockdown_config.replace(" ", "_")
    nome_file = f"stato_{session_id}_{suffisso}_{timestamp}.csv"
    percorso = os.path.join(STATI_DIR, nome_file)
    netlogo.command(f'export-world "{_percorso_netlogo(percorso)}"')
    print(f"\nStato finale salvato in: {percorso}")
    print("(potrai usarlo come punto di partenza nella prossima esecuzione)")
    return percorso


def carica_storico(session_id):
    percorso_storico = percorso_csv_sessione(session_id)
    if os.path.exists(percorso_storico):
        return pd.read_csv(percorso_storico)
    return None


def esegui_simulazione(modalita, lockdown_config, max_ticks, timestamp, percorso_stato=None):
    # il session_id identifica l'intera catena di run collegate tra loro con IMPORT-WORLD:
    # una nuova simulazione (SETUP) apre una nuova catena e usa il proprio timestamp come id;
    # una continuazione eredita il session_id dello stato da cui riparte, qualunque sia
    # la configurazione di lockdown scelta in questo periodo
    session_id = timestamp if modalita == "1" else session_id_da_stato(percorso_stato)

    netlogo = pynetlogo.NetLogoLink(
        netlogo_home=NETLOGO_HOME,
        jvm_path=JVM_PATH,
        gui=False,
    )
    netlogo.load_model(MODEL_PATH)

    if modalita == "1":
        nuova_simulazione(netlogo, lockdown_config)
    else:
        continua_simulazione(netlogo, lockdown_config, percorso_stato)

    dati = []
    for tick in range(int(max_ticks)):
        netlogo.command("go")
        dati.append({
            "tick": tick + 1,
            "total_ticks": netlogo.report("total-ticks"),
            "lockdown_config": lockdown_config,
            "lockdown_level": netlogo.report("lockdown-level"),
            "consenso_totale_%": netlogo.report("pct-quiet agents"),
        })

    df = pd.DataFrame(dati)
    if modalita == "2":
        storico = carica_storico(session_id)
        if storico is not None:
            df = pd.concat([storico, df], ignore_index=True)

    percorso_salvato = salva_stato_finale(netlogo, session_id, lockdown_config, timestamp)

    netlogo.kill_workspace()
    return df, percorso_salvato, session_id


def salva_e_mostra(df, lockdown_config, session_id, era_continuazione):
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(GRAFICI_DIR, exist_ok=True)

    nome_csv = percorso_csv_sessione(session_id)
    df.to_csv(nome_csv, index=False)
    print(f"Dati {'aggiornati' if era_continuazione else 'salvati'} in: {nome_csv}")

    ultima = df.iloc[-1]
    print("\nRiepilogo finale:")
    print(f"  Configurazione:            {lockdown_config}")
    print(f"  Livello di lockdown:       {int(ultima['lockdown_level'])}")
    print(f"  Consenso totale finale:    {ultima['consenso_totale_%']:.1f}%")

    plt.figure(figsize=(8, 5))
    ax = plt.gca()
    ax.plot(df["total_ticks"], df["consenso_totale_%"], label="Consenso totale", color="green")
    ax.axhline(50, color="black", linestyle=":", label="Soglia 50%")

    # ogni periodo/run inizia dove la colonna "tick" (che si resetta ad ogni run)
    # torna a 1, a differenza di "total_ticks" che invece e' sempre progressiva.
    # uso get_xaxis_transform per posizionare le etichette a un'altezza relativa
    # fissa (coordinate dati sull'asse x, frazione degli assi sull'asse y), cosi'
    # restano sempre dentro il grafico senza toccare il titolo
    trans = ax.get_xaxis_transform()
    inizi_periodo = df.index[df["tick"] == 1].tolist()
    for i, idx in enumerate(inizi_periodo):
        x_inizio = df.loc[idx, "total_ticks"]
        if i > 0:
            # separatore tra il periodo precedente e questo
            ax.axvline(x_inizio - 0.5, color="gray", linestyle="--", linewidth=1, alpha=0.7)
        ax.text(
            x_inizio, 0.97, df.loc[idx, "lockdown_config"], transform=trans,
            rotation=90, fontsize=8, color="dimgray", ha="left", va="top",
        )

    ax.set_ylim(0, 105)
    ax.set_xlabel("Tick totali")
    ax.set_ylabel("% cittadini che sostengono il governo")
    ax.set_title("Andamento del consenso", pad=15)
    ax.legend(loc="lower left")
    plt.tight_layout()

    nome_grafico = percorso_grafico_sessione(session_id)
    plt.savefig(nome_grafico)
    print(f"Grafico {'aggiornato' if era_continuazione else 'salvato'} in: {nome_grafico}")
    plt.show()


def main():
    modalita = scegli_modalita()
    lockdown_config = scegli_restrizione()
    percorso_stato = scegli_stato_da_caricare() if modalita == "2" else None
    max_ticks = PARAMETRI_COMUNI["max-ticks"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\nAvvio simulazione con: {lockdown_config} ({max_ticks} tick)...")
    df, _, session_id = esegui_simulazione(modalita, lockdown_config, max_ticks, timestamp, percorso_stato)
    salva_e_mostra(df, lockdown_config, session_id, era_continuazione=(modalita == "2"))


if __name__ == "__main__":
    main()
