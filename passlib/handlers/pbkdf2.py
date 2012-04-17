"""passlib.handlers.pbkdf - PBKDF2 based hashes"""
#=========================================================
#imports
#=========================================================
#core
from binascii import hexlify, unhexlify
from base64 import b64encode, b64decode
import re
import logging; log = logging.getLogger(__name__)
from warnings import warn
#site
#libs
from passlib.utils import ab64_decode, ab64_encode, to_unicode
from passlib.utils.compat import b, bytes, str_to_bascii, u, uascii_to_str, unicode
from passlib.utils.pbkdf2 import pbkdf2
import passlib.utils.handlers as uh
#pkg
#local
__all__ = [
    "pbkdf2_sha1",
    "pbkdf2_sha256",
    "pbkdf2_sha512",
    "cta_pbkdf2_sha1",
    "dlitz_pbkdf2_sha1",
    "grub_pbkdf2_sha512",
]

#=========================================================
#
#=========================================================
class Pbkdf2DigestHandler(uh.HasRounds, uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    "base class for various pbkdf2_{digest} algorithms"
    #=========================================================
    #class attrs
    #=========================================================

    #--GenericHandler--
    setting_kwds = ("salt", "salt_size", "rounds")
    checksum_chars = uh.HASH64_CHARS

    #--HasSalt--
    default_salt_size = 16
    min_salt_size = 0
    max_salt_size = 1024

    #--HasRounds--
    default_rounds = 6400
    min_rounds = 1
    max_rounds = 2**32-1
    rounds_cost = "linear"

    #--this class--
    _prf = None #subclass specified prf identifier

    #NOTE: max_salt_size and max_rounds are arbitrarily chosen to provide sanity check.
    #      the underlying pbkdf2 specifies no bounds for either.

    #NOTE: defaults chosen to be at least as large as pbkdf2 rfc recommends...
    #      >8 bytes of entropy in salt, >1000 rounds
    #      increased due to time since rfc established

    #=========================================================
    #methods
    #=========================================================

    @classmethod
    def from_string(cls, hash):
        rounds, salt, chk = uh.parse_mc3(hash, cls.ident, handler=cls)
        salt = ab64_decode(salt.encode("ascii"))
        if chk:
            chk = ab64_decode(chk.encode("ascii"))
        return cls(rounds=rounds, salt=salt, checksum=chk)

    def to_string(self, withchk=True):
        salt = ab64_encode(self.salt).decode("ascii")
        if withchk and self.checksum:
            chk = ab64_encode(self.checksum).decode("ascii")
        else:
            chk = None
        return uh.render_mc3(self.ident, self.rounds, salt, chk)

    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        return pbkdf2(secret, self.salt, self.rounds, self.checksum_size, self._prf)

def create_pbkdf2_hash(hash_name, digest_size, ident=None):
    "create new Pbkdf2DigestHandler subclass for a specific hash"
    name = 'pbkdf2_' + hash_name
    if ident is None:
        ident = u("$pbkdf2-%s$") % (hash_name,)
    prf = "hmac-%s" % (hash_name,)
    base = Pbkdf2DigestHandler
    return type(name, (base,), dict(
        name=name,
        description="PBKDF2-based hash defined by Passlib, uses HMAC-" + hash_name.upper(),
        ident=ident,
        _prf = prf,
        checksum_size=digest_size,
        encoded_checksum_size=(digest_size*4+2)//3,
        __doc__="""This class implements a generic ``PBKDF2-%(prf)s``-based password hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keywords:

    :param salt:
        Optional salt bytes.
        If specified, the length must be between 0-1024 bytes.
        If not specified, a %(dsc)d byte salt will be autogenerated (this is recommended).

    :param salt_size:
        Optional number of bytes to use when autogenerating new salts.
        Defaults to 16 bytes, but can be any value between 0 and 1024.

    :param rounds:
        Optional number of rounds to use.
        Defaults to %(dr)d, but must be within ``range(1,1<<32)``.
    """ % dict(prf=prf.upper(), dsc=base.default_salt_size, dr=base.default_rounds)
    ))

#---------------------------------------------------------
#derived handlers
#---------------------------------------------------------
pbkdf2_sha1 = create_pbkdf2_hash("sha1", 20, ident=u("$pbkdf2$"))
pbkdf2_sha256 = create_pbkdf2_hash("sha256", 32)
pbkdf2_sha512 = create_pbkdf2_hash("sha512", 64)

ldap_pbkdf2_sha1 = uh.PrefixWrapper("ldap_pbkdf2_sha1", pbkdf2_sha1, "{PBKDF2}", "$pbkdf2$",
                                    description="LDAP-style variant of passlib's pbkdf2_sha1")
ldap_pbkdf2_sha256 = uh.PrefixWrapper("ldap_pbkdf2_sha256", pbkdf2_sha256, "{PBKDF2-SHA256}", "$pbkdf2-sha256$",
                                    description="LDAP-style variant of passlib's pbkdf2_sha256")
ldap_pbkdf2_sha512 = uh.PrefixWrapper("ldap_pbkdf2_sha512", pbkdf2_sha512, "{PBKDF2-SHA512}", "$pbkdf2-sha512$",
                                    description="LDAP-style variant of passlib's pbkdf2_sha512")

#=========================================================
#cryptacular's pbkdf2 hash
#=========================================================

#: bytes used by cta hash for base64 values 63 & 64
CTA_ALTCHARS = b("-_")

class cta_pbkdf2_sha1(uh.HasRounds, uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    """This class implements Cryptacular's PBKDF2-based crypt algorithm, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keywords:

    :param salt:
        Optional salt bytes.
        If specified, it may be any length.
        If not specified, a one will be autogenerated (this is recommended).

    :param salt_size:
        Optional number of bytes to use when autogenerating new salts.
        Defaults to 16 bytes, but can be any value between 0 and 1024.

    :param rounds:
        Optional number of rounds to use.
        Defaults to 10000, must be within ``range(1,1<<32)``.
    """

    #=========================================================
    #class attrs
    #=========================================================
    #--GenericHandler--
    name = "cta_pbkdf2_sha1"
    description = "PBKDF2-HMAC-SHA1 hash used by the python library Cryptacular"
    setting_kwds = ("salt", "salt_size", "rounds")
    ident = u("$p5k2$")

    #NOTE: max_salt_size and max_rounds are arbitrarily chosen to provide sanity check.
    #   underlying algorithm (and reference implementation) allow effectively unbounded values for both of these.

    #--HasSalt--
    default_salt_size = 16
    min_salt_size = 0
    max_salt_size = 1024

    #--HasROunds--
    default_rounds = 10000
    min_rounds = 1
    max_rounds = 2**32-1
    rounds_cost = "linear"

    #=========================================================
    #formatting
    #=========================================================

    #hash       $p5k2$1000$ZxK4ZBJCfQg=$jJZVscWtO--p1-xIZl6jhO2LKR0=
    #ident      $p5k2$
    #rounds     1000
    #salt       ZxK4ZBJCfQg=
    #chk        jJZVscWtO--p1-xIZl6jhO2LKR0=
    #NOTE: rounds in hex

    @classmethod
    def from_string(cls, hash):
        # NOTE: passlib deviation - forbidding zero-padded rounds
        rounds, salt, chk = uh.parse_mc3(hash, cls.ident, rounds_base=16, handler=cls)
        salt = b64decode(salt.encode("ascii"), CTA_ALTCHARS)
        if chk:
            chk = b64decode(chk.encode("ascii"), CTA_ALTCHARS)
        return cls(rounds=rounds, salt=salt, checksum=chk)

    def to_string(self, withchk=True):
        salt = b64encode(self.salt, CTA_ALTCHARS).decode("ascii")
        if withchk and self.checksum:
            chk = b64encode(self.checksum, CTA_ALTCHARS).decode("ascii")
        else:
            chk = None
        return uh.render_mc3(self.ident, self.rounds, salt, chk, rounds_base=16)

    #=========================================================
    #backend
    #=========================================================
    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        return pbkdf2(secret, self.salt, self.rounds, 20, "hmac-sha1")

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#dlitz's pbkdf2 hash
#=========================================================
class dlitz_pbkdf2_sha1(uh.HasRounds, uh.HasSalt, uh.GenericHandler):
    """This class implements Dwayne Litzenberger's PBKDF2-based crypt algorithm, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keywords:

    :param salt:
        Optional salt string.
        If specified, it may be any length, but must use the characters in the regexp range ``[./0-9A-Za-z]``.
        If not specified, a 16 character salt will be autogenerated (this is recommended).

    :param salt_size:
        Optional number of bytes to use when autogenerating new salts.
        Defaults to 16 bytes, but can be any value between 0 and 1024.

    :param rounds:
        Optional number of rounds to use.
        Defaults to 10000, must be within ``range(1,1<<32)``.
    """

    #=========================================================
    #class attrs
    #=========================================================
    #--GenericHandler--
    name = "dlitz_pbkdf2_sha1"
    description = "PBKDF2-HMAC-SHA1 hash released by the author of PyCrypto"
    setting_kwds = ("salt", "salt_size", "rounds")
    ident = u("$p5k2$")

    #NOTE: max_salt_size and max_rounds are arbitrarily chosen to provide sanity check.
    #   underlying algorithm (and reference implementation) allow effectively unbounded values for both of these.

    #--HasSalt--
    default_salt_size = 16
    min_salt_size = 0
    max_salt_size = 1024
    salt_chars = uh.HASH64_CHARS

    #--HasROunds--
    default_rounds = 10000
    min_rounds = 1
    max_rounds = 2**32-1
    rounds_cost = "linear"

    #=========================================================
    #formatting
    #=========================================================

    #hash       $p5k2$c$u9HvcT4d$Sd1gwSVCLZYAuqZ25piRnbBEoAesaa/g
    #ident      $p5k2$
    #rounds     c
    #salt       u9HvcT4d
    #chk        Sd1gwSVCLZYAuqZ25piRnbBEoAesaa/g
    #rounds in lowercase hex, no zero padding

    @classmethod
    def from_string(cls, hash):
        rounds, salt, chk = uh.parse_mc3(hash, cls.ident, rounds_base=16,
                                         default_rounds=400, handler=cls)
        return cls(rounds=rounds, salt=salt, checksum=chk)

    def to_string(self, withchk=True):
        rounds = self.rounds
        if rounds == 400:
            rounds = None # omit rounds measurement if == 400
        return uh.render_mc3(self.ident, rounds, self.salt,
                             checksum=self.checksum if withchk else None,
                             rounds_base=16)

    #=========================================================
    #backend
    #=========================================================
    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        salt = str_to_bascii(self.to_string(withchk=False))
        result = pbkdf2(secret, salt, self.rounds, 24, "hmac-sha1")
        return ab64_encode(result).decode("ascii")

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#crowd
#=========================================================
class atlassian_pbkdf2_sha1(uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    """This class implements the PBKDF2 hash used by Atlassian.

    It supports a fixed-length salt, and a fixed number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keyword:

    :param salt:
        Optional salt bytes.
        If specified, the length must be exactly 16 bytes.
        If not specified, a salt will be autogenerated (this is recommended).
    """
    #--GenericHandler--
    name = "atlassian_pbkdf2_sha1"
    description = "fixed-round PBKDF1-HMAC-SHA1 hash used by various Atlassian products"
    setting_kwds =("salt",)
    ident = u("{PKCS5S2}")
    checksum_size = 32

    _stub_checksum = b("\x00") * 32

    #--HasRawSalt--
    min_salt_size = max_salt_size = 16

    @classmethod
    def from_string(cls, hash):
        hash = to_unicode(hash, "ascii", "hash")
        ident = cls.ident
        if not hash.startswith(ident):
            raise uh.exc.InvalidHashError(cls)
        data = b64decode(hash[len(ident):].encode("ascii"))
        salt, chk = data[:16], data[16:]
        return cls(salt=salt, checksum=chk)

    def to_string(self):
        data = self.salt + (self.checksum or self._stub_checksum)
        hash = self.ident + b64encode(data).decode("ascii")
        return uascii_to_str(hash)

    def _calc_checksum(self, secret):
        #TODO: find out what crowd's policy is re: unicode
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        #crowd seems to use a fixed number of rounds.
        return pbkdf2(secret, self.salt, 10000, 32, "hmac-sha1")

#=========================================================
#grub
#=========================================================
class grub_pbkdf2_sha512(uh.HasRounds, uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    """This class implements Grub's pbkdf2-hmac-sha512 hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keywords:

    :param salt:
        Optional salt bytes.
        If specified, the length must be between 0-1024 bytes.
        If not specified, a 64 byte salt will be autogenerated (this is recommended).

    :param salt_size:
        Optional number of bytes to use when autogenerating new salts.
        Defaults to 64 bytes, but can be any value between 0 and 1024.

    :param rounds:
        Optional number of rounds to use.
        Defaults to 10000, but must be within ``range(1,1<<32)``.
    """
    name = "grub_pbkdf2_sha512"
    description = "PBKDF2-HMAC-SHA512 hash used by the GRUB bootloader"
    setting_kwds = ("salt", "salt_size", "rounds")

    ident = u("grub.pbkdf2.sha512.")

    #NOTE: max_salt_size and max_rounds are arbitrarily chosen to provide sanity check.
    #      the underlying pbkdf2 specifies no bounds for either,
    #      and it's not clear what grub specifies.

    default_salt_size = 64
    min_salt_size = 0
    max_salt_size = 1024

    default_rounds = 10000
    min_rounds = 1
    max_rounds = 2**32-1
    rounds_cost = "linear"

    @classmethod
    def from_string(cls, hash):
        rounds, salt, chk = uh.parse_mc3(hash, cls.ident, sep=u("."),
                                         handler=cls)
        salt = unhexlify(salt.encode("ascii"))
        if chk:
            chk = unhexlify(chk.encode("ascii"))
        return cls(rounds=rounds, salt=salt, checksum=chk)

    def to_string(self, withchk=True):
        salt = hexlify(self.salt).decode("ascii").upper()
        if withchk and self.checksum:
            chk = hexlify(self.checksum).decode("ascii").upper()
        else:
            chk = None
        return uh.render_mc3(self.ident, self.rounds, salt, chk, sep=u("."))

    def _calc_checksum(self, secret):
        #TODO: find out what grub's policy is re: unicode
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        return pbkdf2(secret, self.salt, self.rounds, 64, "hmac-sha512")

#=========================================================
#eof
#=========================================================
