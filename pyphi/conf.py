#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# conf.py

'''
Loading a configuration
~~~~~~~~~~~~~~~~~~~~~~~

Various aspects of PyPhi's behavior can be configured.

When PyPhi is imported, it checks for a YAML file named ``pyphi_config.yml`` in
the current directory and automatically loads it if it exists; otherwise the
default configuration is used.

The various settings are listed here with their defaults.

    >>> import pyphi
    >>> defaults = pyphi.config.defaults()

It is also possible to manually load a configuration file:

    >>> pyphi.config.load_config_file('pyphi_config.yml')

Or load a dictionary of configuration values:

    >>> pyphi.config.load_config_dict({'SOME_CONFIG': 'value'})

Many settings can also be changed on the fly by simply assigning them a new
value:

    >>> pyphi.config.PROGRESS_BARS = True


Approximations and theoretical options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These settings control the algorithms PyPhi uses.

- :attr:`~pyphi.conf.PyphiConfig.ASSUME_CUTS_CANNOT_CREATE_NEW_CONCEPTS`
- :attr:`~pyphi.conf.PyphiConfig.CUT_ONE_APPROXIMATION`
- :attr:`~pyphi.conf.PyphiConfig.MEASURE`
- :attr:`~pyphi.conf.PyphiConfig.PARTITION_TYPE`
- :attr:`~pyphi.conf.PyphiConfig.PICK_SMALLEST_PURVIEW`
- :attr:`~pyphi.conf.PyphiConfig.USE_SMALL_PHI_DIFFERENCE_FOR_CONSTELLATION_DISTANCE`
- :attr:`~pyphi.conf.PyphiConfig.SYSTEM_CUTS`


System resources
~~~~~~~~~~~~~~~~

These settings control how much processing power and memory is available for
PyPhi to use. The default values may not be appropriate for your use-case or
machine, so **please check these settings before running anything**. Otherwise,
there is a risk that simulations might crash (potentially after running for a
long time!), resulting in data loss.

- :attr:`~pyphi.conf.PyphiConfig.PARALLEL_CONCEPT_EVALUATION`
- :attr:`~pyphi.conf.PyphiConfig.PARALLEL_CUT_EVALUATION`
- :attr:`~pyphi.conf.PyphiConfig.PARALLEL_COMPLEX_EVALUATION`

  .. warning::
    Only one of ``PARALLEL_CONCEPT_EVALUATION``, ``PARALLEL_CUT_EVALUATION``,
    and ``PARALLEL_COMPLEX_EVALUATION`` can be set to ``True`` at a time. For
    maximal efficiency, you should parallelize the highest level computations
    possible, *e.g.*, parallelize complex evaluation instead of cut evaluation,
    but only if you are actually computing complexes. You should only
    parallelize concept evaluation if you are just computing constellations.

- :attr:`~pyphi.conf.PyphiConfig.NUMBER_OF_CORES`
- :attr:`~pyphi.conf.PyphiConfig.MAXIMUM_CACHE_MEMORY_PERCENTAGE`


Caching
~~~~~~~

PyPhi is equipped with a transparent caching system for |BigMip| objects which
stores them as they are computed to avoid having to recompute them later. This
makes it easy to play around interactively with the program, or to accumulate
results with minimal effort. For larger projects, however, it is recommended
that you manage the results explicitly, rather than relying on the cache. For
this reason it is disabled by default.

- :attr:`~pyphi.conf.PyphiConfig.CACHE_BIGMIPS`
- :attr:`~pyphi.conf.PyphiConfig.CACHE_POTENTIAL_PURVIEWS`
- :attr:`~pyphi.conf.PyphiConfig.CACHING_BACKEND`
- :attr:`~pyphi.conf.PyphiConfig.FS_CACHE_VERBOSITY`
- :attr:`~pyphi.conf.PyphiConfig.FS_CACHE_DIRECTORY`
- :attr:`~pyphi.conf.PyphiConfig.MONGODB_CONFIG`
- :attr:`~pyphi.conf.PyphiConfig.REDIS_CACHE`
- :attr:`~pyphi.conf.PyphiConfig.REDIS_CONFIG`


Logging
~~~~~~~

These settings control how PyPhi handles log messages. Logs can be written to
standard output, a file, both, or none. If these simple default controls are
not flexible enough for you, you can override the entire logging configuration.
See the `documentation on Python's logger
<https://docs.python.org/3.4/library/logging.html>`_ for more information.

- :attr:`~pyphi.conf.PyphiConfig.LOG_STDOUT_LEVEL`
- :attr:`~pyphi.conf.PyphiConfig.LOG_FILE_LEVEL`
- :attr:`~pyphi.conf.PyphiConfig.LOG_FILE`
- :attr:`~pyphi.conf.PyphiConfig.LOG_CONFIG_ON_IMPORT`
- :attr:`~pyphi.conf.PyphiConfig.PROGRESS_BARS`
- :attr:`~pyphi.conf.PyphiConfig.REPR_VERBOSITY`
- :attr:`~pyphi.conf.PyphiConfig.PRINT_FRACTIONS`


Numerical precision
~~~~~~~~~~~~~~~~~~~

- :attr:`~pyphi.conf.PyphiConfig.PRECISION`


Miscellaneous
~~~~~~~~~~~~~

- :attr:`~pyphi.conf.PyphiConfig.VALIDATE_SUBSYSTEM_STATES`
- :attr:`~pyphi.conf.PyphiConfig.VALIDATE_CONDITIONAL_INDEPENDENCE`
- :attr:`~pyphi.conf.PyphiConfig.SINGLE_MICRO_NODES_WITH_SELFLOOPS_HAVE_PHI`


The ``config`` API
~~~~~~~~~~~~~~~~~~
'''

