package com.example.senti.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.senti.data.Api
import com.example.senti.data.OfflineStore
import com.example.senti.data.Fuente
import com.example.senti.data.Lugar
import com.example.senti.data.PaqueteOffline
import com.example.senti.data.Punto
import com.example.senti.data.RutaCalculada
import com.example.senti.data.ReporteResumen
import com.example.senti.data.TextosFijos
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlin.math.cos
import kotlin.math.pow

// §29: la ventana tiene que cubrir lo que de verdad tarda el worker, no lo que
// nos gustaría que tardara. Medido en el servidor de despliegue: 15,8 s una
// consulta aislada y hasta 75 s con varias conversaciones a la vez, porque el
// modelo corre en CPU y las peticiones comparten los mismos cuatro núcleos.
//
// Con medio minuto la app se rendía justo antes de que llegara la respuesta:
// el worker la dejaba en el hilo y nadie la recogía. Tres minutos cubren el
// caso malo y siguen por debajo del timeout HTTP del cliente.
//
// Se sondea con espera creciente: los primeros intentos son frecuentes para
// que una respuesta rápida se vea enseguida, y luego se espacian para no
// gastar batería esperando a un servidor cargado.
private const val ESPERA_DIFERIDA_MS = 1_500L
private const val ESPERA_DIFERIDA_MAX_MS = 6_000L
private const val VENTANA_DIFERIDA_MS = 180_000L

/**
 * Un mensaje de la conversación tal como lo muestra la UI.
 *
 * `plantillaFija` y `urgencia` no son detalles internos: el §12 exige
 * distinguir visualmente el origen de la información, y una respuesta de
 * plantilla fija es exactamente el caso en que el sistema NO consultó nada.
 * Ocultarlo haría pasar una respuesta genérica por una verificada.
 */
data class Mensaje(
    val texto: String,
    val esUsuario: Boolean,
    val urgencia: String? = null,
    val plantillaFija: Boolean = false,
    val fuentes: List<Fuente> = emptyList(),
    val sinConexion: Boolean = false,
    val tieneImagen: Boolean = false,
    // La imagen enviada, para poder mostrarla en su burbuja. Se guarda el
    // mismo base64 que viajó al servidor —ya redimensionado a 1280 px y
    // comprimido— en lugar del Uri original: los permisos de un Uri del
    // selector caducan, y entonces la foto desaparecería de la conversación.
    val imagenBase64: String? = null,
    // §7.3: la ruta acompaña al mensaje que la generó. Los pasos ya están en
    // el texto; esto solo habilita el mapa, que es una mejora.
    val ruta: RutaCalculada? = null,
    // Un sitio concreto —un refugio, un centro de salud— que el backend
    // encontró y verificó. Habilita abrirlo en Google Maps. Igual que la
    // ruta: el nombre, la dirección y la distancia ya van en el texto.
    val lugar: Lugar? = null,
    val lugarSugerido: Lugar? = null,
)

data class SentiUiState(
    val mensajes: List<Mensaje> = emptyList(),
    val enviando: Boolean = false,
    val autenticando: Boolean = false,
    val reportando: Boolean = false,
    val conversationId: String? = null,
    val autenticado: Boolean = false,
    val sinConexion: Boolean = false,
    val paquete: PaqueteOffline? = null,
    val error: String? = null,
    val reporteResultado: String? = null,
    val reportes: List<ReporteResumen> = emptyList(),
    val cargandoReportes: Boolean = false,
    val lat: Double? = null,
    val lon: Double? = null,
    val ubicacionPedida: Boolean = false,
    val hiloReanudado: Boolean = false,
    /**
     * §29: el acuse ya se mostró y el worker está calculando la respuesta.
     *
     * Se enseña para que el silencio de los siguientes segundos no parezca que
     * la app se colgó. Lo que llega después no sustituye al acuse: se añade.
     */
    val esperandoDiferida: Boolean = false,
    /** Ruta que se está viendo a pantalla completa, si hay alguna. */
    val rutaEnMapa: RutaCalculada? = null,
    val recalculandoRuta: Boolean = false,
    val mapaEnModoMarcado: Boolean = false,
    /**
     * Mensaje del §20.5 cuando, al esquivar lo que el usuario marcó, no queda
     * ninguna ruta verificable. Se muestra tal cual: es un texto fijo, no algo
     * que redacte el modelo.
     */
    val sinRutaTrasMarcar: String? = null,
)

