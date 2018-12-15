#!/usr/bin/env python

import requests
from slack import SlackClient
from deepdiff import DeepDiff
from pprint import pprint
from time import sleep
import random
import hashlib
import json

slack = SlackClient(
        SLACK_TOKEN_NAME="SLACK_API_TOKEN",
        module_name="Config Reporter"
    )


def config_reporter(km_server):
    # Check kotekan master for unique_md5sums.
    try:
        km_status = requests.get(km_server+'/status-kotekan-master').json()
        unique_md5sums = km_status.get('nodes').get('unique_md5sums')
        node_md5sums = km_status.get('nodes').get('node_md5sums')
        md5_map = {}
        unique_configs = {}
        comparison_report = {}
        if len(unique_md5sums.keys()) > 1:
            # Find all the unique md5sums
            for md5 in unique_md5sums:
                md5_map[md5] = []
                for node in node_md5sums.keys():
                    if node_md5sums[node].get('md5sum') == md5:
                        md5_map[md5].append(node)
            # For each md5sum get config from a node
            for md5 in md5_map.keys():
                node = random.choice(md5_map.get(md5))
                unique_configs[md5] = requests.get(
                    url='http://{}:12048/config'.format(node)
                ).json()
            # Compare with kotekan master config
            km_config = km_status.get('current_config')
            _md5 = hashlib.md5()
            _md5.update(json.dumps(km_config, sort_keys=True, separators=(",", ":")))
            km_md5 = _md5.hexdigest()
            for md5 in unique_configs.keys():
                md5_config = unique_configs[md5]
                diff = DeepDiff(km_config, md5_config)
                pprint(diff)
                comparison_report[md5] = diff

             slack.error(
                 msg_title='Array Desync Report',
                 msg='KotekanMaster MD5: {}'.format(km_md5),
                 as_inline_code=True,
             )
             for md5 in md5_map:
                 slack.error(
                     msg_title=str(md5),
                     msg='Nodes running this config: {}'.format(md5_map[md5]),
                     as_inline_code=True,
                 )
                 slack.error(
                     msg_title='Deepdiff against km config',
                     msg=comparison_report[md5],
                     as_inline_code=True
                 )
             
        else:
            pprint('Array in sync.')
    except Exception as e:
        raise e


if __name__ == '__main__':
    while True:
        km_server = 'http://csBfs:54323'
        config_reporter(km_server)
        sleep(60)
