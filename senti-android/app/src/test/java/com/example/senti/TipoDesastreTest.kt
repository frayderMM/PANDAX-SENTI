package com.example.senti

import com.example.senti.data.EventoMapa
import com.example.senti.data.MarcadorMapa
import com.example.senti.data.ReporteResumen
import com.example.senti.data.TipoDesastre
import com.example.senti.data.aMarcador
import com.example.senti.data.tiposPresentes
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * La clasificación de desastres que alimenta el filtro y la ficha del mapa.
 *
 * Es un espejo de `HazardType` del backend, y ahí está el riesgo que estas
 * pruebas cubren: si el backend añade un tipo y la app no, el marcador no
 * puede desaparecer del mapa. Un peligro que no se sabe nombrar se sigue
 * pintando; lo contrario sería ocultar un huaico por un fallo de vocabulario.
 */
class TipoDesastreTest {

    /** Los doce de `HazardType`, copiados a mano desde app/domain.py. */
    private val delBackend = listOf(
        "inundacion", "huaico", "deslizamiento", "lluvia", "sismo", "tsunami",
        "incendio", "via_bloqueada", "puente_afectado", "acumulacion_agua",
        "caida_poste", "otro",
    )

    @Test
    fun `estan los doce tipos del backend`() {
        delBackend.forEach { codigo ->
            assertNotNull("falta el tipo '$codigo'", TipoDesastre.desde(codigo))
        }
        assertEquals(delBackend.size, TipoDesastre.entries.size)
    }

    @Test
    fun `los codigos coinciden exactamente con los del backend`() {
        // Un código con mayúscula o con guion en vez de guion bajo no casaría
        // con lo que llega por la API, y el tipo caería a "desconocido" sin
        // que nada fallara.
        assertEquals(delBackend.toSet(), TipoDesastre.entries.map { it.codigo }.toSet())
    }

    @Test
    fun `cada tipo tiene una etiqueta legible y distinta`() {
        val etiquetas = TipoDesastre.entries.map { it.etiqueta }
        assertTrue("ninguna etiqueta puede ir vacía", etiquetas.none { it.isBlank() })
        assertEquals("no puede haber dos tipos con el mismo nombre",
            etiquetas.size, etiquetas.toSet().size)
    }

    @Test
    fun `cada tipo tiene un color distinto`() {
        // El filtro y los marcadores se distinguen por color; dos tipos del
        // mismo tono los vuelve indistinguibles de un vistazo.
        val colores = TipoDesastre.entries.map { it.color }
        assertEquals(colores.size, colores.toSet().size)
    }

    @Test
    fun `un tipo desconocido se muestra, no se descarta`() {
        // El caso que importa: backend nuevo, app vieja. Se enseña el código
        // legible en vez de esconderlo o llamarlo "Otro".
        assertNull(TipoDesastre.desde("alud"))
        assertEquals("Alud", TipoDesastre.etiquetaDe("alud"))
        assertEquals("Corte electrico", TipoDesastre.etiquetaDe("corte_electrico"))
        assertEquals(TipoDesastre.COLOR_DESCONOCIDO, TipoDesastre.colorDe("alud"))
    }

    @Test
    fun `un tipo ausente o vacio se declara sin clasificar`() {
        assertEquals("Sin clasificar", TipoDesastre.etiquetaDe(null))
        assertEquals("Sin clasificar", TipoDesastre.etiquetaDe(""))
        assertEquals("Sin clasificar", TipoDesastre.etiquetaDe("   "))
    }

    @Test
    fun `el codigo se reconoce sin importar espacios ni mayusculas`() {
        assertEquals(TipoDesastre.HUAICO, TipoDesastre.desde(" Huaico "))
        assertEquals(TipoDesastre.VIA_BLOQUEADA, TipoDesastre.desde("VIA_BLOQUEADA"))
    }
}

/**
 * La conversión a marcador y el recuento del filtro.
 *
 * Lo que se protege aquí es que al unificar eventos y reportes en un solo mapa
 * **no se pierda de dónde vino cada uno**. El §25 prohíbe mezclar reportes
 * ciudadanos con fuentes oficiales, y la ficha solo puede distinguirlos si el
 * dato sobrevive a la conversión.
 */
class MarcadorMapaTest {

