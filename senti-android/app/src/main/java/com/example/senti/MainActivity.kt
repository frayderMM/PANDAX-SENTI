package com.example.senti

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import androidx.core.net.toUri
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Report
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.foundation.layout.RowScope
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.LocationOff
import androidx.compose.material.icons.filled.Add
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.foundation.text.BasicTextField
import com.example.senti.ui.theme.Radios
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Backpack
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.automirrored.filled.AltRoute
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Water
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.Report
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.ui.text.style.TextAlign
import com.example.senti.ui.theme.SentiCelesteProfundo
import com.example.senti.ui.theme.SentiPrimary
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.IconButton
import androidx.compose.ui.draw.clip
import com.example.senti.data.Ubicacion
import com.example.senti.ui.theme.EstadoVerde
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.foundation.layout.fillMaxHeight
import com.example.senti.ui.theme.FormaOnda
import com.example.senti.ui.theme.EstadoNeutro
import com.example.senti.ui.theme.SentiVioleta
import androidx.compose.ui.draw.shadow
import android.content.Intent
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Place
import androidx.compose.ui.layout.ContentScale
import com.example.senti.ui.Mensaje
import com.example.senti.R
import com.example.senti.data.MarcadorMapa
import com.example.senti.data.SesionLocal
import com.example.senti.data.TemaApp
import com.example.senti.data.TipoDesastre
import com.example.senti.data.aMarcador
import com.example.senti.data.formatearFechaHora
import com.example.senti.data.tiposPresentes
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.example.senti.ui.MapaRuta
import com.example.senti.ui.ModoOfflineViewModel
import com.example.senti.ui.PantallaOffline
import com.example.senti.ui.SentiViewModel
import com.example.senti.ui.theme.SENTITheme
import java.io.ByteArrayOutputStream
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.rememberCameraPositionState

private enum class SeccionPrincipal { CHAT, REPORTES, PERFIL }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // El ViewModel se crea aquí y no dentro de PantallaSenti: el tema
            // envuelve toda la pantalla, así que necesita el estado —para
            // saber qué eligió la persona— antes de que exista nada dentro.
            val vm: SentiViewModel = viewModel()
            val estado by vm.estado.collectAsStateWithLifecycle()
            val temaOscuro = when (estado.tema) {
                TemaApp.CLARO -> false
                TemaApp.OSCURO -> true
                TemaApp.SISTEMA -> isSystemInDarkTheme()
            }
            SENTITheme(darkTheme = temaOscuro) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    PantallaSenti(vm = vm, estado = estado)
                }
            }
        }
    }
}

/**
 * §12: la interfaz distingue en texto y en color cuatro niveles.
 *
 * El color va SIEMPRE acompañado de texto. Alguien con daltonismo o mirando la
 * pantalla al sol tiene que poder distinguir una emergencia de un aviso, y el
 * §31.2 pide contraste y accesibilidad de forma explícita. El color solo nunca
 * es información.
 */
private val COLOR_ROJO = Color(0xFFB3261E)
private val COLOR_NARANJA = Color(0xFFB35C00)
private val COLOR_AMARILLO = Color(0xFF8A6D00)
private val COLOR_VERDE = Color(0xFF1B5E20)
private val COLOR_SIN_CONEXION = Color(0xFF49454F)

/**
 * Alturas de los mapas incrustados en las pantallas de reportes.
 *
 * Antes uno pedía 750 dp y el otro 660 dp, fijos, dentro de columnas sin
 * desplazamiento propio. En un teléfono normal —bastante menos de 750 dp de
 * alto una vez descontadas la cabecera y la barra inferior— el mapa se salía
 * de la pantalla y arrastraba con él lo que venía debajo: en "Tu zona" la
 * lista de reportes quedaba pintada fuera del área visible, sin scroll que la
 * trajera de vuelta, así que abrir la pestaña no mostraba ningún reporte.
 *
 * Estos valores caben con margen en un teléfono pequeño, y las pantallas que
 * los usan ahora van dentro de un `LazyColumn`: con letra grande o en tableta
 * el resto del contenido se desplaza en vez de recortarse.
 */
private val ALTURA_MAPA_RESUMEN = 420.dp
private val ALTURA_MAPA_SELECCION = 260.dp

private fun colorUrgencia(urgencia: String?): Color = when (urgencia) {
    "rojo" -> COLOR_ROJO
    "naranja" -> COLOR_NARANJA
    "amarillo" -> COLOR_AMARILLO
    "verde" -> COLOR_VERDE
    else -> COLOR_SIN_CONEXION
}

private fun etiquetaUrgencia(urgencia: String?): String = when (urgencia) {
    "rojo" -> "EMERGENCIA"
    "naranja" -> "URGENTE"
    "amarillo" -> "PRECAUCIÓN"
    "verde" -> "INFORMACIÓN"
    else -> ""
}

// Las etiquetas de tipo viven ahora en `TipoDesastre`, que además lleva el
// color que usan el filtro y los marcadores del mapa. Había dos tablas y no
// coincidían.

private data class ImagenPreparada(val base64: String)

private fun prepararImagenParaChat(context: Context, uri: Uri): ImagenPreparada {
    val bitmap = decodificarImagen(context, uri, maxDimension = 1280)
    val bytes = ByteArrayOutputStream().use { salida ->
        bitmap.compress(Bitmap.CompressFormat.JPEG, 78, salida)
        salida.toByteArray()
    }
    return ImagenPreparada(Base64.encodeToString(bytes, Base64.NO_WRAP))
}

private fun cargarPreviewImagen(context: Context, uri: Uri): Bitmap? = runCatching {
    decodificarImagen(context, uri, maxDimension = 420)
}.getOrNull()

private fun decodificarImagen(context: Context, uri: Uri, maxDimension: Int): Bitmap {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use {
        BitmapFactory.decodeStream(it, null, bounds)
    }
    var sampleSize = 1
    val mayorLado = maxOf(bounds.outWidth, bounds.outHeight)
    while (mayorLado / sampleSize > maxDimension) {
        sampleSize *= 2
    }
    val options = BitmapFactory.Options().apply { inSampleSize = sampleSize }
    return context.contentResolver.openInputStream(uri)?.use {
        BitmapFactory.decodeStream(it, null, options)
    } ?: error("No se pudo leer la imagen seleccionada.")
}

@Composable
fun PantallaSenti(
    vm: SentiViewModel,
    estado: com.example.senti.ui.SentiUiState,
    modifier: Modifier = Modifier,
) {
    val contexto = LocalContext.current
    val offlineVm: ModoOfflineViewModel = viewModel()
    val offline by offlineVm.estado.collectAsStateWithLifecycle()

    // El modo sin conexión ocupa la app ENTERA y sale antes que cualquier otra
    // cosa. No es una pestaña más ni una capa encima del resto: mientras está
    // puesto no hay chat, ni reportes, ni perfil, ni barra inferior, porque
    // ninguno de los tres puede funcionar sin servidor (§26).
    if (offline.activo) {
        BackHandler { offlineVm.salir() }
        PantallaOffline(
            paquete = offline.paquete,
            motivoSinPaquete = offline.motivoSinPaquete,
            guias = offline.guias,
            packs = offline.packs,
            miUbicacion = estado.lat?.let { la ->
                estado.lon?.let { lo -> com.example.senti.data.Punto(la, lo) }
            },
            sincronizando = offline.sincronizando,
            hayRed = offline.hayRed,
            preparado = offline.preparado,
            avisoSync = offline.avisoSync,
            onSincronizar = { offlineVm.sincronizar(estado.lat, estado.lon) },
            onCentrarUbicacion = {
                Ubicacion.ultimaConocida(contexto)?.let { (lat, lon) ->
                    vm.fijarUbicacion(lat, lon)
                }
            },
            onSalir = { offlineVm.salir() },
            modifier = modifier,
        )
        return
    }

    if (!estado.autenticado) {
        // El estado de la red se relee al llegar aquí: si alguien activó el
        // modo avión con la app abierta, el valor leído al arrancar ya no
        // vale y de él depende el aviso que se muestra abajo.
        LaunchedEffect(Unit) { offlineVm.refrescarRed() }

        PantallaAcceso(
            modifier = modifier,
            autenticando = estado.autenticando,
            error = estado.error,
            onLogin = { email, pass -> vm.iniciarSesion(email, pass) },
            onRegistro = { email, pass, nombre, distrito, telefono, recibirAlertas ->
                vm.registrar(email, pass, nombre, distrito, telefono, recibirAlertas)
            },
            // Solo se ofrece si hubo un login online de verdad en este
            // teléfono. Sin eso no hay nada que recuperar y el botón sería
            // una promesa vacía (§26).
            sesionGuardada = offline.sesion,
            hayRed = offline.hayRed,
            onEntrarSinConexion = { offlineVm.entrar() },
        )
        return
    }

    PantallaPrincipal(modifier, vm, estado, onModoSinConexion = { offlineVm.entrar() })
}

