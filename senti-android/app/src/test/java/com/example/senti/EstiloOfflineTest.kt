package com.example.senti

import com.example.senti.data.EstiloOffline
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * El estilo del mapa sin conexión.
 *
 * Se construye concatenando texto, que es cómodo de leer y peligroso de
 * romper: **un estilo mal formado no da error, deja el mapa negro**. MapLibre
 * descarta lo que no entiende y sigue. Por eso aquí se parsea de verdad el
 * JSON producido, en vez de comprobar que contiene ciertas palabras.
 */
class EstiloOfflineTest {

    private val json = Json { ignoreUnknownKeys = true }

    private fun estilo(detalle: String? = "/datos/lima_callao.pmtiles"): JsonObject =
        json.parseToJsonElement(
            EstiloOffline.estiloJson("/datos/peru.pmtiles", detalle)
        ).jsonObject

    private fun capas(e: JsonObject): JsonArray = e["layers"]!!.jsonArray

    private fun idsDeCapa(e: JsonObject): List<String> =
        capas(e).map { it.jsonObject["id"]!!.jsonPrimitive.content }

    @Test
    fun `el estilo con los dos packs es JSON valido`() {
        val e = estilo()
        assertEquals(8, e["version"]!!.jsonPrimitive.content.toInt())
        assertNotNull(e["sources"])
        assertTrue(capas(e).isNotEmpty())
    }

    @Test
    fun `el estilo con solo el pack nacional tambien es valido`() {
        // Es el caso de un APK ensamblado sin el pack de detalle. Tiene que
        // seguir dando un mapa del país, no un archivo roto.
        val e = estilo(detalle = null)
        val fuentes = e["sources"]!!.jsonObject
        assertTrue("debe estar el nacional", fuentes.containsKey("peru"))
        assertFalse("no debe declararse una fuente sin archivo", fuentes.containsKey("detalle"))
    }

    @Test
    fun `las fuentes apuntan a los archivos locales por el protocolo pmtiles`() {
        val fuentes = estilo()["sources"]!!.jsonObject

        val urlPeru = fuentes["peru"]!!.jsonObject["url"]!!.jsonPrimitive.content
        assertEquals("pmtiles://file:///datos/peru.pmtiles", urlPeru)

        val urlDetalle = fuentes["detalle"]!!.jsonObject["url"]!!.jsonPrimitive.content
        assertEquals("pmtiles://file:///datos/lima_callao.pmtiles", urlDetalle)
    }

    @Test
    fun `el estilo no pide nada por la red`() {
        // Lo que define este estilo: todo sale del disco. Una sola URL http
        // dejaría el mapa esperando a un servidor que no está.
        val crudo = EstiloOffline.estiloJson("/datos/peru.pmtiles", "/datos/lima.pmtiles")
        assertFalse("no puede haber http", crudo.contains("http://"))
        assertFalse("ni https", crudo.contains("https://"))
        // Sin `glyphs` no hay capas de texto que puedan quedarse esperando
        // fuentes tipográficas que no van a llegar.
        assertFalse("no debe declarar glyphs", crudo.contains("\"glyphs\""))
        assertFalse("no debe declarar sprite", crudo.contains("\"sprite\""))
    }

    @Test
    fun `no hay capas de simbolo, que exigirian glifos`() {
        capas(estilo()).forEach {
            val tipo = it.jsonObject["type"]!!.jsonPrimitive.content
            assertFalse("una capa symbol necesitaría glyphs", tipo == "symbol")
        }
    }

    @Test
    fun `cada capa tiene identificador unico`() {
        // Ids repetidos hacen que MapLibre descarte la segunda en silencio, y
        // aquí las vías se declaran dos veces —una por pack—, que es justo
        // donde se colaría una colisión.
        val ids = idsDeCapa(estilo())
        assertEquals("hay identificadores repetidos: $ids", ids.size, ids.toSet().size)
    }

