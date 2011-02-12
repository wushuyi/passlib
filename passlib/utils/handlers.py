"""passlib.handler - code for implementing handlers, and global registry for handlers"""
#=========================================================
#imports
#=========================================================
from __future__ import with_statement
#core
import inspect
import re
import hashlib
import logging; log = logging.getLogger(__name__)
import time
import os
#site
#libs
from passlib.utils import abstractmethod, abstractclassmethod, classproperty, h64, \
    getrandstr, rng, Undef, is_crypt_handler
#pkg
#local
__all__ = [

    #framework for implementing handlers
    'CryptHandler',
    'ExtCryptHandler',
]

#==========================================================
#base interface for all the crypt algorithm implementations
#==========================================================
class CryptHandler(object):
    """helper class for implementing a password algorithm using class methods"""

    #=========================================================
    #class attrs
    #=========================================================

    name = None #globally unique name to identify algorithm. should be lower case and hyphens only
    context_kwds = () #tuple of additional kwds required for any encrypt / verify operations; eg "realm" or "user"
    setting_kwds = () #tuple of additional kwds that encrypt accepts for configuration algorithm; eg "salt" or "rounds"

    #=========================================================
    #primary interface - primary methods implemented by each handler
    #=========================================================

    @abstractclassmethod
    def genhash(cls, secret, config, **context):
        """encrypt secret to hash"""

    @classmethod
    def genconfig(cls, **settings):
        """return configuration string encoding settings for hash generation"""
        #NOTE: this implements a default method which is suitable ONLY for classes with no configuration.
        if cls.setting_kwds:
            raise NotImplementedError, "classes with config kwds must implement genconfig()"
        if settings:
            raise TypeError, "%s has no configuration options" % (cls,)
        return None

    #=========================================================
    #secondary interface - more useful interface for user,
    # frequently implemented more efficiently by specific handlers
    #=========================================================

    @classmethod
    def identify(cls, hash):
        """identify if a hash string belongs to this algorithm."""
        #NOTE: this default method is going to be *really* slow for most implementations,
        #they should override it. but if genhash() conforms to the specification, this will do.
        if cls.context_kwds:
            raise NotImplementedError, "classes with context kwds must implement identify()"
        if not hash:
            return False
        try:
            cls.genhash("stub", hash)
        except ValueError:
            return False
        return True

    @classmethod
    def encrypt(cls, secret, **kwds):
        """encrypt secret, returning resulting hash string."""
        if cls.context_kwds:
            context = dict(
                (k,kwds.pop(k))
                for k in cls.context_kwds
                if k in kwds
            )
            config = cls.genconfig(**kwds)
            return cls.genhash(secret, config, **context)
        else:
            config = cls.genconfig(**kwds)
            return cls.genhash(secret, config)

    @classmethod
    def verify(cls, secret, hash, **context):
        """verify a secret against an existing hash."""
        #NOTE: methods whose hashes have multiple encodings should override this,
        # as the hash will need to be normalized before comparing via string equality.
        # alternately, the ExtCryptHandler class provides a more flexible framework.

        #ensure hash was specified - genhash() won't throw error for this
        if not hash:
            raise ValueError, "no hash specified"

        #the genhash() implementation for most setting-less algorithms
        #simply ignores the config string provided; whereas most
        #algorithms with settings have to inspect and validate it.
        #therefore, we do this quick check IFF it's setting-less
        if not cls.setting_kwds and not cls.identify(hash):
            raise ValueError, "not a %s hash" % (cls.name,)

        #do simple string comparison
        return hash == cls.genhash(secret, hash, **context)

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#
#=========================================================
##class ExtCryptHandler(CryptHandler):
##    """class providing an extended handler interface,
##    allowing manipulation of hash & config strings.
##
##    this extended interface adds methods for parsing and rendering
##    a hash or config string to / from a dictionary of components.
##
##    this interface is generally easier to use when *implementing* hash
##    algorithms, and as such is used through passlib. it's kept separate
##    from :class:`CryptHandler` itself, since it's features are not typically
##    required for user-facing purposes.
##
##    when implementing a hash algorithm, subclasses must implement:
##
##        * parse()
##        * render()
##        * genconfig() - render, _norm_salt, _norm_rounds usually helpful for this
##        * genhash() - parse, render usually helpful for this
##
##    subclasses may optionally implement more efficient versions of
##    these functions, though the defaults should be sufficient:
##
##        * identify() - requires parse()
##        * verify() - requires parse()
##
##    some helper methods are provided for implementing genconfig, genhash & verify.
##    """
##
##    #=========================================================
##    #class attrs
##    #=========================================================
##
##    #---------------------------------------------------------
##    # _norm_salt() configuration
##    #---------------------------------------------------------
##
##    salt_chars = None #fill in with (maxium) number of salt chars required, and _norm_salt() will handle truncating etc
##    salt_charset = h64.CHARS #helper used when generating salt
##    salt_charpat = None #optional regexp used by _norm_salt to validate salts
##
##    #override only if minimum number of salt chars is different from salt_chars
##    @classproperty
##    def min_salt_chars(cls):
##        return cls.salt_chars
##
##    #---------------------------------------------------------
##    #_norm_rounds() configuration
##    #---------------------------------------------------------
##    default_rounds = None #default number of rounds to use if none specified (can be name of a preset)
##    min_rounds = None #minimum number of rounds (smaller values silently ignored)
##    max_rounds = None #maximum number of rounds (larger values silently ignored)
##
##    #=========================================================
##    #backend parsing routines - used by helpers below
##    #=========================================================
##
##    @abstractclassmethod
##    def parse(cls, hash):
##        """parse hash or config into dictionary.
##
##        :arg hash: the hash/config string to parse
##
##        :raises ValueError:
##            If hash/config string is empty,
##            or not recognized as belonging to this algorithm
##
##        :returns:
##            dictionary containing a subset of the keys
##            specified in :attr:`setting_kwds`.
##
##            commonly used keys are ``salt``, ``rounds``.
##
##            If and only if the string is a hash, the dict should also contain
##            the key ``checksum``, mapping to the checksum portion of the hash.
##
##        .. note::
##            Specific implementations may perform anywhere from none to full
##            validation of input string; the primary goal of this method
##            is to parse settings from single string into kwds
##            which will be recognized by :meth:`render` and :meth:`encrypt`.
##
##            :meth:`encrypt` is where validation of inputs *must* be performed.
##
##        .. note::
##            If multiple encoding formats are possible, this *must* normalize
##            the checksum kwd to it's canonical format, so the default
##            verify() method can work properly.
##        """
##
##    @abstractclassmethod
##    def render(cls, checksum=None, **settings):
##        """render hash from checksum & settings (as returned by :meth:`parse`).
##
##        :param checksum:
##            Encoded checksum portion of hash.
##
##        :param settings:
##            All other keywords are algorithm-specified,
##            and should be listed in :attr:`setting_kwds`.
##
##        :raises ValueError:
##            If any values are not encodeable into hash.
##
##        :raises NotImplementedError:
##            If checksum is omitted and the algorithm
##            doesn't have any settings (:attr:`setting_kwds` is empty),
##            or doesn't support generating "salt strings"
##            which contain all configuration except for the
##            checksum itself.
##
##        :returns:
##            if checksum is specified, this should return a fully-formed hash.
##            otherwise, it should return a config string containing
##            the specified inputs.
##
##        .. note::
##            Specific implementations may perform anywhere from none to full
##            validation of inputs; the primary goal of this method
##            is to render the settings into a single string
##            which will be recognized by :meth:`parse`.
##
##            :meth:`encrypt` is where validation of inputs *must* be performed.
##        """
##
##    #=========================================================
##    #genhash helper functions
##    #=========================================================
##
##    #NOTE: genhash() must be implemented,
##    # but helper functions are provided below for common workflows...
##
##    #----------------------------------------------------------------
##    #for handlers which normalize config string and hand off to external library
##    #----------------------------------------------------------------
##    @classmethod
##    def _norm_config(cls, config):
##        """normalize & validate config string"""
##        assert cls.setting_kwds, "_norm_config not designed for hashses w/o settings"
##        if not config:
##            raise ValueError, "no %s hash or config string specified" % (cls.name,)
##        settings = cls.parse(config) #this should catch malformed entries
##        settings.pop("checksum", None) #remove checksum if a hash was passed in
##        return cls.genconfig(**settings) #re-generate config string, let genconfig() catch invalid values
##
##    #----------------------------------------------------------------
##    #for handlers which implement the guts of the process directly
##    #----------------------------------------------------------------
##
##    # render() is also usually used for implementing genhash() in this case
##
##    @classmethod
##    def _parse_norm_config(cls, config):
##        """normalize & validate config string, return parsed dictionary"""
##        return cls.parse(cls._norm_config(config))
##
##    #=========================================================
##    #genconfig helpers
##    #=========================================================
##
##    #NOTE: genconfig() must still be implemented,
##    # but helper functions provided below
##
##    #render() is usually used for implementing genconfig()
##
##    @classmethod
##    def _norm_rounds(cls, rounds):
##        return norm_rounds(rounds, cls.default_rounds, cls.min_rounds, cls.max_rounds, name=cls.name)
##
##    @classmethod
##    def _norm_salt(cls, salt):
##        return norm_salt(salt, cls.min_salt_chars, cls.salt_chars, cls.salt_charset, name=cls.name)
##
##    #=========================================================
##    #identify helpers
##    #=========================================================
##
##    #NOTE: this default identify implementation is usually sufficient
##    # (and better than CryptHandler.identify),
##    # though implementations may override it with an even faster check,
##    # such as just looking for a specific string prefix & size
##
##    @classmethod
##    def identify(cls, hash):
##        try:
##            cls.parse(hash)
##        except ValueError:
##            return False
##        return True
##
##    #=========================================================
##    #encrypt helper functions
##    #=========================================================
##
##    #NOTE: the default encrypt() method very rarely needs overidding at all.
##
##    #=========================================================
##    #verify helper functions
##    #=========================================================
##
##    #NOTE: the default verify method provided here works for most cases,
##    # though some handlers will want to implement norm_hash() if their
##    # hash has multiple equivalent representations (eg: case insensitive)
##
##    @classmethod
##    def verify(cls, secret, hash, **context_kwds):
##        info = cls.parse(hash) #<- should throw ValueError for us if hash is invalid
##        if not info.get('checksum'):
##          raise ValueError, "hash lacks checksum (did you pass a config string into verify?)"
##        other_hash = cls.genhash(secret, hash, **context_kwds)
##        other_info = cls.parse(other_hash)
##        return info['checksum'] == other_info['checksum']
##
##    #=========================================================
##    #eoc
##    #=========================================================

