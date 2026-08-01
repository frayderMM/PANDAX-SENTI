package com.example.senti.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.parameter
import io.ktor.client.request.post
import io.ktor.client.request.put
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Cliente de la API de SENTI.
 *
 * El backend es la única fuente de verdad: la app no clasifica urgencias, no
 * decide si una vía está cerrada y no habla con el modelo. El §28 exige que
 * los permisos se validen en el backend, "nunca solo en el frontend", y esa
 * regla se cumple no dándole al cliente ninguna decisión que tomar.
 *
 * El timeout es alto a propósito: el modelo local corre en una RTX 4060 y el
 * primer mensaje tras un arranque en frío tarda decenas de segundos mientras
 * se carga el GGUF. Cortar antes solo produce reintentos que recargan el
 * modelo otra vez.
 */
object Api {

    // Servidor público de SENTI usado por la app Android.
    var baseUrl: String = "http://35.253.231.219:8000"
    var token: String? = null

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    private val client = HttpClient(Android) {
        install(ContentNegotiation) { json(json) }
        install(HttpTimeout) {
            requestTimeoutMillis = 180_000
            connectTimeoutMillis = 15_000
            socketTimeoutMillis = 180_000
        }
    }

    suspend fun login(email: String, password: String): TokenResponse {
        val respuesta: TokenResponse = client.post("$baseUrl/auth/login") {
            contentType(ContentType.Application.Json)
            setBody(LoginRequest(email, password))
        }.body()
        token = respuesta.accessToken
        return respuesta
    }

    suspend fun registro(
        email: String,
        password: String,
        displayName: String? = null,
        municipality: String? = null,
    ): TokenResponse {
        val respuesta: TokenResponse = client.post("$baseUrl/auth/registro") {
            contentType(ContentType.Application.Json)
            setBody(RegistroRequest(email, password, displayName, municipality))
        }.body()
        token = respuesta.accessToken
        return respuesta
    }

    suspend fun chat(
        texto: String,
        conversationId: String? = null,
        nivelOperacion: String = "N0",
        imagenBase64: String? = null,
        imagenMime: String = "image/jpeg",
        lat: Double? = null,
        lon: Double? = null,
    ): ChatResponse = client.post("$baseUrl/chat") {
        contentType(ContentType.Application.Json)
        token?.let { header("Authorization", "Bearer $it") }
        setBody(
            ChatRequest(
                texto = texto,
                conversationId = conversationId,
                canal = "android",
                nivelOperacion = nivelOperacion,
                imagenBase64 = imagenBase64,
                imagenMime = imagenMime,
                lat = lat,
                lon = lon,
            )
        )
    }.body()

    suspend fun perfil(): PerfilResponse = client.get("$baseUrl/perfil") {
        token?.let { header("Authorization", "Bearer $it") }
    }.body()

    /**
     * §13.2: guarda el perfil del hogar. El backend rechaza con 403 los campos
     * sensibles (movilidad reducida, discapacidad, medicamentos) y el contacto
     * de confianza si no hay consentimiento previo para esa finalidad — hay
     * que pedirlo con [registrarConsentimiento] antes de reintentar.
     */
    suspend fun guardarPerfil(datos: PerfilEntrada): GuardarPerfilResponse =
        client.put("$baseUrl/perfil") {
            contentType(ContentType.Application.Json)
            token?.let { header("Authorization", "Bearer $it") }
            setBody(datos)
        }.body()

    /**
     * §13.4: el texto exacto y versionado que se le muestra a alguien antes de
     * aceptar cada finalidad. No es texto de la app: es el mismo aviso legal
     * que ve quien entra por WhatsApp, para no tener dos versiones distintas
     * de lo mismo.
     */
    suspend fun avisoConsentimiento(): AvisoConsentimientoResponse =
        client.get("$baseUrl/auth/aviso-consentimiento").body()

