#!/usr/bin/env python

import re

import slacker
from slacksocket import SlackSocket

from slack_objects import Message, Response
from game_objects import Card, CardDeck, CardPile, color_deck
from slack_token import SLACK_TOKEN, BOT_USER_ID

POST_CHANNEL = '#test-channel'
slack = slacker.Slacker(SLACK_TOKEN)

## Game Logic

class RegexResponder(object):
    "An abstract class that defines the basic call-response loop."

    def respond_to_message(self, msg):
        "Get message, adjust internal state, and reply with a message."
        # Iterate over the list of (regex_obj/method_name) pairs for our current
        # state, and test regex's until we get one that matches. Use the
        # response_method to calculate the return value.
        response_method = None
        print "Text: {}".format(msg.text)
        for reg_ex_obj, method_name in self.REGEX_METHOD_BY_STATE[self._state]:
            print "Testing {}...".format(reg_ex_obj.pattern)
            match_obj = reg_ex_obj.match(msg.text)
            if match_obj:
                print "Matched;",str(match_obj)
                response_method = getattr(self,method_name)
                break

        # If we don't find a match, no response.
        if not response_method:
            print "No match."
            return

        return response_method(match=match_obj, msg=msg)

class CardGame(RegexResponder):

    ASLEEP = 0
    AWAKE = 1

    REGEX_METHOD_BY_STATE = {
        ASLEEP:(
            (re.compile(r'.*<@{0}>.+wake.*'.format(BOT_USER_ID)),
             '_wake_up'),
            ),
        AWAKE:(
            (re.compile(r'.*<@{0}>.+sleep.*'.format(BOT_USER_ID)),
             '_sleep'),
            (re.compile(r'.*'),
             '_echo'),
            ) }

    def __init__(self, decks=None, hands=None):
        # The deck or decks are the cards in play at the beginning of the game.
        self._players = set()

        if isinstance(decks, CardDeck):
            decks = [decks]
        else:
            assert isinstance(decks,(tuple,set,list))
            assert all(isinstance(d, CardDeck) for d in decks)

        # These are the 'hands' that each player will have.
        if isinstance(hands, CardPile):
            hands = [hands]
        elif hands:
            assert isinstance(hands,(tuple,set,list))
            assert all(isinstance(h, CardPile) for h in hands)

        self._players = set()
        self._state = self.ASLEEP
        self._game_channel = None

    def _wake_up(self, match=None, msg=None):
        print "WAKE UP"
        self._state = self.AWAKE
        return Response(
            text="...I'm awake, jeez!",
            chan_id=msg.chan_id)

    def _echo(self, match=None, msg=None):
        if not msg.im:
            print "ECHOING"
            return Response(text=msg.text, chan_id=msg.chan_id)
        else:
            print "NO ECHO"
            return None

    def _sleep(self, match=None, msg=None):
        print "NAPPING"
        self._state = self.ASLEEP
        return Response(text="Yawn... zzz", chan_id=msg.chan_id)

card_game = CardGame(decks=color_deck)

## The Slack Listener

class SlackInterface:

    MESSAGES = {
        'hello_world': (
            "Hello, world. I'm posting this to @channel in response to {user}."),
    }

    POST_CHANNEL = '#test-channel'
    FAKE_PM_CHANNEL_NAME = '___private_message___'

    def __init__(self, responder=None):
        assert isinstance(responder, RegexResponder)
        self.responder = responder

        self.slack = slacker.Slacker(SLACK_TOKEN)
        self.socket = SlackSocket(SLACK_TOKEN, translate=False)
        self.user_to_id = {}
        self.id_to_user = {}
        self.channel_to_id = {}
        self.id_to_channel = {}
        self.im_channels = set()
        self.awake = False

    def _parse_message(self, e):
        if e.type not in ('message',):
            raise ValueError("event.type != message; type is {}".format(e.type))
        if e.event['user'] == BOT_USER_ID:
            raise ValueError("message is from me")
        text = e.event['text']
        user_name = self._get_user_name(e.event['user'])
        channel_name, is_im = self._get_channel_name_and_type(e.event['channel'])
        print (text, user_name, channel_name, is_im)
        return Message(
            text=text,
            user_id=e.event['user'],
            user_name=user_name,
            chan_id=e.event['channel'],
            chan_name=channel_name,
            im=is_im)

    def _get_channel_name_and_type(self, chan_id):
        # Check caches.
        if chan_id in self.id_to_channel:
            is_im = False
            return self.id_to_channel[chan_id], is_im
        elif chan_id in self.im_channels:
            is_im = True
            return self.FAKE_PM_CHANNEL_NAME, is_im

        # Is this a public or private channel?
        try:
            channel_name = self.slack.channels.info(chan_id)
            channel_name = channel_name.body['channel']['name']
            self.id_to_channel[chan_id] = channel_name
            is_im = False
            return channel_name, is_im
        except slacker.Error, e:
            if e.message != u'channel_not_found':
                raise

        # Is this an IM channel?
        if chan_id in [im['id'] for im in self.slack.im.list().body['ims']]:
            self.im_channels.add(chan_id)
            is_im = True
            return self.FAKE_PM_CHANNEL_NAME, is_im

        raise ValueError, "Channel {} is neither chat nor IM.".format(chan_id)

    def _get_user_name(self, user_id):
        if user_id in self.id_to_user:
            return self.id_to_user[user_id]
        else:
            user = self.slack.users.info(user_id).body['user']
            user_name = user['real_name'] or user['name']
            self.id_to_user[user_id] = user_name
            self.user_to_id[user_name] = user_id
            return user_name

    def _echo(self, msg):
        assert isinstance(msg, Message)
        self._write_to_channel(msg.chan_id,msg.text)
        pass

    def _write_to_channel(self, channel, message):
        message = message.replace("@channel", "<!channel|@channel>")
        self.slack.chat.post_message(channel, message, as_user=True)

    def listen(self):
        for e in self.socket.events():

            # Convert socket event to Message object, if possible.
            try:
                msg = self._parse_message(e)
            except StandardError, err:
                print err
                continue

            # TODO: Implement 'sleeping' and 'waking' states.

            # TODO: Implement 'select a game to play' functionality.

            response = self.responder.respond_to_message(msg)
            if not response:
                continue
            if not isinstance(response, (set, list, tuple)):
                response = [response]
            self._write_to_channel(response.chan_id, response.text)


def main():
    si = SlackInterface(card_game)
    si.listen()

if __name__ == '__main__':
    main()