# pylint: disable=too-few-public-methods

import contextlib
import logging
import logging.config
import os
import pprint
import sys
from copy import copy

import yaml

from . import __about__


class Option:
    '''A descriptor implementing PyPhi configuration options.'''
    def __init__(self, default, values=None, on_change=None, description=None):
        self.default = default
        self.values = values
        self.on_change = on_change
        self.description = description

        # Set during config initialization
        self.name = None

    @property
    def __doc__(self):
        values = '\n``values={}``'.format(
            repr(self.values)) if self.values is not None else ''

        return '``default={}``{}\n{}'.format(
            repr(self.default), values, self.description)

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return obj.__dict__[self.name]

    def __set__(self, obj, value):
        # Validate the new value
        if self.values and value not in self.values:
            raise ValueError(
                '{} is not a valid value for {}'.format(value, self.name))

        obj.__dict__[self.name] = value

        # Trigger any callbacks
        if self.on_change is not None:
            self.on_change(obj)


class Config:

    def __init__(self):
        # Set each Option's name and default value
        for k, v in self.options().items():
            v.name = k
            self.__dict__[k] = v.default

    def __str__(self):
        return pprint.pformat(self.__dict__, indent=2)

    def __setattr__(self, name, value):
        '''Before setting, check that the option is value.'''
        if name not in self.options().keys():
            raise ValueError('{} is not a valid config option'.format(name))
        super().__setattr__(name, value)

    @classmethod
    def options(cls):
        '''Return the dictionary ``option`` objects for this class.'''
        return {k: v for k, v in cls.__dict__.items() if isinstance(v, Option)}

    def defaults(self):
        return {k: v.default for k, v in self.options().items()}

    def load_config_dict(self, dct):
        '''Load a dictionary of configuration values.'''
        for k, v in dct.items():
            setattr(self, k, v)

    def load_config_file(self, filename):
        '''Load config from a YAML file.'''
        with open(filename) as f:
            self.load_config_dict(yaml.load(f))

    def snapshot(self):
        return copy(self.__dict__)

    def override(self, **new_config):
        '''Decorator and context manager to override configuration values.

        The initial configuration values are reset after the decorated function
        returns or the context manager completes it block, even if the function
        or block raises an exception. This is intended to be used by tests
        which require specific configuration values.

        Example:
            >>> from pyphi import config
            >>> @config.override(PRECISION=20000)
            ... def test_something():
            ...     assert config.PRECISION == 20000
            ...
            >>> test_something()
            >>> with config.override(PRECISION=100):
            ...     assert config.PRECISION == 100
            ...
        '''
        return _override(self, **new_config)


