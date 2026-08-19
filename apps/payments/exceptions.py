"""Exceções customizadas para o domínio de pagamentos."""


class PaymentGatewayError(Exception):
    """Erro base para falhas no gateway de pagamento."""

    def __init__(self, message: str, provider: str = "", external_id: str = ""):
        super().__init__(message)
        self.provider = provider
        self.external_id = external_id


class PaymentValidationError(PaymentGatewayError):
    """Erro de validação de dados de pagamento (CPF, endereço, cartão vencido, etc.)."""

    pass


class InsufficientStockError(PaymentGatewayError):
    """Erro quando estoque é insuficiente para completar o pedido."""

    def __init__(self, message: str, product_id: str = "", requested_qty: int = 0, available_qty: int = 0):
        super().__init__(message)
        self.product_id = product_id
        self.requested_qty = requested_qty
        self.available_qty = available_qty


class TransactionNotFoundError(PaymentGatewayError):
    """Erro quando transação não é encontrada no banco local."""

    pass


class WebhookAuthenticationError(PaymentGatewayError):
    """Erro de autenticação de webhook (token ausente/inválido)."""

    pass


class WebhookPayloadError(PaymentGatewayError):
    """Erro de payload inválido no webhook (JSON malformado, campos obrigatórios ausentes)."""

    pass


class InvalidStatusTransitionError(PaymentGatewayError):
    """Erro quando tentativa de transição de status inválida é detectada."""

    def __init__(self, message: str, current_status: str = "", new_status: str = ""):
        super().__init__(message)
        self.current_status = current_status
        self.new_status = new_status


class ProfileIncompleteError(PaymentGatewayError):
    """Erro quando perfil do usuário está incompleto para realizar pagamento."""

    def __init__(self, message: str, missing_fields: list[str] | None = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


class SectionDisabledError(PaymentGatewayError):
    """Erro quando seção (loja/serviços/afiliados) está desabilitada no SiteSettings."""

    def __init__(self, message: str, section: str = ""):
        super().__init__(message)
        self.section = section


class GatewayNotConfiguredError(PaymentGatewayError):
    """Erro quando provider de pagamento não está configurado corretamente."""

    def __init__(self, message: str, provider: str = "", missing_config: list[str] | None = None):
        super().__init__(message, provider=provider)
        self.missing_config = missing_config or []


class CardTokenizationError(PaymentGatewayError):
    """Erro durante tokenização de cartão de crédito."""

    pass


class SubscriptionError(PaymentGatewayError):
    """Erro durante criação/gestão de assinatura recorrente."""

    pass


class CheckoutSessionError(PaymentGatewayError):
    """Erro durante criação de sessão de checkout hospedado."""

    pass
