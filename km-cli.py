#!/usr/bin/env python

"""
Kotekan Master Command Line Interface
"""

# Imports
import re
import pprint as pp
import click
import requests


# Global Parameters
HOSTNAME = "csBfs"
PORT = 54323

CANS = ["n", "s"]
RACKS = [0, 1, 2, 3, 4, 5, 6, 8, 9, "A", "B", "C", "D", "E"]
NODES = range(10)
VALID_NODES = []
for can in CANS:
    for rack in RACKS:
        for node in NODES:
            VALID_NODES.append("c{}{}g{}".format(can, rack, node))


# Private REST API for the CLI
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
        except requests.exceptions.RequestException as error:
            print("JSON Error: {}".format(error))
            return "Could not exceute command: {}".format(command)
    except requests.exceptions.RequestException as error:
        raise error


def _post_command(command, data):
    """
    RESTful POST
    """
    url = "http://{0}:{1}/{2}".format(HOSTNAME, PORT, command)
    try:
        post = requests.post(url, json=data)
        post.raise_for_status()
        return post.json()
    except requests.exceptions.RequestException as err:
        raise err


# MAIN CLI GROUP
@click.group()
@click.version_option(
    version="2018.08",
    prog_name="km-cli",
    message="%(prog)s %(version)s",
)
def cli():
    """
    KotekanMaster Command Line Interface
    """
    pass


# GPU Cluster CLI Commands
@click.group("cluster", help="Manage the CHIME GPU Cluster")
def cluster():
    pass


@cluster.command("start-kotekan", help="start kotekan on all nodes")
def start_kotekan():
    """
    Start kotekan on all nodes managed by KotekanMaster
    """
    value = click.prompt(
        "Are you sure you want to START kotekan on the entire cluster [y|n]?",
        type=click.STRING,
    )
    if value == "y":
        start_status = _get_command("start-kotekan")
        pp.pprint(start_status)
    else:
        click.echo("ABORTED: start-kotekan command")


@cluster.command("stop-kotekan", help="stop kotekan on all nodes")
def stop_kotekan():
    """
    Stop kotekan on all nodes managed by KotekanMaster
    """
    value = click.prompt(
        "Are you sure you want to STOP kotekan on the entire cluster [y|n]?",
        type=click.STRING,
    )
    if value == "y":
        stop_status = _get_command("stop-kotekan")
        pp.pprint(stop_status)
    else:
        click.echo("ABORTED: stop-kotekan command")


@cluster.command(
    "restart-cluster",
    help="Re-acquire GPS clock and restart kotekan on the entire cluster",
)
def restart_cluster():
    """
    Restart the entire GPU cluster
    """
    value = click.prompt(
        "Are you sure you want to RE-ACQUIRE GPS clock & RESTART kotekan on the entire cluster [y|n]?",
        type=click.STRING,
    )
    if value == "y":
        restart_status = _get_command("restart-cluster")
        pp.pprint(restart_status)
    else:
        click.echo("ABORTED: restart-cluster command")


@cluster.command("blacklist", help="blacklist a node|rack|seacan")
@click.option(
    "--nodes",
    type=click.STRING,
    required=True,
    help="cn|cs to blacklist entire seacan, e.g. --nodes cs\
          cs[0-9,A-D] to blacklist entire rack, e.g. --nodes cn3\
          cs[0-9,A-D]g[0-9] to blacklist a node, e.g. --nodes cn[3,B]g7\
          NOTE: --nodes argument is case-sensitive.",
)
def blacklist(nodes):
    """
    Blacklist a node from being managed by KotekanMaster
    """
    #nodes = nodes.lower()
    regex = re.compile(nodes)
    current_nodes = filter(regex.match, VALID_NODES)
    click.echo("Blacklist-ing Nodes : {} ".format(current_nodes))
    data = {"node_list": current_nodes}
    blacklist_status = _post_command("blacklist-node", data)
    click.echo(blacklist_status)


@cluster.command("whitelist", help="whitelist a node|rack|seacan")
@click.option(
    "--nodes",
    type=click.STRING,
    required=True,
    help="cn|cs to whitelist entire seacan, e.g. --nodes cs\
          cs[0-9,A-D] to whitelist entire rack, e.g. --nodes cn3\
          cs[0-9,A-D]g[0-9] to whitelist a node, e.g. --nodes cn[0-3,A]g[0-1]\
          NOTE: --nodes argument is case-sensitive",
)
def whitelist(nodes):
    """
    Whitelist a node to be managed by KotekanMaster
    """
    #nodes = nodes.lower()
    regex = re.compile(nodes)
    current_nodes = filter(regex.match, VALID_NODES)
    click.echo("Whitelist-ing Nodes : {}".format(current_nodes))
    data = {"node_list": current_nodes}
    whitelist_status = _post_command("whitelist-node", data)
    click.echo(whitelist_status)


# CHIME/FRB CLI Commands
@click.group("frb-config", help="Change CHIME/FRB Configuration")
def frb():
    pass


