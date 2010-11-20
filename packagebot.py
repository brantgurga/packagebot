# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil -*-
import os
import multiprocessing
import threading
from Queue import Queue
from xml.etree import ElementTree
from argparse import ArgumentParser

class ThreadPoolThread(threading.Thread):
    def __init__(self, verbose, jobs):
        threading.Thread.__init__(self)
        self.jobs = jobs
        self.daemon = True
        self.verbose = verbose

    def run(self):
        if self.verbose:
            print 'Thread started'
        while True:
            func, args, kargs, callback = self.jobs.get()
            if self.verbose:
                print 'Thread job running'
            try:
                callback(func(*args, **kargs))
            finally:
                self.jobs.task_done()

class ThreadPool(object):
    def __init__(self, size, verbose):
        object.__init__(self)
        self.jobs = Queue(size)
        self.verbose = verbose
        for _ in range(size):
            thread = ThreadPoolThread(self.verbose, self.jobs)
            thread.start()

    def putTask(self, task, args = (), kargs = {}, callback = lambda x: x):
        self.jobs.put((task, args, kargs, callback))

    def finish(self):
        self.jobs.join()

class Metadata(object):
    def __init__(self, name, verbose):
        object.__init__(self)
        self.name = name
        self.verbose = verbose

class Category(Metadata):
    def __init__(self, name, xml, verbose):
        Metadata.__init__(self, name, verbose)
        if self.verbose:
            print 'Created category %(name)s' % {'name': self.name}

class Ebuild(Metadata):
    def __init__(self, name, category, xml, verbose):
        Metadata.__init__(self, name, verbose)
        if self.verbose:
            print 'Created ebuild %(name)s' % {'name': self.name}


def process_xml(metatype, category, name, path, verbose):
    if verbose:
        print 'Processing xml for %(name)s' % {'name': name}
    if metatype == 'category':
        result = Category(name, ElementTree.parse(path), verbose)
    elif metatype == 'ebuild':
        result = Ebuild(name, category, ElementTree.parse(path), verbose)
    return result

def handle_xml(metadata):
    if metadata.verbose:
        print 'Processed xml for %(name)s' % {'name': metadata.name}

class PackageBot(object):
    def __init__(self, verbose, tree, pool):
        object.__init__(self)
        self.verbose = verbose
        self.tree = tree
        self.pool = pool

    def run(self):
        name = None
        category = None
        metatype = 'unknown'
        for root, dirs, files in os.walk(self.tree):
            if 'metadata.xml' in files:
                if os.path.dirname(root) == self.tree:
                    category = os.path.basename(root)
                    metatype = 'category'
                else:
                    metatype = 'ebuild'
                name = os.path.basename(root)
                path = os.path.join(root, 'metadata.xml')
                if self.verbose:
                    print 'Reading %(path)s' % {'path': path}
                    print 'Type: %(type)s' % {'type': metatype}
                    print 'Category: %(category)s' % {'category': category}
                    print 'Name: %(name)s' % {'name': name}
                self.pool.putTask(process_xml,
                    (metatype, category, name, path, self.verbose),
                    {},
                    handle_xml)

def main():
    parser = ArgumentParser(description = ('Uses metadata in the portage tree'
            ' to populate a wiki.'),
        epilog = ('PackageBot gathers metadata from a portage tree and adds'
            ' information to a wiki.'))
    parser.add_argument('-V', '--version',
        action = 'version',
        version = '0',
        help = 'print the version of Packagebot and exit')
    parser.add_argument('-v', '--verbose',
        action = 'store_true',
        dest = 'verbose',
        default = False,
        help = 'print details on what Packagebot is doing')
    parser.add_argument('-j', '--jobs',
        action = 'store',
        dest = 'jobs',
        type = int,
        default = multiprocessing.cpu_count(),
        help = 'run jobs in parallel',
        nargs = '?')
    parser.add_argument('tree',
        action = 'store',
        default = '/usr/portage',
        help = 'specify the location of the portage tree',
        nargs = '?')
    options = parser.parse_args()
    if options.verbose:
        print 'Starting in verbose mode'
    tree = os.path.normpath(options.tree)
    pool = ThreadPool(options.jobs, options.verbose)
    if options.verbose:
        print 'Using portage tree at %(tree)s' % {'tree': tree}
        print 'Using %(jobs)u jobs' % {'jobs': options.jobs}
    bot = PackageBot(options.verbose, tree, pool)
    bot.run()
    pool.finish()

if __name__ == '__main__':
    main()
