"""
TicoViz Corporation v2 — Sistema de Pagos Crypto
Soporta USDT (TRC20), BTC, ETH.
Verificacion manual via Telegram + futuro NOWPayments.
"""
import logging
import requests
from typing import Optional
from config import CRYPTO_WALLETS

logger = logging.getLogger("ticoviz.payment")


def generar_info_pago(precio_usd: float, crypto: str = "USDT_TRC20") -> dict:
    """
    Genera informacion de pago para mostrar al cliente.
    Retorna direccion, monto, QR, red, etc.
    """
    wallets = CRYPTO_WALLETS

    if crypto == "USDT_TRC20":
        address = wallets.get("USDT_TRC20", "")
        amount = round(precio_usd, 2)  # 1 USDT ~ 1 USD
        network = "TRC20 (Tron)"
        coin = "USDT"
    elif crypto == "BTC":
        address = wallets.get("BTC", "")
        btc_price = _get_btc_price()
        amount = round(precio_usd / btc_price, 8) if btc_price else 0
        network = "Bitcoin"
        coin = "BTC"
    elif crypto == "ETH":
        address = wallets.get("ETH", "")
        eth_price = _get_eth_price()
        amount = round(precio_usd / eth_price, 6) if eth_price else 0
        network = "Ethereum (ERC20)"
        coin = "ETH"
    else:
        address = wallets.get("USDT_TRC20", "")
        amount = round(precio_usd, 2)
        network = "TRC20 (Tron)"
        coin = "USDT"

    # QR code via free API
    qr_data = address
    qr_url = (
        f"https://api.qrserver.com/v1/create-qr-code/"
        f"?data={qr_data}&size=250x250&bgcolor=0a0a1a&color=e0e0e0"
    )

    return {
        "address": address,
        "amount": amount,
        "amount_display": f"{amount} {coin}",
        "coin": coin,
        "network": network,
        "qr_url": qr_url,
        "precio_usd": precio_usd,
        "memo": "",
        "configured": bool(address),
    }


def _get_btc_price() -> Optional[float]:
    """Obtiene precio BTC/USD de CoinGecko (gratis, sin API key)."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["bitcoin"]["usd"]
    except Exception as e:
        logger.error(f"Error obteniendo precio BTC: {e}")
        return None


def _get_eth_price() -> Optional[float]:
    """Obtiene precio ETH/USD de CoinGecko."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["ethereum"]["usd"]
    except Exception as e:
        logger.error(f"Error obteniendo precio ETH: {e}")
        return None


def get_cryptos_disponibles() -> list:
    """Retorna lista de criptomonedas configuradas."""
    cryptos = []
    if CRYPTO_WALLETS.get("USDT_TRC20"):
        cryptos.append("USDT_TRC20")
    if CRYPTO_WALLETS.get("BTC"):
        cryptos.append("BTC")
    if CRYPTO_WALLETS.get("ETH"):
        cryptos.append("ETH")
    return cryptos if cryptos else ["USDT_TRC20"]
