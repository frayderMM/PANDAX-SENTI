package com.example.senti.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

/** Tema de la app. Aparte del perfil y el paquete offline: es del dispositivo, no de la cuenta. */
enum class TemaApp { SISTEMA, CLARO, OSCURO }

private val Context.preferenciasDataStore by preferencesDataStore(name = "senti_preferencias")

class PreferenciasStore(private val context: Context) {

    private val claveTema = stringPreferencesKey("tema")

    suspend fun leerTema(): TemaApp {
        val guardado = context.preferenciasDataStore.data.first()[claveTema] ?: return TemaApp.SISTEMA
        return runCatching { TemaApp.valueOf(guardado) }.getOrDefault(TemaApp.SISTEMA)
    }

    suspend fun guardarTema(tema: TemaApp) {
        context.preferenciasDataStore.edit { it[claveTema] = tema.name }
    }
}
