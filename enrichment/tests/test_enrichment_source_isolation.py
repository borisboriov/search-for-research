"""Source isolation without real HTTP/model transports."""

import asyncio
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import test_enrichment_assisted as helpers

from sfr_enrichment.common import read
from sfr_enrichment.evidence import immutable_json
from sfr_enrichment.runner import prepare, run


class IsolationTests(unittest.TestCase):
    base: Path
    root: Path
    scope: dict[str, Any]
    profiles: list[dict[str, Any]]
    plan: dict[str, Any]

    def setUp(self) -> None:
        self.fixture = helpers.AssistedTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base, self.root = self.fixture.base, self.fixture.root
        self.scope, self.profiles, self.plan = (
            self.fixture.scope,
            self.fixture.profiles,
            self.fixture.plan,
        )

    def fake_native(
        self, directory: Path, prompt: str, *args: object, **kwargs: object
    ) -> tuple[Path, dict[str, Any]]:
        return self.fixture.fake_native(directory, prompt, *args, **kwargs)

    def configure(self, *, alternative: bool = True, cap: int = 20) -> None:
        self.root = self.base / ("case-" + str(len(list(self.base.iterdir()))))
        self.scope.update(HTTP_total_cap=cap, HTTP_per_profile_cap=8)
        self.plan["profiles"][0]["sources"] = [
            self.spec("https://bad.example/a"),
            self.spec("https://bad.example/b"),
        ]
        if alternative:
            self.plan["profiles"][0]["sources"].append(self.spec("https://good.example/a"))
        self.plan["profiles"][1]["sources"] = [self.spec("https://other.example/b")]
        for name, value in [
            ("profiles", self.profiles),
            ("plan", self.plan),
            ("scope", self.scope),
        ]:
            immutable_json(self.root.parent / (self.root.name + "-" + name + ".json"), value)
        prepare(
            self.root,
            *(
                self.root.parent / (self.root.name + "-" + n + ".json")
                for n in ["profiles", "plan", "scope"]
            ),
        )

    @staticmethod
    def spec(url: str) -> dict[str, Any]:
        return {
            "url": url,
            "kind": "direct_http",
            "discovery": {
                "method": "agent_search",
                "observed_url": url,
                "query": "fixture",
                "note": "offline",
            },
        }

    def invoke(self, mode: str = "connect") -> tuple[Path, list[str], int]:
        calls: list[str] = []

        def response(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if request.url.host == "bad.example":
                if mode in ("empty", "identity"):
                    if request.url.path == "/robots.txt":
                        return httpx.Response(
                            200,
                            text="User-agent: *\nAllow: /",
                            headers={"content-type": "text/plain"},
                        )
                    body = "<html></html>" if mode == "empty" else "<h1>Jane Example</h1>"
                    return httpx.Response(200, text=body, headers={"content-type": "text/html"})
                if mode == "unknown":
                    raise RuntimeError("programming defect")
                if mode == "unsafe":
                    raise ValueError("unsafe destination invariant")
                if mode == "connect":
                    raise httpx.ConnectError("fixture", request=request)
                if mode in ("403", "429"):
                    return httpx.Response(
                        int(mode), text="blocked", headers={"content-type": "text/plain"}
                    )
                return httpx.Response(
                    200, text="User-agent: *\nDisallow: /", headers={"content-type": "text/plain"}
                )
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
                )
            return httpx.Response(
                200,
                text='<h1>Jane Example</h1><a href="mailto:jane@example.edu">Email</a>',
                headers={"content-type": "text/html;charset=utf-8"},
            )

        client = httpx.AsyncClient
        with (
            patch(
                "sfr_enrichment.sources.socket.getaddrinfo",
                return_value=[(0, 0, 0, "", ("8.8.8.8", 443))],
            ),
            patch(
                "sfr_enrichment.sources.httpx.AsyncClient",
                side_effect=lambda **kw: client(transport=httpx.MockTransport(response), **kw),
            ),
            patch("sfr_enrichment.contacts.Budget.wait", new_callable=AsyncMock),
            patch("sfr_enrichment.native.execute", side_effect=self.fake_native) as native,
        ):
            result = asyncio.run(run(self.root, 90))
            return result, calls, native.call_count

    def test_connect_robots_preserves_receipt_and_continues_sources_and_people(self) -> None:
        self.configure()
        _, calls, jobs = self.invoke()
        self.assertEqual(calls.count("https://bad.example/robots.txt"), 1)
        self.assertFalse(
            any(u in calls for u in ["https://bad.example/a", "https://bad.example/b"])
        )
        self.assertIn("https://good.example/a", calls)
        self.assertIn("https://other.example/b", calls)
        self.assertEqual(jobs, 2)
        failures = [read(p) for p in (self.root / "source-failures/A1").glob("*.json")]
        self.assertEqual({r["status"] for r in failures}, {"failed", "skipped"})
        failure = next(r for r in failures if r["status"] == "failed")
        self.assertEqual(read(Path(failure["receipt_path"]))["error"], "ConnectError")
        self.assertTrue((self.root / "completed-progress.json").exists())

    def test_robots_denied_and_domain_403_429_never_fetch_target_or_repeat(self) -> None:
        for mode in ("robots", "403", "429"):
            with self.subTest(mode=mode):
                self.configure()
                _, calls, jobs = self.invoke(mode)
                self.assertEqual(
                    [u for u in calls if "bad.example" in u], ["https://bad.example/robots.txt"]
                )
                self.assertEqual(jobs, 2)
                self.assertEqual(len(list((self.root / "domain-stops").glob("*.json"))), 1)

    def test_no_usable_source_is_failed_profile_not_empty_success(self) -> None:
        self.configure(alternative=False)
        _, _calls, jobs = self.invoke()
        self.assertEqual(jobs, 1)
        self.assertEqual(read(self.root / "profile-failures/A1.json")["status"], "no_usable_source")
        self.assertFalse((self.root / "results/A1.json").exists())
        self.assertTrue((self.root / "results/A2.json").exists())

    def test_empty_source_skips_model_but_identity_only_evidence_is_verified(self) -> None:
        self.configure(alternative=False)
        _, _calls, jobs = self.invoke("empty")
        self.assertEqual(jobs, 1)
        self.assertFalse((self.root / "results/A1.json").exists())
        self.assertEqual(read(self.root / "profile-failures/A1.json")["status"], "no_usable_source")
        self.configure(alternative=False)
        _, _calls, jobs = self.invoke("identity")
        self.assertEqual(jobs, 2)
        self.assertEqual(read(self.root / "results/A1.json")["result"]["items"], [])

    def test_global_budget_and_unknown_or_unsafe_errors_still_abort(self) -> None:
        for mode in ("unknown", "unsafe"):
            with self.subTest(mode=mode):
                self.configure()
                with self.assertRaises((RuntimeError, ValueError)):
                    self.invoke(mode)
                self.assertFalse((self.root / "results/A2.json").exists())
                self.assertFalse((self.root / "source-failures").exists())
        self.configure(cap=1)
        with self.assertRaisesRegex(ValueError, "Frozen HTTP budget"):
            self.invoke("connect")
        self.assertFalse((self.root / "results/A2.json").exists())
