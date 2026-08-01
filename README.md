# Lógica del sistema — SENTI

## Licencia

Este proyecto se distribuye bajo la [Apache License 2.0](LICENSE). El código
original de SENTI puede usarse, modificarse y redistribuirse conforme a sus
términos. Las dependencias de terceros conservan sus propias licencias.

Contrato del sistema. Si el código no cumple esto, el código está mal.

Las referencias `§n` apuntan a la especificación consolidada, que ya no vive en
el repositorio. El código las sigue citando por número: son la trazabilidad
entre una decisión y el párrafo que la impone.

## Principio único

> El modelo **redacta** sobre un resultado ya verificado. Nunca **decide**.

Decide código determinista en `app.rules` y `app.routing`. `app.rules` no
importa `app.llm` ni `app.models` —solo `app.domain`—: por eso el nivel rojo
funciona con el modelo apagado y los criterios del §32 se miden sin levantar
nada.

## Flujo

```
mensaje
  │
  ├─1─ urgencia (regex, determinista)          app/rules/urgency.py
  │      ROJO ──────────────────────► plantilla fija · 0,1 ms · FIN
  │      cola > umbral ─────────────► plantilla fija + diferida · FIN
  │
  ├─2─ herramientas autorizadas                app/orchestrator/tools.py
  │      registro cerrado · permiso por rol · args validados
  │
  ├─3─ backend ejecuta y verifica              app/orchestrator/handlers.py
  │      sin dato → devuelve `ausencia`, nunca vacío
  │      sin herramienta → busca en el RAG      app/rag/retriever.py
  │
  ├─4─ modelo redacta                          app/llm/
  │      sin razonamiento · ≤80 tokens · ≤320 caracteres
  │
  └─5─ guardia de salida                       app/rules/response.py
         lenguaje prohibido → descarta y cae a plantilla
         backend añade fuente + hora + limitación
```

## Quién decide qué

| Decisión | Quién | Dónde |
|---|---|---|
| nivel de urgencia | regex determinista | `rules/urgency.py` |
| ¿la alerta incluye mi zona? | PostGIS | `handlers.py` |
| ¿la vía está cerrada? | operador municipal o fuente oficial | `models/geo.py` |
| descartar una ruta | reglas §20.2 | `rules/scoring.py` |
| puntuar una ruta | fórmula §20.3 | `rules/scoring.py` |
| confianza de un reporte | escalera §21.2 | `rules/trust.py` |
| cobertura cartográfica | medición por distrito §20.4 | `routing/engine.py` |
| fuente, hora, nivel oficial | backend | `rules/response.py` |
| nivel de riesgo del tablero municipal | conteo de alertas críticas vigentes | `rules/municipal_dashboard.py` |
| **redactar el texto** | **modelo** | `llm/` |

## Reglas duras

**Urgencia (§18).** Cuatro niveles, definidos por lo que hay que **hacer** y no
por gravedad abstracta:

| | | ¿pasa por el modelo? |
|---|---|:-:|
| ⬛ **negro** | lo que SENTI no puede responder (§25) | **no** |
| 🟥 **rojo** | vida o muerte | **no** |
| 🟨 **amarillo** | moverse: atascos, cierres, llegar a un sitio de emergencia | sí |
| 🟩 **verde** | preparación y consultas del día a día | sí |

Había un naranja entre rojo y amarillo. Se quitó porque nadie sabía decir dónde
acababa uno y empezaba el otro: los dos terminaban en la misma respuesta y la
frontera solo servía para discutirla.

El **negro** no es una urgencia, es una frontera. Se responde con texto fijo y
sin modelo, y esa es toda la garantía: dejar que el modelo redacte sobre lo que
tiene prohibido decir es la forma más directa de que acabe diciéndolo — basta
un «no puedo predecir sismos, pero normalmente…» para que la frase siguiente
sea una predicción. Y no se limita a negarse: redirige, porque quien pregunta
qué medicamento dar tiene un problema real delante.

El **rojo gana sobre el negro**. «Hay un herido, qué medicamento le doy» pide
algo prohibido, pero primero hay un herido: se atiende la emergencia y la
plantilla roja no receta nada.

Gana el nivel más alto y **no se interpretan negaciones**: un falso positivo de
rojo cuesta una plantilla; un falso negativo cuesta una persona.

**Descarte duro (§20.2).** La ruta desaparece si: contradice una orden oficial
de evacuación · cruza cierre vigente · atraviesa puente afectado · entra a
quebrada activada · requiere cruzar agua · destino no validado. Si todas se
descartan → `sin ruta verificable`, sin excepción. Nunca "la menos mala".

**Puntaje (§20.3).** `0,50·seguridad + 0,20·fuente + 0,15·accesible +
0,10·duración + 0,05·distancia`; los pesos suman 1,0 y se comprueba al importar
el módulo.

Riesgo por tramo: cierre 1,00 (descarta) · zona peligro alto 0,70 · reporte
validado 0,55 · probable 0,40 · pendiente 0,15 · sin señal 0,00. Gana el
**máximo**, no la suma: dos señales medias no equivalen a una grave. Solo
cuentan los reportes a menos de **200 m** del tramo. Los reportes decaen
linealmente a 0 al cumplir su vigencia por tipo de peligro: vencido no penaliza
ni tranquiliza.

`S_fuente`: 1,0 si todo lo considerado es oficial · 0,6 mixto · 0,3 solo
comunitario · 0,0 si no hay información reciente de la zona. Los mínimos de
duración y distancia se calculan **sobre las supervivientes**: compararse con
una ruta descartada falsearía ambos subpuntajes.

Los eventos viales activos que aparecen como marcadores (vía bloqueada,
derrumbe, huaico, puente, inundación, agua o poste) también entran en la ruta:
los oficiales se incorporan como señal validada y el cliente envía como
`exclude_locations` los conflictos que caen sobre la ruta cuando el usuario
recalcula. Un marcador no vial, como un sismo, no se interpreta como obstáculo
de carretera. Un reporte ciudadano pendiente sigue siendo una penalización y
no un cierre oficial.

**Confianza (§21.2).** pendiente → probable (2 reportes de personas distintas,
<300 m, <60 min) → validado (validador **con evidencia**) → confirmado
(municipio o Estado). Solo `confirmado` excluye de la ruta.

**Fuentes (§11.3).** `ok` · `degradado` (se cita con advertencia) · `caido` (no
se cita, **se declara la ausencia**) · `obsoleto` (referencia histórica).

El sondeo recorre solo las fuentes con `healthcheck_url`; las demás se quedan
en su estado inicial, `caido`, con `ultima_consulta_at` nulo. Para citar da
igual —ninguna de las dos es citable— pero para **contarlo** no: donde se
muestre el estado, una fuente nunca consultada se distingue de una que no
responde. Decir que INDECI no contesta cuando nadie le ha preguntado es
afirmar algo que no se ha comprobado, y es la misma clase de error que este
sistema evita en la dirección contraria.

**Retención (§13.5).** ubicación exacta 72 h · distrito 12 meses · foto 30 días
o al resolverse · mensajes 12 meses · auditoría 24 meses · teléfono
seudonimizado. Sin clave de cifrado, un campo sensible **no se guarda**.
Notificación de brecha a la ANPD en 48 h.

