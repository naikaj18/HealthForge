import aws_cdk as core
import aws_cdk.assertions as assertions

from health_forge.health_forge_stack import HealthForgeStack

# example tests. To run these tests, uncomment this file along with the example
# resource in health_forge/health_forge_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = HealthForgeStack(app, "health-forge")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
