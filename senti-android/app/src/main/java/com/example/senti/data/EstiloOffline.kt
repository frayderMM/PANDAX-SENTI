package com.example.senti.data

import android.content.Context
import java.io.File

/**
 * El estilo del mapa sin conexión, construido en código.
 *
 * **Dos packs de teselas, y la razón es el peso.** Medido sobre el basemap de
 * Protomaps: el Perú entero hasta zoom 12 son 94 MB, hasta el 11 son 41 y
 * hasta el 10 son 20. En cambio Lima y Callao **hasta zoom 15** —nivel de
 * calle— caben en 23 MB. Es decir, subir un solo nivel de zoom en todo el país
 * cuesta más que llevar el detalle completo de la ciudad donde vive un tercio
 * de la población.
 *
 * Así que van los dos:
 *
 * | pack | cubre | zoom | para qué sirve |
 * |---|---|---|---|
 * | `peru.pmtiles` | todo el país | 0–11 | ubicarse en cualquier sitio: carreteras, ríos, trazas urbanas |
 * | `lima_callao.pmtiles` | área metropolitana | 0–15 | caminar por una calle concreta |
 *
 * Fuera de Lima el mapa llega hasta donde llega —carreteras y forma de la
 * ciudad, no el nombre de la esquina— y eso **se dice en pantalla**. Prometer
 * detalle de calle en Iquitos y dibujar una mancha sería peor que declarar el
 * límite.
 *
 * **Sin etiquetas de texto, y es una decisión, no un olvido.** Pintar el nombre
 * de una calle obliga a que el estilo declare `glyphs`, y los glifos son
 * archivos que MapLibre descarga de un servidor. Sin red no llegan. Se prefiere
 * no prometerlo: el mapa sin conexión dibuja la **geometría** de las calles y
 * los puntos que importan, y los nombres se leen tocando cada punto.
 *
 * **Fondo claro y vías oscuras.** Es al revés que un mapa nocturno, y la razón
 * es dónde se usa esto: a la intemperie y de día. Bajo sol directo la pantalla
 * de un teléfono pierde casi todo el contraste, y un mapa oscuro se convierte
 * en un rectángulo negro donde no se distingue una calle de un río. Con fondo
 * claro y trazo oscuro sobrevive al reflejo, que es la condición real de uso.
 */
object EstiloOffline {

    /** Pack nacional. Sin él no hay mapa base en ninguna parte. */
    const val ASSET_PERU = "peru.pmtiles"

    /** Pack de detalle del área metropolitana. Su ausencia no rompe nada. */
    const val ASSET_DETALLE = "lima_callao.pmtiles"

    private const val FUENTE_PERU = "peru"
    private const val FUENTE_DETALLE = "detalle"

    /**
     * Zoom a partir del cual manda el pack de detalle.
     *
     * Coincide con el máximo del pack nacional: por debajo dibuja el nacional
     * con sus teselas propias, y por encima —donde el nacional ya solo puede
     * estirar la última tesela— entra el de detalle si la zona lo tiene.
     */
    private const val ZOOM_DETALLE = 12

    data class Packs(val peru: File, val detalle: File?)

    /**
     * Copia los packs del APK al almacenamiento de la app, si hace falta.
     *
     * MapLibre necesita una ruta de archivo real: `pmtiles://asset://` no está
     * soportado, porque leer rangos sueltos de un asset comprimido no se puede.
     * Se copia una sola vez —64 MB, y se nota— y se reutiliza; si el archivo ya
     * está y mide lo mismo, no se vuelve a copiar.
     *
     * Devuelve null si falta el pack nacional: sin él no hay mapa que enseñar,
     * y se prefiere decirlo a pintar un fondo vacío que parezca un mapa sin
     * calles.
     */
    fun prepararPacks(context: Context): Packs? {
        val peru = copiarSiHaceFalta(context, ASSET_PERU) ?: return null
        return Packs(peru = peru, detalle = copiarSiHaceFalta(context, ASSET_DETALLE))
    }

    private fun copiarSiHaceFalta(context: Context, asset: String): File? = runCatching {
        val destino = File(context.filesDir, asset)
        val tamanoAsset = context.assets.openFd(asset).use { it.length }
        if (destino.exists() && destino.length() == tamanoAsset) return destino

        val temporal = File(context.filesDir, "$asset.tmp")
        context.assets.open(asset).use { entrada ->
            temporal.outputStream().use { salida -> entrada.copyTo(salida) }
        }
        if (!temporal.renameTo(destino)) {
            destino.delete()
            temporal.renameTo(destino)
        }
        destino.takeIf { it.exists() }
    }.getOrNull()