class SentiViewModel(app: Application) : AndroidViewModel(app) {

    private val store = OfflineStore(app)
    private val _estado = MutableStateFlow(SentiUiState())
    val estado: StateFlow<SentiUiState> = _estado.asStateFlow()

    init {
        viewModelScope.launch {
            // El paquete offline se carga ANTES de intentar la red: si no hay
            // cobertura, la app ya tiene algo que mostrar en vez de una
            // pantalla vacía con un spinner (§26).
            _estado.update { it.copy(paquete = store.leer()) }
        }
        viewModelScope.launch {
            // El hilo se guardaba al enviar pero nadie lo recuperaba, así que
            // cerrar la app abría una conversación nueva y el backend perdía el
            // contexto —y con él, cualquier respuesta diferida del §29 que
            // hubiera llegado mientras tanto—.
            val hilo = store.hiloVigente() ?: return@launch
            _estado.update { it.copy(conversationId = hilo, hiloReanudado = true) }
            cargarHistorial(hilo)
        }
    }

    fun iniciarSesion(email: String, password: String) = viewModelScope.launch {
        _estado.update { it.copy(autenticando = true, error = null) }
        runCatching { Api.login(email, password) }
            .onSuccess {
                _estado.update { e ->
                    e.copy(
                        autenticado = true,
                        autenticando = false,
                        error = null,
                        sinConexion = false,
                    )
                }
                sincronizarOffline()
            }
            .onFailure { exc ->
                _estado.update { e ->
                    e.copy(
                        autenticando = false,
                        error = "No se pudo iniciar sesión. Verifica tus datos o la conexión.",
                    )
                }
            }
    }

    fun registrar(
        email: String,
        password: String,
        displayName: String?,
        municipality: String?,
    ) = viewModelScope.launch {
        _estado.update { it.copy(autenticando = true, error = null) }
        runCatching { Api.registro(email, password, displayName, municipality) }
            .onSuccess {
                _estado.update { e ->
                    e.copy(
                        autenticado = true,
                        autenticando = false,
                        error = null,
                        sinConexion = false,
                    )
                }
                sincronizarOffline()
            }
            .onFailure {
                _estado.update { e ->
                    e.copy(
                        autenticando = false,
                        error = "No se pudo crear la cuenta. Revisa los campos o usa otro correo.",
                    )
                }
            }
    }

    fun enviar(
        texto: String,
        imagenBase64: String? = null,
        imagenMime: String = "image/jpeg",
    ) = viewModelScope.launch {
        if (texto.isBlank() && imagenBase64 == null) return@launch
        val textoUsuario = texto.ifBlank { "Imagen enviada para evaluación" }
        _estado.update {
            it.copy(
                mensajes = it.mensajes + Mensaje(
                    texto = textoUsuario,
                    esUsuario = true,
                    tieneImagen = imagenBase64 != null,
                    imagenBase64 = imagenBase64,
                ),
                enviando = true,
                error = null,
            )
        }

        runCatching {
            Api.chat(
                texto = texto.ifBlank { "Analiza la imagen y orienta al usuario." },
                conversationId = _estado.value.conversationId,
                imagenBase64 = imagenBase64,
                imagenMime = imagenMime,
                lat = _estado.value.lat,
                lon = _estado.value.lon,
            )
        }
            .onSuccess { r ->
                r.conversationId?.let { id -> viewModelScope.launch { store.tocarHilo(id) } }
                _estado.update {
                    // §29: cuando viene una respuesta detrás, el acuse no se
                    // pinta como mensaje. No es una respuesta, es "estoy en
                    // ello", y ya se muestra como estado bajo el hilo. Pintarlo
                    // dejaba dos burbujas del asistente para una sola pregunta.
                    val mensajes = if (r.diferidaEnCurso) {
                        it.mensajes
                    } else {
                        it.mensajes + Mensaje(
                            texto = r.texto,
                            esUsuario = false,
                            urgencia = r.urgencia,
                            plantillaFija = r.plantillaFija,
                            fuentes = r.fuentes,
                            ruta = r.ruta,
                            lugar = r.lugar,
                            lugarSugerido = r.lugarSugerido,
                        )
                    }
                    it.copy(
                        mensajes = mensajes,
                        conversationId = r.conversationId ?: it.conversationId,
                        hiloReanudado = false,
                        enviando = false,
                        sinConexion = false,
                        esperandoDiferida = r.diferidaEnCurso,
                    )
                }
                // §29: el acuse no es la respuesta. El worker la calcula y la
                // guarda como un mensaje más del hilo; si nadie la recoge, se
                // queda ahí para siempre y el ciudadano solo ve el acuse.
                val hilo = r.conversationId ?: _estado.value.conversationId
                if (r.diferidaEnCurso && hilo != null) recogerDiferida(hilo)
            }
            .onFailure {
                // §26 y §29: sin red la app no se queda muda. Responde con lo
                // que tiene guardado y lo marca como tal, con su fecha.
                _estado.update { e ->
                    e.copy(
                        mensajes = e.mensajes + Mensaje(
                            texto = respuestaSinConexion(e.paquete),
                            esUsuario = false,
                            sinConexion = true,
                        ),
                        enviando = false,
                        sinConexion = true,
                    )
                }
            }
    }

