#!/usr/bin/env python

"""
Kotekan Master Command Line Interface
"""

# Imports
import re
import pprint as pp
import click
import requests
import json


# Global Parameters
HOSTNAME = 'csBfs'
PORT = 54323

CANS = ['n', 's']
RACKS = [0, 1, 2, 3, 4, 5, 6, 8, 9, 'A', 'B', 'C', 'D', 'E']
NODES = range(10)
VALID_NODES = []
for can in CANS:
    for rack in RACKS:
        for node in NODES:
            VALID_NODES.append("c{}{}g{}".format(can, rack, node))


# Private REST API
def _get_command(command):
    """
    RESTful GET
    """
    url = "http://{0}:{1}/{2}".format(HOSTNAME, PORT, command)
    try:
        get = requests.get(url)
        get.raise_for_status()
        try:
            return get.json()
        except:
            return "{} exceuted".format(command)
    except requests.exceptions.HTTPError as err:
        raise err


def _post_command(command, data):
    """
    RESTful POST
    """
    url = "http://{0}:{1}/{2}".format(HOSTNAME, PORT, command)
    try:
        post = requests.post(url, json=data)
        post.raise_for_status()
        return post.json()
    except requests.exceptions.HTTPError as err:
        raise err


# CLI
@click.group()
@click.version_option(version="2018.07rc5", prog_name='km-cli', message='%(prog)s %(version)s')
def cli():
    """
    KotekanMaster Command Line Interface
    """
    pass


@click.command("start-kotekan", help="start kotekan on all nodes")
def start_kotekan():
    """
    Start kotekan on all nodes managed by KotekanMaster
    """
    click.echo("starting kotekan")
    start_status = _get_command("start-kotekan")
    pp.pprint(start_status)


@click.command("stop-kotekan", help="stop kotekan on all nodes")
def stop_kotekan():
    """
    Stop kotekan on all nodes managed by KotekanMaster
    """
    click.echo("stopping kotekan")
    stop_status = _get_command("stop-kotekan")
    pp.pprint(stop_status)


@click.command("restart-cluster", help="restart the entire cluster")
def restart_cluster():
    """
    Restart the entire GPU cluster
    """
    click.echo("restarting cluster")
    value = click.prompt('Are you sure you want to restart the entire cluster [y|n]?', type=click.STRING)
    if value == 'y':
        restart_status = _get_command("restart-cluster")
        pp.pprint(restart_status)
    else:
        click.echo('aborting restart-cluster')


@click.command("blacklist", help="blacklist a node|rack|seacan")
@click.option('--nodes', type=click.STRING, required=True,
              help="cn|cs to blacklist entire seacan, e.g. --nodes cs\
                    cs[0-9,A-D] to blacklist entire rack, e.g. --nodes cn3\
                    cs[0-9,A-D]g[0-9] to blacklist a node, e.g. --nodes cn[3,B]g7")
def blacklist(nodes):
    """
    Blacklist a node from being managed by KotekanMaster
    """
    regex = re.compile(nodes)
    current_nodes = filter(regex.match, VALID_NODES)
    click.echo("Blacklist-ing Nodes : {} ".format(current_nodes))
    data = {"node_list": current_nodes}
    blacklist_status = _post_command('blacklist-node', data)
    click.echo(blacklist_status)


@click.command("whitelist", help="whitelist a node|rack|seacan")
@click.option("--nodes", type=click.STRING, required=True,
              help="cn|cs to whitelist entire seacan, e.g. --nodes cs\
                    cs[0-9,A-D] to whitelist entire rack, e.g. --nodes cn3\
                    cs[0-9,A-D]g[0-9] to whitelist a node, e.g. --nodes cn[0-3,A]g[0-1]")
def whitelist(nodes):
    """
    Whitelist a node to be managed by KotekanMaster
    """
    regex = re.compile(nodes)
    current_nodes = filter(regex.match, VALID_NODES)
    click.echo("Whitelist-ing Nodes : {}".format(current_nodes))
    data = {"node_list": current_nodes}
    whitelist_status = _post_command('whitelist-node', data)
    click.echo(whitelist_status)


@click.command("get-status", help="get status from kotekan master")
def get_status():
    """
    GET KotekanMaster status
    """
    status = _get_command("status-kotekan-master")
    status.pop('current_config')
    status.pop('nodes')
    pp.pprint(status)


@click.command("update-gains")
@click.option("--directory", type=click.STRING, required=True,
              help="update gains directory, e.g. --dir /home/gains/")
def update_gains(directory):
    """
    Update Gains Directory
    """
    data = {"gain_dir": directory}
    update_gains_status = _post_command('update-gain-dir', data)
    click.echo(update_gains_status)


# Adding commands to the cli group
cli.add_command(start_kotekan)
cli.add_command(stop_kotekan)
cli.add_command(restart_cluster)
cli.add_command(blacklist)
cli.add_command(whitelist)
cli.add_command(get_status)
cli.add_command(update_gains)


if __name__ == '__main__':
    cli()
