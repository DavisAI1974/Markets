import unittest
import struct
from prepare_complete_dipole_checks import component_row,validate_wire_components


class DipoleInputTests(unittest.TestCase):
    def test_state_controls_value_not_zero(self):
        self.assertEqual(component_row({'a':{'value':0.,'state':0},'b':{'value':0.,'state':1}},['a','b']),([0.,0.],[0,1]))

    def test_invalid_nonzero_and_missing_identity_fail_closed(self):
        for raw in [{'a':{'value':2.,'state':1}},{}]:
            with self.assertRaises(AssertionError):component_row(raw,['a'])

    def test_wire_null_for_missing_and_float32_for_present(self):
        v=struct.unpack('<f',struct.pack('<f',0.123456789))[0]
        wanted=[{'name':'a','state':'PRESENT','value':v},{'name':'b','state':'MISSING','value':None}]
        validate_wire_components(wanted,['a','b'],struct.pack('<2f',0.123456789,0),[0,1])
        wanted[1]['value']=0.
        with self.assertRaises(AssertionError):validate_wire_components(wanted,['a','b'],struct.pack('<2f',0.123456789,0),[0,1])


if __name__=='__main__':unittest.main()