    private fun reporte(
        id: String = "r1",
        tipo: String = "huaico",
        lat: Double? = -12.0,
        lon: Double? = -77.0,
        confirmado: Boolean = false,
    ) = ReporteResumen(
        id = id, tipo = tipo, estado = "vigente", confianza = "pendiente",
        confirmado = confirmado, descripcion = "Bajó material por la quebrada",
        direccion = null, distrito = "Chosica", reportadoAt = "2026-08-01T10:00:00Z",
        lat = lat, lon = lon,
    )

    private fun evento(
        id: String = "e1",
        tipo: String = "inundacion",
        lat: Double? = -12.1,
        lon: Double? = -77.1,
        oficiales: Int = 2,
    ) = EventoMapa(
        id = id, title = "Desborde del río Rímac", type = tipo, lat = lat, lon = lon,
        personas = 5, reportes = 5, fuentesOficiales = oficiales,
        confidence = 80.0, estado = "CONFIRMADO",
        ultimoReporte = "2026-08-01T09:00:00Z", summary = "El agua alcanzó la vía",
    )

    @Test
    fun `un reporte sin coordenadas no genera marcador`() {
        // No se inventa una posición: un punto en el sitio equivocado es peor
        // que un punto que no está.
        assertNull(reporte(lat = null).aMarcador())
        assertNull(reporte(lon = null).aMarcador())
        assertNull(evento(lat = null).aMarcador())
    }

    @Test
    fun `un reporte ciudadano sin confirmar no se marca como oficial`() {
        val m = reporte(confirmado = false).aMarcador()!!
        assertFalse(m.oficial)
        assertEquals("pendiente", m.confianza)
        assertEquals("Huaico", m.titulo)
        assertEquals("Bajó material por la quebrada", m.descripcion)
    }

    @Test
    fun `un reporte confirmado si se marca como oficial`() {
        assertTrue(reporte(confirmado = true).aMarcador()!!.oficial)
    }

    @Test
    fun `un evento es oficial solo si alguna fuente oficial lo respalda`() {
        assertTrue(evento(oficiales = 1).aMarcador()!!.oficial)
        assertFalse(evento(oficiales = 0).aMarcador()!!.oficial)
    }

    @Test
    fun `el evento conserva su titulo propio y no lo sustituye por el tipo`() {
        val m = evento().aMarcador()!!
        assertEquals("Desborde del río Rímac", m.titulo)
        assertEquals("Inundación", m.etiquetaTipo)
    }

    @Test
    fun `un evento sin titulo cae al nombre del tipo`() {
        val m = evento().copy(title = "").aMarcador()!!
        assertEquals("Inundación", m.titulo)
    }

    @Test
    fun `el filtro cuenta los tipos presentes y los ordena por cantidad`() {
        val marcadores = listOfNotNull(
            reporte("a", "huaico").aMarcador(),
            reporte("b", "huaico").aMarcador(),
            reporte("c", "huaico").aMarcador(),
            reporte("d", "sismo").aMarcador(),
            evento("e", "inundacion").aMarcador(),
            evento("f", "inundacion").aMarcador(),
        )

        assertEquals(
            listOf("huaico" to 3, "inundacion" to 2, "sismo" to 1),
            marcadores.tiposPresentes(),
        )
    }

    @Test
    fun `el filtro solo ofrece tipos que existen en el mapa`() {
        val marcadores = listOfNotNull(reporte("a", "huaico").aMarcador())
        val ofrecidos = marcadores.tiposPresentes().map { it.first }

        assertEquals(listOf("huaico"), ofrecidos)
        assertFalse("no puede ofrecer un tipo sin marcadores", ofrecidos.contains("tsunami"))
    }

    @Test
    fun `sin marcadores el filtro no ofrece nada`() {
        assertTrue(emptyList<MarcadorMapa>().tiposPresentes().isEmpty())
    }

    @Test
    fun `filtrar por un tipo deja solo los de ese tipo`() {
        // Réplica de lo que hace la pantalla: conjunto vacío significa todos.
        val marcadores = listOfNotNull(
            reporte("a", "huaico").aMarcador(),
            reporte("b", "sismo").aMarcador(),
            evento("c", "inundacion").aMarcador(),
        )

        fun filtrar(activos: Set<String>) =
            if (activos.isEmpty()) marcadores else marcadores.filter { it.tipo in activos }

        assertEquals(3, filtrar(emptySet()).size)
        assertEquals(1, filtrar(setOf("huaico")).size)
        assertEquals(2, filtrar(setOf("huaico", "sismo")).size)
        assertEquals(0, filtrar(setOf("tsunami")).size)
    }
}
