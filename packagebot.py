# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil -*-
import os
import multiprocessing
from xml.etree import ElementTree
from argparse import ArgumentParser

def process_xml(metatype, category, name, path):
    return (name, category, metatype, ElementTree.parse(path))

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
        results = list()
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
                results.append(self.pool.apply_async(process_xml,
                    args = (metatype, category, name, path)))
        for result in results:
            result = result.get(None)
            print result[0]
                

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
    pool = multiprocessing.Pool(processes = options.jobs)
    if options.verbose:
        print 'Using portage tree at %(tree)s' % {'tree': tree}
        print 'Using %(jobs)u jobs' % {'jobs': options.jobs}
    bot = PackageBot(options.verbose, tree, pool)
    bot.run()
    pool.close()
    pool.join()

if __name__ == '__main__':
    main()
