import sys
import json
import subprocess
from glob import glob
from os.path import isdir, isfile, join

import egginst
from egginst.utils import pprint_fn_action, console_progress

from egg_meta import split_eggname
from plat import custom_plat
import resolve
import fetch


class Launch(object):

    def __init__(self, remote, prefix=sys.prefix, plat=custom_plat,
                 verbose=False):
        self.remote = remote
        self.prefix = prefix
        self.plat = custom_plat
        self.verbose = verbose

        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.local_dir = join(prefix, 'LOCAL-REPO')
        self.pkgs_dir = join(prefix, 'pkgs')

    def get_installed_apps(self):
        for p in glob(join(self.pkgs_dir, '*', 'EGG-INFO', 'app.json')):
            info = json.load(open(p))
            yield info['key'], info

    def launch_app(self, egg, args=None):
        info = json.load(open(
                join(self.egginfo_dir_egg(egg), 'app.json')))
        if 'app_cmd' in info:
            cmd = info['app_cmd']
        else:
            cmd = [sys.executable,
                   join(self.egginfo_dir_egg(egg), 'app.py')]
        if args:
            cmd.extend(args)
        subprocess.call(cmd)

    def install_app(self, egg, force=False):
        self.install_recur(egg, True, force)

    def install_recur(self, egg, hook, force=False):
        info = self.remote.get_metadata(egg)
        # todo handle python version
        resolver = resolve.Resolve(self.remote, self.verbose)
        req = resolve.Req('%(name)s %(version)s-%(build)d' % info)
        for e in resolver.install_sequence(req):
            self.install(e, hook, force)

    def install(self, egg, hook, force=False):
        if not force and hook and isfile(self.registry_path_egg(egg)):
            if self.verbose:
                print "Already installed:", egg
            return
        egg_path = join(self.local_dir, egg)
        if force or not isfile(egg_path):
            self.fetch_egg(egg, force)
        self.action_callback(egg, 'installing')
        ei = egginst.EggInst(egg_path, prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.install()

    def remove(self, egg, hook):
        self.action_callback(egg, 'removing')
        ei = egginst.EggInst(egg, prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.remove()

    def registry_path_egg(self, egg):
        return join(self.egginfo_dir_egg(egg), 'registry.txt')

    def egginfo_dir_egg(self, egg):
        return join(self.versioned_dir_egg(egg), 'EGG-INFO')

    def versioned_dir_egg(self, egg):
        n, v, b = split_eggname(egg)
        return join(self.pkgs_dir, '%s-%s-%d' % (n.lower(), v, b))

    def fetch_egg(self, egg, force=False):
        f = fetch.FetchAPI(self.remote, self.local_dir)
        f.action_callback = self.action_callback
        f.progress_callback = self.progress_callback
        f.verbose = self.verbose
        f.fetch_egg(egg, force)


if __name__ == '__main__':
    from store.indexed import LocalIndexedStore
    from store.joined import JoinedStore

    rem = JoinedStore([LocalIndexedStore('/Users/ischnell/repo'),
                       LocalIndexedStore('/Users/ischnell/repo2')])
    #rem = LocalIndexedStore('/home/ischnell/eggs/')
    rem.connect()
    prefix = '/Users/ischnell/jpm/Python-2.7'#.2-1'
    x = Launch(rem, prefix=prefix)#, verbose=1)
    fn = 'nose-1.1.2-1.egg'
    #x.install('enstaller-4.5.0-1.egg')
    #x.remove('enstaller-4.5.0-1.egg')
    x.install_app(fn)#, force=1)
#    for d in x.get_installed_apps():
#        print d
    x.launch_app(fn, ['--version'])