**Canal (§7.3, §7.4).** Ninguna instrucción crítica depende de abrir un enlace,
cargar una imagen o usar la app. N2 (satélite): ≤600 car., sin enlaces, sin
botones, ≤6 pasos de ruta, mapa ≤30 KB —frente a 150 KB en N0—. N4: fuera de
alcance, el sistema no promete lo que no puede cumplir.

El nivel lo fija el cliente, que es quien ve la red. De las cuatro condiciones
de activación del §7.4 el backend solo puede medir una —la latencia—, así que la
mide y devuelve `sugerir_modo_ligero` con su motivo; las otras tres (fallos de
envío de media, petición del usuario, falta de señal D2C) las conoce el cliente
y decide él. El backend no impone el nivel: informa con un número medido en vez
de dejar que se estime.

## La API

32 endpoints. La columna de permiso es la que valida el backend (§6); donde está
vacía basta con estar autenticado.

| Método y ruta | Qué hace | Permiso |
|---|---|---|
| `POST /auth/registro` | alta de ciudadano | — |
| `POST /auth/login` | token de acceso | — |
| `GET /auth/aviso-consentimiento` | texto y versión vigentes (§13) | — |
| `POST /auth/consentimiento` | registra consentimiento granular | — |
| `GET /auth/mis-datos` | lo que el sistema guarda de ti (§13) | — |
| `POST /chat` | conversación con el asistente | invitado (§13.4) |
| `GET /chat/{id}/mensajes` | historial y **respuestas diferidas** (§29) | invitado (§13.4) |
| `GET /perfil` | perfil del hogar | — |
| `PUT /perfil` | cantidad y condición, nunca nombres (§14) | `CONFIGURAR_HOGAR` |
| `POST /plan-familiar` | plan desde protocolos versionados (§17) | `GENERAR_PLAN` |
| `GET /offline/paquete` | paquete §26 con su fecha de sincronización | — |
| `POST /rutas` | ruta de menor riesgo, o `sin ruta verificable` | `CONSULTAR_RUTAS` |
| `POST /reportes` | crear reporte ciudadano | `CREAR_REPORTE` |
| `POST /reportes/proponer` | el modelo **propone** tipo y descripción (§21.1) | `CREAR_REPORTE` |
| `POST /reportes/{id}/validar` | sube en la escalera §21.2 | `VALIDAR_REPORTE` |
| `GET /reportes` | estado de la zona, con coordenadas | `CONSULTAR_ALERTAS` |
| `GET /reportes/publicos` | landing: sin identidad ni coordenadas | — |
| `GET /reportes/mapa-publico` | actividad agregada por celdas, sin puntos individuales | — |
| `GET /reportes/pendientes` | cola de validación | `VALIDAR_REPORTE` |
| `POST /municipal/cierres` | cierre de vía | `CONFIRMAR_CIERRE_VIA` |
| `POST /municipal/cierres/{id}/reabrir` | reapertura | `CONFIRMAR_CIERRE_VIA` |
| `POST /municipal/recursos` | registra recurso oficial | `REGISTRAR_RECURSO` |
| `POST /municipal/comunicados` | comunicado municipal | `PUBLICAR_COMUNICADO` |
| `GET /municipal/tablero` | indicadores reales del panel municipal (§22), consumido por el Dashboard del operador y por `/info-general.html` | `PUBLICAR_COMUNICADO` |
| `GET /municipal/mapa-calor` | GeoJSON **agregado por celda** (§22) | `PUBLICAR_COMUNICADO` |
| `PUT /admin/usuarios/{id}/rol` | cambia el rol | `GESTIONAR_USUARIOS_Y_FUENTES` |
| `POST /admin/parametros-riesgo` | versiona umbrales y pesos (§23) | `GESTIONAR_USUARIOS_Y_FUENTES` |
| `GET /admin/fuentes` | registro de fuentes oficiales | `GESTIONAR_USUARIOS_Y_FUENTES` |
| `POST /admin/alertas/interpretar` | el modelo **propone** campos (§15) | `GESTIONAR_USUARIOS_Y_FUENTES` |
| `GET /admin/auditoria` | auditoría completa | `CONSULTAR_AUDITORIA` |
| `POST /webhooks/whatsapp` | entrada de Evolution API (§10.1) | cabecera `X-Senti-Token` |
| `GET /fuentes/estado` | salud de las fuentes (§11.3) | — |
| `GET /health` | vivo o no | — |
| `GET /health/detalle` | PostGIS, pgvector, el modelo con su contexto y los embeddings | — |

`/health/detalle` es la comprobación de despliegue, y cubre las cuatro cosas que
se caen en silencio:

El acceso del portal municipal (`/login.html`) usa `POST /auth/login`; no simula
una sesión en el navegador. El backend sigue siendo quien autentica y emite el
token, y la interfaz solo permite continuar a los roles `operador_municipal` y
`administrador`. Tras autenticarse, el portal abre `/admin.html#/dashboard`, el
panel del operador (barra lateral con Dashboard y Alertas).

El modelo de datos no tiene un concepto de "zona Centro/Norte/Sur": el piloto
es un solo distrito (Lurigancho-Chosica), así que el Dashboard no simula una
subdivisión que no existe — muestra el agregado real del municipio. Las
tarjetas de resumen, "Últimas alertas" e "Incidencias recientes" vienen de
`GET /municipal/tablero`; el nivel de riesgo y el color de cada alerta se
clasifican en `rules/municipal_dashboard.py`, no en el frontend. El clima usa
Open-Meteo directamente desde el navegador (sin backend propio, sin API key).
Lo único que sigue siendo un mockup preparado para conectarse es el mapa de
la zona (Google Maps real si existe `VITE_GOOGLE_MAPS_API_KEY`; si no,
un esquema en SVG).

El tablero con datos reales también sigue existiendo, sin cambios, en
`/info-general.html` (mismo `GET /municipal/tablero`, mismo `POST
/auth/login`): es una pantalla aparte, no enlazada desde el panel del
operador, con su propio diseño.

| Comprueba | Por qué ahí |
|---|---|
| PostGIS y pgvector | sin ellos no hay geometría ni RAG, y el error sale tarde |
| modelo de chat cargado **y su contexto** | apuntar a un modelo ausente no falla hasta la primera pregunta |
| modelo profundo | sostiene §15, §21.1 e imágenes; se cae sin que el chat lo note |
| embeddings y sus dimensiones | si no coinciden con la columna `vector(n)`, la indexación falla |

El contexto se lee de `/api/v0/models` en LM Studio y de `/props` en llama.cpp.
Si el que cargó el servidor no coincide con `SENTI_LLM_CONTEXT_LENGTH`, el
endpoint lo dice: sin ese aviso las respuestas se cortan sin que nada dé error.

## Fuentes oficiales (§11.4)

Registro cerrado en `app/sources/registry.py`. El healthcheck corre cada 15 min
(`SENTI_SOURCE_HEALTHCHECK_MINUTES`) y el sondeo de eventos cada 10 min
(`SENTI_CITIZEN_SOURCE_POLL_MINUTES`). Ambos escriben el resultado en la base
de datos; el estado decide si una fuente se cita, se cita con advertencia o se
declara ausente.

