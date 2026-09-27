from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

import pyotp

from api.exceptions import (
    PreAuthTokenInvalidError,
    TwoFactorAlreadyEnabledError,
    TwoFactorCodeAlreadyUsedError,
    TwoFactorCodeInvalidError,
    TwoFactorNotEnabledError,
)
from api.utils.jwt_methods import decode_pre_auth_token, generate_pre_auth_token
from api.utils.two_factor_methods import (
    generate_backup_codes,
    generate_qr_code_base64,
    generate_totp_uri,
    generate_two_factor_secret,
    hash_backup_code,
    mark_totp_code_used,
    verify_and_burn_backup_code,
    verify_totp_code,
)
from database.models.users import Admin, User


class TwoFactorCoreTest(unittest.IsolatedAsyncioTestCase):
    def test_secret_and_uri_and_qr_generation(self):
        secret = generate_two_factor_secret()
        self.assertEqual(len(secret), 32)

        uri = generate_totp_uri(secret, account_name="test@example.com", issuer="Gladeal")
        self.assertTrue(uri.startswith("otpauth://totp/Gladeal:test%40example.com?secret="))

        qr_b64 = generate_qr_code_base64(uri)
        self.assertTrue(qr_b64.startswith("data:image/png;base64,"))

    def test_backup_codes_generation_hashing_and_burning(self):
        codes = generate_backup_codes(8)
        self.assertEqual(len(codes), 8)
        for code in codes:
            self.assertEqual(len(code), 9)  # XXXX-XXXX
            self.assertIn("-", code)

        hashes = [hash_backup_code(c) for c in codes]
        self.assertEqual(len(hashes), 8)

        # 1. Use the first code
        valid, remaining = verify_and_burn_backup_code(codes[0], hashes)
        self.assertTrue(valid)
        self.assertEqual(len(remaining), 7)
        self.assertNotIn(hashes[0], remaining)

        # 2. Re-attempt to use the burned code -> must fail
        reused_valid, remaining_after_reuse = verify_and_burn_backup_code(codes[0], remaining)
        self.assertFalse(reused_valid)
        self.assertEqual(len(remaining_after_reuse), 7)

        # 3. Invalid code -> must fail
        invalid_valid, _ = verify_and_burn_backup_code("WRONG-CODE", remaining)
        self.assertFalse(invalid_valid)

    def test_totp_verification(self):
        secret = generate_two_factor_secret()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()

        # Valid code
        self.assertTrue(verify_totp_code(secret, current_code))

        # Invalid code
        self.assertFalse(verify_totp_code(secret, "000000" if current_code != "000000" else "111111"))
        self.assertFalse(verify_totp_code(secret, "abc"))
        self.assertFalse(verify_totp_code("", current_code))

    async def test_replay_attack_prevention_in_redis(self):
        fake_redis = AsyncMock()
        # First call: key is set (nx=True returns True)
        fake_redis.set.return_value = True

        with patch("api.utils.two_factor_methods.get_sms_calls_redis", return_value=fake_redis):
            await mark_totp_code_used("user", 1, "123456")
            fake_redis.set.assert_called_once_with("2fa:used:user:1:123456", "1", ex=90, nx=True)

        # Second call: key already exists (nx=True returns None) -> Replay attack
        fake_redis.set.return_value = None
        with patch("api.utils.two_factor_methods.get_sms_calls_redis", return_value=fake_redis):
            with self.assertRaises(TwoFactorCodeAlreadyUsedError):
                await mark_totp_code_used("user", 1, "123456")

    def test_pre_auth_token_lifecycle(self):
        token = generate_pre_auth_token(entity_id=42, role="user")
        decoded_id = decode_pre_auth_token(token, expected_role="user")
        self.assertEqual(decoded_id, 42)

        # Role mismatch -> Invalid
        with self.assertRaises(PreAuthTokenInvalidError):
            decode_pre_auth_token(token, expected_role="admin")

        # Invalid token string -> Invalid
        with self.assertRaises(PreAuthTokenInvalidError):
            decode_pre_auth_token("invalid.token.here", expected_role="user")


