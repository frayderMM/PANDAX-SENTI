package com.example.senti.ui

import android.annotation.SuppressLint
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.Circle
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapProperties
import com.google.maps.android.compose.MapType
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.Polyline
import com.google.maps.android.compose.rememberCameraPositionState
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.senti.data.BloqueoMapa
import com.example.senti.data.Punto
import com.example.senti.data.RutaCalculada
import com.example.senti.data.EventoMapa
import com.example.senti.data.Api
import com.example.senti.ui.theme.Radios
import com.example.senti.ui.theme.SentiCeleste
import com.example.senti.ui.theme.SentiPrimary
import kotlin.math.cos
import kotlin.math.atan2
import kotlin.math.sin
import kotlin.math.sqrt
import kotlinx.coroutines.launch

/** Qué se marca al tocar el mapa. */
private enum class ModoMapa { NINGUNO, ATASCO, DESTINO }

private val ROJO = Color(0xFFD64545)
private val AMBAR = Color(0xFFE8A33D)
private val VERDE = Color(0xFF2E9E5B)

private fun esConflictoVial(tipo: String, titulo: String): Boolean {
    val texto = "$tipo $titulo".lowercase()
    return listOf(
        "via_bloqueada", "bloqueo", "derrumbe", "deslizamiento", "huaico",
        "puente", "inundacion", "inundación", "agua", "poste", "caida_poste",
        "caída de postes", "obstacul",
    ).any(texto::contains)
}

private fun distanciaMetros(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val radioTierra = 6_371_000.0
    val dLat = Math.toRadians(lat2 - lat1)
    val dLon = Math.toRadians(lon2 - lon1)
    val a = sin(dLat / 2) * sin(dLat / 2) +
        cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) *
        sin(dLon / 2) * sin(dLon / 2)
    return radioTierra * 2 * atan2(sqrt(a), sqrt(1 - a))
}

/**
 * Mapa de la ruta de salida.
 *
 * Enseña cuatro cosas y ninguna más: dónde está la persona, a dónde va, por
 * dónde se va y qué está cortado. El §7.3 dice que el mapa es una mejora y
 * nunca el portador de la instrucción — los pasos escritos siguen siendo la
 * respuesta completa—, así que esta pantalla se puede cerrar sin perder nada.
 *
 * @param onMarcarBloqueo se llama con el punto que el usuario toca cuando está
 *   en modo marcado. Marcar no cierra ninguna vía: manda un reporte sin
 *   confirmar, que el §21.2 deja penalizar pero no excluir.
 */
