from bitcoinlib.wallets import Wallet, wallet_create_or_open
from bitcoinlib.services.services import Service
from decimal import Decimal
from django.conf import settings
import asyncio
import logging

logger = logging.getLogger(__name__)

class BitcoinPaymentProcessor:
    def __init__(self):
        self.network = 'testnet' if settings.DEBUG else 'bitcoin'
        self.service = Service(network=self.network)
        
    def generate_wallet(self):
        """Genera una nueva dirección de Bitcoin"""
        # En producción, usar HD wallet con mnemonic seguro
        wallet_name = f"payment_wallet_{settings.SECRET_KEY[:10]}"
        
        try:
            wallet = wallet_create_or_open(
                wallet_name,
                network=self.network,
                witness_type='segwit'
            )
            
            # Generar nueva dirección
            key = wallet.new_key()
            address = key.address
            
            return {
                'address': address,
                'private_key': key.wif,  # Encriptar en producción!
                'derivation_path': key.path
            }
            
        except Exception as e:
            logger.error(f"Error generating Bitcoin wallet: {str(e)}")
            raise
    
    def get_btc_price(self):
        """Obtiene el precio actual de BTC en EUR"""
        # Integrar con API de precios (CoinGecko, Binance, etc.)
        # Por ahora retornamos un valor de ejemplo
        return Decimal('35000.00')
    
    def calculate_crypto_amount(self, eur_amount):
        """Calcula cuánto BTC se necesita para el monto en EUR"""
        btc_price = self.get_btc_price()
        return (Decimal(str(eur_amount)) / btc_price).quantize(Decimal('0.00000001'))
    
    async def check_transaction(self, tx_hash):
        """Verifica una transacción de Bitcoin"""
        try:
            tx = self.service.gettransaction(tx_hash)
            
            if tx:
                return {
                    'confirmed': tx.confirmations > 0,
                    'confirmations': tx.confirmations,
                    'amount': tx.output_total,
                    'fee': tx.fee
                }
        except Exception as e:
            logger.error(f"Error checking BTC transaction: {str(e)}")
        
        return None
    
    async def monitor_address(self, address, expected_amount, callback):
        """Monitorea una dirección para pagos entrantes"""
        checked_txs = set()
        
        while True:
            try:
                # Obtener transacciones de la dirección
                txs = self.service.getaddresstxs(address)
                
                for tx in txs:
                    if tx.txid not in checked_txs:
                        checked_txs.add(tx.txid)
                        
                        # Verificar si la transacción es para nosotros
                        for output in tx.outputs:
                            if output.address == address:
                                amount_btc = Decimal(str(output.value)) / Decimal('100000000')
                                
                                if amount_btc >= expected_amount * Decimal('0.99'):
                                    await callback(tx.txid)
                                    return
                
            except Exception as e:
                logger.error(f"Error monitoring BTC address: {str(e)}")
            
            await asyncio.sleep(30)  # Verificar cada 30 segundos