    @Test
    fun `las vias se dibujan desde los dos packs`() {
        val ids = idsDeCapa(estilo())
        listOf("calles-menores", "calles", "avenidas", "autopistas").forEach { base ->
            assertTrue("falta $base del pack nacional", ids.contains("$base-peru"))
            assertTrue("falta $base del pack de detalle", ids.contains("$base-detalle"))
        }
    }

    @Test
    fun `las capas de detalle solo entran donde el pack nacional se queda corto`() {
        // El pack nacional llega a zoom 11. Si las capas de detalle empezaran
        // antes se dibujarían dos veces la misma vía; si empezaran después,
        // quedaría un hueco de zoom sin detalle dentro de Lima.
        capas(estilo()).forEach { capa ->
            val o = capa.jsonObject
            val id = o["id"]!!.jsonPrimitive.content
            if (id.endsWith("-detalle")) {
                val minzoom = o["minzoom"]?.jsonPrimitive?.content?.toInt()
                assertEquals("«$id» debe entrar en zoom 12", 12, minzoom)
            }
            if (id.endsWith("-peru")) {
                assertFalse("«$id» no debe tener minzoom", o.containsKey("minzoom"))
            }
        }
    }

    @Test
    fun `las autopistas se dibujan por encima de las calles menores`() {
        // El orden del array es el orden de pintado. Una autopista debajo de
        // las calles de barrio aparece cortada en cada cruce.
        val ids = idsDeCapa(estilo())
        assertTrue(ids.indexOf("autopistas-peru") > ids.indexOf("calles-menores-peru"))
        assertTrue(ids.indexOf("avenidas-peru") > ids.indexOf("calles-peru"))
    }

    @Test
    fun `el agua y la tierra van debajo de todas las vias`() {
        val ids = idsDeCapa(estilo())
        assertTrue(ids.indexOf("agua") < ids.indexOf("calles-menores-peru"))
        assertTrue(ids.indexOf("tierra") < ids.indexOf("agua"))
        assertEquals("el fondo va el primero", "fondo", ids.first())
    }

    @Test
    fun `si los packs estan generados, tienen el nombre y el tamano esperados`() {
        // Los `.pmtiles` NO se versionan: `.gitignore` los excluye porque son
        // datos generados. En un clon limpio todavía no existen y esta prueba
        // se salta en vez de fallar — un build sin teselas es válido y la app
        // lo declara en pantalla.
        //
        // Cuando sí están, se comprueba que se llaman como el código espera:
        // renombrar un asset hace desaparecer el mapa sin que nada falle al
        // compilar, y eso no se ve hasta abrir la app sin cobertura.
        val raices = listOf(File("src/main/assets"), File("app/src/main/assets"))
        val assets = raices.firstOrNull { it.isDirectory }
            ?: error("no se encontró el directorio de assets")

        val peru = File(assets, EstiloOffline.ASSET_PERU)
        org.junit.Assume.assumeTrue(
            "packs sin generar; ejecuta scripts/generar-teselas.sh",
            peru.isFile,
        )

        assertTrue("el pack nacional está vacío", peru.length() > 1_000_000)

        val detalle = File(assets, EstiloOffline.ASSET_DETALLE)
        assertTrue("falta ${EstiloOffline.ASSET_DETALLE}", detalle.isFile)
        assertTrue("el pack de detalle está vacío", detalle.length() > 1_000_000)
    }

    @Test
    fun `el recuadro de detalle cubre Lima y Callao`() {
        val d = EstiloOffline.LIMITES_DETALLE

        // Puntos reales dentro: Plaza de Armas, Callao y Villa El Salvador.
        assertTrue("centro de Lima", d.contiene(-12.0464, -77.0428))
        assertTrue("Callao", d.contiene(-12.0566, -77.1181))
        assertTrue("Villa El Salvador", d.contiene(-12.2136, -76.9367))

        // Y fuera: Arequipa e Iquitos, donde solo hay pack nacional.
        assertFalse("Arequipa", d.contiene(-16.4090, -71.5375))
        assertFalse("Iquitos", d.contiene(-3.7437, -73.2516))
    }
}
