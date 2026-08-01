package com.example.senti.data

import java.security.MessageDigest
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Paquete de una zona para usar sin conexión (§26).
 *
 * Se descarga con red y se lee sin ella. Todo lo que hay dentro es una foto
 * del pasado, y el diseño entero gira alrededor de esa frase: [sincronizadoAt]
 * viaja con los datos, [expiraAt] dice cuándo dejan de ser presentables y
 * [advertencia] es el texto que la pantalla obliga a leer. Nunca se muestra la
 * hora actual junto a estos datos.
 *
 * El [checksum] no es paranoia: el archivo vive en el almacenamiento del
 * teléfono, se escribe mientras la app puede morir por falta de memoria y se
 * lee en el peor momento posible. Un paquete a medio escribir que se
 * interpretara como bueno pintaría un mapa con la mitad de los bloqueos.
 */
@Serializable
data class Limites(
    @SerialName("min_lat") val minLat: Double,
    @SerialName("min_lon") val minLon: Double,
    @SerialName("max_lat") val maxLat: Double,
    @SerialName("max_lon") val maxLon: Double,
) {
    fun contiene(lat: Double, lon: Double): Boolean =
        lat in minLat..maxLat && lon in minLon..maxLon
}

@Serializable
data class RutaGuardada(
    val id: String,
    val titulo: String,
    /** Polilínea de Valhalla, precisión 6. Se decodifica con [decodificarPolilinea]. */
    val geometria: String,
    val pasos: List<String> = emptyList(),
    @SerialName("distancia_m") val distanciaM: Int? = null,
    @SerialName("duracion_s") val duracionS: Int? = null,
    @SerialName("calculada_at") val calculadaAt: Long,
)

/**
 * Un conflicto vial de la zona.
 *
 * [oficial] decide de qué color se pinta y qué se puede afirmar de él. Un
 * cierre municipal es "no se puede pasar"; un reporte ciudadano sin validar es
 * "alguien reportó esto". Mezclarlos está prohibido (§25) y por eso el color
 * nunca viaja solo: la ficha lo dice también con palabras.
 */
@Serializable
data class ConflictoOffline(
    val id: String,
    val tipo: String,
    val titulo: String,
    val lat: Double,
    val lon: Double,
    @SerialName("radio_m") val radioM: Double = 0.0,
    val oficial: Boolean,
    val confianza: String = "pendiente",
    @SerialName("reportado_at") val reportadoAt: String? = null,
)

/** Hospital, bomberos, refugio o comisaría. */
@Serializable
data class RecursoOffline(
    val id: String,
    val tipo: String,
    val nombre: String,
    val lat: Double,
    val lon: Double,
    /**
     * OSM acredita que existe y dónde, no que esté designado como refugio ni
     * que esté abierto. La ficha lo declara; callarlo sería presentar un
     * colegio cerrado como punto de acogida.
     */
    @SerialName("ubicacion_referencial") val ubicacionReferencial: Boolean = true,
)

/** Contenido del paquete. Es lo que entra en el checksum. */
@Serializable
data class ContenidoZona(
    val rutas: List<RutaGuardada> = emptyList(),
    val conflictos: List<ConflictoOffline> = emptyList(),
    val recursos: List<RecursoOffline> = emptyList(),
    val telefonos: List<Telefono> = emptyList(),
    @SerialName("ultima_alerta") val ultimaAlerta: AlertaOffline? = null,
    @SerialName("instruccion_sin_senal") val instruccionSinSenal: String = TextosFijos.SIN_SENAL,
    /**
     * Qué NO se pudo descargar en esta sincronización (§11.3).
     *
     * Es el campo más importante del paquete y el más fácil de omitir. Si los
     * bloqueos oficiales fallaron, el mapa se dibuja igual pero sin ninguno, y
     * un mapa sin bloqueos se lee como "no hay bloqueos". Guardar aquí qué
     * faltó es lo que permite a la pantalla decir "esto no se pudo consultar"
     * en vez de dejar que el silencio pase por ausencia de peligro.
     */
    @SerialName("fuentes_fallidas") val fuentesFallidas: List<String> = emptyList(),
)

