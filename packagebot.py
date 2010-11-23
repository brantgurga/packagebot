# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil -*-
import os
import thread
import time
import StringIO
import urllib
import urllib2
import cookielib
import json
from xml.etree import ElementTree
from argparse import ArgumentParser


class Metadata(object):
    def __init__(self, name, xml, verbose):
        object.__init__(self)
        self.name = name
        self.xml = xml
        self.verbose = verbose

    def __str__(self):
        return 'Metadata: %(name)s' % {'name': self.name}

    def __repr__(self):
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
    def __init__(self, name, xml, verbose):
        Metadata.__init__(self, name, xml, verbose)
        if self.verbose:
            print 'Created category %(name)s' % {'name': self.name}

    def __str__(self):
        return 'Category: %(name)s' % {'name': self.name}

    def __repr__(self):
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
    def __init__(self, name, category, xml, verbose):
        Metadata.__init__(self, name, xml, verbose)
        self.category = category
        if self.verbose:
            print 'Created ebuild %(name)s' % {'name': self.name}

    def __str__(self):
        return ('Ebuild: %(category)s/%(name)s' %
            {'category': self.category, 'name': self.name})

    def __repr__(self):
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
    def __init__(self, verbose, tree, jobs, mediawiki):
        object.__init__(self)
        self.verbose = verbose
        self.tree = tree
        self.jobs = jobs
        self.mediawiki = mediawiki
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
        for m in self.metadata[:25]:
            print m

    def divvy_work(self, work, parts):
        quotient, remainder = divmod(len(work), parts)
        indices = [quotient * part + min(part, remainder)
            for part in xrange(parts + 1)]
        return [work[indices[part]:indices[part + 1]]
            for part in xrange(parts)]

    def do_work(self, task):
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
        with self._result_lock:
            self.metadata.extend(result)
            self._thread_count -= 1

class LoginException(Exception):
    def __init__(self, code):
        Exception.__init__(self)
        self.code = code

    def __str__(self):
        print 'Login Issue: %(code)s' % {'code': self.code}

    def __repr__(self):
        print 'LoginException(%(code)s)' % {'code': repr(self.code)}

class MediaWiki(object):
    def __init__(self, endpoint, useragent, verbose):
        object.__init__(self)
        self.endpoint = endpoint
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

    def login(self, user, password, firstattempt = True):
        params = urllib.urlencode({'action': 'login',
            'lgname': user,
            'lgpassword': password,
            'lgtoken': self.token,
            'format': 'json'})
        if self.verbose:
            print 'Using parameters: %(params)s' % {'params': params}
            print 'Using cookies:'
            for cookie in self.cookies:
                print ('%(name)s=%(value)s' %
                    {'name': cookie.name, 'value': cookie.value})
        request = urllib2.Request(self.endpoint, params,
            {'User-Agent': self.useragent})
        result = self.opener.open(request)
        if self.verbose:
            print 'Request sent to %(dest)s' % {'dest': result.geturl()}
            print 'Result metadata: %(metadata)s' % {'metadata': result.info()}
        content = result.read()
        if self.verbose:
            print 'Result: %(result)s' % {'result': content}
        decoded = json.loads(content)
        if 'NeedToken' == decoded['login']['result'] and firstattempt:
            self.token = decoded['login']['token']
            self.login(user, password)
        elif 'Success' == decoded['login']['result']:
            if self.verbose:
                print 'Successful login'
        else:
            raise LoginException(decoded['login']['result'])
        

    def logout(self):
        params = urllib.urlencode({'action': 'logout', 'format': 'json'})
        if self.verbose:
            print 'Using parameters: %(params)s' % {'params': params}
        request = urllib2.Request(self.endpoint, params,
            {'User-Agent': self.useragent})
        result = self.opener.open(request)
        if self.verbose:
            print 'Request sent to %(dest)s' % {'dest': result.geturl()}
            print 'Result metadata: %(metadata)s' % {'metadata': result.info()}
            print 'Result: %(result)s' % {'result': result.read()}


def main():
    parser = ArgumentParser(description = ('Uses metadata in the portage tree'
            ' to populate a wiki.'),
        epilog = ('PackageBot gathers metadata from a portage tree and adds'
            ' information to a wiki.'),
        fromfile_prefix_chars='@')
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
    parser.add_argument('user',
        action = 'store',
        help = 'user for logging into MediaWiki')
    parser.add_argument('password',
        action = 'store',
        help = 'password for logging into MediaWiki')
    parser.add_argument('--useragent',
        action = 'store',
        dest = 'useragent',
        default = 'Funtoo/Packagebot',
        help = 'Specify the useragent for Packagebot to use',
        nargs = '?')
    parser.add_argument('tree',
        action = 'store',
        default = '/usr/portage',
        help = 'specify the location of the portage tree',
        nargs = '?')
    parser.add_argument('endpoint',
        action = 'store',
        default = 'http://docs.funtoo.org/api.php',
        help = 'endpoing for MediaWiki API',
        nargs = '?')
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
