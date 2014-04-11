# optparse.py
# CLI options parser.
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import unicode_literals
from dnf.i18n import _

import argparse
import dnf.yum.misc
import logging
import sys
import dnf.exceptions

logger = logging.getLogger("dnf")

class OptionParser(argparse.ArgumentParser):
    """Subclass that makes some minor tweaks to make ArgumentParser do things the
    "yum way".
    """

    def __init__(self, **kwargs):
        argparse.ArgumentParser.__init__(self, add_help=False, **kwargs)
        self._cmd_usage = {} # names, summary for dnf commands, to build usage
        self._cmd_groups = set() # cmd groups added (main, plugin)
        self._addYumBasicOptions()

    def error(self, msg):
        """Output an error message, and exit the program.  This method
        is overridden so that error output goes to the logger.

        :param msg: the error message to output
        """
        self.print_usage()
        logger.critical(_("Command line error: %s"), msg)
        sys.exit(1)

    @staticmethod
    def _splitArg(seq):
        """ Split all strings in seq, at "," and whitespace.
            Returns a new list. """
        ret = []
        for arg in seq:
            ret.extend(arg.replace(",", " ").split())
        return ret

    @staticmethod
    def _non_nones2dict(in_dct):
        dct = {k: in_dct[k] for k in in_dct
               if in_dct[k] is not None
               if in_dct[k] != []}
        return dct

    def configure_from_options(self, opts, conf, demands, output):
        """Configure parts of CLI from the opts. """

        try:
            # config file is parsed and moving us forward
            # set some things in it.
            if opts.best:
                conf.best = opts.best

            # Handle remaining options
            if opts.allowerasing:
                demands.allow_erasing = opts.allowerasing

            if opts.assumeyes:
                conf.assumeyes = 1
            if opts.assumeno:
                conf.assumeno = 1

            if opts.disableplugins:
                opts.disableplugins = self._splitArg(opts.disableplugins)

            if opts.obsoletes:
                conf.obsoletes = 1

            if opts.installroot:
                self._checkAbsInstallRoot(opts.installroot)
                conf.installroot = opts.installroot
            if opts.noplugins:
                conf.plugins = False

            if opts.showdupesfromrepos:
                conf.showdupesfromrepos = True

            if opts.color not in (None, 'auto', 'always', 'never',
                                  'tty', 'if-tty', 'yes', 'no', 'on', 'off'):
                raise ValueError(_("--color takes one of: auto, always, never"))
            elif opts.color is None:
                if conf.color != 'auto':
                    output.term.reinit(color=conf.color)
            else:
                _remap = {'tty' : 'auto', 'if-tty' : 'auto',
                          '1' : 'always', 'true' : 'always',
                          'yes' : 'always', 'on' : 'always',
                          '0' : 'always', 'false' : 'always',
                          'no' : 'never', 'off' : 'never'}
                opts.color = _remap.get(opts.color, opts.color)
                if opts.color != 'auto':
                    output.term.reinit(color=opts.color)

            if opts.disableexcludes:
                disable_excludes = self._splitArg(opts.disableexcludes)
            else:
                disable_excludes = []
            conf.disable_excludes = disable_excludes

            for exclude in self._splitArg(opts.exclude):
                try:
                    excludelist = conf.exclude
                    excludelist.append(exclude)
                    conf.exclude = excludelist
                except dnf.exceptions.ConfigError as e:
                    logger.critical(e)
                    self.print_help()
                    sys.exit(1)

            if opts.rpmverbosity is not None:
                conf.rpmverbosity = opts.rpmverbosity

        except ValueError as e:
            logger.critical(_('Options Error: %s'), e)
            self.print_help()
            sys.exit(1)

    @staticmethod
    def _checkAbsInstallRoot(installroot):
        if not installroot:
            return
        if installroot[0] == '/':
            return
        # We have a relative installroot ... haha
        logger.critical(_('--installroot must be an absolute path: %s'),
                             installroot)
        sys.exit(1)

    class _RepoCallback(argparse.Action):
        def __call__(self, parser, namespace, values, opt_str):
            operation = 'disable' if opt_str == '--disablerepo' else 'enable'
            l = getattr(namespace, self.dest)
            l.append((values, operation))

    def _addYumBasicOptions(self):
        # All defaults need to be a None, so we can always tell whether the user
        # has set something or whether we are getting a default.
        self.conflict_handler = "resolve"
        self.conflict_handler = "error"

        self.add_argument('--allowerasing', action='store_true', default=None,
                           help=_('allow erasing of installed packages to '
                                  'resolve dependencies'))
        self.add_argument("-b", "--best", action="store_true", default=None,
                           help=_("try the best available package versions in "
                                  "transactions."))
        self.add_argument("-C", "--cacheonly", dest="cacheonly",
                           action="store_true", default=None,
                           help=_("run entirely from system cache, "
                                  "don't update cache"))
        self.add_argument("-c", "--config", dest="conffile",
                           default=None, metavar='[config file]',
                           help=_("config file location"))
        self.add_argument("-R", "--randomwait", dest="sleeptime", type=int,
                           default=None, metavar='[minutes]',
                           help=_("maximum command wait time"))
        self.add_argument("-d", "--debuglevel", dest="debuglevel",
                           metavar='[debug level]', default=None,
                           help=_("debugging output level"), type=int)
        self.add_argument("--debugrepodata",
                           action="store_true", default=None,
                           help=_("dumps package metadata into files"))
        self.add_argument("--debugsolver",
                           action="store_true", default=None,
                           help=_("dumps detailed solving results into files"))
        self.add_argument("--showduplicates", dest="showdupesfromrepos",
                           action="store_true", default=None,
                           help=_("show duplicates, in repos, "
                                  "in list/search commands"))
        self.add_argument("-e", "--errorlevel", default=None, type=int,
                           help=_("error output level"))
        self.add_argument("--rpmverbosity", default=None,
                           help=_("debugging output level for rpm"),
                           metavar='[debug level name]')
        self.add_argument("-q", "--quiet", dest="quiet", action="store_true",
                           default=None, help=_("quiet operation"))
        self.add_argument("-v", "--verbose", action="store_true",
                           default=None, help=_("verbose operation"))
        self.add_argument("-y", "--assumeyes", action="store_true",
                           default=None, help=_("answer yes for all questions"))
        self.add_argument("--assumeno", action="store_true",
                           default=None, help=_("answer no for all questions"))
        self.add_argument("--version", action="store_true", default=None,
                           help=_("show Yum version and exit"))
        self.add_argument("--installroot", help=_("set install root"),
                           metavar='[path]')
        self.add_argument("--enablerepo", action=self._RepoCallback,
                           dest='repos_ed', default=[],
                           metavar='[repo]')
        self.add_argument("--disablerepo", action=self._RepoCallback,
                           dest='repos_ed', default=[],
                           metavar='[repo]')
        self.add_argument("-x", "--exclude", default=[], action="append",
                           help=_("exclude packages by name or glob"),
                           metavar='[package]')
        self.add_argument("--disableexcludes", default=[], action="append",
                          help=_("disable excludes"),
                          metavar='[repo]')
        self.add_argument("--obsoletes", action="store_true", default=None,
                          help=_("enable obsoletes processing during upgrades"))
        self.add_argument("--noplugins", action="store_true", default=None,
                           help=_("disable all plugins"))
        self.add_argument("--nogpgcheck", action="store_true", default=None,
                          help=_("disable gpg signature checking"))
        self.add_argument("--disableplugin", dest="disableplugins", default=[],
                           action="append",
                           help=_("disable plugins by name"),
                           metavar='[plugin]')
        self.add_argument("--color", dest="color", default=None,
                          help=_("control whether color is used"))
        self.add_argument("--releasever", default=None,
                           help=_("override the value of $releasever in config"
                                  " and repo files"))
        self.add_argument("--setopt", dest="setopts", default=[],
                           action="append",
                           help=_("set arbitrary config and repo options"))
        # we add our own help option, so we can control that help is not shown
        # automatic when we do the .parse_known_args(args)
        # but first after plugins are loaded.
        self.add_argument('-h', '--help', action="store_true", help="show help")

    def _add_cmd_usage(self, cmd, group):
        """ store usage info about a single dnf command."""
        summary = cmd.summary
        name = cmd.aliases[0]
        if not name in self._cmd_usage:
            self._cmd_usage[name] = (group, summary)
            self._cmd_groups.add(group)

    def add_commands(self, cli_cmds, group):
        """ store name & summary for dnf commands

        The stored information is used build usage information
        grouped by build-in & plugin commands.
        """
        commands = dnf.yum.misc.unique([x for x in cli_cmds.values()])
        for cmd in commands:
            self._add_cmd_usage(cmd, group)

    def get_usage(self):
        """ get the usage infomation to show the user. """
        desc = {'main': _('List of Main Commands'),
                'plugin': _('List of Plugin Commands')}
        name = dnf.const.PROGRAM_NAME
        usage = '%s [options] COMMAND\n' % name
        for grp in ['main', 'plugin']:
            if not grp in self._cmd_groups:  # dont add plugin usage, if we dont have plugins
                continue
            usage += "\n%s\n\n" % desc[grp]
            for name in sorted(self._cmd_usage.keys()):
                group, summary = self._cmd_usage[name]
                if group == grp:
                    usage += "%-25s %s\n" % (name, summary)
        return usage