@Serializable
data class PaqueteZona(
    /** Versión del FORMATO, no de los datos. Un paquete de otra versión se descarta. */
    @SerialName("formato") val formato: Int = FORMATO_ACTUAL,
    @SerialName("sincronizado_at") val sincronizadoAt: Long,
    @SerialName("expira_at") val expiraAt: Long,
    @SerialName("centro_lat") val centroLat: Double,
    @SerialName("centro_lon") val centroLon: Double,
    val limites: Limites,
    /** SHA-256 de [contenido] serializado. Ver [checksumDe]. */
    val checksum: String,
    val advertencia: String = ADVERTENCIA,
    val contenido: ContenidoZona = ContenidoZona(),
) {
    fun vencido(ahora: Long = System.currentTimeMillis()): Boolean = ahora >= expiraAt

    /**
     * Comprueba que el paquete es coherente consigo mismo.
     *
     * Devuelve el motivo del rechazo, o null si está bien. Se devuelve el
     * motivo y no un booleano porque la pantalla lo enseña: "no hay datos" y
     * "los datos que hay están corruptos" mandan a hacer cosas distintas.
     */
    fun motivoInvalidez(): String? = when {
        formato != FORMATO_ACTUAL ->
            "El paquete se descargó con otra versión de la app y no se puede leer."
        checksum != checksumDe(contenido) ->
            "El paquete descargado está incompleto o dañado."
        expiraAt <= sincronizadoAt ->
            "El paquete tiene una fecha de expiración imposible."
        !limites.contiene(centroLat, centroLon) ->
            "El paquete no cubre su propio centro."
        else -> null
    }

    val valido: Boolean get() = motivoInvalidez() == null

    companion object {
        const val FORMATO_ACTUAL = 1

        const val ADVERTENCIA =
            "Datos descargados. Pueden estar desactualizados: no reflejan lo que " +
                "haya cambiado desde la última sincronización. La ausencia de un " +
                "bloqueo aquí no significa que la vía esté abierta."

        /**
         * Área que se descarga, en metros de medio lado.
         *
         * El requisito son 10 km². Un cuadrado de 10 km² mide √10 ≈ 3,162 km
         * de lado, así que medio lado son 1581 m. Se descarga un cuadrado y no
         * un círculo porque las teselas y los bbox son rectangulares, y
         * recortar un círculo dentro solo dejaría esquinas sin datos.
         */
        const val MEDIO_LADO_M = 1581.0

        /**
         * Cuánto vale un paquete antes de considerarse vencido.
         *
         * Siete días. No es un número redondo elegido por gusto: la vigencia
         * más larga de la tabla de riesgos del backend es la del puente
         * afectado, 168 horas, y son exactamente siete días. Pasado eso,
         * cualquier dato del paquete pudo caducar sin que la app se enterara.
         */
        const val VIGENCIA_MS = 7L * 24 * 60 * 60 * 1000
    }
}

private val JSON_ZONA = Json { ignoreUnknownKeys = true; encodeDefaults = true }

/**
 * SHA-256 del contenido serializado.
 *
 * Se calcula sobre el JSON del contenido y no sobre el paquete entero para que
 * el checksum no se incluya a sí mismo. `encodeDefaults` está activo y el
 * orden de los campos lo fija la clase, así que serializar dos veces el mismo
 * contenido da el mismo texto.
 */
fun checksumDe(contenido: ContenidoZona): String {
    val bytes = JSON_ZONA.encodeToString(ContenidoZona.serializer(), contenido)
        .toByteArray(Charsets.UTF_8)
    return MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }
}

fun paqueteAJson(paquete: PaqueteZona): String =
    JSON_ZONA.encodeToString(PaqueteZona.serializer(), paquete)

fun paqueteDesdeJson(crudo: String): PaqueteZona? =
    runCatching { JSON_ZONA.decodeFromString<PaqueteZona>(crudo) }.getOrNull()

/**
 * Construye el paquete a partir del contenido, calculando checksum y límites.
 *
 * Es el único sitio donde se crea un [PaqueteZona] con datos reales: así el
 * checksum no puede quedar desincronizado del contenido por olvido en una
 * llamada nueva.
 */
fun construirPaquete(
    centroLat: Double,
    centroLon: Double,
    contenido: ContenidoZona,
    ahora: Long = System.currentTimeMillis(),
    medioLadoM: Double = PaqueteZona.MEDIO_LADO_M,
): PaqueteZona {
    val limites = limitesAlrededor(centroLat, centroLon, medioLadoM)
    return PaqueteZona(
        sincronizadoAt = ahora,
        expiraAt = ahora + PaqueteZona.VIGENCIA_MS,
        centroLat = centroLat,
        centroLon = centroLon,
        limites = limites,
        checksum = checksumDe(contenido),
        contenido = contenido,
    )
}

/**
 * Cuadrado de `medioLadoM` metros alrededor de un punto.
 *
 * Un grado de latitud son 111 320 m en cualquier sitio; uno de longitud, esos
 * mismos metros multiplicados por el coseno de la latitud. En Lima (−12°) el
 * coseno vale 0,978, así que ignorarlo estrecharía el cuadrado un 2 % — poco,
 * pero gratis de corregir. Cerca de los polos el coseno tiende a cero y la
 * división se dispara, así que se acota.
 */
fun limitesAlrededor(lat: Double, lon: Double, medioLadoM: Double): Limites {
    val gradoLat = medioLadoM / 111_320.0
    val factor = max(cos(Math.toRadians(lat)), 0.01)
    val gradoLon = medioLadoM / (111_320.0 * factor)
    return Limites(
        minLat = lat - gradoLat,
        minLon = lon - gradoLon,
        maxLat = lat + gradoLat,
        maxLon = lon + gradoLon,
    )
}

/**
 * ¿Sigue sirviendo este paquete para donde estoy ahora?
 *
 * Se considera que sí mientras el usuario esté dentro del área descargada. Si
 * salió de ella, el paquete no vale para su zona aunque no haya vencido: los
 * bloqueos que lleva son de otro sitio.
 */
fun PaqueteZona.cubre(lat: Double, lon: Double): Boolean = limites.contiene(lat, lon)

/** Distancia aproximada en metros. Suficiente para ordenar recursos cercanos. */
fun distanciaAproxM(aLat: Double, aLon: Double, bLat: Double, bLon: Double): Double {
    val dLat = (aLat - bLat) * 111_320.0
    val dLon = (aLon - bLon) * 111_320.0 * cos(Math.toRadians((aLat + bLat) / 2.0))
    return kotlin.math.sqrt(dLat * dLat + dLon * dLon)
}

/** Cuántos metros de lado tiene el área del paquete. Para enseñarlo en pantalla. */
fun Limites.ladoAproxM(): Double = abs(maxLat - minLat) * 111_320.0
