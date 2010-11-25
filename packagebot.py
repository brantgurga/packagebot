# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil -*-
"""Run packagebot against a particular MediaWiki site.

usage: packagebot.py [-h] [-V] [-v] [-j [JOBS]] [--useragent [USERAGENT]]
                     user password [tree] [endpoint]

Uses metadata in the portage tree to populate a wiki.

positional arguments:
  user                  user for logging into MediaWiki
  password              password for logging into MediaWiki
  tree                  specify the location of the portage tree
  endpoint              endpoint for MediaWiki API

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         print the version of Packagebot and exit
  -v, --verbose         print details on what Packagebot is doing
  -j [JOBS], --jobs [JOBS]
                        run jobs in parallel
  --useragent [USERAGENT]
                        Specify the useragent for Packagebot to use

PackageBot gathers metadata from a portage tree and adds information to a
wiki.

"""
import os
import thread
import time
import StringIO
import urllib
import urllib2
import cookielib
import hashlib
import json
from xml.etree import ElementTree
from argparse import ArgumentParser


class Metadata(object):
    """Base class for package and ebuild metadata."""
    def __init__(self, name, xml, verbose):
        """Creates metadata with a name from an ElementTree."""
        object.__init__(self)
        self.name = name
        self.xml = xml
        self.verbose = verbose

    def update(self, wiki):
        """Forms an interface for metadata"""
        print 'Unimplemented update for %(name)s' % {'name': self.name}

    def __str__(self):
        """Gives a brief string representation of a metadata object."""
        return 'Metadata: %(name)s' % {'name': self.name}

    def __repr__(self):
        """Creates a string usable for recreating the metadata."""
        xmloutput = StringIO.StringIO()
        self.xml.write(xmloutput)
        output = ('Metadata(%(name)s, '
                'ElementTree.parse(StringIO.StringIO(%(xml)s)), '
                '%(verbose)s)' %
            {'name': repr(self.name),
                'xml': repr(xmloutput.getvalue()),
                'verbose': repr(self.verbose)})
        xmloutput.close()
        return output


class Category(Metadata):
    """This is a Portage tree category."""
    template = ('{{PortageCategory|'
                    'description=<nowiki>%(description)s</nowiki>}}')
    def __init__(self, name, xml, verbose):
        """Creates a Portage tree category."""
        Metadata.__init__(self, name, xml, verbose)
        if self.verbose:
            print 'Created category %(name)s' % {'name': self.name}

    def update(self, wiki):
        """Updates the wiki content for a category."""
        result = wiki.query('Category:%(name)s' % {'name': self.name})
        token = result['query']['pages'].values()[0]['edittoken']
        timestamp = result['query']['pages'].values()[0]['starttimestamp']
        if 'missing' in result['query']['pages'].values()[0]:
            if self.verbose:
                print 'Creating new page for %(name)s' % {'name': self.name}
            description = ''
            for desc in self.xml.getiterator('longdescription'):
                if 'lang' in desc.attrib and desc.attrib['lang'] == 'en':
                    description = desc.text
            content = (self.template %
                {'description': description})
            wiki.create('Category:%(name)s' % {'name': self.name},
                content,
                token,
                'Packagebot created the category template content',
                timestamp)
        else:
            print 'Would update page for %(name)s' % {'name': self.name}

    def __str__(self):
        """Creates a string describing the category."""
        return 'Category: %(name)s' % {'name': self.name}

    def __repr__(self):
        """Creates a string usable to reconstruct the category."""
        xmloutput = StringIO.StringIO()
        self.xml.write(xmloutput)
        output = ('Category(%(name)s, '
                'ElementTree.parse(StringIO.StringIO(%(xml)s)), '
                '%(verbose)s)' %
            {'name': repr(self.name),
                'xml': repr(xmloutput.getvalue()),
                'verbose': repr(self.verbose)})
        xmloutput.close()
        return output


