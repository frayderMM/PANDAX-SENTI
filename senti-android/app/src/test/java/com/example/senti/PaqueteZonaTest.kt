package com.example.senti

import com.example.senti.data.ConflictoOffline
import com.example.senti.data.ContenidoZona
import com.example.senti.data.PaqueteZona
import com.example.senti.data.RecursoOffline
import com.example.senti.data.checksumDe
import com.example.senti.data.construirPaquete
import com.example.senti.data.cubre
import com.example.senti.data.ladoAproxM
import com.example.senti.data.limitesAlrededor
import com.example.senti.data.paqueteAJson
import com.example.senti.data.paqueteDesdeJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * El paquete de zona: su checksum, su caducidad y su tamaño.
 *
 * Las tres cosas que comprueba son las tres formas que tiene este paquete de
 * mentir sin dar error: venir a medias y parecer entero, ser de hace un mes y
 * parecer de ahora, y cubrir un barrio distinto del que estás.
 */
class PaqueteZonaTest {

    // Plaza de Armas de Lima. Se usa un punto real para que los metros que
    // salen de la conversión se puedan contrastar contra un mapa.
    private val lat = -12.0464
    private val lon = -77.0428

    private val contenido = ContenidoZona(
        conflictos = listOf(
            ConflictoOffline(
                id = "c1", tipo = "via_bloqueada", titulo = "Av. Abancay cerrada",
                lat = lat, lon = lon, oficial = true, confianza = "confirmado",
            )
        ),
        recursos = listOf(
            RecursoOffline("osm/node/1", "centro_salud", "Hospital Loayza", lat, lon)
        ),
    )

    @Test
    fun `un paquete recien construido es valido`() {
        val p = construirPaquete(lat, lon, contenido)
        assertNull(p.motivoInvalidez())
        assertTrue(p.valido)
    }

    @Test
    fun `si el contenido cambia sin recalcular el checksum, el paquete se rechaza`() {
        // Este es el caso que el checksum existe para atrapar: un archivo
        // escrito a medias o manipulado. El paquete sigue siendo JSON válido y
        // se deserializa sin problema; lo único que lo delata es el hash.
        val p = construirPaquete(lat, lon, contenido)
        val manipulado = p.copy(
            contenido = p.contenido.copy(conflictos = emptyList())
        )
        assertFalse(manipulado.valido)
        assertNotNull(manipulado.motivoInvalidez())
    }

    @Test
    fun `un paquete de otra version del formato se rechaza entero`() {
        val p = construirPaquete(lat, lon, contenido).copy(formato = 99)
        assertNotNull(p.motivoInvalidez())
    }

    @Test
    fun `el checksum es estable entre dos serializaciones del mismo contenido`() {
        // Si no lo fuera, un paquete recién guardado se rechazaría al leerlo y
        // la app se quedaría sin datos sin explicación posible.
        assertEquals(checksumDe(contenido), checksumDe(contenido))
        assertEquals(checksumDe(contenido), checksumDe(contenido.copy()))
    }

    @Test
    fun `dos contenidos distintos no comparten checksum`() {
        val otro = contenido.copy(conflictos = emptyList())
        assertFalse(checksumDe(contenido) == checksumDe(otro))
    }

    @Test
    fun `el paquete sobrevive al viaje de ida y vuelta por JSON`() {
        val p = construirPaquete(lat, lon, contenido)
        val recuperado = paqueteDesdeJson(paqueteAJson(p))
        assertEquals(p, recuperado)
        assertTrue(recuperado!!.valido)
    }

    @Test
    fun `un paquete vence a los siete dias y se marca como vencido`() {
        val ahora = 1_800_000_000_000L
        val p = construirPaquete(lat, lon, contenido, ahora = ahora)

        assertFalse("recién descargado no está vencido", p.vencido(ahora))
        assertFalse("a los seis días sigue sirviendo", p.vencido(ahora + 6 * DIA))
        assertTrue("a los siete días está vencido", p.vencido(ahora + 7 * DIA))
        assertTrue("a los diez días, más aún", p.vencido(ahora + 10 * DIA))
    }

    @Test
    fun `el area descargada mide unos diez kilometros cuadrados`() {
        // El requisito son 10 km². Se comprueba el resultado en metros y no la
        // constante, porque el error probable no está en el número sino en la
        // conversión de grados a metros.
        val limites = limitesAlrededor(lat, lon, PaqueteZona.MEDIO_LADO_M)
        val ladoM = limites.ladoAproxM()
        val areaKm2 = (ladoM / 1000.0) * (ladoM / 1000.0)

        assertTrue(
            "el área debe rondar los 10 km², salió $areaKm2",
            abs(areaKm2 - 10.0) < 0.5,
        )
    }

    @Test
    fun `los limites se estrechan en longitud al alejarse del ecuador`() {
        // Un grado de longitud vale menos metros cuanto más lejos del ecuador.
        // Ignorarlo daría un rectángulo en vez de un cuadrado; en Lima el error
        // es del 2 %, pero la fórmula tiene que ser la correcta.
        val enLima = limitesAlrededor(-12.0, -77.0, 1581.0)
        val enEcuador = limitesAlrededor(0.0, -77.0, 1581.0)

        val anchoLima = enLima.maxLon - enLima.minLon
        val anchoEcuador = enEcuador.maxLon - enEcuador.minLon
        assertTrue("en Lima el cuadrado abarca más grados de longitud", anchoLima > anchoEcuador)
    }

    @Test
    fun `el paquete sabe si cubre donde estas`() {
        val p = construirPaquete(lat, lon, contenido)

        assertTrue("el propio centro está dentro", p.cubre(lat, lon))
        assertTrue("un punto a 1 km sigue dentro", p.cubre(lat + 0.009, lon))
        assertFalse("a 5 km ya está fuera", p.cubre(lat + 0.045, lon))
        assertFalse("otra ciudad está fuera", p.cubre(-16.4, -71.5))
    }

    @Test
    fun `las fuentes que fallaron viajan dentro del paquete`() {
        // Es lo que permite a la pantalla decir "esto no se pudo consultar" en
        // vez de dejar que un mapa sin bloqueos se lea como una vía libre.
        val conFallos = contenido.copy(fuentesFallidas = listOf("bloqueos y conflictos viales"))
        val p = construirPaquete(lat, lon, conFallos)

        assertTrue(p.valido)
        assertEquals(listOf("bloqueos y conflictos viales"), p.contenido.fuentesFallidas)

        // Y entran en el checksum: perderlas por el camino sería exactamente
        // el silencio que el §11.3 prohíbe.
        assertFalse(checksumDe(conFallos) == checksumDe(contenido))
    }

    private companion object {
        const val DIA = 24L * 60 * 60 * 1000
    }
}
