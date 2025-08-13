from web3 import Web3
from decimal import Decimal
from django.conf import settings
import asyncio

class EthereumPaymentProcessor:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.ETH_NODE_URL))
        self.usdt_contract_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"  # USDT en Ethereum
        
    def generate_wallet(self):
        """Genera una nueva wallet de Ethereum"""
        account = self.w3.eth.account.create()
        return {
            'address': account.address,
            'private_key': account._private_key.hex()
        }
    
    def get_eth_price(self):
        """Obtiene el precio actual de ETH en EUR"""
        # Aquí integrarías con una API de precios como CoinGecko
        # Por ahora retornamos un valor de ejemplo
        return Decimal('2500.00')
    
    def calculate_crypto_amount(self, eur_amount):
        """Calcula cuánto ETH se necesita para el monto en EUR"""
        eth_price = self.get_eth_price()
        return (Decimal(str(eur_amount)) / eth_price).quantize(Decimal('0.000001'))
    
    async def check_transaction(self, tx_hash):
        """Verifica una transacción"""
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            if receipt:
                confirmations = self.w3.eth.block_number - receipt.blockNumber
                return {
                    'confirmed': receipt.status == 1,
                    'confirmations': confirmations,
                    'from_address': tx['from'],
                    'to_address': tx['to'],
                    'value': Web3.from_wei(tx['value'], 'ether')
                }
        except Exception:
            pass
        
        return None
    
    async def monitor_address(self, address, expected_amount, callback):
        """Monitorea una dirección para pagos entrantes"""
        last_block = self.w3.eth.block_number
        
        while True:
            current_block = self.w3.eth.block_number
            
            if current_block > last_block:
                # Revisar transacciones en los nuevos bloques
                for block_num in range(last_block + 1, current_block + 1):
                    block = self.w3.eth.get_block(block_num, full_transactions=True)
                    
                    for tx in block.transactions:
                        if tx['to'] and tx['to'].lower() == address.lower():
                            value = Web3.from_wei(tx['value'], 'ether')
                            if value >= expected_amount * Decimal('0.99'):  # 1% de tolerancia
                                await callback(tx['hash'].hex())
                                return
                
                last_block = current_block
            
            await asyncio.sleep(10)  # Esperar 10 segundos