    fun abrirMapa(ruta: RutaCalculada) = _estado.update {
        it.copy(rutaEnMapa = ruta, mapaEnModoMarcado = false)
    }

    fun abrirMapaParaBloqueo() {
        val lat = _estado.value.lat ?: return
        val lon = _estado.value.lon ?: return
        _estado.update {
            it.copy(
                rutaEnMapa = RutaCalculada(origenLat = lat, origenLon = lon),
                mapaEnModoMarcado = true,
            )
        }
    }

    fun cerrarMapa() = _estado.update { it.copy(rutaEnMapa = null, mapaEnModoMarcado = false) }

    /** Empieza un hilo nuevo sin borrar los hilos ya guardados en el servidor. */
    fun nuevoChat() = _estado.update {
        it.copy(
            mensajes = emptyList(),
            conversationId = null,
            hiloReanudado = false,
            error = null,
            reporteResultado = null,
        )
    }

    /**
     * Recalcula la ruta esquivando lo que el usuario marcó.
     *
     * Se hace a petición suya y no automáticamente al marcar: marcar tres
     * tramos seguidos dispararía tres cálculos, y cada uno tarda. Además, si
     * el resultado fuese "no hay ruta verificable", conviene que llegue cuando
     * ha terminado de decir lo que sabe y no a mitad.
     */
    /**
     * Recalcula esquivando lo marcado y, si se indicó, hacia otro destino.
     *
     * `destino` gana sobre el que traía la ruta: si alguien lo marca en el
     * mapa es porque quiere ir ahí, no al refugio más cercano que se eligió
     * por él. Sin destino marcado se conserva el anterior, y sin ninguno se
     * pide ruta de escape (§34.2).
     */
    fun recalcularRuta(evitar: List<Punto>, destino: Punto? = null) = viewModelScope.launch {
        val ruta = _estado.value.rutaEnMapa ?: return@launch
        val oLat = ruta.origenLat ?: _estado.value.lat
        val oLon = ruta.origenLon ?: _estado.value.lon
        val dLat = destino?.lat ?: ruta.destinoLat
        val dLon = destino?.lon ?: ruta.destinoLon
        if (oLat == null || oLon == null || (dLat == null) != (dLon == null)) {
            _estado.update { it.copy(error = "Falta la ubicación para calcular la salida.") }
            return@launch
        }

        _estado.update { it.copy(recalculandoRuta = true, sinRutaTrasMarcar = null) }

        // Varios toques sobre la misma zona no deben convertirse en varios
        // `exclude_locations`: Valhalla puede terminar cerrando todos los
        // accesos aunque el usuario solo haya señalado un bloqueo.
        val evitarConsolidados = evitar.consolidarZonas()
        runCatching {
            if (dLat == null || dLon == null) {
                Api.rutaDeEscape(oLat, oLon, evitarConsolidados)
            } else {
                Api.recalcularRuta(oLat, oLon, dLat, dLon, evitarConsolidados)
            }
        }
            .onSuccess { r ->
                _estado.update { e ->
                    if (r.sinRutaVerificable) {
                        // §20.5: no se devuelve "la menos mala" ni se ignoran
                        // las marcas para poder enseñar algo. Se dice.
                        e.copy(
                            recalculandoRuta = false,
                            sinRutaTrasMarcar = r.mensaje ?: TextosFijos.SIN_RUTA,
                        )
                    } else {
                        e.copy(
                            recalculandoRuta = false,
                            rutaEnMapa = r.aRutaCalculada(ruta.destino),
                            mapaEnModoMarcado = false,
                        )
                    }
                }
            }
            .onFailure { ex ->
                _estado.update {
                    it.copy(
                        recalculandoRuta = false,
                        error = "No se pudo recalcular: ${ex.message ?: "sin conexión"}",
                    )
                }
            }
    }