    /**
     * Estilo que lee los packs locales.
     *
     * Las capas de vías se declaran dos veces: una contra el pack nacional y
     * otra contra el de detalle a partir del zoom [ZOOM_DETALLE]. Donde el pack
     * de detalle no tiene teselas —fuera de Lima— sus capas simplemente no
     * dibujan nada y queda el nacional. No hay lógica que decidir en tiempo de
     * ejecución: lo resuelve el propio motor al no encontrar tesela.
     */
    fun estiloJson(rutaPeru: String, rutaDetalle: String?): String {
        val fuentes = buildString {
            append(""""$FUENTE_PERU":{"type":"vector","url":"pmtiles://file://$rutaPeru"}""")
            if (rutaDetalle != null) {
                append(",")
                append(
                    """"$FUENTE_DETALLE":{"type":"vector","url":"pmtiles://file://$rutaDetalle"}"""
                )
            }
        }

        val capasDetalle = if (rutaDetalle == null) "" else "," + capasVias(FUENTE_DETALLE, ZOOM_DETALLE)

        return """
        {
          "version": 8,
          "name": "SENTI sin conexión",
          "sources": { $fuentes },
          "layers": [
            { "id": "fondo", "type": "background",
              "paint": { "background-color": "#EFEBE4" } },

            { "id": "tierra", "type": "fill", "source": "$FUENTE_PERU", "source-layer": "earth",
              "paint": { "fill-color": "#F7F4EE" } },

            { "id": "verde", "type": "fill", "source": "$FUENTE_PERU", "source-layer": "landuse",
              "paint": { "fill-color": "#DFE9D6" } },

            { "id": "agua", "type": "fill", "source": "$FUENTE_PERU", "source-layer": "water",
              "paint": { "fill-color": "#A8CBE0" } },

            ${capasVias(FUENTE_PERU, null)}$capasDetalle
          ]
        }
        """.trimIndent()
    }

    /**
     * Las cuatro capas de vías de una fuente.
     *
     * El orden importa y va de menor a mayor: una autopista dibujada debajo de
     * una calle de barrio se ve cortada en cada cruce.
     */
    private fun capasVias(fuente: String, minzoom: Int?): String {
        val mz = minzoom?.let { """"minzoom": $it, """ } ?: ""
        return """
            { "id": "calles-menores-$fuente", $mz"type": "line", "source": "$fuente",
              "source-layer": "roads",
              "filter": ["in", "kind", "minor_road", "path"],
              "paint": {
                "line-color": "#B0A99D",
                "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.4, 16, 2.5]
              } },

            { "id": "calles-$fuente", $mz"type": "line", "source": "$fuente",
              "source-layer": "roads",
              "filter": ["==", "kind", "medium_road"],
              "paint": {
                "line-color": "#8A8175",
                "line-width": ["interpolate", ["linear"], ["zoom"], 11, 0.7, 16, 4.0]
              } },

            { "id": "avenidas-$fuente", $mz"type": "line", "source": "$fuente",
              "source-layer": "roads",
              "filter": ["==", "kind", "major_road"],
              "paint": {
                "line-color": "#55504A",
                "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.0, 16, 5.5]
              } },

            { "id": "autopistas-$fuente", $mz"type": "line", "source": "$fuente",
              "source-layer": "roads",
              "filter": ["==", "kind", "highway"],
              "paint": {
                "line-color": "#C2701A",
                "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1.0, 16, 6.5]
              } }
        """.trimIndent()
    }

    /**
     * Recuadro del pack de detalle, para saber si la zona del usuario lo tiene.
     *
     * Es el mismo bbox con el que se extrajo `lima_callao.pmtiles`. Vive aquí
     * escrito porque la pantalla necesita poder decir "aquí el mapa llega a
     * nivel de calle" o "aquí solo hay carreteras principales", y leerlo del
     * propio archivo exigiría parsear la cabecera PMTiles a mano.
     */
    val LIMITES_DETALLE = Limites(
        minLat = -12.45, minLon = -77.25,
        maxLat = -11.70, maxLon = -76.70,
    )

    /** Identificadores de las capas que añade la app encima del mapa. */
    object Capas {
        const val RUTA = "senti-ruta"
        const val RUTA_FUENTE = "senti-ruta-fuente"
        const val CONFLICTOS = "senti-conflictos"
        const val CONFLICTOS_FUENTE = "senti-conflictos-fuente"
        const val RECURSOS = "senti-recursos"
        const val RECURSOS_FUENTE = "senti-recursos-fuente"
    }
}
