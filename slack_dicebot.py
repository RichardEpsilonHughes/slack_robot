#!/usr/bin/env python
# coding=utf-8

import re

import slacker
from slacksocket import SlackSocket

from game_objects import CardDeck, CardPile, deck_dict
from slack_objects import Message, Response
from slack_token import SLACK_TOKEN, BOT_USER_ID, BOT_USER_NAME

## Reg-Ex compiler help-function.

def re_comp(pattern):
    pattern = pattern.format(BOT_USER_ID=("@"+BOT_USER_NAME+":?"))
    return re.compile(pattern, flags=re.IGNORECASE)

## Game Logic

class Responder(object):
    "Any class that implements the respond-to-message interface is a responder."

    def respond_to_message(self, msg):
        "Takes a message, coughs up a response."
        return Response(text="NOT IMPLEMENTED ERROR",chan_id=msg.chan_id)

class MethodResponder(Responder):
    """
    A method responder passes messages directly to a list of its internal instance methods,
    until one returns a response object.
    """

    METHOD_LIST_BY_STATE = {}

    def __init__(self):
        assert hasattr(self, 'METHOD_LIST_BY_STATE'), "No METHOD_LIST_BY_STATE for a MethodResponder?"
        assert isinstance(self.METHOD_LIST_BY_STATE, dict)
        for method_list in self.METHOD_LIST_BY_STATE.itervalues():
            assert isinstance(method_list, (tuple, list))
            for method_name in method_list:
                assert hasattr(self, method_name), "method name {} not defined".format(method_name)
                assert type(getattr(self, method_name)) == type(self.__init__), (
                    "{meth_name} not a function, but rather a {meth_type}".format(
                        meth_name=method_name, meth_type=type(getattr(self, method_name))))

    def respond_to_message(self, msg):
        "Takes a message, coughs up a response."
        method_list = self.METHOD_LIST_BY_STATE[self.state]
        for method_name in method_list:
            response_method = getattr(self, method_name)
            response = response_method(msg)
            if isinstance(response,(tuple, set, list)):
                return response
            elif isinstance(response, Response):
                return [response]

class RegexResponder(Responder):
    """
    A regex responder matches incoming classes against a dictionary of regular expressions .
    """

    REGEX_METHOD_BY_STATE = {}

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
        text = self._preprocess_msg_text(msg)
        print u"Effective Text: {}".format(text)
        for reg_ex_obj, method_name in self.REGEX_METHOD_BY_STATE[self._state]:
            print u"Testing {}...".format(reg_ex_obj.pattern)
            match_obj = reg_ex_obj.search(text)
            if match_obj:
                print "Matched;",str(match_obj)
                response_method = getattr(self,method_name)
                break

        # If we don't find a match, no response.
        if not response_method:
            print "No match."
            return

        return response_method(match=match_obj, msg=msg)

    def _preprocess_msg_text(self, msg):
        text = msg.text
        if msg.im:
            text = u'{} '.format(("@" + BOT_USER_NAME)) + text
        return text

