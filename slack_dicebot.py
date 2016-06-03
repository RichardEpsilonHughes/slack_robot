#!/usr/bin/env python

import logging
import re
import random

import slacker
from slacksocket import SlackSocket
from collections import OrderedDict

POST_CHANNEL = '#test-channel'
SLACK_TOKEN = "xoxb-41370365543-eyugiTyl6kqbjO91WVEo5d0S"
BOT_USER_ID = u"U17AWARFZ"
slack = slacker.Slacker(SLACK_TOKEN)

## Slack object encapsulators.

class Message(object):

    def __init__(self,
        text=None,
        user_id=None,
        user_name=None,
        chan_id=None,
        chan_name=None,
        im=False):
        assert isinstance(text,(basestring))
        assert isinstance(user_id,(basestring))
        assert isinstance(user_name,(basestring))
        assert isinstance(chan_id,(basestring))
        assert isinstance(chan_name,(basestring))
        assert isinstance(im,bool)
        self._text = text
        self._user_id = user_id
        self._user_name = user_name
        self._chan_id = chan_id
        self._chan_name = chan_name
        self._im = im

    @property
    def text(self):
        return self._text
    @property
    def user_id(self):
        return self._user_id
    @property
    def user_name(self):
        return self._user_name
    @property
    def chan_id(self):
        return self._chan_id
    @property
    def chan_name(self):
        return self._chan_name
    @property
    def im(self):
        return self._im

    def __str__(self):
        return "{u}@{c}: {t}".format(
            u=self.user_name,c=self.chan_name,t=self.text)
    def __repr__(self):
        return (
            "Message("
            "text={0}, user_id={1}, user_name={2}, "
            "chan_id={3}, chan_name={4}, im={5}").format(
            self.text, self.user_id,self.user_name,
            self.chan_id, self.chan_name, self.im)

## Cards and card collections

class Card(object):

    def __init__(self, suit=None, rank=None, name=None):
        "Initializer. If you want the string to print "
        assert suit is None or isinstance(suit, (basestring)), "suit must be string"
        assert rank is None or isinstance(rank, (int)), "rank must be int"
        assert name is None or isinstance(name, (basestring)), "name must be string"
        assert suit or rank or name, "At least one non-none input, please"
        self._suit = suit
        self._rank = rank
        self._name = name

    @property
    def suit(self):
        "Return the read-only suit property."
        return self._suit
    @property
    def rank(self):
        "Return the read-only rank property."
        return self._rank
    @property
    def name(self):
        "Return the read-only name property."
        return self._name

    # Magic String Methods.
    def __str__(self):
        if self.name:
            return self.name
        elif self.rank and self.suit:
            return '{r} of {s}'.format(r=self.rank, s=self.suit)
        elif self.suit:
            return self.suit
        else:
            return str(self.rank)
    def __repr__(self):
        params = []
        if self.suit:
            params.append('suit={}'.format(repr(self.suit)))
        if self.rank:
            params.append('rank={}'.format(repr(self.rank)))
        if self.name:
            params.append('name={}'.format(repr(self.name)))
        return "Card({})".format(', '.join(params))

    # Magic Comparator Method
    def __cmp__(self, other):
        assert isinstance(other, Card)
        if self.name < other.name:
            return -1
        elif self.name == other.name:
            return 0
        else: # self.name > other.name:
            return 1

