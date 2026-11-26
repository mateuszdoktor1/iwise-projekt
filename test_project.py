import math
import unittest
from itertools import pairwise
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

import fis
import profiles
from simulation import PROFILES, SEGMENT_SECONDS, download_time, metrics, policies, simulate


POLICIES = policies()


class FuzzyTests(unittest.TestCase):
    def test_nine_rules_at_anchors(self):
        expected = [[0.5, 1, 1], [0.5, 2, 2], [0.5, 2, 4]]
        for i, buffer in enumerate((4, 8, 12)):
            for j, speed in enumerate((1, 3, 5)):
                decision = fis.infer(speed, buffer)
                self.assertAlmostEqual(decision.target, expected[i][j])
                self.assertEqual(decision.rate, expected[i][j])

    def test_four_active_rules(self):
        result = fis.infer(4, 10)
        np.testing.assert_allclose(result.strengths[1:, 1:], 0.25)
        self.assertAlmostEqual(result.target, (2 + 2 + 2 + 4) / 4)
        self.assertEqual(result.rate, 2)

    def test_domain_and_monotonicity(self):
        surface = []
        for buffer in np.linspace(0, 16, 33):
            row = []
            for speed in np.linspace(0, 8, 33):
                d = fis.infer(speed, buffer)
                self.assertAlmostEqual(d.strengths.sum(), 1)
                self.assertAlmostEqual(d.target, float((d.strengths * fis.RULES).sum()))
                self.assertGreater(d.aggregate.max(), 0)
                self.assertLessEqual(d.aggregate.max(), 1 + 1e-12)
                self.assertGreaterEqual(d.target, 0.5 - 1e-12)
                self.assertLessEqual(d.target, 4 + 1e-12)
                row.append(d.target)
            surface.append(row)
        for axis in (0, 1):
            self.assertTrue(np.all(np.diff(surface, axis=axis) >= -1e-10))

    def test_input_limits(self):
        self.assertEqual(fis.infer(0, 0).rate, 0.5)
        self.assertEqual(fis.infer(80, 16).rate, 4)
        for args in ((-1, 0), (2, -1), (2, 17), (math.inf, 0), (1, math.nan)):
            with self.assertRaises(ValueError):
                fis.infer(*args)

    def test_discrete_choice(self):
        self.assertEqual(fis.available_rate(3.1), 2)
        self.assertEqual(fis.available_rate(0.3), 0.5)
        self.assertEqual(fis.available_rate(4 - 1e-15), 4)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(profiles, "PROFILE_DIR", self.directory))

    def test_save_list_and_load(self):
        path = profiles.add_profile("Mój-test", ["0:5", "20:1,2", "55:4"], "4")
        self.assertTrue(path.is_file())
        self.assertIn("mój-test", profiles.profile_names())
        profile = profiles.load_profile("MÓJ-test")
        self.assertEqual(profile.points, [(0, 5), (20, 1.2), (55, 4)])
        self.assertEqual(profile.fixed_rate, 4)
        log = simulate(profile.points, policies(profile.fixed_rate)["Stałe 4"], count=3)
        self.assertEqual([segment.rate for segment in log], [0.5, 4, 4])

    def test_legacy_profile_uses_default_fixed_rate(self):
        (self.directory / "starszy.txt").write_text("0:5\n20:1.2\n", encoding="utf-8")
        profile = profiles.load_profile("starszy")
        self.assertEqual(profile.points, [(0, 5), (20, 1.2)])
        self.assertEqual(profile.fixed_rate, 2)

    def test_conflicts_preserve_profiles(self):
        profiles.add_profile("nowy", ["0:1"])
        for name in ("Nowy", "SPADEK"):
            with self.assertRaises(ValueError):
                profiles.add_profile(name, ["0:6"])
        self.assertEqual(profiles.load_profile("nowy").points, [(0, 1)])
        self.assertEqual(profiles.load_profile("spadek").points, PROFILES["spadek"])

    def test_invalid_arguments_leave_no_file(self):
        for points in ([], ["0-5"], ["1:5"], ["0:0"], ["0:5", "0:2"], ["0:inf"], ["0:2", "nan:2"]):
            with self.assertRaises(ValueError):
                profiles.add_profile("test", points)
        with self.assertRaises(ValueError):
            profiles.add_profile("../poza", ["0:3"])
        with self.assertRaisesRegex(ValueError, "stały wariant"):
            profiles.add_profile("test", ["0:3"], "3")
        self.assertEqual(list(self.directory.iterdir()), [])
        with self.assertRaisesRegex(ValueError, "Nie znaleziono"):
            profiles.load_profile("brak")


class PlaybackTests(unittest.TestCase):
    def test_all_fixed_policies_use_their_own_rates(self):
        variants = policies(all_fixed=True)
        self.assertEqual(len(variants), 5)
        for rate in (0.5, 1, 2, 4):
            log = simulate([(0, 6)], variants[f"Stałe {rate:g}"], count=2)
            self.assertEqual([segment.rate for segment in log], [0.5, rate])

    def test_download_across_changes_and_at_boundary(self):
        profile = [(0, 4), (2, 1), (4, 2)]
        self.assertEqual(download_time(profile, 1, 10), 5)
        self.assertEqual(download_time(profile, 2, 1), 1)
        self.assertEqual(download_time(profile, 0, 8), 2)

    def test_startup_and_stall_by_hand(self):
        log = simulate([(0, 1)], POLICIES["Stałe 2"], count=2)
        # 2 Mb w 2 s przed startem, następnie 8 Mb w 8 s przy 4 s zapasu.
        self.assertEqual(log[0].stall, 0)
        self.assertEqual(log[1].buffer_before, 4)
        self.assertEqual(metrics(log), dict(start_s=2, zatrzymania_s=4, srednia_Mb_s=1.25, zmiany=1))

    def test_first_decision_uses_only_last_completed_transfer(self):
        fast = simulate([(0, 6)], POLICIES["FIS"], count=2)
        slow = simulate([(0, 6), (0.5, 0.1)], POLICIES["FIS"], count=2)
        self.assertEqual(fast[1].estimated_speed, slow[1].estimated_speed)
        self.assertEqual(fast[1].rate, slow[1].rate)
        self.assertGreater(slow[1].stall, fast[1].stall)

    def test_buffer_and_playback_clock(self):
        for profile in PROFILES.values():
            for policy in POLICIES.values():
                log = simulate(profile, policy)
                for s in log:
                    self.assertLessEqual(s.buffer_before, 16)
                    self.assertLessEqual(s.buffer_after, 20)
                for a, b in pairwise(log):
                    self.assertGreaterEqual(b.start, a.end)
                    self.assertAlmostEqual(b.buffer_before, a.buffer_after - (b.start - a.end))
                    self.assertAlmostEqual(b.estimated_speed, a.rate * SEGMENT_SECONDS / (a.end - a.start))
                finish = log[-1].end + log[-1].buffer_after
                self.assertAlmostEqual(finish, len(log)*SEGMENT_SECONDS + log[0].end + sum(s.stall for s in log))


if __name__ == "__main__":
    unittest.main()
