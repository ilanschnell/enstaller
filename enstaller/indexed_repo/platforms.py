from os.path import isdir, join

from enstaller.utils import open_with_auth


def to_list(s):
    return s.replace(',', ' ').split()


class Platforms(object):
    """
    An instance represents the list of platforms which are available in a
    repository.  An instance in instantiated by either a local directory
    or a URL which points to an HTTP server.
    """

    def __init__(self, url):
        fn = 'platforms.txt'
        if isdir(url):
            self.txt = open(join(url, fn)).read()
        else:
            handle = open_with_auth(url + fn)
            self.txt = handle.read()
            handle.close()

        self.set_data()

    def set_data(self):
        self.data = {}
        for line in self.txt.splitlines():
            line = line.strip()
            if not line or line.startswith(('#', '--', 'ID')):
                continue
            row = to_list(line)
            ID = int(row[0])
            self.data[ID] = dict(
                subdir = row[1],
                arch = [row[2]],
                platform = [row[3]],
                osdist = row[4:],
                )

    def _ID_matches(self, ID, var, val):
        """
        Returns True if any value belonging to the variable matches the
        platform with the ID.
        """
        if not val:
            return True
        return any(v in self.data[ID][var] for v in to_list(val))

    def get_IDs(self, spec=None):
        """
        returns a sorted list of platform IDs for which the requirements
        (if provided) match.  If the requirements are not provided all IDs
        are returned.
        """
        res = set()
        for ID in self.data.iterkeys():
            if (spec is None or
                all(self._ID_matches(ID, var, spec[var])
                    for var in ['arch', 'platform', 'osdist'])):
                res.add(ID)
        return sorted(res)


if __name__ == '__main__':
    egg_root = 'http://www.enthought.com/repo/epd/eggs/'
    p = Platforms(egg_root)
    print p.txt
    print p.data[2]['subdir']
    for i in xrange(1, 11):
        print '%2i %6s %6s' % (
            i,
            p._ID_matches(i, 'arch', 'amd64'),
            p._ID_matches(i, 'osdist', 'XP, Solaris_10'))
    print "IDs:", p.get_IDs(dict(
        osdist=None,
        platform='linux2, win32, darwin',
        arch=None,
        ))
    print "IDs:", p.get_IDs(dict(
        osdist='XP',
        platform='win32',
        arch='x86',
        ))
