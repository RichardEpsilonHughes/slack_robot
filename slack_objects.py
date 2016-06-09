class Message(object):
    def __init__(self,
                 text=None,
                 user_id=None,
                 chan_id=None,
                 im=False,
                 user_name=None,
                 chan_name=None,
                 tokenized=None
                 ):
        assert isinstance(text, (basestring))
        self.text = text

        assert isinstance(user_id, (basestring))
        self.user_id = user_id

        assert isinstance(chan_id, (basestring))
        self.chan_id = chan_id

        assert isinstance(im, bool)
        self.im = im

        if user_name: assert isinstance(user_name, (basestring))
        self.user_name = user_name

        if chan_name: assert isinstance(chan_name, (basestring))
        self.chan_name = chan_name

        if tokenized: assert (isinstance(tokenized, (list, tuple))
                              and all(isinstance(x, basestring) for x in tokenized))
        self.tokenized = tokenized

    def __str__(self):
        return "{u}@{c}: {t}".format(
            u=self.user_name if self.user_name else self.user_id,
            c=self.chan_name if self.chan_name else self.chan_id,
            t=self.text)

    def __repr__(self):
        return (
            "Message("
            "text={0}, user_id={1}, user_name={2}, "
            "chan_id={3}, chan_name={4}, im={5}").format(
            self.text, self.user_id, self.user_name,
            self.chan_id, self.chan_name, self.im)


class Response(object):
    def __init__(self, text=None, chan_id=None, im=None, none=False):
        self.none = none
        self.text = text
        self.chan_id = chan_id
        self.im = im
