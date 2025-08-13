from django.db import models
from django.contrib.auth import get_user_model
from apps.orders.models import Order

User = get_user_model()

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('crypto_btc', 'Bitcoin'),
        ('crypto_eth', 'Ethereum'),
        ('crypto_usdt', 'USDT'),
        ('stripe', 'Tarjeta de Crédito'),
        ('paypal', 'PayPal'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('confirmed', 'Confirmado'),
        ('failed', 'Fallido'),
        ('expired', 'Expirado'),
        ('refunded', 'Reembolsado'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='EUR')
    
    # Para pagos crypto
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    crypto_currency = models.CharField(max_length=10, blank=True)
    wallet_address = models.CharField(max_length=200, blank=True)
    transaction_hash = models.CharField(max_length=200, blank=True)
    confirmations = models.IntegerField(default=0)
    required_confirmations = models.IntegerField(default=3)
    
    # Para otros métodos de pago
    external_id = models.CharField(max_length=200, blank=True)  # Stripe payment intent, PayPal order id, etc.
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.id} - {self.order.order_number}"

class CryptoWallet(models.Model):
    """Wallets generadas para recibir pagos"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='wallets')
    currency = models.CharField(max_length=10)
    address = models.CharField(max_length=200, unique=True)
    private_key_encrypted = models.TextField()  # Encriptado con Fernet
    derivation_path = models.CharField(max_length=100)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'crypto_wallets'