

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

class Response(object):

    def __init__(self, text=None, chan_id=None):
        self.text = text
        self.chan_id = chan_id