    suspend fun registrarConsentimiento(purpose: String, granted: Boolean): ConsentimientoResponse =
        client.post("$baseUrl/auth/consentimiento") {
            contentType(ContentType.Application.Json)
            token?.let { header("Authorization", "Bearer $it") }
            setBody(ConsentimientoEntrada(purpose, granted))
        }.body()

    /**
     * §26: el paquete que la app conserva sin conexión.
     *
     * Se descarga cuando hay red y se guarda tal cual, incluida
     * `sincronizadoAt`. La app muestra esa fecha, nunca la hora actual: el §26
     * prohíbe presentar una alerta antigua como vigente.
     */
    suspend fun paqueteOffline(): PaqueteOffline = client.get("$baseUrl/offline/paquete") {
        token?.let { header("Authorization", "Bearer $it") }
    }.body()

    /**
     * Recalcula la ruta esquivando lo que el usuario marcó en el mapa.
     *
     * Los puntos valen solo para esta petición y para nadie más: no cierran la
     * vía ni crean un reporte (§6, §21.2). Para publicar un reporte hay que
     * usar explícitamente el formulario correspondiente.
     */
    suspend fun recalcularRuta(
        origenLat: Double,
        origenLon: Double,
        destinoLat: Double,
        destinoLon: Double,
        evitar: List<Punto>,
    ): RutaRecalculada = client.post("$baseUrl/rutas") {
        contentType(ContentType.Application.Json)
        token?.let { header("Authorization", "Bearer $it") }
        setBody(
            RutaEntrada(
                origenLat = origenLat,
                origenLon = origenLon,
                destinoLat = destinoLat,
                destinoLon = destinoLon,
                evitar = evitar.map { PuntoEvitar(it.lat, it.lon) },
            )
        )
    }.body()

    suspend fun rutaDeEscape(
        origenLat: Double,
        origenLon: Double,
        evitar: List<Punto>,
    ): RutaRecalculada = client.post("$baseUrl/rutas") {
        contentType(ContentType.Application.Json)
        token?.let { header("Authorization", "Bearer $it") }
        setBody(
            RutaEntrada(
                origenLat = origenLat,
                origenLon = origenLon,
                haciaRefugio = true,
                evitar = evitar.map { PuntoEvitar(it.lat, it.lon) },
            )
        )
    }.body()

    suspend fun crearReporte(
        tipo: String,
        descripcion: String,
        lat: Double,
        lon: Double,
        direccionAproximada: String? = null,
        distrito: String? = null,
        fotoBase64: String? = null,
    ): ReporteResponse = client.post("$baseUrl/reportes") {
        contentType(ContentType.Application.Json)
        token?.let { header("Authorization", "Bearer $it") }
        setBody(
            ReporteRequest(
                tipo = tipo,
                descripcion = descripcion,
                lat = lat,
                lon = lon,
                direccionAproximada = direccionAproximada,
                distrito = distrito,
                fotoBase64 = fotoBase64,
            )
        )
    }.body()

    /**
     * Mensajes de un hilo, incluidas las respuestas diferidas del §29.
     *
     * Es lo que permite reanudar una conversación: sin esto el hilo seguía
     * vivo en el backend pero la pantalla salía en blanco, que para quien lo
     * usa es lo mismo que haberlo perdido.
     */
    suspend fun mensajes(conversationId: String): List<MensajeHistorial> =
        client.get("$baseUrl/chat/$conversationId/mensajes") {
            token?.let { header("Authorization", "Bearer $it") }
        }.body()

    /** Reportes vigentes de la zona. No incluye quién los hizo (§28). */
    suspend fun listarReportes(
        lat: Double? = null,
        lon: Double? = null,
        radioM: Double = 5000.0,
    ): ReportesResponse = client.get("$baseUrl/reportes") {
        token?.let { header("Authorization", "Bearer $it") }
        lat?.let { parameter("lat", it) }
        lon?.let { parameter("lon", it) }
        parameter("radio_m", radioM)
    }.body()

