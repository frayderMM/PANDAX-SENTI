package com.example.senti.data

/**
 * Los doce tipos de peligro, con su nombre legible y su color.
 *
 * **Espejo de `HazardType` del backend, y esa es toda su responsabilidad.** Los
 * códigos (`inundacion`, `via_bloqueada`…) son los que viajan por la API; aquí
 * solo se les pone nombre en castellano y un color para el mapa. Ninguna
 * decisión depende de esta tabla: el backend clasifica, la app pinta.
 *
 * **Están los doce, no cinco.** La vigencia de un reporte depende de su tipo
 * (§20.3: un puente afectado dura 7 días y un «otro» solo 12 horas), así que
 * meter un huaico o un incendio bajo «Otro» por no tener botón propio no era
 * una etiqueta imprecisa: le daba al reporte una vigencia mucho más corta de
 * la que le corresponde.
 *
 * El tipo desconocido existe porque un cliente viejo puede recibir un tipo
 * nuevo. La
 * alternativa —descartar lo que no se reconoce— haría desaparecer del mapa un
 * peligro real por no saber cómo llamarlo, que es la peor forma posible de
 * fallar en este sistema. Se muestra con su código crudo y color neutro.
 */
enum class TipoDesastre(
    val codigo: String,
    val etiqueta: String,
    /** ARGB. Se usa tal cual en el marcador y en la ficha. */
    val color: Long,
) {
    INUNDACION("inundacion", "Inundación", 0xFF1E88E5),
    HUAICO("huaico", "Huaico", 0xFF8D6E63),
    DESLIZAMIENTO("deslizamiento", "Deslizamiento", 0xFF6D4C41),
    LLUVIA("lluvia", "Lluvia intensa", 0xFF42A5F5),
    SISMO("sismo", "Sismo", 0xFFAB47BC),
    TSUNAMI("tsunami", "Tsunami", 0xFF00838F),
    INCENDIO("incendio", "Incendio", 0xFFE53935),
    VIA_BLOQUEADA("via_bloqueada", "Vía bloqueada", 0xFFF57C00),
    PUENTE_AFECTADO("puente_afectado", "Puente afectado", 0xFFD84315),
    ACUMULACION_AGUA("acumulacion_agua", "Acumulación de agua", 0xFF26A69A),
    CAIDA_POSTE("caida_poste", "Caída de poste", 0xFF7E57C2),
    OTRO("otro", "Otro", 0xFF607D8B);

    companion object {
        /** Color de lo que no se sabe nombrar. Gris, no rojo: no se supone gravedad. */
        const val COLOR_DESCONOCIDO = 0xFF9E9E9E

        fun desde(codigo: String?): TipoDesastre? =
            entries.firstOrNull { it.codigo == codigo?.trim()?.lowercase() }

        /**
         * Nombre para enseñar, reconocido o no.
         *
         * Un tipo desconocido se muestra con su código legible —guiones bajos
         * convertidos en espacios— en vez de ocultarse o llamarse «Otro»:
         * decir «Alud» aunque la app no sepa qué es informa más que decir
         * «Otro», y mucho más que no decir nada.
         */
        fun etiquetaDe(codigo: String?): String {
            desde(codigo)?.let { return it.etiqueta }
            val crudo = codigo?.trim().orEmpty()
            if (crudo.isEmpty()) return "Sin clasificar"
            return crudo.replace('_', ' ').replaceFirstChar { it.uppercase() }
        }

        fun colorDe(codigo: String?): Long = desde(codigo)?.color ?: COLOR_DESCONOCIDO
    }
}

/**
 * Un punto del mapa, venga de donde venga.
 *
 * Los eventos agregados y los reportes ciudadanos se pintan en el mismo mapa y
 * se tocan igual, pero **no significan lo mismo** y la ficha tiene que poder
 * decirlo. Por eso [oficial] y [confianza] viajan aquí en vez de perderse al
 * unificar: el §25 prohíbe mezclar reportes ciudadanos con fuentes oficiales.
 */
data class MarcadorMapa(
    val id: String,
    val titulo: String,
    val tipo: String,
    val descripcion: String?,
    val lat: Double,
    val lon: Double,
    val oficial: Boolean,
    val confianza: String?,
    val estado: String?,
    val personas: Int?,
    val fuentesOficiales: Int?,
    val fecha: String?,
    val distrito: String?,
) {
    val etiquetaTipo: String get() = TipoDesastre.etiquetaDe(tipo)
    val color: Long get() = TipoDesastre.colorDe(tipo)
}

/** Convierte un reporte ciudadano en marcador. Null si no tiene coordenadas. */
fun ReporteResumen.aMarcador(): MarcadorMapa? {
    val la = lat ?: return null
    val lo = lon ?: return null
    return MarcadorMapa(
        id = id,
        // El título es el tipo de desastre, que es lo que alguien busca de un
        // vistazo. La descripción, que la escribió una persona con prisa, va
        // debajo y puede faltar.
        titulo = TipoDesastre.etiquetaDe(tipo),
        tipo = tipo,
        descripcion = descripcion?.takeIf { it.isNotBlank() },
        lat = la,
        lon = lo,
        oficial = confirmado,
        confianza = confianza,
        estado = estado,
        personas = null,
        fuentesOficiales = null,
        fecha = reportadoAt,
        distrito = distrito,
    )
}

/** Convierte un evento agregado en marcador. Null si no tiene coordenadas. */
fun EventoMapa.aMarcador(): MarcadorMapa? {
    val la = lat ?: return null
    val lo = lon ?: return null
    return MarcadorMapa(
        id = id,
        titulo = title.ifBlank { TipoDesastre.etiquetaDe(type) },
        tipo = type,
        descripcion = summary?.takeIf { it.isNotBlank() },
        lat = la,
        lon = lo,
        oficial = fuentesOficiales > 0,
        confianza = null,
        estado = estado,
        personas = personas,
        fuentesOficiales = fuentesOficiales,
        fecha = ultimoReporte,
        distrito = null,
    )
}

/**
 * Tipos presentes en una lista, ordenados por cuántos hay.
 *
 * El filtro solo ofrece lo que existe en el mapa. Un chip de «Tsunami» que al
 * pulsarlo vacía la pantalla no es un filtro: es una pregunta sin respuesta.
 */
fun List<MarcadorMapa>.tiposPresentes(): List<Pair<String, Int>> =
    groupingBy { it.tipo }.eachCount()
        .toList()
        .sortedWith(compareByDescending<Pair<String, Int>> { it.second }.thenBy { it.first })
