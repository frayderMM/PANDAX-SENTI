package com.example.senti

import com.example.senti.data.AlmacenZona
import com.example.senti.data.ConflictoOffline
import com.example.senti.data.ContenidoZona
import com.example.senti.data.LecturaZona
import com.example.senti.data.construirPaquete
import com.example.senti.data.paqueteAJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * El almacén del paquete en disco.
 *
 * Lo que se prueba aquí es una promesa concreta: **una actualización que sale
 * mal no puede dejarte sin el mapa que ya tenías**. Es la diferencia entre
 * salir de casa con datos de ayer y salir sin nada, y ocurre justo cuando la
 * red va mal — que es cuando la gente sincroniza.
 */
class AlmacenZonaTest {

    @get:Rule
    val carpeta = TemporaryFolder()

    private val lat = -12.0464
    private val lon = -77.0428

    private fun contenidoCon(titulo: String) = ContenidoZona(
        conflictos = listOf(
            ConflictoOffline(
                id = "c1", tipo = "via_bloqueada", titulo = titulo,
                lat = lat, lon = lon, oficial = true,
            )
        )
    )

    private fun almacen() = AlmacenZona(carpeta.root)

    @Test
    fun `sin paquete guardado la lectura dice que esta vacio`() {
        assertTrue(almacen().leer() is LecturaZona.Vacio)
    }

    @Test
    fun `un paquete guardado se recupera igual`() {
        val a = almacen()
        val p = construirPaquete(lat, lon, contenidoCon("Av. Abancay cerrada"))

        assertNull("guardar no debe reportar error", a.guardar(p))

        val leido = a.leer()
        assertTrue(leido is LecturaZona.Ok)
        assertEquals(p, (leido as LecturaZona.Ok).paquete)
    }

    @Test
    fun `un paquete invalido no llega a tocar el disco`() {
        val a = almacen()
        val bueno = construirPaquete(lat, lon, contenidoCon("bueno"))
        a.guardar(bueno)

        // Checksum que no corresponde al contenido: exactamente lo que llegaría
        // de una descarga cortada a la mitad.
        val corrupto = construirPaquete(lat, lon, contenidoCon("malo"))
            .copy(checksum = "0000000000000000000000000000000000000000000000000000000000000000")

        assertNotNull("guardar debe rechazarlo y decir por qué", a.guardar(corrupto))

        val leido = a.leer()
        assertTrue("el paquete bueno sigue ahí", leido is LecturaZona.Ok)
        assertEquals(
            "y es el bueno, no el corrupto",
            "bueno",
            (leido as LecturaZona.Ok).paquete.contenido.conflictos.first().titulo,
        )
    }

    @Test
    fun `una actualizacion correcta si sustituye a la anterior`() {
        val a = almacen()
        a.guardar(construirPaquete(lat, lon, contenidoCon("viejo"), ahora = 1_000L))
        a.guardar(construirPaquete(lat, lon, contenidoCon("nuevo"), ahora = 2_000L))

        val leido = a.leer() as LecturaZona.Ok
        assertEquals("nuevo", leido.paquete.contenido.conflictos.first().titulo)
        assertEquals(2_000L, leido.paquete.sincronizadoAt)
    }

    @Test
    fun `un archivo a medio escribir se rechaza y no se sirve a medias`() {
        val a = almacen()
        val p = construirPaquete(lat, lon, contenidoCon("Av. Abancay cerrada"))
        a.guardar(p)

        // Se trunca el archivo, que es lo que deja un corte de corriente o un
        // disco lleno. Lo peligroso no sería fallar: sería leer los bloqueos
        // que sí se alcanzaron a escribir y dibujar medio mapa.
        val archivo = File(carpeta.root, "paquete_zona.json")
        val entero = archivo.readText()
        archivo.writeText(entero.substring(0, entero.length / 2))

        val leido = a.leer()
        assertTrue("un JSON truncado es corrupto", leido is LecturaZona.Corrupto)
    }

    @Test
    fun `un paquete manipulado se detecta por el checksum`() {
        val a = almacen()
        a.guardar(construirPaquete(lat, lon, contenidoCon("Av. Abancay cerrada")))

        // JSON perfectamente válido, con un bloqueo menos. Sin checksum esto
        // pasaría por bueno y alguien cruzaría por donde no debe.
        val archivo = File(carpeta.root, "paquete_zona.json")
        archivo.writeText(archivo.readText().replace("Av. Abancay cerrada", "Av. Abancay abierta"))

        val leido = a.leer()
        assertTrue(leido is LecturaZona.Corrupto)
    }

    @Test
    fun `un paquete corrupto se borra para no reintentarlo en cada arranque`() {
        val a = almacen()
        a.guardar(construirPaquete(lat, lon, contenidoCon("x")))
        val archivo = File(carpeta.root, "paquete_zona.json")
        archivo.writeText("{esto no es json")

        assertTrue(a.leer() is LecturaZona.Corrupto)
        assertTrue("y en la siguiente lectura ya no está", a.leer() is LecturaZona.Vacio)
    }

    @Test
    fun `no queda ningun temporal despues de guardar`() {
        // Un `.tmp` olvidado ocuparía el doble de espacio en un teléfono que
        // suele estar lleno, y en el siguiente guardado confundiría el estado.
        val a = almacen()
        a.guardar(construirPaquete(lat, lon, contenidoCon("x")))

        val temporales = carpeta.root.listFiles()?.filter { it.name.endsWith(".tmp") }.orEmpty()
        assertTrue("no debe quedar ningún .tmp: $temporales", temporales.isEmpty())
    }

    @Test
    fun `borrar deja el almacen vacio`() {
        val a = almacen()
        a.guardar(construirPaquete(lat, lon, contenidoCon("x")))
        a.borrar()
        assertTrue(a.leer() is LecturaZona.Vacio)
    }

    @Test
    fun `lo que se escribe en disco es el JSON del paquete`() {
        // Comprueba que no se guarda una representación distinta de la que se
        // valida: si divergieran, el checksum dejaría de significar nada.
        val a = almacen()
        val p = construirPaquete(lat, lon, contenidoCon("x"))
        a.guardar(p)

        val enDisco = File(carpeta.root, "paquete_zona.json").readText()
        assertEquals(paqueteAJson(p), enDisco)
    }
}
