# -*- coding: utf-8 -*-


# Imports
from urllib.parse import urlencode
import urllib.request as urlrequest
import json


class Slack(object):
    """
    python-object to interact with slack webhooks api.

    Usage
    -----
        slack = slack.Slack(url=API_URL)

    Simple Message
    --------------
        slack.notify(text="Test Message")

    Custom Message
    --------------
        slack.notify(text="Test",
                     channel="#general",
                     username="username",
                     icon_emoji=":sushi:")

    Rich-Formage Message
    --------------------
    payloads = []
    payload = {"title": "Test",
               "pretext": "__TEST__",
               "text": "Testing *right now!*",
               "mrkdwn_in": ["text", "pretext"]
              }
    payloads.append(payload)
    slack.notify(attachment=payloads)

    """

    def __init__(self, url=""):
        self.url = url
        self.opener = urlrequest.build_opener(urlrequest.HTTPHandler())

    def notify(self, **kwargs):
        """
        Send message to slack API
        """
        return self.send(kwargs)

    def send(self, payload):
        """
        Send payload to slack API
        """
        payload_json = json.dumps(payload)
        data = urlencode({"payload": payload_json})
        req = urlrequest.Request(self.url)
        response = self.opener.open(req, data.encode('utf-8')).read()
        return response.decode('utf-8')
