package com.example.senti.data

/**
 * Arma el paquete de la zona con lo que haya en la red (§26, §11.3).
 *
 * **Ninguna fuente que falle borra lo que ya había.** El sincronizador
 * construye un paquete nuevo entero en memoria y se lo entrega al almacén, que
 * solo sustituye el anterior cuando el nuevo está completo y validado. Si la
 * red se corta a la mitad, el paquete viejo sigue en el disco tal cual.
 *
 * **Lo que no se pudo descargar se anota, no se omite.** Es la regla del §11.3
 * aplicada al modo sin conexión: un mapa sin bloqueos oficiales porque la
 * consulta falló se ve exactamente igual que un mapa sin bloqueos porque no
 * los hay. La única diferencia posible es que alguien lo escriba, y eso es
 * [ContenidoZona.fuentesFallidas].
 */
class SincronizadorOffline(private val almacen: AlmacenZona) {

    /**
     * Descarga la zona de 10 km² alrededor del punto y la guarda.
     *
     * `rutas` son las que la app ya tiene calculadas: no se piden al servidor
     * porque calcular una ruta exige un destino, y aquí no hay ninguno que
     * pedir. Lo que se conserva es lo que el usuario ya vio.
     */
    suspend fun sincronizar(
        lat: Double,
        lon: Double,
        rutas: List<RutaGuardada> = emptyList(),
        ahora: Long = System.currentTimeMillis(),
    ): ResultadoSync {
        val limites = limitesAlrededor(lat, lon, PaqueteZona.MEDIO_LADO_M)
        val fallidas = mutableListOf<String>()

        // El paquete base es lo único obligatorio: trae los teléfonos por
        // región y la última alerta. Sin él no hay sincronización que valga, y
        // fallar aquí significa casi siempre que no hay red — el caso en que
        // conservar el paquete anterior es justo lo correcto.
        val base = runCatching { Api.paqueteOffline() }.getOrElse {
            return ResultadoSync.Error(
                "No se pudo contactar con SENTI. Se conserva el paquete anterior."
            )
        }

        // Los reportes ciudadanos NO entran en el paquete, a propósito.
        //
        // Sin conexión no se pueden refrescar, ni validar, ni retirar cuando
        // dejan de ser ciertos. Un reporte pendiente de hace tres días pintado
        // sobre el mapa no informa: o asusta con algo que ya pasó, o —peor—
        // tranquiliza al no aparecer donde sí hay peligro. Su valor entero
        // depende de estar al día (§21.2), y eso es justo lo que aquí no se
        // puede garantizar.
        //
        // Lo que sí se conserva son los conflictos con respaldo oficial: un
        // cierre municipal sigue siendo un cierre mañana, y esa es la
        // diferencia que lo hace utilizable sin red.
        val eventos = runCatching { Api.listarEventos() }.getOrElse {
            fallidas += "bloqueos oficiales y conflictos viales"
            null
        }

        val recursos = runCatching { RecursosOsm.enZona(limites) }.getOrElse {
            fallidas += "hospitales, bomberos y refugios"
            emptyList()
        }

        val conflictos = eventos?.events.orEmpty().mapNotNull { e ->
            val eLat = e.lat ?: return@mapNotNull null
            val eLon = e.lon ?: return@mapNotNull null
            if (!limites.contiene(eLat, eLon)) return@mapNotNull null
            // Solo lo respaldado por una fuente oficial. Sin ese respaldo un
            // evento es actividad reportada, y vale lo mismo que un reporte
            // suelto: nada que se pueda sostener sin poder actualizarlo.
            if (e.fuentesOficiales <= 0) return@mapNotNull null
            ConflictoOffline(
                id = e.id,
                tipo = e.type,
                titulo = e.title,
                lat = eLat,
                lon = eLon,
                oficial = true,
                confianza = e.estado.lowercase(),
                reportadoAt = e.ultimoReporte,
            )
        }

        val contenido = ContenidoZona(
            rutas = rutas,
            conflictos = conflictos,
            recursos = recursos.sortedBy { distanciaAproxM(lat, lon, it.lat, it.lon) },
            telefonos = base.telefonos.ifEmpty { TextosFijos.TELEFONOS },
            ultimaAlerta = base.ultimaAlerta,
            instruccionSinSenal = base.instruccionSinSenal.ifBlank { TextosFijos.SIN_SENAL },
            fuentesFallidas = fallidas,
        )

        val paquete = construirPaquete(lat, lon, contenido, ahora)
        almacen.guardar(paquete)?.let { return ResultadoSync.Error(it) }
        return ResultadoSync.Ok(paquete)
    }
}

sealed interface ResultadoSync {
    data class Ok(val paquete: PaqueteZona) : ResultadoSync
    data class Error(val motivo: String) : ResultadoSync
}