@SuppressLint("MissingPermission")
@Composable
fun MapaRuta(
    ruta: RutaCalculada,
    miUbicacion: Punto?,
    onCerrar: () -> Unit,
    onMarcarBloqueo: (Punto) -> Unit,
    onRecalcular: (List<Punto>, Punto?) -> Unit,
    recalculando: Boolean,
    modoMarcadoInicial: Boolean = false,
) {
    val contexto = LocalContext.current

    // Qué se marca al tocar el mapa. Son tres estados y no dos booleanos: con
    // dos se puede acabar marcando atasco y destino a la vez, y el toque no
    // sabría a cuál de los dos pertenece.
    var modo by remember(modoMarcadoInicial) {
        mutableStateOf(if (modoMarcadoInicial) ModoMapa.ATASCO else ModoMapa.NINGUNO)
    }
    var destinoElegido by remember { mutableStateOf<Punto?>(null) }
    var misMarcas by remember { mutableStateOf(listOf<Punto>()) }
    val alcance = rememberCoroutineScope()
    var cargando by remember { mutableStateOf(true) }
    var fallo by remember { mutableStateOf<String?>(null) }
    var eventos by remember { mutableStateOf<List<EventoMapa>>(emptyList()) }
    var eventoSeleccionado by remember { mutableStateOf<EventoMapa?>(null) }

    LaunchedEffect(Unit) {
        runCatching { eventos = Api.listarEventos().events }
    }

    val puntosRuta = remember(ruta.geometria) { ruta.puntos }
    // Los eventos que caen sobre la ruta no pueden quedarse como decoración:
    // al pedir un nuevo cálculo se envían como exclusiones puntuales. Así un
    // conflicto visible (derrumbe, vía bloqueada, puente afectado, etc.) se
    // usa en la decisión aunque todavía no haya sido convertido en un cierre
    // oficial en el backend. Los eventos sísmicos, por ejemplo, no son
    // obstáculos viales y se dejan fuera.
    val eventosEnRuta = remember(puntosRuta, eventos) {
        eventos.filter { evento ->
            val lat = evento.lat
            val lon = evento.lon
            lat != null && lon != null && esConflictoVial(evento.type, evento.title) &&
                puntosRuta.any { punto -> distanciaMetros(punto.lat, punto.lon, lat, lon) <= 250.0 }
        }.map { Punto(it.lat!!, it.lon!!) }
    }
    val puntosAevitar = misMarcas + eventosEnRuta
    val origen = remember(ruta, miUbicacion) {
        when {
            ruta.origenLat != null && ruta.origenLon != null ->
                Punto(ruta.origenLat, ruta.origenLon)
            miUbicacion != null -> miUbicacion
            puntosRuta.isNotEmpty() -> puntosRuta.first()
            else -> null
        }
    }

    // Encuadre inicial: que quepan el origen, el destino y la ruta entera.
    //
    // Abrir centrado en la persona obligaría a alejar a mano para ver a dónde
    // lleva la ruta, y eso es justo lo que nadie hace con prisa.
    val encuadre = remember(ruta.geometria, origen) {
        buildList {
            addAll(puntosRuta.map { LatLng(it.lat, it.lon) })
            origen?.let { add(LatLng(it.lat, it.lon)) }
            if (ruta.destinoLat != null && ruta.destinoLon != null) {
                add(LatLng(ruta.destinoLat, ruta.destinoLon))
            }
            addAll(ruta.bloqueos.map { LatLng(it.lat, it.lon) })
        }
    }

    val camara = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(
            encuadre.firstOrNull() ?: LatLng(-12.05, -77.04),
            15f,
        )
    }

    LaunchedEffect(encuadre) {
        if (encuadre.size >= 2) {
            val limites = LatLngBounds.builder().apply { encuadre.forEach(::include) }.build()
            // Margen generoso: el panel de instrucciones tapa la franja de
            // abajo, y una ruta que acaba debajo del panel no se ve.
            runCatching { camara.animate(CameraUpdateFactory.newLatLngBounds(limites, 140), 600) }
        } else if (encuadre.size == 1) {
            camara.animate(CameraUpdateFactory.newLatLngZoom(encuadre.first(), 16f), 600)
        }
        cargando = false
    }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = camara,
            properties = MapProperties(mapType = MapType.NORMAL),
            uiSettings = MapUiSettings(
                // Girar e inclinar desorienta a quien mira el mapa con prisa, y
                // el norte arriba es la referencia que todo el mundo comparte.
                rotationGesturesEnabled = false,
                tiltGesturesEnabled = false,
                mapToolbarEnabled = false,
                zoomControlsEnabled = false,
            ),
            onMapLoaded = { cargando = false },
            onMapClick = { p ->
                val punto = Punto(p.latitude, p.longitude)
                when (modo) {
                    ModoMapa.ATASCO -> {
                        misMarcas = misMarcas + punto
                        onMarcarBloqueo(punto)
                    }
                    // El destino es uno solo: cada toque reemplaza al anterior
                    // en vez de acumular. Marcar dos sitios a los que ir no
                    // significa nada, y corregirse tiene que costar un toque.
                    ModoMapa.DESTINO -> destinoElegido = punto
                    ModoMapa.NINGUNO -> Unit
                }
            },
        ) {
            // Un marcador representa un evento unificado. La cantidad visible
            // en el título es de personas únicas, nunca solicitudes.
            eventos.filter { it.lat != null && it.lon != null }.forEach { evento ->
                Marker(
                    state = MarkerState(LatLng(evento.lat!!, evento.lon!!)),
                    title = "[${evento.personas}] ${evento.title}",
                    snippet = "${evento.personas} personas · ${evento.estado} · Confianza ${evento.confidence.toInt()}%",
                    onClick = { eventoSeleccionado = evento; false },
                )
            }
            // ── Cierres, debajo de todo ──────────────────────────────────
            //
            // El radio va en METROS, no en píxeles: al alejar el mapa el
            // círculo sigue cubriendo la zona que representa. Dibujar un
            // cierre más pequeño de lo que es invita a bordearlo por donde no
            // se puede. Con MapLibre había que construir el polígono a mano.
            ruta.bloqueos.filter { it.vinculante }.forEach { b ->
                Circle(
                    center = LatLng(b.lat, b.lon),
                    radius = b.radioM,
                    fillColor = ROJO.copy(alpha = 0.35f),
                    strokeColor = ROJO,
                    strokeWidth = 2f,
                )
            }
            // Reportes sin confirmar: otro color, porque el §21.2 no deja que
            // una sola voz cierre una vía y el color no puede decir lo
            // contrario de lo que hace el sistema.
            ruta.bloqueos.filterNot { it.vinculante }.forEach { b ->
                Circle(
                    center = LatLng(b.lat, b.lon),
                    radius = b.radioM,
                    fillColor = AMBAR.copy(alpha = 0.30f),
                    strokeColor = AMBAR,
                    strokeWidth = 2f,
                )
            }
            // Lo que marca el usuario se pinta igual que un reporte sin
            // confirmar, que es exactamente lo que es hasta que se valide.
            misMarcas.forEach { m ->
                Circle(
                    center = LatLng(m.lat, m.lon),
                    radius = 45.0,
                    fillColor = AMBAR.copy(alpha = 0.45f),
                    strokeColor = AMBAR,
                    strokeWidth = 2f,
                )
            }

            // ── La ruta, encima de los cierres ───────────────────────────
            //
            // Lo que hay que seguir no puede quedar tapado por lo que hay que
            // evitar. Dos trazos: contorno oscuro y color encima, porque sin
            // borde la línea se pierde sobre una avenida del mismo grosor.
            if (puntosRuta.size >= 2) {
                val linea = puntosRuta.map { LatLng(it.lat, it.lon) }
                Polyline(points = linea, color = Color(0xFF15306B), width = 22f)
                Polyline(points = linea, color = SentiPrimary, width = 12f)
            }

            // ── Origen y destino, encima de todo ─────────────────────────
            origen?.let {
                Marker(
                    state = MarkerState(LatLng(it.lat, it.lon)),
                    title = "Estás aquí",
                )
            }
            // El destino que eligió el usuario gana sobre el que traía la
            // ruta: si lo marcó es porque quiere ir ahí.
            val destino = destinoElegido
                ?: ruta.destinoLat?.let { la -> ruta.destinoLon?.let { lo -> Punto(la, lo) } }
            destino?.let {
                Marker(
                    state = MarkerState(LatLng(it.lat, it.lon)),
                    title = if (destinoElegido != null) "A dónde vas" else "Destino",
                )
            }
        }

        eventoSeleccionado?.let { evento ->
            Surface(
                modifier = Modifier.align(Alignment.TopCenter).padding(16.dp),
                shape = RoundedCornerShape(Radios.tarjetaGrande),
                shadowElevation = 8.dp,
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text(evento.title, style = MaterialTheme.typography.titleMedium)
                    Text("${evento.personas} personas reportaron este evento", style = MaterialTheme.typography.bodyMedium)
                    Text("${evento.reportes} reportes ciudadanos · ${evento.fuentesOficiales} fuentes oficiales", style = MaterialTheme.typography.bodySmall)
                    Text("Estado: ${evento.estado} · Confianza: ${evento.confidence.toInt()}%", style = MaterialTheme.typography.bodySmall)
                    evento.summary?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    TextButton(onClick = { eventoSeleccionado = null }) { Text("Cerrar") }
                }
            }
        }

        if (cargando) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = SentiPrimary)
                    Spacer(Modifier.height(12.dp))
                    Text("Cargando el mapa…", style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        fallo?.let {
            Surface(
                color = ROJO.copy(alpha = 0.95f),
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
                shape = RoundedCornerShape(Radios.boton),
            ) {
                Text(
                    it,
                    color = Color.White,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }

        BarraSuperiorMapa(ruta, onCerrar, Modifier.align(Alignment.TopCenter))

        PanelInferiorMapa(
            ruta = ruta,
            modo = modo,
            marcas = puntosAevitar.size,
            tieneDestino = destinoElegido != null,
            onCambiarModo = { modo = if (modo == it) ModoMapa.NINGUNO else it },
            onCentrar = {
                origen?.let { o ->
                    alcance.launch {
                        camara.animate(
                            CameraUpdateFactory.newLatLngZoom(LatLng(o.lat, o.lon), 16f),
                            600,
                        )
                    }
                }
            },
            onQuitarUltima = { if (misMarcas.isNotEmpty()) misMarcas = misMarcas.dropLast(1) },
            onRecalcular = { onRecalcular(puntosAevitar, destinoElegido) },
            recalculando = recalculando,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@Composable
private fun BarraSuperiorMapa(
    ruta: RutaCalculada,
    onCerrar: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth().statusBarsPadding().padding(12.dp),
        shape = RoundedCornerShape(Radios.tarjeta),
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 6.dp,
    ) {
        Row(
            Modifier.padding(horizontal = 8.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onCerrar) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Volver al chat")
            }
            Column(Modifier.weight(1f)) {
                Text(
                ruta.destino ?: if (ruta.geometria == null) "Marca el atasco" else "Ruta de salida",
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                )
                Text(
                    buildString {
                        ruta.distanciaM?.let {
                            append(if (it >= 1000) "%.1f km".format(it / 1000.0) else "$it m")
                        }
                        ruta.duracionS?.let {
                            if (isNotEmpty()) append(" · ")
                            append("${(it / 60).coerceAtLeast(1)} min")
                        }
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun PanelInferiorMapa(
    ruta: RutaCalculada,
    modo: ModoMapa,
    marcas: Int,
    tieneDestino: Boolean,
    onCambiarModo: (ModoMapa) -> Unit,
    onCentrar: () -> Unit,
    onQuitarUltima: () -> Unit,
    onRecalcular: () -> Unit,
    recalculando: Boolean,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth().navigationBarsPadding().padding(12.dp),
        shape = RoundedCornerShape(Radios.tarjetaGrande),
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 10.dp,
    ) {
        Column(Modifier.padding(16.dp)) {
            if (modo == ModoMapa.DESTINO) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Place, null, tint = VERDE, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Toca a dónde quieres ir", style = MaterialTheme.typography.titleSmall)
                }
                Spacer(Modifier.height(4.dp))
                // Al marcar destino propio se dice qué queda comprobado y qué
                // no: el §20.2 descarta el camino —cierres, puentes, quebradas,
                // agua—, pero no acredita el sitio. Un punto elegido a dedo no
                // pasa a ser refugio porque exista una ruta hasta él, y quien
                // lo marca tiene que saberlo antes de ir.
                Text(
                    if (tieneDestino) {
                        "Marcado. Toca otra vez si te equivocaste. Se revisa el " +
                            "camino, no si el sitio es seguro."
                    } else {
                        "Sin destino se busca el refugio validado más cercano."
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else if (modo == ModoMapa.ATASCO) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Filled.Warning,
                        null,
                        tint = AMBAR,
                        modifier = Modifier.size(18.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Toca la calle por donde no se puede pasar",
                        style = MaterialTheme.typography.titleSmall,
                    )
                }
                Spacer(Modifier.height(4.dp))
                // Se dice aquí y no en un aviso legal al final: quien marca
                // tiene que saber que no está cerrando la calle para nadie.
                Text(
                    "Se envía como reporte sin confirmar. No cierra la vía hasta " +
                        "que lo valide la municipalidad.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (marcas > 0) {
                    Spacer(Modifier.height(10.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "$marcas marcado${if (marcas == 1) "" else "s"}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                        Spacer(Modifier.width(10.dp))
                        OutlinedButton(onClick = onQuitarUltima) {
                            Icon(Icons.Filled.Close, null, Modifier.size(14.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Quitar el último", style = MaterialTheme.typography.labelMedium)
                        }
                    }
                }
            } else {
                ruta.pasos.take(2).forEachIndexed { i, paso ->
                    Row(Modifier.padding(bottom = 6.dp)) {
                        Box(
                            Modifier.size(20.dp).background(SentiPrimary, CircleShape),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                "${i + 1}",
                                color = Color.White,
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                        Spacer(Modifier.width(10.dp))
                        Text(paso, style = MaterialTheme.typography.bodySmall, lineHeight = 18.sp)
                    }
                }
                if (ruta.bloqueos.isNotEmpty()) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        "En rojo, lo que está cortado. En ámbar, lo reportado " +
                            "sin confirmar.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            // Recalcular aparece en cuanto hay algo que cambiar: un atasco
            // marcado, un destino nuevo, o los dos. Es una acción aparte y no
            // algo que ocurra al marcar, porque marcar tres tramos seguidos
            // dispararía tres cálculos y cada uno tarda. Además, si la
            // respuesta va a ser "no hay ruta verificable", más vale que
            // llegue cuando ha terminado de marcar y no a mitad.
            if (marcas > 0 || tieneDestino) {
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = onRecalcular,
                    enabled = !recalculando,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (recalculando) {
                        CircularProgressIndicator(
                            Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                            color = Color.White,
                        )
                        Spacer(Modifier.width(9.dp))
                        Text("Calculando…", style = MaterialTheme.typography.labelLarge)
                    } else {
                        Icon(Icons.Filled.Refresh, null, Modifier.size(17.dp))
                        Spacer(Modifier.width(7.dp))
                        Text(
                            if (tieneDestino) "Calcular la ruta hasta ahí"
                            else "Buscar otra ruta evitando esto",
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            // Dos cosas distintas que marcar y un botón para cada una. Con un
            // solo botón que alternara, el toque siguiente era una apuesta:
            // marcar el atasco donde se quería poner el destino manda a
            // alguien por otro sitio sin que se entere.
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = { onCambiarModo(ModoMapa.DESTINO) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (modo == ModoMapa.DESTINO) VERDE else SentiPrimary
                    ),
                ) {
                    Icon(
                        if (modo == ModoMapa.DESTINO) Icons.Filled.Close else Icons.Filled.Place,
                        null,
                        Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        if (modo == ModoMapa.DESTINO) "Terminar" else "A dónde voy",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Button(
                    onClick = { onCambiarModo(ModoMapa.ATASCO) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (modo == ModoMapa.ATASCO) AMBAR else SentiPrimary
                    ),
                ) {
                    Icon(
                        if (modo == ModoMapa.ATASCO) Icons.Filled.Close else Icons.Filled.Add,
                        null,
                        Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        if (modo == ModoMapa.ATASCO) "Terminar" else "Marcar atasco",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = onCentrar, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Filled.MyLocation, null, Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp))
                Text("Centrar en mi ubicación", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