Las fuentes activas y verificadas son:

| Slug | Institución | Tipo | Vigencia | Categorías | URL |
|---|---|---|---:|---|---|
| `igp-censis-sismos` | IGP / CENSIS | ArcGIS REST oficial | 6 h | sismo | `https://ide.igp.gob.pe/arcgis/rest/services/monitoreocensis/Sismicidad/MapServer/0/query` |
| `indeci-geosinpad` | INDECI | OGC API oficial | 24 h | inundación y emergencias | `https://geosinpad.indeci.gob.pe/indeci/rest/services/Emergencias/EMERGENCIAS_SINPAD/OGCFeatureServer/collections/0/items` |
| `senamhi-wis-horario` | SENAMHI | OGC API WIS 2.0 | 6 h | lluvia e inundación | `http://wis.senamhi.gob.pe/oapi/collections/urn%3Awmo%3Amd%3Ape-senamhi%3Asynop-hourly/items` |

SENAMHI WIS se consulta con una ventana dinámica de las últimas seis horas y
solo las observaciones de precipitación positiva generan eventos. El catálogo
de estaciones (`http://wis.senamhi.gob.pe/oapi/collections/stations/items`) se
conserva como referencia de metadatos. El servicio HTTPS de WIS actualmente
publica una cadena de certificados incompleta en el servidor; por eso se usa
su endpoint HTTP oficial y nunca se desactiva la verificación TLS en las demás
fuentes.

Las fuentes antiguas que no tienen un endpoint estructurado y vigente fueron
desactivadas, pero su historial permanece en `official_sources` para no borrar
la trazabilidad: ANA/GeoSNIRH, IGP Último Sismo, INGEMMET GeoCATMIN, SENAMHI
Avisos, SUTRAN, SIGRID/CENEPRED, DIHIDRONAV/CNAT y COEN/INDECI. Una página
oficial disponible no se convierte automáticamente en un feed: para crear un
evento se exigen respuesta estructurada, coordenadas, fecha y vigencia.

## La conversación tiene memoria, y solo la suya

Al modelo se le pasan los **últimos doce mensajes del hilo**, seis intercambios.
Sin eso respondía cada mensaje como si fuera el primero: a «¿qué llevo en mi
mochila?» contestaba «necesito saber qué emergencia estás viviendo», dos
mensajes después de haberle hablado de una alerta naranja.

De esos doce, **solo los cuatro últimos van literales**. Los anteriores se
resumen a 120 caracteres cada uno, que es donde está de qué iba el turno. Los
recientes no se tocan porque ahí viven los pronombres: «¿y por ahí se puede
pasar?» no significa nada sin la frase anterior entera.

El resumen no lo hace un modelo. Generarlo costaría otra llamada —siete
segundos en CPU— para ahorrar unas fichas de prompt, y de un turno viejo lo que
importa está en sus primeras palabras. Medido: doce mensajes enteros son ~600
fichas por petición; comprimidos bajan casi a la mitad.

El límite no es estético. El contexto se paga en cada ficha generada y el
servidor va en CPU. Y sale barato porque el historial va **entre** el sistema y
el mensaje nuevo: el prefijo se mantiene estable y llama.cpp lo reutiliza de
caché, procesando solo lo que se añade.

El aislamiento es **por conversación**, que es lo que separa un hilo de otro
(§13.5). Nunca se mezcla lo que alguien dijo en otra conversación suya, y mucho
menos en la de otra persona. Vale igual para la app y para WhatsApp.

## Dos mapas: Google con conexión, MapLibre sin ella

La cartografía **con conexión** la pone **Google Maps** —SDK en Android,
JavaScript en la web—. La cartografía **sin conexión** la pone **MapLibre**
sobre teselas de OpenStreetMap empaquetadas en el APK. No es una migración a
medias: son los dos, cada uno donde el otro no llega, y el criterio que los
separa es único —¿hay red?—.

El reparto no es una preferencia estética. Las teselas de Google no se pueden
descargar para usarlas fuera de línea; las de OpenStreetMap sí. Mientras hay
cobertura gana Google, que tiene mejor cartografía urbana del Perú y no cuesta
un byte de APK. Cuando no la hay, Google no puede dibujar nada y MapLibre es lo
único que queda.

Lo que **no** cambia es quién decide por dónde se va. Las rutas las sigue
calculando Valhalla sobre las teselas de Perú, y el descarte duro del §20.2 lo
hace `rules/scoring.py` cruzando la geometría en PostGIS. Google dibuja; no
enruta, no descarta y no sabe qué vía está cerrada.

Tres consecuencias que hay que tener presentes:

| | |
|---|---|
| **Depende de un tercero** | si se agota la cuota o cae el servicio, no hay mapa *con conexión*. Los pasos escritos siguen siendo la respuesta completa (§7.3), así que la pantalla se puede cerrar sin perder nada |
| **El mapa sin conexión es otro** | Google no cede sus teselas para uso local, así que el §26 no se sostiene con él. Lo resuelve MapLibre con teselas propias, en la sección siguiente |
| **La clave nunca entra en git** | va en `local.properties`, restringida por paquete y huella SHA-1. Una clave commiteada la copia cualquiera que clone el repositorio |

**El mapa de la zona se filtra por tipo y se toca para leer.** Los doce tipos
de `HazardType` tienen nombre y color en el cliente (`TipoDesastre`), el filtro
ofrece **solo los que hay en el mapa** con su recuento —un chip que al pulsarlo
deja la pantalla vacía no es un filtro— y al tocar un marcador se abre una
ficha con título, tipo, descripción, confianza y fecha.

La ficha sustituye a la burbuja de Google, que recorta a una línea y no admite
una descripción escrita por una persona. Y dice **de dónde viene cada punto**:
un evento con respaldo oficial y un reporte ciudadano sin validar se leen
distinto, porque el §25 prohíbe presentarlos como lo mismo. El color repite esa
distinción pero nunca va solo (§31.2).

Un tipo que el cliente no conozca —backend nuevo, app vieja— **se pinta
igual**, con su código legible y color neutro. Descartar lo que no se sabe
nombrar haría desaparecer del mapa un peligro real por un fallo de vocabulario.

**Reportar no pide coordenadas.** El formulario lleva un mapa donde se toca
para marcar el punto, y se puede volver a tocar para corregirlo. Antes había dos
campos de latitud y longitud: nadie sabe las suyas, y pedírselas a quien está
viendo un huaico es pedirle que abra otra aplicación, copie dos números y
vuelva. Equivocarse marcando es lo normal —el dedo tapa justo lo que hay que
señalar—, así que corregir tiene que costar un toque.

**Recalcular ante un atasco pregunta también a dónde vas.** El mapa de ruta
tiene dos modos de marcado y un botón para cada uno: dónde está el atasco y
cuál es el destino. Son dos modos excluyentes y no dos interruptores, porque
con dos se puede quedar activo el que no se cree y el toque siguiente es una
apuesta: marcar un atasco donde se quería poner el destino manda a alguien por
otro sitio sin que se entere. El atasco se acumula —puede haber varios—; el
destino es uno solo y cada toque reemplaza al anterior, que es cómo se corrige
un error.

