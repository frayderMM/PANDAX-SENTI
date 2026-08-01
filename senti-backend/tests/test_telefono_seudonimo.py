"""El seudónimo del teléfono tiene que ser el mismo por los dos caminos (§10.1, §13.5).

El §10.1 promete que quien escribe por WhatsApp desde el número de su cuenta
recibe su rol y sus herramientas (§6). Esa promesa se sostiene solo si el
seudónimo calculado en el registro coincide con el calculado desde el
`remoteJid` que entrega Evolution, y **ahí no coincidían**: el registro recibe
nueve dígitos tecleados y WhatsApp entrega once con el código de país.

El fallo era invisible por diseño: nada reventaba, el titular de la cuenta
simplemente entraba como invitado y recibía información general. Justo la clase
de avería silenciosa que este sistema existe para no tener.
"""

from __future__ import annotations

from app.core.crypto import canonizar_telefono, pseudonymize_phone


class TestCanonizacion:
    def test_un_movil_peruano_recibe_su_codigo_de_pais(self):
        assert canonizar_telefono("987654321") == "51987654321"

    def test_da_igual_como_lo_escriba_la_persona(self):
        # Espacios, guiones y paréntesis son lo normal al teclear un número.
        for escrito in ("987 654 321", "987-654-321", "(987) 654 321", " 987654321 "):
            assert canonizar_telefono(escrito) == "51987654321", escrito

    def test_lo_que_ya_trae_codigo_de_pais_no_se_duplica(self):
        assert canonizar_telefono("51987654321") == "51987654321"
        assert canonizar_telefono("+51 987 654 321") == "51987654321"

    def test_el_formato_de_whatsapp_se_reduce_a_digitos(self):
        assert canonizar_telefono("51987654321@s.whatsapp.net") == "51987654321"

    def test_a_un_numero_que_no_encaja_no_se_le_inventa_prefijo(self):
        # Un fijo de Lima o un número extranjero: se dejan como están. Ponerle
        # el 51 a un número que no es un móvil peruano lo convertiría en otro
        # número distinto, y eso es peor que no reconocerlo.
        assert canonizar_telefono("014567890") == "014567890"
        assert canonizar_telefono("34612345678") == "34612345678"
        assert canonizar_telefono("") == ""


class TestSeudonimo:
    def test_el_registro_y_whatsapp_producen_el_mismo_seudonimo(self):
        """La prueba que da sentido a todo lo demás."""
        desde_la_app = pseudonymize_phone("987654321")
        desde_whatsapp = pseudonymize_phone("51987654321@s.whatsapp.net")

        assert desde_la_app == desde_whatsapp

    def test_el_mismo_numero_escrito_de_seis_formas_da_un_solo_seudonimo(self):
        formas = [
            "987654321",
            "987 654 321",
            "+51987654321",
            "51 987 654 321",
            "51987654321@s.whatsapp.net",
            "(+51) 987-654-321",
        ]
        seudonimos = {pseudonymize_phone(f) for f in formas}
        assert len(seudonimos) == 1, f"deberían ser el mismo: {seudonimos}"

    def test_dos_numeros_distintos_no_colisionan(self):
        assert pseudonymize_phone("987654321") != pseudonymize_phone("987654322")

    def test_el_numero_no_aparece_en_el_seudonimo(self):
        # §13.5: irreversible. Que el hash no contenga el número no demuestra
        # que sea irreversible, pero lo contrario sí demostraría que no lo es.
        seudonimo = pseudonymize_phone("987654321")
        assert "987654321" not in seudonimo
        assert "51987654321" not in seudonimo
        assert len(seudonimo) == 64  # SHA-256 en hexadecimal
