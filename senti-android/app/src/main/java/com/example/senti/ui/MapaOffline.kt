package com.example.senti.ui

import android.graphics.PointF
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.senti.data.EstiloOffline
import com.example.senti.data.PaqueteZona
import com.example.senti.data.Punto
import com.example.senti.data.geoJsonConflictos
import com.example.senti.data.geoJsonRecursos
import com.example.senti.data.geoJsonRutas
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.sources.GeoJsonSource

/**
 * Lo que se abre al tocar un punto del mapa.
 *
 * Tocar el mapa **no crea nada**. Abre esta ficha y ya. Es la misma regla que
 * el mapa de ruta ya cumple con los atascos marcados: marcar afecta a lo que
 * estás mirando, nunca publica un reporte. Aquí es todavía más estricto porque
 * sin conexión no habría a dónde publicarlo.
 */
data class FichaMapa(
    val titulo: String,
    val lineas: List<String>,
)

private const val ID_UBICACION = "senti-ubicacion"
private const val ID_UBICACION_FUENTE = "senti-ubicacion-fuente"

// El color nunca va solo: la ficha que se abre repite en palabras lo que el
// color dice (§31.2). Aquí solo se decide cómo se ve de un vistazo.
private const val COLOR_RUTA = "#0B63C5"
private const val COLOR_OFICIAL = "#E53935"
private const val COLOR_SALUD = "#26A69A"
private const val COLOR_BOMBEROS = "#EF5350"
private const val COLOR_REFUGIO = "#7E57C2"
private const val COLOR_COMISARIA = "#5C6BC0"
private const val COLOR_UBICACION = "#1B76D2"

/**
 * Mapa sin conexión.
 *
 * Dibuja el pack de teselas local y encima lo que traiga el paquete. Si no hay
 * pack, no dibuja un mapa falso: deja el fondo y quien lo llama enseña el aviso.
 */
@Composable
fun LienzoMapaOffline(
    packs: EstiloOffline.Packs?,
    paquete: PaqueteZona?,
    miUbicacion: Punto?,
    solicitudCentrado: Int,
    onFicha: (FichaMapa) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val propietarioCiclo = LocalLifecycleOwner.current

    val vista = remember {
        // Tiene que llamarse antes de construir el MapView. No descarga nada:
        // sin clave y sin servidor conocido, porque aquí todo es local.
        MapLibre.getInstance(context)
        MapView(context).apply { onCreate(null) }
    }

    val mapa = remember { arrayOfNulls<MapLibreMap>(1) }

    DisposableEffect(propietarioCiclo) {
        val observador = LifecycleEventObserver { _, evento ->
            when (evento) {
                Lifecycle.Event.ON_START -> vista.onStart()
                Lifecycle.Event.ON_RESUME -> vista.onResume()
                Lifecycle.Event.ON_PAUSE -> vista.onPause()
                Lifecycle.Event.ON_STOP -> vista.onStop()
                else -> Unit
            }
        }
        propietarioCiclo.lifecycle.addObserver(observador)
        onDispose {
            propietarioCiclo.lifecycle.removeObserver(observador)
            vista.onDestroy()
        }
    }

    AndroidView(
        modifier = modifier,
        factory = { vista },
        update = { v ->
            v.getMapAsync { m ->
                mapa[0] = m
                if (m.style == null && packs != null) {
                    val json = EstiloOffline.estiloJson(
                        packs.peru.absolutePath,
                        packs.detalle?.absolutePath,
                    )
                    m.setStyle(Style.Builder().fromJson(json)) {
                        prepararCapas(it)
                        pintar(it, paquete, miUbicacion)
                        // Sin paquete no se sabe dónde está el usuario todavía;
                        // se encuadra el pack para que no aparezca el océano.
                        val centro = miUbicacion
                            ?: paquete?.let { p -> Punto(p.centroLat, p.centroLon) }
                        centro?.let { c ->
                            m.animateCamera(
                                CameraUpdateFactory.newLatLngZoom(LatLng(c.lat, c.lon), 15.0)
                            )
                        }
                    }
                    m.addOnMapClickListener { punto ->
                        val pantalla: PointF = m.projection.toScreenLocation(punto)
                        val ficha = consultarFicha(m, pantalla)
                        if (ficha != null) onFicha(ficha)
                        // Se devuelve false siempre: consumir el toque
                        // desactivaría el desplazamiento del mapa, y aquí mover
                        // el mapa importa más que abrir una ficha.
                        false
                    }
                }
            }
        },
    )

    // Repinta cuando cambia el paquete o la posición, sin recrear el estilo.
    LaunchedEffect(paquete, miUbicacion) {
        mapa[0]?.style?.let { pintar(it, paquete, miUbicacion) }
    }

    LaunchedEffect(solicitudCentrado) {
        if (solicitudCentrado == 0) return@LaunchedEffect
        val destino = miUbicacion ?: return@LaunchedEffect
        mapa[0]?.animateCamera(
            CameraUpdateFactory.newLatLngZoom(LatLng(destino.lat, destino.lon), 16.0)
        )
    }
}