El destino marcado gana sobre el que traía la ruta: si alguien lo señala es
porque quiere ir ahí y no al refugio más cercano que se eligió por él. Sin
destino marcado se conserva el anterior, y sin ninguno se pide ruta de escape
(§34.2), que sí busca refugio `validado` y `disponible` a menos de 15 km.

**Qué se comprueba de un destino marcado a mano, y qué no.** Llega como
`destino_lat`/`destino_lon` sin `destino_resource_id`, así que el descarte de
"destino no validado" del §20.2 **no se le aplica**: no hay recurso registrado
contra el que validarlo. Es deliberado y no una laguna — esa regla existe para
que SENTI no *elija* como refugio un sitio que nadie designó, no para
prohibirle a alguien ir a casa de su hermana. Lo que sí se comprueba entero es
el camino: cierre vigente, puente afectado, quebrada activada, cruzar agua y
orden de evacuación contraria descartan igual, y si no sobrevive ninguna ruta
la respuesta es `sin ruta verificable`.

De ahí que el mapa lo diga en voz alta al marcar: SENTI revisa el camino, no el
sitio. Un punto elegido a dedo no queda acreditado como refugio por el hecho de
que exista una ruta hasta él.

Cuando una herramienta encuentra un sitio concreto —un refugio, un centro de
salud— la respuesta lleva `lugar` con su nombre, dirección y coordenadas, y el
cliente ofrece **«Cómo llegar»**, que abre Google Maps con la ruta a pie. Se
elige a pie a propósito: casi toda evacuación de este sistema es caminando, y
dar una ruta en coche por una avenida inundada es peor que no dar ninguna.

Si el recurso vino de OpenStreetMap y no del registro municipal, el botón lo
declara: OSM acredita que existe y dónde, no que esté designado ni abierto.

**Si nombras un sitio, se busca ese.** `buscar_recursos_cercanos` acepta
`nombre`, y cuando llega se filtra por él en un radio de 50 km en vez de los 3
por defecto: quien dice «el hospital del Rebagliati» lo dice a sabiendas y ese
hospital puede estar lejos —7,7 km desde Surco, muy fuera del radio de «lo que
tengo al lado»—. El nombre manda sobre el tipo: si el modelo dedujo `refugio` y
el usuario dijo «Rebagliati», exigir las dos cosas no encuentra nada.

Para una petición genérica de «hospital más cercano», SENTI pregunta primero si
se busca un hospital público, uno privado o una estación de bomberos. Los
recursos importados desde OpenStreetMap solo reciben la categoría pública o
privada cuando la fuente trae una señal explícita de titularidad; si no, se
mantienen como centro de salud genérico y no se inventa su condición. Si se
solicita un establecimiento concreto, la respuesta conserva ese resultado y
ofrece aparte el recurso de salud más cercano como sugerencia, con acciones
separadas para «Cómo llegar» y «Ver mapa».

Y si no aparece, **se declara la ausencia; no se sustituye silenciosamente por
el más cercano**. Devolver otro hospital sin decirlo es la peor variante posible del
§11.3: alguien pide un sitio, lee un nombre distinto con prisa y sigue un
enlace hasta el lugar equivocado creyendo que va al que pidió.

Los nombres se guardan limpios. Los importados llevaban un prefijo `[OSM] `
para reconocerlos, pero `origen_osm` ya hace ese trabajo —columna indexada, y
es la que activa el aviso de ubicación referencial— mientras que el nombre lo
lee el ciudadano: llegó a salir por WhatsApp como «El centro más cercano es
[OSM] Hospital Nacional…».

**En WhatsApp no hay botón, así que va el enlace.** Detrás del texto, nunca en
su lugar: el §7.3 exige que ninguna instrucción crítica dependa de abrirlo, y
el nombre y la dirección viajan escritos igual que antes. Es la misma URL de
Google Maps con ruta a pie que abre el botón de la app, con las coordenadas a
cinco decimales —un metro— porque cada carácter cuenta contra el límite del
§7.4. La advertencia de ubicación referencial se repite ahí, porque aquí no
hay interfaz debajo de la que ponerla.

Se compone **antes** de `light_mode.adaptar`, no después, para que en N2 lo
quite la propia regla de enlaces y el límite de 600 caracteres lo cuente. Y en
N2 ni siquiera se compone: `adaptar` borraría la URL y dejaría un «Cómo
llegar:» apuntando a nada, que es peor que no ofrecerlo porque sugiere que hay
algo detrás.

No se acorta con un servicio externo. Añadiría una llamada de red dentro de la
respuesta, otra dependencia de un tercero en el canal por el que la gente pide
ayuda —el mismo error que ya cuesta caro con el transporte— y un enlace cuyo
destino no se ve antes de tocarlo.

El radio de un cierre se dibuja **en metros**, no en píxeles: al alejar el mapa
el círculo sigue cubriendo la zona que representa. Con MapLibre había que
construir el polígono a mano para conseguirlo. Un cierre dibujado más pequeño
de lo que es invita a bordearlo por donde no se puede.

## Modo sin conexión (§26)

Se entra por el icono de mapa de la **cabecera**, presente en las tres
pestañas. Está ahí y no dentro del perfil porque quien lo necesita está a punto
de quedarse sin cobertura, o ya se quedó: esconder la salida de emergencia a
dos toques y en una sección concreta es cobrar tiempo justo cuando no lo hay.

Es una pantalla que **ocupa la app entera**. Mientras está puesta no hay chat,
ni reportes, ni perfil, ni barra de navegación inferior. No están escondidos:
no existen. Los tres necesitan servidor —el chat llama al modelo, los reportes
se publican, el perfil vive en la base de datos— y un botón que no puede
funcionar durante una emergencia cuesta el tiempo de tocarlo y la confianza de
descubrir que no hacía nada.

Queda el mapa, la fecha de sincronización y cuatro botones: centrar ubicación,
rutas guardadas, guías y salir.

**Todo lo que hace falta viaja en el APK.** El modo sin conexión no llama a la
API ni una vez; está comprobado por prueba, no por convención.

### Las teselas

Dos packs PMTiles, medidos sobre el basemap de Protomaps:

| pack | cubre | zoom | peso | para qué sirve |
|---|---|---:|---:|---|
| `peru.pmtiles` | todo el país | 0–11 | 41 MB | ubicarse en cualquier sitio: carreteras, ríos, trazas urbanas |
| `lima_callao.pmtiles` | área metropolitana | 0–15 | 23 MB | caminar por una calle concreta |

El reparto sale de los números y no de una preferencia: el Perú entero hasta
zoom 12 son 94 MB y hasta el 10 son 20, mientras que **el detalle de calle de
toda el área metropolitana cabe en 23**. Subir un solo nivel de zoom en todo el
país cuesta más que llevar completa la ciudad donde vive un tercio de la
población.

Fuera de Lima y Callao el mapa llega a carreteras y vías principales, no al
nombre de la esquina — y **la pantalla lo dice** cuando detecta que estás
fuera. Un mapa con límites declarados es utilizable; uno al que le faltan
calles sin avisar manda a alguien por una vía que no existe.

