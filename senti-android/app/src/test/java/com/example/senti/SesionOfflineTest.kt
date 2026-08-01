package com.example.senti

import com.example.senti.data.SesionLocal
import com.example.senti.data.aJson
import com.example.senti.data.sesionDesdeJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * La sesión que permite entrar sin conexión (§26, §13.5).
 *
 * La prueba que de verdad importa es la primera: **que la contraseña no esté**.
 * Es la clase de fallo que no se manifiesta nunca durante el desarrollo —la app
 * funciona igual de bien guardándola— y que solo se descubre cuando alguien
 * pierde el teléfono. Por eso se comprueba sobre el texto exacto que se cifra y
 * no sobre la forma de la clase: un campo añadido de más en el futuro tiene que
 * hacer fallar esto.
 */
class SesionOfflineTest {

    private val sesion = SesionLocal(
        email = "vecina@example.pe",
        token = "eyJhbGciOiJIUzI1NiJ9.token-de-prueba",
        rol = "ciudadano",
        expiraAt = 2_000_000_000_000L,
        guardadaAt = 1_900_000_000_000L,
    )

    @Test
    fun `lo que se guarda no contiene ninguna contrasena`() {
        val json = sesion.aJson().lowercase()

        // No se busca solo la palabra exacta: se busca cualquier cosa que
        // huela a credencial. Si alguien añade `clave` o `pass` al modelo, esto
        // tiene que romperse antes de llegar a un teléfono.
        listOf("password", "contrasena", "contraseña", "clave", "pass", "secret", "pwd")
            .forEach { prohibido ->
                assertFalse(
                    "la sesión guardada no puede contener '$prohibido': $json",
                    json.contains(prohibido),
                )
            }
    }

    @Test
    fun `la sesion guardada solo lleva los campos previstos`() {
        // Cierra la puerta que la prueba anterior deja entreabierta: un campo
        // nuevo con un nombre inocente —"p", "cred"— pasaría el filtro de
        // palabras pero no esta lista cerrada.
        val esperados = setOf("email", "token", "rol", "expira_at", "guardada_at")
        val presentes = Regex("\"([a-z_]+)\"\\s*:").findAll(sesion.aJson())
            .map { it.groupValues[1] }
            .toSet()
        assertEquals(esperados, presentes)
    }

    @Test
    fun `la sesion sobrevive al viaje de ida y vuelta`() {
        val recuperada = sesionDesdeJson(sesion.aJson())
        assertEquals(sesion, recuperada)
    }

    @Test
    fun `un texto que no es una sesion se rechaza en vez de reventar`() {
        // Pasa de verdad: el descifrado con una clave invalidada por un cambio
        // de PIN devuelve bytes plausibles pero sin sentido. Lo correcto es
        // tratarlo como "no hay sesión", no cerrar la app al arrancar.
        assertNull(sesionDesdeJson("{no es json"))
        assertNull(sesionDesdeJson(""))
        assertNull(sesionDesdeJson("""{"email":"a@b.pe"}"""))
    }

    @Test
    fun `un token vencido se reconoce como vencido`() {
        assertTrue(sesion.caducada(ahora = sesion.expiraAt))
        assertTrue(sesion.caducada(ahora = sesion.expiraAt + 1))
        assertFalse(sesion.caducada(ahora = sesion.expiraAt - 1))
    }

    @Test
    fun `una sesion vencida sigue sirviendo para identificar al dueno`() {
        // El modo sin conexión la acepta a propósito: no consulta al servidor,
        // así que exigir un token vivo dejaría fuera del mapa justo a quien
        // lleva días sin cobertura. Lo que no puede es fingir estar fresca.
        val vencida = sesion.copy(expiraAt = 1L)
        assertTrue(vencida.caducada())
        assertEquals("vecina@example.pe", vencida.email)
    }
}