class TwoFactorDomainLogicTest(unittest.IsolatedAsyncioTestCase):
    async def test_user_2fa_setup_and_enable(self):
        from api.utils.users_methods import enable_user_2fa, setup_user_2fa

        user = User(
            id=10,
            first_name="Test",
            patronymic="User",
            last_name="Testov",
            phone_number="+79998887766",
            is_banned=False,
            is_two_factor_enabled=False,
            two_factor_secret=None,
            two_factor_backup_codes=None,
        )

        class FakeSession:
            def __init__(self, u):
                self.u = u

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            def begin(self):
                return self

            async def scalar(self, stmt):
                return self.u

        fake_session = FakeSession(user)
        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session), \
             patch("api.utils.users_methods.ensure_user_not_banned", AsyncMock()):
            # 1. Setup
            setup_res = await setup_user_2fa(10)
            self.assertEqual(len(setup_res.secret), 32)
            self.assertEqual(len(setup_res.backup_codes), 8)
            self.assertEqual(user.two_factor_secret, setup_res.secret)
            self.assertFalse(user.is_two_factor_enabled)

            # 2. Enable with invalid code
            with self.assertRaises(TwoFactorCodeInvalidError):
                await enable_user_2fa(10, "000000")
            self.assertFalse(user.is_two_factor_enabled)

            # 3. Enable with valid code
            valid_code = pyotp.TOTP(setup_res.secret).now()
            with patch("api.utils.users_methods.mark_totp_code_used", AsyncMock()):
                await enable_user_2fa(10, valid_code)
            self.assertTrue(user.is_two_factor_enabled)

    async def test_user_2fa_verify_login_and_disable(self):
        from api.utils.users_methods import disable_user_2fa, verify_user_2fa_login

        secret = generate_two_factor_secret()
        backup_codes = generate_backup_codes(8)
        hashed_codes = [hash_backup_code(c) for c in backup_codes]

        user = User(
            id=10,
            first_name="Test",
            patronymic="User",
            last_name="Testov",
            phone_number="+79998887766",
            is_banned=False,
            is_two_factor_enabled=True,
            two_factor_secret=secret,
            two_factor_backup_codes=hashed_codes,
        )

        class FakeSession:
            def __init__(self, u):
                self.u = u

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            def begin(self):
                return self

            async def scalar(self, stmt):
                return self.u

        fake_session = FakeSession(user)
        pre_auth_token = generate_pre_auth_token(entity_id=10, role="user")

        with patch("api.utils.users_methods.AsyncSessionLocal", return_value=fake_session), \
             patch("api.utils.users_methods.ensure_user_not_banned", AsyncMock()), \
             patch("api.utils.users_methods.mark_totp_code_used", AsyncMock()), \
             patch("api.utils.users_methods.create_refresh_token", AsyncMock(return_value=("fake_refresh", datetime.now(timezone.utc)))):

            # 1. Login with valid TOTP
            valid_totp = pyotp.TOTP(secret).now()
            res = await verify_user_2fa_login(pre_auth_token, valid_totp)
            self.assertTrue(bool(res.access_token))

            # 2. Login with valid backup code
            res2 = await verify_user_2fa_login(pre_auth_token, backup_codes[0])
            self.assertTrue(bool(res2.access_token))
            self.assertEqual(len(user.two_factor_backup_codes), 7)

            # 3. Disable 2FA
            await disable_user_2fa(10, valid_totp)
            self.assertFalse(user.is_two_factor_enabled)
            self.assertIsNone(user.two_factor_secret)
            self.assertIsNone(user.two_factor_backup_codes)


class AdminTwoFactorTest(unittest.IsolatedAsyncioTestCase):
    async def test_admin_2fa_lifecycle(self):
        from api.utils.admins_methods import (
            disable_admin_2fa,
            enable_admin_2fa,
            get_admin_2fa_status,
            setup_admin_2fa,
            verify_admin_2fa_login,
        )

        admin = Admin(
            id=5,
            first_name="Admin",
            last_name="Super",
            email="admin@example.com",
            password_hash="fake_hash",
            is_two_factor_enabled=False,
            two_factor_secret=None,
            two_factor_backup_codes=None,
        )

        class FakeSession:
            def __init__(self, a):
                self.a = a

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            def begin(self):
                return self

            async def scalar(self, stmt):
                return self.a

        fake_session = FakeSession(admin)

        with patch("api.utils.admins_methods.AsyncSessionLocal", return_value=fake_session), \
             patch("api.utils.admins_methods.mark_totp_code_used", AsyncMock()):

            # 1. Setup
            setup_res = await setup_admin_2fa(5)
            self.assertEqual(len(setup_res.secret), 32)
            self.assertEqual(len(setup_res.backup_codes), 8)

            # 2. Enable
            valid_totp = pyotp.TOTP(setup_res.secret).now()
            await enable_admin_2fa(5, valid_totp)
            self.assertTrue(admin.is_two_factor_enabled)

            # 3. Status
            status = await get_admin_2fa_status(5)
            self.assertTrue(status.is_two_factor_enabled)
            self.assertEqual(status.backup_codes_remaining, 8)

            # 4. Verify login with backup code
            pre_auth_token = generate_pre_auth_token(entity_id=5, role="admin")
            with patch("api.utils.admins_methods.create_admin_refresh_token", AsyncMock(return_value=("fake_ref", datetime.now(timezone.utc)))):
                auth_res = await verify_admin_2fa_login(pre_auth_token, setup_res.backup_codes[0])
                self.assertTrue(bool(auth_res.access_token))
                self.assertEqual(len(admin.two_factor_backup_codes), 7)

            # 5. Disable
            with patch("api.utils.admins_methods.verify_admin_password_hash", return_value=True):
                await disable_admin_2fa(5, "correct_password", valid_totp)
                self.assertFalse(admin.is_two_factor_enabled)
                self.assertIsNone(admin.two_factor_secret)


if __name__ == "__main__":
    unittest.main()

