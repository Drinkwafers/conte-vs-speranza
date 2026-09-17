breed [ agents an-agent ]

globals [
  threshold                   ; by how much must G exceed the threshold to make someone withdraw consensus?
  lockdown-target              ; equilibrio di disagio target, 0-0.75 (deciso dallo slider LOCKDOWN-EQUILIBRIUM), congelato a inizio run
  previous-lockdown-target     ; equilibrio target della run precedente (0 se e' la prima run, altrimenti arriva da IMPORT-WORLD)
  transition-scale            ; moltiplicatore (calcolato una volta a inizio run) che scala la velocita' di convergenza
                               ; per l'intera durata del periodo, in base al salto rispetto al periodo precedente
  eased-equilibrium           ; bersaglio "morbido" verso cui rilassano i cittadini: segue una curva a S
                               ; (SMOOTHSTEP) da START-EQUILIBRIUM al vero equilibrio del lockdown corrente,
                               ; completata in esattamente TRANSITION-DURATION tick -- pendenza zero garantita
                               ; a inizio e fine transizione, un solo picco centrale di ampiezza prevedibile
  start-equilibrium           ; punto di partenza della transizione in corso: il vero EASED-EQUILIBRIUM al momento
                               ; del cambio di lockdown (non il valore teorico del livello precedente!), cosi' se
                               ; un periodo finisce prima che la transizione precedente sia completa, quella
                               ; successiva riparte da dove il disagio era arrivato davvero, senza scalini artificiali
  total-ticks                 ; contatore esplicito di tick MAI azzerato da RESET-TICKS (che invece azzera TICKS
                               ; ad ogni nuovo periodo): serve solo come coordinata x del plot, cosi' l'asse
                               ; corrisponde sempre e comunque al numero vero di passi simulati, sommato su tutti
                               ; i periodi -- niente piu' contatori impliciti del pennino che possono disallinearsi
]

agents-own [
  perceived-hardship    ; H, ranging from 0-1 (inclusive) -- rilassa verso un equilibrio dipendente dal lockdown fisso della run
  active?                ; if true, the agent has withdrawn its consensus (era "rebelling")
  my-threshold           ; soglia individuale di dissenso, fissata a SETUP e mai piu' toccata (come RISK-AVERSION in Rebellion):
                         ; a differenza di PERCEIVED-HARDSHIP non rilassa verso nessun equilibrio comune, quindi l'eterogeneita'
                         ; tra cittadini non si appiattisce nel tempo
]

patches-own [
  neighborhood        ; surrounding patches within the vision radius
]

to setup
  clear-all

  ; fissa il generatore di numeri casuali: stesso RNG-SEED = stessa run, identica in ogni dettaglio
  random-seed rng-seed

  ; set globals
  set threshold 0.1
  set total-ticks 0
  ; la prima run parte sempre da "nessuna restrizione" come punto di riferimento:
  ; SETUP non puo' mai essere il percorso per proseguire una run caricata (fa clear-all),
  ; quindi qui non serve gestire il caso "run precedente"
  set previous-lockdown-target 0
  ; il bersaglio morbido parte allineato al punto di riferimento (nessuna restrizione = disagio 0):
  set start-equilibrium previous-lockdown-target
  set eased-equilibrium start-equilibrium

  ask patches [
    ; make background a slightly dark gray
    set pcolor gray - 1
    ; cache patch neighborhoods
    set neighborhood patches in-radius vision
  ]

  ; create agents
  create-agents round (initial-agent-density * .01 * count patches) [
    move-to one-of patches with [ not any? turtles-here ]
    set heading 0
    set perceived-hardship random-float 1.0
    set active? false
    ; soglia individuale distribuita normalmente attorno a THRESHOLD (deviazione standard = THRESHOLD-SPREAD
    ; volte il valore centrale): e' questa dispersione, non la forma della curva di transizione, il vero
    ; fattore che decide quanto i cittadini ritirano il consenso in blocco o in modo scaglionato nel tempo
    ; (con dispersione stretta convergono quasi tutti sulla stessa soglia effettiva e crollano quasi
    ; all'unisono; con dispersione ampia il crollo si spalma su molti piu' tick)
    ; con un pavimento a 0.01 per evitare soglie nulle o negative (che renderebbero l'agente sempre "active?")
    set my-threshold (max (list 0.01 (random-normal threshold (threshold * threshold-spread))))
    display-agent
  ]

  ; start clock and plot initial state of system
  reset-ticks

  ; calcola una volta per tutte, per l'intera run, quanto il passaggio dal livello
  ; precedente (0, essendo la prima run) al livello scelto scala la velocita' di convergenza
end

to go
  if ticks = 0 [ set-transition-scale ]
  if ticks >= max-ticks [ stop ]

  ; il livello di lockdown e' fisso per l'intera run: si decide solo a SETUP,
  ; il bersaglio condiviso avanza di un passo (una volta sola, non per agente)
  update-eased-equilibrium
  ask agents [
    ; Rule M: Move to a random site within your vision
    if movement? [ move ]
    ; il disagio rilassa verso l'equilibrio del lockdown fisso di questa run
    update-hardship
    ; Rule A: Determine if each agent should withdraw consensus or stay quiet
    determine-behavior
  ]
  ; update agent display
  ask agents [ display-agent ]
  ; advance clock and update plots
  set total-ticks total-ticks + 1
  tick
end

; POLITICAL DECISION: LIVELLO DI LOCKDOWN
; il virus/l'epidemia sono solo il "perche'" dietro alla decisione: qui non vengono simulati.
; il Presidente sceglie una delle tre configurazioni possibili per l'intero periodo/run;
; per cambiarla si avvia una nuova run (SETUP oppure "Carica stato salvato...")

to-report current-lockdown-level
  report lockdown-equilibrium
end

; AGENT BEHAVIOR

; move to an empty patch
to move ; agent procedure
  ; move to an empty patch within vision
  let targets neighborhood with [ not any? turtles-here ]
  if any? targets [ move-to one-of targets ]
end

; il disagio percepito rilassa (a velocita' RELAXATION-RATE, scalata da TRANSITION-SCALE)
; verso EASED-EQUILIBRIUM -- il bersaglio morbido, non il vero equilibrio del lockdown:
; e' un rilassamento "in cascata" (due stadi in serie) che produce una curva a S invece
; di un'esponenziale ripida fin dal primo tick.
to update-hardship  ; agent procedure
  let effective-rate (relaxation-rate * transition-scale)
  set perceived-hardship perceived-hardship + (effective-rate * (eased-equilibrium - perceived-hardship))
  set perceived-hardship clamp01 perceived-hardship
end

; EASED-EQUILIBRIUM segue una curva a S vera e propria (SMOOTHSTEP), non un'esponenziale:
; a differenza di un rilassamento a cascata (dove la pendenza massima si sposta nel tempo ma
; resta comunque un "ginocchio" ripido da qualche parte), SMOOTHSTEP garantisce pendenza ESATTAMENTE
; zero all'inizio e alla fine della transizione, un solo picco centrale, e soprattutto una durata
; e un'ampiezza del picco che dipendono in modo diretto e prevedibile da TRANSITION-DURATION:
; raddoppiare TRANSITION-DURATION dimezza esattamente la pendenza massima, non solo la ritarda.
; Chiamata una volta per tick (procedura globale, non per agente): il bersaglio e' condiviso
; da tutta la popolazione. TICKS conta i passi dall'inizio di QUESTA transizione, perche' sia
; SETUP che il caricamento di uno stato salvato chiamano RESET-TICKS subito prima.
to update-eased-equilibrium
  let progress ifelse-value (transition-duration <= 0) [ 1 ] [ ticks / transition-duration ]
  set eased-equilibrium start-equilibrium + ((lockdown-target - start-equilibrium) * (smoothstep progress))
end

; curva a S canonica (3x^2 - 2x^3): 0 quando x <= 0, 1 quando x >= 1, pendenza zero a entrambi
; gli estremi, pendenza massima (1.5) esattamente al centro (x = 0.5)
to-report smoothstep [x]
  let c clamp01 x
  report (3 * c * c) - (2 * c * c * c)
end

; EQUILIBRIO DI DISAGIO: ora e' letto direttamente dallo slider LOCKDOWN-EQUILIBRIUM (0-0.75),
; niente piu' mappatura da livello discreto a valore calibrato. Con GOVERNMENT-LEGITIMACY = 0.82
; e la soglia di dissenso individuale distribuita attorno a 0.1 (vedi MY-THRESHOLD), l'hardship
; critico oltre cui un cittadino medio ritira il consenso e' 0.1 / (1 - 0.82) = 0.556: valori
; dello slider sotto questa soglia lasciano la maggioranza sostanzialmente al sicuro (erosione
; visibile ma minoritaria), valori sopra la fanno scendere sotto il 50% -- ma essendo MY-THRESHOLD
; individuale, il superamento non avviene per tutti nello stesso istante.

; SCALA DI TRANSIZIONE (leggera, asimmetrica, valida per l'intera durata del periodo)
; la misura di lockdown si decide solo a inizio run (a SETUP, oppure caricando lo
; stato finale di una run precedente con IMPORT-WORLD): il passaggio dal livello
; precedente (PREVIOUS-LOCKDOWN-TARGET) al nuovo equilibrio scelto tramite lo slider
; LOCKDOWN-EQUILIBRIUM non genera piu' un salto immediato sul disagio, ma modula (per
; tutta la durata di questa run) quanto velocemente UPDATE-HARDSHIP converge
; all'equilibrio. La modulazione e' asimmetrica e volutamente leggera: inasprire
; le restrizioni accelera un po' di piu' la convergenza (verso un equilibrio piu'
; alto) di quanto la rallenti allentarle della stessa entita' (ASYMMETRY-RATIO basso).
to set-transition-scale
  let asymmetry-ratio 0.15 ; allentare pesa solo il 15% di quanto pesa inasprire
  ; normalizzato in [-1, 1] sul range massimo possibile (0.75), cosi' SCALE-INTENSITY
  ; conserva lo stesso significato ("quanto pesa un salto a piena scala") che aveva
  ; quando SALTO andava da -2 a +2 sui tre livelli discreti
  let salto ((current-lockdown-level - previous-lockdown-target) / 0.75)
  ifelse salto > 0
    [ set transition-scale (1 + (salto * scale-intensity)) ]
    [ set transition-scale (1 + (salto * scale-intensity * asymmetry-ratio)) ]
  set lockdown-target current-lockdown-level
  set previous-lockdown-target current-lockdown-level
end

to-report clamp01 [x]
  report (max (list 0 (min (list 1 x))))
end

to determine-behavior
  set active? (grievance > my-threshold)
end

to-report grievance
  report perceived-hardship * (1 - government-legitimacy)
end

to-report pct-quiet [agentset]
  if not any? agentset [ report 0 ]
  report 100 * (count agentset with [not active?]) / (count agentset)
end

; VISUALIZATION OF AGENTS

to display-agent  ; agent procedure
  ifelse visualization = "2D"
    [ display-agent-2d ]
    [ display-agent-3d ]
end

to display-agent-2d  ; agent procedure
  set shape "circle"
  ifelse active?
    [ set color red ]
    [ set color scale-color green grievance 1.5 -0.5 ]
end

to display-agent-3d  ; agent procedure
  set color scale-color green grievance 1.5 -0.5
  ifelse active?
    [ set shape "person active" ]
    [ set shape "person quiet" ]
end


; Copyright 2004 Uri Wilensky.
; Modified to remove the cop/enforcement mechanics and adapted to model
; the erosion/recovery of electoral consensus caused by lockdown fatigue
; during an epidemic. The epidemic itself is not simulated here: it is
; only the backdrop that motivates the lockdown configuration chosen below.
; See Info tab for full copyright and license.
@#$#@#$#@
GRAPHICS-WINDOW
325
10
733
419
-1
-1
10.0
1
10
1
1
1
0
1
1
1
0
39
0
39
1
1
1
ticks
30.0

SLIDER
9
125
214
158
max-ticks
max-ticks
10
500
90.0
10
1
tick
HORIZONTAL

SLIDER
219
125
318
158
rng-seed
rng-seed
0
10000
42.0
1
1
NIL
HORIZONTAL

BUTTON
10
205
80
238
NIL
setup
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

BUTTON
10
250
80
283
NIL
go
T
1
T
OBSERVER
NIL
NIL
NIL
NIL
0

SLIDER
10
300
210
333
government-legitimacy
government-legitimacy
0.0
1.0
0.82
0.01
1
NIL
HORIZONTAL

SLIDER
365
490
565
523
threshold-spread
threshold-spread
0.0
2.0
0.6
0.05
1
x soglia media
HORIZONTAL

MONITOR
115
410
205
455
active (red)
count agents with [active?]
3
1
11

SLIDER
10
86
215
119
vision
vision
0.0
10.0
7.0
.1
1
patches
HORIZONTAL

MONITOR
10
410
110
455
quiet (green)
count agents with [not active?]
1
1
11

SWITCH
10
335
149
368
movement?
movement?
0
1
-1000

BUTTON
10
372
155
405
Salva stato finale...
let path user-new-file\nif path != false [ export-world path ]
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

BUTTON
160
372
320
405
Carica stato salvato...
let path user-file\nif path != false [ import-world path\n  reset-ticks\n  set start-equilibrium eased-equilibrium]
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

SLIDER
9
47
214
80
initial-agent-density
initial-agent-density
0.0
100.0
70.0
1.0
1
%
HORIZONTAL

MONITOR
95
200
177
245
# of agents
count agents
3
1
11

PLOT
10
458
345
618
Consenso elettorale
time
% cittadini
0.0
20.0
0.0
100.0
true
true
"" ""
PENS
"consenso" 1.0 0 -10899396 true "" "plotxy total-ticks (pct-quiet agents)"
"dissenso" 1.0 0 -2674135 true "" "plotxy total-ticks (100 - pct-quiet agents)"
"soglia 50%" 1.0 0 -16777216 true "" "plotxy total-ticks 50"

TEXTBOX
10
26
100
44
Initial settings
11
0.0
0

BUTTON
85
250
179
283
watch one
set visualization \"3D\"\nask max-one-of agents [grievance]\n  [ set size 2 watch-me ]
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
0

CHOOSER
180
250
318
295
visualization
visualization
"2D" "3D"
0

TEXTBOX
793
173
1073
191
Decisione del Presidente del Consiglio
11
0.0
0

SLIDER
793
195
1073
228
lockdown-equilibrium
lockdown-equilibrium
0.35
0.85
0.38
0.01
1
NIL
HORIZONTAL

TEXTBOX
792
30
1072
48
Scala di transizione e equilibrio
11
0.0
0

SLIDER
792
52
1072
85
scale-intensity
scale-intensity
0.0
0.3
0.05
0.005
1
per gradino di lockdown
HORIZONTAL

SLIDER
792
89
1072
122
relaxation-rate
relaxation-rate
0.0
0.2
0.05
0.001
1
/tick
HORIZONTAL

SLIDER
792
126
1072
159
transition-duration
transition-duration
1
80
30.0
1
1
tick
HORIZONTAL

MONITOR
792
259
1072
304
equilibrio di lockdown attuale (target)
precision lockdown-target 2
0
1
11

MONITOR
792
308
1072
353
% consenso (maggioranza tiene se > 50)
precision (pct-quiet agents) 1
0
1
11

MONITOR
792
357
1072
402
tick totali (asse x del plot, mai azzerato tra periodi)
total-ticks
0
1
11

@#$#@#$#@
## WHAT IS IT?

Questo modello e' un adattamento del modello "Rebellion" di Uri Wilensky (a sua volta basato sul modello di violenza civile di Joshua Epstein, 2002), riorientato a uno scopo diverso: fornire al Presidente del Consiglio uno strumento per valutare come le decisioni di lockdown durante un'epidemia influenzano la tenuta della sua maggioranza elettorale nel tempo.

L'epidemia NON viene simulata in dettaglio: e' solo il contesto che giustifica il lockdown. La misura di lockdown puo' essere decisa solo a inizio run (a SETUP, oppure caricando lo stato finale di una run precedente): il modello si concentra su un meccanismo preciso, la modulazione (leggera e asimmetrica) della velocita' con cui il disagio converge al suo equilibrio, in base al CAMBIO di misura tra una run e la successiva: inasprire le restrizioni accelera un po' l'erosione del consenso, allentarle rallenta molto meno il recupero.

## HOW IT WORKS

Ogni agente rappresenta un cittadino/elettore con un livello di PERCEIVED-HARDSHIP (disagio percepito, 0-1). Il GRIEVANCE (livello di insoddisfazione) e' calcolato come PERCEIVED-HARDSHIP * (1 - GOVERNMENT-LEGITIMACY): la legittimita' di base del governo attutisce o amplifica l'effetto del disagio. Se il GRIEVANCE di un cittadino supera la propria soglia individuale (MY-THRESHOLD, assegnata una volta per tutte a ciascun cittadino e mai piu' modificata, distribuita attorno a THRESHOLD con deviazione standard THRESHOLD-SPREAD volte il valore centrale), il cittadino "ritira il consenso" (ACTIVE? diventa true, colore rosso). Dato che quasi tutti i cittadini condividono (quasi) lo stesso PERCEIVED-HARDSHIP nel tempo (convergono tutti verso lo stesso bersaglio, alla stessa velocita' di base), e' la dispersione delle soglie individuali — non la forma della curva di transizione — a decidere se il consenso crolla quasi in blocco (dispersione stretta) o si eroda gradualmente su molti tick (dispersione ampia).

Il LOCKDOWN e' scelto dal Presidente del Consiglio tramite lo slider LOCKDOWN-EQUILIBRIUM (0 = nessuna restrizione, 0.75 = lockdown totale, con qualunque valore intermedio ammesso), ma **resta fisso per l'intera run**: rappresenta la misura in vigore in un dato periodo (es. un mese). Per passare a un periodo diverso, si sposta LOCKDOWN-EQUILIBRIUM e si avvia una nuova run:
- con SETUP si parte da zero (nuova popolazione, nessuna "storia" pregressa, il livello precedente e' convenzionalmente "nessuna restrizione");
- con "Carica stato salvato..." si riprende una popolazione gia' esistente (con tutto il suo disagio accumulato) esportata al termine di una run precedente con "Salva stato finale...": in questo caso il livello precedente e' quello effettivamente in vigore quando quella run si e' fermata.

In entrambi i casi, all'avvio della run, la procedura SET-TRANSITION-SCALE calcola il salto tra il livello precedente e quello nuovo e ne ricava un moltiplicatore TRANSITION-SCALE, che resta fisso per tutta la durata della run e scala la velocita' con cui ogni cittadino insegue il bersaglio (non il disagio direttamente): un salto verso l'alto (nuove restrizioni) accelera la convergenza in proporzione a SCALE-INTENSITY, un salto della stessa entita' verso il basso (restrizioni allentate) la modula molto meno (solo il 15% dell'effetto), sempre restando un aggiustamento leggero. Il bersaglio condiviso da tutta la popolazione, EASED-EQUILIBRIUM, non salta di colpo da un livello all'altro: segue una vera curva a S (funzione SMOOTHSTEP) che parte da START-EQUILIBRIUM (l'equilibrio del livello precedente) e arriva al vero equilibrio del lockdown corrente in esattamente TRANSITION-DURATION tick, con pendenza zero garantita a inizio e fine transizione e un solo picco di variazione a meta' percorso. Ogni cittadino, a sua volta, rilassa il proprio PERCEIVED-HARDSHIP (a velocita' RELAXATION-RATE * TRANSITION-SCALE) verso quel bersaglio mobile, non verso il salto secco. L'equilibrio finale e' letto direttamente dallo slider LOCKDOWN-EQUILIBRIUM (0-0.75): non e' piu' vincolato a tre valori calibrati, ma puo' assumere qualunque punto intermedio, utile per calibrare finemente sui dati storici o per agganciare in futuro il lockdown a un indicatore continuo di gravita' epidemica.

Il plot principale "Consenso elettorale" mostra la percentuale di cittadini che sostiene ancora il governo (consenso) contro quella che lo ha abbandonato (dissenso), con una linea di riferimento al 50% (soglia di maggioranza a rischio).

## HOW TO USE IT

Imposta la popolazione con INITIAL-AGENT-DENSITY e VISION, scegli la misura del primo periodo con LOCKDOWN-EQUILIBRIUM, poi clicca SETUP e GO. La simulazione si ferma da sola dopo MAX-TICKS passi (un periodo/run).

RNG-SEED fissa il generatore di numeri casuali: lasciando lo stesso valore e cliccando di nuovo SETUP, la run e' identica in ogni dettaglio (stessa posizione iniziale degli agenti, stesso disagio di partenza, stessa suddivisione tra esposti e protetti). E' cosi' che si confrontano in modo equo scenari diversi (es. LOCKDOWN-EQUILIBRIUM diverso) senza che il risultato sia falsato dalla casualita'. Per ottenere invece una nuova run casuale, cambia il valore di RNG-SEED prima di cliccare SETUP.

Per simulare una sequenza di periodi (es. mese per mese, come i dati reali usati per calibrare il modello): fai girare una run fino in fondo, premi "Salva stato finale...", poi sposta LOCKDOWN-EQUILIBRIUM sulla misura del periodo successivo e premi "Carica stato salvato..." (senza premere SETUP, che cancellerebbe la popolazione) seguito da GO. Il monitor "equilibrio di lockdown attuale (target)" mostra cosa e' fisso in questa run.

Regola SCALE-INTENSITY (di quanto, in percentuale, ogni gradino di inasprimento del lockdown rispetto al periodo precedente accelera la velocita' con cui ogni cittadino insegue il bersaglio EASED-EQUILIBRIUM; l'allentamento modula la velocita' di una frazione fissa e ridotta di questo valore — l'effetto e' pensato per essere leggero), RELAXATION-RATE (la velocita' base, prima della modulazione, con cui il disagio di ciascun cittadino converge verso il bersaglio EASED-EQUILIBRIUM) e TRANSITION-DURATION (quanti tick impiega EASED-EQUILIBRIUM a passare dal livello precedente al nuovo, seguendo una curva a S: raddoppiarla dimezza la pendenza massima del cambiamento, non la ritarda soltanto — e' la leva giusta per rendere la transizione piu' o meno morbida in modo prevedibile). L'equilibrio finale non e' piu' hardcodato nel codice: si legge direttamente dallo slider LOCKDOWN-EQUILIBRIUM.

GOVERNMENT-LEGITIMACY resta la fiducia di base nel governo, indipendente dal lockdown: puoi cambiarla mentre la simulazione gira per vedere come modula l'effetto del disagio.

THRESHOLD-SPREAD e' la leva piu' diretta sulla forma della caduta di consenso: controlla quanto e' ampia la dispersione delle soglie individuali (MY-THRESHOLD) attorno a THRESHOLD. Con valori bassi (vicino a 0) quasi tutti i cittadini condividono la stessa soglia effettiva e, siccome il loro disagio evolve quasi in sincrono, ritirano il consenso quasi in blocco nello stesso ristretto numero di tick. Con valori alti la stessa popolazione si eroda in modo molto piu' graduale, perche' i cittadini oltrepassano la propria soglia individuale in momenti via via piu' diversi tra loro.

## THINGS TO NOTICE

Confronta l'effetto di passare da LOCKDOWN-EQUILIBRIUM = 0.75 a 0.56 con quello di passare da 0 a 0.56: grazie all'asimmetria della modulazione, nel primo caso (un alleggerimento) TRANSITION-SCALE resta quasi invariato, mentre nel secondo caso (un inasprimento) accelera un po' la convergenza — anche se il livello di arrivo e' lo stesso, il consenso finale del periodo puo' risultare leggermente diverso.

Osserva come il disagio non cresca o scenda mai indefinitamente: converge sempre verso l'equilibrio del lockdown fisso di quel periodo. Variando TRANSITION-DURATION puoi allungare o accorciare la transizione e, a differenza di RELAXATION-RATE, lo fai in modo direttamente proporzionale e prevedibile sulla pendenza massima del cambiamento (raddoppiare TRANSITION-DURATION dimezza il picco, non lo sposta soltanto): prova ad alzarla per vedere lo stacco tra un livello di lockdown e l'altro diventare piu' graduale davvero, non solo piu' tardivo.

## THINGS TO TRY

Simula una sequenza di periodi in stile "prima e seconda ondata": una run con LOCKDOWN-EQUILIBRIUM = 0.75, salva lo stato, poi una run caricata con LOCKDOWN-EQUILIBRIUM = 0 (salto verso il basso, effetto leggero su TRANSITION-SCALE), poi un'altra run caricata di nuovo con LOCKDOWN-EQUILIBRIUM = 0.56 (nuovo salto verso l'alto, questa volta su una popolazione che parte da un disagio piu' basso di quello iniziale): confronta il consenso finale con quello di una singola run diretta a 0.56 senza passare per gli altri due periodi.

Fissa GOVERNMENT-LEGITIMACY alto (es. 0.9) e osserva quanto lockdown la popolazione "tollera" prima che il consenso scenda sotto il 50%; ripeti con legittimita' bassa (es. 0.5) e confronta.

Confronta THRESHOLD-SPREAD basso (es. 0.1) con uno alto (es. 1.5) a parita' di tutto il resto: e' la prova piu' diretta che la sincronia (o meno) del crollo dipende dalla dispersione delle soglie individuali, non dalla velocita' o dalla forma della transizione.

## EXTENDING THE MODEL

Il modello epidemico e' volutamente assente: essendo LOCKDOWN-EQUILIBRIUM ora un valore continuo, si presta gia' bene a essere collegato a un indicatore di gravita' epidemica importato da un simulatore esterno (es. leggendo un file), invece di una scelta manuale, per testare policy automatiche/reattive anziche' decise a mano.

Si potrebbe aggiungere una componente di comunicazione/percezione: la fiducia nel governo (GOVERNMENT-LEGITIMACY) potrebbe essa stessa reagire dinamicamente alla coerenza delle decisioni, invece di restare un parametro fisso impostato dall'utente.

## NETLOGO FEATURES

Nota come CURRENT-LOCKDOWN-LEVEL faccia da ponte tra "cosa sceglie l'utente" (lo slider LOCKDOWN-EQUILIBRIUM) e "come viene usato nel modello" (LOCKDOWN-TARGET, congelato a inizio run): anche se oggi la traduzione e' un semplice passaggio diretto, mantenere questo livello di indirezione rende piu' semplice, in futuro, sostituire la fonte della decisione (es. un file esterno o un indicatore epidemiologico) senza toccare il resto del codice.

## CREDITS AND REFERENCES

Questo modello e' un adattamento di "Rebellion" di Uri Wilensky (2004), a sua volta basato su Joshua M. Epstein, "Modeling civil violence: An agent-based computational approach", Proceedings of the National Academy of Sciences, Vol. 99, Suppl. 3, May 14, 2002, disponibile su
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC128592/.

## HOW TO CITE

If you mention this model or the NetLogo software in a publication, we ask that you include the citations below.

For the model itself:

* Wilensky, U. (2004).  NetLogo Rebellion model.  http://ccl.northwestern.edu/netlogo/models/Rebellion.  Center for Connected Learning and Computer-Based Modeling, Northwestern University, Evanston, IL.

Please cite the NetLogo software as:

* Wilensky, U. (1999). NetLogo. http://ccl.northwestern.edu/netlogo/. Center for Connected Learning and Computer-Based Modeling, Northwestern University, Evanston, IL.

## COPYRIGHT AND LICENSE

Copyright 2004 Uri Wilensky.

![CC BY-NC-SA 3.0](http://ccl.northwestern.edu/images/creativecommons/byncsa.png)

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 3.0 License.  To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/3.0/ or send a letter to Creative Commons, 559 Nathan Abbott Way, Stanford, California 94305, USA.

Commercial licenses are also available. To inquire about commercial licenses, please contact Uri Wilensky at uri@northwestern.edu.

This model was created as part of the projects: PARTICIPATORY SIMULATIONS: NETWORK-BASED DESIGN FOR SYSTEMS LEARNING IN CLASSROOMS and/or INTEGRATED SIMULATION AND MODELING ENVIRONMENT. The project gratefully acknowledges the support of the National Science Foundation (REPP & ROLE programs) -- grant numbers REC #9814682 and REC-0126227.

<!-- 2004 -->
@#$#@#$#@
default
true
0
Polygon -7500403 true true 150 5 40 250 150 205 260 250

airplane
true
0
Polygon -7500403 true true 150 0 135 15 120 60 120 105 15 165 15 195 120 180 135 240 105 270 120 285 150 270 180 285 210 270 165 240 180 180 285 195 285 165 180 105 180 60 165 15

arrow
true
0
Polygon -7500403 true true 150 0 0 150 105 150 105 293 195 293 195 150 300 150

box
false
0
Polygon -7500403 true true 150 285 285 225 285 75 150 135
Polygon -7500403 true true 150 135 15 75 150 15 285 75
Polygon -7500403 true true 15 75 15 225 150 285 150 135
Line -16777216 false 150 285 150 135
Line -16777216 false 150 135 15 75
Line -16777216 false 150 135 285 75

bug
true
0
Circle -7500403 true true 96 182 108
Circle -7500403 true true 110 127 80
Circle -7500403 true true 110 75 80
Line -7500403 true 150 100 80 30
Line -7500403 true 150 100 220 30

butterfly
true
0
Polygon -7500403 true true 150 165 209 199 225 225 225 255 195 270 165 255 150 240
Polygon -7500403 true true 150 165 89 198 75 225 75 255 105 270 135 255 150 240
Polygon -7500403 true true 139 148 100 105 55 90 25 90 10 105 10 135 25 180 40 195 85 194 139 163
Polygon -7500403 true true 162 150 200 105 245 90 275 90 290 105 290 135 275 180 260 195 215 195 162 165
Polygon -16777216 true false 150 255 135 225 120 150 135 120 150 105 165 120 180 150 165 225
Circle -16777216 true false 135 90 30
Line -16777216 false 150 105 195 60
Line -16777216 false 150 105 105 60

car
false
0
Polygon -7500403 true true 300 180 279 164 261 144 240 135 226 132 213 106 203 84 185 63 159 50 135 50 75 60 0 150 0 165 0 225 300 225 300 180
Circle -16777216 true false 180 180 90
Circle -16777216 true false 30 180 90
Polygon -16777216 true false 162 80 132 78 134 135 209 135 194 105 189 96 180 89
Circle -7500403 true true 47 195 58
Circle -7500403 true true 195 195 58

circle
false
0
Circle -7500403 true true 0 0 300

circle 2
false
0
Circle -7500403 true true 0 0 300
Circle -16777216 true false 30 30 240

cow
false
0
Polygon -7500403 true true 200 193 197 249 179 249 177 196 166 187 140 189 93 191 78 179 72 211 49 209 48 181 37 149 25 120 25 89 45 72 103 84 179 75 198 76 252 64 272 81 293 103 285 121 255 121 242 118 224 167
Polygon -7500403 true true 73 210 86 251 62 249 48 208
Polygon -7500403 true true 25 114 16 195 9 204 23 213 25 200 39 123

cylinder
false
0
Circle -7500403 true true 0 0 300

dot
false
0
Circle -7500403 true true 90 90 120

face happy
false
0
Circle -7500403 true true 8 8 285
Circle -16777216 true false 60 75 60
Circle -16777216 true false 180 75 60
Polygon -16777216 true false 150 255 90 239 62 213 47 191 67 179 90 203 109 218 150 225 192 218 210 203 227 181 251 194 236 217 212 240

face neutral
false
0
Circle -7500403 true true 8 7 285
Circle -16777216 true false 60 75 60
Circle -16777216 true false 180 75 60
Rectangle -16777216 true false 60 195 240 225

face sad
false
0
Circle -7500403 true true 8 8 285
Circle -16777216 true false 60 75 60
Circle -16777216 true false 180 75 60
Polygon -16777216 true false 150 168 90 184 62 210 47 232 67 244 90 220 109 205 150 198 192 205 210 220 227 242 251 229 236 206 212 183

fish
false
0
Polygon -1 true false 44 131 21 87 15 86 0 120 15 150 0 180 13 214 20 212 45 166
Polygon -1 true false 135 195 119 235 95 218 76 210 46 204 60 165
Polygon -1 true false 75 45 83 77 71 103 86 114 166 78 135 60
Polygon -7500403 true true 30 136 151 77 226 81 280 119 292 146 292 160 287 170 270 195 195 210 151 212 30 166
Circle -16777216 true false 215 106 30

flag
false
0
Rectangle -7500403 true true 60 15 75 300
Polygon -7500403 true true 90 150 270 90 90 30
Line -7500403 true 75 135 90 135
Line -7500403 true 75 45 90 45

flower
false
0
Polygon -10899396 true false 135 120 165 165 180 210 180 240 150 300 165 300 195 240 195 195 165 135
Circle -7500403 true true 85 132 38
Circle -7500403 true true 130 147 38
Circle -7500403 true true 192 85 38
Circle -7500403 true true 85 40 38
Circle -7500403 true true 177 40 38
Circle -7500403 true true 177 132 38
Circle -7500403 true true 70 85 38
Circle -7500403 true true 130 25 38
Circle -7500403 true true 96 51 108
Circle -16777216 true false 113 68 74
Polygon -10899396 true false 189 233 219 188 249 173 279 188 234 218
Polygon -10899396 true false 180 255 150 210 105 210 75 240 135 240

house
false
0
Rectangle -7500403 true true 45 120 255 285
Rectangle -16777216 true false 120 210 180 285
Polygon -7500403 true true 15 120 150 15 285 120
Line -16777216 false 30 120 270 120

leaf
false
0
Polygon -7500403 true true 150 210 135 195 120 210 60 210 30 195 60 180 60 165 15 135 30 120 15 105 40 104 45 90 60 90 90 105 105 120 120 120 105 60 120 60 135 30 150 15 165 30 180 60 195 60 180 120 195 120 210 105 240 90 255 90 263 104 285 105 270 120 285 135 240 165 240 180 270 195 240 210 180 210 165 195
Polygon -7500403 true true 135 195 135 240 120 255 105 255 105 285 135 285 165 240 165 195

line
true
0
Line -7500403 true 150 0 150 300

line half
true
0
Line -7500403 true 150 0 150 150

pentagon
false
0
Polygon -7500403 true true 150 15 15 120 60 285 240 285 285 120

person
false
0
Circle -7500403 true true 110 5 80
Polygon -7500403 true true 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Rectangle -7500403 true true 127 79 172 94
Polygon -7500403 true true 195 90 240 150 225 180 165 105
Polygon -7500403 true true 105 90 60 150 75 180 135 105

person active
false
0
Polygon -13791810 true false 135 90 150 105 135 165 150 180 165 165 150 105 165 90
Polygon -2674135 true false 195 135 240 30 210 15 165 120
Circle -7500403 true true 110 5 80
Rectangle -7500403 true true 127 79 172 94
Polygon -2674135 true false 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Polygon -2674135 true false 105 135 60 30 90 15 135 120
Polygon -6459832 true false 195 15 270 60 270 75 195 30

person jailed
false
0
Circle -7500403 true true 110 5 80
Polygon -16777216 true false 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Rectangle -7500403 true true 127 79 172 94
Polygon -16777216 true false 195 90 210 150 195 180 165 105
Polygon -16777216 true false 105 90 90 150 105 180 135 105

person quiet
false
0
Polygon -13791810 true false 135 90 150 105 135 165 150 180 165 165 150 105 165 90
Polygon -1184463 true false 195 90 240 195 210 210 165 105
Circle -7500403 true true 110 5 80
Rectangle -7500403 true true 127 79 172 94
Polygon -1184463 true false 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Polygon -1 true false 100 210 130 225 145 165 85 135 63 189
Polygon -13791810 true false 90 210 120 225 135 165 67 130 53 189
Polygon -1 true false 120 224 131 225 124 210
Line -16777216 false 139 168 126 225
Line -16777216 false 140 167 76 136
Polygon -1184463 true false 105 90 60 195 90 210 135 105

person soldier
false
10
Rectangle -7500403 true false 127 79 172 94
Polygon -13345367 true true 105 90 60 195 90 210 135 105
Polygon -13345367 true true 195 90 240 195 210 210 165 105
Circle -7500403 true false 110 5 80
Polygon -13345367 true true 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Polygon -6459832 true false 120 90 105 90 180 195 180 165
Line -6459832 false 109 105 139 105
Line -6459832 false 122 125 151 117
Line -6459832 false 137 143 159 134
Line -6459832 false 158 179 181 158
Line -6459832 false 146 160 169 146
Rectangle -6459832 true false 120 193 180 201
Polygon -6459832 true false 122 4 107 16 102 39 105 53 148 34 192 27 189 17 172 2 145 0
Polygon -16777216 true false 183 90 240 15 247 22 193 90
Rectangle -6459832 true false 114 187 128 208
Rectangle -6459832 true false 177 187 191 208

plant
false
0
Rectangle -7500403 true true 135 90 165 300
Polygon -7500403 true true 135 255 90 210 45 195 75 255 135 285
Polygon -7500403 true true 165 255 210 210 255 195 225 255 165 285
Polygon -7500403 true true 135 180 90 135 45 120 75 180 135 210
Polygon -7500403 true true 165 180 165 210 225 180 255 120 210 135
Polygon -7500403 true true 135 105 90 60 45 45 75 105 135 135
Polygon -7500403 true true 165 105 165 135 225 105 255 45 210 60
Polygon -7500403 true true 135 90 120 45 150 15 180 45 165 90

square
false
0
Rectangle -7500403 true true 30 30 270 270

square 2
false
0
Rectangle -7500403 true true 30 30 270 270
Rectangle -16777216 true false 60 60 240 240

star
false
0
Polygon -7500403 true true 151 1 185 108 298 108 207 175 242 282 151 216 59 282 94 175 3 108 116 108

target
false
0
Circle -7500403 true true 0 0 300
Circle -16777216 true false 30 30 240
Circle -7500403 true true 60 60 180
Circle -16777216 true false 90 90 120
Circle -7500403 true true 120 120 60

tree
false
0
Circle -7500403 true true 118 3 94
Rectangle -6459832 true false 120 195 180 300
Circle -7500403 true true 65 21 108
Circle -7500403 true true 116 41 127
Circle -7500403 true true 45 90 120
Circle -7500403 true true 104 74 152

triangle
false
0
Polygon -7500403 true true 150 15 0 270 300 270

triangle 2
false
0
Polygon -7500403 true true 150 30 15 255 285 255
Polygon -16777216 true false 151 99 225 223 75 224

truck
false
0
Rectangle -7500403 true true 4 45 195 187
Polygon -7500403 true true 296 193 296 150 259 134 244 104 208 104 207 194
Rectangle -1 true false 195 60 195 105
Polygon -16777216 true false 238 112 252 141 219 141 218 112
Circle -16777216 true false 234 174 42
Rectangle -7500403 true true 181 185 214 194
Circle -16777216 true false 144 174 42
Circle -16777216 true false 24 174 42
Circle -7500403 false true 24 174 42
Circle -7500403 false true 144 174 42
Circle -7500403 false true 234 174 42

turtle
true
0
Polygon -10899396 true false 215 204 240 233 246 254 228 266 215 252 193 210
Polygon -10899396 true false 195 90 225 75 245 75 260 89 269 108 261 124 240 105 225 105 210 105
Polygon -10899396 true false 105 90 75 75 55 75 40 89 31 108 39 124 60 105 75 105 90 105
Polygon -10899396 true false 132 85 134 64 107 51 108 17 150 2 192 18 192 52 169 65 172 87
Polygon -10899396 true false 85 204 60 233 54 254 72 266 85 252 107 210
Polygon -7500403 true true 119 75 179 75 209 101 224 135 220 225 175 261 128 261 81 224 74 135 88 99

wheel
false
0
Circle -7500403 true true 3 3 294
Circle -16777216 true false 30 30 240
Line -7500403 true 150 285 150 15
Line -7500403 true 15 150 285 150
Circle -7500403 true true 120 120 60
Line -7500403 true 216 40 79 269
Line -7500403 true 40 84 269 221
Line -7500403 true 40 216 269 79
Line -7500403 true 84 40 221 269

x
false
0
Polygon -7500403 true true 270 75 225 30 30 225 75 270
Polygon -7500403 true true 30 75 75 30 270 225 225 270
@#$#@#$#@
NetLogo 6.2.0
@#$#@#$#@
setup
repeat 5 [ go ]
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
default
0.0
-0.2 0 0.0 1.0
0.0 1 1.0 0.0
0.2 0 0.0 1.0
link direction
true
0
Line -7500403 true 150 150 90 180
Line -7500403 true 150 150 210 180
@#$#@#$#@
0
@#$#@#$#@
