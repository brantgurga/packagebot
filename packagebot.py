# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil -*-
import os
import thread
import time
from xml.etree import ElementTree
from argparse import ArgumentParser


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

class PackageBot(object):
    def __init__(self, verbose, tree, jobs):
        object.__init__(self)
        self.verbose = verbose
        self.tree = tree
        self.jobs = jobs
        self.metadata = []

    def run(self):
        name = None
        category = None
        metatype = 'unknown'
        metadatatuples = []
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
                metadatatuples.append((metatype, category, name, path))

        tasks = self.divvy_work(metadatatuples, self.jobs)

        self._result_lock = thread.allocate_lock()
        self._thread_count = self.jobs
        for task in tasks:
            thread.start_new_thread(self.do_work, (task,))
        while(self._thread_count):
            time.sleep(.1)
        print self.metadata[:25]

    def divvy_work(self, work, parts):
        quotient, remainder = divmod(len(work), parts)
        indices = [quotient * part + min(part, remainder)
            for part in xrange(parts + 1)]
        return [work[indices[part]:indices[part + 1]]
            for part in xrange(parts)]

    def do_work(self, task):
        result = []
        for (metatype, category, name, path) in task:
            result.append(process_xml(metatype, category, name, path,
                self.verbose))
        with self._result_lock:
            self.metadata.extend(result)
            self._thread_count -= 1


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
        default = 1,
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
    jobs = options.jobs
    if options.verbose:
        print 'Using portage tree at %(tree)s' % {'tree': tree}
        print 'Using %(jobs)u jobs' % {'jobs': jobs}
    bot = PackageBot(options.verbose, tree, jobs)
    bot.run()

if __name__ == '__main__':
    main()