    fun descartarAvisoSinRuta() = _estado.update { it.copy(sinRutaTrasMarcar = null) }

    fun marcarBloqueo(lat: Double, lon: Double) = viewModelScope.launch {
        runCatching {
            Api.crearReporte(
                tipo = "via_bloqueada",
                descripcion = "Vía marcada como intransitable desde el mapa.",
                lat = lat,
                lon = lon,
                direccionAproximada = null,
                distrito = null,
                fotoBase64 = null,
            )
        }.onFailure { e ->
            _estado.update {
                it.copy(error = "No se pudo enviar la marca: ${e.message ?: "sin conexión"}")
            }
        }
    }

    fun crearReporte(
        tipo: String,
        descripcion: String,
        lat: Double?,
        lon: Double?,
        direccion: String?,
        distrito: String?,
        fotoBase64: String? = null,
    ) = viewModelScope.launch {
        if (descripcion.isBlank() || lat == null || lon == null) {
            _estado.update {
                it.copy(error = "Completa descripción, latitud y longitud para enviar el reporte.")
            }
            return@launch
        }

        _estado.update { it.copy(reportando = true, error = null, reporteResultado = null) }
        runCatching {
            Api.crearReporte(
                tipo = tipo,
                descripcion = descripcion,
                lat = lat,
                lon = lon,
                direccionAproximada = direccion?.ifBlank { null },
                distrito = distrito?.ifBlank { null },
                fotoBase64 = fotoBase64,
            )
        }
            .onSuccess { r ->
                _estado.update {
                    it.copy(
                        reportando = false,
                        reporteResultado = "Reporte enviado. Estado: ${r.estado}. Confianza: ${r.confianza}.",
                    )
                }
                // Recargar: el reporte recién creado tiene que aparecer en la
                // lista, y además su nivel de confianza puede haber subido a
                // «probable» si coincidía con otro (§21.2).
                cargarReportes(lat, lon)
            }
            .onFailure {
                _estado.update {
                    it.copy(
                        reportando = false,
                        error = "No se pudo enviar el reporte. Verifica tu sesión y la conexión.",
                    )
                }
            }
    }

    fun sincronizarOffline() = viewModelScope.launch {
        runCatching { Api.paqueteOffline() }
            .onSuccess { p ->
                store.guardar(p)
                _estado.update { it.copy(paquete = p, sinConexion = false) }
            }
            .onFailure { _estado.update { it.copy(error = "No se pudo descargar el paquete sin conexión.") } }
    }

    private fun respuestaSinConexion(paquete: PaqueteOffline?): String = buildString {
        appendLine(TextosFijos.SIN_CONEXION)
        if (paquete != null) {
            appendLine("Última sincronización: ${paquete.sincronizadoAt}")
            paquete.ultimaAlerta?.let {
                appendLine()
                appendLine("Última alerta descargada (${it.fecha}): ${it.titulo}")
                appendLine(it.advertencia)
            }
            appendLine()
            appendLine("Teléfonos de emergencia:")
            paquete.telefonos.forEach { appendLine("· ${it.situacion}: ${it.numero}") }
        } else {
            appendLine()
            appendLine("Teléfonos de emergencia:")
            TextosFijos.TELEFONOS.forEach { appendLine("· ${it.situacion}: ${it.numero}") }
        }
        appendLine()
        appendLine(TextosFijos.SIN_SENAL)
    }

