package com.example.senti.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Sesión que sobrevive a la falta de red (§26, §13.5).
 *
 * **La contraseña no está aquí, y no es un descuido que se pueda arreglar
 * después: no existe el campo.** Guardar la contraseña —aunque fuera cifrada—
 * convertiría el teléfono en una copia de la credencial, y un teléfono en una
 * emergencia es justo el objeto que se pierde, se moja o se lo lleva el agua.
 * Lo que se guarda es el token que el backend ya emitió, que caduca solo y que
 * no sirve para entrar en ningún otro sitio.
 *
 * Cifrado con AES/GCM y clave en el Android Keystore. La clave no sale del
 * hardware: se pide al Keystore que cifre, no que entregue la clave. Si alguien
 * saca el almacenamiento de la app —con root o con una copia de seguridad— se
 * lleva bytes que no puede descifrar en otro equipo.
 *
 * Se eligió AES/GCM a mano en lugar de `androidx.security:security-crypto`
 * porque esa biblioteca está descontinuada y arrastra Tink entero para hacer
 * exactamente estas cuarenta líneas.
 */
@Serializable
data class SesionLocal(
    val email: String,
    val token: String,
    val rol: String,
    /** Milisegundos epoch en que el token deja de valer contra el backend. */
    @SerialName("expira_at") val expiraAt: Long,
    /** Milisegundos epoch del login online que originó esta sesión. */
    @SerialName("guardada_at") val guardadaAt: Long,
) {
    /**
     * Un token caducado no permite hablar con el backend, pero **sí** permite
     * entrar en modo sin conexión.
     *
     * Es deliberado: el modo sin conexión no consulta nada al servidor, así
     * que exigir un token vivo solo conseguiría dejar fuera del mapa y de las
     * guías a quien lleva tres días sin cobertura — que es exactamente la
     * persona para la que se hizo esto. Lo que no hace es fingir que la sesión
     * está fresca: [caducada] es pública y la pantalla lo dice.
     */
    fun caducada(ahora: Long = System.currentTimeMillis()): Boolean = ahora >= expiraAt
}

/** Lo que cifra y descifra. Se abstrae para poder probar el resto sin Keystore. */
interface Cofre {
    fun cifrar(claro: String): String
    fun descifrar(cifrado: String): String?
}

/**
 * Cofre real: AES/GCM de 256 bits con la clave dentro del Android Keystore.
 *
 * El vector de inicialización se genera nuevo en cada cifrado y viaja delante
 * del criptograma. Reutilizarlo con GCM rompe el cifrado entero, así que no se
 * fija ni se guarda aparte: se deja que el proveedor lo genere y se transporta.
 */
class CofreKeystore(private val alias: String = ALIAS_SESION) : Cofre {

    override fun cifrar(claro: String): String {
        val cipher = Cipher.getInstance(TRANSFORMACION)
        cipher.init(Cipher.ENCRYPT_MODE, claveOCrear())
        val criptograma = cipher.doFinal(claro.toByteArray(Charsets.UTF_8))
        val salida = cipher.iv + criptograma
        return Base64.encodeToString(salida, Base64.NO_WRAP)
    }

    /**
     * Devuelve null en vez de propagar si el descifrado falla.
     *
     * Falla de verdad en un caso real y previsible: el usuario quita y vuelve
     * a poner la huella o el PIN, y Android invalida las claves del Keystore.
     * Lo correcto entonces es tratar la sesión como inexistente y pedir login,
     * no reventar en el arranque de una app de emergencias.
     */
    override fun descifrar(cifrado: String): String? = runCatching {
        val bytes = Base64.decode(cifrado, Base64.NO_WRAP)
        if (bytes.size <= IV_BYTES) return null
        val cipher = Cipher.getInstance(TRANSFORMACION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            claveOCrear(),
            GCMParameterSpec(TAG_BITS, bytes, 0, IV_BYTES),
        )
        String(cipher.doFinal(bytes, IV_BYTES, bytes.size - IV_BYTES), Charsets.UTF_8)
    }.getOrNull()

    private fun claveOCrear(): SecretKey {
        val ks = KeyStore.getInstance(PROVEEDOR).apply { load(null) }
        (ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }

        val generador = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, PROVEEDOR)
        generador.init(
            KeyGenParameterSpec.Builder(
                alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                // Sin exigir desbloqueo: la sesión se lee al arrancar la app,
                // y pedir huella para ver un mapa de evacuación es poner una
                // puerta en mitad de la salida de emergencia.
                .setUserAuthenticationRequired(false)
                .build()
        )
        return generador.generateKey()
    }

    private companion object {
        const val PROVEEDOR = "AndroidKeyStore"
        const val TRANSFORMACION = "AES/GCM/NoPadding"
        const val ALIAS_SESION = "senti_sesion_v1"
        const val IV_BYTES = 12
        const val TAG_BITS = 128
    }
}

/**
 * Guarda y recupera la sesión cifrada.
 *
 * Se apoya en `SharedPreferences` y no en DataStore por una razón concreta:
 * esto se lee **antes** de pintar nada, en el arranque, para decidir si se
 * enseña el login o el modo sin conexión. `SharedPreferences` tiene lectura
 * síncrona; con DataStore habría que suspender y la primera pantalla
 * parpadearía entre las dos opciones.
 */
class SesionSegura(
    context: Context,
    private val cofre: Cofre = CofreKeystore(),
) {
    private val prefs = context.getSharedPreferences(ARCHIVO, Context.MODE_PRIVATE)

    fun guardar(sesion: SesionLocal) {
        prefs.edit().putString(CLAVE, cofre.cifrar(sesion.aJson())).apply()
    }

    fun leer(): SesionLocal? {
        val cifrado = prefs.getString(CLAVE, null) ?: return null
        val claro = cofre.descifrar(cifrado) ?: return null
        return sesionDesdeJson(claro)
    }

    /** Cierre de sesión explícito. Borra la sesión, no el paquete descargado. */
    fun borrar() {
        prefs.edit().remove(CLAVE).apply()
    }

    private companion object {
        const val ARCHIVO = "senti_sesion"
        const val CLAVE = "sesion_cifrada"
    }
}

private val JSON_SESION = Json { ignoreUnknownKeys = true; encodeDefaults = true }

/**
 * Texto exacto que se cifra y se guarda.
 *
 * Es una función con nombre y no una llamada suelta dentro de [SesionSegura]
 * para que la prueba pueda mirar **lo mismo** que acaba en el disco. Comprobar
 * que ahí no aparece ninguna contraseña sobre una serialización distinta no
 * comprobaría nada.
 */
fun SesionLocal.aJson(): String = JSON_SESION.encodeToString(SesionLocal.serializer(), this)

fun sesionDesdeJson(claro: String): SesionLocal? =
    runCatching { JSON_SESION.decodeFromString<SesionLocal>(claro) }.getOrNull()