class _override(contextlib.ContextDecorator):
    '''See ``Config.override`` for usage.'''

    def __init__(self, config, **new_conf):
        self.config = config
        self.new_conf = new_conf
        self.initial_conf = config.snapshot()

    def __enter__(self):
        '''Save original config values; override with new ones.'''
        self.config.load_config_dict(self.new_conf)

    def __exit__(self, *exc):
        '''Reset config to initial values; reraise any exceptions.'''
        self.config.load_config_dict(self.initial_conf)
        return False


def configure_logging(config):
    '''Reconfigure PyPhi logging based on the current configuration.'''
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(name)s] %(levelname)s '
                          '%(processName)s: %(message)s'
            }
        },
        'handlers': {
            'file': {
                'level': config.LOG_FILE_LEVEL,
                'filename': config.LOG_FILE,
                'class': 'logging.FileHandler',
                'formatter': 'standard',
            },
            'stdout': {
                'level': config.LOG_STDOUT_LEVEL,
                'class': 'pyphi.log.ProgressBarHandler',
                'formatter': 'standard',
            }
        },
        'root': {
            'level': 'DEBUG',
            'handlers': (['file'] if config.LOG_FILE_LEVEL else []) +
                        (['stdout'] if config.LOG_STDOUT_LEVEL else [])
        }
    })


