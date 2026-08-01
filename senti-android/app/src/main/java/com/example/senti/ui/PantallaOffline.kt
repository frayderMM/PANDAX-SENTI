package com.example.senti.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.AltRoute
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.senti.data.EstiloOffline
import com.example.senti.data.Guia
import com.example.senti.data.PackGuias
import com.example.senti.data.PaqueteZona
import com.example.senti.data.Punto
import com.example.senti.data.RutaGuardada
import com.example.senti.data.formatearFechaHora

/**
 * Modo sin conexión (§26).
 *
 * **Aquí no hay chat, ni reportes, ni perfil, ni barra de navegación.** No
 * están escondidos: no existen mientras esta pantalla está puesta. Los tres
 * necesitan servidor —el chat llama al modelo, los reportes se publican, el
 * perfil vive en la base de datos— y ofrecer un botón que no puede funcionar
 * en una emergencia es peor que no ofrecerlo: cuesta el tiempo de tocarlo y la
 * confianza de descubrir que no hacía nada.
 *
 * Lo que queda es lo que funciona sin red: dónde estás, por dónde ibas, qué
 * hay cerca y qué hacer. Y encima de todo, la fecha: nada de lo que se ve aquí
 * es de ahora.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PantallaOffline(
    paquete: PaqueteZona?,
    motivoSinPaquete: String?,
    guias: PackGuias?,
    packs: EstiloOffline.Packs?,
    miUbicacion: Punto?,
    sincronizando: Boolean,
    hayRed: Boolean,
    avisoSync: String?,
    onSincronizar: () -> Unit,
    onSalir: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var solicitudCentrado by remember { mutableStateOf(0) }
    var ficha by remember { mutableStateOf<FichaMapa?>(null) }
    var hojaRutas by remember { mutableStateOf(false) }
    var hojaGuias by remember { mutableStateOf(false) }
    var guiaAbierta by remember { mutableStateOf<Guia?>(null) }
    var confirmarSalida by remember { mutableStateOf(false) }

    Box(modifier.fillMaxSize().background(Color(0xFF0F1418))) {

        LienzoMapaOffline(
            packs = packs,
            paquete = paquete,
            miUbicacion = miUbicacion,
            solicitudCentrado = solicitudCentrado,
            onFicha = { ficha = it },
            modifier = Modifier.fillMaxSize(),
        )

        // ── Cabecera: la fecha, siempre visible ──────────────────────────
        Column(
            Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(12.dp)
                .fillMaxWidth(),
        ) {
            BarraSincronizacion(paquete, sincronizando, hayRed, onSincronizar)

            if (packs == null) {
                Spacer(Modifier.height(8.dp))
                AvisoOffline(
                    "El mapa base no está disponible en esta instalación. " +
                        "Los teléfonos y las guías siguen funcionando."
                )
            } else if (miUbicacion != null &&
                !EstiloOffline.LIMITES_DETALLE.contiene(miUbicacion.lat, miUbicacion.lon)
            ) {
                // Fuera del área metropolitana el pack nacional llega hasta
                // zoom 11: carreteras y forma de la ciudad, no calles con
                // nombre. Decirlo es la diferencia entre un mapa con límites
                // conocidos y un mapa en el que faltan calles sin avisar.
                Spacer(Modifier.height(8.dp))
                AvisoOffline(
                    "Estás fuera de Lima y Callao. Aquí el mapa descargado llega a " +
                        "carreteras y vías principales, no al detalle de cada calle."
                )
            }

            motivoSinPaquete?.let {
                Spacer(Modifier.height(8.dp))
                AvisoOffline(it)
            }

            avisoSync?.let {
                Spacer(Modifier.height(8.dp))
                AvisoOffline(it)
            }

            // §11.3 llevado al modo sin conexión: lo que no se pudo descargar
            // se dice. Un mapa sin bloqueos no es un mapa sin peligro.
            paquete?.contenido?.fuentesFallidas?.takeIf { it.isNotEmpty() }?.let { fallidas ->
                Spacer(Modifier.height(8.dp))
                AvisoOffline(
                    "En la última sincronización no se pudo descargar: " +
                        fallidas.joinToString(", ") + ". Que no aparezcan en el " +
                        "mapa no significa que no existan."
                )
            }
        }

        // ── Botones flotantes: los cuatro, y ninguno más ─────────────────
        Column(
            Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
            horizontalAlignment = Alignment.End,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            BotonOffline(Icons.AutoMirrored.Filled.MenuBook, "Guías") { hojaGuias = true }
            BotonOffline(Icons.AutoMirrored.Filled.AltRoute, "Rutas guardadas") { hojaRutas = true }
            BotonOffline(Icons.Filled.MyLocation, "Centrar ubicación") { solicitudCentrado++ }
            BotonOffline(Icons.Filled.Close, "Salir del modo offline") { confirmarSalida = true }
        }

        // Sin paquete descargado, el texto exacto que pide el requisito. Va
        // sobre el mapa y no en su lugar: el mapa base sigue sirviendo para
        // orientarse aunque no haya datos de la zona.
        if (paquete == null && motivoSinPaquete == null) {
            Surface(
                color = Color(0xE6101418),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .align(Alignment.Center)
                    .padding(28.dp),
            ) {
                Column(Modifier.padding(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Filled.CloudOff, contentDescription = null, tint = Color.White)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "No hay datos offline descargados para esta zona",
                        color = Color.White,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        textAlign = TextAlign.Center,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Cuando tengas conexión, pulsa «Actualizar datos» para " +
                            "descargar los 10 km² de tu zona.",
                        color = Color.White.copy(alpha = 0.75f),
                        style = MaterialTheme.typography.labelMedium,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }

    // ── Hojas y diálogos ─────────────────────────────────────────────────

    ficha?.let { f ->
        AlertDialog(
            onDismissRequest = { ficha = null },
            confirmButton = { TextButton(onClick = { ficha = null }) { Text("Cerrar") } },
            title = { Text(f.titulo) },
            text = {
                Column {
                    f.lineas.forEach {
                        Text("· $it", style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(4.dp))
                    }
                }
            },
        )
    }

    if (hojaRutas) {
        ModalBottomSheet(
            onDismissRequest = { hojaRutas = false },
            sheetState = rememberModalBottomSheetState(),
        ) {
            HojaRutas(paquete?.contenido?.rutas.orEmpty(), paquete)
        }
    }

    if (hojaGuias) {
        ModalBottomSheet(
            onDismissRequest = { hojaGuias = false },
            sheetState = rememberModalBottomSheetState(),
        ) {
            HojaGuias(guias, onAbrir = { guiaAbierta = it })
        }
    }

    guiaAbierta?.let { g ->
        ModalBottomSheet(
            onDismissRequest = { guiaAbierta = null },
            sheetState = rememberModalBottomSheetState(),
        ) {
            DetalleGuia(g, guias)
        }
    }

    if (confirmarSalida) {
        AlertDialog(
            onDismissRequest = { confirmarSalida = false },
            confirmButton = {
                TextButton(onClick = { confirmarSalida = false; onSalir() }) {
                    Text("Salir")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmarSalida = false }) { Text("Quedarme") }
            },
            icon = { Icon(Icons.Filled.Warning, contentDescription = null) },
            title = { Text("Salir del modo sin conexión") },
            text = {
                Text(
                    "El chat, los reportes y el perfil necesitan conexión. Si no " +
                        "la hay, no van a responder. El mapa descargado y las " +
                        "guías se quedan aquí.",
                    style = MaterialTheme.typography.bodySmall,
                )
            },
        )
    }
}

@Composable
private fun BarraSincronizacion(
    paquete: PaqueteZona?,
    sincronizando: Boolean,
    hayRed: Boolean,
    onSincronizar: () -> Unit,
) {
    val vencido = paquete?.vencido() == true
    Surface(
        color = if (vencido) Color(0xE6B3261E) else Color(0xE6202A33),
        shape = RoundedCornerShape(10.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.CloudOff,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    "MODO SIN CONEXIÓN",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelMedium,
                )
                // §26: siempre la fecha de sincronización, nunca la hora actual.
                Text(
                    paquete?.let {
                        "Datos del ${formatearFechaHora(it.sincronizadoAt)}"
                    } ?: "Sin datos descargados",
                    color = Color.White.copy(alpha = 0.85f),
                    style = MaterialTheme.typography.labelMedium,
                )
                if (vencido) {
                    Text(
                        "Vencidos. Pueden no reflejar la situación actual.",
                        color = Color.White,
                        fontWeight = FontWeight.SemiBold,
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
            if (sincronizando) {
                CircularProgressIndicator(
                    Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = Color.White,
                )
            } else if (hayRed) {
                TextButton(onClick = onSincronizar) {
                    Text("Actualizar datos", color = Color.White, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun AvisoOffline(texto: String) {
    Surface(color = Color(0xE68A6D00), shape = RoundedCornerShape(10.dp)) {
        Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.Top) {
            Icon(
                Icons.Filled.Warning,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(texto, color = Color.White, style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Composable
private fun BotonOffline(
    icono: androidx.compose.ui.graphics.vector.ImageVector,
    etiqueta: String,
    onClick: () -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        // La etiqueta va SIEMPRE al lado y no solo al mantener pulsado: un
        // icono sin texto se adivina, y aquí adivinar cuesta tiempo.
        Surface(color = Color(0xCC101418), shape = RoundedCornerShape(6.dp)) {
            Text(
                etiqueta,
                color = Color.White,
                style = MaterialTheme.typography.labelMedium,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            )
        }
        Spacer(Modifier.width(8.dp))
        SmallFloatingActionButton(onClick = onClick) {
            Icon(icono, contentDescription = etiqueta)
        }
    }
}

@Composable
private fun HojaRutas(rutas: List<RutaGuardada>, paquete: PaqueteZona?) {
    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
        Text("Rutas guardadas", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(
            paquete?.let { "Calculadas antes del ${formatearFechaHora(it.sincronizadoAt)}." }
                ?: "Sin paquete descargado.",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(12.dp))

        if (rutas.isEmpty()) {
            Text(
                "No disponible sin conexión: no hay ninguna ruta guardada en este " +
                    "dispositivo. Las rutas se calculan con conexión y se conservan " +
                    "para consultarlas después.",
                style = MaterialTheme.typography.bodySmall,
            )
            return@Column
        }

        LazyColumn(
            Modifier.heightIn(max = 420.dp),
            contentPadding = PaddingValues(bottom = 8.dp),
        ) {
            items(rutas) { r ->
                Card(
                    Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(r.titulo, fontWeight = FontWeight.SemiBold)
                        r.distanciaM?.let {
                            Text(
                                "$it m aproximados",
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                        Spacer(Modifier.height(6.dp))
                        r.pasos.take(8).forEach {
                            Text("· $it", style = MaterialTheme.typography.bodySmall)
                        }
                        if (r.pasos.size > 8) {
                            Text(
                                "…y ${r.pasos.size - 8} pasos más",
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HojaGuias(guias: PackGuias?, onAbrir: (Guia) -> Unit) {
    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
        Text("Guías de emergencia", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(
            "Están dentro de la app. No necesitan conexión.",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(12.dp))

        if (guias == null) {
            Text(
                "No se pudieron leer las guías de esta instalación. Los teléfonos " +
                    "de emergencia siguen disponibles: 115 Defensa Civil · " +
                    "116 Bomberos · 106 SAMU.",
                style = MaterialTheme.typography.bodySmall,
            )
            return@Column
        }

        guias.advertencia()?.let {
            AvisoOffline(it)
            Spacer(Modifier.height(10.dp))
        }

        LazyColumn(
            Modifier.heightIn(max = 440.dp),
            contentPadding = PaddingValues(bottom = 8.dp),
        ) {
            items(guias.ordenadas) { g ->
                Card(
                    onClick = { onAbrir(g) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(g.titulo, fontWeight = FontWeight.SemiBold)
                        Text(
                            g.resumen,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DetalleGuia(guia: Guia, pack: PackGuias?) {
    Column(
        Modifier
            .padding(horizontal = 20.dp)
            .padding(bottom = 28.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text(guia.titulo, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        // §11.4: institución, versión y fecha. Sin esos tres campos una guía no
        // se presenta como verificada, y aquí además se declara de dónde sale
        // literalmente su redacción.
        Text(
            "${guia.institucion} · versión ${guia.version} · ${origenLegible(guia.origen)}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        pack?.let {
            Text(
                "Compilada en la app el ${it.compiladoAt}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            guia.fuente,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        pack?.advertencia()?.let {
            Spacer(Modifier.height(10.dp))
            AvisoOffline(it)
        }

        Spacer(Modifier.height(14.dp))
        guia.acciones.forEach { a ->
            Row(Modifier.padding(vertical = 5.dp)) {
                Text(
                    if (a.critica) "!" else "·",
                    fontWeight = FontWeight.Bold,
                    color = if (a.critica) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
                Spacer(Modifier.width(10.dp))
                Text(a.texto, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun origenLegible(origen: String): String = when (origen) {
    "protocolo" -> "reproduce un protocolo versionado"
    "texto_fijo" -> "texto fijo del sistema"
    else -> "resumen de la recomendación pública"
}
