import os
import sys
import zipfile
from collections import defaultdict
from os.path import basename, isfile, isdir, join

from enstaller.repo.indexed import LocalIndexedRepo, RemoteHTTPIndexedRepo

from enstaller.utils import comparable_version, md5_file, stream_to_file
import metadata
import dist_naming
from requirement import Req, add_Reqs_to_spec


class Resolve(object):

    def __init__(self, repo, auth=None, verbose=False):
        self.verbose = verbose
        repo.connect(auth=auth)
        self.repo = repo

        # maps egg names to specs
        self.index = dict(repo.query())

        # maps cnames to the list of egg names
        self.groups = defaultdict(list)

        for egg, spec in self.index.itervalues():
            add_Reqs_to_spec(spec)
            self.groups[spec['cname']].append(egg)

    def get_version_build(self, egg):
        """
        Returns a tuple(version, build) for an egg name, where version is a
        RationalVersion object (see verlib).  This method is used below
        for determining the distribution with the largest version and build
        number.
        """
        return dist_naming.comparable_spec(self.index[egg])

    def get_egg(self, req):
        """
        return the egg with the largest version and build number
        """
        matches = []
        for egg in self.groups[req.name]:
            if req.matches(self.index[egg]):
                matches.append(egg)
        return max(matches, key=self.get_version_build)

    def reqs_egg(self, egg):
        """
        return the set of requirement objects listed by the given egg
        """
        return self.index[egg]['Reqs']

    def cname_egg(self, egg):
        """
        return the canonical project name for a given distribution
        """
        return self.index[egg]['cname']

    def are_complete(self, eggs):
        """
        return True if the distributions 'eggs' are complete, i.e. the for
        each distribution all dependencies (by name only) are also included
        in the 'eggs'
        """
        cnames = set(self.cname_egg(d) for d in eggs)
        for egg in eggs:
            for r in self.reqs_egg(egg):
                if r.name not in cnames:
                    return False
        return True

    def determine_install_order(self, eggs):
        """
        given the distributions 'eggs' (which are already complete, i.e.
        the for each distribution all dependencies are also included in
        the 'eggs'), return a list of the same distribution in the correct
        install order
        """
        eggs = list(eggs)
        assert self.are_complete(eggs)

        # make sure each project name is listed only once
        assert len(eggs) == len(set(self.cname_egg(d) for d in eggs))

        # the distributions corresponding to the requirements must be sorted
        # because the output of this function is otherwise not deterministic
        eggs.sort(key=self.cname_egg)

        # maps egg -> set of required (project) names
        rns = {}
        for egg in eggs:
            rns[egg] = set(r.name for r in self.reqs_egg(egg))

        # as long as we have things missing, simply look for things which
        # can be added, i.e. all the requirements have been added already
        result = []
        names_inst = set()
        while len(result) < len(eggs):
            n = len(result)
            for egg in eggs:
                if egg in result:
                    continue
                # see if all required packages were added already
                if all(bool(name in names_inst) for name in rns[egg]):
                    result.append(egg)
                    names_inst.add(self.index[egg]['cname'])
                    assert len(names_inst) == len(result)

            if len(result) == n:
                # nothing was added
                raise Exception("Loop in dependency graph\n%r" %
                                [dist_naming.filename_dist(d) for d in eggs])
        return result

    def _sequence_flat(self, root):
        eggs = [root]
        for r in self.reqs_egg(root):
            d = self.get_egg(r)
            if d is None:
                sys.exit('Error: could not resolve %r' % r)
            eggs.append(d)

        can_order = self.are_complete(eggs)
        if self.verbose:
            print "Can determine install order:", can_order
        if can_order:
            eggs = self.determine_install_order(eggs)
        return eggs

    def _sequence_recur(self, root):
        reqs_shallow = {}
        for r in self.reqs_egg(root):
            reqs_shallow[r.name] = r
        reqs_deep = defaultdict(set)

        def add_dependents(egg):
            for r in self.reqs_egg(egg):
                reqs_deep[r.name].add(r)
                if (r.name in reqs_shallow  and
                        r.strictness < reqs_shallow[r.name].strictness):
                    continue
                d = self.get_egg(r)
                if d is None:
                    sys.exit('Error: could not resolve %r required by %r' %
                             (r, egg))
                eggs.add(d)
                add_dependents(d)

        eggs = set([root])
        add_dependents(root)

        cnames = set(self.cname_egg(d) for d in eggs)
        if len(eggs) != len(cnames):
            for cname in cnames:
                ds = [d for d in eggs if self.cname_egg(d) == cname]
                assert len(ds) != 0
                if len(ds) == 1:
                    continue
                if self.verbose:
                    print 'multiple: %s' % cname
                    for d in ds:
                        print '    %s' % d
                r = max(reqs_deep[cname], key=lambda r: r.strictness)
                assert r.name == cname
                # remove the eggs with name 'cname'
                eggs = [d for d in eggs if self.cname_egg(d) != cname]
                # add the one
                eggs.append(self.get_egg(r))

        return self.determine_install_order(eggs)

    def install_sequence(self, req, mode='recur'):
        """
        Return the list of distributions which need to be installed.
        The returned list is given in dependency order.
        The 'mode' may be:

        'root':  only the distribution for the requirement itself is
                 contained in the result (but not any dependencies)

        'flat':  dependencies are handled only one level deep

        'recur': dependencies are handled recursively (default)
        """
        if self.verbose:
            print "Determining install sequence for %r" % req
        root = self.get_egg(req)
        if root is None:
            return None

        if mode == 'root':
            return [root]

        if mode == 'flat':
            return self._sequence_flat(root)

        if mode == 'recur':
            return self._sequence_recur(root)

        raise Exception('did not expect: mode = %r' % mode)

    def list_versions(self, name):
        """
        given the name of a package, retruns a sorted list of versions for
        package `name` found in any repo.
        """
        versions = set()

        req = Req(name)
        for egg in self.groups[req.name]:
            spec = self.index[egg]
            if req.matches(spec):
                versions.add(spec['version'])

        try:
            return sorted(versions, key=comparable_version)
        except TypeError:
            return list(versions)


if __name__ == '__main__':
    from indexed import LocalIndexedRepo

    res = Resolve([LocalIndexedRepo('/Users/ischnell/repo'),
                   LocalIndexedRepo('/Users/ischnell/repo2'),
                   ])
    res.get_egg
    for key in r.query_keys():#name='Cython'):
        print key