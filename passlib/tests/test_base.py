"""tests for passlib.pwhash -- (c) Assurance Technologies 2003-2009"""
#=========================================================
#imports
#=========================================================
from __future__ import with_statement
#core
import hashlib
from logging import getLogger
#site
#pkg
from passlib import hash
from passlib.base import CryptContext, CryptPolicy
from passlib.tests.utils import TestCase, mktemp
from passlib.drivers.md5_crypt import md5_crypt as AnotherHash
from passlib.tests.test_utils_drivers import UnsaltedHash, SaltedHash
#module
log = getLogger(__name__)

#=========================================================
#
#=========================================================
class CryptPolicyTest(TestCase):
    "test CryptPolicy object"

    #TODO: need to test user categories w/in all this

    case_prefix = "CryptPolicy"

    #=========================================================
    #sample crypt policies used for testing
    #=========================================================

    #-----------------------------------------------------
    #sample 1 - average config file
    #-----------------------------------------------------
    sample_config_1s = """\
[passlib]
schemes = des_crypt, md5_crypt, bsdi_crypt, sha512_crypt
default = md5_crypt
all.vary_rounds = 10%
bsdi_crypt.max_rounds = 30000
bsdi_crypt.default_rounds = 25000
sha512_crypt.max_rounds = 50000
sha512_crypt.min_rounds = 40000
"""

    sample_config_1pd = dict(
        schemes = [ "des_crypt", "md5_crypt", "bsdi_crypt", "sha512_crypt"],
        default = "md5_crypt",
        all__vary_rounds = "10%",
        bsdi_crypt__max_rounds = 30000,
        bsdi_crypt__default_rounds = 25000,
        sha512_crypt__max_rounds = 50000,
        sha512_crypt__min_rounds = 40000,
    )

    sample_config_1pid = {
        "schemes": "des_crypt, md5_crypt, bsdi_crypt, sha512_crypt",
        "default": "md5_crypt",
        "all.vary_rounds": "10%",
        "bsdi_crypt.max_rounds": 30000,
        "bsdi_crypt.default_rounds": 25000,
        "sha512_crypt.max_rounds": 50000,
        "sha512_crypt.min_rounds": 40000,
    }

    sample_config_1prd = dict(
        schemes = [ hash.des_crypt, hash.md5_crypt, hash.bsdi_crypt, hash.sha512_crypt],
        default = hash.md5_crypt,
        all__vary_rounds = "10%",
        bsdi_crypt__max_rounds = 30000,
        bsdi_crypt__default_rounds = 25000,
        sha512_crypt__max_rounds = 50000,
        sha512_crypt__min_rounds = 40000,
    )

    #-----------------------------------------------------
    #sample 2 - partial policy & result of overlay on sample 1
    #-----------------------------------------------------
    sample_config_2s = """\
[passlib]
bsdi_crypt.min_rounds = 29000
bsdi_crypt.max_rounds = 35000
bsdi_crypt.default_rounds = 31000
sha512_crypt.min_rounds = 45000
"""

    sample_config_2pd = dict(
        #using this to test full replacement of existing options
        bsdi_crypt__min_rounds = 29000,
        bsdi_crypt__max_rounds = 35000,
        bsdi_crypt__default_rounds = 31000,
        #using this to test partial replacement of existing options
        sha512_crypt__min_rounds=45000,
    )

    sample_config_12pd = dict(
        schemes = [ "des_crypt", "md5_crypt", "bsdi_crypt", "sha512_crypt"],
        default = "md5_crypt",
        all__vary_rounds = "10%",
        bsdi_crypt__min_rounds = 29000,
        bsdi_crypt__max_rounds = 35000,
        bsdi_crypt__default_rounds = 31000,
        sha512_crypt__max_rounds = 50000,
        sha512_crypt__min_rounds=45000,
    )

    #-----------------------------------------------------
    #sample 3 - just changing default
    #-----------------------------------------------------
    sample_config_3pd = dict(
        default="sha512_crypt",
    )

    sample_config_123pd = dict(
        schemes = [ "des_crypt", "md5_crypt", "bsdi_crypt", "sha512_crypt"],
        default = "sha512_crypt",
        all__vary_rounds = "10%",
        bsdi_crypt__min_rounds = 29000,
        bsdi_crypt__max_rounds = 35000,
        bsdi_crypt__default_rounds = 31000,
        sha512_crypt__max_rounds = 50000,
        sha512_crypt__min_rounds=45000,
    )

    #=========================================================
    #constructors
    #=========================================================
    def test_00_constructor(self):
        "test CryptPolicy() constructor"
        policy = CryptPolicy(**self.sample_config_1pd)
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

    def test_01_from_path(self):
        "test CryptPolicy.from_path() constructor"
        path = mktemp()
        with file(path, "w") as fh:
            fh.write(self.sample_config_1s)
        policy = CryptPolicy.from_path(path)
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

        #TODO: test if path missing

    def test_02_from_string(self):
        "test CryptPolicy.from_string() constructor"
        policy = CryptPolicy.from_string(self.sample_config_1s)
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

    def test_03_from_source(self):
        "test CryptPolicy.from_source() constructor"

        #pass it a path
        path = mktemp()
        with file(path, "w") as fh:
            fh.write(self.sample_config_1s)
        policy = CryptPolicy.from_source(path)
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

        #pass it a string
        policy = CryptPolicy.from_source(self.sample_config_1s)
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

        #pass it a dict (NOTE: make a copy to detect in-place modifications)
        policy = CryptPolicy.from_source(self.sample_config_1pd.copy())
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

        #pass it existing policy
        p2 = CryptPolicy.from_source(policy)
        self.assertIs(policy, p2)

        #pass it something wrong
        self.assertRaises(TypeError, CryptPolicy.from_source, 1)
        self.assertRaises(TypeError, CryptPolicy.from_source, [])

    def test_04_from_sources(self):
        "test CryptPolicy.from_sources() constructor"

        #pass it empty list
        self.assertRaises(ValueError, CryptPolicy.from_sources, [])

        #pass it one-element list
        policy = CryptPolicy.from_sources([self.sample_config_1s])
        self.assertEquals(policy.to_dict(), self.sample_config_1pd)

        #pass multiple sources
        path = mktemp()
        with file(path, "w") as fh:
            fh.write(self.sample_config_1s)
        policy = CryptPolicy.from_sources([
            path,
            self.sample_config_2s,
            self.sample_config_3pd,
            ])
        self.assertEquals(policy.to_dict(), self.sample_config_123pd)

    def test_05_replace(self):
        "test CryptPolicy.replace() constructor"

        p1 = CryptPolicy(**self.sample_config_1pd)

        #check overlaying sample 2
        p2 = p1.replace(**self.sample_config_2pd)
        self.assertEquals(p2.to_dict(), self.sample_config_12pd)

        #check repeating overlay makes no change
        p2b = p2.replace(**self.sample_config_2pd)
        self.assertEquals(p2b.to_dict(), self.sample_config_12pd)

        #check overlaying sample 3
        p3 = p2.replace(self.sample_config_3pd)
        self.assertEquals(p3.to_dict(), self.sample_config_123pd)

    #=========================================================
    #reading
    #=========================================================
    def test_10_has_handlers(self):
        "test has_handlers() method"

        p1 = CryptPolicy(**self.sample_config_1pd)
        self.assert_(p1.has_handlers())

        p3 = CryptPolicy(**self.sample_config_3pd)
        self.assert_(not p3.has_handlers())

    def test_11_iter_handlers(self):
        "test iter_handlers() method"

        p1 = CryptPolicy(**self.sample_config_1pd)
        s = self.sample_config_1prd['schemes'][::-1]
        self.assertEquals(list(p1.iter_handlers()), s)

        p3 = CryptPolicy(**self.sample_config_3pd)
        self.assertEquals(list(p3.iter_handlers()), [])

    def test_12_get_handler(self):
        "test get_handler() method"

        p1 = CryptPolicy(**self.sample_config_1pd)

        #check by name
        self.assertIs(p1.get_handler("bsdi_crypt"), hash.bsdi_crypt)

        #check by missing name
        self.assertIs(p1.get_handler("sha256_crypt"), None)
        self.assertRaises(KeyError, p1.get_handler, "sha256_crypt", required=True)

        #check default
        self.assertIs(p1.get_handler(), hash.md5_crypt)

    def test_13_get_options(self):
        "test get_options() method"

        p12 = CryptPolicy(**self.sample_config_12pd)

        self.assertEquals(p12.get_options("bsdi_crypt"),dict(
            vary_rounds = "10%",
            min_rounds = 29000,
            max_rounds = 35000,
            default_rounds = 31000,
        ))

        self.assertEquals(p12.get_options("sha512_crypt"),dict(
            vary_rounds = "10%",
            min_rounds = 45000,
            max_rounds = 50000,
        ))

    def test_14_handler_is_deprecated(self):
        "test handler_is_deprecated() method"
        pa = CryptPolicy(**self.sample_config_1pd)
        pb = pa.replace(deprecated=["des_crypt", "bsdi_crypt"])

        self.assert_(not pa.handler_is_deprecated("des_crypt"))
        self.assert_(not pa.handler_is_deprecated(hash.bsdi_crypt))
        self.assert_(not pa.handler_is_deprecated("sha512_crypt"))

        self.assert_(pb.handler_is_deprecated("des_crypt"))
        self.assert_(pb.handler_is_deprecated(hash.bsdi_crypt))
        self.assert_(not pb.handler_is_deprecated("sha512_crypt"))

    #TODO: test this.
    ##def test_gen_min_verify_time(self):
    ##    "test get_min_verify_time() method"

    #=========================================================
    #serialization
    #=========================================================
    def test_20_iter_config(self):
        "test iter_config() method"
        p1 = CryptPolicy(**self.sample_config_1pd)
        self.assertEquals(dict(p1.iter_config()), self.sample_config_1pd)
        self.assertEquals(dict(p1.iter_config(resolve=True)), self.sample_config_1prd)
        self.assertEquals(dict(p1.iter_config(ini=True)), self.sample_config_1pid)

    def test_21_to_dict(self):
        "test to_dict() method"
        p1 = CryptPolicy(**self.sample_config_1pd)
        self.assertEquals(p1.to_dict(), self.sample_config_1pd)
        self.assertEquals(p1.to_dict(resolve=True), self.sample_config_1prd)

    def test_22_to_string(self):
        "test to_string() method"
        pa = CryptPolicy(**self.sample_config_1pd)
        s = pa.to_string() #NOTE: can't compare string directly, ordering etc may not match
        pb = CryptPolicy.from_string(s)
        self.assertEquals(pb.to_dict(), self.sample_config_1pd)

    #=========================================================
    #
    #=========================================================