class Ebuild(Metadata):
    """This is a Portage tree ebuild."""
    def __init__(self, name, category, xml, verbose):
        """Creates the ebuild metadata from an ElementTree."""
        Metadata.__init__(self, name, xml, verbose)
        self.category = category
        if self.verbose:
            print 'Created ebuild %(name)s' % {'name': self.name}

    def __str__(self):
        """Creates a string description of the ebuild."""
        return ('Ebuild: %(category)s/%(name)s' %
            {'category': self.category, 'name': self.name})

    def __repr__(self):
        """Creates a string to recreate the ebuild metadata."""
        xmloutput = StringIO.StringIO()
        self.xml.write(xmloutput)
        output = ('Ebuild(%(name)s, %(category)s, '
                'ElementTree.parse(StringIO.StringIO(%(xml)s)), '
                '%(verbose)s)' %
            {'name': repr(self.name),
                'category': repr(self.category),
                'xml': repr(xmloutput.getvalue()),
                'verbose': repr(self.verbose)})
        xmloutput.close()
        return output


class PackageBot(object):
    """Workhorse of PackageBot that deals with collecting and sending data."""
    def __init__(self, verbose, tree, jobs, mediawiki):
        """Creates a bot with a particular configuration."""
        object.__init__(self)
        self.verbose = verbose
        self.tree = tree
        self.jobs = jobs
        self.mediawiki = mediawiki
        self.metadata = []

    def run(self):
        """Runs the bot."""
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
        for m in self.metadata:
            m.update(self.mediawiki)

    def divvy_work(self, work, parts):
        """Splits up work for different threads."""
        quotient, remainder = divmod(len(work), parts)
        indices = [quotient * part + min(part, remainder)
            for part in xrange(parts + 1)]
        return [work[indices[part]:indices[part + 1]]
            for part in xrange(parts)]

    def do_work(self, task):
        """Does the work for each thread."""
        result = []
        for (metatype, category, name, path) in task:
            if self.verbose:
                print 'Processing xml for %(name)s' % {'name': name}
            if metatype == 'category':
                result.append(
                    Category(name,
                        ElementTree.parse(path),
                        self.verbose))
            elif metatype == 'ebuild':
                result.append(
                    Ebuild(name,
                        category,
                        ElementTree.parse(path),
                        self.verbose))
            else:
                assert False, 'Unhandled metadata type'
                thread.interrupt_main()
        with self._result_lock:
            self.metadata.extend(result)
            self._thread_count -= 1


class LoginException(Exception):
    """Exceptional issues logging into MediaWiki."""
    def __init__(self, code):
        """Creates a login exception for a particular login issue code."""
        Exception.__init__(self)
        self.code = code

    def __str__(self):
        """Creates a string to describe the login exception."""
        print 'Login Issue: %(code)s' % {'code': self.code}

    def __repr__(self):
        """Creates a string to be used to recreate the LoginException."""
        print 'LoginException(%(code)s)' % {'code': repr(self.code)}