    suspend fun listarEventos(): EventosResponse = client.get("$baseUrl/api/events") {
        token?.let { header("Authorization", "Bearer $it") }
    }.body()
}

@Serializable
data class LoginRequest(val email: String, val password: String)

@Serializable
data class RegistroRequest(
    val email: String,
    val password: String,
    @SerialName("display_name") val displayName: String? = null,
    val municipality: String? = null,
)

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    val role: String,
    @SerialName("expires_in") val expiresIn: Int,
)

@Serializable
data class ChatRequest(
    val texto: String,
    @SerialName("conversation_id") val conversationId: String? = null,
    val canal: String = "android",
    @SerialName("nivel_operacion") val nivelOperacion: String = "N0",
    @SerialName("imagen_base64") val imagenBase64: String? = null,
    @SerialName("imagen_mime") val imagenMime: String = "image/jpeg",
    // §13.2: solo viaja si el usuario concedió el permiso. Sin ella el backend
    // no puede resolver "¿me afecta la alerta?" ni calcular una ruta, y
    // responde pidiéndola.
    val lat: Double? = null,
    val lon: Double? = null,
)

/**
 * Un sitio concreto que el backend encontró y verificó.
 *
 * §7.3: el texto de la respuesta ya lleva el nombre, la dirección y la
 * distancia, así que esto solo habilita el botón del mapa. Si no viene, no se
 * pierde nada: la instrucción escrita sigue completa.
 */
@Serializable
data class Lugar(
    val nombre: String? = null,
    val direccion: String? = null,
    @SerialName("distancia_m") val distanciaM: Int? = null,
    val lat: Double,
    val lon: Double,
    val tipo: String? = null,
    val sugerido: Boolean = false,
    // OSM acredita que existe y dónde, no que el municipio lo haya designado
    // ni que esté abierto. Quien lo lea tiene derecho a saberlo.
    @SerialName("ubicacion_referencial") val ubicacionReferencial: Boolean = false,
)

@Serializable
data class ChatResponse(
    val texto: String,
    val urgencia: String,
    @SerialName("respuesta_plantilla_fija") val plantillaFija: Boolean,
    @SerialName("motivo_plantilla") val motivoPlantilla: String? = null,
    val fuentes: List<Fuente> = emptyList(),
    @SerialName("latencia_ms") val latenciaMs: Double = 0.0,
    val modelo: String? = null,
    @SerialName("conversation_id") val conversationId: String? = null,
    val advertencias: List<String> = emptyList(),
    val ruta: RutaCalculada? = null,
    val lugar: Lugar? = null,
    @SerialName("lugar_sugerido") val lugarSugerido: Lugar? = null,
    // §29: amarillo y verde reciben acuse y el worker calcula la respuesta
    // aparte. Si esto viene a true, lo que se acaba de mostrar no es la
    // respuesta final: falta recogerla del hilo.
    @SerialName("respuesta_diferida_en_curso") val diferidaEnCurso: Boolean = false,
)

/**
 * Ruta devuelta por el motor (§20).
 *
 * `pasos` es la instrucción y basta por sí sola (§7.3). Las coordenadas del
 * destino solo sirven para ofrecer el mapa, que es una mejora: si el usuario no
 * tiene app de mapas o no quiere abrirla, la respuesta sigue siendo completa.
 */
@Serializable
data class RutaCalculada(
    val pasos: List<String> = emptyList(),
    @SerialName("distancia_m") val distanciaM: Int? = null,
    @SerialName("duracion_s") val duracionS: Int? = null,
    val destino: String? = null,
    @SerialName("destino_lat") val destinoLat: Double? = null,
    @SerialName("destino_lon") val destinoLon: Double? = null,
    @SerialName("origen_lat") val origenLat: Double? = null,
    @SerialName("origen_lon") val origenLon: Double? = null,
    /** Polilínea codificada de Valhalla, precisión 6. Ver [decodificarPolilinea]. */
    val geometria: String? = null,
    val bloqueos: List<BloqueoMapa> = emptyList(),
) {
    val puntos: List<Punto> get() = geometria?.let(::decodificarPolilinea) ?: emptyList()
}

