#!/usr/bin/env python

import logging
import re

import slacker
from slacksocket import SlackSocket
from collections import OrderedDict

from slack_objects import Message
from game_objects import Card, CardDeck, CardPile

POST_CHANNEL = '#test-channel'
SLACK_TOKEN = "xoxb-41370365543-eyugiTyl6kqbjO91WVEo5d0S"
BOT_USER_ID = u"U17AWARFZ"
slack = slacker.Slacker(SLACK_TOKEN)

## Cards and card collections
color_deck = CardDeck([Card(name=name) for name in
    ('Red','Orange','Yellow','Green','Blue','Indigo','Violet')], name='ColorDeck')
hand_1 = CardPile(name='hand_1')
hand_2 = CardPile(name='hand_2')

## Game Logic

class RegexResponder(object):
    "An abstract class that defines the basic call-response loop."

    def respond_to_message(self, msg):
        "Get message, adjust internal state, and reply with a message."
        # Iterate over the list of (regex_obj/method_name) pairs for our current
        # state, and test regex's until we get one that matches. Use the
        # response_method to calculate the return value.
        response_method = None
        for reg_ex_obj, method_name in self.REGEX_METHOD_BY_STATE[self._state]:
            match_obj = reg_ex_obj.match(msg.text)
            if match_obj:
                response_method = getattr(self,method_name)
                break

        # If we don't find a match, no response.
        if not response_method:
            return

        return response_method(match=match_obj, msg=msg)

class Game(object):

    # Games have players!
    @property
    def players(self):
        "Return a read-only view on the player IDs."
        return frozenset(self._players)
    def add_player(self, player):
        raise NotImplementedError
    def remove_player(self, player):
        raise NotImplementedError
    def player_status(self, player):
        raise NotImplementedError

class CardGame(Game):

    STATE_ASLEEP = 0
    STATE_AWAKE = 1

    REGEX_METHOD_BY_STATE = {
        ASLEEP:(
            (re.compile(r'<@{0}> wake up'.format(BOT_USER_ID)),
             '_wake_up'),
            ),
        AWAKE:(
            (re.compile(r'.*'),
             '_echo'),
            ) }

    def __init__(self, decks=None, hands=None):
        # The deck or decks are the cards in play at the beginning of the game.
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

    def _wake_up(match=None, msg=None):
        raise NotImplementedError

    def _echo(match=None, msg=None):
        raise NotImplementedError

card_game = CardGame(decks=color_deck)

## The Slack Listener

import ipdb; ipdb.set_trace()

class SlackInterface:

    MESSAGES = {
        'hello_world': (
            "Hello, world. I'm posting this to @channel in response to {user}."),
    }

    POST_CHANNEL = '#test-channel'
    FAKE_PM_CHANNEL_NAME = '___private_message___'
    SLACK_TOKEN = "xoxb-41370365543-eyugiTyl6kqbjO91WVEo5d0S"
    BOT_USER_ID = u"U17AWARFZ"

    def __init__(self):
        self.slack = slacker.Slacker(SLACK_TOKEN)
        self.socket = SlackSocket(SLACK_TOKEN, translate=False)
        self.user_to_id = {}
        self.id_to_user = {}
        self.channel_to_id = {}
        self.id_to_channel = {}
        self.im_channels = set()
        self.awake = False
        self.game = CardGame(decks=color_deck)

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

    def _get_channel_name_and_type(self, channel_id):
        # Check caches.
        if channel_id in self.id_to_channel:
            is_im = False
            return self.id_to_channel[channel_id], is_im
        elif channel_id in self.im_channels:
            is_im = True
            return self.FAKE_PM_CHANNEL_NAME, is_im

        # Is this a public or private channel?
        try:
            channel_name = self.slack.channels.info(channel_id)
            channel_name = channel_name.body['channel']['name']
            self.id_to_channel[channel_id] = channel_name
            is_im = False
            return channel_name, is_im
        except slacker.Error, e:
            if e.message != u'channel_not_found':
                raise

        # Is this an IM channel?
        if channel_id in [im['id'] for im in self.slack.im.list().body['ims']]:
            self.im_channels.add(channel_id)
            channel_name = self.FAKE_PM_CHANNEL_NAME
            is_im = True
            return self.FAKE_PM_CHANNEL_NAME, is_im

        raise ValueError, "Channel {} is neither chat channel nor IM channel".format(channel_id)

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
        s = self
        for e in self.socket.events():

            # Convert socket event to Message object, if possible.
            try:
                msg = self._parse_message(e)
            except StandardError, err:
                print err
                continue

            # TODO: Implement 'sleeping' and 'waking' states.

            # TODO: Implement 'select a game to play' functionality.

            if msg.im: self._echo(msg)
            continue

            # TODO:
            response = self.game.respond_to_message(msg)
            continue
            ## DEBUG LOOP

            if _filter_event(e):
                print _filter_event(e)
                continue
            if e.type not in ('message',):
                print "event.type != message; type is {}".format(e.type)
                continue
            if e.event['user'] == BOT_USER_ID:
                print "event.event['user'] == BOT_USER_ID"
                continue

            text = e.event['text']
            if ('<@%s>'%BOT_USER_ID) not in text:
                print "('<@%s>'%BOT_USER_ID) not in text - continue"
                continue

            try:
                channel_name = get_channel_name(event.event['channel'])
                user_name = get_user_name(event.event['user'])
            except:
                print "Couldn't get channel name and/or user name."
                import ipdb; ipdb.set_trace()
                continue

            print (channel_name, user_name, text)

            if 'debug' in text:
                import ipdb
                ipdb.set_trace()
            elif 'puppy' in text:
                notify_slack(channel_name, 'dog joke placeholder')
            elif re.search('roll (\d+)', text):
                m = re.search('roll (\d+)', text)
                roll_dice(channel_name, int(m.group(1)))


def main():
    si = SlackInterface()
    si.listen()

if __name__ == '__main__':
    main()