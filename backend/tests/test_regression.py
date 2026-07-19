import base64
import asyncio
import json
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import cctp_flow, db
from app.agent.gemini_client import GeminiAgentClient
from app.agent.skills import suggest_lineup
from app.config import settings
from app.data import apply_live_player_totals, get_players, get_world_cup_snapshot
from app.main import app
from app.mcp import client as mcp_module
from app.security import rate_limiter


class AutoGafferRegressionTests(unittest.TestCase):
    """High-value API contracts that must stay true during hackathon changes."""

    @classmethod
    def setUpClass(cls):
        cls._original_db_file = db.DB_FILE
        cls._temp_dir = tempfile.TemporaryDirectory()
        db.DB_FILE = Path(cls._temp_dir.name) / "auth.db"
        cls.client = TestClient(app)
        cls._original_settings = {
            "jwt_secret_key": settings.jwt_secret_key,
            "x402_demo_mode": settings.x402_demo_mode,
            "x402_allow_simulated_purchases": settings.x402_allow_simulated_purchases,
            "hackathon_demo_minutes": settings.hackathon_demo_minutes,
            "x402_facilitator_url": settings.x402_facilitator_url,
            "x402_pay_to": settings.x402_pay_to,
            "x402_asset": settings.x402_asset,
            "cctp_destination_domain": settings.cctp_destination_domain,
            "mcp_simulation": settings.mcp_simulation,
            "live_stats_enabled": settings.live_stats_enabled,
            "live_event_feed_enabled": settings.live_event_feed_enabled,
            "auth_cookie_secure": settings.auth_cookie_secure,
        }
        settings.jwt_secret_key = "test-only-jwt-secret-with-at-least-32-characters"
        settings.x402_demo_mode = True
        settings.x402_allow_simulated_purchases = False
        settings.hackathon_demo_minutes = 30
        settings.x402_facilitator_url = "https://facilitator.test"
        settings.x402_pay_to = "0x3333333333333333333333333333333333333333"
        settings.x402_asset = "0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d"
        settings.cctp_destination_domain = 29
        settings.mcp_simulation = True
        settings.live_stats_enabled = False
        settings.live_event_feed_enabled = False
        settings.auth_cookie_secure = False
        mcp_module._mcp_client = None

    @classmethod
    def tearDownClass(cls):
        db.DB_FILE = cls._original_db_file
        for name, value in cls._original_settings.items():
            setattr(settings, name, value)
        mcp_module._mcp_client = None
        cls._temp_dir.cleanup()

    def setUp(self):
        self.client.cookies.clear()
        rate_limiter.clear()
        settings.x402_allow_simulated_purchases = True
        self.recovery_codes = {}
        if db.DB_FILE.exists():
            db.DB_FILE.unlink()
        db.init_db()
        mcp_module._mcp_client = None

    def register_and_login(self, username="manager"):
        email = f"{username}@example.com"
        register = self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "Manager1",
            },
        )
        self.assertEqual(register.status_code, 200, register.text)
        self.recovery_codes[username] = register.json()["recoveryCode"]
        login = self.client.post(
            "/api/auth/login",
            json={"username_or_email": username, "password": "Manager1"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()["token"]

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def unlock_demo(self, token):
        response = self.client.post(
            "/api/access/unlock",
            headers=self.auth(token),
            json={"mode": "membership", "accessMethod": "demo", "hasPaidX402": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["simulated"])

    def test_locked_ai_and_analytics_explain_capabilities_without_calling_gemini(self):
        token = self.register_and_login()
        status = self.client.get("/api/access/status", headers=self.auth(token))
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["hasAiAccess"])

        for prompt in ("Messi'yi kadroya al", "Deep Tactical Analytics aç"):
            response = self.client.post(
                "/api/agent",
                headers=self.auth(token),
                json={"prompt": prompt, "formation": "4-3-3"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["provider"], "locked")
            self.assertTrue(payload["accessRequired"])
            self.assertIsNone(payload["suggestedAction"])
            self.assertIn("Deep Tactical Analytics", payload["message"])
            self.assertIn("x402", payload["message"])

    def test_demo_membership_is_explicit_and_time_boxed_for_a_new_account(self):
        token = self.register_and_login("freshjudge")
        before = self.client.get("/api/access/status", headers=self.auth(token)).json()
        self.assertFalse(before["membershipActive"])

        self.unlock_demo(token)
        after = self.client.get("/api/access/status", headers=self.auth(token)).json()
        self.assertTrue(after["membershipActive"])
        self.assertTrue(after["hasAiAccess"])
        self.assertEqual(after["accessSource"], "hackathon_demo_pro")
        self.assertIsNotNone(after["membershipExpiresAt"])
        remaining = (
            datetime.fromisoformat(after["membershipExpiresAt"]) - datetime.now(timezone.utc)
        ).total_seconds()
        self.assertGreater(remaining, 29 * 60)
        self.assertLessEqual(remaining, 30 * 60)

    def test_no_username_bypasses_a_disabled_demo_checkout(self):
        settings.x402_allow_simulated_purchases = False
        try:
            token = self.register_and_login("Kaan")
            access = self.client.get("/api/access/status", headers=self.auth(token)).json()
            self.assertFalse(access["demoAccessAvailable"])
            self.assertFalse(access["hasAiAccess"])

            response = self.client.post(
                "/api/access/unlock",
                headers=self.auth(token),
                json={"mode": "membership", "accessMethod": "demo"},
            )
            self.assertEqual(response.status_code, 403, response.text)
        finally:
            settings.x402_allow_simulated_purchases = True

    def test_any_new_manager_can_explicitly_activate_demo_pro_for_30_minutes(self):
        settings.x402_allow_simulated_purchases = True
        try:
            token = self.register_and_login("judgepro")
            before = self.client.get("/api/access/status", headers=self.auth(token)).json()
            self.assertFalse(before["hasAiAccess"])
            self.assertTrue(before["demoAccessAvailable"])
            self.assertEqual(before["demoDurationMinutes"], 30)

            response = self.client.post(
                "/api/access/unlock",
                headers={**self.auth(token), "Idempotency-Key": "judge-demo-pro"},
                json={"mode": "membership", "accessMethod": "demo"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertTrue(payload["simulated"])
            self.assertEqual(payload["chargedAmountUsdc"], 0)
            self.assertEqual(payload["demoReceipt"]["settlement"], "simulated")
            self.assertTrue(payload["membershipActive"])
            self.assertTrue(payload["hasAiAccess"])
            self.assertTrue(payload["hasAnalyticsAccess"])
            self.assertTrue(payload["hasFinanceAccess"])

            ledger = self.client.get("/api/operations/recent", headers=self.auth(token)).json()
            access_operations = [item for item in ledger["operations"] if item["actionType"] == "unlock_membership"]
            self.assertEqual(len(access_operations), 1)
            self.assertEqual(access_operations[0]["provider"], "hackathon_demo")
            self.assertTrue(access_operations[0]["simulated"])
        finally:
            settings.x402_allow_simulated_purchases = False

    def test_demo_match_pass_unlocks_ai_but_not_finance(self):
        settings.x402_allow_simulated_purchases = True
        try:
            token = self.register_and_login("judgepass")
            response = self.client.post(
                "/api/access/unlock",
                headers={**self.auth(token), "Idempotency-Key": "judge-demo-pass"},
                json={"mode": "single_use", "accessMethod": "demo"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertTrue(payload["accessPassActive"])
            self.assertTrue(payload["hasAiAccess"])
            self.assertTrue(payload["hasAnalyticsAccess"])
            self.assertFalse(payload["hasFinanceAccess"])
            self.assertEqual(payload["chargedAmountUsdc"], 0)
        finally:
            settings.x402_allow_simulated_purchases = False

    def test_expired_demo_can_be_activated_again(self):
        settings.x402_allow_simulated_purchases = True
        try:
            token = self.register_and_login("renewjudge")
            first = self.client.post(
                "/api/access/unlock",
                headers={**self.auth(token), "Idempotency-Key": "judge-demo-first"},
                json={"mode": "membership", "accessMethod": "demo"},
            )
            self.assertEqual(first.status_code, 200, first.text)

            connection = db.get_db_connection()
            try:
                connection.execute(
                    "UPDATE users SET membership_expires_at = ? WHERE username = ?",
                    ("2020-01-01T00:00:00+00:00", "renewjudge"),
                )
                connection.commit()
            finally:
                connection.close()

            expired = self.client.get("/api/access/status", headers=self.auth(token)).json()
            self.assertFalse(expired["membershipActive"])
            self.assertFalse(expired["hasAiAccess"])

            renewed = self.client.post(
                "/api/access/unlock",
                headers={**self.auth(token), "Idempotency-Key": "judge-demo-renewed"},
                json={"mode": "membership", "accessMethod": "demo"},
            )
            self.assertEqual(renewed.status_code, 200, renewed.text)
            self.assertTrue(renewed.json()["membershipActive"])
            self.assertNotEqual(first.json()["receipt"], renewed.json()["receipt"])
        finally:
            settings.x402_allow_simulated_purchases = False

    def test_access_unlock_has_a_replay_safe_x402_ledger_receipt(self):
        token = self.register_and_login("ledgerjudge")
        headers = {**self.auth(token), "Idempotency-Key": "demo-access-retry-regression"}
        payload = {"mode": "membership", "accessMethod": "demo", "hasPaidX402": False}
        first = self.client.post("/api/access/unlock", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.post("/api/access/unlock", headers=headers, json=payload)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["operation"]["operationId"], second.json()["operation"]["operationId"])

        ledger = self.client.get("/api/operations/recent", headers=self.auth(token))
        actions = [item for item in ledger.json()["operations"] if item["actionType"] == "unlock_membership"]
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0]["simulated"])

    def test_non_demo_unlock_returns_x402_v2_payment_requirement(self):
        token = self.register_and_login("paiduser")
        response = self.client.post(
            "/api/access/unlock",
            headers=self.auth(token),
            json={"mode": "membership", "accessMethod": "x402", "hasPaidX402": True},
        )
        self.assertEqual(response.status_code, 402, response.text)
        encoded = response.headers.get("PAYMENT-REQUIRED")
        self.assertIsNotNone(encoded)
        requirement = json.loads(base64.b64decode(encoded))
        self.assertEqual(requirement["x402Version"], 2)
        self.assertEqual(requirement["accepts"][0]["amount"], "4990000")
        self.assertFalse(
            self.client.get("/api/access/status", headers=self.auth(token)).json()["hasAiAccess"]
        )

    def test_verified_x402_membership_unlocks_a_new_manager_and_premium_tools(self):
        """A non-demo user only gains Pro access after facilitator settlement."""
        token = self.register_and_login("verifiedpayer")
        wallet = "0x1111111111111111111111111111111111111111"

        with patch("app.routers.access.get_x402_verifier") as get_verifier:
            verifier = get_verifier.return_value
            verifier.verify_and_settle = AsyncMock(return_value={
                "verified": True,
                "settled": True,
                "amount": 4.99,
                "currency": "USDC",
                "payer": wallet,
                "receipt": "0x" + "c" * 64,
                "paymentResponse": "test-payment-response",
            })
            response = self.client.post(
                "/api/access/unlock",
                headers={
                    **self.auth(token),
                    "Idempotency-Key": "verified-payer-membership",
                    "PAYMENT-SIGNATURE": "test-signed-payment",
                },
                json={"mode": "membership", "accessMethod": "x402", "hasPaidX402": True, "walletAddress": wallet},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["simulated"])
        self.assertTrue(response.json()["membershipActive"])
        self.assertEqual(response.json()["walletAddress"], wallet)

        access = self.client.get("/api/access/status", headers=self.auth(token)).json()
        self.assertTrue(access["membershipActive"])
        self.assertTrue(access["hasAiAccess"])
        self.assertTrue(access["hasAnalyticsAccess"])
        self.assertTrue(access["hasFinanceAccess"])
        self.assertEqual(access["accessSource"], "x402_verified")

        lab = self.client.post(
            "/api/tactical-lab/compare",
            headers=self.auth(token),
            json={"formation": "3-5-2", "strategy": "attacking"},
        )
        self.assertEqual(lab.status_code, 200, lab.text)
        self.assertEqual(lab.json()["accessSource"], "x402_verified")

    def test_browser_session_is_httponly_and_cookie_mutations_require_csrf(self):
        token = self.register_and_login("cookieuser")
        login = self.client.post(
            "/api/auth/login",
            json={"username_or_email": "cookieuser", "password": "Manager1"},
        )
        self.assertIn("HttpOnly", login.headers.get("set-cookie", ""))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

        blocked = self.client.post(
            "/api/access/wallet",
            json={"walletAddress": "0x1111111111111111111111111111111111111111"},
        )
        self.assertEqual(blocked.status_code, 403, blocked.text)
        allowed = self.client.post(
            "/api/access/wallet",
            headers=self.auth(token),
            json={"walletAddress": "0x1111111111111111111111111111111111111111"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_password_reset_revokes_existing_tokens(self):
        token = self.register_and_login("revokeuser")
        reset = self.client.post(
            "/api/auth/reset-password",
            json={
                "username_or_email": "revokeuser",
                "recovery_code": self.recovery_codes["revokeuser"],
                "new_password": "Manager2",
            },
        )
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertTrue(reset.json()["recoveryCode"].startswith("WCAI-"))
        revoked = self.client.get("/api/access/status", headers=self.auth(token))
        self.assertEqual(revoked.status_code, 401, revoked.text)
        reused = self.client.post(
            "/api/auth/reset-password",
            json={
                "username_or_email": "revokeuser",
                "recovery_code": self.recovery_codes["revokeuser"],
                "new_password": "Manager3",
            },
        )
        self.assertEqual(reused.status_code, 400, reused.text)

    def test_recovery_lookup_does_not_reveal_whether_an_account_exists(self):
        self.register_and_login("recoveryuser")
        existing = self.client.post(
            "/api/auth/forgot-password-question",
            json={"username_or_email": "recoveryuser"},
        )
        missing = self.client.post(
            "/api/auth/forgot-password-question",
            json={"username_or_email": "definitely-missing"},
        )
        self.assertEqual(existing.status_code, 200, existing.text)
        self.assertEqual(existing.json(), missing.json())

    def test_x402_settlement_receipt_cannot_unlock_two_accounts(self):
        wallet = "0x1111111111111111111111111111111111111111"
        receipt = "0x" + "d" * 64
        tokens = [self.register_and_login(name) for name in ("payerone", "payertwo")]
        verification = {
            "verified": True,
            "settled": True,
            "amount": 4.99,
            "currency": "USDC",
            "payer": wallet,
            "receipt": receipt,
            "paymentResponse": "test-payment-response",
        }
        with patch("app.routers.access.get_x402_verifier") as get_verifier:
            get_verifier.return_value.verify_and_settle = AsyncMock(return_value=verification)
            first = self.client.post(
                "/api/access/unlock",
                headers={**self.auth(tokens[0]), "Idempotency-Key": "receipt-replay-first", "PAYMENT-SIGNATURE": "signed-one"},
                json={"mode": "membership", "accessMethod": "x402", "walletAddress": wallet},
            )
            second = self.client.post(
                "/api/access/unlock",
                headers={**self.auth(tokens[1]), "Idempotency-Key": "receipt-replay-second", "PAYMENT-SIGNATURE": "signed-two"},
                json={"mode": "membership", "accessMethod": "x402", "walletAddress": wallet},
            )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 409, second.text)
        self.assertFalse(self.client.get("/api/access/status", headers=self.auth(tokens[1])).json()["membershipActive"])

    def test_security_headers_and_request_size_limit(self):
        health = self.client.get("/health")
        self.assertEqual(health.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(health.headers.get("x-frame-options"), "DENY")
        oversized = self.client.post(
            "/api/auth/login",
            content=b"x" * (settings.max_request_bytes + 1),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(oversized.status_code, 413, oversized.text)

    def test_cctp_requires_saved_matching_wallet_and_is_one_time(self):
        token = self.register_and_login("cctpjudge")
        self.unlock_demo(token)
        wallet = "0x1111111111111111111111111111111111111111"
        other_wallet = "0x2222222222222222222222222222222222222222"

        missing_wallet = self.client.post(
            "/api/cctp/intent",
            headers=self.auth(token),
            json={"walletAddress": wallet, "amount": 20},
        )
        self.assertEqual(missing_wallet.status_code, 400, missing_wallet.text)

        saved = self.client.post(
            "/api/access/wallet",
            headers=self.auth(token),
            json={"walletAddress": wallet},
        )
        self.assertEqual(saved.status_code, 200, saved.text)

        mismatch = self.client.post(
            "/api/cctp/intent",
            headers=self.auth(token),
            json={"walletAddress": other_wallet, "amount": 20},
        )
        self.assertEqual(mismatch.status_code, 400, mismatch.text)

        intent = self.client.post(
            "/api/cctp/intent",
            headers={**self.auth(token), "Idempotency-Key": "real-cctp-intent"},
            json={"walletAddress": wallet, "amount": 20},
        )
        self.assertEqual(intent.status_code, 200, intent.text)
        operation_id = intent.json()["operation"]["operationId"]
        self.assertEqual(intent.json()["config"]["destination"]["domain"], 29)

        with patch("app.routers.cctp.verify_cctp_receipts", new_callable=AsyncMock) as verify:
            verify.return_value = {"burnTxHash": "0x" + "a" * 64, "mintTxHash": "0x" + "b" * 64, "simulated": False}
            bridged = self.client.post(
                "/api/cctp/confirm",
                headers=self.auth(token),
                json={
                    "operationId": operation_id,
                    "walletAddress": wallet,
                    "amount": 20,
                    "burnTxHash": "0x" + "a" * 64,
                    "mintTxHash": "0x" + "b" * 64,
                },
            )
        self.assertEqual(bridged.status_code, 200, bridged.text)
        self.assertFalse(bridged.json()["simulated"])

        repeated = self.client.post(
            "/api/cctp/intent",
            headers={**self.auth(token), "Idempotency-Key": "new-cctp-intent"},
            json={"walletAddress": wallet, "amount": 20},
        )
        self.assertEqual(repeated.status_code, 409, repeated.text)

    def test_cctp_mint_must_match_the_message_attested_for_the_exact_burn(self):
        wallet = "0x1111111111111111111111111111111111111111"
        burn_input = (
            cctp_flow.BURN_SELECTOR
            + f"{20_000_000:064x}"
            + f"{settings.cctp_destination_domain:064x}"
            + wallet[2:].rjust(64, "0")
            + settings.cctp_source_token[2:].lower().rjust(64, "0")
        )
        minted_message = "0x1234"
        mint_input = (
            cctp_flow.MINT_SELECTOR
            + f"{64:064x}"
            + f"{0:064x}"
            + f"{2:064x}"
            + minted_message[2:].ljust(64, "0")
        )
        burn_tx = {"from": wallet, "to": settings.cctp_token_messenger, "input": burn_input}
        mint_tx = {"from": wallet, "to": settings.cctp_message_transmitter, "input": mint_input}

        with patch(
            "app.cctp_flow._confirmed_transaction",
            new=AsyncMock(side_effect=[(burn_tx, {}), (mint_tx, {})]),
        ), patch(
            "app.cctp_flow.get_attestation",
            new=AsyncMock(return_value={"status": "complete", "message": "0xabcd", "attestation": "0x01"}),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(cctp_flow.verify_cctp_receipts(
                    wallet_address=wallet,
                    amount_usdc=20,
                    burn_tx_hash="0x" + "a" * 64,
                    mint_tx_hash="0x" + "b" * 64,
                ))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("not linked", raised.exception.detail)

    def test_supported_formations_produce_exact_position_counts(self):
        expected = {
            "4-3-3": {"GK": 1, "DF": 4, "MF": 3, "FW": 3},
            "4-4-2": {"GK": 1, "DF": 4, "MF": 4, "FW": 2},
            "3-5-2": {"GK": 1, "DF": 3, "MF": 5, "FW": 2},
            "4-2-3-1": {"GK": 1, "DF": 4, "MF": 5, "FW": 1},
            "5-3-2": {"GK": 1, "DF": 5, "MF": 3, "FW": 2},
        }
        players = {player.id: player for player in get_players()}
        for formation, counts in expected.items():
            result = suggest_lineup(formation, strategy="attacking", max_budget=120)
            self.assertEqual(result["formation"], formation)
            self.assertEqual(len(result["starting_player_ids"]), 11)
            self.assertLessEqual(result["budget_used"], 120)
            actual = {position: 0 for position in counts}
            for player_id in result["starting_player_ids"]:
                actual[players[player_id].position] += 1
            self.assertEqual(actual, counts)

    def test_apply_lineup_persists_the_exact_confirmed_ids_and_formation(self):
        token = self.register_and_login("lineupjudge")
        self.unlock_demo(token)
        proposal = suggest_lineup("3-5-2", strategy="attacking", max_budget=100)
        response = self.client.post(
            "/api/squad/apply-lineup",
            headers=self.auth(token),
            json={
                "formation": "3-5-2",
                "startingPlayerIds": proposal["starting_player_ids"],
                "benchPlayerIds": [],
                "reasoning": "Regression test confirmed lineup",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["formation"], "3-5-2")
        self.assertEqual(payload["appliedPlayerIds"], proposal["starting_player_ids"])

        loaded = self.client.get("/api/squad/load", headers=self.auth(token))
        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertEqual(loaded.json()["formation"], "3-5-2")
        saved_ids = [slot["player"]["id"] for slot in loaded.json()["squad"] if slot["player"]]
        self.assertEqual(set(saved_ids), set(proposal["starting_player_ids"]))

    def test_lineup_action_is_idempotent_and_appears_once_in_ledger(self):
        token = self.register_and_login("ledgerlineupjudge")
        self.unlock_demo(token)
        proposal = suggest_lineup("3-5-2", strategy="attacking", max_budget=100)
        payload = {
            "formation": "3-5-2",
            "startingPlayerIds": proposal["starting_player_ids"],
            "benchPlayerIds": [],
            "reasoning": "Idempotent lineup action",
        }
        headers = {**self.auth(token), "Idempotency-Key": "lineup-retry-regression"}
        first = self.client.post("/api/squad/apply-lineup", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.post("/api/squad/apply-lineup", headers=headers, json=payload)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["operation"]["operationId"], second.json()["operation"]["operationId"])
        self.assertEqual(second.json()["operation"]["status"], "confirmed")

        ledger = self.client.get("/api/operations/recent", headers=self.auth(token))
        self.assertEqual(ledger.status_code, 200, ledger.text)
        lineup_actions = [item for item in ledger.json()["operations"] if item["actionType"] == "apply_lineup"]
        self.assertEqual(len(lineup_actions), 1)

        changed_payload = {**payload, "reasoning": "This is a different action payload"}
        conflict = self.client.post("/api/squad/apply-lineup", headers=headers, json=changed_payload)
        self.assertEqual(conflict.status_code, 409, conflict.text)

    def test_save_rejects_partial_or_malformed_starting_layout(self):
        token = self.register_and_login("layoutuser")
        response = self.client.post(
            "/api/squad/save",
            headers=self.auth(token),
            json={"budget": 100, "cctpUsed": False, "formation": "3-5-2", "squad": [], "bench": []},
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_transfer_rejects_duplicate_or_non_persisted_current_squad(self):
        token = self.register_and_login("transferjudge")
        self.unlock_demo(token)
        players = get_players()
        sell = next(player for player in players if player.position == "MF")
        buy = next(player for player in players if player.position == "MF" and player.id != sell.id)

        duplicate = self.client.post(
            "/api/transfers/execute",
            headers=self.auth(token),
            json={
                "sellPlayerId": sell.id,
                "buyPlayerId": buy.id,
                "squadPlayerIds": [sell.id, sell.id],
                "reasoning": "Duplicate request must be rejected",
            },
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.text)

        not_persisted = self.client.post(
            "/api/transfers/execute",
            headers=self.auth(token),
            json={
                "sellPlayerId": sell.id,
                "buyPlayerId": buy.id,
                "squadPlayerIds": [sell.id],
                "reasoning": "Client state cannot invent a squad slot",
            },
        )
        self.assertEqual(not_persisted.status_code, 400, not_persisted.text)

    def test_worldcup_snapshot_exposes_provenance_and_fixture_scope(self):
        snapshot = get_world_cup_snapshot()
        self.assertEqual(snapshot["tournament"], "FIFA World Cup 2026")
        self.assertEqual(snapshot["playerCount"], 1248)
        self.assertEqual(len(snapshot["teams"]), 48)
        self.assertEqual(sorted(Counter(player.team for player in get_players()).values()), [26] * 48)
        self.assertEqual(len(snapshot["matches"]), 2)
        self.assertTrue(snapshot["snapshotDate"])
        self.assertTrue(snapshot["sourceUrls"])
        self.assertTrue(all(match["stage"] == "Semi-final" for match in snapshot["matches"]))
        self.assertTrue(all(match["result"] is None for match in snapshot["matches"]))

    def test_player_intel_separates_model_signals_from_verified_snapshot_data(self):
        player = get_players()[0]
        response = self.client.get(f"/api/players/{player.id}/intel")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["player"]["id"], player.id)
        self.assertTrue(payload["model"]["isEstimate"])
        self.assertEqual(len(payload["model"]["metrics"]), 5)
        self.assertEqual(len(payload["model"]["trend"]), 5)
        self.assertIn(payload["verified"]["tournamentStats"]["data_status"], {"verified", "not_available"})
        self.assertEqual(payload["verified"]["officialProfile"]["team"], player.team)
        self.assertEqual(payload["verified"]["officialProfile"]["shirtNumber"], player.number)
        self.assertIn(player.name, payload["model"]["scoutBrief"])
        self.assertNotIn("based on position and official FIFA final-squad membership", payload["model"]["scoutBrief"])
        self.assertIn("WCAI scouting estimates", payload["provenance"]["notice"])

    def test_live_goal_assist_overlay_marks_every_rostered_player_with_a_tally(self):
        messi = next(player for player in get_players() if "Messi" in player.name)
        players = apply_live_player_totals({
            "available": True,
            "updated_at": "2026-07-16T19:00:00Z",
            "source_url": "https://example.test/live-events",
            "fifa_source_url": "https://example.test/fifa-stats",
            "events_processed": 102,
            "totals": {"lionelmessi": {"goals": 8, "assists": 4}},
        })
        refreshed_messi = next(player for player in players if player.id == messi.id)
        self.assertEqual(refreshed_messi.world_cup_stats.goals, 8)
        self.assertEqual(refreshed_messi.world_cup_stats.assists, 4)
        self.assertTrue(all(player.world_cup_stats.data_status == "verified" for player in players))

    def test_agent_conversation_never_builds_a_lineup_and_named_replacement_is_single_player(self):
        agent = GeminiAgentClient()
        cubarsi = next(player for player in get_players() if "Cubars" in player.name)
        squad_ids = [cubarsi.id]

        self.assertEqual(
            agent._classify_intent(f"{cubarsi.name} yerine kimi koyabilirim, sevmiyorum onu", squad_ids),
            "targeted_transfer",
        )
        self.assertEqual(
            agent._classify_intent("Ingiltere Arjantin macini kim yener, kadroma kimi almaliyim?", squad_ids),
            "conversation",
        )

        replacement = agent._extract_targeted_transfer_action(
            f"{cubarsi.name} yerine kimi koyabilirim", squad_ids, 100
        )
        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.type, "transfer")
        self.assertEqual(replacement.sellPlayerId, cubarsi.id)
        self.assertNotEqual(replacement.buyPlayerId, cubarsi.id)

        discussion = agent._rule_based_fallback(
            "Ingiltere Arjantin macini kim yener, kadroma kimi almaliyim?",
            squad_ids,
            True,
        )
        self.assertIsNone(discussion.suggestedAction)
        self.assertIn("conversational preview", discussion.message.lower())

        global_discussion = agent._rule_based_fallback(
            "Brezilya Japonya macini kim yener, kimi almaliyim?", [], True
        )
        self.assertIsNone(global_discussion.suggestedAction)
        self.assertIn("Brazil vs Japan", global_discussion.message)

    def test_tournament_hq_endpoint_exposes_schedule_and_roster_provenance(self):
        async def fake_overview(force_refresh=False):
            return {
                "mode": "live_community_feed",
                "updatedAt": "2026-07-15T10:00:00Z",
                "teams": [],
                "groups": [],
                "matches": [],
                "rosters": [],
                "stageOrder": {"group": 0},
                "sources": {
                    "liveSchedule": "community-feed",
                    "localRoster": {},
                    "notice": "Community schedule; dated roster snapshot.",
                },
            }

        with patch("app.routers.worldcup.get_tournament_overview", new=fake_overview):
            response = self.client.get("/api/worldcup/tournament?refresh=true")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "live_community_feed")
        self.assertEqual(payload["sources"]["liveSchedule"], "community-feed")

    def test_matchday_brief_is_source_aware_and_budget_valid(self):
        token = self.register_and_login("briefuser")
        response = self.client.get(
            "/api/worldcup/matchday-brief?formation=3-5-2",
            headers=self.auth(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["briefType"], "wcai_matchday_brief")
        self.assertEqual(payload["lineup"]["formation"], "3-5-2")
        self.assertEqual(len(payload["lineup"]["playerIds"]), 11)
        self.assertLessEqual(payload["lineup"]["budgetUsed"], payload["lineup"]["maxBudget"])
        self.assertIn(payload["dataConfidence"], {"low", "medium", "high"})
        self.assertTrue(payload["sourceUrls"])
        self.assertEqual(len(payload["scenarios"]), 2)

    def test_tactical_lab_is_premium_and_returns_non_mutating_comparison(self):
        token = self.register_and_login("labuser")
        locked = self.client.post(
            "/api/tactical-lab/compare",
            headers=self.auth(token),
            json={"formation": "3-5-2", "strategy": "attacking"},
        )
        self.assertEqual(locked.status_code, 402, locked.text)

        # Every reviewer uses the same explicit, time-boxed demo checkout.
        token = self.register_and_login("tacticaljudge")
        self.unlock_demo(token)
        response = self.client.post(
            "/api/tactical-lab/compare",
            headers=self.auth(token),
            json={
                "formation": "3-5-2",
                "strategy": "attacking",
                "matchContext": "France Spain",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["feature"], "what_if_tactical_lab")
        self.assertEqual(len(payload["comparisons"]), 5)
        self.assertIn("baseline", payload)
        self.assertIn(payload["recommended"]["status"], {"ready", "unavailable"})
        self.assertIn("do not mutate", payload["notice"])


if __name__ == "__main__":
    unittest.main()
