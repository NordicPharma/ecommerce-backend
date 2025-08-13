from ninja import Schema
from typing import Optional, Literal
from decimal import Decimal
from datetime import datetime

class PaymentInitiateSchema(Schema):
    order_id: int
    payment_method: Literal['crypto_btc', 'crypto_eth', 'crypto_usdt']

class CryptoPaymentResponseSchema(Schema):
    payment_id: int
    order_number: str
    amount_eur: Decimal
    crypto_amount: Decimal
    crypto_currency: str
    wallet_address: str
    expires_at: datetime
    qr_code: str

class PaymentStatusSchema(Schema):
    payment_id: int
    status: str
    confirmations: int
    required_confirmations: int
    transaction_hash: Optional[str]
    confirmed_at: Optional[datetime]

class WebhookPayloadSchema(Schema):
    payment_id: int
    transaction_hash: str
    confirmations: int
    amount: Decimal
    from_address: str