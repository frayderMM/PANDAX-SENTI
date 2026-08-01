"""§13.2 y §13.5 — lo que el sistema NO guarda.

Estos tests no comprueban que algo funcione: comprueban que algo **no exista**.
Son los que fallan cuando alguien añade, con buena intención, un campo que
retiene un dato sin finalidad.
"""

from __future__ import annotations

from app.models import HouseholdProfile, Message, User


class TestImagenDelChat:
    """La foto enviada al chat vive en el móvil, no en el servidor."""

    def test_message_no_guarda_imagenes(self) -> None:
        """Se le pasa al modelo para describirla (§25) y se descarta.

        Distinto de la foto de un reporte, que sí se guarda porque un validador
        debe poder verla (§21.3) y el §13.5 le da 30 días. Una foto de chat no
        la revisa nadie después: retenerla sería guardar un dato sin finalidad
        (§13.2).
        """
        columnas = set(Message.__table__.columns.keys())
        prohibidas = {"imagen", "imagen_base64", "foto", "foto_url", "adjunto"}
        assert not (columnas & prohibidas), (
            f"Message no debe guardar imágenes; encontrado: {columnas & prohibidas}"
        )


class TestPerfilDelHogar:
    """§13.2: cantidad y condición, nunca identidad ni diagnóstico."""

    def test_no_guarda_nombres_ni_diagnosticos(self) -> None:
        columnas = set(HouseholdProfile.__table__.columns.keys())
        prohibidas = {
            "nombre_madre", "nombres", "diagnostico", "diagnosticos",
            "receta", "medicamentos_lista", "enfermedad",
        }
        assert not (columnas & prohibidas)

    def test_medicamentos_es_booleano(self) -> None:
        """Saber que hay que prepararlos basta para el plan (§17).

        Saber cuáles son no aporta nada y sí crea un dato de salud.
        """
        col = HouseholdProfile.__table__.columns["medicamentos_habituales"]
        assert col.type.python_type is bool

    def test_el_contacto_de_confianza_va_cifrado(self) -> None:
        """§13.2: solo el teléfono, cifrado, y sin nombre.

        Es dato personal de un tercero que no ha consentido nada.
        """
        columnas = set(HouseholdProfile.__table__.columns.keys())
        assert "contacto_confianza_telefono_cifrado" in columnas
        assert "contacto_confianza_nombre" not in columnas


class TestTelefono:
    def test_el_numero_no_se_guarda_en_claro(self) -> None:
        """§13.5: seudonimizado con hash."""
        columnas = set(User.__table__.columns.keys())
        assert "phone_pseudonym" in columnas
        assert "phone" not in columnas
        assert "telefono" not in columnas
