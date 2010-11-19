# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil -*-
import os
from optparse import OptionParser
import xml.sax

class MetaDataHandler(xml.sax.ContentHandler):
    def __init__(self, verbose):
        object.__init__(self)
        self.verbose = verbose

    def startDocument(self):
        self.type = None

    def startElement(self, name, attrs):
        if name == 'catmetadata':
            self.type = 'category'
        elif name == 'pkgmetadata':
            self.type = 'package'

    def endElement(self, name):
        if name == 'catmetadata':
            self.categories += {}

class MetaDataErrorHandler(xml.sax.ErrorHandler):
    def __init__(self, verbose):
        object.__init__(self)
        self.verbose = verbose

    def error(self, exception):
        messageargs = {'message': exception.getMessage(),
            'line': exception.getLineNumber(),
            'column': exception.getColumnNumber()}
        if self.verbose:
            message = '%(line)u, %(column)u: %(message)s' % messageargs
        else:
            message = '%(message)s' % messageargs
        print message

    def fatalError(self, exception):
        messageargs = {'message': exception.getMessage(),
            'line': exception.getLineNumber(),
            'column': exception.getColumnNumber()}
        if self.verbose:
            message = '%(line)u, %(column)u: %(message)s' % messageargs
        else:
            message = '%(message)s' % messageargs
        print message

    def warning(self, exception):
        messageargs = {'message': exception.getMessage(),
            'line': exception.getLineNumber(),
            'column': exception.getColumnNumber()}
        if self.verbose:
            message = '%(line)u, %(column)u: %(message)s' % messageargs
        else:
            message = '' % messageargs
        print message

class PackageBot(object):
    def __init__(self, verbose, tree):
        object.__init__(self)
        self.verbose = True
        self.tree = tree

    def run(self):
        for root, dirs, files in os.walk(self.tree):
            if 'metadata.xml' in files:
                path = os.path.join(root, 'metadata.xml')
                if self.verbose:
                    print 'Reading %(path)s' % {'path': path}
                metadata_handler = MetaDataHandler(self.verbose)
                metadata_error_handler = MetaDataErrorHandler(self.verbose)
                xml.sax.parse(path, metadata_handler, metadata_error_handler)

def main():
    parser = OptionParser(version = '0',
        description = 'Uses metadata in the portage tree to populate a wiki.',
        epilog = ('PackageBot gathers metadata from a portage tree and adds'
            ' information to a wiki.'))
    parser.add_option('-v', '--verbose',
        action = 'store_true',
        dest = 'verbose',
        default = False,
        help = 'Prints details on what Packagebot is doing')
    (options, args) = parser.parse_args()
    if options.verbose:
        print 'Starting in verbose mode'
    if len(args) > 0:
        tree = args[0]
    else:
        tree = '/usr/portage'
    tree = os.path.normpath(tree)
    if options.verbose:
        print 'Using portage tree at %(tree)s' % {'tree': tree}
    bot = PackageBot(options.verbose, tree)
    bot.run()

if __name__ == '__main__':
    main()