MapLibre lee los packs con `pmtiles://file://`, soportado desde su versión
11.7. Los assets se declaran `noCompress`: un PMTiles ya viene comprimido por
dentro y el formato entero se basa en pedir rangos de bytes sueltos, algo que
de un asset comprimido no se puede hacer.

**Los packs no se versionan.** `.gitignore` excluye `*.pmtiles` por la misma
razón que excluye los extractos OSM: son datos generados y multiplicarían por
diecisiete el tamaño del repositorio. Se reconstruyen con

```bash
./scripts/generar-teselas.sh
```

que los extrae por *range requests* contra el planeta público de Protomaps —no
descarga el planeta, solo los bytes de los dos recuadros—. Sin ellos el APK se
ensambla igual y la pantalla declara que el mapa base no está disponible en esa
instalación; las guías y los teléfonos siguen funcionando. Es una degradación
declarada, no un build roto.

**El mapa sin conexión no dibuja nombres de calle**, y es una decisión. Pintar
texto obliga a declarar `glyphs`, que son archivos que MapLibre descarga de un
servidor: sin red no llegan. Se dibuja la geometría y los nombres se leen
tocando cada punto.

### El paquete de zona

Se descarga con red, se lee sin ella, y cubre **10 km²** alrededor del usuario
—un cuadrado de √10 km de lado— con rutas ya calculadas, conflictos viales
**con respaldo oficial**, recursos cercanos, teléfonos por región y la última
alerta.

**Los reportes ciudadanos no entran, y es deliberado.** Sin conexión no se
pueden refrescar, ni validar, ni retirar cuando dejan de ser ciertos, y su
valor entero depende de estar al día (§21.2). Un reporte pendiente de hace tres
días pintado sobre el mapa no informa: o asusta con algo que ya pasó, o —peor—
tranquiliza al no aparecer donde sí hay peligro. Un cierre municipal, en
cambio, sigue siendo un cierre mañana, y esa es la diferencia que lo hace
utilizable sin red.

| Garantía | Cómo |
|---|---|
| una actualización que falla no te deja peor | se escribe a un temporal, se valida y solo entonces se renombra: o está el viejo o está el nuevo |
| un paquete a medias no se sirve a medias | SHA-256 del contenido; si no cuadra se descarta entero, no se aprovechan los campos legibles |
| nada se presenta como actual | `sincronizado_at` viaja dentro y es lo que se muestra, nunca la hora del reloj |
| lo viejo se declara viejo | vence a los 7 días —168 h, la vigencia más larga de la tabla de riesgos— y entonces la barra se pinta en rojo |
| el silencio de una fuente no pasa por seguridad | lo que no se pudo descargar se guarda en `fuentes_fallidas` y la pantalla lo enseña (§11.3) |

Los recursos —hospitales, bomberos, comisarías, refugios— salen de
OpenStreetMap durante la sincronización, la misma fuente que usa el importador
del backend. Se guardan como referenciales: acreditan que el establecimiento
existe y dónde, no que esté abierto ni designado como punto de acogida.

La ficha que se abre al tocar un punto dice de dónde sale el dato con palabras
y no solo con el color (§25, §31.2), y repite que está descargado y pudo
cambiar.

### La sesión

Tras un login online correcto se guarda una sesión cifrada con AES/GCM y clave
en el Android Keystore. **La contraseña no está, y no es que se cifre: no
existe el campo.** Lo que se guarda es el token que el backend ya emitió, que
caduca solo y no sirve en ningún otro sitio. Un teléfono en una emergencia es
justo el objeto que se pierde.

Un token caducado no vale contra el backend pero **sí** deja entrar al modo sin
conexión, que no consulta nada. Exigir un token vivo dejaría fuera del mapa a
quien lleva tres días sin cobertura, que es la persona para la que se hizo
esto.

### Las guías

Diez guías dentro del APK —mochila, inundación, huaico, incendio, derrumbe,
evacuación, punto de reunión, falta de señal, primeros pasos y teléfonos—, cada
una con institución, versión, fecha de compilación y acciones concretas. Se
abren sin tocar la red y avisan cuando superan su vigencia de doce meses.

Ninguna la redacta el modelo (§25). Cada una declara de dónde sale su texto:

| origen | significa |
|---|---|
| `protocolo` | reproduce literal un protocolo versionado del sistema (§17) |
| `texto_fijo` | reproduce literal un texto fijo del sistema (§7.5, §24.3) |
| `resumen_local` | resume la recomendación pública de la institución citada |

Distinguirlos no es burocracia: presentar los tres como lo mismo sería atribuir
a INDECI una redacción que no es suya.

### Marcar en el mapa no publica nada

Un toque en cualquier mapa afecta a la ruta que estás mirando y a nada más. Un
reporte se crea **solo** al pulsar «Enviar reporte», y hay una prueba que
cuenta los puntos de llamada a `Api.crearReporte` para que siga siendo cierto:
si alguien conecta un gesto del mapa a esa llamada, falla antes de que exista
un APK. El §21.2 reserva el cierre de una vía al operador municipal; si un
toque creara un reporte, cualquiera cerraría calles con el dedo.

### Lo que cuesta

El APK de depuración pesa **116,7 MB**: 64 de teselas y 34 del motor de
MapLibre en tres arquitecturas (`arm64-v8a`, `armeabi-v7a`, `x86_64`; se
descartó `x86`). Es mucho, y es el precio de que el mapa funcione en modo
avión. Se puede bajar a unos 85 MB por APK con `splits` por arquitectura
cuando haya que distribuirlo.

## Análisis con el modelo profundo (§15, §21.1)

Las dos devuelven **propuestas**, nunca hechos, y ambas van por endpoint aparte
para que la revisión humana no se pueda saltar:

| Endpoint | Qué propone | Quién decide |
|---|---|---|
| `POST /admin/alertas/interpretar` | campos de un boletín (§15) | el operador publica, o no |
| `POST /reportes/proponer` | tipo y descripción (§21.1) | el ciudadano revisa y publica |

El §15 prohíbe al modelo fijar nivel, zonas o vigencia; el §21.1 exige que el
ciudadano revise antes de publicar. Por eso `requiere_revision_humana` se fuerza
en el backend en vez de creerse lo que devuelva el modelo.

## La ubicación siempre llega como coordenadas

El ciudadano comparte la ubicación de su teléfono, por la app o por WhatsApp.
**Nunca escribe una dirección.** Todo el sistema recibe `lat`/`lon`: el chat,
los reportes y las rutas.

Por eso **no hay geocodificación** ni servicio de Nominatim. Buscar
"Av. Lima Sur 340" y convertirlo en coordenadas es el problema que Nominatim
resuelve, y aquí no se plantea nunca.

Si algún día hace falta el camino inverso —mostrar el nombre de la vía en el
panel municipal en lugar de dos números— eso lo da `/locate` de Valhalla con
las teselas que ya existen, sin añadir un servicio que pide 8 GB para importar.

## Cobertura cartográfica (§20.4)

La medición por distrito vive en `risk_parameters.umbrales_cobertura`,
versionada por el administrador (§23). Se exigen **las dos** métricas: densidad
de vías ≥ 3,0 por km² y ≥ 60 % de vías etiquetadas.

