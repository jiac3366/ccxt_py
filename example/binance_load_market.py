import sys
import os
import logging
import configparser
from typing import Dict, Any
import asyncio
import json

# 添加父目录到 Python 路径以导入 ExchangeManager
# print(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from load_market import ExchangeManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str):
        self.config = configparser.ConfigParser()
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        self.config.read(config_path)

    def get_exchange_config(self, section: str) -> Dict[str, Any]:
        if not self.config.has_section(section):
            raise ValueError(f"Section {section} not found in config file")
        
        return {
            'apiKey': self.config.get(section, 'API_KEY'),
            'secret': self.config.get(section, 'SECRET'),
            'enableRateLimit': True,
            'timeout': 30000,
        }

async def main():
    try:
        # 获取项目根目录的配置文件路径
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.key', 'config.cfg')
        config_manager = ConfigManager(config_path)
        
        # 创建 ExchangeManager 实例
        exchange_manager = ExchangeManager()
        
        # 获取 Binance 测试网配置
        exchange_config = config_manager.get_exchange_config('binance_future_testnet')
        
        # 使用配置创建交易所实例
        exchange = exchange_manager.get_exchange('binance')
        exchange.options = {**exchange.options, **exchange_config}
        
        logger.info("Loading Binance markets...")
        markets = exchange.load_markets()
        
        # 打印市场信息
        logger.info(f"Successfully loaded {len(markets)} markets")
        # save to markets.json in tests/test_data
        with open('tests/test_data/markets.json', 'w') as f:
            json.dump(markets, f)
        
        # 打印一些示例市场数据
        sample_symbols = list(markets.keys())[:5]  # 取前5个交易对作为样本

        for symbol in sample_symbols:
            market = markets[symbol]
            logger.info(f"\nMarket info for {symbol}:")
            logger.info(f"ID: {market['id']}")
            logger.info(f"Base: {market['base']}")
            logger.info(f"Quote: {market['quote']}")
            logger.info(f"Active: {market.get('active', False)}")
            logger.info(f"Type: {market.get('type', 'spot')}")
            if 'limits' in market:
                logger.info("Limits:")
                logger.info(f"  Amount: {market['limits'].get('amount', {})}")
                logger.info(f"  Price: {market['limits'].get('price', {})}")
                logger.info(f"  Cost: {market['limits'].get('cost', {})}")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
