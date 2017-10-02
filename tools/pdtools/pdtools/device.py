import datetime
import getpass
import json
import operator
import os
import sys
import tarfile
import tempfile
import arrow
import builtins
import click
import yaml
import json
import websocket
import base64

from .comm import change_json, router_request, LOCAL_DEFAULT_USERNAME, LOCAL_DEFAULT_PASSWORD


@click.group()
@click.option('--address', default='192.168.1.1', help='IP address of the ParaDrop device (default=192.168.1.1)')
@click.pass_context
def device(ctx, address):
    """
    Commands to work with a ParaDrop device.
    """
    ctx.obj['address'] = address
    ctx.obj['base_url'] = "http://{}/api/v1".format(address)
    ctx.obj['ws_url'] = "ws://{}//ws".format(address)


@device.command()
@click.pass_context
def changes(ctx):
    """
    List changes in the working queue.
    """
    url = "{}/changes/".format(ctx.obj['base_url'])
    router_request("GET", url)


@device.command()
@click.pass_context
@click.argument('change_id')
def watch(ctx, change_id):
    """
    Stream messages for a change in progress.
    """
    url = "ws://{}/ws/changes/{}/stream".format(ctx.obj['address'], change_id)

    def on_error(ws, error):
        print(error)
    def on_message(ws, message):
        data = json.loads(message)
        time = datetime.datetime.fromtimestamp(data['time'])
        msg = data['message'].rstrip()
        print("{}: {}".format(time, msg))

    router_ws_request(url, on_message=on_message, on_error=on_error)


@device.command()
@click.pass_context
def changes(ctx):
    """
    List changes in the working queue.
    """
    url = "{}/changes/".format(ctx.obj['base_url'])
    router_request("GET", url)


@device.group()
@click.pass_context
def chutes(ctx):
    """
    View or install chutes on the router.
    """
    pass


@chutes.command()
@click.pass_context
def list(ctx):
    """
    List chutes installed on the router.
    """
    url = "{}/chutes/".format(ctx.obj['base_url'])
    router_request("GET", url)


@chutes.command()
@click.pass_context
def install(ctx):
    """
    Install a chute from the working directory.
    """
    url = "{}/chutes/".format(ctx.obj['base_url'])
    headers = {'Content-Type': 'application/x-tar'}

    if not os.path.exists("paradrop.yaml"):
        raise Exception("No paradrop.yaml file found in working directory.")

    with tempfile.TemporaryFile() as temp:
        tar = tarfile.open(fileobj=temp, mode="w")
        for dirName, subdirList, fileList in os.walk('.'):
            for fname in fileList:
                path = os.path.join(dirName, fname)
                arcname = os.path.normpath(path)
                tar.add(path, arcname=arcname)
        tar.close()

        temp.seek(0)
        res = router_request("POST", url, headers=headers, data=temp)
        data = res.json()
        ctx.invoke(watch, change_id=data['change_id'])


@device.group()
@click.argument('chute_name')
@click.pass_context
def chute(ctx, chute_name):
    """
    Operations on a chute.
    """
    ctx.obj['chute'] = chute_name
    ctx.obj['chute_url'] = "{}/chutes/{}".format(ctx.obj['base_url'], chute_name)


@chute.command()
@click.pass_context
def start(ctx):
    """
    Start the chute.
    """
    url = ctx.obj['chute_url'] + "/start"
    router_request("POST", url)


@chute.command()
@click.pass_context
def stop(ctx):
    """
    Stop the chute.
    """
    url = ctx.obj['chute_url'] + "/stop"
    router_request("POST", url)


@chute.command()
@click.pass_context
def delete(ctx):
    """
    Uninstall the chute.
    """
    url = ctx.obj['chute_url']
    res = router_request("DELETE", url)
    data = res.json()
    ctx.invoke(watch, change_id=data['change_id'])


@chute.command()
@click.pass_context
def info(ctx):
    """
    Get information about the chute.
    """
    url = ctx.obj['chute_url']
    router_request("GET", url)


@chute.command()
@click.pass_context
def cache(ctx):
    """
    Get details from the chute installation.
    """
    url = ctx.obj['chute_url'] + "/cache"
    router_request("GET", url)


@chute.command()
@click.pass_context
def logs(ctx):
    """
    Watch log messages from a chute.
    """
    url = "ws://{}/sockjs/logs/{}/websocket".format(ctx.obj['address'], ctx.obj['chute'])

    def on_error(ws, error):
        print(error)
    def on_message(ws, message):
        data = json.loads(message)
        time = arrow.get(data['timestamp']).to('local').datetime
        msg = data['message'].rstrip()
        print("{}: {}".format(time, msg))

    router_ws_request(url, on_message=on_message, on_error=on_error)


