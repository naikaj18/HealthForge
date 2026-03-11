from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_lambda_event_sources as event_sources,
)
from constructs import Construct

from stacks.data_stack import DataStack


class IngestStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, data_stack: DataStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Lambda: Webhook Receiver ---
        # Receives JSON from Health Auto Export, validates, pushes to SQS
        webhook_fn = _lambda.Function(
            self,
            "WebhookReceiver",
            function_name="HealthForge-WebhookReceiver",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/webhook_receiver"),
            timeout=Duration.seconds(10),
            memory_size=128,
            environment={
                "QUEUE_URL": data_stack.ingest_queue.queue_url,
            },
        )
        data_stack.ingest_queue.grant_send_messages(webhook_fn)

        # --- Lambda: Data Processor ---
        # Reads from SQS, parses, deduplicates, writes to DynamoDB
        processor_fn = _lambda.Function(
            self,
            "DataProcessor",
            function_name="HealthForge-DataProcessor",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/data_processor"),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "TABLE_NAME": data_stack.table.table_name,
            },
        )
        data_stack.table.grant_read_write_data(processor_fn)

        # Trigger processor from SQS
        processor_fn.add_event_source(
            event_sources.SqsEventSource(
                data_stack.ingest_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(30),
            )
        )

        # --- API Gateway ---
        api = apigw.RestApi(
            self,
            "HealthForgeApi",
            rest_api_name="HealthForge API",
            description="Ingestion API for Health Auto Export",
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )

        # POST /ingest — webhook for Health Auto Export
        ingest_resource = api.root.add_resource("ingest")
        ingest_resource.add_method(
            "POST",
            apigw.LambdaIntegration(webhook_fn),
            api_key_required=True,
        )

        # POST /upload — manual XML export (placeholder for now)
        upload_resource = api.root.add_resource("upload")
        upload_resource.add_method(
            "POST",
            apigw.LambdaIntegration(webhook_fn),
            api_key_required=True,
        )

        # --- API Key & Usage Plan ---
        api_key = api.add_api_key("HealthForgeApiKey",
            api_key_name="HealthForge-IngestKey",
        )

        usage_plan = api.add_usage_plan("HealthForgeUsagePlan",
            name="HealthForge-UsagePlan",
            throttle=apigw.ThrottleSettings(
                rate_limit=10,
                burst_limit=20,
            ),
        )
        usage_plan.add_api_stage(stage=api.deployment_stage)
        usage_plan.add_api_key(api_key)
