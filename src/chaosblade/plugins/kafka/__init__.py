"""Kafka plugin - fault injection for kafka-python / confluent-kafka.

Intercepts KafkaProducer.send and KafkaConsumer.poll to inject:
- delay: latency on produce/consume operations
- exception: KafkaError / BrokerNotAvailableError
- return: tampered messages

Matchers:
- topic: Kafka topic name
- operation: "produce" or "consume"
"""

from __future__ import annotations

from typing import Any

from chaosblade.common.model.base_model_spec import BaseModelSpec
from chaosblade.executor.delay_executor import DelayActionExecutor
from chaosblade.executor.exception_executor import ThrowExceptionExecutor
from chaosblade.executor.return_executor import ReturnValueExecutor
from chaosblade.plugins.base import (
    DefaultActionSpec,
    DefaultFlagSpec,
    DefaultMatcherSpec,
    DefaultPointCut,
)
from chaosblade.plugins.default_enhancer import DefaultBeforeEnhancer


def _kafka_producer_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract Kafka producer matchers from KafkaProducer.send args.

    KafkaProducer.send(self, topic, value=None, key=None, ...)
    - args[0] = self (KafkaProducer instance)
    - args[1] = topic
    """
    matchers: dict[str, str] = {"operation": "produce"}

    if len(args) >= 2:
        matchers["topic"] = str(args[1])
    elif "topic" in kwargs:
        matchers["topic"] = str(kwargs["topic"])

    return matchers


def _kafka_consumer_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract Kafka consumer matchers from KafkaConsumer.poll args.

    KafkaConsumer.poll(self, timeout_ms=0, max_records=None, ...)
    The subscribed topics are on the consumer instance.
    """
    matchers: dict[str, str] = {"operation": "consume"}

    # Try to get subscribed topics from the consumer instance
    if obj is not None:
        topics = getattr(obj, "_subscription", None) or getattr(obj, "subscription", None)
        if topics:
            if hasattr(topics, "topics"):
                topics = topics.topics
            if isinstance(topics, (set, list, tuple)):
                matchers["topic"] = ",".join(str(t) for t in topics)

    return matchers


class KafkaModelSpec(BaseModelSpec):
    """ModelSpec for Kafka fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "kafka"

    def get_short_desc(self) -> str:
        return "Kafka fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into Kafka operations"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("topic", "Kafka topic name to match"),
            DefaultMatcherSpec("operation", "Operation type: produce or consume"),
        ]

    def _register_actions(self) -> None:
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into Kafka operations",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from Kafka operations",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override Kafka operation result",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class KafkaProducerPlugin:
    """Kafka producer fault injection plugin.

    Target: kafka.KafkaProducer.send (kafka-python)
    """

    def __init__(self) -> None:
        self._model_spec = KafkaModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="kafka",
            target_function="send",
            target_class="KafkaProducer",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="kafka",
            extractor=_kafka_producer_matcher_extractor,
        )

    def get_name(self) -> str:
        return "kafka-producer"

    def get_model_spec(self) -> KafkaModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer


class KafkaConsumerPlugin:
    """Kafka consumer fault injection plugin.

    Target: kafka.KafkaConsumer.poll (kafka-python)
    """

    def __init__(self) -> None:
        self._model_spec = KafkaModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="kafka",
            target_function="poll",
            target_class="KafkaConsumer",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="kafka",
            extractor=_kafka_consumer_matcher_extractor,
        )

    def get_name(self) -> str:
        return "kafka-consumer"

    def get_model_spec(self) -> KafkaModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
