package com.example.senti

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Tocar el mapa no publica nada.
 *
 * **Por qué esta prueba mira el código fuente y no ejecuta la app.** Lo que hay
 * que garantizar es estructural: que no exista ningún camino desde un toque en
 * el mapa hasta `POST /reportes`. Comprobarlo ejecutando exigiría un
 * dispositivo y una prueba de interfaz por cada pantalla con mapa, y aun así
 * solo cubriría los caminos que a alguien se le ocurriera recorrer. Contar los
 * puntos de llamada cubre todos.
 *
 * No prueba que el botón «Enviar reporte» funcione —eso es otra cosa— sino que
 * **es el único que puede**. Si mañana alguien añade una llamada a
 * `Api.crearReporte` desde un gesto del mapa, esto se rompe antes de compilar
 * un APK.
 */
class ReporteSoloExplicitoTest {

    private val fuentes: List<File> by lazy {
        val raices = listOf(
            File("src/main/java/com/example/senti"),
            File("app/src/main/java/com/example/senti"),
        )
        val raiz = raices.firstOrNull { it.isDirectory }
            ?: error("no se encontró el código fuente; buscado en $raices")
        raiz.walkTopDown().filter { it.isFile && it.extension == "kt" }.toList()
    }

    private fun leer(nombre: String): String =
        fuentes.firstOrNull { it.name == nombre }?.readText()
            ?: error("no se encontró $nombre")

    /** Quita comentarios de línea y de bloque para no contar los que hablan de esto. */
    private fun sinComentarios(codigo: String): String = codigo
        .replace(Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL), "")
        .replace(Regex("//.*"), "")

    @Test
    fun `solo hay un sitio en toda la app que publique un reporte`() {
        val llamadas = fuentes
            .filter { it.name != "Api.kt" }
            .flatMap { archivo ->
                sinComentarios(archivo.readText())
                    .split("Api.crearReporte")
                    .drop(1)
                    .map { archivo.name }
            }

        assertEquals(
            "publicar un reporte debe salir de un único sitio, y salió de: $llamadas",
            listOf("SentiViewModel.kt"),
            llamadas,
        )
    }

    @Test
    fun `el mapa de ruta no publica nada al tocarlo`() {
        // Marcar un atasco cambia por dónde se calcula la ruta y nada más. El
        // §21.2 reserva el cierre de una vía al operador municipal: si un toque
        // creara un reporte, cualquiera cerraría calles con el dedo.
        val mapa = sinComentarios(leer("MapaRuta.kt"))
        assertTrue("el mapa de ruta no debe crear reportes", !mapa.contains("crearReporte"))
        assertTrue("ni llamar a /reportes", !mapa.contains("\"/reportes\""))
    }

    @Test
    fun `el mapa sin conexion no publica nada al tocarlo`() {
        // Aquí es todavía más claro: sin red no habría a dónde publicarlo, y
        // una cola de reportes pendientes creados sin querer se vaciaría toda
        // junta al recuperar cobertura.
        val mapa = sinComentarios(leer("MapaOffline.kt"))
        assertTrue("el mapa sin conexión no debe crear reportes", !mapa.contains("crearReporte"))
        assertTrue("ni hablar con la API", !mapa.contains("Api."))
    }

    @Test
    fun `la pantalla sin conexion no habla con la API`() {
        // El modo sin conexión no consulta nada: si lo hiciera, se quedaría
        // esperando un servidor inalcanzable justo cuando hay prisa.
        val pantalla = sinComentarios(leer("PantallaOffline.kt"))
        assertTrue("la pantalla sin conexión no debe llamar a la API", !pantalla.contains("Api."))
    }

    @Test
    fun `las guias se leen del APK y no de la red`() {
        val guias = sinComentarios(leer("Guias.kt"))
        assertTrue("las guías salen de assets", guias.contains("context.assets.open"))
        assertTrue("y nunca de la API", !guias.contains("Api."))
        assertTrue("ni de una URL", !guias.contains("http"))
    }

    @Test
    fun `la sesion se lee antes de la carga pesada del disco`() {
        // Regresión. La lectura de la sesión estaba dentro de la misma
        // corrutina que copia los 64 MB de teselas del APK, así que durante
        // ese rato el estado decía "no hay sesión guardada" y el login se
        // pintaba SIN el botón de entrar sin conexión. Justo lo que alguien
        // sin cobertura necesita, ausente durante decenas de segundos.
        //
        // El invariante: la sesión se publica antes de arrancar la corrutina.
        val fuente = sinComentarios(leer("ModoOfflineViewModel.kt"))

        val posSesion = fuente.indexOf("sesionSegura.leer()")
        val posCorrutina = fuente.indexOf("viewModelScope.launch")

        assertTrue("no se encontró la lectura de la sesión", posSesion >= 0)
        assertTrue("no se encontró la corrutina de carga", posCorrutina >= 0)
        assertTrue(
            "la sesión debe leerse antes de lanzar la carga pesada, " +
                "o el botón de entrar sin conexión llega tarde",
            posSesion < posCorrutina,
        )
    }

    @Test
    fun `la copia de los packs no bloquea el hilo principal`() {
        // El otro lado de la misma moneda: leer la sesión es barato y va
        // síncrono, pero copiar los packs son decenas de megas y tiene que
        // seguir fuera del hilo principal o es un ANR en gama baja.
        val fuente = sinComentarios(leer("ModoOfflineViewModel.kt"))

        val posIO = fuente.indexOf("Dispatchers.IO")
        val posPacks = fuente.indexOf("prepararPacks")

        assertTrue("no se encontró el cambio a Dispatchers.IO", posIO >= 0)
        assertTrue(
            "prepararPacks debe ejecutarse dentro del bloque de Dispatchers.IO",
            posPacks > posIO,
        )
    }

    @Test
    fun `la sesion guardada no tiene ningun campo de contrasena`() {
        // Complementa a SesionOfflineTest desde el otro lado: allí se mira el
        // JSON que sale, aquí que el modelo no lo declare siquiera.
        val sesion = sinComentarios(leer("SesionSegura.kt"))
        listOf("password", "contrasena", "contraseña")
            .forEach { prohibido ->
                assertTrue(
                    "SesionSegura.kt no puede mencionar '$prohibido' fuera de un comentario",
                    !sesion.lowercase().contains(prohibido),
                )
            }
    }
}
