"""passlib.handlers.fshp
"""

#=========================================================
#imports
#=========================================================
#core
from base64 import b64encode, b64decode
import re
import logging; log = logging.getLogger(__name__)
from warnings import warn
#site
#libs
from passlib.utils import to_unicode
import passlib.utils.handlers as uh
from passlib.utils.compat import b, bytes, bascii_to_str, iteritems, u,\
                                 unicode
from passlib.utils.pbkdf2 import pbkdf1
#pkg
#local
__all__ = [
    'fshp',
]
#=========================================================
#sha1-crypt
#=========================================================
class fshp(uh.HasRounds, uh.HasRawSalt, uh.HasRawChecksum, uh.GenericHandler):
    """This class implements the FSHP password hash, and follows the :ref:`password-hash-api`.

    It supports a variable-length salt, and a variable number of rounds.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept the following optional keywords:

    :param salt:
        Optional raw salt string.
        If not specified, one will be autogenerated (this is recommended).

    :param salt_size:
        Optional number of bytes to use when autogenerating new salts.
        Defaults to 16 bytes, but can be any non-negative value.

    :param rounds:
        Optional number of rounds to use.
        Defaults to 40000, must be between 1 and 4294967295, inclusive.

    :param variant:
        Optionally specifies variant of FSHP to use.

        * ``0`` - uses SHA-1 digest (deprecated).
        * ``1`` - uses SHA-2/256 digest (default).
        * ``2`` - uses SHA-2/384 digest.
        * ``3`` - uses SHA-2/512 digest.
    """

    #=========================================================
    #class attrs
    #=========================================================
    #--GenericHandler--
    name = "fshp"
    summary = "Fairly Secure Hashed Password - a PBKDF1-based password hash"
    setting_kwds = ("salt", "salt_size", "rounds", "variant")
    checksum_chars = uh.PADDED_BASE64_CHARS
    ident = u("{FSHP")
    # checksum_size is property() that depends on variant

    #--HasRawSalt--
    default_salt_size = 16 #current passlib default, FSHP uses 8
    min_salt_size = 0
    max_salt_size = None

    #--HasRounds--
    default_rounds = 16384 #current passlib default, FSHP uses 4096
    min_rounds = 1 #set by FSHP
    max_rounds = 4294967295 # 32-bit integer limit - not set by FSHP
    rounds_cost = "linear"

    #--variants--
    default_variant = 1
    _variant_info = {
        #variant: (hash name, digest size)
        0: ("sha1",     20),
        1: ("sha256",   32),
        2: ("sha384",   48),
        3: ("sha512",   64),
        }
    _variant_aliases = dict(
        [(unicode(k),k) for k in _variant_info] +
        [(v[0],k) for k,v in iteritems(_variant_info)]
        )

    #=========================================================
    #instance attrs
    #=========================================================
    variant = None

    #=========================================================
    #init
    #=========================================================
    def __init__(self, variant=None, **kwds):
        # NOTE: variant must be set first, since it controls checksum size, etc.
        self.use_defaults = kwds.get("use_defaults") # load this early
        self.variant = self._norm_variant(variant)
        super(fshp, self).__init__(**kwds)

    def _norm_variant(self, variant):
        if variant is None:
            if not self.use_defaults:
                raise TypeError("no variant specified")
            variant = self.default_variant
        if isinstance(variant, bytes):
            variant = variant.decode("ascii")
        if isinstance(variant, unicode):
            try:
                variant = self._variant_aliases[variant]
            except KeyError:
                raise ValueError("invalid fshp variant")
        if not isinstance(variant, int):
            raise TypeError("fshp variant must be int or known alias")
        if variant not in self._variant_info:
            raise ValueError("invalid fshp variant")
        return variant

    @property
    def checksum_alg(self):
        return self._variant_info[self.variant][0]

    @property
    def checksum_size(self):
        return self._variant_info[self.variant][1]

    #=========================================================
    #formatting
    #=========================================================

    _hash_regex = re.compile(u(r"""
            ^
            \{FSHP
            (\d+)\| # variant
            (\d+)\| # salt size
            (\d+)\} # rounds
            ([a-zA-Z0-9+/]+={0,3}) # digest
            $"""), re.X)

    @classmethod
    def from_string(cls, hash):
        hash = to_unicode(hash, "ascii", "hash")
        m = cls._hash_regex.match(hash)
        if not m:
            raise uh.exc.InvalidHashError(cls)
        variant, salt_size, rounds, data = m.group(1,2,3,4)
        variant = int(variant)
        salt_size = int(salt_size)
        rounds = int(rounds)
        try:
            data = b64decode(data.encode("ascii"))
        except TypeError:
            raise uh.exc.MalformedHashError(cls)
        salt = data[:salt_size]
        chk = data[salt_size:]
        return cls(salt=salt, checksum=chk, rounds=rounds, variant=variant)

    @property
    def _stub_checksum(self):
        return b('\x00') * self.checksum_size

    def to_string(self):
        chk = self.checksum or self._stub_checksum
        salt = self.salt
        data = bascii_to_str(b64encode(salt+chk))
        return "{FSHP%d|%d|%d}%s" % (self.variant, len(salt), self.rounds, data)

    #=========================================================
    #backend
    #=========================================================

    def _calc_checksum(self, secret):
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        #NOTE: for some reason, FSHP uses pbkdf1 with password & salt reversed.
        #      this has only a minimal impact on security,
        #      but it is worth noting this deviation.
        return pbkdf1(
            secret=self.salt,
            salt=secret,
            rounds=self.rounds,
            keylen=self.checksum_size,
            hash=self.checksum_alg,
            )

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#eof
#=========================================================
