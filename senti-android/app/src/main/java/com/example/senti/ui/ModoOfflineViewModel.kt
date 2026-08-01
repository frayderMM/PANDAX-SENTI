package com.example.senti.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.senti.data.AlmacenZona
import com.example.senti.data.EstiloOffline
import com.example.senti.data.Guias
import com.example.senti.data.LecturaZona
import com.example.senti.data.PackGuias
import com.example.senti.data.PaqueteZona
import com.example.senti.data.Red
import com.example.senti.data.ResultadoSync
import com.example.senti.data.RutaGuardada
import com.example.senti.data.SesionLocal
import com.example.senti.data.SesionSegura
import com.example.senti.data.SincronizadorOffline
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class EstadoOffline(
    /** Si está puesto, la app entera es el mapa sin conexión y nada más. */
    val activo: Boolean = false,
    val paquete: PaqueteZona? = null,
    /** Por qué no hay paquete utilizable: corrupto, de otra versión… */
    val motivoSinPaquete: String? = null,
    val guias: PackGuias? = null,
    /** Packs de teselas ya copiados, o null si el APK no trae el nacional. */
    val packs: EstiloOffline.Packs? = null,
    val sincronizando: Boolean = false,
    val hayRed: Boolean = false,
    /** Sesión guardada del último login online, si la hay. */
    val sesion: SesionLocal? = null,
    val avisoSync: String? = null,
)

/**
 * Estado del modo sin conexión.
 *
 * Va en su propio ViewModel y no dentro de [SentiViewModel] por la misma razón
 * por la que la pantalla no comparte nada con el resto: son dos mundos. Este
 * no habla con el modelo, no publica reportes y no necesita sesión viva. Lo
 * único que comparte con el otro es de dónde salió la sesión.
 */
class ModoOfflineViewModel(app: Application) : AndroidViewModel(app) {

    private val almacen = AlmacenZona(app.filesDir)
    private val sesionSegura = SesionSegura(app)
    private val sincronizador = SincronizadorOffline(almacen)

    private val _estado = MutableStateFlow(EstadoOffline())
    val estado: StateFlow<EstadoOffline> = _estado.asStateFlow()

    init {
        viewModelScope.launch {
            // Todo esto toca disco: leer el paquete, parsear las guías y, la
            // primera vez, copiar decenas de megas de teselas del APK. En el
            // hilo principal eso es un ANR garantizado en un teléfono de gama
            // baja, que es el objetivo de esta app.
            val cargado = withContext(Dispatchers.IO) {
                Triple(
                    almacen.leer(),
                    Guias.cargar(app),
                    EstiloOffline.prepararPacks(app),
                )
            }
            val (lectura, guias, packs) = cargado
            _estado.update {
                it.copy(
                    paquete = (lectura as? LecturaZona.Ok)?.paquete,
                    motivoSinPaquete = (lectura as? LecturaZona.Corrupto)?.motivo,
                    guias = guias,
                    packs = packs,
                    hayRed = Red.hay(app),
                    sesion = sesionSegura.leer(),
                )
            }
        }
    }

    /** ¿Se puede entrar sin conexión? Solo con una sesión que existió de verdad. */
    fun haySesionGuardada(): Boolean = _estado.value.sesion != null

    fun entrar() {
        _estado.update { it.copy(activo = true, hayRed = Red.hay(getApplication())) }
    }

    fun salir() {
        _estado.update { it.copy(activo = false, avisoSync = null) }
    }

    fun refrescarRed() {
        _estado.update { it.copy(hayRed = Red.hay(getApplication())) }
    }

    fun descartarAviso() {
        _estado.update { it.copy(avisoSync = null) }
    }

    /**
     * Descarga la zona de 10 km² alrededor del punto.
     *
     * Si falla, el estado NO se toca salvo para poner el aviso: el paquete que
     * ya estaba cargado sigue en pantalla y el del disco sigue en el disco.
     */
    fun sincronizar(lat: Double?, lon: Double?, rutas: List<RutaGuardada> = emptyList()) {
        if (lat == null || lon == null) {
            _estado.update {
                it.copy(
                    avisoSync = "Hace falta tu ubicación para saber qué zona descargar.",
                )
            }
            return
        }
        if (_estado.value.sincronizando) return

        viewModelScope.launch {
            _estado.update { it.copy(sincronizando = true, avisoSync = null) }
            val resultado = withContext(Dispatchers.IO) {
                sincronizador.sincronizar(lat, lon, rutas)
            }
            _estado.update { e ->
                when (resultado) {
                    is ResultadoSync.Ok -> e.copy(
                        sincronizando = false,
                        paquete = resultado.paquete,
                        motivoSinPaquete = null,
                        avisoSync = resultado.paquete.contenido.fuentesFallidas
                            .takeIf { it.isNotEmpty() }
                            ?.let { "Descargado, pero sin: ${it.joinToString(", ")}." }
                            ?: "Zona actualizada.",
                    )
                    is ResultadoSync.Error -> e.copy(
                        sincronizando = false,
                        avisoSync = resultado.motivo,
                    )
                }
            }
        }
    }

    /** Guarda la sesión tras un login online correcto. Nunca la contraseña. */
    fun recordarSesion(sesion: SesionLocal) {
        sesionSegura.guardar(sesion)
        _estado.update { it.copy(sesion = sesion) }
    }

    /**
     * Cierre de sesión explícito.
     *
     * Borra la sesión pero **no** el paquete ni las guías. Cerrar sesión es
     * "este no soy yo", no "bórrame el mapa de evacuación del barrio".
     */
    fun olvidarSesion() {
        sesionSegura.borrar()
        _estado.update { it.copy(sesion = null, activo = false) }
    }
}
