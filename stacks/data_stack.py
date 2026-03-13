from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_dynamodb as dynamodb,
    aws_sqs as sqs,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- DynamoDB: Single-table design ---
        self.table = dynamodb.Table(
            self,
            "HealthTable",
            table_name="HealthForge",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # GSI1: Query metrics by type and date range
        # PK: USER#<userId>#METRIC#<metricType>  SK: <date>
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # --- SQS: Ingest queue with DLQ ---
        self.dlq = sqs.Queue(
            self,
            "IngestDLQ",
            queue_name="HealthForge-Ingest-DLQ",
            retention_period=Duration.days(14),
        )

        self.ingest_queue = sqs.Queue(
            self,
            "IngestQueue",
            queue_name="HealthForge-Ingest",
            visibility_timeout=Duration.seconds(300),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dlq,
            ),
        )

        # --- CloudWatch Alarm: DLQ messages ---
        self.dlq.metric_approximate_number_of_messages_visible(
            period=Duration.minutes(5),
        ).create_alarm(
            self,
            "DLQAlarm",
            alarm_name="HealthForge-DLQ-MessagesVisible",
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        )
