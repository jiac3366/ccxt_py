# RestAPI Python Service

## 安装要求

- Python 3.8+
- pip

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 生成 gRPC 代码：
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. market_service.proto
```

3. 配置交易所 API（可选）：
   - 复制 `config.cfg.example` 为 `config.cfg`
   - 在 `config.cfg` 中填入你的 API 密钥


4. 运行服务：
```bash
python load_market.py
```

## 错误处理

服务使用标准的 gRPC 状态码进行错误处理：

- `INVALID_ARGUMENT`: 无效的交易所名称
- `UNIMPLEMENTED`: 交易所不支持市场数据加载
- `UNAVAILABLE`: 网络错误
- `FAILED_PRECONDITION`: 交易所 API 错误
- `INTERNAL`: 内部服务错误