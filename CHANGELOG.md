# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-07-06

### Added

- **Core Framework**
  - MonkeyPatcher engine for runtime method interception
  - ImportHook (PEP 451) for deferred patching on module import
  - Injector with matcher comparison, effect-count/effect-percent limiting
  - EnhancerFactory for sync/async wrapper creation
  - Thread-safe StatusManager and PluginManager

- **Fault Executors**
  - `delay` — Millisecond-level latency injection with random offset
  - `throwCustomException` — Configurable exception injection
  - `returnValue` — Return value tampering

- **Middleware Plugins**
  - Redis (`redis.client.Redis`)
  - HTTP/Requests (`requests.Session`)
  - MySQL via mysql-connector (`mysql.connector`)
  - MySQL via PyMySQL (`pymysql.connections`)
  - gRPC (`grpc._channel`)
  - Kafka Producer (`kafka.KafkaProducer`)
  - Kafka Consumer (`kafka.KafkaConsumer`)
  - SQLAlchemy (`sqlalchemy.engine`)

- **Service Layer**
  - HTTP management server (GET/POST/CORS)
  - Handlers: create, destroy, status, list, health
  - JSON request/response protocol compatible with ChaosBlade CLI

- **CLI & Deployment**
  - `chaosblade-exec-python start` — Standalone agent mode
  - `chaosblade-exec-python status` — Query agent health and experiments
  - `chaosblade-exec-python attach` — Generate sitecustomize.py for auto-injection
  - `chaosblade-exec-python detach` — Remove sitecustomize.py hook
  - SIGTERM/atexit graceful shutdown

- **Configuration**
  - Priority chain: Environment Variables > Config File > Defaults
  - Simple YAML parser (zero dependencies)

- **Project Infrastructure**
  - 209 unit tests with full coverage
  - Wheel packaging via hatchling
  - GitHub Actions CI/CD workflows
  - Apache License 2.0
