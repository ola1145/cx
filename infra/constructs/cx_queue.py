"""CxQueue: encrypted SQS queue with a dead-letter queue."""
from __future__ import annotations
import aws_cdk as cdk
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class CxQueue(Construct):
    def __init__(self, scope: Construct, id: str, *,
                 visibility_timeout: cdk.Duration = cdk.Duration.seconds(300),
                 max_receive_count: int = 3) -> None:
        super().__init__(scope, id)
        dlq = sqs.Queue(self, "DLQ", encryption=sqs.QueueEncryption.SQS_MANAGED,
                        retention_period=cdk.Duration.days(14))
        self.queue = sqs.Queue(self, "Queue",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            visibility_timeout=visibility_timeout,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=max_receive_count, queue=dlq))
