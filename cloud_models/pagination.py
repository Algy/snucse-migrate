# -*- coding: utf-8 -*-


class Pagination(object):
    '''http://flask.pocoo.org/snippets/44/'''
    def __init__(self, page, per_page, total_count):
        self.page = page
        self.per_page = per_page
        self.total_count = total_count
        self.max_page = self.total_count / self.per_page

    @property
    def has_prev(self):
        return self.page > 0

    @property
    def has_next(self):
        return self.page < self.max_pagepage

    def iter_pages(self, left_edge=2, left_current=7,
                   right_current=8, right_edge=2):
        last = -1
        for num in xrange(self.max_page + 1):
            if num < left_edge or \
               (num > self.page - left_current - 1 and
                num <= self.page + right_current) or \
               num > self.max_page - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

    def articles_on_page(self, all_articles):
        return all_articles[self.page * self.per_page:
                            (self.page + 1) * self.per_page]


class ArticleContainer(object):
    def pagination(self, page):
        try:
            self.article_count
        except AttributeError:
            return None

        try:
            pagination = self._pagination
            pagination.page = page
            return pagination
        except AttributeError:
            self._pagination = Pagination(page, app.config['ARTICLE_PER_PAGE'],
                                          self.article_count)
        return self._pagination
