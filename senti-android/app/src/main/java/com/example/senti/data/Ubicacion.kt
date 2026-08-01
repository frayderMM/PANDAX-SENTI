package com.example.senti.data

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import androidx.core.content.ContextCompat

/**
 * Ubicación del dispositivo (§13.2).
 *
 * Usa `LocationManager` de la plataforma y no Google Play Services: es una
 * dependencia menos, funciona en equipos sin servicios de Google —frecuentes en
 * gama baja, que es el parque real del usuario objetivo— y para lo que hace
 * falta aquí basta.
 *
 * Solo se pide `ACCESS_COARSE_LOCATION` de partida. El §13.2 dice que la
 * ubicación va "a nivel de zona aproximada por defecto" y que la exacta solo se
 * pide para calcular una ruta; pedir precisión fina desde el primer momento
 * contradiría eso.
 */
object Ubicacion {

    val PERMISOS = arrayOf(
        Manifest.permission.ACCESS_COARSE_LOCATION,
        Manifest.permission.ACCESS_FINE_LOCATION,
    )

    fun hayPermiso(context: Context): Boolean =
        PERMISOS.any {
            ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
        }

    /**
     * Última ubicación conocida, o null.
     *
     * No se pide una lectura nueva del GPS a propósito: obtener una fija puede
     * tardar decenas de segundos bajo techo o con lluvia, justo cuando alguien
     * necesita respuesta. La última conocida sirve para saber en qué distrito
     * está, que es lo que el backend usa para filtrar alertas y reportes.
     */
    fun ultimaConocida(context: Context): Pair<Double, Double>? {
        if (!hayPermiso(context)) return null
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
            ?: return null
        val proveedores = listOf(
            LocationManager.GPS_PROVIDER,
            LocationManager.NETWORK_PROVIDER,
            LocationManager.PASSIVE_PROVIDER,
        )
        var mejor: Location? = null
        for (p in proveedores) {
            val loc = runCatching { lm.getLastKnownLocation(p) }.getOrNull() ?: continue
            if (mejor == null || loc.time > mejor.time) mejor = loc
        }
        return mejor?.let { it.latitude to it.longitude }
    }
}
