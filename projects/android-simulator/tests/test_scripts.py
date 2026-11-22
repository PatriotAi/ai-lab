"""Тести розбору: на «зламаному» стані мають ловити, на чистому — мовчати."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import plan  # noqa: E402
import report  # noqa: E402
import tap_text  # noqa: E402
import urltools  # noqa: E402
import redact_logs  # noqa: E402

CRASH = """11-17 10:00:00.000 E/AndroidRuntime( 1234): FATAL EXCEPTION: main
11-17 10:00:00.000 E/AndroidRuntime( 1234): Process: org.example.app, PID: 1234
11-17 10:00:00.000 E/AndroidRuntime( 1234): java.lang.NullPointerException: boom
"""
OTHER_CRASH = CRASH.replace("org.example.app", "com.other.thing")


class Problems(unittest.TestCase):
    def test_crash_of_target_is_caught(self):
        r = report.find_problems(CRASH, "", "", "org.example.app")
        self.assertEqual(r["crashes"], 1)
        self.assertIn("NullPointerException", r["first_crash"])

    def test_foreign_crash_is_ignored(self):
        r = report.find_problems(OTHER_CRASH, "", "", "org.example.app")
        self.assertEqual((r["crashes"], r["first_crash"]), (0, ""))

    def test_anr_and_monkey(self):
        r = report.find_problems("", "E/ActivityManager: ANR in org.example.app (x)",
                                 "// CRASH: org.example.app (pid 1)\n// NOT RESPONDING: org.example.app", "org.example.app")
        self.assertEqual((r["crashes"], r["anrs"]), (1, 2))

    def test_clean_is_silent(self):
        r = report.find_problems("", "I/ActivityManager: Start proc", "Events injected: 300", "org.example.app")
        self.assertEqual((r["crashes"], r["anrs"]), (0, 0))

    def test_verdict(self):
        ok = {"installed": True, "launched": True, "flow_rc": "0", "crashes": 0, "anrs": 0}
        self.assertEqual(report.failed(ok, True), [])
        self.assertTrue(report.failed({**ok, "crashes": 1}, True))
        self.assertEqual(report.failed({**ok, "crashes": 1}, False), [])
        self.assertTrue(report.failed({**ok, "flow_rc": "1"}, True))
        self.assertTrue(report.failed({"installed": False}, True))


class Plan(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(plan.classify_target("https://x.org/a.apk?dl=1")["kind"], "app")
        self.assertEqual(plan.classify_target("https://x.org/")["kind"], "web")
        self.assertEqual(plan.classify_target("fdroid:org.fdroid.fdroid")["source"], "fdroid")
        a = plan.classify_target("artifact:my-apk@123")
        self.assertEqual((a["artifact_name"], a["artifact_run_id"]), ("my-apk", "123"))

    def test_rejects_bad_input(self):
        for bad in ["", "file:///etc/passwd", "https://a b", "fdroid:../x", "artifact:a;rm", "https://x\nrun"]:
            with self.assertRaises(plan.PlanError, msg=bad):
                plan.classify_target(bad)
        with self.assertRaises(plan.PlanError):
            plan.normalize({"target": "https://x.org", "flow": "../../etc"}, 0)
        with self.assertRaises(plan.PlanError):
            plan.normalize({"target": "https://x.org", "android": "9; rm"}, 0)

    def test_secret_in_form_is_rejected(self):
        for u in ["https://s.vercel.app/?a=1&_vercel_share=TOPSECRET",
                  "https://s.vercel.app/?x-vercel-protection-bypass=K"]:
            with self.assertRaises(plan.PlanError) as e:
                plan.normalize({"target": u}, 0)
            self.assertNotIn("TOPSECRET", str(e.exception))
        self.assertEqual(plan.normalize({"target": "https://s.vercel.app/?a=1"}, 0)["target"],
                         "https://s.vercel.app/?a=1")

    def test_selftest_file_is_valid(self):
        runs = plan.build("push", {}, Path(plan.__file__).resolve().parent.parent / "selftest.json")
        self.assertGreaterEqual(len(runs), 2)


class TapText(unittest.TestCase):
    XML = ('<?xml version="1.0"?><hierarchy><node index="0" text="" content-desc="Got it" '
           'bounds="[0,0][100,50]"/><node text="Accept &amp; continue" bounds="[10,20][110,60]"/></hierarchy>')

    def test_finds_button_in_priority_order(self):
        self.assertEqual(tap_text.find(self.XML, ["Accept & continue", "Got it"]), (60, 40))
        self.assertEqual(tap_text.find(self.XML, ["got it"]), (50, 25))

    def test_no_match_and_garbage(self):
        self.assertIsNone(tap_text.find(self.XML, ["Nope"]))
        self.assertIsNone(tap_text.find("<<<not xml", ["Got it"]))


class Redact(unittest.TestCase):
    def test_masks_secret_like_values(self):
        # Значення збираються під час запуску, щоб у коді не лежало нічого
        # схожого на ключ (інакше сканер секретів справедливо червоніє).
        fake = "".join(["W3sP", "0k9xZ2", "Lm8QbT"])
        line = "D/DhcpClient(  917): l2" + "key: " + fake + " lease address: /10.0.2.16"
        out, n = redact_logs.redact_text(line)
        self.assertEqual(n, 1)
        self.assertNotIn(fake, out)
        self.assertIn("lease address", out)
        out, n = redact_logs.redact_text("api_" + "token=" + '"' + "abcd1234" + "efgh5678ijkl" + '"')
        self.assertEqual(n, 1)

    def test_leaves_names_and_plain_text(self):
        for line in ["Preferences: unsupported " + "key: " + "enable_feature_toggle_x",
                     "initializeKeyboardTheme(): Apply keyboard theme 2026",
                     "token count 42"]:
            out, n = redact_logs.redact_text(line)
            self.assertEqual((out, n), (line, 0), line)


class Conditions(unittest.TestCase):
    def test_valid_and_dedup(self):
        run = plan.normalize({"target": "https://x.org", "conditions": "dark, big-font,dark"}, 0)
        self.assertEqual(run["conditions"], "dark,big-font")

    def test_rejects_unknown_and_conflict(self):
        for bad in ["dark;reboot", "flood", "locale-uk,locale-en"]:
            with self.assertRaises(plan.PlanError, msg=bad):
                plan.normalize({"target": "https://x.org", "conditions": bad}, 0)

    def test_condition_not_applied_fails_verdict(self):
        ok = {"installed": True, "launched": True, "flow_rc": "", "crashes": 0, "anrs": 0}
        self.assertEqual(report.failed({**ok, "conditions": [{"name": "dark", "ok": True, "detail": ""}]}, True), [])
        self.assertTrue(report.failed({**ok, "conditions": [{"name": "offline", "ok": False, "detail": "x"}]}, True))


class Scrub(unittest.TestCase):
    def test_scrub_removes_secret(self):
        with tempfile.TemporaryDirectory() as d:
            u, f = os.path.join(d, "u"), os.path.join(d, "log")
            Path(u).write_text("https://s.vercel.app/?x-vercel-protection-bypass=K3Y&x-vercel-set-bypass-cookie=true")
            Path(f).write_text("GET /?x-vercel-protection-bypass=K3Y ok")
            urltools.scrub(u, [f, os.path.join(d, "missing")])
            self.assertNotIn("K3Y", Path(f).read_text())


if __name__ == "__main__":
    unittest.main()
