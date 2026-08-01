package com.example.senti.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val EsquemaOscuro = darkColorScheme(
    primary = SentiPrimaryLight,
    onPrimary = SentiText,
    primaryContainer = SentiSurfaceVariantDark,
    onPrimaryContainer = SentiTextDark,
    background = SentiBackgroundDark,
    onBackground = SentiTextDark,
    surface = SentiSurfaceDark,
    onSurface = SentiTextDark,
    surfaceVariant = SentiSurfaceVariantDark,
    onSurfaceVariant = SentiTextMutedDark,
    outline = SentiTextMutedDark,
    error = EstadoRojo,
)

private val EsquemaClaro = lightColorScheme(
    primary = SentiPrimary,
    onPrimary = SentiOnPrimary,
    primaryContainer = SentiPrimaryContainer,
    onPrimaryContainer = SentiOnPrimaryContainer,
    background = SentiBackground,
    onBackground = SentiText,
    surface = SentiSurface,
    onSurface = SentiText,
    surfaceVariant = SentiSurfaceVariant,
    onSurfaceVariant = SentiTextMuted,
    outline = SentiOutline,
    error = EstadoRojo,
)

/**
 * El color dinámico de Android 12 queda desactivado a propósito.
 *
 * Tomaría los colores del fondo de pantalla del usuario, y en SENTI el color
 * significa gravedad (§12, §18). Un rojo de emergencia que cambia de tono según
 * la foto del móvil deja de ser una señal reconocible.
 */
@Composable
fun SENTITheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) EsquemaOscuro else EsquemaClaro,
        typography = Typography,
        shapes = FormasSenti,
        content = content,
    )
}
