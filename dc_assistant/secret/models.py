import os
from django.db import models
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Util import strxor

from django.shortcuts import reverse
from django.utils.encoding import force_bytes
from django.db.models import QuerySet
from .utils import encrypt_master_key, decrypt_master_key, generate_random_key
from django.contrib.auth.hashers import make_password, check_password
from taggit.managers import TaggableManager
from extend.models import TaggedItem, LoggingModel
from organisation.models import Device
from django.contrib.auth.hashers import PBKDF2PasswordHasher


__all__ = (
    'Secret',
    'SecretRole',
    'SessionKey',
    'UserKey',
)

class InvalidKey(Exception):
    """
    Raised when a provided key is invalid.
    """
    pass


class SecretValidationHasher(PBKDF2PasswordHasher):
    """
    Use Django integrated SHA256 hasher with a low iteration count to avoid delay
    """
    iterations = 1000


class UserKeyQuerySet(QuerySet):

    def active(self):
        return self.filter(master_key_cipher__isnull=False)


class UserKey(models.Model):
    """
    A UserKey stores a user's personal RSA (public key) encryption key, which is used to generate master encryption key.
    The encrypted instance (device passwords as secrets in model secrets an so on) of the master key can be decrypted only with the user's
    matching private key. Private key user have to save(copy to file, notes) private key as he do their other
    private keys (for example private key for access to servers by ssh)
    """
    created = models.DateField(
        auto_now_add=True
    )
    last_updated = models.DateTimeField(
        auto_now=True
    )
    user = models.OneToOneField(
        to=User,
        on_delete=models.CASCADE,
        related_name='user_key',
        editable=False
    )
    public_key = models.TextField(
        verbose_name='RSA public key'
    )
    master_key_cipher = models.BinaryField(
        max_length=512,
        blank=True,
        null=True,
        editable=False
    )
    objects = UserKeyQuerySet.as_manager()

    class Meta:
        ordering = ['user__username']
        # permissions = (
        #     ('activate_userkey', "Can activate user keys for decryption"),
        # )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Store the initial public_key and master_key_cipher to check for changes on save().
        self.__initial_public_key = self.public_key
        self.__initial_master_key_cipher = self.master_key_cipher

    def __str__(self):
        return self.user.username

    def clean(self, *args, **kwargs):

        if self.public_key:

            # Validate the public key format
            try:
                pubkey = RSA.import_key(self.public_key)
            except ValueError:
                raise ValidationError({
                    'public_key': "Invalid RSA key format."
                })
            except Exception:
                raise ValidationError("Something wrong trying to save your key. Please ensure that you're "
                                      "uploading a valid RSA public key in PEM format (no SSH/PGP).")

            # Validate the public key length
            pubkey_length = pubkey.size_in_bits()
            if pubkey_length < 2048:
                raise ValidationError({
                    'public_key': "Insufficient key length. Keys must be at least {} bits long.".format(2048)
                })
            # We can't use keys bigger than our master_key_cipher field can hold
            if pubkey_length > 4096:
                raise ValidationError({
                    'public_key': "Public key size ({}) is too large. Maximum key size is 4096 bits.".format(pubkey_length)
                })

        super().clean()

    def save(self, *args, **kwargs):

        # Check that public_key was modified. If yes, clean the initial master_key_cipher.
        if self.__initial_master_key_cipher and self.public_key != self.__initial_public_key:
            self.master_key_cipher = None

        # If no other active UserKeys exist, generate a new master key and use it to activate this UserKey.
        if self.is_filled() and not self.is_active() and not UserKey.objects.active().count():
            master_key = generate_random_key()
            self.master_key_cipher = encrypt_master_key(master_key, self.public_key)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):

        # If Secrets exist and this is the last active UserKey, prevent its deletion. Deleting the last UserKey will
        # result in the master key being destroyed and rendering all Secrets inaccessible.
        if Secret.objects.count() and [uk.pk for uk in UserKey.objects.active()] == [self.pk]:
            raise Exception("Cannot delete the last active UserKey when Secrets exist! This would render all secrets "
                            "inaccessible.")

        super().delete(*args, **kwargs)

    def is_filled(self):
        """
        Returns True if the UserKey has been filled with a public RSA key.
        """
        return bool(self.public_key)
    is_filled.boolean = True

    def is_active(self):
        """
        Returns True if the UserKey has been populated with an encrypted copy of the master key.
        """
        return self.master_key_cipher is not None
    is_active.boolean = True

    def get_master_key(self, private_key):
        """
        Given the User's private key, return the encrypted master key.
        """
        if not self.is_active:
            raise ValueError("Unable to retrieve master key: UserKey is inactive.")
        try:
            return decrypt_master_key(force_bytes(self.master_key_cipher), private_key)
        except ValueError:
            return None

    def activate(self, master_key):
        """
        Activate the UserKey by saving an encrypted copy of the master key to the database.
        """
        if not self.public_key:
            raise Exception("Cannot activate UserKey: Its public key must be filled first.")
        self.master_key_cipher = encrypt_master_key(master_key, self.public_key)
        self.save()