#=========================================================
#CryptContext
#=========================================================
class CryptContextTest(TestCase):
    "test CryptContext object's behavior"
    case_prefix = "CryptContext"

    #=========================================================
    #constructor
    #=========================================================
    def test_00_constructor(self):
        "test CryptContext simple constructor"
        #create crypt context using handlers
        cc = CryptContext([UnsaltedHash, SaltedHash, hash.md5_crypt])
        c, b, a = cc.policy.iter_handlers()
        self.assertIs(a, UnsaltedHash)
        self.assertIs(b, SaltedHash)
        self.assertIs(c, hash.md5_crypt)

        #create context using names
        cc = CryptContext([UnsaltedHash, SaltedHash, "md5_crypt"])
        c, b, a = cc.policy.iter_handlers()
        self.assertIs(a, UnsaltedHash)
        self.assertIs(b, SaltedHash)
        self.assertIs(c, hash.md5_crypt)

    #TODO: test policy & other options

    #=========================================================
    #policy adaptation
    #=========================================================
    #TODO:
    #norm_handler_settings
    #hash_is_compliant

    #=========================================================
    #identify
    #=========================================================
    def test_20_basic(self):
        "test basic encrypt/identify/verify functionality"
        handlers = [UnsaltedHash, SaltedHash, AnotherHash]
        cc = CryptContext(handlers, policy=None)

        #run through handlers
        for crypt in handlers:
            h = cc.encrypt("test", scheme=crypt.name)
            self.assertEquals(cc.identify(h), crypt.name)
            self.assertEquals(cc.identify(h, resolve=True), crypt)
            self.assert_(cc.verify('test', h))
            self.assert_(not cc.verify('notest', h))

        #test default
        h = cc.encrypt("test")
        self.assertEquals(cc.identify(h), AnotherHash.name)

    def test_21_identify(self):
        "test identify() border cases"
        handlers = [UnsaltedHash, SaltedHash, AnotherHash]
        cc = CryptContext(handlers, policy=None)

        #check unknown hash
        self.assertEquals(cc.identify('$9$232323123$1287319827'), None)
        self.assertRaises(ValueError, cc.identify, '$9$232323123$1287319827', required=True)

        #make sure "None" is accepted
        self.assertEquals(cc.identify(None), None)
        self.assertRaises(ValueError, cc.identify, None, required=True)

    def test_22_verify(self):
        "test verify() scheme kwd"
        handlers = [UnsaltedHash, SaltedHash, AnotherHash]
        cc = CryptContext(handlers, policy=None)

        h = AnotherHash.encrypt("test")

        #check base verify
        self.assert_(cc.verify("test", h))
        self.assert_(not cc.verify("notest", h))

        #check verify using right alg
        self.assert_(cc.verify('test', h, scheme='md5_crypt'))
        self.assert_(not cc.verify('notest', h, scheme='md5_crypt'))

        #check verify using wrong alg
        self.assertRaises(ValueError, cc.verify, 'test', h, scheme='salted_example')

    def test_23_verify_empty_hash(self):
        "test verify() allows hash=None"
        handlers = [UnsaltedHash, SaltedHash, AnotherHash]
        cc = CryptContext(handlers, policy=None)
        self.assert_(not cc.verify("test", None))
        for handler in handlers:
            self.assert_(not cc.verify("test", None, scheme=handler.name))

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#EOF
#=========================================================