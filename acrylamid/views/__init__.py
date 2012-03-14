#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2011 posativ <info@posativ.org>. All rights reserved.
# License: BSD Style, 2 clauses. see acrylamid.py

import sys
import os
import glob
import traceback

from acrylamid import log

# module-wide callbacks variable contaning views, reset this on initialize!
__views_list = []


def get_views():

    global __views_list
    return __views_list


def index_views(module, urlmap, conf, env):
    """Stupid an naïve try getting attribute specified in `views` in
    various flavours and fail silent.

    We remove already mapped urls and pop views'name from kwargs to
    avoid the practical worst-case O(m*n), m=num rules, n=num modules.

    Views are stored into module-global variable `callbacks` and can be
    retrieved using :func:`views.get_views`.
    """

    global __views_list

    for view, rule in urlmap[:]:
        try:
            mem = getattr(module, view)
        except AttributeError:
            try:
                mem = getattr(module, view.capitalize())
            except AttributeError:
                try:
                    mem = getattr(module, view.lower())
                except AttributeError:
                    try:
                        mem = getattr(module, view.upper())
                    except AttributeError:
                        mem = None
        if mem:
            kwargs = conf['views'][rule].copy()
            kwargs['path'] = rule
            try:
                kwargs['condition'] = conf['views'][rule]['if']
            except KeyError:
                pass
            kwargs.pop('if', None)
            __views_list.append(mem(conf, env, **kwargs))
            urlmap.remove((view, rule))


def initialize(ext_dir, conf, env):

    global __views_list
    __views_list = []

    # view -> path
    urlmap = [(conf['views'][k]['view'], k) for k in conf['views']]

    ext_dir.extend([os.path.dirname(__file__)])
    ext_list = []

    # handle ext_dir
    for mem in ext_dir[:]:
        if os.path.isdir(mem):
            sys.path.insert(0, mem)
        else:
            ext_dir.remove(mem)
            log.error("View directory %r does not exist. -- skipping" % mem)

    for mem in ext_dir:
        files = glob.glob(os.path.join(mem, "*.py"))
        files += [p.rstrip('/__init__.py') for p in \
                    glob.glob(os.path.join(mem, '*/__init__.py'))]
        ext_list += files

    for mem in [os.path.basename(x).replace('.py', '') for x in ext_list]:
        if mem.startswith('_'):
            continue
        try:
            _module = __import__(mem)
            #sys.modules[__package__].__dict__[mem] = _module
            index_views(_module, urlmap, conf, env)
        except (ImportError, Exception), e:
            log.error('%r ImportError %r', mem, e)
            traceback.print_exc(file=sys.stdout)


class View(object):

    __view__ = True

    filters = None
    condition = lambda v, e: True
    view = 'View'
    path = '/'

    def __init__(self, *args, **kwargs):
        for k in ('condition', 'view', 'path', 'filters'):
            try:
                setattr(self, k, kwargs[k])
            except KeyError:
                pass
        for k in ('condition', 'view', 'path', 'filters'):
            kwargs.pop(k, None)
