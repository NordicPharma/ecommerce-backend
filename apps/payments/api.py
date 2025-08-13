from ninja import Router
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import qrcode
import io
import base64
from decimal import Decimal
from .models import Payment, CryptoWallet
from .schemas import (
    PaymentInitiateSchema, CryptoPaymentResponseSchema,
    PaymentStatusSchema, WebhookPayloadSchema
)
from .crypto.bitcoin import BitcoinPaymentProcessor
from .crypto.ethereum import EthereumPaymentProcessor
from apps.orders.models import Order
from apps.utils.auth import JWTAuth
import logging

router = Router(tags=["payments"])
logger = logging.getLogger(__name__)

@router.post("/initiate", auth=JWTAuth(), response=CryptoPaymentResponseSchema)
@transaction.atomic
def initiate_payment(request, data: PaymentInitiateSchema):
    """Inicia un pago con criptomonedas"""
    # Obtener orden
    order = get_object_or_404(Order, id=data.order_id, user=request.auth)
    
    # Verificar que no tenga ya un pago
    if hasattr(order, 'payment') and order.payment.status != 'failed':
        return router.create_response(
            request,
            {"detail": "Esta orden ya tiene un pago asociado"},
            status=400
        )
    
    # Determinar procesador según método de pago
    if data.payment_method == 'crypto_btc':
        processor = BitcoinPaymentProcessor()
        crypto_currency = 'BTC'
    elif data.payment_method in ['crypto_eth', 'crypto_usdt']:
        processor = EthereumPaymentProcessor()
        crypto_currency = 'ETH' if data.payment_method == 'crypto_eth' else 'USDT'
    else:
        return router.create_response(
            request,
            {"detail": "Método de pago no soportado"},
            status=400
        )
    
    # Generar wallet
    wallet_data = processor.generate_wallet()
    
    # Calcular cantidad en crypto
    crypto_amount = processor.calculate_crypto_amount(order.total)
    
    # Crear pago
    payment = Payment.objects.create(
        order=order,
        user=request.auth,
        payment_method=data.payment_method,
        amount=order.total,
        currency='EUR',
        crypto_amount=crypto_amount,
        crypto_currency=crypto_currency,
        wallet_address=wallet_data['address'],
        expires_at=timezone.now() + timedelta(minutes=30)
    )
    
    # Guardar wallet (encriptar private key en producción)
    CryptoWallet.objects.create(
        payment=payment,
        currency=crypto_currency,
        address=wallet_data['address'],
        private_key_encrypted=wallet_data['private_key'],  # Encriptar esto!
        derivation_path=wallet_data.get('derivation_path', '')
    )
    
    # Generar QR code
    qr_data = f"{crypto_currency.lower()}:{wallet_data['address']}?amount={crypto_amount}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Iniciar monitoreo de blockchain
    from apps.payments.tasks import monitor_crypto_payment
    monitor_crypto_payment.delay(payment.id)
    
    return {
        'payment_id': payment.id,
        'order_number': order.order_number,
        'amount_eur': order.total,
        'crypto_amount': crypto_amount,
        'crypto_currency': crypto_currency,
        'wallet_address': wallet_data['address'],
        'expires_at': payment.expires_at,
        'qr_code': f"data:image/png;base64,{qr_base64}"
    }

@router.get("/status/{payment_id}", auth=JWTAuth(), response=PaymentStatusSchema)
def get_payment_status(request, payment_id: int):
    """Obtiene el estado de un pago"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.auth)
    
    return {
        'payment_id': payment.id,
        'status': payment.status,
        'confirmations': payment.confirmations,
        'required_confirmations': payment.required_confirmations,
        'transaction_hash': payment.transaction_hash,
        'confirmed_at': payment.confirmed_at
    }

@router.post("/webhook/{provider}")
def payment_webhook(request, provider: str, data: WebhookPayloadSchema):
    """Webhook para recibir notificaciones de pagos"""
    # Verificar autenticidad del webhook (implementar según proveedor)
    
    try:
        payment = Payment.objects.get(id=data.payment_id)
        
        # Actualizar información del pago
        payment.transaction_hash = data.transaction_hash
        payment.confirmations = data.confirmations
        
        # Si tiene suficientes confirmaciones, marcar como confirmado
        if data.confirmations >= payment.required_confirmations:
            payment.status = 'confirmed'
            payment.confirmed_at = timezone.now()
            
            # Actualizar estado de la orden
            payment.order.status = 'paid'
            payment.order.paid_at = timezone.now()
            payment.order.save()
            
            # Enviar email de confirmación
            from apps.payments.tasks import send_payment_confirmation_email
            send_payment_confirmation_email.delay(payment.id)
        
        payment.save()
        
        return {"success": True}
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found: {data.payment_id}")
        return router.create_response(
            request,
            {"detail": "Payment not found"},
            status=404
        )
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return router.create_response(
            request,
            {"detail": "Internal error"},
            status=500
        )

@router.post("/simulate/{payment_id}", auth=JWTAuth())
def simulate_payment(request, payment_id: int):
    """Simula un pago exitoso (solo para desarrollo)"""
    if not settings.DEBUG:
        return router.create_response(
            request,
            {"detail": "Not available in production"},
            status=403
        )
    
    payment = get_object_or_404(Payment, id=payment_id, user=request.auth)
    
    # Simular pago confirmado
    payment.status = 'confirmed'
    payment.confirmations = payment.required_confirmations
    payment.transaction_hash = f"SIMULATED-{payment.id}"
    payment.confirmed_at = timezone.now()
    payment.save()
    
    # Actualizar orden
    payment.order.status = 'paid'
    payment.order.paid_at = timezone.now()
    payment.order.save()
    
    return {"success": True, "message": "Payment simulated successfully"}