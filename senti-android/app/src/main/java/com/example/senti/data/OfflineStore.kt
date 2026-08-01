package com.example.senti.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.Json

/**
 * Almacén sin conexión (§26).
 *
 * Lo que se guarda: última alerta con su fecha, plan familiar, checklist,
 * teléfonos por región, instrucción de falta de señal y última ruta.
 *
 * Lo que NO se guarda, y por qué importa: el token de sesión no se conserva
 * junto al paquete. Un teléfono perdido en una emergencia sigue siendo un
 * teléfono perdido, y el §13.2 obliga a minimizar la exposición de los datos
 * del hogar.
 *
 * La regla que gobierna el módulo es la del §26: "muestra siempre la fecha de
 * última sincronización" y "no presenta una alerta antigua como vigente". Por
 * eso `sincronizadoAt` viaja dentro del paquete y no se recalcula al leerlo.
 */
private val Context.dataStore by preferencesDataStore(name = "senti_offline")

class OfflineStore(private val context: Context) {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private val clavePaquete = stringPreferencesKey("paquete_offline")
    private val claveHilo = stringPreferencesKey("hilo_actual")
    private val claveHiloUltimo = stringPreferencesKey("hilo_ultimo_uso")
    private val claveHistorial = stringPreferencesKey("historial_hilos")

    suspend fun guardar(paquete: PaqueteOffline) {
        val serializado = json.encodeToString(PaqueteOffline.serializer(), paquete)
        context.dataStore.edit { it[clavePaquete] = serializado }
    }

    suspend fun leer(): PaqueteOffline? {
        val crudo = context.dataStore.data.first()[clavePaquete] ?: return null
        return runCatching { json.decodeFromString<PaqueteOffline>(crudo) }.getOrNull()
    }

    // ── Hilo de conversación ────────────────────────────────────────────
    //
    // El identificador de conversación vivía solo en memoria, así que cerrar
    // la app abría un hilo nuevo y el backend perdía el contexto de lo ya
    // hablado. Persistirlo es lo que hace que "seguir la conversación"
    // signifique algo.

    /** Minutos de inactividad tras los cuales el hilo se archiva. */
    private val inactividadMs = 10 * 60 * 1000L

    /**
     * Devuelve el hilo vigente, o null si caducó por inactividad.
     *
     * Al caducar, el hilo anterior se guarda en el historial en vez de
     * perderse: alguien que preguntó por una ruta hace media hora puede querer
     * releerla, y en una emergencia eso importa más que empezar limpio.
     */
    suspend fun hiloVigente(): String? {
        val prefs = context.dataStore.data.first()
        val id = prefs[claveHilo] ?: return null
        val ultimo = prefs[claveHiloUltimo]?.toLongOrNull() ?: 0L
        if (System.currentTimeMillis() - ultimo > inactividadMs) {
            archivar(id)
            return null
        }
        return id
    }

    /** Marca actividad en el hilo. Reinicia la cuenta de los 10 minutos. */
    suspend fun tocarHilo(id: String) {
        context.dataStore.edit {
            it[claveHilo] = id
            it[claveHiloUltimo] = System.currentTimeMillis().toString()
        }
    }

    private suspend fun archivar(id: String) {
        context.dataStore.edit { prefs ->
            val previos = prefs[claveHistorial]
                ?.split(",")
                ?.filter { it.isNotBlank() && it != id }
                ?: emptyList()
            // Se conservan los diez últimos: el historial es para releer algo
            // reciente, no un archivo permanente. El §13.5 limita la retención
            // en el servidor; en el dispositivo se guarda aún menos.
            prefs[claveHistorial] = (listOf(id) + previos).take(10).joinToString(",")
            prefs.remove(claveHilo)
            prefs.remove(claveHiloUltimo)
        }
    }

    /** Hilos archivados, del más reciente al más antiguo. */
    suspend fun historial(): List<String> =
        context.dataStore.data.first()[claveHistorial]
            ?.split(",")
            ?.filter { it.isNotBlank() }
            ?: emptyList()

    /**
     * Al cerrar sesión. El hilo y el paquete son de la cuenta que se fue, no
     * del dispositivo: sin esto, entrar con otra cuenta en el mismo teléfono
     * reanudaría el hilo de la persona anterior y le mostraría su plan
     * familiar como si fuera propio.
     */
    suspend fun borrarSesion() {
        context.dataStore.edit {
            it.remove(clavePaquete)
            it.remove(claveHilo)
            it.remove(claveHiloUltimo)
            it.remove(claveHistorial)
        }
    }
}

/**
 * §7.5 y §29: texto que existe aunque no haya nada más.
 *
 * Está compilado en la app, no descargado: es la única respuesta que tiene que
 * seguir funcionando cuando no hay red, no hay paquete descargado y no hay
 * nada que consultar. Duplica lo que dice el backend a propósito — es una
 * duplicación que se paga una vez y salva el caso peor.
 */
object TextosFijos {

    const val SIN_SENAL =
        "Si no tienes señal: sal a un espacio abierto con vista al cielo, activa " +
            "roaming y VoLTE, y espera. Si tu equipo y plan lo permiten, el celular " +
            "puede conectarse por satélite y aparecerá el nombre del operador con un " +
            "ícono de satélite. Entonces envía tu mensaje por WhatsApp: texto corto " +
            "primero, foto después."

    const val SIN_RUTA =
        "No pude verificar una ruta transitable. No intentes cruzar el bloqueo. " +
            "Aléjate del borde de la vía y comunícate con Policía de Carreteras 110, " +
            "Aló SUTRAN 0800-12345 o Defensa Civil 115."

    const val SIN_CONEXION =
        "Modo sin conexión. Esta información no se ha actualizado desde la fecha indicada."

    /** §24.3. Tabla nacional; el backend la afina por región cuando hay red. */
    val TELEFONOS = listOf(
        Telefono("Emergencia en carretera", "110", "Policía de Carreteras"),
        Telefono("Bloqueo, vía inundada, socorro vial", "0800-12345", "Aló SUTRAN"),
        Telefono("Defensa Civil", "115", "INDECI"),
        Telefono("Policía", "105", "PNP"),
        Telefono("Bomberos, rescate, materiales peligrosos", "116", "Bomberos"),
        Telefono("Emergencia médica", "106", "SAMU"),
        Telefono("Asegurados EsSalud", "117", "EsSalud"),
    )
}