Un distrito sin medición registrada se trata como **cobertura insuficiente**.
La asimetría es deliberada: declarar incompleta una cartografía buena solo suena
prudente de más; declarar buena una que nadie midió manda a alguien por una vía
que quizá no existe. Bajo el umbral, la respuesta cambia de "esta es la ruta" a
"esta es una ruta posible; la cartografía de la zona es incompleta".

## Mapa de calor (§22)

`GET /municipal/mapa-calor` devuelve GeoJSON **agregado en celdas de 300 m**,
nunca reportes sueltos. Dos motivos, y el segundo es el que manda: cien puntos
encimados no dicen dónde concentrar recursos, y un punto exacto cruzado con la
hora señala una vivienda concreta (§13.2).

La landing pública de reportes usa `GET /reportes/publicos`: devuelve actividad
vigente por distrito, tipo, estado y confianza, pero no identidad, coordenadas,
dirección aproximada ni fotos. `GET /reportes/mapa-publico` ofrece además una
agregación geoespacial por celdas de al menos 1 km, nunca puntos individuales.
`GET /reportes` conserva la consulta autenticada con coordenadas para el estado
de la zona del ciudadano; no se sustituye por la vista pública. Junto a los
reportes se publica el estado de las fuentes (`GET /fuentes/estado`): que una
esté caída se ve, no se calla (§11.3).

El peso usa la escalera del §21.2 —confirmado 4, validado 3, probable 2,
pendiente 1— porque priorizar por número bruto premia a quien más reporta, no a
la zona más afectada.

## WhatsApp (§10.1)

El transporte es **Evolution API** sobre Baileys, no la nube de Meta: no hay
plantillas aprobadas ni `phone_number_id`. La ventana de 24 h se respeta igual,
porque es una regla de WhatsApp y no del proveedor: cada mensaje del ciudadano
la reabre, y fuera de ella SENTI no inicia conversación.

```
Evolution ──► POST /webhooks/whatsapp
                │  comprueba X-Senti-Token
                │  descarta fromMe · grupos · duplicados
                │  responde 200 y ENCOLA
                ▼
             worker ──► ¿consintió? ──no──► envía el aviso del §13.4 y para
                          │ sí
                          ▼
                    orquestador (canal WHATSAPP) ──► Evolution sendText
```

El webhook **no responde al ciudadano**. Una respuesta puede tardar decenas de
segundos y Evolution reintenta si no recibe un 2xx enseguida: contestar dentro
del webhook produce mensajes duplicados y una cola que se realimenta sola, justo
cuando hay una emergencia y llegan todos a la vez.

| Regla | Por qué |
|---|---|
| se descarta `fromMe` | el propio envío vuelve como evento y el bot se contesta a sí mismo en bucle |
| se deduplica por `data.key.id` | Evolution reintenta; sin esto la misma instrucción llega tres veces |
| los grupos se ignoran | el §13.2 no permite tratar datos de terceros que no han consentido, y en un grupo cada mensaje arrastra a todos |
| cabecera `X-Senti-Token` | Evolution no firma sus peticiones: sin secreto compartido, quien descubra la URL hace que SENTI escriba a quien él diga |
| `SENTI_WHATSAPP_ENABLED=false` → 503 | un canal de emergencia a medio configurar que traga mensajes en silencio es peor que uno que declara que no está |

**El teléfono nunca se guarda en claro por defecto** (§13.5). La conversación
se busca y se crea por seudónimo; el número en claro vive en memoria el
tiempo de contestar. Si ese seudónimo coincide con el de una cuenta, quien
escribe tiene sus herramientas y su rol (§6); si no, entra como invitado y
recibe información general (§13.4). El rol sale de la cuenta, nunca del
canal.

La única excepción, y solo con consentimiento explícito y separado
(`ConsentPurpose.ALERTAS_WHATSAPP`, no implícito por dar el teléfono en el
registro): `AlertSubscriber` guarda nombre, teléfono y distrito en claro,
porque es la única forma de que SENTI escriba por iniciativa propia en vez
de solo responder. Revocar ese consentimiento en `POST /auth/consentimiento`
desactiva la suscripción; el número sigue en la tabla (por si se reactiva)
pero deja de recibir nada.

Para que esa coincidencia ocurra, **el número se canoniza antes de calcular el
seudónimo**. Los dos caminos lo traen escrito distinto: Evolution entrega
`51987654321@s.whatsapp.net`, con código de país, y en el registro la gente
teclea sus nueve dígitos. Dos textos distintos dan dos HMAC distintos, y el
titular de una cuenta entraba por WhatsApp como invitado sin que nada fallara
—recibía menos de lo que le corresponde, en silencio—. `canonizar_telefono`
reduce a dígitos y antepone el 51 a los móviles peruanos; lo que ya trae código
de país o no encaja en ese patrón se deja intacto, porque inventarle un prefijo
a un número extranjero lo convertiría en otro número.

El alta pide el celular por eso, y lo dice donde lo pide: es lo que enlaza la
cuenta con el canal que sigue funcionando cuando la app no puede.

El primer contacto recibe el aviso del §13.4 y **no se procesa nada más** hasta
que responda `ACEPTO`. Se guarda cuándo aceptó y qué versión del aviso: demostrar
el consentimiento exige poder reproducir qué se aceptó, no solo que se aceptó.

## Cola y carga (§29)

```
prioridad: rojo > negro > amarillo > verde      (colas de Celery homónimas)

profundidad = peticiones al modelo en vuelo      app/core/queue.py
  rojo                     → plantilla fija SIEMPRE, sin diferida
  negro                    → plantilla fija SIEMPRE, sin diferida (§25)
  amarillo + cola > 32     → plantilla fija + respuesta diferida
  el resto                 → el modelo responde, una sola vez
```

**Tres textos se devuelven sin preguntar al modelo**: la plantilla de nivel
rojo (§18), la de nivel negro (§25) y `sin ruta verificable` (§20.5). Amarillo y
verde tuvieron plantilla propia y se quitaron: devolvían consejo genérico sin mirar la
pregunta —a «agua entrando a mi casa» contestaban lo mismo que a cualquier otra
cosa— y una respuesta instantánea que no responde no es una respuesta.

Y por eso **una pregunta da una respuesta**. Se difiere únicamente lo que quedó
incompleto, que hoy es solo la plantilla de cola llena. El rojo no se difiere
—su plantilla ya es la respuesta correcta— y `sin ruta verificable` tampoco:
recalcularla podría contradecir al §20.5, que fija el texto palabra por
palabra.

El umbral es `SENTI_LLM_QUEUE_MAX_DEPTH`, 32 por defecto. La diferida la calcula
un worker y se guarda como un mensaje más. El worker corre el mismo pipeline en
`modo_diferido`, porque si no volvería a tomar el atajo del acuse y la respuesta
diferida existiría sin aportar nada. El rojo **no se difiere**: su respuesta
fija ya es la correcta (§18).