class MethodCardGame(MethodResponder):

    # CLASS VARIABLES

    # Game states
    ASLEEP = 0
    ACCEPTING_PLAYERS = 1
    ACTIVE_GAME = 2

    METHOD_LIST_BY_STATE = {
        ASLEEP:(
            '_wake_up',
            '_quit',
            '_grumble',
            ),
        ACCEPTING_PLAYERS:(
            '_back_to_sleep',
            # '_help',
            # '_add_player',
            # '_remove_player',
            # '_list_player',
            # '_begin_game',
            # '_grumble',
        ),
        ACTIVE_GAME:(
            '_back_to_sleep',
            # '_help',
            # '_list_players',
            # '_check_hand',
            # '_examine_card',
            # '_return_card',
            # '_discard_hand',
            # '_shuffle_deck',
            # '_check_deck',
            # '_deal_cards',
            # '_grumble'
        )}

    HELP_STR_BY_STATE = {
        ASLEEP:"",
        ACCEPTING_PLAYERS:u'\n'.join((
            u'Card game is ready to start in #{CHANNEL} after players join:',
            u' • `{BOT} sleep`: Put {BOT} back to sleep.',
            u' • `{BOT} join`: Join the game.',
            u' • `{BOT} leave`: Leave the game.',
            u' • `{BOT} list`: List the players in the game.',
            u' • `{BOT} begin game`: Start the game.',
            u' • `{BOT} help`: Play this message again.',
        )),
        ACTIVE_GAME:u'\n'.join((
            u'Card game is going down in #{CHANNEL}.:',
            u' • `<@{BOT}> sleep`: Put <@{BOT}> back to sleep.',
            u' • `<@{BOT}> list`: List the players in the game.',
            u' • `<@{BOT}> check hand [player]`: Look at someone\'s hand. Default is your hand.',
            u' • `<@{BOT}> examine card [card name]`: Display the detailed information for this card.',
            u' • `<@{BOT}> return card [card name]`: Return a card in your hand to the bottom of the deck.',
            u' • `<@{BOT}> discard hand`: Return all your cards to the bottom of the deck.',
            u' • `<@{BOT}> shuffle`: Shuffle the deck.',
            u' • `<@{BOT}> check deck [num_cards]`: Check the size of the deck, or peek at the number of .',
            u' • `<@{BOT}> deal [num_cards] to [player]`: Deal off the top of the deck.',
        ))}

    def __init__(self, deck=None):
        super(MethodCardGame, self).__init__()
        assert isinstance(deck, CardDeck)

        self.deck = deck
        self._initialize()

    def _initialize(self):
        self.player_id_to_name = dict()
        self.player_name_to_id = dict()
        self.player_id_to_hand = dict()
        self.state = self.ASLEEP
        self.game_chan_id = None
        self.game_chan_name = None

    # Static decorators start {
    def _no_ims(func):
        print "defining func_wrapper for _no_ims"
        def func_wrapper(self, msg):
            print "checking if msg is im..."
            if msg.im:
                return Response(
                    text="That function (`{}`) doesn't work in IMs. Try in a channel.".format(func.__name__),
                    im=msg.user_id)
            else:
                return func(self, msg)
        return func_wrapper

    def _verify_msg_input(*args):
        print "defining func_decorator for _verify_msg_input"
        def _function_decorator(func):
            print "defining func_wrapper for _verify_msg_input"
            def func_wrapper(self, msg):
                print "checking for {0} in {1}".format(args, msg.tokenized)
                if not all((str(word) in msg.tokenized) for word in args):
                    return
                else:
                    return func(self, msg)
            return func_wrapper
        return _function_decorator

    def _players_only(func):
        print "defining func_wrapper for _players_only"
        def func_wrapper(self, msg):
            if msg.user_id not in self.player_id_to_name:
                return
            else:
                return func(self, msg)
        return func_wrapper
    # } and end.

    # Private functions start {
    def _format_card_sequence(self, cards, sort=True):
        if sort: cards = sorted(cards)
        return u"\n".join(
            u' • `{}`'.format(card.name) for card in cards)
    @property
    def help_str_for_state(self):
        return self.HELP_STR_BY_STATE[self.state].format(
            BOT="<@{}>".format(BOT_USER_ID),
            B_U_ID=BOT_USER_ID,
            CHANNEL=self.game_chan_name)
    # } and end.

    # Responder methods start {
    @_verify_msg_input('wake')
    @_no_ims
    def _wake_up(self, msg):
        print "WAKE UP"
        self.state = self.ACCEPTING_PLAYERS
        self.game_chan_id   = msg.chan_id
        self.game_chan_name = msg.chan_name
        return Response(text=self.help_str_for_state,
                        chan_id=self.game_chan_id)

    @_verify_msg_input('quit')
    @_no_ims
    def _quit(self, msg):
        raise SystemExit

    def _grumble(self, msg=None):
        text = {
            self.ASLEEP:"Gnr... zzz.... snr...",
            self.ACCEPTING_PLAYERS:"Wot? I didn't catch that.",
            self.ACTIVE_GAME:"Wot? I didn't catch that.",
            }[self.state]
        return Response(text=text,chan_id=msg.chan_id)

    @_verify_msg_input('sleep')
    @_no_ims
    def _back_to_sleep(self, msg):
        for hand in self.player_id_to_hand.values():
            self.deck.insert(hand.pull(num_cards='all',))
        self._initialize()
        if msg.im:
            return [
                Response(text="{} put me to sleep... Night night... zzz".format(msg.user_name),
                         chan_id=self.game_chan_id),
                Response(text="Night night... zzz",
                         im=msg.user_id)
            ]
        else:
            return Response(text="Yawn... zzz", chan_id=msg.chan_id)
    # } and end.
    pass
    # End class.