class CardDeck(object):
    """An ordered list of cards, with some utility functions to help manage moving them."""
    def __init__(self, cards, name=None):
        if isinstance(cards,Card):
            self._cards = [cards]
        elif isinstance(cards,(tuple,set,list)):
            assert all(isinstance(card,Card) for card in cards), "all cards must be Card type"
            self._cards = list(cards)
        else:
            ValueError, "cards must be one or more of Card type"

        if name:
            assert isinstance(name,(basestring))
        self._name = name

    @property
    def name(self):
        "Return immutable name property."
        return self._name

    def __len__(self):
        "How many cards in dis"
        return len(self._cards)
    def __str__(self):
        return "{0} w/ {1} cards".format(
            self.name if self.name else "CardDeck",
            len(self))
    def __repr__(self):
        return "CardDeck({cards}{name})".format(
            cards=repr(self.peek()),
            name='' if not self._name else ', name={}'.format(repr(self.name)))

    def peek(self, num_cards='all'):
        "Return an immutable tuple of the first {num_cards} cards from the deck."
        assert num_cards == 'all' or (isinstance(num_cards, int) and num_cards > 0)
        if num_cards == 'all':
            return tuple(self._cards)
        else:
            return tuple(self._cards[:num_cards])

    def shuffle(self):
        "Randomize the deck."
        random.shuffle(self._cards)

    def draw(self, num_cards=1):
        "Remove the first {num_cards} cards from the deck and return them in a list."
        assert isinstance(num_cards,int) and num_cards > 0
        if len(self._cards) > num_cards:
            num_cards = min(len(self._cards), num_cards)
        drawn_cards = self._cards[:num_cards]
        self._cards = self._cards[num_cards:]
        return drawn_cards

    def insert(self, cards, top=True):
        """
        Given a collection of cards, put them in to the top or the bottom of the
        deck (default top). If they're ordered, preserve that order.
        """
        # Verify cards are cards.
        if isinstance(cards,Card):
            cards = list([cards])
        elif isinstance(cards,(tuple,set,list)):
            assert all(isinstance(card,Card) for card in cards), "all cards must be Card type"
            cards = list(cards)

        if top:
            self._cards = cards + self_cards
        else:
            self._cards += cards

class CardPile(object):
    """An unordered set of cards."""

    def __init__(self, cards, name=None):
        # Verify input
        if isinstance(cards,Card):
            self._cards = set([cards])
        elif isinstance(cards,(tuple,set,list)):
            assert all(isinstance(card,Card) for card in cards), "all cards must be Card type"
            self._cards = set(cards)
        else:
            ValueError, "cards must be one or more of Card type"

        if name:
            assert isinstance(name,(basestring))
        self._name = name

    def __len__(self):
        return len(self._cards)
    def __str__(self):
        raise NotImplementedError
    def __repr__(self):
        return "CardPile({cards}{name})".format(
            cards=repr(self._cards),
            name='' if not self.name else ', {}'.format(repr(self.name)))
        raise NotImplementedError

    @property
    def name(self):
        "Return immutable name property."
        return self._name

    def peek(self):
        "Return an immutable tuple of all the cards."
        return frozenset(self._cards)

    def add(self, new_cards):
        """
        Given a card or collection of cards, assert none of the input cards are
        in the pile, and then add them to the pile."""
        # Verify input
        if isinstance(new_cards,Card):
            new_cards = set([new_cards])
        elif isinstance(new_cards,(tuple,set,list)):
            assert all(isinstance(card,Card) for card in new_cards), "all cards must be Card type"
            new_cards = set(new_cards)
        else:
            ValueError, "cards must be one or more of Card type"

        # No dupes, right?
        assert len(self._cards & new_cards) == 0

        # Okay, get em'.
        self._cards |= new_cards

    def pull(self, num_cards=1, key_fn=None):
        """
        Given a number of cards to pull, and a function that accepts a Card and
        returns either True or False, pull cards from the pile that return True
        for that function until you have pulled num_cards or no cards return
        True for that function.
        Return those cards as a set."""
        assert isinstance(num_cards, int) and num_cards >= 0
        assert isinstance(key_fn, type(lambda x:x))

        # Pull cards.
        pulled_cards = set()
        for card in self._cards:
            if num_cards <= 0:
                break
            if key_fn(card):
                pulled_cards.add(card)
                num_cards -= 1
        self._cards -= pulled_cards
        return pulled_cards

color_deck = CardDeck([Card(name=name) for name in
    ('Red','Orange','Yellow','Green','Blue','Indigo','Violet')])

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

class Game(RegexResponder):

    def __init__(self):
        if type(self)==Game:
            raise NotImplementedError, "Don't instantiate a plain Game object!"
        self._players = set()

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
            ) }r

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