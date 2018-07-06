# -*- coding: utf-8 -*-

"""
Send Messages to Slack using Slack Incoming Webhooks
"""

# Imports
from urllib import urlencode
import urllib2 as urlrequest
import json
import time

"""
Slack Message Colors
    |-----------|---------|
    | LOG LEVEL |  COLOR  |
    |-----------|---------|
    | DEBUG     | #268bd2 |
    | INFO      | #859900 |
    | WARNING   | #6c71c4 |
    | ERROR     | #cb4b16 |
    | CRITICAL  | #dc2f2f |
    |-----------|---------|
"""


class Slack():
    """
    Client to send messages to slack.

    Parameters
    ----------
        slack_token_url : str
            Slack Webhook URL
        module_name : str
            Name of the module sending messages to slack
    """

    def __init__(self, slack_token_url, module_name):
        self.url = slack_token_url
        self.opener = urlrequest.build_opener(urlrequest.HTTPHandler())
        self.module_name = module_name

    ###########################################################################
    #                        Public Messages API                              #
    ###########################################################################
    def send_text_message(self, text):
        return self._notify(text=text)

    def debug_message(self, msg_title=None, msg_text=None):
        return self._send_message(
            msg_title=msg_title, msg_text=msg_text, msg_level='DEBUG')

    def info_message(self, msg_title=None, msg_text=None):
        return self._send_message(
            msg_title=msg_title, msg_text=msg_text, msg_level='INFO')

    def warning_message(self, msg_title=None, msg_text=None):
        return self._send_message(
            msg_title=msg_title, msg_text=msg_text, msg_level='WARNING')

    def error_message(self, msg_title=None, msg_text=None):
        return self._send_message(
            msg_title=msg_title, msg_text=msg_text, msg_level='ERROR')

    def critical_message(self, msg_title=None, msg_text=None):
        return self._send_message(
            msg_title=msg_title, msg_text=msg_text, msg_level='CRITICAL')

    # Core Communication
    def _notify(self, **kwargs):
        """
        Send message to slack API
        """
        return self._send(kwargs)

    def _send(self, payload):
        """
        Send payload to slack API
        """
        payload_json = json.dumps(payload)
        data = urlencode({"payload": payload_json})
        req = urlrequest.Request(self.url)
        response = self.opener.open(req, data.encode('utf-8')).read()
        return response.decode('utf-8')

    # Private Messaging API
    def _send_custom_mesaage(self, text, slack_channel, username, icon_emoji):
        self._notify(text=text,
                     slack_channel=slack_channel,
                     username=username,
                     icon_emoji=icon_emoji)

    def _send_attachment_message(self, attachments):
        self._notify(attachments=attachments)

    def _send_message(self, msg_title=None, msg_text=None, msg_level=None):
        """
        """
        try:
            color = self.get_message_color(log_level=msg_level)
        except Exception as e:
            raise e

        attachment = self.create_attachement(color=color,
                                             title=msg_title,
                                             text=msg_text,
                                             footer=self.module_name)
        status = self.send_attachment_message(attachments=attachment)
        return status

    # Create Messages API
    def create_attachement(self, fallback="", color="#999999", pretext="",
                           author_name="", author_link="", author_icon="",
                           title="", title_link="", text="",
                           fields=[], actions=[],
                           image_url="", thumb_url="",
                           footer="", footer_icon="",
                           timestamp=time.time()):
        # Generate the slack attachment
        slack_message = [
                {"fallback": fallback,
                 "color": color,
                 "pretext": pretext,
                 "author_name": author_name,
                 "author_link": author_link,
                 "author_icon": author_icon,
                 "title": title,
                 "title_link": title_link,
                 "text": text,
                 "fields": fields,
                 "actions": actions,
                 "image_url": image_url,
                 "thumb_url": thumb_url,
                 "footer": footer,
                 "footer_icon": footer_icon,
                 "ts": timestamp}
            ]
        return slack_message

    # Message Formatting
    def get_message_color(self, log_level):
        # Valid Message Levels and corresponding colors.
        valid_levels = {"DEBUG": "#268bd2",
                        "INFO": "#859900",
                        "WARN": "#6c71c4", "WARNING": "#6c71c4",
                        "ERROR": "#cb4b16",
                        "CRITICAL": "#dc2f2f", "CRIT": "#dc2f2f"}
        # Default Message Color (Grey)
        default_color = "#999999"

        try:
            assert type(log_level) == str
            if log_level.upper() in valid_levels.keys():
                message_color = valid_levels.get(log_level.upper())
            else:
                message_color = default_color
        except Exception as e:
            raise e
        return message_color


