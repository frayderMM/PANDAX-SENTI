package com.example.senti

import com.example.senti.data.ConflictoOffline
import com.example.senti.data.RecursoOffline
import com.example.senti.data.RutaGuardada
import com.example.senti.data.geoJsonConflictos
import com.example.senti.data.geoJsonRecursos
import com.example.senti.data.geoJsonRutas
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Las capas que se dibujan encima del mapa sin conexión.
 *
 * Un fallo aquí no da error: da un mapa. Un GeoJSON mal escapado hace que
 * MapLibre descarte la capa entera en silencio, y lo que desaparece son los
 * bloqueos — es decir, la pantalla queda igual que si no hubiera ninguno.
 */
class GeoJsonOfflineTest {

    private val ruta = RutaGuardada(
        id = "r1",
        titulo = "Salida al refugio",
        // Dos puntos reales del centro de Lima, precisión 6.
        geometria = "fng~Upzi}qCqBhC",
        pasos = listOf("Camina al norte"),
        calculadaAt = 1_800_000_000_000L,
    )

    @Test
    fun `una ruta con geometria se convierte en una linea`() {
        val json = geoJsonRutas(listOf(ruta))
        assertTrue(json.contains("\"LineString\""))
        assertTrue(json.contains("\"Salida al refugio\""))
        assertEquals(1, contar(json, "\"Feature\""))
    }

    @Test
    fun `una ruta sin geometria suficiente se descarta en vez de dibujarse vacia`() {
        // MapLibre aceptaría una LineString de un punto y no dibujaría nada,
        // que es indistinguible de un fallo. Mejor no emitirla.
        val corta = ruta.copy(geometria = "")
        assertEquals(0, contar(geoJsonRutas(listOf(corta)), "\"Feature\""))
    }

    @Test
    fun `sin rutas se emite una coleccion vacia y valida`() {
        assertEquals("""{"type":"FeatureCollection","features":[]}""", geoJsonRutas(emptyList()))
    }

    @Test
    fun `el conflicto oficial y el ciudadano se distinguen en las propiedades`() {
        // El estilo filtra por esta propiedad para pintarlos de colores
        // distintos. Si los dos salieran iguales, un reporte sin validar se
        // vería como un cierre municipal, que es justo lo que el §25 prohíbe.
        val json = geoJsonConflictos(
            listOf(
                ConflictoOffline("c1", "via_bloqueada", "Cierre municipal", -12.0, -77.0,
                    oficial = true, confianza = "confirmado"),
                ConflictoOffline("c2", "huaico", "Reporte vecinal", -12.01, -77.01,
                    oficial = false, confianza = "pendiente"),
            )
        )
        assertTrue(json.contains(""""oficial":"true""""))
        assertTrue(json.contains(""""oficial":"false""""))
        assertEquals(2, contar(json, "\"Feature\""))
    }

    @Test
    fun `las coordenadas van en orden longitud latitud`() {
        // GeoJSON es [lon, lat] y el resto de la app usa (lat, lon). Invertirlo
        // no da error: pone Lima en el océano Índico.
        val json = geoJsonConflictos(
            listOf(ConflictoOffline("c1", "sismo", "x", -12.0464, -77.0428, oficial = true))
        )
        assertTrue(
            "debe emitirse [lon,lat]: $json",
            json.contains("[-77.0428,-12.0464]"),
        )
    }

    @Test
    fun `un titulo con comillas no rompe el JSON`() {
        // Un reporte ciudadano lleva texto escrito por una persona. Unas
        // comillas sin escapar invalidan la colección entera y MapLibre la
        // descarta sin decir nada: desaparecen TODOS los bloqueos, no solo ese.
        val json = geoJsonConflictos(
            listOf(
                ConflictoOffline(
                    "c1", "via_bloqueada",
                    """La "curva" del cerro \ se cayó""",
                    -12.0, -77.0, oficial = false,
                )
            )
        )
        assertTrue("las comillas deben ir escapadas", json.contains("\\\""))
        assertTrue("la barra debe ir escapada", json.contains("\\\\"))
        assertFalse("no debe quedar una comilla cruda", json.contains("""La "curva"""))
    }

    @Test
    fun `un salto de linea en la descripcion se escapa`() {
        val json = geoJsonConflictos(
            listOf(ConflictoOffline("c1", "otro", "linea1\nlinea2", -12.0, -77.0, oficial = false))
        )
        assertTrue(json.contains("linea1\\nlinea2"))
        assertFalse("no debe haber un salto real dentro de la cadena", json.contains("linea1\nlinea2"))
    }

    @Test
    fun `los recursos conservan tipo y caracter referencial`() {
        val json = geoJsonRecursos(
            listOf(
                RecursoOffline("osm/node/1", "centro_salud", "Hospital Loayza", -12.0, -77.0),
                RecursoOffline("osm/node/2", "bomberos", "Compañía 4", -12.01, -77.01,
                    ubicacionReferencial = false),
            )
        )
        assertTrue(json.contains(""""tipo":"centro_salud""""))
        assertTrue(json.contains(""""tipo":"bomberos""""))
        assertTrue(json.contains(""""referencial":"true""""))
        assertTrue(json.contains(""""referencial":"false""""))
    }

    @Test
    fun `sin datos las tres capas quedan vacias y no nulas`() {
        // Una capa vacía deja el mapa limpio; una capa nula deja la anterior
        // pintada, y entonces el mapa mostraría los bloqueos de la zona vieja.
        val vacia = """{"type":"FeatureCollection","features":[]}"""
        assertEquals(vacia, geoJsonRutas(emptyList()))
        assertEquals(vacia, geoJsonConflictos(emptyList()))
        assertEquals(vacia, geoJsonRecursos(emptyList()))
    }

    private fun contar(texto: String, aguja: String): Int =
        texto.split(aguja).size - 1
}
