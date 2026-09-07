# Copyright (C) 2026 Thermetery Technology Co Limited
# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from nvbackend import GPU

class KeplerTests(unittest.TestCase):
    def test_max_without_curve_does_not_partially_apply(self):
        from druta import Druta
        app = Druta.__new__(Druta)
        app.guard = Mock(return_value=True)
        app.gpu = SimpleNamespace(static={}, set_fan=Mock(), set_voltage_boost=Mock())
        app.vf_points = []
        app.vf_read = Mock()
        app.log = Mock()
        app.autosave_before = Mock()
        app.oc_max()
        app.gpu.set_fan.assert_not_called()
        app.gpu.set_voltage_boost.assert_not_called()
        app.autosave_before.assert_not_called()

    def test_clock_grid_uses_upper_regime(self):
        gpu = GPU.__new__(GPU)
        # Low divider regime followed by fractional 13 MHz boost bins.
        clocks = list(range(136, 406, 2)) + [round(419 + i * 13.05) for i in range(61)]
        gpu.lockable_clocks_by_mem = Mock(return_value=[(3505, clocks)])
        self.assertAlmostEqual(gpu.clock_step_khz(), 13050, delta=20)

    def test_uniform_pascal_and_turing_grids_are_preserved(self):
        for step in (12657, 15000):
            gpu = GPU.__new__(GPU)
            clocks = [round(139 + i * step / 1000) for i in range(141)]
            gpu.lockable_clocks_by_mem = Mock(return_value=[(1000, clocks)])
            self.assertAlmostEqual(gpu.clock_step_khz(), step, delta=5)

    def test_kepler_zero_getter_cannot_enable_private_writes(self):
        gpu = GPU.__new__(GPU)
        gpu.arch = Mock(return_value=2)
        gpu.nvapi = SimpleNamespace(ok=True, ClkDomCtlGet=Mock(), ClkDomCtlSet=Mock())
        gpu._clkdom_get = Mock()
        self.assertIsNone(gpu.clkdom_layout())
        self.assertIsNone(gpu.read_rail_offset_mv())
        self.assertEqual(gpu.clkdom_controls_for_ui(), [])
        self.assertEqual(gpu.clkdom_pairing([{'domain':15, 'prog_mhz':270}]), {})
        self.assertFalse(gpu.set_rail_offset_mv(12.5)[0])
        self.assertFalse(gpu.set_clk_domain_offset(2,25)[0])
        gpu.nvapi.ClkDomCtlSet.assert_not_called()
        gpu._clkdom_get.assert_not_called()

if __name__ == '__main__':
    unittest.main()
