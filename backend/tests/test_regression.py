import base64
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.agent.gemini_client import GeminiAgentClient
from app.agent.skills import suggest_lineup
from app.config import settings
from app.data import apply_live_player_totals, get_players, get_world_cup_snapshot
from app.main import app
from app.mcp import client as mcp_module


class AutoGafferRegressionTests(unittest.TestCase):
    """High-value API contracts that must stay true during hackathon changes."""

    @classmethod
    def setUpClass(cls):
        cls._original_db_file = db.DB_FILE
        cls._temp_dir = tempfile.TemporaryDirectory()
        db.DB_FILE = Path(cls._temp_dir.name) / "auth.db"
        cls.client = TestClient(app)
        cls._original_settings = {
            "x402_demo_mode": settings.x402_demo_mode,
            "x402_allow_simulated_purchases": settings.x402_allow_simulated_purchases,
            "mcp_simulation": settings.mcp_simulation,
            "live_stats_enabled": settings.live_stats_enabled,
            "live_event_feed_enabled": settings.live_event_feed_enabled,
        }
        settings.x402_demo_mode = True
        settings.x402_allow_simulated_purchases = False
        settings.mcp_simulation = True
        settings.live_stats_enabled = False
        settings.live_event_feed_enabled = False
        mcp_module._mcp_client = None

    @classmethod
    def tearDownClass(cls):
        db.DB_FILE = cls._original_db_file
        for name, value in cls._original_settings.items():
            setattr(settings, name, value)
        mcp_module._mcp_client = None
        cls._temp_dir.cleanup()

    def setUp(self):
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
                "security_question": "club",
                "security_answer": "injective",
            },
        )
        self.assertEqual(register.status_code, 200, register.text)
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
            json={"mode": "membership", "hasPaidX402": False},
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

    def test_kaan_demo_membership_is_free_but_explicit_and_persistent(self):
        token = self.register_and_login("Kaan")
        before = self.client.get("/api/access/status", headers=self.auth(token)).json()
        self.assertFalse(before["membershipActive"])

        self.unlock_demo(token)
        after = self.client.get("/api/access/status", headers=self.auth(token)).json()
        self.assertTrue(after["membershipActive"])
        self.assertTrue(after["hasAiAccess"])
        self.assertEqual(after["accessSource"], "kaan_demo")

    def test_access_unlock_has_a_replay_safe_x402_ledger_receipt(self):
        token = self.register_and_login("Kaan")
        headers = {**self.auth(token), "Idempotency-Key": "demo-access-retry-regression"}
        payload = {"mode": "membership", "hasPaidX402": False}
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
            json={"mode": "membership", "hasPaidX402": True},
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

    def test_cctp_requires_saved_matching_wallet_and_is_one_time(self):
        token = self.register_and_login("Kaan")
        self.unlock_demo(token)
        wallet = "0x1111111111111111111111111111111111111111"
        other_wallet = "0x2222222222222222222222222222222222222222"

        missing_wallet = self.client.post(
            "/api/cctp",
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
            "/api/cctp",
            headers=self.auth(token),
            json={"walletAddress": other_wallet, "amount": 20},
        )
        self.assertEqual(mismatch.status_code, 400, mismatch.text)

        bridged = self.client.post(
            "/api/cctp",
            headers=self.auth(token),
            json={"walletAddress": wallet, "amount": 20},
        )
        self.assertEqual(bridged.status_code, 200, bridged.text)
        self.assertTrue(bridged.json()["simulated"])

        repeated = self.client.post(
            "/api/cctp",
            headers=self.auth(token),
            json={"walletAddress": wallet, "amount": 20},
        )
        self.assertEqual(repeated.status_code, 409, repeated.text)

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
        token = self.register_and_login("Kaan")
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
        token = self.register_and_login("Kaan")
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
        token = self.register_and_login("Kaan")
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

        # The free demo flag is intentionally limited to the Kaan account;
        # use a fresh Kaan token to exercise the entitled path.
        token = self.register_and_login("Kaan")
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