class PyphiConfig(Config):

    ASSUME_CUTS_CANNOT_CREATE_NEW_CONCEPTS = Option(False, description="""
    In certain cases, making a cut can actually cause a previously reducible
    concept to become a proper, irreducible concept. Assuming this can never
    happen can increase performance significantly, however the obtained results
    are not strictly accurate.  """)

    CUT_ONE_APPROXIMATION = Option(False, description="""
    When determining the MIP for |big_phi|, this restricts the set of system
    cuts that are considered to only those that cut the inputs or outputs of a
    single node. This restricted set of cuts scales linearly with the size of
    the system; the full set of all possible bipartitions scales
    exponentially. This approximation is more likely to give theoretically
    accurate results with modular, sparsely-connected, or homogeneous
    networks.""")

    MEASURE = Option('EMD', description="""
    The measure to use when computing distances between repertoires and
    concepts.  Users can dynamically register new measures with the
    ``pyphi.distance.measures.register`` decorator; see :mod:`~pyphi.distance`
    for examples. A full list of currently installed measures is available by
    calling ``print(pyphi.distance.measures.all())``. Note that some measures
    cannot be used for calculating |big_phi| because they are asymmetric.""")

    PARALLEL_CONCEPT_EVALUATION = Option(False, description="""
    Controls whether concepts are evaluated in parallel when computing
    constellations.""")

    PARALLEL_CUT_EVALUATION = Option(True, description="""
    Controls whether system cuts are evaluated in parallel, which is faster but
    requires more memory. If cuts are evaluated sequentially, only two |BigMip|
    instances need to be in memory at once.""")

    PARALLEL_COMPLEX_EVALUATION = Option(False, description="""
    Controls whether systems are evaluated in parallel when computing
    complexes.""")

    NUMBER_OF_CORES = Option(-1, description="""
    Controls the number of CPU cores used to evaluate unidirectional cuts.
    Negative numbers count backwards from the total number of available cores,
    with ``-1`` meaning "use all available cores.""")

    MAXIMUM_CACHE_MEMORY_PERCENTAGE = Option(50, description="""
    PyPhi employs several in-memory caches to speed up computation. However,
    these can quickly use a lot of memory for large networks or large numbers
    of them; to avoid thrashing, this setting limits the percentage of a
    system's RAM that the caches can collectively use.""")

    CACHE_BIGMIPS = Option(False, description="""
    Controls whether |BigMip| objects are cached and automatically
    retrieved.""")

    CACHE_POTENTIAL_PURVIEWS = Option(True, description="""
    Controls whether the potential purviews of mechanisms of a network are
    cached. Caching speeds up computations by not recomputing expensive
    reducibility checks, but uses additional memory.""")

    CACHING_BACKEND = Option('fs', description="""
    Controls whether precomputed results are stored and read from a local
    filesystem-based cache in the current directory or from a database. Set
    this to ``'fs'`` for the filesystem, ``'db'`` for the database.""")

    FS_CACHE_VERBOSITY = Option(0, description="""
    Controls how much caching information is printed if the filesystem cache is
    used. Takes a value between ``0`` and ``11``.""")

    FS_CACHE_DIRECTORY = Option('__pyphi_cache__', description="""
    If the filesystem is used for caching, the cache will be stored in this
    directory. This directory can be copied and moved around if you want to
    reuse results *e.g.* on a another computer, but it must be in the same
    directory from which Python is being run.""")

    MONGODB_CONFIG = Option({
        'host': 'localhost',
        'port': 27017,
        'database_name': 'pyphi',
        'collection_name': 'cache'
    }, description="""
    Set the configuration for the MongoDB database backend (only has an
    effect if ``CACHING_BACKEND`` is ``'db'``).""")

    REDIS_CACHE = Option(False, description="""
    Specifies whether to use Redis to cache |Mice|.""")

    REDIS_CONFIG = Option({
        'host': 'localhost',
        'port': 6379,
    }, description="""
    Configure the Redis database backend. These are the defaults in the
    provided ``redis.conf`` file.""")

    LOG_FILE = Option('pyphi.log', on_change=configure_logging, description="""
    Controls the name of the log file.""")

    LOG_FILE_LEVEL = Option('INFO', on_change=configure_logging, description="""
    Controls the level of log messages written to the log
    file. This setting has the same possible values as
    ``LOG_STDOUT_LEVEL``.""")

    LOG_STDOUT_LEVEL = Option('WARNING', on_change=configure_logging, description="""
    Controls the level of log messages written to standard
    output. Can be one of ``'DEBUG'``, ``'INFO'``, ``'WARNING'``, ``'ERROR'``,
    ``'CRITICAL'``, or ``None``. ``'DEBUG'`` is the least restrictive level and
    will show the most log messages. ``'CRITICAL'`` is the most restrictive
    level and will only display information about fatal errors. If set to
    ``None``, logging to standard output will be disabled entirely.""")

    LOG_CONFIG_ON_IMPORT = Option(True, description="""
    Controls whether the configuration is printed when PyPhi is imported.

      .. tip::

        If this is enabled and ``LOG_FILE_LEVEL`` is ``INFO`` or higher, then
        the log file can serve as an automatic record of which configuration
        settings you used to obtain results.""")

    PROGRESS_BARS = Option(True, description="""
    Controls whether to show progress bars on the console.

      .. tip::
        If you are iterating over many systems rather than doing one long-running
        calculation, consider disabling this for speed.""")

    PRECISION = Option(6, description="""
    If ``MEASURE`` is ``EMD``, then the Earth Mover's Distance is calculated
    with an external C++ library that a numerical optimizer to find a good
    approximation. Consequently, systems with analytically zero |big_phi| will
    sometimes be numerically found to have a small but non-zero amount. This
    setting controls the number of decimal places to which PyPhi will consider
    EMD calculations accurate. Values of |big_phi| lower than ``10e-PRECISION``
    will be considered insignificant and treated as zero. The default value is
    about as accurate as the EMD computations get.""")

    VALIDATE_SUBSYSTEM_STATES = Option(True, description="""
    Controls whether PyPhi checks if the subsystems's state is possible
    (reachable with nonzero probability from some past state), given the
    subsystem's TPM (**which is conditioned on background conditions**). If
    this is turned off, then **calculated** |big_phi| **values may not be
    valid**, since they may be associated with a subsystem that could never be
    in the given state.""")

    VALIDATE_CONDITIONAL_INDEPENDENCE = Option(True, description="""
    Controls whether PyPhi checks if a system's TPM is conditionally
    independent.""")

    SINGLE_MICRO_NODES_WITH_SELFLOOPS_HAVE_PHI = Option(False, description="""
    If set to ``True``, the Phi value of single micro-node subsystems is the
    difference between their unpartitioned constellation (a single concept) and
    the null concept. If set to False, their Phi is defined to be zero. Single
    macro-node subsystems may always be cut, regardless of circumstances.""")

    REPR_VERBOSITY = Option(2, values=[0, 1, 2], description="""
    Controls the verbosity of ``__repr__`` methods on PyPhi objects. Can be set
    to ``0``, ``1``, or ``2``. If set to ``1``, calling ``repr`` on PyPhi
    objects will return pretty-formatted and legible strings, excluding
    repertoires. If set to ``2``, ``repr`` calls also include repertoires.

    Although this breaks the convention that ``__repr__`` methods should return
    a representation which can reconstruct the object, readable representations
    are convenient since the Python REPL calls ``repr`` to represent all
    objects in the shell and PyPhi is often used interactively with the
    REPL. If set to ``0``, ``repr`` returns more traditional object
    representations.""")

    PRINT_FRACTIONS = Option(True, description="""
    Controls whether numbers in a ``repr`` are printed as fractions. Numbers
    are still printed as decimals if the fraction's denominator would be
    large. This only has an effect if ``REPR_VERBOSITY > 0``.""")

    PARTITION_TYPE = Option('BI', values=['BI', 'TRI', 'ALL'], description="""
    Controls the type of partition used for |small_phi| computations.

    If set to ``'BI'``, partitions will have two parts.

    If set to ``'TRI'``, partitions will have three parts. In addition,
    computations will only consider partitions that strictly partition the
    mechanism the mechanism. That is, for the mechanism ``(A, B)`` and purview
    ``(B, C, D)`` the partition::

      A,B     ∅
      ─── ✕ ───
       B     C,D

    is not considered, but::

       A      B
      ─── ✕ ───
       B     C,D

    is. The following is also valid::

      A,B      ∅
      ─── ✕ ─────
       ∅     B,C,D

    In addition, this setting introduces "wedge" tripartitions of the form::

       A      B     ∅
      ─── ✕ ─── ✕ ───
       B      C     D

    where the mechanism in the third part is always empty.

    In addition, in the case of a |small_phi|-tie when computing MICE, The
    ``'TRIPARTITION'`` setting choses the MIP with smallest purview instead of
    the largest (which is the default).

    Finally, if set to ``'ALL'``, all possible partitions will be tested.""")

    PICK_SMALLEST_PURVIEW = Option(False, description="""
    When computing MICE, it is possible for several MIPs to have the same
    |small_phi| value. If this setting is set to ``True`` the MIP with the
    smallest purview is chosen; otherwise, the one with largest purview is
    chosen.""")

    USE_SMALL_PHI_DIFFERENCE_FOR_CONSTELLATION_DISTANCE = Option(False, description="""
    If set to ``True``, the distance between constellations
    (when computing a |BigMip|) is calculated using the difference between the
    sum of |small_phi| in the constellations instead of the extended EMD.""")

    SYSTEM_CUTS = Option('3.0_STYLE', values=['3.0_STYLE', 'CONCEPT_STYLE'], description="""
    If set to ``'3.0_STYLE'``, then traditional IIT 3.0 cuts will be used when
    computing |big_phi|. If set to ``'CONCEPT_STYLE'``, then experimental
    concept- style system cuts will be used instead.""")


def print_config():
    '''Print the current configuration.'''
    print('Current PyPhi configuration:\n', str(config))


PYPHI_CONFIG_FILENAME = 'pyphi_config.yml'

config = PyphiConfig()


def initialize():
    '''Initialize PyPhi config.'''
    # Try and load the config file
    file_loaded = False
    if os.path.exists(PYPHI_CONFIG_FILENAME):
        config.load_config_file(PYPHI_CONFIG_FILENAME)
        file_loaded = True

    # Setup logging
    configure_logging(config)

    # Log the PyPhi version and loaded configuration
    if config.LOG_CONFIG_ON_IMPORT:
        log = logging.getLogger(__name__)

        log.info('PyPhi v%s', __about__.__version__)
        if file_loaded:
            log.info('Loaded configuration from '
                     '`./%s`', PYPHI_CONFIG_FILENAME)
        else:
            log.info('Using default configuration (no config file provided)')

        log.info('Current PyPhi configuration:\n %s', str(config))


initialize()
