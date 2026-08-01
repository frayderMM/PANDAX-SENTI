package com.example.senti.data

/**
 * Convierte el paquete a las capas que MapLibre dibuja encima del mapa base.
 *
 * Se produce GeoJSON como texto y no con las clases del SDK a propósito: así
 * esto es lógica pura, se prueba en la JVM sin emulador, y lo que la prueba
 * comprueba es exactamente la cadena que recibe MapLibre.
 *
 * **Lo que nunca se dibuja: lo que no está en el paquete.** No hay relleno, no
 * hay interpolación y no hay "aproximadamente por aquí". Si un dato no se
 * descargó, no aparece, y la pantalla dice que no se descargó (§11.3).
 */

/** Escapa lo mínimo para que un texto quepa dentro de una cadena JSON. */
private fun String.aJsonString(): String {
    val sb = StringBuilder(length + 2)
    sb.append('"')
    for (c in this) {
        when (c) {
            '"' -> sb.append("\\\"")
            '\\' -> sb.append("\\\\")
            '\n' -> sb.append("\\n")
            '\r' -> sb.append("\\r")
            '\t' -> sb.append("\\t")
            else -> if (c < ' ') sb.append("\\u%04x".format(c.code)) else sb.append(c)
        }
    }
    sb.append('"')
    return sb.toString()
}

private fun coleccion(features: List<String>): String =
    """{"type":"FeatureCollection","features":[${features.joinToString(",")}]}"""

private fun punto(lat: Double, lon: Double, propiedades: Map<String, String>): String {
    val props = propiedades.entries.joinToString(",") {
        "${it.key.aJsonString()}:${it.value.aJsonString()}"
    }
    return """{"type":"Feature","properties":{$props},""" +
        """"geometry":{"type":"Point","coordinates":[$lon,$lat]}}"""
}

/**
 * Rutas guardadas, como líneas.
 *
 * La polilínea viene codificada de Valhalla y se decodifica aquí con el mismo
 * [decodificarPolilinea] que usa el mapa con conexión. Una ruta de un solo
 * punto no es una línea y se descarta: MapLibre la aceptaría y no dibujaría
 * nada, que es peor porque no se distingue de un fallo.
 */
fun geoJsonRutas(rutas: List<RutaGuardada>): String = coleccion(
    rutas.mapNotNull { ruta ->
        val puntos = decodificarPolilinea(ruta.geometria)
        if (puntos.size < 2) return@mapNotNull null
        val coords = puntos.joinToString(",") { "[${it.lon},${it.lat}]" }
        """{"type":"Feature","properties":{"id":${ruta.id.aJsonString()},""" +
            """"titulo":${ruta.titulo.aJsonString()}},""" +
            """"geometry":{"type":"LineString","coordinates":[$coords]}}"""
    }
)

/**
 * Conflictos viales.
 *
 * `oficial` viaja como propiedad para que el estilo pinte de un color el cierre
 * vinculante y de otro el reporte ciudadano sin validar. El color no es un
 * adorno: son dos cosas que no significan lo mismo y el §25 prohíbe
 * mezclarlas. Aun así el color nunca va solo — la ficha que se abre al tocar
 * lo dice con palabras, porque el §31.2 exige que el color no sea la única
 * información.
 */
fun geoJsonConflictos(conflictos: List<ConflictoOffline>): String = coleccion(
    conflictos.map { c ->
        punto(
            c.lat, c.lon,
            mapOf(
                "id" to c.id,
                "titulo" to c.titulo,
                "tipo" to c.tipo,
                "oficial" to c.oficial.toString(),
                "confianza" to c.confianza,
            )
        )
    }
)

/** Hospitales, bomberos, comisarías y refugios. */
fun geoJsonRecursos(recursos: List<RecursoOffline>): String = coleccion(
    recursos.map { r ->
        punto(
            r.lat, r.lon,
            mapOf(
                "id" to r.id,
                "nombre" to r.nombre,
                "tipo" to r.tipo,
                "referencial" to r.ubicacionReferencial.toString(),
            )
        )
    }
)
