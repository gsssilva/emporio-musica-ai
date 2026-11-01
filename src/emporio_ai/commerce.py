"""Commercial calculations in integer cents, independent of the language model."""

from __future__ import annotations


class PaymentRuleError(ValueError):
    pass


def discounted_price(price_cents: int, discount_bps: int = 0) -> int:
    if type(price_cents) is not int or price_cents < 0:
        raise ValueError("Preço deve ser um inteiro não negativo em centavos.")
    if type(discount_bps) is not int or not 0 <= discount_bps <= 10000:
        raise ValueError("Desconto inválido.")
    return (price_cents * (10000 - discount_bps) + 5000) // 10000


def quote_payment(
    price_cents: int,
    *,
    promotion_bps: int = 0,
    method: str,
    installments: int = 1,
) -> dict:
    current = discounted_price(price_cents, promotion_bps)
    if not isinstance(method, str) or method not in {"pix", "debit", "credit", "boleto"}:
        raise PaymentRuleError("Forma de pagamento desconhecida.")
    if type(installments) is not int or not 1 <= installments <= 12:
        raise PaymentRuleError("Número de parcelas deve ser um inteiro de 1 a 12.")
    if method != "credit" and installments != 1:
        raise PaymentRuleError("Parcelamento disponível somente no cartão de crédito.")
    pix_discount = method == "pix" and promotion_bps == 0
    total = discounted_price(current, 500) if pix_discount else current
    minimum = 8000 if 4 <= installments <= 6 else 10000 if installments >= 7 else 0
    if total < minimum * installments:
        raise PaymentRuleError("Valor por parcela inferior ao mínimo da faixa solicitada.")
    quotient, remainder = divmod(total, installments)
    amounts = [quotient + (index < remainder) for index in range(installments)]
    # The manual's exception below R$50 for 2-3 installments is ambiguous.
    needs_confirmation = 2 <= installments <= 3 and min(amounts) < 5000
    return {
        "method": method,
        "table_price_cents": price_cents,
        "promotion_bps": promotion_bps,
        "current_price_cents": current,
        "pix_discount_applied": pix_discount,
        "total_cents": total,
        "installments": installments,
        "installment_amounts_cents": amounts,
        "status": "needs_confirmation" if needs_confirmation else "quoted",
        "policy_sections": ["3", "3.1", "6.2"],
        "confirmation_reason": (
            "O manual contém uma exceção ambígua para parcelas abaixo de R$ 50 em até 3 vezes."
            if needs_confirmation else None
        ),
    }
