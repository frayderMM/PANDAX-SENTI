package com.example.senti

import com.example.senti.data.decodificarPolilinea
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * El decodificador de polilíneas de Valhalla.
 *
 * Se prueba con más cuidado del que aparenta un formato de transporte porque
 * un fallo aquí no da error: da una línea. Un signo mal leído dibuja la ruta
 * en el hemisferio contrario —eso se ve—, pero un desplazamiento de un bit
 * dibuja una ruta plausible por las calles equivocadas, y eso no se ve.
 *
 * El caso de referencia es una ruta peatonal **real** pedida al Valhalla del
 * servidor entre dos puntos del centro de Lima, con los valores que produce
 * `app/routing/valhalla.py`. Se compara contra ese decodificador y no contra
 * una cadena de ejemplo de internet a propósito: los ejemplos que circulan son
 * de precisión 5 y Valhalla usa 6, que es exactamente el error que hay que
 * atrapar —con precisión equivocada la ruta sale a diez veces su tamaño, en
 * mitad del Pacífico, y sin lanzar ninguna excepción—.
 */
class PolilineaTest {

    private val rutaReal =
        "fng~Upzi}qCqBhCaAxB_@pBI|B@xBfDEYiFH{@PYn@Sp@UnAq@n@i@`@m@RMXCTH`DjDlAiAvBgBmBiBMWIa@?]" +
            "Tk@^e@h@k@Xe@Rm@N}@PaA?e@VKb@C`C??q@lEQl\\wA|_@cBpBIJuArBmLn@}ApBoDpFuJrK{R~AmCtBsD" +
            "xE{HnI_NjQe[l@eAtAcCzP}YtMcUfD{FhAoBh`@_r@bBuCnRaApBK?aB?sC?wAFcANoC|@sNFcAh{@oT~Cw" +
            "@`n@{OhF{A`a@qIlAEzDcWtAaJrJkk@fTas@lRhFdBf@~HvBrc@bMpDp@pDTpCAfGU[kDq@yPd@{Cb@w@V]" +
            "f@c@z@]Z?^Dd@J`ChArFAz@cAv@_AdBcCuD{CW[Fc@^cB"

    /** Precisión 6 son ~0,1 m; se exige coincidencia exacta al microgrado. */
    private fun casiIgual(a: Double, b: Double) = abs(a - b) < 1e-6

    @Test
    fun `coincide con el decodificador del backend sobre una ruta real`() {
        val puntos = decodificarPolilinea(rutaReal)

        assertEquals("mismo número de puntos que en Python", 106, puntos.size)

        assertTrue(casiIgual(puntos[0].lat, -12.04658) && casiIgual(puntos[0].lon, -77.043129))
        assertTrue(casiIgual(puntos[1].lat, -12.046523) && casiIgual(puntos[1].lon, -77.043198))
        assertTrue(casiIgual(puntos[2].lat, -12.04649) && casiIgual(puntos[2].lon, -77.043259))
        assertTrue(
            casiIgual(puntos.last().lat, -12.056001) && casiIgual(puntos.last().lon, -77.035)
        )
    }

    @Test
    fun `la ruta entera cae dentro del Peru`() {
        // La comprobación que atrapa una precisión equivocada: con precisión 5
        // estos mismos bytes dan latitudes de -120, que no están en el mapa.
        val puntos = decodificarPolilinea(rutaReal)
        assertTrue(puntos.isNotEmpty())
        assertTrue(
            "toda la ruta debe caer en el Perú continental",
            puntos.all { it.lat in -18.5..0.0 && it.lon in -81.5..-68.5 },
        )
    }

    @Test
    fun `los puntos consecutivos estan cerca unos de otros`() {
        // Un salto de kilómetros entre dos puntos seguidos es la firma de un
        // desplazamiento de bits: la ruta sigue pareciendo una ruta, pero da
        // un tirón. Ninguna maniobra peatonal separa dos vértices 2 km.
        val puntos = decodificarPolilinea(rutaReal)
        puntos.zipWithNext { a, b ->
            val dLat = abs(a.lat - b.lat)
            val dLon = abs(a.lon - b.lon)
            assertTrue("salto anómalo entre $a y $b", dLat < 0.02 && dLon < 0.02)
        }
    }

    @Test
    fun `una cadena vacia no es un error, es una ruta sin geometria`() {
        assertEquals(0, decodificarPolilinea("").size)
    }

    @Test
    fun `una cadena truncada devuelve lo que pudo leer y no revienta`() {
        // El §7.3 cuenta con que el canal puede cortar a media respuesta. Que
        // el mapa salga corto es aceptable; que la app se cierre, no.
        for (corte in 1 until rutaReal.length) {
            val parcial = decodificarPolilinea(rutaReal.substring(0, corte))
            assertTrue("nunca más puntos que la cadena entera", parcial.size <= 106)
        }
    }
}
