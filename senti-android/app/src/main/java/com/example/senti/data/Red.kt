package com.example.senti.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities

/**
 * ¿Hay red ahora mismo?
 *
 * Responde a "el sistema cree que hay internet", que **no** es lo mismo que
 * "SENTI responde". Se usa solo para decidir si tiene sentido ofrecer el botón
 * de actualizar; nunca para dar por buena una respuesta que no ha llegado. Lo
 * que decide de verdad si hay servicio es que la petición funcione, y eso lo
 * comprueba quien la hace.
 *
 * `NET_CAPABILITY_VALIDATED` es la diferencia entre estar conectado a un wifi y
 * que ese wifi llegue a algún sitio. Sin ese matiz, el portal cautivo de un
 * hotel o una antena saturada cuentan como conexión y la app se queda
 * esperando a un servidor inalcanzable.
 */
object Red {

    fun hay(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val activa = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(activa) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
}