@Composable
private fun PantallaPrincipal(
    modifier: Modifier = Modifier,
    vm: SentiViewModel,
    estado: com.example.senti.ui.SentiUiState,
    onModoSinConexion: () -> Unit,
) {
    var seccion by remember { mutableStateOf(SeccionPrincipal.CHAT) }

    Scaffold(
        // `imePadding()` va AQUÍ y en ningún sitio más.
        //
        // Con edge-to-edge la ventana no se redimensiona al abrir el teclado:
        // solo se reportan insets. Si cada trozo los aplica por su cuenta, se
        // suman —el Scaffold reserva la barra inferior, el compositor añadía
        // navigationBarsPadding() y otra vez imePadding()— y aparece una franja
        // muerta del alto de la barra más la de navegación.
        //
        // Aplicándolo al Scaffold sube todo el conjunto, barra inferior
        // incluida, y el espacio se cuenta una sola vez.
        modifier = modifier
            .fillMaxSize()
            .imePadding(),
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface,
                tonalElevation = 0.dp,
                modifier = Modifier.shadow(18.dp),
            ) {
                // Los iconos van rellenos cuando la pestaña está activa y con
                // contorno cuando no. Antes todos iban rellenos y lo único que
                // cambiaba era un tono de gris, que sobre una pantalla con
                // reflejos no se distingue: había que fijarse para saber en qué
                // parte de la app estabas.
                PestanaSenti(
                    seleccionada = seccion == SeccionPrincipal.CHAT,
                    onClick = { seccion = SeccionPrincipal.CHAT },
                    activo = Icons.AutoMirrored.Filled.Chat,
                    inactivo = Icons.AutoMirrored.Outlined.Chat,
                    etiqueta = "Chat",
                )
                PestanaSenti(
                    seleccionada = seccion == SeccionPrincipal.REPORTES,
                    onClick = { seccion = SeccionPrincipal.REPORTES },
                    activo = Icons.Filled.Report,
                    inactivo = Icons.Outlined.Report,
                    etiqueta = "Reportes",
                )
                PestanaSenti(
                    seleccionada = seccion == SeccionPrincipal.PERFIL,
                    onClick = { seccion = SeccionPrincipal.PERFIL },
                    activo = Icons.Filled.Person,
                    inactivo = Icons.Outlined.Person,
                    etiqueta = "Perfil",
                )
            }
        },
    ) { padding ->
        // Solo el margen inferior. El superior lo aplica la cabecera con su
        // propio `statusBarsPadding()`, para que el color de marca llegue hasta
        // arriba del todo en vez de dejar una franja del color de fondo bajo el
        // reloj — que es lo que delata a una app como hecha a medias.
        val soloAbajo = Modifier.padding(bottom = padding.calculateBottomPadding())
        when (seccion) {
            SeccionPrincipal.REPORTES -> PantallaReportes(
                soloAbajo,
                estado,
                onCrearReporte = vm::crearReporte,
                onCargarReportes = vm::cargarReportes,
                onModoSinConexion = onModoSinConexion,
            )
            SeccionPrincipal.PERFIL -> PantallaPerfil(
                soloAbajo,
                estado,
                onCerrarSesion = vm::cerrarSesion,
                onFijarTema = vm::fijarTema,
            )
            SeccionPrincipal.CHAT -> PantallaChat(soloAbajo, vm, estado, onModoSinConexion)
        }
    }

    // El mapa va FUERA del Scaffold y encima de él. Dentro quedaría recortado
    // por la barra inferior, y una franja del mapa tapada por tres pestañas es
    // justo donde suele caer la calle por la que hay que salir.
    val enMapa = estado.rutaEnMapa
    if (enMapa != null) {
        val miUbicacion = estado.lat?.let { la ->
            estado.lon?.let { lo -> com.example.senti.data.Punto(la, lo) }
        }

        BackHandler { vm.cerrarMapa() }
        MapaRuta(
            ruta = enMapa,
            miUbicacion = miUbicacion,
            onCerrar = vm::cerrarMapa,
            onRecalcular = vm::recalcularRuta,
            recalculando = estado.recalculandoRuta,
            modoMarcadoInicial = estado.mapaEnModoMarcado,
        )

        // §20.5 literal. Si al esquivar lo que marcó el usuario no queda
        // ninguna ruta verificable, se dice — no se le devuelve la anterior
        // como si sus marcas no contaran.
        estado.sinRutaTrasMarcar?.let { aviso ->
            AlertDialog(
                onDismissRequest = vm::descartarAvisoSinRuta,
                confirmButton = {
                    TextButton(onClick = vm::descartarAvisoSinRuta) { Text("Entendido") }
                },
                icon = { Icon(Icons.Filled.Warning, contentDescription = null) },
                title = { Text("Sin ruta verificable") },
                text = { Text(aviso, style = MaterialTheme.typography.bodyMedium) },
            )
        }
    }
}

/**
 * Cabecera compacta.
 *
 * Antes era un bloque de degradado de unos 150 dp con el nombre, el subtítulo y
 * dos chips de teléfonos. En una pantalla de chat con el teclado abierto eso se
 * comía casi todo el espacio de los mensajes, que es el contenido.
 *
 * Los teléfonos salieron de aquí: estaban repetidos en el pie de cada pantalla,
 * así que ocupaban sitio permanente sin añadir nada. La emergencia se marca
 * donde importa —en el color y la etiqueta de cada respuesta (§12, §18)— y no
 * en un adorno fijo.
 */
@Composable
private fun RowScope.PestanaSenti(
    seleccionada: Boolean,
    onClick: () -> Unit,
    activo: ImageVector,
    inactivo: ImageVector,
    etiqueta: String,
) {
    NavigationBarItem(
        selected = seleccionada,
        onClick = onClick,
        icon = {
            Icon(
                if (seleccionada) activo else inactivo,
                contentDescription = etiqueta,
                modifier = Modifier.size(23.dp),
            )
        },
        label = {
            Text(
                etiqueta,
                style = MaterialTheme.typography.labelMedium.copy(
                    fontWeight = if (seleccionada) FontWeight.Bold else FontWeight.Medium
                ),
            )
        },
        colors = NavigationBarItemDefaults.colors(
            selectedIconColor = MaterialTheme.colorScheme.primary,
            selectedTextColor = MaterialTheme.colorScheme.primary,
            indicatorColor = MaterialTheme.colorScheme.primaryContainer,
            unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
        ),
    )
}

@Composable
private fun EncabezadoSenti(
    titulo: String,
    subtitulo: String? = null,
    /**
     * Acceso al modo sin conexión, presente en TODAS las pantallas.
     *
     * Vive en la cabecera y no dentro de una sección por una razón concreta:
     * quien lo necesita está a punto de quedarse sin cobertura, o ya se quedó,
     * y entonces cada toque de más es tiempo. Estuvo dentro del perfil —dos
     * toques y saber que había que buscarlo ahí— y eso es esconder la salida
     * de emergencia en un cajón.
     */
    onModoSinConexion: (() -> Unit)? = null,
    // Cuando no es null, cambia el icono de marca por una flecha de volver.
    // Las pantallas que cuelgan de "Tu perfil" no son un destino propio de la
    // barra inferior; necesitan cómo volver sin depender solo del gesto de
    // Android.
    onVolver: (() -> Unit)? = null,
    accion: (@Composable () -> Unit)? = null,
) {
    Surface(
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Box {
            // Un velo diagonal muy tenue del violeta del icono. Es lo único que
            // queda del degradado anterior, que recorría del azul al violeta a
            // plena saturación y competía con los colores de gravedad: cuando
            // aparecía un rojo de emergencia real, la pantalla ya venía cargada
            // de color y el rojo se leía como un elemento más de la marca.
            Box(
                Modifier
                    .matchParentSize()
                    .background(
                        Brush.linearGradient(
                            listOf(Color.Transparent, SentiVioleta.copy(alpha = 0.55f))
                        )
                    )
            )
            Row(
                Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(start = 18.dp, end = 14.dp, top = 14.dp, bottom = 18.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (onVolver != null) {
                    IconButton(onClick = onVolver, modifier = Modifier.size(42.dp)) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Volver",
                            tint = Color.White,
                        )
                    }
                } else {
                    Surface(
                        color = Color.White.copy(alpha = 0.16f),
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.size(42.dp),
                    ) {
                        // El icono propio de SENTI, no un triángulo de
                        // peligro. Ese triángulo es el símbolo con el que la
                        // app marca un peligro real (§18); gastarlo en la
                        // cabecera de todas las pantallas lo vacía de
                        // significado justo donde hace falta.
                        Image(
                            painter = painterResource(R.mipmap.ic_launcher_foreground),
                            contentDescription = null,
                            modifier = Modifier.fillMaxSize(),
                        )
                    }
                }
                Spacer(Modifier.width(13.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        titulo,
                        style = MaterialTheme.typography.headlineSmall,
                        color = Color.White,
                        maxLines = 1,
                    )
                    subtitulo?.let {
                        Spacer(Modifier.height(1.dp))
                        Text(
                            it,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.White.copy(alpha = 0.82f),
                            maxLines = 2,
                        )
                    }
                }
                accion?.invoke()
                onModoSinConexion?.let { abrir ->
                    IconButton(onClick = abrir, modifier = Modifier.size(42.dp)) {
                        Icon(
                            Icons.Filled.Map,
                            contentDescription = "Mapa sin conexión",
                            tint = Color.White,
                        )
                    }
                }
            }
        }
    }
}

/**
 * Pastilla de estado para la cabecera.
 *
 * Blanca translúcida y no de color: el color en esta app significa gravedad
 * (§12, §18), y un indicador de "tengo tu ubicación" en verde se leería como
 * "la situación está bien", que es una afirmación que el sistema no hace.
 */
@Composable
private fun PastillaCabecera(
    texto: String,
    icono: ImageVector,
    onClick: (() -> Unit)? = null,
) {
    val forma = RoundedCornerShape(50)
    Surface(
        color = Color.White.copy(alpha = if (onClick != null) 0.22f else 0.14f),
        contentColor = Color.White,
        shape = forma,
        modifier = if (onClick != null) {
            Modifier.clip(forma).clickable(onClick = onClick)
        } else {
            Modifier
        },
    ) {
        Row(
            Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(icono, contentDescription = null, modifier = Modifier.size(15.dp))
            Spacer(Modifier.width(6.dp))
            Text(texto, style = MaterialTheme.typography.labelMedium)
        }
    }
}

/**
 * Pantalla de chat.
 *
 * Tres cosas que arreglan el layout roto anterior:
 *
 * 1. **Sin `statusBarsPadding()`.** El `Scaffold` ya entrega los insets en su
 *    `padding`; aplicarlos otra vez dejaba una banda muerta arriba.
 * 2. **Cabecera compacta y fija.** La anterior ocupaba ~150 dp, y con el
 *    teclado abierto no quedaba altura para los mensajes.
 * 3. **`imePadding()` solo en el `Scaffold`.** Con edge-to-edge la ventana no
 *    se redimensiona: si además lo aplican el contenedor y el compositor, los
 *    insets se suman y queda una franja muerta bajo el teclado.
 */
