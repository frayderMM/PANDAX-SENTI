package com.example.senti.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Hospitales, bomberos, comisarías y refugios de la zona, desde OpenStreetMap.
 *
 * **Por qué OSM y no el backend.** El backend no publica un listado de
 * recursos: los busca por proximidad como herramienta del chat, y esa
 * herramienta responde a una pregunta, no devuelve un catálogo para descargar.
 * OSM sí, es la misma fuente que el importador del backend usa para poblar la
 * tabla `resources`, y se consulta solo durante la sincronización — con red y
 * sin prisa. En modo sin conexión no se llama a nada.
 *
 * **Lo que un recurso de OSM acredita y lo que no.** Acredita que el
 * establecimiento existe y dónde está. No acredita que esté abierto, que tenga
 * capacidad ni que la municipalidad lo haya designado punto de acogida. Por eso
 * todos se guardan con `ubicacionReferencial = true` y la ficha lo dice. Es la
 * misma tensión que el importador del backend declara en voz alta, y se
 * resuelve igual: mejor un hospital referencial que ningún hospital, siempre
 * que quien lo lea sepa cuál de las dos cosas está mirando.
 */
object RecursosOsm {

    private const val OVERPASS = "https://overpass-api.de/api/interpreter"

    // No se piden farmacias ni consultorios: en una inundación o un huaico no
    // son destino de evacuación y multiplicarían las filas sin mejorar nada.
    // Es el mismo recorte que hace el importador del backend.
    private val TIPOS = mapOf(
        "hospital" to "centro_salud",
        "clinic" to "centro_salud",
        "doctors" to "centro_salud",
        "fire_station" to "bomberos",
        "police" to "comisaria",
        "shelter" to "refugio",
        "school" to "refugio",
        "community_centre" to "refugio",
    )

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    private val client = HttpClient(Android) {
        install(ContentNegotiation) { json(json) }
        install(HttpTimeout) {
            // Overpass es un servicio público y compartido: bajo carga tarda.
            // Se le da margen, pero acotado — la sincronización no puede
            // quedarse colgada esperándole.
            requestTimeoutMillis = 45_000
            connectTimeoutMillis = 15_000
            socketTimeoutMillis = 45_000
        }
    }

    /** Consulta la zona. Lanza si Overpass falla: lo gestiona el sincronizador. */
    suspend fun enZona(limites: Limites): List<RecursoOffline> {
        val filtro = TIPOS.keys.joinToString("|")
        val caja = "${limites.minLat},${limites.minLon},${limites.maxLat},${limites.maxLon}"
        val consulta = """
            [out:json][timeout:40];
            (
              node["amenity"~"^($filtro)$"]($caja);
              way["amenity"~"^($filtro)$"]($caja);
            );
            out center tags;
        """.trimIndent()

        val respuesta: RespuestaOverpass = client.post(OVERPASS) {
            contentType(ContentType.Text.Plain)
            setBody(consulta)
        }.body()

        return respuesta.elements.mapNotNull { it.aRecurso() }
    }

    private fun ElementoOsm.aRecurso(): RecursoOffline? {
        val lat = this.lat ?: center?.lat ?: return null
        val lon = this.lon ?: center?.lon ?: return null
        val amenity = tags["amenity"] ?: return null
        val tipo = TIPOS[amenity] ?: return null
        // Un elemento sin nombre no se descarta: "Bomberos" a 300 m sigue
        // sirviendo para orientarse aunque OSM no traiga su denominación. Lo
        // que no se hace es inventarle un nombre concreto.
        val nombre = tags["name"] ?: etiquetaGenerica(tipo)
        return RecursoOffline(
            id = "osm/$type/$id",
            tipo = tipo,
            nombre = nombre,
            lat = lat,
            lon = lon,
            ubicacionReferencial = true,
        )
    }

    private fun etiquetaGenerica(tipo: String): String = when (tipo) {
        "centro_salud" -> "Centro de salud (sin nombre en el mapa)"
        "bomberos" -> "Estación de bomberos (sin nombre en el mapa)"
        "comisaria" -> "Comisaría (sin nombre en el mapa)"
        else -> "Posible punto de refugio (sin nombre en el mapa)"
    }
}

@Serializable
private data class RespuestaOverpass(val elements: List<ElementoOsm> = emptyList())

@Serializable
private data class ElementoOsm(
    val type: String = "node",
    val id: Long = 0,
    val lat: Double? = null,
    val lon: Double? = null,
    val center: CentroOsm? = null,
    val tags: Map<String, String> = emptyMap(),
)

@Serializable
private data class CentroOsm(val lat: Double, val lon: Double)
