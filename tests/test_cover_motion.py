"""Cover travel state and time-based position."""

import importlib.util
import sys
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "cover_motion.py"
    )
    spec = importlib.util.spec_from_file_location("cover_motion", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cover_motion"] = module
    spec.loader.exec_module(module)
    return module


cm = _load()
RUN = 20.0


class StatusTest(unittest.TestCase):
    def test_status_is_a_position(self) -> None:
        self.assertEqual(cm.cover_position_from_status(0), 0)
        self.assertEqual(cm.cover_position_from_status(100), 100)
        self.assertEqual(cm.cover_position_from_status(37), 37)
        self.assertIsNone(cm.cover_position_from_status(0xFF))
        self.assertIsNone(cm.cover_position_from_status(101))


class ReportTest(unittest.TestCase):
    def test_report_while_stopped_sets_the_position(self) -> None:
        travel = cm.CoverTravel()
        self.assertFalse(travel.report(0, 0.0))
        self.assertEqual(travel.position, 0)
        self.assertTrue(travel.is_closed())
        travel.report(40, 1.0)
        self.assertFalse(travel.is_closed())

    def test_unknown_report_clears_a_stopped_position(self) -> None:
        travel = cm.CoverTravel(position=60, closed=False)
        travel.report(None, 0.0)
        self.assertIsNone(travel.position)
        self.assertIsNone(travel.closed)
        self.assertIsNone(travel.is_closed())

    def test_unknown_report_clears_a_closed_state(self) -> None:
        travel = cm.CoverTravel(position=0, closed=True)
        travel.report(None, 0.0)
        self.assertIsNone(travel.position)
        self.assertIsNone(travel.is_closed())

    def test_end_report_finishes_a_run(self) -> None:
        travel = cm.CoverTravel(position=30)
        travel.start(cm.MOTION_UP, 0.0, RUN)
        self.assertTrue(travel.report(100, 14.0))
        self.assertEqual(travel.motion, cm.MOTION_STOP)
        self.assertEqual(travel.position, 100)

    def test_report_during_a_run_rebases_it(self) -> None:
        travel = cm.CoverTravel(position=100)
        travel.start(cm.MOTION_DOWN, 0.0, RUN)
        self.assertFalse(travel.report(100, 1.0))
        self.assertEqual(travel.motion, cm.MOTION_DOWN)
        self.assertEqual(travel.position_at(6.0, RUN), 75)


class TravelTest(unittest.TestCase):
    def test_unknown_position_needs_a_full_run(self) -> None:
        travel = cm.CoverTravel()
        travel.start(cm.MOTION_DOWN, 0.0, RUN)
        travel.stop(10.0, RUN)
        self.assertIsNone(travel.position)
        travel.start(cm.MOTION_DOWN, 20.0, RUN)
        travel.stop(41.0, RUN)
        self.assertEqual(travel.position, 0)
        self.assertTrue(travel.is_closed())

    def test_partial_run_from_known_position(self) -> None:
        travel = cm.CoverTravel(position=0, closed=True)
        travel.start(cm.MOTION_UP, 0.0, RUN)
        self.assertEqual(travel.position_at(5.0, RUN), 25)
        self.assertFalse(travel.is_closed())
        travel.stop(5.0, RUN)
        self.assertEqual(travel.position, 25)
        self.assertFalse(travel.is_closed())

    def test_position_is_clamped(self) -> None:
        travel = cm.CoverTravel(position=90)
        travel.start(cm.MOTION_UP, 0.0, RUN)
        travel.stop(30.0, RUN)
        self.assertEqual(travel.position, 100)

    def test_reverse_settles_the_first_run(self) -> None:
        travel = cm.CoverTravel(position=100, closed=False)
        travel.start(cm.MOTION_DOWN, 0.0, RUN)
        travel.start(cm.MOTION_UP, 4.0, RUN)
        self.assertEqual(travel.position, 80)
        self.assertEqual(travel.motion, cm.MOTION_UP)

    def test_same_direction_keeps_the_start(self) -> None:
        travel = cm.CoverTravel(position=100)
        travel.start(cm.MOTION_DOWN, 0.0, RUN)
        self.assertFalse(travel.start(cm.MOTION_DOWN, 3.0, RUN))
        self.assertEqual(travel.started_at, 0.0)

    def test_without_run_time_only_open_or_closed(self) -> None:
        travel = cm.CoverTravel()
        travel.start(cm.MOTION_DOWN, 0.0, None)
        self.assertEqual(travel.motion, cm.MOTION_STOP)
        self.assertTrue(travel.is_closed())
        self.assertIsNone(travel.position_at(5.0, None))
        travel.start(cm.MOTION_UP, 1.0, None)
        self.assertFalse(travel.is_closed())

    def test_seconds_to_target(self) -> None:
        travel = cm.CoverTravel(position=60)
        self.assertAlmostEqual(travel.seconds_to(35, RUN), 5.0)


if __name__ == "__main__":
    unittest.main()
