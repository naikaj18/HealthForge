#!/usr/bin/env python3
import os
import aws_cdk as cdk

from stacks.data_stack import DataStack
from stacks.ingest_stack import IngestStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

data_stack = DataStack(app, "HealthForgeData", env=env)
IngestStack(app, "HealthForgeIngest", data_stack=data_stack, env=env)

app.synth()