#=========================================================
#
#=========================================================
class BaseSRHandler(object):
    """helper class for implementing hash schemes which have both salt and rounds"""

    #=========================================================
    #password hash api - required attributes
    #=========================================================
    name = None #required
    setting_kwds = ("salt", "rounds")
    context_kwds = ()

    #=========================================================
    #password hash api - optional salt attributes
    #=========================================================
    max_salt_chars = None #required

    @classproperty
    def min_salt_chars(cls):
        "min salt chars (defaults to max_salt_chars if not specified by subclass)"
        return cls.max_salt_chars

    @classproperty
    def default_salt_chars(cls):
        "default salt chars (defaults to max_salt_chars if not specified by subclass)"
        return cls.max_salt_chars

    salt_chars = h64.CHARS

    @classproperty
    def default_salt_charset(cls):
        return cls.salt_chars

    #=========================================================
    #password hash api - optional rounds attributes
    #=========================================================
    min_rounds = 0
    max_rounds = None #required
    default_rounds = None #required
    rounds_cost = "linear" #common case

    strict_rounds_bounds = False #if true, always raises error if specified rounds values out of range - required by spec for some hashes

    #=========================================================
    #other class attrs
    #=========================================================
    #TODO: could implement norm_checksum()
    ##checksum_size = None #required - checksum size
    ##checksum_charset = None #required - checksum charset

    #=========================================================
    #handler helpers
    #=========================================================
    @classmethod
    def validate_class(cls):
        "helper to ensure class is configured property"
        if not cls.name:
            raise ValueError, "no name specified"

        if 'rounds' not in cls.setting_kwds:
            raise ValueError, "rounds not in setting_kwds"

        if cls.max_rounds is None:
            raise ValueError, "max rounds not specified"

        if cls.min_rounds > cls.max_rounds:
            raise ValueError, "min rounds too large"

        if cls.default_rounds is None:
            raise ValueError, "default rounds not specified"
        if cls.default_rounds < cls.min_rounds:
            raise ValueError, "default rounds too small"
        if cls.default_rounds > cls.max_rounds:
            raise ValueError, "default rounds too large"

        if cls.rounds_cost not in ("linear", "log2"):
            raise ValueError, "unknown rounds cost function"

        if 'salt' not in cls.setting_kwds:
            raise ValueError, "salt not in setting_kwds"

        if cls.min_salt_chars > cls.max_salt_chars:
            raise ValueError, "min salt chars too large"

        if cls.default_salt_chars < cls.min_salt_chars:
            raise ValueError, "default salt chars too small"
        if cls.default_salt_chars > cls.max_salt_chars:
            raise ValueError, "default salt chars too large"

        if any(c not in cls.salt_charset for c in cls.default_salt_charset):
            raise ValueError, "default salt charset not subset of salt charset"

    #=========================================================
    #instance attributes
    #=========================================================
    checksum = None
    salt = None
    rounds = None

    #=========================================================
    #init
    #=========================================================
    def __init__(self, checksum=None, salt=None, rounds=None, strict=False):
        self.checksum = checksum
        self.salt = self.norm_salt(salt, strict=strict)
        self.rounds = self.norm_rounds(rounds, strict=strict)

    #=========================================================
    #helpers
    #=========================================================
    @classmethod
    def norm_salt(cls, salt, strict=False):
        "helper to normalize salt string; strict flag causes error even for correctable errors"
        if salt is None:
            if strict:
                raise ValueError, "no salt specified"
            return getrandstr(rng, cls.default_salt_charset, cls.default_salt_chars)

        mn = cls.min_salt_chars
        if mn and len(salt) < mn:
            raise ValueError, "%s salt string must be >= %d characters" % (cls.name, mn)

        mx = cls.max_salt_chars
        if len(salt) > mx:
            if strict:
                raise ValueError, "%s salt string must be <= %d characters" % (cls.name, mx)
            salt = salt[:mx]

        return salt

    @classmethod
    def norm_rounds(cls, rounds, strict=False):
        "helper to normalize rounds value; strict flag causes error even for correctable errors"
        if rounds is None:
            if strict:
                raise ValueError, "no rounds specified"
            return cls.default_rounds

        if cls.strict_rounds_bounds:
            strict = True

        mn = cls.min_rounds
        if rounds < mn:
            if strict:
                raise ValueError, "%s rounds must be >= %d" % (cls.name, mn)
            rounds = mn

        mx = cls.max_rounds
        if rounds > mx:
            if strict:
                raise ValueError, "%s rounds must be <= %d" % (cls.name, mx)
            rounds = mx

        return rounds

    #=========================================================
    #password hash api - primary interface (default implementation)
    #=========================================================
    @classmethod
    def genconfig(cls, **settings):
        return cls(**settings).to_string()

    @classmethod
    def genhash(cls, secret, config):
        if cls.calc_checksum:
            self = cls.from_string(config)
            self.checksum = self.calc_checksum(secret)
            return self.to_string()
        else:
            raise NotImplementedError, "%s subclass must implemented genhash OR calc_checksum" % (cls.name,)

    calc_checksum = None #subclasses may alternately implement this instead of genhash

    #=========================================================
    #password hash api - secondary interface (default implementation)
    #=========================================================
    @classmethod
    def identify(cls, hash):
        #NOTE: subclasses may wish to use faster / simpler identify,
        # and raise value errors only when an invalid (but identifiable) string is parsed
        if not hash:
            return False
        try:
            cls.from_string(hash)
            return True
        except ValueError:
            return False

    @classmethod
    def encrypt(cls, secret, **settings):
        self = cls(**settings)
        if self.calc_checksum:
            #save ourselves some parsing calls if subclass provides this method
            self.checksum = self.calc_checksum(secret)
            return self.to_string()
        else:
            return cls.genhash(secret, self.to_string())

    @classmethod
    def verify(cls, secret, hash):
        #NOTE: classes may wish to override this
        if cls.calc_checksum:
            #save ourselves some parsing calls if subclass provides this method
            self = cls.from_string(hash)
            return self.checksum == self.calc_checksum(secret)
        else:
            return hash == cls.genhash(secret, hash)

    #=========================================================
    #password hash api - parsing interface
    #=========================================================
    @abstractclassmethod
    def from_string(cls, hash):
        "return parsed instance from hash/configuration string; raising ValueError on invalid inputs"
        #MUST BE IMPLEMENTED BY SUBCLASS
        pass

    @abstractmethod
    def to_string(self):
        "render instance to hash or configuration string (depending on if checksum attr is set)"
        #MUST BE IMPLEMENTED BY SUBCLASS
        pass

    #=========================================================
    #
    #=========================================================

#=========================================================
# eof
#=========================================================