# License: BSD Style, 2 clauses. see acrylamid.py
# -*- encoding: utf-8 -*-

from acrylamid.filters import Filter
from acrylamid.filters import log

import re, os, codecs
from HTMLParser import HTMLParser
from cgi import escape
from os.path import join, dirname, basename

class HyphenPatternNotFound(Exception): pass



class Hyphenator:
    """ Hyphenation, using Frank Liang's algorithm.
    
    This module provides a single function to hyphenate words.  hyphenate_word takes 
    a string (the word), and returns a list of parts that can be separated by hyphens.

    >>> hyphenate_word("hyphenation")
    ['hy', 'phen', 'ation']
    >>> hyphenate_word("supercalifragilisticexpialidocious")
    ['su', 'per', 'cal', 'ifrag', 'ilis', 'tic', 'ex', 'pi', 'ali', 'do', 'cious']
    >>> hyphenate_word("project")
    ['project']

    Ned Batchelder, July 2007.
    This Python code is in the public domain."""

    __version__ = '1.0.20070709'

    def __init__(self, chars, patterns, exceptions=''):
        self.chars = unicode('[.'+chars+']')
        self.tree = {}
        for pattern in patterns.split():
            self._insert_pattern(pattern)
    
        self.exceptions = {}
        for ex in exceptions.split():
            # Convert the hyphenated pattern into a point array for use later.
            self.exceptions[ex.replace('-', '')] = [0] + [ int(h == '-') for h in re.split(r"[a-z]", ex) ]
                
    def _insert_pattern(self, pattern):
        # Convert the a pattern like 'a1bc3d4' into a string of chars 'abcd'
        # and a list of points [ 1, 0, 3, 4 ].
        chars = re.sub('[0-9]', '', pattern)
        points = [ int(d or 0) for d in re.split(self.chars, pattern, flags=re.U) ]

        # Insert the pattern into the tree.  Each character finds a dict
        # another level down in the tree, and leaf nodes have the list of
        # points.
        t = self.tree
        for c in chars:
            if c not in t:
                t[c] = {}
            t = t[c]
        t[None] = points
        
    def hyphenate_word(self, word):
        """ Given a word, returns a list of pieces, broken at the possible
            hyphenation points.
        """
        # Short words aren't hyphenated.
        if len(word) <= 4:
            return [word]
        # If the word is an exception, get the stored points.
        if word.lower() in self.exceptions:
            points = self.exceptions[word.lower()]
        else:
            work = '.' + word.lower() + '.'
            points = [0] * (len(work)+1)
            for i in range(len(work)):
                t = self.tree
                for c in work[i:]:
                    if c in t:
                        t = t[c]
                        if None in t:
                            p = t[None]
                            for j in range(len(p)):
                                points[i+j] = max(points[i+j], p[j])
                    else:
                        break
            # No hyphens in the first two chars or the last two.
            points[1] = points[2] = points[-2] = points[-3] = 0

        # Examine the points to build the pieces list.
        pieces = ['']
        for c, p in zip(word, points[2:]):
            pieces[-1] += c
            if p % 2:
                pieces.append('')
        return pieces
    

class Separator(HTMLParser):
    """helper class to apply Hyphenator to each word except in pre, code,
    math and em tags."""

    def __init__(self, html, hyphenationfunc):
        HTMLParser.__init__(self)
        self.hyphenate = hyphenationfunc
        self.result = []
        self.stack = []

        self.feed(html)

    def handle_starttag(self, tag, attrs):
        """Apply and stack each read tag until we reach maxword."""

        def tagify(tag, attrs):
            """convert parsed tag back into a html tag"""
            if attrs:
                return '<%s %s>' % (tag, ' '.join(['%s="%s"' % (k, escape(v))
                                        for k,v in attrs]))
            else:
                return '<%s>' % tag

        self.stack.append(tag)
        self.result.append(tagify(tag, attrs))

    def handle_data(self, data):
        """Hyphenate words longer than 10 characters."""

        if filter(lambda i: i in self.stack, ['pre', 'code', 'math', 'em']):
            pass
        else:
            split = [word for word in re.split(r"[.:,\s!?+=\(\)/-]+", data) if len(word) > 10]
            for word in split:
                hyphenated = '&shy;'.join(self.hyphenate(word))
                data = data.replace(word, hyphenated)

        self.result.append(data)

    def handle_endtag(self, tag):
        """Until we reach not the maxwords limit, we can safely pop every ending tag,
           added by handle_starttag. Afterwards, we apply missing endings tags if missing."""
        try: self.stack.pop()
        except Exception: pass
        self.result.append('</%s>' % tag)

    def handle_entityref(self, name):
        self.result.append('&'  + name + ';')
        
    def handle_charref(self, char):
        self.result.append('&#' + char + ';')


def build(lang):
    """build the Hyphenator from given language.  If you want add more, see
    http://tug.org/svn/texhyphen/trunk/hyph-utf8/tex/generic/hyph-utf8/patterns/txt/ ."""
    
    def gethyph(lang, directory='hyph/', prefix='hyph-'):
        
        for la in [prefix+lang, prefix+lang[:2]]:
            for p in os.listdir(directory):
                f = os.path.basename(p)
                if f.startswith(la):
                    return join(directory, p)
                
        raise HyphenPatternNotFound("no hyph-definition found for '%s'" % lang)
        
    try:
        dir = os.path.join(dirname(__file__), 'hyph/')
        fpath = gethyph(lang, dir).rsplit('.', 2)[0]
        try:
            with codecs.open(fpath + '.chr.txt', encoding='utf-8') as f:
                chars = ''.join([line[0] for line in f.readlines()])
            with codecs.open(fpath + '.pat.txt', encoding='utf-8') as f:
                patterns = f.read()
        except IOError:
            raise HyphenPatternNotFound('hyph/%s.chr.txt or hyph/%s.pat.txt missing' % (lang, lang))
        
        hyphenator = Hyphenator(chars, patterns, exceptions='')
        del patterns; del chars
        log.debug("built Hyphenator from <%s>" % basename(fpath))
        return hyphenator.hyphenate_word
        
    except HyphenPatternNotFound, e:
        log.warn(e.message)
        return lambda x: [x]


class Hyphenate(Filter):

    __name__ = 'Hyphenate'
    __match__ = ['hyphenate', 'hyph']
#    __priority__ = 5.0

    def __init__(self, conf, env):
        
        # build default hyphenate_word using conf's lang (if available)
        self.default = build(conf['lang'][0].replace('_', '-'))
        
    def __call__(self, content, req):
        
        if req.lang:
            hyphenate_word = build(req.lang[0].replace('_', '-'))
        else:
            hyphenate_word = self.default

        return ''.join(Separator(content, hyphenate_word).result)