@chute.command()
@click.pass_context
def update(ctx):
    """
    Update the chute from the working directory.
    """
    url = ctx.obj['chute_url']
    headers = {'Content-Type': 'application/x-tar'}

    if not os.path.exists("paradrop.yaml"):
        raise Exception("No paradrop.yaml file found in working directory.")

    with tempfile.TemporaryFile() as temp:
        tar = tarfile.open(fileobj=temp, mode="w")
        for dirName, subdirList, fileList in os.walk('.'):
            for fname in fileList:
                path = os.path.join(dirName, fname)
                arcname = os.path.normpath(path)
                tar.add(path, arcname=arcname)
        tar.close()

        temp.seek(0)
        res = router_request("PUT", url, headers=headers, data=temp)
        data = res.json()
        ctx.invoke(watch, change_id=data['change_id'])


@chute.command()
@click.pass_context
def networks(ctx):
    """
    List the chute's networks.
    """
    url = ctx.obj['chute_url'] + "/networks"
    router_request("GET", url)


@chute.command()
@click.pass_context
def shell(ctx):
    """
    Open a shell inside a chute.

    This requires you to have enabled SSH access to the device and installed
    bash inside your chute.
    """
    cmd = ["ssh", "-t", "paradrop@{}".format(ctx.obj['address']), "sudo", "docker",
            "exec", "-it", ctx.obj['chute'], "/bin/bash"]
    os.spawnvpe(os.P_WAIT, "ssh", cmd, os.environ)


@chute.group()
@click.pass_context
@click.argument('network')
def network(ctx, network):
    """
    Operations on a chute network.
    """
    ctx.obj['network'] = network
    ctx.obj['network_url'] = "{}/networks/{}".format(ctx.obj['chute_url'],
            network)


@network.command()
@click.pass_context
def stations(ctx):
    """
    List stations connected to the network.
    """
    url = ctx.obj['network_url'] + "/stations"
    router_request("GET", url)


@network.group()
@click.pass_context
@click.argument('station')
def station(ctx, station):
    """
    operations on a chute's network stations.
    """
    ctx.obj['station'] = station
    ctx.obj['station_url'] = ctx.obj['network_url'] + "/stations/" + station


@station.command()
@click.pass_context
def show(ctx):
    """
    Show station information.
    """
    router_request("GET", ctx.obj['station_url'])


@station.command()
@click.pass_context
def delete(ctx):
    """
    Kick a station off the network.
    """
    router_request("DELETE", ctx.obj['station_url'])


@device.group(invoke_without_command=False)
@click.pass_context
def hostconfig(ctx):
    """
    Commands to work with the hostconfig.
    """
    pass

@hostconfig.command()
@click.pass_context
def show(ctx):
    """
    Get host configuration.
    """
    url = ctx.obj['base_url'] + "/config/hostconfig"
    res = router_request("GET", url, dump=False)
    click.echo(json.dumps(res.json(), indent=4, sort_keys=True))

@hostconfig.command()
@click.pass_context
@click.argument('option')
@click.argument('value')
def change(ctx, option, value):
    """
    Change one setting in the host configuration.
    """
    url = ctx.obj['base_url'] + "/config/hostconfig"
    req = router_request("GET", url, dump=False)
    config = req.json()

    change_json(config, option, value)
    data = {
        'config': config
    }
    router_request("PUT", url, json=data)


@hostconfig.command()
@click.pass_context
def edit(ctx):
    """
    Interactively edit the host configuration.
    """
    url = ctx.obj['base_url'] + "/config/hostconfig"
    req = router_request("GET", url, dump=False)
    config = req.json()

    fd, path = tempfile.mkstemp()
    os.close(fd)

    with open(path, 'w') as output:
        output.write(yaml.safe_dump(config, default_flow_style=False))

    # Get modified time before calling editor.
    orig_mtime = os.path.getmtime(path)

    editor = os.environ.get("EDITOR", "vim")
    os.spawnvpe(os.P_WAIT, editor, [editor, path], os.environ)

    with open(path, 'r') as source:
        data = source.read()
        config = yaml.safe_load(data)

    # Check if the file has been modified, and if it has, send the update.
    new_mtime = os.path.getmtime(path)
    if new_mtime != orig_mtime:
        data = {
            'config': config
        }
        router_request("PUT", url, json=data)

    os.remove(path)


@device.group(invoke_without_command=False)
@click.pass_context
def sshkeys(ctx):
    """
    Commands to work with the SSH authorized keys.
    """
    pass

@sshkeys.command()
@click.pass_context
def show(ctx):
    """
    Get SSH authorized keys.
    """
    url = ctx.obj['base_url'] + "/config/sshKeys"
    router_request("GET", url)

@sshkeys.command()
@click.pass_context
@click.argument('path')
def add(ctx, path):
    """
    Add an authorized key from a file.
    """
    url = ctx.obj['base_url'] + "/config/sshKeys"
    with open(path, 'r') as source:
        key_string = source.read().strip()
        data = {
            'key': key_string
        }
        router_request("POST", url, json=data)


