# stacks/analysis_stack.py
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_events as events,
    aws_events_targets as targets,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct
from stacks.data_stack import DataStack


class AnalysisStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, data_stack: DataStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Gemini API key from SSM Parameter Store
        gemini_key_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self, "GeminiApiKey",
            parameter_name="/healthforge/gemini-api-key",
        )

        # Email config from SSM
        sender_email = ssm.StringParameter.value_for_string_parameter(
            self, "/healthforge/sender-email"
        )
        recipient_email = ssm.StringParameter.value_for_string_parameter(
            self, "/healthforge/recipient-email"
        )

        # Lambda Layer for shared utilities (dates, db, scores, etc.)
        # Layer structure: python/ dir with all shared modules
        # Built by: cp lambdas/shared/*.py lambdas/shared_layer/python/
        shared_layer = _lambda.LayerVersion(
            self,
            "SharedLayer",
            layer_version_name="HealthForge-Shared",
            code=_lambda.Code.from_asset("lambdas/shared_layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared utilities for HealthForge analysis lambdas",
        )

        # --- Lambda: Aggregation ---
        aggregation_fn = _lambda.Function(
            self,
            "Aggregation",
            function_name="HealthForge-Aggregation",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/aggregation"),
            layers=[shared_layer],
            timeout=Duration.seconds(120),
            memory_size=512,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            environment={
                "TABLE_NAME": data_stack.table.table_name,
                "USER_ID": "default",
            },
        )
        data_stack.table.grant_read_data(aggregation_fn)

        # --- Lambda: Insight (Gemini Flash) ---
        insight_fn = _lambda.Function(
            self,
            "Insight",
            function_name="HealthForge-Insight",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/insight"),
            timeout=Duration.seconds(60),
            memory_size=128,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            environment={
                "GEMINI_API_KEY_PARAM": "/healthforge/gemini-api-key",
            },
        )
        gemini_key_param.grant_read(insight_fn)

        # --- Lambda: Email Renderer ---
        email_fn = _lambda.Function(
            self,
            "EmailRenderer",
            function_name="HealthForge-EmailRenderer",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/email_renderer"),
            timeout=Duration.seconds(30),
            memory_size=128,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            environment={
                "SENDER_EMAIL": sender_email,
                "RECIPIENT_EMAIL": recipient_email,
            },
        )
        email_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=[
                    f"arn:aws:ses:{self.region}:{self.account}:identity/{sender_email}",
                ],
            )
        )

        # --- Step Functions ---
        aggregate_step = tasks.LambdaInvoke(
            self, "AggregateData",
            lambda_function=aggregation_fn,
            output_path="$.Payload",
        )

        insight_step = tasks.LambdaInvoke(
            self, "GenerateInsights",
            lambda_function=insight_fn,
            output_path="$.Payload",
        )

        email_step = tasks.LambdaInvoke(
            self, "SendEmail",
            lambda_function=email_fn,
            output_path="$.Payload",
        )

        # Retry with exponential backoff for each step
        for step in [aggregate_step, insight_step, email_step]:
            step.add_retry(
                errors=["States.TaskFailed"],
                interval=Duration.seconds(5),
                max_attempts=2,
                backoff_rate=2.0,
            )

        # Catch-all error handling
        error_state = sfn.Fail(self, "PipelineFailed", cause="Lambda execution failed", error="ExecutionError")
        for step in [aggregate_step, insight_step, email_step]:
            step.add_catch(error_state)

        # Chain: Aggregate → Check if should send → Insight → Email
        should_send = sfn.Choice(self, "ShouldSendEmail")
        skip_state = sfn.Pass(self, "SkipEmail")

        definition = aggregate_step.next(
            should_send
            .when(sfn.Condition.boolean_equals("$.send_email", False), skip_state)
            .otherwise(insight_step.next(email_step))
        )

        state_machine = sfn.StateMachine(
            self,
            "WeeklyReportPipeline",
            state_machine_name="HealthForge-WeeklyReport",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(5),
        )

        # --- EventBridge: Sunday 10 AM ET (15:00 UTC, approximation for EDT) ---
        events.Rule(
            self,
            "WeeklySchedule",
            rule_name="HealthForge-WeeklyReport",
            schedule=events.Schedule.cron(
                minute="0",
                hour="13",  # 9 AM EDT / 8 AM EST
                week_day="SUN",
            ),
            targets=[targets.SfnStateMachine(
                state_machine,
                input=events.RuleTargetInput.from_object({
                    "user_id": "default",
                }),
            )],
        )

        # --- CloudWatch Alarm: Step Functions failures ---
        state_machine.metric_failed(
            period=Duration.days(1),
        ).create_alarm(
            self,
            "StepFunctionFailureAlarm",
            alarm_name="HealthForge-StepFunction-Failures",
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        )