    /** Reportes vigentes de la zona (§21). */
    fun cargarReportes(lat: Double? = null, lon: Double? = null) = viewModelScope.launch {
        _estado.update { it.copy(cargandoReportes = true) }
        runCatching { Api.listarReportes(lat, lon) }
            .onSuccess { r ->
                _estado.update {
                    it.copy(reportes = r.reportes, cargandoReportes = false, sinConexion = false)
                }
            }
            .onFailure {
                // Sin red se conserva la última lista conocida en vez de
                // vaciarla: una lista vieja con su aviso es más útil que una
                // pantalla en blanco (§26).
                _estado.update { it.copy(cargandoReportes = false, sinConexion = true) }
            }
    }

    /** Recupera los mensajes de un hilo, incluidas las diferidas (§29). */
    private fun cargarHistorial(conversationId: String) = viewModelScope.launch {
        runCatching { Api.mensajes(conversationId) }
            .onSuccess { historial ->
                _estado.update { e ->
                    e.copy(
                        mensajes = historial.map { m ->
                            Mensaje(
                                texto = m.contenido,
                                esUsuario = m.rol == "user",
                                urgencia = m.urgencia,
                                plantillaFija = m.respuestaPlantillaFija,
                                fuentes = m.fuentes,
                            )
                        }
                    )
                }
            }
    }

    /**
     * §29: espera a que el worker deje la respuesta diferida y la muestra.
     *
     * Se sondea en vez de abrir una conexión persistente porque el canal ya
     * está pensado para redes que se caen: si el sondeo falla, el mensaje sigue
     * guardado en el servidor y se recupera al reabrir el hilo.
     */
    private fun recogerDiferida(conversationId: String) = viewModelScope.launch {
        val previos = _estado.value.mensajes.size
        var espera = ESPERA_DIFERIDA_MS
        var transcurrido = 0L
        while (transcurrido < VENTANA_DIFERIDA_MS) {
            delay(espera)
            transcurrido += espera
            espera = (espera + 500L).coerceAtMost(ESPERA_DIFERIDA_MAX_MS)
            val historial = runCatching { Api.mensajes(conversationId) }.getOrNull() ?: continue
            if (historial.size > previos) {
                _estado.update { e ->
                    e.copy(
                        mensajes = historial.map { m ->
                            Mensaje(
                                texto = m.contenido,
                                esUsuario = m.rol == "user",
                                urgencia = m.urgencia,
                                plantillaFija = m.respuestaPlantillaFija,
                                fuentes = m.fuentes,
                            )
                        },
                        esperandoDiferida = false,
                    )
                }
                return@launch
            }
        }
        // Se agotaron los intentos. No se inventa nada ni se borra el acuse: la
        // respuesta está en el servidor y aparecerá al reabrir el hilo.
        _estado.update { it.copy(esperandoDiferida = false) }
    }

    /** Ubicación del dispositivo, cuando el usuario la concede (§13.2). */
    fun fijarUbicacion(lat: Double?, lon: Double?) {
        _estado.update { it.copy(lat = lat, lon = lon, ubicacionPedida = true) }
    }

    fun marcarUbicacionPedida() {
        _estado.update { it.copy(ubicacionPedida = true) }
    }
}

/** Conserva una sola exclusión por zona marcada, con una separación de 180 m. */
private fun List<Punto>.consolidarZonas(): List<Punto> = buildList {
    for (punto in this@consolidarZonas) {
        if (none { distanciaMetros(it, punto) < 180.0 }) add(punto)
        if (size == 24) break
    }
}

private fun distanciaMetros(a: Punto, b: Punto): Double {
    val dLat = (a.lat - b.lat) * 111_320.0
    val dLon = (a.lon - b.lon) * 111_320.0 * cos(Math.toRadians((a.lat + b.lat) / 2.0))
    return (dLat.pow(2) + dLon.pow(2)).pow(0.5)
}