class RegexCardGame(RegexResponder):

    # TODO: Create a class method that serves as a decorator for methods that only players can use.
    # TODO: Create a class method that serves as a decorator for methods that don't accept PMs.

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
            # What is in my hand? Or, uh, someone else's hand?
            (re_comp(r'{BOT_USER_ID}\s+check\s+hand\s*(?P<player_name>@?[\w.]*)'),
             '_check_hand'),
            # Examine this card.
            (re_comp(r'{BOT_USER_ID}\s+examine\s+card\s*(?P<card_name>@?[\s\w.]*)'),
             '_examine_card'),
            # Return this card to the deck.
            (re_comp(r'{BOT_USER_ID}\s+return\s+card\s*(?P<card_name>[\s\w]*)'),
             '_return_card'),
            # Return your whole hand to the deck.
            (re_comp(r'{BOT_USER_ID}\s+discard\s+hand'),
             '_discard_hand'),
            ## DECK MANAGEMENT
            # Shuffle!
            (re_comp(r'{BOT_USER_ID}\s+shuffle'),
             '_shuffle_deck'),
            # How many cards are in the deck? Or, lemme see the top X cards.
            (re_comp(r'{BOT_USER_ID}\s+check\s+deck\s*(?P<peek_depth>\d*)'),
             '_check_deck'),
            # Deal {person} {num_cards} cards.
            (re_comp('\s+deal\s+(?P<num_cards>\d+)\s+to\s(?P<player_name>@?[\w.]+)'),
             '_deal_cards'),
            # Grumble...
            (re_comp(r'{BOT_USER_ID}'),
             '_grumble'),
        )}

    def __init__(self, deck=None):
        super(RegexCardGame, self).__init__()

        # The deck or decks are the cards in play at the beginning of the game.
        assert isinstance(deck, CardDeck)

        self._deck = deck
        self._initialize()

    def _initialize(self):
        self._player_id_to_name = dict()
        self._player_name_to_id = dict()
        self._hands = dict()
        self._state = self.ASLEEP
        self._game_chan_id = None
        self._game_chan_name = None

    def _format_card_sequence(self, cards, sort=True):
        if sort:
            return u"\n".join(u' • `{}`'.format(card.name) for card in sorted(cards))
        else:
            return u"\n".join(u' • `{}`'.format(card.name) for card in cards)

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
        response = self._help(msg=msg)
        response.chan_id = self._game_chan_id
        return response

    def _back_to_sleep(self, match=None, msg=None):
        print match
        interrupt = self._no_im(msg)
        if interrupt: return interrupt

        for hand in self._hands.values():
            cards = hand.pull(num_cards='all',)
            self._deck.insert(cards)

        self._initialize()
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
                u' • `<@{B_U_ID}> help`: Play this message again.',
            ))
        elif self._state == self.ACTIVE_GAME:
            text = u'\n'.join((
                u'Card game is going down in #{CHANNEL}.:',
                u' • `<@{B_U_ID}> sleep`: Put <@{B_U_ID}> back to sleep.',
                u' • `<@{B_U_ID}> list`: List the players in the game.',
                u' • `<@{B_U_ID}> check hand [player]`: Look at someone\'s hand. Default is your hand.',
                u' • `<@{B_U_ID}> examine card [card name]`: Display the detailed information for this card.',
                u' • `<@{B_U_ID}> return card [card name]`: Return a card in your hand to the bottom of the deck.',
                u' • `<@{B_U_ID}> discard hand`: Return all your cards to the bottom of the deck.',
                u' • `<@{B_U_ID}> shuffle`: Shuffle the deck.',
                u' • `<@{B_U_ID}> check deck [num_cards]`: Check the size of the deck, or peek at the number of .',
                u' • `<@{B_U_ID}> deal [num_cards] to [player]`: Deal off the top of the deck.',
            ))
        text=text.format(B_U_ID=BOT_USER_ID, CHANNEL=self._game_chan_name)
        return Response(text=text, chan_id=msg.chan_id)

    def _add_player(self, match=None, msg=None):
        assert self._game_chan_id
        player_id = msg.user_id
        player_name = msg.user_name.lower()
        if player_id in self._player_id_to_name:
            return Response(text="You're already in this game.", chan_id=msg.chan_id)
        self._player_id_to_name[player_id] = player_name
        self._player_name_to_id[player_name] = player_id
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
        if player_id not in self._player_id_to_name:
            return Response(text="You aren't a player, tho.", chan_id=msg.chan_id)
        del self._player_id_to_name[player_id]
        del self._player_name_to_id[player_name]
        del self._hands[player_id]
        responses.append(Response(
            text="<@{}> has left the game.".format(player_name), chan_id=self._game_chan_id))
        if msg.im:
            responses.append(
                # Private message.
                Response(text=u"You've left the game.", chan_id=msg.chan_id))
        return tuple(responses)

    def _list_players(self, match=None, msg=None):
        if not self._player_id_to_name:
            return Response(text="No one is playing yet. Sad!", chan_id=msg.chan_id)
        players = u'\n'.join(
            u' • <@{}>'.format(player_name)
            for player_name in self._player_id_to_name.itervalues())
        print self._player_id_to_name.values()
        return Response(text=u"The players are:\n{}".format(players), chan_id=msg.chan_id)

    def _begin_game(self, match=None, msg=None):
        self._state=self.ACTIVE_GAME
        self._deck.shuffle()
        response = self._help(msg=msg)
        response.chan_id = self._game_chan_id
        return response

    def _check_hand(self, match=None, msg=None):
        # TODO: Test if we appropriately handle checking other player's hands.
        if msg.user_id not in self._player_id_to_name.keys():
            return
        player_name = match.group('player_name').lstrip('@ ')
        if not player_name:
            player_name = msg.user_name.lower()
        elif player_name not in self._player_name_to_id:
            return Response(text="I don't recognize the player, '{}'.".format(player_name), chan_id=msg.chan_id)
        if player_name == msg.user_name.lower():
            # This is your own hand, so IM full details.
            hand = self._hands[msg.user_id]
            if hand:
                text = u"Your hand is:\n" + self._format_card_sequence(hand.peek())
            else:
                text = u"Your hand is empty."
            return Response(text=text, im=msg.user_id)
        player_id = self._player_name_to_id[player_name]
        hand = self._hands[player_id]
        text = "{p} has {h} card{s} in their hand.".format(
            p=player_name, h=len(hand),
            s='s' if len(hand) != 1 else '')
        return Response(text=text, im=msg.user_id)

    def _examine_card(self, match=None, msg=None):
        card_name = match.group('card_name').strip()
        if not card_name:
            return Response(text="This command requires a card name to function.", im=msg.user_id)
        all_cards = list(self._deck.peek())
        for hand in self._hands.values():
            all_cards += list(hand.peek())
        matching_card = [card for card in all_cards if card.name == card_name]
        if len(matching_card) == 0:
            return Response(text="I couldn't find that card. May not be in the game; did you typo?", im=msg.user_id)
        elif len(matching_card) > 1:
            return Response(
                text="What the fuck? More than one card with the name `{}`! That shouldn't be!".format(card_name),
                im=msg.user_id)
        else:
            matching_card = matching_card[0]
        details = matching_card.details
        if not details:
            return Response(
                text="The card `{c}` has no details.".format(c=card_name),
                im=msg.user_id)
        return Response(text=(u"`"+matching_card.name+u"`\n```\n"+details+u"\n```"), im=msg.user_id)

    def _return_card(self, match=None, msg=None):
        if msg.user_id not in self._player_id_to_name.keys():
            print "PLAYERS ONLY"
            return
        card_name = match.group('card_name').lower().strip()
        key_fn = lambda card: (
            card.name.lower().strip() == card_name )
        pulled_card = [x for x in self._hands[msg.user_id].pull(key_fn=key_fn)][0]
        if not pulled_card:
            return Response(text="No card like that found.", im=msg.user_id)
        self._deck.insert(pulled_card,top=False)
        return Response(
            text="{p} returned `{card}` to the bottom of the deck.".format(
                p=msg.user_name, card=pulled_card.name),
            chan_id=self._game_chan_id)

    def _discard_hand(self, match=None, msg=None):
        if msg.user_id not in self._player_id_to_name.keys():
            print "PLAYERS ONLY"
            return
        self._deck.insert(
            self._hands[msg.user_id].pull(num_cards='all',),
            top=False)
        return Response(
            text="{p} returned their entire hand to the bottom of the deck.".format(p=msg.user_name),
            chan_id=self._game_chan_id)

    def _shuffle_deck(self, match=None, msg=None):
        if msg.user_id not in self._player_id_to_name.keys():
            print "PLAYERS ONLY"
            return
        self._deck.shuffle()
        return Response(
            text="`{player} shuffles the deck...`".format(player=msg.user_name.lower()),
            chan_id=self._game_chan_id)

    def _check_deck(self, match=None, msg=None):
        responses = []
        if msg.user_id not in self._player_id_to_name.keys():
            print "PLAYERS ONLY"
            return
        peek_depth = match.group('peek_depth').strip('')
        try:
            peek_depth = int(peek_depth)
        except:
            peek_depth = 0
        if peek_depth:
            peek = self._deck.peek(peek_depth)
            responses.append(Response(
                text=(
                    u"First {n} card{s}:\n".format(
                        n=len(peek),
                        s=(u' is' if len(peek) == 1 else u's are'))
                    + self._format_card_sequence(peek, sort=False)),
                im=msg.user_id))
            responses.append(Response(
                text=u"{u} peeks at the first {n} card{s} of the deck.".format(
                    u=msg.user_name, n=len(peek), s=('s' if len(peek) > 1 else '')),
                chan_id=self._game_chan_id))
        else:
            responses.append(Response(
                text=u"The deck has {} card/s.".format(len(self._deck)),
                im=msg.user_id))
        return responses

    def _deal_cards(self, match=None, msg=None):
        if msg.user_id not in self._player_id_to_name.keys():
            print "PLAYERS ONLY"
            return
        player_name = match.group('player_name').lstrip('@')
        if player_name in ('everyone','all','us'):
            player_ids = self._player_name_to_id
        elif player_name in ('me','myself','I'):
            player_ids = [msg.user_id]
        elif player_name in self._player_name_to_id:
            player_ids = [self._player_name_to_id[player_name]]
        else:
            return Response(text="I don't recognize the player, '{}'.".format(player_name),
                            im=msg.user_id)
        num_cards = int(match.group('num_cards'))
        text = []
        for player_id in player_ids:
            drawn_cards = self._deck.draw(num_cards)
            self._hands[player_id].add(drawn_cards)
            text.append(u"@{p} drew:\n{d}".format(
                p=self._player_id_to_name[player_id],
                d=self._format_card_sequence(drawn_cards)))
        text=u"\n".join(text)
        return Response(text=text, chan_id=self._game_chan_id)

