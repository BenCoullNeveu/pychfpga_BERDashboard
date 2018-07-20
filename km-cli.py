#!/usr/bin/env python

"""
Kotekan Master Command Line Interface
"""

# Imports
import click
import requests
import pprint as pp

# Global Parameters
HOSTNAME = 'csBfs'
PORT = 54323


def _get_command(command):
    """
    RESTful GET
    """
    url = "http://{0}:{1}/{2}".format(HOSTNAME, PORT, command)
    try:
        get = requests.get(url)
        get.raise_for_status()
        return get.json()
    except requests.exceptions.HTTPError as err:
        raise err


def _post_command(command, data):
    """
    RESTful POST
    """
    url = "http://{0}:{1}/{2}".format(HOSTNAME, PORT, command)
    try:
        post = requests.post(url, data=data)
        post.raise_for_status()
        return post.json()
    except requests.exceptions.HTTPError as err:
        raise err


@click.group()
def cli():
    """
    KotekanMaster Command Line Interface
    """
    pass


@click.command("start-kotekan", help="Start kotekan on all nodes")
def start_kotekan():
    """
    Start kotekan on all nodes managed by KotekanMaster
    """
    click.echo("starting kotekan")


@click.command("stop-kotekan", help="Stop kotekan on all nodes")
def stop_kotekan():
    """
    Stop kotekan on all nodes managed by KotekanMaster
    """
    click.echo("stopping kotekan")


@click.command("blacklist-node", help="Blacklist a node")
@click.option("--node", type=str, required=True,
              help="node to blacklist, e.g. cn0g0")
def blacklist_node(node):
    """
    Blacklist a node from being managed by KotekanMaster
    """
    click.echo("Blacklist-ing Node: {}".format(node))


@click.command("whitelist-node", help="Whitelist a node")
@click.option("--node", type=str, required=True,
              help="node to whitelist, e.g. cn0g0")
def whitelist_node(node):
    """
    Blacklist a node from being managed by KotekanMaster
    """
    click.echo("Whitelist-ing Node: {}".format(node))


@click.command("get-status")
def get_status():
    """
    GET KotekanMaster status
    """
    status = _get_command("status-kotekan-master")
    status.pop('current_config')
    status.pop('nodes')
    pp.pprint(status)


# Adding commands to the cli group
cli.add_command(start_kotekan)
cli.add_command(stop_kotekan)
cli.add_command(blacklist_node)
cli.add_command(whitelist_node)
cli.add_command(get_status)

if __name__ == '__main__':
    cli()
