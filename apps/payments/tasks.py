from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import asyncio
from .models import Payment
from .crypto.bitcoin import BitcoinPaymentProcessor
from .crypto.ethereum import EthereumPaymentProcessor
import logging

logger = logging.getLogger(__name__)

@shared_task
def monitor_crypto_payment(payment_id):
    """Monitorea una dirección de crypto para detectar pagos"""
    try:
        payment = Payment.objects.get(id=payment_id)
        
        # Solo monitorear pagos pendientes y no expirados
        if payment.status != 'pending' or payment.expires_at < timezone.now():
            return
        
        # Seleccionar procesador
        if payment.crypto_currency == 'BTC':
            processor = BitcoinPaymentProcessor()
        else:
            processor = EthereumPaymentProcessor()
        
        # Callback cuando se detecta el pago
        async def payment_detected(tx_hash):
            payment.transaction_hash = tx_hash
            payment.status = 'processing'
            payment.save()
            
            # Continuar monitoreando confirmaciones
            monitor_transaction_confirmations.delay(payment.id)
        
        # Ejecutar monitoreo asíncrono
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            processor.monitor_address(
                payment.wallet_address,
                payment.crypto_amount,
                payment_detected
            )
        )
        
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found")
    except Exception as e:
        logger.error(f"Error monitoring payment {payment_id}: {str(e)}")
        # Reintentar en 30 segundos
        monitor_crypto_payment.apply_async(args=[payment_id], countdown=30)

@shared_task
def monitor_transaction_confirmations(payment_id):
    """Monitorea las confirmaciones de una transacción"""
    try:
        payment = Payment.objects.get(id=payment_id)
        
        if payment.status != 'processing' or not payment.transaction_hash:
            return
        
        # Seleccionar procesador
        if payment.crypto_currency == 'BTC':
            processor = BitcoinPaymentProcessor()
        else:
            processor = EthereumPaymentProcessor()
        
        # Verificar transacción
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tx_info = loop.run_until_complete(
            processor.check_transaction(payment.transaction_hash)
        )
        
        if tx_info:
            payment.confirmations = tx_info['confirmations']
            
            if tx_info['confirmations'] >= payment.required_confirmations:
                payment.status = 'confirmed'
                payment.confirmed_at = timezone.now()
                
                # Actualizar orden
                payment.order.status = 'paid'
                payment.order.paid_at = timezone.now()
                payment.order.save()
                
                # Enviar confirmación
                send_payment_confirmation_email.delay(payment.id)
            
            payment.save()
            
            # Si aún no tiene suficientes confirmaciones, verificar de nuevo
            if payment.status == 'processing':
                monitor_transaction_confirmations.apply_async(
                    args=[payment_id],
                    countdown=60  # Verificar cada minuto
                )
        
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found")
    except Exception as e:
        logger.error(f"Error monitoring confirmations for payment {payment_id}: {str(e)}")

@shared_task
def send_payment_confirmation_email(payment_id):
    """Envía email de confirmación de pago"""
    try:
        payment = Payment.objects.get(id=payment_id)
        
        # Aquí implementarías el envío de email
        # Por ejemplo con Django's send_mail o un servicio como SendGrid
        
        logger.info(f"Payment confirmation email sent for order {payment.order.order_number}")
        
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found")

@shared_task
def check_expired_payments():
    """Verifica pagos expirados y los marca como tal"""
    expired_payments = Payment.objects.filter(
        status='pending',
        expires_at__lt=timezone.now()
    )
    
    for payment in expired_payments:
        payment.status = 'expired'
        payment.save()
        
        # Liberar la wallet para reutilización futura
        payment.wallets.update(is_used=False)
    
    logger.info(f"Marked {expired_payments.count()} payments as expired")