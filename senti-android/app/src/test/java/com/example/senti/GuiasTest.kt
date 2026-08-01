package com.example.senti

import com.example.senti.data.Guias
import com.example.senti.data.fechaIsoAMs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Las guías que viajan dentro del APK.
 *
 * Se prueba el asset **real**, el mismo que se empaqueta, y no un JSON de
 * ejemplo escrito para la prueba. Es la única forma de que esto sirva de algo:
 * lo que puede romperse aquí no es el parser —es que alguien edite el JSON y
 * se deje una coma, o borre las acciones críticas de la guía de huaico— y un
 * fixture propio no se enteraría.
 */
class GuiasTest {

    private val crudo: String by lazy {
        // El directorio de trabajo de un test unitario es el del módulo.
        val candidatos = listOf(
            File("src/main/assets/${Guias.ASSET}"),
            File("app/src/main/assets/${Guias.ASSET}"),
        )
        candidatos.firstOrNull { it.exists() }?.readText()
            ?: error("no se encontró el asset de guías; buscado en $candidatos")
    }

    private val pack by lazy {
        Guias.parsear(crudo) ?: error("el asset de guías no se pudo interpretar")
    }

    /** Las diez que exige el requisito, por identificador. */
    private val exigidas = listOf(
        "mochila", "inundacion", "huaico", "incendio", "derrumbe",
        "evacuacion", "punto_reunion", "sin_senal", "primeros_pasos", "telefonos",
    )

    @Test
    fun `el asset empaquetado se interpreta`() {
        assertNotNull(Guias.parsear(crudo))
    }

    @Test
    fun `estan las diez guias exigidas`() {
        exigidas.forEach { id ->
            assertNotNull("falta la guía '$id'", pack.porId(id))
        }
        assertEquals("no debe haber guías de más sin declarar", exigidas.size, pack.guias.size)
    }

    @Test
    fun `cada guia lleva institucion, version, fuente y acciones`() {
        // §11.4: una guía sin institución ni versión no se puede presentar como
        // verificada. Y una guía sin acciones no es una guía: es un título.
        pack.guias.forEach { g ->
            assertTrue("'${g.id}' sin título", g.titulo.isNotBlank())
            assertTrue("'${g.id}' sin institución", g.institucion.isNotBlank())
            assertTrue("'${g.id}' sin fuente", g.fuente.isNotBlank())
            assertTrue("'${g.id}' sin versión", g.version.isNotBlank())
            assertTrue("'${g.id}' sin acciones", g.acciones.isNotEmpty())
            g.acciones.forEach { a ->
                assertTrue("acción vacía en '${g.id}'", a.texto.isNotBlank())
            }
        }
    }

    @Test
    fun `cada guia declara de donde sale su redaccion`() {
        // Distinguir los tres orígenes es lo que impide atribuir a INDECI una
        // redacción que no es suya. Un valor desconocido aquí significa que
        // alguien añadió una guía sin decir de dónde la sacó.
        val validos = setOf("protocolo", "texto_fijo", "resumen_local")
        pack.guias.forEach { g ->
            assertTrue(
                "origen desconocido '${g.origen}' en '${g.id}'",
                g.origen in validos,
            )
        }
    }

    @Test
    fun `las guias de peligro llevan al menos una accion critica`() {
        // Una guía de huaico donde nada esté marcado como crítico se lee como
        // una lista de sugerencias, y ahí dentro está "aléjate del cauce".
        listOf("inundacion", "huaico", "incendio", "derrumbe", "evacuacion").forEach { id ->
            val g = pack.porId(id) ?: error("falta '$id'")
            assertTrue(
                "'$id' no tiene ninguna acción crítica",
                g.acciones.any { it.critica },
            )
        }
    }

    @Test
    fun `las guias reproducidas de un protocolo conservan su texto literal`() {
        // Son las que el backend puede trazar palabra por palabra. Si alguien
        // las "mejora" redactando, dejan de ser reproducciones y la etiqueta
        // de origen pasa a ser falsa.
        val inundacion = pack.porId("inundacion") ?: error("falta inundación")
        assertEquals("protocolo", inundacion.origen)
        listOf(
            "Guardar documentos en una bolsa impermeable",
            "Cargar los celulares",
            "Confirmar el punto de reunión",
        ).forEach { esperada ->
            assertTrue(
                "el protocolo INUNDACION-2H incluye «$esperada» y no aparece",
                inundacion.acciones.any { it.texto == esperada },
            )
        }

        val huaico = pack.porId("huaico") ?: error("falta huaico")
        assertEquals("protocolo", huaico.origen)
        assertTrue(
            huaico.acciones.any { it.texto == "No intentes cruzar el material del huaico" },
        )
    }

    @Test
    fun `los telefonos de emergencia estan completos`() {
        val telefonos = pack.porId("telefonos") ?: error("falta la guía de teléfonos")
        val texto = telefonos.acciones.joinToString(" ") { it.texto }
        listOf("115", "116", "106", "105", "110", "0800-12345").forEach { numero ->
            assertTrue("falta el $numero", texto.contains(numero))
        }
    }

    @Test
    fun `un pack recien compilado no esta desactualizado`() {
        val compilado = pack.compiladoMs
        assertNotNull("la fecha de compilación debe leerse", compilado)
        assertFalse(pack.desactualizado(ahora = compilado!!))
        assertNull(pack.advertencia(ahora = compilado))
    }

    @Test
    fun `pasada la vigencia el pack se marca y se avisa`() {
        val compilado = pack.compiladoMs!!
        // Trece meses después de compilarlo, con vigencia de doce.
        val tarde = compilado + 400L * 24 * 60 * 60 * 1000

        assertTrue(pack.desactualizado(ahora = tarde))
        val aviso = pack.advertencia(ahora = tarde)
        assertNotNull("debe haber advertencia", aviso)
        assertTrue("la advertencia debe decir que puede no estar vigente",
            aviso!!.contains("vigente"))
    }

    @Test
    fun `una fecha ilegible se trata como desactualizada`() {
        // El lado seguro: una fecha que no se entiende no es una fecha
        // reciente. La asimetría es deliberada, igual que en la cobertura
        // cartográfica del §20.4.
        val roto = pack.copy(compiladoAt = "ayer por la tarde")
        assertNull(roto.compiladoMs)
        assertTrue(roto.desactualizado())
    }

    @Test
    fun `las guias salen ordenadas y sin saltos`() {
        val ordenes = pack.ordenadas.map { it.orden }
        assertEquals("el orden debe ser estrictamente creciente", ordenes.sorted(), ordenes)
        assertEquals("no debe haber dos guías con el mismo orden",
            ordenes.size, ordenes.toSet().size)
    }

    @Test
    fun `el parseo de fechas ISO aguanta lo que no lo es`() {
        assertEquals(0L, fechaIsoAMs("1970-01-01"))
        assertNull(fechaIsoAMs(""))
        assertNull(fechaIsoAMs("no es fecha"))
        assertNull(fechaIsoAMs("2026-13-45"))
    }
}
