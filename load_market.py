import grpc
from concurrent import futures
import ccxt
import proto.market_service_pb2 as market_pb2
import proto.market_service_pb2_grpc as market_pb2_grpc
import logging
from typing import Dict, Any, Optional
import signal
import sys
from functools import lru_cache

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('market_service.log')
    ]
)
logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self):
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        
    @lru_cache(maxsize=100)
    def get_exchange_class(self, exchange_id: str) -> Optional[type]:
        """获取交易所类，使用缓存避免重复查找"""
        return getattr(ccxt, exchange_id, None)
        
    def get_exchange(self, exchange_id: str) -> ccxt.Exchange:
        """获取或创建交易所实例"""
        if exchange_id not in self.exchanges:
            exchange_class = self.get_exchange_class(exchange_id)
            if not exchange_class:
                raise ValueError(f"Unsupported exchange: {exchange_id}")
                
            self.exchanges[exchange_id] = exchange_class({
                'enableRateLimit': True,
                'timeout': 30000,
                'enableLastJsonResponse': False,  # 减少内存使用
                'verbose': False,  # 关闭详细日志
            })
        return self.exchanges[exchange_id]

class MarketServicer(market_pb2_grpc.MarketServiceServicer):
    def __init__(self):
        self.exchange_manager = ExchangeManager()

    async def LoadMarkets(self, request, context):
        try:
            exchange_id = request.exchange
            logger.info(f"Received request for exchange: {exchange_id}")
            
            try:
                exchange = self.exchange_manager.get_exchange(exchange_id)
            except ValueError as e:
                logger.error(f"Invalid exchange: {str(e)}")
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(str(e))
                return market_pb2.MarketResponse()
            
            if not exchange.has.get('fetchMarkets'):
                error_msg = f"Exchange {exchange_id} does not support market loading"
                logger.error(error_msg)
                context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                context.set_details(error_msg)
                return market_pb2.MarketResponse()
            
            try:
                markets = await exchange.load_markets()
            except ccxt.NetworkError as e:
                logger.error(f"Network error while loading markets: {str(e)}")
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details(str(e))
                return market_pb2.MarketResponse()
            except ccxt.ExchangeError as e:
                logger.error(f"Exchange error while loading markets: {str(e)}")
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details(str(e))
                return market_pb2.MarketResponse()
            
            response = market_pb2.MarketResponse()
            processed_count = 0
            error_count = 0
            
            for symbol, market in markets.items():
                try:
                    market_info = market_pb2.MarketInfo()
                    market_info.id = market['id']
                    market_info.symbol = market['symbol']
                    market_info.base = market['base']
                    market_info.quote = market['quote']
                    market_info.active = market.get('active', False)
                    response.markets[symbol].CopyFrom(market_info)
                    processed_count += 1
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing market {symbol}: {str(e)}")
                    continue
            
            logger.info(f"Successfully processed {processed_count} markets "
                       f"({error_count} errors) for {exchange_id}")
            return response
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return market_pb2.MarketResponse()

class GracefulServer:
    def __init__(self, port: int = 50051, max_workers: int = 10):
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=max_workers),
            options=[
                ('grpc.max_send_message_length', 100 * 1024 * 1024),
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),
                ('grpc.keepalive_time_ms', 30000),
                ('grpc.keepalive_timeout_ms', 10000),
                ('grpc.http2.max_pings_without_data', 0),
                ('grpc.keepalive_permit_without_calls', 1),
            ]
        )
        market_pb2_grpc.add_MarketServiceServicer_to_server(MarketServicer(), self.server)
        self.port = port
        
    def start(self):
        server_addr = f'[::]:{self.port}'
        self.server.add_insecure_port(server_addr)
        self.server.start()
        logger.info(f"Server started on {server_addr}")
        
        def handle_signal(signum, frame):
            logger.info("Received shutdown signal, stopping server gracefully...")
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
    def stop(self):
        logger.info("Stopping server...")
        self.server.stop(5)  # 5 seconds grace period
        
    def wait_for_termination(self):
        self.server.wait_for_termination()

def serve(port: int = 50051, max_workers: int = 10):
    server = GracefulServer(port, max_workers)
    try:
        server.start()
        server.wait_for_termination()
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        server.stop()
        sys.exit(1)

if __name__ == '__main__':
    serve()