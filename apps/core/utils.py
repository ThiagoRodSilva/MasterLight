"""Utils de uso transversal."""

import secrets
import string


def generate_code(length: int = 8) -> str:
    """Gera codigo alfanumerico randomico maiusculo (uso: tracking afiliado)."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def money_fmt(value) -> str:
    """Formata valor Decimal como moeda BR."""
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"