**El acuse no es una respuesta y no se guarda como tal.** Cuando viene una
respuesta detrás, el acuse no se persiste ni se pinta como mensaje: es la señal
de que el sistema está en ello, y el cliente la muestra como estado. Guardarlo
dejaba dos mensajes del asistente para una sola pregunta, y al reabrir el hilo
aparecían los dos como si hubiera contestado dos veces.

La excepción es que falle el encolado: entonces el acuse **sí** se guarda,
porque pasa a ser lo único que el ciudadano va a recibir.

**La recogida es obligatoria en el cliente.** La respuesta llega en
`respuesta_diferida_en_curso`; con ella el cliente sondea
`GET /chat/{id}/mensajes` hasta que aparece el mensaje nuevo, y mientras tanto
avisa de que falta algo. La ventana es de tres minutos con espera creciente:
medido en el servidor, una respuesta tarda 15,8 s aislada y hasta 75 s con
varias conversaciones a la vez. Se sondea en vez de mantener una conexión abierta
porque este canal se diseña para redes que se caen: si el sondeo falla, el
mensaje sigue guardado y se recupera al reabrir el hilo. Android además
restaura el hilo al arrancar, que es lo que hace que reabrirlo signifique algo.

Sin esa recogida el sistema queda peor que si no existiera: el ciudadano lee el
acuse y cree que eso era la respuesta.

La medida falla hacia **no degradar**: si Valkey no responde, `profundidad()`
devuelve 0. Degradar por un contador roto sería una avería silenciosa que
empeora el servicio sin carga real. Por el mismo motivo se cuenta con un
conjunto ordenado con marca de tiempo y no con un contador: un worker que muere
deja basura que caduca sola en vez de dejar el sistema degradado para siempre.

## RAG (§19)

Precedencia de fuentes: API oficial → servicio geográfico → boletín → documento
→ comunicado municipal → reporte validado → probable → pendiente → web oficial
→ **Gemma, siempre el último**. El RAG es lo que hay por encima del modelo: sin
él, una pregunta general la respondería con lo que recuerde.

| Regla | Por qué |
|---|---|
| troceado por párrafo, no por caracteres | partir separa «no cruce el cauce» de «si el agua supera la rodilla» |
| búsqueda híbrida léxica + vectorial | «huaico» es peruanismo; «qué hago si sube el agua» no casa por palabras con «inundación súbita» |
| vigencia filtrada en el SQL | un fragmento caducado no debe llegar ni a ordenarse |
| cada fragmento lleva institución, URL y hash | §11.4 y §12 |
| umbral absoluto 0,62 **y** corte relativo al mejor (0,92) | con corpus pequeño todo supera el absoluto y se cuelan fragmentos de relleno |
| sin embeddings → solo texto, y se reindexa después | un documento buscable por palabras es mejor que uno perdido |

## Lo que el modelo no puede hacer (§25)

Predecir sismos · inventar alertas, refugios o teléfonos · declarar una vía
segura · cambiar un nivel oficial · extender una vigencia · confirmar un
reporte · recomendar medicamentos · mezclar reportes ciudadanos con fuentes
oficiales · citarse a sí mismo como fuente · concluir sobre una imagen (solo
observa).

Esto está impedido **por código**, no por prompt, y con dos mecanismos distintos
según el camino:

- **Chat**: el modelo devuelve texto libre y lo verifica la guardia de lenguaje
  de `rules/response.py`, que descarta la salida y cae a plantilla. Además la
  recorta a 320 caracteres.
- **Análisis (§15, §21.1, imágenes)**: esquema Pydantic en `llm/schemas.py`,
  enviado como `response_format` y **validado otra vez al recibir**, porque
  confiar en que el servidor cumplió no es verificar. El esquema de imagen tiene
  `observacion` y `confianza`, y ningún campo donde escribir una conclusión.

## Frases fijas

| Situación | Texto |
|---|---|
| ruta | «la ruta de menor riesgo según la información disponible» |
| sin ruta | §20.5 literal, con 110 · 0800-12345 · 115 |
| sin evidencia | «No pude verificar información oficial suficiente para responder.» |
| reporte sin validar | «Este reporte es ciudadano y todavía no ha sido validado.» |
| sin señal | §7.5 literal, sin intervención del modelo |

## Entidades (§27)

29 tablas. El rol no es una de ellas: es un enum en la columna del usuario,
validado en `core/security.py`.

`users` `consents` `household_profiles` · `alerts` `alert_zones`
`alert_subscribers` `municipal_notices` · `official_sources` `source_health`
`documents` `document_chunks` · `citizen_reports` `report_validations`
`resources` · `hazards` `affected_roads` `road_blocks` `routes`
`route_segments` · `family_plans` `plan_tasks` `conversations` `messages`
`incidents` · `audit_logs` `retention_jobs` `risk_parameters` `protocols`
`emergency_phones`

`alert_subscribers` es la única tabla con un teléfono en claro (§13.4): nace
solo del consentimiento explícito `ALERTAS_WHATSAPP` en `POST /auth/registro`,
nunca por inferencia desde `users.phone_pseudonym` (que sigue siendo
irreversible para todo lo demás).

## Herramientas (§16)

`consultar_alerta_actual` `consultar_perfil_hogar` `buscar_recursos_cercanos`
`calcular_ruta` `crear_plan_familiar` `consultar_reporte`
`consultar_estado_fuentes` `preparar_mensaje_contacto`
`guardar_informacion_offline` `consultar_web_oficial`

**La herramienta la elige el router, y solo si no reconoce nada, el modelo.**
Cuando el router identifica la intención, la herramienta se ejecuta ahí mismo:
una llamada al modelo en vez de dos, sin catálogo en el prompt y sin
razonamiento. Se probó dejando elegir siempre al modelo y se midió en el
servidor: **18-80 s por mensaje, contra ~2 s con el router**. En un sistema
donde alguien puede estar esperando, eso no es un matiz.

Cuando el router no reconoce nada —una frase que nadie previó— sí decide el
modelo, y se paga el coste solo en el caso que antes se perdía. El catálogo que
ve lo filtra el backend por rol (§6): un permiso no se le pide por favor en el
prompt, se aplica quitando la herramienta de la lista.

Tres barreras por llamada, todas en el backend: registro cerrado · permiso por
rol (§6) · argumentos validados. Y una cuarta que no es una barrera sino una
sustitución: **dónde está el usuario no lo escribe el modelo**. El distrito sale
del perfil (§13.2) y las coordenadas del mensaje; se sobrescriben siempre, sobre
las claves que la herramienta declare. Sin eso, «¿hay alerta en mi distrito?»
llamaba a la herramienta con `zona="mi distrito"`, que no es ningún sitio.

Elegir no es ejecutar. El modelo pide; el backend valida y ejecuta. Y cuando
`calcular_ruta` devuelve que no hay ruta verificable, la respuesta la escribe el
backend con el literal del §20.5: si el modelo redactara sobre ese resultado,
acabaría ofreciendo la menos mala.

El router determinista no es un modelo pequeño, y no por ahorro: un
clasificador estadístico no se puede probar caso por caso, y todo el diseño
descansa en que las decisiones sean deterministas y medibles (§32).

## Permisos (§6)