/** Crea fuentes vacías y capas una sola vez, al cargar el estilo. */
private fun prepararCapas(estilo: Style) {
    val vacio = """{"type":"FeatureCollection","features":[]}"""

    estilo.addSource(GeoJsonSource(EstiloOffline.Capas.RUTA_FUENTE, vacio))
    estilo.addSource(GeoJsonSource(EstiloOffline.Capas.CONFLICTOS_FUENTE, vacio))
    estilo.addSource(GeoJsonSource(EstiloOffline.Capas.RECURSOS_FUENTE, vacio))
    estilo.addSource(GeoJsonSource(ID_UBICACION_FUENTE, vacio))

    estilo.addLayer(
        LineLayer(EstiloOffline.Capas.RUTA, EstiloOffline.Capas.RUTA_FUENTE).withProperties(
            PropertyFactory.lineColor(COLOR_RUTA),
            PropertyFactory.lineWidth(5.0f),
            PropertyFactory.lineCap("round"),
            PropertyFactory.lineJoin("round"),
        )
    )

    // Recursos: una capa por tipo. Se podría hacer con una expresión `match` y
    // una sola capa, pero cuatro filtros explícitos se leen de un vistazo y no
    // dependen del orden de los argumentos de una expresión.
    listOf(
        "centro_salud" to COLOR_SALUD,
        "bomberos" to COLOR_BOMBEROS,
        "refugio" to COLOR_REFUGIO,
        "comisaria" to COLOR_COMISARIA,
    ).forEach { (tipo, color) ->
        estilo.addLayer(
            CircleLayer("${EstiloOffline.Capas.RECURSOS}-$tipo", EstiloOffline.Capas.RECURSOS_FUENTE)
                .withProperties(
                    PropertyFactory.circleColor(color),
                    PropertyFactory.circleRadius(6.0f),
                    PropertyFactory.circleStrokeColor("#FFFFFF"),
                    PropertyFactory.circleStrokeWidth(1.5f),
                )
                .withFilter(Expression.eq(Expression.get("tipo"), Expression.literal(tipo)))
        )
    }

    // Los conflictos van ENCIMA de los recursos: si un cierre cae sobre un
    // hospital, lo que hay que ver es el cierre.
    //
    // Una sola capa, porque sin conexión solo se guarda lo oficial. Los
    // reportes ciudadanos no entran en el paquete: su valor depende de estar
    // al día y aquí no se pueden refrescar ni retirar (§21.2).
    estilo.addLayer(
        CircleLayer(EstiloOffline.Capas.CONFLICTOS, EstiloOffline.Capas.CONFLICTOS_FUENTE)
            .withProperties(
                PropertyFactory.circleColor(COLOR_OFICIAL),
                PropertyFactory.circleRadius(9.0f),
                PropertyFactory.circleStrokeColor("#FFFFFF"),
                PropertyFactory.circleStrokeWidth(2.0f),
            )
    )

    estilo.addLayer(
        CircleLayer(ID_UBICACION, ID_UBICACION_FUENTE).withProperties(
            PropertyFactory.circleColor(COLOR_UBICACION),
            PropertyFactory.circleRadius(7.0f),
            PropertyFactory.circleStrokeColor("#FFFFFF"),
            PropertyFactory.circleStrokeWidth(3.0f),
        )
    )
}

private fun pintar(estilo: Style, paquete: PaqueteZona?, miUbicacion: Punto?) {
    val contenido = paquete?.contenido

    (estilo.getSource(EstiloOffline.Capas.RUTA_FUENTE) as? GeoJsonSource)
        ?.setGeoJson(geoJsonRutas(contenido?.rutas.orEmpty()))
    (estilo.getSource(EstiloOffline.Capas.CONFLICTOS_FUENTE) as? GeoJsonSource)
        ?.setGeoJson(geoJsonConflictos(contenido?.conflictos.orEmpty()))
    (estilo.getSource(EstiloOffline.Capas.RECURSOS_FUENTE) as? GeoJsonSource)
        ?.setGeoJson(geoJsonRecursos(contenido?.recursos.orEmpty()))

    val ubicacion = miUbicacion?.let {
        """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},""" +
            """"geometry":{"type":"Point","coordinates":[${it.lon},${it.lat}]}}]}"""
    } ?: """{"type":"FeatureCollection","features":[]}"""
    (estilo.getSource(ID_UBICACION_FUENTE) as? GeoJsonSource)?.setGeoJson(ubicacion)
}

/**
 * Qué hay bajo el dedo.
 *
 * Se consultan primero los conflictos y luego los recursos, en ese orden,
 * porque si los dos caen en el mismo sitio lo que hay que leer es el peligro.
 */
private fun consultarFicha(mapa: MapLibreMap, punto: PointF): FichaMapa? {
    mapa.queryRenderedFeatures(punto, EstiloOffline.Capas.CONFLICTOS).firstOrNull()?.let { f ->
        return FichaMapa(
            titulo = f.getStringProperty("titulo") ?: "Conflicto vial",
            lineas = listOfNotNull(
                f.getStringProperty("tipo")?.replace("_", " "),
                "Respaldado por una fuente oficial o municipal. No intentes cruzarlo.",
                f.getStringProperty("confianza")?.let { "Confianza: $it" },
                "Dato descargado. Puede haber cambiado.",
            ),
        )
    }

    val capasRecurso = listOf("centro_salud", "bomberos", "refugio", "comisaria")
        .map { "${EstiloOffline.Capas.RECURSOS}-$it" }
        .toTypedArray()
    mapa.queryRenderedFeatures(punto, *capasRecurso).firstOrNull()?.let { f ->
        val referencial = f.getStringProperty("referencial") == "true"
        return FichaMapa(
            titulo = f.getStringProperty("nombre") ?: "Recurso",
            lineas = listOfNotNull(
                f.getStringProperty("tipo")?.replace("_", " "),
                if (referencial) {
                    "Ubicación referencial de OpenStreetMap: acredita que existe " +
                        "y dónde, no que esté abierto ni designado como refugio."
                } else {
                    null
                },
                "Dato descargado. Puede haber cambiado.",
            ),
        )
    }
    return null
}

