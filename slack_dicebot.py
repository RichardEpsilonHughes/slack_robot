#!/usr/bin/env python
# coding=utf-8

import re

import slacker
from slacksocket import SlackSocket

from game_objects import CardDeck, CardPile, color_deck
from slack_objects import Message, Response
from slack_token import SLACK_TOKEN, BOT_USER_ID

POST_CHANNEL = '#test-channel'
slack = slacker.Slacker(SLACK_TOKEN)

## Reg-Ex compiler help-function.

def re_comp(pattern):
    pattern = pattern.format(BOT_USER_ID=("<@"+BOT_USER_ID+">:?"))
    return re.compile(pattern, flags=re.IGNORECASE)

## Game Logic

class RegexResponder(object):
    "An abstract class that defines the basic call-response loop."

    REGEX_METHOD_BY_STATE = None

    def __init__(self):
        assert hasattr(self,'REGEX_METHOD_BY_STATE'), "No REGEX_METHOD_BY_STATE for a regex responder?"
        assert isinstance(self.REGEX_METHOD_BY_STATE, dict)
        for value in self.REGEX_METHOD_BY_STATE.itervalues():
            assert type(value) == type(())
            for regex_method in value:
                assert len(regex_method) == 2
                regexobj, method_name = regex_method
                assert isinstance(regexobj, re._pattern_type)
                assert isinstance(method_name, basestring)
                assert hasattr(self, method_name)
        self._state = None

    def respond_to_message(self, msg):
        "Get message, adjust internal state, and reply with a message."
        # Iterate over the list of (regex_obj/method_name) pairs for our current
        # state, and test regex's until we get one that matches. Use the
        # response_method to calculate the return value.
        response_method, match_obj = None, None
        print "Text: {}".format(msg.text)
        for reg_ex_obj, method_name in self.REGEX_METHOD_BY_STATE[self._state]:
            print "Testing {}...".format(reg_ex_obj.pattern)
            match_obj = reg_ex_obj.search(msg.text)
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

    # Game States.
    ASLEEP = 0
    ACCEPTING_PLAYERS = 1
    ACTIVE_GAME = 2

    REGEX_METHOD_BY_STATE = {
        ASLEEP:(
            (re_comp(r'{BOT_USER_ID}.+wake'),
             '_wake_up'),
            (re_comp(r'{BOT_USER_ID}.+quit'),
             '_quit'),
            (re_comp(r'{BOT_USER_ID}'),
             '_grumble'),
            ),
        ACCEPTING_PLAYERS:(
            # Go back to sleep.
            (re_comp(r'{BOT_USER_ID}.+sleep'),
             '_back_to_sleep'),
            # Help?
            (re_comp(r'{BOT_USER_ID}\s.*help'),
             '_help'),
            # Add me as a player.
            (re_comp(r'{BOT_USER_ID}\s+join'),
             '_add_player'),
            # Remove me as a player.
            (re_comp(r'{BOT_USER_ID}\s+leave'),
             '_remove_player'),
            # Who is playing?
            (re_comp(r'{BOT_USER_ID}\s+list'),
             '_list_players'),
            # Start playing.
            (re_comp(r'{BOT_USER_ID}\s+begin\s+game'),
             '_begin_game'),
            ),
        ACTIVE_GAME:(
            # Back to sleep.
            (re_comp(r'{BOT_USER_ID}.+sleep'),
             '_back_to_sleep'),
            # TODO: What is in my hand?
            # TODO: Deal {person} {num_cards} cards.
        )}

    def __init__(self, decks=None, hands=None):
        super(CardGame, self).__init__()

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

        self._players = dict()
        self._state = self.ASLEEP
        self._game_chan_id = None
        self._game_chan_name = None

    def _no_im(self, msg):
        if msg.im:
            return Response(text="Try again, but in a channel, not in an IM.",chan_id=msg.chan_id)

    def _quit(self, match=None, msg=None):
        raise SystemExit

    def _grumble(self, match=None, msg=None):
        return Response(text="Gnr... zzz.... snr...",chan_id=msg.chan_id)

    def _wake_up(self, match=None, msg=None):
        print match
        interrupt = self._no_im(msg)
        if interrupt: return interrupt
        print "WAKE UP"
        self._state = self.ACCEPTING_PLAYERS
        self._game_chan_id = msg.chan_id
        self._game_chan_name = msg.chan_name
        return self._help(msg=msg)

    def _back_to_sleep(self, match=None, msg=None):
        print match
        interrupt = self._no_im(msg)
        if interrupt: return interrupt
        print "NAPPING"
        self._state = self.ASLEEP
        self._game_chan_id = None
        self._game_chan_name = None
        return Response(text="Yawn... zzz", chan_id=msg.chan_id)

    def _help(self, match=None, msg=None):
        if self._state == self.ACCEPTING_PLAYERS:
            text = u'\n'.join((
                u'Card game is ready to start in #{CHANNEL} after players join:',
                u' • `<@{BOT_USER_ID}> sleep`: Put <@{BOT_USER_ID}> back to sleep.',
                u' • `<@{BOT_USER_ID}> join`: Join the game.',
                u' • `<@{BOT_USER_ID}> leave`: Leave the game.',
                u' • `<@{BOT_USER_ID}> list`: List the players in the game.',
                u' • `<@{BOT_USER_ID}> begin game`: Start the game.',
                u' • `<@{BOT_USER_ID}> help`: Play this message again.',
            )).format(
                BOT_USER_ID=BOT_USER_ID,
                CHANNEL=self._game_chan_name,
            )
            return Response(text=text, chan_id=msg.chan_id)
        return None

    def _add_player(self, match=None, msg=None):
        assert self._game_chan_id
        player_id = msg.user_id
        if player_id in self._players:
            return Response(text="You're already in this game.", chan_id=msg.chan_id)
        self._players[player_id] = msg.user_name
        responses = [Response(
            text="<@{}> has joined the game.".format(msg.user_name), chan_id=self._game_chan_id)]
        if msg.im:
            responses.append(
                # Private message.
                Response(text="You've joined the game.", chan_id=msg.chan_id))
        return tuple(responses)

    def _remove_player(self, match=None, msg=None):
        responses = []
        player_id = msg.user_id
        if player_id not in self._players:
            return Response(text="You aren't a player, tho.", chan_id=msg.chan_id)
        del self._players[player_id]
        responses.append(Response(
            text="<@{}> has left the game.".format(msg.user_name), chan_id=self._game_chan_id))
        if msg.im:
            responses.append(
                # Private message.
                Response(text=u"You've left the game.", chan_id=msg.chan_id))
        return tuple(responses)

    def _list_players(self, match=None, msg=None):
        if not self._players:
            return Response(text="No one is playing yet. Sad!", chan_id=msg.chan_id)
        players = u'\n'.join(
            u' • <@{}>'.format(player_name)
            for player_name in self._players.itervalues())
        return Response(text=u"The players are:\n{}".format(players), chan_id=msg.chan_id)

    def _begin_game(self, match=None, msg=None):
        self._state=self.ACTIVE_GAME
        return Response(text="WE GAMING NOW", chan_id=self._game_chan_id)

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
            # Not even worth mentioning.
            return
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

    def _write_to_channel(self, response):
        message = response.text.replace("@channel", "<!channel|@channel>")
        channel = response.chan_id
        if not channel or not message:
            # TODO: Implement instant messaging by player name/id.
            return
        self.slack.chat.post_message(channel, message, as_user=True)

    def listen(self):
        for e in self.socket.events():

            # Convert socket event to Message object, if possible.
            try:
                msg = self._parse_message(e)
            except StandardError, err:
                print err
                continue
            if not msg:
                continue

            # TODO: Implement 'sleeping' and 'waking' states.

            # TODO: Implement 'select a game to play' functionality.

            responses = self.responder.respond_to_message(msg)
            if not responses:
                continue
            if not isinstance(responses, (set, list, tuple)):
                responses = [responses]
            for response in responses:
                self._write_to_channel(response)


def main():
    si = SlackInterface(card_game)
    si.listen()

if __name__ == '__main__':
    main()