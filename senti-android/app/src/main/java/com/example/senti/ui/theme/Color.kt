package com.example.senti.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Paleta de SENTI.
 *
 * La regla que la ordena: **el color es información, no decoración.**
 *
 * El §12 obliga a distinguir cuatro niveles de confianza y el §18 cuatro de
 * urgencia, todos por color además de por texto. Si la interfaz ya usa verde,
 * ámbar y rojo para adornar cabeceras y botones, cuando aparece un rojo de
 * emergencia real no destaca: se lee como un elemento más de la marca.
 *
 * Por eso la base es neutra y fría, y el color saturado queda reservado a los
 * estados. Es también la razón de que no haya degradados de varios tonos: un
 * gradiente teal-verde-ámbar recorre justamente los tres colores con los que el
 * sistema comunica gravedad.
 */

// Marca: tomada del propio icono de SENTI, que va de un índigo vivo a un
// violeta. Son tonos contiguos, no un arcoíris: el azul-violeta identifica a
// la app y el rojo, el ámbar y el verde siguen significando gravedad.
val SentiPrimary = Color(0xFF3B5BF5)
val SentiOnPrimary = Color(0xFFFFFFFF)
val SentiPrimaryContainer = Color(0xFFE0E7FF)
val SentiOnPrimaryContainer = Color(0xFF16218C)

// Acentos del degradado del icono.
val SentiVioleta = Color(0xFF8B3BF5)
val SentiCeleste = Color(0xFF22B8F0)
val SentiCelesteProfundo = Color(0xFF1E6BE8)

// Superficies: grises fríos, alto contraste.
val SentiBackground = Color(0xFFF5F7FE)
val SentiSurface = Color(0xFFFFFFFF)
val SentiSurfaceVariant = Color(0xFFEEF1FE)
val SentiOutline = Color(0xFFD5DCF5)
val SentiText = Color(0xFF0F172A)
val SentiTextMuted = Color(0xFF5A6B80)

// Modo oscuro.
val SentiPrimaryLight = Color(0xFF9DB0FF)
val SentiBackgroundDark = Color(0xFF0D1420)
val SentiSurfaceDark = Color(0xFF141D2B)
val SentiSurfaceVariantDark = Color(0xFF1E293B)
val SentiTextDark = Color(0xFFE8EDF3)
val SentiTextMutedDark = Color(0xFF9AA9BC)

/**
 * Estados: los únicos colores saturados de la aplicación.
 *
 * Contrastan sobre blanco para cumplir AA (§31.2). Alguien mirando el teléfono
 * bajo la lluvia tiene que distinguirlos, y el color nunca va solo: siempre lo
 * acompaña el texto del nivel.
 */
val EstadoRojo = Color(0xFFB3261E)
val EstadoVerde = Color(0xFF1B5E20)
val EstadoNeutro = Color(0xFF52606D)
