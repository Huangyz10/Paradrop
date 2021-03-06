import click
from click.testing import CliRunner
from mock import patch

from pdtools import cloud


@patch("pdtools.cloud.util.format_result")
@patch("pdtools.cloud.ControllerClient")
def test_simple_cloud_commands(ControllerClient, format_result):
    commands = [
        ["claim-node", "token"],
        ["create-node", "test"],
        ["delete-node", "test"],
        ["describe-node", "test"],
        ["group-add-node", "group", "node"],
        ["help"],
        ["list-groups"],
        ["list-nodes"],
        ["login"],
        ["logout"],
        ["rename-node", "node", "node"]
    ]

    format_result.return_value = "result"

    runner = CliRunner()
    for command in commands:
        result = runner.invoke(cloud.root, command, obj={})
        print("Command {} exit code {}".format(command[0], result.exit_code))
        assert result.exit_code == 0
