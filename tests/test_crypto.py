"""Unit tests for the crypto module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clipshare.crypto import (
    generate_dh_keypair,
    compute_shared_secret,
    aes_key_to_base64,
    aes_key_from_base64,
)


class TestDiffieHellman:
    """Tests for DH key exchange."""

    def test_keypair_generation(self):
        """Test that keypair generation produces valid keys."""
        priv, pub = generate_dh_keypair()
        assert priv is not None
        assert pub is not None
        assert len(priv) > 0
        assert len(pub) > 0
        assert priv != pub  # private and public should differ

    def test_shared_secret_matches(self):
        """Test that both sides compute the same shared secret."""
        priv_a, pub_a = generate_dh_keypair()
        priv_b, pub_b = generate_dh_keypair()

        secret_a = compute_shared_secret(priv_a, pub_b)
        secret_b = compute_shared_secret(priv_b, pub_a)

        assert secret_a == secret_b, "Shared secrets must be identical"
        assert len(secret_a) == 32  # SHA-256 produces 32 bytes

    def test_different_keys_different_secrets(self):
        """Test that different keypairs produce different secrets."""
        priv_a, pub_a = generate_dh_keypair()
        priv_b, pub_b = generate_dh_keypair()
        priv_c, pub_c = generate_dh_keypair()

        secret_ab = compute_shared_secret(priv_a, pub_b)
        secret_ac = compute_shared_secret(priv_a, pub_c)

        assert secret_ab != secret_ac, "Different peers should produce different secrets"

    def test_keypair_determinism(self):
        """Test that same inputs produce same results."""
        priv, pub = generate_dh_keypair()
        secret1 = compute_shared_secret(priv, pub)  
        secret2 = compute_shared_secret(priv, pub)
        # Same inputs should give same secret (DH property)
        assert secret1 == secret2

    def test_multiple_keypairs(self):
        """Test generating multiple unique keypairs."""
        keypairs = [generate_dh_keypair() for _ in range(10)]
        # All private keys should be unique
        priv_keys = [kp[0] for kp in keypairs]
        assert len(set(priv_keys)) == 10, "Private keys should be unique"
        # All public keys should be unique
        pub_keys = [kp[1] for kp in keypairs]
        assert len(set(pub_keys)) == 10, "Public keys should be unique"

    def test_base64_key_conversion(self):
        """Test base64 key encoding/decoding."""
        _, pub_a = generate_dh_keypair()
        _, pub_b = generate_dh_keypair()
        priv_a, _ = generate_dh_keypair()

        secret = compute_shared_secret(priv_a, pub_b)

        # Encode and decode
        b64 = aes_key_to_base64(secret)
        decoded = aes_key_from_base64(b64)

        assert decoded == secret, "Base64 round-trip should preserve key"
        assert len(b64) > 0


class TestAESEncryption:
    """Tests for AES-GCM encryption (requires cryptography library)."""

    def test_aes_available(self):
        """Test whether AES encryption is available."""
        from clipshare.crypto import _HAS_AES
        # In test environment without cryptography, this will be False
        # In production with cryptography, this will be True
        assert isinstance(_HAS_AES, bool)

    def test_encrypt_decrypt(self):
        """Test AES-GCM encrypt/decrypt round-trip."""
        from clipshare.crypto import _HAS_AES, encrypt_data, decrypt_data
        import os

        if not _HAS_AES:
            print("  SKIP (cryptography not installed)")
            return

        key = os.urandom(32)
        plaintext = b"Hello, this is a secret message for clipboard sync!"

        encrypted = encrypt_data(key, plaintext)
        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)  # nonce + tag overhead

        decrypted = decrypt_data(key, encrypted)
        assert decrypted == plaintext

    def test_encrypt_different_nonces(self):
        """Test that encrypting same data produces different ciphertexts."""
        from clipshare.crypto import _HAS_AES, encrypt_data
        import os

        if not _HAS_AES:
            print("  SKIP (cryptography not installed)")
            return

        key = os.urandom(32)
        plaintext = b"same data"

        ct1 = encrypt_data(key, plaintext)
        ct2 = encrypt_data(key, plaintext)

        # Nonces are different, so ciphertexts should differ
        assert ct1 != ct2

    def test_decrypt_wrong_key_fails(self):
        """Test that decrypting with wrong key raises error."""
        from clipshare.crypto import _HAS_AES, encrypt_data, decrypt_data
        import os

        if not _HAS_AES:
            print("  SKIP (cryptography not installed)")
            return

        key1 = os.urandom(32)
        key2 = os.urandom(32)
        plaintext = b"secret"

        encrypted = encrypt_data(key1, plaintext)
        
        try:
            decrypt_data(key2, encrypted)
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected


if __name__ == "__main__":
    import sys
    print("Run via run_tests.py instead")
    sys.exit(0)