/** Un cierre que la ruta esquivó. */
@Serializable
data class BloqueoMapa(
    val lat: Double,
    val lon: Double,
    @SerialName("radio_m") val radioM: Double,
    val motivo: String,
    /**
     * Si es `true` el cierre es oficial o municipal y la ruta lo excluyó; si es
     * `false` viene de un reporte comunitario validado, que penaliza pero no
     * excluye (§21.2). El mapa los pinta distinto porque significan cosas
     * distintas: uno es "no se puede pasar" y el otro "se ha reportado".
     */
    val vinculante: Boolean = true,
)

data class Punto(val lat: Double, val lon: Double)

/**
 * Decodifica el formato de polilínea de Valhalla (precisión 6).
 *
 * Se transporta codificada y no como lista de pares porque una ruta urbana son
 * varios cientos de puntos: codificada ocupa unas seis veces menos, y el §7.3
 * cuenta con que el canal puede estar degradado justo cuando esto se pide.
 */
fun decodificarPolilinea(codificada: String, precision: Int = 6): List<Punto> {
    val factor = Math.pow(10.0, precision.toDouble())
    val puntos = ArrayList<Punto>(codificada.length / 4)
    var indice = 0
    var lat = 0
    var lon = 0

    while (indice < codificada.length) {
        // Cada coordenada son grupos de 5 bits; el bit 0x20 dice "sigue".
        var desplazamiento = 0
        var resultado = 0
        var byte: Int
        do {
            if (indice >= codificada.length) return puntos
            byte = codificada[indice++].code - 63
            resultado = resultado or ((byte and 0x1f) shl desplazamiento)
            desplazamiento += 5
        } while (byte >= 0x20)
        lat += if (resultado and 1 != 0) (resultado shr 1).inv() else resultado shr 1

        desplazamiento = 0
        resultado = 0
        do {
            if (indice >= codificada.length) return puntos
            byte = codificada[indice++].code - 63
            resultado = resultado or ((byte and 0x1f) shl desplazamiento)
            desplazamiento += 5
        } while (byte >= 0x20)
        lon += if (resultado and 1 != 0) (resultado shr 1).inv() else resultado shr 1

        puntos.add(Punto(lat / factor, lon / factor))
    }
    return puntos
}

@Serializable
data class ReporteRequest(
    val tipo: String,
    val descripcion: String? = null,
    val lat: Double,
    val lon: Double,
    @SerialName("direccion_aproximada") val direccionAproximada: String? = null,
    val distrito: String? = null,
    @SerialName("foto_base64") val fotoBase64: String? = null,
)

@Serializable
data class ReporteResponse(
    val id: String,
    val estado: String,
    val confianza: String,
    @SerialName("motivo_confianza") val motivoConfianza: String? = null,
    @SerialName("vence_at") val venceAt: String? = null,
    val nota: String? = null,
)

/**
 * §11.4: institución, URL y hora de consulta. §12: hash del origen.
 * La UI muestra los cuatro campos; una fuente sin ellos no se presenta como
 * verificada.
 */
@Serializable
data class Fuente(
    val institucion: String? = null,
    val url: String? = null,
    val sha256: String? = null,
    @SerialName("consultada_at") val consultadaAt: String? = null,
    val confianza: String? = null,
)

