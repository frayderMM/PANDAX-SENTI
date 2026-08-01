package com.example.senti.data

import android.content.Context
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Guías de emergencia (§17, §26).
 *
 * **Viajan dentro del APK y no se descargan nunca.** Es la diferencia entre
 * una guía y todo lo demás: el paquete offline puede no haberse sincronizado,
 * puede estar vencido o puede no existir, pero las guías están desde que se
 * instala la app. Alguien que instaló SENTI en el aeropuerto y se quedó sin
 * datos tiene que poder leer qué hacer ante un huaico.
 *
 * Ninguna acción la escribe el modelo (§25). El campo [Guia.origen] dice de
 * dónde sale cada una y la pantalla lo muestra:
 *
 * | origen | significa |
 * |---|---|
 * | `protocolo` | reproduce literal un protocolo versionado del sistema (§17) |
 * | `texto_fijo` | reproduce literal un texto fijo del sistema (§7.5, §24.3) |
 * | `resumen_local` | resume la recomendación pública de la institución citada |
 *
 * Distinguirlos importa: `protocolo` y `texto_fijo` son trazables palabra por
 * palabra contra el backend, `resumen_local` no. Presentar los tres como lo
 * mismo sería atribuir a INDECI una redacción que no es suya.
 */
@Serializable
data class AccionGuia(
    val texto: String,
    val critica: Boolean = false,
)

@Serializable
data class Guia(
    val id: String,
    val titulo: String,
    val institucion: String,
    val fuente: String,
    val version: String,
    val origen: String,
    val orden: Int = 99,
    val resumen: String = "",
    val acciones: List<AccionGuia> = emptyList(),
)

@Serializable
data class PackGuias(
    val version: String,
    @SerialName("compilado_at") val compiladoAt: String,
    @SerialName("vigencia_meses") val vigenciaMeses: Int = 12,
    @SerialName("nota_origen") val notaOrigen: String = "",
    val guias: List<Guia> = emptyList(),
) {
    /**
     * Milisegundos epoch de la fecha de compilación, o null si no se pudo leer.
     *
     * Que devuelva null no es un detalle: [desactualizado] lo trata como
     * "sí, está desactualizado". Una fecha que no se entiende no es una fecha
     * reciente.
     */
    val compiladoMs: Long? get() = fechaIsoAMs(compiladoAt)

    fun desactualizado(ahora: Long = System.currentTimeMillis()): Boolean {
        val base = compiladoMs ?: return true
        val limite = Calendar.getInstance(TimeZone.getTimeZone("UTC")).apply {
            timeInMillis = base
            add(Calendar.MONTH, vigenciaMeses)
        }.timeInMillis
        return ahora >= limite
    }

    /** El aviso que la pantalla enseña encima de la guía, o null si está vigente. */
    fun advertencia(ahora: Long = System.currentTimeMillis()): String? =
        if (desactualizado(ahora)) {
            "Esta guía se compiló el ${formatearFecha(compiladoMs)} y ya superó su " +
                "vigencia de $vigenciaMeses meses. Puede no reflejar la recomendación " +
                "vigente de la institución. Verifícala cuando tengas conexión."
        } else {
            null
        }

    fun porId(id: String): Guia? = guias.firstOrNull { it.id == id }

    val ordenadas: List<Guia> get() = guias.sortedBy { it.orden }
}

object Guias {

    const val ASSET = "guias_emergencia.json"

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    /**
     * Lee el pack del APK.
     *
     * Devuelve null solo si el asset falta o está roto, que en la práctica
     * significa que el APK se ensambló mal. No se intenta arreglar ni sustituir
     * por nada: la pantalla lo dice y quedan los teléfonos fijos de
     * [TextosFijos], que están compilados en el código y no en un asset.
     */
    fun cargar(context: Context): PackGuias? = runCatching {
        val crudo = context.assets.open(ASSET).use { it.readBytes().toString(Charsets.UTF_8) }
        json.decodeFromString<PackGuias>(crudo)
    }.getOrNull()

    /** Parseo aislado para poder probarlo sin `Context`. */
    fun parsear(crudo: String): PackGuias? =
        runCatching { json.decodeFromString<PackGuias>(crudo) }.getOrNull()
}

private const val ISO_DIA = "yyyy-MM-dd"

/** Convierte `2026-08-01` a milisegundos epoch UTC. Null si no encaja. */
fun fechaIsoAMs(iso: String): Long? = runCatching {
    SimpleDateFormat(ISO_DIA, Locale.US)
        .apply { timeZone = TimeZone.getTimeZone("UTC"); isLenient = false }
        .parse(iso.take(10))
        ?.time
}.getOrNull()

/** Fecha legible para la interfaz. Sin hora: aquí solo importa el día. */
fun formatearFecha(ms: Long?): String {
    if (ms == null) return "fecha desconocida"
    return SimpleDateFormat("d MMM yyyy", Locale.forLanguageTag("es-PE"))
        .apply { timeZone = TimeZone.getDefault() }
        .format(java.util.Date(ms))
}

/** Fecha y hora legibles. Se usa para la última sincronización (§26). */
fun formatearFechaHora(ms: Long?): String {
    if (ms == null) return "nunca"
    return SimpleDateFormat("d MMM yyyy, HH:mm", Locale.forLanguageTag("es-PE"))
        .apply { timeZone = TimeZone.getDefault() }
        .format(java.util.Date(ms))
}
