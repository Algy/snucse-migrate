# -*- coding: utf-8 -*-

import hashlib

from sqlalchemy.ext.hybrid import hybrid_property


class Anonymity(object):
    @hybrid_property
    def anonymous_name(self):
        try:
            return self.anonymous['name']
        except:
            return None

    @anonymous_name.setter
    def set_anonymous_name(self, value):
        if self.anonymous is None:
            self.anonymous = {}
        self.anonymous['name'] = value

    @hybrid_property
    def anonymous_password(self):
        try:
            return self.anonymous['password']
        except:
            return None

    @anonymous_password.setter
    def set_anonymous_password(self, value):
        if self.anonymous is None:
            self.anonymous = {}
        self.anonymous['password'] = self._generate_password(value)

    def is_correct_anonymous_password(self, value):
        if self.uid is None or self.anonymous is None:
            return False
        return self.anonymous['password'] == self._generate_password(value)

    @classmethod
    def _generate_password(cls, value):
        return hashlib.sha512(u'@#!82433%s2834' % value).hexdigest()