@Serializable
data class PerfilResponse(
    @SerialName("tiene_perfil") val tienePerfil: Boolean,
    val nota: String? = null,
    val distrito: String? = null,
    @SerialName("zona_aproximada") val zonaAproximada: String? = null,
    val integrantes: Int = 1,
    val ninos: Int = 0,
    @SerialName("adultos_mayores") val adultosMayores: Int = 0,
    val mascotas: Int = 0,
    @SerialName("movilidad_reducida") val movilidadReducida: Boolean = false,
    val discapacidad: Boolean = false,
    @SerialName("medicamentos_habituales") val medicamentosHabituales: Boolean = false,
    val vehiculo: Boolean = false,
    @SerialName("punto_reunion_configurado") val puntoReunionConfigurado: Boolean = false,
    @SerialName("mochila_lista") val mochilaLista: Boolean = false,
    @SerialName("contacto_confianza_configurado") val contactoConfianzaConfigurado: Boolean = false,
)

/**
 * Entrada de `PUT /perfil`. Todos opcionales o con valor por defecto porque el
 * perfil es opcional (§13.2): guardar solo el distrito y dejar el resto en
 * blanco tiene que funcionar igual que rellenarlo entero.
 */
@Serializable
data class PerfilEntrada(
    val distrito: String? = null,
    @SerialName("zona_aproximada") val zonaAproximada: String? = null,
    val integrantes: Int = 1,
    val ninos: Int = 0,
    @SerialName("adultos_mayores") val adultosMayores: Int = 0,
    val mascotas: Int = 0,
    @SerialName("movilidad_reducida") val movilidadReducida: Boolean = false,
    val discapacidad: Boolean = false,
    @SerialName("medicamentos_habituales") val medicamentosHabituales: Boolean = false,
    val vehiculo: Boolean = false,
    @SerialName("medio_transporte") val medioTransporte: String? = null,
    @SerialName("punto_reunion_descripcion") val puntoReunionDescripcion: String? = null,
    @SerialName("contacto_confianza_telefono") val contactoConfianzaTelefono: String? = null,
    @SerialName("mochila_lista") val mochilaLista: Boolean = false,
)

@Serializable
data class GuardarPerfilResponse(val ok: Boolean, val distrito: String? = null)

/** Una finalidad del §13.4: por qué se pide cada dato y por cuánto se guarda. */
@Serializable
data class FinalidadConsentimiento(
    val purpose: String,
    val obligatoria: Boolean,
    val descripcion: String,
)

@Serializable
data class AvisoConsentimientoResponse(
    val version: String,
    @SerialName("texto_whatsapp") val textoWhatsapp: String,
    val finalidades: List<FinalidadConsentimiento> = emptyList(),
    val nota: String,
)

@Serializable
data class ConsentimientoEntrada(val purpose: String, val granted: Boolean)

@Serializable
data class ConsentimientoResponse(val purpose: String, val granted: Boolean, val version: String)

/** Valores de [ConsentimientoEntrada.purpose] (`ConsentPurpose` en el backend). */
object Finalidad {
    const val PERFIL_HOGAR = "perfil_hogar"
    const val CONTACTO_CONFIANZA = "contacto_confianza"
}

@Serializable
data class PaqueteOffline(
    @SerialName("sincronizado_at") val sincronizadoAt: String,
    val telefonos: List<Telefono> = emptyList(),
    @SerialName("instruccion_sin_senal") val instruccionSinSenal: String,
    val plan: PlanOffline? = null,
    @SerialName("ultima_alerta") val ultimaAlerta: AlertaOffline? = null,
    @SerialName("no_disponible_offline") val noDisponibleOffline: List<String> = emptyList(),
)

@Serializable
data class Telefono(val situacion: String, val numero: String, val entidad: String? = null)

@Serializable
data class PlanOffline(
    val titulo: String,
    @SerialName("generado_at") val generadoAt: String,
    val tareas: List<TareaOffline> = emptyList(),
)

@Serializable
data class TareaOffline(val texto: String, val critica: Boolean, val completada: Boolean)

@Serializable
data class AlertaOffline(
    val titulo: String,
    val nivel: String? = null,
    val entidad: String,
    val fecha: String,
    val advertencia: String,
)

@Serializable
data class ReportesResponse(
    @SerialName("consultado_at") val consultadoAt: String,
    val reportes: List<ReporteResumen> = emptyList(),
    val nota: String? = null,
)

