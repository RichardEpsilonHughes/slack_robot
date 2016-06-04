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

            ## PLAYER MANAGEMENT
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
            (re_comp(r'{BOT_USER_ID}'),
             '_grumble'),
            ),
        ACTIVE_GAME:(
            # Back to sleep.
            (re_comp(r'{BOT_USER_ID}.+sleep'),
             '_back_to_sleep'),
            # Help?
            (re_comp(r'{BOT_USER_ID}\s.*help'),
             '_help'),
            # Who is playing?
            (re_comp(r'{BOT_USER_ID}\s+list'),
             '_list_players'),
            ## HAND MANAGEMENT
            # TODO: What is in my hand? Or, uh, someone else's hand?
            (re_comp(r'{BOT_USER_ID}\s+check\s+hand\s*(?P<player_name>@?[\w.]*)'),
             '_check_hand'),
            # TODO: Return this card to the deck.
            (re_comp(r'{BOT_USER_ID}\s+return\s+card\s*(?P<card_name>[\s\w]*)'),
             '_return_card'),
            ## DECK MANAGEMENT
            # TODO: Shuffle!
            (re_comp(r'{BOT_USER_ID}\s+shuffle'),
             '_shuffle_deck'),
            # TODO: How many cards are in the deck? Or, lemme see the top X cards.
            (re_comp(r'{BOT_USER_ID}\s+check\s+deck\s*(?P<peek_depth>\d*)'),
             '_check_deck'),
            # TODO: Deal {person} {num_cards} cards.
            (re_comp('\s+deal\s+(?P<num_cards>\d+)\s+to\s(?P<player_name>@?[\w.]+)'),
             '_deal_cards'),
            (re_comp(r'{BOT_USER_ID}'),
             '_grumble'),
        )}

    def __init__(self, deck=None):
        super(CardGame, self).__init__()

        # The deck or decks are the cards in play at the beginning of the game.
        self._players = set()

        assert isinstance(deck, CardDeck)

        self._deck = deck
        self._players = dict()
        self._player_ids = dict()
        self._hands = dict()
        self._state = self.ASLEEP
        self._game_chan_id = None
        self._game_chan_name = None

    def _no_im(self, msg):
        if msg.im:
            return Response(text="Try again, but in a channel, not in an IM.",chan_id=msg.chan_id)

    def _quit(self, match=None, msg=None):
        raise SystemExit

    def _grumble(self, match=None, msg=None):
        text = {
            self.ASLEEP:"Gnr... zzz.... snr...",
            self.ACCEPTING_PLAYERS:'Wot?',
            self.ACTIVE_GAME:'Wot?',
            }[self._state]
        return Response(text=text,chan_id=msg.chan_id)

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
        self._state = self.ASLEEP
        self._game_chan_id = None
        self._game_chan_name = None
        return Response(text="Yawn... zzz", chan_id=msg.chan_id)

    def _help(self, match=None, msg=None):
        if self._state == self.ACCEPTING_PLAYERS:
            text = u'\n'.join((
                u'Card game is ready to start in #{CHANNEL} after players join:',
                u' • `<@{B_U_ID}> sleep`: Put <@{B_U_ID}> back to sleep.',
                u' • `<@{B_U_ID}> join`: Join the game.',
                u' • `<@{B_U_ID}> leave`: Leave the game.',
                u' • `<@{B_U_ID}> list`: List the players in the game.',
                u' • `<@{B_U_ID}> begin game`: Start the game.',
                u' • `<@{B_U_ID}> help`: Play this message again.', ))
        elif self._state == self.ACTIVE_GAME:
            text = u'\n'.join((
                u'Card game is going down in #{CHANNEL}.:',
                u' • `<@{B_U_ID}> sleep`: Put <@{B_U_ID}> back to sleep.',
                u' • `<@{B_U_ID}> check hand [player]`: Look at someone\'s hand. Default is your hand.',
                u' • `<@{B_U_ID}> return card [card name]`: Return a card in your hand to the bottom of the deck.',
                u' • `<@{B_U_ID}> shuffle`: Shuffle the deck.',
                u' • `<@{B_U_ID}> check deck`: Start the game.',
                u' • `<@{B_U_ID}> deal [num_cards] to [player]`: Deal off the top of the deck.',
            ))
        text=text.format(B_U_ID=BOT_USER_ID, CHANNEL=self._game_chan_name)
        return Response(text=text, chan_id=msg.chan_id)

    def _add_player(self, match=None, msg=None):
        assert self._game_chan_id
        player_id = msg.user_id
        player_name = msg.user_name.lower()
        if player_id in self._players:
            return Response(text="You're already in this game.", chan_id=msg.chan_id)
        self._players[player_id] = player_name
        self._player_ids[player_name] = player_id
        self._hands[player_id] = CardPile(name='Hand of {}'.format(player_name))
        responses = [Response(
            text="<@{}> has joined the game.".format(player_name), chan_id=self._game_chan_id)]
        if msg.im:
            responses.append(
                # Private message.
                Response(text="You've joined the game.", chan_id=msg.chan_id))
        return tuple(responses)

    def _remove_player(self, match=None, msg=None):
        responses = []
        player_id = msg.user_id
        player_name = msg.user_name.lower()
        if player_id not in self._players:
            return Response(text="You aren't a player, tho.", chan_id=msg.chan_id)
        del self._players[player_id]
        del self._player_ids[player_name]
        del self._hands[player_id]
        responses.append(Response(
            text="<@{}> has left the game.".format(player_name), chan_id=self._game_chan_id))
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
        print self._players.values()
        return Response(text=u"The players are:\n{}".format(players), chan_id=msg.chan_id)

    def _begin_game(self, match=None, msg=None):
        self._state=self.ACTIVE_GAME
        return self._help(msg=msg)

    def _check_hand(self, match=None, msg=None):
        if msg.user_id not in self._players.keys():
            print "PLAYERS ONLY"
            return
        player_name = match.group('player_name').lstrip('@ ')
        if not player_name:
            player_name = msg.user_name.lower()
        elif player_name not in self._player_ids:
            return Response(text="I don't recognize the player, '{}'.".format(player_name), chan_id=msg.chan_id)
        player_id = self._player_ids[player_name]
        hand = self._hands[player_id]
        text = "{p} has the hand: {h}".format(p=player_name,h=hand)
        return Response(text=text, chan_id=msg.chan_id)

    def _return_card(self, match=None, msg=None):
        if msg.user_id not in self._players.keys():
            print "PLAYERS ONLY"
            return
        card_name = match.group('card_name').strip().lower()
        key_fn = (lambda card:(str(card).lower().strip() == card_name))
        pulled_card = self._hands[msg.user_id].pull(key_fn=key_fn)
        if not pulled_card:
            return Response(text="Ain't no card like that.", chan_id=msg.chan_id)
        self._deck.insert(pulled_card,top=False)
        return Response(text="Returned {card} to the bottom of the deck.".format(card=pulled_card), chan_id=msg.chan_id)

    def _shuffle_deck(self, match=None, msg=None):
        if msg.user_id not in self._players.keys():
            print "PLAYERS ONLY"
            return
        self._deck.shuffle()
        return Response(
            text="`{player} shuffling deck`".format(player=msg.user_name.lower()),
            chan_id=self._game_chan_id)

    def _check_deck(self, match=None, msg=None):
        if msg.user_id not in self._players.keys():
            print "PLAYERS ONLY"
            return
        peek_depth = match.group('peek_depth').strip('')
        try:
            peek_depth = int(peek_depth)
        except:
            peek_depth = 0
        if peek_depth:
            peek = self._deck.peek(peek_depth)
            return Response(text="Peekin' dis deck: {}".format(peek), chan_id=msg.chan_id)
        else:
            return Response(text="Deck has {} cards.".format(len(self._deck)), chan_id=msg.chan_id)

    def _deal_cards(self, match=None, msg=None):
        if msg.user_id not in self._players.keys():
            print "PLAYERS ONLY"
            return
        player_name = match.group('player_name').lstrip('@')
        if player_name not in self._player_ids:
            return Response(text="I don't recognize the player, '{}'.".format(player_name), chan_id=msg.chan_id)
        num_cards = int(match.group('num_cards'))
        player_id = self._player_ids[player_name]
        drawn_cards = self._deck.draw(num_cards)
        self._hands[player_id].add(drawn_cards)
        text="Player {p} drew cards: {c}".format(
            p=player_name, c=drawn_cards)
        return Response(text=text, chan_id=msg.chan_id)

card_game = CardGame(deck=color_deck)

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