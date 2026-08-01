package com.example.senti.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp

/**
 * Cabecera con borde inferior ondulado.
 *
 * La curva no es solo estética: separa la zona de marca de la de contenido sin
 * necesidad de una línea ni de un cambio brusco de color, y da altura visual a
 * la cabecera sin ocupar altura útil, porque el seno sube en los extremos y
 * baja en el centro, justo donde empieza el formulario.
 *
 * `alturaOnda` es la amplitud en píxeles. Valores altos comen espacio de
 * contenido; en pantallas pequeñas conviene dejarlo por debajo de 60.
 */
class FormaOnda(private val alturaOnda: Float = 46f) : Shape {
    override fun createOutline(
        size: Size,
        layoutDirection: LayoutDirection,
        density: Density,
    ): Outline {
        val path = Path().apply {
            moveTo(0f, 0f)
            lineTo(0f, size.height - alturaOnda)
            // Dos curvas encadenadas: la primera baja, la segunda sube. Una
            // sola quadratic da un arco simétrico que parece un error de
            // recorte; dos dan la ondulación de la referencia.
            cubicTo(
                size.width * 0.25f, size.height - alturaOnda * 2.4f,
                size.width * 0.62f, size.height + alturaOnda * 0.7f,
                size.width, size.height - alturaOnda * 1.1f,
            )
            lineTo(size.width, 0f)
            close()
        }
        return Outline.Generic(path)
    }
}

/**
 * Radios de esquina de SENTI.
 *
 * Material da 4/8/12 dp por defecto, que es la proporción de una interfaz de
 * escritorio de hace diez años. En un teléfono actual esos radios se leen como
 * "aplicación vieja" antes de que nadie haya leído una palabra, y una app que
 * parece abandonada no se abre en una emergencia.
 *
 * Los valores suben con el tamaño del elemento —una tarjeta grande aguanta 24
 * dp, un chip pequeño con 24 dp se convierte en una pastilla— y se quedan por
 * debajo del redondeo total salvo donde la pastilla es intencionada: el campo
 * de escribir y los chips de estado.
 */
object Radios {
    val chip = 12.dp
    val boton = 16.dp
    val campo = 18.dp
    val tarjeta = 22.dp
    val tarjetaGrande = 28.dp
    val hoja = 30.dp
    /** Burbuja del chat: tres esquinas redondas y una en pico, hacia quien habla. */
    val burbuja = 22.dp
    val burbujaPico = 6.dp
}

/** Formas de Material 3, para que los componentes las hereden sin repetirlas. */
val FormasSenti = Shapes(
    extraSmall = RoundedCornerShape(Radios.chip),
    small = RoundedCornerShape(Radios.boton),
    medium = RoundedCornerShape(Radios.tarjeta),
    large = RoundedCornerShape(Radios.tarjetaGrande),
    extraLarge = RoundedCornerShape(Radios.hoja),
)