/**
 * Resumen de un reporte para el listado.
 *
 * Sin autor y sin foto a propósito: el §28 prohíbe mostrar datos de contacto a
 * otros usuarios, y una foto de la vía puede incluir a terceros.
 */
@Serializable
data class ReporteResumen(
    val id: String,
    val tipo: String,
    val estado: String,
    val confianza: String,
    val confirmado: Boolean = false,
    val descripcion: String? = null,
    val direccion: String? = null,
    val distrito: String? = null,
    @SerialName("reportado_at") val reportadoAt: String,
    val lat: Double? = null,
    val lon: Double? = null,
    val mio: Boolean = false,
)

@Serializable
data class EventosResponse(val events: List<EventoMapa> = emptyList())

@Serializable
data class EventoMapa(
    val id: String,
    val title: String,
    val type: String = "",
    val lat: Double? = null,
    val lon: Double? = null,
    @SerialName("unique_reporter_count") val personas: Int = 0,
    @SerialName("citizen_report_count") val reportes: Int = 0,
    @SerialName("official_source_count") val fuentesOficiales: Int = 0,
    val confidence: Double = 0.0,
    @SerialName("validation_status") val estado: String = "SIN_CONFIRMAR",
    @SerialName("last_reported_at") val ultimoReporte: String? = null,
    val summary: String? = null,
)

@Serializable
data class MensajeHistorial(
    val rol: String,
    val contenido: String,
    val urgencia: String? = null,
    @SerialName("respuesta_plantilla_fija") val respuestaPlantillaFija: Boolean = false,
    val fuentes: List<Fuente> = emptyList(),
    @SerialName("enviado_at") val enviadoAt: String,
)

@Serializable
data class PuntoEvitar(val lat: Double, val lon: Double)

@Serializable
data class RutaEntrada(
    @SerialName("origen_lat") val origenLat: Double,
    @SerialName("origen_lon") val origenLon: Double,
    @SerialName("destino_lat") val destinoLat: Double? = null,
    @SerialName("destino_lon") val destinoLon: Double? = null,
    @SerialName("hacia_refugio") val haciaRefugio: Boolean = false,
    val evitar: List<PuntoEvitar> = emptyList(),
    val guardar: Boolean = true,
)

@Serializable
data class PasoRuta(val instruccion: String)

/**
 * Respuesta de `POST /rutas`.
 *
 * `sinRutaVerificable` llega con estado 200 y no con un error: el §20.5 dice
 * que "no hay ruta verificable" es un resultado correcto del sistema. Tratarlo
 * como fallo haría que el cliente reintentara, y reintentar no va a hacer
 * aparecer una ruta que no existe.
 */
@Serializable
data class RutaRecalculada(
    @SerialName("sin_ruta_verificable") val sinRutaVerificable: Boolean = false,
    val mensaje: String? = null,
    val pasos: List<PasoRuta> = emptyList(),
    @SerialName("distancia_m") val distanciaM: Int? = null,
    @SerialName("duracion_s") val duracionS: Int? = null,
    val geometria: String? = null,
    @SerialName("origen_lat") val origenLat: Double? = null,
    @SerialName("origen_lon") val origenLon: Double? = null,
    @SerialName("destino_lat") val destinoLat: Double? = null,
    @SerialName("destino_lon") val destinoLon: Double? = null,
    val bloqueos: List<BloqueoMapa> = emptyList(),
) {
    /** La convierte a lo que dibuja el mapa, conservando el nombre del destino. */
    fun aRutaCalculada(destino: String?) = RutaCalculada(
        pasos = pasos.map { it.instruccion },
        distanciaM = distanciaM,
        duracionS = duracionS,
        destino = destino,
        destinoLat = destinoLat,
        destinoLon = destinoLon,
        origenLat = origenLat,
        origenLon = origenLon,
        geometria = geometria,
        bloqueos = bloqueos,
    )
}