| | ciudadano | validador | operador | admin |
|---|:-:|:-:|:-:|:-:|
| consultar alertas · chat · rutas | sí | sí | sí | sí |
| configurar hogar / plan | sí | no | no | no |
| crear reporte | sí | sí | sí | no |
| validar reporte | no | sí | sí | no |
| cerrar vía / recursos / comunicado | no | no | sí | no |
| usuarios y fuentes | no | no | no | sí |
| auditoría | no | propia | propia | completa |

Validados en backend, nunca solo en el cliente. La auditoría limitada del §6 se
modela como un permiso distinto (`CONSULTAR_AUDITORIA_PROPIA`) y no como una
versión debilitada del mismo.

**La contraseña no tiene longitud mínima**, por decisión de producto: se
registra gente con prisa y desde teclados incómodos. Queda el máximo de 128
porque bcrypt trunca a 72 bytes y aceptar entradas enormes solo regala trabajo
de hash a quien quiera saturar el registro. El rol nunca sale del formulario:
el registro público crea ciudadanos y lo cambia un administrador (§6).

**El chat no exige cuenta.** El §13.4 pide un modo invitado que dé información
general, así que `/chat` acepta petición sin token. El permiso no desaparece:
se comprueba una capa más abajo, en cada herramienta que lo requiere
(`preparar_mensaje_contacto`, `guardar_informacion_offline`…). Quien entra sin
cuenta conversa y recibe información general; lo que toca sus datos no se
ejecuta, porque no hay usuario del que sacarlos.

Cuando el invitado pregunta algo que necesitaba una herramienta, **la
limitación la añade el backend**, con la fórmula del §11.3: «no significa que no
haya peligro: significa que no tengo el dato». Dejarlo en manos del modelo
producía respuestas que pedían la ubicación —incluso teniéndola ya— y prometían
una consulta que nunca iba a ocurrir.

## Modelos y servicios de inferencia

El chat, la visión y el análisis profundo usan **Gemma 4 E4B** cuantizado a Q4
en llama.cpp (`llama-cpu:1234`). El backend lo identifica como
`google/gemma-4-e4b`; `/health/detalle` verifica que el modelo esté cargado,
que tenga visión y que el contexto servido sea 8192.

El sondeo independiente de fuentes usa **Gemma 2B** en `llama-citizen:1236`.
El backend consulta primero los feeds oficiales en paralelo, valida fecha,
coordenadas y vigencia, clasifica el tipo con reglas deterministas y solo
después puede pedir al 2B un resumen factual del título. El 2B no decide tipo,
ubicación, fecha, vigencia ni confirma reportes; tampoco sustituye al Gemma 4B
del chat.

Los embeddings del RAG se sirven aparte en `llama-embed-cpu:1235`, con
`nomic-embed-text-v1.5` y 768 dimensiones. Valhalla atiende las rutas en
`valhalla:8002`; Google Maps solo dibuja el mapa en los clientes.

**El modelo no es intercambiable por cualquiera del mismo tamaño.** Se probó
con `gemma-3-4b`, que ocupa la mitad: su plantilla no declara herramientas y
llama.cpp rechaza la petición entera con *«Unable to generate parser for this
template»*. Gemma 4 sí las declara, y además razona antes de emitir la llamada
—por eso `enable_thinking` se activa solo en el turno que elige (§16)—.

Cuando la plantilla no admite herramientas, el cliente reintenta sin catálogo
en vez de caer a plantilla fija: quien decidió qué consultar fue el router y el
resultado ya viene verificado, así que al modelo solo le queda redactar. Perder
la respuesta entera por eso sería desproporcionado.

`SENTI_LLM_CONTEXT_LENGTH` (8192) debe coincidir con el `--ctx-size` del
contenedor. Si no coinciden, las respuestas se cortan sin que nada dé error: es
lo que avisa `/health/detalle`.

## Presupuesto en CPU

Servidor de 10 vCPU (5 núcleos físicos) sin GPU. El coste está en el prompt
fijo, no en la generación.

**Lo que cuesta que elija el modelo.** Ofrecerle las diez herramientas son
~1261 tokens de esquemas en cada petición, y elegir obliga a llamarlo dos veces:
una para que pida la herramienta y otra para que redacte con el resultado. Antes
un router de regex elegía por él y el backend rellenaba los argumentos, así que
bastaba una llamada con 105-214 tokens de esquema. Se cambió a propósito: el
router solo reconocía lo que alguien pensó en escribir.

Mitigaciones vigentes, todas medidas en el servidor de despliegue:

| medida | efecto |
|---|---|
| `--threads 5` | 3,6 s → 2,0 s (de 5 a 10 hilos ya no gana: límite de memoria) |
| `--cache-reuse 256` | no reprocesa el prefijo común |
| `enable_thinking: false` **siempre** | razonar le costaba ~350 fichas: 35 s a 10 fichas/s. Elige el router, que no delibera |
| `max_tokens: 80` · ≤320 caracteres | 80 fichas ≈ 320 caracteres: generar más era generar para tirarlo |
| `--cache-type-k/v q8_0` | la caché KV es lo que más se lee por ficha; a la mitad de bytes, +8,6 % |
| `--threads 4` · `--threads-batch 8` | generar está limitado por memoria y no escala; leer el prompt sí |
| `--mlock` | fija el GGUF en RAM para que el kernel no expulse páginas del modelo |

El router no es un modelo pequeño, y no por ahorro: un clasificador estadístico
no se puede probar caso por caso, y todo el diseño descansa en que las
decisiones sean deterministas y medibles (§32).

Lo urgente nunca espera al modelo: rojo responde en 0,2 ms y amarillo/verde
reciben acuse con respuesta diferida (§29).

## Despliegue, operación y validación

El flujo autorizado es siempre:

```text
local: editar → validar → commit → push
servidor: git pull → docker compose build → docker compose up -d → validar
```

El servidor expone la API en el puerto 8000 y el panel de reportes en el 8080.
PostGIS/pgvector, Valkey, Valhalla y los modelos quedan restringidos a la red
interna o a `127.0.0.1`. Las claves y contraseñas viven en `.env`, que nunca se
versiona.

Comprobaciones mínimas después de cada despliegue:

```bash
docker compose config --quiet
docker compose ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/health/detalle
curl -fsS http://127.0.0.1:8000/fuentes/estado
curl -fsS http://127.0.0.1:8080/
docker compose exec -T api sh -c "ruff check app tests && python -m pytest tests/ -q"
```

La validación operativa del servidor realizada el **31/07/2026** confirmó:

| Componente | Resultado |
|---|---|
| API `/health` | HTTP 200 |
| API `/health/detalle` | PostGIS 3.5, pgvector 0.8.5, Gemma 4E4B y embeddings disponibles |
| Panel web | HTTP 200 en el puerto 8080 |
| IGP, INDECI y SENAMHI | `ok`, verificadas y citables |
| Sondeo paralelo de fuentes | ejecutado; sin datos recientes válidos en esa ventana |
| Registro de eventos | 0 eventos nuevos; no se registraron datos antiguos como actuales |

Un sondeo con cero eventos no significa ausencia de peligro: significa que no
se recibió un dato oficial reciente que cumpla las reglas. La interfaz debe
mostrar el estado de la fuente y su limitación, nunca convertir el silencio en
una garantía de seguridad.