@frb.command("gains")
@click.option(
    "-d",
    "--directory",
    type=click.STRING,
    required=True,
    help="e.g. --directory /path/to/gains/dir",
)
def update_gains(directory):
    """
    Update gains directory
    """
    data = {"gain_dir": directory}
    update_gains_status = _post_command("update-gain-dir", data)
    click.echo(update_gains_status)


@frb.command("east-west")
@click.option(
    "-cs",
    "--column-spacing",
    "column_spacing",
    is_flag=False,
    required=True,
    type=click.Tuple([click.IntRange(0, 3), float]),
    help="e.g. --spacing (column, spacing)",
)
def update_ew(column_spacing):
    """
    Update east-west column spacing
    """
    data = {
        "east_west_id": column_spacing[0],
        "east_west_beam": column_spacing[1],
    }
    ew_spacing_status = _post_command("update-east-west-beam", data)
    click.echo(ew_spacing_status)


@frb.command("north-south")
@click.option(
    "-be",
    "--beam-extent",
    "beam_extent",
    is_flag=False,
    required=True,
    type=click.FLOAT,
    help="e.g. --beam-extent 66.6",
)
def update_ns(beam_extent):
    """
    Update north/south-most beam extent
    """
    data = {"northmost_beam": beam_extent}
    update_northmost_extent_status = _post_command(
        "update-north-south-beam", data
    )
    click.echo(update_northmost_extent_status)


# CHIME/PULSAR CLI Commands
@click.group("pulsar-config", help="Change CHIME/PULSAR Configuration")
def pulsar():
    pass


@pulsar.command("update-beam")
@click.option(
    "-p",
    "--parameters",
    "beam_parameters",
    is_flag=False,
    required=True,
    type=click.Tuple(
        [click.IntRange(0, 10), click.FLOAT, click.FLOAT, click.INT]
    ),
    help="e.g. -p <BEAM_NUMBER> <RA> <DEC> <SCALING>\n\
          e.g. --parameters 3 66.6 23.3 48",
)
def update_pulsar_pointing(beam_parameters):
    """
    Update CHIME/Pulsar beam pointing
    """
    data = {
        "beam": beam_parameters[0],
        "ra": beam_parameters[1],
        "dec": beam_parameters[2],
        "scaling": beam_parameters[3],
    }
    print(data)
    pulsar_pointing_status = _post_command("update-pulsar-pointing", data)
    click.echo(pulsar_pointing_status)


# CHIME/COSMOLOGY CLI Commands
@click.group("cosmology-config", help="Change CHIME Configuration")
def cosmology():
    pass


@cosmology.command("Work-In-Progress", help="Nothing to do 0.0")
def cosmology_config():
    pass


@click.command("status", help="Get Status from KotekanMaster")
@click.option(
    "--all", "status_option", flag_value="all", help="get all status reports"
)
@click.option(
    "--gps", "status_option", flag_value="gps", help="get current gps status"
)
@click.option(
    "--config",
    "status_option",
    flag_value="config",
    help="get current kotekan config",
)
@click.option(
    "--nodes",
    "status_option",
    flag_value="nodes",
    help="get current node-list",
)
@click.option(
    "--blacklist",
    "status_option",
    flag_value="blacklist",
    help="get node blacklist",
)
@click.option(
    "--watchdog",
    "status_option",
    flag_value="watchdog",
    help="get watchdog statistics",
)
@click.option(
    "--frb",
    "status_option",
    flag_value="frb",
    help="get frb gains, beam spacing/extent ",
)
@click.option(
    "--start-time",
    "status_option",
    flag_value="start-time",
    help="get km start time",
)
@click.option(
    "--cal-broker",
    "status_option",
    flag_value="cal_broker",
    help="get calibration broker status",
)
@click.option(
    "--pulsar-beams",
    "status_option",
    flag_value="pulsar_beams",
    help="get current pulsar pointings",
)
def get_status(status_option):
    """
    GET KotekanMaster status
    """
    status = _get_command("status-kotekan-master")

    if (status_option == "all") or (status_option is None):
        data_to_print = status.keys()
        data_to_print.remove("current_config")
        data_to_print.remove("nodes")

    elif status_option == "gps":
        data_to_print = ["gps_status"]

    elif status_option == "config":
        data_to_print = ["current_config"]

    elif status_option == "nodes":
        data_to_print = ["nodes"]

    elif status_option == "blacklist":
        data_to_print = ["blacklist_nodes"]

    elif status_option == "start-time":
        data_to_print = ["start_time"]

    elif status_option == "watchdog":
        data_to_print = ["watchdog_status"]

    elif status_option == "frb":
        data_to_print = ["frb_status"]

    elif status_option == "cal_broker":
        data_to_print = ["calibration_broker_status"]

    elif status_option == "pulsar_beams":
        data_to_print = ["pulsar_status"]

    try:
        for key in data_to_print:
            pp.pprint(key)
            pp.pprint(status[key])
    except Exception as error:
        raise error


# Adding commands to the cli group
cli.add_command(get_status)
cli.add_command(frb)
cli.add_command(cluster)
cli.add_command(pulsar)
cli.add_command(cosmology)

if __name__ == "__main__":
    cli()
