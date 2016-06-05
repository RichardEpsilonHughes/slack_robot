import random

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
        return '({name})'.format(name=self.name)
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

        assert isinstance(name,(basestring)), "Decks must be named."
        self._name = name

    @property
    def name(self):
        "Return immutable name property."
        return self._name

    def __len__(self):
        "How many cards in dis"
        return len(self._cards)
    def __str__(self):
        "str"
        return repr(self)
    def __repr__(self):
        return '{name}:[{cards}]'.format(
            name=self.name,
            cards=','.join(str(card) for card in self._cards))

    def peek(self, num_cards='all'):
        "Return an immutable tuple of the first {num_cards} cards from the deck."
        assert num_cards == 'all' or (isinstance(num_cards, int) and num_cards > 0)
        if num_cards == 'all':
            return tuple(self._cards)
        else:
            return tuple(self._cards[:num_cards])

    def shuffle(self):
        "Randomize the deck, return this object."
        random.shuffle(self._cards)
        return self

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
        deck (default top). If they're ordered, preserve that order. Return this object.
        """
        # Verify cards are cards.
        if isinstance(cards,Card):
            cards = list([cards])
        elif isinstance(cards,(tuple,set,list)):
            assert all(isinstance(card,Card) for card in cards), "all cards must be Card type"
            cards = list(cards)

        if top:
            self._cards = cards + self._cards
        else:
            self._cards += cards

        return self

class CardPile(object):
    """An unordered set of cards."""

    def __init__(self, cards=None, name=None):
        # Verify input
        if cards is None:
            self._cards = set()
        elif isinstance(cards,Card):
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
        return repr(self)
    def __repr__(self):
        return self.name+':{'+','.join(str(card) for card in self._cards)+'}'
        return "CardPile(cards={cards}{name})".format(
            cards=repr(self._cards),
            name='' if not self.name else ', name={}'.format(repr(self.name)))

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
        in the pile, and then add them to the pile. Return this object."""
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

        return self

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
    ('Red','Orange','Yellow','Green','Blue','Indigo','Violet')], name='ColorDeck')
hand_1 = CardPile(name='hand_1')
hand_2 = CardPile(name='hand_2')

deck_dict = {'color_deck':color_deck}