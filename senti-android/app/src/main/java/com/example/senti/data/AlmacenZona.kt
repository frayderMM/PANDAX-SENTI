package com.example.senti.data

import java.io.File

/**
 * Guarda el paquete de zona en el disco del teléfono (§26).
 *
 * **La regla que manda: una actualización que falla no puede dejarte peor que
 * antes.** Alguien con el paquete de su barrio descargado sale de viaje, la
 * sincronización se corta a medias y vuelve a casa sin mapa. Por eso se escribe
 * en un archivo aparte y solo se renombra al definitivo cuando el paquete
 * nuevo ya está completo y validado. Renombrar dentro del mismo sistema de
 * archivos es atómico: o está el viejo o está el nuevo, nunca medio archivo.
 *
 * Se usa un archivo y no DataStore porque el paquete puede pesar cientos de
 * kilobytes. DataStore serializa todas las preferencias en cada escritura y
 * está pensado para valores pequeños; meter aquí el paquete entero reescribiría
 * también el hilo de conversación en cada sincronización.
 */
class AlmacenZona(private val directorio: File) {

    private val definitivo: File get() = File(directorio, NOMBRE)
    private val temporal: File get() = File(directorio, "$NOMBRE.tmp")

    /**
     * Escribe el paquete de forma atómica.
     *
     * Devuelve el motivo del rechazo, o null si se guardó. Un paquete inválido
     * ni siquiera se escribe: si el servidor devolvió algo incoherente, lo peor
     * que se puede hacer es sustituir por eso el paquete bueno que ya había.
     */
    fun guardar(paquete: PaqueteZona): String? {
        paquete.motivoInvalidez()?.let { return it }

        return runCatching {
            directorio.mkdirs()
            // El temporal se escribe entero y se vuelca a disco ANTES de
            // renombrar. Sin el `fd.sync()` el renombrado puede llegar al disco
            // antes que el contenido, y un corte de luz en ese hueco deja un
            // archivo con el nombre bueno y basura dentro.
            temporal.outputStream().use { salida ->
                salida.write(paqueteAJson(paquete).toByteArray(Charsets.UTF_8))
                salida.flush()
                salida.fd.sync()
            }
            if (!temporal.renameTo(definitivo)) {
                // `renameTo` falla si el destino existe en algunos sistemas de
                // archivos. Se borra y se reintenta; el temporal sigue intacto,
                // así que en el peor caso se pierde el nuevo, no el viejo.
                definitivo.delete()
                if (!temporal.renameTo(definitivo)) error("no se pudo renombrar el paquete")
            }
            null
        }.getOrElse { exc ->
            temporal.delete()
            "No se pudo guardar el paquete: ${exc.message ?: "error de escritura"}"
        }
    }

    /**
     * Lee el paquete guardado.
     *
     * Un paquete corrupto se trata como ausente y se borra: dejarlo ahí haría
     * que cada arranque volviera a intentar leerlo y volviera a fallar. Lo que
     * NO se hace es intentar repararlo o usar los campos que sí se entienden —
     * un mapa con la mitad de los bloqueos es peor que un mapa vacío, porque
     * el vacío se ve y la mitad no.
     */
    fun leer(): LecturaZona {
        val archivo = definitivo
        if (!archivo.exists()) return LecturaZona.Vacio

        val crudo = runCatching { archivo.readText(Charsets.UTF_8) }.getOrNull()
            ?: return LecturaZona.Corrupto("No se pudo leer el paquete guardado.")

        val paquete = paqueteDesdeJson(crudo)
            ?: run {
                archivo.delete()
                return LecturaZona.Corrupto("El paquete guardado no se pudo interpretar.")
            }

        paquete.motivoInvalidez()?.let {
            archivo.delete()
            return LecturaZona.Corrupto(it)
        }
        return LecturaZona.Ok(paquete)
    }

    /** Solo para el cierre de sesión explícito. La sincronización nunca borra. */
    fun borrar() {
        definitivo.delete()
        temporal.delete()
    }

    private companion object {
        const val NOMBRE = "paquete_zona.json"
    }
}

/**
 * Resultado de leer el disco.
 *
 * Son tres casos y no dos porque llevan a pantallas distintas: sin paquete se
 * ofrece descargar, con paquete corrupto se avisa de que hubo un problema y se
 * ofrece descargar, y con paquete bueno se pinta el mapa.
 */
sealed interface LecturaZona {
    data object Vacio : LecturaZona
    data class Corrupto(val motivo: String) : LecturaZona
    data class Ok(val paquete: PaqueteZona) : LecturaZona
}