@device.command()
@click.pass_context
def password(ctx):
    """
    Change the router admin password.
    """
    url = ctx.obj['base_url'] + "/password/change"

    username = builtins.input("Username: ")
    while True:
        password = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm password: ")

        if password == confirm:
            break
        else:
            print("Passwords do not match.")

    data = {
        "username": username,
        "password": password
    }
    router_request("POST", url, json=data)


@device.command()
@click.pass_context
@click.argument('router_id')
@click.argument('router_password')
@click.option('--server', default="https://paradrop.org")
@click.option('--wamp', default="ws://paradrop.org:9086/ws")
def provision(ctx, router_id, router_password, server, wamp):
    """
    Provision the router.
    """
    url = ctx.obj['base_url'] + "/config/provision"

    data = {
        'routerId': router_id,
        'apitoken': router_password,
        'pdserver': server,
        'wampRouter': wamp
    }
    router_request("POST", url, json=data)


def print_pdconf(res):
    if res.ok:
        data = res.json()
        data.sort(key=operator.itemgetter("age"))

        print("{:3s} {:12s} {:20s} {:30s} {:5s}".format("Age", "Type", "Name",
            "Comment", "Pass"))
        for item in data:
            print("{age:<3d} {type:12s} {name:20s} {comment:30s} {success}".format(**item))


@device.group()
@click.pass_context
def pdconf(ctx):
    """
    Access the pdconf subsystem.

    pdconf manages low-level configuration of the Paradrop device.
    These commands are implemented for debugging purposes and are
    not intended for ordinary configuration purposes.
    """
    pass


@pdconf.command()
@click.pass_context
def show(ctx):
    """
    Show status of pdconf subsystem.
    """
    url = ctx.obj['base_url'] + "/config/pdconf"
    res = router_request("GET", url, dump=False)
    print_pdconf(res)


@pdconf.command()
@click.pass_context
def reload(ctx):
    """
    Force pdconf to reload files.
    """
    url = ctx.obj['base_url'] + "/config/pdconf"
    res = router_request("PUT", url, dump=False)
    print_pdconf(res)


@device.group()
@click.pass_context
def snapd(ctx):
    """
    Access the snapd subsystem.
    """
    ctx.obj['snapd_url'] = "http://{}/snapd".format(ctx.obj['address'])


@snapd.command()
@click.pass_context
@click.argument('email')
def createUser(ctx, email):
    """
    Create user account.
    """
    url = ctx.obj['snapd_url'] + "/v2/create-user"
    data = {
        'email': email,
        'sudoer': True
    }
    router_request("POST", url, json=data)


@snapd.command()
@click.pass_context
def connectAll(ctx):
    """
    Connect all interfaces.
    """
    url = ctx.obj['snapd_url'] + "/v2/interfaces"
    res = router_request("GET", url, dump=False)
    data = res.json()
    for item in data['result']['plugs']:
        connections = item.get('connections', [])
        if len(connections) > 0:
            continue

        if item['plug'] == 'docker':
            # The docker slot needs to be treated differently from core slots.
            slot = {'snap': 'docker'}
        elif item['plug'] == 'zerotier-control':
            slot = {'snap': 'zerotier-one'}
        else:
            # Most slots are provided by the core snap and specified this way.
            slot = {'slot': item['interface']}

        req = {
            'action': 'connect',
            'slots': [slot],
            'plugs': [{'snap': item['snap'], 'plug': item['plug']}]
        }
        print("snap connect {snap}:{plug} {interface}".format(**item))
        router_request("POST", url, json=req, dump=False)


@device.command()
@click.pass_context
def log(ctx):
    """
    Monitor the logs of the router.
    """
    url = ctx.obj['ws_url'] + "/paradrop_logs"

    # First try with the default username and password.
    # If that fails, prompt user and try again.
    userpass = "{}:{}".format(LOCAL_DEFAULT_USERNAME, LOCAL_DEFAULT_PASSWORD)
    encoded_creds = base64.b64encode(userpass.encode('utf-8')).decode('ascii')

    # websocket.enableTrace(True)
    count = 3
    ws = websocket.WebSocket()
    while count > 0:
        try:
            ws.connect(url, header=['Authorization: Basic %s' %  encoded_creds])
            click.echo('ParaDrop log server connected!')
        except:
            click.echo('Failed to connect! Are you username and password correct?')
            count -= 1
            username = builtins.input('Username: ')
            password = getpass.getpass('Password: ')
            userpass = "{}:{}".format(username, password)
            encoded_creds = base64.b64encode(userpass.encode('utf-8')).decode('ascii')
            continue

        while True:
            try:
                message = ws.recv()
                click.echo(message)
            except:
                ws.close()
                click.echo('ParaDrop log server disconnected')
                sys.exit(0)