class MediaWiki(object):
    """This is the MediaWiki context tracker."""
    def __init__(self, endpoint, useragent, verbose):
        """Creates the MediaWiki context for a given configuration."""
        object.__init__(self)
        self.apiendpoint = urlparse.urljoin(endpoint, 'api.php')
        self.indexpoint = urlparse.urljoin(endpoint, 'index.php')
        self.verbose = verbose
        self.useragent = useragent
        self.token = ''
        self.opener = urllib2.OpenerDirector()
        self.cookies = cookielib.CookieJar()
        cookie_handler = urllib2.HTTPCookieProcessor(self.cookies)
        self.opener.add_handler(cookie_handler)
        self.opener.add_handler(urllib2.HTTPHandler())
        self.opener.add_handler(urllib2.HTTPSHandler())
        if verbose:
            print 'Using endpoint: %(endpoint)s' % {'endpoint': endpoint}

    def call(self, action, **params):
        """Makes the actual Web service call."""
        params.update({'format': 'json', 'action': action})
        apiparams = urllib.urlencode(params)
        if self.verbose:
            print 'Using parameters: %(apiparams)s' % {'apiparams': apiparams}
            print 'Using cookies:'
            for cookie in self.cookies:
                print('%(name)s=%(value)s' %
                    {'name': cookie.name, 'value': cookie.value})
        request = urllib2.Request(self.apiendpoint, apiparams,
            {'User-Agent': self.useragent})
        result = self.opener.open(request)
        if self.verbose:
            print 'Request sent to %(dest)s' % {'dest': result.geturl()}
            print 'Result metadata: %(metadata)s' % {'metadata': result.info()}
        content = result.read()
        if self.verbose:
            print 'Result: %(result)s' % {'result': content}
        decoded = json.loads(content)
        return decoded

    def create(self, name, content, token, summary, timestamp):
        """Creates a page of content on the wiki."""
        md5 = hashlib.md5(content).hexdigest()
        self.call('edit',
            title=name,
            text=content,
            token=token,
            summary=summary,
            notminor=True,
            bot=True,
            starttimestamp=timestamp,
            createonly=True,
            recreate=True,
            md5=md5)
        pass
            
    def query(self, name):
        """Retrieves information about a page from the wiki."""
        return self.call('query', prop='info|revisions',
            intoken='edit',
            titles=name)

    def login(self, user, password, firstattempt=True):
        """Logs in to MediaWiki with a given name and password."""
        decoded = self.call('login', lgname=user,
            lgpassword=password,
            lgtoken=self.token)
        if 'NeedToken' == decoded['login']['result'] and firstattempt:
            self.token = decoded['login']['token']
            self.login(user, password, False)
        elif 'Success' == decoded['login']['result']:
            if self.verbose:
                print 'Successful login'
        else:
            raise LoginException(decoded['login']['result'])

    def logout(self):
        """Logs out from MediaWiki."""
        self.call('logout')


def main():
    """Runs the application."""
    parser = ArgumentParser(description=('Uses metadata in the portage tree'
            ' to populate a wiki.'),
        epilog=('PackageBot gathers metadata from a portage tree and adds'
            ' information to a wiki.'),
        fromfile_prefix_chars='@')
    parser.add_argument('-V', '--version',
        action='version',
        version='0',
        help='print the version of Packagebot and exit')
    parser.add_argument('-v', '--verbose',
        action='store_true',
        dest='verbose',
        default=False,
        help='print details on what Packagebot is doing')
    parser.add_argument('-j', '--jobs',
        action='store',
        dest='jobs',
        type=int,
        default=1,
        help='run jobs in parallel',
        nargs='?')
    parser.add_argument('user',
        action='store',
        help='user for logging into MediaWiki')
    parser.add_argument('password',
        action='store',
        help='password for logging into MediaWiki')
    parser.add_argument('--useragent',
        action='store',
        dest='useragent',
        default='Funtoo/Packagebot',
        help='Specify the useragent for Packagebot to use',
        nargs='?')
    parser.add_argument('tree',
        action='store',
        default='/usr/portage',
        help='specify the location of the portage tree',
        nargs='?')
    parser.add_argument('endpoint',
        action='store',
        default='http://docs.funtoo.org',
        help='endpoint for MediaWiki API',
        nargs='?')
    options = parser.parse_args()
    if options.verbose:
        print 'Starting in verbose mode'
    tree = os.path.normpath(options.tree)
    jobs = options.jobs
    if options.verbose:
        print 'Using portage tree at %(tree)s' % {'tree': tree}
        print 'Using %(jobs)u jobs' % {'jobs': jobs}
    mediawiki = MediaWiki(options.endpoint, options.useragent, options.verbose)
    try:
        mediawiki.login(options.user, options.password)
        bot = PackageBot(options.verbose, tree, jobs, mediawiki)
        bot.run()
        mediawiki.logout()
    except LoginException:
        print 'There was a failure logging in.'

if __name__ == '__main__':
    main()
