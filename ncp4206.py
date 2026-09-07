# Copyright (C) 2026 Thermetery Technology Co Limited
# SPDX-License-Identifier: GPL-3.0-or-later
"""NCP4206 absolute VID control, scoped to the measured GTX 770 board.

Public source: onsemi NCP4206 datasheet, Table 10/11 and Voltage Control Mode.
Only VOUT_COMMAND and bit 3 of the paired VR Config registers are writable.
No calibration, protection, nonvolatile, or phase-control fields are changed.
"""
import math
import threading
import time
from types import SimpleNamespace
from railctl import Rail, _linear11

NORMAL_MAX_MV = 1281
XOC_MAX_MV = 2000
MIN_MV = 600


def decode_vid(code):
    if not isinstance(code, int) or not 2 <= code <= 198:
        return None
    return 1600.0 - (code - 2) * 6.25


def encode_vid(mv):
    if not math.isfinite(mv) or not 375 <= mv <= 1600:
        raise ValueError('NCP4206 VID can encode only 375..1600 mV; XOC does not extend the register')
    # Never round a requested ceiling upward.
    return 2 + math.ceil((1600 - mv) / 6.25)


class NCP4206(Rail):
    absolute_voltage = True

    def __init__(self, nvapi):
        recipe = {'kind': 'ncp4206-absolute-v1', 'port': 2, 'addr7': 32,
                  'identity': [65, 12952, 1], 'normal_max': NORMAL_MAX_MV,
                  'xoc_max': XOC_MAX_MV, 'vid_max': 1600, 'min_mv': MIN_MV}
        p = SimpleNamespace(name='GTX 770 - NVVDD (NCP4206)', regulator='NCP4206',
                            rail='NVVDD', port=2, addr7=32, src=recipe,
                            read_only=False, env_min=MIN_MV, env_max=NORMAL_MAX_MV,
                            hw_min_mv=MIN_MV, hw_max_mv=XOC_MAX_MV)
        super().__init__(p, nvapi)
        self._mutex = threading.RLock()

    def present(self):
        identity = getattr(self.nvapi, 'selected', None) or {}
        if identity.get('devid') != 0x1184 or identity.get('subsys') != 0x1033196e:
            return False
        return (self.read(0x99, 1), self.read(0x9a, 2), self.read(0x9b, 1),
                self.read(0x20, 1)) == (65, 12952, 1, 32)

    def capture_control(self):
        if not self.present():
            raise ValueError('NCP4206 identity is unavailable')
        command, a, b = self.read(0x21, 2), self.read(0xd2, 1), self.read(0xd3, 1)
        if None in (command, a, b) or not 0 <= command <= 255 or (a & 8) != (b & 8):
            raise ValueError('NCP4206 command/mode read failed or paired VID modes disagree')
        enabled = bool(a & 8)
        if enabled and decode_vid(command) is None:
            raise ValueError('active NCP4206 VID is not a voltage code')
        return {'kind': 'absolute_vid', 'enabled': enabled, 'command': command}

    def telemetry(self):
        try:
            state = self.capture_control()
            raw = self.read(0xd7, 2)
            value = _linear11(raw) * 1000 if raw is not None else None
            if value is not None and not 300 <= value <= 2000:
                value = None
            return {'vout_mv': value, 'target_mv': decode_vid(state['command']) if state['enabled'] else None,
                    'control': state, 'offset_mv': None}
        except ValueError:
            return {}

    def read_vout(self):
        return self.telemetry().get('vout_mv')

    def validate_control(self, state, xoc=None):
        if not isinstance(state, dict) or set(state) != {'kind', 'enabled', 'command'}:
            raise ValueError('invalid NCP4206 profile control')
        if state['kind'] != 'absolute_vid' or type(state['enabled']) is not bool or type(state['command']) is not int:
            raise ValueError('invalid NCP4206 profile types')
        if not 0 <= state['command'] <= 255:
            raise ValueError('invalid NCP4206 command')
        if state['enabled']:
            target = decode_vid(state['command'])
            ceiling = XOC_MAX_MV if (self.xoc if xoc is None else xoc) else NORMAL_MAX_MV
            if target is None or not MIN_MV <= target <= ceiling:
                raise ValueError('NCP4206 target exceeds the saved mode or encoding bounds')
        return True

    def _write_checked(self, reg, value, width):
        if reg not in (0x21, 0xd2, 0xd3):
            raise ValueError('NCP4206 register is not writable')
        if not self._raw_write(reg, value, width) or self.read(reg, width) != value:
            raise ValueError(f'NCP4206 0x{reg:02X} write/readback failed')

    def _apply_control(self, state):
        # Only the command and VID_EN bits come from the profile. All other
        # register bits are retained from the current device, never replayed.
        a, b = self.read(0xd2, 1), self.read(0xd3, 1)
        if a is None or b is None:
            raise ValueError('NCP4206 configuration read failed')
        enabled = state['enabled']
        if enabled:
            self._write_checked(0x21, state['command'], 2)
        self._write_checked(0xd2, (a | 8) if enabled else (a & ~8), 1)
        self._write_checked(0xd3, (b | 8) if enabled else (b & ~8), 1)
        if not enabled:
            # Off codes may be restored only AFTER GPU VID mode is active.
            self._write_checked(0x21, state['command'], 2)
        if self.capture_control() != state:
            raise ValueError('NCP4206 final command/mode mismatch')

    def restore_control(self, state, *, recovery=False):
        with self._mutex:
            try:
                self.validate_control(state, xoc=True if recovery else None)
                before = self.capture_control()
                try:
                    self._apply_control(state)
                except Exception as exc:
                    try:
                        self._apply_control(before)
                    except Exception as rollback:
                        return False, f'{exc}; restoration also failed: {rollback}'
                    return False, f'{exc}; previous command/mode restored'
                return True, ('NCP4206 GPU VID mode restored' if not state['enabled'] else
                              f"NCP4206 target {decode_vid(state['command']):.2f} mV verified")
            except (ValueError, TypeError) as exc:
                return False, str(exc)

    def plan(self, mv):
        try:
            value = float(mv)
            ceiling = XOC_MAX_MV if self.xoc else NORMAL_MAX_MV
            if not math.isfinite(value) or not MIN_MV <= value <= ceiling:
                raise ValueError(f'NCP4206 target must be {MIN_MV}..{ceiling} mV in this mode')
            code = encode_vid(value)
            self.capture_control()
            return True, f'NCP4206 target {decode_vid(code):.2f} mV (VID 0x{code:02X})'
        except (ValueError, TypeError) as exc:
            return False, str(exc)

    def set_voltage_mv(self, mv, *, acknowledged=False):
        if not acknowledged:
            return False, 'I2C voltage writes require acknowledgment'
        with self._mutex:
            ok, msg = self.plan(mv)
            if not ok:
                return ok, msg
            return self.restore_control({'kind': 'absolute_vid', 'enabled': True,
                                         'command': encode_vid(float(mv))})

    def reset(self):
        return self.restore_control({'kind': 'absolute_vid', 'enabled': False, 'command': 0})

    def verify(self, *, acknowledged=False, ref=None, log=None):
        if not acknowledged:
            return False, 'I2C verification requires acknowledgment', []
        with self._mutex:
            original = self.capture_control()
            baseline = self.read_vout()
            if baseline is None or not 800 <= baseline <= NORMAL_MAX_MV - 30:
                return False, 'loaded rail lacks headroom for the bounded verification step', []
            target = math.floor((baseline + 25) / 6.25) * 6.25
            samples = []
            result = (False, 'NCP4206 verification did not run', samples)
            try:
                ok, msg = self.set_voltage_mv(target, acknowledged=True)
                if not ok:
                    result = (False, msg, samples)
                else:
                    for _ in range(5):
                        time.sleep(.15)
                        samples.append(self.read_vout())
                    valid = [v for v in samples if v is not None]
                    moved = len(valid) == 5 and min(valid) >= baseline + 8 and all(abs(v-target) <= 15 for v in valid)
                    result = (moved, f'NCP4206 {baseline:.2f} -> target {target:.2f} mV; VMON {valid}', samples)
            finally:
                ok, msg = self.restore_control(original, recovery=True)
            if not ok:
                return False, 'NCP4206 verification restoration failed: ' + msg, samples
            return result
