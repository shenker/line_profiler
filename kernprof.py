#!/usr/bin/env python
# -*- coding: UTF-8 -*-
""" Script to conveniently run the profiler on code in a variety of
circumstances.
"""

import cProfile
import optparse
import os
import sys

def find_script(script_name):
    """ Find the script.

    If the input is not a file, then $PATH will be searched.
    """
    if os.path.isfile(script_name):
        return script_name
    path = os.getenv('PATH', os.defpath).split(os.pathsep)
    for dir in path:
        if dir == '':
            continue
        fn = os.path.join(dir, script_name)
        if os.path.isfile(fn):
            return fn

    print >>sys.stderr, 'Could not find script %s' % script_name
    raise SystemExit(1)

class ContextualProfile(cProfile.Profile):
    """ A subclass of cProfile.Profile that adds a context manager for Python
    2.5 with: statements and a decorator.
    """

    def __init__(self, *args, **kwds):
        super(ContextualProfile, self).__init__(*args, **kwds)
        self.enable_count = 0

    def enable_by_count(self, subcalls=True, builtins=True):
        """ Enable the profiler if it hasn't been enabled before.
        """
        if self.enable_count == 0:
            self.enable(subcalls=subcalls, builtins=builtins)
        self.enable_count += 1

    def disable_by_count(self):
        """ Disable the profiler if the number of disable requests matches the
        number of enable requests.
        """
        if self.enable_count > 0:
            self.enable_count -= 1
            if self.enable_count == 0:
                self.disable()

    def __call__(self, func):
        """ Decorate a function to start the profiler on function entry and stop
        it on function exit.
        """
        def f(*args, **kwds):
            self.enable_by_count()
            try:
                result = func(*args, **kwds)
            finally:
                self.disable_by_count()
            return result
        f.__name__ = func.__name__
        f.__doc__ = func.__doc__
        f.__dict__.update(func.__dict__)
        return f

    def __enter__(self):
        self.enable_by_count()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disable_by_count()


def main(args):
    usage = "%s [-s setupfile] [-o output_file_path] scriptfile [arg] ..."
    parser = optparse.OptionParser(usage=usage % sys.argv[0])
    parser.allow_interspersed_args = False
    parser.add_option('-l', '--line-by-line', action='store_true',
        help="Use the line-by-line profiler from the line_profiler module "
        "instead of cProfile. Implies --builtin.")
    parser.add_option('-b', '--builtin', action='store_true',
        help="Put 'profile' in the builtins. Use 'profile.enable()' and "
            "'profile.disable()' in your code to turn it on and off, or "
            "'@profile' to decorate a single function, or 'with profile:' "
            "to profile a single section of code.")
    parser.add_option('-o', '--outfile', default=None,
        help="Save stats to <outfile>")
    parser.add_option('-s', '--setup', default=None,
       help="Code to execute before the code to profile")

    if not sys.argv[1:]:
        parser.print_usage()
        sys.exit(2)

    options, args = parser.parse_args()

    if not options.outfile:
        if options.line_by_line:
            extension = 'lprof'
        else:
            extension = 'prof'
        options.outfile = '%s.%s' % (os.path.basename(args[0]), extension)

    ns = locals()

    sys.argv[:] = args
    if options.setup is not None:
        # Run some setup code outside of the profiler. This is good for large
        # imports.
        setup_file = find_script(options.setup)
        __file__ = setup_file
        __name__ = '__main__'
        # Make sure the script's directory is on sys.path instead of just
        # kernprof.py's.
        sys.path.insert(0, os.path.dirname(setup_file))
        execfile(setup_file, ns, ns)

    script_file = find_script(sys.argv[0])
    __file__ = script_file
    __name__ = '__main__'
    # Make sure the script's directory is on sys.path instead of just
    # kernprof.py's.
    sys.path.insert(0, os.path.dirname(script_file))

    if options.line_by_line:
        import line_profiler
        prof = line_profiler.LineProfiler()
        options.builtin = True
    else:
        prof = ContextualProfile()
    if options.builtin:
        import __builtin__
        __builtin__.__dict__['profile'] = prof

    try:
        try:
            if options.builtin:
                execfile(script_file, ns, ns)
            else:
                prof.runctx('execfile(%r)' % (script_file,), ns, ns)
        except (KeyboardInterrupt, SystemExit):
            pass
    finally:
        prof.dump_stats(options.outfile)
        print 'Wrote profile results to %s' % options.outfile

if __name__ == '__main__':
    sys.exit(main(sys.argv))