## The Slack Listener

class SlackInterface:

    MESSAGES = {
        'hello_world': (
            "Hello, world. I'm posting this to @channel in response to {user}."),
    }

    # Get any sequence of word-characters, possibly including the @ before them to indicate a username,
    # OR,
    # Get ANYTHING that starts and ends with ``.
    TOKENIZER_RE = re.compile(r'(?:@?\w+|`[^`]*`)')

    FAKE_PM_CHANNEL_NAME = '___private_message___'
    def __init__(self, responder=None):
        assert isinstance(responder, Responder)
        self.responder = responder

        self.slack = slacker.Slacker(SLACK_TOKEN)
        self.socket = SlackSocket(SLACK_TOKEN, translate=False)
        self.user_id_to_user_name = {}
        self.chan_id_to_chan_name = {}
        self.user_id_to_im_chan_id = {}
        self._update_cache()

    def _update_cache(self):
        self.user_id_to_user_name = {
            u['id']:u['name']
            for u in self.slack.users.list().body['members']}
        self.chan_id_to_chan_name = {
            c['id']:c['name']
            for c in self.slack.channels.list().body['channels']}
        self.chan_id_to_chan_name.update({
            g['id']:g['name']
            for g in self.slack.groups.list().body['groups']})
        self.user_id_to_im_chan_id = {
            i['user']:i['id']
            for i in self.slack.im.list().body['ims']}

    def _parse_message(self, e):
        if e.type not in ('message',) or e.event['user'] == BOT_USER_ID:
            return None

        # Extract and preprocess text.
        text = e.event['text']
        for u_id, u_name in self.user_id_to_user_name.iteritems():
            text = text.replace("<@{}>".format(u_id),
                                "@{}".format(u_name))
        tokenized = self.TOKENIZER_RE.findall(text.lower())

        # Extract user and channel names from cache.
        u_name = self._get_user_name(e.event['user'])
        chan_name, is_im = self._get_channel_name_and_type(e.event['channel'])

        # if we aren't called out by name and this isn't a direct message to us,
        # we absolutely do not care
        if '@{}'.format(BOT_USER_NAME) not in tokenized and not is_im: return

        print (text, u_name, chan_name, is_im)

        return Message(
            text=text,                  tokenized=tokenized,
            user_id=e.event['user'],    user_name=u_name,
            chan_id=e.event['channel'], chan_name=chan_name,
            im=is_im)

    def _get_channel_name_and_type(self, chan_id):
        # Check channel_id and im_channel caches.
        for loop in (True, False):
            if chan_id in self.chan_id_to_chan_name:
                return self.chan_id_to_chan_name[chan_id], False
            elif chan_id in self.user_id_to_im_chan_id.values():
                return self.FAKE_PM_CHANNEL_NAME, True
            if loop: self._update_cache()
        raise ValueError, "Could not find channel_id."

    def _get_user_name(self, user_id):
        for loop in (True, False):
            if user_id in self.user_id_to_user_name:
                return self.user_id_to_user_name[user_id]
            if loop: self._update_cache()
        raise ValueError, "Could not find user id."

    def _send_response(self, response):
        assert isinstance(response, Response)

        message = response.text.replace("@channel", "<!channel|@channel>")
        if not message: return
        channel = response.chan_id
        if not channel and response.im:
            if not response.im in self.user_id_to_im_chan_id:
                self._update_cache()
            channel = self.user_id_to_im_chan_id[response.im]
        if not channel:
            raise StandardError, "No channel, explicit or actual, in response {}".format(response)
        self.slack.chat.post_message(channel, message, as_user=True)

    def listen(self):
        print "Happy birthday!"
        for e in self.socket.events():
            # Convert socket event to Message object, if possible.
            try:
                msg = self._parse_message(e)
            except StandardError, err:
                print err
                continue
            if not msg:
                continue

            responses = self.responder.respond_to_message(msg)
            if not responses: continue
            if not isinstance(responses, (set, list, tuple)):
                responses = [responses]
            for response in responses:
                try:
                    self._send_response(response)
                except StandardError, err:
                    print err
                    continue
def main():
    # TODO: Implement 'select a game to play' functionality.
    if True:
        card_game = RegexCardGame(deck=deck_dict['major_arcana'])
    else:
        card_game = MethodCardGame(deck=deck_dict['major_arcana'])
    si = SlackInterface(card_game)
    si.listen()

if __name__ == '__main__':
    main()