@Composable
private fun PantallaChat(
    modifier: Modifier = Modifier,
    vm: SentiViewModel,
    estado: com.example.senti.ui.SentiUiState,
    onModoSinConexion: () -> Unit,
) {
    var entrada by remember { mutableStateOf("") }
    var imagenSeleccionada by remember { mutableStateOf<Uri?>(null) }
    var errorImagen by remember { mutableStateOf<String?>(null) }
    var fotoTemporal by remember { mutableStateOf<Uri?>(null) }
    // "Nuevo chat" no borra nada del servidor, pero sí saca de la vista la
    // conversación que se está leyendo, y esta pantalla no ofrece ninguna
    // lista de hilos anteriores a la que volver para recuperarla. El botón
    // está justo al lado del de ubicación, así que un toque de más es fácil;
    // solo se pide confirmación cuando de verdad hay algo que perder.
    var confirmarNuevoChat by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val listState = rememberLazyListState()

    val selectorImagen = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        if (uri != null) { imagenSeleccionada = uri; errorImagen = null }
    }
    val camara = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { exito: Boolean ->
        if (exito) { imagenSeleccionada = fotoTemporal; errorImagen = null }
    }
    val permisoUbicacion = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { concedidos ->
        if (concedidos.values.any { it }) {
            val u = Ubicacion.ultimaConocida(context)
            vm.fijarUbicacion(u?.first, u?.second)
        } else {
            // §13.4: negarse no bloquea el servicio. Se marca como pedida para
            // no volver a preguntar en cada entrada.
            vm.marcarUbicacionPedida()
        }
    }

    // §13.2: se pide al entrar, una sola vez, y solo si no se preguntó antes.
    LaunchedEffect(estado.autenticado) {
        if (!estado.ubicacionPedida) {
            if (Ubicacion.hayPermiso(context)) {
                val u = Ubicacion.ultimaConocida(context)
                vm.fijarUbicacion(u?.first, u?.second)
            } else {
                permisoUbicacion.launch(Ubicacion.PERMISOS)
            }
        }
    }

    LaunchedEffect(estado.mensajes.size) {
        if (estado.mensajes.isNotEmpty()) listState.animateScrollToItem(estado.mensajes.lastIndex)
    }

    val previewImagen = remember(imagenSeleccionada) {
        imagenSeleccionada?.let { cargarPreviewImagen(context, it) }
    }

    Column(modifier.fillMaxSize()) {
        EncabezadoSenti(
            titulo = "SENTI",
            subtitulo = "Asistencia ante emergencias",
            onModoSinConexion = onModoSinConexion,
            accion = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(
                        onClick = {
                            if (estado.mensajes.isNotEmpty()) {
                                confirmarNuevoChat = true
                            } else {
                                vm.nuevoChat()
                            }
                        },
                        modifier = Modifier.size(42.dp),
                    ) {
                        Icon(
                            Icons.Filled.Add,
                            contentDescription = "Nuevo chat",
                            tint = Color.White,
                        )
                    }
                    if (estado.lat != null) {
                        PastillaCabecera("Ubicación activa", Icons.Filled.LocationOn)
                    } else {
                        // Pulsable, y lo parece. Antes era un `TextButton` blanco
                        // sobre fondo blanco-azulado que no se leía como un botón,
                        // y sin ubicación no hay ruta que calcular.
                        PastillaCabecera("Activar ubicación", Icons.Filled.LocationOff) {
                            permisoUbicacion.launch(Ubicacion.PERMISOS)
                        }
                    }
                }
            },
        )

        if (estado.sinConexion) BannerSinConexion(estado.paquete?.sincronizadoAt)
        estado.error?.let { AvisoError(it) }
        errorImagen?.let { AvisoError(it) }

        LazyColumn(
            state = listState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (estado.mensajes.isEmpty()) item { EstadoVacioChat { entrada = it } }
            items(estado.mensajes) { m ->
                BurbujaMensaje(
                    m,
                    hayMapaPropio = true,
                    onAbrirMapa = vm::abrirMapa,
                )
            }
            if (estado.enviando) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "Consultando fuentes…",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            // §29: el acuse ya está arriba y la respuesta viene detrás. Sin este
            // aviso, los segundos de espera parecen la app colgada y la persona
            // vuelve a preguntar, que es justo lo que la cola no necesita.
            if (estado.esperandoDiferida) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "Preparando una respuesta más completa…",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        Surface(
            color = MaterialTheme.colorScheme.surface,
            shadowElevation = 14.dp,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
                previewImagen?.let { bmp ->
                    Surface(
                        shape = RoundedCornerShape(Radios.boton),
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(
                            Modifier.padding(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Image(
                                bitmap = bmp.asImageBitmap(),
                                contentDescription = "Imagen adjunta",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier
                                    .size(52.dp)
                                    .clip(RoundedCornerShape(12.dp)),
                            )
                            Spacer(Modifier.width(11.dp))
                            Column(Modifier.weight(1f)) {
                                Text(
                                    "Foto lista para enviar",
                                    style = MaterialTheme.typography.titleSmall,
                                )
                                // §25: el modelo describe lo observable, no concluye.
                                Text(
                                    "Describiré lo que se ve, sin sacar conclusiones.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            IconButton(onClick = { imagenSeleccionada = null }) {
                                Icon(Icons.Filled.Close, contentDescription = "Quitar la foto")
                            }
                        }
                    }
                    Spacer(Modifier.height(9.dp))
                }

                // Un solo contenedor con todo dentro.
                //
                // Antes eran dos iconos sueltos, un campo con su propio borde y
                // un botón: cuatro rectángulos de anchos distintos alineados a
                // ojo. Metiéndolos en una misma pastilla, la fila se lee como
                // un elemento y deja de parecer un formulario montado a mano.
                Row(verticalAlignment = Alignment.Bottom) {
                    Surface(
                        shape = RoundedCornerShape(26.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        modifier = Modifier.weight(1f),
                    ) {
                        Row(verticalAlignment = Alignment.Bottom) {
                            IconButton(
                                onClick = {
                                    fotoTemporal = crearUriFoto(context)
                                    fotoTemporal?.let { camara.launch(it) }
                                },
                                modifier = Modifier.size(46.dp),
                            ) {
                                Icon(
                                    Icons.Filled.PhotoCamera,
                                    contentDescription = "Tomar una foto",
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.size(21.dp),
                                )
                            }
                            IconButton(
                                onClick = {
                                    selectorImagen.launch(
                                        PickVisualMediaRequest(
                                            ActivityResultContracts.PickVisualMedia.ImageOnly
                                        )
                                    )
                                },
                                modifier = Modifier.size(46.dp),
                            ) {
                                Icon(
                                    Icons.Filled.Image,
                                    contentDescription = "Elegir de la galería",
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.size(21.dp),
                                )
                            }
                            BasicTextField(
                                value = entrada,
                                onValueChange = { entrada = it },
                                textStyle = MaterialTheme.typography.bodyMedium.copy(
                                    color = MaterialTheme.colorScheme.onSurface
                                ),
                                cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                                maxLines = 5,
                                modifier = Modifier
                                    .weight(1f)
                                    .heightIn(min = 46.dp, max = 132.dp)
                                    .padding(end = 14.dp, top = 13.dp, bottom = 13.dp),
                                decorationBox = { campo ->
                                    if (entrada.isEmpty()) {
                                        Text(
                                            "Escribe qué está pasando…",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                    campo()
                                },
                            )
                        }
                    }
                    Spacer(Modifier.width(8.dp))
                    val puedeEnviar =
                        (entrada.isNotBlank() || imagenSeleccionada != null) && !estado.enviando
                    FilledIconButton(
                        onClick = {
                            val base64 = imagenSeleccionada?.let { uri ->
                                runCatching { prepararImagenParaChat(context, uri).base64 }
                                    .onFailure { errorImagen = "No se pudo procesar la imagen." }
                                    .getOrNull()
                            }
                            vm.enviar(entrada.trim(), base64)
                            if (entrada.contains("atascad", ignoreCase = true)) {
                                vm.abrirMapaParaBloqueo()
                            }
                            entrada = ""
                            imagenSeleccionada = null
                        },
                        enabled = puedeEnviar,
                        shape = CircleShape,
                        modifier = Modifier.size(50.dp),
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.Send,
                            contentDescription = "Enviar",
                            modifier = Modifier.size(21.dp),
                        )
                    }
                }
            }
        }
    }

    if (confirmarNuevoChat) {
        AlertDialog(
            onDismissRequest = { confirmarNuevoChat = false },
            icon = { Icon(Icons.Filled.Warning, contentDescription = null) },
            title = { Text("¿Empezar un chat nuevo?") },
            text = {
                Text(
                    "Dejarás de ver esta conversación en la app. No se borra del " +
                        "servidor, pero aquí no hay forma de volver a abrirla.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            },
            confirmButton = {
                TextButton(onClick = { confirmarNuevoChat = false; vm.nuevoChat() }) {
                    Text("Empezar de nuevo")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmarNuevoChat = false }) { Text("Seguir aquí") }
            },
        )
    }
}

/** Destino temporal para la foto de la cámara. */
private fun crearUriFoto(context: Context): Uri? = runCatching {
    val archivo = java.io.File.createTempFile("senti_", ".jpg", context.cacheDir)
    androidx.core.content.FileProvider.getUriForFile(
        context, "${context.packageName}.fileprovider", archivo
    )
}.getOrNull()

@Composable
private fun EstadoVacioChat(onSugerencia: (String) -> Unit) {
    Column(Modifier.padding(top = 18.dp, bottom = 6.dp)) {
        Text(
            "¿Qué está pasando?",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            "Cuéntamelo con tus palabras. Si me dices la zona y qué ves, la " +
                "respuesta llega antes.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(22.dp))

        // Sugerencias que se pulsan y envían.
        //
        // Antes esto era una lista de viñetas que decía "Zona o distrito",
        // "Tipo de peligro"… es decir, deberes. Quien abre la app con agua
        // entrando en su casa no va a redactar un informe: va a pulsar lo
        // primero que se parezca a lo suyo. Las frases son las que de verdad
        // escribe la gente, no categorías del sistema.
        SUGERENCIAS_CHAT.forEach { (icono, texto) ->
            SugerenciaChat(icono, texto) { onSugerencia(texto) }
            Spacer(Modifier.height(9.dp))
        }

        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.Shield,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(14.dp),
            )
            Spacer(Modifier.width(7.dp))
            // §12, dicho de entrada y no escondido en un "acerca de".
            Text(
                "SENTI no reemplaza al canal oficial del Estado.",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private val SUGERENCIAS_CHAT = listOf(
    Icons.Filled.Water to "Está entrando agua a mi casa",
    Icons.AutoMirrored.Filled.AltRoute to "Dame una ruta de salida, estoy atascado",
    Icons.Filled.Campaign to "¿Hay alguna alerta en mi distrito?",
    Icons.Filled.Backpack to "¿Qué llevo en la mochila de emergencia?",
)

@Composable
private fun SugerenciaChat(icono: ImageVector, texto: String, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(Radios.tarjeta),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer,
                shape = RoundedCornerShape(11.dp),
            ) {
                Icon(
                    icono,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onPrimaryContainer,
                    modifier = Modifier.padding(8.dp).size(19.dp),
                )
            }
            Spacer(Modifier.width(13.dp))
            Text(
                texto,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            Icon(
                Icons.AutoMirrored.Filled.ArrowForward,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(17.dp),
            )
        }
    }
}

@Composable
private fun PantallaReportes(
    modifier: Modifier = Modifier,
    estado: com.example.senti.ui.SentiUiState,
    onCrearReporte: (
        tipo: String,
        descripcion: String,
        lat: Double?,
        lon: Double?,
        direccion: String?,
        distrito: String?,
        fotoBase64: String?,
    ) -> Unit,
    onCargarReportes: (Double?, Double?) -> Unit,
    onModoSinConexion: () -> Unit,
) {
    var creando by remember { mutableStateOf(false) }

    // Se cargan al entrar, no al pulsar: quien abre esta pestaña quiere ver el
    // estado de su zona, no un botón.
    LaunchedEffect(Unit) { onCargarReportes(null, null) }

    Column(modifier.fillMaxSize()) {
        // La cabecera va a sangre, fuera del padding del contenido. Antes
        // estaba dentro y quedaba como un rectángulo de color flotando con
        // márgenes, distinto a como se ve en el chat: la misma cabecera con
        // dos aspectos según la pestaña.
        EncabezadoSenti(
            titulo = if (creando) "Reportar" else "Tu zona",
            subtitulo = if (creando) {
                "Nace pendiente hasta que alguien lo valide."
            } else {
                "Un reporte ciudadano no es información oficial hasta validarse."
            },
            onModoSinConexion = onModoSinConexion,
        )

        Box(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
            if (creando) {
                FormularioReporte(estado, onCrearReporte)
            } else {
                ListaReportes(
                    estado = estado,
                    onRecargar = { onCargarReportes(null, null) },
                    encabezado = { ReportesMapa(estado.reportes, estado.lat, estado.lon) },
                )
            }

            // Reportes se consulta desde la pestaña inferior; crear un reporte
            // es una acción puntual y no necesita otra pestaña permanente.
            FloatingActionButton(
                onClick = { creando = !creando },
                modifier = Modifier.align(Alignment.BottomEnd).padding(bottom = 18.dp),
                containerColor = if (creando) MaterialTheme.colorScheme.surfaceVariant else SentiPrimary,
            ) {
                Icon(
                    if (creando) Icons.Filled.Close else Icons.Filled.Add,
                    contentDescription = if (creando) "Cerrar nuevo reporte" else "Nuevo reporte",
                )
            }
        }
    }
}

@Composable
private fun ReportesMapa(
    reportes: List<com.example.senti.data.ReporteResumen>,
    miLat: Double?,
    miLon: Double?,
) {
    var eventos by remember { mutableStateOf<List<com.example.senti.data.EventoMapa>>(emptyList()) }
    LaunchedEffect(Unit) {
        runCatching { eventos = com.example.senti.data.Api.listarEventos().events }
    }

    // Eventos agregados y reportes ciudadanos se unifican para pintarlos, pero
    // cada marcador conserva de dónde vino: la ficha lo dice y el §25 prohíbe
    // presentarlos como lo mismo.
    val marcadores = remember(reportes, eventos) {
        eventos.mapNotNull { it.aMarcador() } + reportes.mapNotNull { it.aMarcador() }
    }
    val tipos = remember(marcadores) { marcadores.tiposPresentes() }

    // Vacío significa "todos". Es distinto de "ninguno seleccionado": un filtro
    // que empieza sin nada marcado enseñaría un mapa en blanco al abrir.
    var tiposActivos by remember { mutableStateOf<Set<String>>(emptySet()) }
    var seleccion by remember { mutableStateOf<MarcadorMapa?>(null) }

    val visibles = remember(marcadores, tiposActivos) {
        if (tiposActivos.isEmpty()) marcadores else marcadores.filter { it.tipo in tiposActivos }
    }

    // Si el filtro deja fuera lo que había abierto, la ficha se cierra sola:
    // dejarla mostraría el detalle de un punto que ya no está en el mapa.
    LaunchedEffect(visibles) {
        if (seleccion != null && visibles.none { it.id == seleccion!!.id }) seleccion = null
    }

    val centro = marcadores.firstOrNull()?.let { LatLng(it.lat, it.lon) }
        ?: miLat?.let { la -> miLon?.let { lo -> LatLng(la, lo) } }
        ?: LatLng(-12.05, -77.04)
    val camara = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(centro, if (marcadores.isEmpty()) 12f else 6f)
    }

    if (tipos.isNotEmpty()) {
        FiltroTipos(
            tipos = tipos,
            activos = tiposActivos,
            total = marcadores.size,
            onAlternar = { codigo ->
                tiposActivos = if (codigo in tiposActivos) {
                    tiposActivos - codigo
                } else {
                    tiposActivos + codigo
                }
            },
            onTodos = { tiposActivos = emptySet() },
        )
        Spacer(Modifier.height(10.dp))
    }

    Surface(
        modifier = Modifier.fillMaxWidth().height(ALTURA_MAPA_RESUMEN),
        shape = RoundedCornerShape(Radios.tarjetaGrande),
        shadowElevation = 3.dp,
    ) {
        Box {
            GoogleMap(
                modifier = Modifier.fillMaxSize(),
                cameraPositionState = camara,
                uiSettings = MapUiSettings(
                    zoomControlsEnabled = false,
                    mapToolbarEnabled = false,
                ),
                // Tocar el mapa fuera de un marcador cierra la ficha. No crea
                // nada: publicar un reporte exige el formulario y su botón.
                onMapClick = { seleccion = null },
            ) {
                if (miLat != null && miLon != null) {
                    Marker(
                        state = MarkerState(LatLng(miLat, miLon)),
                        title = "Mi ubicación",
                        snippet = "Tu ubicación actual",
                        icon = BitmapDescriptorFactory.defaultMarker(
                            BitmapDescriptorFactory.HUE_AZURE
                        ),
                    )
                }
                visibles.forEach { m ->
                    Marker(
                        state = MarkerState(LatLng(m.lat, m.lon)),
                        title = m.titulo,
                        snippet = m.etiquetaTipo,
                        icon = BitmapDescriptorFactory.defaultMarker(matizDe(m.color)),
                        onClick = {
                            seleccion = m
                            // Se consume el toque para que no salga además la
                            // burbuja diminuta de Google: la ficha de abajo
                            // dice lo mismo y cabe entera.
                            true
                        },
                    )
                }
            }

            seleccion?.let { m ->
                FichaMarcador(
                    marcador = m,
                    onCerrar = { seleccion = null },
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(12.dp),
                )
            }

            if (visibles.isEmpty() && marcadores.isNotEmpty()) {
                Surface(
                    color = MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
                    shape = RoundedCornerShape(Radios.tarjeta),
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                ) {
                    Text(
                        "Ningún evento de ese tipo en tu zona. Que no aparezca no " +
                            "significa que no exista: solo que no hay ninguno " +
                            "registrado con esa clasificación.",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(14.dp),
                    )
                }
            }
        }
    }
}

/**
 * Convierte el color del tipo al matiz que acepta el marcador de Google.
 *
 * `BitmapDescriptorFactory` solo admite un matiz de 0 a 360, no un color
 * completo, así que se pasa el color a HSV y se toma la componente H. Se pierde
 * saturación y brillo; el tono, que es lo que distingue un tipo de otro de un
 * vistazo, se conserva.
 */
private fun matizDe(argb: Long): Float {
    val hsv = FloatArray(3)
    android.graphics.Color.colorToHSV(argb.toInt(), hsv)
    return hsv[0]
}

/**
 * Filtro por tipo de desastre.
 *
 * Solo ofrece los tipos que hay en el mapa y enseña cuántos de cada uno. Un
 * chip que al pulsarlo deja la pantalla vacía no es un filtro, es una pregunta
 * sin respuesta.
 */
@Composable
private fun FiltroTipos(
    tipos: List<Pair<String, Int>>,
    activos: Set<String>,
    total: Int,
    onAlternar: (String) -> Unit,
    onTodos: () -> Unit,
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            ChipTipo(
                texto = "Todos ($total)",
                color = MaterialTheme.colorScheme.primary,
                seleccionado = activos.isEmpty(),
                onClick = onTodos,
            )
        }
        items(tipos) { (codigo, cuantos) ->
            ChipTipo(
                texto = "${com.example.senti.data.TipoDesastre.etiquetaDe(codigo)} ($cuantos)",
                color = Color(com.example.senti.data.TipoDesastre.colorDe(codigo)),
                seleccionado = codigo in activos,
                onClick = { onAlternar(codigo) },
            )
        }
    }
}

@Composable
private fun ChipTipo(
    texto: String,
    color: Color,
    seleccionado: Boolean,
    onClick: () -> Unit,
) {
    Surface(
        color = if (seleccionado) color.copy(alpha = 0.18f) else MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(
            if (seleccionado) 1.5.dp else 1.dp,
            if (seleccionado) color else MaterialTheme.colorScheme.outline.copy(alpha = 0.5f),
        ),
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Row(
            Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // El punto de color repite lo que dice el marcador en el mapa. El
            // texto va siempre al lado: el color no es la información (§31.2).
            Box(Modifier.size(9.dp).clip(CircleShape).background(color))
            Spacer(Modifier.width(7.dp))
            Text(
                texto,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = if (seleccionado) FontWeight.SemiBold else FontWeight.Normal,
            )
        }
    }
}

/**
 * Ficha de un marcador tocado.
 *
 * Sustituye a la burbuja de Google, que recorta el texto a una línea y no cabe
 * una descripción escrita por una persona. Lo que aquí importa además del qué
 * es **de dónde viene**: un evento con respaldo oficial y un reporte ciudadano
 * sin validar se leen distinto, y el §25 prohíbe presentarlos como lo mismo.
 */
@Composable
private fun FichaMarcador(
    marcador: MarcadorMapa,
    onCerrar: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(Radios.tarjeta),
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 8.dp,
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                Box(
                    Modifier
                        .padding(top = 5.dp)
                        .size(11.dp)
                        .clip(CircleShape)
                        .background(Color(marcador.color))
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        marcador.titulo,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        marcador.etiquetaTipo,
                        style = MaterialTheme.typography.labelMedium,
                        color = Color(marcador.color),
                    )
                }
                IconButton(onClick = onCerrar, modifier = Modifier.size(28.dp)) {
                    Icon(Icons.Filled.Close, contentDescription = "Cerrar")
                }
            }

            marcador.descripcion?.let {
                Spacer(Modifier.height(9.dp))
                Text(it, style = MaterialTheme.typography.bodySmall)
            }

            Spacer(Modifier.height(10.dp))

            // El origen, dicho con palabras y no solo con un color.
            Text(
                if (marcador.oficial) {
                    "Confirmado por fuente oficial o municipal."
                } else {
                    "Reporte ciudadano. Todavía no ha sido validado."
                },
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
                color = if (marcador.oficial) COLOR_ROJO else COLOR_AMARILLO,
            )

            val detalles = listOfNotNull(
                marcador.confianza?.let { "Confianza: ${etiquetaConfianza(it)}" },
                marcador.personas?.takeIf { it > 0 }?.let { "$it personas lo reportaron" },
                marcador.fuentesOficiales?.takeIf { it > 0 }?.let { "$it fuentes oficiales" },
                marcador.distrito,
                marcador.fecha?.take(16)?.replace('T', ' '),
            )
            if (detalles.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    detalles.joinToString(" · "),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * §12: cada reporte muestra su nivel de confianza en texto y en color.
 *
 * Es la diferencia entre "alguien dijo que la avenida está inundada" y "el
 * municipio confirmó que está cerrada", y el ciudadano tiene que poder verla de
 * un vistazo sin leer la letra pequeña.
 */
private fun colorConfianza(confianza: String): Color = when (confianza) {
    "confirmado" -> COLOR_ROJO
    "validado" -> COLOR_NARANJA
    "probable" -> COLOR_AMARILLO
    else -> COLOR_SIN_CONEXION
}

private fun etiquetaConfianza(confianza: String): String = when (confianza) {
    "confirmado" -> "CONFIRMADO POR EL MUNICIPIO"
    "validado" -> "VALIDADO"
    "probable" -> "PROBABLE"
    else -> "SIN CONFIRMAR"
}

/**
 * Mapa y lista de reportes de la zona, en un único `LazyColumn`.
 *
 * Antes el mapa y la lista vivían en una `Column` sin desplazamiento propio.
 * Con el mapa a 750 dp de alto, en cualquier teléfono normal la lista quedaba
 * empujada fuera del área visible sin ninguna forma de llegar a ella —"Tu
 * zona" parecía no tener reportes cuando en realidad estaban ahí, invisibles.
 * Un solo `LazyColumn` con el mapa como primer elemento hace que todo el
 * contenido se desplace junto y quepa en cualquier tamaño de pantalla.
 *
 * `contentPadding` deja hueco abajo para que el botón flotante de "nuevo
 * reporte" no tape ni el último reporte ni el aviso que va debajo.
 */
@Composable
private fun ListaReportes(
    estado: com.example.senti.ui.SentiUiState,
    onRecargar: () -> Unit,
    encabezado: @Composable () -> Unit,
) {
    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(top = 14.dp, bottom = 96.dp),
    ) {
        item { encabezado() }

        when {
            estado.cargandoReportes && estado.reportes.isEmpty() -> item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("Buscando reportes…", style = MaterialTheme.typography.bodySmall)
                }
            }
            estado.reportes.isEmpty() -> item {
                Card(colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )) {
                    Column(Modifier.padding(14.dp)) {
                        Text("No hay reportes vigentes cerca", fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(4.dp))
                        // §11.3 y §12: ausencia de reportes no es ausencia de peligro.
                        Text(
                            "Que nadie haya reportado no significa que no haya peligro. " +
                                "Si ves algo, repórtalo.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(10.dp))
                        OutlinedButton(onClick = onRecargar) { Text("Actualizar") }
                    }
                }
            }
            else -> {
                item {
                    Column {
                        OutlinedButton(onClick = onRecargar, modifier = Modifier.fillMaxWidth()) {
                            Text("Actualizar")
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "Los reportes ciudadanos sin validar no son información oficial.",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }

}

@Composable
private fun FormularioReporte(
    estado: com.example.senti.ui.SentiUiState,
    onCrearReporte: (
        tipo: String, descripcion: String, lat: Double?, lon: Double?,
        direccion: String?, distrito: String?, fotoBase64: String?,
    ) -> Unit,
) {
    val context = LocalContext.current
    var tipo by remember { mutableStateOf("inundacion") }
    var descripcion by remember { mutableStateOf("") }
    var distrito by remember { mutableStateOf("") }
    var direccion by remember { mutableStateOf("") }
    var lat by remember { mutableStateOf("") }
    var lon by remember { mutableStateOf("") }
    var fotoBase64 by remember { mutableStateOf<String?>(null) }
    var fotoPreview by remember { mutableStateOf<Bitmap?>(null) }
    // Los 12 tipos que reconoce el backend (§20.3), no solo 5: elegir el
    // correcto no es cosmético, decide cuánto dura vigente el reporte.
    val tipos = listOf(
        "inundacion", "huaico", "deslizamiento", "lluvia", "via_bloqueada",
        "puente_afectado", "acumulacion_agua", "sismo", "tsunami", "incendio",
        "caida_poste", "otro",
    )

    val selector = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        if (uri != null) {
            runCatching { prepararImagenParaChat(context, uri) }
                .onSuccess {
                    fotoBase64 = it.base64
                    fotoPreview = cargarPreviewImagen(context, uri)
                }
        }
    }

    // `contentPadding` bottom deja hueco para el botón flotante de cerrar el
    // formulario, que si no tapa el botón de enviar justo cuando se llega a él.
    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(bottom = 96.dp),
    ) {
        item {
            Text("¿Qué viste?", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(6.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(tipos) { t ->
                    TipoReporteChip(TipoDesastre.etiquetaDe(t), tipo == t) { tipo = t }
                }
            }
        }

        item {
            OutlinedTextField(
                value = descripcion,
                onValueChange = { descripcion = it },
                label = { Text("Describe lo que ves") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
            )
        }

        item {
            Card(colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant
            )) {
                Column(Modifier.padding(12.dp)) {
                    Text("Fotografía (opcional)", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(4.dp))
                    // §13.5 y §28: se avisa antes de adjuntar, no después.
                    Text(
                        "Se borra a los 30 días y se le quitan los metadatos de "
                            + "ubicación antes de guardarla. Evita que salgan personas.",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(10.dp))
                    fotoPreview?.let { bmp ->
                        Image(
                            bitmap = bmp.asImageBitmap(),
                            contentDescription = "Fotografía adjunta",
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 220.dp),
                        )
                        Spacer(Modifier.height(8.dp))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = {
                            selector.launch(
                                PickVisualMediaRequest(
                                    ActivityResultContracts.PickVisualMedia.ImageOnly
                                )
                            )
                        }) {
                            Icon(Icons.Filled.PhotoCamera, contentDescription = null,
                                modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(if (fotoBase64 == null) "Adjuntar" else "Cambiar")
                        }
                        if (fotoBase64 != null) {
                            TextButton(onClick = { fotoBase64 = null; fotoPreview = null }) {
                                Text("Quitar")
                            }
                        }
                    }
                }
            }
        }

        item {
            Text("¿Dónde?", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(6.dp))
            OutlinedTextField(
                value = direccion,
                onValueChange = { direccion = it },
                label = { Text("Referencia (av., cuadra, puente)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = distrito,
                onValueChange = { distrito = it },
                label = { Text("Distrito") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Spacer(Modifier.height(12.dp))
            MapaDeReporte(
                lat = lat.toDoubleOrNull(),
                lon = lon.toDoubleOrNull(),
                onMarcar = { p ->
                    lat = p.latitude.toString()
                    lon = p.longitude.toString()
                },
            )
        }

        item {
            Button(
                onClick = {
                    onCrearReporte(
                        tipo.trim(),
                        descripcion.trim(),
                        lat.toDoubleOrNull(),
                        lon.toDoubleOrNull(),
                        direccion.trim(),
                        distrito.trim(),
                        fotoBase64,
                    )
                },
                enabled = !estado.reportando,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (estado.reportando) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text("Enviar reporte")
            }
            estado.reporteResultado?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, style = MaterialTheme.typography.bodySmall, color = COLOR_VERDE)
            }
            estado.error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, style = MaterialTheme.typography.bodySmall, color = COLOR_ROJO)
            }
        }
    }
}

@Composable
private fun TipoReporteChip(
    texto: String,
    seleccionado: Boolean,
    onClick: () -> Unit,
) {
    // Radios.chip (12 dp) y no 8: el resto de la app sigue la escala de
    // Formas.kt, y 8 dp es justo el valor "de escritorio de hace diez años"
    // que esa escala existe para evitar.
    if (seleccionado) {
        Button(
            onClick = onClick,
            shape = RoundedCornerShape(Radios.chip),
            contentPadding = ButtonDefaults.ContentPadding,
        ) {
            Text(texto)
        }
    } else {
        OutlinedButton(
            onClick = onClick,
            shape = RoundedCornerShape(Radios.chip),
            contentPadding = ButtonDefaults.ContentPadding,
        ) {
            Text(texto)
        }
    }
}

@Composable
private fun PantallaPerfil(
    modifier: Modifier = Modifier,
    estado: com.example.senti.ui.SentiUiState,
    onCerrarSesion: () -> Unit,
    onFijarTema: (TemaApp) -> Unit,
) {
    // Las preguntas frecuentes cuelgan de aquí y no de la barra inferior: se
    // leen una vez, no son un destino al que se vuelve.
    var enFaq by remember { mutableStateOf(false) }

    if (enFaq) {
        BackHandler { enFaq = false }
        PantallaFAQ(modifier, onVolver = { enFaq = false })
        return
    }

    Column(modifier.fillMaxSize()) {
        EncabezadoSenti(
            titulo = "Tu perfil",
            subtitulo = "Los datos mínimos para orientarte a ti y no a un promedio.",
        )
        LazyColumn(
            Modifier.fillMaxSize().padding(horizontal = 14.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 14.dp),
        ) {
            item {
                FilaPerfil(
                    icono = Icons.Filled.CheckCircle,
                    color = EstadoVerde,
                    titulo = "Sesión activa",
                    detalle = "La app está conectada a tu cuenta.",
                )
            }
            estado.paquete?.let { paquete ->
                item {
                    FilaPerfil(
                        icono = Icons.Filled.CloudOff,
                        color = MaterialTheme.colorScheme.primary,
                        titulo = "Guardado para usar sin internet",
                        // §26: se muestra CUÁNDO se sincronizó, nunca la hora
                        // actual. Presentar información vieja como si fuera de
                        // ahora es lo mismo que mentir sobre ella.
                        detalle = "Última actualización: " +
                            paquete.sincronizadoAt.take(16).replace('T', ' '),
                    )
                }
            }
            item {
                // §13.2, donde el usuario lo va a leer y no en un enlace legal.
                Surface(
                    shape = RoundedCornerShape(Radios.tarjeta),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(Modifier.padding(14.dp)) {
                        Icon(
                            Icons.Filled.Shield,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(19.dp),
                        )
                        Spacer(Modifier.width(11.dp))
                        Column {
                            Text(
                                "Qué se guarda de ti",
                                style = MaterialTheme.typography.titleSmall,
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                "Cuántos son en casa y qué necesitan, nunca nombres, " +
                                    "diagnósticos ni recetas. Las fotos que envías por " +
                                    "el chat no se guardan en ningún servidor.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
            item { FilaTema(estado.tema, onFijarTema) }
            item {
                Surface(
                    onClick = { enFaq = true },
                    shape = RoundedCornerShape(Radios.tarjeta),
                    color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(
                        1.dp,
                        MaterialTheme.colorScheme.outline.copy(alpha = 0.5f),
                    ),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                            shape = RoundedCornerShape(12.dp),
                        ) {
                            Icon(
                                Icons.AutoMirrored.Filled.HelpOutline,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.padding(9.dp).size(20.dp),
                            )
                        }
                        Spacer(Modifier.width(13.dp))
                        Column(Modifier.weight(1f)) {
                            Text("Preguntas frecuentes", style = MaterialTheme.typography.titleSmall)
                            Text(
                                "Cómo funciona SENTI y qué límites tiene.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowForward,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp),
                        )
                    }
                }
            }
            item {
                OutlinedButton(
                    onClick = onCerrarSesion,
                    shape = RoundedCornerShape(28.dp),
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                ) {
                    Text("Cerrar sesión", style = MaterialTheme.typography.bodyMedium)
                }
            }
            estado.error?.let { item { AvisoError(it) } }
        }
    }
}

/**
 * Selector de tema. Vive en el dispositivo, no en la cuenta (§ninguno: es una
 * preferencia de accesibilidad y comodidad, no un dato personal), por eso se
 * guarda en `PreferenciasStore` y sobrevive a cerrar sesión.
 */
@Composable
private fun FilaTema(tema: TemaApp, onCambiar: (TemaApp) -> Unit) {
    Surface(
        shape = RoundedCornerShape(Radios.tarjeta),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(15.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Icon(
                        Icons.Filled.Palette,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(9.dp).size(20.dp),
                    )
                }
                Spacer(Modifier.width(13.dp))
                Text("Tema", style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OpcionTema("Sistema", tema == TemaApp.SISTEMA, Modifier.weight(1f)) { onCambiar(TemaApp.SISTEMA) }
                OpcionTema("Claro", tema == TemaApp.CLARO, Modifier.weight(1f)) { onCambiar(TemaApp.CLARO) }
                OpcionTema("Oscuro", tema == TemaApp.OSCURO, Modifier.weight(1f)) { onCambiar(TemaApp.OSCURO) }
            }
        }
    }
}

@Composable
private fun OpcionTema(texto: String, seleccionado: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    if (seleccionado) {
        Button(onClick = onClick, shape = RoundedCornerShape(Radios.chip), modifier = modifier) {
            Text(texto, style = MaterialTheme.typography.labelMedium)
        }
    } else {
        OutlinedButton(onClick = onClick, shape = RoundedCornerShape(Radios.chip), modifier = modifier) {
            Text(texto, style = MaterialTheme.typography.labelMedium)
        }
    }
}

private data class PreguntaFrecuente(val pregunta: String, val respuesta: String)

/**
 * Contenido fijo y no del modelo: son respuestas sobre cómo funciona la app,
 * no orientación ante una emergencia, así que no hace falta el backend. Cada
 * una describe un comportamiento que ya existe en la app, no una promesa
 * nueva — igual que el resto de textos fijos de SENTI.
 */
private val PREGUNTAS_FRECUENTES = listOf(
    PreguntaFrecuente(
        "¿SENTI reemplaza a Defensa Civil, Bomberos o la Policía?",
        "No, nunca. SENTI orienta; el canal oficial del Estado es quien confirma y " +
            "actúa. En una emergencia real, llama primero: 115 Defensa Civil, " +
            "116 Bomberos, 105 Policía, 106 SAMU.",
    ),
    PreguntaFrecuente(
        "¿Qué significa que un reporte esté \"Probable\" o \"Confirmado\"?",
        "Es el nivel de confianza, no una opinión. \"Confirmado por el municipio\" " +
            "viene de una fuente oficial. \"Validado\" y \"Probable\" son reportes " +
            "ciudadanos sin esa confirmación — se muestran igual, pero con esa " +
            "diferencia siempre visible en el color y en el texto.",
    ),
    PreguntaFrecuente(
        "¿Qué pasa si no tengo señal?",
        "La app guarda un paquete básico —teléfonos de emergencia, la última " +
            "alerta descargada y tu plan familiar— desde la última vez que hubo " +
            "conexión, y siempre muestra la fecha de esa descarga. Nunca presenta " +
            "esa información vieja como si fuera de ahora.",
    ),
    PreguntaFrecuente(
        "¿Alguien más puede ver mis reportes o quién los hizo?",
        "Los reportes ciudadanos se muestran sin el nombre de quien los hizo, y " +
            "los datos de tu perfil del hogar no se comparten con otros usuarios.",
    ),
    PreguntaFrecuente(
        "¿Las fotos que envío por el chat se guardan?",
        "No se guardan en ningún servidor: se usan solo para analizar ese mensaje.",
    ),
    PreguntaFrecuente(
        "¿Puedo negarme a compartir algún dato?",
        "Sí. Cada dato se pide por separado y negarte no bloquea el servicio " +
            "básico: protocolos, teléfonos e información oficial siguen " +
            "disponibles. Revisa qué autorizaste en \"Términos y condiciones\".",
    ),
)

@Composable
private fun PantallaFAQ(modifier: Modifier = Modifier, onVolver: () -> Unit) {
    Column(modifier.fillMaxSize()) {
        EncabezadoSenti(
            titulo = "Preguntas frecuentes",
            subtitulo = "Cómo funciona SENTI y qué límites tiene.",
            onVolver = onVolver,
        )
        LazyColumn(
            Modifier.fillMaxSize().padding(horizontal = 14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = PaddingValues(vertical = 14.dp),
        ) {
            items(PREGUNTAS_FRECUENTES) { PreguntaFrecuenteFila(it) }
        }
    }
}

@Composable
private fun PreguntaFrecuenteFila(pf: PreguntaFrecuente) {
    var abierta by remember { mutableStateOf(false) }
    Surface(
        onClick = { abierta = !abierta },
        shape = RoundedCornerShape(Radios.tarjeta),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(15.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(pf.pregunta, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                Icon(
                    if (abierta) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                )
            }
            if (abierta) {
                Spacer(Modifier.height(8.dp))
                Text(
                    pf.respuesta,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun FilaPerfil(
    icono: ImageVector,
    color: Color,
    titulo: String,
    detalle: String,
) {
    Surface(
        shape = RoundedCornerShape(Radios.tarjeta),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(color = color.copy(alpha = 0.12f), shape = RoundedCornerShape(12.dp)) {
                Icon(
                    icono,
                    contentDescription = null,
                    tint = color,
                    modifier = Modifier.padding(9.dp).size(20.dp),
                )
            }
            Spacer(Modifier.width(13.dp))
            Column {
                Text(titulo, style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(2.dp))
                Text(
                    detalle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * Pantalla de acceso, centrada verticalmente.
 *
 * Antes era una lista que empezaba pegada arriba y dejaba media pantalla vacía
 * debajo. El formulario es corto y es lo único que hay que hacer aquí, así que
 * va centrado, con el ancho acotado para que en tabletas no se estire.
 *
 * §13.4: se puede usar SENTI sin cuenta. Eso se dice arriba y no al final, para
 * que quien no quiera registrarse no rellene el formulario primero.
 */
@Composable
private fun PantallaAcceso(
    modifier: Modifier = Modifier,
    autenticando: Boolean,
    error: String?,
    onLogin: (String, String) -> Unit,
    onRegistro: (String, String, String?, String?, String?, Boolean) -> Unit,
    sesionGuardada: SesionLocal? = null,
    hayRed: Boolean = true,
    onEntrarSinConexion: () -> Unit = {},
) {
    var modoRegistro by remember { mutableStateOf(false) }
    var email by remember { mutableStateOf("") }
    var pass by remember { mutableStateOf("") }
    var passVisible by remember { mutableStateOf(false) }
    var nombre by remember { mutableStateOf("") }
    var distrito by remember { mutableStateOf("") }
    var telefono by remember { mutableStateOf("") }
    var recibirAlertas by remember { mutableStateOf(false) }

    // El número se comprueba sobre sus dígitos, para que dé igual cómo lo
    // escriba cada uno. Nueve dígitos empezando por 9 es el móvil peruano; el
    // backend le antepone el 51 al canonizarlo.
    //
    // Es opcional: quien no lo dé se registra igual y usa la app. Lo que no
    // puede es quedar a medias — un número mal escrito no avisa a nadie y
    // además nadie se entera de que no avisó.
    val digitosTelefono = telefono.filter { it.isDigit() }
    val telefonoValido = digitosTelefono.length == 9 && digitosTelefono.startsWith("9")

    val puedeEnviar = email.isNotBlank() && pass.isNotBlank() && !autenticando &&
        (!modoRegistro || telefono.isBlank() || telefonoValido)

    Box(
        modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
    ) {
        // Cabecera azul con borde ondulado, como la referencia. Ocupa el tercio
        // superior y el formulario se superpone sobre ella.
        Box(
            Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.42f)
                .clip(FormaOnda(52f))
                .background(
                    Brush.linearGradient(
                        listOf(SentiCelesteProfundo, MaterialTheme.colorScheme.primary)
                    )
                )
        )

        Box(
            Modifier
                .fillMaxSize()
                .systemBarsPadding()
                .imePadding(),
            contentAlignment = Alignment.Center,
        ) {
        Column(
            Modifier
                .verticalScroll(rememberScrollState())
                .widthIn(max = 420.dp)
                .padding(horizontal = 24.dp, vertical = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // El icono de SENTI, no un triángulo de peligro genérico. Lo
            // primero que ve alguien al abrir la app no puede ser una señal de
            // alarma: la app se abre también para prepararse, y el §12 reserva
            // ese símbolo para cuando hay un peligro de verdad.
            Surface(
                color = Color.White.copy(alpha = 0.18f),
                shape = RoundedCornerShape(24.dp),
                modifier = Modifier.size(84.dp),
            ) {
                Image(
                    painter = painterResource(R.mipmap.ic_launcher_foreground),
                    contentDescription = null,
                    modifier = Modifier.fillMaxSize(),
                )
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "SENTI",
                color = Color.White,
                style = MaterialTheme.typography.displaySmall,
                letterSpacing = 2.sp,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                "Orientación ante lluvias, inundaciones y huaicos",
                color = Color.White.copy(alpha = 0.9f),
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(28.dp))

            Surface(
                shape = RoundedCornerShape(Radios.tarjetaGrande),
                color = MaterialTheme.colorScheme.surface,
                shadowElevation = 12.dp,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(
                    Modifier.padding(22.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        if (modoRegistro) "Crear cuenta" else "Iniciar sesión",
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        if (modoRegistro) {
                            "Con cuenta se guarda tu perfil del hogar y tus reportes."
                        } else {
                            "Para chat, reportes y modo sin conexión."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )

                    Spacer(Modifier.height(20.dp))

                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text("Correo") },
                        singleLine = true,
                        shape = RoundedCornerShape(28.dp),
                        colors = coloresCampoPildora(),
                        modifier = Modifier.fillMaxWidth(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = pass,
                        onValueChange = { pass = it },
                        label = { Text("Contraseña") },
                        singleLine = true,
                        shape = RoundedCornerShape(28.dp),
                        colors = coloresCampoPildora(),
                        visualTransformation = if (passVisible) {
                            VisualTransformation.None
                        } else {
                            PasswordVisualTransformation()
                        },
                        // Sin esto, tipear una contraseña larga a ciegas en un
                        // formulario con dos campos (correo y contraseña, y
                        // hasta cuatro en el registro) es la situación exacta
                        // en la que un error tipográfico pasa desapercibido
                        // hasta que el envío falla.
                        trailingIcon = {
                            IconButton(onClick = { passVisible = !passVisible }) {
                                Icon(
                                    if (passVisible) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                                    contentDescription = if (passVisible) {
                                        "Ocultar contraseña"
                                    } else {
                                        "Mostrar contraseña"
                                    },
                                )
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    )

                    if (modoRegistro) {
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = nombre,
                            onValueChange = { nombre = it },
                            label = { Text("Cómo te llamamos (opcional)") },
                            singleLine = true,
                            shape = RoundedCornerShape(28.dp),
                            colors = coloresCampoPildora(),
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = distrito,
                            onValueChange = { distrito = it },
                            label = { Text("Distrito (opcional)") },
                            singleLine = true,
                            shape = RoundedCornerShape(28.dp),
                            colors = coloresCampoPildora(),
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = telefono,
                            // Se filtran las letras al escribir en vez de
                            // rechazarlas al enviar: un campo que las acepta y
                            // luego dice que no valen hace escribir dos veces.
                            onValueChange = { nuevo ->
                                telefono = nuevo.filter { it.isDigit() || it == ' ' }.take(12)
                            },
                            label = { Text("Teléfono WhatsApp (opcional)") },
                            placeholder = { Text("9XX XXX XXX") },
                            singleLine = true,
                            isError = telefono.isNotBlank() && !telefonoValido,
                            supportingText = {
                                Text(
                                    if (telefono.isNotBlank() && !telefonoValido) {
                                        // Un número mal escrito no avisa a
                                        // nadie, y además nadie se entera de
                                        // que no avisó. Se dice al teclearlo.
                                        "Nueve dígitos y empieza por 9."
                                    } else {
                                        // §13.5, dicho donde se pide el dato y
                                        // no en un enlace legal que nadie abre.
                                        "En tu cuenta se guarda cifrado y de un solo " +
                                            "sentido. Solo se conserva para poder " +
                                            "escribirte si marcas la casilla de abajo."
                                    },
                                    style = MaterialTheme.typography.labelSmall,
                                )
                            },
                            shape = RoundedCornerShape(28.dp),
                            colors = coloresCampoPildora(),
                            modifier = Modifier.fillMaxWidth(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                        )
                        Spacer(Modifier.height(4.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = recibirAlertas,
                                onCheckedChange = { recibirAlertas = it },
                            )
                            Text(
                                "Avísenme por WhatsApp de las alertas de mi distrito. " +
                                    "Necesita teléfono y distrito.",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }

                    error?.let {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            it,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center,
                        )
                    }

                    Spacer(Modifier.height(20.dp))
                    Button(
                        onClick = {
                            if (modoRegistro) {
                                onRegistro(
                                    email.trim(), pass,
                                    nombre.trim().ifBlank { null },
                                    distrito.trim().ifBlank { null },
                                    // Van solo los dígitos. El backend los
                                    // canoniza igualmente —les antepone el 51
                                    // para que el seudónimo coincida con el
                                    // del número que entrega WhatsApp—, así
                                    // que esto es por no mandarle espacios
                                    // que va a tirar de todos modos.
                                    digitosTelefono.ifBlank { null },
                                    recibirAlertas,
                                )
                            } else {
                                onLogin(email.trim(), pass)
                            }
                        },
                        enabled = puedeEnviar,
                        shape = RoundedCornerShape(28.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                    ) {
                        if (autenticando) {
                            CircularProgressIndicator(
                                Modifier.size(18.dp),
                                strokeWidth = 2.dp,
                                color = Color.White,
                            )
                            Spacer(Modifier.width(10.dp))
                        }
                        Text(
                            if (modoRegistro) "Crear cuenta" else "Entrar",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }

                    Spacer(Modifier.height(6.dp))
                    TextButton(onClick = { modoRegistro = !modoRegistro }) {
                        Text(
                            if (modoRegistro) {
                                "Ya tengo cuenta"
                            } else {
                                "Crear una cuenta"
                            },
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }

                    if (!modoRegistro) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Al entrar con internet, SENTI descargará automáticamente " +
                                "el mapa y los datos básicos para usarlos sin conexión.",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                        )
                    }

                    // §26: si ya hubo un login en este teléfono, se puede
                    // entrar sin red. No se comprueba nada contra el servidor
                    // —no habría con qué— y por eso solo lleva al mapa
                    // descargado y a las guías, nunca al chat.
                    if (sesionGuardada != null) {
                        Spacer(Modifier.height(10.dp))
                        OutlinedButton(
                            onClick = onEntrarSinConexion,
                            shape = RoundedCornerShape(28.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(52.dp),
                        ) {
                            Icon(
                                Icons.Filled.CloudOff,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp),
                            )
                            Spacer(Modifier.width(10.dp))
                            Text(
                                "Usar mapa sin internet",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "Última sesión de ${sesionGuardada.email}, guardada el " +
                                formatearFechaHora(sesionGuardada.guardadaAt) + ".",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                        )
                    } else if (!hayRed) {
                        // Sin red y sin sesión guardada no se puede entrar, y
                        // callarlo deja a alguien reintentando un formulario
                        // que no puede funcionar. El §11.3 aplicado a la
                        // propia app: se declara la causa, no se deja adivinar.
                        Spacer(Modifier.height(14.dp))
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(Radios.tarjeta),
                        ) {
                            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
                                Icon(
                                    Icons.Filled.CloudOff,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.size(18.dp),
                                )
                                Spacer(Modifier.width(10.dp))
                                Text(
                                    "No hay conexión y este teléfono todavía no ha " +
                                        "iniciado sesión ninguna vez. El modo sin " +
                                        "conexión necesita una sesión guardada, y solo " +
                                        "se guarda al entrar con internet al menos una " +
                                        "vez.\n\nMientras tanto: 115 Defensa Civil · " +
                                        "116 Bomberos · 106 SAMU.",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }

            Spacer(Modifier.height(20.dp))
            // §12: SENTI no reemplaza al canal oficial. Va aquí, en la primera
            // pantalla, y no escondido en un pie.
            Text(
                "SENTI no reemplaza al canal oficial del Estado.\n" +
                    "Emergencias: 115 Defensa Civil · 116 Bomberos · 106 SAMU",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.labelMedium,
                textAlign = TextAlign.Center,
            )
            }
        }
    }
}

/**
 * Campos tipo píldora: relleno suave y sin borde marcado.
 *
 * Un borde de 1 dp alrededor de cada campo multiplica las líneas en pantalla y
 * compite con la información. El relleno delimita igual sin añadir contorno.
 */
@Composable
private fun coloresCampoPildora() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
    unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
    focusedBorderColor = MaterialTheme.colorScheme.primary,
    unfocusedBorderColor = Color.Transparent,
)

/**
 * Antes usaba un rosa fijo (`0xFFFFDAD6`) igual en claro y en oscuro. Coincide
 * con el `errorContainer` por defecto en modo claro, pero en modo oscuro ese
 * rosa brillante sobre un fondo casi negro deslumbra en vez de avisar. El
 * color del tema resuelve el contraste correcto en los dos modos (§31.2).
 */
@Composable
private fun AvisoError(texto: String) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(Radios.chip),
    ) {
        Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.Warning,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onErrorContainer,
            )
            Spacer(Modifier.width(8.dp))
            Text(
                texto,
                color = MaterialTheme.colorScheme.onErrorContainer,
                style = MaterialTheme.typography.labelMedium,
            )
        }
    }
}

@Composable
private fun BannerSinConexion(sincronizadoAt: String?) {
    Surface(color = COLOR_SIN_CONEXION, shape = RoundedCornerShape(Radios.chip)) {
        Column(Modifier.fillMaxWidth().padding(10.dp)) {
            Text(
                "MODO SIN CONEXIÓN",
                color = Color.White,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelMedium,
            )
            // §26: "muestra siempre la fecha de última sincronización".
            Text(
                sincronizadoAt?.let { "Última actualización: $it" }
                    ?: "No hay información descargada en este dispositivo.",
                color = Color.White,
                style = MaterialTheme.typography.labelMedium,
            )
        }
    }
}


/**
 * Burbuja de mensaje.
 *
 * Sigue el patrón de las referencias: del usuario a la derecha en azul sólido,
 * de SENTI a la izquierda en gris claro, esquinas asimétricas —la que apunta al
 * emisor queda casi recta— y la hora fuera de la burbuja, en pequeño.
 *
 * La franja de urgencia solo aparece cuando hay algo que advertir. Antes salía
 * un encabezado "INFORMACIÓN" verde en cada respuesta, incluido un saludo, y
 * una etiqueta que aparece siempre deja de leerse: cuando llegue la que dice
 * EMERGENCIA no la distinguirá nadie (§12, §18).
 */
@Composable
private fun BurbujaMensaje(
    m: Mensaje,
    hayMapaPropio: Boolean = false,
    onAbrirMapa: (com.example.senti.data.RutaCalculada) -> Unit = {},
) {
    val esUrgente = m.urgencia == "rojo" || m.urgencia == "naranja"

    if (m.esUsuario) {
        // La miniatura se decodifica una vez por mensaje y se recuerda: sin
        // `remember` se rehace en cada recomposición del chat.
        val miniatura = remember(m.imagenBase64) {
            m.imagenBase64?.let { b64 ->
                runCatching {
                    val bytes = Base64.decode(b64, Base64.NO_WRAP)
                    val opciones = BitmapFactory.Options().apply { inSampleSize = 2 }
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opciones)
                }.getOrNull()
            }
        }

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Column(horizontalAlignment = Alignment.End, modifier = Modifier.widthIn(max = 300.dp)) {
                miniatura?.let { bmp ->
                    Surface(
                        shape = RoundedCornerShape(
                            Radios.burbuja, Radios.burbuja, Radios.burbujaPico, Radios.burbuja,
                        ),
                        shadowElevation = 2.dp,
                    ) {
                        Image(
                            bitmap = bmp.asImageBitmap(),
                            contentDescription = "Foto que enviaste",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .widthIn(max = 240.dp)
                                .heightIn(max = 260.dp),
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                }
                if (m.texto.isNotBlank()) {
                    Surface(
                        color = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary,
                        shape = RoundedCornerShape(
                            Radios.burbuja, Radios.burbuja, Radios.burbujaPico, Radios.burbuja,
                        ),
                    ) {
                        Text(
                            m.texto,
                            Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
        return
    }

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        // Avatar de SENTI. Sin él las respuestas parecían tarjetas de un panel
        // y no la voz de alguien contestando, y esa diferencia importa: lo que
        // llega por aquí son instrucciones que hay que seguir, no resultados
        // que consultar.
        Surface(
            color = MaterialTheme.colorScheme.primary,
            shape = CircleShape,
            modifier = Modifier.size(32.dp),
        ) {
            Image(
                painter = painterResource(R.mipmap.ic_launcher_foreground),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Spacer(Modifier.width(9.dp))
        Column(modifier = Modifier.widthIn(max = 300.dp)) {
            Surface(
                color = MaterialTheme.colorScheme.surface,
                shape = RoundedCornerShape(
                    Radios.burbujaPico, Radios.burbuja, Radios.burbuja, Radios.burbuja,
                ),
                shadowElevation = 1.dp,
            ) {
                Column {
                    if (esUrgente || m.sinConexion) {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .background(
                                    if (m.sinConexion) EstadoNeutro else colorUrgencia(m.urgencia)
                                )
                                .padding(horizontal = 12.dp, vertical = 5.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(
                                if (m.sinConexion) Icons.Filled.CloudOff else Icons.Filled.Warning,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(13.dp),
                            )
                            Spacer(Modifier.width(6.dp))
                            Text(
                                if (m.sinConexion) "SIN CONEXIÓN" else etiquetaUrgencia(m.urgencia),
                                color = Color.White,
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                    }
                    Text(
                        m.texto,
                        Modifier.padding(horizontal = 16.dp, vertical = 13.dp),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    m.ruta?.let {
                        AccionesRuta(it, hayMapaPropio) { onAbrirMapa(it) }
                    }
                    m.lugar?.let { AbrirEnMaps(it, "Destino solicitado") }
                    m.lugarSugerido?.let { AbrirEnMaps(it, "Sugerencia más cercana") }
                    if (m.fuentes.isNotEmpty()) FuentesDesplegables(m.fuentes)
                }
            }
            if (m.plantillaFija && !m.sinConexion) {
                // §29: se declara cuándo la respuesta no consultó ninguna
                // fuente. Va debajo y en gris, no como etiqueta destacada: es
                // un matiz de procedencia, no una advertencia.
                Text(
                    "Respuesta inmediata, sin consultar fuentes",
                    Modifier.padding(start = 6.dp, top = 3.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * §24.1 y §32.2: la respuesta cita fuente y hora, pero no dentro del texto.
 *
 * El backend las manda aparte cuando el canal tiene interfaz; en WhatsApp y en
 * modo ligero siguen viajando en el cuerpo, porque allí no hay dónde pulsar
 * (§7.3). Aquí se muestran bajo un control para que la respuesta se lea limpia
 * sin perder la trazabilidad.
 *
 * Se muestra el hash de origen cuando existe: es la medida del §12 contra la
 * suplantación de alertas oficiales, y sirve de poco si nadie puede verlo.
 */
@Composable
private fun FuentesDesplegables(fuentes: List<com.example.senti.data.Fuente>) {
    var abierto by remember { mutableStateOf(false) }
    Column(Modifier.padding(start = 12.dp, end = 12.dp, bottom = 10.dp)) {
        TextButton(
            onClick = { abierto = !abierto },
            contentPadding = PaddingValues(horizontal = 4.dp, vertical = 0.dp),
        ) {
            Icon(
                if (abierto) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(4.dp))
            Text(
                if (fuentes.size == 1) "Ver la fuente" else "Ver las ${fuentes.size} fuentes",
                style = MaterialTheme.typography.labelMedium,
            )
        }
        if (abierto) {
            fuentes.forEach { f ->
                Column(Modifier.padding(start = 8.dp, top = 6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        f.confianza?.let { c ->
                            Surface(
                                color = colorConfianzaFuente(c),
                                shape = RoundedCornerShape(50),
                            ) {
                                Text(
                                    c.replace("_", " "),
                                    color = Color.White,
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
                                )
                            }
                            Spacer(Modifier.width(6.dp))
                        }
                        Text(
                            f.institucion ?: "Fuente sin identificar",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    f.url?.let {
                        Text(it, style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    f.consultadaAt?.let {
                        Text(
                            "Consultada: ${it.take(16).replace('T', ' ')}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    f.sha256?.let {
                        // §12: hash del contenido oficial ingerido.
                        Text(
                            "Huella del documento: ${it.take(16)}…",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

/** §12: los cuatro niveles, en color y en texto. */
private fun colorConfianzaFuente(confianza: String): Color = when (confianza) {
    "OFICIAL" -> COLOR_VERDE
    "MUNICIPAL" -> Color(0xFF0B4A6F)
    "VALIDADO" -> COLOR_AMARILLO
    else -> COLOR_SIN_CONEXION
}

/**
 * Acceso al mapa cuando hay una ruta (§7.3).
 *
 * Abre la app de mapas con un intent `geo:`, **no con un enlace en el texto**.
 * La diferencia importa: el §12 prohíbe enviar enlaces de dominios ajenos
 * porque un enlace en un mensaje se puede suplantar. Un intent con coordenadas
 * no viaja como texto y no se puede falsificar en tránsito.
 *
 * Los pasos ya están escritos en la respuesta. Este botón es una mejora: si el
 * usuario no tiene app de mapas, o no quiere gastar datos abriéndola, la
 * instrucción sigue completa sin pulsarlo.
 */
/**
 * Botón para abrir un sitio concreto en Google Maps, con la ruta ya trazada.
 *
 * §7.3: el texto de la respuesta ya dice el nombre, la dirección y a cuántos
 * metros está. Esto es una mejora encima de una instrucción que ya está
 * completa — si Maps no está instalado o el intent falla, no se pierde nada.
 *
 * Se usa `google.navigation:` con modo a pie: casi toda evacuación de este
 * sistema es caminando, y darle a alguien una ruta en coche por una avenida
 * inundada es peor que no darle ninguna.
 */
/**
 * Mini mapa para marcar dónde ocurre lo que se reporta.
 *
 * Sustituye a dos campos de latitud y longitud. Nadie sabe sus coordenadas, y
 * pedírselas a quien está viendo un huaico es pedirle que abra otra aplicación,
 * copie dos números y vuelva. Se toca el mapa y ya está.
 *
 * Se puede volver a tocar tantas veces como haga falta: el marcador se mueve al
 * último punto. Equivocarse marcando es lo normal —el dedo tapa justo lo que
 * hay que señalar— y obligar a borrar un campo para corregir es una fricción
 * que acaba en reportes con la ubicación mal puesta.
 */
@Composable
private fun MapaDeReporte(
    lat: Double?,
    lon: Double?,
    onMarcar: (LatLng) -> Unit,
) {
    val marcado = if (lat != null && lon != null) LatLng(lat, lon) else null
    val camara = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(marcado ?: LatLng(-12.05, -77.04), 15f)
    }

    Text(
        "¿Dónde está ocurriendo?",
        style = MaterialTheme.typography.labelLarge,
        modifier = Modifier.padding(bottom = 6.dp),
    )
    Surface(
        shape = RoundedCornerShape(Radios.boton),
        tonalElevation = 1.dp,
        modifier = Modifier.fillMaxWidth().height(ALTURA_MAPA_SELECCION),
    ) {
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = camara,
            uiSettings = MapUiSettings(
                rotationGesturesEnabled = false,
                tiltGesturesEnabled = false,
                mapToolbarEnabled = false,
                zoomControlsEnabled = false,
            ),
            onMapClick = onMarcar,
        ) {
            marcado?.let { Marker(state = MarkerState(it), title = "Aquí") }
        }
    }
    Text(
        if (marcado == null) "Toca el mapa para marcar el punto."
        else "Toca otra vez si quieres corregirlo.",
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 6.dp),
    )
}

@Composable
private fun AbrirEnMaps(lugar: com.example.senti.data.Lugar, etiqueta: String) {
    val contexto = LocalContext.current
    Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp)) {
        Text(etiqueta, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            Button(
                onClick = {
                    val destino = "${lugar.lat},${lugar.lon}"
                    val intento = Intent(
                        Intent.ACTION_VIEW,
                        "google.navigation:q=$destino&mode=w".toUri(),
                    ).setPackage("com.google.android.apps.maps")
                    val alternativa = Intent(
                        Intent.ACTION_VIEW,
                        "geo:$destino?q=$destino(${lugar.nombre.orEmpty()})".toUri(),
                    )
                    runCatching { contexto.startActivity(intento) }
                        .recoverCatching { contexto.startActivity(alternativa) }
                },
                shape = RoundedCornerShape(Radios.boton),
                modifier = Modifier.weight(1f),
            ) {
                Icon(Icons.Filled.MyLocation, contentDescription = "Cómo llegar", Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Cómo llegar")
            }
            OutlinedButton(
                onClick = {
                    val destino = "${lugar.lat},${lugar.lon}"
                    val intento = Intent(
                        Intent.ACTION_VIEW,
                        "geo:$destino?q=$destino(${lugar.nombre.orEmpty()})".toUri(),
                    )
                    contexto.startActivity(intento)
                },
                shape = RoundedCornerShape(Radios.boton),
                modifier = Modifier.weight(1f),
            ) {
                Icon(Icons.Filled.Map, contentDescription = "Ver mapa", Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Ver mapa")
            }
        }
        if (lugar.ubicacionReferencial) {
            // §20.2: OSM acredita que existe y dónde, no que el municipio lo
            // haya designado ni que esté abierto ahora. Callarlo sería
            // presentar como validado algo que no lo está.
            Text(
                "Ubicación referencial: no está confirmada por el municipio.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

@Composable
private fun AccionesRuta(
    ruta: com.example.senti.data.RutaCalculada,
    hayMapaPropio: Boolean = false,
    onAbrirMapa: () -> Unit = {},
) {
    val context = LocalContext.current
    val hayDestino = ruta.destinoLat != null && ruta.destinoLon != null

    Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.Place,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(6.dp))
            Text(
                buildString {
                    ruta.destino?.let { append(it) } ?: append("Ruta de salida")
                    ruta.distanciaM?.let { append(" · ${it / 1000.0} km".replace(".0 km", " km")) }
                    ruta.duracionS?.let { append(" · ${it / 60} min") }
                },
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (hayDestino) {
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    // El mapa propio enseña además dónde está la persona y qué
                    // está cortado; una app de mapas externa solo sabe llevar
                    // al destino, y no conoce ninguno de los cierres que
                    // decidieron esta ruta. Si no hay mapa base publicado se
                    // cae al intent, que sigue siendo mejor que nada.
                    if (hayMapaPropio) {
                        onAbrirMapa()
                    } else {
                        val etiqueta = Uri.encode(ruta.destino ?: "Destino")
                        val geo = Uri.parse(
                            "geo:${ruta.destinoLat},${ruta.destinoLon}" +
                                "?q=${ruta.destinoLat},${ruta.destinoLon}($etiqueta)"
                        )
                        runCatching {
                            context.startActivity(Intent(Intent.ACTION_VIEW, geo))
                        }
                    }
                },
                shape = RoundedCornerShape(22.dp),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            ) {
                Icon(Icons.Filled.Map, contentDescription = null, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(7.dp))
                Text(
                    if (hayMapaPropio) "Ver el mapa de la ruta" else "Ver la ruta en el mapa",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Spacer(Modifier.height(4.dp))
            // §7.3, dicho al usuario y no solo respetado en el código.
            Text(
                "Los pasos de arriba bastan aunque no abras el mapa.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