class SecretRole(LoggingModel):
    """
    A SecretRole represents an arbitrary functional classification of Secrets. For example, a user might define roles
    such as "Login Credentials" or "SNMP Communities."

    By default, only superusers will have access to decrypt Secrets. To allow other users to decrypt Secrets, grant them
    access to the appropriate SecretRoles either individually or by group.
    """
    name = models.CharField(
        max_length=50,
        unique=True
    )
    slug = models.SlugField(
        unique=True
    )
    description = models.CharField(
        max_length=100,
        blank=True,
    )
    users = models.ManyToManyField(
        to=User,
        related_name='secretroles',
        blank=True
    )
    groups = models.ManyToManyField(
        to=Group,
        related_name='secretroles',
        blank=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?role={}".format(reverse('secret:secret_list'), self.slug)

    def has_member(self, user):
        """
        Check whether the given user has belongs to this SecretRole. Note that superusers belong to all roles.
        """
        if user.is_superuser:
            return True
        return user in self.users.all() or user.groups.filter(pk__in=self.groups.all()).exists()


class SessionKey(models.Model):
    """
    A SessionKey stores a User's temporary key to be used for the encryption and decryption of secrets.
    """
    userkey = models.OneToOneField(
        to=UserKey,
        on_delete=models.CASCADE,
        related_name='session_key',
        editable=False
    )
    cipher = models.BinaryField(
        max_length=512,
        editable=False
    )
    hash = models.CharField(
        max_length=128,
        editable=False
    )
    created = models.DateTimeField(
        auto_now_add=True
    )

    key = None

    class Meta:
        ordering = ['userkey__user__username']

    def __str__(self):
        return self.userkey.user.username

    def save(self, master_key=None, *args, **kwargs):

        if master_key is None:
            raise Exception("The master key must be provided to save a session key.")

        # Generate random 256-bit session key if one is not already defined
        if self.key is None:
            self.key = generate_random_key()

        # Generate SHA256 hash using Django's built-in password hashing mechanism
        self.hash = make_password(self.key)

        # Encrypt master key using the session key
        self.cipher = strxor.strxor(self.key, master_key)

        super().save(*args, **kwargs)

    def get_master_key(self, session_key):

        # Validate the provided session key
        if not check_password(session_key, self.hash):
            raise InvalidKey("Invalid session key")

        # Decrypt master key using provided session key
        master_key = strxor.strxor(session_key, bytes(self.cipher))

        return master_key

    def get_session_key(self, master_key):
        print(master_key)

        # Recover session key using the master key
        session_key = strxor.strxor(master_key, bytes(self.cipher))

        # Validate the recovered session key
        if not check_password(session_key, self.hash):
            raise InvalidKey("Invalid master key")

        return session_key


class Secret(LoggingModel):
    """
    A Secret stores an AES256-encrypted copy of sensitive data, such as passwords or secret keys. An irreversible
    SHA-256 hash is stored along with the ciphertext for validation upon decryption. Each Secret is assigned to a
    Device; Devices may have multiple Secrets associated with them. A name can optionally be defined along with the
    ciphertext; this string is stored as plain text in the database.

    A Secret can be up to 65,535 bytes (64KB - 1B) in length. Each secret string will be padded with random data to
    a minimum of 64 bytes during encryption in order to protect short strings from ciphertext analysis.
    """
    device = models.ForeignKey(
        to=Device,
        on_delete=models.CASCADE,
        related_name='secrets'
    )
    role = models.ForeignKey(
        to=SecretRole,
        on_delete=models.PROTECT,
        related_name='secrets'
    )
    name = models.CharField(
        max_length=100,
        blank=True
    )
    # 128-bit IV + 16-bit pad length + 65535B secret + 15B padding
    ciphertext = models.BinaryField(
        max_length=65568,
        editable=False
    )
    hash = models.CharField(
        max_length=128,
        editable=False
    )
    tag = TaggableManager(through=TaggedItem)

    plaintext = None

    class Meta:
        ordering = ['device', 'role', 'name']
        unique_together = ['device', 'role', 'name']

    def __init__(self, *args, **kwargs):
        self.plaintext = kwargs.pop('plaintext', None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        #return self.name
        return '{} for {}'.format(self.name, self.device)
        # try:
        #     device = self.device
        # except Device.DoesNotExist:
        #     device = None
        # print('Secret __str__', self.role)
        # if self.role and device and self.name:
        #     return '{} for {} ({})'.format(self.role, self.device, self.name)
        # # Return role and device if no name is set
        # if self.role and device:
        #     return '{} for {}'.format(self.role, self.device)
        # return 'Secret'

    def get_absolute_url(self):
        return reverse('secret:secret', args=[self.pk])

    def _pad(self, s):
        """
        Prepare the length of the password plaintext (2B) and complete with garbage to a multiple 16B (minimum 64B).
        +--+--------+-------------------------------------------+
        |LL|MySecret|xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx|
        +--+--------+-------------------------------------------+
        """
        s = s.encode('utf8')
        if len(s) > 65535:
            raise ValueError("Maximum plaintext size is 65535 bytes.")

        # Minimum ciphertext size is 64 bytes to conceal the length of short secrets.
        if len(s) <= 62:
            pad_length = 62 - len(s)
        elif (len(s) + 2) % 16:
            pad_length = 16 - ((len(s) + 2) % 16)
        else:
            pad_length = 0

        header = bytes([len(s) >> 8]) + bytes([len(s) % 256])

        return header + s + os.urandom(pad_length)

    def _unpad(self, s):
        """
        Use the first two bytes of s as a plaintext length indicator and return only that many bytes as the
        plaintext.
        """
        if isinstance(s[0], str):
            plaintext_length = (ord(s[0]) << 8) + ord(s[1])
        else:
            plaintext_length = (s[0] << 8) + s[1]
        return s[2:plaintext_length + 2].decode('utf8')

    def encrypt(self, secret_key):
        """
        Generate a random initialization vector (IV) for AES. Complete the plaintext to the AES block size (16 bytes) and
        encrypt. Prepare the IV for use in decryption. At the finally record the SHA256 hash of the plaintext for validation
        upon decryption.
        """
        if self.plaintext is None:
            raise Exception("Must unlock or set plaintext before locking.")

        # Pad and encrypt plaintext
        iv = os.urandom(16)
        aes = AES.new(secret_key, AES.MODE_CFB, iv)
        self.ciphertext = iv + aes.encrypt(self._pad(self.plaintext))

        # Generate SHA256 using Django's built-in password hashing mechanism
        self.hash = make_password(self.plaintext, hasher=SecretValidationHasher())

        self.plaintext = None

    def decrypt(self, secret_key):
        """
        Consume the first 16 bytes of self.ciphertext as the AES initialization vector (IV). The remainder is decrypted
        using the IV and the provided secret key. Padding is then removed to reveal the plaintext. Finally, validate the
        decrypted plaintext value against the stored hash.
        """
        if self.plaintext is not None:
            return
        if not self.ciphertext:
            raise Exception("Must define ciphertext before unlocking.")

        # Decrypt ciphertext and remove padding
        iv = bytes(self.ciphertext[0:16])
        ciphertext = bytes(self.ciphertext[16:])
        aes = AES.new(secret_key, AES.MODE_CFB, iv)
        plaintext = self._unpad(aes.decrypt(ciphertext))

        # Verify decrypted plaintext against hash
        if not self.validate(plaintext):
            raise ValueError("Invalid key or ciphertext!")

        self.plaintext = plaintext

    def validate(self, plaintext):
        """
        Validate that a given plaintext matches the stored hash.
        """
        if not self.hash:
            raise Exception("Hash is not generated for this secret.")
        return check_password(plaintext, self.hash, preferred=SecretValidationHasher())

    def decryptable_by(self, user):
        """
        Check whether the given user has permission to decrypt this Secret.
        """
        return self.role.has_member(user)